# Ingest

`src/avm/ingest/` — data acquisition modules.

| Module | Description |
|---|---|
| `transactions.py` | Fetch HDB resale transactions from data.gov.sg API or load from CSV |
| `onemap.py` | Geocode unique building addresses via OneMap REST API (async) |
| `macro.py` | Load macroeconomic features CSV (SORA, CPI, HDB RPI, GDP, unemployment, cooling dummies) |

## Synthetic mode

`generate_synthetic_transactions(n)` and `generate_synthetic_macro(path)` produce
realistic fake data for CI and testing — no external API calls required.
