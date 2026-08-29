"""Shared payment-event ingestion helpers (customer resolution, merchant scoping)."""
from __future__ import annotations

import uuid

from app.api.schemas import PaymentEventRequest
from app.models.domain import Customer, Merchant, Transaction
from app.repositories.interfaces import CustomerRepository


def resolve_customer_for_payment(
    payload: PaymentEventRequest,
    merchant: Merchant,
    customer_repo: CustomerRepository,
) -> Customer:
    """
    Resolve an existing customer for this merchant or prepare a new one.
    Deduplicates by email (same merchant) then external_id (same merchant).
    Never trusts merchant_id from the request payload.
    """
    existing: Customer | None = None

    if payload.customer_email:
        candidates = customer_repo.list_by_merchant(merchant_id=merchant.id, limit=500)
        email_lower = payload.customer_email.lower()
        existing = next(
            (c for c in candidates if c.email and c.email.lower() == email_lower),
            None,
        )

    if not existing and payload.customer_external_id:
        by_ext = customer_repo.get_by_external_id(payload.customer_external_id)
        if by_ext and (not by_ext.merchant_id or by_ext.merchant_id == merchant.id):
            existing = by_ext

    if existing:
        return existing

    return Customer(
        merchant_id=merchant.id,
        external_id=payload.customer_external_id
        or f"cus_{payload.customer_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}",
        name=payload.customer_name,
        email=payload.customer_email,
        phone=payload.customer_phone,
    )


def build_transaction_for_payment(
    payload: PaymentEventRequest,
    merchant: Merchant,
    customer: Customer,
) -> Transaction:
    return Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=payload.transaction_amount,
        currency=payload.transaction_currency,
        payment_method=payload.payment_method,
        status=payload.transaction_status,
        failure_reason=payload.failure_reason,
    )
