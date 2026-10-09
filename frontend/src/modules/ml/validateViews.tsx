"use client";

import { BadgeCheck, Check, Copy, History, Minus, ShieldAlert, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Bars } from "@/charts/Bars";
import { Heatmap } from "@/charts/Heatmap";
import { post, useRuns } from "@/modules/research/api";
import { isNum, label } from "@/modules/research/format";
import { lab } from "@/modules/research/lab";
import { useStudies } from "@/modules/research/store";
import { Empty } from "@/modules/research/outputs/tables";
import type { ViewProps } from "@/modules/research/outputs/types";
import type { FeatureResult, Row } from "@/modules/research/types";

/* ---------------------------------------------------------------- helpers */

type Dist = { n?: number; mean?: number; p5?: number; p50?: number; p95?: number; share_positive?: number };
type Check = { name: string; status: "pass" | "warn" | "fail" | string; detail?: string };
export type Verdict = { label?: string; headline?: string; checks?: Check[]; fails?: number; warnings?: number; strategy_sharpe?: number; best_control?: string; leakage_badge?: string; rule?: string };

export const verdictOf = (r: FeatureResult) => (r as FeatureResult & { verdict?: Verdict }).verdict;
const section = (r: FeatureResult, k: string) => (r.sections?.[k] ?? {}) as Row;
const n = (v: unknown) => (isNum(v) ? v : null);
const f2 = (v: unknown) => (isNum(v) ? v.toFixed(2) : "–");
const pct = (v: unknown, d = 1) => (isNum(v) ? `${(v * 100).toFixed(d)}%` : "–");
const years = (v: unknown) => (!isNum(v) ? "–" : v < 0.1 ? "<0.1 yr" : `${v.toPrecision(2)} yr`);
const NAMES: Record<string, string> = {
  cash: "Cash", buy_and_hold: "Buy and hold", equal_weight: "Equal weight", constant_exposure: "Constant exposure", shuffled_signal: "Shuffled signal", model_control: "Simple model",
  beats_best_control: "Beats the best control", shuffled_signal_p: "Beats shuffled signals", deflated_sharpe: "Deflated Sharpe", min_backtest_length: "Enough history", cpcv: "Purged cross-validation",
  plateau: "Parameter plateau", leakage: "No look-ahead", transfer: "Transfers out of sample", monte_carlo: "Bootstrap", stability: "Seed stability", pbo: "Overfitting probability",
  unfiltered: "As uploaded", meta_filter: "Meta-label filter", meta_sized: "Meta-label sizing",
  other_tickers_same_period: "Other tickers, same dates", later_period_same_tickers: "Later dates, same tickers", other_tickers_later_period: "Other tickers, later dates", later_period: "Later dates",
};
/** Autopsy causes, phrased as the way a backtest can lie. */
const CAUSES: Record<string, string> = {
  regime_dependence: "One period carries it", single_asset_luck: "Edge does not transfer", cost_sensitivity: "Trading costs eat it", trial_count: "Too many trials",
  parameter_cliff: "Fragile settings", seed_luck: "Lucky seed", leakage: "Look-ahead leakage",
};
const nameOf = (k: unknown) => NAMES[String(k)] ?? label(String(k));
/** API detail strings carry snake_case ids; show them as words. */
const humanise = (t: unknown) => String(t ?? "").replace(/\b[a-z]+(?:_[a-z0-9]+)+\b/g, (m) => nameOf(m).toLowerCase()).replace(/^badge pass$/, "no look-ahead found");

/** A section the input cannot support says why and what would unlock it, instead of an empty chart. */
function Unavailable({ s }: { s: Row }) {
  return (
    <div className="val-unavail">
      <Minus size={14} aria-hidden />
      <div><b>Not computed for this input</b><span>{String(s.reason ?? "This test needs a different kind of upload.")}</span></div>
    </div>
  );
}
const unavailable = (s: Row) => s.status === "unavailable";

