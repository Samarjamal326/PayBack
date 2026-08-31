from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    app_env: str = "development"
    payback_env: str = "development"
    database_mode: str = "memory"
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

    # LLM Provider: "ollama" | "huggingface" | "mock"
    llm_provider: str = "ollama"

    # Ollama (Local development default)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # Hugging Face (free/low-cost model only)
    huggingface_api_key: str = ""
    huggingface_model: str = "mistralai/Mistral-7B-Instruct-v0.2"

    # Authentication & Tenant Security
    # In test/dev mode without Supabase Auth or JWT secret, defaults gracefully
    auth_enabled: bool = False
    jwt_secret_key: str = "payback-dev-secret-key-change-in-production-1234567890"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours

    # Messaging Delivery Providers
    # 'mock' | 'resend' | 'smtp' | 'whatsapp'
    message_delivery_provider: str = "resend"
    
    # Resend Email Configuration
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"
    
    # SMTP Email Configuration (fallback)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "recovery@payback.ai"
    
    # WhatsApp Configuration
    whatsapp_api_url: str = ""
    whatsapp_api_token: str = ""
    whatsapp_from_phone: str = ""

    # CORS Configuration
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://payback.vercel.app",
        "https://inspiring-cranachan-9c8d4a.netlify.app",
    ]

    # Background Execution
    # 'in_memory' | 'sync'
    background_executor_type: str = "in_memory"
    background_max_workers: int = 4

    # Cloudflare Tunnel (for Razorpay webhooks in development)
    cloudflare_tunnel_id: str = ""
    cloudflare_tunnel_hostname: str = "api.payback.local"

    def is_razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    def is_supabase_configured(self) -> bool:
        return bool(self.supabase_url and (self.supabase_service_role_key or self.supabase_anon_key))

    def is_smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    def is_whatsapp_configured(self) -> bool:
        return bool(self.whatsapp_api_url and self.whatsapp_api_token)

    def is_resend_configured(self) -> bool:
        return bool(self.resend_api_key)

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

    @property
    def webhook_url(self) -> str:
        """Returns the webhook URL for Razorpay configuration."""
        if self.cloudflare_tunnel_hostname:
            return f"https://{self.cloudflare_tunnel_hostname}/api/v1/events/webhook/razorpay"
        # Fallback to localhost for development
        return "http://localhost:8000/api/v1/events/webhook/razorpay"


settings = Settings()

