"use client";

import { useMemo, useState } from "react";
import { Bars } from "@/charts/Bars";
import { TimeSeries } from "@/charts/TimeSeries";
import { Heatmap } from "@/charts/Heatmap";
import { Distribution } from "@/charts/Distribution";
import { XYPlot } from "@/charts/XYPlot";
import { isNum, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import { Skipped } from "./BacktestViews";

type Tile = { test: string; name: string; status: "pass" | "fail" | "skipped"; value: number | null; threshold: string; finding: string; reason: string; weight: number };
type VMeta = { grade: { grade: string; score: number | null; reason: string; cap: string | null }; tiles: Tile[]; next_test: string | null; what_would_change: string[];
  holdout: { status: string; from: string | null; looks: { actor: string; at: number; version: number | null }[]; sharpe?: number; dev_sharpe?: number; return?: number };
  luck: { sharpe: number; lottery_p95: number; effective_trials: number; raw_trials: number };
  power?: { rows: { true_sharpe: number; detected: number }[]; years: number; trades: number; false_positive: number | null; years_for_80pct: Record<string, number> };
  cpcv?: { splits: number; paths: number; median: number; share_positive: number } | null };
const vm = (r: ViewProps["result"]) => r.meta as unknown as VMeta;
const TONE = { pass: "var(--up)", fail: "var(--down)", skipped: "var(--text-4)" };

export function Tiles({ result }: ViewProps) {
  const tiles = vm(result).tiles ?? [];
  return (
    <div className="vt">
      {tiles.map((t) => (
        <div key={t.test} className="vt-tile" style={{ ["--tone" as string]: TONE[t.status] }}>
          <b>{t.name}</b>
          <span className="vt-status">{t.status}</span>
          <p>{t.status === "skipped" ? t.reason : t.finding}</p>
          {t.threshold ? <i>{t.threshold}</i> : null}
        </div>
      ))}
    </div>
  );
}

/** Scorecard with editable weights: the grade recomputes here from stored results, no new run (V-7). */
export function Scorecard({ result }: ViewProps) {
  const tiles = vm(result).tiles ?? [];
  const [w, setW] = useState<Record<string, number>>(() => Object.fromEntries(tiles.map((t) => [t.test, t.weight])));
  const g = useMemo(() => {
    const judged = tiles.filter((t) => t.status !== "skipped");
    const tot = judged.reduce((a, t) => a + (w[t.test] ?? 0), 0);
    const s = tot ? judged.filter((t) => t.status === "pass").reduce((a, t) => a + (w[t.test] ?? 0), 0) / tot : null;
    let letter = s === null ? "—" : s >= 0.85 ? "A" : s >= 0.7 ? "B" : s >= 0.55 ? "C" : s >= 0.4 ? "D" : "F";
    const cap = vm(result).grade.cap;
    if (cap && letter < cap) letter = cap;
    return { letter, s };
  }, [tiles, w, result]);
  const m = vm(result);
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div className="st-fig"><b>{g.letter}</b><span>{isNum(g.s) ? `${pct(g.s, 0)} of weight passed` : ""}{m.grade.cap ? ` · capped at ${m.grade.cap}` : ""}</span></div>
      <table className="vt-table">
        <thead><tr><th>Test</th><th>Result</th><th>Weight</th></tr></thead>
        <tbody>{tiles.map((t) => (
          <tr key={t.test}><td>{t.name}</td><td style={{ color: TONE[t.status] }}>{t.status}</td>
            <td><input className="input" type="number" min={0} step={1} aria-label={`Weight of ${t.name}`} value={w[t.test] ?? 0} onChange={(e) => setW({ ...w, [t.test]: Number(e.target.value) || 0 })} /></td></tr>
        ))}</tbody>
      </table>
      {m.next_test ? <p className="bd-find"><b>Next test</b>{m.next_test}</p> : null}
      {m.what_would_change.length ? <p className="bd-find"><b>What would change it</b>{m.what_would_change.join("; ")}</p> : null}
    </div>
  );
}

