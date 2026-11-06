"use client";

import { line as d3line, polygonContains, scaleLinear } from "d3";
import { memo, useMemo, useState, type ReactNode } from "react";
import { downloadCsv } from "./export";
import { AxisLabel, AxisX, AxisY, GridX, GridY, Legend, Readout, ReadoutRow, ReadoutTitle, SERIES, Svg, crisp, fmtTick, robustExtent, useWidth } from "./core";

export type XYPoint = { x: number; y: number; label?: string; group?: string; size?: number; emphasis?: boolean; detail?: [string, string][] };

type Props = {
  points: XYPoint[];
  /** Lines drawn through ordered points, e.g. fitted values either side of a cutoff. */
  lines?: { label: string; points: { x: number; y: number }[]; color?: string; dash?: boolean }[];
  xLabel: string;
  yLabel: string;
  height?: number;
  refX?: { x: number; label?: string; color?: string }[];
  refY?: { y: number; label?: string; color?: string }[];
  diagonal?: boolean;
  quadrants?: [string, string, string, string];
  labelPoints?: boolean;
  groupColors?: Record<string, string>;
  formatX?: (v: number) => string;
  formatY?: (v: number) => string;
  robust?: boolean;
  square?: boolean;
  footer?: ReactNode;
  onSelection?: (points: XYPoint[]) => void;
};

const NO_LINES: NonNullable<Props["lines"]> = [];
const NO_REF_X: NonNullable<Props["refX"]> = [];
const NO_REF_Y: NonNullable<Props["refY"]> = [];
const M = { top: 14, right: 16, bottom: 34, left: 52 };

