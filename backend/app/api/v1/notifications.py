from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import NotificationResponse, UnreadCountResponse
from app.core.auth import get_current_merchant
from app.models.domain import Merchant
from app.repositories.factory import get_repository_bundle

router = APIRouter(prefix="/notifications", tags=["notifications"])
_repos = get_repository_bundle()


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = Query(default=False),
    merchant: Merchant = Depends(get_current_merchant),
) -> list[NotificationResponse]:
    notifications = _repos.notifications.list_by_merchant(
        merchant_id=merchant.id,
        limit=limit,
        unread_only=unread_only,
    )
    return [NotificationResponse(**n.model_dump()) for n in notifications]


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(merchant: Merchant = Depends(get_current_merchant)) -> UnreadCountResponse:
    count = _repos.notifications.count_unread(merchant.id)
    return UnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> NotificationResponse:
    notification = _repos.notifications.mark_read(notification_id=notification_id, merchant_id=merchant.id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    return NotificationResponse(**notification.model_dump())