function StatusIcon({ status }: { status: string }) {
  const Icon = status === "pass" ? Check : status === "fail" ? X : Minus;
  return <i className="val-ico" data-s={status} aria-label={status}><Icon size={11} strokeWidth={2.6} /></i>;
}

/** Where a value sits against a bootstrap or permutation distribution: 5–95% band, median tick, marker for the strategy. */
function RangeStrip({ d, mark, markLabel, format = f2, domain }: { d: Dist; mark?: number | null; markLabel?: string; format?: (v: number) => string; domain?: [number, number] }) {
  if (!isNum(d.p5) || !isNum(d.p95)) return null;
  const vals = [d.p5, d.p95, d.p50 ?? d.p5, mark ?? d.p5, 0];
  const [lo0, hi0] = domain ?? [Math.min(...vals), Math.max(...vals)];
  const pad = (hi0 - lo0) * 0.08 || 1;
  const lo = lo0 - pad, hi = hi0 + pad;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="val-strip" role="img" aria-label={`5th to 95th percentile ${format(d.p5)} to ${format(d.p95)}${isNum(mark) ? `; ${markLabel ?? "strategy"} ${format(mark)}` : ""}`}>
      <div className="val-strip-track">
        {lo < 0 && hi > 0 ? <span className="val-strip-zero" style={{ left: x(0) }} /> : null}
        <span className="val-strip-band" style={{ left: x(d.p5), width: `calc(${x(d.p95)} - ${x(d.p5)})` }} />
        {isNum(d.p50) ? <span className="val-strip-med" style={{ left: x(d.p50) }} /> : null}
        {isNum(mark) ? <span className="val-strip-mark" data-edge={(mark - lo) / (hi - lo) > 0.8 ? "r" : (mark - lo) / (hi - lo) < 0.2 ? "l" : undefined} style={{ left: x(mark) }}><em>{markLabel ?? "Strategy"} {format(mark)}</em></span> : null}
      </div>
      <div className="val-strip-axis num"><span style={{ left: x(d.p5) }}>{format(d.p5)}</span>{isNum(d.p50) ? <span style={{ left: x(d.p50) }}>{format(d.p50)}</span> : null}<span style={{ left: x(d.p95) }}>{format(d.p95)}</span></div>
    </div>
  );
}

function Kpis({ items }: { items: [string, ReactNode, string?, string?][] }) {
  return (
    <div className="ml-stats">
      {items.map(([l, v, tone, title]) => <div key={l} title={title}><span>{l}</span><b className="num" style={tone ? { color: tone } : undefined}>{v}</b></div>)}
    </div>
  );
}

/* ---------------------------------------------------------------- verdict hero */

