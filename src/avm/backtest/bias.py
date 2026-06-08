"""Bias diagnostics: signed error over time, segment-level residual analysis."""

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.avm.io import storage

logger = logging.getLogger(__name__)


def compute_signed_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean signed prediction error (positive = over-prediction)."""
    return float(np.mean(y_pred - y_true))


def error_by_segment(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    target_col: str = "resale_price",
    segment_cols: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute mean signed error and MAE sliced by each segment column."""
    segment_cols = segment_cols or ["town", "flat_type"]
    df = df.copy()
    df["_y_pred"] = y_pred
    df["_residual"] = y_pred - df[target_col]
    df["_abs_error"] = np.abs(df["_residual"])

    results = {}
    for col in segment_cols:
        if col not in df.columns:
            continue
        seg = (
            df.groupby(col)
            .agg(
                n=("_residual", "count"),
                mean_signed_error=("_residual", "mean"),
                mae=("_abs_error", "mean"),
                mape_pct=(target_col, lambda x: (df.loc[x.index, "_abs_error"] / x).mean() * 100),
            )
            .reset_index()
            .sort_values("mean_signed_error", ascending=False)
        )
        results[col] = seg
    return results


def error_by_price_band(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    target_col: str = "resale_price",
    n_bands: int = 5,
) -> pd.DataFrame:
    df = df.copy()
    df["_y_pred"] = y_pred
    df["_residual"] = y_pred - df[target_col]
    df["_abs_error"] = np.abs(df["_residual"])
    df["price_band"] = pd.qcut(df[target_col], q=n_bands, labels=False)

    return (
        df.groupby("price_band")
        .agg(
            price_min=(target_col, "min"),
            price_max=(target_col, "max"),
            n=("_residual", "count"),
            mean_signed_error=("_residual", "mean"),
            mae=("_abs_error", "mean"),
        )
        .reset_index()
    )


def generate_backtest_report(
    fold_results: list[dict],
    segment_results: dict[str, pd.DataFrame],
    price_band_results: pd.DataFrame,
    output_dir: str = "reports",
) -> None:
    storage.makedirs(output_dir + "/")

    folds_df = pd.DataFrame(fold_results)
    folds_df.to_csv(f"{output_dir}/backtest_metrics.csv", index=False)

    # --- Signed error over time plot ---
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    ax = axes[0]
    ax.bar(folds_df["test_start"], folds_df["signed_error"], color="steelblue")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_title("Mean Signed Prediction Error by Test Period")
    ax.set_xlabel("Test period start")
    ax.set_ylabel("Signed error (SGD)")
    ax.tick_params(axis="x", rotation=45)

    ax2 = axes[1]
    ax2.plot(folds_df["test_start"], folds_df["MAE"], marker="o", label="MAE", color="coral")
    ax2.plot(folds_df["test_start"], folds_df["RMSE"], marker="s", label="RMSE", color="steelblue")
    ax2.set_title("MAE and RMSE by Test Period")
    ax2.set_xlabel("Test period start")
    ax2.set_ylabel("SGD")
    ax2.legend()
    ax2.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    storage.savefig(plt, f"{output_dir}/backtest_error_over_time.png")
    plt.close()

    # --- Segment bias plots ---
    for seg_name, seg_df in segment_results.items():
        top_n = seg_df.nlargest(20, "n")
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = ["coral" if v > 0 else "steelblue" for v in top_n["mean_signed_error"]]
        ax.barh(top_n[seg_name], top_n["mean_signed_error"], color=colors)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_title(f"Mean Signed Error by {seg_name}")
        ax.set_xlabel("Signed error (SGD)  [positive = over-prediction]")
        plt.tight_layout()
        storage.savefig(plt, f"{output_dir}/backtest_bias_{seg_name}.png")
        plt.close()
        seg_df.to_csv(f"{output_dir}/backtest_bias_{seg_name}.csv", index=False)

    price_band_results.to_csv(f"{output_dir}/backtest_bias_price_band.csv", index=False)
    logger.info("Backtest report written to %s/", output_dir)