export function Stitched({ rows }: ViewProps) {
  if (rows.length < 2) return <Skipped reason="walk-forward did not run" />;
  return <TimeSeries data={rows} series={[{ key: "oos", label: "Out of sample, stitched", color: "var(--accent)", width: 2 }]} height={260} format={(v) => `${((v - 1) * 100).toFixed(0)}%`} />;
}

function Hist({ rows, mark, markLabel, format }: { rows: ViewProps["rows"]; mark: number; markLabel: string; format: (v: number) => string }) {
  if (!rows.length) return <Skipped reason="not run" />;
  return <Bars bars={rows.map((r) => ({ label: format(r.bin as number), value: r.count as number, color: (r.bin as number) >= mark ? "var(--down)" : undefined }))}
    format={(v) => String(Math.round(v))} signed={false} yLabel={`count; red at or beyond ${markLabel}`} height={220} />;
}

export function VsRandom({ rows, result }: ViewProps) {
  const t = ((result.tables.vs_random ?? [])[0] ?? {}) as Record<string, number>;
  return <Hist rows={rows} mark={t.real_mean_trade ?? Infinity} markLabel={`yours ${pct(t.real_mean_trade, 2)}`} format={(v) => pct(v, 2)} />;
}

export function Lottery({ rows, result }: ViewProps) {
  const l = vm(result).luck;
  return <Hist rows={rows} mark={l?.sharpe ?? Infinity} markLabel={`yours ${l?.sharpe?.toFixed(2)}`} format={(v) => v.toFixed(2)} />;
}

export function Holdout({ result }: ViewProps) {
  const h = vm(result).holdout;
  if (!h?.from) return <Skipped reason="no hold-out: the hold-out share is 0" />;
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {h.status === "open" ? (
        <div className="st-fig"><b>{isNum(h.sharpe) ? h.sharpe.toFixed(2) : "—"}</b><span>hold-out Sharpe vs {isNum(h.dev_sharpe) ? h.dev_sharpe.toFixed(2) : "—"} in development · return {pct(h.return, 1)}</span></div>
      ) : <div className="st-fig"><b>Sealed</b><span>from {h.from}. Turn on "Open the hold-out" in settings and run again; each look is logged.</span></div>}
      <p className="bd-find"><b>Looks</b>{h.looks.length ? h.looks.map((l) => `${l.actor} ${new Date(l.at * 1000).toLocaleDateString()}`).join("; ") : "none"}</p>
    </div>
  );
}

type Repro = { match: boolean; result_hash: string; reproduced_hash: string; data_version: string; at: number; grade: string | null };

/** Certificate: the server re-runs this validation from its stored settings and compares hashes. */
export function Certificate({ result }: ViewProps) {
  const m = result.meta as unknown as { run?: { id: string }; run_hash: string; result_hash: string; grade: { grade: string; reason: string }; strategy?: { name: string; version: number | null } };
  const [r, setR] = useState<Repro | { error: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const go = () => {
    if (!m.run?.id) return;
    setBusy(true);
    void import("../api").then(({ studio }) => studio<Repro>("POST", `/jobs/${m.run!.id}/reproduce`)).then(setR, (e) => setR({ error: e instanceof Error ? e.message : "Failed" })).finally(() => setBusy(false));
  };
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div className="st-fig"><b>{m.grade?.grade}</b><span>{m.strategy?.name}{m.strategy?.version ? ` v${m.strategy.version}` : ""} · result {m.result_hash} · run {m.run_hash}</span></div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn" disabled={busy || !m.run?.id} onClick={go}>{busy ? "Re-running on the server…" : "Reproduce on the server"}</button>
        {r && "error" in r ? <span className="bd-find error"><b>Failed</b>{r.error}</span> : null}
        {r && !("error" in r) ? <span className={`chip ${r.match ? "up" : "down"}`}>{r.match ? `reproduced ${new Date(r.at * 1000).toLocaleDateString()} ✓` : `differs: ${r.reproduced_hash}`}</span> : null}
      </div>
    </div>
  );
}

