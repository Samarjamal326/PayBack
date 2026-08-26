from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

import numpy as np
from pydantic import BaseModel, Field

# Default path to feature schema artifact
DEFAULT_FEATURE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4] / "ml" / "artifacts" / "feature_schema.json"
)


class RecoveryFeatures(BaseModel):
    """
    Structured feature representation for PayBack recovery context.
    Can be instantiated directly, from a dict, or built from domain models.
    """

    amount: float = Field(default=0.0, ge=0.0)
    checkout_intent_score: float = Field(default=0.5, ge=0.0, le=1.0)
    customer_tenure_days: float = Field(default=0.0, ge=0.0)
    previous_transactions: float = Field(default=0.0, ge=0.0)
    historical_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    previous_failures: float = Field(default=0.0, ge=0.0)
    previous_recoveries: float = Field(default=0.0, ge=0.0)
    days_since_failure: float = Field(default=0.0, ge=0.0)
    retry_count: float = Field(default=0.0, ge=0.0)
    messages_sent: float = Field(default=0.0, ge=0.0)
    opted_out: float = Field(default=0.0, ge=0.0, le=1.0)
    high_value: Optional[float] = None
    prior_recovery_rate: Optional[float] = None
    customer_history_strength: Optional[float] = None
    payment_method: str = Field(default="unknown")
    failure_type: str = Field(default="unknown")

    def model_post_init(self, __context: Any) -> None:
        """Derive engineered features if not explicitly supplied."""
        if self.high_value is None:
            self.high_value = 1.0 if self.amount >= 10_000.0 else 0.0

        if self.prior_recovery_rate is None:
            denom = self.previous_failures + self.previous_recoveries
            if denom > 0:
                self.prior_recovery_rate = min(max(self.previous_recoveries / denom, 0.0), 1.0)
            else:
                self.prior_recovery_rate = 0.0

        if self.customer_history_strength is None:
            # np.clip(np.log1p(previous_transactions) / np.log1p(40), 0, 1)
            norm = math.log1p(40.0)
            strength = math.log1p(max(self.previous_transactions, 0.0)) / norm
            self.customer_history_strength = min(max(strength, 0.0), 1.0)


def extract_recovery_features(
    *,
    amount: float,
    checkout_intent_score: float = 0.5,
    customer_tenure_days: float = 0.0,
    previous_transactions: float = 0.0,
    historical_success_rate: float = 0.0,
    previous_failures: float = 0.0,
    previous_recoveries: float = 0.0,
    days_since_failure: float = 0.0,
    retry_count: float = 0.0,
    messages_sent: float = 0.0,
    opted_out: bool | float = False,
    payment_method: str = "unknown",
    failure_type: str = "unknown",
    high_value: Optional[float] = None,
    prior_recovery_rate: Optional[float] = None,
    customer_history_strength: Optional[float] = None,
) -> RecoveryFeatures:
    """Helper to construct RecoveryFeatures with type conversions."""
    opted_out_val = 1.0 if (opted_out is True or opted_out == 1.0) else 0.0
    return RecoveryFeatures(
        amount=float(amount),
        checkout_intent_score=float(checkout_intent_score),
        customer_tenure_days=float(customer_tenure_days),
        previous_transactions=float(previous_transactions),
        historical_success_rate=float(historical_success_rate),
        previous_failures=float(previous_failures),
        previous_recoveries=float(previous_recoveries),
        days_since_failure=float(days_since_failure),
        retry_count=float(retry_count),
        messages_sent=float(messages_sent),
        opted_out=opted_out_val,
        payment_method=str(payment_method),
        failure_type=str(failure_type),
        high_value=high_value,
        prior_recovery_rate=prior_recovery_rate,
        customer_history_strength=customer_history_strength,
    )


class FeatureAdapter:
    """
    Transforms structured recovery inputs into the exact feature vector
    expected by the trained XGBoost model using ml/artifacts/feature_schema.json.
    """

    def __init__(self, schema_path: Union[str, Path] = DEFAULT_FEATURE_SCHEMA_PATH) -> None:
        self.schema_path = Path(schema_path)
        self.schema = self._load_schema()
        self.numeric_features: list[str] = self.schema["numeric_features"]
        self.categorical_features: list[str] = self.schema["categorical_features"]
        self.categories: dict[str, list[str]] = self.schema["categories"]

        # Build ordered feature names: numeric followed by one-hot columns
        self.feature_names: list[str] = list(self.numeric_features)
        for cat_feature in self.categorical_features:
            for cat_val in self.categories[cat_feature]:
                self.feature_names.append(f"{cat_feature}_{cat_val}")

        self.num_features: int = len(self.feature_names)

    def _load_schema(self) -> dict[str, Any]:
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Feature schema not found at {self.schema_path}")
        with open(self.schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def transform_single(
        self,
        features: Union[RecoveryFeatures, Mapping[str, Any]],
    ) -> np.ndarray:
        """
        Transforms a single feature record into a 1D numpy array of shape (num_features,).
        Preserves the exact numeric ordering and one-hot categorical ordering.
        """
        if not isinstance(features, RecoveryFeatures):
            if isinstance(features, Mapping):
                features = RecoveryFeatures(**features)
            else:
                raise TypeError(
                    f"Expected RecoveryFeatures or dict-like mapping, got {type(features).__name__}"
                )

        values: list[float] = []

        # 1. Numeric features in exact schema order
        for num_feat in self.numeric_features:
            val = getattr(features, num_feat, None)
            if val is None:
                raise ValueError(f"Missing required numeric feature: {num_feat}")
            try:
                values.append(float(val))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid float value for numeric feature '{num_feat}': {val}") from exc

        # 2. Categorical features one-hot encoded in exact category order
        for cat_feat in self.categorical_features:
            raw_val = getattr(features, cat_feat, "")
            # Normalize casing/whitespace
            val_str = str(raw_val).strip().lower()
            allowed_cats = self.categories[cat_feat]
            for allowed_cat in allowed_cats:
                values.append(1.0 if val_str == allowed_cat else 0.0)

        return np.array(values, dtype=np.float32)

    def transform(
        self,
        inputs: Union[
            RecoveryFeatures,
            Mapping[str, Any],
            Sequence[Union[RecoveryFeatures, Mapping[str, Any]]],
        ],
    ) -> np.ndarray:
        """
        Transforms a single or batch of feature records into a 2D numpy array of shape (N, num_features).
        """
        if isinstance(inputs, (RecoveryFeatures, Mapping)):
            single = self.transform_single(inputs)
            return single.reshape(1, -1)

        if isinstance(inputs, Sequence):
            if len(inputs) == 0:
                return np.empty((0, self.num_features), dtype=np.float32)
            rows = [self.transform_single(item) for item in inputs]
            return np.vstack(rows).astype(np.float32)

        raise TypeError(f"Unsupported input type for transform: {type(inputs).__name__}")
