# Features

`src/avm/features/` — feature engineering.

| Module | Description |
|---|---|
| `building.py` | Storey range → median, remaining lease → months, Y/N → bool, date expansion |
| `spatial.py` | Geodesic distances to nearest MRT and school; elite school flag |
| `macro.py` | 1-month lagged merge of macroeconomic features (leakage guard) |

## Macro lag

Transactions at month T are merged with macro data from T-1 to prevent leakage:
the model never sees economic data "from the future" of the transaction date.

## Feature count

~197 features after one-hot encoding: spatial (MRT/school distances, elite flag),
building (storey, lease, Y/N flags), macroeconomic (7 columns), transaction metadata
(flat_type, flat_model, town, floor_area, year, month).
