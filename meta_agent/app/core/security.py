import hashlib
import base64
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cache import redis_client
from app.core.database import get_db
from app.models.database import User
from app.utils.logger import logger

# ── Password hashing ─────────────────────────────────────────────────────────
# passlib's bcrypt backend calls bcrypt.hashpw with a >72-byte test string
# during initialisation (detect_wrap_bug). bcrypt 4.x raises ValueError for
# that, crashing passlib before it can hash anything. We bypass passlib entirely
# and call bcrypt directly. Passwords are SHA-256 pre-hashed first (44-byte
# base64 output) so bcrypt's 72-byte limit is never reached — same approach
# as Django's BCryptSHA256PasswordHasher.

# ── OAuth2 scheme ─────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def _prehash(password: str) -> bytes:
    """Return SHA-256(password) as base64 bytes — always 44 bytes, safe for bcrypt."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[int]:
    """Returns user_id from an *access* token, or None if invalid.

    Refresh tokens are explicitly rejected here so a long-lived refresh token
    can never be presented as a bearer credential to a protected endpoint.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") == "refresh":
            return None
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except JWTError as e:
        logger.warning(f"Token decode failed: {e}")
        return None


# ── Refresh tokens ────────────────────────────────────────────────────────────
# A refresh token is a longer-lived JWT carrying a unique JTI (token id). The
# JTI is recorded in Redis; presence of the JTI == the token is still valid.
# Revoking (logout / rotation) deletes the JTI, which immediately invalidates
# the token even though the signed JWT itself is still cryptographically valid.

_REFRESH_JTI_PREFIX = "refresh_jti:"


def _store_refresh_jti(jti: str, user_id: int) -> None:
    """Record an active refresh JTI in Redis with a matching TTL."""
    if redis_client is None:
        logger.warning("Redis unavailable — refresh JTI not stored; revocation disabled")
        return
    ttl = settings.refresh_token_expire_minutes * 60
    try:
        redis_client.setex(f"{_REFRESH_JTI_PREFIX}{jti}", ttl, str(user_id))
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"Failed to store refresh JTI: {e}")


def is_refresh_jti_active(jti: str, user_id: int) -> bool:
    """True only if the JTI is still present in Redis and owned by this user.

    Fails closed: if Redis is unavailable we cannot prove the token wasn't
    revoked, so we treat it as invalid.
    """
    if redis_client is None:
        return False
    try:
        stored = redis_client.get(f"{_REFRESH_JTI_PREFIX}{jti}")
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"Failed to read refresh JTI: {e}")
        return False
    return stored is not None and stored == str(user_id)


def revoke_refresh_jti(jti: str) -> None:
    """Invalidate a refresh token by removing its JTI from Redis."""
    if redis_client is None or not jti:
        return
    try:
        redis_client.delete(f"{_REFRESH_JTI_PREFIX}{jti}")
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"Failed to revoke refresh JTI: {e}")


def create_refresh_token(user_id: int) -> str:
    """Issue a long-lived refresh token and register its JTI in Redis."""
    jti = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(minutes=settings.refresh_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "jti": jti,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    _store_refresh_jti(jti, user_id)
    return token


def decode_refresh_token(token: str) -> Optional[dict]:
    """Validate signature + ``type=refresh`` and return the payload, else None.

    Does NOT check revocation — callers must additionally verify the JTI via
    ``is_refresh_jti_active``.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as e:
        logger.warning(f"Refresh token decode failed: {e}")
        return None
    if payload.get("type") != "refresh" or not payload.get("jti"):
        return None
    return payload


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency — validates token and returns current User object."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_token(token)
    if not user_id:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
    if not user:
        raise credentials_exception

    # Subscription validation: a paid plan whose paid period has lapsed must not
    # keep enjoying paid access on the strength of a still-valid access token.
    if user.subscription_expires is not None and user.subscription_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription expired. Please renew to continue.",
        )

    return user