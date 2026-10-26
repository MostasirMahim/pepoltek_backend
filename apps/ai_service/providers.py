"""
ai_service/providers.py
Modular provider implementations for Gemini, Groq, DeepSeek, Qwen, OpenAI, Anthropic, Ollama, and Local NLP.
"""
import os
import re
import json
import time
import logging
import urllib.request
import urllib.error
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Dummy/placeholder keys that should be treated as not configured
DUMMY_KEY_PATTERNS = ("sk-change-me", "sk-ant-change-me", "change-me", "your-", "xxx", "test-key")


def is_valid_key(key: Optional[str]) -> bool:
    if not key or not isinstance(key, str):
        return False
    clean = key.strip()
    if len(clean) < 8:
        return False
    if any(pat in clean.lower() for pat in DUMMY_KEY_PATTERNS):
        return False
    return True


def _create_openai_client(api_key: str, base_url: Optional[str] = None, timeout: int = 30):
    """Safely instantiates an OpenAI client with an explicit httpx.Client to prevent proxies keyword incompatibility in httpx 0.28+."""
    import httpx
    import openai
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": timeout,
        "http_client": httpx.Client(timeout=timeout),
    }
    if base_url:
        kwargs["base_url"] = base_url
    return openai.OpenAI(**kwargs)


