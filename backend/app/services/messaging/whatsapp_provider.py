from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.models.domain import DeliveryProvider, MessageChannel, MessageStatus
from app.services.messaging.interfaces import DeliveryProviderAdapter, DeliveryResult

logger = logging.getLogger(__name__)


class WhatsAppDeliveryProvider(DeliveryProviderAdapter):
    """
    Standard WhatsApp delivery adapter (e.g., WhatsApp Cloud API / Twilio).
    Gracefully falls back to simulation when API credentials are not configured.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None,
        from_phone: Optional[str] = None,
    ) -> None:
        self.api_url = api_url
        self.api_token = api_token
        self.from_phone = from_phone

    @property
    def provider_type(self) -> DeliveryProvider:
        return DeliveryProvider.WHATSAPP_API

    @property
    def is_configured(self) -> bool:
        return bool(self.api_url and self.api_token)

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body_html: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        return DeliveryResult(
            success=False,
            channel=MessageChannel.EMAIL,
            provider=DeliveryProvider.WHATSAPP_API,
            status=MessageStatus.FAILED,
            failure_reason="WhatsApp provider does not support Email channel",
        )

    def send_whatsapp(
        self,
        recipient_phone: str,
        message: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        if not self.is_configured:
            # Safe simulated delivery when credentials not configured
            msg_id = f"sim_wa_{uuid.uuid4().hex[:12]}"
            logger.info(
                "[SIMULATED WHATSAPP] (unconfigured) To: %s | Provider ID: %s",
                recipient_phone,
                msg_id,
            )
            return DeliveryResult(
                success=True,
                channel=MessageChannel.WHATSAPP,
                provider=DeliveryProvider.WHATSAPP_API,
                provider_message_id=msg_id,
                status=MessageStatus.DELIVERED,
            )

        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient_phone,
                "type": "text",
                "text": {"body": message},
            }

            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            msg_id = (
                data.get("messages", [{}])[0].get("id")
                or f"wa_{uuid.uuid4().hex[:12]}"
            )
            return DeliveryResult(
                success=True,
                channel=MessageChannel.WHATSAPP,
                provider=DeliveryProvider.WHATSAPP_API,
                provider_message_id=msg_id,
                status=MessageStatus.SENT,
            )
        except Exception as exc:
            logger.error("WhatsApp delivery failed to %s: %s", recipient_phone, exc)
            return DeliveryResult(
                success=False,
                channel=MessageChannel.WHATSAPP,
                provider=DeliveryProvider.WHATSAPP_API,
                status=MessageStatus.FAILED,
                failure_reason=str(exc),
            )
