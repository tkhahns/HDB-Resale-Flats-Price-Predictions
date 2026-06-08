# ADR-005: Persist the sklearn preprocessor alongside the model

**Status:** Accepted

**Context:** `AVMEnsemble.predict(X)` expects an already-encoded dense/sparse matrix.
The original pipeline saved only the ensemble; the fitted `ColumnTransformer`
(StandardScaler + OneHotEncoder) existed only in memory and was lost after training.
This made the model completely unusable for inference.

**Decision:** Introduce `AVMModelBundle` — a dataclass that wraps:
- `ensemble`: the LGBM + XGBoost AVMEnsemble
- `preprocessor`: the fitted sklearn Pipeline
- `feature_names`: list of encoded feature names
- `collinearity_dropped`: columns removed by VIF pruning (must be excluded at predict time)
- `manifest`: run_date, metrics, `latest_macro` (macro feature values for API use)

`save_bundle(prefix)` writes all four components atomically.  `load_bundle(prefix)` restores
them.  `AVMModelBundle.predict(X)` is the sole inference entry point — it chains
`drop_pre_encode_cols → preprocessor.transform → ensemble.predict` so callers never need
to manage the preprocessing step.

**Consequences:** Inference is now possible end-to-end from a raw feature DataFrame.
The bundle is the unit of deployment: nothing works without all four components present.
