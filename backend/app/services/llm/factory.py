from __future__ import annotations

from typing import Optional
from app.config import Settings, settings
from app.services.llm.interface import MessageGenerator
from app.services.llm.mock import MockMessageGenerator
from app.services.llm.ollama import OllamaMessageGenerator
from app.services.llm.huggingface import HuggingFaceMessageGenerator


def get_message_generator(app_settings: Optional[Settings] = None) -> MessageGenerator:
    """
    Returns the appropriate MessageGenerator instance based on application configuration.
    Priority:
      1. 'mock' -> MockMessageGenerator (for tests/offline)
      2. 'ollama' -> OllamaMessageGenerator (local development)
      3. 'huggingface' -> HuggingFaceMessageGenerator (cloud deployment)
    """
    cfg = app_settings or settings
    provider = (getattr(cfg, "llm_provider", "") or "ollama").lower()

    if provider == "mock":
        return MockMessageGenerator()
    elif provider == "huggingface":
        return HuggingFaceMessageGenerator(
            api_key=cfg.huggingface_api_key,
            model_name=cfg.huggingface_model,
        )
    elif provider == "ollama":
        return OllamaMessageGenerator(
            base_url=cfg.ollama_base_url,
            model_name=cfg.ollama_model,
        )
    else:
        return MockMessageGenerator()
