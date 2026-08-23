"""
Tests for the recovery state machine.
"""
from __future__ import annotations

import pytest

from app.core.state_machine import InvalidTransitionError, assert_transition, can_transition
from app.models.domain import RecoveryStatus


class TestValidTransitions:
    def test_detected_to_analyzing(self):
        assert_transition(RecoveryStatus.DETECTED, RecoveryStatus.ANALYZING)

    def test_analyzing_to_eligibility(self):
        assert_transition(RecoveryStatus.ANALYZING, RecoveryStatus.ELIGIBILITY_CHECK)

    def test_eligibility_to_decision(self):
        assert_transition(RecoveryStatus.ELIGIBILITY_CHECK, RecoveryStatus.DECISION)

    def test_eligibility_can_stop(self):
        assert_transition(RecoveryStatus.ELIGIBILITY_CHECK, RecoveryStatus.STOPPED)

    def test_decision_to_action_pending(self):
        assert_transition(RecoveryStatus.DECISION, RecoveryStatus.ACTION_PENDING)

    def test_decision_to_escalated(self):
        assert_transition(RecoveryStatus.DECISION, RecoveryStatus.ESCALATED)

    def test_decision_to_stopped(self):
        assert_transition(RecoveryStatus.DECISION, RecoveryStatus.STOPPED)

    def test_monitoring_retry_loop(self):
        assert_transition(RecoveryStatus.MONITORING, RecoveryStatus.ACTION_PENDING)


class TestInvalidTransitions:
    def test_cannot_go_backward(self):
        with pytest.raises(InvalidTransitionError):
            assert_transition(RecoveryStatus.DECISION, RecoveryStatus.DETECTED)

    def test_terminal_state_recovered_has_no_exit(self):
        with pytest.raises(InvalidTransitionError):
            assert_transition(RecoveryStatus.RECOVERED, RecoveryStatus.ANALYZING)

    def test_terminal_state_stopped_has_no_exit(self):
        with pytest.raises(InvalidTransitionError):
            assert_transition(RecoveryStatus.STOPPED, RecoveryStatus.ACTION_PENDING)

    def test_terminal_state_escalated_has_no_exit(self):
        with pytest.raises(InvalidTransitionError):
            assert_transition(RecoveryStatus.ESCALATED, RecoveryStatus.DECISION)

    def test_cannot_skip_states(self):
        with pytest.raises(InvalidTransitionError):
            assert_transition(RecoveryStatus.DETECTED, RecoveryStatus.DECISION)


class TestCanTransition:
    def test_returns_true_for_valid(self):
        assert can_transition(RecoveryStatus.DETECTED, RecoveryStatus.ANALYZING) is True

    def test_returns_false_for_invalid(self):
        assert can_transition(RecoveryStatus.STOPPED, RecoveryStatus.ANALYZING) is False
