"""
Shared test fixtures.
"""
from __future__ import annotations

import os

# Force in-memory repositories for the entire test session (before app imports).
os.environ["DATABASE_MODE"] = "memory"

import pytest

from app.config import settings
from app.models.domain import (
    Customer,
    PaymentMethod,
    Policy,
    RecoveryCase,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)


@pytest.fixture(autouse=True)
def reset_in_memory_repositories():
    import app.repositories.factory as factory

    factory._shared_supabase_bundle = None
    settings.database_mode = "memory"
    factory.reset_in_memory_repositories()


@pytest.fixture
def default_policy() -> Policy:
    return Policy()


@pytest.fixture
def failed_transaction() -> Transaction:
    return Transaction(
        customer_id="cust-1",
        amount=2_499.0,
        payment_method=PaymentMethod.CARD,
        status=TransactionStatus.FAILED,
        failure_reason="card_declined",
    )


@pytest.fixture
def abandoned_transaction() -> Transaction:
    return Transaction(
        customer_id="cust-1",
        amount=999.0,
        payment_method=PaymentMethod.UPI,
        status=TransactionStatus.ABANDONED,
    )


@pytest.fixture
def high_value_transaction() -> Transaction:
    return Transaction(
        customer_id="cust-1",
        amount=15_000.0,
        payment_method=PaymentMethod.NET_BANKING,
        status=TransactionStatus.FAILED,
        failure_reason="bank_error",
    )


@pytest.fixture
def active_customer() -> Customer:
    return Customer(
        id="cust-1",
        name="Priya Sharma",
        email="priya@example.com",
        phone="+919876543210",
    )


@pytest.fixture
def opted_out_customer() -> Customer:
    return Customer(
        id="cust-2",
        name="Rahul Verma",
        email="rahul@example.com",
        opted_out=True,
    )


@pytest.fixture
def detected_case(failed_transaction: Transaction, active_customer: Customer) -> RecoveryCase:
    return RecoveryCase(
        transaction_id=failed_transaction.id,
        customer_id=active_customer.id,
        amount_at_risk=failed_transaction.amount,
        reason="card_declined",
        status=RecoveryStatus.DETECTED,
    )
