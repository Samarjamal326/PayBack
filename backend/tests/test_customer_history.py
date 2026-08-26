from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.core.probability import (
    RecoveryContext,
    recovery_context_from_domain,
)
from app.models.domain import (
    Customer,
    PaymentMethod,
    RecoveryCase,
    RecoveryOutcome,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.repositories.memory import (
    InMemoryCustomerRepository,
    InMemoryRecoveryCaseRepository,
    InMemoryTransactionRepository,
)
from app.repositories.supabase import (
    SupabaseClient,
    SupabaseRecoveryCaseRepository,
    SupabaseTransactionRepository,
)
from app.services.ml.customer_history import (
    CustomerHistory,
    CustomerHistoryService,
    compute_customer_history,
)


@pytest.fixture
def base_dt() -> datetime:
    return datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_customer(base_dt: datetime) -> Customer:
    # Created 30 days before base_dt
    return Customer(
        id="cust-100",
        name="Aarav Patel",
        email="aarav@example.com",
        created_at=base_dt - timedelta(days=30),
        opted_out=False,
    )


@pytest.fixture
def tx_repo() -> InMemoryTransactionRepository:
    return InMemoryTransactionRepository()


@pytest.fixture
def case_repo() -> InMemoryRecoveryCaseRepository:
    return InMemoryRecoveryCaseRepository()


# ---------------------------------------------------------------------------
# 1. Customer with no previous transactions
# ---------------------------------------------------------------------------

def test_customer_with_no_history(sample_customer, base_dt, tx_repo, case_repo):
    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=base_dt,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )
    assert history.customer_tenure_days == pytest.approx(30.0, 1e-2)
    assert history.previous_transactions == 0.0
    assert history.historical_success_rate == 0.0
    assert history.previous_failures == 0.0
    assert history.previous_recoveries == 0.0
    assert history.prior_recovery_rate == 0.0
    assert history.customer_history_strength == 0.0


# ---------------------------------------------------------------------------
# 2. Customer with several successful transactions
# ---------------------------------------------------------------------------

def test_customer_with_successful_transactions(sample_customer, base_dt, tx_repo, case_repo):
    for i in range(5):
        tx = Transaction(
            id=f"tx-succ-{i}",
            customer_id=sample_customer.id,
            amount=1000.0 * (i + 1),
            status=TransactionStatus.SUCCESS,
            created_at=base_dt - timedelta(days=10 - i),
        )
        tx_repo.save(tx)

    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=base_dt,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )
    assert history.previous_transactions == 5.0
    assert history.historical_success_rate == 1.0
    assert history.previous_failures == 0.0
    assert history.previous_recoveries == 0.0
    assert history.prior_recovery_rate == 0.0
    expected_strength = math.log1p(5.0) / math.log1p(40.0)
    assert history.customer_history_strength == pytest.approx(expected_strength, 1e-3)


# ---------------------------------------------------------------------------
# 3. Customer with previous failures
# ---------------------------------------------------------------------------

def test_customer_with_previous_failures(sample_customer, base_dt, tx_repo, case_repo):
    for i in range(3):
        tx = Transaction(
            id=f"tx-fail-{i}",
            customer_id=sample_customer.id,
            amount=500.0,
            status=TransactionStatus.FAILED,
            created_at=base_dt - timedelta(days=5 - i),
        )
        tx_repo.save(tx)

    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=base_dt,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )
    assert history.previous_transactions == 3.0
    assert history.historical_success_rate == 0.0
    assert history.previous_failures == 3.0
    assert history.previous_recoveries == 0.0
    assert history.prior_recovery_rate == 0.0


# ---------------------------------------------------------------------------
# 4. Customer with previous recoveries
# ---------------------------------------------------------------------------

def test_customer_with_previous_recoveries(sample_customer, base_dt, tx_repo, case_repo):
    # 2 failures
    for i in range(2):
        tx = Transaction(
            id=f"tx-rec-{i}",
            customer_id=sample_customer.id,
            amount=1500.0,
            status=TransactionStatus.FAILED,
            created_at=base_dt - timedelta(days=6 - i),
        )
        tx_repo.save(tx)
        # 1 recovered case
        case = RecoveryCase(
            id=f"case-rec-{i}",
            transaction_id=tx.id,
            customer_id=sample_customer.id,
            amount_at_risk=1500.0,
            reason="bank_error",
            status=RecoveryStatus.RECOVERED if i == 0 else RecoveryStatus.STOPPED,
            outcome=RecoveryOutcome.RECOVERED if i == 0 else RecoveryOutcome.STOPPED,
            created_at=base_dt - timedelta(days=5 - i),
        )
        case_repo.save(case)

    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=base_dt,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )
    assert history.previous_transactions == 2.0
    assert history.previous_failures == 2.0
    assert history.previous_recoveries == 1.0
    # prior_recovery_rate = 1 / (2 + 1) = 1/3 ≈ 0.3333
    assert history.prior_recovery_rate == pytest.approx(1.0 / 3.0, 1e-3)


