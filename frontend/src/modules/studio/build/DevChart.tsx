"use client";

import { ChevronLeft, ChevronRight, Pause, Play, SlidersHorizontal } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
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

export const SPEEDS = [1, 2, 5];

/** The Chart page's engine over the preview window: trades, ctx.plot series, the paused bar, and replay controls that drive the debugger. */
export const DevChart = memo(function DevChart({ symbol, prev, pausedAt, playing, speed, onPlay, onSpeed, onGo }: {
  symbol: string; prev: DevPreview | null; pausedAt: string | null; playing: boolean; speed: number;
  onPlay: (on: boolean) => void; onSpeed: (s: number) => void; onGo: (date: string | null, step?: 1 | -1) => void;
}) {
  const [all, setAll] = useState<Bar[]>([]);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [chart, setChart] = useState<VelaChart | null>(null);
  const handles = useRef(new Map<string, { h: { setVisible: (v: boolean) => void; moveTo: (t: "price" | { newPane: true }) => void; remove: () => void }; own: boolean }>());
  const sym = symbol.trim().toUpperCase();
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
  const rows = useMemo(() => (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym), [prev?.trades, sym]);
  const shown = useMemo(() => rows.filter((r) => filter === "all" || (filter === "win" ? Number(r.pnl) > 0 : Number(r.pnl) <= 0)), [rows, filter]);
  const currentTrade = pausedAt ? shown.findLastIndex((r) => String(r.entry_date) <= pausedAt) : -1;
  const hop = useCallback((d: 1 | -1) => {
    const next = shown[pausedAt ? (d > 0 ? shown.findIndex((r) => String(r.entry_date) > pausedAt) : shown.findLastIndex((r) => String(r.entry_date) < pausedAt)) : d > 0 ? 0 : shown.length - 1];
    if (next) onGo(String(next.entry_date));
  }, [shown, pausedAt, onGo]);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || t.closest("input, textarea, select, .monaco-editor")) return;
      if (e.key === "]" || e.key === "[") { e.preventDefault(); hop(e.key === "]" ? 1 : -1); }
    };
    window.addEventListener("keydown", on); return () => window.removeEventListener("keydown", on);
  }, [hop]);
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
  }, [barsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Plots: one native per ctx.plot name, moved to its own pane or onto price, hidden from the Plots menu.
  useEffect(() => {
    if (!chart) return;
    const names = Object.keys(plots ?? {});
    names.forEach((n, i) => {
      feed.plots[n] = (plots?.[n] ?? []).filter((p) => !p.symbol || p.symbol === sym).map((p) => ({ time: ms(p.date), value: p.value }));
      feed.colors[n] = cv(`--s${(i % 6) + 1}`, box.current ?? undefined);
      const wantOwn = own[n] ?? prev?.plot_charts?.[n] !== "main";
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
  }, [chart, plots, hidden, own, sym, prev?.plot_charts, prev?.draw]); // eslint-disable-line react-hooks/exhaustive-deps

  // Trades as markers on the lane, held spans and the paused bar as shading, the view follows the paused bar.
  useEffect(() => {
    if (!chart) return;
    const up = cv("--up", box.current ?? undefined), down = cv("--down", box.current ?? undefined), trades = (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym);
    chart.marks.defineGroup({ id: "trades", label: "Trades" });
    chart.marks.set(trades.flatMap((t, i) => {
      const long = String(t.side).toLowerCase() !== "short", win = Number(t.pnl) >= 0, ret = `${(Number(t.return) * 100).toFixed(1)}%`;
      return [
        { id: `in${i}`, time: ms(String(t.entry_date)), group: "trades", title: `${long ? "Long" : "Short"} entry`, tooltip: `${long ? "Long" : "Short"} ${String(t.entry_date)}`, glyph: { shape: "diamond" as const, color: long ? up : down, letter: long ? "B" : "S" } },
        { id: `out${i}`, time: ms(String(t.exit_date)), group: "trades", title: `Exit ${ret}`, tooltip: `Exit ${ret}`, glyph: { shape: "square" as const, color: win ? up : down, letter: "X" } },
      ];
    }));
    feed.spans = [
      ...trades.map((t) => ({ from: ms(String(t.entry_date)), to: ms(String(t.exit_date)), color: tint(Number(t.pnl) >= 0 ? up : down, "1f") })),
      ...(pausedAt ? [{ from: ms(pausedAt), to: ms(pausedAt) + 864e5, color: tint(cv("--s1", box.current ?? undefined), "55") }] : []),
    ];
    push();
    if (pausedAt) { const r = chart.getVisibleRange(), t = ms(pausedAt); if (r && (t < r.from || t > r.to)) { const w = r.to - r.from; chart.setVisibleRange({ from: t - w / 2, to: t + w / 2 }); } }
  }, [chart, prev?.trades, sym, pausedAt]); // eslint-disable-line react-hooks/exhaustive-deps


  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => onGo(null, 1), 600 / speed);
    return () => clearInterval(t);
  }, [playing, speed, onGo]);

  if (error || !bars.length) return <div className="dv-empty">{error ? `No bars: ${error}` : prev ? "Loading bars" : "Run a preview to chart it"}</div>;
  return (
    <div className="dv-chart">
      <div className="dv-chartbox" ref={box} />
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
