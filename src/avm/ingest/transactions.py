"""Load HDB resale transaction data from local CSV or data.gov.sg API."""

import logging
import time

import pandas as pd
import requests

from src.avm.io import storage

logger = logging.getLogger(__name__)

_DATAGOV_RESOURCE_ID = "f1765b54-a209-4718-8d38-a39237f502b3"
_DATAGOV_API = "https://data.gov.sg/api/action/datastore_search"
_PAGE_LIMIT = 1000


def load_from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m")
    logger.info("Loaded %d transactions from %s", len(df), path)
    return df


def fetch_from_datagov(
    output_path: str,
    start_date: str = "2017-01",
    end_date: str = "2024-03",
) -> pd.DataFrame:
    """Fetch all HDB resale transactions from data.gov.sg and save to CSV."""
    records = []
    offset = 0
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    logger.info("Fetching transactions from data.gov.sg (this may take a few minutes)…")
    while True:
        resp = requests.get(
            _DATAGOV_API,
            params={"resource_id": _DATAGOV_RESOURCE_ID, "limit": _PAGE_LIMIT, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()["result"]["records"]
        if not page:
            break
        records.extend(page)
        offset += _PAGE_LIMIT
        logger.debug("Fetched %d records so far", len(records))
        time.sleep(0.1)

    df = pd.DataFrame(records)
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m")
    df = df[(df["month"] >= start_ts) & (df["month"] <= end_ts)].reset_index(drop=True)

    storage.makedirs(output_path)
    df.to_csv(output_path, index=False)
    logger.info("Saved %d transactions to %s", len(df), output_path)
    return df


def generate_synthetic_transactions(n: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic transaction DataFrame for testing purposes."""
    import numpy as np

    rng = np.random.default_rng(seed)
    towns = [
        "ANG MO KIO",
        "BEDOK",
        "BISHAN",
        "BUKIT BATOK",
        "BUKIT MERAH",
        "BUKIT TIMAH",
        "CENTRAL AREA",
        "CHOA CHU KANG",
        "CLEMENTI",
        "GEYLANG",
        "HOUGANG",
        "JURONG EAST",
        "JURONG WEST",
        "KALLANG/WHAMPOA",
        "MARINE PARADE",
        "PASIR RIS",
        "PUNGGOL",
        "QUEENSTOWN",
        "SEMBAWANG",
        "SENGKANG",
        "SERANGOON",
        "TAMPINES",
        "TOA PAYOH",
        "WOODLANDS",
        "YISHUN",
    ]
    flat_types = ["2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE"]
    flat_models = ["Model A", "Improved", "New Generation", "Premium Apartment", "Standard"]
    storey_bands = [
        "01 TO 03",
        "04 TO 06",
        "07 TO 09",
        "10 TO 12",
        "13 TO 15",
        "16 TO 18",
        "19 TO 21",
    ]
    months = pd.date_range("2017-01", "2024-03", freq="MS")

    chosen_months = rng.choice(months, size=n)
    chosen_towns = rng.choice(towns, size=n)
    chosen_types = rng.choice(flat_types, size=n, p=[0.05, 0.25, 0.35, 0.25, 0.10])
    floor_area = rng.uniform(40, 180, size=n).round(1)
    base_price = floor_area * rng.uniform(4000, 8000, size=n)

    df = pd.DataFrame(
        {
            "month": chosen_months,
            "town": chosen_towns,
            "flat_type": chosen_types,
            "block": rng.integers(1, 999, size=n).astype(str),
            "street_name": rng.choice(
                ["ANG MO KIO AVE 1", "BEDOK NORTH RD", "BISHAN ST 11", "CLEMENTI AVE 2"], size=n
            ),
            "storey_range": rng.choice(storey_bands, size=n),
            "floor_area_sqm": floor_area,
            "flat_model": rng.choice(flat_models, size=n),
            "lease_commence_date": rng.integers(1970, 2020, size=n),
            "remaining_lease": [
                f"{y} years {m} months"
                for y, m in zip(rng.integers(40, 95, size=n), rng.integers(0, 11, size=n))
            ],
            "resale_price": base_price.astype(int),
        }
    )
    return df