class BaseAIProvider:
    name: str = "base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        """
        Returns: (parsed_json_dict, model_name_used)
        """
        raise NotImplementedError

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        raise NotImplementedError

    def health_check(self) -> dict:
        return {
            "name": self.name,
            "available": self.is_available(),
            "status": "ready" if self.is_available() else "missing_key",
        }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Google Gemini Provider (Free Tier Available)
# ─────────────────────────────────────────────────────────────────────────────
class GeminiProvider(BaseAIProvider):
    name = "gemini"

    # Candidate models to try in descending order of preference
    CANDIDATE_MODELS = [
        "gemini-3-flash-preview",
        "gemini-3.8-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-pro-latest",
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()

    def is_available(self) -> bool:
        return is_valid_key(self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        if not self.is_available():
            raise ValueError("Gemini API key is not configured or invalid.")

        last_error = None
        for model in self.CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER REQUEST:\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                },
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    text_content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    cleaned = text_content.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]
                    if cleaned.startswith("```"):
                        cleaned = cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    return json.loads(cleaned.strip()), model
            except urllib.error.HTTPError as he:
                error_body = he.read().decode("utf-8", errors="ignore")
                logger.warning("Gemini model '%s' failed (HTTP %s): %s", model, he.code, error_body[:120])
                last_error = he
                continue
            except Exception as e:
                logger.warning("Gemini model '%s' exception: %s", model, e)
                last_error = e
                continue

        raise RuntimeError(f"All Gemini models exhausted. Last error: {last_error}")

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        if not self.is_available():
            raise ValueError("Gemini API key is not configured.")

        # text-embedding-004
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={self.api_key}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": text[:2048]}]},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                values = data.get("embedding", {}).get("values", [])
                if values:
                    if len(values) < 1536:
                        return values + [0.0] * (1536 - len(values))
                    return values[:1536]
        except Exception as e:
            logger.warning("Gemini embedding failed: %s", e)
        return [0.0] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# 2. Groq Cloud Provider (OpenAI SDK Compatible, Ultra Fast Free Tier)
# ─────────────────────────────────────────────────────────────────────────────
class GroqProvider(BaseAIProvider):
    name = "groq"
    CANDIDATE_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()

    def is_available(self) -> bool:
        return is_valid_key(self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        if not self.is_available():
            raise ValueError("Groq API key not configured.")

        client = _create_openai_client(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=timeout,
        )

        last_error = None
        for model in self.CANDIDATE_MODELS:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt + "\nRespond with valid JSON only."},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                raw = resp.choices[0].message.content
                return json.loads(raw), model
            except Exception as e:
                logger.warning("Groq model %s failed: %s", model, e)
                last_error = e
                continue

        raise RuntimeError(f"All Groq models exhausted. Last error: {last_error}")

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        return [0.0] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# 3. DeepSeek Provider (OpenAI SDK Compatible)
# ─────────────────────────────────────────────────────────────────────────────
class DeepSeekProvider(BaseAIProvider):
    name = "deepseek"
    CANDIDATE_MODELS = ["deepseek-chat"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("DEEPSEEK_API_KEY", "")).strip()

    def is_available(self) -> bool:
        return is_valid_key(self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        if not self.is_available():
            raise ValueError("DeepSeek API key not configured.")

        client = _create_openai_client(
            api_key=self.api_key,
            base_url="https://api.deepseek.com",
            timeout=timeout,
        )

        model = self.CANDIDATE_MODELS[0]
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt + "\nReturn valid JSON only."},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content), model

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        return [0.0] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# 4. Qwen Provider (Alibaba DashScope / OpenAI SDK Compatible)
# ─────────────────────────────────────────────────────────────────────────────
class QwenProvider(BaseAIProvider):
    name = "qwen"
    CANDIDATE_MODELS = ["qwen-plus", "qwen-turbo"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")).strip()

    def is_available(self) -> bool:
        return is_valid_key(self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        if not self.is_available():
            raise ValueError("Qwen / DashScope API key not configured.")

        client = _create_openai_client(
            api_key=self.api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            timeout=timeout,
        )

        for model in self.CANDIDATE_MODELS:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt + "\nReturn strict JSON."},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                return json.loads(resp.choices[0].message.content), model
            except Exception as e:
                logger.warning("Qwen model %s failed: %s", model, e)
                continue

        raise RuntimeError("Qwen generation failed across candidate models.")

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        return [0.0] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# 5. OpenAI Provider (GPT-4o-mini / text-embedding-3-small)
# ─────────────────────────────────────────────────────────────────────────────
class OpenAIProvider(BaseAIProvider):
    name = "openai"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()

    def is_available(self) -> bool:
        return is_valid_key(self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        if not self.is_available():
            raise ValueError("OpenAI API key not configured.")

        client = _create_openai_client(api_key=self.api_key, timeout=timeout)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content), "gpt-4o-mini"

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        if not self.is_available():
            return [0.0] * 1536

        import openai

        client = openai.OpenAI(api_key=self.api_key, timeout=timeout)
        resp = client.embeddings.create(model="text-embedding-3-small", input=text[:4000])
        return resp.data[0].embedding


# ─────────────────────────────────────────────────────────────────────────────
# 6. Anthropic Provider (Claude 3 Haiku)
# ─────────────────────────────────────────────────────────────────────────────
class AnthropicProvider(BaseAIProvider):
    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("ANTHROPIC_API_KEY", "")).strip()

    def is_available(self) -> bool:
        return is_valid_key(self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        if not self.is_available():
            raise ValueError("Anthropic API key not configured.")

        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key, timeout=timeout)
        msg = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = msg.content[0].text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip()), "claude-3-haiku-20240307"

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        return [0.0] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# 7. Ollama Provider (Local Offline LLM)
# ─────────────────────────────────────────────────────────────────────────────
class OllamaProvider(BaseAIProvider):
    name = "ollama"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")).rstrip("/")

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/models")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 30) -> tuple[dict, str]:
        import openai

        client = openai.OpenAI(base_url=self.base_url, api_key="ollama", timeout=timeout)
        resp = client.chat.completions.create(
            model="llama3.2",
            messages=[
                {"role": "system", "content": system_prompt + "\nRespond with valid JSON only."},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content), "ollama-llama3.2"

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        return [0.0] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# 8. Local NLP Provider (100% Free Python Regex & Taxonomy Matching Fallback)
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_SKILLS_TAXONOMY = {
    # Tech skills
    "python", "javascript", "typescript", "react", "next.js", "nextjs", "node", "nodejs",
    "vue", "angular", "go", "golang", "rust", "java", "spring", "c#", ".net", "php",
    "django", "fastapi", "flask", "postgresql", "postgres", "mysql", "mongodb", "redis",
    "kafka", "rabbitmq", "aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform",
    "graphql", "rest", "ci/cd", "git", "linux", "html", "css", "tailwind", "microservices",
    "data engineering", "spark", "airflow", "snowflake", "databricks", "machine learning",
    "ai", "nlp", "llm", "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow",
    # Health & Clinical skills
    "epic", "cerner", "hipaa", "hitech", "clinical trials", "telemedicine", "telehealth",
    "patient intake", "nursing", "ehr", "emr", "hl7", "fhir", "meditech", "allscripts",
    "oncology", "cardiology", "pediatrics", "icu", "bls", "acls", "cpr", "pharmacology",
    "phlebotomy", "vital signs", "triage", "care coordination", "medical billing", "icd-10"
}

ROLE_LEVEL_KEYWORDS = {
    "Lead": ("lead", "principal", "staff", "head", "director", "manager"),
    "Senior": ("senior", "sr", "experienced", "advanced"),
    "Mid": ("mid", "intermediate"),
    "Junior": ("junior", "associate", "entry"),
}


class LocalNLPProvider(BaseAIProvider):
    name = "local_nlp"

    def is_available(self) -> bool:
        return True  # Always available as ground fallback

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 5) -> tuple[dict, str]:
        # Detect if this is an NL query search or a CV parse
        if "recruiter search queries" in system_prompt.lower() or "filter" in user_prompt.lower():
            return self._parse_nl_query(user_prompt), "local-rule-engine"
        return self._parse_resume_text(user_prompt), "local-rule-engine"

    def _parse_resume_text(self, text: str) -> dict:
        text_lower = text.lower()

        # 1. Contact Extraction
        email_match = re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(r"(?:\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)
        phone = phone_match.group(0) if phone_match else None

        # Name heuristic
        name = "Candidate Specialist"
        for line in text.splitlines()[:15]:
            clean_line = line.strip()
            if 3 < len(clean_line) < 40 and not any(h in clean_line.lower() for h in ("resume", "cv", "curriculum", "email", "phone", "http")):
                words = clean_line.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
                    name = clean_line
                    break

        # 2. Skills Extraction via Taxonomy Match
        found_skills = set()
        for skill in KNOWN_SKILLS_TAXONOMY:
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, text_lower):
                found_skills.add(skill.title() if len(skill) > 3 else skill.upper())

        # 3. Titles / Role Detection
        detected_title = "Specialist Professional"
        for title_line in text.splitlines()[:20]:
            tl = title_line.lower()
            if any(k in tl for k in ("engineer", "developer", "architect", "nurse", "physician", "analyst", "manager", "specialist")):
                detected_title = title_line.strip()
                break

        # 4. Education Extraction
        education_list = []
        edu_patterns = [
            (r"(master['’]?s|m\.s\.|msc|mba)\s+(?:in|of)?\s+([A-Za-z\s]+)", "Master's Degree"),
            (r"(bachelor['’]?s|b\.s\.|bsc|ba)\s+(?:in|of)?\s+([A-Za-z\s]+)", "Bachelor's Degree"),
            (r"(ph\.?d\.?|doctorate)\s+(?:in|of)?\s+([A-Za-z\s]+)", "Doctorate"),
        ]
        for pattern, degree_type in edu_patterns:
            m = re.search(pattern, text_lower)
            if m:
                major = m.group(2).strip()[:40].title() if m.lastindex >= 2 else "Field of Study"
                education_list.append({"degree": degree_type, "field": major, "institution": "Accredited University"})

        # Summary
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 60]
        summary = paragraphs[0][:300] if paragraphs else "Experienced specialist with verified technical background."

        return {
            "contact": {
                "name": name,
                "email": email,
                "phone": phone,
            },
            "titles": [detected_title],
            "skills": sorted(list(found_skills))[:20],
            "education": education_list or [{"degree": "Bachelor's Degree", "field": "Relevant Domain"}],
            "summary": summary,
            "_confidence": {
                "contact": 0.85 if email else 0.5,
                "skills": 0.80 if found_skills else 0.4,
                "education": 0.75 if education_list else 0.5,
                "summary": 0.70,
            },
        }

    def _parse_nl_query(self, query: str) -> dict:
        q_lower = query.lower()

        # Extract skills
        skills = []
        for s in KNOWN_SKILLS_TAXONOMY:
            if re.search(r"\b" + re.escape(s) + r"\b", q_lower):
                years_match = re.search(rf"(\d+)\+?\s*(?:years?|yrs?)[^\.,]*{re.escape(s)}|{re.escape(s)}[^\.,]*(\d+)\+?\s*(?:years?|yrs?)", q_lower)
                min_years = 1
                if years_match:
                    found_val = years_match.group(1) or years_match.group(2)
                    min_years = int(found_val)
                skills.append({"name": s.title() if len(s) > 3 else s.upper(), "min_years": min_years})

        # Level
        level = "all"
        for l_name, keywords in ROLE_LEVEL_KEYWORDS.items():
            if any(k in q_lower for k in keywords):
                level = l_name
                break

        # Engagement
        engagement = []
        if "c2c" in q_lower or "corp-to-corp" in q_lower:
            engagement.append("C2C")
        if "w2" in q_lower:
            engagement.append("W2")
        if "1099" in q_lower or "contract" in q_lower:
            engagement.append("1099")
        if "full-time" in q_lower or "direct hire" in q_lower:
            engagement.append("Direct Hire")

        # Sector
        sector = "all"
        if any(h in q_lower for h in ("health", "clinic", "nurse", "medical", "hospital", "patient")):
            sector = "healthcare"
        elif any(t in q_lower for t in ("tech", "software", "code", "engineer", "react", "python")):
            sector = "technology"

        return {
            "skills": skills,
            "level": level,
            "sector": sector,
            "engagement": engagement or ["all"],
            "location": "Remote" if "remote" in q_lower else "all",
        }

    def generate_embedding(self, text: str, timeout: int = 15) -> list[float]:
        import hashlib
        import math

        vector = [0.0] * 1536
        words = text.lower().split()
        for idx, w in enumerate(words):
            slot = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % 1536
            vector[slot] += 1.0 / (idx + 1.0)

        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [round(v / norm, 6) for v in vector]
