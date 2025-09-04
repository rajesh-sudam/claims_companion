from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import io

from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../../uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf", "text/plain"}
MAX_SIZE_MB = 5

def validate_text(contents: bytes):
    text = contents.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text file is empty")
    # Add more validation as needed (e.g., regex, keywords)
    return text

def run_ocr_on_image(contents: bytes):
    image = Image.open(io.BytesIO(contents))
    return pytesseract.image_to_string(image)

def run_ocr_on_pdf(contents: bytes):
    images = convert_from_bytes(contents)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img)
    return text

@router.post("/claims/{claim_id}/upload")
async def upload_document(claim_id: int, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")
    contents = await file.read()
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    filename = f"{claim_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    # Validation and OCR
    extracted_text = ""
    if file.content_type == "text/plain":
        extracted_text = validate_text(contents)
    elif file.content_type in ["image/jpeg", "image/png"]:
        extracted_text = run_ocr_on_image(contents)
    elif file.content_type == "application/pdf":
        extracted_text = run_ocr_on_pdf(contents)

    return {
        "filename": filename,
        "content_type": file.content_type,
        "size": len(contents),
        "extracted_text": extracted_text[:500]  # Return first 500 chars for preview
    }