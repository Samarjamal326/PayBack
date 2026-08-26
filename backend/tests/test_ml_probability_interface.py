"""
Integration tests for the RecoveryProbabilityModel interface connection.

Verifies:
1. XGBoostRecoveryProbabilityModel satisfies the RecoveryProbabilityModel protocol.
2. A valid RecoveryContext can be converted into ML features.
3. The adapter correctly calls XGBoostRecoveryPredictor.
4. The returned probability is in [0.0, 1.0].
5. Repeated inference with identical context returns identical probability.
6. The existing probability interface can use the XGBoost implementation.
7. Feature mapping edge cases (payment method normalisation, failure type mapping).
8. recovery_context_from_domain builds a context from domain objects.
"""
from __future__ import annotations

import pytest

from app.core.probability import (
    RecoveryContext,
    RecoveryProbabilityModel,
    recovery_context_from_domain,
)
from app.models.domain import (
    Customer,
    PaymentMethod,
    RecoveryCase,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.services.ml.xgboost_model import (
    XGBoostRecoveryProbabilityModel,
    _normalise_failure_type,
    _normalise_payment_method,
)
from app.services.ml.xgboost_probability import XGBoostRecoveryPredictor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def standard_context() -> RecoveryContext:
    return RecoveryContext(
        amount=2500.0,
        payment_method_raw="upi",
        failure_reason_raw="temporary_bank_error",
        retry_count=0,
        messages_sent=1,
        opted_out=False,
        checkout_intent_score=0.75,
        customer_tenure_days=90.0,
        previous_transactions=8.0,
        historical_success_rate=0.85,
        previous_failures=1.0,
        previous_recoveries=1.0,
        days_since_failure=0.5,
    )


@pytest.fixture
def model() -> XGBoostRecoveryProbabilityModel:
    return XGBoostRecoveryProbabilityModel()


@pytest.fixture
def failed_tx() -> Transaction:
    return Transaction(
        customer_id="cust-1",
        amount=2499.0,
        payment_method=PaymentMethod.UPI,
        status=TransactionStatus.FAILED,
        failure_reason="card_declined",
    )


@pytest.fixture
def active_customer() -> Customer:
    return Customer(
        id="cust-1",
        name="Priya Sharma",
        email="priya@example.com",
        phone="+919876543210",
    )


@pytest.fixture
def recovery_case(failed_tx: Transaction, active_customer: Customer) -> RecoveryCase:
    return RecoveryCase(
        transaction_id=failed_tx.id,
        customer_id=active_customer.id,
        amount_at_risk=failed_tx.amount,
        reason="card_declined",
        status=RecoveryStatus.DETECTED,
        retry_count=0,
        message_count=0,
    )


# ---------------------------------------------------------------------------
# 1. Protocol Conformance
# ---------------------------------------------------------------------------

class TestProtocolConformance:
    def test_satisfies_recovery_probability_model_protocol(self, model):
        """XGBoostRecoveryProbabilityModel must satisfy the RecoveryProbabilityModel Protocol."""
        assert isinstance(model, RecoveryProbabilityModel)

    def test_has_predict_method(self, model):
        assert callable(model.predict)

    def test_predict_method_signature(self, model, standard_context):
        """predict() must accept a RecoveryContext and return a float."""
        result = model.predict(standard_context)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# 2. RecoveryContext → ML Features Conversion
# ---------------------------------------------------------------------------

class TestContextToFeatureMapping:
    def test_context_can_be_constructed(self, standard_context):
        assert standard_context.amount == 2500.0
        assert standard_context.payment_method_raw == "upi"
        assert standard_context.failure_reason_raw == "temporary_bank_error"

    def test_recovery_context_from_domain(self, failed_tx, active_customer, recovery_case):
        ctx = recovery_context_from_domain(failed_tx, active_customer, recovery_case)
        assert ctx.amount == failed_tx.amount
        assert ctx.payment_method_raw == failed_tx.payment_method.value
        assert ctx.failure_reason_raw == (failed_tx.failure_reason or "")
        assert ctx.opted_out == active_customer.opted_out
        assert ctx.retry_count == recovery_case.retry_count
        assert ctx.messages_sent == recovery_case.message_count
        assert ctx.days_since_failure >= 0.0

    def test_opted_out_customer_reflected_in_context(self, failed_tx, recovery_case):
        opted_out_cust = Customer(id="cust-9", name="Test User", opted_out=True)
        ctx = recovery_context_from_domain(failed_tx, opted_out_cust, recovery_case)
        assert ctx.opted_out is True

    def test_retry_count_reflected_in_context(self, failed_tx, active_customer):
        case = RecoveryCase(
            transaction_id=failed_tx.id,
            customer_id=active_customer.id,
            amount_at_risk=failed_tx.amount,
            reason="test",
            status=RecoveryStatus.DETECTED,
            retry_count=2,
            message_count=3,
        )
        ctx = recovery_context_from_domain(failed_tx, active_customer, case)
        assert ctx.retry_count == 2
        assert ctx.messages_sent == 3


# ---------------------------------------------------------------------------
# 3. Payment Method Normalisation
# ---------------------------------------------------------------------------

class TestPaymentMethodNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        ("upi",         "upi"),
        ("card",        "card"),
        ("net_banking", "netbanking"),
        ("wallet",      "wallet"),
        ("emi",         ""),
        ("unknown",     ""),
        ("UPI",         "upi"),        # case insensitive
        ("NET_BANKING", "netbanking"), # uppercase normalised
        ("other",       ""),           # unrecognised → empty (all zeros)
    ])
    def test_normalise_payment_method(self, raw, expected):
        assert _normalise_payment_method(raw) == expected

    def test_net_banking_maps_to_netbanking_not_all_zeros(self):
        """net_banking should become 'netbanking', not be treated as unknown."""
        result = _normalise_payment_method("net_banking")
        assert result == "netbanking"


