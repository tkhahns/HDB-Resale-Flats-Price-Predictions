"""Multi-collinearity detection and resolution via VIF and Pearson correlation."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor

logger = logging.getLogger(__name__)


def compute_vif(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Variance Inflation Factor for each column in df (numeric only)."""
    numeric = df.select_dtypes(include="number").dropna(axis=1)
    if numeric.shape[1] < 2:
        return pd.DataFrame({"Feature": numeric.columns, "VIF": [np.nan] * numeric.shape[1]})

    X = numeric.values
    vif_data = []
    for i, col in enumerate(numeric.columns):
        try:
            v = variance_inflation_factor(X, i)
        except Exception:
            v = np.nan
        vif_data.append({"Feature": col, "VIF": round(v, 4)})

    return pd.DataFrame(vif_data).sort_values("VIF", ascending=False).reset_index(drop=True)


def prune_by_vif(
    df: pd.DataFrame,
    threshold: float = 10.0,
    protected: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Iteratively drop the highest-VIF feature until all remaining VIF < threshold.

    Returns (pruned_df, list_of_dropped_columns).
    protected columns (e.g. the target) are never dropped.
    """
    protected = set(protected or [])
    dropped: list[str] = []
    current = df.copy()

    while True:
        candidates = [c for c in current.select_dtypes(include="number").columns if c not in protected]
        if len(candidates) < 2:
            break

        vif_df = compute_vif(current[candidates])
        max_vif = vif_df["VIF"].max()
        if max_vif < threshold:
            break

        worst = vif_df.loc[vif_df["VIF"].idxmax(), "Feature"]
        logger.info("Dropping '%s' (VIF=%.2f > threshold=%.2f)", worst, max_vif, threshold)
        current = current.drop(columns=[worst])
        dropped.append(worst)

    logger.info("VIF pruning complete: dropped %d features, %d remain", len(dropped), len(current.columns))
    return current, dropped


def correlation_screen(
    df: pd.DataFrame,
    threshold: float = 0.85,
    protected: list[str] | None = None,
) -> pd.DataFrame:
    """Return a DataFrame of highly correlated feature pairs (|r| > threshold)."""
    protected = set(protected or [])
    numeric = df.select_dtypes(include="number")
    corr = numeric.corr().abs()
    pairs = []
    cols = corr.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if r >= threshold:
                pairs.append(
                    {
                        "feature_a": cols[i],
                        "feature_b": cols[j],
                        "pearson_r": round(r, 4),
                        "both_unprotected": cols[i] not in protected and cols[j] not in protected,
                    }
                )
    result = pd.DataFrame(pairs) if pairs else pd.DataFrame(columns=["feature_a", "feature_b", "pearson_r", "both_unprotected"])
    if not result.empty:
        result = result.sort_values("pearson_r", ascending=False)
    logger.info("Found %d highly correlated pairs (|r| ≥ %.2f)", len(result), threshold)
    return result


def generate_collinearity_report(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    dropped: list[str],
    corr_pairs: pd.DataFrame,
    output_path: str = "reports/collinearity_report.csv",
) -> None:
    """Save a before/after VIF comparison and correlation pairs to CSV."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    before_vif = compute_vif(before_df).rename(columns={"VIF": "VIF_before"})
    after_vif = compute_vif(after_df).rename(columns={"VIF": "VIF_after"})
    merged = before_vif.merge(after_vif, on="Feature", how="outer").sort_values(
        "VIF_before", ascending=False
    )
    merged.to_csv(output_path, index=False)

    dropped_path = output_path.replace(".csv", "_dropped.csv")
    pd.DataFrame({"dropped_feature": dropped}).to_csv(dropped_path, index=False)

    corr_path = output_path.replace(".csv", "_corr_pairs.csv")
    corr_pairs.to_csv(corr_path, index=False)

    logger.info(
        "Collinearity report written to %s (%d features dropped)", output_path, len(dropped)
    )
