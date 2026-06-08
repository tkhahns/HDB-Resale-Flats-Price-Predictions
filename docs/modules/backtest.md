# Backtest

`src/avm/backtest/` — temporal validation and bias diagnostics.

## Walk-forward CV (`walk_forward.py`)

Expanding-window cross-validation with 6-month steps and an 18-month minimum
training window.  Each fold trains a fresh LGBM + XGBoost ensemble to measure
out-of-sample performance over time.

## Bias diagnostics (`bias.py`)

After the final model is trained on all training data, predictions on the held-out
test set are sliced by:

- **Town** — detect systematic over/under-prediction in specific areas
- **Flat type** — check if 2-room vs executive flats are predicted equally well
- **Price band** — quintile analysis to catch systematic bias at price extremes

Reports:
- `backtest_metrics.csv` — MAE/RMSE/R²/signed_error per fold
- `backtest_bias_{town,flat_type}.csv` + `.png`
- `backtest_bias_price_band.csv`
