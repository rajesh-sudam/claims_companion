"""Helper functions for authentication and JWT handling.

This module centralises password hashing and JSON Web Token operations.
It uses passlib with bcrypt for secure password storage and PyJWT
to encode and decode tokens. The secret key and token expiry are
configurable via environment variables.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Set

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from .db import get_db
from .models import User, UserRole, Session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET", "change-this-in-production")
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRY_SECONDS", str(7 * 24 * 60 * 60)))

def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: int | timedelta | None = None) -> str:
    """Create a signed JWT with optional expiry.

    Args:
        data: Payload to encode in the token.
        expires_delta: Optional time in seconds (int) or a timedelta object.
            If omitted, the default expiry is used.

    Returns:
        A JWT string encoded with HS256.
    """
    to_encode = data.copy()
    
    if isinstance(expires_delta, timedelta):
        expire_seconds = expires_delta.total_seconds()
    else:
        expire_seconds = expires_delta or ACCESS_TOKEN_EXPIRE_SECONDS

    to_encode["exp"] = int(time.time()) + int(expire_seconds)
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode a JWT and return the payload if valid.

    Raises HTTPException with 401 if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

def get_current_active_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    """Dependency to get the current user, ensuring the token is valid and active."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.split(" ", 1)[1]
    
    # Check if session is active in the database
    db_session = db.query(Session).filter(Session.token == token).first()
    if not db_session or db_session.expires_at < datetime.now(timezone.utc):
        if db_session: # Expired session
            db.delete(db_session)
            db.commit()
        raise HTTPException(status_code=401, detail="Session expired or invalid, please log in again")

    payload = decode_access_token(token)
    user_id = int(payload.get("sub", 0))
    if user_id == 0:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found for token")
    
    return user

def require_active_user_with_roles(required_roles: Set[UserRole]):
    """Dependency factory to protect routes based on user roles."""
    def _dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
        return current_user
    return _dependency