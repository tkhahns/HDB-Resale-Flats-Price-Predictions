"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { BacktestFold } from "@/lib/types";

interface Props {
  folds: BacktestFold[];
}

export default function BacktestChart({ folds }: Props) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Walk-forward backtest — MAE &amp; signed error by period
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={folds} margin={{ left: 10, right: 10, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="test_start"
            tick={{ fontSize: 11 }}
            angle={-40}
            textAnchor="end"
            interval={0}
          />
          <YAxis yAxisId="mae" orientation="left" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <YAxis yAxisId="err" orientation="right" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <Tooltip
            formatter={(value: number, name: string) =>
              name === "Signed error" ? [`S$${value.toLocaleString()}`, name] : [`S$${value.toLocaleString()}`, name]
            }
          />
          <Legend wrapperStyle={{ paddingTop: 8 }} />
          <Bar yAxisId="mae" dataKey="MAE" name="MAE" fill="#6366f1" opacity={0.8} />
          <ReferenceLine yAxisId="err" y={0} stroke="#374151" strokeDasharray="3 3" />
          <Line
            yAxisId="err"
            type="monotone"
            dataKey="signed_error"
            name="Signed error"
            stroke="#f59e0b"
            dot={{ r: 3 }}
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
