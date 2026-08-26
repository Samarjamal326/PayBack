from __future__ import annotations

import logging
from typing import Optional

from app.models.domain import Notification, NotificationType
from app.repositories.interfaces import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service managing merchant-facing notifications for recovery lifecycle events.
    Supports in-app notification bell, recovery completion alerts, escalation notices, etc.
    """

    def __init__(self, repo: NotificationRepository) -> None:
        self.repo = repo

    def notify_recovery_completed(
        self,
        merchant_id: str,
        case_id: str,
        amount: float,
        currency: str = "INR",
    ) -> Notification:
        notification = Notification(
            merchant_id=merchant_id,
            notification_type=NotificationType.RECOVERY_COMPLETED,
            title="Recovery Successful",
            message=f"Recovery case '{case_id}' successfully recovered {currency} {amount:,.2f}.",
            recovery_case_id=case_id,
        )
        logger.info("Notification sent [RECOVERY_COMPLETED] to merchant '%s'", merchant_id)
        return self.repo.save(notification)

    def notify_recovery_escalated(
        self,
        merchant_id: str,
        case_id: str,
        reason: str,
    ) -> Notification:
        notification = Notification(
            merchant_id=merchant_id,
            notification_type=NotificationType.RECOVERY_ESCALATED,
            title="Recovery Escalated to Human Review",
            message=f"Case '{case_id}' escalated. Reason: {reason}.",
            recovery_case_id=case_id,
        )
        logger.info("Notification sent [RECOVERY_ESCALATED] to merchant '%s'", merchant_id)
        return self.repo.save(notification)

    def notify_action_failed(
        self,
        merchant_id: str,
        case_id: str,
        action: str,
        error: str,
    ) -> Notification:
        notification = Notification(
            merchant_id=merchant_id,
            notification_type=NotificationType.ACTION_FAILED,
            title="Recovery Action Failed",
            message=f"Action '{action}' for case '{case_id}' failed: {error}.",
            recovery_case_id=case_id,
        )
        logger.info("Notification sent [ACTION_FAILED] to merchant '%s'", merchant_id)
        return self.repo.save(notification)

    def list_notifications(
        self,
        merchant_id: str,
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[Notification]:
        return self.repo.list_by_merchant(merchant_id=merchant_id, limit=limit, unread_only=unread_only)

    def count_unread(self, merchant_id: str) -> int:
        return self.repo.count_unread(merchant_id=merchant_id)

    def mark_read(self, notification_id: str, merchant_id: str) -> Optional[Notification]:
        return self.repo.mark_read(notification_id=notification_id, merchant_id=merchant_id)
