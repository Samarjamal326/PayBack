from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.models.domain import Customer
from app.repositories.interfaces import RecoveryCaseRepository, TransactionRepository


@dataclass(frozen=True)
class CustomerHistory:
    """
    Structured customer-history features extracted from real PayBack repositories.
    """

    customer_tenure_days: float
    previous_transactions: float
    historical_success_rate: float
    previous_failures: float
    previous_recoveries: float
    prior_recovery_rate: float
    customer_history_strength: float


def compute_customer_history(
    customer: Customer,
    reference_dt: datetime,
    transaction_repo: Optional[TransactionRepository] = None,
    case_repo: Optional[RecoveryCaseRepository] = None,
) -> CustomerHistory:
    """
    Computes real customer history features for ML feature extraction.

    Calculates:
      1. customer_tenure_days: max((reference_dt - customer.created_at).total_seconds() / 86400.0, 0.0)
      2. previous_transactions: count of transactions for customer before reference_dt
      3. historical_success_rate: previous_successful / previous_transactions if previous_transactions > 0 else 0.0
      4. previous_failures: count of failed transactions for customer before reference_dt
      5. previous_recoveries: count of recovered cases for customer before reference_dt
      6. prior_recovery_rate: previous_recoveries / (previous_failures + previous_recoveries) if denom > 0 else 0.0
      7. customer_history_strength: min(max(log1p(previous_transactions) / log1p(40), 0.0), 1.0)

    Enforces temporal correctness: only events strictly prior to `reference_dt` are counted.
    """
    # 1. Customer tenure
    ref_tz = reference_dt if reference_dt.tzinfo is not None else reference_dt.replace(tzinfo=timezone.utc)
    cust_tz = customer.created_at if customer.created_at.tzinfo is not None else customer.created_at.replace(tzinfo=timezone.utc)
    tenure_days = max((ref_tz - cust_tz).total_seconds() / 86400.0, 0.0)

    # Repository queries
    prev_txns = 0
    prev_success = 0
    prev_failures = 0
    prev_recoveries = 0

    if transaction_repo is not None:
        prev_txns = transaction_repo.count_by_customer_before(customer.id, ref_tz)
        prev_success = transaction_repo.count_successful_by_customer_before(customer.id, ref_tz)
        prev_failures = transaction_repo.count_failed_by_customer_before(customer.id, ref_tz)

    if case_repo is not None:
        prev_recoveries = case_repo.count_recovered_by_customer_before(customer.id, ref_tz)

    # 2. historical_success_rate
    if prev_txns > 0:
        hist_success_rate = min(max(float(prev_success) / float(prev_txns), 0.0), 1.0)
    else:
        hist_success_rate = 0.0

    # 3. prior_recovery_rate
    denom = prev_failures + prev_recoveries
    if denom > 0:
        prior_rec_rate = min(max(float(prev_recoveries) / float(denom), 0.0), 1.0)
    else:
        prior_rec_rate = 0.0

    # 4. customer_history_strength
    strength = math.log1p(float(prev_txns)) / math.log1p(40.0)
    history_strength = min(max(strength, 0.0), 1.0)

    return CustomerHistory(
        customer_tenure_days=round(tenure_days, 4),
        previous_transactions=float(prev_txns),
        historical_success_rate=round(hist_success_rate, 4),
        previous_failures=float(prev_failures),
        previous_recoveries=float(prev_recoveries),
        prior_recovery_rate=round(prior_rec_rate, 4),
        customer_history_strength=round(history_strength, 4),
    )


class CustomerHistoryService:
    """
    Isolated service to query and build CustomerHistory objects given customer ID and context.
    """

    def __init__(
        self,
        transaction_repo: Optional[TransactionRepository] = None,
        case_repo: Optional[RecoveryCaseRepository] = None,
    ) -> None:
        self.transaction_repo = transaction_repo
        self.case_repo = case_repo

    def get_history(
        self,
        customer: Customer,
        reference_dt: datetime,
    ) -> CustomerHistory:
        return compute_customer_history(
            customer=customer,
            reference_dt=reference_dt,
            transaction_repo=self.transaction_repo,
            case_repo=self.case_repo,
        )
