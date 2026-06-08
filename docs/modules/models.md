# Models

## AVMModelBundle (`src/avm/models/ensemble.py`)

The primary deployment unit.  Wraps the ensemble, preprocessor, and metadata.

```python
bundle = AVMModelBundle.load_bundle("models/date=2026-01-01")
prices = bundle.predict(X_raw_df)  # end-to-end: preprocess → ensemble predict
```

## AVMEnsemble

Simple weighted average of LGBM and XGBoost predictions.

```python
p = lgbm_weight * lgbm.predict(X_enc) + xgb_weight * xgb.predict(X_enc)
```

## Preprocessing (`src/avm/models/preprocess.py`)

`fit_transform_train(X)` builds a `ColumnTransformer`:
- Numeric columns → `StandardScaler`
- Categorical columns (`town`, `flat_type`, `flat_model`, `closest_mrt`) → `OneHotEncoder(handle_unknown="ignore")`
