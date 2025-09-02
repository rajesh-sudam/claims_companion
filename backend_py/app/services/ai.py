from __future__ import annotations
import os
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Dict, Optional, Union
from openai import AsyncOpenAI, OpenAI
from typing import Dict


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

async def summarize_claim_for_staff(claim, messages) -> Dict:
    """
    Returns dict with fields: summary (str), risk_score (0..1), facts (dict).
    Uses your existing OpenAI client.
    """
    if not _client:
        # Fallback if no OpenAI client available
        return {
            "summary": f"Basic summary: {claim.claim_type} claim with status {claim.status}",
            "risk_score": 0.5,
            "facts": {"claim_type": claim.claim_type, "status": claim.status}
        }
    
    # Minimal, deterministic-ish prompt:
    prompt = f"""
You are an insurance intake assistant for staff. Summarize the claim succinctly,
list key facts, and estimate a risk score 0..1 (1 = likely fraud/deny, 0 = very safe).
Claim:
- Number: {claim.claim_number}
- Type: {claim.claim_type}
- Status: {claim.status}
- Description: {claim.incident_description or 'N/A'}

Recent user messages (latest last):
{chr(10).join(f"- {m.role}: {m.message}" for m in messages[-8:])}

Return JSON with keys: summary, risk_score, facts.
"""
    
    try:
        resp = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300,
            temperature=0.1
        )
        
        import json
        result = json.loads(resp.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"AI summary error: {e}")
        return {
            "summary": f"Error generating AI summary. Claim type: {claim.claim_type}, Status: {claim.status}",
            "risk_score": 0.5,
            "facts": {"error": str(e), "claim_type": claim.claim_type}
        }

def summarize_claim(claim_type: str, description: str, status: str) -> str:
    # super lightweight fallback summary (replace with real OpenAI call if you prefer)
    return (
        f"Claim type: {claim_type}. Status: {status}. "
        f"User reported: {description[:400]}{'...' if len(description) > 400 else ''}"
    )

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
    """
    Ensure each context chunk has: id, text, doc_id, chunk_id, score.
    Accepts either raw strings or dicts from your RAG service.
    """
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


def _build_system_prompt(claim: Any, norm_context: List[Dict[str, Any]]) -> str:
    print(f"DEBUG PROMPT: Building system prompt with {len(norm_context)} context chunks")
    
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
    print(f"DEBUG PROMPT: Final context string length: {len(context_str)}")

    prompt = (
        "You are a helpful insurance claims assistant for NovaWorks insurance.\n\n"
        
        "INSTRUCTIONS:\n"
        "- Answer questions about the user's specific claim using the CLAIM INFORMATION below\n"
        "- Answer policy questions using the POLICY CONTEXT below\n"
        "- For greetings: Respond warmly as their claims assistant\n"
        "- For unrelated questions: Politely redirect to claim/policy topics\n"
        "- Be helpful and concise\n\n"
        
        f"CLAIM INFORMATION (use this to answer questions about their claim):\n"
        f"- Claim number: {claim_number}\n"
        f"- Claim type: {claim_type}\n"
        f"- Status: {status}\n"
        f"- Created: {created or 'unknown'}\n"
        f"- Incident description: {desc or 'n/a'}\n\n"
        
        "POLICY CONTEXT (use this to answer coverage/policy questions):\n"
        f"{context_str}\n\n"
        
        "EXAMPLES:\n"
        "- 'What is my claim number?' → Answer: 'Your claim number is {claim_number}'\n"
        "- 'Hi' → Answer: 'Hello! I'm your NovaWorks claims assistant. How can I help with your claim today?'\n"
        "- 'What's covered?' → Use the policy context to explain coverage\n\n"
        
        "RESPONSE FORMAT - Always respond with valid JSON:\n"
        "{\n"
        '  "answer": "your response here",\n'
        '  "citations": [{"id": "context-id"}] // only for policy context answers\n'
        "}"
    )
    
    print(f"DEBUG PROMPT: Final system prompt length: {len(prompt)}")
    return prompt


