"use client";

import { memo, useState } from "react";
import { Svg, useWidth } from "./core";

export type RadarAxis = { key: string; label: string; better?: "high" | "low"; format?: (v: number) => string };
export type RadarSeries = { label: string; values: Record<string, number | null | undefined>; primary?: boolean; color?: string };

type Props = { axes: RadarAxis[]; series: RadarSeries[]; height?: number };

/**
 * Several models scored on several metrics at once. Each axis is rescaled across the models so that
 * outward is always better (axes where lower is better are flipped); the readout gives raw values.
 * The model under test is filled in the accent; comparators are outlines in the tint family.
 */
function RadarImpl({ axes, series, height = 340 }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [axisHover, setAxisHover] = useState<number | null>(null);
  const cx = width / 2, cy = height / 2 + 4;
  const R = Math.max(40, Math.min(width / 2 - 92, height / 2 - 34));
  const ang = (i: number) => -Math.PI / 2 + (i / axes.length) * Math.PI * 2;
  // Per-axis scale: worst model at 18% of the radius, best at the rim.
  const norm = axes.map((a) => {
    const vs = series.map((s) => s.values[a.key]).filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    const lo = Math.min(...vs), hi = Math.max(...vs);
    return (v: number | null | undefined) => {
      if (typeof v !== "number" || !Number.isFinite(v)) return null;
      const t = hi === lo ? 1 : (v - lo) / (hi - lo);
      return 0.18 + 0.82 * (a.better === "low" ? 1 - t : t);
    };
  });
  let k = 0;
  const colors = series.map((s) => s.color ?? (s.primary ? "var(--accent)" : `var(--tint-${(k++ % 5) + 1})`));
  const point = (i: number, r: number) => [cx + Math.cos(ang(i)) * R * r, cy + Math.sin(ang(i)) * R * r] as const;
  const poly = (s: RadarSeries) => axes.map((a, i) => point(i, norm[i](s.values[a.key]) ?? 0).join(",")).join(" ");
  // Draw comparators first so the model under test sits on top.
  const order = series.map((_, i) => i).sort((a, b) => Number(Boolean(series[a].primary)) - Number(Boolean(series[b].primary)));
  const fmt = (a: RadarAxis, v: number | null | undefined) => (typeof v === "number" && Number.isFinite(v) ? (a.format ? a.format(v) : v.toFixed(2)) : "–");

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 ? (
        <Svg width={width} height={height} label={`Radar of ${series.length} models across ${axes.length} metrics`} onPointerLeave={() => { setHover(null); setAxisHover(null); }}>
          {[0.25, 0.5, 0.75, 1].map((r) => (
            <polygon key={r} points={axes.map((_, i) => point(i, r).join(",")).join(" ")} fill="none" stroke={r === 1 ? "var(--line-3)" : "var(--line-2)"} strokeWidth={1} />
          ))}
          {axes.map((a, i) => {
            const [x, y] = point(i, 1);
            const [lx, ly] = point(i, 1.12);
            const anchor = Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end";
            return (
              <g key={a.key} onPointerEnter={() => setAxisHover(i)} style={{ cursor: "default" }}>
                <line x1={cx} y1={cy} x2={x} y2={y} stroke="var(--line-2)" />
                <text x={lx} y={ly} dy={ly < cy - R * 0.9 ? -2 : ly > cy + R * 0.9 ? 10 : 4} textAnchor={anchor} fontSize={11.5} fill={axisHover === i ? "var(--text)" : "var(--text-2)"} style={{ fontFamily: "var(--font)" }}>
                  {a.label}{a.better === "low" ? " ↓" : ""}
                </text>
              </g>
            );
          })}
          {order.map((si) => {
            const s = series[si];
            const dim = hover !== null && hover !== si;
            return (
              <g key={s.label} onPointerEnter={() => setHover(si)} style={{ transition: "opacity .16s" }} opacity={dim ? 0.25 : 1}>
                <polygon points={poly(s)} fill={colors[si]} fillOpacity={s.primary ? 0.16 : 0.05} stroke={colors[si]} strokeWidth={s.primary ? 2.2 : 1.4} strokeLinejoin="round" />
                {axes.map((a, i) => {
                  const r = norm[i](s.values[a.key]);
                  if (r === null) return null;
                  const [x, y] = point(i, r);
                  return <circle key={a.key} cx={x} cy={y} r={s.primary ? 3.2 : 2.4} fill={colors[si]} stroke="var(--island)" strokeWidth={1} />;
                })}
              </g>
            );
          })}
          {axisHover !== null ? (() => {
            const a = axes[axisHover];
            return series.map((s, si) => {
              const r = norm[axisHover](s.values[a.key]);
              if (r === null) return null;
              const [x, y] = point(axisHover, r);
              return <text key={s.label} x={x + 6} y={y - 5} fontSize={10.5} fill={colors[si]} paintOrder="stroke" stroke="var(--island)" strokeWidth={3} className="num">{fmt(a, s.values[a.key])}</text>;
            });
          })() : null}
        </Svg>
      ) : <div style={{ height }} />}
      <div className="radar-legend">
        {series.map((s, si) => (
          <button key={s.label} type="button" onPointerEnter={() => setHover(si)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(si)} onBlur={() => setHover(null)} data-primary={s.primary || undefined}>
            <i style={{ background: colors[si], opacity: s.primary ? 1 : 0.8 }} />{s.label}
          </button>
        ))}
      </div>
      {hover !== null ? (
        <table className="radar-readout">
          <tbody>
            {axes.map((a) => <tr key={a.key}><td>{a.label}</td><td className="num">{fmt(a, series[hover].values[a.key])}</td></tr>)}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}

export const Radar = memo(RadarImpl);
