"""Chat and AI endpoints with RAG integration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..db import get_db
from ..models import ChatMessage, Claim
from ..auth_utils import decode_access_token
from ..sockets import sio
from ..services.ai import generate_ai_reply_rag
from ..rag import RAGService

router = APIRouter()
rag_service = RAGService()  # Load and index docs at startup

def _get_user_id(authorization: str | None) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    try:
        return int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token payload")

class SendMessageRequest(BaseModel):
    message_text: str
    message_type: str | None = None

@router.get("/{claim_id}/history")
def chat_history(
    claim_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    rows = db.execute(
        text(
            """
            SELECT id, role, message, created_at
            FROM chat_messages
            WHERE claim_id = :cid
            ORDER BY id
            """
        ),
        {"cid": claim_id},
    ).mappings().all()

    history = []
    for row in rows:
        history.append(
            {
                "id": row["id"],
                "message_type": row["role"],
                "message_text": row["message"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )
    return {"history": history}

@router.post("/{claim_id}/messages")
async def send_message(
    claim_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    text_msg = body.message_text.strip() if body.message_text else ""
    if not text_msg:
        raise HTTPException(status_code=400, detail="message_text is required")

    # Store user's message
    user_chat = ChatMessage(
        claim_id=claim_id,
        user_id=user_id,
        role="user",
        message=text_msg,
    )
    db.add(user_chat)
    db.commit()
    db.refresh(user_chat)

    room = str(claim_id)
    await sio.emit(
        "chat_message",
        {
            "id": user_chat.id,
            "claim_id": claim_id,
            "message_type": "user",
            "message_text": user_chat.message,
            "created_at": user_chat.created_at.isoformat() if user_chat.created_at else None,
        },
        to=room,
    )

    # RAG: Retrieve relevant context from documents
    context_chunks = rag_service.retrieve(text_msg, top_k=3)

    # Generate AI reply using RAG context
    try:
        ai_text = await generate_ai_reply_rag(claim, text_msg, context_chunks)
    except Exception:
        ai_text = "I'm having trouble generating a response right now."

    # Store AI message
    ai_chat = ChatMessage(
        claim_id=claim_id,
        user_id=None,
        role="ai",
        message=ai_text,
    )
    db.add(ai_chat)
    db.commit()
    db.refresh(ai_chat)

    await sio.emit(
        "chat_message",
        {
            "id": ai_chat.id,
            "claim_id": claim_id,
            "message_type": "ai",
            "message_text": ai_chat.message,
            "created_at": ai_chat.created_at.isoformat() if ai_chat.created_at else None,
        },
        to=room,
    )

    return {
        "message": {
            "id": ai_chat.id,
            "claim_id": claim_id,
            "message_type": "ai",
            "message_text": ai_chat.message,
            "created_at": ai_chat.created_at.isoformat() if ai_chat.created_at else None,
            "sources": context_chunks,  # Optionally return sources for transparency
        }
    }