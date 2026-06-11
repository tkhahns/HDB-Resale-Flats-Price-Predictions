# HDB Resale Flats — Automated Valuation Model (AVM)

A production ML pipeline that predicts Singapore HDB resale flat prices using an LGBM + XGBoost ensemble (**R²=0.954, MAE≈27k SGD** on real data).

Runs daily on AWS (EventBridge Scheduler → ECS Fargate), publishes model bundles and date-partitioned reports to S3, and serves real-time predictions via a FastAPI REST endpoint. A Next.js dashboard deployed on Vercel visualises model analytics and exposes a live price estimator.

---

## System architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Data sources                                                            │
│  data.gov.sg HDB API  ·  OneMap geocoding API  ·  macro CSVs (SORA/CPI) │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ fetch + geocode
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  AWS                                                                     │
│                                                                          │
│  EventBridge (daily 07:00 SGT)                                           │
│    └─ ECS Fargate  ──  python -m src.avm.pipeline --all                  │
│         │                                                                │
│         │  writes date-partitioned artifacts                             │
│         ▼                                                                │
│  S3 — artifacts bucket                                                   │
│    ├─ models/                                                            │
│    │    ├─ latest.json          ← pointer: model_prefix + reports_prefix │
│    │    └─ date=YYYY-MM-DD/                                              │
│    │         ├─ avm_ensemble.pkl                                         │
│    │         ├─ preprocessor.pkl                                         │
│    │         ├─ feature_names.json                                       │
│    │         └─ manifest.json                                            │
│    └─ reports/                                                           │
│         └─ date=YYYY-MM-DD/                                              │
│              ├─ analytics.json  ← consumed by Vercel dashboard           │
│              ├─ model_metrics.csv                                        │
│              ├─ feature_importance.csv                                   │
│              ├─ backtest_metrics.csv                                     │
│              └─ backtest_bias_*.csv / *.png                              │
│                                                                          │
│  S3 — data bucket                                                        │
│    ├─ raw/         (transactions CSV, building info, MRT, schools)       │
│    ├─ interim/     (combined + geocoded)                                 │
│    └─ processed/   (train / test after feature engineering)              │
│                                                                          │
│  ECS Service  ──  FastAPI AVM                                            │
│    ├─ POST /predict      (ensemble inference, <50ms p95)                 │
│    ├─ GET  /model-info   (manifest of loaded bundle)                     │
│    ├─ GET  /healthz  /readyz                                             │
│    └─ GET  /metrics      (Prometheus)                                    │
│         reads latest.json on startup → loads bundle from S3             │
│                                                                          │
│  Supporting services                                                     │
│    ├─ Glue Crawler → Athena → QuickSight  (ad-hoc SQL analytics)        │
│    ├─ CloudWatch Logs + Alarms            (pipeline + API monitoring)    │
│    └─ ECR                                 (hdb-avm-batch, hdb-avm-api)  │
└──────────────────────────────────────────────────────────────────────────┘
          │  s3:GetObject (read-only IAM)        │  proxy /predict
          ▼                                      ▼
┌─────────────────────────────────────────────────────┐
│  Vercel  (web/ — Next.js 14 App Router)             │
│                                                     │
│  Server components (ISR, revalidate=3600)           │
│    └─ reads analytics.json from S3 via AWS SDK      │
│         shows: metrics cards, backtest chart,       │
│                bias charts, feature importance      │
│                                                     │
│  API routes                                         │
│    ├─ /api/analytics  ← S3 read, 1-hr cache         │
│    └─ /api/predict    ← proxy → FastAPI ECS         │
│         (injects X-Api-Key server-side;             │
│          never exposes key to browser)              │
└─────────────────────────────────────────────────────┘
          ▲
          │  browser