/** Walk-forward over window counts × in-sample lengths: efficiency per cell, passing cells outlined. */
export function WfMatrix({ rows }: ViewProps) {
  const ws = [...new Set(rows.map((r) => r.windows as number))], xs = [...new Set(rows.map((r) => r.in_sample_x as number))];
  if (!rows.length) return <Skipped reason="needs at least two settings to choose from" />;
  const at = (w: number, x: number) => rows.find((r) => r.windows === w && r.in_sample_x === x);
  return <Heatmap rows={ws.map(String)} cols={xs.map((x) => `${x}×`)} values={ws.map((w) => xs.map((x) => (at(w, x)?.wfe as number | null) ?? null))} format={(v) => pct(v, 0)}
    centered={false} rowTitle="Windows" colTitle="In-sample length vs out-of-sample" outline={(r, c) => at(ws[r], xs[c])?.pass === true} />;
}

/** CPCV: equity of every recombined out-of-sample path. */
export function Cpcv({ rows, result }: ViewProps) {
  const c = vm(result).cpcv;
  if (!c || rows.length < 2) return <Skipped reason="needs at least two settings and six groups of 40 bars" />;
  return (
    <>
      <TimeSeries data={rows} series={Array.from({ length: c.paths }, (_, j) => ({ key: `p${j}`, label: `Path ${j + 1}`, color: "var(--text-3)", width: 1.2 }))} height={240} legend={false} format={(v) => `${((v - 1) * 100).toFixed(0)}%`} />
      <p className="calendar-note">{c.splits} splits · {c.paths} paths · median Sharpe {c.median.toFixed(2)} · {pct(c.share_positive, 0)} of paths above zero</p>
    </>
  );
}

/** Chance this much history detects a strategy that truly has each Sharpe. */
export function Power({ result }: ViewProps) {
  const p = vm(result).power;
  if (!p) return <Skipped reason="not run" />;
  return (
    <div>
      {p.rows.map((r) => (
        <div key={r.true_sharpe} className="vd-row"><span>True Sharpe {r.true_sharpe.toFixed(2)}</span>
          <span className="vd-bar"><i style={{ width: `${r.detected * 100}%`, background: r.detected >= 0.8 ? "var(--up)" : "var(--text-3)" }} /></span><b>{pct(r.detected, 0)}</b></div>
      ))}
      <p className="calendar-note">{p.years.toFixed(1)} years, {p.trades} trades{isNum(p.false_positive) ? ` · ${pct(p.false_positive, 0)} of shuffled prices clear the same bar` : ""} · 80% power needs {p.years_for_80pct["0.5"]?.toFixed(0)} years at Sharpe 0.5</p>
    </div>
  );
}

/** PBO detail: logit of the in-sample winner's out-of-sample rank, and the ranks themselves. */
export function PboLogits({ rows }: ViewProps) {
  const v = rows.map((r) => r.logit).filter(isNum);
  if (v.length < 4) return <Skipped reason="needs at least eight settings" />;
  return <Distribution values={v} observed={0} tail="left" xLabel="Logit of the winner's out-of-sample rank; left of 0 = overfit" observedLabel="Median rank" />;
}

export function PboRanks({ rows }: ViewProps) {
  if (rows.length < 4) return <Skipped reason="needs at least eight settings" />;
  return <XYPlot points={rows.map((r) => ({ x: r.is_sharpe as number, y: r.oos_sharpe as number }))} xLabel="Winner's in-sample Sharpe" yLabel="Same setting out of sample" refY={[{ y: 0 }]} diagonal height={240}
    formatX={(v) => v.toFixed(2)} formatY={(v) => v.toFixed(2)} />;
}
