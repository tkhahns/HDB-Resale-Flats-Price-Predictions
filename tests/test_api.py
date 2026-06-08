"""FastAPI integration tests using TestClient with a synthetic model bundle."""

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.avm.models.ensemble import AVMEnsemble, AVMModelBundle
from src.avm.models.preprocess import fit_transform_train, transform_test, drop_pre_encode_cols


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_bundle(tmp_path):
    """Create a minimal synthetic model bundle and write it to tmp_path."""
    import pandas as pd
    from src.avm.models.ensemble import train_ensemble
    from src.avm.ingest.transactions import generate_synthetic_transactions
    from src.avm.features.building import (
        convert_storey_range_to_median,
        convert_remaining_lease_to_months,
        map_yn_to_bool,
        expand_transaction_date,
    )
    from src.avm.features.macro import merge_macro_features
    from src.avm.ingest.macro import generate_synthetic_macro

    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        macro_path = f.name
    try:
        generate_synthetic_macro(macro_path)
        from src.avm.ingest.macro import load_macro_from_csv
        macro_df = load_macro_from_csv(macro_path)
    finally:
        os.unlink(macro_path)

    df = generate_synthetic_transactions(n=300)
    df = convert_storey_range_to_median(df)
    df = convert_remaining_lease_to_months(df)
    df = map_yn_to_bool(df)
    df = merge_macro_features(df, macro_df, lag_months=1)
    df = expand_transaction_date(df)

    target = "resale_price"
    X = drop_pre_encode_cols(df.drop(columns=[target]))
    y = df[target].values

    X_enc, preprocessor, feature_names = fit_transform_train(X)
    lgbm_params = {"n_estimators": 10, "num_leaves": 8, "learning_rate": 0.1, "verbose": -1}
    xgb_params = {"n_estimators": 10, "learning_rate": 0.1}
    ensemble, _, _ = train_ensemble(
        X_enc, y, X_enc, y,
        lgbm_params=lgbm_params,
        xgb_params=xgb_params,
        feature_names=feature_names,
    )
    latest_macro_row = macro_df.sort_values("month").iloc[-1].to_dict()
    latest_macro = {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in latest_macro_row.items()}
    bundle = AVMModelBundle(
        ensemble=ensemble,
        preprocessor=preprocessor,
        feature_names=feature_names,
        collinearity_dropped=[],
        manifest={"run_date": "2026-01-01", "metrics": {"MAE": 50000}, "latest_macro": latest_macro},
    )
    prefix = str(tmp_path / "bundle")
    bundle.save_bundle(prefix)
    return bundle, prefix


_SAMPLE_REQUEST = {
    "town": "TAMPINES",
    "flat_type": "4 ROOM",
    "storey_range": "07 TO 09",
    "floor_area_sqm": 95.0,
    "flat_model": "Model A",
    "lease_commence_date": 1998,
    "remaining_lease": "65 years 06 months",
    "block": "123",
    "street_name": "TAMPINES AVE 1",
    "transaction_month": "2024-01",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    tmp = tmp_path_factory.mktemp("api_test")
    bundle, prefix = _make_bundle(tmp)

    # Write latest.json pointing at the test bundle so lifespan.load() finds it
    from src.avm.io.storage import write_json
    latest_json = str(tmp / "latest.json")
    write_json({"model_prefix": prefix, "run_date": "2026-01-01"}, latest_json)
    os.environ["AVM_LATEST_JSON"] = latest_json

    from src.avm.api.main import app
    with TestClient(app) as c:
        yield c

    os.environ.pop("AVM_LATEST_JSON", None)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz_ready(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_predict_single(client):
    r = client.post("/predict", json=_SAMPLE_REQUEST)
    assert r.status_code == 200
    body = r.json()
    assert "predicted_price" in body
    assert body["currency"] == "SGD"
    assert body["predicted_price"] > 0


def test_predict_batch(client):
    batch = {"instances": [_SAMPLE_REQUEST, _SAMPLE_REQUEST]}
    r = client.post("/predict", json=batch)
    assert r.status_code == 200
    body = r.json()
    assert "predictions" in body
    assert len(body["predictions"]) == 2
    for pred in body["predictions"]:
        assert pred["predicted_price"] > 0


def test_predict_bad_input(client):
    bad = {**_SAMPLE_REQUEST, "floor_area_sqm": -10}  # fails pydantic validation
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_model_info(client):
    r = client.get("/model-info")
    assert r.status_code == 200
    body = r.json()
    assert body["run_date"] == "2026-01-01"
    assert "metrics" in body


def test_readyz_not_ready():
    """readyz returns 503 when bundle is not loaded."""
    from unittest.mock import patch
    from src.avm.api import model_registry as reg
    from src.avm.api.main import app

    original = reg._bundle
    reg._bundle = None
    # Suppress lifespan's load() so it doesn't repopulate _bundle
    with patch.object(reg, "load", return_value=None):
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/readyz")
    reg._bundle = original
    assert r.status_code == 503


def test_empty_batch_rejected(client):
    r = client.post("/predict", json={"instances": []})
    assert r.status_code == 422