┌─────────┴───────────┐
│  User               │
│  views dashboard    │
│  submits price form │
└─────────────────────┘
```

### CI/CD

```
Pull request
  └─ GitHub Actions  ci.yml
       ├─ ruff lint + format check
       ├─ pytest (48 unit tests)
       ├─ synthetic integration  (pipeline --all --synthetic)
       └─ docker build + smoke test

Merge to main  (manual workflow_dispatch only for CD)
  └─ GitHub Actions  cd.yml  (OIDC — no long-lived AWS keys)
       ├─ docker build + push → ECR  (hdb-avm-batch, hdb-avm-api)
       ├─ terraform apply            (infra/terraform/)
       └─ aws ecs update-service --force-new-deployment
```

---

## Pipeline stages

| Stage | Module | Output |
|---|---|---|
| **Ingest** | `ingest/transactions.py`, `ingest/onemap.py`, `ingest/macro.py` | `interim_combined.csv` |
| **Validate** | `validate/schema.py` | `reports/validation_report.html` |
| **Features** | `features/building.py`, `features/spatial.py`, `features/macro.py` | `processed_train.csv`, `processed_test.csv` |
| **Collinearity** | `collinearity.py` | `reports/collinearity_report.csv`, pruned feature list |
| **Train** | `models/ensemble.py` | `models/date=.../`, `models/latest.json` |
| **Backtest** | `backtest/walk_forward.py`, `backtest/bias.py` | `reports/backtest_*.csv/png` |
| **Analytics** | `pipeline._write_analytics_summary` | `reports/analytics.json` |

```bash
# Full pipeline on real data
python -m src.avm.pipeline --all --run-date 2026-06-08

# Synthetic end-to-end (no API calls, ~30s, used in CI)
python -m src.avm.pipeline --all --synthetic --run-date 2026-01-01
```

---

## Features

- **197 features**: spatial (MRT/school geodesic distances, elite school flag), building (storey median, remaining lease months, Y/N facility flags), macroeconomic (SORA 3M, CPI, HDB RPI, GDP, unemployment, cooling-measure dummies with 1-month leakage guard), transaction metadata
- **Data validation**: pandera schema checks + PSI/KS drift detection
- **VIF-based collinearity resolution**: iterative removal of highest-VIF feature until all VIF < 10
- **Walk-forward backtesting**: 6-month steps, 18-month minimum window, bias diagnostics by town / flat type / price band
- **Production deployment**: containerized (Docker multi-stage), S3-backed, scheduled via EventBridge, served via FastAPI

---

## Quick start

```bash
# Install
pip install -e ".[dev]"

# Run synthetic pipeline (no API calls, ~30s)
python -m src.avm.pipeline --all --synthetic --run-date 2026-01-01

# Run tests
pytest tests/ -v

# Start API locally (after a pipeline run that produced models/)
uvicorn src.avm.api.main:app --reload
curl http://localhost:8000/healthz
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"town":"TAMPINES","flat_type":"4 ROOM","storey_range":"07 TO 09",
       "floor_area_sqm":95,"flat_model":"Model A","lease_commence_date":1998,
       "remaining_lease":"65 years 06 months","block":"123",
       "street_name":"TAMPINES AVE 1","transaction_month":"2024-01"}'

# Start Vercel dashboard locally
cd web && cp .env.example .env.local  # fill in vars
npm install && npm run dev
```

---

## Project structure

```
src/avm/
  pipeline.py          # orchestrator: --all --synthetic --run-date
  io/storage.py        # fsspec-backed transparent local/S3 helpers
  ingest/              # data.gov.sg transactions, OneMap geocoding, macro CSV
  features/            # building transforms, spatial distances, macro lag merge
  models/              # preprocess, train_lgbm/xgb, AVMEnsemble, AVMModelBundle
  backtest/            # walk_forward_cv, error_by_segment, error_by_price_band
  validate/            # pandera schemas, PSI/KS drift
  collinearity.py      # VIF pruning, correlation screen, report
  api/
    main.py            # FastAPI app (lifespan model load, /predict, /metrics)
    model_registry.py  # thread-safe singleton bundle loader
    schemas.py         # Pydantic request/response models
    features.py        # request → feature DataFrame assembly

