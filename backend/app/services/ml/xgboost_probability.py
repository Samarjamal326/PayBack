from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

import numpy as np
import xgboost as xgb

from app.services.ml.feature_adapter import (
    DEFAULT_FEATURE_SCHEMA_PATH,
    FeatureAdapter,
    RecoveryFeatures,
)

# Base ML directory resolution
_ML_DIR = Path(__file__).resolve().parents[4] / "ml"
DEFAULT_MODEL_PATH = _ML_DIR / "models" / "payback_xgboost.json"
DEFAULT_CALIBRATION_PATH = _ML_DIR / "artifacts" / "calibration.json"
DEFAULT_METADATA_PATH = _ML_DIR / "artifacts" / "model_metadata.json"


def safe_logit(p: Union[float, np.ndarray], eps: float = 1e-6) -> Union[float, np.ndarray]:
    """
    Computes logit safely with clipping to avoid inf/-inf.
    Matches training notebook implementation:
        p = np.clip(np.asarray(p), eps, 1 - eps)
        return np.log(p / (1 - p))
    """
    p_arr = np.asarray(p, dtype=np.float64)
    p_clipped = np.clip(p_arr, eps, 1.0 - eps)
    logit = np.log(p_clipped / (1.0 - p_clipped))
    if np.isscalar(p) or p_arr.ndim == 0:
        return float(logit)
    return logit


def sigmoid(z: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Computes sigmoid 1 / (1 + exp(-z)) safely."""
    z_arr = np.asarray(z, dtype=np.float64)
    res = 1.0 / (1.0 + np.exp(-z_arr))
    if np.isscalar(z) or z_arr.ndim == 0:
        return float(res)
    return res


@dataclass(frozen=True)
class CalibrationConfig:
    method: str
    coefficient: float
    intercept: float

    @classmethod
    def from_file(cls, path: Union[str, Path] = DEFAULT_CALIBRATION_PATH) -> CalibrationConfig:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Calibration artifact not found at {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            method=data.get("method", "sigmoid_on_logit"),
            coefficient=float(data["coefficient"]),
            intercept=float(data["intercept"]),
        )

    def calibrate(self, raw_probability: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Applies calibration:
            z = coef * safe_logit(p) + intercept
            p_calibrated = 1 / (1 + exp(-z))
        """
        logit = safe_logit(raw_probability)
        z = self.coefficient * logit + self.intercept
        return sigmoid(z)


@dataclass(frozen=True)
class ModelArtifacts:
    model_path: Path
    schema_path: Path
    calibration_path: Path
    metadata_path: Optional[Path] = None


class XGBoostRecoveryPredictor:
    """
    Inference service for PayBack recovery probability estimation.
    Loads payback_xgboost.json, calibration.json, and uses FeatureAdapter
    to produce calibrated recovery probabilities in [0.0, 1.0].
    """

    def __init__(
        self,
        model_path: Union[str, Path] = DEFAULT_MODEL_PATH,
        schema_path: Union[str, Path] = DEFAULT_FEATURE_SCHEMA_PATH,
        calibration_path: Union[str, Path] = DEFAULT_CALIBRATION_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.schema_path = Path(schema_path)
        self.calibration_path = Path(calibration_path)

        # 1. Feature Adapter
        self.feature_adapter = FeatureAdapter(self.schema_path)

        # 2. Calibration Config
        self.calibration = CalibrationConfig.from_file(self.calibration_path)

        # 3. XGBoost Booster
        self.booster = self._load_model()

    def _load_model(self) -> xgb.Booster:
        if not self.model_path.exists():
            raise FileNotFoundError(f"XGBoost model file not found at {self.model_path}")
        booster = xgb.Booster()
        booster.load_model(str(self.model_path))
        # Ensure single-thread deterministic CPU inference
        booster.set_param({"nthread": 1})
        return booster

    def predict_raw_from_features(self, feature_matrix: np.ndarray) -> np.ndarray:
        """
        Runs XGBoost inference on a 2D float feature matrix.
        Returns raw predicted probabilities.
        """
        if feature_matrix.ndim == 1:
            feature_matrix = feature_matrix.reshape(1, -1)

        if feature_matrix.shape[1] != self.feature_adapter.num_features:
            raise ValueError(
                f"Feature matrix has {feature_matrix.shape[1]} features, "
                f"expected {self.feature_adapter.num_features}"
            )

        dmat = xgb.DMatrix(feature_matrix)
        preds = self.booster.predict(dmat)
        return np.asarray(preds, dtype=np.float64)

    def predict_probability(
        self,
        features: Union[
            RecoveryFeatures,
            Mapping[str, Any],
            Sequence[Union[RecoveryFeatures, Mapping[str, Any]]],
        ],
        *,
        calibrate: bool = True,
    ) -> Union[float, list[float]]:
        """
        Computes the recovery probability for a single input or a list of inputs.
        If a single input is passed, returns a float in [0.0, 1.0].
        If a sequence is passed, returns a list of floats.
        """
        is_single = isinstance(features, (RecoveryFeatures, Mapping))
        feat_matrix = self.feature_adapter.transform(features)

        if feat_matrix.shape[0] == 0:
            return []

        raw_probs = self.predict_raw_from_features(feat_matrix)

        if calibrate:
            cal_probs = self.calibration.calibrate(raw_probs)
        else:
            cal_probs = raw_probs

        # Bound strictly to [0.0, 1.0]
        bounded = np.clip(cal_probs, 0.0, 1.0)

        if is_single:
            return float(bounded[0])
        return [float(p) for p in bounded]


# Module-level singleton instance
_predictor_instance: Optional[XGBoostRecoveryPredictor] = None


def get_recovery_predictor(
    model_path: Union[str, Path] = DEFAULT_MODEL_PATH,
    schema_path: Union[str, Path] = DEFAULT_FEATURE_SCHEMA_PATH,
    calibration_path: Union[str, Path] = DEFAULT_CALIBRATION_PATH,
    force_reload: bool = False,
) -> XGBoostRecoveryPredictor:
    """Returns a singleton or fresh instance of XGBoostRecoveryPredictor."""
    global _predictor_instance
    if _predictor_instance is None or force_reload:
        _predictor_instance = XGBoostRecoveryPredictor(
            model_path=model_path,
            schema_path=schema_path,
            calibration_path=calibration_path,
        )
    return _predictor_instance
