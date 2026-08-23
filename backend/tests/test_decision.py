"""
Tests for the deterministic decision engine.
Verifies business rules independent of FastAPI, LangGraph, or the LLM.
"""
from __future__ import annotations

import pytest

from app.core.decision import evaluate
from app.models.domain import (
    Customer,
    Policy,
    RecoveryAction,
    RecoveryCase,
    RecoveryDecision,
    RecoveryStatus,
    StopReason,
    Transaction,
    TransactionStatus,
)


def _case(transaction: Transaction, customer: Customer) -> RecoveryCase:
    return RecoveryCase(
        transaction_id=transaction.id,
        customer_id=customer.id,
        amount_at_risk=transaction.amount,
        reason="test",
        status=RecoveryStatus.DETECTED,
    )


class TestRecover:
    def test_failed_payment_enters_recovery(self, failed_transaction, active_customer, default_policy):
        case = _case(failed_transaction, active_customer)
        result = evaluate(case, failed_transaction, active_customer, default_policy)

        assert result.decision == RecoveryDecision.RECOVER
        assert result.action == RecoveryAction.CREATE_PAYMENT_LINK
        assert result.recovery_probability > 0

    def test_abandoned_checkout_enters_recovery(self, abandoned_transaction, active_customer, default_policy):
        case = _case(abandoned_transaction, active_customer)
        result = evaluate(case, abandoned_transaction, active_customer, default_policy)

        assert result.decision == RecoveryDecision.RECOVER
        assert result.action == RecoveryAction.SEND_WHATSAPP

    def test_same_input_same_decision(self, failed_transaction, active_customer, default_policy):
        case = _case(failed_transaction, active_customer)
        r1 = evaluate(case, failed_transaction, active_customer, default_policy)
        r2 = evaluate(case, failed_transaction, active_customer, default_policy)
        assert r1.decision == r2.decision
        assert r1.recovery_probability == r2.recovery_probability


class TestStop:
    def test_opted_out_customer_is_stopped(self, failed_transaction, opted_out_customer, default_policy):
        case = _case(failed_transaction, opted_out_customer)
        result = evaluate(case, failed_transaction, opted_out_customer, default_policy)

        assert result.decision == RecoveryDecision.STOP
        assert result.stop_reason == StopReason.OPT_OUT

    def test_max_retries_stops_recovery(self, failed_transaction, active_customer, default_policy):
        case = _case(failed_transaction, active_customer)
        case = case.model_copy(update={"retry_count": default_policy.maximum_retries})
        result = evaluate(case, failed_transaction, active_customer, default_policy)

        assert result.decision == RecoveryDecision.STOP
        assert result.stop_reason == StopReason.MAX_RETRIES

    def test_max_messages_stops_recovery(self, failed_transaction, active_customer, default_policy):
        case = _case(failed_transaction, active_customer)
        case = case.model_copy(update={"message_count": default_policy.maximum_messages})
        result = evaluate(case, failed_transaction, active_customer, default_policy)

        assert result.decision == RecoveryDecision.STOP
        assert result.stop_reason == StopReason.MAX_MESSAGES

    def test_successful_transaction_not_recoverable(self, active_customer, default_policy):
        tx = Transaction(
            customer_id=active_customer.id,
            amount=500.0,
            status=TransactionStatus.SUCCESS,
        )
        case = _case(tx, active_customer)
        result = evaluate(case, tx, active_customer, default_policy)

        assert result.decision == RecoveryDecision.STOP
        assert result.stop_reason == StopReason.NOT_RECOVERABLE

    def test_recovery_window_expired(self, active_customer, default_policy):
        from datetime import datetime, timezone, timedelta
        old_tx = Transaction(
            customer_id=active_customer.id,
            amount=1_000.0,
            status=TransactionStatus.FAILED,
            failure_reason="bank_error",
            created_at=datetime.now(timezone.utc) - timedelta(hours=100),
        )
        case = _case(old_tx, active_customer)
        result = evaluate(case, old_tx, active_customer, default_policy)

        assert result.decision == RecoveryDecision.STOP
        assert result.stop_reason == StopReason.WINDOW_EXPIRED


class TestEscalate:
    def test_high_value_transaction_escalates(self, high_value_transaction, active_customer, default_policy):
        case = _case(high_value_transaction, active_customer)
        result = evaluate(case, high_value_transaction, active_customer, default_policy)

        assert result.decision == RecoveryDecision.ESCALATE

    def test_human_approval_required_escalates(self, failed_transaction, active_customer):
        policy = Policy(human_approval_required=True)
        case = _case(failed_transaction, active_customer)
        result = evaluate(case, failed_transaction, active_customer, policy)

        assert result.decision == RecoveryDecision.ESCALATE

    def test_opted_out_takes_priority_over_escalation(self, high_value_transaction, opted_out_customer, default_policy):
        """Opt-out is always evaluated before escalation rules."""
        case = _case(high_value_transaction, opted_out_customer)
        result = evaluate(case, high_value_transaction, opted_out_customer, default_policy)

        assert result.decision == RecoveryDecision.STOP
        assert result.stop_reason == StopReason.OPT_OUT
