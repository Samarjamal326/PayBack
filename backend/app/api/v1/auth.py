from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import AuthResponse, LoginRequest, MerchantProfileResponse, RegisterRequest
from app.core.auth import get_auth_provider, get_current_merchant
from app.models.domain import Merchant
from app.repositories.factory import get_repository_bundle

router = APIRouter(prefix="/auth", tags=["auth"])
_repos = get_repository_bundle()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_merchant(payload: RegisterRequest) -> AuthResponse:
    existing = _repos.merchants.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Merchant with email '{payload.email}' already exists.",
        )

    merchant = Merchant(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
    )
    saved = _repos.merchants.save(merchant)

    provider = get_auth_provider()
    token = provider.create_access_token(
        subject=saved.id,
        extra_claims={"merchant_id": saved.id, "name": saved.name, "email": saved.email},
    )

    return AuthResponse(
        access_token=token,
        merchant_id=saved.id,
        name=saved.name,
        email=saved.email,
    )


@router.post("/login", response_model=AuthResponse)
def login_merchant(payload: LoginRequest) -> AuthResponse:
    merchant = _repos.merchants.get_by_email(payload.email)
    if not merchant:
        # Create merchant if not existing in dev mode
        merchant = Merchant(
            name=payload.email.split("@")[0].capitalize(),
            email=payload.email,
        )
        merchant = _repos.merchants.save(merchant)

    provider = get_auth_provider()
    token = provider.create_access_token(
        subject=merchant.id,
        extra_claims={"merchant_id": merchant.id, "name": merchant.name, "email": merchant.email},
    )

    return AuthResponse(
        access_token=token,
        merchant_id=merchant.id,
        name=merchant.name,
        email=merchant.email,
    )


@router.get("/me", response_model=MerchantProfileResponse)
def get_me(merchant: Merchant = Depends(get_current_merchant)) -> MerchantProfileResponse:
    return MerchantProfileResponse(
        id=merchant.id,
        name=merchant.name,
        email=merchant.email,
        phone=merchant.phone,
        timezone=merchant.timezone,
        created_at=merchant.created_at,
    )
