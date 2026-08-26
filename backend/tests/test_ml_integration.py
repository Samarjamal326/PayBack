from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.services.ml.feature_adapter import (
    DEFAULT_FEATURE_SCHEMA_PATH,
    FeatureAdapter,
    RecoveryFeatures,
    extract_recovery_features,
)
from app.services.ml.xgboost_probability import (
    DEFAULT_CALIBRATION_PATH,
    DEFAULT_MODEL_PATH,
    CalibrationConfig,
    XGBoostRecoveryPredictor,
    get_recovery_predictor,
    safe_logit,
    sigmoid,
)


# ---------------------------------------------------------------------------
# 1. Artifact Loading Tests
# ---------------------------------------------------------------------------

def test_artifacts_exist():
    assert DEFAULT_MODEL_PATH.exists(), f"Missing model at {DEFAULT_MODEL_PATH}"
    assert DEFAULT_FEATURE_SCHEMA_PATH.exists(), f"Missing schema at {DEFAULT_FEATURE_SCHEMA_PATH}"
    assert DEFAULT_CALIBRATION_PATH.exists(), f"Missing calibration at {DEFAULT_CALIBRATION_PATH}"


def test_feature_adapter_initialization():
    adapter = FeatureAdapter()
    assert len(adapter.numeric_features) == 14
    assert len(adapter.categorical_features) == 2
    assert len(adapter.categories["payment_method"]) == 4
    assert len(adapter.categories["failure_type"]) == 6
    # Total features: 14 numeric + 4 payment_method + 6 failure_type = 24
    assert adapter.num_features == 24
    assert len(adapter.feature_names) == 24


def test_calibration_config_loading():
    config = CalibrationConfig.from_file()
    assert config.method == "sigmoid_on_logit"
    assert pytest.approx(config.coefficient, 1e-6) == 0.9540740845599085
    assert pytest.approx(config.intercept, 1e-6) == -0.01725399436142655


def test_predictor_initialization():
    predictor = XGBoostRecoveryPredictor()
    assert predictor.booster is not None
    assert predictor.feature_adapter.num_features == 24


def test_missing_artifacts_raise_error(tmp_path):
    non_existent = tmp_path / "non_existent.json"
    with pytest.raises(FileNotFoundError):
        FeatureAdapter(schema_path=non_existent)

    with pytest.raises(FileNotFoundError):
        CalibrationConfig.from_file(non_existent)

    with pytest.raises(FileNotFoundError):
        XGBoostRecoveryPredictor(model_path=non_existent)


# ---------------------------------------------------------------------------
# 2. Feature Ordering & Encoding Tests
# ---------------------------------------------------------------------------

def test_exact_feature_ordering():
    adapter = FeatureAdapter()
    expected_order = [
        "amount",
        "checkout_intent_score",
        "customer_tenure_days",
        "previous_transactions",
        "historical_success_rate",
        "previous_failures",
        "previous_recoveries",
        "days_since_failure",
        "retry_count",
        "messages_sent",
        "opted_out",
        "high_value",
        "prior_recovery_rate",
        "customer_history_strength",
        "payment_method_upi",
        "payment_method_card",
        "payment_method_netbanking",
        "payment_method_wallet",
        "failure_type_temporary_bank_error",
        "failure_type_timeout",
        "failure_type_insufficient_funds",
        "failure_type_expired_instrument",
        "failure_type_authentication_failure",
        "failure_type_unknown",
    ]
    assert adapter.feature_names == expected_order


