"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { FeatureImportanceRow } from "@/lib/types";

interface Props {
  data: FeatureImportanceRow[];
}

export default function FeatureImportanceChart({ data }: Props) {
  const rows = [...data].sort((a, b) => a.mean_importance - b.mean_importance);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Feature importance — top 20
      </h3>
      <ResponsiveContainer width="100%" height={Math.max(300, rows.length * 22)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 140, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="Feature" tick={{ fontSize: 11 }} width={135} />
          <Tooltip />
          <Legend />
          <Bar dataKey="LGBM_importance" name="LightGBM" fill="#6366f1" stackId="a" />
          <Bar dataKey="XGB_importance" name="XGBoost" fill="#f59e0b" stackId="a" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
