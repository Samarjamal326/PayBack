from app.core.idempotency import IdempotencyGuard
from app.models.domain import Customer, RecoveryCase, RecoveryStatus, Transaction, TransactionStatus
from app.repositories.memory import InMemoryProcessedWebhookEventRepository
from app.services.razorpay.webhook import process_razorpay_webhook_event
from app.services.recovery import RecoveryService


def test_webhook_idempotency_duplicate_event():
    service = RecoveryService()
    webhook_repo = InMemoryProcessedWebhookEventRepository()
    guard = IdempotencyGuard(webhook_repo)

    # Ingest a failed transaction
    cust = Customer(id="cust_idem_1", name="Idem Customer")
    tx = Transaction(id="tx_idem_1", customer_id="cust_idem_1", amount=1500.0, status=TransactionStatus.FAILED)
    case = service.ingest_payment_event(tx, cust)
    assert case.status == RecoveryStatus.DETECTED

    # Mock webhook event
    event_data = {
        "id": "evt_test_12345",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_123",
                    "amount": 150000,
                    "notes": {"transaction_id": "tx_idem_1"},
                }
            }
        },
    }

    # 1. First delivery -> processed and recovered
    res1 = process_razorpay_webhook_event(event_data, service, idempotency_guard=guard)
    assert res1.processed is True
    assert res1.is_duplicate is False

    updated_case = service.get_case(case.id)
    assert updated_case.status == RecoveryStatus.RECOVERED

    # 2. Second duplicate delivery -> marked as duplicate, no redundant state transition
    res2 = process_razorpay_webhook_event(event_data, service, idempotency_guard=guard)
    assert res2.processed is True
    assert res2.is_duplicate is True

    # 3. Third duplicate delivery -> still safely handled
    res3 = process_razorpay_webhook_event(event_data, service, idempotency_guard=guard)
    assert res3.processed is True
    assert res3.is_duplicate is True
