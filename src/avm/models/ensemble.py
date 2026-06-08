"""LGBM + XGBoost ensemble (Automated Valuation Model)."""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.avm.models.train import evaluate, feature_importance_df, train_lgbm, train_xgboost

logger = logging.getLogger(__name__)


@dataclass
class AVMEnsemble:
    lgbm_model: Any
    xgb_model: Any
    lgbm_weight: float
    xgb_weight: float
    feature_names: list[str]

    def predict(self, X: Any) -> np.ndarray:
        p_lgbm = self.lgbm_model.predict(X)
        p_xgb = self.xgb_model.predict(X)
        return self.lgbm_weight * p_lgbm + self.xgb_weight * p_xgb

    def save(self, path: str) -> None:
        from src.avm.io.storage import save_joblib
        save_joblib(self, path)
        logger.info("Ensemble saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "AVMEnsemble":
        from src.avm.io.storage import load_joblib
        return load_joblib(path)


@dataclass
class AVMModelBundle:
    """Complete portable bundle for inference: ensemble + preprocessor + metadata."""

    ensemble: AVMEnsemble
    preprocessor: Any  # fitted sklearn Pipeline
    feature_names: list[str]
    collinearity_dropped: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Preprocess raw feature DataFrame and return price predictions."""
        from src.avm.models.preprocess import drop_pre_encode_cols, transform_test
        X_clean = drop_pre_encode_cols(X, extra_drops=self.collinearity_dropped)
        X_enc = transform_test(X_clean, self.preprocessor)
        return self.ensemble.predict(X_enc)

    def save_bundle(self, prefix: str) -> None:
        """Persist all bundle components under prefix/ (local or s3://)."""
        from src.avm.io.storage import makedirs, save_joblib, write_json
        makedirs(prefix + "/")
        save_joblib(self.ensemble, f"{prefix}/avm_ensemble.pkl")
        save_joblib(self.preprocessor, f"{prefix}/preprocessor.pkl")
        write_json({"feature_names": self.feature_names}, f"{prefix}/feature_names.json")
        write_json(
            {"collinearity_dropped": self.collinearity_dropped, **self.manifest},
            f"{prefix}/manifest.json",
        )
        logger.info("Bundle saved → %s/", prefix)

    @classmethod
    def load_bundle(cls, prefix: str) -> "AVMModelBundle":
        """Load bundle from prefix/ (local or s3://)."""
        from src.avm.io.storage import load_joblib, read_json
        ensemble = load_joblib(f"{prefix}/avm_ensemble.pkl")
        preprocessor = load_joblib(f"{prefix}/preprocessor.pkl")
        feature_names = read_json(f"{prefix}/feature_names.json")["feature_names"]
        manifest = read_json(f"{prefix}/manifest.json")
        collinearity_dropped = manifest.pop("collinearity_dropped", [])
        return cls(
            ensemble=ensemble,
            preprocessor=preprocessor,
            feature_names=feature_names,
            collinearity_dropped=collinearity_dropped,
            manifest=manifest,
        )


def train_ensemble(
    X_train: Any,
    y_train: np.ndarray,
    X_test: Any,
    y_test: np.ndarray,
    lgbm_params: dict,
    xgb_params: dict,
    feature_names: list[str],
    lgbm_weight: float = 0.5,
    xgb_weight: float = 0.5,
) -> tuple[AVMEnsemble, dict[str, float], dict[str, float]]:
    """Train both models, evaluate individually and as ensemble."""
    lgbm_model = train_lgbm(X_train, y_train, lgbm_params)
    xgb_model = train_xgboost(X_train, y_train, xgb_params)

    lgbm_metrics = evaluate(y_test, lgbm_model.predict(X_test), "LGBM")
    xgb_metrics = evaluate(y_test, xgb_model.predict(X_test), "XGBoost")

    ensemble = AVMEnsemble(
        lgbm_model=lgbm_model,
        xgb_model=xgb_model,
        lgbm_weight=lgbm_weight,
        xgb_weight=xgb_weight,
        feature_names=feature_names,
    )
    ens_metrics = evaluate(y_test, ensemble.predict(X_test), "Ensemble(LGBM+XGB)")

    logger.info(
        "Ensemble improvement over best single: MAE %.0f → %.0f",
        min(lgbm_metrics["MAE"], xgb_metrics["MAE"]),
        ens_metrics["MAE"],
    )

    return ensemble, ens_metrics, {"lgbm": lgbm_metrics, "xgboost": xgb_metrics, "ensemble": ens_metrics}


def summarise_feature_importance(ensemble: AVMEnsemble, top_n: int = 20) -> pd.DataFrame:
    lgbm_fi = feature_importance_df(ensemble.lgbm_model, ensemble.feature_names, top_n)
    xgb_fi = feature_importance_df(ensemble.xgb_model, ensemble.feature_names, top_n)
    combined = (
        lgbm_fi.rename(columns={"Importance": "LGBM_importance"})
        .merge(xgb_fi.rename(columns={"Importance": "XGB_importance"}), on="Feature", how="outer")
        .fillna(0)
    )
    combined["mean_importance"] = (combined["LGBM_importance"] + combined["XGB_importance"]) / 2
    return combined.sort_values("mean_importance", ascending=False).reset_index(drop=True)
