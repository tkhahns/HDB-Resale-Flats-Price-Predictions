import { getAnalytics } from "@/lib/analytics";
import MetricsCard from "@/components/MetricsCard";
import BacktestChart from "@/components/BacktestChart";
import BiasChart from "@/components/BiasChart";
import FeatureImportanceChart from "@/components/FeatureImportanceChart";
import PredictForm from "@/components/PredictForm";

export const revalidate = 3600;

export default async function DashboardPage() {
  let data;
  try {
    data = await getAnalytics();
  } catch {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <p className="text-gray-500">
          Analytics data not available. Run the pipeline first to generate{" "}
          <code className="rounded bg-gray-100 px-1">analytics.json</code>.
        </p>
      </main>
    );
  }

  const avgMAPE =
    data.backtest_folds.length > 0
      ? data.backtest_folds.reduce((s, f) => s + f.MAPE_pct, 0) / data.backtest_folds.length
      : null;

  return (
    <main className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            HDB Resale AVM Dashboard
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Singapore HDB automated valuation model · Last run:{" "}
            <span className="font-medium text-gray-700">{data.run_date}</span>
          </p>
        </div>
        <div className="flex gap-4 text-sm text-gray-500">
          <span>
            <span className="font-semibold text-gray-700">{data.n_train.toLocaleString()}</span> train
          </span>
          <span>
            <span className="font-semibold text-gray-700">{data.n_test.toLocaleString()}</span> test
          </span>
          {avgMAPE != null && (
            <span>
              Avg backtest MAPE:{" "}
              <span className="font-semibold text-indigo-600">{avgMAPE.toFixed(2)}%</span>
            </span>
          )}
        </div>
      </div>

      {/* Model metrics */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
          Model metrics (hold-out test set)
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <MetricsCard label="LightGBM" metrics={data.metrics.lgbm} />
          <MetricsCard label="XGBoost" metrics={data.metrics.xgboost} />
          <MetricsCard label="Ensemble" metrics={data.metrics.ensemble} />
        </div>
      </section>

      {/* Live estimate */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
          Price estimator
        </h2>
        <PredictForm />
      </section>

      {/* Backtest */}
      {data.backtest_folds.length > 0 && (
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Walk-forward backtest ({data.backtest_folds.length} folds)
          </h2>
          <BacktestChart folds={data.backtest_folds} />
        </section>
      )}

      {/* Bias grids */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
          Bias analysis
        </h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {data.bias_by_flat_type.length > 0 && (
            <BiasChart
              data={data.bias_by_flat_type}
              segmentKey="flat_type"
              title="By flat type"
            />
          )}
          {data.bias_by_town.length > 0 && (
            <BiasChart
              data={data.bias_by_town}
              segmentKey="town"
              title="By town (top 15 by volume)"
              topN={15}
            />
          )}
        </div>
      </section>

      {/* Feature importance */}
      {data.feature_importance_top20.length > 0 && (
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Feature importance
          </h2>
          <FeatureImportanceChart data={data.feature_importance_top20} />
        </section>
      )}

      <footer className="border-t border-gray-100 pt-4 text-center text-xs text-gray-400">
        HDB Resale AVM · data via data.gov.sg · model artifacts refreshed daily
      </footer>
    </main>
  );
}
