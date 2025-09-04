from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional
from ..db import get_db
from ..models import Claim, ChatMessage, UserRole, User, ClaimProgress
from ..services.ai import summarize_claim_for_staff
from ..auth_utils import require_active_user_with_roles

class StatusUpdate(BaseModel):
    status: str

router = APIRouter()

@router.get("/claims")
async def list_admin_claims(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user_with_roles({UserRole.agent, UserRole.admin})),
):
    query = db.query(Claim)
    if status:
        query = query.filter(Claim.status == status)
    
    claims = query.order_by(Claim.created_at.desc()).all()
    
    return {"claims": [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "claim_type": c.claim_type,
            "status": c.status,
            "incident_date": c.incident_date.isoformat() if c.incident_date else None,
            "estimated_completion": c.estimated_completion.isoformat() if c.estimated_completion else None,
        }
        for c in claims
    ]}

@router.get("/claims/{claim_id}/summary")
async def get_claim_summary(claim_id: int, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    messages = db.query(ChatMessage).filter(ChatMessage.claim_id == claim_id).order_by(ChatMessage.created_at.asc()).all()

    summary = await summarize_claim_for_staff(claim, messages)
    return summary

@router.get("/claims/{claim_id}", dependencies=[Depends(require_active_user_with_roles({UserRole.agent, UserRole.admin}))])
async def get_admin_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {
        "claim": {
            "id": claim.id,
            "claim_number": claim.claim_number,
            "claim_type": claim.claim_type,
            "status": claim.status,
            "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
            "incident_description": claim.incident_description,
            "estimated_completion": claim.estimated_completion.isoformat() if claim.estimated_completion else None,
        }
    }

@router.get("/claims/{claim_id}/progress", dependencies=[Depends(require_active_user_with_roles({UserRole.agent, UserRole.admin}))])
async def get_admin_claim_progress(claim_id: int, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    steps = db.query(ClaimProgress).filter(ClaimProgress.claim_id == claim_id).order_by(ClaimProgress.created_at).all()

    progress_list = []
    for step in steps:
        progress_list.append({
            "id": step.id,
            "step_id": step.step_id,
            "step_title": step.step_title,
            "status": step.status,
            "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            "description": step.description,
        })
    return {"progress": progress_list}

@router.get("/chat/{claim_id}/history", dependencies=[Depends(require_active_user_with_roles({UserRole.agent, UserRole.admin}))])
async def get_admin_chat_history(claim_id: int, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
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

@router.put("/claims/{claim_id}/status", dependencies=[Depends(require_active_user_with_roles({UserRole.agent, UserRole.admin}))])
async def update_claim_status(claim_id: int, status_update: StatusUpdate, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim.status = status_update.status
    db.commit()
    return {"status": claim.status}