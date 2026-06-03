import asyncio
import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, field_validator
from typing import AsyncGenerator, Optional, List

from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.models.database import (
    Conversation, ConversationStatus, ExecutionMode,
    User, Project, Task, TaskStatus, AgentType
)
from app.agents.requirements_gatherer import RequirementsGathererAgent
from app.core.orchestrator import MetaAgentOrchestrator
from app.utils.logger import logger
from app.utils.dependencies import enforce_limits, apply_rate_limits

router = APIRouter()
gatherer = RequirementsGathererAgent()
orchestrator = MetaAgentOrchestrator()

MAX_GATHERING_TURNS = 10

_CONFIRM_RE = re.compile(
    r'\b(execute|yes|go|start|proceed|run|do\s+it|build|ship|confirm|ok|okay|sure|absolutely|definitely)\b',
    re.IGNORECASE,
)

_MODIFY_RE = re.compile(
    r'\b(change|update|modify|edit|revise|adjust|add|remove|replace|instead|actually|wait|hold)\b',
    re.IGNORECASE,
)


def _is_confirmation(message: str) -> bool:
    return bool(_CONFIRM_RE.search(message)) and not _MODIFY_RE.search(message)


def _is_modification(message: str) -> bool:
    return bool(_MODIFY_RE.search(message))


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    project_id: int
    mode: str = "normal"
    initial_message: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ["normal", "hardcore"]:
            raise ValueError("Mode must be 'normal' or 'hardcore'")
        return v

    @field_validator("initial_message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        if len(v) > 5000:
            raise ValueError("Message too long (max 5000 characters)")
        return v.strip()


class MessageSend(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class ConversationResponse(BaseModel):
    id: int
    project_id: int
    mode: str
    status: str
    messages: List[dict]
    gathered_requirements: Optional[dict] = None
    final_prompt: Optional[str] = None
    gathering_turn_count: int = 0

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_gathering_task(project_id: int, title: str = "Requirements Gathering") -> Task:
    return Task(
        project_id=project_id,
        title=title,
        description="Gather complete requirements before execution",
        agent_type=AgentType.REQUIREMENTS_GATHERER,
        status=TaskStatus.IN_PROGRESS,
    )


_MAX_CONTEXT_CHARS = 12_000


def _extract_prior_result(conversation: Conversation) -> Optional[dict]:
    """Walk messages newest-first and return the first embedded result dict."""
    for msg in reversed(conversation.messages):
        if msg.get("role") == "assistant" and isinstance(msg.get("result"), dict):
            return msg["result"]
    return None


def _build_refinement_context(prior_result: dict) -> str:
    """Flatten agent outputs into a text summary the decomposer can use."""
    sections: list[str] = []

    results = prior_result.get("results") or prior_result.get("task_results") or {}
    if not results:
        raw = json.dumps(prior_result, indent=2)
        return raw[:_MAX_CONTEXT_CHARS]

    for task_id, task_data in results.items():
        output = task_data.get("output", {})
        agent = task_data.get("agent", f"task_{task_id}")
        header = f"── {agent} (task {task_id}) ──"

        if agent == "code_generator":
            code = output.get("code") or output.get("raw_output", "")
            sections.append(f"{header}\n```\n{code}\n```")

        elif agent == "api_designer":
            spec = json.dumps(output.get("api_design", output), indent=2)
            sections.append(f"{header}\n{spec}")

        elif agent == "database_schema":
            sql = output.get("sql_ddl", "")
            schema = json.dumps(output.get("schema", {}), indent=2) if output.get("schema") else ""
            sections.append(f"{header}\n{sql}\n{schema}")

        elif agent == "frontend_generator":
            for i, comp in enumerate(output.get("components", [])):
                sections.append(f"{header} component {i+1}\n```\n{comp}\n```")

        elif agent in ("testing_agent", "documentation_agent"):
            text = output.get("test_code") or output.get("documentation") or output.get("raw_output", "")
            sections.append(f"{header}\n{text}")

        elif agent == "devops":
            for fname, content in output.get("files", {}).items():
                sections.append(f"{header} {fname}\n{content}")

        else:
            sections.append(f"{header}\n{json.dumps(output, indent=2)}")

    combined = "\n\n".join(sections)
    if len(combined) > _MAX_CONTEXT_CHARS:
        combined = combined[:_MAX_CONTEXT_CHARS] + "\n... (truncated)"
    return combined


def _force_ready_with_fallback(conversation: Conversation) -> None:
    """Transition to READY using whatever requirements have been gathered so far."""
    gathered = conversation.gathered_requirements or {}
    conversation.status = ConversationStatus.READY
    conversation.final_prompt = json.dumps(gathered) if gathered else conversation.messages[0].get("content", "")
    conversation.messages.append({
        "role": "assistant",
        "content": (
            f"Gathering limit reached ({MAX_GATHERING_TURNS} turns). "
            "Proceeding with the requirements collected so far.\n\n"
            "Reply **execute** to start building, or send a message to adjust."
        ),
    })


async def _guarded(coro, conversation_id: int):
    """
    Wrap a background coroutine so an unhandled exception can never vanish
    silently into a discarded ``asyncio.Task``.  On failure it logs and marks
    the conversation COMPLETED with an error message, using its own session.
    """
    try:
        await coro
    except Exception as e:
        logger.error("Background task failed conv=%d: %s", conversation_id, e, exc_info=True)
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv:
                conv.status = ConversationStatus.COMPLETED
                conv.messages.append({"role": "assistant", "content": f"Execution failed: {e}"})
                flag_modified(conv, "messages")
                db.commit()
        finally:
            db.close()


async def _ask_gatherer(conversation: Conversation) -> None:
    """
    Run requirements gatherer using proper multi-turn history (run_with_history).
    Updates conversation messages and gathered_requirements in place.

    Owns its own DB session (``SessionLocal``) for the full duration of the
    async gatherer call.  It never borrows the caller's request-scoped session,
    because awaiting the agent yields control back to the event loop and any
    session it touched could be mutated concurrently by another coroutine.
    The conversation is re-loaded inside the local session by id; callers must
    ``db.refresh(conversation)`` afterwards to observe the committed changes.

    Enforces a max turn limit and transitions out of GATHERING on failure.
    """
    conversation_id = conversation.id

    with SessionLocal() as db:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
        ).first()
        if conversation is None:
            logger.error("_ask_gatherer: conversation %d not found", conversation_id)
            return

        try:
            conversation.gathering_turn_count += 1

            # ── Max turns exceeded: force-transition to READY ────────────────
            if conversation.gathering_turn_count > MAX_GATHERING_TURNS:
                logger.warning(
                    "Conversation %d hit gathering turn limit (%d)",
                    conversation.id, MAX_GATHERING_TURNS,
                )
                _force_ready_with_fallback(conversation)
                return  # JSON flags + commit still run in `finally`

            gathering_task = _make_gathering_task(conversation.project_id, "Requirements Gathering (turn)")
            db.add(gathering_task)
            db.flush()

            gathered = conversation.gathered_requirements or {}

            try:
                result = await gatherer.run_with_history(
                    conversation_messages=conversation.messages,
                    gathered_so_far=gathered,
                    task_db_record=gathering_task,
                    db=db,
                )

                if result.success:
                    output = result.output
                    status_val = output.get("status")

                    if status_val == "needs_clarification":
                        conversation.messages.append({
                            "role": "assistant",
                            "content": output["question"],
                        })
                        conversation.gathered_requirements = output.get("gathered_so_far", gathered)

                    elif status_val == "ready":
                        conversation.status = ConversationStatus.READY
                        conversation.final_prompt = output["final_prompt"]
                        conversation.gathered_requirements = output.get("requirements_summary", {})
                        conversation.messages.append({
                            "role": "assistant",
                            "content": (
                                f"I have everything I need.\n\n"
                                f"**Final specification:**\n{output['final_prompt']}\n\n"
                                f"Reply **execute** to start building, or tell me what to change."
                            ),
                        })
                    else:
                        conversation.messages.append({
                            "role": "assistant",
                            "content": "I had trouble parsing that. Could you rephrase?",
                        })

                else:
                    # Agent returned an error result but didn't throw — recoverable
                    logger.warning("Gatherer returned error for conversation %d: %s", conversation.id, result.error)
                    if gathered:
                        _force_ready_with_fallback(conversation)
                    else:
                        conversation.status = ConversationStatus.FAILED
                        conversation.messages.append({
                            "role": "assistant",
                            "content": f"Requirements gathering failed: {result.error}",
                        })

                gathering_task.status = TaskStatus.COMPLETED

            except Exception as e:
                logger.error("Requirements gathering failed for conversation %d: %s", conversation.id, e, exc_info=True)
                gathering_task.status = TaskStatus.FAILED
                gathering_task.error_message = str(e)

                if gathered:
                    _force_ready_with_fallback(conversation)
                else:
                    conversation.status = ConversationStatus.FAILED
                    conversation.messages.append({
                        "role": "assistant",
                        "content": (
                            f"Requirements gathering encountered an error: {e}\n\n"
                            "Use the reset endpoint to try again."
                        ),
                    })

        finally:
            # JSON mutation tracking — SQLAlchemy does not detect in-place
            # list/dict edits (e.g. messages.append). Flag BOTH JSON columns on
            # EVERY branch (including the max-turns early return above) so no
            # update is silently dropped, then commit exactly once.
            flag_modified(conversation, "messages")
            flag_modified(conversation, "gathered_requirements")
            db.commit()


async def _execute_in_background(
    conversation_id: int,
    user_request: str,
    project_id: int,
    project_context: Optional[str] = None,
) -> None:
    """Run orchestrator with its own DB session, update conversation on finish."""
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
        ).first()
        if not conversation:
            logger.error("Background exec: conversation %d not found", conversation_id)
            return

        result = await orchestrator.process(
            user_request=user_request,
            project_id=project_id,
            db=db,
            project_context=project_context,
        )

        first_task = (
            db.query(Task)
            .filter(Task.project_id == project_id)
            .order_by(Task.id.desc())
            .first()
        )
        if first_task:
            conversation.execution_task_id = first_task.id

        conversation.status = ConversationStatus.COMPLETED
        conversation.messages.append({
            "role": "assistant",
            "content": "Execution complete! Here are your results:",
            "result": result.to_dict(),
        })
        logger.info("Background exec completed for conversation %d", conversation_id)

    except Exception as e:
        logger.error("Background exec failed for conversation %d: %s", conversation_id, e, exc_info=True)
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
        ).first()
        if conversation:
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": f"Execution failed: {str(e)}",
            })

    finally:
        if conversation:
            flag_modified(conversation, "messages")
            db.commit()
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    data: ConversationCreate,
    current_user: User = Depends(enforce_limits),
    db: Session = Depends(get_db),
):
    # Rate limiting (per-minute burst + daily tier quota) is applied by the
    # enforce_limits dependency — every start launches a run (NORMAL → execute,
    # HARDCORE → gatherer), so enforcement at the route level is correct here.
    project = db.query(Project).filter(
        Project.id == data.project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    mode = ExecutionMode.HARDCORE if data.mode == "hardcore" else ExecutionMode.NORMAL

    conversation = Conversation(
        project_id=data.project_id,
        user_id=current_user.id,
        mode=mode,
        status=ConversationStatus.GATHERING if mode == ExecutionMode.HARDCORE else ConversationStatus.READY,
        messages=[{"role": "user", "content": data.initial_message}],
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.info("Conversation %d started | mode=%s | user=%s", conversation.id, mode.value, current_user.email)

    # ── NORMAL MODE: kick off background execution, return immediately ───────
    if mode == ExecutionMode.NORMAL:
        # Same guarded transition as send_message: atomically flip READY→EXECUTING
        # and commit BEFORE launching the background task. The conversation was
        # just created (no real contention here) but we keep the pattern uniform
        # so the "only one launcher" invariant holds everywhere.
        flipped = db.query(Conversation).filter(
            Conversation.id == conversation.id,
            Conversation.status == ConversationStatus.READY,
        ).update(
            {
                Conversation.status: ConversationStatus.EXECUTING,
                Conversation.final_prompt: data.initial_message,
            },
            synchronize_session=False,
        )
        db.commit()
        db.refresh(conversation)

        if flipped:
            asyncio.create_task(_guarded(_execute_in_background(
                conversation_id=conversation.id,
                user_request=data.initial_message,
                project_id=data.project_id,
            ), conversation.id))

    # ── HARDCORE MODE: start gathering (fast — no orchestrator) ───────────────
    else:
        await _ask_gatherer(conversation)
        # _ask_gatherer committed via its own session; reload into the request
        # session so the response reflects the gathered state.
        db.refresh(conversation)

    return conversation


@router.post("/{conversation_id}/message", response_model=ConversationResponse)
async def send_message(
    conversation_id: int,
    data: MessageSend,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # ── Reject any input while a run is already active ────────────────────────
    # No new message (and therefore no new execution) is accepted while the
    # conversation is mid-run. This is the first line of defence against
    # duplicate runs; the atomic status transitions below close the remaining
    # concurrent-confirmation race.
    if conversation.status in (ConversationStatus.EXECUTING, ConversationStatus.REFINING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A run is already in progress for this conversation; wait for it to finish.",
        )

    conversation.messages.append({"role": "user", "content": data.message})
    flag_modified(conversation, "messages")
    db.commit()

    # ── GATHERING: continue questions ─────────────────────────────────────────
    if (conversation.mode == ExecutionMode.HARDCORE
            and conversation.status == ConversationStatus.GATHERING):
        await _ask_gatherer(conversation)
        # _ask_gatherer owns its own session; refresh below (line ~474) reloads
        # the committed changes into the request session before responding.

    # ── READY: decide between execute vs. modify ───────────────────────────────
    elif conversation.status == ConversationStatus.READY:
        if _is_confirmation(data.message):
            # Same enforcement as start_conversation / refinement / agents.execute.
            apply_rate_limits(current_user, db)
            # Atomic READY→EXECUTING transition committed BEFORE launching the
            # background task. The conditional UPDATE only succeeds for the
            # single request that observes status=READY, so two concurrent
            # "execute" confirmations cannot both launch the orchestrator.
            flipped = db.query(Conversation).filter(
                Conversation.id == conversation.id,
                Conversation.status == ConversationStatus.READY,
            ).update(
                {Conversation.status: ConversationStatus.EXECUTING},
                synchronize_session=False,
            )
            db.commit()
            db.refresh(conversation)
            if not flipped:
                # Lost the race — another request already started execution.
                return conversation

            asyncio.create_task(_guarded(_execute_in_background(
                conversation_id=conversation.id,
                user_request=conversation.final_prompt,
                project_id=conversation.project_id,
            ), conversation.id))

        elif _is_modification(data.message):
            conversation.status = ConversationStatus.GATHERING
            conversation.final_prompt = None
            conversation.messages.append({
                "role": "assistant",
                "content": "Got it — let me update the requirements. What would you like to change?",
            })
            flag_modified(conversation, "messages")
            db.commit()

        else:
            conversation.messages.append({
                "role": "assistant",
                "content": (
                    "I'm ready to build. Reply **execute** to start, "
                    "or tell me what you'd like to change."
                ),
            })
            flag_modified(conversation, "messages")
            db.commit()

    # ── COMPLETED: refinement in background ──────────────────────────────────
    elif conversation.status == ConversationStatus.COMPLETED:
        # Refinement launches a run — same enforcement as the execute path above.
        apply_rate_limits(current_user, db)
        # Atomic COMPLETED→REFINING transition — same guard as execute: only the
        # request that flips the row launches the refinement run, so concurrent
        # refine requests cannot double-launch.
        flipped = db.query(Conversation).filter(
            Conversation.id == conversation.id,
            Conversation.status == ConversationStatus.COMPLETED,
        ).update(
            {Conversation.status: ConversationStatus.REFINING},
            synchronize_session=False,
        )
        db.commit()
        db.refresh(conversation)
        if not flipped:
            # Lost the race — another request already started refinement.
            return conversation

        prior = _extract_prior_result(conversation)
        context = _build_refinement_context(prior) if prior else None
        if not context:
            logger.warning("Conversation %d: no prior result found for refinement", conversation.id)

        asyncio.create_task(_guarded(_execute_in_background(
            conversation_id=conversation.id,
            user_request=f"Refinement request: {data.message}",
            project_id=conversation.project_id,
            project_context=context,
        ), conversation.id))

    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    project_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if project_id:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id,
        ).first()
        if not project:
            raise HTTPException(404, "Project not found")
        query = query.filter(Conversation.project_id == project_id)
    offset = (page - 1) * limit
    return query.order_by(Conversation.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{conversation_id}/stream")
async def stream_conversation_progress(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    SSE endpoint — streams task-level progress events while a conversation is
    executing.  Closes automatically when the conversation reaches COMPLETED.

    Event format (text/event-stream):
        data: {"type": "task_update", "task_id": 1, "status": "in_progress", "agent": "code_generator"}
        data: {"type": "conversation_status", "status": "completed"}
        data: {"type": "done"}
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        seen_task_states: dict = {}
        last_conv_status: Optional[str] = None
        last_updated_at: Optional[datetime] = None
        poll_interval = 2.0
        max_polls = 180  # 6 minutes at 2s intervals
        idle_streak = 0

        for _ in range(max_polls):
            # Refresh only the conversation row — not the entire identity map
            db.expire(conversation)
            conv = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            if not conv:
                break

            # Only query tasks when the conversation has actually been touched
            conv_changed = conv.updated_at != last_updated_at
            last_updated_at = conv.updated_at

            if conv_changed:
                idle_streak = 0
                # populate_existing(): the orchestrator mutates Task rows from a
                # SEPARATE session, so without this the identity map would hand
                # back stale Task instances (the fresh SELECT does not overwrite
                # already-loaded attributes) and task_update events would stop
                # firing. This refreshes in-place WITHOUT issuing any extra query.
                tasks = (
                    db.query(Task)
                    .filter(Task.project_id == conv.project_id)
                    .order_by(Task.execution_order)
                    .populate_existing()
                    .all()
                )

                for task in tasks:
                    current_status = task.status.value
                    if seen_task_states.get(task.id) != current_status:
                        seen_task_states[task.id] = current_status
                        yield f"data: {json.dumps({'type': 'task_update', 'task_id': task.id, 'title': task.title, 'agent': task.agent_type.value, 'status': current_status})}\n\n"
            else:
                idle_streak += 1

            # Only emit conversation status when it changes
            conv_status = conv.status.value
            if conv_status != last_conv_status:
                last_conv_status = conv_status
                yield f"data: {json.dumps({'type': 'conversation_status', 'status': conv_status})}\n\n"

            if conv.status in (ConversationStatus.COMPLETED, ConversationStatus.REFINING):
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

            # Heartbeat so clients know the connection is alive
            if idle_streak > 0 and idle_streak % 5 == 0:
                yield f": heartbeat\n\n"

            await asyncio.sleep(poll_interval)
        else:
            yield f"data: {json.dumps({'type': 'timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{conversation_id}/reset", response_model=ConversationResponse)
async def reset_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reset a stuck or failed conversation back to GATHERING so the user
    can restart the requirements flow.  Preserves message history.
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.status not in (
        ConversationStatus.GATHERING,
        ConversationStatus.FAILED,
        ConversationStatus.READY,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reset conversation in '{conversation.status.value}' state",
        )

    conversation.status = ConversationStatus.GATHERING
    conversation.gathering_turn_count = 0
    conversation.gathered_requirements = None
    conversation.final_prompt = None
    conversation.messages.append({
        "role": "assistant",
        "content": "Conversation has been reset. Let's start gathering requirements again — what would you like to build?",
    })
    flag_modified(conversation, "messages")
    db.commit()
    db.refresh(conversation)

    logger.info("Conversation %d reset by user %s", conversation.id, current_user.email)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    db.delete(conversation)
    db.commit()
