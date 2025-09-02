from fastapi import APIRouter, Depends, Header, HTTPException, File, UploadFile, Form
from pathlib import Path
import uuid
import random
import string
from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Claim, ClaimProgress, User
from ..auth_utils import decode_access_token
from ..rag import analyse_claim_with_rag
print("=== LOADING Claims MODULE ===")
router = APIRouter(prefix="/claims", tags=["claims"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def _get_user_id(authorization: str | None) -> int:
    """Extract the user ID from the bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    try:
        return int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token payload")

@router.post("")
async def create_claim(
    claim_type: str = Form(...),
    incident_date: Optional[date] = Form(None),
    incident_description: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Create a new claim with documents and trigger AI/RAG analysis."""
    user_id = _get_user_id(authorization)
    
    # Generate a claim number
    rand_part = ''.join(random.choices(string.digits, k=6))
    claim_number = f"CLM{user_id:04d}{rand_part}"
    
    # Create the claim record
    claim = Claim(
        claim_number=claim_number,
        user_id=user_id,
        claim_type=claim_type,
        status="submitted",
        incident_date=incident_date,
        incident_description=incident_description,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    
    # Save uploaded files
    saved_files = []
    for file in files:
        ext = Path(file.filename).suffix
        fname = f"{uuid.uuid4()}{ext}"
        fpath = UPLOAD_DIR / fname
        with open(fpath, "wb") as f:
            f.write(await file.read())
        saved_files.append(str(fpath))
    
    # Insert default progress step
    step = ClaimProgress(
        claim_id=claim.id,
        step_id="submitted",
        step_title="Claim Submitted",
        status="completed",
        completed_at=datetime.now(),
        description=f"Your claim has been received and assigned number {claim.claim_number}"
    )
    db.add(step)
    db.commit()
    
    # Run AI/RAG analysis
    try:
        analysis = analyse_claim_with_rag(
            claim_type=claim_type,
            description=incident_description,
            files=saved_files,
        )
        
        # Add AI analysis progress step
        ai_step = ClaimProgress(
            claim_id=claim.id,
            step_id="ai_analysis",
            step_title="AI Validation",
            status="completed",
            completed_at=datetime.now(),
            description=f"AI Analysis: {analysis}"
        )
        db.add(ai_step)
        db.commit()
    except Exception as e:
        # Fallback if RAG pipeline fails
        ai_step = ClaimProgress(
            claim_id=claim.id,
            step_id="ai_analysis",
            step_title="AI Validation",
            status="failed",
            completed_at=datetime.now(),
            description=f"AI analysis failed: {str(e)}"
        )
        db.add(ai_step)
        db.commit()
    
    return {
        "claim": {
            "id": claim.id,
            "claim_number": claim.claim_number,
            "status": claim.status,
            "claim_type": claim.claim_type,
        }
    }

@router.post("/{claim_id}/documents")
async def upload_documents(
    claim_id: int,
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Handle document uploads for a claim."""
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    saved_files = []
    for file in files:
        ext = Path(file.filename).suffix
        fname = f"{uuid.uuid4()}{ext}"
        fpath = UPLOAD_DIR / fname
        with open(fpath, "wb") as f:
            f.write(await file.read())
        saved_files.append(str(fpath))
    
    # Optionally re-run RAG validation on uploaded docs
    try:
        analysis = analyse_claim_with_rag(
            claim_type=claim.claim_type,
            description=claim.incident_description,
            files=saved_files,
        )
        
        # Add document analysis progress step
        doc_step = ClaimProgress(
            claim_id=claim.id,
            step_id="ai_doc_analysis",
            step_title="AI Document Check",
            status="completed",
            completed_at=datetime.now(),
            description=f"AI found: {analysis}"
        )
        db.add(doc_step)
        db.commit()
    except Exception as e:
        # Log error but don't fail the upload
        print(f"Document analysis failed: {str(e)}")
    
    return {"uploaded": saved_files}

# Keep the existing endpoints for listing, getting, and updating claims
@router.get("")
def list_claims(db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    """Return all claims belonging to the authenticated user."""
    user_id = _get_user_id(authorization)
    claims = db.query(Claim).filter(Claim.user_id == user_id).order_by(Claim.created_at.desc()).all()
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

@router.get("/{claim_id}")
def get_claim(claim_id: int, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    """Return details of a single claim if owned by the authenticated user."""
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {"claim": {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "claim_type": claim.claim_type,
        "status": claim.status,
        "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
        "incident_description": claim.incident_description,
        "estimated_completion": claim.estimated_completion.isoformat() if claim.estimated_completion else None,
    }}

@router.get("/{claim_id}/progress")
def get_claim_progress(claim_id: int, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    """Return the progress timeline for a claim."""
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
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