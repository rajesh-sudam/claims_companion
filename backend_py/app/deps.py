# backend_py/app/deps.py
from __future__ import annotations
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .db import get_db
from .auth_utils import decode_access_token
from .models import User

ALLOWED_ROLES = {"manager", "analyst"}

def get_current_user(authorization: str | None = Header(default=None),
                     db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    uid = int(payload.get("sub") or 0)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden: admin only")
    return user
