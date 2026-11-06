"use client";

import { forwardRef, useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type SVGProps } from "react";
import { create } from "zustand";
import type { ScaleLinear } from "d3";
import { EyeOff } from "lucide-react";
import "./charts.css";

export type Margin = { top: number; right: number; bottom: number; left: number };

/** Categorical series colours, theme-aware through CSS variables. */
export const SERIES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"];

/** Width of an element, tracked with ResizeObserver. */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(Math.floor(el.getBoundingClientRect().width));
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

/** Snap a coordinate to the pixel grid so 1px strokes render crisp. */
export const crisp = (v: number) => Math.round(v) + 0.5;

type SvgProps = Omit<SVGProps<SVGSVGElement>, "ref" | "width" | "height"> & { width: number; height: number; label: string; children: ReactNode };

export const Svg = forwardRef<SVGSVGElement, SvgProps>(function Svg({ width, height, label, children, style, onPointerMove, ...rest }, ref) {
  // Coalesce pointer-move bursts to one handler call per animation frame.
  const latest = useRef<React.PointerEvent<SVGSVGElement> | null>(null);
  const frame = useRef(0);
  const handler = useRef(onPointerMove);
  useEffect(() => { handler.current = onPointerMove; });
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  const move = onPointerMove ? (e: React.PointerEvent<SVGSVGElement>) => {
    latest.current = Object.create(e, { currentTarget: { value: e.currentTarget } });
    if (frame.current) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = 0;
      if (latest.current) handler.current?.(latest.current);
      latest.current = null;
    });
  } : undefined;
  const leave = rest.onPointerLeave;
  return (
    <svg ref={ref} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}
      style={{ display: "block", overflow: "visible", fontFamily: "var(--mono)", touchAction: "pan-y", userSelect: "none", ...style }} {...rest} onPointerMove={move}
      onPointerLeave={leave ? (e) => { cancelAnimationFrame(frame.current); frame.current = 0; latest.current = null; leave(e); } : undefined}>
      {children}
    </svg>
  );
});

type Linear = ScaleLinear<number, number>;

export function GridY({ scale, x1, x2, ticks = 5, zero = true }: { scale: Linear; x1: number; x2: number; ticks?: number; zero?: boolean }) {
  return (
    <g>
      {scale.ticks(ticks).map((t) => (
        <line key={t} x1={x1} x2={x2} y1={crisp(scale(t))} y2={crisp(scale(t))} stroke={zero && t === 0 ? "var(--line-3)" : "var(--grid)"} />
      ))}
    </g>
  );
}

export function GridX({ scale, y1, y2, ticks = 6 }: { scale: Linear; y1: number; y2: number; ticks?: number }) {
  return (
    <g>
      {scale.ticks(ticks).map((t) => <line key={t} x1={crisp(scale(t))} x2={crisp(scale(t))} y1={y1} y2={y2} stroke="var(--grid)" />)}
    </g>
  );
}

/** Y axis labels; with `spine`, also the axis line and short outward ticks, as in a printed figure. */
export function AxisY({ scale, x, ticks = 5, format = fmtTick, side = "left", spine }: { scale: Linear; x: number; ticks?: number; format?: (v: number) => string; side?: "left" | "right"; spine?: boolean }) {
  const [a, b] = scale.range();
  const d = side === "left" ? -1 : 1;
  return (
    <g>
      {spine ? <line x1={crisp(x)} x2={crisp(x)} y1={a} y2={b} stroke="var(--line-3)" /> : null}
      {spine ? scale.ticks(ticks).map((t) => <line key={`t${t}`} x1={x} x2={x + 4 * d} y1={crisp(scale(t))} y2={crisp(scale(t))} stroke="var(--line-3)" />) : null}
      {scale.ticks(ticks).map((t) => (
        <text key={t} x={side === "left" ? x - (spine ? 9 : 8) : x + (spine ? 9 : 8)} y={scale(t)} dy="0.32em" textAnchor={side === "left" ? "end" : "start"} fontSize={10.5} fill="var(--text-3)">
          {format(t)}
        </text>
      ))}
    </g>
  );
}

