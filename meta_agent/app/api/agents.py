import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.core.orchestrator import MetaAgentOrchestrator
from app.models.database import Project, Task, User
from app.services.job_manager import (
    JobStatus, create_job, get_job, update_status,
)
from app.utils.logger import logger
from app.utils.dependencies import enforce_limits

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


# ── Background runner ────────────────────────────────────────────────────────

async def _run_orchestrator_job(
    job_id: str,
    user_request: str,
    project_id: int,
) -> None:
    """Runs orchestrator in the background with its own DB session."""
    update_status(job_id, JobStatus.RUNNING)
    db = SessionLocal()
    try:
        result = await orchestrator.process(
            user_request=user_request,
            project_id=project_id,
            db=db,
        )
        update_status(job_id, JobStatus.COMPLETED, result=result.to_dict())
        logger.info("Job %s completed", job_id)
    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e, exc_info=True)
        update_status(job_id, JobStatus.FAILED, error=str(e))
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/execute")
async def execute(
    data: ExecuteRequest,
    current_user: User = Depends(enforce_limits),
    db: Session = Depends(get_db),
):
    """
    Submit an orchestrator job.  Returns immediately with a job_id.

    Poll /agents/jobs/{job_id} for status and results.

    Rate limiting (per-minute burst + daily tier quota) is applied by the
    ``enforce_limits`` dependency — see app/utils/dependencies.py.
    """
    project = db.query(Project).filter(
        Project.id == data.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    job_id = create_job(metadata={
        "user_id": current_user.id,
        "project_id": data.project_id,
        "request_preview": data.request[:80],
    })

    logger.info(
        "Job %s queued | user=%s | project=%s | request='%s'",
        job_id, current_user.email, project.name, data.request[:60],
    )

    asyncio.create_task(_run_orchestrator_job(
        job_id=job_id,
        user_request=data.request,
        project_id=data.project_id,
    ))

    return {"job_id": job_id, "status": "pending"}


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll for job status and results."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only expose the job to the user who created it
    if job.get("metadata", {}).get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "result": job["result"],
        "error": job["error"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
    }


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
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = (
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.execution_order)
        .all()
    )
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
