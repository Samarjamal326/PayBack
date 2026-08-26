"""
Outcome Simulator for PayBack recovery actions.
Simulates deterministic ground-truth outcomes given action selection and customer intent.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict

from app.evaluation.synthetic import SyntheticCase
from app.models.domain import RecoveryAction


@dataclass
class SimulationOutcome:
    success: bool
    amount_recovered: float
    action_cost: float
    net_recovery: float


class OutcomeSimulator:
    """
    Simulates recovery results based on chosen actions and ground-truth probabilities.
    """

    # Configurable channel conversion rates given customer willingness
    DEFAULT_CHANNEL_EFFICIENCY: Dict[RecoveryAction, float] = {
        RecoveryAction.CREATE_PAYMENT_LINK: 0.85,
        RecoveryAction.SEND_WHATSAPP: 0.75,
        RecoveryAction.RETRY_PAYMENT: 0.70,
        RecoveryAction.SEND_EMAIL: 0.55,
        RecoveryAction.ESCALATE: 0.80,
        RecoveryAction.STOP: 0.00,
    }

    def __init__(
        self,
        seed: int = 42,
        channel_efficiency: Dict[RecoveryAction, float] | None = None,
    ) -> None:
        self.rng = random.Random(seed)
        self.channel_efficiency = channel_efficiency or self.DEFAULT_CHANNEL_EFFICIENCY

    def simulate_outcome(
        self,
        case: SyntheticCase,
        action: RecoveryAction,
        cost: float = 0.0,
    ) -> SimulationOutcome:
        """
        Calculates whether the selected action recovers revenue.
        """
        amount = case.context.amount

        # 1. Stopping recovers 0 and costs 0
        if action in (RecoveryAction.STOP,):
            return SimulationOutcome(
                success=False,
                amount_recovered=0.0,
                action_cost=cost,
                net_recovery=-cost,
            )

        # 2. If customer has zero intent/opted out/permanent failure, recovery fails
        if not case.ground_truth_will_pay_if_prompted:
            return SimulationOutcome(
                success=False,
                amount_recovered=0.0,
                action_cost=cost,
                net_recovery=-cost,
            )

        # 3. Channel conversion efficiency check
        efficiency = self.channel_efficiency.get(action, 0.60)
        roll = self.rng.random()

        if roll < efficiency:
            return SimulationOutcome(
                success=True,
                amount_recovered=amount,
                action_cost=cost,
                net_recovery=amount - cost,
            )

        return SimulationOutcome(
            success=False,
            amount_recovered=0.0,
            action_cost=cost,
            net_recovery=-cost,
        )