export function AxisX({ scale, y, ticks = 6, format = fmtTick, spine }: { scale: Linear; y: number; ticks?: number; format?: (v: number) => string; spine?: boolean }) {
  const [a, b] = scale.range();
  return (
    <g>
      {spine ? <line x1={a} x2={b} y1={crisp(y)} y2={crisp(y)} stroke="var(--line-3)" /> : null}
      {spine ? scale.ticks(ticks).map((t) => <line key={`t${t}`} x1={crisp(scale(t))} x2={crisp(scale(t))} y1={y} y2={y + 4} stroke="var(--line-3)" />) : null}
      {scale.ticks(ticks).map((t) => (
        <text key={t} x={scale(t)} y={y + 15} textAnchor="middle" fontSize={10.5} fill="var(--text-3)">{format(t)}</text>
      ))}
    </g>
  );
}

export function AxisLabel({ x, y, children, anchor = "start", rotate = false }: { x: number; y: number; children: ReactNode; anchor?: "start" | "middle" | "end"; rotate?: boolean }) {
  return (
    <text x={x} y={y} fontSize={11} fill="var(--text-3)" textAnchor={anchor} style={{ fontFamily: "var(--font)" }} transform={rotate ? `rotate(-90 ${x} ${y})` : undefined}>
      {children}
    </text>
  );
}

/** Rounded value tag drawn on an axis at the crosshair, like a terminal price tag. */
export function AxisTag({ x, y, text, anchor = "start", tone = "var(--text)" }: { x: number; y: number; text: string; anchor?: "start" | "end" | "middle"; tone?: string }) {
  const w = text.length * 6.6 + 12;
  const left = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
  return (
    <g pointerEvents="none">
      <rect x={left} y={y - 9} width={w} height={18} rx={4} fill={tone} />
      <text x={left + w / 2} y={y} dy="0.33em" textAnchor="middle" fontSize={10.5} fill="var(--bg)" fontWeight={500}>{text}</text>
    </g>
  );
}

export function fmtTick(v: number): string {
  const a = Math.abs(v);
  if (a === 0) return "0";
  if (a >= 1e6 || a < 1e-3) return v.toExponential(0).replace("e+", "e");
  if (a >= 1000) return `${(v / 1000).toFixed(a >= 1e4 ? 0 : 1)}k`;
  return String(Number(v.toPrecision(3)));
}

/** Floating readout positioned inside a relatively positioned chart container. */
export function Readout({ x, y, width, children, w = 230 }: { x: number; y: number; width: number; children: ReactNode; w?: number }) {
  const fitted = Math.min(w, Math.max(0, width));
  const left = x + 18 + fitted > width ? x - 18 - fitted : x + 18;
  return (
    <div role="status" style={{
      position: "absolute", left: Math.max(0, left), top: y, width: fitted, maxWidth: "100%", pointerEvents: "none", zIndex: 6,
      padding: "9px 11px", borderRadius: 9, background: "color-mix(in oklch, var(--raise) 92%, transparent)", backdropFilter: "blur(8px)",
      boxShadow: "var(--shadow)", fontSize: 12, lineHeight: 1.6,
    }}>
      {children}
    </div>
  );
}

export function ReadoutRow({ label, value, tone, swatch }: { label: ReactNode; value: ReactNode; tone?: string; swatch?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
      <span style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-3)", whiteSpace: "nowrap", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
        {swatch ? <i style={{ width: 8, height: 8, borderRadius: 2, background: swatch, flex: "none" }} /> : null}
        {label}
      </span>
      <span className="num" style={{ color: tone ?? "var(--text)", textAlign: "right", whiteSpace: "nowrap" }}>{value}</span>
    </div>
  );
}

export function ReadoutTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 4, fontWeight: 550, color: "var(--text)" }}>
      <span>{children}</span>{aside ? <span className="num" style={{ fontWeight: 400 }}>{aside}</span> : null}
    </div>
  );
}

