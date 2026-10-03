"use client";

import { scaleLinear } from "d3";
import { memo, useEffect, useMemo, useState } from "react";
import { AxisLabel, AxisY, GridY, Readout, ReadoutRow, Svg, crisp, robustExtent, useWidth, usePointerIndex } from "./core";

export type Spec = {
  id: string;
  estimate: number;
  lo: number | null;
  hi: number | null;
  significant: boolean;
  choices: Record<string, string>;
  extra?: [string, string][];
};

type Props = {
  specs: Spec[];
  dimensions: { key: string; label: string; base?: string }[];
  formatChoice?: (dim: string, value: string) => string;
  formatValue?: (v: number) => string;
  yLabel?: string;
  onHover?: (spec: Spec | null) => void;
};

const CURVE_H = 230;
const ROW = 12;
const DIM_ROW = 18;
const LEFT = 156;
const RIGHT = 12;

/**
 * Specification curve with a linked decision ledger (Simonsohn, Simmons and Nelson 2020).
 * Collapsed, the ledger shows one row per decision with a mark where a spec departs from the base;
 * expanded, it shows one row per choice.
 */
function SpecCurveImpl({ specs, dimensions, formatChoice = (_, v) => v, formatValue = (v) => v.toFixed(4), yLabel = "Estimate", onHover }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [expanded, setExpanded] = useState(false);
  const sorted = useMemo(() => [...specs].sort((a, b) => a.estimate - b.estimate), [specs]);

  const dims = useMemo(() => dimensions
    .map((d) => {
      const values = [...new Set(sorted.map((s) => s.choices[d.key]).filter(Boolean))];
      const base = d.base ?? mode(sorted.map((s) => s.choices[d.key]));
      return { ...d, base, values: [base, ...values.filter((v) => v !== base)] };
    })
    .filter((d) => d.values.length > 1), [dimensions, sorted]);

  const ledgerH = expanded
    ? dims.reduce((h, d) => h + DIM_ROW + d.values.length * ROW + 6, 0)
    : dims.length * DIM_ROW;
  const height = CURVE_H + 18 + ledgerH + 6;
  const x0 = LEFT;
  const x1 = Math.max(x0 + 10, width - RIGHT);
  const step = (x1 - x0) / Math.max(1, sorted.length);
  const xAt = (i: number) => x0 + (i + 0.5) * step;

  const [lo, hi] = useMemo(() => {
    const vals = sorted.flatMap((s) => [s.estimate, s.lo ?? s.estimate, s.hi ?? s.estimate]);
    const [a, b] = robustExtent(vals);
    return [Math.min(a, 0), Math.max(b, 0)];
  }, [sorted]);
  const y = scaleLinear().domain([lo, hi]).range([CURVE_H - 8, 10]).nice();
  const [yMin, yMax] = y.domain();
  const clamp = (v: number) => Math.max(yMin, Math.min(yMax, v));
  const offScale = sorted.filter((s) => s.estimate < yMin || s.estimate > yMax).length;

  const { index, onMove, onLeave } = usePointerIndex(sorted.length, x0, x1);
  const hovered = index === null ? null : sorted[index];
  useEffect(() => { onHover?.(hovered); }, [hovered, onHover]);
  const markW = Math.max(1, Math.min(6, step * 0.6));
  const dotR = Math.max(1.6, Math.min(3, step * 0.3));

  const tone = (s: Spec) => (s.significant ? (s.estimate > 0 ? "var(--up)" : "var(--down)") : "var(--text-3)");

  let cursor = CURVE_H + 18;
  const ledger = dims.map((d) => {
    const top = cursor;
    if (expanded) cursor += DIM_ROW + d.values.length * ROW + 6;
    else cursor += DIM_ROW;
    return { ...d, top };
  });

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {width > 0 ? (
        <Svg width={width} height={height} label="Specification curve" onPointerMove={onMove} onPointerLeave={onLeave}>
          <GridY scale={y} x1={x0} x2={x1} ticks={5} />
          <AxisY scale={y} x={x0} ticks={5} />
          <AxisLabel x={0} y={14}>{yLabel}</AxisLabel>
          <AxisLabel x={0} y={28}>95% CI</AxisLabel>

          {sorted.map((s, i) => (
            <g key={s.id} opacity={hovered && hovered !== s ? 0.55 : 1}>
              {s.lo !== null && s.hi !== null ? (
                <line x1={crisp(xAt(i))} x2={crisp(xAt(i))} y1={y(clamp(s.lo))} y2={y(clamp(s.hi))} stroke={tone(s)} strokeOpacity={0.35} strokeWidth={Math.max(1, Math.min(2, step * 0.25))} />
              ) : null}
              {s.estimate < yMin || s.estimate > yMax ? (
                <path d={s.estimate > yMax ? `M${xAt(i) - 3.5},${y(yMax) + 6}L${xAt(i)},${y(yMax)}L${xAt(i) + 3.5},${y(yMax) + 6}Z` : `M${xAt(i) - 3.5},${y(yMin) - 6}L${xAt(i)},${y(yMin)}L${xAt(i) + 3.5},${y(yMin) - 6}Z`} fill={tone(s)} />
              ) : (
                <circle cx={xAt(i)} cy={y(s.estimate)} r={dotR} fill={tone(s)} />
              )}
            </g>
          ))}

          {ledger.map((d) => (
            <g key={d.key}>
              <line x1={0} x2={x1} y1={crisp(d.top - 4)} y2={crisp(d.top - 4)} stroke="var(--line)" />
              <text x={0} y={d.top + 9} fontSize={10.5} fill="var(--text-2)" style={{ fontFamily: "var(--font)" }}>{d.label}</text>
              {expanded ? (
                d.values.map((v, j) => {
                  const ry = d.top + DIM_ROW + j * ROW;
                  return (
                    <g key={v}>
                      <text x={x0 - 8} y={ry + 3.5} textAnchor="end" fontSize={10} fill={j === 0 ? "var(--text-3)" : "var(--text-2)"}>{truncate(formatChoice(d.key, v), 20)}</text>
                      <line x1={x0} x2={x1} y1={crisp(ry)} y2={crisp(ry)} stroke="var(--grid)" />
                      {sorted.map((s, i) => s.choices[d.key] === v ? (
                        <rect key={s.id} x={xAt(i) - markW / 2} y={ry - 3} width={markW} height={6} rx={1} fill={j === 0 ? "var(--line-2)" : "var(--accent)"} />
                      ) : null)}
                    </g>
                  );
                })
              ) : (
                <>
                  <text x={x0 - 8} y={d.top + 9} textAnchor="end" fontSize={10} fill="var(--text-3)">{truncate(formatChoice(d.key, d.base), 16)}</text>
                  {sorted.map((s, i) => s.choices[d.key] && s.choices[d.key] !== d.base ? (
                    <rect key={s.id} x={xAt(i) - markW / 2} y={d.top + 2} width={markW} height={9} rx={1} fill="var(--accent)" />
                  ) : null)}
                </>
              )}
            </g>
          ))}

          {hovered && index !== null ? (
            <line x1={crisp(xAt(index))} x2={crisp(xAt(index))} y1={4} y2={height - 4} stroke="var(--text-2)" strokeOpacity={0.6} strokeDasharray="2 3" />
          ) : null}
          <rect x={x0} y={0} width={x1 - x0} height={height} fill="transparent" />
        </Svg>
      ) : <div style={{ height: 320 }} />}

      <div style={{ position: "absolute", right: 0, top: -2, display: "flex", gap: 6, alignItems: "center" }}>
        {offScale ? <span className="chip warn" title="Estimates beyond the axis are drawn as arrows at the edge">{offScale} off scale</span> : null}
        <button className="btn sm ghost" onClick={() => setExpanded((e) => !e)} aria-expanded={expanded}>{expanded ? "Collapse choices" : "Show every choice"}</button>
      </div>

      {hovered && index !== null ? (
        <Readout x={xAt(index)} y={12} width={width}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <b style={{ fontWeight: 500 }}>Spec {index + 1} of {sorted.length}</b>
            <span className="num" style={{ color: tone(hovered) }}>{hovered.significant ? "significant" : "not significant"}</span>
          </div>
          <ReadoutRow label="Estimate" value={formatValue(hovered.estimate)} tone={tone(hovered)} />
          {hovered.lo !== null && hovered.hi !== null ? <ReadoutRow label="95% CI" value={`${formatValue(hovered.lo)} to ${formatValue(hovered.hi)}`} /> : null}
          {hovered.extra?.map(([k, v]) => <ReadoutRow key={k} label={k} value={v} />)}
          <div style={{ height: 1, background: "var(--line)", margin: "6px 0" }} />
          {dims.filter((d) => hovered.choices[d.key] !== d.base).map((d) => (
            <ReadoutRow key={d.key} label={d.label} value={formatChoice(d.key, hovered.choices[d.key])} tone="var(--accent)" />
          ))}
          {dims.every((d) => hovered.choices[d.key] === d.base) ? <span style={{ color: "var(--text-3)" }}>Base specification</span> : null}
        </Readout>
      ) : null}
    </div>
  );
}

function mode(values: (string | undefined)[]): string {
  const counts = new Map<string, number>();
  for (const v of values) if (v) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
}

const truncate = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

export const SpecCurve = memo(SpecCurveImpl);
