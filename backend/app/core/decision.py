from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.domain import (
    EscalateReason,
    Policy,
    RecoveryAction,
    RecoveryCase,
    RecoveryDecision,
    StopReason,
    Transaction,
    TransactionStatus,
    Customer,
)


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


def evaluate(
    case: RecoveryCase,
    transaction: Transaction,
    customer: Customer,
    policy: Policy,
) -> DecisionResult:
    """
    Deterministic decision engine.

    Evaluates every stop/escalate/recover condition in priority order.
    The LLM never touches this logic.
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

    # --- Escalations --------------------------------------------------------

    if transaction.amount >= policy.high_value_threshold:
        return DecisionResult(
            decision=RecoveryDecision.ESCALATE,
            action=RecoveryAction.ESCALATE,
            reason=f"Transaction amount {transaction.amount} exceeds high-value threshold "
                   f"{policy.high_value_threshold}. Human approval required.",
            escalate_reason=EscalateReason.HIGH_VALUE,
            recovery_probability=_estimate_probability(transaction),
        )

    if policy.human_approval_required:
        return DecisionResult(
            decision=RecoveryDecision.ESCALATE,
            action=RecoveryAction.ESCALATE,
            reason="Merchant policy requires human approval before recovery.",
            escalate_reason=EscalateReason.POLICY_REQUIRES_APPROVAL,
            recovery_probability=_estimate_probability(transaction),
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

    prob = _estimate_probability(transaction)
    action = _select_action(transaction)

    return DecisionResult(
        decision=RecoveryDecision.RECOVER,
        action=action,
        reason=f"Failed/abandoned payment with estimated recovery probability {prob:.0%}.",
        recovery_probability=prob,
    )


def _estimate_probability(transaction: Transaction) -> float:
    """
    Placeholder deterministic probability estimate.
    Future: replaced by ML model prediction.
    """
    if transaction.status == TransactionStatus.FAILED:
        return 0.70
    if transaction.status == TransactionStatus.ABANDONED:
        return 0.45
    if transaction.status == TransactionStatus.PENDING:
        return 0.60
    return 0.10


def _select_action(transaction: Transaction) -> RecoveryAction:
    """Choose the most appropriate initial action based on transaction context."""
    if transaction.status == TransactionStatus.FAILED:
        return RecoveryAction.CREATE_PAYMENT_LINK
    if transaction.status == TransactionStatus.ABANDONED:
        return RecoveryAction.SEND_WHATSAPP
    return RecoveryAction.RETRY_PAYMENT
