"""Walk-forward (expanding-window) backtesting for the AVM pipeline."""

import logging
from typing import Callable, Any

import numpy as np
import pandas as pd

from src.avm.models.train import evaluate

logger = logging.getLogger(__name__)


def _month_offset(period: pd.Period, n: int) -> pd.Period:
    return period + n


def walk_forward_cv(
    df: pd.DataFrame,
    model_fn: Callable[[pd.DataFrame, pd.DataFrame], tuple[Any, np.ndarray]],
    date_col: str = "month",
    target_col: str = "resale_price",
    step_months: int = 6,
    min_train_months: int = 18,
) -> list[dict]:
    """Run expanding-window walk-forward cross-validation.

    model_fn(df_train, df_test) → (fitted_model, y_pred array)

    Returns a list of fold result dicts with metrics + fold metadata.
    """
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col])

    periods = df[date_col].dt.to_period("M")
    all_periods = sorted(periods.unique())

    start_idx = min_train_months
    if start_idx >= len(all_periods):
        raise ValueError(
            f"Not enough months for walk-forward CV: need >{min_train_months}, have {len(all_periods)}"
        )

    fold_results = []
    fold_num = 1

    for i in range(start_idx, len(all_periods) - step_months + 1, step_months):
        train_end = all_periods[i - 1]
        test_start = all_periods[i]
        test_end = all_periods[min(i + step_months - 1, len(all_periods) - 1)]

        train_mask = periods <= train_end
        test_mask = (periods >= test_start) & (periods <= test_end)

        df_train_fold = df[train_mask].copy()
        df_test_fold = df[test_mask].copy()

        if df_test_fold.empty:
            continue

        logger.info(
            "Fold %d: train up to %s | test %s → %s (%d test rows)",
            fold_num, train_end, test_start, test_end, len(df_test_fold),
        )

        try:
            model, y_pred = model_fn(df_train_fold, df_test_fold)
            y_true = df_test_fold[target_col].values
            metrics = evaluate(y_true, y_pred, f"Fold-{fold_num}")
            metrics["signed_error"] = round(float(np.mean(y_pred - y_true)), 2)
            fold_results.append(
                {
                    "fold": fold_num,
                    "train_end": str(train_end),
                    "test_start": str(test_start),
                    "test_end": str(test_end),
                    "n_train": len(df_train_fold),
                    "n_test": len(df_test_fold),
                    **metrics,
                }
            )
        except Exception as exc:
            logger.error("Fold %d failed: %s", fold_num, exc)

        fold_num += 1

    logger.info("Walk-forward CV complete: %d folds", len(fold_results))
    return fold_results
