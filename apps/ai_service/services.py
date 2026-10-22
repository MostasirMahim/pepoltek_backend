"""
ai_service/services.py
Provider-agnostic AI adapter with automatic failover across multiple AI providers.
Wraps Gemini, Groq, DeepSeek, Qwen, OpenAI, Anthropic, Ollama, and Local NLP fallback.
Called only from Celery tasks or domain services - never directly from public views.

AI Principle: AI is decision support, never autonomous.
All outputs are stored as suggestions and require human review before application.
"""
import logging
import time
import re
from django.conf import settings

from .manager import ai_manager

logger = logging.getLogger(__name__)

PARSE_RESUME_PROMPT_VERSION = "v2.0-multi-provider"


def parse_resume(*, raw_text: str, document_id: str) -> dict:
    """
    Send extracted resume text through the ranked AI provider failover chain.
    Returns: { output: dict, confidence: dict, model: str, provider: str, prompt_version: str }
    Contact PII is sanitized before external transmission (data minimization).
    """
    sanitized = _redact_pii_for_llm(raw_text)
    prompt = _build_parse_prompt(sanitized)
    start = time.time()

    try:
        raw_output, provider_used, model_used, latency = ai_manager.execute_json_with_failover(
            system_prompt=_RESUME_SYSTEM_PROMPT,
            user_prompt=prompt,
            timeout=getattr(settings, "AI_REQUEST_TIMEOUT", 30),
        )
        total_time = time.time() - start
        logger.info(
            "AI parse complete document=%s provider=%s model=%s latency=%.2fs (total=%.2fs)",
            document_id,
            provider_used,
            model_used,
            latency,
            total_time,
        )

        output, confidence = _validate_parse_output(raw_output)
        return {
            "output": output,
            "confidence": confidence,
            "model": f"{provider_used}:{model_used}",
            "provider": provider_used,
            "prompt_version": PARSE_RESUME_PROMPT_VERSION,
            "latency": latency,
        }
    except Exception as exc:
        total_time = time.time() - start
        logger.error("AI parse failed document=%s latency=%.2fs error=%s", document_id, total_time, exc)
        raise


def nl_query_to_filter(query: str) -> dict:
    """
    Convert a natural-language recruiter search query into a structured filter JSON.
    The filter is validated server-side and shown as editable chips in the UI.
    """
    prompt = f"Convert this search query to a structured filter JSON:\n\n{query}"
    try:
        result, provider_used, model_used, latency = ai_manager.execute_json_with_failover(
            system_prompt=_NL_SEARCH_SYSTEM_PROMPT,
            user_prompt=prompt,
            timeout=15,
        )
        logger.info("NL search converted via %s (%s) in %.2fs", provider_used, model_used, latency)
        return result
    except Exception as exc:
        logger.error("NL search failed: %s", exc)
        return {}


def generate_candidate_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding for a candidate profile or requisition description.
    Protected attributes (age, gender, religion, nationality) must NOT be in text.
    Fails over from cloud providers to local hash embeddings.
    """
    try:
        emb, provider_used = ai_manager.execute_embedding_with_failover(text)
        logger.info("Embedding generated via %s (dims=%d)", provider_used, len(emb))
        return emb
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc)
        # Final emergency zero-vector fallback
        return [0.0] * 1536


def get_ai_status() -> dict:
    """Returns real-time health and status of all configured AI providers."""
    return ai_manager.get_status_report()


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _redact_pii_for_llm(text: str) -> str:
    """
    Best-effort regex redaction of obvious PII before sending to external LLM.
    Server-side parsed fields are the authoritative source.
    """
    # Phone numbers
    text = re.sub(r"\b(\+?[\d\s\-().]{7,15})\b", "[PHONE]", text)
    # Email addresses
    text = re.sub(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text)
    return text


def _build_parse_prompt(text: str) -> str:
    return f"""Extract structured information from the following resume text.

<resume>
{text[:15000]}
</resume>

Return valid JSON matching the schema exactly. Use null for fields not present in the text.
Do not infer attributes like age, gender, nationality, or religion - leave them null."""


def _validate_parse_output(raw: dict) -> tuple[dict, dict]:
    """Validates and sanitizes AI output. Returns (cleaned_output, confidence_map)."""
    required_keys = ["contact", "titles", "skills", "education", "summary"]
    output = {k: raw.get(k) for k in required_keys}
    confidence = raw.get("_confidence", {})
    if not isinstance(confidence, dict):
        confidence = {}
    for key in required_keys:
        confidence.setdefault(key, 0.6)
    return output, confidence


_RESUME_SYSTEM_PROMPT = """You are a structured data extraction specialist.
Extract ONLY information explicitly present in the resume text.
Return strict JSON. Never infer age, gender, nationality, religion, or photo.
Use null for absent fields. Add a "_confidence" object with float values 0.0-1.0 per field."""

_NL_SEARCH_SYSTEM_PROMPT = """Convert recruiter search queries to JSON filter objects.
Return ONLY valid JSON. Example output:
{"skills": [{"name": "Python", "min_years": 3}], "level": "senior", "engagement": ["C2C"]}
Stick to these filter keys: skills, level, sector, engagement, work_auth, location, timezone."""
