from fastapi import APIRouter, Depends, Header, HTTPException, File, UploadFile, Form
from pathlib import Path
import uuid
import random
import string
from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Claim, ClaimProgress, ClaimDocument, User
from ..auth_utils import decode_access_token
from ..rag import analyse_claim_with_rag
from .chat import initiate_smart_document_request, send_human_review_message
from ..services.ai_validation import get_smart_validation_status, AIDocumentValidator
from ..services.ai import _client as openai_client
import os
import json

router = APIRouter(prefix="/claims", tags=["claims"])

def _get_user_id(authorization: str | None) -> int:
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
    """Create a new claim with enhanced validation and AI analysis."""
    user_id = _get_user_id(authorization)
    
    # Generate claim number
    rand_part = ''.join(random.choices(string.digits, k=6))
    claim_number = f"CLM{user_id:04d}{rand_part}"
    
    # Create claim with validation fields
    claim = Claim(
        claim_number=claim_number,
        user_id=user_id,
        claim_type=claim_type,
        status="submitted",
        incident_date=incident_date,
        incident_description=incident_description,
        uploaded_documents=[],
        validation_progress=0,
        validation_status="pending",
        manual_review_required=False
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    
    # Create consistent upload directory
    upload_dir = Path(f"/home/app/uploads/claims/{claim.id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Process uploaded files with validation
    saved_files = []
    doc_validator = AIDocumentValidator(openai_client)
    
    for file in files:
        # Save file with consistent naming
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create database record
        doc_record = ClaimDocument(
            claim_id=claim.id,
            file_name=file.filename,
            file_url=f"/static/uploads/claims/{claim.id}/{file.filename}",
            document_type="initial_upload",
            status="pending_validation",
            file_size_bytes=len(content),
            mime_type=file.content_type
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)
        
        # AI validation of document
        try:
            validation_result = await doc_validator.validate_document(
                str(file_path), 
                None  # Will determine appropriate checklist item based on content
            )
            
            # Update document with validation results
            doc_record.validation_status = "valid" if validation_result.is_valid else "invalid"
            doc_record.validation_confidence = validation_result.confidence_score
            doc_record.validation_issues = json.dumps(validation_result.issues)
            doc_record.validation_suggestions = json.dumps(validation_result.suggestions)
            doc_record.extracted_data = json.dumps(validation_result.extracted_data)
            doc_record.ai_validated_at = datetime.now(timezone.utc)
            
        except Exception as e:
            doc_record.validation_status = "error"
            doc_record.validation_issues = json.dumps([f"Validation error: {str(e)}"])
        
        saved_files.append(str(file_path))
    
    claim.uploaded_documents = saved_files
    db.commit()

    # Get comprehensive validation status
    claim_documents = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim.id).all()
    validation_status = await get_smart_validation_status(claim, claim_documents, openai_client)
    
    # Update claim with validation results
    claim.validation_progress = validation_status.get('progress', 0)
    claim.validation_status = validation_status.get('decision_hint', 'pending')
    claim.last_validation_update = datetime.now(timezone.utc)
    
    # Determine if manual review is needed
    if validation_status.get('decision_hint') in ['needs_correction', 'needs_verification']:
        claim.manual_review_required = True
    
    db.commit()

    # Add progress steps
    step = ClaimProgress(
        claim_id=claim.id,
        step_id="submitted",
        step_title="Claim Submitted",
        status="completed",
        completed_at=datetime.now(timezone.utc),
        description=f"Claim {claim.claim_number} received with {len(files)} document(s)"
    )
    db.add(step)
    
    # Add validation step
    validation_step = ClaimProgress(
        claim_id=claim.id,
        step_id="initial_validation",
        step_title="Document Validation",
        status="completed",
        completed_at=datetime.now(timezone.utc),
        description=f"AI validation completed: {validation_status.get('progress', 0)}% complete"
    )
    db.add(validation_step)
    db.commit()
    
    # Initiate smart document request if needed
    if validation_status.get('progress', 0) < 100:
        await initiate_smart_document_request(claim.id, db)
    
    return {
        "claim": {
            "id": claim.id,
            "claim_number": claim.claim_number,
            "status": claim.status,
            "claim_type": claim.claim_type,
            "validation_progress": claim.validation_progress,
            "next_step": validation_status.get('next_prompt')
        }
    }

@router.post("/{claim_id}/documents")
async def upload_documents(
    claim_id: int,
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Enhanced document upload with real-time validation."""
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    upload_dir = Path(f"/home/app/uploads/claims/{claim_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    doc_validator = AIDocumentValidator(openai_client)
    uploaded_docs = []
    validation_results = []
    
    for file in files:
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create document record
        doc_record = ClaimDocument(
            claim_id=claim_id,
            file_name=file.filename,
            file_url=f"/static/uploads/claims/{claim_id}/{file.filename}",
            document_type="supplemental_upload",
            status="pending_validation",
            file_size_bytes=len(content),
            mime_type=file.content_type
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)
        
        # Validate document
        try:
            validation_result = await doc_validator.validate_document(str(file_path), None)
            
            doc_record.validation_status = "valid" if validation_result.is_valid else "invalid"
            doc_record.validation_confidence = validation_result.confidence_score
            doc_record.validation_issues = json.dumps(validation_result.issues)
            doc_record.validation_suggestions = json.dumps(validation_result.suggestions)
            doc_record.extracted_data = json.dumps(validation_result.extracted_data)
            doc_record.ai_validated_at = datetime.now(timezone.utc)
            
            validation_results.append({
                "filename": file.filename,
                "is_valid": validation_result.is_valid,
                "confidence": validation_result.confidence_score,
                "issues": validation_result.issues,
                "suggestions": validation_result.suggestions
            })
            
        except Exception as e:
            doc_record.validation_status = "error"
            doc_record.validation_issues = json.dumps([f"Validation error: {str(e)}"])
            validation_results.append({
                "filename": file.filename,
                "is_valid": False,
                "confidence": 0.0,
                "issues": [f"Validation error: {str(e)}"],
                "suggestions": ["Please try uploading again"]
            })
        
        uploaded_docs.append(doc_record)
    
    db.commit()
    
    # Get updated validation status
    claim_documents = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()
    validation_status = await get_smart_validation_status(claim, claim_documents, openai_client)
    
    # Update claim validation
    claim.validation_progress = validation_status.get('progress', 0)
    claim.validation_status = validation_status.get('decision_hint', 'pending')
    claim.last_validation_update = datetime.now(timezone.utc)
    
    if validation_status.get('decision_hint') in ['ready_for_review', 'pre_approve']:
        claim.status = "pending_human_review"
        await send_human_review_message(claim_id, db)
    
    db.commit()
    
    # Add progress step
    upload_step = ClaimProgress(
        claim_id=claim_id,
        step_id="documents_uploaded",
        step_title="Documents Uploaded",
        status="completed",
        completed_at=datetime.now(timezone.utc),
        description=f"{len(files)} document(s) uploaded and validated ({validation_status.get('progress', 0)}% complete)"
    )
    db.add(upload_step)
    db.commit()
    
    return {
        "uploaded_files": [doc.file_name for doc in uploaded_docs],
        "validation_results": validation_results,
        "overall_validation": validation_status,
        "next_step": validation_status.get('next_prompt')
    }

@router.get("/{claim_id}/validation")
async def get_claim_validation_status(
    claim_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None)
):
    """Get detailed validation status for a claim."""
    user_id = _get_user_id(authorization)
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.user_id == user_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    claim_documents = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim_id).all()
    validation_status = await get_smart_validation_status(claim, claim_documents, openai_client)
    
    return {
        "claim_id": claim_id,
        "validation_status": validation_status,
        "documents": [
            {
                "id": doc.id,
                "filename": doc.file_name,
                "validation_status": doc.validation_status,
                "confidence": doc.validation_confidence,
                "issues": json.loads(doc.validation_issues) if doc.validation_issues else [],
                "suggestions": json.loads(doc.validation_suggestions) if doc.validation_suggestions else []
            }
            for doc in claim_documents
        ]
    }

# Keep existing endpoints but enhance them with validation data
@router.get("")
def list_claims(db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    user_id = _get_user_id(authorization)
    claims = db.query(Claim).filter(Claim.user_id == user_id).order_by(Claim.created_at.desc()).all()
    return {"claims": [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "claim_type": c.claim_type,
            "status": c.status,
            "incident_date": c.incident_date.isoformat() if c.incident_date else None,
            "validation_progress": getattr(c, 'validation_progress', 0),
            "validation_status": getattr(c, 'validation_status', 'pending'),
            "manual_review_required": getattr(c, 'manual_review_required', False)
        }
        for c in claims
    ]}

@router.get("/{claim_id}")
def get_claim(claim_id: int, db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
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
        "validation_progress": getattr(claim, 'validation_progress', 0),
        "validation_status": getattr(claim, 'validation_status', 'pending'),
        "ai_risk_score": getattr(claim, 'ai_risk_score', None),
        "manual_review_required": getattr(claim, 'manual_review_required', False)
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