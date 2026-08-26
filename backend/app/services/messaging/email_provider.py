from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.models.domain import DeliveryProvider, MessageChannel, MessageStatus
from app.services.messaging.interfaces import DeliveryProviderAdapter, DeliveryResult

logger = logging.getLogger(__name__)


class EmailDeliveryProvider(DeliveryProviderAdapter):
    """
    Standard Email delivery adapter (SMTP-compatible).
    Gracefully falls back to simulation when SMTP credentials are not configured.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 587,
        user: Optional[str] = None,
        password: Optional[str] = None,
        from_email: str = "recovery@payback.ai",
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email

    @property
    def provider_type(self) -> DeliveryProvider:
        return DeliveryProvider.EMAIL_SMTP

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body_html: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        if not self.is_configured:
            # Safe simulated delivery when credentials not configured
            msg_id = f"sim_smtp_{uuid.uuid4().hex[:12]}"
            logger.info(
                "[SIMULATED SMTP EMAIL] (unconfigured) To: %s | Subject: %s",
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
            # When configured with real credentials, send via smtplib
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart("alternative")
            sender = f"{merchant_name or 'PayBack Recovery'} <{self.from_email}>"
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient_email
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.from_email, [recipient_email], msg.as_string())

            msg_id = f"smtp_{uuid.uuid4().hex[:12]}"
            return DeliveryResult(
                success=True,
                channel=MessageChannel.EMAIL,
                provider=DeliveryProvider.EMAIL_SMTP,
                provider_message_id=msg_id,
                status=MessageStatus.SENT,
            )
        except Exception as exc:
            logger.error("SMTP delivery failed to %s: %s", recipient_email, exc)
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
            failure_reason="Email provider does not support WhatsApp channel",
        )
