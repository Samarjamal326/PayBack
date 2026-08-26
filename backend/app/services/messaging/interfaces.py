from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.models.domain import DeliveryProvider, MessageChannel, MessageStatus


@dataclass(frozen=True)
class DeliveryResult:
    """Standardized delivery result across all messaging providers."""
    success: bool
    channel: MessageChannel
    provider: DeliveryProvider
    provider_message_id: Optional[str] = None
    status: MessageStatus = MessageStatus.SENT
    failure_reason: Optional[str] = None
    timestamp: datetime = None  # type: ignore

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, "timestamp", datetime.now(timezone.utc))


class DeliveryProviderAdapter(ABC):
    """
    Provider-independent delivery interface.
    Cleanly separated from LLM message content generation.
    """

    @property
    @abstractmethod
    def provider_type(self) -> DeliveryProvider:
        ...

    @abstractmethod
    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body_html: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        ...

    @abstractmethod
    def send_whatsapp(
        self,
        recipient_phone: str,
        message: str,
        merchant_name: Optional[str] = None,
    ) -> DeliveryResult:
        ...
