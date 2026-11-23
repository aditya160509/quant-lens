"use client";

import { Columns2, Rows2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { studio } from "../api";

type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number };
const LAYOUTS = [["2v", 2], ["2h", 2], ["4", 4], ["8", 8]] as const;

/** Several symbols side by side on Vela's own workspace: synced crosshair and time, maximise a cell, its own replay. */
export function ChartGrid({ symbols, theme }: { symbols: string[]; theme: { background: string; accent: string; up: string; down: string } }) {
  const box = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<string>(symbols.length > 4 ? "8" : symbols.length > 2 ? "4" : "2v");
  const [sync, setSync] = useState({ crosshair: true, viewport: true });
  const [bars, setBars] = useState<Record<string, Bar[]> | null>(null);
  const cells = symbols.slice(0, LAYOUTS.find(([l]) => l === layout)?.[1] ?? 4);
  const key = cells.join(",");
  useEffect(() => {
    const request = new AbortController();
    void studio<{ bars: Record<string, Bar[]> }>("GET", `/bars?symbols=${encodeURIComponent(key)}&tf=1d`, undefined, request.signal).then((d) => setBars(d.bars), () => undefined);
    return () => request.abort();
  }, [key]);
  useEffect(() => {
    const el = box.current; if (!el || !bars) return;
    let dead = false, ws: { destroy: () => void } | null = null;
    void Promise.all([import("@luxalgo/vela/workspace"), import("@luxalgo/vela")]).then(([{ VelaWorkspace }, { createTheme }]) => {
      if (dead) return;
      ws = new VelaWorkspace(el, {
        layout, timeframe: "1d", theme: createTheme({ colors: { background: theme.background, accent: theme.accent } }), upColor: theme.up, downColor: theme.down,
        cells: Object.fromEntries(cells.map((s, i) => [`c${i}`, { symbol: s, timeframe: "1d", data: (bars[s] ?? []).map((b) => ({ time: Date.parse(b.time), open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume })) }])),
        sync: { crosshair: sync.crosshair, viewport: sync.viewport },
      });
    });
    return () => { dead = true; ws?.destroy(); };
  }, [bars, layout, sync, theme]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="dv-grid">
      <div className="dv-grid-bar">
        <span className="seg" role="group" aria-label="Layout">{LAYOUTS.map(([l, n]) => <button key={l} type="button" aria-label={l === "2v" ? "Two side by side" : l === "2h" ? "Two stacked" : `${l} charts`} aria-pressed={layout === l} disabled={n > symbols.length && l !== "2v"} onClick={() => setLayout(l)}>{l === "2v" ? <Columns2 size={14} /> : l === "2h" ? <Rows2 size={14} /> : l}</button>)}</span>
        <label className="dv-check"><input type="checkbox" checked={sync.crosshair} onChange={(e) => setSync((x) => ({ ...x, crosshair: e.target.checked }))} />Sync crosshair</label>
        <label className="dv-check"><input type="checkbox" checked={sync.viewport} onChange={(e) => setSync((x) => ({ ...x, viewport: e.target.checked }))} />Sync time</label>
      </div>
      <div className="dv-grid-ws" ref={box}>{bars ? null : <p className="dv-empty">Loading bars</p>}</div>
    </div>
  );
}
