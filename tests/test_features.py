"""Unit tests for feature engineering modules."""

import numpy as np
import pandas as pd
import pytest

from src.avm.features.building import (
    convert_remaining_lease_to_months,
    convert_storey_range_to_median,
    expand_transaction_date,
    impute_unseen_categories,
    map_yn_to_bool,
)
from src.avm.features.macro import merge_macro_features
from src.avm.features.spatial import is_elite

# ---------------------------------------------------------------------------
# Building features
# ---------------------------------------------------------------------------


class TestStoreyRange:
    def test_median_basic(self):
        df = pd.DataFrame({"storey_range": ["01 TO 03", "10 TO 12", "19 TO 21"]})
        result = convert_storey_range_to_median(df)
        assert result["storey_range"].tolist() == [2.0, 11.0, 20.0]

    def test_single_storey_band(self):
        df = pd.DataFrame({"storey_range": ["04 TO 06"]})
        result = convert_storey_range_to_median(df)
        assert result["storey_range"].iloc[0] == 5.0

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({"storey_range": ["01 TO 03"]})
        original = df.copy()
        convert_storey_range_to_median(df)
        pd.testing.assert_frame_equal(df, original)


class TestRemainingLease:
    def test_years_and_months(self):
        df = pd.DataFrame({"remaining_lease": ["73 years 05 months"]})
        result = convert_remaining_lease_to_months(df)
        assert result["remaining_lease"].iloc[0] == 73 * 12 + 5

    def test_years_only(self):
        df = pd.DataFrame({"remaining_lease": ["60 years"]})
        result = convert_remaining_lease_to_months(df)
        assert result["remaining_lease"].iloc[0] == 720

    def test_multiple_rows(self):
        df = pd.DataFrame({"remaining_lease": ["50 years 00 months", "80 years 11 months"]})
        result = convert_remaining_lease_to_months(df)
        assert result["remaining_lease"].tolist() == [600, 80 * 12 + 11]


class TestMapYnToBool:
    def test_y_to_true(self):
        df = pd.DataFrame({"residential": ["Y", "N", "Y"]})
        result = map_yn_to_bool(df, cols=["residential"])
        assert result["residential"].tolist() == [True, False, True]

    def test_non_yn_cols_unchanged(self):
        df = pd.DataFrame({"other_col": [1, 2, 3]})
        result = map_yn_to_bool(df, cols=["residential"])
        assert "other_col" in result.columns


class TestExpandTransactionDate:
    def test_year_month_extracted(self):
        df = pd.DataFrame({"month": pd.to_datetime(["2021-04", "2023-09"])})
        result = expand_transaction_date(df)
        assert "year" in result.columns
        assert "month_numeric" in result.columns
        assert "month" not in result.columns
        assert result["year"].tolist() == [2021, 2023]
        assert result["month_numeric"].tolist() == [4, 9]


class TestImputeUnseenCategories:
    def test_unseen_replaced(self):
        df_train = pd.DataFrame({"flat_model": ["Model A", "Improved", "Standard"]})
        df_test = pd.DataFrame({"flat_model": ["Model A", "2-room", "3Gen"]})
        result = impute_unseen_categories(df_test, df_train, "flat_model", "Model A")
        assert set(result["flat_model"].unique()).issubset({"Model A", "Improved", "Standard"})

    def test_seen_categories_unchanged(self):
        df_train = pd.DataFrame({"flat_model": ["Model A", "Improved"]})
        df_test = pd.DataFrame({"flat_model": ["Model A", "Improved"]})
        result = impute_unseen_categories(df_test, df_train, "flat_model", "Model A")
        assert result["flat_model"].tolist() == ["Model A", "Improved"]


# ---------------------------------------------------------------------------
# Spatial features
# ---------------------------------------------------------------------------


class TestIsElite:
    def _make_schools(self):
        return pd.DataFrame(
            {
                "school_name": ["Raffles Institution", "Some School"],
                "sap_ind": ["No", "No"],
                "autonomous_ind": ["Yes", "No"],
                "gifted_ind": ["No", "No"],
                "ip_ind": ["Yes", "No"],
            }
        )

    def test_elite_school_detected(self):
        schools = self._make_schools()
        assert is_elite("Raffles Institution", schools) is True

    def test_non_elite_school(self):
        schools = self._make_schools()
        assert is_elite("Some School", schools) is False

    def test_unknown_school_returns_false(self):
        schools = self._make_schools()
        assert is_elite("Ghost School", schools) is False


# ---------------------------------------------------------------------------
# Macro features
# ---------------------------------------------------------------------------


class TestMacroMerge:
    def _make_macro(self):
        months = pd.date_range("2020-01", "2024-03", freq="MS")
        return pd.DataFrame(
            {
                "month": months,
                "sora_3m": np.linspace(0.2, 4.0, len(months)),
                "cpi_all_items": np.linspace(99, 112, len(months)),
                "cpi_housing": np.linspace(99, 110, len(months)),
                "hdb_rpi": np.linspace(129, 185, len(months)),
                "gdp_growth_qoq": np.linspace(-13, 3, len(months)),
                "unemployment_rate": np.linspace(3.0, 2.0, len(months)),
                "cooling_measure": [0] * len(months),
            }
        )

    def _make_transactions(self):
        return pd.DataFrame(
            {
                "month": pd.to_datetime(["2021-06", "2022-12", "2023-09"]),
                "resale_price": [450000, 550000, 600000],
            }
        )

    def test_macro_columns_added(self):
        macro = self._make_macro()
        tx = self._make_transactions()
        result = merge_macro_features(tx, macro, lag_months=1)
        for col in ["sora_3m", "cpi_all_items", "hdb_rpi"]:
            assert col in result.columns

    def test_lag_prevents_future_leakage(self):
        """With lag=1, transaction in month T should see macro from T-1, not T."""
        macro = pd.DataFrame(
            {
                "month": pd.to_datetime(["2021-01", "2021-02"]),
                "sora_3m": [1.0, 2.0],
                "cpi_all_items": [100.0, 101.0],
                "cpi_housing": [100.0, 101.0],
                "hdb_rpi": [140.0, 141.0],
                "gdp_growth_qoq": [3.0, 3.1],
                "unemployment_rate": [2.2, 2.1],
                "cooling_measure": [0, 0],
            }
        )
        tx = pd.DataFrame({"month": pd.to_datetime(["2021-02"]), "resale_price": [500000]})
        result = merge_macro_features(tx, macro, lag_months=1)
        # Transaction in Feb should see Jan's macro (sora_3m=1.0), not Feb's (2.0)
        assert result["sora_3m"].iloc[0] == pytest.approx(1.0)

    def test_no_macro_rows_missing(self):
        macro = self._make_macro()
        tx = self._make_transactions()
        result = merge_macro_features(tx, macro, lag_months=1)
        assert result["sora_3m"].notna().all()
