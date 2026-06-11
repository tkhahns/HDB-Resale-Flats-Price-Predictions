"use client";

import { ModelMetrics } from "@/lib/types";

interface Props {
  label: string;
  metrics: ModelMetrics;
}

function fmt(v: number | undefined, decimals = 2): string {
  if (v == null) return "—";
  return v.toLocaleString("en-SG", { maximumFractionDigits: decimals });
}

export default function MetricsCard({ label, metrics }: Props) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">{label}</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div>
          <dt className="text-xs text-gray-400">MAE</dt>
          <dd className="text-lg font-bold text-gray-800">S${fmt(metrics.MAE, 0)}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-400">RMSE</dt>
          <dd className="text-lg font-bold text-gray-800">S${fmt(metrics.RMSE, 0)}</dd>
        </div>
        {metrics.MAPE_pct != null && (
          <div>
            <dt className="text-xs text-gray-400">MAPE</dt>
            <dd className="text-lg font-bold text-gray-800">{fmt(metrics.MAPE_pct)}%</dd>
          </div>
        )}
        {metrics.R2 != null && (
          <div>
            <dt className="text-xs text-gray-400">R²</dt>
            <dd className="text-lg font-bold text-gray-800">{fmt(metrics.R2, 4)}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
