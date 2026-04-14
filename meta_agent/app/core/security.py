import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
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
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[int]:
    """Returns user_id from token or None if invalid."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except JWTError as e:
        logger.warning(f"Token decode failed: {e}")
        return None


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

    return user