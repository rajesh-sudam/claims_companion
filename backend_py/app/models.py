
from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import relationship,  Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import Enum as SAEnum 
from enum import Enum as PyEnum
from typing import Optional

from .db import Base


class UserRole(str, PyEnum):
    user = "user"
    agent = "agent"
    data_analyst = "data_analyst"
    admin = "admin"
    

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(10))
    role = Column(
        SAEnum(UserRole, name="user_role"),
        nullable=False,
        server_default=UserRole.user.value,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    claims = relationship("Claim", back_populates="user")
    messages = relationship("ChatMessage", back_populates="user")
    sessions = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(Text, unique=True, nullable=False, index=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions")


class Claim(Base):
    __tablename__ = "claims"

    id: int = Column(Integer, primary_key=True, index=True)
    claim_number: str = Column(String(20), unique=True, nullable=False)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    claim_type: str = Column(String(50), nullable=False)
    status: str = Column(String(50), default="submitted")
    incident_date: date | None = Column(Date, nullable=True)
    incident_description: str | None = Column(Text, nullable=True)
    estimated_completion: date | None = Column(Date, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="claims")
    progress_steps = relationship("ClaimProgress", back_populates="claim")
    messages = relationship("ChatMessage", back_populates="claim")
    documents = relationship("ClaimDocument", back_populates="claim")


class ClaimProgress(Base):
    __tablename__ = "claim_progress"

    id: int = Column(Integer, primary_key=True, index=True)
    claim_id: int = Column(Integer, ForeignKey("claims.id"), nullable=False)
    step_id: str = Column(String(50), nullable=False)
    step_title: str = Column(String(200), nullable=False)
    status: str = Column(String(20), nullable=False)
    completed_at: datetime | None = Column(DateTime, nullable=True)
    description: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.now)

    claim = relationship("Claim", back_populates="progress_steps")


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    id: int = Column(Integer, primary_key=True, index=True)
    claim_id: int = Column(Integer, ForeignKey("claims.id"), nullable=False)
    file_name: str = Column(String(255), nullable=False)
    file_url: str = Column(String(500), nullable=False)
    document_type: str | None = Column(String(100), nullable=True)
    status: str = Column(String(50), default="pending_review")
    uploaded_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)

    claim = relationship("Claim", back_populates="documents")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: int = Column(Integer, primary_key=True, index=True)
    claim_id: int = Column(Integer, ForeignKey("claims.id"), nullable=False)
    user_id: int | None = Column(Integer, ForeignKey("users.id"), nullable=True)
    role: str = Column(String(20), nullable=False)
    message: str = Column(Text, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    attachment_url: str | None = Column(String(500), nullable=True)
    attachment_name: str | None = Column(String(255), nullable=True)
    
    # Correct Relationships
    claim = relationship("Claim", back_populates="messages")
    user = relationship("User", back_populates="messages")
