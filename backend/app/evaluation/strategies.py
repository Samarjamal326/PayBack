"""
Recovery Strategies for benchmarking: Baseline vs Rule-Based vs PayBack Intelligent Strategy.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

from app.core.decision import DecisionEngine
from app.evaluation.synthetic import SyntheticCase
from app.models.domain import RecoveryAction


class Strategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def decide(self, case: SyntheticCase) -> Tuple[RecoveryAction, float, str]:
        """
        Returns (selected_action, estimated_cost, reason).
        """
        raise NotImplementedError


class BaselineRetryStrategy(Strategy):
    """
    Baseline Strategy: Blindly retry every payment once, regardless of context.
    """

    @property
    def name(self) -> str:
        return "BASELINE (Retry All)"

    def decide(self, case: SyntheticCase) -> Tuple[RecoveryAction, float, str]:
        if case.context.opted_out:
            return RecoveryAction.STOP, 0.0, "Customer opted out."

        cost = case.policy.action_costs.get(RecoveryAction.RETRY_PAYMENT.value, 2.0)
        return RecoveryAction.RETRY_PAYMENT, cost, "Baseline: retry all failed payments."


class RuleBasedStrategy(Strategy):
    """
    Rule-Based Strategy: Static heuristic without expected value optimization.
    """

    @property
    def name(self) -> str:
        return "RULE_BASED (Static)"

    def decide(self, case: SyntheticCase) -> Tuple[RecoveryAction, float, str]:
        ctx = case.context
        if ctx.opted_out:
            return RecoveryAction.STOP, 0.0, "Customer opted out."

        if ctx.transaction_status == "abandoned":
            cost = case.policy.action_costs.get(RecoveryAction.SEND_WHATSAPP.value, 1.0)
            return RecoveryAction.SEND_WHATSAPP, cost, "Abandoned checkout message."

        if ctx.payment_method_raw in ("card", "net_banking"):
            cost = case.policy.action_costs.get(RecoveryAction.RETRY_PAYMENT.value, 2.0)
            return RecoveryAction.RETRY_PAYMENT, cost, "Retry card/netbanking payment."

        cost = case.policy.action_costs.get(RecoveryAction.CREATE_PAYMENT_LINK.value, 5.0)
        return RecoveryAction.CREATE_PAYMENT_LINK, cost, "Generate payment link."


class PayBackIntelligentStrategy(Strategy):
    """
    PayBack Intelligent Strategy: Context Engine + XGBoost ML Probability + EV Maximization + Guardrails.
    """

    def __init__(self) -> None:
        self.engine = DecisionEngine()

    @property
    def name(self) -> str:
        return "PAYBACK (Context + ML + EV Intelligence)"

    def decide(self, case: SyntheticCase) -> Tuple[RecoveryAction, float, str]:
        decision = self.engine.evaluate_context(
            context=case.context,
            customer=case.customer,
            policy=case.policy,
            transaction=case.transaction,
        )
        action = decision.selected_action
        cost = case.policy.action_costs.get(action.value, 0.0)
        return action, cost, decision.reason
