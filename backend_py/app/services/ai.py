from __future__ import annotations
import os
from datetime import datetime
from typing import Any, List
from openai import AsyncOpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_client: AsyncOpenAI | None = None
if OPENAI_API_KEY:
    _client = AsyncOpenAI(api_key=OPENAI_API_KEY)

def _fmt_dt(dt: Any) -> str | None:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    try:
        return str(dt)
    except Exception:
        return None

async def generate_ai_reply_rag(claim, user_text: str, context_chunks: List[str]) -> str:
    """
    Call OpenAI Chat Completions and return the assistant text, using RAG context.
    Expects a SQLAlchemy `claim` ORM object and a list of context strings.
    """
    if _client is None:
        raise RuntimeError(
            "OPENAI_API_KEY is not set in backend environment; cannot call OpenAI."
        )

    claim_number = getattr(claim, "claim_number", None) or f"#{getattr(claim, 'id', 'N/A')}"
    claim_type = getattr(claim, "claim_type", None) or "claim"
    status = getattr(claim, "status", None) or "submitted"
    created = _fmt_dt(getattr(claim, "created_at", None))
    desc = getattr(claim, "incident_description", None) or ""

    system_prompt = (
        "You are a helpful, concise insurance claims assistant. "
        "Use the provided context from policy documents to answer the user's question. "
        "Answer in plain English; keep replies short (2–5 sentences) unless the user asks for detail. "
        "If the user asks for status/next steps, be clear and actionable. "
        "Never invent policy information. If something is unknown, say what you *can* do next.\n\n"
        f"Claim context:\n"
        f"- Claim number: {claim_number}\n"
        f"- Claim type: {claim_type}\n"
        f"- Status: {status}\n"
        f"- Created: {created or 'unknown'}\n"
        f"- Incident description: {desc or 'n/a'}\n\n"
        "Relevant policy/document context:\n"
        + "\n---\n".join(context_chunks)
    )

    resp = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        max_tokens=400,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    return (resp.choices[0].message.content or "").strip()