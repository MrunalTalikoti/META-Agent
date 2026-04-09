"""
Export & Metrics API
--------------------
GET  /api/projects/{id}/export   → download zip of all generated files
GET  /api/projects/{id}/files    → list files without downloading
GET  /api/metrics                → usage stats for current user
GET  /api/admin/metrics          → global stats (admin only — placeholder)
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import io

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database import Project, Task, TaskStatus, User, AgentExecution
from app.services.file_export import FileExportService
from app.utils.logger import logger

router = APIRouter()


@router.get("/projects/{project_id}/export")
async def export_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download all generated files for a project as a zip archive."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")

    tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.COMPLETED,
    ).order_by(Task.execution_order).all()

    if not tasks:
        raise HTTPException(404, "No completed tasks found for this project")

    try:
        zip_bytes = FileExportService.build_zip(project, tasks)
    except Exception as e:
        logger.error(f"Export failed for project {project_id}: {e}")
        raise HTTPException(500, f"Export failed: {str(e)}")

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)
    filename = f"{safe_name}_project.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/files")
async def list_project_files(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all files that would be in the export zip."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")

    tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.COMPLETED,
    ).all()

    return {
        "project_id": project_id,
        "project_name": project.name,
        "files": FileExportService.get_project_files_summary(tasks),
    }


@router.get("/metrics")
async def get_user_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Usage and cost statistics for the current user."""
    # Total projects
    project_count = db.query(func.count(Project.id)).filter(
        Project.user_id == current_user.id
    ).scalar()

    # Total tasks
    task_count = db.query(func.count(Task.id)).join(Project).filter(
        Project.user_id == current_user.id
    ).scalar()

    # Completed tasks
    completed_count = db.query(func.count(Task.id)).join(Project).filter(
        Project.user_id == current_user.id,
        Task.status == TaskStatus.COMPLETED,
    ).scalar()

    # Token / cost totals from agent_executions
    executions = (
        db.query(
            func.sum(AgentExecution.total_tokens).label("total_tokens"),
            func.sum(AgentExecution.estimated_cost_usd).label("total_cost_microdollars"),
            func.count(AgentExecution.id).label("total_llm_calls"),
        )
        .join(Task)
        .join(Project)
        .filter(Project.user_id == current_user.id)
        .first()
    )

    total_tokens = executions.total_tokens or 0
    total_cost_usd = (executions.total_cost_microdollars or 0) / 1_000_000
    total_llm_calls = executions.total_llm_calls or 0

    return {
        "user_id": current_user.id,
        "tier": current_user.tier.value,
        "requests_today": current_user.requests_today,
        "projects": project_count,
        "tasks": {
            "total": task_count,
            "completed": completed_count,
            "success_rate": round(completed_count / task_count * 100, 1) if task_count else 0,
        },
        "llm_usage": {
            "total_calls": total_llm_calls,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost_usd, 4),
        },
    }