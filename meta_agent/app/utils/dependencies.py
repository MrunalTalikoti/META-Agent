"""
Centralized request-throttling for expensive (LLM / orchestrator) operations.

Two independent limits guard every run-launching code path:

  1. ``rate_limiter.enforce()`` — Redis sliding-window, per-minute burst control
     (fails open if Redis is down).
  2. ``check_rate_limit()``     — per-user daily tier quota, backed by the DB.

Historically these were applied inline and inconsistently: ``/agents/execute``
enforced *both*, while the conversation flows enforced *only* the daily quota
and missed the per-minute limiter entirely. This module is the single source of
truth so no endpoint can drift to enforcing one limit but not the other.

Use it two ways:
  • ``Depends(enforce_limits)`` — on endpoints where *every* call launches a run
    (e.g. ``/agents/execute``, ``start_conversation``). It also authenticates,
    so it is a drop-in replacement for ``Depends(get_current_user)``.
  • ``apply_rate_limits(user, db)`` — call directly inside a handler when only
    *some* branches launch a run (e.g. ``send_message`` only enforces on the
    execute-confirmation and refinement branches, not on gathering replies).
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database import User
from app.utils.rate_limiter import rate_limiter
from app.utils.tier_limits import check_rate_limit


def apply_rate_limits(user: User, db: Session) -> None:
    """Apply BOTH limits, in a fixed order. Raises HTTP 429 if either is exceeded.

    The per-minute burst limit is checked first (cheap, no DB write) before the
    daily quota is consumed, so a throttled burst never spends a user's daily
    allowance.
    """
    rate_limiter.enforce(str(user.id))
    check_rate_limit(user, db)


def enforce_limits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: authenticate the caller and enforce both rate limits.

    Returns the authenticated ``User`` so handlers can keep using
    ``current_user`` exactly as they did with ``Depends(get_current_user)``.
    """
    apply_rate_limits(current_user, db)
    return current_user
