"""Enhanced Chat and AI endpoints with smart validation and robust document analysis."""

from __future__ import annotations
print("=== LOADING Enhanced Chat MODULE ===")
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Form, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone

import os
import json
from ..db import get_db
from ..models import ChatMessage, Claim, ClaimProgress, ClaimDocument
from ..auth_utils import decode_access_token
from ..sockets import sio
from ..services.ai import generate_ai_reply_rag, AIAnswer, _client as openai_client
from ..rag import RAGService, get_rag_service, analyse_claim_with_rag
from ..services.ai_validation import get_smart_validation_status, get_basic_checklist_items

router = APIRouter(prefix="/chat", tags=["chat"])


# --------------------------
# Helpers
# --------------------------
def _norm_state(s: str | None) -> str:
    return (s or "").lower().replace("-", "_").replace(" ", "_")

def _should_escalate_to_human(validation_status: Dict[str, Any]) -> bool:
    """
    Auto-escalate if:
      - All REQUIRED items exist and are not missing/invalid
      - No REQUIRED item is in 'needs_review'
    Optional items may be missing; that does not block escalation.
    """
    items = validation_status.get("items", []) or []
    required_items = [i for i in items if i.get("required") is True]
    if not required_items:
        return False

    any_required_missing_or_invalid = any(
        _norm_state(i.get("state")) in ("missing", "invalid") for i in required_items
    )
    any_required_needs_review = any(
        _norm_state(i.get("state")) == "needs_review" for i in required_items
    )

    return (not any_required_missing_or_invalid) and (not any_required_needs_review)


async def initiate_smart_document_request(claim_id: int, db: Session):
    """Triggers the AI to generate the first conversational document request."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return

    # Get the initial validation status to guide the AI.
    claim_documents: list[ClaimDocument] = []  # No documents yet
    validation_status = await get_smart_validation_status(claim, claim_documents, openai_client)
    context_chunks: list[Any] = []  # No RAG context needed for the first request

    # Call the main AI reply generator to craft the first, conversational request.
    ai_result: AIAnswer = await generate_ai_reply_rag(
        claim=claim,
        user_text="Hi, I just created my claim and need to know the next step.",  # Friendly prompt to kick things off
        context_chunks=context_chunks,
        validation_status=validation_status,
    )
    message_text = ai_result.answer

    ai_chat = ChatMessage(
        claim_id=claim_id,
        user_id=None,
        role="ai_request_documents",
        message=message_text,
    )
    db.add(ai_chat)

    # Add progress step
    progress_step = ClaimProgress(
        claim_id=claim_id,
        step_id="documents_requested",
        step_title="Smart Document Request",
        status="active",
        description="AI assistant requested specific documents with validation guidance.",
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
    """Enhanced human review message with validation context"""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return

    # Get validation status to customize message
    claim_documents = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()
    try:
        validation_status = await get_smart_validation_status(claim, claim_documents, openai_client)
        progress = validation_status.get("progress", 0)
        decision_hint = validation_status.get("decision_hint", "")

        if progress >= 90 and decision_hint == "ready_for_review":
            message_text = f"""Great news! Your {claim.claim_type} claim documentation is now complete ({progress}% validated).

Your claim has been forwarded to our human review team for final processing. Based on our initial AI analysis, everything looks good and we expect to have a decision within 2-3 business days.

You'll receive updates as your claim progresses through final review."""
        elif progress >= 70:
            message_text = f"""Your {claim.claim_type} claim is {progress}% complete and has been sent for human review.

Our claims specialist will review your documentation and may contact you if any additional information is needed. Expected processing time is 3-5 business days.

Thank you for providing the necessary documentation."""
        else:
            message_text = f"""Your {claim.claim_type} claim has been escalated to our human review team.

While our AI validation is {progress}% complete, a claims specialist will personally review your case to ensure we have everything needed for processing.

You may be contacted within 1-2 business days if additional documentation is required."""
    except Exception:
        # Fallback message if validation status can't be retrieved
        message_text = f"""Thank you for submitting your documents for your {claim.claim_type} claim.

Your claim is now under review by our human claims team. We will notify you of any updates or if additional information is needed.

Expected processing time is 3-5 business days."""

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


