"""Main pipeline orchestrator for the HDB AVM research data pipeline.

Usage:
    python -m src.avm.pipeline --all                              # full pipeline on real data
    python -m src.avm.pipeline --all --synthetic                  # end-to-end on synthetic data
    python -m src.avm.pipeline --all --synthetic --run-date 2026-01-01
    python -m src.avm.pipeline --validate                         # validation stage only
    make pipeline                                                 # shorthand for --all

Environment variables:
    AVM_ARTIFACTS_BUCKET   S3 bucket for models/ and reports/ (blank → local)
    AVM_DATA_BUCKET        S3 bucket for raw/interim/processed data (blank → local)
"""

import argparse
import logging
import os
import sys
from datetime import date

import pandas as pd
import yaml

from src.avm.io import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("avm.pipeline")


def _load_config(path: str = "config/pipeline.yaml") -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    artifacts_bucket = os.environ.get("AVM_ARTIFACTS_BUCKET", "")
    data_bucket = os.environ.get("AVM_DATA_BUCKET", "")
    if artifacts_bucket:
        cfg["data"]["models_dir"] = f"s3://{artifacts_bucket}/models"
        cfg["data"]["reports_dir"] = f"s3://{artifacts_bucket}/reports"
    if data_bucket:
        for key in (
            "raw_transactions",
            "building_info",
            "mrt_data",
            "schools_data",
            "hdb_property",
            "macro_data",
            "interim_combined",
            "processed_train",
            "processed_test",
        ):
            if key in cfg["data"]:
                local_rel = cfg["data"][key].lstrip("data/")
                cfg["data"][key] = f"s3://{data_bucket}/{local_rel}"
    return cfg


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _run_ingest(cfg: dict, synthetic: bool) -> pd.DataFrame:
    from src.avm.features.building import merge_property_info
    from src.avm.features.spatial import (
        add_elite_flags,
        compute_mrt_features,
        compute_school_features,
    )
    from src.avm.ingest.macro import generate_synthetic_macro
    from src.avm.ingest.onemap import (
        geocode_buildings,
        geocode_schools,
        load_mrt_data,
        load_schools_data,
    )
    from src.avm.ingest.transactions import (
        fetch_from_datagov,
        generate_synthetic_transactions,
        load_from_csv,
    )

    if synthetic:
        logger.info("=== INGEST (synthetic mode) ===")
        df = generate_synthetic_transactions(n=5000)
        generate_synthetic_macro(cfg["data"]["macro_data"])
        interim_path = cfg["data"]["interim_combined"]
        storage.makedirs(interim_path)
        df.to_csv(interim_path, index=False)
        logger.info("Synthetic interim data saved → %s", interim_path)
        return df

    logger.info("=== INGEST ===")
    raw_path = cfg["data"]["raw_transactions"]
    if storage.exists(raw_path):
        df = load_from_csv(raw_path)
    else:
        df = fetch_from_datagov(raw_path)

    # Geocode unique buildings
    unique_buildings = df[["block", "street_name"]].drop_duplicates().reset_index(drop=True)
    bldg_path = cfg["data"]["building_info"]
    if storage.exists(bldg_path):
        buildings_geo = pd.read_csv(bldg_path, index_col=0)
    else:
        buildings_geo = geocode_buildings(unique_buildings)
        storage.makedirs(bldg_path)
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
    if storage.exists(prop_path):
        prop_df = pd.read_csv(prop_path)
        df_combined = merge_property_info(df_combined, prop_df)

    # Macro data
    macro_path = cfg["data"]["macro_data"]
    if not storage.exists(macro_path):
        generate_synthetic_macro(macro_path)

    interim_path = cfg["data"]["interim_combined"]
    storage.makedirs(interim_path)
    df_combined.to_csv(interim_path, index=False)
    logger.info("Interim combined data saved → %s  (%d rows)", interim_path, len(df_combined))
    return df_combined


