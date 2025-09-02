
from __future__ import annotations
from typing import Optional, Literal, Set
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, Date
from pydantic import BaseModel

from ..db import get_db
from ..models import User, UserRole, Claim, ChatMessage
from ..routes.auth import require_active_user_with_roles
from ..services.ai import summarize_claim_for_staff

router = APIRouter()

# Define role-based access dependencies
can_process_claims = require_active_user_with_roles({UserRole.agent, UserRole.admin})
can_view_analytics = require_active_user_with_roles({UserRole.data_analyst, UserRole.admin})
is_admin = require_active_user_with_roles({UserRole.admin})

@router.get("/test")
def test_endpoint():
    return {"message": "Admin router is working"}

@router.get("/claims")
def list_claims(
    status: Optional[str] = Query(default=None),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(can_process_claims)
):
    q = db.query(Claim)
    if status:
        q = q.filter(Claim.status == status)
    total = q.count()
    rows = (
        q.order_by(Claim.created_at.desc())
         .offset((page - 1) * page_size)
         .limit(page_size)
         .all()
    )
    data = [{
        "id": c.id,
        "claim_number": c.claim_number,
        "status": c.status,
        "claim_type": c.claim_type,
        "created_at": c.created_at.isoformat(),
        "user_id": c.user_id,
    } for c in rows]
    return {"total": total, "page": page, "page_size": page_size, "claims": data}

@router.get("/claims/{claim_id}")
async def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(can_process_claims)
):
    c = db.query(Claim).filter(Claim.id == claim_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.claim_id == claim_id).all()
    ai_summary_data = await summarize_claim_for_staff(c, messages)
    
    return {
        "id": c.id,
        "claim_number": c.claim_number,
        "status": c.status,
        "claim_type": c.claim_type,
        "incident_description": c.incident_description,
        "created_at": c.created_at.isoformat(),
        "user_id": c.user_id,
        "ai_summary": ai_summary_data["summary"],
        "risk_score": ai_summary_data["risk_score"],
        "facts": ai_summary_data["facts"],
    }

class DecisionBody(BaseModel):
    decision: Literal["approve", "reject", "needs_info"]
    notes: Optional[str] = None

@router.post("/claims/{claim_id}/decision")
def decide_claim(
    claim_id: int,
    body: DecisionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(can_process_claims)
):
    c = db.query(Claim).filter(Claim.id == claim_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Claim not found")
    next_status = {
        "approve": "approved",
        "reject": "rejected",
        "needs_info": "needs_info",
    }[body.decision]
    c.status = next_status
    db.commit()
    return {"ok": True, "claim_id": c.id, "status": c.status}

@router.get("/metrics")
def metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(can_view_analytics)
):
    total = db.query(func.count(Claim.id)).scalar() or 0
    by_status = dict(db.query(Claim.status, func.count(Claim.id)).group_by(Claim.status))
    return {"total": total, "by_status": by_status}

@router.get("/analytics/claims-by-date")
def claims_by_date(
    db: Session = Depends(get_db),
    current_user: User = Depends(can_view_analytics)
):
    results = db.query(
        func.date(Claim.created_at).label('date'),
        func.count(Claim.id).label('count')
    ).group_by(func.date(Claim.created_at)).all()
    
    return [{"date": str(r.date), "count": r.count} for r in results]

@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(is_admin)
):
    users = db.query(User).all()
    return [{"id": u.id, "email": u.email, "role": u.role.value, "created_at": u.created_at.isoformat()} for u in users]

class RoleUpdate(BaseModel):
    new_role: UserRole

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(is_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.new_role
    db.commit()
    return {"ok": True, "user_id": user.id, "new_role": body.new_role.value}
