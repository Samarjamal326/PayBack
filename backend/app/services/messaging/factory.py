from __future__ import annotations

from typing import Optional

from app.config import Settings, settings
from app.services.messaging.email_provider import EmailDeliveryProvider
from app.services.messaging.interfaces import DeliveryProviderAdapter
from app.services.messaging.mock import MockDeliveryProvider
from app.services.messaging.whatsapp_provider import WhatsAppDeliveryProvider


def get_delivery_provider(app_settings: Optional[Settings] = None) -> DeliveryProviderAdapter:
    """
    Factory function returning the configured messaging delivery provider.
    Priority / fallback:
      1. 'mock' -> MockDeliveryProvider (default, zero-cost, offline-safe)
      2. 'smtp' / 'email' -> EmailDeliveryProvider
      3. 'whatsapp' -> WhatsAppDeliveryProvider
      4. fallback -> MockDeliveryProvider
    """
    cfg = app_settings or settings
    provider_name = (cfg.message_delivery_provider or "mock").lower()

    if provider_name in ("smtp", "email"):
        return EmailDeliveryProvider(
            host=cfg.smtp_host,
            port=cfg.smtp_port,
            user=cfg.smtp_user,
            password=cfg.smtp_password,
            from_email=cfg.smtp_from_email,
        )
    elif provider_name == "whatsapp":
        return WhatsAppDeliveryProvider(
            api_url=cfg.whatsapp_api_url,
            api_token=cfg.whatsapp_api_token,
            from_phone=cfg.whatsapp_from_phone,
        )
    else:
        return MockDeliveryProvider()
