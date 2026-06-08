"""Geocode HDB buildings and schools via the OneMap API."""

import asyncio
import logging

import aiohttp
import nest_asyncio
import pandas as pd

nest_asyncio.apply()
logger = logging.getLogger(__name__)

_ONEMAP_URL = "https://www.onemap.gov.sg/api/common/elastic/search"


async def _fetch_coords(
    session: aiohttp.ClientSession, query: str
) -> tuple[float | None, float | None]:
    params = {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": "1"}
    try:
        async with session.get(
            _ONEMAP_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            data = await resp.json()
            result = data["results"][0]
            return float(result["LATITUDE"]), float(result["LONGITUDE"])
    except Exception:
        return None, None


async def _batch_geocode(queries: list[str]) -> list[tuple[float | None, float | None]]:
    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_coords(session, q) for q in queries]
        return await asyncio.gather(*tasks)


def geocode_buildings(buildings_df: pd.DataFrame) -> pd.DataFrame:
    """Add latitude/longitude to a DataFrame with 'block' and 'street_name' columns."""
    queries = [f"{row.block} {row.street_name}" for row in buildings_df.itertuples()]
    results = asyncio.run(_batch_geocode(queries))
    out = buildings_df.copy()
    out["latitude"] = [r[0] for r in results]
    out["longitude"] = [r[1] for r in results]
    missing = out["latitude"].isna().sum()
    if missing:
        logger.warning("Failed to geocode %d / %d buildings", missing, len(out))
    return out


def geocode_schools(schools_df: pd.DataFrame, name_col: str = "school_name") -> pd.DataFrame:
    """Add lat/lon to schools DataFrame, falling back to postal_code on failure."""
    import numpy as np

    out = schools_df.copy()
    if "lat" in out.columns and "long" in out.columns and out["lat"].notna().all():
        logger.info("Schools already have coordinates — skipping geocoding")
        return out

    queries = schools_df[name_col].tolist()
    results = asyncio.run(_batch_geocode(queries))
    out["lat"] = [r[0] for r in results]
    out["long"] = [r[1] for r in results]

    if "postal_code" in out.columns:
        missing_idx = out[out["lat"].isna()].index
        if len(missing_idx):
            retry_queries = out.loc[missing_idx, "postal_code"].astype(str).tolist()
            retry_results = asyncio.run(_batch_geocode(retry_queries))
            out.loc[missing_idx, "lat"] = [r[0] if r[0] is not None else np.nan for r in retry_results]
            out.loc[missing_idx, "long"] = [r[1] if r[1] is not None else np.nan for r in retry_results]

    return out


def load_mrt_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def load_schools_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)
