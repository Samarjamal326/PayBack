from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.action_scoring import ActionScorer
from app.core.explanation import ExplanationEngine
from app.core.probability import (
    RecoveryContext,
    RecoveryProbabilityModel,
    recovery_context_from_domain,
)
from app.core.recoverability import RecoverabilityClassifier
from app.models.domain import (
    ActionCandidate,
    Customer,
    DecisionRecord,
    EscalateReason,
    Policy,
    RecoverabilityCategory,
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
    recoverability: RecoverabilityCategory = RecoverabilityCategory.LIKELY_RECOVERABLE
    expected_value: float = 0.0
    candidates: list[ActionCandidate] = field(default_factory=list)
    explanation_details: list[str] = field(default_factory=list)


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


class DecisionEngine:
    """
    Full Phase 3 Decision Engine:
    Evaluates recovery context, calculates ML probability, scores candidate actions via EV,
    enforces policy rules/guardrails, and returns an explainable DecisionRecord.
    """

    def __init__(
        self,
        classifier: Optional[RecoverabilityClassifier] = None,
        probability_model: Optional[RecoveryProbabilityModel] = None,
        scorer: Optional[ActionScorer] = None,
        explainer: Optional[ExplanationEngine] = None,
    ) -> None:
        self.classifier = classifier or RecoverabilityClassifier()
        self.probability_model = probability_model
        self.scorer = scorer or ActionScorer()
        self.explainer = explainer or ExplanationEngine()

    def evaluate_context(
        self,
        context: RecoveryContext,
        customer: Customer,
        policy: Policy,
        transaction: Optional[Transaction] = None,
    ) -> DecisionRecord:
        """
        Executes full deterministic evaluation pipeline on a RecoveryContext.
        """
        # Step 1: Recoverability classification
        category, class_reason = self.classifier.classify(context)

        # Step 2: ML recovery probability estimation
        model = self.probability_model or _get_default_probability_model()
        prob = model.predict(context)

        # Step 3: Candidate action generation and expected-value scoring
        candidates = self.scorer.generate_and_score_candidates(
            ctx=context,
            policy=policy,
            category=category,
            base_probability=prob,
        )

        # Step 4: Guardrail check & action selection
        decision, action, stop_reason, esc_reason = self._select_best_action(
            ctx=context,
            policy=policy,
            category=category,
            candidates=candidates,
            transaction=transaction,
        )

        # Find chosen candidate or make fallback
        chosen_candidate = next((c for c in candidates if c.action == action), None)
        ev = chosen_candidate.expected_value if chosen_candidate else 0.0

        selected_dummy = chosen_candidate or ActionCandidate(
            action=action,
            probability=prob,
            expected_value=ev,
            cost=0.0,
            eligible=True,
        )

        # Step 5: Explainable decision generation
        summary_reason, details = self.explainer.build_explanation(
            ctx=context,
            customer=customer,
            policy=policy,
            category=category,
            probability=prob,
            selected=selected_dummy,
            candidates=candidates,
        )

        if stop_reason:
            summary_reason = f"Recovery stopped: {stop_reason.value}"
        elif esc_reason:
            summary_reason = f"Recovery escalated: {esc_reason.value}"

        return DecisionRecord(
            recoverability=category,
            recovery_probability=prob,
            selected_action=action,
            expected_value=ev,
            reason=summary_reason,
            decision=decision,
            stop_reason=stop_reason,
            escalate_reason=esc_reason,
            candidates=candidates,
            explanation_details=details,
        )

    def _select_best_action(
        self,
        ctx: RecoveryContext,
        policy: Policy,
        category: RecoverabilityCategory,
        candidates: list[ActionCandidate],
        transaction: Optional[Transaction] = None,
    ) -> tuple[RecoveryDecision, RecoveryAction, Optional[StopReason], Optional[EscalateReason]]:
        # Hard stops (order matters)
        if ctx.opted_out:
            return RecoveryDecision.STOP, RecoveryAction.STOP, StopReason.OPT_OUT, None

        if ctx.days_since_failure * 24.0 > policy.recovery_window_hours:
            return RecoveryDecision.STOP, RecoveryAction.STOP, StopReason.WINDOW_EXPIRED, None

        if ctx.retry_count >= policy.maximum_retries:
            return RecoveryDecision.STOP, RecoveryAction.STOP, StopReason.MAX_RETRIES, None

        if ctx.messages_sent >= policy.maximum_messages:
            return RecoveryDecision.STOP, RecoveryAction.STOP, StopReason.MAX_MESSAGES, None

        if transaction and transaction.status == TransactionStatus.SUCCESS:
            return RecoveryDecision.STOP, RecoveryAction.STOP, StopReason.NOT_RECOVERABLE, None

        if category == RecoverabilityCategory.NON_RECOVERABLE:
            return RecoveryDecision.STOP, RecoveryAction.STOP, StopReason.NOT_RECOVERABLE, None

        # Escalations
        if ctx.amount >= policy.high_value_threshold:
            return RecoveryDecision.ESCALATE, RecoveryAction.ESCALATE, None, EscalateReason.HIGH_VALUE

        if policy.human_approval_required:
            return RecoveryDecision.ESCALATE, RecoveryAction.ESCALATE, None, EscalateReason.POLICY_REQUIRES_APPROVAL

        # Non-recoverable statuses check
        if transaction and transaction.status not in (TransactionStatus.FAILED, TransactionStatus.ABANDONED, TransactionStatus.PENDING):
            return RecoveryDecision.STOP, RecoveryAction.STOP, StopReason.NOT_RECOVERABLE, None

        # Best action selection by EV ranking among eligible actions
        eligible = [c for c in candidates if c.eligible and c.action not in (RecoveryAction.STOP, RecoveryAction.ESCALATE)]
        if eligible:
            ranked = sorted(eligible, key=lambda c: (c.expected_value, c.probability), reverse=True)
            return RecoveryDecision.RECOVER, ranked[0].action, None, None

        # Fallback to direct heuristic selection if no candidate remained
        action = _select_action(transaction) if transaction else RecoveryAction.CREATE_PAYMENT_LINK
        return RecoveryDecision.RECOVER, action, None, None


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
    Deterministic decision engine with ML-based recovery probability estimation,
    recoverability classification, and expected-value candidate ranking.
    """

    context = recovery_context_from_domain(
        transaction=transaction,
        customer=customer,
        case=case,
        transaction_repo=transaction_repo,
        case_repo=case_repo,
    )

    engine = DecisionEngine(probability_model=probability_model)
    rec = engine.evaluate_context(
        context=context,
        customer=customer,
        policy=policy,
        transaction=transaction,
    )

    return DecisionResult(
        decision=rec.decision,
        action=rec.selected_action,
        reason=rec.reason,
        stop_reason=rec.stop_reason,
        escalate_reason=rec.escalate_reason,
        recovery_probability=rec.recovery_probability,
        recoverability=rec.recoverability,
        expected_value=rec.expected_value,
        candidates=rec.candidates,
        explanation_details=rec.explanation_details,
    )


def _select_action(transaction: Transaction) -> RecoveryAction:
    """Choose the most appropriate initial action based on transaction context."""
    if transaction.status == TransactionStatus.FAILED:
        return RecoveryAction.CREATE_PAYMENT_LINK
    if transaction.status == TransactionStatus.ABANDONED:
        return RecoveryAction.SEND_WHATSAPP
    return RecoveryAction.RETRY_PAYMENT


