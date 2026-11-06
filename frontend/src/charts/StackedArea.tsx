"use client";

import { area, scaleLinear, scaleUtc, stack, stackOffsetExpand, stackOffsetNone, type SeriesPoint } from "d3";
import { memo, useEffect, useId, useMemo, useState } from "react";
import { GridY, Legend, Readout, ReadoutRow, ReadoutTitle, SERIES, Svg, crisp, fmtDate, fmtTick, nearest, parseDate, useCrosshair, useWidth } from "./core";
import { useChartScope } from "./ChartScope";
import { useDataWindow } from "./dataWindow";

type Row = Record<string, unknown>;
type Event = { date: string | number; label: string; kind?: string };
const percent = (v: number) => `${(v * 100).toFixed(1)}%`;

/** Shares and levels use the same denominator in the plot, direct labels and data window. */
function StackedAreaImpl({ data, x = "date", keys, labels, height = 260, normalize = true, format, colors, events: suppliedEvents = [], title = "Composition over time" }: {
  data: Row[]; x?: string; keys: string[]; labels?: Record<string, string>; height?: number; normalize?: boolean; format?: (v: number) => string; colors?: Record<string, string>; events?: Event[]; title?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const uid = useId();
  const chartScope = useChartScope();
  const events = [...new Map([...suppliedEvents, ...(chartScope?.events ?? [])].map((e) => [`${e.date}|${e.label}`, e])).values()];
  const zoom = chartScope?.linked ? chartScope.range : null;
  const [mode, setMode] = useState<boolean | null>(null);
  const [selected, setSelected] = useState<string[] | null>(null);
  const share = mode ?? normalize;
  const activeKeys = useMemo(() => keys.filter((k) => selected === null || selected.includes(k)), [keys, selected]);
  const fmt = share ? percent : format ?? fmtTick;
  const hoverT = useCrosshair((s) => s.t);
  const source = useCrosshair((s) => s.source);
  const setHover = useCrosshair((s) => s.set);
  const rows = useMemo(() => data.flatMap((r) => {
    const t = parseDate(r[x]);
    if (t === null) return [];
    return [{ ...Object.fromEntries(keys.map((k) => [k, typeof r[k] === "number" && Number.isFinite(r[k]) ? Math.max(0, r[k] as number) : 0])), t }];
  }).filter((r) => !zoom || r.t >= zoom[0] && r.t <= zoom[1]).sort((a, b) => a.t - b.t), [data, x, keys, zoom]);
  const times = useMemo(() => rows.map((r) => r.t), [rows]);
  const layers = useMemo(() => stack<Record<string, number>>().keys(activeKeys).offset(share ? stackOffsetExpand : stackOffsetNone)(rows), [activeKeys, share, rows]);
  const color = (k: string) => colors?.[k] ?? SERIES[keys.indexOf(k) % SERIES.length];
  const total = (r: Record<string, number>) => activeKeys.reduce((s, k) => s + r[k], 0);
  const value = (r: Record<string, number>, k: string) => share ? (total(r) ? r[k] / total(r) : 0) : r[k];
  useEffect(() => {
    useDataWindow.getState().register({ chartId: uid, title, series: activeKeys.map((k) => ({ label: labels?.[k] ?? k, color: color(k) })), valueAt: (t) => {
      if (!times.length || t < times[0] || t > times[times.length - 1]) return activeKeys.map(() => null);
      return activeKeys.map((k) => fmt(value(rows[nearest(times, t)], k)));
    } });
    return () => useDataWindow.getState().unregister(uid);
    // Values and formatting are refreshed whenever the data or lens changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, keys, selected, share, format, labels, colors, title, uid]);
  useEffect(() => () => { if (useCrosshair.getState().source === uid) setHover(null, null); }, [uid, setHover]);
  const topMargin = events.length ? 34 : 12;
  const bottom = height - 26;
  const right = Math.max(20, width - (activeKeys.length <= 6 && width >= 420 ? 152 : 12));
  const xs = scaleUtc().domain(zoom ?? [times[0] ?? 0, times[times.length - 1] ?? 1]).range([8, right]);
  const max = useMemo(() => layers.reduce((m, l) => l.reduce((n, d) => Math.max(n, d[1]), m), 0), [layers]);
  const ys = scaleLinear().domain([0, share ? 1 : max || 1]).range([bottom, topMargin]);
  const paths = useMemo(() => {
    const xScale = scaleUtc().domain(zoom ?? [times[0] ?? 0, times[times.length - 1] ?? 1]).range([8, right]);
    const yScale = scaleLinear().domain([0, share ? 1 : max || 1]).range([bottom, topMargin]);
    const path = area<SeriesPoint<Record<string, number>>>().x((d) => xScale(d.data.t)).y0((d) => yScale(d[0])).y1((d) => yScale(d[1]));
    return layers.map((l) => ({ key: l.key, d: path(l) ?? "" }));
  }, [layers, times, right, share, max, bottom, topMargin, zoom]);
  const hi = hoverT !== null && times.length && hoverT >= times[0] && hoverT <= times[times.length - 1] ? nearest(times, hoverT) : null;
  const hr = hi !== null ? rows[hi] : null;
  const last = rows[rows.length - 1];
  const ends = layers.map((l) => ({ key: l.key, y: l.length ? ys((l[l.length - 1][0] + l[l.length - 1][1]) / 2) : bottom, labelY: 0 })).sort((a, b) => a.y - b.y);
  ends.forEach((e, i) => { e.labelY = Math.max(e.y, i ? ends[i - 1].labelY + 18 : topMargin + 6); });
  for (let i = ends.length - 1; i >= 0; i--) ends[i].labelY = Math.min(ends[i].labelY, i === ends.length - 1 ? bottom - 4 : ends[i + 1].labelY - 18);
  let lastLabelX = -Infinity;
  const annotations = events.flatMap((event) => {
    const t = parseDate(event.date);
    return t === null || t < times[0] || t > times[times.length - 1] ? [] : [{ ...event, t }];
  }).sort((a, b) => a.t - b.t).map((event) => {
    const position = xs(event.t);
    const showLabel = position - lastLabelX >= 130;
    if (showLabel) lastLabelX = position;
    return { ...event, position, showLabel };
  });
  const moveTo = (i: number) => { if (times.length) setHover(times[Math.max(0, Math.min(times.length - 1, i))], uid); };
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div className="chart-mode-tabs" role="group" aria-label={`${title}: display`}>
        <button type="button" aria-pressed={share} onClick={() => setMode(true)}>Share</button>
        <button type="button" aria-pressed={!share} onClick={() => setMode(false)}>Absolute</button>
        {zoom ? <button onClick={() => chartScope?.setRange(null)}>Reset linked zoom</button> : null}
      </div>
      {keys.length > 6 ? <Legend isolate items={keys.map((k) => ({ id: k, label: labels?.[k] ?? k, color: color(k), hidden: !activeKeys.includes(k) }))} onToggle={(k, additive) => setSelected((s) => additive ? (s ?? keys).includes(k) ? (s ?? keys).filter((v) => v !== k) : [...(s ?? []), k] : s?.length === 1 && s[0] === k ? null : [k])} /> : null}
      {!rows.length || !activeKeys.length ? <p className="chart-empty">{!rows.length ? zoom ? "No observations in this zoom range. Reset linked zoom to restore the full window." : "No dated observations. Run the study with a window containing data." : "No series selected. Select a name in the legend to restore it."}</p> : width > 0 ? <>
        <Svg width={width} height={height} label={`${title}. ${last ? activeKeys.map((k) => `${labels?.[k] ?? k} ${fmt(value(last, k))}`).join(", ") : ""}. Use arrow keys to inspect dates.`} tabIndex={0}
          onFocus={() => moveTo(times.length - 1)} onBlur={() => { if (useCrosshair.getState().source === uid) setHover(null, null); }}
          onKeyDown={(e) => { if (["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(e.key)) { e.preventDefault(); if (e.key === "Escape") setHover(null, null); else moveTo(e.key === "Home" ? 0 : e.key === "End" ? times.length - 1 : (hi ?? times.length - 1) + (e.key === "ArrowLeft" ? -1 : 1)); } }}
          onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); moveTo(nearest(times, +xs.invert(e.clientX - r.left))); }} onPointerLeave={() => setHover(null, null)}>
          <GridY scale={ys} x1={8} x2={right} ticks={4} />
          {paths.map((l) => <path key={l.key} d={l.d} fill={color(l.key)} fillOpacity={0.5} stroke={color(l.key)} strokeWidth={1} />)}
          {rows.length === 1 ? layers.map((l) => <rect key={l.key} x={xs(last.t) - 3} y={ys(l[0][1])} width={6} height={Math.max(0, ys(l[0][0]) - ys(l[0][1]))} fill={color(l.key)} />) : null}
          {ys.ticks(4).map((v) => <text key={v} x={12} y={ys(v) - 3} fontSize={10.5} fill="var(--text-2)">{fmt(v)}</text>)}
          {xs.ticks(Math.max(2, Math.floor(right / 120))).map((t) => <text key={+t} x={xs(t)} y={height - 6} textAnchor="middle" fontSize={10.5} fill="var(--text-3)">{new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}</text>)}
          {annotations.map((event, i) => <g key={`${event.t}-${i}`}><title>{event.label}: {fmtDate(event.t, true)}</title><line x1={event.position} x2={event.position} y1={topMargin} y2={bottom} stroke="var(--text-3)" strokeDasharray="3 3" />{event.showLabel ? <text x={event.position} y={16} textAnchor={event.position > right - 130 ? "end" : "start"} fontSize={10} fill="var(--text-2)">{event.label.length > 22 ? `${event.label.slice(0, 21)}…` : event.label}</text> : null}</g>)}
          {activeKeys.length <= 6 && width >= 420 ? ends.map((e) => <g key={e.key}><path d={`M${right},${e.y} L${right + 8},${e.labelY}`} fill="none" stroke={color(e.key)} /><text x={right + 12} y={e.labelY} dy=".32em" fontSize={11} fill="var(--text-2)">{labels?.[e.key] ?? e.key} {fmt(value(last, e.key))}</text></g>) : null}
          {hr ? <line x1={crisp(xs(hr.t))} x2={crisp(xs(hr.t))} y1={topMargin} y2={bottom} stroke="var(--text-2)" strokeDasharray="3 3" /> : null}
        </Svg>
        {activeKeys.length <= 6 && width < 420 ? <div className="chart-direct-values">{activeKeys.map((k) => <span key={k}><i style={{ background: color(k) }} />{labels?.[k] ?? k} <b className="num">{fmt(value(last, k))}</b></span>)}</div> : null}
      </> : <div style={{ height }} />}
      {hr && source === uid ? <Readout x={xs(hr.t)} y={topMargin + 12} width={width} w={240}><ReadoutTitle>{fmtDate(hr.t, true)}</ReadoutTitle>{[...activeKeys].sort((a, b) => hr[b] - hr[a]).map((k) => <ReadoutRow key={k} label={labels?.[k] ?? k} value={fmt(value(hr, k))} swatch={color(k)} />)}<ReadoutRow label="Total (absolute)" value={(format ?? fmtTick)(total(hr))} /></Readout> : null}
    </div>
  );
}
export const StackedArea = memo(StackedAreaImpl);
