"""Model training and evaluation for the AVM pipeline."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNetCV, LassoCV, LinearRegression, RidgeCV
import xgboost as xgb

logger = logging.getLogger(__name__)


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, model_name: str = "") -> dict[str, float]:
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = r2_score(y_true, y_pred)
    mape = mean_absolute_percentage_error(y_true, y_pred) * 100
    metrics = {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "R2": round(r2, 4), "MAPE_pct": round(mape, 2)}
    prefix = f"[{model_name}] " if model_name else ""
    logger.info(
        "%sMAE=%.0f  RMSE=%.0f  R²=%.4f  MAPE=%.2f%%",
        prefix, mae, rmse, r2, mape,
    )
    return metrics


def train_lgbm(X_train: Any, y_train: np.ndarray, params: dict) -> LGBMRegressor:
    model = LGBMRegressor(**params)
    model.fit(X_train, y_train)
    logger.info("LGBM trained")
    return model


def train_xgboost(X_train: Any, y_train: np.ndarray, params: dict) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(**params)
    model.fit(X_train, y_train)
    logger.info("XGBoost trained")
    return model


def feature_importance_df(model: Any, feature_names: list[str], top_n: int = 20) -> pd.DataFrame:
    importances = model.feature_importances_
    df = (
        pd.DataFrame({"Feature": feature_names, "Importance": importances})
        .sort_values("Importance", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    return df


def train_all_baselines(X_train: Any, y_train: np.ndarray, X_test: Any, y_test: np.ndarray) -> dict[str, dict]:
    results = {}

    lr = LinearRegression()
    lr.fit(X_train, y_train)
    results["LinearRegression"] = evaluate(y_test, lr.predict(X_test), "LinearRegression")

    ridge = RidgeCV(cv=5)
    ridge.fit(X_train, y_train)
    results["Ridge"] = evaluate(y_test, ridge.predict(X_test), "Ridge")

    lasso = LassoCV(alphas=[0.01, 0.1, 1.0, 10.0], max_iter=500, cv=3)
    lasso.fit(X_train, y_train)
    results["Lasso"] = evaluate(y_test, lasso.predict(X_test), "Lasso")

    dt = DecisionTreeRegressor(criterion="squared_error", max_features="sqrt", min_samples_leaf=5, min_samples_split=3)
    dt.fit(X_train, y_train)
    results["DecisionTree"] = evaluate(y_test, dt.predict(X_test), "DecisionTree")

    rf = RandomForestRegressor(n_jobs=-1, n_estimators=200, max_depth=17, min_samples_leaf=4, oob_score=True)
    rf.fit(X_train, y_train)
    results["RandomForest"] = evaluate(y_test, rf.predict(X_test), "RandomForest")

    return results
