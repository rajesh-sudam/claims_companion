"""Authentication routes.

These endpoints handle user registration, login and retrieval of
current user information. Tokens are issued via JSON Web Tokens
(JWT) and stored on the client. A cookie-based approach could be
added easily if desired.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..models import User
from ..db import get_db
from ..auth_utils import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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