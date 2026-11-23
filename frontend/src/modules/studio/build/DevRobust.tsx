"use client";

import { useMemo, useState } from "react";
import { Distribution } from "@/charts/Distribution";
import type { QuickRun } from "./DevIDE";
import { bootstrapTrades, percentile, shuffleTrades } from "./devStats";

const SEED = 42;
// runs × trades per click; past this the synchronous resampling freezes the page.
const MAX_DRAWS = 2_000_000;
const pc = (v: number) => `${(v * 100).toFixed(1)}%`;

/** Monte Carlo over a finished run's trades: reorder them (timing luck) or resample them (sample luck), and see where the real result sits. */
export function DevRobust({ quick }: { quick: QuickRun | null }) {
  const [method, setMethod] = useState<"shuffle" | "bootstrap">("shuffle");
  const [runs, setRuns] = useState(1000);
  const pnl = useMemo(() => (quick?.result?.tables?.trades ?? []).map((t) => Number(t.pnl)).filter(Number.isFinite), [quick]);
  const capital = quick?.result?.charts?.equity_curve?.[0]?.strategy ?? 0;
  const n = Math.max(1, Math.min(runs, Math.floor(MAX_DRAWS / Math.max(1, pnl.length))));
  const mc = useMemo(() => (pnl.length < 5 ? null : (method === "shuffle" ? shuffleTrades : bootstrapTrades)(pnl, capital, n, SEED)), [pnl, capital, n, method]);
  if (!mc) return <p className="dv-empty">{quick ? "Needs at least 5 trades" : "Run a backtest first"}</p>;
  const retPct = percentile(mc.final, mc.orig.ret), ddPct = percentile(mc.dd, mc.orig.dd);
  const verdict = method === "shuffle"
    ? (ddPct < 5 ? "Drawdown was deeper than in most reorderings." : ddPct > 95 ? "Drawdown was shallower than in most reorderings." : "Drawdown fell within the central 90% of reorderings.")
    : (retPct > 95 ? "The return sits in the top 5% of resamples: the backtest may be in the luckiest tail." : retPct < 50 ? "The return is below the median resample: weaker than typical." : "The return is in the typical range of resamples.");
  return (
    <div className="dv-tear">
      <div className="dv-dbar">
        <span className="seg" role="group" aria-label="Method" title="Trades resampled IID at fixed capital: a diagnostic of luck, not a forecast">{(["shuffle", "bootstrap"] as const).map((m) => <button key={m} type="button" aria-pressed={method === m} onClick={() => setMethod(m)}>{m === "shuffle" ? "Reorder" : "Resample"}</button>)}</span>
        <select className="input sm" aria-label="Runs" value={runs} onChange={(e) => setRuns(Number(e.target.value))}>{[500, 1000, 5000].map((n) => <option key={n} value={n}>{n} runs</option>)}</select>
        {n < runs ? <span className="dv-count">capped at {n} runs ({pnl.length} trades)</span> : null}
        <span className="dv-count">seed {SEED}</span>
      </div>
      <p className="bd-desc">{verdict}{method === "shuffle" ? ` Final return stays at ${pc(mc.orig.ret)} when the same trade P&L is reordered.` : ""}</p>
      <div className="dv-dgrid">
        {method === "bootstrap" ? <div className="dv-plot"><b>Final return · original {pc(mc.orig.ret)} · percentile {retPct.toFixed(0)}</b><Distribution values={mc.final} observed={mc.orig.ret} xLabel="Final return" height={200} format={pc} /></div> : null}
        <div className="dv-plot"><b>Max drawdown · original {pc(mc.orig.dd)} · percentile {ddPct.toFixed(0)}</b><Distribution values={mc.dd} observed={mc.orig.dd} xLabel="Max drawdown" height={200} format={pc} /></div>
      </div>
    </div>
  );
}
