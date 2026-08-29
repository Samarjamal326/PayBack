from __future__ import annotations

import logging
import uuid
from typing import Optional

import httpx

from app.models.domain import DeliveryProvider, MessageChannel, MessageStatus
from app.services.messaging.interfaces import DeliveryProviderAdapter, DeliveryResult

logger = logging.getLogger(__name__)


class ResendDeliveryProvider(DeliveryProviderAdapter):
    """
    Resend email delivery adapter for production email sending.
    Uses Resend API for reliable email delivery with tracking.
    """

    def __init__(
        self,
        api_key: str = "",
        from_email: str = "onboarding@resend.dev",
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.from_email = from_email
        self._http_client = http_client
        self.api_base = "https://api.resend.com/emails"

    @property
    def provider_type(self) -> DeliveryProvider:
        return DeliveryProvider.EMAIL_SMTP

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=30.0)

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body_html: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        if not self.is_configured:
            # Safe simulated delivery when credentials not configured
            msg_id = f"sim_resend_{uuid.uuid4().hex[:12]}"
            logger.info(
                "[SIMULATED RESEND EMAIL] (unconfigured) To: %s | Subject: %s",
                recipient_email,
                subject,
            )
            return DeliveryResult(
                success=True,
                channel=MessageChannel.EMAIL,
                provider=DeliveryProvider.EMAIL_SMTP,
                provider_message_id=msg_id,
                status=MessageStatus.DELIVERED,
            )

        try:
            client = self._get_client()
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            sender = f"{merchant_name or 'PayBack Recovery'} <{self.from_email}>"
            
            payload = {
                "from": sender,
                "to": [recipient_email],
                "subject": subject,
                "html": body_html,
            }

            response = client.post(self.api_base, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            resend_id = data.get("id")

            logger.info(
                "Resend email sent successfully to %s (Resend ID: %s)",
                recipient_email,
                resend_id,
            )

            return DeliveryResult(
                success=True,
                channel=MessageChannel.EMAIL,
                provider=DeliveryProvider.EMAIL_SMTP,
                provider_message_id=resend_id,
                status=MessageStatus.SENT,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("Resend API error %s: %s", exc.response.status_code, exc.response.text)
            return DeliveryResult(
                success=False,
                channel=MessageChannel.EMAIL,
                provider=DeliveryProvider.EMAIL_SMTP,
                status=MessageStatus.FAILED,
                failure_reason=f"Resend API error ({exc.response.status_code}): {exc.response.text}",
            )
        except Exception as exc:
            logger.error("Resend delivery failed to %s: %s", recipient_email, exc)
            return DeliveryResult(
                success=False,
                channel=MessageChannel.EMAIL,
                provider=DeliveryProvider.EMAIL_SMTP,
                status=MessageStatus.FAILED,
                failure_reason=str(exc),
            )

    def send_whatsapp(
        self,
        recipient_phone: str,
        message: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        return DeliveryResult(
            success=False,
            channel=MessageChannel.WHATSAPP,
            provider=DeliveryProvider.EMAIL_SMTP,
            status=MessageStatus.FAILED,
            failure_reason="Resend provider does not support WhatsApp channel",
        )
