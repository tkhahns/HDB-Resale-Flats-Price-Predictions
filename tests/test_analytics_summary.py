"""Unit tests for _write_analytics_summary in pipeline.py."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest


def _make_cfg(reports_dir: str) -> dict:
    return {"data": {"reports_dir": reports_dir}}


def test_write_analytics_summary_creates_file():
    from src.avm.pipeline import _write_analytics_summary

    fold_results = [
        {
            "fold": 1,
            "test_start": "2023-01",
            "test_end": "2023-06",
            "n_train": 1000,
            "n_test": 200,
            "MAPE_pct": 5.43,
            "MAE": 18000.0,
            "RMSE": 24000.0,
            "signed_error": -500.0,
        }
    ]
    all_metrics = {
        "lgbm": {"MAE": 19000.0, "RMSE": 25000.0, "MAPE_pct": 5.8},
        "xgboost": {"MAE": 20000.0, "RMSE": 26000.0, "MAPE_pct": 6.1},
        "ensemble": {"MAE": 18000.0, "RMSE": 24000.0, "MAPE_pct": 5.43},
    }
    seg_results = {
        "flat_type": pd.DataFrame(
            [
                {
                    "flat_type": "4 ROOM",
                    "n": 500,
                    "mean_signed_error": -200.0,
                    "mae": 15000.0,
                    "mape_pct": 4.5,
                }
            ]
        ),
        "town": pd.DataFrame(
            [
                {
                    "town": "TAMPINES",
                    "n": 300,
                    "mean_signed_error": 100.0,
                    "mae": 12000.0,
                    "mape_pct": 3.9,
                }
            ]
        ),
    }
    price_band = pd.DataFrame(
        [
            {
                "price_band": 0,
                "price_min": 200000.0,
                "price_max": 400000.0,
                "n": 100,
                "mean_signed_error": 500.0,
                "mae": 8000.0,
            }
        ]
    )
    fi_df = pd.DataFrame(
        [
            {
                "Feature": "floor_area_sqm",
                "LGBM_importance": 0.35,
                "XGB_importance": 0.30,
                "mean_importance": 0.325,
            }
        ]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = _make_cfg(tmpdir)
        _write_analytics_summary(
            cfg,
            run_date="2026-06-08",
            all_metrics=all_metrics,
            fold_results=fold_results,
            seg_results=seg_results,
            price_band=price_band,
            fi_df=fi_df,
            n_train=1000,
            n_test=200,
        )

        out = Path(tmpdir) / "analytics.json"
        assert out.exists(), "analytics.json not created"

        data = json.loads(out.read_text())
        assert data["run_date"] == "2026-06-08"
        assert data["n_train"] == 1000
        assert data["n_test"] == 200
        assert "ensemble" in data["metrics"]
        assert len(data["backtest_folds"]) == 1
        assert data["backtest_folds"][0]["MAPE_pct"] == pytest.approx(5.43)
        assert len(data["bias_by_flat_type"]) == 1
        assert data["bias_by_flat_type"][0]["flat_type"] == "4 ROOM"
        assert len(data["feature_importance_top20"]) == 1
        assert data["feature_importance_top20"][0]["Feature"] == "floor_area_sqm"


def test_write_analytics_summary_empty_segments():
    from src.avm.pipeline import _write_analytics_summary

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = _make_cfg(tmpdir)
        _write_analytics_summary(
            cfg,
            run_date="2026-06-08",
            all_metrics={"lgbm": {}, "xgboost": {}, "ensemble": {}},
            fold_results=[],
            seg_results={},
            price_band=pd.DataFrame(),
            fi_df=pd.DataFrame(),
            n_train=0,
            n_test=0,
        )
        data = json.loads((Path(tmpdir) / "analytics.json").read_text())
        assert data["backtest_folds"] == []
        assert data["bias_by_flat_type"] == []
        assert data["feature_importance_top20"] == []
