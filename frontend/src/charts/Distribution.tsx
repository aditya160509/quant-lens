"use client";

import { area, bin, quantileSorted, scaleLinear } from "d3";
import { memo, useMemo, useState } from "react";
import { AxisLabel, AxisX, AxisY, Readout, ReadoutRow, Svg, crisp, useWidth } from "./core";

type View = "histogram" | "strip" | "box" | "ridge";
type Props = {
  values: number[]; observed?: number | null; tail?: "right" | "left" | "two";
  xLabel?: string; observedLabel?: string; height?: number; format?: (v: number) => string;
  initialView?: View;
};

/** Empirical distributions: no density is reconstructed from summary percentiles. */
function DistributionImpl({ values, observed = null, tail = "right", xLabel = "Statistic", observedLabel = "Observed", height = 220, format = (v) => v.toFixed(2), initialView = "histogram" }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [view, setView] = useState<View>(initialView);
  const clean = useMemo(() => values.filter(Number.isFinite).sort((a, b) => a - b), [values]);
  const mark = observed !== null && Number.isFinite(observed) ? observed : null;
  const { bins, domain, q } = useMemo(() => {
    const lo = Math.min(clean[0] ?? 0, mark ?? Infinity), hi = Math.max(clean[clean.length - 1] ?? 0, mark ?? -Infinity);
    const pad = (hi - lo || Math.abs(lo) || 1) * 0.08;
    const scale = scaleLinear().domain([lo - pad, hi + pad]).nice();
    return { bins: bin().domain(scale.domain() as [number, number]).thresholds(scale.ticks(Math.min(40, Math.max(8, Math.round(Math.sqrt(clean.length))))))(clean), domain: scale.domain(), q: [0.05, 0.25, 0.5, 0.75, 0.95].map((p) => quantileSorted(clean, p) ?? 0) };
  }, [clean, mark]);
  const left = view === "histogram" ? 38 : 12, right = Math.max(24, width - 12), bottom = height - 32, top = 28;
  const x = scaleLinear().domain(domain).range([left, right]);
  const maxCount = Math.max(1, ...bins.map((b) => b.length));
  const y = scaleLinear().domain([0, maxCount]).range([bottom, top]);
  const inTail = (v: number) => mark === null ? false : tail === "right" ? v >= mark : tail === "left" ? v <= mark : Math.abs(v) >= Math.abs(mark);
  const extreme = mark === null ? null : clean.filter(inTail).length;
  const hb = hover === null ? null : bins[hover];
  const midY = (top + bottom) / 2;
  const ridge = area<(typeof bins)[number]>().x((b) => x(((b.x0 ?? 0) + (b.x1 ?? 0)) / 2)).y0(bottom).y1((b) => y(b.length))(bins);
  const summary = `${xLabel}: ${clean.length} observations; median ${format(q[2])}; central 90% ${format(q[0])} to ${format(q[4])}.`;
  return <div ref={ref} style={{ position: "relative" }}>
    {!clean.length ? <p className="chart-empty">No finite observations. Run the study with enough valid samples to estimate a distribution.</p> : <>
      <div className="chart-mode-tabs" role="group" aria-label={`${xLabel} distribution view`}>{(["histogram", "strip", "box", "ridge"] as View[]).map((v) => <button key={v} aria-pressed={view === v} onClick={() => { setView(v); setHover(null); }}>{v.charAt(0).toUpperCase() + v.slice(1)}</button>)}</div>
      <p className="calendar-note">Median {format(q[2])} · Central 90%: {format(q[0])} to {format(q[4])}{mark !== null ? ` · ${observedLabel} ${format(mark)} · ${((extreme ?? 0) / clean.length * 100).toFixed(1)}% as extreme` : ""}</p>
      {width > 0 ? <Svg width={width} height={height} label={summary} tabIndex={0}
        onFocus={() => setHover(0)} onBlur={() => setHover(null)}
        onKeyDown={(e) => { if (["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(e.key)) { e.preventDefault(); setHover(e.key === "Escape" ? null : e.key === "Home" ? 0 : e.key === "End" ? bins.length - 1 : Math.max(0, Math.min(bins.length - 1, (hover ?? 0) + (e.key === "ArrowLeft" ? -1 : 1)))); } }}
        onPointerMove={(e) => { const v = x.invert(e.clientX - e.currentTarget.getBoundingClientRect().left); const i = bins.findIndex((b, i) => (b.x0 ?? 0) <= v && (v < (b.x1 ?? 0) || i === bins.length - 1 && v <= (b.x1 ?? 0))); setHover(i < 0 ? null : i); }} onPointerLeave={() => setHover(null)}>
        <rect x={x(q[0])} y={top} width={Math.max(1, x(q[4]) - x(q[0]))} height={bottom - top} fill="var(--text)" fillOpacity={0.04} />
        {view === "histogram" ? bins.map((b, i) => { const count = b.filter(inTail).length; const w = Math.max(1, x(b.x1 ?? 0) - x(b.x0 ?? 0) - 1); return <g key={i}><rect x={x(b.x0 ?? 0)} y={y(b.length)} width={w} height={bottom - y(b.length)} fill="var(--c1)" fillOpacity={hover === i ? 0.95 : 0.6} rx={1.5} />{count ? <rect x={x(b.x0 ?? 0)} y={y(count)} width={w} height={bottom - y(count)} fill="var(--down)" rx={1.5} /> : null}</g>; }) : null}
        {view === "ridge" ? <path d={ridge ?? ""} fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth={1.5} /> : null}
        {view === "strip" ? clean.map((v, i) => <circle key={i} cx={x(v)} cy={midY + ((i * 37) % 11 - 5) * 4} r={clean.length > 1000 ? 1 : 2.5} fill={inTail(v) ? "var(--down)" : "var(--c1)"} fillOpacity={clean.length > 1000 ? 0.3 : 0.7} />) : null}
        {view === "box" ? <g><line x1={x(q[0])} x2={x(q[4])} y1={midY} y2={midY} stroke="var(--text-2)" />{[q[0], q[4]].map((v, i) => <line key={i} x1={x(v)} x2={x(v)} y1={midY - 14} y2={midY + 14} stroke="var(--text-2)" />)}<rect x={x(q[1])} y={midY - 24} width={Math.max(1, x(q[3]) - x(q[1]))} height={48} fill="var(--accent-soft)" stroke="var(--accent)" />{clean.filter((v) => v < q[0] || v > q[4]).map((v, i) => <circle key={i} cx={x(v)} cy={midY} r={2} fill="var(--text-2)" />)}</g> : null}
        <line x1={crisp(x(q[2]))} x2={crisp(x(q[2]))} y1={top} y2={bottom} stroke="var(--text-2)" strokeDasharray="3 3" />
        {mark !== null ? <g><line x1={crisp(x(mark))} x2={crisp(x(mark))} y1={top - 8} y2={bottom} stroke="var(--down)" strokeWidth={1.5} /><text x={x(mark)} y={top - 12} textAnchor={x(mark) > width / 2 ? "end" : "start"} fontSize={10.5} fill="var(--text)">{observedLabel} {format(mark)}</text></g> : null}
        {view === "histogram" ? <>
          <AxisLabel x={left} y={12} anchor="start">Count</AxisLabel>
          <AxisY scale={y} x={left} ticks={Math.min(4, maxCount)} format={(v) => String(v)} spine />
        </> : null}
        <AxisX scale={x} y={bottom} ticks={Math.max(2, Math.floor(width / 90))} format={format} spine /><AxisLabel x={right} y={height - 1} anchor="end">{xLabel}</AxisLabel>
      </Svg> : <div style={{ height }} />}
      {view !== "histogram" || mark !== null ? <p className="calendar-note">{view === "box" ? "Box: 25th–75th percentiles; whiskers: 5th–95th. Dots show observations beyond the whiskers." : view === "ridge" ? "Frequency ridge joins histogram bin centres; it is not a fitted probability density." : view === "strip" ? "Each dot is one observation; vertical jitter only separates overlapping values." : mark === null ? null : "Red bars count observations as extreme as the marker."}{view !== "histogram" || mark !== null ? " The shaded interval contains the central 90%." : null}</p> : null}
      {hb ? <Readout x={x(((hb.x0 ?? 0) + (hb.x1 ?? 0)) / 2)} y={60} width={width}><ReadoutRow label="Range" value={`${format(hb.x0 ?? 0)} to ${format(hb.x1 ?? 0)}`} /><ReadoutRow label="Observations" value={`${hb.length} of ${clean.length}`} /><ReadoutRow label="Share" value={`${(hb.length / clean.length * 100).toFixed(1)}%`} /></Readout> : null}
    </>}
  </div>;
}
export const Distribution = memo(DistributionImpl);
