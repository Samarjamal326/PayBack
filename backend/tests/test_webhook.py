"""
Tests for Razorpay Webhook signature verification and event processing.
"""
from __future__ import annotations

import hashlib
import hmac
import pytest

from app.models.domain import (
    Customer,
    PaymentMethod,
    RecoveryOutcome,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.services.razorpay.webhook import (
    process_razorpay_webhook_event,
    verify_webhook_signature,
)
from app.services.recovery import RecoveryService


class TestWebhookSignature:
    def test_valid_signature_accepted(self):
        secret = "super_secret_webhook_key"
        body = b'{"event": "payment_link.paid"}'
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        assert verify_webhook_signature(body, signature, secret) is True

    def test_invalid_signature_rejected(self):
        secret = "super_secret_webhook_key"
        body = b'{"event": "payment_link.paid"}'
        assert verify_webhook_signature(body, "invalid_signature_string", secret) is False

    def test_empty_signature_or_secret_rejected(self):
        assert verify_webhook_signature(b"body", "", "secret") is False
        assert verify_webhook_signature(b"body", "sig", "") is False


class TestWebhookEventProcessing:
    def test_payment_link_paid_recovers_case(self):
        svc = RecoveryService()

        # Ingest failed payment
        customer = Customer(name="Rohan Joshi", email="rohan@example.com")
        tx = Transaction(
            id="tx_test_webhook_001",
            customer_id=customer.id,
            amount=2499.0,
            status=TransactionStatus.FAILED,
        )
        case = svc.ingest_payment_event(tx, customer)

        # Run recovery -> state becomes ACTION_EXECUTED / MONITORING
        svc.run_recovery(case.id)

        # Webhook payload for payment_link.paid
        event_data = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_test_123",
                        "amount": 249900,
                        "notes": {"transaction_id": "tx_test_webhook_001"},
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_test_456",
                        "amount": 249900,
                        "status": "captured",
                        "notes": {"transaction_id": "tx_test_webhook_001"},
                    }
                },
            },
        }

        result = process_razorpay_webhook_event(event_data, svc)
        assert result.processed is True
        assert result.case_id == case.id

        updated = svc.get_case(case.id)
        assert updated.status == RecoveryStatus.RECOVERED
        assert updated.outcome == RecoveryOutcome.RECOVERED
        assert updated.amount_recovered == 2499.0

        # Verify audit trail
        audits = svc.get_audit_history(case.id)
        event_types = [a.event_type.value for a in audits]
        assert "PAYMENT_SUCCEEDED" in event_types
        assert "RECOVERY_COMPLETED" in event_types

    def test_payment_failed_event_logs_audit(self):
        svc = RecoveryService()
        customer = Customer(name="Rohan Joshi")
        tx = Transaction(
            id="tx_test_webhook_fail",
            customer_id=customer.id,
            amount=500.0,
            status=TransactionStatus.FAILED,
        )
        case = svc.ingest_payment_event(tx, customer)

        event_data = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_failed_1",
                        "notes": {"transaction_id": "tx_test_webhook_fail"},
                    }
                }
            },
        }

        result = process_razorpay_webhook_event(event_data, svc)
        assert result.processed is True

        audits = svc.get_audit_history(case.id)
        event_types = [a.event_type.value for a in audits]
        assert "PAYMENT_FAILED" in event_types
