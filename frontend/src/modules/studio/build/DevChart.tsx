"use client";

import { ChevronLeft, ChevronRight, Maximize2, Minimize2, Pause, Play, Settings2, SlidersHorizontal } from "lucide-react";
import { Fragment, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Vela as VelaChart } from "@luxalgo/vela";
import { studio } from "../api";
import type { DevPreview, Draw } from "./DevIDE";

type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number };

type Pt = { time: number; value: number | null };
/** What the Vela natives read: ctx.plot series, held spans, the paused bar. Written by DevChart, read by the one chart on screen. */
const feed = { plots: {} as Record<string, Pt[]>, colors: {} as Record<string, string>, draw: null as Draw | null, own: {} as Record<string, boolean>, bg: [] as { from: number; to: number; color: string }[], spans: [] as { from: number; to: number; color: string }[], subs: new Set<() => void>() };
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
/** Vela loads in the browser only; the two native indicators that paint our plots and spans register once. */
function boot() {
  return Promise.all([import("@luxalgo/vela"), import("@luxalgo/vela/plugin")]).then(([{ Vela, createTheme }, { registerNativeIndicator, stableSeriesId }]) => {
    for (const [type, paneHint] of [["atlas.plot", "price"], ["atlas.pane", "new"]] as const) registerNativeIndicator({
      type, title: "Plot", paneHint, overlay: paneHint === "price", multiInstance: true,
      inputsSchema: () => [{ key: "name", title: "Name", type: "string", defval: "" }], defaultInputs: () => ({ name: "" }),
      create: () => {
        let ctx: import("@luxalgo/vela/plugin").NativeIndicatorContext | null = null, name = "", off = () => {};
        const run = () => {
          const pts = feed.plots[name]; if (!ctx || !pts) return;
          const by = new Map(pts.map((p) => [p.time, p.value]));
          const st = feed.draw?.styles[name], d = feed.draw, sid = (n: string) => stableSeriesId({ instanceId: "atlas.plot", kind: "line", title: n, ordinal: 0 });
          const kind = ({ step: "step", histogram: "histogram", area: "area", dots: "circles" } as const)[st?.style as "step"] ?? "line";
          const own = feed.own[name], firstOwn = Object.keys(feed.plots).find((n) => feed.own[n]) === name;
          ctx.emit({
            series: [{ id: sid(name), title: name, paneId: "", kind, points: ctx.bars().map((b) => ({ time: b.time, value: by.get(b.time) ?? null })), style: { color: st?.color ?? feed.colors[name], width: st?.width ?? 1.5, lineStyle: "solid" } }],
            fills: (d?.fills ?? []).filter((f) => f.a === name && f.b !== name && feed.own[f.b] === own).map((f, i) => ({ id: `fill${i}`, paneId: "", fromSeriesId: sid(f.a), toSeriesId: sid(f.b), color: f.color ?? tint(feed.colors[name], "26") })),
            priceLines: own && firstOwn ? (d?.hlines ?? []).filter((h) => h.chart === "own").map((h, i) => ({ id: `h${i}`, paneId: "", price: h.value, color: h.color ?? "#888888", lineStyle: "dashed" as const, width: 1, title: h.name })) : [],
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
          priceLines: (feed.draw?.hlines ?? []).filter((h) => h.chart === "main").map((h, i) => ({ id: `h${i}`, paneId: "", price: h.value, color: h.color ?? "#888888", lineStyle: "dashed" as const, width: 1, title: h.name })),
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
const STYLES = [["candles", "Candles"], ["hollow", "Hollow candles"], ["bars", "OHLC bars"], ["heikinashi", "Heikin-Ashi"], ["line", "Line"], ["linemarkers", "Line with markers"], ["stepline", "Step line"], ["area", "Area"], ["baseline", "Baseline"], ["columns", "Columns"]] as const;
const SCALES = [["price", "Linear"], ["log", "Log"], ["percent", "Percent"], ["indexed", "Indexed to 100"]] as const;
type View = { style: string; scale: string; dw: boolean; blind: boolean };
const VIEW_KEY = "studio:chart:view";
const readView = (): View => { try { return { style: "candles", scale: "price", dw: false, blind: false, ...JSON.parse(localStorage.getItem(VIEW_KEY) ?? "{}") }; } catch { return { style: "candles", scale: "price", dw: false, blind: false }; } };
const download = (name: string, href: string) => { const a = document.createElement("a"); a.href = href; a.download = name; a.click(); };

/** The Chart page's engine over the preview window: trades, ctx.plot series, the paused bar, and replay controls that drive the debugger. */
const NO_NOTES: string[] = [];
export const DevChart = memo(function DevChart({ symbol, prev, pausedAt, playing, speed, onPlay, onSpeed, onGo, onMark, onNote, notes = NO_NOTES, drawKey, max, onMax }: {
  symbol: string; prev: DevPreview | null; drawKey: string; pausedAt: string | null; playing: boolean; speed: number;
  onPlay: (on: boolean) => void; onSpeed: (s: number) => void; onGo: (date: string | null, step?: 1 | -1) => void; onMark?: (date: string) => void; onNote?: (date: string) => void; notes?: string[]; max?: boolean; onMax?: () => void;
}) {
  const [all, setAll] = useState<Bar[]>([]);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [chart, setChart] = useState<VelaChart | null>(null);
  const handles = useRef(new Map<string, { h: { setVisible: (v: boolean) => void; moveTo: (t: "price" | { newPane: true }) => void; remove: () => void }; own: boolean }>());
  // Symbol picker over the run's symbols (`,` and `.` step through them); the prop (debugger's paused symbol) wins when it changes.
  const [pick, setPick] = useState<string | null>(null);
  useEffect(() => setPick(null), [symbol]);
  const sym = (pick ?? symbol).trim().toUpperCase();
  const perSym = useMemo(() => {
    const m = new Map<string, { n: number; pnl: number; wins: number }>();
    for (const t of prev?.trades ?? []) { const k = String(t.symbol ?? symbol).toUpperCase(), r = m.get(k) ?? { n: 0, pnl: 0, wins: 0 }; r.n++; r.pnl += Number(t.pnl) || 0; if (Number(t.pnl) > 0) r.wins++; m.set(k, r); }
    return [...m].sort((a, b) => b[1].n - a[1].n);
  }, [prev?.trades, symbol]);
  const [view, setView] = useState<View>(readView);
  const setV = (p: Partial<View>) => setView((v) => { const n = { ...v, ...p }; try { localStorage.setItem(VIEW_KEY, JSON.stringify(n)); } catch { /* private mode */ } return n; });
  const [compare, setCompare] = useState<string[]>([]);
  const [cmpBars, setCmpBars] = useState<Record<string, Bar[]>>({});
  useEffect(() => {
    const want = compare.filter((c) => !cmpBars[c]); if (!want.length) return;
    void studio<{ bars: Record<string, Bar[]> }>("GET", `/bars?symbols=${encodeURIComponent(want.join(","))}&tf=1d`).then((d) => setCmpBars((x) => ({ ...x, ...d.bars })), () => undefined);
  }, [compare]); // eslint-disable-line react-hooks/exhaustive-deps
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
  const barsKey = `${sym}:${bars.length}:${bars[0]?.time}:${bars.at(-1)?.time}`;
  useEffect(() => {
    const el = box.current; if (!el || !bars.length) return;
    let dead = false, c: VelaChart | null = null;
    void (booted ??= boot()).then(({ Vela, createTheme }) => {
      if (dead) return;
      const up = cv("--up", el), down = cv("--down", el);
      c = new Vela(el, { data: bars.map((b) => ({ time: ms(b.time), open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume })), timeframe: "1d", theme: createTheme({ colors: { background: cv("--island", el), accent: cv("--s1", el) } }), upColor: up, downColor: down, height: el.clientHeight, drawings: { groups: TOOL_GROUPS } });
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
    const src = { ...plots, ...cmp };
    const names = Object.keys(src);
    names.forEach((n, i) => {
      feed.plots[n] = (src[n] ?? []).filter((p) => !p.symbol || p.symbol === sym).map((p) => ({ time: ms(p.date), value: p.value }));
      feed.colors[n] = cv(`--s${(i % 6) + 1}`, box.current ?? undefined);
      const wantOwn = n in cmp ? false : own[n] ?? prev?.plot_charts?.[n] !== "main";
      feed.own[n] = wantOwn;
      let e = handles.current.get(n);
      if (e && e.own !== wantOwn) { e.h.remove(); e = undefined; }
      if (!e) { e = { h: chart.addNativeIndicator(wantOwn ? "atlas.pane" : "atlas.plot", { inputs: { name: n } }), own: wantOwn }; handles.current.set(n, e); }
      e.h.setVisible(!hidden.includes(n));
    });
    handles.current.forEach((e, n) => { if (!names.includes(n)) { e.h.remove(); handles.current.delete(n); } });
    feed.draw = prev?.draw ?? null;
    feed.bg = (prev?.draw?.bg ?? []).map((b) => ({ from: ms(b.date), to: ms(b.date) + 864e5, color: b.color }));
    push();
  }, [chart, plots, hidden, own, sym, prev?.plot_charts, prev?.draw, compare, cmpBars]); // eslint-disable-line react-hooks/exhaustive-deps

  // Trades as markers on the lane, held spans and the paused bar as shading, the view follows the paused bar.
  useEffect(() => {
    if (!chart) return;
    const up = cv("--up", box.current ?? undefined), down = cv("--down", box.current ?? undefined), trades = (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym);
    chart.marks.defineGroup({ id: "trades", label: "Trades" });
    chart.marks.defineGroup({ id: "notes", label: "Comments" });
    chart.marks.set([...trades.flatMap((t, i) => {
      const long = String(t.side).toLowerCase() !== "short", win = Number(t.pnl) >= 0, ret = `${(Number(t.return) * 100).toFixed(1)}%`;
      return [
        { id: `in${i}`, time: ms(String(t.entry_date)), group: "trades", title: `${long ? "Long" : "Short"} entry`, tooltip: `${long ? "Long" : "Short"} ${String(t.entry_date)}`, glyph: { shape: "diamond" as const, color: long ? up : down, letter: long ? "B" : "S" } },
        { id: `out${i}`, time: ms(String(t.exit_date)), group: "trades", title: `Exit ${ret}`, tooltip: `Exit ${ret}`, glyph: { shape: "square" as const, color: win ? up : down, letter: "X" } },
      ];
    }), ...notes.map((d) => ({ id: `note${d}`, time: ms(d), group: "notes", title: "Comment", tooltip: `Comment on ${d} (Shift+click the bar to open)`, glyph: { shape: "circle" as const, color: cv("--accent", box.current ?? undefined), letter: "C" } }))]);
    feed.spans = [
      ...trades.map((t) => ({ from: ms(String(t.entry_date)), to: ms(String(t.exit_date)), color: tint(Number(t.pnl) >= 0 ? up : down, "1f") })),
      ...(pausedAt ? [{ from: ms(pausedAt), to: ms(pausedAt) + 864e5, color: tint(cv("--s1", box.current ?? undefined), "55") }] : []),
    ];
    push();
    if (pausedAt) { const r = chart.getVisibleRange(), t = ms(pausedAt); if (r && (t < r.from || t > r.to)) { const w = r.to - r.from; chart.setVisibleRange({ from: t - w / 2, to: t + w / 2 }); } }
  }, [chart, prev?.trades, sym, pausedAt, notes]); // eslint-disable-line react-hooks/exhaustive-deps
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
    chart.renderer.set({ priceStyle: hollow ? "candles" : view.style, logScale: view.scale === "log", scaleMode: view.scale === "log" ? "price" : view.scale });
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
        <details className="dv-view" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
          <summary className="btn sm ghost" aria-label="Chart settings"><Settings2 size={13} /></summary>
          <div className="dv-menu dv-chartmenu" role="menu">
            <label>Type<select className="input sm" value={view.style} onChange={(e) => setV({ style: e.target.value })}>{STYLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Scale<select className="input sm" value={view.scale} onChange={(e) => setV({ scale: e.target.value })}>{SCALES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Go to<input className="input sm" type="date" min={bars[0]?.time} max={bars.at(-1)?.time} onChange={(e) => e.target.value && onGo(e.target.value)} /></label>
            <label>Compare<input className="input sm" placeholder="QQQ, IWM" defaultValue={compare.join(", ")} onKeyDown={(e) => { if (e.key !== "Enter") return; const next = e.currentTarget.value.split(",").map((x) => x.trim().toUpperCase()).filter((x) => x && x !== sym); setCompare(next); if (next.length && view.scale === "price") setV({ scale: "percent" }); }} /></label>
            <label className="dv-check"><input type="checkbox" checked={view.dw} onChange={(e) => setV({ dw: e.target.checked })} />Data window</label>
            <label className="dv-check"><input type="checkbox" checked={view.blind} onChange={(e) => setV({ blind: e.target.checked })} />Blind replay</label>
            <hr />
            <button type="button" onClick={exportPng}>Export PNG</button>
            <button type="button" onClick={exportCsv}>Export CSV</button>
          </div>
        </details>
        {onMax ? <button type="button" className="icon-btn" aria-label={max ? "Restore chart" : "Maximise chart"} title={max ? "Restore (Esc)" : "Maximise chart (⌘⇧↵)"} onClick={onMax}>{max ? <Minimize2 size={13} /> : <Maximize2 size={13} />}</button> : null}
      </div>
      <div className="dv-chartbox" ref={box} />
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