/** The one-page answer: verdict, the autopsy sentence, and every check with its evidence. */
export function ValVerdict({ result }: ViewProps) {
  const v = verdictOf(result);
  if (!v?.label) return <Empty />;
  const checks = v.checks ?? [];
  const order = { fail: 0, warn: 1, pass: 2 } as Record<string, number>;
  const sorted = [...checks].sort((a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3));
  const controls = section(result, "controls");
  return (
    <div className="val-hero">
      <Kpis items={[
        ["Edge over best control", isNum(controls.edge_vs_best) ? `${controls.edge_vs_best > 0 ? "+" : ""}${f2(controls.edge_vs_best)}` : "–", isNum(controls.edge_vs_best) ? (controls.edge_vs_best > 0 ? "var(--up)" : "var(--down)") : undefined],
        ["Checks", `${checks.filter((c) => c.status === "pass").length} pass · ${v.warnings ?? 0} warn · ${v.fails ?? 0} fail`],
      ]} />
      <div className="val-score" role="img" aria-label={`${checks.length} checks, in order: ${sorted.map((c) => c.status).join(", ")}`}>
        {sorted.map((c) => <i key={c.name} data-s={c.status} title={`${nameOf(c.name)}: ${c.status}`} />)}
      </div>
      <ul className="val-checks">
        {sorted.map((c) => (
          <li key={c.name} data-s={c.status}><StatusIcon status={c.status} /><b>{nameOf(c.name)}</b><span>{humanise(c.detail)}</span></li>
        ))}
      </ul>
      {v.rule ? <p className="ml-note"><b>Rule.</b> {v.rule}</p> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- autopsy */

type Cause = { cause: string; severity: number; evidence?: string; sharpe_by_cost_bps?: Record<string, number>; breakeven_bps?: number };

/** Every candidate reason the backtest could be lying, ranked by how much of the result it explains. */
export function ValAutopsy({ result }: ViewProps) {
  const a = section(result, "autopsy");
  const causes = ((a.ranked_causes as Cause[]) ?? []).slice().sort((x, y) => y.severity - x.severity);
  if (!causes.length) return <Empty />;
  return (
    <div className="val-autopsy">
      <ol>
        {causes.map((c, i) => {
          const tone = c.severity >= 0.66 ? "var(--down)" : c.severity >= 0.33 ? "var(--warn)" : "var(--text-4)";
          return (
            <li key={c.cause} data-quiet={c.severity < 0.05 || undefined}>
              <span className="num val-rank">{i + 1}</span>
              <div className="val-cause">
                <div className="val-cause-h"><b>{CAUSES[c.cause] ?? nameOf(c.cause)}</b><span className="num" style={{ color: tone }}>{Math.round(c.severity * 100)}</span></div>
                <div className="val-meter" aria-hidden><i style={{ width: `${Math.max(2, c.severity * 100)}%`, background: tone }} /></div>
                {c.evidence ? <span className="val-evidence">{c.evidence}</span> : null}
              </div>
            </li>
          );
        })}
      </ol>
      <p className="ml-note">Severity runs 0–100: how much of the headline Sharpe the cause can explain. Each comes from a standard test shown further down this page.</p>
    </div>
  );
}

/** Sharpe as trading costs rise, with the run's own cost and the breakeven marked. */
export function ValCostCurve({ result }: ViewProps) {
  const cost = ((section(result, "autopsy").ranked_causes as Cause[]) ?? []).find((c) => c.cause === "cost_sensitivity");
  const pts = Object.entries(cost?.sharpe_by_cost_bps ?? {}).map(([k, v]) => ({ bps: Number(k), sharpe: v })).filter((p) => isNum(p.sharpe)).sort((a, b) => a.bps - b.bps);
  if (pts.length < 2) return <Empty />;
  const used = n((result.meta?.config as Row | undefined)?.cost_bps) ?? 5;
  return (
    <div>
      <Kpis items={[["Breakeven cost", isNum(cost?.breakeven_bps) ? `${cost.breakeven_bps.toFixed(1)} bps` : "–", undefined, "Cost per unit of turnover at which net Sharpe reaches zero"], ["Sharpe before costs", f2(pts[0].sharpe)], [`Sharpe at ${used} bps`, f2(pts.find((p) => p.bps === used)?.sharpe)]]} />
      <Bars bars={pts.map((p) => ({ label: `${p.bps} bps`, value: p.sharpe }))} height={200} yLabel="Annualised Sharpe" format={(v) => v.toFixed(1)} />
    </div>
  );
}

/* ---------------------------------------------------------------- controls */

/** The strategy against every simple alternative; the verdict uses the best one, not zero. */
export function ValControls({ result }: ViewProps) {
  const c = section(result, "controls");
  const rows = ((c.controls as Row[]) ?? []).filter((r) => isNum(r.sharpe));
  const strat = n(c.strategy_sharpe);
  if (!rows.length || strat === null) return <Empty />;
  const shuffledP95 = n((c.shuffled as Row | undefined)?.control_sharpe_p95);
  const bars = [
    { label: "Strategy", value: strat, color: "var(--accent)" },
    ...rows.filter((r) => r.name !== "shuffled_signal").map((r) => ({ label: nameOf(r.name), value: r.sharpe as number, muted: true, detail: [["Total return", pct(r.total_return)], ...(r.note ? [["Note", String(r.note)]] : [])] as [string, string][] })),
    ...(shuffledP95 !== null ? [{ label: "Shuffled (95th pct)", value: shuffledP95, muted: true }] : []),
  ];
  const missing = [...((c.unavailable as Row[]) ?? []), ...((c.controls as Row[]) ?? []).filter((r) => !isNum(r.sharpe))];
  return (
    <div>
      <Bars bars={bars} signed={false} height={230} yLabel="Annualised Sharpe" format={(v) => v.toFixed(2)} refLines={isNum(c.best_control_sharpe) ? [{ y: c.best_control_sharpe, label: "Best control", color: "var(--text-3)" }] : []} />
      {missing.length ? <p className="ml-note">{missing.map((m) => <span key={String(m.name)}><b>{nameOf(m.name)}:</b> {String(m.reason ?? m.note ?? "not computed")}. </span>)}</p> : null}
    </div>
  );
}

/** Where the real signal lands among the same trades with the signal randomly reassigned. */
export function ValShuffle({ result }: ViewProps) {
  const c = section(result, "controls");
  const s = (c.shuffled ?? {}) as Row;
  if (unavailable(s) || !s.sharpe_distribution) return unavailable(s) ? <Unavailable s={s} /> : <Empty />;
  const p = n(s.p_value);
  return (
    <div>
      <Kpis items={[["p-value", p === null ? "–" : p < 0.01 ? "<0.01" : p.toFixed(3), p !== null ? (p < 0.05 ? "var(--up)" : "var(--down)") : undefined, "Share of shuffles that matched or beat the real signal"], ["Permutations", String(s.permutations ?? "–")], ["Shuffled median", f2((s.sharpe_distribution as Dist).p50)]]} />
      <RangeStrip d={s.sharpe_distribution as Dist} mark={n(c.strategy_sharpe)} />
      <p className="ml-note">The band holds 90% of Sharpes from {String(s.permutations ?? 100)} random reassignments of your signal across the same names and dates. A real edge sits clearly outside it.</p>
    </div>
  );
}

/* ---------------------------------------------------------------- robustness */

export function ValCpcv({ result }: ViewProps) {
  const s = section(result, "cpcv");
  const d = (s.distribution ?? {}) as Dist;
  if (!isNum(d.p5)) return <Empty />;
  const split = ((s.split_sharpes as unknown[]) ?? []).filter(isNum);
  return (
    <div>
      <Kpis items={[["Median Sharpe", f2(d.p50)], ["Positive", pct(d.share_positive, 0), isNum(d.share_positive) ? (d.share_positive >= 0.8 ? "var(--up)" : d.share_positive >= 0.5 ? "var(--warn)" : "var(--down)") : undefined], ["Splits", String(s.splits ?? split.length)]]} />
      <RangeStrip d={d} mark={null} />
      {split.length ? <div className="val-dots" aria-label="Sharpe per split">{split.map((v, i) => <i key={i} title={`Split ${i + 1}: ${v.toFixed(2)}`} style={{ background: v > 0 ? "var(--up)" : "var(--down)" }} />)}</div> : null}
      <p className="ml-note">{String(s.note ?? `${s.n_groups} date groups, ${s.k_test_groups} held out per split.`)}</p>
    </div>
  );
}

export function ValMonteCarlo({ result }: ViewProps) {
  const s = section(result, "monte_carlo");
  const sh = (s.sharpe ?? {}) as Dist, dd = (s.max_drawdown ?? {}) as Dist;
  if (!isNum(sh.p5)) return <Empty />;
  const pLoss = n(s.prob_sharpe_not_positive);
  return (
    <div>
      <Kpis items={[["Chance Sharpe ≤ 0", pct(pLoss, 0), pLoss !== null ? (pLoss < 0.05 ? "var(--up)" : pLoss < 0.25 ? "var(--warn)" : "var(--down)") : undefined], ["Bad-case drawdown", pct(dd.p5), "var(--down)", "5th percentile of the bootstrap maximum drawdown"], ["Draws", String(s.draws ?? "–")]]} />
      <div className="val-sub">Sharpe</div>
      <RangeStrip d={sh} mark={n(section(result, "controls").strategy_sharpe)} markLabel="Actual" />
      <div className="val-sub">Maximum drawdown</div>
      <RangeStrip d={dd} mark={n(s.observed_max_drawdown)} markLabel="Actual" format={(v) => pct(v, 0)} />
      <p className="ml-note">Moving-block bootstrap ({String(s.block_length ?? "–")}-period blocks) keeps volatility clustering while reshuffling history.</p>
    </div>
  );
}

export function ValTransfer({ result }: ViewProps) {
  const s = section(result, "transfer");
  if (unavailable(s)) return <Unavailable s={s} />;
  const tests = ((s.tests as Row[]) ?? []).filter((t) => isNum(t.sharpe));
  if (!tests.length) return <Empty />;
  return (
    <div>
      <Bars bars={[{ label: "In-sample", value: n(s.reference_sharpe) ?? 0, muted: true }, ...tests.map((t) => ({ label: nameOf(t.name), value: t.sharpe as number }))]} height={200} yLabel="Annualised Sharpe" format={(v) => v.toFixed(2)} />
      <p className="ml-note"><b>{String(s.scope ?? "")}.</b> {String(s.rule ?? "")}.</p>
    </div>
  );
}

export function ValPlateau({ result }: ViewProps) {
  const s = section(result, "plateau");
  if (unavailable(s)) return <Unavailable s={s} />;
  const grid = s.sharpe_grid as (number | null)[][] | undefined;
  const axes = (s.axes ?? {}) as Record<string, number[]>;
  const [rk, ck] = Object.keys(axes);
  if (!grid?.length || !rk || !ck) return <Empty />;
  const base = (s.baseline ?? {}) as Row;
  const rows = axes[rk], cols = axes[ck];
  const isPlateau = s.label === "plateau";
  return (
    <div>
      <Kpis items={[["Shape", isPlateau ? "Plateau" : "Cliff", isPlateau ? "var(--up)" : "var(--down)"], ["Grid median", f2(s.grid_median)], ["Worst neighbour", f2(s.worst_neighbour)]]} />
      <Heatmap rows={rows.map((v) => (v < 1 ? pct(v, 0) : String(v)))} cols={cols.map(String)} values={grid} centered format={(v) => v.toFixed(2)}
        rowTitle={label(rk)} colTitle={label(ck)} outline={(i, j) => rows[i] === base.fraction && cols[j] === base.delay} />
      <p className="ml-note">Outlined cell: your settings. {String(s.rule ?? "")}. A plateau means nearby settings work too; a cliff means the result depends on one lucky choice.</p>
    </div>
  );
}

export function ValStability({ result }: ViewProps) {
  const s = section(result, "stability");
  if (unavailable(s)) return <Unavailable s={s} />;
  const seeds = ((s.seed_sharpes ?? s.sharpes) as unknown[] | undefined)?.filter(isNum) ?? [];
  return (
    <div>
      <Kpis items={[["Best vs median", isNum(s.best_over_median) ? `${s.best_over_median.toFixed(2)}×` : "–", s.flag ? "var(--down)" : "var(--up)"], ["Seeds", String(s.n_seeds ?? seeds.length)], ["Spread", f2(s.std ?? s.spread)]]} />
      {seeds.length ? <Bars bars={seeds.map((v, i) => ({ label: `Seed ${i + 1}`, value: v }))} height={170} yLabel="Sharpe" format={(v) => v.toFixed(2)} /> : null}
      <p className="ml-note">Flagged when the best seed beats the median by more than 25%: a result that needs a lucky seed is not a result.</p>
    </div>
  );
}

/** Deflated Sharpe, probability of backtest overfitting and minimum backtest length together. */
export function ValOverfit({ result }: ViewProps) {
  const d = section(result, "deflated_sharpe"), p = section(result, "pbo"), m = section(result, "min_backtest_length");
  const dsr = n(d.dsr), pbo = n(p.pbo);
  return (
    <div>
      <Kpis items={[
        ["Deflated Sharpe", dsr === null ? "–" : dsr.toFixed(2), dsr === null ? undefined : dsr >= 0.95 ? "var(--up)" : dsr >= 0.5 ? "var(--warn)" : "var(--down)", "Probability the true Sharpe is above zero after the number of trials"],
        ["Trials counted", String(d.trials ?? "–")],
        ["Overfitting probability", unavailable(p) ? "n/a" : pbo === null ? "–" : pct(pbo, 0), pbo === null ? undefined : pbo < 0.2 ? "var(--up)" : pbo < 0.5 ? "var(--warn)" : "var(--down)"],
        ["History needed", years(m.min_years_required), m.sufficient === false ? "var(--down)" : undefined, `Observed ${years(m.observed_years)}`],
      ]} />
      {unavailable(p) ? <p className="ml-note"><b>Overfitting probability:</b> {String(p.reason)}.</p> : null}
      <p className="ml-note">Deflated Sharpe corrects for how many strategies were tried before this one. Upload the trial matrix of everything you tested for the honest count.</p>
    </div>
  );
}

export function ValLeakage({ result }: ViewProps) {
  const s = section(result, "leakage");
  const checks = (s.checks as Row[]) ?? [];
  return (
    <div>
      <span className="val-badge" data-s={s.badge}>{s.badge === "pass" ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}{s.badge === "pass" ? "No look-ahead found" : "Look-ahead detected"}</span>
      <ul className="val-checks" style={{ marginTop: 10 }}>
        {checks.map((c) => (
          <li key={String(c.name)} data-s={c.pass ? "pass" : "fail"}><StatusIcon status={c.pass ? "pass" : "fail"} /><b>{label(String(c.name).replace(/_/g, " "))}</b>
            <span>{c.note ? String(c.note) : c.t ? `Data after ${String(c.t)} perturbed; results up to that date ${c.unchanged ? "unchanged" : "changed"}.` : isNum(c.mean_rank_ic) ? `Mean rank IC ${c.mean_rank_ic.toFixed(3)} (limit ${String(c.threshold)}).` : ""}</span></li>
        ))}
      </ul>
    </div>
  );
}

/* ---------------------------------------------------------------- improve my strategy */

export function ValImprove({ result }: ViewProps) {
  const s = section(result, "improve");
  if (unavailable(s)) return <Unavailable s={s} />;
  const rows = (s.rows as Row[]) ?? [];
  if (!rows.length) return <Empty />;
  const base = rows.find((r) => r.variant === "unfiltered");
  return (
    <div>
      <p className="val-sentence" style={{ fontSize: 14 }}>
        {s.improved ? `${nameOf(s.best_variant)} lifts Sharpe by ${f2(s.sharpe_delta)}.` : `Neither filter nor sizing beats your strategy as uploaded (best change ${isNum(s.sharpe_delta) && s.sharpe_delta > 0 ? "+" : ""}${f2(s.sharpe_delta)}): keep it simple.`}
      </p>
      <div className="val-variants">
        {rows.map((r) => {
          const d = isNum(r.sharpe) && isNum(base?.sharpe) && r !== base ? r.sharpe - (base.sharpe as number) : null;
          return (
            <div key={String(r.variant)} data-best={r.variant === s.best_variant && s.improved ? true : undefined}>
              <span>{nameOf(r.variant)}</span>
              <b className="num">{f2(r.sharpe)}{d !== null ? <em style={{ color: d > 0 ? "var(--up)" : d < 0 ? "var(--down)" : "var(--text-4)" }}> {d >= 0 ? "+" : ""}{d.toFixed(2)}</em> : null}</b>
              <dl><div><dt>Total return</dt><dd className="num">{pct(r.total_return, 0)}</dd></div><div><dt>Turnover</dt><dd className="num">{pct(r.avg_turnover, 0)}</dd></div><div><dt>Positions kept</dt><dd className="num">{pct(r.positions_kept, 0)}</dd></div></dl>
            </div>
          );
        })}
      </div>
      <p className="ml-note">{String(s.note ?? "")} Meta-label features: {((s.features as string[]) ?? []).map((x) => label(x)).join(", ")}.</p>
    </div>
  );
}

/* ---------------------------------------------------------------- receipt */

function Hash({ v }: { v: unknown }) {
  const [done, setDone] = useState(false);
  const s = String(v ?? "");
  if (!s) return <>–</>;
  return (
    <button type="button" className="val-hash num" title="Copy full hash" onClick={() => { void navigator.clipboard?.writeText(s); setDone(true); setTimeout(() => setDone(false), 1200); }}>
      {s.slice(0, 12)}…{done ? <Check size={11} /> : <Copy size={11} />}
    </button>
  );
}

/** What was tested, on which dates, with which settings, and the hashes that prove it. */
/** Freeze this run as a public, read-only page, or put its exact settings back in the form. */
function ReceiptActions({ scope, featureId }: { scope: string; featureId: string }) {
  const jobId = scope.split(":")[1];
  const payload = useRuns((s) => s.runs.find((r) => r.jobId === jobId)?.payload);
  const setForm = useStudies((s) => s.setForm);
  const [state, setState] = useState<{ busy?: boolean; id?: string; error?: string }>({});
  if (!jobId || jobId === "draft") return null;
  const publish = async () => {
    setState({ busy: true });
    try { setState({ id: (await post<{ id: string }>("/verified", { job_id: jobId })).id }); } catch (e) { setState({ error: e instanceof Error ? e.message : "Could not publish" }); }
  };
  return (
    <div className="val-actions">
      {state.id ? (
        <Link className="btn" href={`${lab().root}/verified/${state.id}`}><BadgeCheck size={13} />Open verified page</Link>
      ) : (
        <button type="button" className="btn primary" onClick={() => void publish()} disabled={state.busy}><BadgeCheck size={13} />{state.busy ? "Publishing…" : "Publish verified page"}</button>
      )}
      {payload ? <button type="button" className="btn" onClick={() => setForm(featureId, () => ({ ...payload }), {})}><History size={13} />Load these exact settings</button> : null}
      {state.error ? <span className="err" role="alert">{state.error}</span> : null}
      <span className="val-actions-note">A verified page is frozen under the hash of the result: anyone with the link can read it, nobody can edit it.</span>
    </div>
  );
}

export function ValReceipt({ result, scope, feature }: ViewProps) {
  const r = section(result, "receipt"), q = section(result, "data_quality");
  const p = (r.provenance ?? section(result, "cpcv").provenance ?? {}) as Row;
  const range = p.date_range as string[] | undefined;
  const uni = p.universe as { count?: number } | undefined;
  const items: [string, ReactNode][] = [
    ["Input", label(String(p.input ?? "–").replace("upload:", "upload · "))],
    ["Dates", range ? `${range[0]} → ${range[1]}` : "–"],
    ["Periods", String(p.periods ?? "–")],
    ["Universe", uni?.count ? `${uni.count} names` : "single series"],
    ["Purge / embargo", `${String(p.purge_sessions ?? 0)} / ${String(p.embargo_sessions ?? 0)} sessions`],
    ["Missing data", pct(p.missing_data_share)],
    ["Seed", String(r.seed ?? "–")],
    ["Receipt", <Hash key="r" v={r.receipt_sha256} />],
    ["Data hash", <Hash key="d" v={r.data_sha256} />],
    ["Settings hash", <Hash key="s" v={r.settings_sha256} />],
    ["Code version", <Hash key="c" v={r.code_version_sha256} />],
  ];
  const warnings = (q.warnings as string[]) ?? [];
  return (
    <div>
      {feature.id === "mlvalidate" && !scope.startsWith("verified:") ? <ReceiptActions scope={scope} featureId={feature.id} /> : null}
      <dl className="ml-receipt">{items.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <p className="ml-note"><b>Calendar.</b> {String(p.calendar ?? q.calendar_handling ?? "")} <b>Splits and adjustments.</b> {warnings.length ? warnings.join(" ") : `No anomalies (${String(q.split_adjustment_rule ?? "")}).`} <b>Reproduce.</b> {String(r.rerun ?? "")}.</p>
    </div>
  );
}