def _run_validate(cfg: dict, df: pd.DataFrame) -> None:
    from src.avm.ingest.macro import load_macro_from_csv
    from src.avm.validate.schema import (
        check_drift,
        generate_validation_report,
        validate_macro,
        validate_transactions,
    )

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
        convert_remaining_lease_to_months,
        convert_storey_range_to_median,
        expand_transaction_date,
        impute_unseen_categories,
        map_yn_to_bool,
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

    storage.makedirs(cfg["data"]["processed_train"])
    df_train.to_csv(cfg["data"]["processed_train"], index=False)
    df_test.to_csv(cfg["data"]["processed_test"], index=False)
    logger.info(
        "Processed: train=%d rows, test=%d rows, features=%d",
        len(df_train),
        len(df_test),
        df_train.shape[1],
    )
    return df_train, df_test


def _run_collinearity(cfg: dict, df_train: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    from src.avm.collinearity import (
        correlation_screen,
        generate_collinearity_report,
        prune_by_vif,
    )

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
    df_pruned = df_train.drop(
        columns=[c for c in dropped if c in df_train.columns], errors="ignore"
    )
    return df_pruned, dropped


def _run_train(
    cfg: dict,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    dropped_cols: list[str],
    run_date: str,
):
    from src.avm.models.ensemble import AVMModelBundle, summarise_feature_importance, train_ensemble
    from src.avm.models.preprocess import drop_pre_encode_cols, fit_transform_train, transform_test

    logger.info("=== TRAIN ===")
    target = cfg["features"]["target"]

    X_train = drop_pre_encode_cols(df_train.drop(columns=[target]), extra_drops=dropped_cols)
    y_train = df_train[target].values
    X_test = drop_pre_encode_cols(df_test.drop(columns=[target]), extra_drops=dropped_cols)
    y_test = df_test[target].values

    X_train_enc, preprocessor, feature_names = fit_transform_train(X_train)
    X_test_enc = transform_test(X_test, preprocessor)

    lgbm_params = cfg["models"]["lgbm"]
    xgb_params = cfg["models"]["xgboost"]
    weights = cfg["models"]["ensemble_weights"]

    ensemble, ens_metrics, all_metrics = train_ensemble(
        X_train_enc,
        y_train,
        X_test_enc,
        y_test,
        lgbm_params=lgbm_params,
        xgb_params=xgb_params,
        feature_names=feature_names,
        lgbm_weight=weights["lgbm"],
        xgb_weight=weights["xgboost"],
    )

    reports_dir = cfg["data"]["reports_dir"]
    storage.makedirs(reports_dir)
    import pandas as _pd

    _pd.DataFrame(all_metrics).T.to_csv(f"{reports_dir}/model_metrics.csv")
    fi_df = summarise_feature_importance(ensemble)
    fi_df.to_csv(f"{reports_dir}/feature_importance.csv", index=False)

    # Capture latest macro values for API real-time feature assembly
    latest_macro: dict = {}
    try:
        from src.avm.ingest.macro import load_macro_from_csv

        macro_df = load_macro_from_csv(cfg["data"]["macro_data"])
        latest_row = macro_df.sort_values("month").iloc[-1].to_dict()
        latest_macro = {
            k: (str(v) if hasattr(v, "isoformat") else v) for k, v in latest_row.items()
        }
    except Exception:
        pass

    # Save complete model bundle (ensemble + preprocessor + metadata)
    models_prefix = cfg["data"]["models_prefix"]
    bundle = AVMModelBundle(
        ensemble=ensemble,
        preprocessor=preprocessor,
        feature_names=feature_names,
        collinearity_dropped=dropped_cols,
        manifest={"run_date": run_date, "metrics": ens_metrics, "latest_macro": latest_macro},
    )
    bundle.save_bundle(models_prefix)

    # Write latest.json pointer — only on success, written last
    latest_json_path = cfg["data"]["models_latest_json"]
    storage.write_json(
        {"model_prefix": models_prefix, "run_date": run_date, "metrics": ens_metrics},
        latest_json_path,
    )
    logger.info("latest.json → %s", latest_json_path)

    return bundle


def _run_backtest(
    cfg: dict,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    dropped_cols: list[str],
) -> None:
    from src.avm.backtest.bias import (
        error_by_price_band,
        error_by_segment,
        generate_backtest_report,
    )
    from src.avm.backtest.walk_forward import walk_forward_cv
    from src.avm.models.preprocess import fit_transform_train, transform_test

    logger.info("=== BACKTEST ===")
    target = cfg["features"]["target"]
    date_col = "transaction_month"

    # Load processed data (pre-collinearity) so transaction_month and year are intact
    df_bt_train = pd.read_csv(cfg["data"]["processed_train"])
    df_bt_test = pd.read_csv(cfg["data"]["processed_test"])
    df_all = pd.concat([df_bt_train, df_bt_test], ignore_index=True)

    if date_col not in df_all.columns:
        logger.error("'transaction_month' column missing — cannot run backtest")
        return

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
    df_bt_train_target = df_bt_train[target].values
    X_tr_enc, pp, _ = fit_transform_train(X_tr)
    X_te_enc = transform_test(X_te, pp)
    from src.avm.models.train import train_lgbm, train_xgboost

    lgbm_m = train_lgbm(X_tr_enc, df_bt_train_target, cfg["models"]["lgbm"])
    xgb_m = train_xgboost(X_tr_enc, df_bt_train_target, cfg["models"]["xgboost"])
    w = cfg["models"]["ensemble_weights"]
    y_pred_test = w["lgbm"] * lgbm_m.predict(X_te_enc) + w["xgboost"] * xgb_m.predict(X_te_enc)

    seg_cols = [c for c in ["town", "flat_type"] if c in df_bt_test.columns]
    seg_results = error_by_segment(df_bt_test, y_pred_test, target, seg_cols)
    price_band = error_by_price_band(df_bt_test, y_pred_test, target)

    generate_backtest_report(fold_results, seg_results, price_band, cfg["data"]["reports_dir"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="HDB AVM Research Pipeline")
    parser.add_argument("--config", default="config/pipeline.yaml")
    parser.add_argument("--run-date", default=None, help="Run date YYYY-MM-DD (default: today)")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--features", action="store_true")
    parser.add_argument("--collinearity", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument(
        "--synthetic", action="store_true", help="Use synthetic data (no API calls)"
    )
    args = parser.parse_args(argv)

    run_date = args.run_date or str(date.today())
    cfg = _load_config(args.config)

    # Date-partition reports and models for QuickSight / Athena compatibility
    base_reports = cfg["data"]["reports_dir"]
    base_models = cfg["data"].get("models_dir", "models")
    cfg["data"]["reports_dir"] = f"{base_reports}/date={run_date}"
    cfg["data"]["models_prefix"] = f"{base_models}/date={run_date}"
    cfg["data"]["models_latest_json"] = f"{base_models}/latest.json"

    storage.makedirs(cfg["data"]["reports_dir"])

    run_all = args.all

    # --- Ingest ---
    if run_all or args.ingest:
        df = _run_ingest(cfg, synthetic=args.synthetic)
    else:
        interim = cfg["data"]["interim_combined"]
        if not storage.exists(interim):
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
        if not storage.exists(train_path):
            logger.error("Processed data not found — run --features first")
            sys.exit(1)
        df_train = pd.read_csv(train_path)
        df_test = pd.read_csv(test_path)

    # --- Collinearity ---
    dropped_cols: list[str] = []
    if run_all or args.collinearity:
        df_train, dropped_cols = _run_collinearity(cfg, df_train)

    # --- Train ---
    if run_all or args.train:
        _run_train(cfg, df_train, df_test, dropped_cols, run_date)

    # --- Backtest ---
    if run_all or args.backtest:
        _run_backtest(cfg, df_train, df_test, dropped_cols)

    logger.info("Pipeline complete. Reports in %s/", cfg["data"]["reports_dir"])


if __name__ == "__main__":
    main()
