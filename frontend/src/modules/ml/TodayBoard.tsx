"use client";

import Link from "next/link";
import { CalendarHeatmap } from "@/charts/CalendarHeatmap";
import { ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";
import { latestRun, useJob } from "@/modules/research/api";
import { featureHref, metaFor } from "@/modules/research/catalog";
import { isNum, out } from "@/modules/research/format";
import type { FeatureResult, FeatureSpec, RunRecord } from "@/modules/research/types";
import { verdictOf } from "./validateViews";

type Row = Record<string, unknown>;
const n = (v: unknown) => (isNum(v) ? v : null);
const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;

/** A tiny trend line, scaled to its own range. */
function Spark({ values, color = "var(--accent)", w = 120, h = 28 }: { values: number[]; color?: string; w?: number; h?: number }) {
  if (values.length < 2) return null;
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - lo) / span) * (h - 4)).toFixed(1)}`);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="today-spark">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={w} cy={pts[pts.length - 1].split(",")[1]} r={2.2} fill={color} />
    </svg>
  );
}

function Tile({ id, label, run, span = 4, children }: { id: string; label: string; run?: RunRecord; span?: number; children: (r: FeatureResult) => ReactNode }) {
  const job = useJob(run?.status === "completed" ? run.jobId : null);
  const result = job.data?.status === "completed" ? job.data.result : null;
  const Icon = metaFor(id).icon;
  return (
    <Link href={featureHref(id)} className="today-tile" style={{ gridColumn: `span ${span}` }}>
      <span className="today-h"><Icon size={13} strokeWidth={1.7} />{label}<ArrowUpRight size={13} className="today-go" /></span>
      {result ? children(result) : job.isLoading && run?.status === "completed" ? <span className="skel" style={{ height: 64, display: "block" }} /> : <span className="today-empty">{!run ? "Not run yet. Open to run it." : run.status === "running" || run.status === "queued" ? "Study in progress. Open to see its stages." : "This result is unavailable. Open the study and run it again."}</span>}
    </Link>
  );
}

const VTONE: Record<string, string> = { "HELD UP": "var(--up)", MIXED: "var(--warn)", FAILED: "var(--down)" };

/** The ML overview once anything has run: the latest answer from every page, each linking to its exhibits. */
export function TodayBoard({ features, runs }: { features: FeatureSpec[]; runs: RunRecord[] }) {
  const have = new Set(features.map((f) => f.id));
  const run = (id: string) => (have.has(id) ? latestRun(runs, id) : undefined);
  if (!["mlvalidate", "ml02", "ml03", "ml05", "ml06"].some((id) => run(id)?.status === "completed")) return null;
  return (
    <section className="today">
      <div className="ov-stage"><span className="n">●</span><h2>Today</h2><p>The latest answer from each page. Open any tile for the exhibits behind it.</p></div>
      <div className="today-grid">
        <Tile id="mlvalidate" label="Last validation" run={run("mlvalidate")} span={5}>
          {(r) => {
            const v = verdictOf(r);
            const checks = v?.checks ?? [];
            const order: Record<string, number> = { fail: 0, warn: 1, pass: 2 };
            return (
              <>
                <span className="verdict-stamp" style={{ ["--tone" as string]: VTONE[v?.label ?? ""] ?? "var(--text-3)" }}>{v?.label ?? "–"}</span>
                <p className="today-line">{v?.headline}</p>
                {checks.length ? <div className="val-score">{[...checks].sort((a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3)).map((c) => <i key={c.name} data-s={c.status} />)}</div> : null}
              </>
            );
          }}
        </Tile>
        <Tile id="ml02" label="Top of today's ranking" run={run("ml02")} span={4}>
          {(r) => {
            const rows = [...out(r, "current_predictions")].filter((x) => isNum(x.prediction)).sort((a, b) => (b.prediction as number) - (a.prediction as number)).slice(0, 5);
            const max = Math.max(...rows.map((x) => Math.abs(x.prediction as number)), 1e-9);
            const icKey = Object.keys(out(r, "rolling_monthly_ic_series")[0] ?? {}).find((k) => /ic/i.test(k) && isNum(out(r, "rolling_monthly_ic_series")[0][k]));
            const ic = icKey ? out(r, "rolling_monthly_ic_series").map((x) => n(x[icKey])).filter((v): v is number => v !== null) : [];
            return (
              <>
                <ol className="today-rank">
                  {rows.map((x, i) => (
                    <li key={String(x.ticker)}>
                      <span className="num">{i + 1}</span><b>{String(x.ticker)}</b>
                      <i style={{ width: `${(Math.abs(x.prediction as number) / max) * 100}%` }} />
                      <span className="num">{pct(x.prediction as number, 2)}</span>
                    </li>
                  ))}
                </ol>
                {ic.length > 1 ? <span className="today-cap" style={{ display: "flex", alignItems: "center", gap: 8 }}>Ranking IC <Spark values={ic} color={ic[ic.length - 1] >= 0 ? "var(--up)" : "var(--down)"} w={110} h={20} /></span> : null}
              </>
            );
          }}
        </Tile>
        <Tile id="ml06" label="Market state" run={run("ml06")} span={3}>
          {(r) => {
            const cur = out(r, "current_regime_probabilities")[0] as Row | undefined;
            const labels = ((r.meta as Row).state_labels ?? {}) as Record<string, string>;
            const key = cur ? `state_${String(cur.dominant_state)}` : "";
            const name = labels[key] ?? (cur ? `State ${String(cur.dominant_state)}` : "–");
            const p = n(cur?.[key]);
            const tone = name === "Stress" ? "var(--stress)" : name === "Calm" ? "var(--calm)" : "var(--accent)";
            const hist = out(r, "regime_probability_time_series").slice(-90).map((x) => n(x[key]) ?? 0);
            return (
              <>
                <span className="today-big" style={{ color: tone }}>{name}</span>
                <span className="today-cap">{p !== null ? `${pct(p, 0)} probability` : ""}{cur?.date ? ` · ${String(cur.date)}` : ""}</span>
                <Spark values={hist} color={tone} w={180} />
              </>
            );
          }}
        </Tile>
        <Tile id="ml03" label="Risk ahead" run={run("ml03")} span={6}>
          {(r) => {
            const t = out(r, "risk_today")[0] as Row | undefined;
            const stress = out(r, "regime_probability").slice(-120).map((x) => n(x.stress_probability) ?? 0);
            if (!t) return null;
            return (
              <div className="today-kv">
                <div><span>{String(t.asset)} · next month vol</span><b className="num">{isNum(t.vol_21d) ? pct(t.vol_21d, 0) : "–"}</b></div>
                <div><span>1-day 99% VaR</span><b className="num">{isNum(t.var_99) ? pct(t.var_99, 1) : "–"}</b></div>
                <div><span>Size for target risk</span><b className="num">{isNum(t.size_multiple) ? `${t.size_multiple.toFixed(2)}×` : "–"}</b></div>
                <div><span>Stress probability, 6 months</span><Spark values={stress} color="var(--stress)" w={150} /></div>
              </div>
            );
          }}
        </Tile>
        <Tile id="ml05" label="Allocation" run={run("ml05")} span={6}>
          {(r) => {
            const w = [...out(r, "hrp_weights")].filter((x) => isNum(x.weight)).sort((a, b) => (b.weight as number) - (a.weight as number));
            const s = out(r, "rebalance_summary")[0] as Row | undefined;
            return (
              <>
                <div className="today-weights" role="img" aria-label={w.map((x) => `${String(x.asset)} ${pct(x.weight as number, 0)}`).join(", ")}>
                  {w.map((x, i) => <i key={String(x.asset)} style={{ flex: x.weight as number, background: `var(--c${(i % 8) + 1})` }} title={`${String(x.asset)} ${pct(x.weight as number, 1)}`}><span>{String(x.asset)} {pct(x.weight as number, 0)}</span></i>)}
                </div>
                {s ? <span className="today-cap">{s.trade_recommended ? `Rebalance recommended: turnover ${isNum(s.turnover) ? pct(s.turnover, 0) : "–"}, cost ${isNum(s.cost_bps) ? `${s.cost_bps.toFixed(1)} bps` : "–"}` : "No trade: the expected gain does not cover the cost"}</span> : null}
              </>
            );
          }}
        </Tile>
      </div>
      <details className="ml-activity">
        <summary>Recent activity · {runs.length} saved runs</summary>
        <CalendarHeatmap hourly title="Saved run activity" signed={false} aggregate="sum" format={String} data={runs.map((r) => ({ date: r.startedAt, value: 1 }))} />
        <p className="ml-note">Local history retains up to 60 runs across the labs. Counts describe saved history, not all runs on the server.</p>
        <ol className="ml-activity-list">{runs.slice(0, 10).map((r) => <li key={r.jobId}>
          <Link href={`${featureHref(r.featureId)}?run=${encodeURIComponent(r.jobId)}`}>
            <time className="num" dateTime={new Date(r.startedAt).toISOString()}>{new Date(r.startedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time>
            <b>{metaFor(r.featureId, r.featureName).name}</b>
            <span style={{ color: r.tone === "up" ? "var(--up)" : r.tone === "down" ? "var(--down)" : r.tone === "warn" ? "var(--warn)" : "var(--text-2)" }}>{r.headline ?? r.status}</span>
          </Link>
        </li>)}</ol>
      </details>
    </section>
  );
}
