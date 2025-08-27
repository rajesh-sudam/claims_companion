"""ORM models for the ClaimsCompanion backend.

These classes map to PostgreSQL tables defined in the Node.js
implementation. They represent users, claims, progress steps and
chat messages. SQLAlchemy automatically reflects these models into
the database schema when run with Alembic or via explicit table
creation. For the MVP we rely on the SQL scripts mounted by
Docker to initialise the database.
"""

from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    password: str = Column(String(255), nullable=False)
    phone: str | None = Column(String(20))
    first_name: str | None = Column(String(100))
    last_name: str | None = Column(String(100))
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claims = relationship("Claim", back_populates="user")
    messages = relationship("ChatMessage", back_populates="user")


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
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    status: str = Column(String(20), nullable=False)  # 'pending', 'active', 'completed'
    completed_at: datetime | None = Column(DateTime, nullable=True)
    description: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="progress_steps")


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    id: int = Column(Integer, primary_key=True, index=True)
    claim_id: int = Column(Integer, ForeignKey("claims.id"), nullable=False)
    file_name: str = Column(String(255), nullable=False)
    file_url: str = Column(String(500), nullable=False)
    document_type: str | None = Column(String(100), nullable=True)
    status: str = Column(String(50), default="pending_review")
    uploaded_at: datetime = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="documents")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: int = Column(Integer, primary_key=True, index=True)
    claim_id: int = Column(Integer, ForeignKey("claims.id"), nullable=False)
    user_id: int | None = Column(Integer, ForeignKey("users.id"), nullable=True)
    role: str = Column(String(20), nullable=False)  # 'user', 'ai', 'agent'
    message: str = Column(Text, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="messages")
    user = relationship("User", back_populates="messages")