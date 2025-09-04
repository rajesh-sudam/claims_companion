"""Chat and AI endpoints with RAG integration."""

from __future__ import annotations
print("=== LOADING Chat MODULE ===")
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Form, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone

import os
import json # Import json to parse the string
from ..db import get_db
from ..models import ChatMessage, Claim, ClaimProgress
from ..auth_utils import decode_access_token
from ..sockets import sio
from ..services.ai import generate_ai_reply_rag, AIAnswer
from ..rag import RAGService, get_rag_service, analyse_claim_with_rag # Import analyse_claim_with_rag

router = APIRouter(prefix="/chat", tags=["chat"])

async def initiate_document_request(claim_id: int, db: Session):
    """Initiates a request for documents from the AI."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return

    claim_type_messages = {
        "motor": "To process your motor claim, please upload photos of the damage, a copy of the police report, and any repair estimates you have.",
        "health": "For your health claim, please upload your medical bills, receipts, and a copy of your doctor's report.",
        "property": "For your property claim, please provide photos of the damage, a list of damaged items, and any receipts or proof of ownership.",
        "travel": "To proceed with your travel claim, please upload your travel itinerary, receipts for any expenses, and any relevant documentation (e.g., flight cancellation notice).",
    }

    message_text = claim_type_messages.get(
        claim.claim_type,
        "To proceed with your claim, please upload the necessary documents. You can upload multiple files at once."
    )

    ai_chat = ChatMessage(
        claim_id=claim_id,
        user_id=None,
        role="ai_request_documents",
        message=message_text,
    )
    db.add(ai_chat)

    # Add a progress step for "Documents Requested"
    progress_step = ClaimProgress(
        claim_id=claim_id,
        step_id="documents_requested",
        step_title="Documents Requested",
        status="active",
        description="The AI assistant has requested the necessary documents.",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(progress_step)

    claim.status = "awaiting_documents"

    db.commit()
    db.refresh(ai_chat)

    room = str(claim_id)
    await sio.emit(
        "chat_message",
        {
            "id": ai_chat.id,
            "claim_id": claim_id,
            "message_type": "ai_request_documents",
            "message_text": ai_chat.message,
            "created_at": ai_chat.created_at.isoformat() if ai_chat.created_at else None,
        },
        to=room,
    )

async def send_human_review_message(claim_id: int, db: Session):
    """Sends a message to the user informing them that their claim is under human review."""
    message_text = "Thank you for submitting your documents. Your claim is now under review by a human agent. We will notify you of any updates."
    ai_chat = ChatMessage(
        claim_id=claim_id,
        user_id=None,
        role="ai",
        message=message_text,
    )
    db.add(ai_chat)
    db.commit()
    db.refresh(ai_chat)

    room = str(claim_id)
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
    saved_files = [] # Initialize saved_files list
    if file:
    # Use absolute path in container
        storage_path = f"/home/app/uploads/claims/{claim_id}/{file.filename}"
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(await file.read())
        attachment_url = f"/static/uploads/claims/{claim_id}/{file.filename}"
        attachment_name = file.filename
        saved_files.append(storage_path)     
        print(f"DEBUG CHAT: Saved file to: {storage_path}")

    # Store user's message
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

    # --- RAG retrieval and analysis ---
    print(f"DEBUG RAG: ========== RAG Retrieval ==========")
    print(f"DEBUG RAG: User message: '{message_text}'")
    print(f"DEBUG RAG: Message length: {len(message_text)}")
    print(f"DEBUG RAG: Claim ID: {claim_id}")
    
    try:
        rag_service = get_rag_service()
        # Add existing uploaded documents from the claim to the RAG service
        if claim.uploaded_documents:
            rag_service.add_documents(claim.uploaded_documents)
        # Add any newly uploaded files to the RAG service
        if saved_files:
            rag_service.add_documents(saved_files)

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
            
        # Call analyse_claim_with_rag to get the structured analysis
        # Pass the claim_type and description to analyse_claim_with_rag
        claim_analysis_json_str = analyse_claim_with_rag(
            claim_type=claim.claim_type,
            description=claim.incident_description, # Use claim's description for analysis
            files=saved_files # Pass any newly uploaded files for analysis
        )
        claim_analysis_dict = json.loads(claim_analysis_json_str)
        print(f"DEBUG CHAT: Claim Analysis: {claim_analysis_dict}")

    except Exception as e:
        print(f"DEBUG RAG: RAG service error: {type(e).__name__}: {e}")
        context_chunks = []
        claim_analysis_dict = {} # Ensure it's an empty dict on error

    # --- AI generation with grounding & JSON citations ---
    print(f"DEBUG AI: ========== AI Generation ==========")
    print(f"DEBUG AI: Passing {len(context_chunks)} chunks to AI")
    
    try:
        print("DEBUG AI: Calling generate_ai_reply_rag()...")
        ai_result: AIAnswer = await generate_ai_reply_rag(
            claim,
            message_text,
            context_chunks,
        )
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