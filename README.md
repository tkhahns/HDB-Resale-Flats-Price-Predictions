# HDB Resale Flats — Automated Valuation Model (AVM)

A production ML pipeline that predicts Singapore HDB resale flat prices using an LGBM + XGBoost ensemble (**R²=0.954, MAE≈27k SGD** on real data).

Runs daily on AWS (EventBridge Scheduler → ECS Fargate), publishes model bundles and date-partitioned reports to S3, and serves real-time predictions via a FastAPI REST endpoint behind an ALB.

---

## Architecture

```
EventBridge (daily 07:00 SGT)
  └─ ECS Fargate batch task
       ├─ data.gov.sg + OneMap APIs
       ├─ S3 datalake (raw / interim / processed)
       └─ S3 artifacts (models/date=YYYY-MM-DD/ + latest.json)
                │
                ├─ Glue Crawler → Athena → QuickSight (SPICE dashboards)
                └─ FastAPI ECS service (reads latest.json, serves /predict)
```

See [docs/architecture.md](docs/architecture.md) for the full diagram and [docs/runbook.md](docs/runbook.md) for operational procedures.

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

# Run tests (54 tests)
pytest tests/ -v

# Start API locally (after pipeline run)
uvicorn src.avm.api.main:app --reload
curl http://localhost:8000/healthz
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"town":"TAMPINES","flat_type":"4 ROOM","storey_range":"07 TO 09",
       "floor_area_sqm":95,"flat_model":"Model A","lease_commence_date":1998,
       "remaining_lease":"65 years 06 months","block":"123",
       "street_name":"TAMPINES AVE 1","transaction_month":"2024-01"}'
```

---

## Project structure

```
src/avm/
  pipeline.py          # orchestrator (--all --synthetic --run-date)
  io/storage.py        # fsspec-backed local/S3 helpers
  ingest/              # data.gov.sg + OneMap + macro CSV
  features/            # building transforms, spatial distances, macro lag
  models/              # preprocess, train, ensemble, AVMModelBundle
  backtest/            # walk-forward CV, bias diagnostics
  validate/            # pandera schemas, PSI/KS drift
  collinearity.py      # VIF pruning, correlation screen
  api/                 # FastAPI: main, schemas, features, model_registry
config/
  pipeline.yaml        # all thresholds and paths
docker/
  Dockerfile.base / .batch / .api
infra/terraform/       # ECR, S3, ECS, IAM, EventBridge, Glue/Athena, CloudWatch
.github/workflows/
  ci.yml               # lint + tests + synthetic integration + docker smoke
  cd.yml               # OIDC → ECR push → terraform apply → ECS force-deploy
docs/                  # mkdocs-material site (architecture, runbook, ADRs)
```

---

## AWS deployment

```bash
# 1. Set variables
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
# Edit: vpc_id, subnet IDs, alert_email

# 2. Init + apply
cd infra/terraform && terraform init && terraform apply

# 3. Push images (normally done by CD pipeline)
docker build --platform linux/amd64 -f docker/Dockerfile.base -t hdb-avm-base .
docker build --platform linux/amd64 -f docker/Dockerfile.batch \
  --build-arg BASE_IMAGE=hdb-avm-base -t <ecr-url>/hdb-avm-batch:latest .
docker push <ecr-url>/hdb-avm-batch:latest

# 4. Trigger first manual run
aws ecs run-task --cluster hdb-avm --task-definition hdb-avm-batch \
  --launch-type FARGATE --network-configuration ...

# 5. Enable daily schedule (after verifying the manual run succeeds)
# See docs/runbook.md
```

---

## Environment variables

| Variable | Description |
|---|---|
| `AVM_ARTIFACTS_BUCKET` | S3 bucket for models/ and reports/ |
| `AVM_DATA_BUCKET` | S3 bucket for raw/interim/processed data |
| `AVM_LATEST_JSON` | Override path to latest.json (useful for tests) |

---

## CI/CD

- **CI** (`.github/workflows/ci.yml`): ruff lint/format → pytest → synthetic integration → docker build + smoke test
- **CD** (`.github/workflows/cd.yml`): OIDC credentials → ECR push → terraform apply → force new API deployment

Requires GitHub repository secret `AWS_DEPLOY_ROLE_ARN` (IAM role with OIDC trust for the GitHub Actions principal).
