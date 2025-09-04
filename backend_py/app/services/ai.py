from __future__ import annotations
import os
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Dict, Optional, Union
from openai import AsyncOpenAI, OpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print(f"DEBUG INIT: OPENAI_API_KEY exists: {OPENAI_API_KEY is not None}")
print(f"DEBUG INIT: OPENAI_MODEL: {OPENAI_MODEL}")

_client: Optional[AsyncOpenAI] = None
if OPENAI_API_KEY:
    _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    print("DEBUG INIT: OpenAI client initialized successfully")
else:
    print("DEBUG INIT: No OpenAI API key found - client not initialized")

def _fmt_dt(dt: Any) -> str | None:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    try:
        return str(dt)
    except Exception:
        return None

@dataclass
class AICitation:
    id: str
    doc_id: Optional[str] = None
    chunk_id: Optional[str] = None
    score: Optional[float] = None
    snippet: Optional[str] = None

@dataclass
class AIAnswer:
    answer: str
    citations: List[AICitation]

def _normalize_context(context_chunks: List[Union[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Ensure each context chunk has: id, text, doc_id, chunk_id, score."""
    print(f"DEBUG NORMALIZE: Input chunks count: {len(context_chunks)}")
    print(f"DEBUG NORMALIZE: Input chunk types: {[type(ch).__name__ for ch in context_chunks]}")
    
    norm: List[Dict[str, Any]] = []
    for i, ch in enumerate(context_chunks):
        print(f"DEBUG NORMALIZE: Processing chunk {i}: {type(ch).__name__}")
        if isinstance(ch, str):
            chunk_dict = {
                "id": f"ctx-{i+1}",
                "text": ch,
                "doc_id": None,
                "chunk_id": None,
                "score": None,
            }
            print(f"DEBUG NORMALIZE: String chunk {i} -> {len(ch)} chars")
        else:
            chunk_dict = {
                "id": str(ch.get("id") or f"ctx-{i+1}"),
                "text": str(ch.get("text") or ch.get("content") or ""),
                "doc_id": ch.get("doc_id"),
                "chunk_id": ch.get("chunk_id"),
                "score": float(ch.get("score")) if ch.get("score") is not None else None,
            }
            print(f"DEBUG NORMALIZE: Dict chunk {i} -> id={chunk_dict['id']}, text={len(chunk_dict['text'])} chars")
        norm.append(chunk_dict)
    
    # drop empties
    filtered = [c for c in norm if c["text"].strip()]
    print(f"DEBUG NORMALIZE: After filtering empty text: {len(filtered)} chunks remain")
    return filtered

def _build_enhanced_system_prompt(
    claim: Any, 
    norm_context: List[Dict[str, Any]], 
    validation_status: Optional[Dict[str, Any]] = None
) -> str:
    """Build enhanced system prompt with validation context"""
    print(f"DEBUG PROMPT: Building enhanced system prompt with {len(norm_context)} context chunks")
    
    claim_number = getattr(claim, "claim_number", None) or f"#{getattr(claim, 'id', 'N/A')}"
    claim_type = getattr(claim, "claim_type", None) or "claim"
    status = getattr(claim, "status", None) or "submitted"
    created = _fmt_dt(getattr(claim, "created_at", None))
    desc = getattr(claim, "incident_description", None) or ""

    print(f"DEBUG PROMPT: Claim info - number={claim_number}, type={claim_type}, status={status}")

    # Render context with stable IDs so the model can cite them
    blocks = []
    for c in norm_context:
        preview = c["text"]
        if len(preview) > 1200:
            preview = preview[:1200] + "…"
        blocks.append(f"[{c['id']}] (doc={c.get('doc_id')}, chunk={c.get('chunk_id')}, score={c.get('score')})\n{preview}")
        print(f"DEBUG PROMPT: Added context block {c['id']} with {len(preview)} chars")

    context_str = "\n\n---\n\n".join(blocks) if blocks else "No context provided."
    
    # Add validation status information
    validation_context = ""
    if validation_status:
        progress = validation_status.get('progress', 0)
        next_prompt = validation_status.get('next_prompt', '')
        decision_hint = validation_status.get('decision_hint', '')
        validation_summary = validation_status.get('validation_summary', {})
        
        validation_context = f"""
        
CURRENT VALIDATION STATUS:
- Progress: {progress}% complete
- Decision Status: {decision_hint}
- Next Step: {next_prompt}
- Completed Items: {validation_summary.get('completed_items', 0)}/{validation_summary.get('total_items', 0)}
- Missing Items: {validation_summary.get('missing_items', 0)}
- Invalid Items: {validation_summary.get('invalid_items', 0)}

VALIDATION GUIDANCE:
- If documents are missing: Guide the user to upload specific required documents
- If documents are invalid: Explain what's wrong and how to fix it  
- If progress is high: Congratulate and explain next steps
- Always be specific about what's needed rather than giving generic responses
"""

    print(f"DEBUG PROMPT: Final context string length: {len(context_str)}")
    print(f"DEBUG PROMPT: Validation context length: {len(validation_context)}")

    prompt = (
        "You are an intelligent insurance claims assistant for NovaWorks insurance with advanced document validation capabilities.\n\n"
        
        "ENHANCED INSTRUCTIONS:\n"
        "- Answer user questions based on the provided CONTEXT and VALIDATION STATUS\n"
        "- If validation status shows missing/invalid documents, provide specific guidance\n"
        "- Use validation progress to tailor your responses appropriately\n"
        "- Cite sources using [context-id] format when referencing policy information\n"
        "- Be encouraging about progress made while being clear about remaining requirements\n"
        "- For document issues, explain exactly what's needed and why\n"
        "- If user just uploaded a document, acknowledge it and explain next steps\n\n"
        
        f"CLAIM INFORMATION:\n"
        f"Claim Number: {claim_number}\n"
        f"Claim Type: {claim_type}\n"
        f"Status: {status}\n"
        f"Created: {created or 'unknown'}\n"
        f"Incident Description: {desc or 'n/a'}\n"
        
        f"{validation_context}\n"
        
        f"POLICY CONTEXT:\n"
        f"{context_str}\n\n"
        
        "RESPONSE FORMAT - Always respond with valid JSON:\n"
        "{\n"
        '  "answer": "your helpful and specific response here",\n'
        '  "citations": [{"id": "context-id"}] // include if you referenced policy information\n'
        "}\n\n"
        
        "RESPONSE GUIDELINES:\n"
        "- Be warm, professional, and encouraging\n"
        "- Acknowledge any documents uploaded\n"
        "- Provide specific next steps based on validation status\n"
        "- Explain progress made and remaining requirements\n"
        "- Give constructive feedback on document issues\n"
        "- Use plain language, avoid insurance jargon\n"
    )
    
    print(f"DEBUG PROMPT: Final enhanced system prompt length: {len(prompt)}")
    return prompt

async def generate_ai_reply_rag(
    claim: Any,
    user_text: str,
    context_chunks: List[Union[str, Dict[str, Any]]],
    validation_status: Optional[Dict[str, Any]] = None
) -> AIAnswer:
    """Enhanced AI reply generation with validation context"""
    print(f"DEBUG MAIN: ========== Starting Enhanced AI generation ==========")
    print(f"DEBUG MAIN: User query: '{user_text}'")
    print(f"DEBUG MAIN: Client initialized: {_client is not None}")
    print(f"DEBUG MAIN: Raw context chunks received: {len(context_chunks)}")
    print(f"DEBUG MAIN: Validation status provided: {validation_status is not None}")
    
    if context_chunks:
        for i, chunk in enumerate(context_chunks[:3]):
            chunk_preview = str(chunk)[:150] + "..." if len(str(chunk)) > 150 else str(chunk)
            print(f"DEBUG MAIN: Chunk {i}: {chunk_preview}")
    
    norm_context = _normalize_context(context_chunks)
    print(f"DEBUG MAIN: Normalized context chunks: {len(norm_context)}")

    # Fallback if API is unavailable
    if _client is None:
        print("DEBUG MAIN: OpenAI client is None - using enhanced fallback")
        
        # Enhanced fallback using validation status
        if validation_status:
            progress = validation_status.get('progress', 0)
            next_prompt = validation_status.get('next_prompt', '')
            
            if progress < 50:
                fallback = f"I see your claim is {progress}% complete. {next_prompt}"
            elif progress < 100:
                fallback = f"Great progress! Your claim is {progress}% complete. {next_prompt}"
            else:
                fallback = "Your claim documentation is complete! I'm processing your request."
        else:
            fallback = "I'm here to help with your claim. Please let me know what you need."
        
        cits = []
        for c in norm_context[:2]:
            cits.append(AICitation(id=c["id"], doc_id=c.get("doc_id"), chunk_id=c.get("chunk_id"), score=c.get("score")))
        
        return AIAnswer(answer=fallback, citations=cits)

    system_prompt = _build_enhanced_system_prompt(claim, norm_context, validation_status)

    try:
        print("DEBUG MAIN: Making enhanced OpenAI API call...")
        print(f"DEBUG MAIN: Model: {OPENAI_MODEL}")
        print(f"DEBUG MAIN: User message: '{user_text}'")
        
        resp = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,  # Slightly higher for more natural responses
            max_tokens=600,   # Increased for more detailed responses
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text or "I need help with my claim."},  # Handle empty messages
            ],
            response_format={"type": "json_object"},
        )

        raw = (resp.choices[0].message.content or "").strip()
        print(f"DEBUG MAIN: OpenAI raw response: '{raw}'")
        
        answer_text = ""
        citations: List[AICitation] = []
 
        try:
            print("DEBUG MAIN: Parsing enhanced JSON response...")
            data = json.loads(raw)
            print(f"DEBUG MAIN: Parsed JSON keys: {list(data.keys())}")
            
            answer_text = str(data.get("answer", "")).strip()
            print(f"DEBUG MAIN: Extracted answer: '{answer_text}'")
            
            raw_citations = data.get("citations") or []
            print(f"DEBUG MAIN: Raw citations: {raw_citations}")
            
            cit_ids = [str(c.get("id")) for c in raw_citations if isinstance(c, dict) and c.get("id")]
            print(f"DEBUG MAIN: Citation IDs: {cit_ids}")
            
            # Map back to context
            index: Dict[str, Dict[str, Any]] = {c["id"]: c for c in norm_context}
            print(f"DEBUG MAIN: Context index keys: {list(index.keys())}")
            
            for cid in cit_ids:
                c = index.get(cid)
                print(f"DEBUG MAIN: Looking up citation {cid}: {'found' if c else 'NOT FOUND'}")
                if not c:
                    continue
                citations.append(AICitation(
                    id=cid,
                    doc_id=c.get("doc_id"),
                    chunk_id=c.get("chunk_id"),
                    score=c.get("score"),
                    snippet=(c.get("text") or "")[:240]
                ))
            
            print(f"DEBUG MAIN: Final citations count: {len(citations)}")
            
        except json.JSONDecodeError as e:
            print(f"DEBUG MAIN: JSON parsing failed: {e}")
            print(f"DEBUG MAIN: Raw response was: '{raw}'")
            
            # Enhanced fallback parsing with validation context
            if validation_status and validation_status.get('next_prompt'):
                answer_text = f"Thank you for your message. {validation_status.get('next_prompt')}"
            else:
                answer_text = raw or "I'm here to help with your claim."
            
            for c in norm_context[:2]:
                citations.append(AICitation(
                    id=c["id"],
                    doc_id=c.get("doc_id"),
                    chunk_id=c.get("chunk_id"),
                    score=c.get("score"),
                    snippet=(c.get("text") or "")[:240]
                ))

    except Exception as e:
        print(f"DEBUG MAIN: OpenAI API call failed: {type(e).__name__}: {e}")
        
        # Enhanced error fallback with validation context
        if validation_status:
            progress = validation_status.get('progress', 0)
            next_prompt = validation_status.get('next_prompt', '')
            answer_text = f"I'm processing your claim (currently {progress}% complete). {next_prompt}"
        else:
            answer_text = "I'm here to help with your claim. How can I assist you?"
        
        citations = []
        for c in norm_context[:2]:
            citations.append(AICitation(
                id=c["id"],
                doc_id=c.get("doc_id"),
                chunk_id=c.get("chunk_id"),
                score=c.get("score"),
                snippet=(c.get("text") or "")[:240]
            ))

    # Final enhancement check
    if not answer_text.strip():
        if validation_status and validation_status.get('next_prompt'):
            answer_text = validation_status.get('next_prompt')
        else:
            answer_text = "How can I help you with your claim today?"

    print(f"DEBUG MAIN: ========== Enhanced Final result ==========")
    print(f"DEBUG MAIN: Answer: '{answer_text}'")
    print(f"DEBUG MAIN: Citations: {len(citations)}")
    
    return AIAnswer(answer=answer_text, citations=citations)

async def summarize_claim_for_staff(claim, messages) -> Dict:
    """Enhanced claim summary for staff with validation insights"""
    if not _client:
        return {
            "summary": f"Basic summary: {claim.claim_type} claim with status {claim.status}",
            "risk_score": 0.5,
            "facts": {"claim_type": claim.claim_type, "status": claim.status}
        }
    
    prompt = f"""
You are an insurance staff assistant. Provide a comprehensive claim summary including validation insights.

Claim Details:
- Number: {claim.claim_number}
- Type: {claim.claim_type}
- Status: {claim.status}
- Description: {claim.incident_description or 'N/A'}

Recent Messages:
{chr(10).join(f"- {m.role}: {m.message}" for m in messages[-8:])}

Analyze for:
- Completeness of documentation
- Potential red flags or inconsistencies  
- Risk factors (fraud indicators, unusual patterns)
- Customer communication quality
- Next recommended actions

Return JSON with: summary, risk_score (0-1), facts, recommendations, validation_insights.
"""
    
    try:
        resp = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.1
        )
        
        result = json.loads(resp.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"Enhanced AI summary error: {e}")
        return {
            "summary": f"Enhanced summary generation failed. Claim type: {claim.claim_type}, Status: {claim.status}",
            "risk_score": 0.5,
            "facts": {"error": str(e), "claim_type": claim.claim_type},
            "recommendations": ["Manual review recommended due to AI processing error"],
            "validation_insights": ["Unable to generate automated insights"]
        }