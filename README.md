# HDB Resale Flats — Automated Valuation Model (AVM)

A quantitative research data pipeline and ensemble Automated Valuation Model for Singapore HDB resale flat prices.  
Featurizes **197 macroeconomic and spatial features** from **160 000+ multi-source records**, validates data quality, detects feature multi-collinearity, and produces auditable out-of-sample backtest reports with bias diagnostics.

---

## Architecture

```
HDB-Resale-Flats-Price-Predictions/
├── config/
│   └── pipeline.yaml          # all paths, model params, thresholds
├── data/
│   ├── raw/                   # immutable source files (not committed)
│   ├── external/macro/        # macroeconomic series (synthetic pre-generated)
│   ├── interim/               # geocoded + merged intermediate data
│   └── processed/             # model-ready train / test CSVs
├── src/avm/
│   ├── ingest/
│   │   ├── transactions.py    # data.gov.sg API + CSV loader
│   │   ├── onemap.py          # async OneMap geocoding
│   │   └── macro.py           # SORA / CPI / RPI / GDP / unemployment series
│   ├── validate/
│   │   └── schema.py          # pandera schema + PSI drift detection
│   ├── features/
│   │   ├── spatial.py         # MRT & school geodesic distances
│   │   ├── building.py        # lease / storey / Y-N transformations
│   │   └── macro.py           # leakage-safe macro merge (1-month lag)
│   ├── collinearity.py        # VIF iteration + Pearson correlation screen
│   ├── models/
│   │   ├── preprocess.py      # OneHotEncoder + StandardScaler pipeline
│   │   ├── train.py           # LR / Ridge / Lasso / DT / RF + evaluate()
│   │   └── ensemble.py        # LGBM + XGBoost AVM ensemble
│   ├── backtest/
│   │   ├── walk_forward.py    # expanding-window out-of-sample CV
│   │   └── bias.py            # signed error, segment & price-band bias
│   └── pipeline.py            # CLI orchestrator (argparse)
├── notebooks/
│   ├── 1_feature_engineering+EDA.ipynb
│   └── 2_model_building.ipynb
├── reports/                   # generated: metrics, collinearity, backtest plots
├── tests/
│   ├── test_features.py
│   ├── test_collinearity.py
│   └── test_validate.py
├── Makefile
└── requirements.txt
```

---

## Quick Start

```bash
pip install -r requirements.txt

# End-to-end on synthetic data (no API calls required)
make synthetic

# Run tests
make test
```

For a real run, place source files under `data/raw/` (see [Data Sources](#data-sources)) then:

```bash
make pipeline          # runs all stages
# or individually:
make ingest
make validate
make features
make collinearity
make train
make backtest
```

---

## Pipeline Stages

| Stage | Command | Output |
|---|---|---|
| **Ingest** | `make ingest` | `data/interim/df_combined.csv` |
| **Validate** | `make validate` | `reports/validation_report.html` |
| **Features** | `make features` | `data/processed/df_train.csv`, `df_test.csv` |
| **Collinearity** | `make collinearity` | `reports/collinearity_report.csv` |
| **Train** | `make train` | `reports/avm_ensemble.pkl`, `model_metrics.csv` |
| **Backtest** | `make backtest` | `reports/backtest_metrics.csv`, bias plots |

---

## Data Sources

| Source | Content | Notes |
|---|---|---|
| [data.gov.sg](https://data.gov.sg) | 174 893 HDB resale transactions Jan 2017 – Mar 2024 | Fetched via API or CSV |
| [OneMap API](https://www.onemap.gov.sg) | Lat/lon for 9 551 unique buildings, MRT stations, schools | Async geocoding |
| HDB Property Information | Building metadata (max floor, facilities) | Merged on block + street |
| **Macroeconomic series** | SORA, CPI, HDB RPI, GDP growth, unemployment, cooling-measure dummies | Pre-generated synthetic series in `data/external/macro/`; replace with real MAS/SingStat API data for production |

---

## Macroeconomic Features

Monthly features joined to each transaction at **T−1 lag** (leakage guard):

| Feature | Source | Purpose |
|---|---|---|
| `sora_3m` | MAS API | Mortgage rate proxy → affordability |
| `cpi_all_items` | SingStat | Inflation environment |
| `cpi_housing` | SingStat | Housing-specific price pressure |
| `hdb_rpi` | data.gov.sg | Market-wide momentum |
| `gdp_growth_qoq` | SingStat | Macro demand cycle |
| `unemployment_rate` | MOM | Household income stability |
| `cooling_measure` | Manual (ABSD/LTV events) | Regime / structural break |

---

## Collinearity Resolution

VIF is computed iteratively on the numeric feature matrix; features with VIF > 10 are dropped one at a time (highest VIF first) until all remaining features satisfy the threshold. A Pearson correlation screen (|r| > 0.85) identifies highly correlated pairs. Full before/after VIF table saved to `reports/collinearity_report.csv`.

---

## Model Performance (Static Test Set: Sep 2023 – Mar 2024)

| Model | MAE (SGD) | R² | MAPE |
|---|---|---|---|
| Linear Regression | 48 455 | 0.865 | 8.25% |
| Ridge / Lasso | ~48 477 | 0.865 | ~8.25% |
| Decision Tree | 54 335 | 0.808 | 8.91% |
| Random Forest | 35 874 | 0.913 | 5.76% |
| LightGBM | 28 050 | 0.951 | 4.70% |
| XGBoost | 27 568 | 0.954 | 4.66% |
| **LGBM + XGBoost Ensemble** | **27 145** | **0.954** | **4.55%** |

---

## Backtesting

Walk-forward expanding-window CV steps through the 2017–2024 time series in 6-month increments (minimum 18-month training window). Each fold reports MAE, RMSE, MAPE, and mean signed error. Bias diagnostics slice residuals by town, flat type, and price band — outputs saved to `reports/`.

---

## Tests

```bash
make test
# or: python -m pytest tests/ -v
```

Tests cover feature transformations, collinearity detection, leakage guard in macro merge, schema validation, and drift detection — without requiring any real data.
