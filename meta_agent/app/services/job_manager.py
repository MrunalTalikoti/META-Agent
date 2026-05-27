"""
Distributed job state manager backed by Redis.

Stores job lifecycle (pending → running → completed/failed) so any worker
or container can query status.  Falls back to a process-local dict when
Redis is unavailable — jobs still work within a single worker but won't
be visible cross-process.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from app.core.cache import redis_client
from app.utils.logger import logger

_KEY_PREFIX = "job"
_TTL_SECONDS = 3600  # auto-expire finished jobs after 1 hour

# Process-local fallback when Redis is down
_local_store: Dict[str, dict] = {}


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redis_available() -> bool:
    return redis_client is not None


def _key(job_id: str) -> str:
    return f"{_KEY_PREFIX}:{job_id}"


def create_job(metadata: Optional[dict] = None) -> str:
    """Create a new job in PENDING state.  Returns the job_id (UUID)."""
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "result": None,
        "error": None,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "metadata": metadata or {},
    }
    _save(job_id, job)
    return job_id


def update_status(
    job_id: str,
    status: JobStatus,
    *,
    result: Any = None,
    error: Optional[str] = None,
) -> None:
    """Transition a job to a new status."""
    job = get_job(job_id)
    if job is None:
        logger.warning("Job %s not found — cannot update status", job_id)
        return

    job["status"] = status
    if status == JobStatus.RUNNING:
        job["started_at"] = _now_iso()
    if status in (JobStatus.COMPLETED, JobStatus.FAILED):
        job["completed_at"] = _now_iso()
    if result is not None:
        job["result"] = result
    if error is not None:
        job["error"] = error

    _save(job_id, job)


def get_job(job_id: str) -> Optional[dict]:
    """Return the full job dict, or None if not found."""
    if _redis_available():
        try:
            raw = redis_client.get(_key(job_id))
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error("Redis get failed for job %s: %s", job_id, e)
    return _local_store.get(job_id)


# ── Internal ────────────────────────────────────────────────────────────────

def _save(job_id: str, job: dict) -> None:
    if _redis_available():
        try:
            redis_client.setex(_key(job_id), _TTL_SECONDS, json.dumps(job))
            return
        except Exception as e:
            logger.error("Redis set failed for job %s: %s — falling back to local", job_id, e)
    _local_store[job_id] = job
