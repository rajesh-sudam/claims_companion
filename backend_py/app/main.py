from __future__ import annotations
import os
import logging
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .db import Base, engine, SessionLocal, wait_for_db

from .models import User, UserRole
from .auth_utils import hash_password
# Import models so SQLAlchemy knows about all tables before create_all()
# (lint: F401 unused import on purpose)
from . import models  # noqa: F401
from .sockets import sio
from .routes import auth, claims, chat, admin
from .routes.auth import _seed_employees  # reuse the helper
import socketio

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="ClaimsCompanion API (Python)")

@app.on_event("startup")
def on_startup():
    # Wait until Postgres is accepting connections (handles container race)
    try:
        log.info("Waiting for database to be ready...")
        wait_for_db(max_tries=60, delay_seconds=1.0)
        log.info("Database is ready. Creating tables if they don't exist...")
        Base.metadata.create_all(bind=engine)
        log.info("Table creation complete.")
    except Exception as e:
        # Let Uvicorn crash early with a clear reason
        log.exception("Startup failed while preparing the database: %s", e)
        raise

    # Seed employees (idempotent)
    with SessionLocal() as db:
        _seed_employees(db)
        
        # Seed other users from environment variables
        seeds = [
            (os.getenv("ADMIN_MANAGER_EMAIL"), os.getenv("ADMIN_MANAGER_PASSWORD"), UserRole.data_analyst),
            (os.getenv("ADMIN_ANALYST_EMAIL"), os.getenv("ADMIN_ANALYST_PASSWORD"), UserRole.data_analyst),
        ]
        for email, pwd, role in seeds:
            if email and pwd and not db.query(User).filter(User.email == email).first():
                db.add(User(email=email, password=hash_password(pwd), role=role))
        db.commit()


# Open CORS wide for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Routes
app.include_router(auth.router,   prefix="/api",  tags=["auth"])
app.include_router(claims.router, prefix="/api", tags=["claims"])
app.include_router(chat.router,   prefix="/api",  tags=["chat"])
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
# app.include_router(chat.router,   prefix="/api/register")


# Socket.IO + FastAPI combined ASGI app
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
