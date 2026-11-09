"use client";

import type { InputSpec } from "@/modules/research/types";
import { label } from "@/modules/research/format";

type Part = { name: string; field: string; weight: number };

const FACTORS = ["valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile", "liquidity_percentile", "size_percentile", "prox52_percentile"];
const DEFAULT: Record<string, number> = { valuation_percentile: 25, quality_percentile: 25, momentum_percentile: 25, low_vol_percentile: 15, liquidity_percentile: 10 };
const NAME = (f: string) => label(f.replace(/_percentile$/, ""));

const parts = (v: unknown): Part[] => {
  try {
    const list = typeof v === "string" && v.trim() ? JSON.parse(v) : v;
    return Array.isArray(list) ? (list as Part[]) : [];
  } catch { return []; }
};

/** One weight per factor; the backend scales them to sum to one, shown here as shares. */
export function ComponentWeights({ value, onChange }: { field: InputSpec; value: unknown; onChange: (v: unknown) => void }) {
  const set = parts(value);
  const weights = Object.fromEntries(FACTORS.map((f) => [f, set.length ? set.find((p) => p.field === f)?.weight ?? 0 : DEFAULT[f] ?? 0]));
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  const write = (field: string, weight: number) => onChange(FACTORS.map((f) => ({ name: NAME(f), field: f, weight: f === field ? weight : weights[f] })).filter((p) => p.weight > 0));
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {FACTORS.map((f) => (
        <div key={f} style={{ display: "grid", gridTemplateColumns: "92px 1fr 44px", gap: 8, alignItems: "center", fontSize: 12 }}>
          <span>{NAME(f)}</span>
          <input className="range" type="range" min={0} max={100} step={5} value={weights[f]} aria-label={`${NAME(f)} weight`} style={{ ["--fill" as string]: `${weights[f]}%` }} onChange={(e) => write(f, Number(e.target.value))} />
          <span className="num" style={{ textAlign: "right" }}>{total ? `${Math.round((weights[f] / total) * 100)}%` : "–"}</span>
        </div>
      ))}
    </div>
  );
}
