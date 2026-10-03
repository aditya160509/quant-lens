"use client";

import { area as d3area, curveMonotoneX, curveStepAfter, line as d3line, scaleLinear, scaleTime } from "d3";
import { useId, useMemo, useRef, useState, type ReactNode } from "react";
import { MessageSquarePlus, Minus, RotateCcw, X } from "lucide-react";
import { useNotes } from "./annotations";
import {
  AxisTag, GridY, Legend, Readout, ReadoutRow, ReadoutTitle, SERIES, Svg, crisp, fmtDate, fmtTick, nearest, parseDate, robustExtent, useCrosshair, useWidth,
} from "./core";

type Row = Record<string, unknown>;

export type Series = {
  key: string;
  label: string;
  color?: string;
  kind?: "line" | "area" | "step" | "bars";
  dash?: boolean;
  width?: number;
  /** Faint lines drawn behind the main series, e.g. placebo paths. Excluded from the legend and readout. */
  muted?: boolean;
};

export type TimeSeriesProps = {
  data: Row[];
  x?: string;
  series: Series[];
  band?: { lo: string; hi: string; color?: string; label?: string };
  refLines?: { y: number; label?: string; color?: string; dash?: boolean }[];
  markers?: { date: string; label: string; color?: string }[];
  regions?: { from: string; to?: string; label?: string; color?: string }[];
  /** Categorical strip under the plot, e.g. a regime label per date. */
  ribbon?: { key: string; label?: string; colors?: Record<string, string> };
  /** Highlight points where this boolean column is true. */
  highlight?: string;
  height?: number;
  format?: (v: number) => string;
  yLabel?: string;
  /** Persist user notes under this key. */
  notesKey?: string;
  legend?: boolean;
  robust?: boolean;
  /** Green fill above zero, red below, like a cumulative PnL chart. Applies to area series. */
  zeroFill?: boolean;
  /** Overlay bars (e.g. daily PnL) on the same axis. */
  bars?: { key: string; label?: string };
  /** Top-right slot beside the legend. */
  toolbar?: ReactNode;
};

const M = { top: 12, right: 56, bottom: 26, left: 8 };
const RIBBON_H = 14;

/**
 * Time-series chart in the terminal style: y axis on the right, crosshair with axis tags,
 * linked hover across charts, drag-to-zoom (double-click resets), event markers, shaded regions,
 * a categorical ribbon and notes pinned to dates.
 */