/** Scatter plot with optional fitted lines, reference lines, quadrant labels and nearest-point readout. */
function XYPlotImpl({
  points, lines = NO_LINES, xLabel, yLabel, height = 300, refX = NO_REF_X, refY = NO_REF_Y, diagonal = false, quadrants, labelPoints = false,
  groupColors, formatX = fmtTick, formatY = fmtTick, robust = false, square = false, footer, onSelection,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [selecting, setSelecting] = useState(false);
  const [lasso, setLasso] = useState<[number, number][]>([]);
  const [selected, setSelected] = useState<XYPoint[]>([]);
  const [hoverBin, setHoverBin] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const groups = useMemo(() => [...new Set(points.map((p) => p.group ?? ""))], [points]);
  const colorOf = (g = "") => groupColors?.[g] ?? (groups.length > 1 ? SERIES[groups.indexOf(g) % SERIES.length] : "var(--s1)");

  const [xd, yd] = useMemo(() => {
    const xsv = [...points.map((p) => p.x), ...lines.flatMap((l) => l.points.map((p) => p.x)), ...refX.map((r) => r.x)];
    const ysv = [...points.map((p) => p.y), ...lines.flatMap((l) => l.points.map((p) => p.y)), ...refY.map((r) => r.y)];
    const ext = (v: number[]): [number, number] => {
      if (robust) return robustExtent(v, 0.06, 0.01);
      const f = v.filter(Number.isFinite);
      if (!f.length) return [0, 1];
      const lo = Math.min(...f), hi = Math.max(...f), pad = (hi - lo || 1) * 0.08;
      return [lo - pad, hi + pad];
    };
    let xe = ext(xsv);
    let ye = ext(ysv);
    if (square) { const lo = Math.min(xe[0], ye[0]); const hi = Math.max(xe[1], ye[1]); xe = [lo, hi]; ye = [lo, hi]; }
    return [xe, ye];
  }, [points, lines, refX, refY, robust, square]);

  const plotW = Math.max(40, width - M.left - M.right);
  const xs = scaleLinear().domain(xd).range([M.left, M.left + plotW]).nice();
  const ys = scaleLinear().domain(yd).range([height - M.bottom, M.top]).nice();
  const inside = (p: { x: number; y: number }) => p.x >= xs.domain()[0] && p.x <= xs.domain()[1] && p.y >= ys.domain()[0] && p.y <= ys.domain()[1];
  const shown = points.filter(inside);
  const hp = hover === null ? null : shown[hover];
  const r = shown.length > 600 ? 1.8 : shown.length > 120 ? 2.6 : 4;

  const density = shown.length > 2000;
  const bins = useMemo(() => {
    if (points.length <= 2000) return [];
    const radius = 9, bins = new Map<string, { x: number; y: number; count: number; members: XYPoint[] }>();
    for (const p of points) {
      if (!inside(p)) continue;
      const px = xs(p.x), py = ys(p.y);
      const q = (Math.sqrt(3) / 3 * px - py / 3) / radius, r = py * 2 / 3 / radius;
      let a = Math.round(q), b = Math.round(r); const c = Math.round(-q - r);
      const da = Math.abs(a - q), db = Math.abs(b - r), dc = Math.abs(c + q + r);
      if (da > db && da > dc) a = -b - c; else if (db > dc) b = -a - c;
      const key = `${a},${b}`, bin = bins.get(key);
      if (bin) { bin.count++; bin.members.push(p); }
      else bins.set(key, { x: radius * Math.sqrt(3) * (a + b / 2), y: radius * 1.5 * b, count: 1, members: [p] });
    }
    return [...bins.values()];
    // Scales are rebuilt from these inputs; pointer state never rebuilds density geometry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, width, height, xd, yd]);
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const maxBin = Math.max(1, ...bins.map((b) => b.count));
  const choose = (next: XYPoint[]) => { setSelected(next); onSelection?.(next); };
  const pointAt = (e: React.PointerEvent<SVGSVGElement>): [number, number] => { const b = e.currentTarget.getBoundingClientRect(); return [Math.max(M.left, Math.min(M.left + plotW, e.clientX - b.left)), Math.max(M.top, Math.min(height - M.bottom, e.clientY - b.top))]; };
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const [mx, my] = pointAt(e);
    if (lasso.length) { const last = lasso[lasso.length - 1]; if (Math.hypot(mx - last[0], my - last[1]) > 3) setLasso([...lasso, [mx, my]]); return; }
    if (density) { let best = -1, distance = 14 * 14; bins.forEach((b, i) => { const d = (b.x - mx) ** 2 + (b.y - my) ** 2; if (d < distance) { best = i; distance = d; } }); setHoverBin(best < 0 ? null : best); return; }
    let best = -1, bestD = 24 * 24;
    shown.forEach((p, i) => { const dx = xs(p.x) - mx, dy = ys(p.y) - my, d = dx * dx + dy * dy; if (d < bestD) { bestD = d; best = i; } });
    setHover(best >= 0 ? best : null);
  };

  const [xa, xb] = xs.domain();
  const [ya, yb] = ys.domain();

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {points.length ? <div className="chart-mode-tabs" role="group" aria-label="Scatter selection">
        <button aria-pressed={selecting} onClick={() => { setSelecting(!selecting); setLasso([]); }}>Lasso</button>
        <button onClick={() => choose(shown)}>Select all {shown.length}</button>
        {selected.length ? <><button onClick={() => choose([])}>Clear selection</button><button onClick={() => downloadCsv(selected.map(({ x, y, label, group }) => ({ x, y, label, group })), "scatter-selection")}>CSV · {selected.length} selected</button></> : null}
        {density ? <span>{shown.length.toLocaleString()} observations · 1–{maxBin} per hexagon</span> : null}
      </div> : null}
      {groups.length > 1 && !density || lines.length ? (
        <div style={{ marginBottom: 6 }}>
          <Legend items={[...groups.filter(Boolean).map((g) => ({ label: g, color: colorOf(g) })), ...lines.map((l, i) => ({ label: l.label, color: l.color ?? SERIES[(i + 1) % SERIES.length], dash: l.dash }))]} />
        </div>
      ) : null}
      {width > 0 ? (
        <Svg width={width} height={height} label={`${yLabel} against ${xLabel}. ${shown.length} observations${density ? ", hexagonal density" : ""}.`} tabIndex={0}
          onFocus={() => setHover(shown.length ? 0 : null)} onBlur={() => setHover(null)}
          onKeyDown={(e) => { if (["ArrowLeft", "ArrowRight", "Home", "End", "Escape", " "].includes(e.key)) { e.preventDefault(); if (e.key === "Escape") { setLasso([]); setSelecting(false); setHover(null); choose([]); } else if (e.key === " " && hp) choose(selected.includes(hp) ? selected.filter((p) => p !== hp) : [...selected, hp]); else setHover(e.key === "Home" ? 0 : e.key === "End" ? shown.length - 1 : Math.max(0, Math.min(shown.length - 1, (hover ?? 0) + (e.key === "ArrowLeft" ? -1 : 1)))); } }}
          onPointerMove={onMove} onPointerLeave={() => { setHover(null); setHoverBin(null); }}
          onPointerDown={(e) => { if (selecting && e.button === 0) { e.preventDefault(); setLasso([pointAt(e)]); e.currentTarget.setPointerCapture(e.pointerId); } }}
          onPointerUp={() => { if (lasso.length >= 3) choose(shown.filter((p) => polygonContains(lasso, [xs(p.x), ys(p.y)]))); setLasso([]); }} onPointerCancel={() => setLasso([])} style={{ touchAction: selecting ? "none" : "auto", cursor: selecting ? "crosshair" : "default" }}>
          <GridY scale={ys} x1={M.left} x2={M.left + plotW} ticks={5} />
          <GridX scale={xs} y1={M.top} y2={height - M.bottom} ticks={6} />
          {xa < 0 && xb > 0 ? <line x1={crisp(xs(0))} x2={crisp(xs(0))} y1={M.top} y2={height - M.bottom} stroke="var(--line-3)" /> : null}
          <AxisY scale={ys} x={M.left} ticks={5} format={formatY} spine />
          <AxisX scale={xs} y={height - M.bottom} ticks={6} format={formatX} spine />
          <AxisLabel x={M.left + plotW} y={height - 2} anchor="end">{xLabel}</AxisLabel>
          <AxisLabel x={M.left} y={M.top - 4}>{yLabel}</AxisLabel>
          {quadrants ? (
            <g style={{ fontFamily: "var(--font)" }} fontSize={11} fill="var(--text-4)">
              <text x={M.left + plotW - 6} y={M.top + 14} textAnchor="end">{quadrants[0]}</text>
              <text x={M.left + 6} y={M.top + 14}>{quadrants[1]}</text>
              <text x={M.left + 6} y={height - M.bottom - 8}>{quadrants[2]}</text>
              <text x={M.left + plotW - 6} y={height - M.bottom - 8} textAnchor="end">{quadrants[3]}</text>
            </g>
          ) : null}
          {diagonal ? <line x1={xs(Math.max(xa, ya))} y1={ys(Math.max(xa, ya))} x2={xs(Math.min(xb, yb))} y2={ys(Math.min(xb, yb))} stroke="var(--text-3)" strokeDasharray="4 4" /> : null}
          {refX.map((l, i) => (
            <g key={`rx${i}`}>
              <line x1={crisp(xs(l.x))} x2={crisp(xs(l.x))} y1={M.top} y2={height - M.bottom} stroke={l.color ?? "var(--warn)"} strokeDasharray="4 3" />
              {l.label ? <text x={xs(l.x) + 5} y={M.top + 11} fontSize={10.5} fill={l.color ?? "var(--warn)"} style={{ fontFamily: "var(--font)" }}>{l.label}</text> : null}
            </g>
          ))}
          {refY.map((l, i) => (
            <g key={`ry${i}`}>
              <line x1={M.left} x2={M.left + plotW} y1={crisp(ys(l.y))} y2={crisp(ys(l.y))} stroke={l.color ?? "var(--warn)"} strokeDasharray="4 3" />
              {l.label ? <text x={M.left + plotW - 4} y={ys(l.y) - 5} textAnchor="end" fontSize={10.5} fill={l.color ?? "var(--warn)"} style={{ fontFamily: "var(--font)" }}>{l.label}</text> : null}
            </g>
          ))}
          {density ? bins.map((b, i) => <path key={i} d={Array.from({ length: 6 }, (_, j) => { const a = (60 * j - 30) * Math.PI / 180; return `${j ? "L" : "M"}${b.x + 8.5 * Math.cos(a)},${b.y + 8.5 * Math.sin(a)}`; }).join("") + "Z"} fill="var(--accent)" fillOpacity={0.12 + .88 * Math.sqrt(b.count / maxBin)} stroke={b.members.some((p) => selectedSet.has(p)) ? "var(--warn)" : "none"}><title>{b.count} observations</title></path>) : shown.map((p, i) => (
            <circle key={i} cx={xs(p.x)} cy={ys(p.y)} r={p.size ?? (p.emphasis ? r + 2.5 : r)} fill={p.emphasis ? "var(--warn)" : colorOf(p.group)}
              fillOpacity={p.emphasis ? 1 : shown.length > 300 ? 0.35 : 0.75} stroke={p.emphasis ? "var(--panel)" : "none"} strokeWidth={1.5} />
          ))}
          {lines.map((l, i) => {
            const d = d3line<{ x: number; y: number }>().x((p) => xs(p.x)).y((p) => ys(p.y))([...l.points].filter(inside).sort((a, b) => a.x - b.x));
            return <path key={l.label} d={d ?? ""} fill="none" stroke={l.color ?? SERIES[(i + 1) % SERIES.length]} strokeWidth={2} strokeDasharray={l.dash ? "5 4" : undefined} />;
          })}
          {labelPoints && !density ? shown.filter((p) => p.label).map((p, i) => (
            <text key={`l${i}`} x={xs(p.x)} y={ys(p.y) - (p.emphasis ? 11 : 8)} textAnchor="middle" fontSize={10.5} fill={p.emphasis ? "var(--text)" : "var(--text-2)"} style={{ fontFamily: "var(--font)" }} fontWeight={p.emphasis ? 600 : 400}>{p.label}</text>
          )) : null}
          {!density && selected.filter(inside).map((p, i) => <circle key={`selected-${i}`} cx={xs(p.x)} cy={ys(p.y)} r={4} fill="none" stroke="var(--warn)" strokeWidth={1.5} />)}
          {lasso.length ? <path d={lasso.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join("") + "Z"} fill="var(--accent)" fillOpacity={.12} stroke="var(--accent)" strokeDasharray="4 3" /> : null}
          {hp ? <circle cx={xs(hp.x)} cy={ys(hp.y)} r={(hp.size ?? r) + 3} fill="none" stroke="var(--text)" strokeWidth={1.5} /> : null}
        </Svg>
      ) : <div style={{ height }} />}
      {hp ? (
        <Readout x={xs(hp.x)} y={Math.max(0, ys(hp.y) - 40)} width={width} w={210}>
          {hp.label ? <ReadoutTitle>{hp.label}</ReadoutTitle> : null}
          <ReadoutRow label={xLabel} value={formatX(hp.x)} />
          <ReadoutRow label={yLabel} value={formatY(hp.y)} />
          {hp.group ? <ReadoutRow label="Group" value={hp.group} /> : null}
          {hp.detail?.map(([k, v]) => <ReadoutRow key={k} label={k} value={v} />)}
        </Readout>
      ) : null}
      {density && hoverBin !== null && bins[hoverBin] ? <Readout x={bins[hoverBin].x} y={bins[hoverBin].y} width={width}><ReadoutRow label="Observations" value={String(bins[hoverBin].count)} /></Readout> : null}
      {selected.length ? <div role="status" className="chart-direct-values">{selected.length.toLocaleString()} selected · {xLabel} {formatX(Math.min(...selected.map((p) => p.x)))}–{formatX(Math.max(...selected.map((p) => p.x)))} · {yLabel} {formatY(Math.min(...selected.map((p) => p.y)))}–{formatY(Math.max(...selected.map((p) => p.y)))}</div> : null}
      {footer}
    </div>
  );
}

export const XYPlot = memo(XYPlotImpl);
