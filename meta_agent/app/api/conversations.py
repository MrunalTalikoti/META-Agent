from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

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
    mode: str = "normal"  # "normal" or "hardcore"
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


class MessageResponse(BaseModel):
    role: str
    content: str
    result: Optional[dict] = None


class ConversationResponse(BaseModel):
    id: int
    mode: str
    status: str
    messages: List[dict]
    gathered_requirements: Optional[dict] = None
    final_prompt: Optional[str] = None

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new conversation in either mode:
    - NORMAL: Executes immediately
    - HARDCORE: Starts requirements gathering
    """

    # Verify project access
    project = db.query(Project).filter(
        Project.id == data.project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Determine mode
    mode = ExecutionMode.HARDCORE if data.mode == "hardcore" else ExecutionMode.NORMAL

    # Create conversation
    conversation = Conversation(
        project_id=data.project_id,
        user_id=current_user.id,
        mode=mode,
        status=ConversationStatus.GATHERING if mode == ExecutionMode.HARDCORE else ConversationStatus.READY,
        messages=[{"role": "user", "content": data.initial_message}]
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.info(
        f"Conversation started | mode={mode.value} | "
        f"user={current_user.email} | project={project.name}"
    )

    # ── NORMAL MODE: Execute immediately ──────────────────────────────────────
    if mode == ExecutionMode.NORMAL:
        conversation.status = ConversationStatus.EXECUTING
        conversation.final_prompt = data.initial_message
        db.commit()

        try:
            # Execute
            result = await orchestrator.process(
                user_request=data.initial_message,
                project_id=data.project_id,
                db=db
            )

            # Update conversation
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": "✓ Execution complete! See results below.",
                "result": result.to_dict()
            })
            flag_modified(conversation, "messages")
            db.commit()

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": f"✗ Execution failed: {str(e)}"
            })
            flag_modified(conversation, "messages")
            db.commit()

    # ── HARDCORE MODE: Start requirements gathering ──────────────────────────
    else:
        # Create a task for the requirements gathering
        gathering_task = Task(
            project_id=data.project_id,
            title="Requirements Gathering",
            description="Gather complete requirements before execution",
            agent_type=AgentType.REQUIREMENTS_GATHERER,
            status=TaskStatus.IN_PROGRESS
        )
        db.add(gathering_task)
        db.flush()

        try:
            # Ask first clarifying question
            result = await gatherer.run(
                description=f"User's initial request: {data.initial_message}\n\nAsk your first clarifying question.",
                task_db_record=gathering_task,
                db=db
            )

            if result.success:
                output = result.output

                if output.get("status") == "needs_clarification":
                    # Add assistant's question to conversation
                    conversation.messages.append({
                        "role": "assistant",
                        "content": output["question"]
                    })
                    conversation.gathered_requirements = output.get("gathered_so_far", {})
                    flag_modified(conversation, "messages")
                    flag_modified(conversation, "gathered_requirements")
                    db.commit()

                elif output.get("status") == "ready":
                    # Rare case: first message was complete enough
                    conversation.status = ConversationStatus.READY
                    conversation.final_prompt = output["final_prompt"]
                    conversation.gathered_requirements = output.get("requirements_summary", {})
                    conversation.messages.append({
                        "role": "assistant",
                        "content": f"Perfect! I have everything I need:\n\n{output['final_prompt']}\n\nReply with 'execute' to proceed."
                    })
                    flag_modified(conversation, "messages")
                    db.commit()

                else:
                    # Error case
                    conversation.messages.append({
                        "role": "assistant",
                        "content": "I encountered an error understanding your request. Could you rephrase it?"
                    })
                    flag_modified(conversation, "messages")
                    db.commit()

            gathering_task.status = TaskStatus.COMPLETED
            db.commit()

        except Exception as e:
            logger.error(f"Requirements gathering failed: {e}", exc_info=True)
            gathering_task.status = TaskStatus.FAILED
            gathering_task.error_message = str(e)
            conversation.messages.append({
                "role": "assistant",
                "content": f"Sorry, I encountered an error: {str(e)}"
            })
            flag_modified(conversation, "messages")
            db.commit()

    db.refresh(conversation)
    return conversation


@router.post("/{conversation_id}/message", response_model=ConversationResponse)
async def send_message(
    conversation_id: int,
    data: MessageSend,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Continue conversation:
    - HARDCORE + GATHERING: Continue requirements gathering
    - HARDCORE + READY: Execute when user says "execute"
    - Any + COMPLETED: Refine the output
    """

    # Fetch conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Add user message
    conversation.messages.append({"role": "user", "content": data.message})
    flag_modified(conversation, "messages")
    db.commit()

    # ── HARDCORE + GATHERING: Continue asking questions ──────────────────────
    if (conversation.mode == ExecutionMode.HARDCORE and 
        conversation.status == ConversationStatus.GATHERING):

        gathering_task = Task(
            project_id=conversation.project_id,
            title="Requirements Gathering (continued)",
            description="Continue gathering requirements",
            agent_type=AgentType.REQUIREMENTS_GATHERER,
            status=TaskStatus.IN_PROGRESS
        )
        db.add(gathering_task)
        db.flush()

        try:
            gathered = conversation.gathered_requirements or {}

            # Build conversation history for context
            history = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in conversation.messages
            ])

            result = await gatherer.run(
                description=f"Conversation so far:\n{history}\n\nGathered requirements: {gathered}\n\nBased on the user's latest response, either ask the next clarifying question or mark as ready if you have enough information.",
                task_db_record=gathering_task,
                db=db
            )

            if result.success:
                output = result.output

                if output.get("status") == "ready":
                    # Requirements complete!
                    conversation.status = ConversationStatus.READY
                    conversation.final_prompt = output["final_prompt"]
                    conversation.gathered_requirements = output.get("requirements_summary", {})
                    conversation.messages.append({
                        "role": "assistant",
                        "content": f"Perfect! I have all the information I need.\n\n**Final Specification:**\n{output['final_prompt']}\n\n**Reply with 'execute' to start building, or ask me to change anything.**"
                    })

                elif output.get("status") == "needs_clarification":
                    # More questions
                    conversation.messages.append({
                        "role": "assistant",
                        "content": output["question"]
                    })
                    conversation.gathered_requirements = output.get("gathered_so_far", {})

                else:
                    conversation.messages.append({
                        "role": "assistant",
                        "content": "I'm having trouble understanding. Could you clarify?"
                    })

                flag_modified(conversation, "messages")
                flag_modified(conversation, "gathered_requirements")
                db.commit()

            gathering_task.status = TaskStatus.COMPLETED
            db.commit()

        except Exception as e:
            logger.error(f"Requirements gathering failed: {e}", exc_info=True)
            gathering_task.status = TaskStatus.FAILED
            db.commit()

    # ── READY + "execute": Start execution ───────────────────────────────────
    elif (conversation.status == ConversationStatus.READY and 
          data.message.lower().strip() in ["execute", "yes", "go", "start", "proceed"]):

        conversation.status = ConversationStatus.EXECUTING
        db.commit()

        try:
            result = await orchestrator.process(
                user_request=conversation.final_prompt,
                project_id=conversation.project_id,
                db=db
            )

            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": "✓ Execution complete! Here are your results:",
                "result": result.to_dict()
            })
            flag_modified(conversation, "messages")
            db.commit()

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": f"✗ Execution failed: {str(e)}"
            })
            flag_modified(conversation, "messages")
            db.commit()

    # ── COMPLETED: Refinement ────────────────────────────────────────────────
    elif conversation.status == ConversationStatus.COMPLETED:
        conversation.status = ConversationStatus.REFINING
        db.commit()

        try:
            # Build refinement prompt
            refinement_prompt = f"Based on the previously generated code, make this modification: {data.message}"

            result = await orchestrator.process(
                user_request=refinement_prompt,
                project_id=conversation.project_id,
                db=db
            )

            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": "✓ Refinement complete!",
                "result": result.to_dict()
            })
            flag_modified(conversation, "messages")
            db.commit()

        except Exception as e:
            logger.error(f"Refinement failed: {e}", exc_info=True)
            conversation.status = ConversationStatus.COMPLETED
            conversation.messages.append({
                "role": "assistant",
                "content": f"✗ Refinement failed: {str(e)}"
            })
            flag_modified(conversation, "messages")
            db.commit()

    # ── READY but not "execute": User changing requirements ──────────────────
    elif conversation.status == ConversationStatus.READY:
        # User wants to modify the final prompt
        conversation.status = ConversationStatus.GATHERING
        conversation.final_prompt = None
        conversation.messages.append({
            "role": "assistant",
            "content": "Got it, let me update the requirements. What would you like to change?"
        })
        flag_modified(conversation, "messages")
        db.commit()

    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get conversation details and history"""

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return conversation


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all conversations for current user, optionally filtered by project"""

    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)

    if project_id:
        # Verify project access
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(404, "Project not found")
        
        query = query.filter(Conversation.project_id == project_id)

    conversations = query.order_by(Conversation.created_at.desc()).all()
    return conversations


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation"""

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(404, "Conversation not found")

    db.delete(conversation)
    db.commit()