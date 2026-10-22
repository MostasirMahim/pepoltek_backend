"""
ai_service/manager.py
Central AI Provider Manager with automatic key detection, prioritized ranking, and failover circuit.
"""
import os
import time
import logging
from typing import Optional, Any
from django.conf import settings

from .providers import (
    BaseAIProvider,
    GeminiProvider,
    GroqProvider,
    DeepSeekProvider,
    QwenProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    LocalNLPProvider,
    is_valid_key,
)

logger = logging.getLogger(__name__)

DEFAULT_PRIORITY_ORDER = [
    "gemini",
    "groq",
    "deepseek",
    "qwen",
    "openai",
    "anthropic",
    "ollama",
    "local_nlp",
]


class AIProviderManager:
    def __init__(self):
        self._providers: dict[str, BaseAIProvider] = {}
        self.reload_providers()

    def reload_providers(self):
        """Instantiate providers with current environment/settings keys."""
        gemini_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        groq_key = getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
        deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", None) or os.getenv("DEEPSEEK_API_KEY")
        qwen_key = getattr(settings, "QWEN_API_KEY", None) or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        openai_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.getenv("ANTHROPIC_API_KEY")
        ollama_url = getattr(settings, "OLLAMA_BASE_URL", None) or os.getenv("OLLAMA_BASE_URL")

        self._providers = {
            "gemini": GeminiProvider(api_key=gemini_key),
            "groq": GroqProvider(api_key=groq_key),
            "deepseek": DeepSeekProvider(api_key=deepseek_key),
            "qwen": QwenProvider(api_key=qwen_key),
            "openai": OpenAIProvider(api_key=openai_key),
            "anthropic": AnthropicProvider(api_key=anthropic_key),
            "ollama": OllamaProvider(base_url=ollama_url),
            "local_nlp": LocalNLPProvider(),
        }

    def get_ranked_providers(self) -> list[BaseAIProvider]:
        """
        Calculates the active failover order based on:
        1. Configured priority list in settings.AI_PROVIDER_PRIORITY
        2. Preferred provider in settings.AI_PROVIDER (if not 'auto')
        3. Active API keys / availability check
        4. Guaranteed local_nlp fallback at the end
        """
        priority_setting = getattr(settings, "AI_PROVIDER_PRIORITY", None) or os.getenv("AI_PROVIDER_PRIORITY", "")
        if isinstance(priority_setting, str) and priority_setting.strip():
            priority_list = [p.strip().lower() for p in priority_setting.split(",") if p.strip()]
        else:
            priority_list = list(DEFAULT_PRIORITY_ORDER)

        # Ensure all known providers are in the list
        for p_name in DEFAULT_PRIORITY_ORDER:
            if p_name not in priority_list:
                priority_list.append(p_name)

        # If a single primary AI_PROVIDER is explicitly selected (and not 'auto'), promote it to rank 1
        preferred = getattr(settings, "AI_PROVIDER", None) or os.getenv("AI_PROVIDER", "auto")
        preferred = preferred.lower().strip()
        if preferred and preferred != "auto" and preferred in priority_list:
            priority_list.remove(preferred)
            priority_list.insert(0, preferred)

        # Filter to providers that are currently available (have keys or are local)
        active_chain: list[BaseAIProvider] = []
        for name in priority_list:
            provider = self._providers.get(name)
            if provider and provider.is_available():
                active_chain.append(provider)

        # Guarantee local_nlp is present as the ultimate safety net
        local_provider = self._providers["local_nlp"]
        if local_provider not in active_chain:
            active_chain.append(local_provider)

        return active_chain

    def execute_json_with_failover(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: int = 30,
    ) -> tuple[dict, str, str, float]:
        """
        Executes a JSON generation request across ranked providers.
        Fails over on rate limits (429), server errors (503), timeouts, or exceptions.
        Returns: (parsed_json, provider_name, model_name, latency_seconds)
        """
        chain = self.get_ranked_providers()
        errors = []

        for provider in chain:
            start_time = time.time()
            try:
                data, model_used = provider.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    timeout=timeout,
                )
                latency = time.time() - start_time
                logger.info(
                    "[AI Manager] Success via provider='%s' model='%s' in %.2fs",
                    provider.name,
                    model_used,
                    latency,
                )
                return data, provider.name, model_used, latency
            except Exception as exc:
                latency = time.time() - start_time
                error_desc = f"{provider.name} failed in {latency:.2f}s: {exc}"
                logger.warning("[AI Failover] %s. Failing over to next candidate in queue...", error_desc)
                errors.append(error_desc)
                continue

        # If everything somehow failed, force local_nlp
        logger.error("[AI Manager] All providers failed. Forcing local NLP fallback. Errors: %s", errors)
        start_time = time.time()
        local_data, local_model = self._providers["local_nlp"].generate_json(system_prompt, user_prompt, timeout=5)
        latency = time.time() - start_time
        return local_data, "local_nlp", local_model, latency

    def execute_embedding_with_failover(self, text: str, timeout: int = 15) -> tuple[list[float], str]:
        """
        Generates 1536-dimensional embeddings with failover.
        Returns: (embedding_vector, provider_name)
        """
        chain = self.get_ranked_providers()
        for provider in chain:
            try:
                emb = provider.generate_embedding(text=text, timeout=timeout)
                if emb and any(v != 0.0 for v in emb):
                    return emb, provider.name
            except Exception as exc:
                logger.warning("[AI Failover] Embedding failed on %s: %s", provider.name, exc)
                continue

        # Final local hash embedding fallback
        return self._providers["local_nlp"].generate_embedding(text), "local_nlp"

    def get_status_report(self) -> dict:
        """Detailed status report of all providers and failover priority."""
        chain = self.get_ranked_providers()
        active_names = [p.name for p in chain]

        report = []
        for idx, p_name in enumerate(DEFAULT_PRIORITY_ORDER):
            provider = self._providers.get(p_name)
            is_avail = provider.is_available() if provider else False
            is_active = p_name in active_names
            rank = active_names.index(p_name) + 1 if is_active else None

            # Masked key preview
            key_preview = "N/A"
            if hasattr(provider, "api_key") and provider.api_key:
                k = provider.api_key
                if is_valid_key(k):
                    key_preview = f"{k[:8]}...{k[-5:]}" if len(k) > 15 else "***"
                else:
                    key_preview = "(invalid/dummy key)"
            elif p_name == "ollama":
                key_preview = getattr(provider, "base_url", "local")
            elif p_name == "local_nlp":
                key_preview = "(built-in python engine)"

            report.append({
                "provider": p_name,
                "configured": is_avail,
                "active_in_failover": is_active,
                "rank": rank,
                "key_preview": key_preview,
            })

        return {
            "current_mode": getattr(settings, "AI_PROVIDER", "auto"),
            "primary_active_provider": active_names[0] if active_names else "local_nlp",
            "active_failover_chain": active_names,
            "providers": report,
        }


# Global singleton instance
ai_manager = AIProviderManager()
