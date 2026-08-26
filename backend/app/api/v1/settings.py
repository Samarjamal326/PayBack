from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    MerchantProfileResponse,
    NotificationSettingsResponse,
    UpdateMerchantProfileRequest,
    UpdateNotificationSettingsRequest,
)
from app.core.auth import get_current_merchant
from app.models.domain import Merchant, MerchantSettings
from app.repositories.factory import get_repository_bundle

router = APIRouter(prefix="/settings", tags=["settings"])
_repos = get_repository_bundle()


@router.get("/profile", response_model=MerchantProfileResponse)
def get_profile(merchant: Merchant = Depends(get_current_merchant)) -> MerchantProfileResponse:
    return MerchantProfileResponse(
        id=merchant.id,
        name=merchant.name,
        email=merchant.email,
        phone=merchant.phone,
        timezone=merchant.timezone,
        created_at=merchant.created_at,
    )


@router.put("/profile", response_model=MerchantProfileResponse)
def update_profile(
    payload: UpdateMerchantProfileRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> MerchantProfileResponse:
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    updated = merchant.model_copy(update=update_data)
    saved = _repos.merchants.save(updated)
    return MerchantProfileResponse(
        id=saved.id,
        name=saved.name,
        email=saved.email,
        phone=saved.phone,
        timezone=saved.timezone,
        created_at=saved.created_at,
    )


@router.get("/notifications", response_model=NotificationSettingsResponse)
def get_notification_settings(merchant: Merchant = Depends(get_current_merchant)) -> NotificationSettingsResponse:
    settings_obj = _repos.merchants.get_settings(merchant.id)
    return NotificationSettingsResponse(**settings_obj.model_dump())


@router.put("/notifications", response_model=NotificationSettingsResponse)
def update_notification_settings(
    payload: UpdateNotificationSettingsRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> NotificationSettingsResponse:
    settings_obj = _repos.merchants.get_settings(merchant.id)
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    updated = settings_obj.model_copy(update=update_data)
    saved = _repos.merchants.save_settings(updated)
    return NotificationSettingsResponse(**saved.model_dump())
