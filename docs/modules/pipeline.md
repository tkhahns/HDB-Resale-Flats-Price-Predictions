# Pipeline

`src/avm/pipeline.py` — main orchestrator.

```
python -m src.avm.pipeline --all --synthetic --run-date 2026-01-01
```

## Stages

| Stage | Flag | Description |
|---|---|---|
| Ingest | `--ingest` | Fetch transactions (data.gov.sg), geocode, merge macro |
| Validate | `--validate` | Schema checks, PSI/KS drift detection |
| Features | `--features` | Storey/lease/Y-N transforms, date expansion, macro lag |
| Collinearity | `--collinearity` | VIF pruning + Pearson correlation screen |
| Train | `--train` | Fit LGBM + XGBoost ensemble, save `AVMModelBundle` |
| Backtest | `--backtest` | Walk-forward CV, segment bias diagnostics |

`--all` runs every stage sequentially.

## Environment variables

| Variable | Effect |
|---|---|
| `AVM_ARTIFACTS_BUCKET` | S3 bucket for `models/` and `reports/` |
| `AVM_DATA_BUCKET` | S3 bucket for `raw/`, `interim/`, `processed/` |

## Output layout

All artifacts are date-partitioned:
```
models/date=YYYY-MM-DD/{avm_ensemble.pkl, preprocessor.pkl, feature_names.json, manifest.json}
models/latest.json
reports/date=YYYY-MM-DD/{model_metrics.csv, backtest_metrics.csv, ...}
```
