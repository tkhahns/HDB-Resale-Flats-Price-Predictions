"use client";

import { useState, FormEvent } from "react";

const FLAT_TYPES = ["1 ROOM", "2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE", "MULTI-GENERATION"];
const TOWNS = [
  "ANG MO KIO", "BEDOK", "BISHAN", "BUKIT BATOK", "BUKIT MERAH", "BUKIT PANJANG",
  "BUKIT TIMAH", "CENTRAL AREA", "CHOA CHU KANG", "CLEMENTI", "GEYLANG", "HOUGANG",
  "JURONG EAST", "JURONG WEST", "KALLANG/WHAMPOA", "MARINE PARADE", "PASIR RIS",
  "PUNGGOL", "QUEENSTOWN", "SEMBAWANG", "SENGKANG", "SERANGOON", "TAMPINES",
  "TOA PAYOH", "WOODLANDS", "YISHUN",
];

interface PredictionResult {
  predicted_price: number;
  model_run_date?: string;
}

export default function PredictForm() {
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);

    const fd = new FormData(e.currentTarget);
    const body = {
      town: fd.get("town"),
      flat_type: fd.get("flat_type"),
      floor_area_sqm: Number(fd.get("floor_area_sqm")),
      storey_range: fd.get("storey_range"),
      remaining_lease_months: Number(fd.get("remaining_lease_months")),
      flat_model: fd.get("flat_model") || "Model A",
    };

    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error ?? `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Live price estimate
      </h3>
      <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Town
          <select name="town" required className="rounded border border-gray-300 p-1.5 text-sm">
            {TOWNS.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Flat type
          <select name="flat_type" required className="rounded border border-gray-300 p-1.5 text-sm">
            {FLAT_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Floor area (sqm)
          <input
            name="floor_area_sqm"
            type="number"
            min={30}
            max={300}
            defaultValue={90}
            required
            className="rounded border border-gray-300 p-1.5 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Storey range
          <input
            name="storey_range"
            type="text"
            placeholder="10 TO 12"
            defaultValue="10 TO 12"
            required
            className="rounded border border-gray-300 p-1.5 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Remaining lease (months)
          <input
            name="remaining_lease_months"
            type="number"
            min={0}
            max={1200}
            defaultValue={780}
            required
            className="rounded border border-gray-300 p-1.5 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Flat model
          <input
            name="flat_model"
            type="text"
            placeholder="Model A"
            defaultValue="Model A"
            className="rounded border border-gray-300 p-1.5 text-sm"
          />
        </label>
        <div className="col-span-2 flex items-end sm:col-span-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? "Estimating…" : "Estimate price"}
          </button>
        </div>
      </form>

      {result && (
        <div className="mt-4 rounded-xl bg-indigo-50 px-5 py-4">
          <p className="text-xs text-indigo-500">Estimated resale price</p>
          <p className="text-3xl font-bold text-indigo-700">
            S${result.predicted_price.toLocaleString("en-SG", { maximumFractionDigits: 0 })}
          </p>
          {result.model_run_date && (
            <p className="mt-1 text-xs text-indigo-400">Model run date: {result.model_run_date}</p>
          )}
        </div>
      )}
      {error && (
        <div className="mt-4 rounded-xl bg-red-50 px-5 py-4 text-sm text-red-600">{error}</div>
      )}
    </div>
  );
}
