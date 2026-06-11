"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { BiasRow } from "@/lib/types";

interface Props {
  data: BiasRow[];
  segmentKey: string;
  title: string;
  topN?: number;
}

export default function BiasChart({ data, segmentKey, title, topN = 15 }: Props) {
  const rows = [...data]
    .sort((a, b) => Number(b.n) - Number(a.n))
    .slice(0, topN)
    .sort((a, b) => Number(b.mean_signed_error) - Number(a.mean_signed_error));

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
      <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 28)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 100, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
            tick={{ fontSize: 11 }}
          />
          <YAxis type="category" dataKey={segmentKey} tick={{ fontSize: 11 }} width={95} />
          <Tooltip formatter={(v: number) => [`S$${v.toLocaleString()}`, "Signed error"]} />
          <ReferenceLine x={0} stroke="#374151" strokeDasharray="3 3" />
          <Bar dataKey="mean_signed_error" name="Signed error">
            {rows.map((r, i) => (
              <Cell
                key={i}
                fill={Number(r.mean_signed_error) >= 0 ? "#f87171" : "#60a5fa"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
