from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any, Optional

from app.core.idempotency import IdempotencyGuard
from app.models.domain import (
    AuditEventType,
    AuditRecord,
    RecoveryCase,
    RecoveryOutcome,
    RecoveryStatus,
    WebhookProcessingStatus,
)
from app.services.recovery import RecoveryService

logger = logging.getLogger(__name__)

# Razorpay error code to human-readable message mapping
RAZORPAY_ERROR_MAPPING = {
    "BAD_REQUEST_ERROR": "Invalid payment details provided",
    "INSUFFICIENT_FUNDS": "Insufficient funds in your account",
    "PAYMENT_FAILED": "Payment processing failed",
    "GATEWAY_ERROR": "Payment gateway error, please try again",
    "AUTHENTICATION_FAILED": "Authentication failed",
    "INVALID_CARD": "Invalid card details",
    "CARD_EXPIRED": "Card has expired",
    "INVALID_CVV": "Invalid CVV code",
    "INVALID_EXpiry": "Invalid expiry date",
    "MAX_AMOUNT_EXCEEDED": "Maximum amount exceeded",
    "MIN_AMOUNT_EXCEEDED": "Minimum amount not met",
    "INVALID_BANK": "Invalid bank selected",
    "BANK_DOWN": "Bank services are temporarily unavailable",
    "TIMEOUT": "Payment processing timeout",
    "CANCELLED": "Payment was cancelled",
}

def get_human_readable_error(code: str, fallback: str = "") -> str:
    """Convert Razorpay error code to human-readable message."""
    return RAZORPAY_ERROR_MAPPING.get(code, fallback or code)


@dataclass
class WebhookResult:
    processed: bool
    event: str
    message: str
    case_id: Optional[str] = None
    is_duplicate: bool = False


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
    idempotency_guard: Optional[IdempotencyGuard] = None,
) -> WebhookResult:
    """
    Processes an authenticated Razorpay webhook event with idempotency protection.
    """
    if not isinstance(event_data, dict):
        return WebhookResult(
            processed=False,
            event="unknown",
            message="Malformed event payload: expected JSON dictionary.",
        )

    event_type = event_data.get("event", "")
    payload = event_data.get("payload", {})
    provider_event_id = event_data.get("id") or event_data.get("event_id") or ""

    # Generate fallback event identity from payload entity IDs if not top-level
    if not provider_event_id:
        payment_id = payload.get("payment", {}).get("entity", {}).get("id")
        link_id = payload.get("payment_link", {}).get("entity", {}).get("id")
        order_id = payload.get("order", {}).get("entity", {}).get("id")
        entity_key = payment_id or link_id or order_id or ""
        if entity_key and event_type:
            provider_event_id = f"{event_type}_{entity_key}"

    # Webhook Idempotency check
    guard = idempotency_guard or (
        IdempotencyGuard(recovery_service._repos.processed_webhooks)
        if hasattr(recovery_service, "_repos") and recovery_service._repos.processed_webhooks
        else None
    )

    if guard and provider_event_id:
        if guard.is_event_processed("razorpay", provider_event_id):
            logger.info("Duplicate Razorpay webhook event '%s' ignored.", provider_event_id)
            return WebhookResult(
                processed=True,
                event=event_type,
                message=f"Event '{provider_event_id}' already processed (idempotent duplicate).",
                is_duplicate=True,
            )

    logger.info("Processing Razorpay webhook event: %s (id=%s)", event_type, provider_event_id)

    result: WebhookResult
    if event_type in ("payment_link.paid", "payment.captured", "order.paid"):
        result = _handle_payment_success(event_type, payload, recovery_service)
    elif event_type in ("payment.failed", "payment_link.expired", "payment_link.cancelled"):
        result = _handle_payment_failure_or_expiry(event_type, payload, recovery_service)
    else:
        result = WebhookResult(
            processed=False,
            event=event_type,
            message=f"Event '{event_type}' ignored (not a recovery event).",
        )

    # Record successful processing in idempotency repo
    if guard and provider_event_id and result.processed:
        try:
            merchant_id = None
            if result.case_id:
                try:
                    case = recovery_service.get_case(result.case_id)
                    if case:
                        merchant_id = case.merchant_id
                except Exception:
                    pass
            
            guard.record_processed_event(
                provider="razorpay",
                provider_event_id=provider_event_id,
                event_type=event_type,
                merchant_id=merchant_id,
                status=WebhookProcessingStatus.PROCESSED,
            )
        except Exception as guard_exc:
            logger.warning("Failed to record processed webhook event in guard: %s", guard_exc)

    return result


