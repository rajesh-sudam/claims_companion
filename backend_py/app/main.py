"""Entry point for the FastAPI/Socket.IO ASGI application."""

from __future__ import annotations

import logging
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware




# Import engine/Base and the DB wait helper
from .db import Base, engine, wait_for_db

# Import models so SQLAlchemy knows about all tables before create_all()
# (lint: F401 unused import on purpose)
from . import models  # noqa: F401

from .sockets import sio
from .routes import auth, claims, chat

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="ClaimsCompanion API (Python)")


@app.on_event("startup")
def on_startup():
    # Wait until Postgres is accepting connections (handles container race)
    try:
        log.info("Waiting for database to be ready...")
        wait_for_db(max_tries=60, delay_seconds=1.0)
        log.info("Database is ready. Creating tables if needed...")
        Base.metadata.create_all(bind=engine)
        log.info("Table creation complete.")
    except Exception as e:
        # Let Uvicorn crash early with a clear reason
        log.exception("Startup failed while preparing the database: %s", e)
        raise

# Open CORS wide for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Routes
app.include_router(auth.router,   prefix="/api/auth",  tags=["auth"])
app.include_router(claims.router, prefix="/api/claims", tags=["claims"])
app.include_router(chat.router,   prefix="/api/chat",  tags=["chat"])

# Socket.IO + FastAPI combined ASGI app
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
