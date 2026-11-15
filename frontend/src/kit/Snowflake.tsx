"use client";

import { isNum } from "@/modules/research/format";

/** Scores the shape is drawn from, clockwise from the top, each 0 to 100. */
export const SHAPE_KEYS = ["valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile", "core_quant_score"] as const;
const LABELS = ["Valuation", "Quality", "Momentum", "Low volatility", "Score"];

/** A name's score shape: one small radar per name so a list reads at a glance (bigger = stronger everywhere). */
export function Snowflake({ values, size = 22 }: { values: (number | null | undefined)[]; size?: number }) {
  const r = size / 2 - 1, c = size / 2;
  const pt = (i: number, f: number) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / values.length; return `${(c + Math.cos(a) * r * f).toFixed(1)},${(c + Math.sin(a) * r * f).toFixed(1)}`; };
  const known = values.filter(isNum);
  const title = values.map((v, i) => `${LABELS[i] ?? i} ${isNum(v) ? v.toFixed(0) : "unknown"}`).join(", ");
  return (
    <svg className="snow" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={title}>
      <title>{title}</title>
      <polygon points={values.map((_, i) => pt(i, 1)).join(" ")} fill="none" stroke="var(--line-2, var(--line))" strokeWidth={0.8} />
      {known.length >= 3 ? <polygon points={values.map((v, i) => pt(i, isNum(v) ? Math.max(0.06, Math.min(1, v / 100)) : 0.06)).join(" ")} fill="color-mix(in oklch, var(--accent) 45%, transparent)" stroke="var(--accent)" strokeWidth={0.9} strokeLinejoin="round" /> : null}
    </svg>
  );
}

export const shapeOf = (r: Record<string, unknown>) => SHAPE_KEYS.map((k) => (isNum(r[k]) ? (r[k] as number) : null));
