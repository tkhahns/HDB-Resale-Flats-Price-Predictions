"""LGBM + XGBoost ensemble (Automated Valuation Model)."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
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
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("Ensemble saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "AVMEnsemble":
        return joblib.load(path)


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
