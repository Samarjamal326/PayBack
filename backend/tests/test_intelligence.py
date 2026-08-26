"""
Tests for Phase 3 Context Engine, Recoverability Classifier, Action Scoring, and Explanation.
"""
import pytest

from app.core.action_scoring import ActionScorer
from app.core.decision import DecisionEngine, evaluate
from app.core.explanation import ExplanationEngine
from app.core.probability import RecoveryContext, recovery_context_from_domain
from app.core.recoverability import RecoverabilityClassifier
from app.models.domain import (
    Customer,
    PaymentMethod,
    Policy,
    RecoverabilityCategory,
    RecoveryAction,
    RecoveryCase,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)


def test_recoverability_classification_opt_out():
    classifier = RecoverabilityClassifier()
    ctx = RecoveryContext(
        amount=500.0,
        payment_method_raw="card",
        failure_reason_raw="network_error",
        opted_out=True,
    )

    category, reason = classifier.classify(ctx)
    assert category == RecoverabilityCategory.NON_RECOVERABLE
    assert "opted out" in reason.lower()


def test_recoverability_classification_highly_recoverable():
    classifier = RecoverabilityClassifier()
    ctx = RecoveryContext(
        amount=1200.0,
        payment_method_raw="card",
        failure_reason_raw="gateway_timeout",
        opted_out=False,
        previous_transactions=5.0,
        historical_success_rate=0.80,
    )

    category, _ = classifier.classify(ctx)
    assert category == RecoverabilityCategory.HIGHLY_RECOVERABLE


def test_action_scorer_computes_expected_value():
    scorer = ActionScorer()
    ctx = RecoveryContext(
        amount=1000.0,
        payment_method_raw="card",
        failure_reason_raw="network_error",
        opted_out=False,
        previous_transactions=3.0,
        historical_success_rate=0.80,
    )
    policy = Policy()

    candidates = scorer.generate_and_score_candidates(
        ctx=ctx,
        policy=policy,
        category=RecoverabilityCategory.HIGHLY_RECOVERABLE,
        base_probability=0.80,
    )

    assert len(candidates) >= 5
    link_c = next(c for c in candidates if c.action == RecoveryAction.CREATE_PAYMENT_LINK)
    assert link_c.expected_value > 0.0
    expected_ev = round((link_c.probability * 1000.0) - link_c.cost, 2)
    assert link_c.expected_value == expected_ev


def test_decision_engine_explains_decision():
    cust = Customer(name="Priya Sharma", email="priya@example.com", phone="+919876543210")
    tx = Transaction(
        customer_id=cust.id,
        amount=2499.0,
        payment_method=PaymentMethod.CARD,
        status=TransactionStatus.FAILED,
        failure_reason="network_error",
    )
    case = RecoveryCase(
        transaction_id=tx.id,
        customer_id=cust.id,
        amount_at_risk=tx.amount,
        reason="network_error",
    )
    policy = Policy()

    result = evaluate(case, tx, cust, policy)
    assert result.decision.value in ("recover", "escalate", "stop")
    assert result.action in (RecoveryAction.CREATE_PAYMENT_LINK, RecoveryAction.RETRY_PAYMENT)
    assert result.expected_value > 0
    assert len(result.explanation_details) >= 3
