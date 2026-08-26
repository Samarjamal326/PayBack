"""
Benchmark Evaluator: Runs Baseline vs PayBack Strategy on Synthetic Dataset.
Produces reproducible comparison metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.evaluation.simulator import OutcomeSimulator
from app.evaluation.strategies import (
    BaselineRetryStrategy,
    PayBackIntelligentStrategy,
    Strategy,
)
from app.evaluation.synthetic import SyntheticCase, SyntheticDataGenerator
from app.models.domain import RecoveryAction


@dataclass
class StrategyMetrics:
    strategy_name: str
    total_cases: int
    amount_at_risk: float
    amount_recovered: float
    total_action_costs: float
    net_revenue_recovered: float
    recovery_rate: float
    recovery_percentage: float
    stop_count: int
    stop_rate: float
    escalation_count: int
    escalation_rate: float
    unnecessary_interventions: int
    unnecessary_intervention_rate: float


@dataclass
class ComparisonReport:
    total_cases: int
    amount_at_risk: float
    baseline: StrategyMetrics
    payback: StrategyMetrics
    absolute_improvement: float
    percentage_improvement: float
    cost_savings: float


class StrategyEvaluator:
    """
    Runs deterministic evaluation runs comparing strategies.
    """

    def evaluate_strategy(
        self,
        strategy: Strategy,
        dataset: List[SyntheticCase],
        seed: int = 42,
    ) -> StrategyMetrics:
        simulator = OutcomeSimulator(seed=seed)

        total_cases = len(dataset)
        amount_at_risk = sum(c.context.amount for c in dataset)

        recovered_total = 0.0
        total_costs = 0.0
        success_count = 0
        stop_count = 0
        esc_count = 0
        unnecessary_interventions = 0

        for case in dataset:
            action, cost, _ = strategy.decide(case)
            total_costs += cost

            if action == RecoveryAction.STOP:
                stop_count += 1
            elif action == RecoveryAction.ESCALATE:
                esc_count += 1

            # Check for unnecessary intervention (contacting a customer with 0 intent / permanent decline)
            if not case.ground_truth_will_pay_if_prompted and action != RecoveryAction.STOP:
                unnecessary_interventions += 1

            outcome = simulator.simulate_outcome(case, action, cost)
            if outcome.success:
                success_count += 1
                recovered_total += outcome.amount_recovered

        rec_rate = (success_count / total_cases) if total_cases > 0 else 0.0
        rec_pct = (recovered_total / amount_at_risk) if amount_at_risk > 0 else 0.0
        stop_rate = (stop_count / total_cases) if total_cases > 0 else 0.0
        esc_rate = (esc_count / total_cases) if total_cases > 0 else 0.0
        unnec_rate = (unnecessary_interventions / total_cases) if total_cases > 0 else 0.0

        return StrategyMetrics(
            strategy_name=strategy.name,
            total_cases=total_cases,
            amount_at_risk=round(amount_at_risk, 2),
            amount_recovered=round(recovered_total, 2),
            total_action_costs=round(total_costs, 2),
            net_revenue_recovered=round(recovered_total - total_costs, 2),
            recovery_rate=round(rec_rate, 4),
            recovery_percentage=round(rec_pct, 4),
            stop_count=stop_count,
            stop_rate=round(stop_rate, 4),
            escalation_count=esc_count,
            escalation_rate=round(esc_rate, 4),
            unnecessary_interventions=unnecessary_interventions,
            unnecessary_intervention_rate=round(unnec_rate, 4),
        )

    def compare(
        self,
        dataset_size: int = 1000,
        seed: int = 42,
    ) -> ComparisonReport:
        generator = SyntheticDataGenerator(seed=seed)
        dataset = generator.generate_dataset(size=dataset_size)

        baseline_strat = BaselineRetryStrategy()
        payback_strat = PayBackIntelligentStrategy()

        baseline_metrics = self.evaluate_strategy(baseline_strat, dataset, seed=seed)
        payback_metrics = self.evaluate_strategy(payback_strat, dataset, seed=seed)

        abs_imp = payback_metrics.net_revenue_recovered - baseline_metrics.net_revenue_recovered
        pct_imp = (
            (abs_imp / baseline_metrics.net_revenue_recovered * 100.0)
            if baseline_metrics.net_revenue_recovered > 0
            else 0.0
        )
        cost_savings = baseline_metrics.total_action_costs - payback_metrics.total_action_costs

        return ComparisonReport(
            total_cases=dataset_size,
            amount_at_risk=baseline_metrics.amount_at_risk,
            baseline=baseline_metrics,
            payback=payback_metrics,
            absolute_improvement=round(abs_imp, 2),
            percentage_improvement=round(pct_imp, 2),
            cost_savings=round(cost_savings, 2),
        )
