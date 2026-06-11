export interface ModelMetrics {
  MAE: number;
  RMSE: number;
  MAPE_pct?: number;
  R2?: number;
  [key: string]: number | undefined;
}

export interface BacktestFold {
  fold: number;
  test_start: string;
  test_end: string;
  n_train: number;
  n_test: number;
  MAPE_pct: number;
  MAE: number;
  RMSE: number;
  signed_error: number;
}

export interface BiasRow {
  [key: string]: string | number;
  n: number;
  mean_signed_error: number;
  mae: number;
  mape_pct: number;
}

export interface PriceBandRow {
  price_band: number;
  price_min: number;
  price_max: number;
  n: number;
  mean_signed_error: number;
  mae: number;
}

export interface FeatureImportanceRow {
  Feature: string;
  LGBM_importance: number;
  XGB_importance: number;
  mean_importance: number;
}

export interface AnalyticsData {
  run_date: string;
  n_train: number;
  n_test: number;
  metrics: {
    lgbm: ModelMetrics;
    xgboost: ModelMetrics;
    ensemble: ModelMetrics;
  };
  backtest_folds: BacktestFold[];
  bias_by_flat_type: BiasRow[];
  bias_by_town: BiasRow[];
  bias_by_price_band: PriceBandRow[];
  feature_importance_top20: FeatureImportanceRow[];
}
