import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, field_validator
from typing import AsyncGenerator, Optional, List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database import (
    Conversation, ConversationStatus, ExecutionMode,
    User, Project, Task, TaskStatus, AgentType
)
from app.agents.requirements_gatherer import RequirementsGathererAgent
from app.core.orchestrator import MetaAgentOrchestrator
from app.utils.logger import logger
from app.utils.tier_limits import check_rate_limit

router = APIRouter()
gatherer = RequirementsGathererAgent()
orchestrator = MetaAgentOrchestrator()


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
    mode: str
    status: str
    messages: List[dict]
    gathered_requirements: Optional[dict] = None
    final_prompt: Optional[str] = None

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


async def _ask_gatherer(conversation: Conversation, db: Session) -> None:
    """
    Run requirements gatherer using proper multi-turn history (run_with_history).
    Updates conversation messages and gathered_requirements in place.
    """
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
            conversation.messages.append({
                "role": "assistant",
                "content": f"Sorry, I encountered an error: {result.error}",
            })

        gathering_task.status = TaskStatus.COMPLETED
    except Exception as e:
        logger.error(f"Requirements gathering failed: {e}", exc_info=True)
        gathering_task.status = TaskStatus.FAILED
        gathering_task.error_message = str(e)
        conversation.messages.append({
            "role": "assistant",
            "content": f"Sorry, something went wrong: {str(e)}",
        })

    flag_modified(conversation, "messages")
    flag_modified(conversation, "gathered_requirements")
    db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Rate limit
    check_rate_limit(current_user, db)

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

    logger.info(f"Conversation {conversation.id} started | mode={mode.value} | user={current_user.email}")

    # ── NORMAL MODE: execute immediately ──────────────────────────────────────
    if mode == ExecutionMode.NORMAL:
        conversation.status = ConversationStatus.EXECUTING
        conversation.final_prompt = data.initial_message
        db.commit()
        try:
            result = await orchestrator.process(
                user_request=data.initial_message,
                project_id=data.project_id,
                db=db,
            )
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": "✓ Execution complete! See results below.",
                "result": result.to_dict(),
            })
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": f"✗ Execution failed: {str(e)}",
            })
        flag_modified(conversation, "messages")
        db.commit()

    # ── HARDCORE MODE: start gathering ────────────────────────────────────────
    else:
        await _ask_gatherer(conversation, db)

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

    # Append user message
    conversation.messages.append({"role": "user", "content": data.message})
    flag_modified(conversation, "messages")
    db.commit()

    # ── GATHERING: continue questions ─────────────────────────────────────────
    if (conversation.mode == ExecutionMode.HARDCORE
            and conversation.status == ConversationStatus.GATHERING):
        await _ask_gatherer(conversation, db)

    # ── READY + trigger word: execute ─────────────────────────────────────────
    elif (conversation.status == ConversationStatus.READY
          and data.message.lower().strip() in {"execute", "yes", "go", "start", "proceed", "run"}):

        check_rate_limit(current_user, db)
        conversation.status = ConversationStatus.EXECUTING
        db.commit()

        try:
            result = await orchestrator.process(
                user_request=conversation.final_prompt,
                project_id=conversation.project_id,
                db=db,
            )
            # Set execution_task_id to first task created (approximate link)
            first_task = db.query(Task).filter(
                Task.project_id == conversation.project_id
            ).order_by(Task.id.desc()).first()
            if first_task:
                conversation.execution_task_id = first_task.id

            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": "✓ Execution complete! Here are your results:",
                "result": result.to_dict(),
            })
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": f"✗ Execution failed: {str(e)}",
            })
        flag_modified(conversation, "messages")
        db.commit()

    # ── COMPLETED: refinement ─────────────────────────────────────────────────
    elif conversation.status == ConversationStatus.COMPLETED:
        check_rate_limit(current_user, db)
        conversation.status = ConversationStatus.REFINING
        db.commit()
        try:
            refinement_prompt = f"Modify the previously generated code: {data.message}"
            result = await orchestrator.process(
                user_request=refinement_prompt,
                project_id=conversation.project_id,
                db=db,
            )
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": "✓ Refinement complete!",
                "result": result.to_dict(),
            })
        except Exception as e:
            logger.error(f"Refinement failed: {e}", exc_info=True)
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": f"✗ Refinement failed: {str(e)}",
            })
        flag_modified(conversation, "messages")
        db.commit()

    # ── READY but not trigger: user modifying requirements ────────────────────
    elif conversation.status == ConversationStatus.READY:
        conversation.status = ConversationStatus.GATHERING
        conversation.final_prompt = None
        conversation.messages.append({
            "role": "assistant",
            "content": "Got it — let me update the requirements. What would you like to change?",
        })
        flag_modified(conversation, "messages")
        db.commit()

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
        poll_interval = 1.0  # seconds
        max_polls = 120      # 2-minute hard cap

        for _ in range(max_polls):
            # Refresh conversation and its project tasks from DB
            db.expire_all()
            conv = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            if not conv:
                break

            tasks = (
                db.query(Task)
                .filter(Task.project_id == conv.project_id)
                .order_by(Task.execution_order)
                .all()
            )

            for task in tasks:
                current_status = task.status.value
                if seen_task_states.get(task.id) != current_status:
                    seen_task_states[task.id] = current_status
                    event = json.dumps({
                        "type": "task_update",
                        "task_id": task.id,
                        "title": task.title,
                        "agent": task.agent_type.value,
                        "status": current_status,
                    })
                    yield f"data: {event}\n\n"

            # Emit conversation status on each change
            conv_status = conv.status.value
            status_event = json.dumps({
                "type": "conversation_status",
                "status": conv_status,
            })
            yield f"data: {status_event}\n\n"

            if conv.status == ConversationStatus.COMPLETED:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

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