def _handle_payment_success(
    event_type: str,
    payload: dict[str, Any],
    recovery_service: RecoveryService,
) -> WebhookResult:
    payment_link_entity = payload.get("payment_link", {}).get("entity", {})
    payment_entity = payload.get("payment", {}).get("entity", {})
    order_entity = payload.get("order", {}).get("entity", {})

    notes = payment_link_entity.get("notes") or payment_entity.get("notes") or order_entity.get("notes") or {}
    transaction_id = notes.get("transaction_id")
    order_id = order_entity.get("id")
    payment_id = payment_entity.get("id")

    # If notes wasn't present, try extracting transaction_id from description
    description = payment_link_entity.get("description") or payment_entity.get("description") or ""
    if not transaction_id and "transaction " in description:
        parts = description.split("transaction ")
        if len(parts) > 1:
            transaction_id = parts[1].strip()

    # Amount from paise to INR
    amount_paise = payment_entity.get("amount") or payment_link_entity.get("amount") or 0
    amount_inr = float(amount_paise) / 100.0

    # First try to find transaction by ID from notes
    transaction = None
    if transaction_id:
        transaction = recovery_service._transactions_repo.get(transaction_id)
    
    # Fallback: try to find by Razorpay order ID
    if not transaction and order_id:
        transactions = recovery_service._transactions_repo.list_by_merchant(limit=1000)
        transaction = next((t for t in transactions if t.razorpay_order_id == order_id), None)
    
    # Fallback: try to find by Razorpay payment ID
    if not transaction and payment_id:
        transactions = recovery_service._transactions_repo.list_by_merchant(limit=1000)
        transaction = next((t for t in transactions if t.razorpay_payment_id == payment_id), None)
    
    # Fallback: try to find by Razorpay payment ID
    if not transaction and payment_id:
        transactions = recovery_service._transactions_repo.list_by_merchant(limit=1000)
        transaction = next((t for t in transactions if t.razorpay_payment_id == payment_id), None)

    if not transaction:
        return WebhookResult(
            processed=False,
            event=event_type,
            message=f"No matching transaction found for transaction_id='{transaction_id}', order_id='{order_id}', or payment_id='{payment_id}'.",
        )

    # Update transaction with success status
    from app.models.domain import TransactionStatus
    transaction.status = TransactionStatus.SUCCESS
    transaction.razorpay_payment_id = payment_id or transaction.razorpay_payment_id
    if not transaction.razorpay_order_id and order_id:
        transaction.razorpay_order_id = order_id
    recovery_service._transactions_repo.save(transaction)

    # Check if there's an existing recovery case for this transaction
    case = recovery_service.get_case_by_transaction_id(transaction.id)
    if case:
        # Recover the existing case
        recovered_case = recovery_service.mark_case_recovered(
            case_id=case.id,
            amount_recovered=amount_inr if amount_inr > 0 else case.amount_at_risk,
            detail=f"Payment succeeded via Razorpay Test Webhook ({event_type}, payment_id={payment_id})",
        )

        return WebhookResult(
            processed=True,
            event=event_type,
            message=f"Transaction '{transaction.id}' succeeded and recovery case '{case.id}' marked RECOVERED for amount INR {recovered_case.amount_recovered:.2f}.",
            case_id=case.id,
        )
    else:
        # No recovery case exists - this was a successful payment that never failed
        return WebhookResult(
            processed=True,
            event=event_type,
            message=f"Transaction '{transaction.id}' succeeded (no recovery case needed).",
        )


