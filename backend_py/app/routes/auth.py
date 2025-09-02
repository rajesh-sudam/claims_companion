"""Authentication routes.

These endpoints handle user registration, login and retrieval of
current user information. Tokens are issued via JSON Web Tokens
(JWT) and stored on the client. A cookie-based approach could be
added easily if desired.
"""
from __future__ import annotations
import os
print("=== LOADING Auth MODULE ===")
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional
from ..models import User, UserRole
from ..db import get_db
from passlib.hash import bcrypt
from ..auth_utils import hash_password, verify_password, create_access_token, decode_access_token

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


# ----- Helpers -----
def _get_user_from_token(authorization: str | None, db: Session) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    uid = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

def _seed_employees(db: Session):
    """Create default manager/analyst if not present."""
    defaults = [
        {
            "email": os.getenv("EMP_MANAGER_EMAIL", "manager@cc.io"),
            "password": os.getenv("EMP_MANAGER_PASSWORD", "manager123"),
            "role": UserRole.manager,
            "first_name": "Claims",
            "last_name": "Manager",
        },
        {
            "email": os.getenv("EMP_ANALYST_EMAIL", "analyst@cc.io"),
            "password": os.getenv("EMP_ANALYST_PASSWORD", "analyst123"),
            "role": UserRole.analyst,
            "first_name": "Claims",
            "last_name": "Analyst",
        },
    ]
    for d in defaults:
        existing = db.query(User).filter(User.email == d["email"]).first()
        if not existing:
            user = User(
                email=d["email"],
                password=bcrypt.hash(d["password"]),
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
    """Create a new user and return a token.

    If the email is already registered, a 400 error is returned. On
    success the password is hashed and a JWT is issued.
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        password=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "phone": user.phone}, "token": token}


@router.post("/login")
def login_user(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return a token and user details."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "phone": user.phone}, "token": token}


@router.get("/me")
def get_me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Return the currently authenticated user's information.

    Requires a valid Authorization header with a Bearer token. If
    valid, the user is looked up by ID and returned; otherwise a 401
    error is raised.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"user": {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "phone": user.phone}}


# Utility you can reuse to protect admin-only endpoints
def require_roles(*allowed_roles: UserRole):
    def _dep(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing token")
        token = authorization.split(" ", 1)[1]
        payload = decode_access_token(token)
        role = payload.get("role")
        if role not in {r.value if isinstance(r, UserRole) else r for r in allowed_roles}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload
    return _dep