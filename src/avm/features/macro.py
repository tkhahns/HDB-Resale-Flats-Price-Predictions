"""Merge macroeconomic features onto transaction records."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_MACRO_COLS = [
    "sora_3m",
    "cpi_all_items",
    "cpi_housing",
    "hdb_rpi",
    "gdp_growth_qoq",
    "unemployment_rate",
    "cooling_measure",
]


def merge_macro_features(
    transactions_df: pd.DataFrame,
    macro_df: pd.DataFrame,
    lag_months: int = 1,
) -> pd.DataFrame:
    """Left-join macro series onto transactions on transaction month.

    Applies a lag so that a transaction in month T only sees macro data from
    month T-lag_months, preventing look-ahead leakage.
    """
    macro = macro_df.copy()
    macro["month"] = macro["month"] + pd.DateOffset(months=lag_months)
    macro["_merge_month"] = macro["month"].dt.to_period("M")

    tx = transactions_df.copy()
    if tx["month"].dtype == "object":
        tx["month"] = pd.to_datetime(tx["month"])
    tx["_merge_month"] = tx["month"].dt.to_period("M")

    macro_slim = macro[["_merge_month"] + _MACRO_COLS].drop_duplicates("_merge_month")
    merged = tx.merge(macro_slim, on="_merge_month", how="left")
    merged.drop(columns=["_merge_month"], inplace=True)

    missing = merged[_MACRO_COLS[0]].isna().sum()
    if missing:
        logger.warning("%d rows have no macro data after lag-merge", missing)
    else:
        logger.info("Macro features merged successfully for all %d rows", len(merged))

    return merged
