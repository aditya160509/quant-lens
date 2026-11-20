"use client";

import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { ChartOverlay, OHLCVBar } from "@/components/chart_engine/types";
import { studio } from "../api";
import type { DevPreview } from "./DevIDE";

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
  const overlay = useMemo<ChartOverlay>(() => ({
    bars: bars.map((b): OHLCVBar => ({ timestamp: ms(b.time), open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume })),
    trades: (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym).map((t) => ({ entry: ms(String(t.entry_date)), exit: ms(String(t.exit_date)), side: String(t.side), pnl: Number(t.pnl) })),
    lines: Object.entries(prev?.plots ?? {}).map(([name, pts]) => ({ name, separate: prev?.plot_charts?.[name] !== "main", points: pts.filter((p) => !p.symbol || p.symbol === sym).map((p) => ({ timestamp: ms(p.date), value: p.value })) })),
    upto: at >= 0 ? at + 1 : undefined,
    pauseAt: pausedAt ? ms(pausedAt) : null,
  }), [bars, prev?.trades, prev?.plots, prev?.plot_charts, sym, at, pausedAt]);

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
