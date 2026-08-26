from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any, Optional

from app.models.domain import (
    AuditEventType,
    AuditRecord,
    RecoveryCase,
    RecoveryOutcome,
    RecoveryStatus,
)
from app.services.recovery import RecoveryService

logger = logging.getLogger(__name__)


@dataclass
class WebhookResult:
    processed: bool
    event: str
    message: str
    case_id: Optional[str] = None


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """
    Verifies Razorpay webhook signature using HMAC SHA256.
    """
    if not signature or not secret:
        return False

    expected_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def process_razorpay_webhook_event(
    event_data: dict[str, Any],
    recovery_service: RecoveryService,
) -> WebhookResult:
    """
    Processes an authenticated Razorpay webhook event.
    """
    event_type = event_data.get("event", "")
    payload = event_data.get("payload", {})

    logger.info("Processing Razorpay webhook event: %s", event_type)

    if event_type in ("payment_link.paid", "payment.captured", "order.paid"):
        return _handle_payment_success(event_type, payload, recovery_service)
    elif event_type in ("payment.failed", "payment_link.expired", "payment_link.cancelled"):
        return _handle_payment_failure_or_expiry(event_type, payload, recovery_service)

    return WebhookResult(
        processed=False,
        event=event_type,
        message=f"Event '{event_type}' ignored (not a recovery event).",
    )


def _handle_payment_success(
    event_type: str,
    payload: dict[str, Any],
    recovery_service: RecoveryService,
) -> WebhookResult:
    payment_link_entity = payload.get("payment_link", {}).get("entity", {})
    payment_entity = payload.get("payment", {}).get("entity", {})

    notes = payment_link_entity.get("notes") or payment_entity.get("notes") or {}
    transaction_id = notes.get("transaction_id")
    link_id = payment_link_entity.get("id")

    # If notes wasn't present, try extracting transaction_id from description
    description = payment_link_entity.get("description") or payment_entity.get("description") or ""
    if not transaction_id and "transaction " in description:
        parts = description.split("transaction ")
        if len(parts) > 1:
            transaction_id = parts[1].strip()

    # Amount from paise to INR
    amount_paise = payment_entity.get("amount") or payment_link_entity.get("amount") or 0
    amount_inr = float(amount_paise) / 100.0

    case = None
    if transaction_id:
        case = recovery_service.get_case_by_transaction_id(transaction_id)
        if not case:
            # Fallback: maybe description passed case_id directly
            try:
                case = recovery_service.get_case(transaction_id)
            except Exception:
                case = None


    if not case:
        return WebhookResult(
            processed=False,
            event=event_type,
            message=f"No matching recovery case found for transaction '{transaction_id}' or link '{link_id}'.",
        )

    # Recover the case
    recovered_case = recovery_service.mark_case_recovered(
        case_id=case.id,
        amount_recovered=amount_inr if amount_inr > 0 else case.amount_at_risk,
        detail=f"Payment succeeded via Razorpay Test Webhook ({event_type}, link_id={link_id})",
    )

    return WebhookResult(
        processed=True,
        event=event_type,
        message=f"Recovery case '{case.id}' marked RECOVERED for amount INR {recovered_case.amount_recovered:.2f}.",
        case_id=case.id,
    )


def _handle_payment_failure_or_expiry(
    event_type: str,
    payload: dict[str, Any],
    recovery_service: RecoveryService,
) -> WebhookResult:
    payment_link_entity = payload.get("payment_link", {}).get("entity", {})
    payment_entity = payload.get("payment", {}).get("entity", {})

    notes = payment_link_entity.get("notes") or payment_entity.get("notes") or {}
    transaction_id = notes.get("transaction_id")

    if transaction_id:
        case = recovery_service.get_case_by_transaction_id(transaction_id)
        if case:
            recovery_service.record_audit_event(
                case_id=case.id,
                event_type=AuditEventType.RECOVERY_STOPPED if "cancelled" in event_type or "expired" in event_type else AuditEventType.PAYMENT_FAILED,
                detail=f"Razorpay webhook event '{event_type}' received.",
            )
            return WebhookResult(
                processed=True,
                event=event_type,
                message=f"Recorded '{event_type}' for case '{case.id}'.",
                case_id=case.id,
            )

    return WebhookResult(
        processed=False,
        event=event_type,
        message=f"Event '{event_type}' received without active recovery case match.",
    )
