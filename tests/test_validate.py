"""Unit tests for data validation module."""

import pandas as pd
import pytest

from src.avm.validate.schema import (
    check_drift,
    validate_macro,
    validate_transactions,
)
from src.avm.ingest.macro import generate_synthetic_macro


def _valid_transactions(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": pd.date_range("2020-01", periods=n, freq="MS"),
            "town": ["ANG MO KIO"] * n,
            "flat_type": ["4 ROOM"] * n,
            "block": ["123"] * n,
            "street_name": ["ANG MO KIO AVE 1"] * n,
            "storey_range": ["07 TO 09"] * n,
            "floor_area_sqm": [93.0] * n,
            "flat_model": ["Model A"] * n,
            "lease_commence_date": [1998] * n,
            "remaining_lease": ["73 years 05 months"] * n,
            "resale_price": [500_000.0] * n,
        }
    )


class TestValidateTransactions:
    def test_valid_data_passes(self):
        df = _valid_transactions()
        result = validate_transactions(df)
        assert result["passed"] is True
        assert result["errors"] == []

    def test_price_out_of_range_fails(self):
        df = _valid_transactions()
        df.loc[0, "resale_price"] = 10.0  # below minimum
        result = validate_transactions(df)
        assert result["passed"] is False

    def test_floor_area_out_of_range_fails(self):
        df = _valid_transactions()
        df.loc[0, "floor_area_sqm"] = 5.0  # below 30 sqm min
        result = validate_transactions(df)
        assert result["passed"] is False


class TestValidateMacro:
    def test_synthetic_macro_passes(self, tmp_path):
        macro_path = str(tmp_path / "macro.csv")
        macro_df = generate_synthetic_macro(macro_path)
        result = validate_macro(macro_df)
        assert result["passed"] is True


class TestCheckDrift:
    def _make_df(self, mean: float, n: int = 200) -> pd.DataFrame:
        import numpy as np
        rng = np.random.default_rng(42)
        return pd.DataFrame(
            {
                "resale_price": rng.normal(mean, 50_000, n),
                "floor_area_sqm": rng.normal(95, 15, n),
            }
        )

    def test_same_distribution_no_drift(self):
        df_train = self._make_df(500_000)
        df_test = self._make_df(500_000)
        result = check_drift(df_train, df_test)
        assert "drift_by_feature" in result
        assert isinstance(result["flagged_features"], list)

    def test_large_shift_flagged(self):
        df_train = self._make_df(400_000, n=500)
        df_test = self._make_df(800_000, n=500)  # very different mean
        result = check_drift(df_train, df_test, psi_threshold=0.1)
        assert "resale_price" in result["flagged_features"]
