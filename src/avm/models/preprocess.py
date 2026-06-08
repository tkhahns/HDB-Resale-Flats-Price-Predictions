"""Build sklearn preprocessing pipelines for the AVM feature matrix."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

logger = logging.getLogger(__name__)

_COLS_TO_DROP_BEFORE_ENCODE = [
    "bldg_contract_town",
    "latitude",
    "longitude",
    "lease_commence_date",
    "year_completed",
    "block",
    "street_name",
    "transaction_month",  # time index preserved for backtest; not a model feature
]

_UNSEEN_MRT_FALLBACK = "Punggol"
_UNSEEN_FLAT_MODEL_FALLBACK = "Model A"


def drop_pre_encode_cols(df: pd.DataFrame, extra_drops: list[str] | None = None) -> pd.DataFrame:
    to_drop = _COLS_TO_DROP_BEFORE_ENCODE + (extra_drops or [])
    existing = [c for c in to_drop if c in df.columns]
    return df.drop(columns=existing)


def split_column_types(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    num_cols = df.select_dtypes(exclude="object").columns.tolist()
    return cat_cols, num_cols


def build_preprocessing_pipeline(X_train: pd.DataFrame) -> Pipeline:
    cat_cols, num_cols = split_column_types(X_train)
    transformer = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=True), cat_cols),
        ]
    )
    pipeline = Pipeline(steps=[("preprocessor", transformer)])
    logger.info(
        "Preprocessing pipeline: %d numeric + %d categorical features", len(num_cols), len(cat_cols)
    )
    return pipeline


def get_feature_names(pipeline: Pipeline, X_train: pd.DataFrame) -> list[str]:
    cat_cols, num_cols = split_column_types(X_train)
    transformer: ColumnTransformer = pipeline.named_steps["preprocessor"]
    enc: OneHotEncoder = transformer.named_transformers_["cat"]
    encoded_cat = enc.get_feature_names_out(cat_cols).tolist()
    return num_cols + encoded_cat


def fit_transform_train(
    X_train: pd.DataFrame,
) -> tuple[Any, Pipeline, list[str]]:
    pipeline = build_preprocessing_pipeline(X_train)
    X_enc = pipeline.fit_transform(X_train)
    feature_names = get_feature_names(pipeline, X_train)
    logger.info("Encoded training matrix shape: %s", X_enc.shape)
    return X_enc, pipeline, feature_names


def transform_test(X_test: pd.DataFrame, pipeline: Pipeline) -> Any:
    return pipeline.transform(X_test)
