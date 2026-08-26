"""
XGBoostRecoveryProbabilityModel — implements RecoveryProbabilityModel using the
trained XGBoost model and calibration artifacts.

Architecture:
    RecoveryContext
          ↓
    XGBoostRecoveryProbabilityModel.predict()
          ↓
    _map_context_to_features()    ← feature mapping (no schema duplication)
          ↓
    XGBoostRecoveryPredictor      ← already-tested ML component
          ↓
    FeatureAdapter + payback_xgboost.json + calibration.json
          ↓
    probability ∈ [0.0, 1.0]
"""
from __future__ import annotations

from app.core.probability import RecoveryContext, RecoveryProbabilityModel
from app.services.ml.feature_adapter import RecoveryFeatures, extract_recovery_features
from app.services.ml.xgboost_probability import XGBoostRecoveryPredictor, get_recovery_predictor

# ---------------------------------------------------------------------------
# Payment method normalisation
# ---------------------------------------------------------------------------
# Domain PaymentMethod enum values → ML feature_schema.json categories.
# Schema categories: ["upi", "card", "netbanking", "wallet"]
# Domain values:    "upi", "card", "net_banking", "wallet", "emi", "unknown"
#
# Mismatches:
#   "net_banking" → "netbanking"   (spelling difference, unambiguous mapping)
#   "emi"         → ""             (no ML category; all payment_method bits = 0)
#   "unknown"     → ""             (no ML category; all payment_method bits = 0)
_PAYMENT_METHOD_MAP: dict[str, str] = {
    "upi": "upi",
    "card": "card",
    "net_banking": "netbanking",
    "wallet": "wallet",
    "emi": "",          # no corresponding ML category → all zeros
    "unknown": "",      # no corresponding ML category → all zeros
}

# ---------------------------------------------------------------------------
# Failure type normalisation
# ---------------------------------------------------------------------------
# Transaction.failure_reason is a free-text string.
# ML schema failure_type categories:
#   "temporary_bank_error", "timeout", "insufficient_funds",
#   "expired_instrument", "authentication_failure", "unknown"
#
# We perform a best-effort keyword match. Unrecognised reasons → "unknown".
_FAILURE_TYPE_KEYWORDS: list[tuple[str, str]] = [
    # (substring_to_match_lowercase, ml_category)
    ("insufficient_fund",   "insufficient_funds"),
    ("insufficient fund",   "insufficient_funds"),
    ("low_balance",         "insufficient_funds"),
    ("low balance",         "insufficient_funds"),
    ("expired",             "expired_instrument"),
    ("timeout",             "timeout"),
    ("timed_out",           "timeout"),
    ("timed out",           "timeout"),
    ("auth",                "authentication_failure"),
    ("otp",                 "authentication_failure"),
    ("authentication",      "authentication_failure"),
    ("bank_error",          "temporary_bank_error"),
    ("bank error",          "temporary_bank_error"),
    ("bank_decline",        "temporary_bank_error"),
    ("card_declined",       "temporary_bank_error"),
    ("declined",            "temporary_bank_error"),
    ("temporary",           "temporary_bank_error"),
    ("technical",           "temporary_bank_error"),
]

_ML_FAILURE_CATEGORIES = {
    "temporary_bank_error",
    "timeout",
    "insufficient_funds",
    "expired_instrument",
    "authentication_failure",
    "unknown",
}


def _normalise_payment_method(raw: str) -> str:
    """Maps domain PaymentMethod value to ML feature_schema.json category."""
    return _PAYMENT_METHOD_MAP.get(raw.strip().lower(), "")


def _normalise_failure_type(raw: str) -> str:
    """
    Maps Transaction.failure_reason (free text) to the closest ML failure_type category.
    If the raw value is already an exact ML category, it is used as-is.
    Falls back to 'unknown'.
    """
    if not raw:
        return "unknown"

    normalised = raw.strip().lower()

    # Exact match against known ML categories
    if normalised in _ML_FAILURE_CATEGORIES:
        return normalised

    # Keyword substring match
    for keyword, ml_category in _FAILURE_TYPE_KEYWORDS:
        if keyword in normalised:
            return ml_category

    return "unknown"


def _map_context_to_features(context: RecoveryContext) -> RecoveryFeatures:
    """
    Translates a RecoveryContext into RecoveryFeatures for ML inference.
    Uses extract_recovery_features() which in turn uses the FeatureAdapter schema.
    """
    return extract_recovery_features(
        amount=context.amount,
        checkout_intent_score=context.checkout_intent_score,
        customer_tenure_days=context.customer_tenure_days,
        previous_transactions=context.previous_transactions,
        historical_success_rate=context.historical_success_rate,
        previous_failures=context.previous_failures,
        previous_recoveries=context.previous_recoveries,
        days_since_failure=context.days_since_failure,
        retry_count=float(context.retry_count),
        messages_sent=float(context.messages_sent),
        opted_out=context.opted_out,
        payment_method=_normalise_payment_method(context.payment_method_raw),
        failure_type=_normalise_failure_type(context.failure_reason_raw),
    )


class XGBoostRecoveryProbabilityModel:
    """
    Implements RecoveryProbabilityModel using the trained XGBoost model.

    This is the adapter between PayBack's domain context and the ML inference
    component. It does not duplicate model loading, feature encoding, or
    calibration — all of that lives in XGBoostRecoveryPredictor.

    Usage:
        model = XGBoostRecoveryProbabilityModel()
        context = recovery_context_from_domain(transaction, customer, case)
        probability = model.predict(context)
    """

    def __init__(self, predictor: XGBoostRecoveryPredictor | None = None) -> None:
        """
        Args:
            predictor: Optional XGBoostRecoveryPredictor. If None, uses the
                       module-level singleton (lazy-loaded on first call).
        """
        self._predictor = predictor

    def _get_predictor(self) -> XGBoostRecoveryPredictor:
        if self._predictor is None:
            self._predictor = get_recovery_predictor()
        return self._predictor

    def predict(self, context: RecoveryContext) -> float:
        """
        Returns calibrated recovery probability ∈ [0.0, 1.0].

        Deterministic: identical context → identical output.
        No DB, API, or network calls.
        """
        features = _map_context_to_features(context)
        predictor = self._get_predictor()
        probability = predictor.predict_probability(features)
        assert isinstance(probability, float), (
            f"Expected float from predictor, got {type(probability).__name__}"
        )
        return probability
