"""Building-level feature engineering: type conversions and property merges."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_YN_COLS = [
    "residential",
    "commercial",
    "market_hawker",
    "miscellaneous",
    "multistorey_carpark",
    "precinct_pavilion",
]
_PROPERTY_DROP_COLS = [
    "1room_sold",
    "2room_sold",
    "3room_sold",
    "4room_sold",
    "5room_sold",
    "exec_sold",
    "multigen_sold",
    "studio_apartment_sold",
    "1room_rental",
    "2room_rental",
    "3room_rental",
    "other_room_rental",
]


def convert_storey_range_to_median(df: pd.DataFrame) -> pd.DataFrame:
    """Convert '07 TO 09' storey range strings to the numeric median (8.0)."""
    out = df.copy()
    out["storey_range"] = (
        out["storey_range"].str.split(" TO ").apply(lambda x: (int(x[0]) + int(x[1])) / 2)
    )
    return out


def convert_remaining_lease_to_months(df: pd.DataFrame) -> pd.DataFrame:
    """Convert '73 years 05 months' strings to total months (integer)."""

    def _parse(s: str) -> int:
        parts = s.split()
        years = int(parts[0])
        months = int(parts[2]) if "months" in s else 0
        return years * 12 + months

    out = df.copy()
    out["remaining_lease"] = out["remaining_lease"].apply(_parse)
    return out


def map_yn_to_bool(df: pd.DataFrame, cols: list[str] | None = None) -> pd.DataFrame:
    """Map 'Y'/'N' strings to True/False for the given columns."""
    cols = cols or _YN_COLS
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = out[col].map({"Y": True, "N": False})
    return out


def expand_transaction_date(df: pd.DataFrame) -> pd.DataFrame:
    """Split month column into year and month_numeric; preserve as transaction_month for CV."""
    out = df.copy()
    ts = pd.to_datetime(out["month"])
    out["transaction_month"] = ts  # kept for walk-forward CV date slicing; excluded from model
    out["year"] = ts.dt.year
    out["month_numeric"] = ts.dt.month
    out.drop(columns=["month"], inplace=True)
    return out


def merge_property_info(transactions_df: pd.DataFrame, property_df: pd.DataFrame) -> pd.DataFrame:
    """Merge HDB property information on block + street_name."""
    prop = property_df.copy()
    prop = prop.drop(columns=[c for c in _PROPERTY_DROP_COLS if c in prop.columns], errors="ignore")
    prop = prop.rename(columns={"blk_no": "block", "street": "street_name"})
    merged = pd.merge(transactions_df, prop, on=["block", "street_name"], how="left")
    missing = merged["max_floor_lvl"].isna().sum() if "max_floor_lvl" in merged.columns else 0
    if missing:
        logger.warning("Property info missing for %d rows after merge", missing)
    return merged


def impute_unseen_categories(
    df_test: pd.DataFrame, df_train: pd.DataFrame, col: str, fallback: str
) -> pd.DataFrame:
    """Replace categories in df_test that don't appear in df_train with fallback."""
    seen = set(df_train[col].dropna().unique())
    mask = ~df_test[col].isin(seen)
    count = mask.sum()
    if count:
        logger.info("Imputing %d unseen '%s' values → '%s'", count, col, fallback)
        df_test = df_test.copy()
        df_test.loc[mask, col] = fallback
    return df_test
