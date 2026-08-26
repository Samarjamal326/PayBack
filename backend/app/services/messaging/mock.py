from __future__ import annotations

import logging
import uuid

from app.models.domain import DeliveryProvider, MessageChannel, MessageStatus
from app.services.messaging.interfaces import DeliveryProviderAdapter, DeliveryResult

logger = logging.getLogger(__name__)


class MockDeliveryProvider(DeliveryProviderAdapter):
    """
    Default zero-cost mock delivery provider.
    Simulates successful or configured delivery behavior without external network calls.
    """

    @property
    def provider_type(self) -> DeliveryProvider:
        return DeliveryProvider.MOCK

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body_html: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        msg_id = f"mock_email_{uuid.uuid4().hex[:12]}"
        logger.info(
            "[MOCK EMAIL DELIVERY] To: %s | Subject: %s | Provider ID: %s",
            recipient_email,
            subject,
            msg_id,
        )
        return DeliveryResult(
            success=True,
            channel=MessageChannel.EMAIL,
            provider=DeliveryProvider.MOCK,
            provider_message_id=msg_id,
            status=MessageStatus.DELIVERED,
        )

    def send_whatsapp(
        self,
        recipient_phone: str,
        message: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        msg_id = f"mock_wa_{uuid.uuid4().hex[:12]}"
        logger.info(
            "[MOCK WHATSAPP DELIVERY] To: %s | Provider ID: %s | Content: %s...",
            recipient_phone,
            msg_id,
            message[:60],
        )
        return DeliveryResult(
            success=True,
            channel=MessageChannel.WHATSAPP,
            provider=DeliveryProvider.MOCK,
            provider_message_id=msg_id,
            status=MessageStatus.DELIVERED,
        )
