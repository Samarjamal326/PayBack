from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.core.probability import (
    RecoveryContext,
    RecoveryProbabilityModel,
    recovery_context_from_domain,
)
from app.models.domain import (
    Customer,
    EscalateReason,
    Policy,
    RecoveryAction,
    RecoveryCase,
    RecoveryDecision,
    StopReason,
    Transaction,
    TransactionStatus,
)
from app.repositories.interfaces import RecoveryCaseRepository, TransactionRepository


@dataclass(frozen=True)
class DecisionResult:
    decision: RecoveryDecision
    action: RecoveryAction
    reason: str
    stop_reason: StopReason | None = None
    escalate_reason: EscalateReason | None = None
    recovery_probability: float = 0.0


def _hours_since(dt: datetime) -> float:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600


def _get_default_probability_model() -> RecoveryProbabilityModel:
    """
    Lazy-initialization of the active production probability model (XGBoost).
    Marked experimental as training was synthetic-based.
    """
    from app.services.ml.xgboost_model import XGBoostRecoveryProbabilityModel
    return XGBoostRecoveryProbabilityModel()


def evaluate(
    case: RecoveryCase,
    transaction: Transaction,
    customer: Customer,
    policy: Policy,
    *,
    probability_model: Optional[RecoveryProbabilityModel] = None,
    transaction_repo: Optional[TransactionRepository] = None,
    case_repo: Optional[RecoveryCaseRepository] = None,
) -> DecisionResult:
    """
    Deterministic decision engine with ML-based recovery probability estimation.

    Evaluates hard stops, escalations, and non-recoverable checks in priority order.
    The recovery probability is computed via the RecoveryProbabilityModel abstraction
    (defaulting to the trained XGBoost model) using real customer-history signals.
    """

    # --- Hard stops (order matters) -----------------------------------------

    if customer.opted_out:
        return DecisionResult(
            decision=RecoveryDecision.STOP,
            action=RecoveryAction.STOP,
            reason="Customer has opted out of recovery communications.",
            stop_reason=StopReason.OPT_OUT,
        )

    window_hours = _hours_since(transaction.created_at)
    if window_hours > policy.recovery_window_hours:
        return DecisionResult(
            decision=RecoveryDecision.STOP,
            action=RecoveryAction.STOP,
            reason=f"Recovery window of {policy.recovery_window_hours}h has expired.",
            stop_reason=StopReason.WINDOW_EXPIRED,
        )

    if case.retry_count >= policy.maximum_retries:
        return DecisionResult(
            decision=RecoveryDecision.STOP,
            action=RecoveryAction.STOP,
            reason=f"Maximum retries ({policy.maximum_retries}) reached.",
            stop_reason=StopReason.MAX_RETRIES,
        )

    if case.message_count >= policy.maximum_messages:
        return DecisionResult(
            decision=RecoveryDecision.STOP,
            action=RecoveryAction.STOP,
            reason=f"Maximum messages ({policy.maximum_messages}) sent.",
            stop_reason=StopReason.MAX_MESSAGES,
        )

    if transaction.status == TransactionStatus.SUCCESS:
        return DecisionResult(
            decision=RecoveryDecision.STOP,
            action=RecoveryAction.STOP,
            reason="Transaction already succeeded — nothing to recover.",
            stop_reason=StopReason.NOT_RECOVERABLE,
        )

    # --- Compute probability via RecoveryProbabilityModel abstraction --------

    model = probability_model or _get_default_probability_model()
    context = recovery_context_from_domain(
        transaction=transaction,
        customer=customer,
        case=case,
        transaction_repo=transaction_repo,
        case_repo=case_repo,
    )
    prob = model.predict(context)

    # --- Escalations --------------------------------------------------------

    if transaction.amount >= policy.high_value_threshold:
        return DecisionResult(
            decision=RecoveryDecision.ESCALATE,
            action=RecoveryAction.ESCALATE,
            reason=f"Transaction amount {transaction.amount} exceeds high-value threshold "
                   f"{policy.high_value_threshold}. Human approval required.",
            escalate_reason=EscalateReason.HIGH_VALUE,
            recovery_probability=prob,
        )

    if policy.human_approval_required:
        return DecisionResult(
            decision=RecoveryDecision.ESCALATE,
            action=RecoveryAction.ESCALATE,
            reason="Merchant policy requires human approval before recovery.",
            escalate_reason=EscalateReason.POLICY_REQUIRES_APPROVAL,
            recovery_probability=prob,
        )

    # --- Non-recoverable statuses -------------------------------------------

    if transaction.status not in (TransactionStatus.FAILED, TransactionStatus.ABANDONED, TransactionStatus.PENDING):
        return DecisionResult(
            decision=RecoveryDecision.STOP,
            action=RecoveryAction.STOP,
            reason=f"Transaction status {transaction.status!r} is not a recovery candidate.",
            stop_reason=StopReason.NOT_RECOVERABLE,
        )

    # --- Recover ------------------------------------------------------------

    action = _select_action(transaction)

    return DecisionResult(
        decision=RecoveryDecision.RECOVER,
        action=action,
        reason=f"Failed/abandoned payment with estimated recovery probability {prob:.0%}.",
        recovery_probability=prob,
    )


def _select_action(transaction: Transaction) -> RecoveryAction:
    """Choose the most appropriate initial action based on transaction context."""
    if transaction.status == TransactionStatus.FAILED:
        return RecoveryAction.CREATE_PAYMENT_LINK
    if transaction.status == TransactionStatus.ABANDONED:
        return RecoveryAction.SEND_WHATSAPP
    return RecoveryAction.RETRY_PAYMENT