@router.get("/{claim_id}/validation-status")
async def get_validation_status(
    claim_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Get current validation status with progress and next steps"""
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Get claim documents
    claim_documents = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()

    # Get smart validation status
    validation_status = await get_smart_validation_status(claim, claim_documents, openai_client)

    return {
        "claim_id": claim_id,
        "claim_type": claim.claim_type,
        "validation_status": validation_status,
    }


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

    # Handle empty messages with files
    if not message_text.strip() and not file:
        raise HTTPException(status_code=400, detail="Please provide a message or upload a file")

    if not message_text.strip() and file:
        message_text = (
            f"I've uploaded a document: {file.filename}. Please analyze this for my {claim.claim_type} claim."
        )

    attachment_url, attachment_name = None, None
    saved_files: list[str] = []

    if file:
        # Get the current validation status to understand what is being requested
        current_docs = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()
        validation_status_pre = await get_smart_validation_status(claim, current_docs, openai_client)

        # Find the first missing required document type
        doc_type = "unknown"
        if validation_status_pre and validation_status_pre.get("items"):
            missing_item = next(
                (item for item in validation_status_pre["items"] if item.get("required") and _norm_state(item.get("state")) == "missing"),
                None,
            )
            if missing_item and missing_item.get("doc_type"):
                doc_type = missing_item["doc_type"]

        # Use absolute path in container
        storage_path = f"/home/app/uploads/claims/{claim_id}/{file.filename}"
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(await file.read())
        attachment_url = f"/static/uploads/claims/{claim_id}/{file.filename}"
        attachment_name = file.filename
        saved_files.append(storage_path)
        print(f"DEBUG CHAT: Saved file to: {storage_path}")
        print(f"DEBUG CHAT: Contextually classified as doc_type: {doc_type}")

        # Create document record with the contextually determined type
        doc_record = ClaimDocument(
            claim_id=claim_id,
            file_name=file.filename,
            file_url=attachment_url,
            document_type=doc_type,
            status="pending_validation",
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)

    # Store user's message
    user_chat = ChatMessage(
        claim_id=claim_id,
        user_id=user_id,
        role="user",
        message=message_text,
        attachment_url=attachment_url,
        attachment_name=attachment_name,
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
            "attachment": {"name": attachment_name, "url": attachment_url} if attachment_url else None,
        },
        to=room,
    )
    print("DEBUG CHAT: Emitted user message via socket")

    # Get current validation status AFTER potential upload
    claim_documents = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()
    validation_status = await get_smart_validation_status(claim, claim_documents, openai_client)

    print(f"DEBUG VALIDATION: Current validation status: {validation_status.get('decision_hint')}")
    print(f"DEBUG VALIDATION: Progress: {validation_status.get('progress')}%")
    print(f"DEBUG VALIDATION: Next prompt: {validation_status.get('next_prompt')}")

    # --- Auto escalate to human verification when required docs need 0 review ---
    if _should_escalate_to_human(validation_status):
        print("DEBUG VALIDATION: All required items OK and 0 review → auto-escalating to human verification")

        # Mark claim status and flags
        claim.status = "under_human_review"
        setattr(claim, "manual_review_required", True)
        setattr(claim, "validation_progress", validation_status.get("progress", 100))
        # A simple textual status string if your Claim model stores it
        setattr(claim, "validation_status", validation_status.get("decision_hint", "ready_for_review"))
        db.commit()

        # Create/append a progress step
        progress_step = ClaimProgress(
            claim_id=claim_id,
            step_id="human_review_started",
            step_title="Sent to Human Verification",
            status="active",
            description="All required docs validated automatically. Escalated to human reviewer.",
            completed_at=datetime.now(timezone.utc),
        )
        db.add(progress_step)
        db.commit()

        # Notify user with a dedicated message
        await send_human_review_message(claim_id, db)

        # Emit claim_updated with documents so frontend can link evidence filenames
        claim_docs = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()
        await sio.emit(
            "claim_updated",
            {
                "claim": {
                    "id": claim.id,
                    "claim_number": claim.claim_number,
                    "claim_type": claim.claim_type,
                    "status": claim.status,
                    "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
                    "validation_progress": getattr(claim, "validation_progress", validation_status.get("progress", 100)),
                    "validation_status": getattr(claim, "validation_status", "ready_for_review"),
                    "manual_review_required": True,
                },
                "progress": [
                    {
                        "id": step.id,
                        "step_id": step.step_id,
                        "step_title": step.step_title,
                        "status": step.status,
                        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                        "description": step.description,
                    }
                    for step in db.query(ClaimProgress)
                    .filter(ClaimProgress.claim_id == claim_id)
                    .order_by(ClaimProgress.created_at)
                    .all()
                ],
                "documents": [
                    {"file_name": d.file_name, "file_url": d.file_url}
                    for d in claim_docs
                    if getattr(d, "file_url", None)
                ],
            },
            to=room,
        )

        # Short-circuit: return immediate response; AI reply not necessary here
        final_response = {
            "message": {
                "id": None,
                "claim_id": claim_id,
                "message_type": "ai",
                "message_text": "All required documents look good. We’ve sent your claim to a human reviewer.",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "sources": [],
            },
            "validation_status": validation_status,
            "progress": validation_status.get("progress", 100),
            "next_step": "Your claim is now in human verification.",
        }
        print(f"DEBUG CHAT: Final response (auto-escalated): {final_response}")
        print(f"DEBUG CHAT: ========== End chat message ==========")
        return final_response

    # --- Upsert Progress Step for Document Upload ---
    if file:  # Only run this if a file was part of this message
        total_docs = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).count()
        progress_step = db.query(ClaimProgress).filter_by(claim_id=claim_id, step_id="documents_uploaded").first()

        if progress_step:
            # Update existing step
            progress_step.description = f"{total_docs} document(s) uploaded and validated ({validation_status.get('progress', 0)}% complete)"
            progress_step.completed_at = datetime.now(timezone.utc)
        else:
            # Create new step if it doesn't exist
            progress_step = ClaimProgress(
                claim_id=claim_id,
                step_id="documents_uploaded",
                step_title="Documents Uploaded",
                status="completed",
                completed_at=datetime.now(timezone.utc),
                description=f"{total_docs} document(s) uploaded and validated ({validation_status.get('progress', 0)}% complete)",
            )
            db.add(progress_step)
        db.commit()

    # --- RAG retrieval and analysis ---
    print(f"DEBUG RAG: ========== RAG Retrieval ==========")
    print(f"DEBUG RAG: User message: '{message_text}'")
    print(f"DEBUG RAG: Message length: {len(message_text)}")

    try:
        rag_service = get_rag_service()

        # Add existing uploaded documents
        if getattr(claim, "uploaded_documents", None):
            rag_service.add_documents(claim.uploaded_documents)
        if saved_files:
            rag_service.add_documents(saved_files)

        # Enhanced query that includes validation context
        query_parts = [message_text]
        if file:
            query_parts.append(f"User uploaded: {file.filename}")
        if validation_status.get("next_prompt"):
            query_parts.append(f"Validation status: {validation_status.get('next_prompt')}")

        enhanced_query = " | ".join(query_parts)
        print(f"DEBUG RAG: Enhanced query: '{enhanced_query}'")

        try:
            context_chunks: List[Any] = rag_service.retrieve(enhanced_query, top_k=5)
            print(f"DEBUG RAG: Retrieved {len(context_chunks)} chunks")
        except Exception as e:
            print(f"DEBUG RAG: RAG service error: {e}")
            context_chunks = []

        if context_chunks:
            for i, chunk in enumerate(context_chunks):
                chunk_str = str(chunk) if chunk is not None else ""
                chunk_type = type(chunk).__name__
                chunk_preview = (chunk_str[:200] + "...") if len(chunk_str) > 200 else chunk_str
                print(f"DEBUG RAG: Chunk {i} ({chunk_type}): {chunk_preview}")

    except Exception as e:
        print(f"DEBUG RAG: RAG service error: {type(e).__name__}: {e}")
        context_chunks = []

    # --- Enhanced AI generation with validation context ---
    print(f"DEBUG AI: ========== AI Generation ==========")
    print(f"DEBUG AI: Passing {len(context_chunks)} chunks to AI")

    try:
        print("DEBUG AI: Calling generate_ai_reply_rag()...")

        # Create enhanced context that includes validation status
        enhanced_context = []
        if context_chunks:
            enhanced_context.extend(context_chunks)

        # Add validation context as additional information
        validation_context = {
            "id": "validation-status",
            "text": f"VALIDATION STATUS: Progress {validation_status.get('progress', 0)}%, Next: {validation_status.get('next_prompt', 'Continue processing')}",
            "doc_id": "validation",
            "chunk_id": "status",
            "score": 1.0,
        }
        enhanced_context.append(validation_context)

        ai_result: AIAnswer = await generate_ai_reply_rag(
            claim,
            message_text,
            enhanced_context,
            validation_status,  # Pass validation status as additional context
        )
        ai_text = ai_result.answer
        print(f"DEBUG AI: Generated answer: '{ai_text}'")

        # If the response is generic, enhance it with validation guidance
        if "Hello! How can I assist you" in ai_text and validation_status.get("next_prompt"):
            ai_text = (
                f"Thank you for your message! {validation_status.get('next_prompt')}\n\n"
                f"Your claim is currently {validation_status.get('progress', 0)}% complete. How else can I help you today?"
            )

        # Convert citations to serializable format
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

        # Enhanced fallback that uses validation status
        if validation_status.get("next_prompt"):
            ai_text = f"Thanks for your upload! {validation_status.get('next_prompt')}"
        else:
            ai_text = "I've received your message. Let me help you with your claim."
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

    # Broadcast AI message with validation status
    await sio.emit(
        "chat_message",
        {
            "id": ai_chat.id,
            "claim_id": claim_id,
            "message_type": "ai",
            "message_text": ai_chat.message,
            "created_at": ai_chat.created_at.isoformat() if ai_chat.created_at else None,
            "sources": sources,
            "validation_status": validation_status,  # Include validation status for UI
        },
        to=room,
    )
    print("DEBUG CHAT: Emitted AI message via socket")

    # Fetch updated claim and progress to send to client for real-time UI update
    updated_claim = db.query(Claim).filter(Claim.id == claim_id).first()
    progress_steps = (
        db.query(ClaimProgress).filter(ClaimProgress.claim_id == claim_id).order_by(ClaimProgress.created_at).all()
    )
    claim_docs = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()

    await sio.emit(
        "claim_updated",
        {
            "claim": {
                "id": updated_claim.id,
                "claim_number": updated_claim.claim_number,
                "claim_type": updated_claim.claim_type,
                "status": updated_claim.status,
                "incident_date": updated_claim.incident_date.isoformat() if updated_claim.incident_date else None,
                "validation_progress": getattr(updated_claim, "validation_progress", 0),
                "validation_status": getattr(updated_claim, "validation_status", "pending"),
                "manual_review_required": getattr(updated_claim, "manual_review_required", False),
            },
            "progress": [
                {
                    "id": step.id,
                    "step_id": step.step_id,
                    "step_title": step.step_title,
                    "status": step.status,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "description": step.description,
                }
                for step in progress_steps
            ],
            # Provide documents so frontend can map evidence filenames to links
            "documents": [
                {"file_name": d.file_name, "file_url": d.file_url}
                for d in claim_docs
                if getattr(d, "file_url", None)
            ],
        },
        to=room,
    )
    print("DEBUG CHAT: Emitted claim_updated event")

    final_response = {
        "message": {
            "id": ai_chat.id,
            "claim_id": claim_id,
            "message_type": "ai",
            "message_text": ai_chat.message,
            "created_at": ai_chat.created_at.isoformat() if ai_chat.created_at else None,
            "sources": sources,
        },
        "validation_status": validation_status,
        "progress": validation_status.get("progress", 0),
        "next_step": validation_status.get("next_prompt"),
    }

    print(f"DEBUG CHAT: Final response: {final_response}")
    print(f"DEBUG CHAT: ========== End chat message ==========")

    return final_response
