"""Unit tests for collinearity detection and pruning."""

import numpy as np
import pandas as pd

from src.avm.collinearity import (
    compute_vif,
    correlation_screen,
    prune_by_vif,
)


def _make_independent_df(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "x1": rng.normal(0, 1, n),
            "x2": rng.normal(0, 1, n),
            "x3": rng.normal(0, 1, n),
        }
    )


def _make_collinear_df(n: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n)
    x2 = x1 * 0.99 + rng.normal(0, 0.01, n)  # near-perfect collinearity
    x3 = rng.normal(0, 1, n)
    return pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})


class TestComputeVIF:
    def test_returns_dataframe(self):
        df = _make_independent_df()
        result = compute_vif(df)
        assert isinstance(result, pd.DataFrame)
        assert "Feature" in result.columns
        assert "VIF" in result.columns

    def test_independent_features_low_vif(self):
        df = _make_independent_df(n=500)
        result = compute_vif(df)
        assert (result["VIF"] < 5).all(), (
            f"Expected VIF < 5 for independent features, got:\n{result}"
        )

    def test_collinear_features_high_vif(self):
        df = _make_collinear_df()
        result = compute_vif(df)
        # x1 and x2 are nearly collinear — at least one should have very high VIF
        assert result["VIF"].max() > 10


class TestPruneByVif:
    def test_independent_features_unchanged(self):
        df = _make_independent_df(n=500)
        pruned, dropped = prune_by_vif(df, threshold=10.0)
        assert len(dropped) == 0
        assert set(pruned.columns) == set(df.columns)

    def test_collinear_feature_dropped(self):
        df = _make_collinear_df()
        pruned, dropped = prune_by_vif(df, threshold=10.0)
        assert len(dropped) >= 1
        # After pruning, remaining VIF should be < threshold
        if pruned.shape[1] >= 2:
            vif_after = compute_vif(pruned)
            assert (vif_after["VIF"].dropna() < 10.0).all()

    def test_protected_column_never_dropped(self):
        df = _make_collinear_df()
        df["target"] = np.random.default_rng(0).normal(0, 1, len(df))
        _, dropped = prune_by_vif(df, threshold=5.0, protected=["target"])
        assert "target" not in dropped


class TestCorrelationScreen:
    def test_no_pairs_for_independent_features(self):
        df = _make_independent_df(n=1000)
        result = correlation_screen(df, threshold=0.85)
        assert len(result) == 0

    def test_detects_collinear_pair(self):
        df = _make_collinear_df()
        result = correlation_screen(df, threshold=0.85)
        assert len(result) >= 1
        found = result[
            (result["feature_a"].isin(["x1", "x2"])) & (result["feature_b"].isin(["x1", "x2"]))
        ]
        assert len(found) == 1

    def test_returns_sorted_by_correlation(self):
        df = _make_collinear_df()
        result = correlation_screen(df, threshold=0.5)
        if len(result) > 1:
            assert result["pearson_r"].iloc[0] >= result["pearson_r"].iloc[-1]
