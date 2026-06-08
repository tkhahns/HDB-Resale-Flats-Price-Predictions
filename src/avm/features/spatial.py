"""Spatial feature engineering: distances to MRT stations and schools."""

import logging

import pandas as pd
from geopy.distance import geodesic

logger = logging.getLogger(__name__)

_SCHOOL_LEVELS = ("PRIMARY", "SECONDARY", "MIXED LEVELS")
_ELITE_INDICATORS = ("sap_ind", "autonomous_ind", "gifted_ind", "ip_ind")


def _nearest_geodesic(
    lat: float, lon: float, ref_lats: pd.Series, ref_lons: pd.Series
) -> tuple[float, int]:
    """Return (min_distance_km, index_of_nearest) for a single point."""
    min_dist = float("inf")
    min_idx = -1
    for i, (rlat, rlon) in enumerate(zip(ref_lats, ref_lons)):
        d = geodesic((lat, lon), (rlat, rlon)).km
        if d < min_dist:
            min_dist = d
            min_idx = i
    return min_dist, min_idx


def compute_mrt_features(buildings_df: pd.DataFrame, mrt_df: pd.DataFrame) -> pd.DataFrame:
    """Add shortest_distance_to_closest_mrt and closest_mrt columns."""
    import math

    distances, names = [], []
    for row in buildings_df.itertuples():
        lat, lon = row.latitude, row.longitude
        if lat is None or lon is None or (isinstance(lat, float) and math.isnan(lat)):
            distances.append(float("nan"))
            names.append(None)
            continue
        dist, idx = _nearest_geodesic(lat, lon, mrt_df["lat"], mrt_df["lng"])
        distances.append(round(dist, 4))
        names.append(mrt_df["station_name"].iloc[idx])

    out = buildings_df.copy()
    out["shortest_distance_to_closest_mrt"] = distances
    out["closest_mrt"] = names
    logger.info("Computed MRT distances for %d buildings", len(out))
    return out


def compute_school_features(buildings_df: pd.DataFrame, schools_df: pd.DataFrame) -> pd.DataFrame:
    """Add closest school name (by level) for each building."""
    import math

    pri = schools_df[schools_df["mainlevel_code"] == "PRIMARY"].reset_index(drop=True)
    sec = schools_df[schools_df["mainlevel_code"] == "SECONDARY"].reset_index(drop=True)
    mixed = schools_df[schools_df["mainlevel_code"] == "MIXED LEVELS"].reset_index(drop=True)

    closest_pri, closest_sec, closest_mixed = [], [], []
    for row in buildings_df.itertuples():
        lat, lon = row.latitude, row.longitude
        if lat is None or lon is None or (isinstance(lat, float) and math.isnan(lat)):
            closest_pri.append(None)
            closest_sec.append(None)
            closest_mixed.append(None)
            continue
        _, i = _nearest_geodesic(lat, lon, pri["lat"], pri["long"])
        closest_pri.append(pri["school_name"].iloc[i] if len(pri) else None)
        _, i = _nearest_geodesic(lat, lon, sec["lat"], sec["long"])
        closest_sec.append(sec["school_name"].iloc[i] if len(sec) else None)
        _, i = _nearest_geodesic(lat, lon, mixed["lat"], mixed["long"])
        closest_mixed.append(mixed["school_name"].iloc[i] if len(mixed) else None)

    out = buildings_df.copy()
    out["closest_pri_sch"] = closest_pri
    out["closest_sec_sch"] = closest_sec
    out["closest_mixed_sch"] = closest_mixed
    return out


def is_elite(school_name: str, schools_df: pd.DataFrame) -> bool:
    """Return True if the named school has any elite designation."""
    rows = schools_df[schools_df["school_name"] == school_name]
    if rows.empty:
        return False
    row = rows.iloc[0]
    return any(row.get(col, "No") == "Yes" for col in _ELITE_INDICATORS)


def add_elite_flags(df: pd.DataFrame, schools_df: pd.DataFrame) -> pd.DataFrame:
    """Replace closest_*_sch school name columns with binary elite flags."""
    out = df.copy()
    for col, flag_col in [
        ("closest_pri_sch", "is_elite_closest_pri_sch"),
        ("closest_sec_sch", "is_elite_closest_sec_sch"),
        ("closest_mixed_sch", "is_elite_closest_mixed_sch"),
    ]:
        if col in out.columns:
            out[flag_col] = out[col].apply(
                lambda s: is_elite(s, schools_df) if pd.notna(s) else False
            )
            out.drop(columns=[col], inplace=True)
    return out
