# Enhanced validation service with AI-powered document analysis
from __future__ import annotations
import os
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import re
from pathlib import Path
import PyPDF2
from PIL import Image
import pytesseract

@dataclass
class ChecklistItem:
    key: str
    title: str
    required: bool = True
    doc_type: Optional[str] = None
    claim_fields: Optional[List[str]] = None
    accept_ext: Optional[List[str]] = None
    max_mb: Optional[int] = 10
    ai_validation_prompt: Optional[str] = None  # For AI-powered validation
    alternative_docs: Optional[List[str]] = None  # Alternative document types

@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    issues: List[str]
    suggestions: List[str]
    extracted_data: Dict[str, Any]

# Enhanced checklists with AI validation prompts

MOTOR_CHECKLIST: List[ChecklistItem] = [
    ChecklistItem(
        "incident_date", 
        "Date when the incident occurred", 
        True, 
        None, 
        ["incident_date"],
        ai_validation_prompt="Verify the incident date is provided and reasonable (not in future, within policy period)"
    ),
    ChecklistItem(
        "description", 
        "Detailed description of what happened", 
        True, 
        None, 
        ["incident_description"],
        ai_validation_prompt="Check if description includes: what happened, where, how the damage occurred, other parties involved"
    ),
    ChecklistItem(
        "damage_photos", 
        "Clear photos showing vehicle damage from multiple angles", 
        True, 
        "motor_photos", 
        accept_ext=[".jpg", ".jpeg", ".png", ".heic", ".webp"],
        ai_validation_prompt="Analyze if photos clearly show vehicle damage, are not blurry, show multiple angles, include license plate if visible"
    ),
    ChecklistItem(
        "repair_invoice", 
        "Repair invoice, estimate, or quotation", 
        False, 
        "repair_invoice", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Verify document shows repair costs, labor, parts, is from legitimate repair shop",
        alternative_docs=["repair_estimate", "quotation"]
    ),
    ChecklistItem(
        "police_report", 
        "Garda report or incident number (if applicable)", 
        False, 
        "police_report", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Check if document is official police report with incident number, date, parties involved"
    ),
    ChecklistItem(
        "drivers_license", 
        "Valid driver's license of the person driving", 
        True, 
        "drivers_license", 
        accept_ext=[".jpg", ".jpeg", ".png", ".pdf"],
        ai_validation_prompt="Verify license is valid, not expired, matches policy holder or authorized driver"
    ),
]

