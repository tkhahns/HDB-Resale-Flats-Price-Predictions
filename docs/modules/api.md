# FastAPI Prediction Service

`src/avm/api/` — real-time prediction endpoint.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness probe — always 200 |
| `GET` | `/readyz` | Readiness probe — 503 until model loaded |
| `POST` | `/predict` | Single or batch price prediction |
| `GET` | `/model-info` | Manifest of the loaded model |
| `GET` | `/metrics` | Prometheus metrics |

## Single prediction request

```json
POST /predict
{
  "town": "TAMPINES",
  "flat_type": "4 ROOM",
  "storey_range": "07 TO 09",
  "floor_area_sqm": 95.0,
  "flat_model": "Model A",
  "lease_commence_date": 1998,
  "remaining_lease": "65 years 06 months",
  "block": "123",
  "street_name": "TAMPINES AVE 1",
  "transaction_month": "2024-01"
}
```

Response: `{ "predicted_price": 650000, "currency": "SGD", "model_run_date": "2026-01-01" }`

## Batch prediction

Wrap multiple requests in `{ "instances": [...] }`.

## Model hot-swap

On startup the service loads the bundle pointed to by `models/latest.json`.
When the daily batch publishes a new bundle (and updates `latest.json`), call
`GET /readyz` — the next container restart picks up the new model automatically.
For immediate hot-swap, force a new ECS deployment.