def test_categorical_one_hot_encoding():
    adapter = FeatureAdapter()

    # Case 1: UPI and temporary_bank_error
    f1 = extract_recovery_features(
        amount=1500.0,
        checkout_intent_score=0.85,
        payment_method="upi",
        failure_type="temporary_bank_error",
    )
    vec1 = adapter.transform_single(f1)
    assert vec1.shape == (24,)
    # payment_method: upi=1, card=0, netbanking=0, wallet=0
    assert list(vec1[14:18]) == [1.0, 0.0, 0.0, 0.0]
    # failure_type: temporary_bank_error=1, timeout=0, insufficient_funds=0, expired_instrument=0, auth_fail=0, unknown=0
    assert list(vec1[18:24]) == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    # Case 2: card and authentication_failure
    f2 = extract_recovery_features(
        amount=2000.0,
        payment_method="card",
        failure_type="authentication_failure",
    )
    vec2 = adapter.transform_single(f2)
    assert list(vec2[14:18]) == [0.0, 1.0, 0.0, 0.0]
    assert list(vec2[18:24]) == [0.0, 0.0, 0.0, 0.0, 1.0, 0.0]

    # Case 3: Unknown or unrecognized category results in all zeros for that group (or unknown=1 if explicitly set)
    f3 = extract_recovery_features(
        amount=500.0,
        payment_method="other_method",
        failure_type="unknown",
    )
    vec3 = adapter.transform_single(f3)
    assert list(vec3[14:18]) == [0.0, 0.0, 0.0, 0.0]
    assert list(vec3[18:24]) == [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def test_derived_feature_computations():
    # Test high_value, prior_recovery_rate, customer_history_strength derivation
    f_low = extract_recovery_features(
        amount=5000.0,
        previous_transactions=10.0,
        previous_failures=2.0,
        previous_recoveries=3.0,
    )
    assert f_low.high_value == 0.0
    assert f_low.prior_recovery_rate == pytest.approx(3.0 / (2.0 + 3.0))
    expected_strength = np.log1p(10.0) / np.log1p(40.0)
    assert f_low.customer_history_strength == pytest.approx(expected_strength, 1e-4)

    f_high = extract_recovery_features(
        amount=15000.0,
        previous_transactions=0.0,
        previous_failures=0.0,
        previous_recoveries=0.0,
    )
    assert f_high.high_value == 1.0
    assert f_high.prior_recovery_rate == 0.0
    assert f_high.customer_history_strength == 0.0


# ---------------------------------------------------------------------------
# 3. Determinism & Batch Transformation Tests
# ---------------------------------------------------------------------------

def test_deterministic_prediction():
    predictor = get_recovery_predictor(force_reload=True)
    input_data = {
        "amount": 2500.0,
        "checkout_intent_score": 0.8,
        "customer_tenure_days": 120.0,
        "previous_transactions": 5.0,
        "historical_success_rate": 0.9,
        "previous_failures": 1.0,
        "previous_recoveries": 1.0,
        "days_since_failure": 1.0,
        "retry_count": 0.0,
        "messages_sent": 1.0,
        "opted_out": 0.0,
        "payment_method": "upi",
        "failure_type": "timeout",
    }

    prob1 = predictor.predict_probability(input_data)
    prob2 = predictor.predict_probability(input_data)
    prob3 = predictor.predict_probability(input_data)

    assert prob1 == prob2 == prob3
    assert isinstance(prob1, float)


def test_batch_prediction():
    predictor = get_recovery_predictor()
    item1 = {
        "amount": 1000.0,
        "checkout_intent_score": 0.9,
        "payment_method": "upi",
        "failure_type": "temporary_bank_error",
    }
    item2 = {
        "amount": 25000.0,
        "checkout_intent_score": 0.2,
        "opted_out": 1.0,
        "payment_method": "card",
        "failure_type": "expired_instrument",
    }

    single1 = predictor.predict_probability(item1)
    single2 = predictor.predict_probability(item2)

    batch = predictor.predict_probability([item1, item2])
    assert len(batch) == 2
    assert pytest.approx(batch[0], 1e-6) == single1
    assert pytest.approx(batch[1], 1e-6) == single2

    # Verify high intent + bank error has higher recovery probability than opted out + low intent
    assert single1 > single2


def test_empty_batch():
    predictor = get_recovery_predictor()
    batch = predictor.predict_probability([])
    assert batch == []


# ---------------------------------------------------------------------------
# 4. Calibration & Mathematical Consistency Tests
# ---------------------------------------------------------------------------

def test_calibration_math():
    config = CalibrationConfig(
        method="sigmoid_on_logit",
        coefficient=0.9540740845599085,
        intercept=-0.01725399436142655,
    )
    raw_p = 0.75
    logit = safe_logit(raw_p)
    z = config.coefficient * logit + config.intercept
    expected = sigmoid(z)

    calibrated = config.calibrate(raw_p)
    assert pytest.approx(calibrated, 1e-6) == expected


def test_probability_range():
    predictor = get_recovery_predictor()

    # Extreme high recovery case
    f_high = extract_recovery_features(
        amount=100.0,
        checkout_intent_score=1.0,
        customer_tenure_days=1000.0,
        previous_transactions=50.0,
        historical_success_rate=1.0,
        previous_failures=0.0,
        previous_recoveries=10.0,
        days_since_failure=0.0,
        retry_count=0.0,
        messages_sent=0.0,
        opted_out=0.0,
        payment_method="upi",
        failure_type="temporary_bank_error",
    )
    p_high = predictor.predict_probability(f_high)
    assert 0.0 <= p_high <= 1.0
    assert p_high > 0.6

    # Extreme low recovery case (opted out, expired instrument, high retries)
    f_low = extract_recovery_features(
        amount=50000.0,
        checkout_intent_score=0.0,
        customer_tenure_days=0.0,
        previous_transactions=0.0,
        historical_success_rate=0.0,
        previous_failures=10.0,
        previous_recoveries=0.0,
        days_since_failure=14.0,
        retry_count=5.0,
        messages_sent=5.0,
        opted_out=1.0,
        payment_method="wallet",
        failure_type="expired_instrument",
    )
    p_low = predictor.predict_probability(f_low)
    assert 0.0 <= p_low <= 1.0
    assert p_low < 0.15


# ---------------------------------------------------------------------------
# 5. Invalid / Missing Input Handling Tests
# ---------------------------------------------------------------------------

def test_invalid_input_types():
    adapter = FeatureAdapter()
    with pytest.raises(TypeError):
        adapter.transform_single(12345)  # type: ignore

    with pytest.raises(TypeError):
        adapter.transform(12345)  # type: ignore


def test_invalid_feature_values():
    with pytest.raises(Exception):
        # amount cannot be negative
        RecoveryFeatures(amount=-100.0)

    with pytest.raises(Exception):
        # checkout_intent_score must be in [0, 1]
        RecoveryFeatures(checkout_intent_score=1.5)


def test_feature_adapter_missing_key_in_dict():
    adapter = FeatureAdapter()
    # If dict is missing required field without default, RecoveryFeatures raises ValidationError
    with pytest.raises(Exception):
        adapter.transform_single({"checkout_intent_score": "invalid_type"})
