from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional, Set

from ..models import User, UserRole, Session
from ..db import get_db
from ..auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_active_user,
    require_active_user_with_roles,
)

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _seed_employees(db: Session):
    """Create default admin/agent if not present."""
    defaults = [
        {
            "email": os.getenv("EMP_ADMIN_EMAIL", "admin@cc.io"),
            "password": os.getenv("EMP_ADMIN_PASSWORD", "admin123"),
            "role": UserRole.admin,
            "first_name": "App",
            "last_name": "Admin",
        },
        {
            "email": os.getenv("EMP_AGENT_EMAIL", "agent@cc.io"),
            "password": os.getenv("EMP_AGENT_PASSWORD", "agent123"),
            "role": UserRole.agent,
            "first_name": "Claims",
            "last_name": "Agent",
        },
    ]
    for d in defaults:
        existing = db.query(User).filter(User.email == d["email"]).first()
        if not existing:
            user = User(
                email=d["email"],
                password=hash_password(d["password"]),
                first_name=d["first_name"],
                last_name=d["last_name"],
                role=d["role"],
            )
            db.add(user)
    db.commit()

# Call this at app startup from main.py (we expose route for idempotency too)
@router.post("/seed-employees")
def seed_employees(db: Session = Depends(get_db)):
    _seed_employees(db)
    return {"ok": True}



@router.post("/register")
def register_user(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user. Does not automatically log them in."""
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        password=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        role=UserRole.user # Explicitly set role to user
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "phone": user.phone}


@router.post("/login")
def login_user(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate a user, create a session, and return a token."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Token expires in 1 day
    expires_delta = timedelta(days=1)
    expires_at = datetime.now(timezone.utc) + expires_delta
    
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role.value}
    token = create_access_token(token_data, expires_delta)

    # Create a new session in the database
    new_session = Session(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        user_agent=request.headers.get("User-Agent")
    )
    db.add(new_session)
    db.commit()

    return {"user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "phone": user.phone, "role": user.role.value}, "token": token}


@router.post("/logout")
def logout_user(response: Response, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Invalidate the current user's session by deleting the token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]

    db_session = db.query(Session).filter(Session.token == token).first()
    if db_session:
        db.delete(db_session)
        db.commit()
    
    response.status_code = 204 # No Content
    return response


@router.get("/me")
def get_me(current_user: User = Depends(get_current_active_user)):
    """Return the currently authenticated user's information."""
    return {"user": {"id": current_user.id, "email": current_user.email, "first_name": current_user.first_name, "last_name": current_user.last_name, "phone": current_user.phone, "role": current_user.role.value}}