/** Robust axis domain: ignores extreme outliers so one degenerate estimate cannot flatten the chart. */
export function robustExtent(values: number[], pad = 0.08, q = 0.02): [number, number] {
  const v = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!v.length) return [-1, 1];
  const at = (p: number) => v[Math.min(v.length - 1, Math.max(0, Math.round(p * (v.length - 1))))];
  let lo = v.length > 20 ? at(q) : v[0];
  let hi = v.length > 20 ? at(1 - q) : v[v.length - 1];
  const iqr = at(0.75) - at(0.25);
  if (iqr > 0) {
    lo = Math.max(lo, at(0.25) - 6 * iqr);
    hi = Math.min(hi, at(0.75) + 6 * iqr);
  }
  if (lo === hi) { lo -= Math.abs(lo) * 0.5 || 1; hi += Math.abs(hi) * 0.5 || 1; }
  const span = hi - lo;
  return [lo - span * pad, hi + span * pad];
}

export function usePointerIndex(count: number, x0: number, x1: number) {
  const [index, setIndex] = useState<number | null>(null);
  const onMove = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - r.left;
    if (mx < x0 - 4 || mx > x1 + 4 || count === 0) { setIndex(null); return; }
    const i = Math.floor(((mx - x0) / Math.max(1, x1 - x0)) * count);
    setIndex(Math.max(0, Math.min(count - 1, i)));
  }, [count, x0, x1]);
  return { index, setIndex, onMove, onLeave: () => setIndex(null) };
}

/** Shared crosshair time: hovering any time-series chart highlights the same date in every other one. */
export const useCrosshair = create<{ t: number | null; source: string | null; set: (t: number | null, source: string | null) => void }>()((set) => ({
  t: null,
  source: null,
  set: (t, source) => set({ t, source }),
}));

export const parseDate = (v: unknown): number | null => {
  if (typeof v !== "string" && typeof v !== "number") return null;
  const t = typeof v === "number" ? v : Date.parse(v.length === 10 ? `${v}T00:00:00Z` : v);
  return Number.isFinite(t) ? t : null;
};

export const fmtDate = (t: number, long = false) =>
  new Date(t).toLocaleDateString("en-US", long ? { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" } : { year: "numeric", month: "short", timeZone: "UTC" });

/** Closest index in a sorted numeric array. */
export function nearest(sorted: number[], v: number): number {
  let lo = 0;
  let hi = sorted.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] < v) lo = mid; else hi = mid;
  }
  return Math.abs(sorted[lo] - v) <= Math.abs(sorted[hi] - v) ? lo : hi;
}

/** Diverging fill for a value in [-1, 1]: down colour below zero, up colour above, panel at zero. */
export const diverging = (s: number, neg = "var(--down)", pos = "var(--up)") =>
  `color-mix(in oklch, ${s >= 0 ? pos : neg} ${Math.round(Math.min(1, Math.abs(s)) * 78)}%, var(--panel-2))`;

export function Legend({ items, onToggle, isolate = false }: { isolate?: boolean; items: { label: string; color: string; value?: ReactNode; dash?: boolean; id?: string; hidden?: boolean }[]; onToggle?: (id: string, additive: boolean) => void }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 12, color: "var(--text-2)" }}>
      {items.map((it) => {
        const inner = (
          <>
            {it.hidden ? <EyeOff size={12} aria-hidden /> : <svg width={14} height={8} aria-hidden><line x1={0} x2={14} y1={4} y2={4} stroke={it.color} strokeWidth={2} strokeDasharray={it.dash ? "3 2" : undefined} strokeLinecap="round" /></svg>}
            {it.label}
            {it.value !== undefined && !it.hidden ? <span className="num" style={{ color: "var(--text)" }}>{it.value}</span> : null}
          </>
        );
        const style = { display: "inline-flex", alignItems: "center", gap: 6, whiteSpace: "nowrap", opacity: it.hidden ? 0.45 : 1, transition: "opacity 120ms" } as const;
        return onToggle ? (
          <button key={it.label} type="button" className="chart-legend-item" aria-pressed={!it.hidden} title={isolate ? "Click to isolate; Shift-click to add or remove" : it.hidden ? "Show series" : "Hide series"}
            onClick={(e) => onToggle(it.id ?? it.label, e.shiftKey)} style={style}>{inner}</button>
        ) : <span key={it.label} style={style}>{inner}</span>;
      })}
    </div>
  );
}
