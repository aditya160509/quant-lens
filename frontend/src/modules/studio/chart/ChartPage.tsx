"use client";

import { ChevronLeft, ChevronRight, Pause, Play, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useStableDimensions } from "@/components/chart_engine/StableChartContainer";
import { getAllIndicators } from "@/components/chart_engine/IndicatorEngine/registry";
import { StudioChart, type ChartBar, type ChartIndicator, type ChartTrade } from "@/charts/studio/StudioChart";
import type { FeatureSpec } from "@/modules/research/types";
import { studio } from "../api";
import "../studio.css";

const Q360ChartCore = dynamic(() => import("@/components/chart_engine/q360_chart_core"), { ssr: false, loading: () => null });

/** The full trading chart (drawings, layouts, indicators, replay, alerts), the same one /trade uses. */
function FullChart({ symbol, onSymbol }: { symbol: string; onSymbol: (s: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const dims = useStableDimensions(ref);
  return (
    <div ref={ref} style={{ width: "100%", height: "calc(100vh - 120px)", minHeight: 520, background: "#03050a", overflow: "hidden", borderRadius: 8 }}>
      <Q360ChartCore symbol={symbol} timeframe="1d" mode="intraday" height={dims.height} width={dims.width} onSymbolChange={onSymbol} />
    </div>
  );
}

const TF = [["1d", "Day"], ["1w", "Week"], ["1mo", "Month"]] as const;
const SPEEDS = [1, 5, 20];
type Job = { result?: { tables: { trades?: (ChartTrade & { symbol: string })[] }; meta: { strategy?: { name: string } } } };

function useStored<T>(key: string, init: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(init);
  useEffect(() => { try { const raw = localStorage.getItem(key); if (raw) setV(JSON.parse(raw) as T); } catch { /* storage blocked */ } }, [key]);
  return [v, (x: T) => { setV(x); try { localStorage.setItem(key, JSON.stringify(x)); } catch { /* storage blocked */ } }];
}

/** Chart: one price source (/bars), indicators, a backtest's trades on price, a trade navigator and replay. */
export default function ChartPage({ id }: { features: FeatureSpec[]; id?: string }) {
  const router = useRouter();
  const q = useSearchParams();
  const symbol = (id ?? q?.get("symbol") ?? "SPY").toUpperCase();
  const run = q?.get("run") ?? null;
  const [draft, setDraft] = useState(symbol);
  const [tf, setTf] = useState<string>("1d");
  const [bars, setBars] = useState<ChartBar[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [indicators, setIndicators] = useStored<ChartIndicator[]>("studio:chart:indicators", [{ id: "sma", params: { period: 50 } }, { id: "sma", params: { period: 200 } }]);
  const [job, setJob] = useState<Job | null>(null);
  const [at, setAt] = useState(-1);
  const [replay, setReplay] = useState<{ upto: number; playing: boolean; speed: number } | null>(null);
  const all = useMemo(() => getAllIndicators().sort((a, b) => a.name.localeCompare(b.name)), []);

  useEffect(() => { setDraft(symbol); }, [symbol]);
  useEffect(() => {
    setError(null);
    void studio<{ bars: Record<string, ChartBar[]>; missing?: string[] }>("GET", `/bars?symbols=${encodeURIComponent(symbol)}&tf=${tf}`).then((d) => {
      const b = d.bars[symbol] ?? [];
      setBars(b);
      if (!b.length) setError(`no bars for ${symbol}`);
    }, (e) => { setBars([]); setError(e instanceof Error ? e.message : "bars unavailable"); });
  }, [symbol, tf]);
  useEffect(() => { if (run) void studio<Job>("GET", `/jobs/${run}`).then(setJob, () => setJob(null)); else setJob(null); }, [run]);

  const trades = useMemo(() => (job?.result?.tables.trades ?? []).filter((t) => t.symbol === symbol), [job, symbol]);
  const names = useMemo(() => [...new Set((job?.result?.tables.trades ?? []).map((t) => t.symbol))].sort(), [job]);

  useEffect(() => {
    if (!replay?.playing) return;
    const t = setInterval(() => setReplay((r) => (r && r.upto < bars.length ? { ...r, upto: Math.min(bars.length, r.upto + r.speed) } : r ? { ...r, playing: false } : r)), 120);
    return () => clearInterval(t);
  }, [replay?.playing, bars.length]);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).matches("input, textarea, select")) return;
      if (e.key === "ArrowRight" && trades.length) setAt((i) => Math.min(trades.length - 1, i + 1));
      if (e.key === "ArrowLeft" && trades.length) setAt((i) => Math.max(0, i - 1));
      if (e.key === "r" || e.key === "R") setReplay((r) => (r ? null : { upto: Math.min(60, bars.length), playing: true, speed: 1 }));
    };
    window.addEventListener("keydown", on); return () => window.removeEventListener("keydown", on);
  }, [trades.length, bars.length]);

  const go = (s: string) => router.push(`/studio/chart/${encodeURIComponent(s.trim().toUpperCase())}${run ? `?run=${run}` : ""}`);
  const cur = at >= 0 ? trades[at] : null;

  if (!run) return <div className="bd"><FullChart symbol={symbol} onSymbol={go} /></div>;

  return (
    <div className="bd">
      <header className="bd-head">
        <form onSubmit={(e) => { e.preventDefault(); if (draft.trim()) go(draft); }}>
          <input className="input" aria-label="Symbol" value={draft} onChange={(e) => setDraft(e.target.value)} style={{ width: 110, fontWeight: 600 }} />
        </form>
        <div className="bd-modes" role="tablist">
          {TF.map(([v, l]) => <button key={v} role="tab" aria-selected={tf === v} className={`btn sm${tf === v ? " on" : ""}`} onClick={() => setTf(v)}>{l}</button>)}
        </div>
        <select className="input" aria-label="Add indicator" value="" onChange={(e) => { const d = all.find((x) => x.id === e.target.value); if (d) setIndicators([...indicators, { id: d.id, params: { ...d.defaultParams } }]); }}>
          <option value="">Add indicator</option>
          {all.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <span style={{ flex: 1 }} />
        {job ? <span className="bd-meta">{job.result?.meta.strategy?.name ?? "Backtest"} · {trades.length} trades on {symbol}</span> : null}
        {names.length ? (
          <select className="input" aria-label="Traded names" value={names.includes(symbol) ? symbol : ""} onChange={(e) => e.target.value && go(e.target.value)}>
            <option value="">Traded names ({names.length})</option>
            {names.map((n) => <option key={n}>{n}</option>)}
          </select>
        ) : null}
        <button className="btn sm" onClick={() => setReplay(replay ? null : { upto: Math.min(60, bars.length), playing: true, speed: 1 })}>{replay ? <X size={12} /> : <Play size={12} />}{replay ? "End replay" : "Replay"}<kbd>R</kbd></button>
      </header>

      {indicators.length ? (
        <div className="ch-chips">
          {indicators.map((ind, i) => {
            const d = all.find((x) => x.id === ind.id);
            return (
              <span key={i} className="chip">
                {d?.shortName ?? ind.id}
                {Object.entries(ind.params).filter(([, v]) => typeof v === "number").map(([k, v]) => (
                  <input key={k} className="ch-param" aria-label={`${d?.shortName} ${k}`} value={String(v)} onChange={(e) => { const n = Number(e.target.value); if (Number.isFinite(n) && n > 0) setIndicators(indicators.map((x, j) => (j === i ? { ...x, params: { ...x.params, [k]: n } } : x))); }} />
                ))}
                <button aria-label={`Remove ${d?.shortName}`} onClick={() => setIndicators(indicators.filter((_, j) => j !== i))}><X size={11} /></button>
              </span>
            );
          })}
        </div>
      ) : null}

      <section className="bd-card" style={{ padding: 8 }}>
        {error ? <div className="st-skip">skipped: {error}</div> : bars.length ? <StudioChart bars={bars} indicators={indicators} trades={trades} upto={replay?.upto} focus={cur} /> : <div className="st-skip">Loading…</div>}
      </section>

      {replay ? (
        <div className="ch-bar">
          <button className="btn sm" onClick={() => setReplay({ ...replay, playing: !replay.playing })}>{replay.playing ? <Pause size={12} /> : <Play size={12} />}</button>
          <input type="range" min={2} max={bars.length} value={replay.upto} aria-label="Replay position" onChange={(e) => setReplay({ ...replay, upto: Number(e.target.value), playing: false })} style={{ flex: 1 }} />
          {SPEEDS.map((s) => <button key={s} className={`btn sm${replay.speed === s ? " on" : ""}`} onClick={() => setReplay({ ...replay, speed: s })}>{s}×</button>)}
          <span className="bd-meta">{bars[replay.upto - 1]?.time}</span>
        </div>
      ) : null}

      {trades.length ? (
        <div className="ch-bar">
          <button className="btn sm" aria-label="Previous trade" onClick={() => setAt(Math.max(0, at - 1))}><ChevronLeft size={12} /></button>
          <button className="btn sm" aria-label="Next trade" onClick={() => setAt(Math.min(trades.length - 1, at + 1))}><ChevronRight size={12} /></button>
          {cur ? (
            <span className="bd-meta">Trade {at + 1} of {trades.length}: {cur.side} {cur.entry_date} → {cur.exit_date} · <b style={{ color: cur.pnl >= 0 ? "var(--up)" : "var(--down)" }}>{cur.pnl >= 0 ? "+" : ""}{Math.round(cur.pnl).toLocaleString()}</b>{cur.exit_reason ? ` · ${cur.exit_reason}` : ""}</span>
          ) : <span className="bd-meta">{trades.length} trades · ← → to step</span>}
        </div>
      ) : null}
    </div>
  );
}
