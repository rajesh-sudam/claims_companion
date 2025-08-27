from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Document  # You need a Document model/table

router = APIRouter()

@router.post("/claims/{claim_id}/upload")
async def upload_document(claim_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Validate type/size as before
    contents = await file.read()
    # Save file to disk
    filename = f"{claim_id}_{file.filename}"
    with open(f"uploads/{filename}", "wb") as f:
        f.write(contents)
    # Save metadata to DB
    doc = Document(
        claim_id=claim_id,
        filename=filename,
        content_type=file.content_type,
        size=len(contents),
        # Add other fields as needed
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    # Optionally run OCR and return preview
    return {"filename": filename, "id": doc.id}