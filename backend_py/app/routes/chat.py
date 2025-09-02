"""Chat and AI endpoints with RAG integration."""

from __future__ import annotations
print("=== LOADING Chat MODULE ===")
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Form, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

import os
from ..db import get_db
from ..models import ChatMessage, Claim
from ..auth_utils import decode_access_token
from ..sockets import sio
from ..services.ai import generate_ai_reply_rag, AIAnswer
from ..rag import RAGService

router = APIRouter(prefix="/chat", tags=["chat"])
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
    message_type: str | None = None  # optional: "status", "coverage", etc.


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
    message_text: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    print(f"DEBUG CHAT: ========== New chat message ==========")
    print(f"DEBUG CHAT: Claim ID: {claim_id}")
    print(f"DEBUG CHAT: Message: '{message_text}'")
    print(f"DEBUG CHAT: Has file: {file is not None}")
    
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    print(f"DEBUG CHAT: Found claim - number: {claim.claim_number}, type: {claim.claim_type}")
        
    attachment_url, attachment_name = None, None
    if file:
        # store file in same storage as claim docs (like in new.tsx)
        storage_path = f"uploads/claims/{claim_id}/{file.filename}"
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(await file.read())
        attachment_url = f"/static/{storage_path}"   # or your S3/GCS path
        attachment_name = file.filename
        print(f"DEBUG CHAT: Saved file to: {storage_path}")

    # Store user's message (first instance)
    print("DEBUG CHAT: Storing user message (first instance)...")
    user_chat = ChatMessage(
        claim_id=claim_id,
        user_id=user_id,
        role="user",
        message=message_text,
    )
    db.add(user_chat)
    db.commit()
    db.refresh(user_chat)
    print(f"DEBUG CHAT: Stored user message with ID: {user_chat.id}")

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
    print("DEBUG CHAT: Emitted user message via socket")

    # NOTE: This appears to be duplicate message storage - you might want to remove this
    print("DEBUG CHAT: WARNING - About to store duplicate user message")
    print("DEBUG CHAT: This will fail because attachment_url/attachment_name columns don't exist")
    try:
        chat_msg = ChatMessage(
            claim_id=claim_id,
            user_id=user_id,
            role="user",
            message=message_text.strip(),
            # attachment_url=attachment_url,      # These columns don't exist - commenting out
            # attachment_name=attachment_name,    # These columns don't exist - commenting out
        )
        db.add(chat_msg)
        db.commit()
        db.refresh(chat_msg)
        print(f"DEBUG CHAT: Stored duplicate user message with ID: {chat_msg.id}")
    except Exception as e:
        print(f"DEBUG CHAT: Failed to store duplicate message: {type(e).__name__}: {e}")
        # Use the first user_chat message instead
        chat_msg = user_chat

    # --- RAG retrieval with debug ---
    print(f"DEBUG RAG: ========== RAG Retrieval ==========")
    print(f"DEBUG RAG: User message: '{message_text}'")
    print(f"DEBUG RAG: Message length: {len(message_text)}")
    print(f"DEBUG RAG: Claim ID: {claim_id}")
    
    try:
        print("DEBUG RAG: Calling rag_service.retrieve()...")
        context_chunks: List[Any] = rag_service.retrieve(message_text, top_k=3)
        print(f"DEBUG RAG: Retrieved {len(context_chunks)} chunks")
        
        if context_chunks:
            for i, chunk in enumerate(context_chunks):
                chunk_type = type(chunk).__name__
                chunk_preview = str(chunk)[:200] + "..." if len(str(chunk)) > 200 else str(chunk)
                print(f"DEBUG RAG: Chunk {i} ({chunk_type}): {chunk_preview}")
        else:
            print("DEBUG RAG: NO CHUNKS RETURNED FROM RAG SERVICE")
            
    except Exception as e:
        print(f"DEBUG RAG: RAG service error: {type(e).__name__}: {e}")
        context_chunks = []

    # --- AI generation with grounding & JSON citations ---
    print(f"DEBUG AI: ========== AI Generation ==========")
    print(f"DEBUG AI: Passing {len(context_chunks)} chunks to AI")
    
    try:
        print("DEBUG AI: Calling generate_ai_reply_rag()...")
        ai_result: AIAnswer = await generate_ai_reply_rag(claim, message_text, context_chunks)
        ai_text = ai_result.answer
        print(f"DEBUG AI: Generated answer: '{ai_text}'")
        print(f"DEBUG AI: Generated {len(ai_result.citations)} citations")
        
        # Convert citations to a serializable shape for the client
        sources = [
            {
                "id": c.id,
                "doc_id": c.doc_id,
                "chunk_id": c.chunk_id,
                "score": c.score,
                "snippet": c.snippet,
            }
            for c in ai_result.citations
        ]
        print(f"DEBUG AI: Serialized sources: {sources}")
        
    except Exception as e:
        print(f"DEBUG AI: AI generation error: {type(e).__name__}: {e}")
        import traceback
        print(f"DEBUG AI: Full traceback: {traceback.format_exc()}")
        ai_text = "I'm having trouble generating a response right now."
        sources = []
    
    # Store AI message
    print("DEBUG CHAT: Storing AI message...")
    ai_chat = ChatMessage(
        claim_id=claim_id,
        user_id=None,
        role="ai",
        message=ai_text,
    )
    db.add(ai_chat)
    db.commit()
    db.refresh(ai_chat)
    print(f"DEBUG CHAT: Stored AI message with ID: {ai_chat.id}")

    # Broadcast AI message
    await sio.emit(
        "chat_message",
        {
            "id": ai_chat.id,
            "claim_id": claim_id,
            "message_type": "ai",
            "message_text": ai_chat.message,
            "created_at": ai_chat.created_at.isoformat() if ai_chat.created_at else None,
            "sources": sources,  # let the UI show evidence
        },
        to=room,
    )
    print("DEBUG CHAT: Emitted AI message via socket")

    final_response = {
        "message": {
            "id": ai_chat.id,
            "claim_id": claim_id,
            "message_type": "ai",
            "message_text": ai_chat.message,
            "created_at": ai_chat.created_at.isoformat() if ai_chat.created_at else None,
            "sources": sources,
        }
    }
    print(f"DEBUG CHAT: Final response: {final_response}")
    print(f"DEBUG CHAT: ========== End chat message ==========")
    
    return final_response