HOME_CHECKLIST: List[ChecklistItem] = [
    ChecklistItem(
        "incident_date", 
        "Date when the damage/loss occurred", 
        True, 
        None, 
        ["incident_date"],
        ai_validation_prompt="Verify incident date is provided and reasonable"
    ),
    ChecklistItem(
        "description", 
        "Detailed description of what was damaged/lost and how", 
        True, 
        None, 
        ["incident_description"],
        ai_validation_prompt="Check description includes: what was damaged, cause of damage, extent of loss"
    ),
    ChecklistItem(
        "damage_photos", 
        "Clear photos of property damage", 
        True, 
        "home_photos", 
        accept_ext=[".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Analyze photos show clear damage to property, multiple angles, good lighting"
    ),
    ChecklistItem(
        "proof_ownership", 
        "Proof of ownership (receipts, photos of items before damage)", 
        True, 
        "proof_ownership", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Verify documents prove ownership of damaged items, show purchase dates and values"
    ),
    ChecklistItem(
        "repair_quotes", 
        "Professional repair or replacement quotes", 
        False, 
        "repair_quotes", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Check quotes are from legitimate contractors, include detailed breakdown of costs"
    ),
    ChecklistItem(
        "police_report", 
        "Police report (for theft, vandalism, break-in)", 
        False, 
        "police_report", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Verify official police report for criminal activity"
    ),
]

TRAVEL_CHECKLIST: List[ChecklistItem] = [
    ChecklistItem(
        "trip_dates", 
        "Travel dates and destination", 
        True, 
        None, 
        ["incident_date"],
        ai_validation_prompt="Verify travel dates are within policy coverage period"
    ),
    ChecklistItem(
        "itinerary", 
        "Travel itinerary or booking confirmation", 
        True, 
        "itinerary", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Check document shows confirmed bookings, dates, destinations, passenger names"
    ),
    ChecklistItem(
        "boarding_pass", 
        "Boarding passes or flight tickets", 
        True, 
        "boarding_pass", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Verify boarding passes match itinerary, show actual travel occurred"
    ),
    ChecklistItem(
        "description", 
        "Detailed description of the incident", 
        True, 
        None, 
        ["incident_description"],
        ai_validation_prompt="Check description explains what happened, when, where, impact on travel"
    ),
    ChecklistItem(
        "receipts", 
        "Receipts for additional expenses incurred", 
        False, 
        "travel_receipts", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Verify receipts are legitimate, relate to travel disruption, show reasonable amounts"
    ),
    ChecklistItem(
        "pir", 
        "Property Irregularity Report (for lost/delayed baggage)", 
        False, 
        "pir", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Check PIR is official airline document with reference number"
    ),
]

HEALTH_CHECKLIST: List[ChecklistItem] = [
    ChecklistItem(
        "treatment_date", 
        "Date of medical treatment", 
        True, 
        None, 
        ["incident_date"],
        ai_validation_prompt="Verify treatment date is within policy coverage period"
    ),
    ChecklistItem(
        "description", 
        "Medical condition, symptoms, or reason for treatment", 
        True, 
        None, 
        ["incident_description"],
        ai_validation_prompt="Check description includes medical condition, symptoms, treatment needed"
    ),
    ChecklistItem(
        "medical_invoices", 
        "Itemized medical bills and invoices", 
        True, 
        "medical_invoices", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Verify invoices are from licensed medical providers, show detailed treatments and costs"
    ),
    ChecklistItem(
        "medical_referral", 
        "Doctor's referral letter or prescription", 
        False, 
        "referral", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Check referral is from qualified medical practitioner, relates to claimed treatment"
    ),
    ChecklistItem(
        "discharge_summary", 
        "Hospital discharge summary (if applicable)", 
        False, 
        "discharge", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Verify discharge summary shows dates, treatments, diagnosis"
    ),
    ChecklistItem(
        "membership_card", 
        "Health insurance membership card or policy number", 
        False, 
        "membership_card", 
        accept_ext=[".pdf", ".jpg", ".jpeg", ".png"],
        ai_validation_prompt="Check membership card matches policy holder information"
    ),
]

CHECKLISTS: Dict[str, List[ChecklistItem]] = {
    "motor": MOTOR_CHECKLIST,
    "property": HOME_CHECKLIST,
    "travel": TRAVEL_CHECKLIST,
    "health": HEALTH_CHECKLIST,
}

class AIDocumentValidator:
    """AI-powered document validation and analysis"""
    
    def __init__(self, openai_client=None):
        self.openai_client = openai_client
    
    async def validate_document(self, file_path: str, checklist_item: ChecklistItem) -> ValidationResult:
        """Validate a document using AI analysis"""
        try:
            # Extract text/data from document
            extracted_data = self._extract_document_data(file_path)
            
            if not extracted_data.get('text') and not extracted_data.get('is_image'):
                return ValidationResult(
                    is_valid=False,
                    confidence_score=0.0,
                    issues=["Could not read document content"],
                    suggestions=["Please upload a clearer version or different file format"],
                    extracted_data={}
                )
            
            # AI-powered validation if OpenAI client available
            if self.openai_client and checklist_item.ai_validation_prompt:
                ai_result = await self._ai_validate_content(
                    extracted_data, 
                    checklist_item.ai_validation_prompt,
                    checklist_item.key
                )
                return ai_result
            
            # Fallback basic validation
            return self._basic_validation(extracted_data, checklist_item)
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                issues=[f"Error processing document: {str(e)}"],
                suggestions=["Please try uploading the document again"],
                extracted_data={}
            )
    
    def _extract_document_data(self, file_path: str) -> Dict[str, Any]:
        """Extract text and metadata from document"""
        file_ext = Path(file_path).suffix.lower()
        data = {
            'file_path': file_path,
            'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            'file_type': file_ext
        }
        
        try:
            if file_ext == '.pdf':
                # Extract text from PDF
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() or ""
                    data['text'] = text
                    data['page_count'] = len(reader.pages)
            
            elif file_ext in ['.jpg', '.jpeg', '.png', '.heic', '.webp']:
                # OCR on images
                data['is_image'] = True
                try:
                    image = Image.open(file_path)
                    data['image_size'] = image.size
                    # Basic OCR (install pytesseract: pip install pytesseract)
                    try:
                        text = pytesseract.image_to_string(image)
                        data['text'] = text
                        data['ocr_confidence'] = 'medium'  # Would need actual confidence from OCR
                    except:
                        data['text'] = ""
                        data['ocr_confidence'] = 'failed'
                except Exception as e:
                    data['image_error'] = str(e)
            
        except Exception as e:
            data['extraction_error'] = str(e)
        
        return data
    
    async def _ai_validate_content(self, extracted_data: Dict[str, Any], validation_prompt: str, doc_type: str) -> ValidationResult:
        """Use AI to validate document content"""
        
        content_text = extracted_data.get('text', '')[:2000]  # Limit text length
        
        prompt = f"""
        You are an insurance document validator. Analyze this document content and validate it based on the requirements.
        
        Document type: {doc_type}
        Validation requirements: {validation_prompt}
        
        Document content:
        {content_text}
        
        Document metadata: {json.dumps({k: v for k, v in extracted_data.items() if k != 'text'}, indent=2)}
        
        Respond in JSON format with:
        {{
            "is_valid": true/false,
            "confidence_score": 0.0-1.0,
            "issues": ["list of specific issues found"],
            "suggestions": ["list of specific suggestions for improvement"],
            "extracted_info": {{"key": "value pairs of useful information found"}}
        }}
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return ValidationResult(
                is_valid=result.get('is_valid', False),
                confidence_score=result.get('confidence_score', 0.5),
                issues=result.get('issues', []),
                suggestions=result.get('suggestions', []),
                extracted_data=result.get('extracted_info', {})
            )
            
        except Exception as e:
            # Fallback if AI validation fails
            return self._basic_validation(extracted_data, None)
    
    def _basic_validation(self, extracted_data: Dict[str, Any], checklist_item: Optional[ChecklistItem]) -> ValidationResult:
        """Basic validation without AI"""
        issues = []
        suggestions = []
        
        # Check file size
        file_size_mb = extracted_data.get('file_size', 0) / (1024 * 1024)
        max_size = checklist_item.max_mb if checklist_item else 10
        
        if file_size_mb > max_size:
            issues.append(f"File size ({file_size_mb:.1f}MB) exceeds limit ({max_size}MB)")
            suggestions.append("Please compress the file or upload a smaller version")
        
        # Check if text was extracted
        text_content = extracted_data.get('text', '').strip()
        
        if extracted_data.get('is_image') and len(text_content) < 10:
            issues.append("Image appears to contain little readable text")
            suggestions.append("Please ensure the image is clear and well-lit")
        
        if extracted_data.get('file_type') == '.pdf' and len(text_content) < 20:
            issues.append("PDF appears to be scanned or contains little text")
            suggestions.append("Please ensure the PDF is readable or upload a clearer version")
        
        is_valid = len(issues) == 0
        confidence = 0.8 if is_valid else 0.3
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=confidence,
            issues=issues,
            suggestions=suggestions if issues else ["Document appears to be readable"],
            extracted_data={'text_length': len(text_content)}
        )

class SmartClaimValidator:
    """Enhanced claim validation with AI-powered analysis"""
    
    def __init__(self, openai_client=None):
        self.doc_validator = AIDocumentValidator(openai_client)
    
    async def build_smart_checklist_status(self, claim, claim_documents: List, claim_type: str) -> Dict[str, Any]:
        """Build enhanced checklist status with AI validation"""
        items = CHECKLISTS.get(claim_type, [])
        status = []
        satisfied = 0
        total_confidence = 0.0
        
        # Build document index
        by_type: Dict[str, list] = {}
        for d in claim_documents:
            by_type.setdefault(d.document_type or d.doc_type, []).append(d)
        
        # Helper: check claim fields
        def _has_field(field: str) -> bool:
            val = getattr(claim, field, None)
            return bool(val and str(val).strip())
        
        for item in items:
            present = False
            invalid = False
            confidence = 0.0
            evidence = []
            validation_details = {}
            
            if item.doc_type:
                # Document-based validation
                docs = by_type.get(item.doc_type, [])
                if docs:
                    present = True
                    # Validate each document with AI
                    for doc in docs:
                        if hasattr(doc, 'file_url') and doc.file_url:
                            # Convert URL to file path
                            file_path = doc.file_url.replace('/static/', '/home/app/')
                            validation_result = await self.doc_validator.validate_document(file_path, item)
                            
                            if not validation_result.is_valid:
                                invalid = True
                            
                            confidence = max(confidence, validation_result.confidence_score)
                            validation_details[doc.file_name] = {
                                'is_valid': validation_result.is_valid,
                                'issues': validation_details.issues,
                                'suggestions': validation_result.suggestions,
                                'confidence': validation_result.confidence_score
                            }
                        
                        evidence.append(doc.file_name)
                
                # Check for alternative document types
                if not present and item.alternative_docs:
                    for alt_type in item.alternative_docs:
                        alt_docs = by_type.get(alt_type, [])
                        if alt_docs:
                            present = True
                            evidence.extend([d.file_name for d in alt_docs])
                            break
                            
            elif item.claim_fields:
                # Field-based validation
                present = all(_has_field(f) for f in item.claim_fields)
                confidence = 1.0 if present else 0.0
            
            # Determine state
            if present and not invalid and confidence > 0.6:
                state = "ok"
                satisfied += 1
            elif present and (invalid or confidence <= 0.6):
                state = "needs_review"
            elif present and invalid:
                state = "invalid"
            else:
                state = "missing"
            
            total_confidence += confidence
            
            status.append({
                "key": item.key,
                "title": item.title,
                "required": item.required,
                "state": state,
                "confidence": round(confidence, 2),
                "doc_type": item.doc_type,
                "evidence": evidence,
                "validation_details": validation_details
            })
        
        # Calculate progress
        required_items = [s for s in status if s["required"]]
        req_total = len(required_items)
        req_satisfied = sum(1 for s in required_items if s["state"] == "ok")
        progress = int((req_satisfied / req_total) * 100) if req_total else 100
        
        # Generate intelligent next prompt
        next_prompt = self._generate_next_prompt(status, claim_type)
        
        # Enhanced decision logic
        decision = self._make_intelligent_decision(status, total_confidence / len(status) if status else 0)
        
        return {
            "items": status,
            "progress": progress,
            "overall_confidence": round(total_confidence / len(status), 2) if status else 0,
            "decision_hint": decision,
            "next_prompt": next_prompt,
            "claim_type": claim_type,
            "validation_summary": self._create_validation_summary(status)
        }
    
    def _generate_next_prompt(self, status: List[Dict], claim_type: str) -> str:
        """Generate intelligent next step prompt"""
        
        # Find first missing required item
        missing_required = next((s for s in status if s["required"] and s["state"] == "missing"), None)
        if missing_required:
            return f"Next: Please {self._get_action_verb(missing_required)} your {missing_required['title'].lower()}."
        
        # Find first invalid item that needs fixing
        invalid_item = next((s for s in status if s["state"] == "invalid"), None)
        if invalid_item:
            # Get specific suggestion from validation details
            suggestions = []
            for doc_name, details in invalid_item.get('validation_details', {}).items():
                suggestions.extend(details.get('suggestions', []))
            
            if suggestions:
                return f"Issue with {invalid_item['title']}: {suggestions[0]}"
            else:
                return f"The uploaded {invalid_item['title'].lower()} needs to be clearer. Please upload a better version."
        
        # Find items needing review
        review_item = next((s for s in status if s["state"] == "needs_review"), None)
        if review_item:
            return f"Your {review_item['title'].lower()} needs verification. Please ensure it's clear and complete."
        
        # Find optional items that would help
        missing_optional = [s for s in status if not s["required"] and s["state"] == "missing"]
        if missing_optional:
            return f"Optional: You may also provide {missing_optional[0]['title'].lower()} to strengthen your claim."
        
        # All items satisfied
        required_done = sum(1 for s in status if s["required"] and s["state"] == "ok")
        total_required = sum(1 for s in status if s["required"])
        
        if required_done == total_required:
            return "All required documents received! Your claim is being processed."
        
        return "Please provide any missing information to complete your claim."
    
    def _get_action_verb(self, item: Dict) -> str:
        """Get appropriate action verb for the item"""
        if item.get('doc_type'):
            return "upload" if "photo" in item['title'].lower() else "attach"
        else:
            return "provide"
    
    def _make_intelligent_decision(self, status: List[Dict], avg_confidence: float) -> str:
        """Make intelligent decision about claim status"""
        
        required_items = [s for s in status if s["required"]]
        required_ok = sum(1 for s in required_items if s["state"] == "ok")
        required_total = len(required_items)
        
        invalid_count = sum(1 for s in status if s["state"] == "invalid")
        missing_count = sum(1 for s in required_items if s["state"] == "missing")
        
        if missing_count > 0:
            return "needs_more_info"
        elif invalid_count > 0:
            return "needs_correction"
        elif required_ok == required_total and avg_confidence > 0.8:
            return "ready_for_review" 
        elif required_ok == required_total and avg_confidence > 0.6:
            return "pre_approve"
        else:
            return "needs_verification"
    
    def _create_validation_summary(self, status: List[Dict]) -> Dict[str, Any]:
        """Create summary of validation results"""
        
        total_items = len(status)
        ok_items = sum(1 for s in status if s["state"] == "ok")
        missing_items = sum(1 for s in status if s["state"] == "missing")
        invalid_items = sum(1 for s in status if s["state"] == "invalid")
        review_items = sum(1 for s in status if s["state"] == "needs_review")
        
        return {
            "total_items": total_items,
            "completed_items": ok_items,
            "missing_items": missing_items,
            "invalid_items": invalid_items,
            "review_items": review_items,
            "completion_rate": round((ok_items / total_items) * 100, 1) if total_items else 0
        }

# Integration functions for your existing codebase

async def get_smart_validation_status(claim, claim_documents: List, openai_client=None) -> Dict[str, Any]:
    """Main function to get enhanced validation status"""
    validator = SmartClaimValidator(openai_client)
    return await validator.build_smart_checklist_status(claim, claim_documents, claim.claim_type)

def get_basic_checklist_items(claim_type: str) -> List[Dict[str, Any]]:
    """Get basic checklist items for display"""
    items = CHECKLISTS.get(claim_type, [])
    return [
        {
            "key": item.key,
            "title": item.title,
            "required": item.required,
            "doc_type": item.doc_type,
            "accept_extensions": item.accept_ext,
            "max_size_mb": item.max_mb
        }
        for item in items
    ]