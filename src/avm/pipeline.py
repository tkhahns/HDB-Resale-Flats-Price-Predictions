"""Main pipeline orchestrator for the HDB AVM research data pipeline.

Usage:
    python -m src.avm.pipeline --all              # full pipeline on real data
    python -m src.avm.pipeline --all --synthetic  # end-to-end on synthetic data
    python -m src.avm.pipeline --validate         # validation stage only
    make pipeline                                 # shorthand for --all
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("avm.pipeline")


def _load_config(path: str = "config/pipeline.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------

def _run_ingest(cfg: dict, synthetic: bool) -> pd.DataFrame:
    from src.avm.ingest.transactions import fetch_from_datagov, generate_synthetic_transactions, load_from_csv
    from src.avm.ingest.onemap import geocode_buildings, load_mrt_data, load_schools_data, geocode_schools
    from src.avm.ingest.macro import generate_synthetic_macro, load_macro_from_csv
    from src.avm.features.spatial import compute_mrt_features, compute_school_features, add_elite_flags
    from src.avm.features.building import merge_property_info

    if synthetic:
        logger.info("=== INGEST (synthetic mode) ===")
        df = generate_synthetic_transactions(n=5000)
        macro_df = generate_synthetic_macro(cfg["data"]["macro_data"])
        interim_path = cfg["data"]["interim_combined"]
        Path(interim_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(interim_path, index=False)
        logger.info("Synthetic interim data saved → %s", interim_path)
        return df

    logger.info("=== INGEST ===")
    raw_path = cfg["data"]["raw_transactions"]
    if Path(raw_path).exists():
        df = load_from_csv(raw_path)
    else:
        df = fetch_from_datagov(raw_path)

    # Geocode unique buildings
    unique_buildings = df[["block", "street_name"]].drop_duplicates().reset_index(drop=True)
    bldg_path = cfg["data"]["building_info"]
    if Path(bldg_path).exists():
        buildings_geo = pd.read_csv(bldg_path, index_col=0)
    else:
        buildings_geo = geocode_buildings(unique_buildings)
        buildings_geo.to_csv(bldg_path)

    # MRT features
    mrt_df = load_mrt_data(cfg["data"]["mrt_data"])
    buildings_geo = compute_mrt_features(buildings_geo, mrt_df)

    # School features
    schools_raw = load_schools_data(cfg["data"]["schools_data"])
    schools_df = geocode_schools(schools_raw)
    buildings_geo = compute_school_features(buildings_geo, schools_df)

    # Merge spatial features into transactions
    df_combined = df.merge(buildings_geo, on=["block", "street_name"], how="left")
    df_combined = add_elite_flags(df_combined, schools_df)

    # Merge HDB property info
    prop_path = cfg["data"]["hdb_property"]
    if Path(prop_path).exists():
        prop_df = pd.read_csv(prop_path)
        df_combined = merge_property_info(df_combined, prop_df)

    # Macro data
    macro_path = cfg["data"]["macro_data"]
    if not Path(macro_path).exists():
        generate_synthetic_macro(macro_path)

    interim_path = cfg["data"]["interim_combined"]
    Path(interim_path).parent.mkdir(parents=True, exist_ok=True)
    df_combined.to_csv(interim_path, index=False)
    logger.info("Interim combined data saved → %s  (%d rows)", interim_path, len(df_combined))
    return df_combined


def _run_validate(cfg: dict, df: pd.DataFrame) -> None:
    from src.avm.validate.schema import (
        validate_transactions,
        validate_macro,
        check_drift,
        generate_validation_report,
    )
    from src.avm.ingest.macro import load_macro_from_csv

    logger.info("=== VALIDATE ===")
    train_cutoff = pd.Timestamp(cfg["data"]["train_cutoff"])

    if "month" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["month"]):
        df["month"] = pd.to_datetime(df["month"])

    schema_result = validate_transactions(df)
    if not schema_result["passed"]:
        logger.error("Schema validation FAILED — %d errors found", len(schema_result["errors"]))

    macro_df = load_macro_from_csv(cfg["data"]["macro_data"])
    macro_result = validate_macro(macro_df)

    df_train = df[df["month"] < train_cutoff]
    df_test = df[df["month"] >= train_cutoff]
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    drift_result = check_drift(df_train, df_test, numeric_cols)

    report_path = f"{cfg['data']['reports_dir']}/validation_report.html"
    generate_validation_report(
        {"schema": schema_result, "macro": macro_result, "drift": drift_result},
        report_path,
    )


def _run_features(cfg: dict, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    from src.avm.features.building import (
        convert_storey_range_to_median,
        convert_remaining_lease_to_months,
        map_yn_to_bool,
        expand_transaction_date,
        impute_unseen_categories,
    )
    from src.avm.features.macro import merge_macro_features
    from src.avm.ingest.macro import load_macro_from_csv

    logger.info("=== FEATURES ===")

    if "month" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["month"]):
        df["month"] = pd.to_datetime(df["month"])

    train_cutoff = pd.Timestamp(cfg["data"]["train_cutoff"])
    df_train = df[df["month"] < train_cutoff].copy()
    df_test = df[df["month"] >= train_cutoff].copy()

    # Macro merge (with lag)
    macro_df = load_macro_from_csv(cfg["data"]["macro_data"])
    lag = cfg["features"].get("macro_lag_months", 1)
    df_train = merge_macro_features(df_train, macro_df, lag_months=lag)
    df_test = merge_macro_features(df_test, macro_df, lag_months=lag)

    # Building feature transforms
    for transform in [
        convert_storey_range_to_median,
        convert_remaining_lease_to_months,
        map_yn_to_bool,
    ]:
        df_train = transform(df_train)
        df_test = transform(df_test)

    # Expand date
    df_train = expand_transaction_date(df_train)
    df_test = expand_transaction_date(df_test)

    # Drop high-cardinality / leaky cols
    drop_cols = [c for c in cfg["features"].get("cols_to_drop", []) if c in df_train.columns]
    df_train.drop(columns=drop_cols, inplace=True, errors="ignore")
    df_test.drop(columns=drop_cols, inplace=True, errors="ignore")

    # Impute unseen categories in test
    for col, fallback in [("flat_model", "Model A"), ("closest_mrt", "Punggol")]:
        if col in df_test.columns:
            df_test = impute_unseen_categories(df_test, df_train, col, fallback)

    df_train.to_csv(cfg["data"]["processed_train"], index=False)
    df_test.to_csv(cfg["data"]["processed_test"], index=False)
    logger.info(
        "Processed: train=%d rows, test=%d rows, features=%d",
        len(df_train), len(df_test), df_train.shape[1],
    )
    return df_train, df_test


def _run_collinearity(cfg: dict, df_train: pd.DataFrame) -> pd.DataFrame:
    from src.avm.collinearity import (
        compute_vif,
        prune_by_vif,
        correlation_screen,
        generate_collinearity_report,
    )
    from src.avm.models.preprocess import drop_pre_encode_cols

    logger.info("=== COLLINEARITY ===")
    target = cfg["features"]["target"]
    numeric_train = df_train.select_dtypes(include="number").drop(columns=[target], errors="ignore")

    corr_threshold = cfg["validation"].get("correlation_threshold", 0.85)
    vif_threshold = cfg["validation"].get("vif_threshold", 10.0)

    corr_pairs = correlation_screen(numeric_train, threshold=corr_threshold, protected=[target])
    pruned, dropped = prune_by_vif(numeric_train, threshold=vif_threshold, protected=[target])

    generate_collinearity_report(
        numeric_train,
        pruned,
        dropped,
        corr_pairs,
        output_path=f"{cfg['data']['reports_dir']}/collinearity_report.csv",
    )
    return df_train.drop(columns=[c for c in dropped if c in df_train.columns], errors="ignore")


def _run_train(
    cfg: dict,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
) -> tuple:
    from src.avm.models.preprocess import fit_transform_train, transform_test, drop_pre_encode_cols
    from src.avm.models.ensemble import train_ensemble, summarise_feature_importance
    from src.avm.models.train import train_all_baselines

    logger.info("=== TRAIN ===")
    target = cfg["features"]["target"]

    X_train = drop_pre_encode_cols(df_train.drop(columns=[target]))
    y_train = df_train[target].values
    X_test = drop_pre_encode_cols(df_test.drop(columns=[target]))
    y_test = df_test[target].values

    X_train_enc, pipeline, feature_names = fit_transform_train(X_train)
    X_test_enc = transform_test(X_test, pipeline)

    lgbm_params = cfg["models"]["lgbm"]
    xgb_params = cfg["models"]["xgboost"]
    weights = cfg["models"]["ensemble_weights"]

    ensemble, ens_metrics, all_metrics = train_ensemble(
        X_train_enc, y_train, X_test_enc, y_test,
        lgbm_params=lgbm_params,
        xgb_params=xgb_params,
        feature_names=feature_names,
        lgbm_weight=weights["lgbm"],
        xgb_weight=weights["xgboost"],
    )

    reports_dir = cfg["data"]["reports_dir"]
    Path(reports_dir).mkdir(exist_ok=True)

    pd.DataFrame(all_metrics).T.to_csv(f"{reports_dir}/model_metrics.csv")
    fi_df = summarise_feature_importance(ensemble)
    fi_df.to_csv(f"{reports_dir}/feature_importance.csv", index=False)
    ensemble.save(f"{reports_dir}/avm_ensemble.pkl")

    return ensemble, pipeline, feature_names, X_test_enc, y_test


def _run_backtest(cfg: dict, df_train: pd.DataFrame, df_test: pd.DataFrame, pipeline) -> None:
    from src.avm.backtest.walk_forward import walk_forward_cv
    from src.avm.backtest.bias import (
        error_by_segment,
        error_by_price_band,
        generate_backtest_report,
    )
    from src.avm.models.preprocess import fit_transform_train, transform_test

    logger.info("=== BACKTEST ===")
    target = cfg["features"]["target"]
    date_col = "transaction_month"

    # Load processed data (pre-collinearity) so transaction_month and year are intact
    df_bt_train = pd.read_csv(cfg["data"]["processed_train"])
    df_bt_test = pd.read_csv(cfg["data"]["processed_test"])
    df_all = pd.concat([df_bt_train, df_bt_test], ignore_index=True)

    if date_col not in df_all.columns:
        logger.error("'transaction_month' column missing from processed data — cannot run backtest")
        return

    dropped_cols = getattr(_run_collinearity, "_last_dropped", [])

    def _model_fn(train_fold: pd.DataFrame, test_fold: pd.DataFrame):
        from src.avm.models.train import train_lgbm, train_xgboost

        X_tr = train_fold.drop(columns=[target, date_col] + dropped_cols, errors="ignore")
        y_tr = train_fold[target].values
        X_te = test_fold.drop(columns=[target, date_col] + dropped_cols, errors="ignore")

        X_tr_enc, pp, fn = fit_transform_train(X_tr)
        X_te_enc = transform_test(X_te, pp)

        lgbm = train_lgbm(X_tr_enc, y_tr, cfg["models"]["lgbm"])
        xgb_m = train_xgboost(X_tr_enc, y_tr, cfg["models"]["xgboost"])
        w = cfg["models"]["ensemble_weights"]
        y_pred = w["lgbm"] * lgbm.predict(X_te_enc) + w["xgboost"] * xgb_m.predict(X_te_enc)
        return None, y_pred

    step = cfg["backtest"].get("step_months", 6)
    min_train = cfg["backtest"].get("min_train_months", 18)
    fold_results = walk_forward_cv(
        df_all, _model_fn, date_col=date_col, step_months=step, min_train_months=min_train
    )

    # Final-model bias on held-out test set
    X_tr = df_bt_train.drop(columns=[target, date_col] + dropped_cols, errors="ignore")
    X_te = df_bt_test.drop(columns=[target, date_col] + dropped_cols, errors="ignore")
    y_te = df_bt_test[target].values
    X_tr_enc, pp, _ = fit_transform_train(X_tr)
    X_te_enc = transform_test(X_te, pp)
    from src.avm.models.train import train_lgbm, train_xgboost
    lgbm_m = train_lgbm(X_tr_enc, df_bt_train[target].values, cfg["models"]["lgbm"])
    xgb_m = train_xgboost(X_tr_enc, df_bt_train[target].values, cfg["models"]["xgboost"])
    w = cfg["models"]["ensemble_weights"]
    y_pred_test = w["lgbm"] * lgbm_m.predict(X_te_enc) + w["xgboost"] * xgb_m.predict(X_te_enc)
    df_test_bias = df_bt_test

    seg_cols = [c for c in ["town", "flat_type"] if c in df_test_bias.columns]
    seg_results = error_by_segment(df_test_bias, y_pred_test, target, seg_cols)
    price_band = error_by_price_band(df_test_bias, y_pred_test, target)

    generate_backtest_report(
        fold_results, seg_results, price_band, cfg["data"]["reports_dir"]
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="HDB AVM Research Pipeline")
    parser.add_argument("--config", default="config/pipeline.yaml")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--features", action="store_true")
    parser.add_argument("--collinearity", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic data (no API calls)")
    args = parser.parse_args(argv)

    cfg = _load_config(args.config)
    Path(cfg["data"]["reports_dir"]).mkdir(parents=True, exist_ok=True)

    run_all = args.all

    # --- Ingest ---
    if run_all or args.ingest:
        df = _run_ingest(cfg, synthetic=args.synthetic)
    else:
        interim = cfg["data"]["interim_combined"]
        if not Path(interim).exists():
            logger.error("Interim data not found at %s — run --ingest first", interim)
            sys.exit(1)
        df = pd.read_csv(interim)

    # --- Validate ---
    if run_all or args.validate:
        _run_validate(cfg, df)

    # --- Features ---
    if run_all or args.features:
        df_train, df_test = _run_features(cfg, df)
    else:
        train_path = cfg["data"]["processed_train"]
        test_path = cfg["data"]["processed_test"]
        if not Path(train_path).exists():
            logger.error("Processed data not found — run --features first")
            sys.exit(1)
        df_train = pd.read_csv(train_path)
        df_test = pd.read_csv(test_path)

    # --- Collinearity ---
    if run_all or args.collinearity:
        df_train = _run_collinearity(cfg, df_train)

    # --- Train ---
    if run_all or args.train:
        ensemble, pipeline, feature_names, X_test_enc, y_test = _run_train(cfg, df_train, df_test)

    # --- Backtest ---
    if run_all or args.backtest:
        _run_backtest(cfg, df_train, df_test, pipeline if (run_all or args.train) else None)

    logger.info("Pipeline complete. Reports in %s/", cfg["data"]["reports_dir"])


if __name__ == "__main__":
    main()