def _handle_payment_failure_or_expiry(
    event_type: str,
    payload: dict[str, Any],
    recovery_service: RecoveryService,
) -> WebhookResult:
    payment_link_entity = payload.get("payment_link", {}).get("entity", {})
    payment_entity = payload.get("payment", {}).get("entity", {})
    order_entity = payload.get("order", {}).get("entity", {})

    notes = payment_link_entity.get("notes") or payment_entity.get("notes") or order_entity.get("notes") or {}
    transaction_id = notes.get("transaction_id")
    order_id = order_entity.get("id")
    payment_id = payment_entity.get("id")

    # Extract customer information from webhook payload
    customer_email = payment_link_entity.get("customer_email") or payment_entity.get("email") or order_entity.get("customer_email") or notes.get("customer_email")
    customer_name = payment_link_entity.get("customer_name") or payment_entity.get("name") or order_entity.get("customer_name") or notes.get("customer_name")
    customer_phone = payment_link_entity.get("customer_contact") or payment_entity.get("contact") or order_entity.get("customer_contact") or notes.get("customer_phone")

    # Extract failure details
    failure_code = payment_entity.get("code") or payment_entity.get("error_code") or ""
    raw_failure_reason = payment_entity.get("description") or payment_entity.get("error_description") or payment_entity.get("reason") or ""
    
    # Convert error code to human-readable message if no description provided
    failure_reason = raw_failure_reason if raw_failure_reason else get_human_readable_error(failure_code, f"Payment failed ({failure_code})")
    
    # First try to find transaction by ID from notes
    transaction = None
    if transaction_id:
        transaction = recovery_service._transactions_repo.get(transaction_id)
    
    # Fallback: try to find by Razorpay order ID
    if not transaction and order_id:
        transactions = recovery_service._transactions_repo.list_by_merchant(limit=1000)
        transaction = next((t for t in transactions if t.razorpay_order_id == order_id), None)
    
    # Fallback: try to find by Razorpay payment ID
    if not transaction and payment_id:
        transactions = recovery_service._transactions_repo.list_by_merchant(limit=1000)
        transaction = next((t for t in transactions if t.razorpay_payment_id == payment_id), None)

    if not transaction:
        return WebhookResult(
            processed=False,
            event=event_type,
            message=f"No matching transaction found for transaction_id='{transaction_id}', order_id='{order_id}', or payment_id='{payment_id}'.",
        )

    # Update transaction with failure status
    from app.models.domain import TransactionStatus
    transaction.status = TransactionStatus.FAILED
    transaction.failure_reason = failure_reason or f"Razorpay {event_type}"
    transaction.failure_code = failure_code
    transaction.razorpay_payment_id = payment_id or transaction.razorpay_payment_id
    if not transaction.razorpay_order_id and order_id:
        transaction.razorpay_order_id = order_id
    recovery_service._transactions_repo.save(transaction)

    # Check if recovery case already exists
    existing_case = recovery_service.get_case_by_transaction_id(transaction.id)
    if existing_case:
        # Recovery case already exists, just record the failure event
        recovery_service.record_audit_event(
            case_id=existing_case.id,
            event_type=AuditEventType.RECOVERY_STOPPED if "cancelled" in event_type or "expired" in event_type else AuditEventType.PAYMENT_FAILED,
            detail=f"Razorpay webhook event '{event_type}' received. Payment failed: {failure_reason}",
        )
        return WebhookResult(
            processed=True,
            event=event_type,
            message=f"Recorded '{event_type}' for existing case '{existing_case.id}'.",
            case_id=existing_case.id,
        )

    # No existing recovery case - create one and trigger the recovery engine
    customer = recovery_service._customers_repo.get(transaction.customer_id)
    if not customer:
        return WebhookResult(
            processed=False,
            event=event_type,
            message=f"Customer '{transaction.customer_id}' not found for transaction '{transaction.id}'.",
        )
    
    # Update customer information from webhook if missing
    customer_updated = False
    if not customer.email and customer_email:
        customer.email = customer_email
        customer_updated = True
    if not customer.name and customer_name:
        customer.name = customer_name
        customer_updated = True
    if not customer.phone and customer_phone:
        customer.phone = customer_phone
        customer_updated = True
    
    if customer_updated:
        recovery_service._customers_repo.save(customer)
        logger.info(f"Updated customer '{customer.id}' with information from webhook: email={customer_email}, name={customer_name}, phone={customer_phone}")

    # Create recovery case for the failed payment
    case = recovery_service.ingest_payment_event(transaction, customer)
    
    # Trigger the full recovery workflow
    try:
        recovery_service.run_recovery(case.id)
        
        return WebhookResult(
            processed=True,
            event=event_type,
            message=f"Payment failure processed. Recovery case '{case.id}' created and recovery workflow triggered for merchant '{transaction.merchant_id}'.",
            case_id=case.id,
        )
    except Exception as exc:
        logger.error(f"Failed to run recovery workflow for case '{case.id}': {exc}")
        return WebhookResult(
            processed=True,
            event=event_type,
            message=f"Recovery case '{case.id}' created but workflow failed: {str(exc)}",
            case_id=case.id,
        )

