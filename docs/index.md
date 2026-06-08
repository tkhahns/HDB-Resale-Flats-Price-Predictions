# HDB AVM — Automated Valuation Model

Production ML pipeline that predicts Singapore HDB resale flat prices using an LGBM + XGBoost ensemble (R²=0.954, MAE≈27k SGD on real data).

## Quick start

```bash
pip install -e ".[dev]"
python -m src.avm.pipeline --all --synthetic
```

See the [Architecture](architecture.md) overview and the [Runbook](runbook.md) for operational procedures.
