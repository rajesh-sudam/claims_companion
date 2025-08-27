"""Database configuration and helper functions.

This module defines the SQLAlchemy engine and session factory used
throughout the application. The ``Base`` class is imported by the
models module to declare ORM models. A ``get_db`` dependency is
provided for FastAPI routes to obtain a transactional session scoped
to the request lifecycle.
"""

from __future__ import annotations

import os, time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Load DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql+psycopg2://cc:cc@db:5432/cc

# Create the SQLAlchemy engine. The pool_pre_ping flag ensures broken
# connections are detected and recycled automatically.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session factory for ORM usage
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for declarative models.

    All ORM models should inherit from this class. It exposes the
    ``metadata`` attribute used by SQLAlchemy to create and drop
    database tables.
    """


def wait_for_db(max_tries: int = 60, delay_seconds: float = 1.0):
    """Poll the DB until a trivial query works (or give up)."""
    last_err = None
    for attempt in range(1, max_tries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as e:
            last_err = e
            time.sleep(delay_seconds)
    raise RuntimeError(f"Database not ready after {max_tries} tries") from last_err


def get_db():
    """FastAPI dependency that yields a transactional database session.

    The session is automatically closed after the request is processed.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