web/                   # Next.js 14 App Router (Vercel)
  app/
    page.tsx           # server component dashboard (ISR)
    api/analytics/     # S3 → JSON route (1-hr revalidation)
    api/predict/       # FastAPI proxy (injects API key server-side)
  components/
    MetricsCard.tsx
    BacktestChart.tsx
    BiasChart.tsx
    FeatureImportanceChart.tsx
    PredictForm.tsx    # live price estimator
  lib/
    analytics.ts       # S3 / URL / local-file data fetcher
    types.ts           # shared TypeScript interfaces
  vercel.json
  .env.example

config/
  pipeline.yaml        # all thresholds, paths, model hyperparameters

docker/
  Dockerfile.base      # shared Python + deps layer
  Dockerfile.batch     # pipeline runner image
  Dockerfile.api       # FastAPI service image

infra/terraform/       # ECR, S3, ECS, IAM, EventBridge, Glue/Athena, CloudWatch

.github/workflows/
  ci.yml               # lint → tests → synthetic integration → docker smoke
  cd.yml               # OIDC → ECR push → terraform apply → ECS force-deploy

tests/                 # 48 unit tests
docs/                  # mkdocs-material site (architecture, runbook, ADRs)
```

---

## AWS deployment

```bash
# 1. Configure Terraform
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
# Edit: vpc_id, subnet IDs, alert_email

# 2. Apply infrastructure
cd infra/terraform && terraform init && terraform apply

# 3. Push images (normally handled by the CD workflow)
docker build --platform linux/amd64 -f docker/Dockerfile.base -t hdb-avm-base .
docker build --platform linux/amd64 -f docker/Dockerfile.batch \
  --build-arg BASE_IMAGE=hdb-avm-base -t <ecr-url>/hdb-avm-batch:latest .
docker push <ecr-url>/hdb-avm-batch:latest

# 4. Trigger first manual run
aws ecs run-task --cluster hdb-avm --task-definition hdb-avm-batch \
  --launch-type FARGATE --network-configuration ...

# 5. Enable daily schedule after verifying the manual run
# See docs/runbook.md
```

---

## Vercel deployment

1. Import repo on [vercel.com/new](https://vercel.com/new), set **Root Directory** → `web`
2. Add environment variables (Settings → Environment Variables):

| Variable | Description |
|---|---|
| `AVM_ARTIFACTS_BUCKET` | S3 bucket name for models/ and reports/ |
| `AWS_REGION` | `ap-southeast-1` |
| `AWS_ACCESS_KEY_ID` | IAM user key — `s3:GetObject` on artifacts bucket only |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |
| `AVM_API_URL` | FastAPI ECS service base URL |
| `AVM_API_KEY` | Optional API key forwarded to FastAPI |
| `ANALYTICS_JSON_URL` | Alternative: direct HTTPS URL to `analytics.json` (skips S3 SDK) |

3. Deploy. Dashboard auto-refreshes analytics every hour via ISR.

---

## Environment variables (pipeline / API)

| Variable | Description |
|---|---|
| `AVM_ARTIFACTS_BUCKET` | S3 bucket for models/ and reports/ (blank → local) |
| `AVM_DATA_BUCKET` | S3 bucket for raw/interim/processed data (blank → local) |
| `AVM_LATEST_JSON` | Override path to latest.json (useful for local tests) |

---

## CI/CD

- **CI** (`ci.yml`): ruff lint/format → pytest → synthetic integration → docker build + smoke test
- **CD** (`cd.yml`): manual `workflow_dispatch` only — OIDC credentials → ECR push → terraform apply → ECS force-deploy

Requires GitHub repository secret `AWS_DEPLOY_ROLE_ARN` (IAM role with OIDC trust for the GitHub Actions principal).