async def generate_ai_reply_rag(
    claim: Any,
    user_text: str,
    context_chunks: List[Union[str, Dict[str, Any]]]
) -> AIAnswer:
    """
    Call OpenAI with RAG grounding and return a structured AIAnswer.
    - If OPENAI_API_KEY is missing, returns a deterministic fallback.
    - Ensures the model answers from context and returns machine-readable citations.
    """
    print(f"DEBUG MAIN: ========== Starting AI generation ==========")
    print(f"DEBUG MAIN: User query: '{user_text}'")
    print(f"DEBUG MAIN: Client initialized: {_client is not None}")
    print(f"DEBUG MAIN: Raw context chunks received: {len(context_chunks)}")
    
    if context_chunks:
        for i, chunk in enumerate(context_chunks[:3]):  # Show first 3
            chunk_preview = str(chunk)[:150] + "..." if len(str(chunk)) > 150 else str(chunk)
            print(f"DEBUG MAIN: Chunk {i}: {chunk_preview}")
    else:
        print("DEBUG MAIN: NO CONTEXT CHUNKS PROVIDED")
    
    norm_context = _normalize_context(context_chunks)
    print(f"DEBUG MAIN: Normalized context chunks: {len(norm_context)}")

    # Fallback if API is unavailable
    if _client is None:
        print("DEBUG MAIN: OpenAI client is None - using fallback")
        fallback = "I cannot find this in the policy context."
        cits = []
        # naive heuristic: if we have context, include first two ids
        for c in norm_context[:2]:
            cits.append(AICitation(id=c["id"], doc_id=c.get("doc_id"), chunk_id=c.get("chunk_id"), score=c.get("score")))
        print(f"DEBUG MAIN: Fallback response with {len(cits)} citations")
        return AIAnswer(answer=fallback, citations=cits)

    system_prompt = _build_system_prompt(claim, norm_context)

    try:
        print("DEBUG MAIN: Making OpenAI API call...")
        print(f"DEBUG MAIN: Model: {OPENAI_MODEL}")
        print(f"DEBUG MAIN: User message: '{user_text}'")
        
        resp = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.1,
            max_tokens=450,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format={"type": "json_object"},
        )

        raw = (resp.choices[0].message.content or "").strip()
        print(f"DEBUG MAIN: OpenAI raw response: '{raw}'")
        
        answer_text = ""
        citations: List[AICitation] = []
 
        # Parse JSON strictly; if it fails, fallback gracefully
        try:
            print("DEBUG MAIN: Parsing JSON response...")
            data = json.loads(raw)
            print(f"DEBUG MAIN: Parsed JSON keys: {list(data.keys())}")
            
            answer_text = str(data.get("answer", "")).strip()
            print(f"DEBUG MAIN: Extracted answer: '{answer_text}'")
            
            raw_citations = data.get("citations") or []
            print(f"DEBUG MAIN: Raw citations: {raw_citations}")
            
            cit_ids = [str(c.get("id")) for c in raw_citations if isinstance(c, dict) and c.get("id")]
            print(f"DEBUG MAIN: Citation IDs: {cit_ids}")
            
            # Map back to our rich context to attach doc/chunk/score
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
            # If the model didn't return JSON as requested, just pass through text
            answer_text = raw or "I cannot find this in the policy context."
            for c in norm_context[:2]:
                citations.append(AICitation(
                    id=c["id"],
                    doc_id=c.get("doc_id"),
                    chunk_id=c.get("chunk_id"),
                    score=c.get("score"),
                    snippet=(c.get("text") or "")[:240]
                ))
            print(f"DEBUG MAIN: Using fallback parsing with {len(citations)} citations")

    except Exception as e:
        print(f"DEBUG MAIN: OpenAI API call failed: {type(e).__name__}: {e}")
        print(f"DEBUG MAIN: Using error fallback")
        # If the model didn't return JSON as requested, just pass through text
        answer_text = "I cannot find this in the policy context."
        for c in norm_context[:2]:
            citations.append(AICitation(
                id=c["id"],
                doc_id=c.get("doc_id"),
                chunk_id=c.get("chunk_id"),
                score=c.get("score"),
                snippet=(c.get("text") or "")[:240]
            ))

    # Final guardrail
    if not answer_text.strip():
        print("DEBUG MAIN: Empty answer, using final fallback")
        answer_text = "I cannot find this in the policy context."

    print(f"DEBUG MAIN: ========== Final result ==========")
    print(f"DEBUG MAIN: Answer: '{answer_text}'")
    print(f"DEBUG MAIN: Citations: {len(citations)}")
    for i, cit in enumerate(citations):
        print(f"DEBUG MAIN: Citation {i}: id={cit.id}, doc_id={cit.doc_id}, score={cit.score}")

    return AIAnswer(answer=answer_text, citations=citations)