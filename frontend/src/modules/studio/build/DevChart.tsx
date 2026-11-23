"use client";

import { ChevronLeft, ChevronRight, LayoutGrid, List, Maximize2, Minimize2, Pause, Play, Settings2, SlidersHorizontal, SquareFunction } from "lucide-react";
import { Fragment, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Vela as VelaChart } from "@luxalgo/vela";
import { studio } from "../api";
import { ChartGrid } from "./ChartGrid";
import { type IndicatorInfo, IndicatorPicker } from "./IndicatorPicker";
import type { DevPreview, Draw } from "./DevIDE";

type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number };

type Pt = { time: number; value: number | null };
/** What the Vela natives read: ctx.plot series, held spans, the paused bar. Written by DevChart, read by the one chart on screen. */
const feed = { tradeLines: [] as { price: number; color: string; title: string; from: number; to: number }[], plots: {} as Record<string, Pt[]>, colors: {} as Record<string, string>, draw: null as Draw | null, own: {} as Record<string, boolean>, groups: {} as Record<string, string[]>, hidden: new Set<string>(), over: {} as Record<string, string>, bg: [] as { from: number; to: number; color: string }[], spans: [] as { from: number; to: number; color: string }[], subs: new Set<() => void>() };
const push = () => feed.subs.forEach((f) => f());
let probe: CanvasRenderingContext2D | null = null;
/** A theme token as #rrggbb (tokens resolve to lab() in the browser; Vela wants hex). Read on the chart's own element, where the tokens live. */
const cv = (n: string, el: Element = document.body) => {
  probe ??= document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const v = getComputedStyle(el).getPropertyValue(n).trim(); if (!probe || !v) return "";
  probe.clearRect(0, 0, 1, 1); probe.fillStyle = v; probe.fillRect(0, 0, 1, 1);
  const [r, g, b] = probe.getImageData(0, 0, 1, 1).data; return `#${[r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("")}`;
};
const tint = (c: string, a: string) => (/^#[0-9a-f]{6}$/i.test(c) ? c + a : c);
let booted: ReturnType<typeof boot> | null = null;
/** Five flyouts instead of a column of single tools (TradingView-style groups). */
const TOOL_GROUPS: { id: string; label: string; tools: import("@luxalgo/vela").DrawingTypeKey[] }[] = [
  { id: "lines", label: "Lines", tools: ["trendline", "ray", "extendedline", "hline", "hray", "vline", "crossline", "parallelchannel", "regressionchannel"] },
  { id: "fib", label: "Fibonacci and Gann", tools: ["fibretracement", "fibextension", "fibfan", "fibtimezones", "pitchfork", "gannfan", "gannbox"] },
  { id: "shapes", label: "Shapes", tools: ["box", "ellipse", "triangle", "polyline", "freehand", "highlighter", "arrow"] },
  { id: "text", label: "Text and marks", tools: ["text", "note", "callout", "pricelabel", "flagmark", "arrowmarkup", "arrowmarkdown"] },
  { id: "measure", label: "Measure", tools: ["datepricerange", "position", "anchoredvwap", "fixedrangevp"] },
];
const known = new Set<string>();
let groupType: ((group: string, title: string, paneHint: "price" | "new") => string) | null = null;
/** Vela loads in the browser only; the native indicators that paint our plots and spans register here. */
function boot() {
  return Promise.all([import("@luxalgo/vela"), import("@luxalgo/vela/plugin")]).then(([{ Vela, createTheme }, { registerNativeIndicator, stableSeriesId }]) => {
    // One type per plot group, registered on first use, so each legend reads the indicator's own name ("RSI(14)").
    groupType = (group, title, paneHint) => { const type = `atlas.g.${group}`; if (!known.has(type)) { known.add(type); register(type, title, paneHint); } return type; };
    const register = (type: string, title: string, paneHint: "price" | "new") => registerNativeIndicator({
      type, title, paneHint, overlay: paneHint === "price", multiInstance: true,
      inputsSchema: () => [{ key: "name", title: "Name", type: "string", defval: "" }], defaultInputs: () => ({ name: "" }),
      create: () => {
        let ctx: import("@luxalgo/vela/plugin").NativeIndicatorContext | null = null, name = "", off = () => {};
        // One instance per group: every output of one indicator (`RSI(14).rsi`, ...) shares its pane, fills and level lines, as on TradingView.
        const run = () => {
          const names = feed.groups[name]; if (!ctx || !names) return;
          const d = feed.draw, bars = ctx.bars(), sid = (n: string) => stableSeriesId({ instanceId: "atlas.plot", kind: "line", title: n, ordinal: 0 });
          const own = feed.own[names[0]!], prefix = name.split("|")[0]!, groups = Object.keys(feed.groups);
          const firstOwn = groups.find((g) => feed.own[feed.groups[g]![0]!]) === name, owned = (h: { name: string }) => groups.some((g) => h.name.startsWith(`${g.split("|")[0]} `));
          ctx.emit({
            series: names.filter((n) => !feed.hidden.has(n)).map((n) => {
              const by = new Map((feed.plots[n] ?? []).map((p) => [p.time, p.value])), st = d?.styles[n];
              const kind = ({ step: "step", histogram: "histogram", area: "area", dots: "circles" } as const)[st?.style as "step"] ?? "line";
              return { id: sid(n), title: n, paneId: "", kind, points: bars.map((b) => ({ time: b.time, value: by.get(b.time) ?? null })), style: { color: feed.over[n] ?? st?.color ?? feed.colors[n], width: st?.width ?? 1.5, lineStyle: "solid" as const } };
            }),
            fills: (d?.fills ?? []).filter((f) => names.includes(f.a) && names.includes(f.b) && f.a !== f.b && !feed.hidden.has(f.a) && !feed.hidden.has(f.b)).map((f, i) => ({ id: `fill${i}`, paneId: "", fromSeriesId: sid(f.a), toSeriesId: sid(f.b), color: f.color ?? tint(feed.colors[f.a]!, "1f") })),
            priceLines: own ? (d?.hlines ?? []).filter((h) => h.chart === "own" && (h.name.startsWith(`${prefix} `) || (firstOwn && !owned(h)))).map((h, i) => ({ id: `h${i}`, paneId: "", price: h.value, color: h.color ?? "#787b86", lineStyle: "dashed" as const, width: 1, title: h.name.startsWith(`${prefix} `) ? h.name.slice(prefix.length + 1) : h.name })) : [],
          });
        };
        return { start: (c, i) => { ctx = c; name = String(i.name ?? ""); off = (feed.subs.add(run), () => feed.subs.delete(run)); run(); }, onBars: run, onViewport: () => {}, setInputs: (i) => { name = String(i.name ?? ""); run(); }, suspend: () => {}, resume: run, stop: () => { off(); ctx = null; } };
      },
    });
    registerNativeIndicator({
      type: "atlas.spans", title: "Trades", paneHint: "price", overlay: true, legend: false,
      inputsSchema: () => [], defaultInputs: () => ({}),
      create: () => {
        let ctx: import("@luxalgo/vela/plugin").NativeIndicatorContext | null = null, off = () => {};
        const run = () => ctx?.emit({
          backgrounds: [...feed.spans, ...feed.bg].map((x, i) => ({ id: `span${i}`, paneId: "", from: x.from, to: x.to, color: x.color, overlay: true })),
          priceLines: [...(feed.draw?.hlines ?? []).filter((h) => h.chart === "main").map((h, i) => ({ id: `h${i}`, paneId: "", price: h.value, color: h.color ?? "#888888", lineStyle: "dashed" as const, width: 1, title: h.name })),],
          // The trade under the cursor: entry, exit, MAE, MFE, stop and target levels drawn across its holding span.
          lines: feed.tradeLines.map((l, i) => ({ id: `t${i}`, paneId: "", xloc: "bar_time" as const, x1: l.from, y1: l.price, x2: l.to, y2: l.price, extend: "none" as const, color: l.color, invisible: false, width: 1, style: "dashed" as const, arrowLeft: false, arrowRight: false, overlay: true })),
          labels: feed.tradeLines.map((l, i) => ({ id: `tl${i}`, paneId: "", xloc: "bar_time" as const, x: l.from, y: l.price, yloc: "price" as const, text: l.title, style: "label_left" as const, color: "#00000000", textColor: l.color, size: "small" as const, textAlign: "left" as const, fontFamily: "default" as const, noFill: true })),
        });
        return { start: (c) => { ctx = c; off = (feed.subs.add(run), () => feed.subs.delete(run)); run(); }, onBars: run, onViewport: () => {}, setInputs: () => {}, suspend: () => {}, resume: run, stop: () => { off(); ctx = null; } };
      },
    });
    return { Vela, createTheme };
  });
}
const ms = (d: string) => Date.parse(d);

export const SPEEDS = [1, 2, 5, 10, 20, 50];
const RANGES = ["1M", "3M", "6M", "1Y", "5Y", "YTD", "ALL"] as const;
const STYLES = [["candles", "Candles"], ["hollow", "Hollow candles"], ["bars", "OHLC bars"], ["heikinashi", "Heikin-Ashi"], ["line", "Line"], ["linemarkers", "Line with markers"], ["stepline", "Step line"], ["area", "Area"], ["baseline", "Baseline"], ["columns", "Columns"], ["renko", "Renko (ATR 14 box)"], ["linebreak", "Line break (3)"], ["kagi", "Kagi (ATR 14)"], ["pnf", "Point and figure (ATR 14, 3 box)"], ["range", "Range bars (ATR 14)"]] as const;
const SCALES = [["price", "Linear"], ["log", "Log"], ["percent", "Percent"], ["indexed", "Indexed to 100"]] as const;
type View = { style: string; scale: string; dw: boolean; blind: boolean; eq?: boolean; regime?: boolean };
const VIEW_KEY = "studio:chart:view";
type Ohlcv = { time: number; open: number; high: number; low: number; close: number; volume: number };
/** Price-only bar types: each new brick or line is stamped with the bar that completed it (1 ms apart when one bar makes several). */
export const DERIVED = new Set(["renko", "linebreak", "kagi", "pnf", "range"]);
export function transformBars(src: Ohlcv[], style: string): Ohlcv[] {
  if (!DERIVED.has(style) || src.length < 2) return src;
  const out: Ohlcv[] = [];
  // Box = average true range over the last 14 bars of the window, fixed for the whole chart.
  const tr = src.slice(-15).map((b, i, a) => (i ? Math.max(b.high - b.low, Math.abs(b.high - a[i - 1]!.close), Math.abs(b.low - a[i - 1]!.close)) : 0)).slice(1);
  const box = tr.reduce((p, v) => p + v, 0) / tr.length || src[0]!.close * 0.01;
  const seg = (time: number, a: number, b: number, volume: number): Ohlcv => ({ time: Math.max(time, (out.at(-1)?.time ?? -Infinity) + 1), open: a, high: Math.max(a, b), low: Math.min(a, b), close: b, volume });
  if (style === "range") {
    // A bar closes once its high-low span reaches one box.
    let cur: Ohlcv | null = null;
    for (const b of src) {
      cur = cur ? { ...cur, high: Math.max(cur.high, b.high), low: Math.min(cur.low, b.low), close: b.close, volume: cur.volume + b.volume } : { ...b };
      if (cur.high - cur.low >= box) { out.push({ ...cur, time: Math.max(b.time, (out.at(-1)?.time ?? -Infinity) + 1) }); cur = null; }
    }
    return out;
  }
  if (style === "kagi" || style === "pnf") {
    // Kagi: one segment per swing, reversing after a one-box move against the extreme. Point and figure: columns in whole boxes, reversing after three.
    const rev = style === "pnf" ? 3 * box : box, snap = (x: number) => (style === "pnf" ? Math.floor(x / box) * box : x);
    let start = snap(src[0]!.close), end = start, up = src[1]!.close >= src[0]!.close, t = src[0]!.time, vol = 0;
    for (const b of src.slice(1)) {
      vol += b.volume;
      const x = snap(b.close);
      if (up ? x > end : x < end) end = x;
      else if (up ? end - b.close >= rev : b.close - end >= rev) { out.push(seg(t, start, end, vol)); start = end; end = style === "pnf" ? x + (up ? box : 0) : b.close; up = !up; t = b.time; vol = 0; }
    }
    out.push(seg(t, start, end, vol));
    return out;
  }
  if (style === "renko") {
    let last = src[0]!.close;
    for (const b of src) {
      let k = 0;
      while (b.close >= last + box) { out.push({ time: b.time + k++, open: last, high: last + box, low: last, close: last + box, volume: k === 1 ? b.volume : 0 }); last += box; }
      while (b.close <= last - box) { out.push({ time: b.time + k++, open: last, high: last, low: last - box, close: last - box, volume: k === 1 ? b.volume : 0 }); last -= box; }
    }
    return out;
  }
  // Three-line break: a new line only when the close breaks the high or low of the last three lines.
  out.push({ ...src[0]!, open: src[0]!.open, high: Math.max(src[0]!.open, src[0]!.close), low: Math.min(src[0]!.open, src[0]!.close) });
  for (const b of src.slice(1)) {
    const prev = out.slice(-3), top = Math.max(...prev.map((x) => x.high)), bot = Math.min(...prev.map((x) => x.low)), l = out.at(-1)!;
    const up = l.close >= l.open;
    if (b.close > (up ? l.close : top)) out.push({ time: b.time, open: up ? l.close : l.open, high: b.close, low: up ? l.close : l.open, close: b.close, volume: b.volume });
    else if (b.close < (up ? bot : l.close)) out.push({ time: b.time, open: up ? l.open : l.close, high: up ? l.open : l.close, low: b.close, close: b.close, volume: b.volume });
  }
  return out;
}
const readView = (): View => { try { return { style: "candles", scale: "price", dw: false, blind: false, ...JSON.parse(localStorage.getItem(VIEW_KEY) ?? "{}") }; } catch { return { style: "candles", scale: "price", dw: false, blind: false }; } };
const download = (name: string, href: string) => { const a = document.createElement("a"); a.href = href; a.download = name; a.click(); };

/** The Chart page's engine over the preview window: trades, ctx.plot series, the paused bar, and replay controls that drive the debugger. */
const NO_NOTES: string[] = [];
export const DevChart = memo(function DevChart({ symbol, prev, pausedAt, playing, speed, onPlay, onSpeed, onGo, onMark, onNote, notes = NO_NOTES, drawKey, max, onMax, onAddIndicator }: {
  symbol: string; prev: DevPreview | null; drawKey: string; pausedAt: string | null; playing: boolean; speed: number;
  onPlay: (on: boolean) => void; onSpeed: (s: number) => void; onGo: (date: string | null, step?: 1 | -1) => void; onMark?: (date: string) => void; onNote?: (date: string) => void; notes?: string[]; max?: boolean; onMax?: () => void; onAddIndicator?: (ind: IndicatorInfo) => void;
}) {
  const [all, setAll] = useState<Bar[]>([]);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [chart, setChart] = useState<VelaChart | null>(null);
  const handles = useRef(new Map<string, { h: { setVisible: (v: boolean) => void; moveTo: (t: "price" | { newPane: true }) => void; remove: () => void }; own: boolean; sig?: string }>());
  // Symbol picker over the run's symbols (`,` and `.` step through them); the prop (debugger's paused symbol) wins when it changes.
  const [pick, setPick] = useState<string | null>(null);
  useEffect(() => setPick(null), [symbol]);
  const sym = (pick ?? symbol).trim().toUpperCase();
  const perSym = useMemo(() => {
    const m = new Map<string, { n: number; pnl: number; wins: number; dd: number; peak: number; curve: number[] }>();
    for (const t of [...(prev?.trades ?? [])].sort((a, b) => String(a.exit_date).localeCompare(String(b.exit_date)))) {
      const k = String(t.symbol ?? symbol).toUpperCase(), r = m.get(k) ?? { n: 0, pnl: 0, wins: 0, dd: 0, peak: 0, curve: [0] };
      r.n++; r.pnl += Number(t.pnl) || 0; if (Number(t.pnl) > 0) r.wins++;
      r.peak = Math.max(r.peak, r.pnl); r.dd = Math.min(r.dd, r.pnl - r.peak); r.curve.push(r.pnl); m.set(k, r);
    }
    // Counts come from the server when it sends them (exact for 4,000-name runs); the sparkline curve comes from the trades.
    for (const r of prev?.symbol_stats ?? []) { const x = m.get(r.symbol) ?? { n: 0, pnl: 0, wins: 0, dd: 0, peak: 0, curve: [0] }; m.set(r.symbol, { ...x, n: r.trades, pnl: r.pnl, wins: r.wins, dd: r.max_dd }); }
    return [...m].sort((a, b) => b[1].n - a[1].n);
  }, [prev?.trades, prev?.symbol_stats, symbol]);
  const [view, setView] = useState<View>(readView);
  const setV = (p: Partial<View>) => setView((v) => { const n = { ...v, ...p }; try { localStorage.setItem(VIEW_KEY, JSON.stringify(n)); } catch { /* private mode */ } return n; });
  const [compare, setCompare] = useState<string[]>([]);
  const [cmpBars, setCmpBars] = useState<Record<string, Bar[]>>({});
  // Spread or ratio against one other symbol, with its rolling 60-day return correlation.
  const [spread, setSpread] = useState<{ sym: string; mode: "ratio" | "diff" } | null>(null);
  const [grid, setGrid] = useState(false);
  // A run's trades pinned as a baseline layer: the next preview's entries diff against it.
  const [baseline, setBaseline] = useState<{ sym: string; dates: string[] } | null>(null);
  const TPL_KEY = "studio:chart:templates";
  const [templates, setTemplates] = useState<Record<string, View & { compare: string[] }>>(() => { try { return JSON.parse(localStorage.getItem(TPL_KEY) ?? "{}"); } catch { return {}; } });
  const saveTemplates = (t: typeof templates) => { setTemplates(t); try { localStorage.setItem(TPL_KEY, JSON.stringify(t)); } catch { /* private mode */ } };
  useEffect(() => {
    const want = [...compare, ...(spread ? [spread.sym] : [])].filter((c) => !cmpBars[c]); if (!want.length) return;
    void studio<{ bars: Record<string, Bar[]> }>("GET", `/bars?symbols=${encodeURIComponent(want.join(","))}&tf=1d`).then((d) => setCmpBars((x) => ({ ...x, ...d.bars })), () => undefined);
  }, [compare, spread?.sym]); // eslint-disable-line react-hooks/exhaustive-deps
  const [drawer, setDrawer] = useState<null | "symbols" | "months" | "regimes">(null);
  const [picker, setPicker] = useState(false);
  // Per-output colours picked in the Plots menu, kept per strategy.
  const colorKey = `studio:chart:colors:${drawKey}`;
  const [colors, setColors] = useState<Record<string, string>>({});
  useEffect(() => { try { setColors(JSON.parse(localStorage.getItem(colorKey) ?? "{}")); } catch { setColors({}); } }, [colorKey]);
  const setColor = (n: string, c: string) => setColors((x) => { const next = { ...x, [n]: c }; try { localStorage.setItem(colorKey, JSON.stringify(next)); } catch { /* blocked */ } return next; });
  // Symbol × month heatmap: summed trade return by exit month.
  const months = useMemo(() => {
    if (drawer !== "months") return null;
    const cols = [...new Set((prev?.trades ?? []).map((t) => String(t.exit_date).slice(0, 7)))].sort();
    const cell = new Map<string, number>();
    for (const t of prev?.trades ?? []) { const k = `${String(t.symbol ?? symbol).toUpperCase()}|${String(t.exit_date).slice(0, 7)}`; cell.set(k, (cell.get(k) ?? 0) + (Number(t.return) || 0)); }
    const max = Math.max(1e-9, ...[...cell.values()].map(Math.abs));
    return { cols, cell, max, rows: perSym.slice(0, 40).map(([k]) => k) };
  }, [drawer, prev?.trades, perSym, symbol]);
  const [readout, setReadout] = useState<import("@luxalgo/vela").DataWindowReadout | null>(null);
  useEffect(() => {
    if (!sym) return;
    setError(null);
    const request = new AbortController();
    void studio<{ bars: Record<string, Bar[]> }>("GET", `/bars?symbols=${encodeURIComponent(sym)}&tf=1d`, undefined, request.signal).then((d) => { if (!request.signal.aborted) setAll(d.bars[sym] ?? []); }, (e: Error) => { if (!request.signal.aborted) { setAll([]); setError(e.message); } });
    return () => request.abort();
  }, [sym]);

  const from = prev?.bars?.[0]?.date, to = prev?.bars?.at(-1)?.date;
  const bars = useMemo(() => all.filter((b) => (!from || b.time >= from) && (!to || b.time <= to)), [all, from, to]);
  const at = pausedAt ? bars.findIndex((b) => b.time >= pausedAt) : -1;
  const [hidden, setHidden] = useState<string[]>([]);
  const [own, setOwn] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState<"all" | "win" | "loss">("all");
  // Rebuild the chart when the workspace switches theme (.is-light on its root), so its colours follow.
  const [light, setLight] = useState(false);
  useEffect(() => {
    const root = box.current?.closest(".ws"); if (!root) return;
    const sync = () => setLight(root.classList.contains("is-light")); sync();
    const obs = new MutationObserver(sync); obs.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, [bars.length > 0]); // eslint-disable-line react-hooks/exhaustive-deps
  const rows = useMemo(() => (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym), [prev?.trades, sym]);
  // Equity, drawdown and exposure of this symbol's trades on the price time axis (marked to the close while open).
  const gridSyms = useMemo(() => [...new Set([sym, ...compare, ...perSym.map(([k]) => k)])].slice(0, 8), [sym, compare, perSym]);
  const gridTheme = useMemo(() => { const el = box.current ?? undefined; return { background: cv("--island", el), accent: cv("--s1", el), up: cv("--up", el), down: cv("--down", el) }; }, [grid, light]); // eslint-disable-line react-hooks/exhaustive-deps
  const eqPlots = useMemo(() => {
    if (!view.eq || !rows.length) return null;
    const eq: { date: string; symbol: null; value: number }[] = [], dd: typeof eq = [], ex: typeof eq = [];
    let peak = 0;
    for (const b of bars) {
      let v = 0, pos = 0;
      for (const t of rows) {
        const dir = String(t.side).toLowerCase() === "short" ? -1 : 1, en = String(t.entry_date), xd = String(t.exit_date);
        if (xd <= b.time) v += Number(t.pnl) || 0;
        else if (en <= b.time) { v += (b.close - Number(t.entry)) * Number(t.shares) * dir; pos += dir * Number(t.shares) * b.close; }
      }
      peak = Math.max(peak, v); eq.push({ date: b.time, symbol: null, value: v }); dd.push({ date: b.time, symbol: null, value: v - peak }); ex.push({ date: b.time, symbol: null, value: pos });
    }
    return { Equity: eq, Drawdown: dd, Exposure: ex };
  }, [view.eq, rows, bars]);
  const shown = useMemo(() => rows.filter((r) => filter === "all" || (filter === "win" ? Number(r.pnl) > 0 : Number(r.pnl) <= 0)), [rows, filter]);
  const currentTrade = pausedAt ? shown.findLastIndex((r) => String(r.entry_date) <= pausedAt) : -1;
  const hop = useCallback((d: 1 | -1) => {
    const next = shown[pausedAt ? (d > 0 ? shown.findIndex((r) => String(r.entry_date) > pausedAt) : shown.findLastIndex((r) => String(r.entry_date) < pausedAt)) : d > 0 ? 0 : shown.length - 1];
    if (next) onGo(String(next.entry_date));
  }, [shown, pausedAt, onGo]);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target instanceof Element ? e.target : null;
      if (e.metaKey || e.ctrlKey || t?.closest("input, textarea, select, .monaco-editor")) return;
      if (e.key === "]" || e.key === "[") { e.preventDefault(); hop(e.key === "]" ? 1 : -1); }
      if ((e.key === "," || e.key === ".") && perSym.length > 1) { e.preventDefault(); const i = perSym.findIndex(([k]) => k === sym); setPick(perSym[(i + (e.key === "." ? 1 : -1) + perSym.length) % perSym.length]![0]); }
    };
    window.addEventListener("keydown", on); return () => window.removeEventListener("keydown", on);
  }, [hop, perSym, sym]);
  const valueAt = (name: string) => { const pts = prev?.plots?.[name]?.filter((p) => !p.symbol || p.symbol === sym) ?? []; const hit = pausedAt ? pts.findLast((p) => p.date <= pausedAt) : pts.at(-1); return hit?.value == null ? "—" : +hit.value.toFixed(4); };
  const plots = prev?.plots;
  const derived = DERIVED.has(view.style) ? view.style : "";
  const barsKey = `${sym}:${bars.length}:${bars[0]?.time}:${bars.at(-1)?.time}:${derived}`;
  useEffect(() => {
    const el = box.current; if (!el || !bars.length) return;
    let dead = false, c: VelaChart | null = null;
    void (booted ??= boot()).then(({ Vela, createTheme }) => {
      if (dead) return;
      const up = cv("--up", el), down = cv("--down", el);
      c = new Vela(el, { data: transformBars(bars.map((b) => ({ time: ms(b.time), open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume })), derived), timeframe: "1d", theme: createTheme({ colors: { background: cv("--island", el), accent: cv("--s1", el) } }), upColor: up, downColor: down, height: el.clientHeight, drawings: { groups: TOOL_GROUPS } });
      void c.ready().then(() => { if (dead) return; c!.renderer.set("attribution", false); handles.current.clear(); c!.addNativeIndicator("atlas.spans"); setChart(c); });
    });
    let frame = 0;
    let width = 0;
    let height = 0;
    const ro = new ResizeObserver(() => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (!c || !el.clientWidth || !el.clientHeight || (width === el.clientWidth && height === el.clientHeight)) return;
        width = el.clientWidth;
        height = el.clientHeight;
        c.resize();
      });
    });
    ro.observe(el);
    return () => { dead = true; ro.disconnect(); cancelAnimationFrame(frame); setChart(null); c?.destroy(); };
  }, [barsKey, light]); // eslint-disable-line react-hooks/exhaustive-deps

  // Plots: one native per ctx.plot name, moved to its own pane or onto price, hidden from the Plots menu.
  useEffect(() => {
    if (!chart) return;
    // Compare symbols ride on the price pane as plain series; the Percent or Indexed scale rebases them with price.
    const cmp = Object.fromEntries(compare.filter((c) => cmpBars[c]).map((c) => [c, cmpBars[c]!.map((b) => ({ date: b.time, symbol: null, value: b.close }))]));
    const sp: Record<string, { date: string; symbol: null; value: number | null }[]> = {};
    if (spread && cmpBars[spread.sym]) {
      const b = new Map(cmpBars[spread.sym]!.map((x) => [x.time, x.close])), pts = bars.filter((x) => b.has(x.time));
      sp[`${sym}${spread.mode === "ratio" ? "/" : "−"}${spread.sym}`] = pts.map((x) => ({ date: x.time, symbol: null, value: spread.mode === "ratio" ? x.close / b.get(x.time)! : x.close - b.get(x.time)! }));
      const ra = pts.map((x, i) => (i ? x.close / pts[i - 1]!.close - 1 : 0)), rb = pts.map((x, i) => (i ? b.get(x.time)! / b.get(pts[i - 1]!.time)! - 1 : 0));
      sp[`Corr 60d ${spread.sym}`] = pts.map((x, i) => {
        if (i < 60) return { date: x.time, symbol: null, value: null };
        const a = ra.slice(i - 59, i + 1), c = rb.slice(i - 59, i + 1), ma = a.reduce((p, v) => p + v, 0) / 60, mc = c.reduce((p, v) => p + v, 0) / 60;
        let cov = 0, va = 0, vc = 0; for (let k = 0; k < 60; k++) { cov += (a[k]! - ma) * (c[k]! - mc); va += (a[k]! - ma) ** 2; vc += (c[k]! - mc) ** 2; }
        return { date: x.time, symbol: null, value: va && vc ? cov / Math.sqrt(va * vc) : null };
      });
    }
    const src = { ...plots, ...cmp, ...eqPlots, ...sp };
    const names = Object.keys(src);
    // Group outputs by indicator: `Name(args).key` plots share one pane or overlay; plain plots on the price chart share one group so fills between them work.
    const groups: Record<string, string[]> = {};
    names.forEach((n, i) => {
      feed.plots[n] = (src[n] ?? []).filter((p) => !p.symbol || p.symbol === sym).map((p) => ({ time: ms(p.date), value: p.value }));
      feed.colors[n] = cv(`--s${(i % 6) + 1}`, box.current ?? undefined);
      const wantOwn = n in sp ? true : n in cmp ? false : own[n] ?? prev?.plot_charts?.[n] !== "main";
      feed.own[n] = wantOwn;
      const g = `${/^(.+\))\.[^.]+$/.exec(n)?.[1] ?? (wantOwn ? n : "main")}|${wantOwn ? "own" : "main"}`;
      (groups[g] ??= []).push(n);
    });
    feed.groups = groups;
    feed.hidden = new Set(hidden);
    feed.over = colors;
    Object.entries(groups).forEach(([g, list]) => {
      const wantOwn = feed.own[list[0]!]!;
      let e = handles.current.get(g);
      const prefix = g.split("|")[0]!, title = prefix === "main" ? "Plots" : prefix, sig = list.map((n) => colors[n] ?? "").join();
      if (e && e.sig !== sig) { e.h.remove(); handles.current.delete(g); e = undefined; } // Vela keeps a running instance's styles, so a new colour gets a new instance
      if (!e) { e = { h: chart.addNativeIndicator(groupType!(g, title, wantOwn ? "new" : "price"), { inputs: { name: g } }), own: wantOwn, sig }; handles.current.set(g, e); }
      e.h.setVisible(list.some((n) => !hidden.includes(n)));
    });
    handles.current.forEach((e, g) => { if (!(g in groups)) { e.h.remove(); handles.current.delete(g); } });
    feed.draw = prev?.draw ?? null;
    feed.bg = (prev?.draw?.bg ?? []).map((b) => ({ from: ms(b.date), to: ms(b.date) + 864e5, color: b.color }));
    // Market regime ribbon: green above SPY's 200-day mean, red below; stronger in high volatility.
    if (view.regime) for (const r of prev?.regimes ?? []) if (r.regime !== "warm-up") feed.bg.push({ from: ms(r.from), to: ms(r.to), color: tint(cv(r.regime.startsWith("trend up") ? "--up" : "--down", box.current ?? undefined), r.regime.endsWith("high vol") ? "22" : "0e") });
    push();
  }, [chart, plots, hidden, own, sym, prev?.plot_charts, prev?.draw, compare, cmpBars, eqPlots, spread, view.regime, prev?.regimes, colors]); // eslint-disable-line react-hooks/exhaustive-deps

  // Trades as markers on the lane, held spans and the paused bar as shading, the view follows the paused bar.
  useEffect(() => {
    if (!chart) return;
    const up = cv("--up", box.current ?? undefined), down = cv("--down", box.current ?? undefined), trades = (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym);
    chart.marks.defineGroup({ id: "trades", label: "Trades" });
    chart.marks.defineGroup({ id: "notes", label: "Comments" });
    chart.marks.defineGroup({ id: "baseline", label: "Baseline entries" });
    const now = new Set(trades.map((t) => String(t.entry_date))), base = baseline?.sym === sym ? baseline.dates : [];
    chart.marks.set([...trades.flatMap((t, i) => {
      const long = String(t.side).toLowerCase() !== "short", win = Number(t.pnl) >= 0, ret = `${(Number(t.return) * 100).toFixed(1)}%`;
      return [
        { id: `in${i}`, time: ms(String(t.entry_date)), group: "trades", title: `${long ? "Long" : "Short"} entry`, tooltip: `${long ? "Long" : "Short"} ${String(t.entry_date)}`, glyph: { shape: "diamond" as const, color: long ? up : down, letter: long ? "B" : "S" } },
        { id: `out${i}`, time: ms(String(t.exit_date)), group: "trades", title: `Exit ${ret}`, tooltip: `Exit ${ret} · ${String(t.exit_reason ?? "")} · ${Number(t.bars) || 0} bars · MAE ${(Number(t.mae) * 100).toFixed(1)}% · MFE ${(Number(t.mfe) * 100).toFixed(1)}%`, glyph: { shape: "square" as const, color: win ? up : down, letter: "X" } },
      ];
    }), ...base.map((d) => ({ id: `base${d}`, time: ms(d), group: "baseline", title: now.has(d) ? "Baseline entry (kept)" : "Baseline entry (gone now)", tooltip: `Baseline entry ${d}${now.has(d) ? "" : " · not in this run"}`, glyph: { shape: "circle" as const, color: now.has(d) ? "#8a8f98" : down, letter: "b" } })), ...notes.map((d) => ({ id: `note${d}`, time: ms(d), group: "notes", title: "Comment", tooltip: `Comment on ${d} (Shift+click the bar to open)`, glyph: { shape: "circle" as const, color: cv("--accent", box.current ?? undefined), letter: "C" } }))]);
    feed.spans = [
      ...trades.map((t) => ({ from: ms(String(t.entry_date)), to: ms(String(t.exit_date)), color: tint(Number(t.pnl) >= 0 ? up : down, "1f") })),
      ...(pausedAt ? [{ from: ms(pausedAt), to: ms(pausedAt) + 864e5, color: tint(cv("--s1", box.current ?? undefined), "55") }] : []),
    ];
    const cur = pausedAt ? trades.find((t) => String(t.entry_date) <= pausedAt && pausedAt <= String(t.exit_date)) : undefined;
    const dir = String(cur?.side).toLowerCase() === "short" ? -1 : 1, en = Number(cur?.entry);
    const span = cur ? { from: ms(String(cur.entry_date)), to: ms(String(cur.exit_date)) } : { from: 0, to: 0 };
    feed.tradeLines = cur ? [
      { price: en, color: "#8a8f98", title: "Entry" , ...span },
      { price: Number(cur.exit), color: Number(cur.pnl) >= 0 ? up : down, title: `Exit · ${String(cur.exit_reason ?? "")}` , ...span },
      ...(Number.isFinite(Number(cur.mae)) ? [{ price: en * (1 + dir * Number(cur.mae)), color: down, title: "MAE" , ...span }] : []),
      ...(Number.isFinite(Number(cur.mfe)) ? [{ price: en * (1 + dir * Number(cur.mfe)), color: up, title: "MFE" , ...span }] : []),
      ...(cur.stop != null ? [{ price: Number(cur.stop), color: down, title: "Stop", ...span }] : []),
      ...(cur.target != null ? [{ price: Number(cur.target), color: up, title: "Target", ...span }] : []),
    ] : [];
    push();
    if (pausedAt) { const r = chart.getVisibleRange(), t = ms(pausedAt); if (r && (t < r.from || t > r.to)) { const w = r.to - r.from; chart.setVisibleRange({ from: t - w / 2, to: t + w / 2 }); } }
  }, [chart, prev?.trades, sym, pausedAt, notes, baseline]); // eslint-disable-line react-hooks/exhaustive-deps
  // Click a trade marker: the debugger pauses on that bar, so the rule values that fired show in Debug.
  useEffect(() => chart?.on("mark:click", (e) => { if (/^(in|out)\d+$/.test(e.id)) onGo(new Date(e.time).toISOString().slice(0, 10)); }), [chart, onGo]);
  // Synced cursor date: the bar under the crosshair is broadcast; the editor lights the lines that placed orders that day.
  useEffect(() => {
    if (!chart) return;
    let last = "";
    return chart.renderer.onCrosshairMove((e) => {
      const d = e.time == null ? "" : new Date(e.time).toISOString().slice(0, 10);
      if (d !== last) { last = d; window.dispatchEvent(new CustomEvent("studio:cursor-date", { detail: d })); }
    });
  }, [chart]);
  // Alt+click a bar with an order: open the line that placed it.
  const alt = useRef(false), shift = useRef(false); // Shift+click a bar: comment on it
  useEffect(() => {
    const el = box.current; if (!chart || !el) return;
    const down = (e: PointerEvent) => { alt.current = e.altKey; shift.current = e.shiftKey; };
    el.addEventListener("pointerdown", down, true);
    const off = chart.renderer.onClick((e) => { if (e.time == null) return; const d = new Date(e.time).toISOString().slice(0, 10); if (alt.current) onMark?.(d); else if (shift.current) onNote?.(d); });
    return () => { el.removeEventListener("pointerdown", down, true); off(); };
  }, [chart, onMark, onNote]);


  // Drawings belong to the strategy and symbol (W-7); tool defaults and favourites follow the user everywhere.
  // shortcut: kept in this browser's storage, not on the server; move to the strategy record when drawings need to sync across devices.
  useEffect(() => {
    if (!chart) return;
    const key = `studio:drawings:${drawKey}:${sym}`, PREFS = "studio:drawings:prefs";
    const read = (k: string) => { try { return JSON.parse(localStorage.getItem(k) ?? "null"); } catch { return null; } };
    const write = (k: string, v: unknown) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* blocked or full */ } };
    const d = chart.drawings, doc = read(key), prefs = read(PREFS);
    if (doc) d.fromJSON(doc);
    if (prefs?.defaults) d.setToolDefaults(prefs.defaults);
    if (prefs?.favorites) d.setFavorites(prefs.favorites);
    const save = () => write(key, d.toJSON());
    const savePrefs = () => write(PREFS, { defaults: d.toolDefaults(), favorites: d.favorites() });
    const offs = [
      ...(["drawing:created", "drawing:edited", "drawing:removed", "drawing:replaced", "drawing:history"] as const).map((e) => chart.on(e, save)),
      ...(["drawing:defaults", "drawing:favorites"] as const).map((e) => chart.on(e, savePrefs)),
    ];
    return () => offs.forEach((off) => off());
  }, [chart, drawKey, sym]);

  // Chart type and price scale (Vela renderer features).
  useEffect(() => {
    if (!chart) return;
    const hollow = view.style === "hollow";
    chart.renderer.set({ priceStyle: hollow || derived ? "candles" : view.style, logScale: view.scale === "log", scaleMode: view.scale === "log" ? "price" : view.scale });
    if (hollow) chart.renderer.set("upColor", cv("--island", box.current ?? undefined)); // shortcut: hollow = up candles filled with the background; Vela has no hollow style
    else chart.renderer.set("upColor", cv("--up", box.current ?? undefined));
  }, [chart, view.style, view.scale]);
  // Data window: the readout of every series at the crosshair.
  useEffect(() => {
    if (!chart || !view.dw) return setReadout(null);
    setReadout(chart.renderer.dataWindowReadout());
    return chart.renderer.onCrosshairMove(() => setReadout(chart.renderer.dataWindowReadout()));
  }, [chart, view.dw]);
  // Blind replay: bars after the paused one stay hidden.
  useEffect(() => {
    if (!chart) return;
    if (view.blind && pausedAt) void chart.replay.start({ from: ms(pausedAt) });
    else if (chart.replay.state.active) chart.replay.stop();
  }, [chart, view.blind, pausedAt]);
  const exportCsv = () => {
    const names = Object.keys(plots ?? {}), by = names.map((n) => new Map((plots?.[n] ?? []).filter((p) => !p.symbol || p.symbol === sym).map((p) => [p.date, p.value])));
    const rowsOut = bars.map((b) => [b.time, b.open, b.high, b.low, b.close, b.volume, ...by.map((m) => m.get(b.time) ?? "")].join(","));
    download(`${sym}.csv`, URL.createObjectURL(new Blob([["date,open,high,low,close,volume", ...names].join(",") + "\n" + rowsOut.join("\n")], { type: "text/csv" })));
  };
  const exportPng = () => { const url = chart?.renderer.screenshot(); if (url) download(`${sym}.png`, url); };

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => onGo(null, 1), 600 / speed);
    return () => clearInterval(t);
  }, [playing, speed, onGo]);

  if (error || !bars.length) return <div className="dv-empty">{error ? `No bars: ${error}` : prev ? "Loading bars" : "Run a preview to chart it"}</div>;
  return (
    <div className="dv-chart">
      <div className="dv-chartbar" onDoubleClick={(e) => { if (e.target === e.currentTarget) onMax?.(); }}>
        {perSym.length > 1 ? <select className="input sm" aria-label="Symbol" title="Symbol ( , and . step)" value={sym} onChange={(e) => setPick(e.target.value)}>
          {perSym.map(([k, r]) => <option key={k} value={k}>{k} · {r.n} trades · {r.pnl >= 0 ? "+" : ""}{r.pnl.toFixed(0)} · {Math.round((r.wins / r.n) * 100)}% win</option>)}
        </select> : <b>{sym}</b>}
        <select className="input sm dv-rng-sel" aria-label="Range" value="" onChange={(e) => e.target.value && chart?.setVisibleRangePreset(e.target.value as (typeof RANGES)[number])}><option value="">Range</option>{RANGES.map((r) => <option key={r} value={r}>{r === "ALL" ? "All" : r}</option>)}</select>
        <span className="seg dv-rng" role="group" aria-label="Range">{RANGES.map((r) => <button key={r} type="button" onClick={() => chart?.setVisibleRangePreset(r)}>{r === "ALL" ? "All" : r}</button>)}</span>
        <button type="button" className="icon-btn" aria-label="Grid" aria-pressed={grid} disabled={gridSyms.length < 2} title={gridSyms.length < 2 ? "Grid: add Compare symbols or run on several" : "Grid of symbols"} onClick={() => setGrid((g) => !g)}><LayoutGrid size={13} /></button>
        {onAddIndicator ? <button type="button" className="icon-btn" aria-label="Indicators" title="Indicators" aria-pressed={picker} onClick={() => setPicker((x) => !x)}><SquareFunction size={13} /></button> : null}
        {rows.length || perSym.length ? <button type="button" className="icon-btn" aria-label="Symbols, months and regimes" aria-pressed={!!drawer} title="Symbols, months and regimes" onClick={() => setDrawer((d) => (d ? null : "symbols"))}><List size={13} /></button> : null}
        <details className="dv-view" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
          <summary className="btn sm ghost" aria-label="Chart settings"><Settings2 size={13} /></summary>
          <div className="dv-menu dv-chartmenu" role="menu">
            <label>Type<select className="input sm" value={view.style} onChange={(e) => setV({ style: e.target.value })}>{STYLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Scale<select className="input sm" value={view.scale} onChange={(e) => setV({ scale: e.target.value })}>{SCALES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Go to<input className="input sm" type="date" min={bars[0]?.time} max={bars.at(-1)?.time} onChange={(e) => e.target.value && onGo(e.target.value)} /></label>
            <label>Compare<input className="input sm" placeholder="QQQ, IWM" defaultValue={compare.join(", ")} onKeyDown={(e) => { if (e.key !== "Enter") return; const next = e.currentTarget.value.split(",").map((x) => x.trim().toUpperCase()).filter((x) => x && x !== sym); setCompare(next); if (next.length && view.scale === "price") setV({ scale: "percent" }); }} /></label>
            <label>Spread<span className="dv-spread"><input className="input sm" placeholder="QQQ" defaultValue={spread?.sym ?? ""} onKeyDown={(e) => { if (e.key !== "Enter") return; const v = e.currentTarget.value.trim().toUpperCase(); setSpread(v && v !== sym ? { sym: v, mode: spread?.mode ?? "ratio" } : null); }} />
              <select className="input sm" aria-label="Spread type" value={spread?.mode ?? "ratio"} onChange={(e) => spread && setSpread({ ...spread, mode: e.target.value as "ratio" | "diff" })}><option value="ratio">A/B</option><option value="diff">A−B</option></select></span></label>
            <label>Template<select className="input sm" value="" onChange={(e) => { const t = templates[e.target.value]; if (!t) return; const { compare: c, ...v } = t; setV(v); setCompare(c); }}><option value="">Apply…</option>{Object.keys(templates).map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
            <button type="button" onClick={() => { const n = window.prompt("Template name", "")?.trim(); if (n) saveTemplates({ ...templates, [n]: { ...view, compare } }); }}>Save view as template</button>
            {Object.keys(templates).length ? <button type="button" onClick={() => { const n = window.prompt(`Delete which template? ${Object.keys(templates).join(", ")}`, "")?.trim(); if (n && templates[n]) { const { [n]: _, ...rest } = templates; saveTemplates(rest); } }}>Delete a template</button> : null}
            <button type="button" onClick={() => setBaseline(baseline ? null : { sym, dates: rows.map((t) => String(t.entry_date)) })}>{baseline ? `Clear baseline (${baseline.dates.length} entries)` : "Pin trades as baseline"}</button>
            {baseline?.sym === sym ? <p className="dv-base-diff">{(() => { const now = new Set(rows.map((t) => String(t.entry_date))), was = new Set(baseline.dates); const added = [...now].filter((d) => !was.has(d)).length, gone = [...was].filter((d) => !now.has(d)).length; return `vs baseline: ${added} new entries, ${gone} gone, ${now.size - added} same`; })()}</p> : null}
            <hr />
            <label className="dv-check"><input type="checkbox" checked={view.dw} onChange={(e) => setV({ dw: e.target.checked })} />Data window</label>
            <label className="dv-check"><input type="checkbox" checked={!!view.eq} onChange={(e) => setV({ eq: e.target.checked })} />Equity, drawdown, exposure</label>
            <label className="dv-check"><input type="checkbox" checked={!!view.regime} onChange={(e) => setV({ regime: e.target.checked })} />Regime ribbon</label>
            <label className="dv-check"><input type="checkbox" checked={view.blind} onChange={(e) => setV({ blind: e.target.checked })} />Blind replay</label>
            <hr />
            <button type="button" onClick={exportPng}>Export PNG</button>
            <button type="button" onClick={exportCsv}>Export CSV</button>
          </div>
        </details>
        {onMax ? <button type="button" className="icon-btn" aria-label={max ? "Restore chart" : "Maximise chart"} title={max ? "Restore (Esc)" : "Maximise chart (⌘⇧↵)"} onClick={onMax}>{max ? <Minimize2 size={13} /> : <Maximize2 size={13} />}</button> : null}
      </div>
      <div className="dv-chartbox" ref={box} />
      {grid && gridSyms.length > 1 ? <div className="dv-grid-over"><ChartGrid symbols={gridSyms} theme={gridTheme} /></div> : null}
      {picker && onAddIndicator ? <IndicatorPicker onClose={() => setPicker(false)} onPick={(ind) => { onAddIndicator(ind); setPicker(false); }} /> : null}
      {drawer ? <div className="dv-symdrawer" role="dialog" aria-label="Symbols">
        <header><span className="seg" role="group">{(["symbols", "months", "regimes"] as const).map((d) => <button key={d} type="button" aria-pressed={drawer === d} onClick={() => setDrawer(d)}>{d[0]!.toUpperCase() + d.slice(1)}</button>)}</span>
          <button type="button" className="icon-btn" aria-label="Close" onClick={() => setDrawer(null)}>×</button></header>
        {drawer === "symbols" ? <table className="dv-symtable"><thead><tr><th>Symbol</th><th>Trades</th><th>P&L</th><th>Win</th><th>Max DD</th><th aria-label="Curve" /></tr></thead>
          <tbody>{perSym.map(([k, r]) => { const lo = Math.min(...r.curve), hi = Math.max(...r.curve), span = hi - lo || 1; return (
            <tr key={k} aria-selected={k === sym} onClick={() => setPick(k)}><td>{k}</td><td>{r.n}</td><td className={r.pnl >= 0 ? "up" : "down"}>{r.pnl.toFixed(0)}</td><td>{Math.round((r.wins / r.n) * 100)}%</td><td className="down">{r.dd.toFixed(0)}</td>
              <td><svg viewBox="0 0 60 16" width="60" height="16" aria-hidden><polyline fill="none" stroke="currentColor" strokeWidth="1.2" points={r.curve.map((v, i) => `${(i / Math.max(1, r.curve.length - 1)) * 60},${16 - ((v - lo) / span) * 16}`).join(" ")} /></svg></td></tr>); })}</tbody></table>
        : drawer === "months" && months ? <div className="dv-heat" style={{ gridTemplateColumns: `56px repeat(${months.cols.length}, minmax(8px, 22px))` }}>
          <span />{months.cols.map((c) => <span key={c} className="dv-heat-col">{c.endsWith("-01") ? c.slice(0, 4) : ""}</span>)}
          {months.rows.map((k) => <Fragment key={k}><b>{k}</b>{months.cols.map((c) => { const v = months.cell.get(`${k}|${c}`); return <button key={c} type="button" title={`${k} ${c}: ${v == null ? "no trades" : `${(v * 100).toFixed(1)}%`}`} style={v == null ? undefined : { background: `color-mix(in oklab, var(${v >= 0 ? "--up" : "--down"}) ${Math.round(20 + 80 * Math.abs(v) / months.max)}%, transparent)` }} onClick={() => { setPick(k); const t = (prev?.trades ?? []).find((x) => String(x.symbol ?? symbol).toUpperCase() === k && String(x.exit_date).startsWith(c)); if (t) onGo(String(t.entry_date)); setDrawer(null); }} />; })}</Fragment>)}
        </div> : null}
        {drawer === "regimes" ? <table className="dv-symtable"><thead><tr><th>Regime at entry</th><th>Trades</th><th>P&L</th><th>Win</th><th>Days</th></tr></thead>
          <tbody>{(prev?.regime_pnl ?? []).map((r) => <tr key={r.regime}><td>{r.regime}</td><td>{r.trades}</td><td className={r.pnl >= 0 ? "up" : "down"}>{r.pnl.toFixed(0)}</td><td>{Math.round(r.win_rate * 100)}%</td><td>{r.days}</td></tr>)}</tbody></table> : null}
      </div> : null}
      {readout?.date ? <div className="dv-dw" aria-label="Data window">
        <b>{readout.date}</b>
        {readout.ohlc ? <dl><dt>O</dt><dd>{readout.ohlc.o}</dd><dt>H</dt><dd>{readout.ohlc.h}</dd><dt>L</dt><dd>{readout.ohlc.l}</dd><dt>C</dt><dd>{readout.ohlc.c}</dd>{readout.ohlc.vol ? <><dt>Vol</dt><dd>{readout.ohlc.vol}</dd></> : null}</dl> : null}
        {readout.groups.map((g) => <dl key={g.name}>{g.rows.map((r) => <Fragment key={r.label}><dt style={{ color: r.color }}>{r.label}</dt><dd>{r.value}</dd></Fragment>)}</dl>)}
      </div> : null}
      <div className="dv-replay">
        <button className="icon-btn" aria-label="Back one bar" title="Back one bar" onClick={() => onGo(null, -1)}><ChevronLeft size={15} /></button>
        <button className="icon-btn" aria-label={playing ? "Pause" : "Play"} title={playing ? "Pause" : "Play"} onClick={() => onPlay(!playing)}>{playing ? <Pause size={15} /> : <Play size={15} />}</button>
        <button className="icon-btn" aria-label="Forward one bar" title="Forward one bar" onClick={() => onGo(null, 1)}><ChevronRight size={15} /></button>
        <input type="range" min={0} max={bars.length - 1} value={Math.max(at, 0)} aria-label="Replay position" onChange={(e) => { onPlay(false); onGo(bars[Number(e.target.value)].time); }} />
        <span className="seg" role="group" aria-label="Speed">{SPEEDS.map((s) => <button key={s} type="button" aria-pressed={speed === s} onClick={() => onSpeed(s)}>{s}x</button>)}</span>
        <time>{pausedAt ?? bars.at(-1)?.time}</time>
        {/* One chart footer (TradingView range bar): replay on the left, trade navigator on the right. */}
        {rows.length || Object.keys(prev?.plots ?? {}).length ? <>
          <span className="dv-fsep" aria-hidden />
          <div className="dv-navbar">
            <b>Trades<span>{currentTrade >= 0 ? `${currentTrade + 1} / ` : ""}{shown.length}</span></b>
            <select className="input sm" aria-label="Filter trades" value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}><option value="all">All</option><option value="win">Winners</option><option value="loss">Losers</option></select>
            <button className="icon-btn" aria-label="Previous trade" title="Previous trade [" onClick={() => hop(-1)}><ChevronLeft size={14} /></button>
            <button className="icon-btn" aria-label="Next trade" title="Next trade ]" onClick={() => hop(1)}><ChevronRight size={14} /></button>
            {Object.keys(prev?.plots ?? {}).length ? (
              <details className="dv-view" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
                <summary className="btn sm ghost" aria-label="Plots"><SlidersHorizontal size={13} />Plots</summary>
                <div className="dv-menu dv-plots" role="menu">
                  {Object.keys(prev?.plots ?? {}).map((n) => (
                    <div key={n} role="group">
                      <label><input type="checkbox" checked={!hidden.includes(n)} onChange={() => setHidden((h) => (h.includes(n) ? h.filter((x) => x !== n) : [...h, n]))} />{n}</label>
                      <output>{valueAt(n)}</output>
                      <input type="color" aria-label={`${n} colour`} value={colors[n] ?? prev?.draw?.styles[n]?.color ?? feed.colors[n] ?? "#888888"} onChange={(e) => setColor(n, e.target.value)} />
                      <button type="button" className="btn sm ghost" aria-pressed={own[n] ?? prev?.plot_charts?.[n] !== "main"} onClick={() => setOwn((o) => ({ ...o, [n]: !(o[n] ?? prev?.plot_charts?.[n] !== "main") }))}>Own pane</button>
                    </div>
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        </> : null}
      </div>
    </div>
  );
});
