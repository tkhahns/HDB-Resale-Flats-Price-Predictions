"""FastAPI prediction service for the HDB AVM.

Endpoints:
    GET  /healthz       liveness probe (always 200)
    GET  /readyz        readiness probe (200 only after model loaded)
    POST /predict       single or batch price prediction
    GET  /model-info    manifest of the currently loaded model
    GET  /metrics       prometheus-format metrics
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Union

import pandas as pd
from fastapi import FastAPI, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from src.avm.api import model_registry
from src.avm.api.features import build_feature_df
from src.avm.api.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    HealthResponse,
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
)

logger = logging.getLogger(__name__)

# ── Prometheus metrics ────────────────────────────────────────────────────────
_predict_counter = Counter("avm_predictions_total", "Total prediction requests")
_predict_errors = Counter("avm_prediction_errors_total", "Prediction errors")
_predict_latency = Histogram("avm_prediction_latency_seconds", "Prediction latency")


# ── Lifespan: load model on startup ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model_registry.load()
        logger.info("Model loaded successfully on startup")
    except Exception as exc:
        logger.warning("Could not load model on startup: %s", exc)
    yield


app = FastAPI(
    title="HDB AVM Prediction Service",
    description="Automated Valuation Model for Singapore HDB resale flats",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/healthz", response_model=HealthResponse, tags=["ops"])
def healthz():
    return {"status": "ok"}


@app.get("/readyz", response_model=HealthResponse, tags=["ops"])
def readyz():
    if not model_registry.is_ready():
        raise HTTPException(status_code=503, detail="Model not yet loaded")
    return {"status": "ready"}


@app.post(
    "/predict",
    response_model=Union[PredictionResponse, BatchPredictionResponse],
    tags=["predict"],
)
def predict(body: Union[BatchPredictionRequest, PredictionRequest]):
    if not model_registry.is_ready():
        raise HTTPException(status_code=503, detail="Model not yet loaded")

    bundle = model_registry.get_bundle()
    run_date = model_registry.get_run_date()

    requests_list = body.instances if isinstance(body, BatchPredictionRequest) else [body]

    macro_values = bundle.manifest.get("latest_macro", {})
    t0 = time.perf_counter()
    try:
        dfs = [build_feature_df(req, macro_values=macro_values) for req in requests_list]
        df_all = pd.concat(dfs, ignore_index=True)
        prices = bundle.predict(df_all)
        _predict_counter.inc(len(requests_list))
    except Exception as exc:
        _predict_errors.inc()
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _predict_latency.observe(time.perf_counter() - t0)

    preds = [PredictionResponse(predicted_price=float(p), model_run_date=run_date) for p in prices]
    if isinstance(body, BatchPredictionRequest):
        return BatchPredictionResponse(predictions=preds)
    return preds[0]


@app.get("/model-info", response_model=ModelInfoResponse, tags=["ops"])
def model_info():
    if not model_registry.is_ready():
        raise HTTPException(status_code=503, detail="Model not yet loaded")
    bundle = model_registry.get_bundle()
    manifest = bundle.manifest.copy()
    return ModelInfoResponse(
        model_prefix=manifest.pop("model_prefix", ""),
        run_date=manifest.pop("run_date", model_registry.get_run_date() or ""),
        metrics=manifest.get("metrics", {}),
    )


@app.get("/metrics", tags=["ops"], include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
