from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Environment
    app_env: str = "development"
    payback_env: str = "development"
    log_level: str = "INFO"

    # Supabase (free tier / development) — optional in Phase 2
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""

    # Razorpay (TEST MODE ONLY)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Hugging Face (free/low-cost model only)
    huggingface_api_key: str = ""
    huggingface_model: str = "mistralai/Mistral-7B-Instruct-v0.2"

    def is_razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    def validate_razorpay_test_mode(self) -> bool:
        """
        Hard safety check: Enforce Razorpay Test Mode only.
        Live keys (rzp_live_) are strictly rejected to guarantee ZERO COST.
        """
        if not self.razorpay_key_id:
            return False
        if self.razorpay_key_id.startswith("rzp_live_"):
            raise ValueError(
                "LIVE Razorpay key detected! Live Mode is strictly forbidden. "
                "Only Test Mode keys beginning with 'rzp_test_' are permitted."
            )
        if not self.razorpay_key_id.startswith("rzp_test_"):
            raise ValueError(
                f"Invalid Razorpay key prefix '{self.razorpay_key_id[:8]}...'. "
                "Keys must start with 'rzp_test_' for Test Mode."
            )
        return True

    @property
    def razorpay_mode(self) -> str:
        if not self.razorpay_key_id:
            return "UNCONFIGURED"
        if self.razorpay_key_id.startswith("rzp_test_"):
            return "TEST"
        return "INVALID"


settings = Settings()
