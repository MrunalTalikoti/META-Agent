from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.orchestrator import MetaAgentOrchestrator
from app.models.database import Project, Task, User
from app.utils.logger import logger

router = APIRouter()
orchestrator = MetaAgentOrchestrator()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    project_id: int
    request: str

    @field_validator("request")
    @classmethod
    def request_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Request cannot be empty")
        if len(v) > 2000:
            raise ValueError("Request too long (max 2000 characters)")
        return v.strip()


class TaskStatusResponse(BaseModel):
    id: int
    title: str
    description: str
    agent_type: str
    status: str
    output_data: Optional[dict]
    error_message: Optional[str]
    execution_order: int

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/execute")
async def execute(
    data: ExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Main endpoint. Send a natural language request, get agent-generated output.
    
    Example request:
    {
      "project_id": 1,
      "request": "Write a Python function that validates email addresses"
    }
    """
    # Verify project belongs to user
    project = db.query(Project).filter(
        Project.id == data.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    logger.info(
        f"Execute request | user={current_user.email} | "
        f"project={project.name} | request='{data.request[:60]}'"
    )

    try:
        result = await orchestrator.process(
            user_request=data.request,
            project_id=data.project_id,
            db=db,
        )
        return result.to_dict()

    except Exception as e:
        logger.error(f"Orchestrator failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and output of a specific task."""
    task = (
        db.query(Task)
        .join(Project)
        .filter(Task.id == task_id, Project.user_id == current_user.id)
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "agent_type": task.agent_type.value,
        "status": task.status.value,
        "output_data": task.output_data,
        "error_message": task.error_message,
        "execution_order": task.execution_order,
    }


@router.get("/projects/{project_id}/tasks")
async def list_project_tasks(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all tasks for a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = db.query(Task).filter(Task.project_id == project_id).order_by(Task.execution_order).all()

    return [
        {
            "id": t.id,
            "title": t.title,
            "agent_type": t.agent_type.value,
            "status": t.status.value,
            "execution_order": t.execution_order,
            "has_output": t.output_data is not None,
        }
        for t in tasks
    ]