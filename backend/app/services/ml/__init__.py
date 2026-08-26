"""
PayBack ML Service Package.

Provides feature adaptation and calibrated XGBoost recovery probability inference.
"""

from app.services.ml.customer_history import (
    CustomerHistory,
    CustomerHistoryService,
    compute_customer_history,
)
from app.services.ml.feature_adapter import (
    FeatureAdapter,
    RecoveryFeatures,
    extract_recovery_features,
)
from app.services.ml.xgboost_model import (
    XGBoostRecoveryProbabilityModel,
    _map_context_to_features,
    _normalise_failure_type,
    _normalise_payment_method,
)
from app.services.ml.xgboost_probability import (
    CalibrationConfig,
    ModelArtifacts,
    XGBoostRecoveryPredictor,
    get_recovery_predictor,
)

__all__ = [
    "CustomerHistory",
    "CustomerHistoryService",
    "compute_customer_history",
    "FeatureAdapter",
    "RecoveryFeatures",
    "extract_recovery_features",
    "CalibrationConfig",
    "ModelArtifacts",
    "XGBoostRecoveryPredictor",
    "get_recovery_predictor",
    "XGBoostRecoveryProbabilityModel",
    "_map_context_to_features",
    "_normalise_failure_type",
    "_normalise_payment_method",
]

