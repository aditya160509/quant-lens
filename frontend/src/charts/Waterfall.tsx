"use client";

import { scaleLinear } from "d3";
import { memo, useMemo } from "react";
import { Svg, crisp, fmtTick, useWidth } from "./core";

const M = { top: 6, right: 70, bottom: 26, left: 130 };
const ROW = 24;

/**
 * One prediction explained: from the base value, each feature pushes the output up or down until it
 * reaches the prediction. Largest pushes first; the rest are folded into "other features".
 */
function WaterfallImpl({ base, items, maxRows = 10, format = fmtTick }: { base: number; items: { label: string; value: number }[]; maxRows?: number; format?: (v: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const steps = useMemo(() => {
    const sorted = [...items].filter((i) => Number.isFinite(i.value)).sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
    const head = sorted.slice(0, maxRows);
    const rest = sorted.slice(maxRows).reduce((a, i) => a + i.value, 0);
    const list = rest ? [...head, { label: `${sorted.length - maxRows} other features`, value: rest }] : head;
    const steps: { label: string; value: number; from: number; to: number }[] = [];
    let acc = base;
    for (const i of [...list].reverse()) { steps.push({ ...i, from: acc, to: acc + i.value }); acc += i.value; }
    return steps.reverse();
  }, [base, items, maxRows]);
  const final = steps.length ? steps[0].to : base;
  const all = steps.flatMap((s) => [s.from, s.to]).concat(base);
  const xs = scaleLinear().domain([Math.min(...all), Math.max(...all)]).range([M.left, Math.max(M.left + 10, width - M.right)]).nice();
  const height = M.top + M.bottom + (steps.length + 1) * ROW;

  return (
    <div ref={ref}>
      {width > 0 ? (
        <Svg width={width} height={height} label="Waterfall of feature contributions">
          <line x1={crisp(xs(base))} x2={crisp(xs(base))} y1={M.top} y2={height - M.bottom} stroke="var(--line-3)" strokeDasharray="3 3" />
          <line x1={crisp(xs(final))} x2={crisp(xs(final))} y1={M.top} y2={height - M.bottom} stroke="var(--accent)" strokeDasharray="3 3" />
          {steps.map((s, i) => {
            const y = M.top + i * ROW;
            const up = s.value >= 0;
            const x0 = xs(Math.min(s.from, s.to)), x1 = xs(Math.max(s.from, s.to));
            return (
              <g key={s.label}>
                <text x={M.left - 10} y={y + ROW / 2 + 4} textAnchor="end" fontSize={11} fill="var(--text-2)" style={{ fontFamily: "var(--font)" }}>{s.label.length > 20 ? `${s.label.slice(0, 19)}…` : s.label}</text>
                <rect x={x0} y={y + 4} width={Math.max(1.5, x1 - x0)} height={ROW - 8} rx={2} fill={up ? "var(--up)" : "var(--down)"} fillOpacity={0.85} />
                <text x={x1 + 6} y={y + ROW / 2 + 4} fontSize={10.5} fill={up ? "var(--up)" : "var(--down)"}>{up ? "+" : ""}{format(s.value)}</text>
              </g>
            );
          })}
          <text x={xs(base)} y={height - 8} textAnchor="middle" fontSize={10.5} fill="var(--text-3)">base {format(base)}</text>
          <text x={xs(final)} y={M.top + steps.length * ROW + ROW / 2 + 4} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--accent)">prediction {format(final)}</text>
        </Svg>
      ) : <div style={{ height }} />}
    </div>
  );
}

export const Waterfall = memo(WaterfallImpl);
