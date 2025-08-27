"""Helper functions for authentication and JWT handling.

This module centralises password hashing and JSON Web Token operations.
It uses passlib with bcrypt for secure password storage and PyJWT
to encode and decode tokens. The secret key and token expiry are
configurable via environment variables.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Secret key used to sign JWTs. In production this should be a long,
# random string stored securely. For the MVP we default to an
# insecure value to avoid crashes when the environment is not set.
SECRET_KEY = os.getenv("JWT_SECRET", "change-this-in-production")

# Token expiration time in seconds. Default to 7 days.
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRY_SECONDS", str(7 * 24 * 60 * 60)))


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        password: The plain-text password.

    Returns:
        A hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash.

    Args:
        plain_password: The candidate password provided by the user.
        hashed_password: The stored password hash.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: int | None = None) -> str:
    """Create a signed JWT with optional expiry.

    Args:
        data: Payload to encode in the token. Should contain at least
            user identification fields (e.g. id and email).
        expires_delta: Optional time in seconds until the token expires.
            If omitted, the default expiry from ACCESS_TOKEN_EXPIRE_SECONDS
            is used.

    Returns:
        A JWT string encoded with HS256.
    """
    to_encode = data.copy()
    expire_seconds = expires_delta or ACCESS_TOKEN_EXPIRE_SECONDS
    to_encode["exp"] = int(time.time()) + expire_seconds
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