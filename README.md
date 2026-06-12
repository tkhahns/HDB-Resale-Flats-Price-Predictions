# HDB Resale AVM

> Automated Valuation Model for Singapore HDB resale flats — LGBM + XGBoost ensemble trained on 232k transactions, served via FastAPI on AWS ECS, with a Next.js analytics dashboard on Vercel.

![CI](https://github.com/tkhahns/HDB-Resale-Flats-Price-Predictions/actions/workflows/ci.yml/badge.svg)

**Model performance (real data, hold-out test set)**

| Model | MAE | RMSE | MAPE |
|---|---|---|---|
| LightGBM | ~28k SGD | ~40k SGD | ~5.9% |
| XGBoost | ~29k SGD | ~41k SGD | ~6.1% |
| **Ensemble** | **~27k SGD** | **~39k SGD** | **~5.7%** |
| Walk-forward backtest (16 folds) | ~29k SGD avg | — | ~6.2% avg |

---

## What this is

This project started as a university course project (NUS CS3244) and was rebuilt end-to-end into a production ML system. The two original Jupyter notebooks (`1_feature_engineering+EDA.ipynb`, `2_model_building.ipynb`) explored the data and prototyped the models; everything in them has since been refactored into a modular Python package with a CI/CD pipeline, containerised deployment, and a live web dashboard.

**The system does three things:**

1. **Trains daily** — an ECS Fargate batch job pulls fresh transaction data from data.gov.sg, re-trains the ensemble, and publishes versioned model artifacts + reports to S3
2. **Serves predictions** — a FastAPI service loads the latest model bundle from S3 and answers `POST /predict` requests in <50ms (p95)
3. **Visualises analytics** — a Next.js dashboard on Vercel reads the daily `analytics.json` report from S3 and shows model metrics, backtest results, bias breakdowns, and a live price estimator form

---

## System architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  EXTERNAL DATA SOURCES                                                       ║
║                                                                              ║
║  ┌─────────────────────┐  ┌────────────────────┐  ┌──────────────────────┐  ║
║  │   data.gov.sg API   │  │    OneMap API      │  │  Macro indicators    │  ║
║  │  HDB resale records │  │  building geocode  │  │  SORA · CPI · RPI    │  ║
║  │  232 k transactions │  │  school geocode    │  │  GDP · unemployment  │  ║
║  └──────────┬──────────┘  └─────────┬──────────┘  └──────────┬───────────┘  ║
╚═════════════╪═════════════════════════╪═════════════════════════╪════════════╝
              │  ① paginated fetch      │  ② geocode addresses    │  ③ lag-merge
              │    with retry (429)     │    block + street       │    1 month guard
              └─────────────────────────┴─────────────────────────┘
                                        │
                     ┌──────────────────┘
                     │  EventBridge cron  07:00 SGT  (daily)
                     ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  AWS  —  ECS FARGATE  BATCH PIPELINE                                         ║
║                                                                              ║
║  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────┐  ┌─────────┐  ║
║  │  ingest  │─▶│ validate │─▶│  features  │─▶│ collinearity│─▶│  train  │  ║
║  │          │  │          │  │            │  │             │  │         │  ║
║  │ fetch tx │  │ pandera  │  │ 197 feats  │  │ Pearson r   │  │  LGBM   │  ║
║  │ geocode  │  │ schema   │  │ building   │  │ VIF < 10    │  │ XGBoost │  ║
║  │ macro lag│  │ PSI/KS   │  │ spatial    │  │ iterative   │  │ ensemble│  ║
║  │          │  │ drift    │  │ macro      │  │ pruning     │  │ weight  │  ║
║  └──────────┘  └──────────┘  └────────────┘  └─────────────┘  └────┬────┘  ║
║                                                                      │       ║
║                                                               ┌──────▼────┐  ║
║                                                               │ backtest  │  ║
║                                                               │ 16-fold   │  ║
║                                                               │ walk-fwd  │  ║
║                                                               │ bias diag │  ║
║                                                               └──────┬────┘  ║
╚══════════════════════════════════════════════════════════════════════╪═══════╝
          ④ writes CSVs                                        ⑤ writes artifacts
          ┌───────────────────────────────────────────────────────────┘
          │
          ▼
╔═══════════════════════════╗    ╔══════════════════════════════════════════════╗
║  S3  —  DATA BUCKET       ║    ║  S3  —  ARTIFACTS BUCKET                     ║
║                           ║    ║                                              ║
║  raw/                     ║    ║  models/                                     ║
║  ├─ resale_transactions   ║    ║  ├─ latest.json                              ║
║  ├─ building_info         ║    ║  │   { model_prefix, reports_prefix,         ║
║  ├─ mrt_lrt_data          ║    ║  │     run_date, metrics }                   ║
║  └─ schools               ║    ║  └─ date=YYYY-MM-DD/                         ║
║                           ║    ║       ├─ avm_ensemble.pkl                    ║
║  interim/                 ║    ║       ├─ preprocessor.pkl                    ║
║  └─ combined.csv          ║    ║       ├─ feature_names.json                  ║
║                           ║    ║       └─ manifest.json                       ║
║  processed/               ║    ║                                              ║
║  ├─ train.csv             ║    ║  reports/date=YYYY-MM-DD/                    ║
║  └─ test.csv              ║    ║  ├─ analytics.json   ← dashboard feed        ║
║                           ║    ║  ├─ model_metrics.csv                        ║
║                           ║    ║  ├─ feature_importance.csv                   ║
║                           ║    ║  ├─ backtest_metrics.csv                     ║
║                           ║    ║  └─ backtest_bias_*.csv / *.png              ║
╚═══════════════════════════╝    ╚═══════════════════════╤════════════════════════╝
                                                         │
                  ┌──────────────────────────────────────┤
                  │  ⑥ read latest.json                  │  ⑦ read analytics.json
                  │    load bundle on startup             │    s3:GetObject  (read-only IAM)
                  ▼                                       ▼
╔══════════════════════════════════╗  ╔═════════════════════════════════════════════╗
║  AWS ECS SERVICE  —  FastAPI     ║  ║  VERCEL  —  Next.js 14 App Router           ║
║                                  ║  ║                                             ║
║  on startup:                     ║  ║  app/page.tsx          ISR revalidate=3600  ║
║    read latest.json → load pkl   ║  ║  ├─ MetricsCard         MAE / RMSE / MAPE  ║
║    hot-swap on /refresh          ║  ║  ├─ BacktestChart        fold MAE + bias   ║
║                                  ║  ║  ├─ BiasChart            town / flat type  ║
║  POST /predict                   ║  ║  ├─ FeatureImportance    top-20 features   ║
║    preprocess → ensemble.predict ║  ║  └─ PredictForm          live estimator    ║
║    <50 ms p95                    ║  ║                                             ║
║                                  ║  ║  app/api/analytics/    S3 read, 1-hr cache ║
║  GET  /model-info  manifest      ║  ║  app/api/predict/      proxy → FastAPI     ║
║  GET  /healthz     liveness      ║  ║                        injects X-Api-Key   ║
║  GET  /readyz      readiness     ║  ║                        server-side only     ║
║  GET  /metrics     Prometheus    ║  ║                                             ║
╚═══════════════════╤══════════════╝  ╚══════════════════════╤══════════════════════╝
                    │  ⑧ POST /predict                        │  ⑨ HTTPS
                    │    X-Api-Key (injected by Vercel)        │
                    └────────────────────────────────────────▶│
                                                              ▼
                                                    ┌─────────────────┐
                                                    │    Browser      │
                                                    │  views charts   │
                                                    │  submits form   │
                                                    └─────────────────┘
```

**Numbered flow:**

| Step | What happens |
|---|---|
| ① | Pipeline fetches HDB resale records from data.gov.sg (paginated, retry on 429) |
| ② | OneMap API geocodes each unique block+street to lat/lng; cached after first run |
| ③ | Macro indicators (SORA, CPI, HDB RPI, GDP, unemployment) joined with 1-month lag to prevent data leakage |
| ④ | Raw, interim, and processed CSVs written to the data S3 bucket (or local filesystem when `AVM_DATA_BUCKET` unset) |
| ⑤ | Model bundle (pkl files + manifest) and `analytics.json` written to the artifacts S3 bucket under `date=YYYY-MM-DD/`; `latest.json` updated atomically last |
| ⑥ | FastAPI service reads `latest.json` on startup to locate the bundle prefix, loads the pkl files, and holds the bundle as a thread-safe singleton |
| ⑦ | Vercel server component reads `analytics.json` directly from S3 using a read-only IAM user (`s3:GetObject` only); result cached by ISR for 1 hour |
| ⑧ | The Vercel `/api/predict` route proxies browser requests to FastAPI, injecting `X-Api-Key` server-side so the key is never exposed to the client |
| ⑨ | Browser receives rendered HTML + Recharts components; price form calls `/api/predict` via `fetch()` |

---

## ML pipeline

### Feature engineering (197 features)

| Group | Features |
|---|---|
| **Spatial** | Geodesic distance to nearest MRT, MRT line, distance to nearest 3 elite schools, elite school within 1km flag |
| **Building** | Storey range → median floor, remaining lease → months, Y/N facility flags (sap, autonomous, gifted, IP) |
| **Transaction** | Flat type, flat model, town, floor area sqm, transaction year/month |
| **Macroeconomic** | SORA 3M, CPI, HDB Resale Price Index, GDP growth, unemployment rate, cooling-measure dummies — all merged with 1-month lag to prevent leakage |

### Modelling approach

```
Raw transactions (232k rows)
  │
  ├─ train / test split at configurable cutoff date
  │
  ├─ Collinearity pruning
  │    ├─ Pearson correlation screen  (threshold = 0.85)
  │    └─ Iterative VIF removal       (threshold = 10.0)
  │
  ├─ Preprocessing pipeline (sklearn)
  │    ├─ Numeric: median imputation + StandardScaler
  │    └─ Categorical: most-frequent imputation + OneHotEncoder
  │
  └─ Ensemble
       ├─ LightGBM  (weight 0.5)
       └─ XGBoost   (weight 0.5)
            └─ weighted average → final prediction
```

### Walk-forward backtesting

Expanding-window CV with 6-month steps and an 18-month minimum training window. Each fold re-trains from scratch to simulate live deployment. Bias diagnostics broken down by town, flat type, and price quintile are written to `reports/date=.../` on every run.

### Pipeline stages

| # | Stage | Key module | Primary output |
|---|---|---|---|
| 1 | **Ingest** | `ingest/transactions.py`, `ingest/onemap.py` | `data/interim/combined.csv` |
| 2 | **Validate** | `validate/schema.py` | `reports/validation_report.html` |
| 3 | **Features** | `features/building.py`, `features/spatial.py`, `features/macro.py` | `data/processed/train.csv`, `test.csv` |
| 4 | **Collinearity** | `collinearity.py` | `reports/collinearity_report.csv` |
| 5 | **Train** | `models/ensemble.py` | `models/date=.../`, `models/latest.json` |
| 6 | **Backtest** | `backtest/walk_forward.py`, `backtest/bias.py` | `reports/backtest_*.csv/png` |
| 7 | **Analytics** | `pipeline._write_analytics_summary` | `reports/analytics.json` |

---

## Quick start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Synthetic end-to-end run (no external API calls, ~30s)
python -m src.avm.pipeline --all --synthetic --run-date 2026-01-01

# 3. Full run on real data (fetches from data.gov.sg + OneMap, ~15 min first time)
python -m src.avm.pipeline --all --run-date 2026-06-08

# 4. Run tests
pytest tests/ -v                          # 48 unit + integration tests

# 5. Start API locally (requires a completed pipeline run)
uvicorn src.avm.api.main:app --reload
curl http://localhost:8000/healthz
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"town":"TAMPINES","flat_type":"4 ROOM","storey_range":"07 TO 09",
       "floor_area_sqm":95,"flat_model":"Model A","lease_commence_date":1998,
       "remaining_lease":"65 years 06 months","block":"123",
       "street_name":"TAMPINES AVE 1","transaction_month":"2024-01"}'

# 6. Start dashboard locally
cd web && cp .env.example .env.local      # fill in env vars
npm install && npm run dev
```

Individual pipeline stages can be run selectively:

```bash
python -m src.avm.pipeline --ingest
python -m src.avm.pipeline --features --collinearity
python -m src.avm.pipeline --train --backtest --run-date 2026-06-08
```

---

## API reference

The FastAPI service (`src/avm/api/`) loads the model bundle from `models/latest.json` on startup and hot-swaps it on `/refresh` without a restart.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/predict` | Single or batch price prediction |
| `GET` | `/model-info` | Bundle manifest (run date, metrics) |
| `GET` | `/healthz` | Liveness probe — always 200 |
| `GET` | `/readyz` | Readiness probe — 503 until model loaded |
| `GET` | `/metrics` | Prometheus metrics |

**Single prediction request:**
```json
{
  "town": "TAMPINES",
  "flat_type": "4 ROOM",
  "storey_range": "07 TO 09",
  "floor_area_sqm": 95,
  "flat_model": "Model A",
  "lease_commence_date": 1998,
  "remaining_lease": "65 years 06 months",
  "block": "123",
  "street_name": "TAMPINES AVE 1",
  "transaction_month": "2024-01"
}
```

**Response:**
```json
{ "predicted_price": 612500.0, "model_run_date": "2026-06-08" }
```

---

## Deployment

### AWS infrastructure

All infrastructure is managed by Terraform (`infra/terraform/`). Core resources: ECR (two repos), two S3 buckets (data + artifacts), ECS cluster with Fargate task definitions for the batch job and API service, EventBridge schedule, Glue Crawler + Athena database, CloudWatch log groups and alarms.

```bash
# First-time setup
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
# Edit: aws_region, vpc_id, subnet_ids, alert_email

cd infra/terraform
terraform init
terraform apply

# Images are built and pushed by the CD workflow (GitHub Actions)
# Trigger the first pipeline run manually:
aws ecs run-task \
  --cluster hdb-avm \
  --task-definition hdb-avm-batch \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

**IAM security model:**
- GitHub Actions uses OIDC role assumption — no long-lived AWS keys in the repo
- Vercel uses a dedicated read-only IAM user with `s3:GetObject` only on the artifacts bucket
- Browser traffic reaches FastAPI only through the Vercel proxy, which injects the API key server-side

### Vercel dashboard

```
Settings → Build and Deployment → Root Directory → web
```

| Environment variable | Description |
|---|---|
| `AVM_ARTIFACTS_BUCKET` | S3 bucket name (models/ and reports/) |
| `AWS_REGION` | `ap-southeast-1` |
| `AWS_ACCESS_KEY_ID` | Read-only IAM user key |
| `AWS_SECRET_ACCESS_KEY` | Read-only IAM user secret |
| `AVM_API_URL` | FastAPI ECS service base URL |
| `AVM_API_KEY` | Optional — forwarded as `X-Api-Key` to FastAPI |
| `ANALYTICS_JSON_URL` | Alternative to S3: direct HTTPS URL to `analytics.json` |

The dashboard uses Next.js ISR (`revalidate: 3600`) — analytics refresh automatically every hour after a new pipeline run without a redeploy.

### Pipeline environment variables

| Variable | Description |
|---|---|
| `AVM_ARTIFACTS_BUCKET` | S3 bucket for models/ and reports/ (blank → local filesystem) |
| `AVM_DATA_BUCKET` | S3 bucket for raw/interim/processed data (blank → local) |
| `AVM_LATEST_JSON` | Override path to latest.json (useful in tests) |

---

## CI / CD

```
Every pull request
  └─ ci.yml
       ├─ ruff check + ruff format --check
       ├─ pytest (48 tests)
       ├─ python -m src.avm.pipeline --all --synthetic   (integration)
       └─ docker build + smoke test (healthz probe)

Manual workflow_dispatch → main
  └─ cd.yml  (OIDC — no long-lived AWS keys stored anywhere)
       ├─ docker build --platform linux/amd64
       ├─ push hdb-avm-batch:sha + hdb-avm-api:sha → ECR
       ├─ terraform fmt -check + validate + plan + apply
       └─ aws ecs update-service --force-new-deployment
```

Requires one GitHub secret: `AWS_DEPLOY_ROLE_ARN` — an IAM role with an OIDC trust policy for `token.actions.githubusercontent.com`.

---

## Project structure

```
.
├─ src/avm/
│   ├─ pipeline.py          # orchestrator — flags: --all --ingest --train --backtest --synthetic --run-date
│   ├─ io/
│   │   └─ storage.py       # fsspec wrapper: transparent local ↔ S3 for all reads/writes
│   ├─ ingest/
│   │   ├─ transactions.py  # data.gov.sg paginated fetch with retry, CSV loader
│   │   ├─ onemap.py        # OneMap geocoding for buildings and schools
│   │   └─ macro.py         # macro CSV loader + synthetic macro generator
│   ├─ features/
│   │   ├─ building.py      # storey range, remaining lease, Y/N flags, date expansion
│   │   ├─ spatial.py       # MRT geodesic distance, school distance + elite flags
│   │   └─ macro.py         # lag-merge of macro series onto transaction dates
│   ├─ collinearity.py      # Pearson screen + iterative VIF pruning
│   ├─ validate/
│   │   └─ schema.py        # pandera schemas, PSI/KS drift detection, HTML report
│   ├─ models/
│   │   ├─ train.py         # train_lgbm, train_xgboost, evaluate, feature_importance_df
│   │   ├─ preprocess.py    # sklearn Pipeline: impute + scale/encode
│   │   └─ ensemble.py      # AVMEnsemble, AVMModelBundle (save/load bundle)
│   ├─ backtest/
│   │   ├─ walk_forward.py  # expanding-window CV, fold-level metrics
│   │   └─ bias.py          # error_by_segment, error_by_price_band, plots
│   └─ api/
│       ├─ main.py          # FastAPI app — lifespan load, /predict, /metrics
│       ├─ model_registry.py# thread-safe singleton bundle loader + hot-swap
│       ├─ schemas.py       # Pydantic request/response models
│       └─ features.py      # PredictionRequest → feature DataFrame
│
├─ web/                     # Next.js 14 App Router — Vercel dashboard
│   ├─ app/
│   │   ├─ page.tsx         # server component: metrics, charts, predict form (ISR)
│   │   └─ api/
│   │       ├─ analytics/   # route: S3 → JSON, revalidate=3600
│   │       └─ predict/     # route: proxy to FastAPI, injects API key
│   ├─ components/
│   │   ├─ MetricsCard.tsx
│   │   ├─ BacktestChart.tsx
│   │   ├─ BiasChart.tsx
│   │   ├─ FeatureImportanceChart.tsx
│   │   └─ PredictForm.tsx
│   └─ lib/
│       ├─ analytics.ts     # data fetcher: S3 SDK → URL fallback → local file
│       └─ types.ts         # shared TypeScript interfaces
│
├─ config/
│   └─ pipeline.yaml        # all thresholds, paths, model hyperparameters
├─ docker/
│   ├─ Dockerfile.base      # shared Python + deps layer (linux/amd64)
│   ├─ Dockerfile.batch     # pipeline runner image
│   └─ Dockerfile.api       # FastAPI service image
├─ infra/terraform/         # ECR, S3, ECS, IAM, EventBridge, Glue/Athena, CloudWatch
├─ tests/                   # 48 unit + integration tests
├─ docs/                    # mkdocs-material site (architecture, runbook, ADRs)
└─ .github/workflows/
    ├─ ci.yml
    └─ cd.yml
```
