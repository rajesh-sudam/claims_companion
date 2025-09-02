
"""Helper functions for authentication and JWT handling.

This module centralises password hashing and JSON Web Token operations.
It uses passlib with bcrypt for secure password storage and PyJWT
to encode and decode tokens. The secret key and token expiry are
configurable via environment variables.
"""

from __future__ import annotations

import os
import time
from datetime import timedelta
from typing import Any, Dict

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException

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
