"""
Full End-to-End Recovery Loop Integration Test.

Tests the complete flow:
Failed Payment -> PayBack Case Created -> Decision -> Test Payment Link Created
-> Simulated Webhook Payment -> Case Marked RECOVERED -> Full Audit Trail Verified.
"""
from __future__ import annotations

import json
import httpx
import pytest

from app.models.domain import (
    AuditEventType,
    Customer,
    PaymentMethod,
    RecoveryAction,
    RecoveryDecision,
    RecoveryOutcome,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.services.actions.executor import ActionExecutor
from app.services.actions.razorpay import RazorpayPaymentProvider
from app.services.actions.stubs import StubEscalationProvider, StubMessagingProvider
from app.services.llm.mock import MockMessageGenerator
from app.services.razorpay.webhook import process_razorpay_webhook_event
from app.services.recovery import RecoveryService


class TestEndToEndRecoveryLoop:
    def test_complete_recovery_lifecycle(self):
        # 1. Setup Razorpay Test Provider with mocked client
        def razorpay_mock_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.read())
            assert data["amount"] == 249900  # exact amount in paise
            assert data["notes"]["transaction_id"] == "tx_rzp_test_001"

            return httpx.Response(
                200,
                json={
                    "id": "plink_test_recover_777",
                    "short_url": "https://rzp.io/i/test_recover_777",
                    "status": "created",
                    "amount": 249900,
                },
            )

        mock_http = httpx.Client(transport=httpx.MockTransport(razorpay_mock_handler))
        rzp_provider = RazorpayPaymentProvider(
            key_id="rzp_test_e2e_key",
            key_secret="e2e_secret",
            http_client=mock_http,
        )

        executor = ActionExecutor(
            payment=rzp_provider,
            messaging=StubMessagingProvider(),
            escalation=StubEscalationProvider(),
            message_generator=MockMessageGenerator(),
        )

        service = RecoveryService(executor=executor)

        # 2. Ingest Failed Payment Event
        customer = Customer(
            name="Deepika Padukone",
            email="deepika@example.com",
            phone="+919876543210",
        )
        tx = Transaction(
            id="tx_rzp_test_001",
            customer_id=customer.id,
            amount=2499.0,
            currency="INR",
            payment_method=PaymentMethod.CARD,
            status=TransactionStatus.FAILED,
            failure_reason="bank_timeout",
        )

        case = service.ingest_payment_event(tx, customer)
        assert case.status == RecoveryStatus.DETECTED
        assert case.amount_at_risk == 2499.0

        # 3. Run Recovery Agent Workflow
        processed_case = service.run_recovery(case.id)

        # Decision engine should choose RECOVER and action CREATE_PAYMENT_LINK
        assert processed_case.decision == RecoveryDecision.RECOVER
        assert processed_case.selected_action == RecoveryAction.CREATE_PAYMENT_LINK

        # Check action records
        actions = service.get_action_history(case.id)
        assert len(actions) >= 1
        link_action = [a for a in actions if a.action == RecoveryAction.CREATE_PAYMENT_LINK][0]
        assert link_action.external_ref == "https://rzp.io/i/test_recover_777"

        # 4. Simulate Customer Paying via Razorpay Test Webhook
        webhook_payload = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_test_recover_777",
                        "amount": 249900,
                        "notes": {"transaction_id": "tx_rzp_test_001"},
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_test_succ_123",
                        "amount": 249900,
                        "status": "captured",
                        "notes": {"transaction_id": "tx_rzp_test_001"},
                    }
                },
            },
        }

        webhook_res = process_razorpay_webhook_event(webhook_payload, service)
        assert webhook_res.processed is True
        assert webhook_res.case_id == case.id

        # 5. Verify Final State and Recovered Amount
        final_case = service.get_case(case.id)
        assert final_case.status == RecoveryStatus.RECOVERED
        assert final_case.outcome == RecoveryOutcome.RECOVERED
        assert final_case.amount_recovered == 2499.0

        # 6. Verify Complete Audit Trail
        audits = service.get_audit_history(case.id)
        assert len(audits) >= 6
        audit_events = [a.event_type for a in audits]

        expected_sequence = [
            AuditEventType.PAYMENT_FAILED,
            AuditEventType.RECOVERY_CASE_CREATED,
            AuditEventType.ELIGIBILITY_CHECKED,
            AuditEventType.ACTION_SELECTED,
            AuditEventType.PAYMENT_LINK_CREATED,
            AuditEventType.DECISION_MADE,
            AuditEventType.PAYMENT_SUCCEEDED,
            AuditEventType.RECOVERY_COMPLETED,
        ]

        for expected in expected_sequence:
            assert expected in audit_events, f"Expected {expected} in audit trail"
