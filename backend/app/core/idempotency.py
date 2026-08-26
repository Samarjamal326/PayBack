from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.models.domain import ProcessedWebhookEvent, WebhookProcessingStatus
from app.repositories.interfaces import ProcessedWebhookEventRepository

logger = logging.getLogger(__name__)


class IdempotencyGuard:
    """
    Guarantees that duplicate webhook deliveries or repeated external actions
    do not cause duplicated recovery cases, messages, or audit records.
    """

    def __init__(self, repo: ProcessedWebhookEventRepository) -> None:
        self.repo = repo

    def is_event_processed(self, provider: str, provider_event_id: str) -> bool:
        """Checks if a webhook event ID has already been recorded."""
        if not provider_event_id:
            return False
        return self.repo.get_by_provider_event_id(provider, provider_event_id) is not None

    def record_processed_event(
        self,
        provider: str,
        provider_event_id: str,
        event_type: str,
        merchant_id: Optional[str] = None,
        status: WebhookProcessingStatus = WebhookProcessingStatus.PROCESSED,
    ) -> ProcessedWebhookEvent:
        """Records an event as processed."""
        event = ProcessedWebhookEvent(
            merchant_id=merchant_id,
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            processed_at=datetime.now(timezone.utc),
            processing_status=status,
        )
        return self.repo.save(event)
