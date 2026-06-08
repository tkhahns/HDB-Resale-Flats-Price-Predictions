"""Tests for AVMModelBundle — save/load round-trip reproduces identical predictions."""

import numpy as np
import pandas as pd
import pytest

from src.avm.models.ensemble import AVMEnsemble, AVMModelBundle, train_ensemble
from src.avm.models.preprocess import fit_transform_train, transform_test, drop_pre_encode_cols


def _make_feature_df(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    towns = ["BEDOK", "BISHAN", "CLEMENTI", "HOUGANG", "TAMPINES"]
    flat_types = ["3 ROOM", "4 ROOM", "5 ROOM"]
    return pd.DataFrame({
        "floor_area_sqm": rng.uniform(60, 150, n),
        "storey_median": rng.integers(1, 20, n).astype(float),
        "remaining_lease_months": rng.integers(600, 1100, n).astype(float),
        "year": rng.integers(2017, 2024, n).astype(float),
        "month_numeric": rng.integers(1, 13, n).astype(float),
        "sora_3m": rng.uniform(0.5, 4.0, n),
        "cpi_all_items": rng.uniform(95, 120, n),
        "town": rng.choice(towns, n),
        "flat_type": rng.choice(flat_types, n),
        "resale_price": rng.uniform(300_000, 900_000, n),
    })


def _split_xy(df: pd.DataFrame):
    target = "resale_price"
    X = drop_pre_encode_cols(df.drop(columns=[target]))
    y = df[target].values
    return X, y


def test_bundle_save_load_predicts_identically(tmp_path):
    """Round-tripping through save_bundle/load_bundle must reproduce identical predictions."""
    df = _make_feature_df(n=300)
    train_df = df.iloc[:200]
    test_df = df.iloc[200:]

    X_tr, y_tr = _split_xy(train_df)
    X_te, y_te = _split_xy(test_df)

    X_tr_enc, preprocessor, feature_names = fit_transform_train(X_tr)
    X_te_enc = transform_test(X_te, preprocessor)

    lgbm_params = {"n_estimators": 20, "num_leaves": 15, "learning_rate": 0.1, "verbose": -1}
    xgb_params = {"n_estimators": 20, "learning_rate": 0.1}

    ensemble, ens_metrics, _ = train_ensemble(
        X_tr_enc, y_tr, X_te_enc, y_te,
        lgbm_params=lgbm_params,
        xgb_params=xgb_params,
        feature_names=feature_names,
    )

    bundle = AVMModelBundle(
        ensemble=ensemble,
        preprocessor=preprocessor,
        feature_names=feature_names,
        collinearity_dropped=[],
        manifest={"run_date": "2026-01-01"},
    )

    prefix = str(tmp_path / "bundle")
    bundle.save_bundle(prefix)

    loaded = AVMModelBundle.load_bundle(prefix)

    y_orig = bundle.predict(test_df.drop(columns=["resale_price"]))
    y_loaded = loaded.predict(test_df.drop(columns=["resale_price"]))

    np.testing.assert_array_almost_equal(y_orig, y_loaded)


def test_bundle_manifest_preserved(tmp_path):
    df = _make_feature_df(n=100)
    X, y = _split_xy(df)
    X_enc, preprocessor, feature_names = fit_transform_train(X)
    lgbm_params = {"n_estimators": 10, "num_leaves": 8, "learning_rate": 0.1, "verbose": -1}
    xgb_params = {"n_estimators": 10, "learning_rate": 0.1}
    ensemble, _, _ = train_ensemble(
        X_enc, y, X_enc, y,
        lgbm_params=lgbm_params,
        xgb_params=xgb_params,
        feature_names=feature_names,
    )
    bundle = AVMModelBundle(
        ensemble=ensemble,
        preprocessor=preprocessor,
        feature_names=feature_names,
        collinearity_dropped=["year"],
        manifest={"run_date": "2026-06-08", "custom": "value"},
    )
    prefix = str(tmp_path / "manifest_test")
    bundle.save_bundle(prefix)
    loaded = AVMModelBundle.load_bundle(prefix)

    assert loaded.collinearity_dropped == ["year"]
    assert loaded.manifest["run_date"] == "2026-06-08"
    assert loaded.manifest["custom"] == "value"
    assert loaded.feature_names == feature_names


def test_bundle_all_files_written(tmp_path):
    df = _make_feature_df(n=80)
    X, y = _split_xy(df)
    X_enc, preprocessor, feature_names = fit_transform_train(X)
    lgbm_params = {"n_estimators": 10, "num_leaves": 8, "learning_rate": 0.1, "verbose": -1}
    xgb_params = {"n_estimators": 10, "learning_rate": 0.1}
    ensemble, _, _ = train_ensemble(
        X_enc, y, X_enc, y,
        lgbm_params=lgbm_params,
        xgb_params=xgb_params,
        feature_names=feature_names,
    )
    bundle = AVMModelBundle(
        ensemble=ensemble,
        preprocessor=preprocessor,
        feature_names=feature_names,
    )
    prefix = str(tmp_path / "files_check")
    bundle.save_bundle(prefix)

    bundle_dir = tmp_path / "files_check"
    assert (bundle_dir / "avm_ensemble.pkl").exists()
    assert (bundle_dir / "preprocessor.pkl").exists()
    assert (bundle_dir / "feature_names.json").exists()
    assert (bundle_dir / "manifest.json").exists()
