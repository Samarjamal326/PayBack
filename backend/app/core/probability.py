"""
RecoveryProbabilityModel — abstract interface for recovery probability estimation.

This module defines the protocol that all probability models must satisfy,
keeping the rest of PayBack decoupled from any specific implementation.

Current implementations:
  - XGBoostRecoveryProbabilityModel  (trained XGBoost + calibration)

Future implementations might include:
  - HeuristicRecoveryProbabilityModel
  - EnsembleRecoveryProbabilityModel
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from app.models.domain import Customer, RecoveryCase, Transaction
from app.repositories.interfaces import RecoveryCaseRepository, TransactionRepository


@dataclass(frozen=True)
class RecoveryContext:
    """
    Structured snapshot of all available information at decision time.
    This is the single input object passed to RecoveryProbabilityModel.

    Derived from domain objects:
      - Transaction  (amount, payment_method, status, failure_reason)
      - Customer     (opted_out, created_at -> customer_tenure_days)
      - RecoveryCase (retry_count, message_count, created_at, amount_at_risk)
      - CustomerHistory (previous_transactions, historical_success_rate, previous_failures, previous_recoveries, prior_recovery_rate, customer_history_strength)

    `checkout_intent_score` remains an explicitly documented development placeholder (0.5)
    as PayBack does not currently capture checkout intent telemetry.
    """

    # -----------------------------------------------------------------------
    # From Transaction
    # -----------------------------------------------------------------------
    amount: float
    """Transaction amount in INR (or configured currency)."""

    payment_method_raw: str
    """Raw payment method string from PaymentMethod enum (e.g. 'net_banking')."""

    failure_reason_raw: str
    """Raw failure_reason string from Transaction (free text or structured code)."""

    # -----------------------------------------------------------------------
    # From RecoveryCase
    # -----------------------------------------------------------------------
    retry_count: int = 0
    """Number of recovery retries already attempted."""

    messages_sent: int = 0
    """Number of recovery messages already sent (message_count on RecoveryCase)."""

    # -----------------------------------------------------------------------
    # From Customer
    # -----------------------------------------------------------------------
    opted_out: bool = False
    """Whether the customer has opted out of recovery communications."""

    customer_tenure_days: float = 0.0
    """Days since customer account was created (derived from Customer.created_at)."""

    # -----------------------------------------------------------------------
    # Real Customer History Features
    # -----------------------------------------------------------------------
    previous_transactions: float = 0.0
    """Total historical transaction count for this customer before current transaction."""

    historical_success_rate: float = 0.0
    """Fraction of past transactions that succeeded [0, 1]. 0.0 when no history."""

    previous_failures: float = 0.0
    """Number of previous failed transactions before current transaction."""

    previous_recoveries: float = 0.0
    """Number of previously recovered transactions before current transaction."""

    prior_recovery_rate: Optional[float] = None
    """Fraction of prior recovery cases recovered. Derived if None."""

    customer_history_strength: Optional[float] = None
    """Log-scaled customer history strength. Derived if None."""

    days_since_failure: float = 0.0
    """Days elapsed since the failing transaction."""

    # -----------------------------------------------------------------------
    # Documented Development Placeholder
    # -----------------------------------------------------------------------
    checkout_intent_score: float = 0.5
    """
    DOCUMENTED PLACEHOLDER: Normalised checkout intent score [0, 1].
    Currently not captured by PayBack/Razorpay data pipeline.
    """


@runtime_checkable
class RecoveryProbabilityModel(Protocol):
    """
    Protocol that all recovery probability models must satisfy.

    Implementations must be:
      - Deterministic: identical inputs → identical output
      - Self-contained: no DB, API, or external calls
      - Range-bounded: returned probability ∈ [0.0, 1.0]
    """

    def predict(self, context: RecoveryContext) -> float:
        """
        Returns the estimated probability of successful recovery given the context.

        Args:
            context: Structured recovery context at decision time.

        Returns:
            float in [0.0, 1.0].
        """
        ...


def recovery_context_from_domain(
    transaction: Transaction,
    customer: Customer,
    case: RecoveryCase,
    *,
    transaction_repo: Optional[TransactionRepository] = None,
    case_repo: Optional[RecoveryCaseRepository] = None,
) -> RecoveryContext:
    """
    Constructs a RecoveryContext from the domain objects and queries customer history
    from repositories if provided.

    Enforces temporal correctness: counts only historical transactions/recoveries
    strictly before the current transaction.created_at.
    """
    from datetime import datetime, timezone
    from app.services.ml.customer_history import compute_customer_history

    now = datetime.now(timezone.utc)
    tx_created = transaction.created_at
    if tx_created.tzinfo is None:
        tx_created = tx_created.replace(tzinfo=timezone.utc)
    days_since = max((now - tx_created).total_seconds() / 86400.0, 0.0)

    # Compute real customer history features
    history = compute_customer_history(
        customer=customer,
        reference_dt=tx_created,
        transaction_repo=transaction_repo,
        case_repo=case_repo,
    )

    return RecoveryContext(
        amount=float(transaction.amount),
        payment_method_raw=transaction.payment_method.value,
        failure_reason_raw=transaction.failure_reason or "",
        retry_count=int(case.retry_count),
        messages_sent=int(case.message_count),
        opted_out=bool(customer.opted_out),
        customer_tenure_days=history.customer_tenure_days,
        days_since_failure=round(days_since, 4),
        previous_transactions=history.previous_transactions,
        historical_success_rate=history.historical_success_rate,
        previous_failures=history.previous_failures,
        previous_recoveries=history.previous_recoveries,
        prior_recovery_rate=history.prior_recovery_rate,
        customer_history_strength=history.customer_history_strength,
        checkout_intent_score=0.5,  # Explicit documented placeholder
    )

