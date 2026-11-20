"use client";

import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { StudioChart, type ChartBar, type ChartLine, type ChartTrade } from "@/charts/studio/StudioChart";
import { studio } from "../api";
import type { DevPreview } from "./DevIDE";

export const SPEEDS = [1, 2, 5];

/** The Chart page's engine over the preview window: trades, ctx.plot series, the paused bar, and replay controls that drive the debugger. */
export function DevChart({ symbol, prev, pausedAt, playing, speed, onPlay, onSpeed, onGo }: {
  symbol: string; prev: DevPreview | null; pausedAt: string | null; playing: boolean; speed: number;
  onPlay: (on: boolean) => void; onSpeed: (s: number) => void; onGo: (date: string | null, step?: 1 | -1) => void;
}) {
  const [all, setAll] = useState<ChartBar[]>([]);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [h, setH] = useState(0);
  const sym = symbol.trim().toUpperCase();
  useEffect(() => {
    if (!sym) return;
    setError(null);
    void studio<{ bars: Record<string, ChartBar[]> }>("GET", `/bars?symbols=${encodeURIComponent(sym)}&tf=1d`).then((d) => setAll(d.bars[sym] ?? []), (e: Error) => { setAll([]); setError(e.message); });
  }, [sym]);

  const from = prev?.bars?.[0]?.date, to = prev?.bars?.at(-1)?.date;
  const bars = useMemo(() => all.filter((b) => (!from || b.time >= from) && (!to || b.time <= to)), [all, from, to]);
  const trades = useMemo(() => (prev?.trades ?? []).filter((t) => !t.symbol || t.symbol === sym) as unknown as ChartTrade[], [prev?.trades, sym]);
  const lines = useMemo<ChartLine[]>(() => Object.entries(prev?.plots ?? {}).map(([name, pts]) => ({ name, separate: prev?.plot_charts?.[name] !== "main", points: pts.filter((p) => !p.symbol || p.symbol === sym) })), [prev?.plots, prev?.plot_charts, sym]);
  const at = pausedAt ? bars.findIndex((b) => b.time >= pausedAt) : -1;

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
      <div className="dv-chartbox" ref={box}>{h > 80 ? <StudioChart bars={bars} indicators={[]} trades={trades} lines={lines} upto={at >= 0 ? at + 1 : undefined} pauseAt={pausedAt} height={h} /> : null}</div>
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
