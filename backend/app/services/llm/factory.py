from typing import Optional
from backend.app.config import Settings, get_settings
from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.exceptions import LLMConfigurationError
from backend.app.services.llm.gemini import GeminiProvider


def get_llm_provider(settings: Optional[Settings] = None) -> LLMProvider:
    """
    Factory function to instantiate the configured LLMProvider.
    Allows easy switching between providers (Gemini, OpenAI) via environment settings.
    """
    cfg = settings or get_settings()
    provider_name = (cfg.LLM_PROVIDER or "").lower().strip()

    if provider_name == "gemini":
        return GeminiProvider(
            api_key=cfg.GEMINI_API_KEY,
            model=cfg.GEMINI_MODEL,
            timeout_seconds=cfg.LLM_TIMEOUT_SECONDS,
        )
    elif provider_name == "openai":
        raise LLMConfigurationError(
            "OpenAI provider is not yet configured. Please set LLM_PROVIDER=gemini."
        )
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{cfg.LLM_PROVIDER}'. Supported providers: 'gemini', 'openai'."
        )
