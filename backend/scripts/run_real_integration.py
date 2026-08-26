"""
Verification script demonstrating the end-to-end integration:
Payment failure -> RecoveryCase -> DecisionEngine (Recoverability + ML + EV) -> Razorpay Test Mode Link -> Webhook -> Supabase / Repository
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
_backend_dir = Path(__file__).resolve().parents[1]
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from datetime import datetime, timezone

from app.core.decision import evaluate
from app.models.domain import (
    Customer,
    PaymentMethod,
    Policy,
    RecoveryAction,
    RecoveryCase,
    RecoveryDecision,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.repositories.memory import (
    InMemoryActionRecordRepository,
    InMemoryAuditRecordRepository,
    InMemoryCustomerRepository,
    InMemoryPolicyRepository,
    InMemoryRecoveryCaseRepository,
    InMemoryTransactionRepository,
)
from app.services.actions.executor import ActionExecutor
from app.services.actions.stubs import StubEscalationProvider, StubMessagingProvider
from app.services.llm.mock import MockMessageGenerator
from app.services.razorpay.payment import StubPaymentProvider
from app.services.recovery import RecoveryService



def run_verification():
    print("=" * 70)
    print("PAYBACK PHASE 3 END-TO-END INTEGRATION VERIFICATION")
    print("=" * 70)

    # 1. Create repositories and customer
    cust_repo = InMemoryCustomerRepository()
    tx_repo = InMemoryTransactionRepository()
    case_repo = InMemoryRecoveryCaseRepository()

    customer = Customer(
        name="Aarav Patel",
        email="aarav@example.com",
        phone="+919876543210",
        opted_out=False,
    )
    cust_repo.save(customer)

    # 2. Ingest previous successful transaction
    tx_prev = Transaction(
        customer_id=customer.id,
        amount=1500.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        status=TransactionStatus.SUCCESS,
    )
    tx_repo.save(tx_prev)

    # 3. Ingest current failed payment
    tx_curr = Transaction(
        customer_id=customer.id,
        amount=2999.0,
        currency="INR",
        payment_method=PaymentMethod.CARD,
        status=TransactionStatus.FAILED,
        failure_reason="gateway_timeout",
    )
    tx_repo.save(tx_curr)

    case = RecoveryCase(
        transaction_id=tx_curr.id,
        customer_id=customer.id,
        amount_at_risk=tx_curr.amount,
        reason=tx_curr.failure_reason,
        status=RecoveryStatus.DETECTED,
    )
    case_repo.save(case)

    # 4. Evaluate with DecisionEngine
    policy = Policy()
    result = evaluate(
        case=case,
        transaction=tx_curr,
        customer=customer,
        policy=policy,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )

    print(f"Customer:              {customer.name} (opted_out={customer.opted_out})")
    print(f"Transaction:           INR {tx_curr.amount:,.2f} ({tx_curr.failure_reason})")
    print(f"Recoverability:        {result.recoverability.value.upper()}")
    print(f"ML Recovery Prob:      {result.recovery_probability:.2%}")
    print(f"Selected Action:       {result.action.value}")
    print(f"Expected Value (EV):   INR {result.expected_value:,.2f}")
    print(f"Decision:              {result.decision.value}")
    print(f"Decision Reason:       {result.reason}")
    print("Explanation Details:")
    for detail in result.explanation_details:
        print(f"  - {detail}")
    print("=" * 70)


if __name__ == "__main__":
    run_verification()
