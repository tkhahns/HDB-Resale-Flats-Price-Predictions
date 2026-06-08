"""Data validation: schema checks, range checks, and drift detection."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema, Check
from scipy import stats

logger = logging.getLogger(__name__)

TRANSACTION_SCHEMA = DataFrameSchema(
    {
        "month": Column(pa.DateTime, nullable=False),
        "town": Column(str, nullable=False),
        "flat_type": Column(str, nullable=False),
        "block": Column(str, nullable=False),
        "street_name": Column(str, nullable=False),
        "storey_range": Column(str, nullable=False),
        "floor_area_sqm": Column(float, Check.between(30, 250), nullable=False),
        "flat_model": Column(str, nullable=False),
        "lease_commence_date": Column(int, Check.between(1960, 2024), nullable=False),
        "remaining_lease": Column(str, nullable=False),
        "resale_price": Column(float, Check.between(50_000, 2_000_000), nullable=False),
    },
    coerce=True,
)

MACRO_SCHEMA = DataFrameSchema(
    {
        "month": Column(pa.DateTime, nullable=False),
        "sora_3m": Column(float, Check.between(-1, 15), nullable=False),
        "cpi_all_items": Column(float, Check.between(80, 150), nullable=False),
        "cpi_housing": Column(float, Check.between(80, 150), nullable=False),
        "hdb_rpi": Column(float, Check.between(80, 250), nullable=False),
        "gdp_growth_qoq": Column(float, Check.between(-20, 20), nullable=False),
        "unemployment_rate": Column(float, Check.between(0, 10), nullable=False),
        "cooling_measure": Column(int, Check.isin([0, 1]), nullable=False),
    },
    coerce=True,
)


def validate_transactions(df: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {"passed": True, "errors": []}
    try:
        TRANSACTION_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        results["passed"] = False
        results["errors"] = exc.failure_cases.to_dict("records")
        logger.error("Schema validation failed: %d errors", len(results["errors"]))
    return results


def validate_macro(df: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {"passed": True, "errors": []}
    try:
        MACRO_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        results["passed"] = False
        results["errors"] = exc.failure_cases.to_dict("records")
    return results


def _psi(expected: pd.Series, actual: pd.Series, buckets: int = 10) -> float:
    """Population Stability Index between two numeric distributions."""
    breakpoints = pd.qcut(expected, q=buckets, duplicates="drop", retbins=True)[1]
    exp_pct = pd.cut(expected, bins=breakpoints, include_lowest=True).value_counts(normalize=True).sort_index()
    act_pct = pd.cut(actual, bins=breakpoints, include_lowest=True).value_counts(normalize=True).sort_index()
    exp_pct = exp_pct.reindex(act_pct.index, fill_value=1e-4)
    act_pct = act_pct.reindex(exp_pct.index, fill_value=1e-4)
    return float(((act_pct - exp_pct) * (act_pct / exp_pct).apply(pd.np.log if hasattr(pd, "np") else __import__("numpy").log)).sum())


def check_drift(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    numeric_cols: list[str] | None = None,
    psi_threshold: float = 0.2,
) -> dict[str, Any]:
    """Run KS-test and PSI on numeric columns; flag columns above threshold."""
    import numpy as np

    if numeric_cols is None:
        numeric_cols = df_train.select_dtypes(include="number").columns.tolist()

    drift_results: dict[str, dict] = {}
    flagged = []

    for col in numeric_cols:
        if col not in df_test.columns:
            continue
        exp = df_train[col].dropna().values
        act = df_test[col].dropna().values
        ks_stat, ks_p = stats.ks_2samp(exp, act)

        # PSI: use bins spanning the range of both distributions so
        # non-overlapping distributions yield a high score.
        combined_min = min(exp.min(), act.min())
        combined_max = max(exp.max(), act.max())
        bins = np.linspace(combined_min, combined_max, 11)
        exp_counts, _ = np.histogram(exp, bins=bins)
        act_counts, _ = np.histogram(act, bins=bins)
        eps = 1e-4
        exp_pct = np.where(exp_counts == 0, eps, exp_counts / exp_counts.sum())
        act_pct = np.where(act_counts == 0, eps, act_counts / act_counts.sum())
        psi = float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))

        drift_results[col] = {"ks_stat": round(ks_stat, 4), "ks_p": round(ks_p, 4), "psi": round(psi, 4)}
        if psi > psi_threshold:
            flagged.append(col)

    if flagged:
        logger.warning("Drift detected in %d features: %s", len(flagged), flagged)
    else:
        logger.info("No significant drift detected across %d features", len(numeric_cols))

    return {"drift_by_feature": drift_results, "flagged_features": flagged}


def check_geocoding_coverage(buildings_df: pd.DataFrame, min_coverage: float = 0.99) -> bool:
    coverage = buildings_df["latitude"].notna().mean()
    ok = coverage >= min_coverage
    if not ok:
        logger.error("Geocoding coverage %.1f%% below threshold %.1f%%", coverage * 100, min_coverage * 100)
    return ok


def check_macro_completeness(transactions_df: pd.DataFrame, macro_df: pd.DataFrame) -> list[str]:
    """Return transaction months not present in the (lagged) macro table."""
    tx_months = transactions_df["month"].dt.to_period("M").unique()
    mac_months = macro_df["month"].dt.to_period("M").unique()
    missing = [str(m) for m in tx_months if m not in mac_months]
    if missing:
        logger.warning("Macro data missing for %d transaction months: %s", len(missing), missing[:5])
    return missing


def generate_validation_report(results: dict[str, Any], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    lines = ["<html><body>", "<h1>Validation Report</h1>"]
    for key, val in results.items():
        lines.append(f"<h2>{key}</h2><pre>{val}</pre>")
    lines += ["</body></html>"]
    Path(output_path).write_text("\n".join(lines))
    logger.info("Validation report written to %s", output_path)
