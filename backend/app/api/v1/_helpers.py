"""Shared helpers for API v1 endpoints."""
from __future__ import annotations

from app.core.auth import DEV_MERCHANT_EMAIL, DEV_MERCHANT_ID
from app.models.domain import Merchant


def is_demo_admin(merchant: Merchant) -> bool:
    """
    Returns True if this merchant should see legacy rows where merchant_id IS NULL
    (reconciled to the development merchant in migration 002).
    """
    return merchant.id == DEV_MERCHANT_ID or merchant.email.lower() == DEV_MERCHANT_EMAIL.lower()
