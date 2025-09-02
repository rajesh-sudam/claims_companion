from __future__ import annotations
from typing import Optional, Literal
print("=== LOADING ADMIN MODULE ===")
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import User, UserRole, Claim , ChatMessage
from ..auth_utils import decode_access_token
from pydantic import BaseModel
from typing import Optional, Literal
from ..services.ai import summarize_claim , summarize_claim_for_staff  # add this function to services/ai.py


router = APIRouter()

@router.get("/test")
def test_endpoint():
    return {"message": "Admin router is working"}

def current_employee(authorization: str | None, db: Session, allowed: set[UserRole]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    uid = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

@router.get("/claims")
def list_claims(
    status: Optional[str] = Query(default=None),
    page: int = 1,
    page_size: int = 20,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    current_employee(authorization, db, {UserRole.analyst, UserRole.manager})
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
async def get_claim(  # Add async here
    claim_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    current_employee(authorization, db, {UserRole.analyst, UserRole.manager})
    c = db.query(Claim).filter(Claim.id == claim_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    # Get related chat messages for this claim (you'll need to adjust this query)
    # Assuming you have a ChatMessage model with claim_id foreign key
    messages = db.query(ChatMessage).filter(ChatMessage.claim_id == claim_id).all()
    
    # Call the async function with await
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
class DecisionBody(BaseModel):  # Changed from OPENAI_MODEL
    decision: Literal["approve", "reject", "needs_info"]
    notes: Optional[str] = None

@router.post("/claims/{claim_id}/decision")
def decide_claim(
    claim_id: int,
    body: DecisionBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    emp = current_employee(authorization, db, {UserRole.analyst, UserRole.manager})  # Fixed function name
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
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    current_employee(authorization, db, {UserRole.analyst, UserRole.manager})
    total = db.query(func.count(Claim.id)).scalar() or 0
    by_status = dict(db.query(Claim.status, func.count(Claim.id)).group_by(Claim.status))
    return {"total": total, "by_status": by_status}


@router.get("/users")
def list_users(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    current_employee(authorization, db, {UserRole.manager})  # Only managers
    users = db.query(User).all()
    return [{"id": u.id, "email": u.email, "role": u.role.value, "created_at": u.created_at.isoformat()} for u in users]

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    new_role: UserRole,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    current_employee(authorization, db, {UserRole.manager})  # Only managers
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = new_role
    db.commit()
    return {"ok": True, "user_id": user.id, "new_role": new_role.value}

@router.get("/analytics/claims-by-date")
def claims_by_date(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    current_employee(authorization, db, {UserRole.analyst, UserRole.manager})
    # Add date-based claim analytics
    from sqlalchemy import func, Date
    results = db.query(
        func.date(Claim.created_at).label('date'),
        func.count(Claim.id).label('count')
    ).group_by(func.date(Claim.created_at)).all()
    
    return [{"date": str(r.date), "count": r.count} for r in results]