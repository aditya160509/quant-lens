"use client";

import { ChevronLeft, ChevronRight, Pause, Play, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { ChartOverlay, OHLCVBar } from "@/components/chart_engine/types";
import { studio } from "../api";
import type { DevPreview } from "./DevIDE";
import { excursions } from "./devStats";

type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number };
const Q360ChartCore = dynamic(() => import("@/components/chart_engine/q360_chart_core"), { ssr: false, loading: () => null });
const ms = (d: string) => Date.parse(d);

export const SPEEDS = [1, 2, 5];

/** The Chart page's engine over the preview window: trades, ctx.plot series, the paused bar, and replay controls that drive the debugger. */
export function DevChart({ symbol, prev, pausedAt, playing, speed, onPlay, onSpeed, onGo }: {
  symbol: string; prev: DevPreview | null; pausedAt: string | null; playing: boolean; speed: number;
  onPlay: (on: boolean) => void; onSpeed: (s: number) => void; onGo: (date: string | null, step?: 1 | -1) => void;
}) {
  const [all, setAll] = useState<Bar[]>([]);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [h, setH] = useState(0);
  const sym = symbol.trim().toUpperCase();
  useEffect(() => {
    if (!sym) return;
    setError(null);
    void studio<{ bars: Record<string, Bar[]> }>("GET", `/bars?symbols=${encodeURIComponent(sym)}&tf=1d`).then((d) => setAll(d.bars[sym] ?? []), (e: Error) => { setAll([]); setError(e.message); });
  }, [sym]);

  const from = prev?.bars?.[0]?.date, to = prev?.bars?.at(-1)?.date;
  const bars = useMemo(() => all.filter((b) => (!from || b.time >= from) && (!to || b.time <= to)), [all, from, to]);
  const at = pausedAt ? bars.findIndex((b) => b.time >= pausedAt) : -1;
  const [hidden, setHidden] = useState<string[]>([]);
  const [own, setOwn] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState<"all" | "win" | "loss">("all");
  const rows = useMemo(() => (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym).map((t) => {
    const e = excursions({ entry_date: String(t.entry_date), exit_date: String(t.exit_date), side: String(t.side), entry: Number(t.entry), exit: Number(t.exit), pnl: Number(t.pnl), ret: Number(t.return) }, all);
    return { entry: String(t.entry_date), exit: String(t.exit_date), side: String(t.side), ret: Number(t.return), pnl: Number(t.pnl), days: Math.round((ms(String(t.exit_date)) - ms(String(t.entry_date))) / 864e5), ...e };
  }), [prev?.trades, sym, all]);
  const shown = rows.filter((r) => filter === "all" || (filter === "win" ? r.pnl > 0 : r.pnl <= 0));
  const here = pausedAt ? shown.findIndex((r) => r.entry >= pausedAt) : -1;
  const hop = useCallback((d: 1 | -1) => {
    const next = shown[pausedAt ? (d > 0 ? shown.findIndex((r) => r.entry > pausedAt) : shown.findLastIndex((r) => r.entry < pausedAt)) : d > 0 ? 0 : shown.length - 1];
    if (next) onGo(next.entry);
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
  const overlay = useMemo<ChartOverlay>(() => ({
    bars: bars.map((b): OHLCVBar => ({ timestamp: ms(b.time), open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume })),
    trades: (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym).map((t) => ({ entry: ms(String(t.entry_date)), exit: ms(String(t.exit_date)), side: String(t.side), pnl: Number(t.pnl) })),
    lines: Object.entries(prev?.plots ?? {}).filter(([name]) => !hidden.includes(name)).map(([name, pts]) => ({ name, separate: own[name] ?? prev?.plot_charts?.[name] !== "main", points: pts.filter((p) => !p.symbol || p.symbol === sym).map((p) => ({ timestamp: ms(p.date), value: p.value })) })),
    upto: at >= 0 ? at + 1 : undefined,
    pauseAt: pausedAt ? ms(pausedAt) : null,
  }), [bars, prev?.trades, prev?.plots, prev?.plot_charts, sym, at, pausedAt, hidden, own]);

  useEffect(() => {
    const el = box.current; if (!el) return;
    const ro = new ResizeObserver(() => setH(Math.round(el.clientHeight))); ro.observe(el); setH(Math.round(el.clientHeight));
    return () => ro.disconnect();
  }, [bars.length > 0]);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => onGo(null, 1), 600 / speed);
    return () => clearInterval(t);
  }, [playing, speed, onGo]);

  if (error || !bars.length) return <div className="dv-empty">{error ? `No bars: ${error}` : prev ? "Loading bars" : "Run a preview to chart it"}</div>;
  return (
    <div className="dv-chart">
      <div className="dv-chartbox" ref={box}>{h > 80 ? <Q360ChartCore symbol={sym} timeframe="1d" mode="intraday" chartEngine="custom" height={h} overlay={overlay} /> : null}</div>
      {rows.length || Object.keys(prev?.plots ?? {}).length ? (
        <div className="dv-nav">
          <div className="dv-navbar">
            <b>Trades<span>{shown.length}</span></b>
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
          <div className="dv-navrows" role="table" aria-label="Trades">
            <div role="row" className="dv-navhead"><span>Entry</span><span>Side</span><span>Hold</span><span>Return</span><span>MAE</span><span>MFE</span></div>
            {shown.map((r, i) => (
              <button key={r.entry + r.exit} role="row" className="dv-navrow" data-on={i === here || undefined} onClick={() => onGo(r.entry)}>
                <span>{r.entry}</span><span>{r.side}</span><span data-num>{r.days}d</span><span data-num data-sign={r.ret >= 0 ? "up" : "down"}>{(r.ret * 100).toFixed(1)}%</span>
                <span data-num>{r.mae == null ? "—" : `${(r.mae * 100).toFixed(1)}%`}</span><span data-num>{r.mfe == null ? "—" : `${(r.mfe * 100).toFixed(1)}%`}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <div className="dv-replay">
        <button className="icon-btn" aria-label="Back one bar" title="Back one bar" onClick={() => onGo(null, -1)}><ChevronLeft size={15} /></button>
        <button className="icon-btn" aria-label={playing ? "Pause" : "Play"} title={playing ? "Pause" : "Play"} onClick={() => onPlay(!playing)}>{playing ? <Pause size={15} /> : <Play size={15} />}</button>
        <button className="icon-btn" aria-label="Forward one bar" title="Forward one bar" onClick={() => onGo(null, 1)}><ChevronRight size={15} /></button>
        <input type="range" min={0} max={bars.length - 1} value={Math.max(at, 0)} aria-label="Replay position" onChange={(e) => { onPlay(false); onGo(bars[Number(e.target.value)].time); }} />
        <span className="seg" role="group" aria-label="Speed">{SPEEDS.map((s) => <button key={s} type="button" aria-pressed={speed === s} onClick={() => onSpeed(s)}>{s}x</button>)}</span>
        <time>{pausedAt ?? bars.at(-1)?.time}</time>
      </div>
    </div>
  );
}
