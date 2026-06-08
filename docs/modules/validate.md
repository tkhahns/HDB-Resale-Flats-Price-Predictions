# Validate

`src/avm/validate/schema.py` — data quality gates.

## Schema validation

`pandera` schemas define expected types and ranges for both the transaction
DataFrame and the macro DataFrame.  Violations are logged and recorded in
`validation_report.html`.

## Drift detection

For each numeric column, the pipeline computes:
- **KS statistic** — Kolmogorov-Smirnov two-sample test (train vs test distribution)
- **PSI** — Population Stability Index using 10 equally-spaced bins covering the combined
  range of both distributions

Columns with PSI > 0.2 are flagged as potentially drifted.
