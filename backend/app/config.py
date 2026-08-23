from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database — not required in Phase 1
    database_url: str = ""

    # Hugging Face — not required in Phase 1
    huggingface_api_key: str = ""
    huggingface_model: str = "mistralai/Mistral-7B-Instruct-v0.2"

    # Razorpay — not required in Phase 1
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # App
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