export function TimeSeries({
  data, x = "date", series: seriesProp, band, refLines = [], markers = [], regions = [], ribbon, highlight, height = 260,
  format = fmtTick, yLabel, notesKey, legend = true, robust = false, zeroFill = false, bars, toolbar,
}: TimeSeriesProps) {
  const uid = useId();
  const series = useMemo<Series[]>(() => (bars ? [...seriesProp, { key: bars.key, label: bars.label ?? bars.key, kind: "bars" as const }] : seriesProp), [seriesProp, bars]);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());
  const toggle = (k: string) => setHidden((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const [ref, width] = useWidth<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState<[number, number] | null>(null);
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null);
  const [noting, setNoting] = useState(false);
  const [leveling, setLeveling] = useState(false);
  const [draft, setDraft] = useState<{ t: number; text: string } | null>(null);
  const hoverT = useCrosshair((s) => s.t);
  const setHover = useCrosshair((s) => s.set);
  const notes = useNotes((s) => (notesKey ? s.notes[notesKey] : undefined)) ?? [];
  const addNote = useNotes((s) => s.add);
  const removeNote = useNotes((s) => s.remove);

  const rows = useMemo(() => data
    .map((r) => ({ r, t: parseDate(r[x]) }))
    .filter((d): d is { r: Row; t: number } => d.t !== null)
    .sort((a, b) => a.t - b.t), [data, x]);
  const times = useMemo(() => rows.map((d) => d.t), [rows]);
  const visible = useMemo(() => (zoom ? rows.filter((d) => d.t >= zoom[0] && d.t <= zoom[1]) : rows), [rows, zoom]);

  const ribbonH = ribbon ? RIBBON_H + 8 : 0;
  const plotH = height - M.top - M.bottom - ribbonH;
  const x0 = M.left;
  const x1 = Math.max(x0 + 20, width - M.right);
  const tDomain: [number, number] = zoom ?? [times[0] ?? 0, times[times.length - 1] ?? 1];
  const xs = scaleTime().domain(tDomain).range([x0, x1]);

  const yDomain = useMemo(() => {
    const vals: number[] = [];
    for (const { r } of visible) {
      for (const s of series) { if (hidden.has(s.key)) continue; const v = r[s.key]; if (typeof v === "number" && Number.isFinite(v)) vals.push(v); }
      if (band) for (const k of [band.lo, band.hi]) { const v = r[k]; if (typeof v === "number" && Number.isFinite(v)) vals.push(v); }
    }
    for (const l of refLines) vals.push(l.y);
    if (!vals.length) return [0, 1] as [number, number];
    if (robust) return robustExtent(vals, 0.06, 0.005);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
    return [lo - pad, hi + pad] as [number, number];
  }, [visible, series, band, refLines, robust, hidden]);
  const ys = scaleLinear().domain(yDomain).range([M.top + plotH, M.top]).nice();
  const [yMin, yMax] = ys.domain();
  const clampY = (v: number) => Math.max(yMin, Math.min(yMax, v));

  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : null);
  const paths = series.map((s, i) => {
    const color = s.color ?? SERIES[i % SERIES.length];
    const pts = visible.filter((d) => num(d.r[s.key]) !== null);
    const gen = d3line<{ r: Row; t: number }>().x((d) => xs(d.t)).y((d) => ys(clampY(num(d.r[s.key]) as number)))
      .defined((d) => num(d.r[s.key]) !== null)
      .curve(s.kind === "step" ? curveStepAfter : curveMonotoneX);
    const fill = s.kind === "area" && !zeroFill
      ? d3area<{ r: Row; t: number }>().x((d) => xs(d.t)).y0(ys(Math.max(yMin, Math.min(yMax, 0)))).y1((d) => ys(clampY(num(d.r[s.key]) as number)))
        .defined((d) => num(d.r[s.key]) !== null).curve(curveMonotoneX)(visible)
      : null;
    const zf = s.kind === "area" && zeroFill
      ? (sign: 1 | -1) => d3area<{ r: Row; t: number }>().x((d) => xs(d.t)).y0(ys(clampY(0)))
        .y1((d) => ys(clampY(sign * Math.max(0, sign * (num(d.r[s.key]) as number))))).defined((d) => num(d.r[s.key]) !== null).curve(curveMonotoneX)(visible)
      : null;
    return { s, color, d: gen(visible) ?? "", fill, pts, zUp: zf?.(1) ?? null, zDn: zf?.(-1) ?? null };
  });
  const bandPath = band
    ? d3area<{ r: Row; t: number }>().x((d) => xs(d.t)).y0((d) => ys(clampY(num(d.r[band.lo]) as number))).y1((d) => ys(clampY(num(d.r[band.hi]) as number)))
      .defined((d) => num(d.r[band.lo]) !== null && num(d.r[band.hi]) !== null).curve(curveMonotoneX)(visible)
    : null;

  const ticks = xs.ticks(Math.max(2, Math.floor((x1 - x0) / 110)));
  const tickFmt = xs.tickFormat();

  const pxToT = (px: number) => xs.invert(px).getTime();
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = Math.max(x0, Math.min(x1, e.clientX - r.left));
    const t = pxToT(px);
    if (drag) setDrag({ ...drag, to: t });
    if (times.length) setHover(times[nearest(times, t)], uid);
  };
  const onDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    const r = e.currentTarget.getBoundingClientRect();
    const t = pxToT(Math.max(x0, Math.min(x1, e.clientX - r.left)));
    if (noting) { setDraft({ t: times[nearest(times, t)], text: "" }); setNoting(false); return; }
    if (leveling && notesKey) {
      const y = ys.invert(e.clientY - r.top);
      addNote(notesKey, { id: `lvl-${Date.now()}`, t: 0, y: Number(y.toPrecision(4)), text: "" });
      setLeveling(false);
      return;
    }
    setDrag({ from: t, to: t });
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onUp = () => {
    if (drag && Math.abs(xs(drag.to) - xs(drag.from)) > 8) setZoom([Math.min(drag.from, drag.to), Math.max(drag.from, drag.to)]);
    setDrag(null);
  };

  const hoverIdx = hoverT !== null && times.length ? nearest(times, hoverT) : null;
  const hovered = hoverIdx !== null && hoverT !== null && hoverT >= tDomain[0] && hoverT <= tDomain[1] ? rows[hoverIdx] : null;
  const isSource = useCrosshair.getState().source === uid;
  const legendSeries = paths.filter((p) => !p.s.muted);
  const visibleSeries = legendSeries.filter((p) => !hidden.has(p.s.key));
  const lastRow = visible[visible.length - 1];
  const legendItems = legend && legendSeries.length > 1
    ? legendSeries.map((p) => ({ id: p.s.key, hidden: hidden.has(p.s.key), label: p.s.label, color: p.color, dash: p.s.dash, value: (() => { const v = num((hovered ?? lastRow)?.r[p.s.key]); return v === null ? undefined : format(v); })() }))
    : null;

  const ribbonValues = ribbon ? [...new Set(rows.map((d) => String(d.r[ribbon.key] ?? "")).filter(Boolean))] : [];
  const ribbonColor = (v: string) => ribbon?.colors?.[v] ?? SERIES[ribbonValues.indexOf(v) % SERIES.length];
  const ribbonTop = M.top + plotH + M.bottom - 2;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, minHeight: legendItems || notesKey || zoom || toolbar ? 24 : 0, marginBottom: 4 }}>
        {legendItems ? <Legend items={legendItems} onToggle={toggle} /> : null}
        <span style={{ marginLeft: "auto", display: "flex", gap: 4, alignItems: "center" }}>
          {toolbar}
          {zoom ? <button className="btn sm ghost" onClick={() => setZoom(null)}><RotateCcw size={11} />Reset zoom</button> : null}
          {notesKey ? (
            <button className="btn sm ghost" aria-pressed={leveling} onClick={() => { setLeveling((v) => !v); setNoting(false); }} style={leveling ? { color: "var(--accent)" } : undefined} title="Draw a horizontal level">
              <Minus size={12} />{leveling ? "Click a level" : "Level"}
            </button>
          ) : null}
          {notesKey ? (
            <button className="btn sm ghost" aria-pressed={noting} onClick={() => setNoting((n) => !n)} style={noting ? { color: "var(--accent)" } : undefined}>
              <MessageSquarePlus size={12} />{noting ? "Click a date" : "Note"}
            </button>
          ) : null}
        </span>
      </div>
      {width > 0 ? (
        <Svg ref={svgRef} width={width} height={height} label={`${series.map((s) => s.label).join(", ")} over time`}
          onPointerMove={onMove} onPointerLeave={() => { setHover(null, null); }} onPointerDown={onDown} onPointerUp={onUp}
          onDoubleClick={() => setZoom(null)} style={{ cursor: noting || leveling ? "copy" : "crosshair" }}>
          <defs>
            <clipPath id={`${uid}-clip`}><rect x={x0} y={M.top - 2} width={x1 - x0} height={plotH + 4} /></clipPath>
            {paths.filter((p) => p.fill).map((p) => (
              <linearGradient key={p.s.key} id={`${uid}-${p.s.key}-fill`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={p.color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={p.color} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>

          {regions.map((rg, i) => {
            const a = parseDate(rg.from);
            const b = rg.to ? parseDate(rg.to) : tDomain[1];
            if (a === null || b === null) return null;
            const xa = Math.max(x0, xs(a));
            const xb = Math.min(x1, xs(b));
            if (xb <= xa) return null;
            return (
              <g key={i}>
                <rect x={xa} y={M.top} width={xb - xa} height={plotH} fill={rg.color ?? "var(--accent)"} fillOpacity={0.07} />
                {rg.label ? <text x={xa + 6} y={M.top + 12} fontSize={10.5} fill="var(--text-3)" style={{ fontFamily: "var(--font)" }}>{rg.label}</text> : null}
              </g>
            );
          })}

          <GridY scale={ys} x1={x0} x2={x1} ticks={5} />
          {ys.ticks(5).map((t) => (
            <text key={t} x={x1 + 8} y={ys(t)} dy="0.32em" fontSize={10.5} fill="var(--text-3)">{format(t)}</text>
          ))}
          {ticks.map((t) => (
            <text key={t.getTime()} x={xs(t)} y={M.top + plotH + 17} textAnchor="middle" fontSize={10.5} fill="var(--text-3)">{tickFmt(t)}</text>
          ))}
          {yLabel ? <text x={x1 + 8} y={M.top - 2} fontSize={10.5} fill="var(--text-4)" style={{ fontFamily: "var(--font)" }}>{yLabel}</text> : null}

          <g clipPath={`url(#${uid}-clip)`}>
            {bandPath ? <path d={bandPath} fill={band?.color ?? "var(--band)"} /> : null}
            {notes.filter((n) => n.y !== undefined).map((n) => (
              <g key={n.id}>
                <line x1={x0} x2={x1} y1={crisp(ys(n.y!))} y2={crisp(ys(n.y!))} stroke="var(--accent)" strokeOpacity={0.9} />
                <text x={x1 - 4} y={ys(n.y!) - 4} textAnchor="end" fontSize={10.5} fill="var(--accent)" style={{ fontFamily: "var(--mono)" }}>{format(n.y!)}</text>
              </g>
            ))}
            {refLines.map((l, i) => (
              <g key={i}>
                <line x1={x0} x2={x1} y1={crisp(ys(l.y))} y2={crisp(ys(l.y))} stroke={l.color ?? "var(--text-3)"} strokeDasharray={l.dash === false ? undefined : "4 4"} strokeOpacity={0.8} />
                {l.label ? <text x={x0 + 6} y={ys(l.y) - 5} fontSize={10.5} fill={l.color ?? "var(--text-3)"} style={{ fontFamily: "var(--font)" }}>{l.label}</text> : null}
              </g>
            ))}
            {paths.filter((p) => !hidden.has(p.s.key)).map((p) => p.s.kind === "bars" ? (
              <g key={p.s.key}>
                {p.pts.map((d) => {
                  const v = num(d.r[p.s.key]) as number;
                  const w = Math.max(1, ((x1 - x0) / Math.max(1, visible.length)) * 0.7);
                  const y0 = ys(Math.max(yMin, Math.min(yMax, 0)));
                  const y1 = ys(clampY(v));
                  return <rect key={d.t} x={xs(d.t) - w / 2} y={Math.min(y0, y1)} width={w} height={Math.abs(y1 - y0)} rx={1} fill={v >= 0 ? "var(--up)" : "var(--down)"} fillOpacity={0.75} />;
                })}
              </g>
            ) : (
              <g key={p.s.key}>
                {p.zUp ? <path d={p.zUp} fill="var(--up)" fillOpacity={0.16} /> : null}
                {p.zDn ? <path d={p.zDn} fill="var(--down)" fillOpacity={0.16} /> : null}
                {p.fill ? <path d={p.fill} fill={`url(#${uid}-${p.s.key}-fill)`} /> : null}
                <path d={p.d} fill="none" stroke={p.color} style={{ strokeWidth: p.s.width ?? (p.s.muted ? 1 : "var(--lw, 1.6)") }} strokeOpacity={p.s.muted ? 0.28 : 1}
                  strokeDasharray={p.s.dash ? "5 4" : undefined} strokeLinejoin="round" strokeLinecap="round" />
              </g>
            ))}
            {highlight ? visible.filter((d) => d.r[highlight] === true).map((d) => {
              const v = num(d.r[series[0].key]);
              return v === null ? null : <circle key={d.t} cx={xs(d.t)} cy={ys(clampY(v))} r={2.5} fill="var(--accent)" />;
            }) : null}
          </g>

          {visibleSeries.filter((p) => p.s.kind !== "bars").map((p) => {
            const lv = [...p.pts].reverse().find((d) => d.t <= tDomain[1]);
            const v = lv ? num(lv.r[p.s.key]) : null;
            return v === null ? null : <AxisTag key={`end-${p.s.key}`} x={x1 + 2} y={ys(clampY(v))} text={format(v)} tone={p.color} />;
          })}

          {markers.map((m, i) => {
            const t = parseDate(m.date);
            if (t === null || t < tDomain[0] || t > tDomain[1]) return null;
            const mx = crisp(xs(t));
            return (
              <g key={i}>
                <line x1={mx} x2={mx} y1={M.top} y2={M.top + plotH} stroke={m.color ?? "var(--warn)"} strokeDasharray="3 3" />
                <AxisTag x={mx} y={M.top + 2} text={m.label} anchor={mx > x1 - 80 ? "end" : "start"} tone={m.color ?? "var(--warn)"} />
              </g>
            );
          })}

          {notes.filter((n) => n.y === undefined && n.t >= tDomain[0] && n.t <= tDomain[1]).map((n) => {
            const nx = xs(n.t);
            const row = rows[nearest(times, n.t)];
            const v = row ? num(row.r[series[0].key]) : null;
            const ny = v === null ? M.top + 14 : ys(clampY(v));
            return (
              <g key={n.id}>
                <line x1={nx} x2={nx} y1={ny} y2={M.top + 4} stroke="var(--accent)" strokeOpacity={0.6} />
                <circle cx={nx} cy={ny} r={3.5} fill="var(--accent)" stroke="var(--panel)" strokeWidth={1.5} />
                <AxisTag x={nx} y={M.top + 4} text={n.text.length > 26 ? `${n.text.slice(0, 25)}…` : n.text} anchor={nx > x1 - 140 ? "end" : "start"} tone="var(--accent)" />
              </g>
            );
          })}

          {ribbon ? (
            <g>
              {rows.map((d, i) => {
                const next = rows[i + 1]?.t ?? d.t + (rows[1] ? rows[1].t - rows[0].t : 0);
                if (next < tDomain[0] || d.t > tDomain[1]) return null;
                const v = String(d.r[ribbon.key] ?? "");
                const a = Math.max(x0, xs(d.t));
                const b = Math.min(x1, xs(next));
                return v ? <rect key={d.t} x={a} y={ribbonTop} width={Math.max(0.5, b - a)} height={RIBBON_H} fill={ribbonColor(v)} fillOpacity={0.75} /> : null;
              })}
              <text x={x1 + 8} y={ribbonTop + RIBBON_H / 2} dy="0.32em" fontSize={10} fill="var(--text-3)" style={{ fontFamily: "var(--font)" }}>{ribbon.label ?? ""}</text>
            </g>
          ) : null}

          {drag ? (
            <rect x={Math.min(xs(drag.from), xs(drag.to))} y={M.top} width={Math.abs(xs(drag.to) - xs(drag.from))} height={plotH} fill="var(--accent)" fillOpacity={0.1} stroke="var(--accent-line)" />
          ) : null}

          {hovered ? (
            <g pointerEvents="none">
              <line x1={crisp(xs(hovered.t))} x2={crisp(xs(hovered.t))} y1={M.top} y2={M.top + plotH} stroke="var(--text-3)" strokeDasharray="2 3" />
              {visibleSeries.map((p) => {
                const v = num(hovered.r[p.s.key]);
                return v === null ? null : <circle key={p.s.key} cx={xs(hovered.t)} cy={ys(clampY(v))} r={3.5} fill={p.color} stroke="var(--panel)" strokeWidth={1.5} />;
              })}
              <AxisTag x={xs(hovered.t)} y={M.top + plotH + 13} text={fmtDate(hovered.t, true)} anchor="middle" tone="var(--text-2)" />
              {(() => {
                const v = num(hovered.r[visibleSeries[0]?.s.key ?? ""]);
                return v === null ? null : <AxisTag x={x1 + 2} y={ys(clampY(v))} text={format(v)} tone={visibleSeries[0].color} />;
              })()}
            </g>
          ) : null}
        </Svg>
      ) : <div style={{ height }} />}

      {ribbon && ribbonValues.length ? (
        <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 11.5, color: "var(--text-3)" }}>
          {ribbonValues.map((v) => <span key={v} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><i style={{ width: 10, height: 10, borderRadius: 3, background: ribbonColor(v), opacity: 0.8 }} />{v}</span>)}
        </div>
      ) : null}

      {hovered && isSource && visibleSeries.length > 0 && !legendItems ? (
        <Readout x={xs(hovered.t)} y={28} width={width} w={200}>
          <ReadoutTitle>{fmtDate(hovered.t, true)}</ReadoutTitle>
          {visibleSeries.map((p) => { const v = num(hovered.r[p.s.key]); return v === null ? null : <ReadoutRow key={p.s.key} label={p.s.label} value={format(v)} swatch={p.color} />; })}
          {band && num(hovered.r[band.lo]) !== null ? <ReadoutRow label={band.label ?? "95% band"} value={`${format(num(hovered.r[band.lo]) as number)} to ${format(num(hovered.r[band.hi]) as number)}`} /> : null}
          {ribbon ? <ReadoutRow label={ribbon.label ?? "State"} value={String(hovered.r[ribbon.key] ?? "–")} /> : null}
        </Readout>
      ) : null}

      {draft && notesKey ? (
        <div className="popover" style={{ position: "absolute", left: Math.min(Math.max(0, xs(draft.t) - 120), width - 250), top: 40, width: 250, padding: 10, zIndex: 8 }}>
          <div style={{ fontSize: 11.5, color: "var(--text-3)", marginBottom: 6 }}>Note on {fmtDate(draft.t, true)}</div>
          <form onSubmit={(e) => { e.preventDefault(); if (draft.text.trim()) addNote(notesKey, { id: `${draft.t}-${Date.now()}`, t: draft.t, text: draft.text.trim() }); setDraft(null); }} style={{ display: "flex", gap: 6 }}>
            <input className="input" autoFocus value={draft.text} placeholder="What happened here?" onChange={(e) => setDraft({ ...draft, text: e.target.value })} onKeyDown={(e) => { if (e.key === "Escape") setDraft(null); }} />
            <button className="btn primary" type="submit">Add</button>
          </form>
        </div>
      ) : null}

      {notes.length && notesKey ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          {notes.map((n) => (
            <span key={n.id} className="chip accent" style={{ height: 24 }}>
              <span className="num" style={{ fontSize: 11 }}>{n.y !== undefined ? `Level ${format(n.y)}` : fmtDate(n.t)}</span>{n.text}
              <button aria-label="Delete note" onClick={() => removeNote(notesKey, n.id)} style={{ display: "grid", placeItems: "center" }}><X size={11} /></button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