# ---------------------------------------------------------------------------
# 5. Mixed transaction history
# ---------------------------------------------------------------------------

def test_mixed_transaction_history(sample_customer, base_dt, tx_repo, case_repo):
    # 4 success, 2 failed
    for i in range(4):
        tx_repo.save(Transaction(
            id=f"tx-s-{i}",
            customer_id=sample_customer.id,
            amount=100.0,
            status=TransactionStatus.SUCCESS,
            created_at=base_dt - timedelta(days=15 - i),
        ))
    for i in range(2):
        tx_repo.save(Transaction(
            id=f"tx-f-{i}",
            customer_id=sample_customer.id,
            amount=200.0,
            status=TransactionStatus.FAILED,
            created_at=base_dt - timedelta(days=5 - i),
        ))

    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=base_dt,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )
    assert history.previous_transactions == 6.0
    assert history.historical_success_rate == pytest.approx(4.0 / 6.0, 1e-3)
    assert history.previous_failures == 2.0


# ---------------------------------------------------------------------------
# 6. Current transaction excluded from historical counts (Temporal Check)
# ---------------------------------------------------------------------------

def test_current_transaction_excluded_temporally(sample_customer, base_dt, tx_repo, case_repo):
    # 2 past transactions
    tx_repo.save(Transaction(
        id="tx-past-1",
        customer_id=sample_customer.id,
        amount=100.0,
        status=TransactionStatus.SUCCESS,
        created_at=base_dt - timedelta(hours=2),
    ))
    tx_repo.save(Transaction(
        id="tx-past-2",
        customer_id=sample_customer.id,
        amount=200.0,
        status=TransactionStatus.FAILED,
        created_at=base_dt - timedelta(hours=1),
    ))

    # Current transaction (occurring at base_dt)
    curr_tx = Transaction(
        id="tx-current",
        customer_id=sample_customer.id,
        amount=500.0,
        status=TransactionStatus.FAILED,
        created_at=base_dt,
    )
    tx_repo.save(curr_tx)

    # Future transaction (occurring after base_dt)
    tx_repo.save(Transaction(
        id="tx-future",
        customer_id=sample_customer.id,
        amount=1000.0,
        status=TransactionStatus.SUCCESS,
        created_at=base_dt + timedelta(hours=1),
    ))

    # Query with reference_dt = curr_tx.created_at (base_dt)
    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=curr_tx.created_at,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )

    # Must count ONLY the 2 past transactions, excluding tx-current and tx-future
    assert history.previous_transactions == 2.0
    assert history.previous_failures == 1.0
    assert history.historical_success_rate == 0.5


# ---------------------------------------------------------------------------
# 7. Current recovery case excluded from historical recovery counts
# ---------------------------------------------------------------------------

def test_current_recovery_case_excluded_temporally(sample_customer, base_dt, case_repo):
    # Past recovered case
    case_repo.save(RecoveryCase(
        id="case-past",
        transaction_id="tx-p",
        customer_id=sample_customer.id,
        amount_at_risk=100.0,
        reason="err",
        status=RecoveryStatus.RECOVERED,
        outcome=RecoveryOutcome.RECOVERED,
        created_at=base_dt - timedelta(days=1),
    ))

    # Current recovery case
    case_repo.save(RecoveryCase(
        id="case-current",
        transaction_id="tx-c",
        customer_id=sample_customer.id,
        amount_at_risk=200.0,
        reason="err",
        status=RecoveryStatus.RECOVERED,
        outcome=RecoveryOutcome.RECOVERED,
        created_at=base_dt,
    ))

    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=base_dt,
        case_repo=case_repo,
    )
    assert history.previous_recoveries == 1.0


# ---------------------------------------------------------------------------
# 8, 9, 10. Calculations: success rate, prior recovery rate, customer history strength
# ---------------------------------------------------------------------------

def test_calculations_and_clamping(sample_customer, base_dt, tx_repo, case_repo):
    # 50 transactions to test log1p(50) / log1p(40) clamping to 1.0
    for i in range(50):
        tx_repo.save(Transaction(
            id=f"tx-many-{i}",
            customer_id=sample_customer.id,
            amount=100.0,
            status=TransactionStatus.SUCCESS if i % 2 == 0 else TransactionStatus.FAILED,
            created_at=base_dt - timedelta(days=100 - i),
        ))

    history = compute_customer_history(
        customer=sample_customer,
        reference_dt=base_dt,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )
    assert history.previous_transactions == 50.0
    assert history.historical_success_rate == 0.5
    assert history.previous_failures == 25.0
    # strength clamped to 1.0
    assert history.customer_history_strength == 1.0


