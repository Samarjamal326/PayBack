"""
Tests for Synthetic Dataset Generator and Strategy Evaluator benchmark.
"""
from app.evaluation.evaluator import StrategyEvaluator
from app.evaluation.simulator import OutcomeSimulator
from app.evaluation.strategies import BaselineRetryStrategy, PayBackIntelligentStrategy
from app.evaluation.synthetic import SyntheticDataGenerator
from app.models.domain import RecoveryAction


def test_synthetic_generator_is_deterministic_with_seed():
    gen1 = SyntheticDataGenerator(seed=123)
    data1 = gen1.generate_dataset(size=20)

    gen2 = SyntheticDataGenerator(seed=123)
    data2 = gen2.generate_dataset(size=20)

    assert len(data1) == 20
    assert len(data2) == 20
    assert data1[0].context.amount == data2[0].context.amount
    assert data1[0].customer.name == data2[0].customer.name


def test_outcome_simulator_deterministic_results():
    gen = SyntheticDataGenerator(seed=42)
    case = gen.generate_dataset(size=1)[0]

    sim1 = OutcomeSimulator(seed=100)
    out1 = sim1.simulate_outcome(case, RecoveryAction.CREATE_PAYMENT_LINK, cost=5.0)

    sim2 = OutcomeSimulator(seed=100)
    out2 = sim2.simulate_outcome(case, RecoveryAction.CREATE_PAYMENT_LINK, cost=5.0)

    assert out1.success == out2.success
    assert out1.amount_recovered == out2.amount_recovered
    assert out1.action_cost == out2.action_cost


def test_strategy_evaluator_comparison():
    evaluator = StrategyEvaluator()
    report = evaluator.compare(dataset_size=50, seed=42)

    assert report.total_cases == 50
    assert report.amount_at_risk > 0
    assert report.baseline.total_cases == 50
    assert report.payback.total_cases == 50
    # PayBack should have fewer or equal unnecessary interventions than baseline
    assert report.payback.unnecessary_interventions <= report.baseline.unnecessary_interventions