# ---------------------------------------------------------------------------
# 4. Failure Type Normalisation
# ---------------------------------------------------------------------------

class TestFailureTypeNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        # Exact ML category passthrough
        ("temporary_bank_error",  "temporary_bank_error"),
        ("timeout",               "timeout"),
        ("insufficient_funds",    "insufficient_funds"),
        ("expired_instrument",    "expired_instrument"),
        ("authentication_failure","authentication_failure"),
        ("unknown",               "unknown"),
        # Domain free-text → keyword match
        ("card_declined",         "temporary_bank_error"),
        ("bank_error",            "temporary_bank_error"),
        ("insufficient_fund",     "insufficient_funds"),
        ("expired",               "expired_instrument"),
        ("timed_out",             "timeout"),
        ("auth_failure",          "authentication_failure"),
        # Unrecognised → unknown
        ("",                      "unknown"),
        ("unrecognised_code",     "unknown"),
        # Case insensitive
        ("CARD_DECLINED",         "temporary_bank_error"),
    ])
    def test_normalise_failure_type(self, raw, expected):
        assert _normalise_failure_type(raw) == expected


# ---------------------------------------------------------------------------
# 5. XGBoostRecoveryProbabilityModel.predict() End-to-End
# ---------------------------------------------------------------------------

class TestXGBoostModelPredict:
    def test_returns_float(self, model, standard_context):
        result = model.predict(standard_context)
        assert isinstance(result, float)

    def test_probability_in_range(self, model, standard_context):
        result = model.predict(standard_context)
        assert 0.0 <= result <= 1.0

    def test_deterministic_repeated_calls(self, model, standard_context):
        """Identical inputs must produce identical outputs."""
        p1 = model.predict(standard_context)
        p2 = model.predict(standard_context)
        p3 = model.predict(standard_context)
        assert p1 == p2 == p3

    def test_opted_out_lowers_probability(self, model):
        """opt-out flag should strongly reduce recovery probability."""
        ctx_normal = RecoveryContext(
            amount=1000.0,
            payment_method_raw="upi",
            failure_reason_raw="timeout",
            opted_out=False,
            checkout_intent_score=0.8,
        )
        ctx_opted_out = RecoveryContext(
            amount=1000.0,
            payment_method_raw="upi",
            failure_reason_raw="timeout",
            opted_out=True,
            checkout_intent_score=0.8,
        )
        p_normal = model.predict(ctx_normal)
        p_opted_out = model.predict(ctx_opted_out)
        assert p_normal > p_opted_out

    def test_high_retry_lowers_probability(self, model):
        """More retries should correlate with lower recovery probability."""
        ctx_first = RecoveryContext(
            amount=1500.0,
            payment_method_raw="card",
            failure_reason_raw="bank_error",
            retry_count=0,
            checkout_intent_score=0.7,
        )
        ctx_many = RecoveryContext(
            amount=1500.0,
            payment_method_raw="card",
            failure_reason_raw="bank_error",
            retry_count=3,
            checkout_intent_score=0.7,
        )
        p_first = model.predict(ctx_first)
        p_many = model.predict(ctx_many)
        assert p_first > p_many

    def test_accepts_injected_predictor(self):
        """Model should accept an externally-provided predictor."""
        predictor = XGBoostRecoveryPredictor()
        model = XGBoostRecoveryProbabilityModel(predictor=predictor)
        ctx = RecoveryContext(
            amount=500.0,
            payment_method_raw="upi",
            failure_reason_raw="unknown",
        )
        result = model.predict(ctx)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# 6. Interface Usability via Protocol
# ---------------------------------------------------------------------------

class TestInterfaceUsability:
    def test_can_call_through_protocol_type(self, model, standard_context):
        """The model should be usable via the RecoveryProbabilityModel protocol type."""
        probability_model: RecoveryProbabilityModel = model
        result = probability_model.predict(standard_context)
        assert 0.0 <= result <= 1.0

    def test_domain_to_context_to_prediction_pipeline(
        self, failed_tx, active_customer, recovery_case
    ):
        """Full pipeline: domain objects → context → model → probability."""
        model = XGBoostRecoveryProbabilityModel()
        ctx = recovery_context_from_domain(failed_tx, active_customer, recovery_case)
        probability = model.predict(ctx)
        assert 0.0 <= probability <= 1.0
        assert isinstance(probability, float)