# ---------------------------------------------------------------------------
# 11, 12, 13. Naive & timezone-aware datetime handling for tenure
# ---------------------------------------------------------------------------

def test_naive_and_timezone_aware_datetime_handling():
    # Naive datetimes
    cust_naive = Customer(
        id="cust-naive",
        name="Naive User",
        created_at=datetime(2026, 8, 1, 12, 0, 0),
    )
    ref_naive = datetime(2026, 8, 11, 12, 0, 0)
    h_naive = compute_customer_history(cust_naive, ref_naive)
    assert h_naive.customer_tenure_days == pytest.approx(10.0, 1e-2)

    # Timezone-aware datetimes
    cust_tz = Customer(
        id="cust-tz",
        name="Tz User",
        created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    ref_tz = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)
    h_tz = compute_customer_history(cust_tz, ref_tz)
    assert h_tz.customer_tenure_days == pytest.approx(15.0, 1e-2)

    # Mixed (naive customer, tz reference)
    h_mixed = compute_customer_history(cust_naive, ref_tz)
    assert h_mixed.customer_tenure_days == pytest.approx(15.0, 1e-2)


# ---------------------------------------------------------------------------
# 14. CustomerHistoryService integration
# ---------------------------------------------------------------------------

def test_customer_history_service(sample_customer, base_dt, tx_repo, case_repo):
    service = CustomerHistoryService(transaction_repo=tx_repo, case_repo=case_repo)
    tx_repo.save(Transaction(
        id="tx-s1",
        customer_id=sample_customer.id,
        amount=100.0,
        status=TransactionStatus.SUCCESS,
        created_at=base_dt - timedelta(days=2),
    ))

    history = service.get_history(sample_customer, base_dt)
    assert isinstance(history, CustomerHistory)
    assert history.previous_transactions == 1.0
    assert history.historical_success_rate == 1.0


# ---------------------------------------------------------------------------
# 15. Supabase repository mock testing
# ---------------------------------------------------------------------------

def test_supabase_repositories_queries_with_mock(base_dt):
    mock_client = MagicMock(spec=SupabaseClient)
    # Mock returning 2 transaction rows and 1 case row
    mock_client.select.side_effect = [
        [{"id": "tx-1"}, {"id": "tx-2"}],  # total count
        [{"id": "tx-1"}],                    # successful count
        [{"id": "tx-2"}],                    # failed count
        [{"id": "case-1"}],                  # recovered cases count
    ]

    supa_tx_repo = SupabaseTransactionRepository(mock_client)
    supa_case_repo = SupabaseRecoveryCaseRepository(mock_client)

    cust = Customer(id="cust-supa", name="Supa User", created_at=base_dt - timedelta(days=5))
    history = compute_customer_history(
        customer=cust,
        reference_dt=base_dt,
        transaction_repo=supa_tx_repo,
        case_repo=supa_case_repo,
    )

    assert history.previous_transactions == 2.0
    assert history.historical_success_rate == 0.5
    assert history.previous_failures == 1.0
    assert history.previous_recoveries == 1.0
    assert history.prior_recovery_rate == 0.5

    # Check mock calls
    assert mock_client.select.call_count == 4


# ---------------------------------------------------------------------------
# 16. recovery_context_from_domain end-to-end with real history
# ---------------------------------------------------------------------------

def test_recovery_context_from_domain_with_repositories(sample_customer, base_dt, tx_repo, case_repo):
    tx_repo.save(Transaction(
        id="tx-prev-1",
        customer_id=sample_customer.id,
        amount=500.0,
        status=TransactionStatus.SUCCESS,
        created_at=base_dt - timedelta(days=2),
    ))

    curr_tx = Transaction(
        id="tx-curr",
        customer_id=sample_customer.id,
        amount=1500.0,
        payment_method=PaymentMethod.UPI,
        status=TransactionStatus.FAILED,
        failure_reason="temporary_bank_error",
        created_at=base_dt,
    )

    curr_case = RecoveryCase(
        id="case-curr",
        transaction_id=curr_tx.id,
        customer_id=sample_customer.id,
        amount_at_risk=1500.0,
        reason="temporary_bank_error",
        status=RecoveryStatus.DETECTED,
        retry_count=1,
        message_count=1,
        created_at=base_dt,
    )

    ctx = recovery_context_from_domain(
        transaction=curr_tx,
        customer=sample_customer,
        case=curr_case,
        transaction_repo=tx_repo,
        case_repo=case_repo,
    )

    assert ctx.amount == 1500.0
    assert ctx.payment_method_raw == "upi"
    assert ctx.customer_tenure_days == pytest.approx(30.0, 1e-2)
    assert ctx.previous_transactions == 1.0
    assert ctx.historical_success_rate == 1.0
    assert ctx.previous_failures == 0.0
    assert ctx.checkout_intent_score == 0.5  # Documented placeholder
