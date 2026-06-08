"""Request-time feature assembly for the prediction API.

Assembles a raw feature DataFrame from a PredictionRequest so it matches
the format the preprocessor expects.  This reuses the same transformations
applied during training (storey_range median, remaining_lease months, etc.).

Macro features (sora_3m, cpi_all_items, etc.) change monthly.  The bundle
manifest stores `latest_macro` — the last row of the macro CSV seen at
training time.  Pass it via `macro_values` so they are included in the
feature matrix exactly as during training.
"""

from typing import Optional

import pandas as pd

from src.avm.api.schemas import PredictionRequest
from src.avm.features.building import (
    convert_remaining_lease_to_months,
    convert_storey_range_to_median,
    expand_transaction_date,
    map_yn_to_bool,
)

_YN_COLS = [
    "residential",
    "commercial",
    "market_hawker",
    "miscellaneous",
    "multistorey_carpark",
    "precinct_pavilion",
]

_MACRO_COLS = [
    "sora_3m",
    "cpi_all_items",
    "cpi_housing",
    "hdb_rpi",
    "gdp_growth_qoq",
    "unemployment_rate",
    "cooling_measure",
]


def build_feature_df(
    request: PredictionRequest,
    macro_values: Optional[dict] = None,
) -> pd.DataFrame:
    """Convert a single PredictionRequest into a one-row feature DataFrame.

    Args:
        request: Validated prediction request.
        macro_values: Dict of macro feature values (from bundle.manifest["latest_macro"]).
                      If omitted, macro columns are excluded from the feature row.
    """
    row: dict = {
        "town": request.town,
        "flat_type": request.flat_type,
        "storey_range": request.storey_range,
        "floor_area_sqm": float(request.floor_area_sqm),
        "flat_model": request.flat_model,
        "lease_commence_date": int(request.lease_commence_date),
        "remaining_lease": request.remaining_lease,
        "block": request.block,
        "street_name": request.street_name,
    }
    # Add missing Y/N columns as "N" (most buildings lack these fields in real-time)
    for col in _YN_COLS:
        row[col] = "N"

    # Inject macro features from bundle manifest (latest known values)
    if macro_values:
        for col in _MACRO_COLS:
            if col in macro_values:
                row[col] = macro_values[col]

    # Use transaction_month if provided, otherwise today
    if request.transaction_month:
        row["month"] = pd.Timestamp(request.transaction_month)
    else:
        row["month"] = pd.Timestamp.now().normalize()

    df = pd.DataFrame([row])
    df = convert_storey_range_to_median(df)
    df = convert_remaining_lease_to_months(df)
    df = map_yn_to_bool(df)
    df = expand_transaction_date(df)
    return df
