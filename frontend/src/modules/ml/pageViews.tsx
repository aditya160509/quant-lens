"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import { Bars } from "@/charts/Bars";
import { Diverging } from "@/charts/Diverging";
import { Dumbbell } from "@/charts/Dumbbell";
import { Treemap } from "@/charts/Treemap";
import { RankList } from "@/charts/RankList";
import { Radar } from "@/charts/Radar";
import { StackedArea } from "@/charts/StackedArea";
import { TimeSeries } from "@/charts/TimeSeries";
import { useManifest } from "@/modules/research/api";
import { featureHref } from "@/modules/research/catalog";
import { isNum, label, out } from "@/modules/research/format";
import { Empty } from "@/modules/research/outputs/tables";
import type { ViewProps } from "@/modules/research/outputs/types";
import { useStudies } from "@/modules/research/store";
import { defaultsFor } from "@/modules/research/StudyForm";
import type { FeatureResult, Row } from "@/modules/research/types";
import { Segmented } from "@/workspace/ui";
import { pivot } from "./views";

/* ---------------------------------------------------------------- helpers */

const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const n = (v: unknown) => (isNum(v) ? v : null);
const f2 = (v: unknown) => (isNum(v) ? v.toFixed(2) : "–");
const f3 = (v: unknown) => (isNum(v) ? v.toFixed(3) : "–");
const pct = (v: unknown, d = 1) => (isNum(v) ? `${(v * 100).toFixed(d)}%` : "–");
const signed = (v: unknown, fmt: (x: number) => string) => (isNum(v) ? `${v > 0 ? "+" : ""}${fmt(v)}` : "–");
const tone = (v: unknown) => (isNum(v) ? (v > 0 ? "var(--up)" : v < 0 ? "var(--down)" : undefined) : undefined);
const usd = (v: unknown) => (!isNum(v) ? "–" : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}bn` : v >= 1e6 ? `$${(v / 1e6).toFixed(0)}m` : `$${Math.round(v).toLocaleString()}`);

const MODEL: Record<string, string> = { ensemble: "Ensemble", lightgbm: "LightGBM", ridge: "Ridge", ols3: "3-factor OLS", ic_composite: "IC composite", xgboost: "XGBoost", catboost: "CatBoost" };
const STRATEGY: Record<string, string> = {
  min_variance: "Min variance (shrinkage)", turnover_aware: "Min variance, trade only when worth it", standard_hrp: "Hierarchical risk parity", inverse_variance: "Inverse variance", equal_weight: "Equal weight",
  unmanaged: "Unmanaged", vol_targeted: "Volatility-targeted", half_kelly: "Half-Kelly", regime_filtered: "Regime-filtered", constant_exposure: "Constant exposure",
};
const nm = (k: unknown) => MODEL[str(k)] ?? STRATEGY[str(k)] ?? label(str(k));

function Stats({ items }: { items: [string, ReactNode, string?, string?][] }) {
  return (
    <div className="ml-stats">
      {items.map(([l, v, c, t]) => <div key={l} title={t}><span>{l}</span><b className="num" style={c ? { color: c } : undefined}>{v}</b></div>)}
    </div>
  );
}

/* ---------------------------------------------------------------- provenance and hand-offs (every page) */

type Prov = { train_window?: { start?: string; end?: string } | null; test_window?: { start?: string; end?: string } | null; purge?: number; embargo?: number; universe?: string; symbols?: number; sessions?: number; missing_share?: number; calendar?: string; session_rule?: string; dropped_sessions?: number };
const provOf = (r: FeatureResult) => (r as FeatureResult & { provenance?: Prov }).provenance;
const win = (w?: { start?: string; end?: string } | null) => (w?.start ? `${w.start} → ${w.end ?? ""}` : "–");

/** What the model was trained and tested on, so every number on the page can be traced. */
export function MlProvenance({ result }: ViewProps) {
  const p = provOf(result);
  if (!p) return <Empty />;
  const items: [string, ReactNode][] = [
    ["Trained on", win(p.train_window)], ["Tested on", win(p.test_window)], ["Purge / embargo", `${p.purge ?? 0} / ${p.embargo ?? 0} sessions`],
    ["Universe", `${label(str(p.universe ?? "custom"))}${p.symbols ? ` · ${p.symbols} names` : ""}`], ["Sessions", str(p.sessions ?? "–")], ["Missing data", pct(p.missing_share)],
  ];
  return (
    <div>
      <dl className="ml-receipt">{items.map(([k, v]) => <div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>)}</dl>
      {p.calendar ? <p className="ml-note"><b>Calendar.</b> {p.calendar}.{p.session_rule ? ` ${p.session_rule[0].toUpperCase()}${p.session_rule.slice(1)}${p.dropped_sessions ? ` (${p.dropped_sessions} dropped)` : ""}.` : ""}</p> : null}
    </div>
  );
}

type Handoff = { to: string; field: string; label: string; about: string };
const HANDOFFS: Record<string, Handoff[]> = {
  ml02: [
    { to: "mlvalidate", field: "artifact_id", label: "Validate this ranking", about: "Controls, shuffled signals, bootstrap, transfer and the overfitting autopsy on the held-out predictions." },
    { to: "ml05", field: "alpha_artifact_id", label: "Use as allocation views", about: "Scores become Black–Litterman views, scaled by the held-out IC; ignored if that IC is not positive." },
    { to: "ml04", field: "artifact_id", label: "Filter with meta-labels", about: "Barrier-labelled trades on the ranking's long and short side, with a second model deciding which to skip." },
  ],
  ml05: [{ to: "mlvalidate", field: "artifact_id", label: "Validate this allocation", about: "The walk-forward net returns, tested against controls, bootstrap and the autopsy." }],
  ml06: [{ to: "ml03", field: "regime_artifact_id", label: "Use these regimes for volatility", about: "The volatility model switches between calm and stress using this market-wide state instead of the asset's own." }],
};

/** One click carries this run's output into the next page, with the form filled in. */
export function MlNext({ result, feature }: ViewProps) {
  const router = useRouter();
  const manifest = useManifest();
  const setForm = useStudies((s) => s.setForm);
  const id = str((result.meta as Row).artifact_id);
  const items = HANDOFFS[feature.id] ?? [];
  if (!id || !items.length) return <Empty />;
  const go = (h: Handoff) => {
    const spec = manifest.data?.find((f) => f.id === h.to);
    setForm(h.to, (cur) => ({ ...cur, [h.field]: id, ...(h.to === "mlvalidate" ? { upload_id: "" } : {}) }), spec ? defaultsFor(spec) : {});
    router.push(featureHref(h.to));
  };
  return (
    <div className="ml-next">
      {items.map((h) => (
        <button key={h.label} type="button" onClick={() => go(h)}>
          <span><b>{h.label}</b><em>{h.about}</em></span>
          <ArrowRight size={15} aria-hidden />
        </button>
      ))}
      <p className="ml-note">Hand-offs are kept for this session on the server; if one has expired, rerun this page.</p>
    </div>
  );
}

/** Comparator colours: distinct hues, pulled toward grey so the series under test (accent) stays the loudest. */
const QUIET = ["var(--c2)", "var(--c3)", "var(--c5)", "var(--c4)", "var(--c6)", "var(--c8)"];
const quiet = (i: number) => `color-mix(in oklch, ${QUIET[i % QUIET.length]} 62%, var(--text-4))`;

/* ---------------------------------------------------------------- Alpha */

const nz = (v: unknown) => (isNum(v) ? v : null);

/** Every model on every metric at once, outward is better; the model under test is filled. */
export function AlphaRadar({ rows }: ViewProps) {
  if (rows.length < 2) return <Empty />;
  return (
    <div>
      <Radar axes={[
        { key: "test_ic", label: "Held-out IC", format: (v) => v.toFixed(3) },
        { key: "ic_tstat", label: "IC t-stat", format: (v) => v.toFixed(2) },
        { key: "ew_spread", label: "EW spread", format: (v) => pct(v, 2) },
        { key: "vw_spread", label: "VW spread", format: (v) => pct(v, 2) },
        { key: "net_sharpe", label: "Net Sharpe", format: (v) => v.toFixed(2) },
        { key: "turnover", label: "Turnover", better: "low", format: (v) => pct(v, 0) },
        { key: "capacity_usd", label: "Capacity", format: (v) => usd(v) },
      ]} series={rows.map((r) => ({ label: nm(r.model), primary: Boolean(r.primary), values: { test_ic: nz(r.test_ic), ic_tstat: nz(r.ic_tstat), ew_spread: nz(r.ew_spread), vw_spread: nz(r.vw_spread), net_sharpe: nz(r.net_sharpe), turnover: nz(r.turnover), capacity_usd: nz(r.capacity_usd) } }))} />
      <p className="ml-note">Each axis is rescaled across the models shown, so the rim is the best of them and the centre the worst; turnover is flipped so outward is always better. Hover an axis or a model for the raw numbers.</p>
    </div>
  );
}

/** The chosen allocation against its controls on return, risk, drawdown and trading cost. */
export function StrategyRadar({ rows }: ViewProps) {
  if (rows.length < 3) return <Empty />;
  const key = "strategy" in (rows[0] ?? {}) ? "strategy" : "model";
  const primary = rows.find((r) => r.kind === "chosen") ?? rows[0];
  return (
    <div>
      <Radar axes={[
        { key: "annual_return", label: "Return", format: (v) => pct(v) },
        { key: "sharpe", label: "Sharpe", format: (v) => v.toFixed(2) },
        { key: "annual_volatility", label: "Volatility", better: "low", format: (v) => pct(v) },
        { key: "max_drawdown", label: "Max drawdown", format: (v) => pct(v) },
        { key: "average_turnover", label: "Turnover", better: "low", format: (v) => pct(v, 0) },
        { key: "cost_drag_annual", label: "Cost drag", better: "low", format: (v) => pct(v, 2) },
      ]} series={rows.map((r) => ({ label: nm(r[key]), primary: r === primary, values: { annual_return: nz(r.annual_return), sharpe: nz(r.sharpe), annual_volatility: nz(r.annual_volatility), max_drawdown: nz(r.max_drawdown), average_turnover: nz(r.average_turnover), cost_drag_annual: nz(r.cost_drag_annual) } }))} />
      <p className="ml-note">Outward is better on every axis: lower volatility, shallower drawdown, less turnover and cost. Rescaled across the strategies shown.</p>
    </div>
  );
}

/** Each holding's share of portfolio risk now and after the trades, against an equal share. */
export function HoldingRisk({ rows }: ViewProps) {
  const list = rows.filter((r) => isNum(r.current_risk_contribution) || isNum(r.target_risk_contribution));
  if (!list.length) return <Empty />;
  const sorted = [...list].sort((a, b) => (n(b.current_risk_contribution) ?? 0) - (n(a.current_risk_contribution) ?? 0));
  return (
    <div>
      <Dumbbell aLabel="Now" bLabel="After trades" shared rows={sorted.map((r) => ({
        label: `${str(r.asset)} · ${pct(r.current_weight, 0)} → ${pct(r.target_weight, 0)}`, a: nz(r.current_risk_contribution), b: nz(r.target_risk_contribution), format: (v) => pct(v, 1), neutral: true,
      }))} />
      <p className="ml-note">Share of total portfolio variance each holding carries, before and after the trade list; an equal share would be {pct(1 / list.length, 0)} each. Weights are shown beside each name.</p>
    </div>
  );
}

/** The model against the simple alternatives it must beat, on held-out data. */
export function AlphaControls({ rows }: ViewProps) {
  const [metric, setMetric] = useState<"test_ic" | "net_sharpe">("test_ic");
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => (n(b[metric]) ?? -9) - (n(a[metric]) ?? -9));
  const primary = rows.find((r) => r.primary);
  const best = sorted.find((r) => !r.primary);
  return (
    <div>
      <div className="ml-bar">
        <Segmented<"test_ic" | "net_sharpe"> label="Metric" value={metric} onChange={setMetric} options={[{ value: "test_ic", label: "Held-out IC" }, { value: "net_sharpe", label: "Net Sharpe" }]} />
      </div>
      <Bars bars={sorted.filter((r) => isNum(r[metric])).map((r) => ({
        label: nm(r.model), value: r[metric] as number, color: r.primary ? "var(--accent)" : undefined, muted: !r.primary,
        ...(metric === "test_ic" && isNum(r.ic_tstat) && Math.abs(r.ic_tstat) > 0.05 ? { lo: (r.test_ic as number) - 1.96 * Math.abs((r.test_ic as number) / r.ic_tstat), hi: (r.test_ic as number) + 1.96 * Math.abs((r.test_ic as number) / r.ic_tstat) } : {}),
        detail: [["Kind", str(r.kind)], ["IC t-stat", f2(r.ic_tstat)], ["EW spread", pct(r.ew_spread, 2)], ["VW spread", pct(r.vw_spread, 2)], ["Turnover", pct(r.turnover, 0)], ["Capacity", usd(r.capacity_usd)]],
      }))} signed={false} height={220} yLabel={metric === "test_ic" ? "Rank IC, held-out" : "Annualised Sharpe, net"} format={(v) => (metric === "test_ic" ? v.toFixed(3) : v.toFixed(2))} />
      <div className="ml-table-wrap">
        <table className="ml-table">
          <thead><tr><th>Model</th><th>IC</th><th>IC t</th><th>EW spread</th><th>VW spread</th><th>Net Sharpe</th><th>Turnover</th><th>Capacity</th></tr></thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={str(r.model)} data-primary={r.primary || undefined}>
                <td>{nm(r.model)}{r.kind === "control" ? <em> control</em> : r.kind === "baseline" ? <em> baseline</em> : null}</td>
                <td className="num" style={{ color: tone(r.test_ic) }}>{f3(r.test_ic)}</td><td className="num">{f2(r.ic_tstat)}</td>
                <td className="num">{pct(r.ew_spread, 2)}</td><td className="num">{pct(r.vw_spread, 2)}</td>
                <td className="num" style={{ color: tone(r.net_sharpe) }}>{f2(r.net_sharpe)}</td><td className="num">{pct(r.turnover, 0)}</td><td className="num">{usd(r.capacity_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {primary && best ? <p className="ml-note"><b>Read.</b> {nm(primary.model)} {(n(primary.test_ic) ?? 0) > (n(best.test_ic) ?? 0) ? "beats" : "does not beat"} the best alternative ({nm(best.model)}) on held-out IC. Value-weighted spreads use 63-day dollar volume; capacity is the AUM at which a trade first exceeds 10% of a name&apos;s average daily dollar volume.</p> : null}
    </div>
  );
}

/** Names sorted into bins by prediction: a real signal climbs from the bottom bin to the top under both weightings.
 * "Excess" subtracts the average bin so a rising market does not make every bar green. */
export function AlphaDeciles({ rows }: ViewProps) {
  const models = useMemo(() => [...new Set(rows.map((r) => str(r.model)))], [rows]);
  const [model, setModel] = useState<string | null>(null);
  const [w, setW] = useState("equal");
  const [mode, setMode] = useState<"excess" | "raw">("excess");
  if (!rows.length) return <Empty />;
  const m = model ?? (models.includes("ensemble") ? "ensemble" : models[0]);
  const weights = [...new Set(rows.map((r) => str(r.weighting)))];
  const ww = weights.includes(w) ? w : weights[0];
  const sel = rows.filter((r) => str(r.model) === m && str(r.weighting) === ww).sort((a, b) => (n(a.bin) ?? 0) - (n(b.bin) ?? 0));
  const avg = sel.reduce((t, r) => t + (n(r.mean_return) ?? 0), 0) / (sel.length || 1);
  const spread = sel.length > 1 ? (n(sel[sel.length - 1].mean_return) ?? 0) - (n(sel[0].mean_return) ?? 0) : null;
  const prefix = sel.length === 10 ? "D" : sel.length === 5 ? "Q" : "B";
  const rising = sel.every((r, i) => i === 0 || (n(r.mean_return) ?? 0) >= (n(sel[i - 1].mean_return) ?? 0));
  return (
    <div>
      <div className="ml-bar">
        {models.length > 1 ? <select className="input" style={{ height: 28, width: "auto" }} aria-label="Model" value={m} onChange={(e) => setModel(e.target.value)}>{models.map((x) => <option key={x} value={x}>{nm(x)}</option>)}</select> : null}
        {weights.length > 1 ? <Segmented<string> label="Weighting" value={ww} onChange={setW} options={weights.map((x) => ({ value: x, label: label(x) }))} /> : null}
        <Segmented<"excess" | "raw"> label="Scale" value={mode} onChange={setMode} options={[{ value: "excess", label: "Excess" }, { value: "raw", label: "Raw" }]} />
      </div>
      <Stats items={[["Top minus bottom", signed(spread, (x) => pct(x, 2)), tone(spread), "Mean forward return of the top bin minus the bottom bin, per rebalance"], ["Monotonic", rising ? "Yes" : "No", rising ? "var(--up)" : "var(--warn)", "Every bin at least as good as the one below"], ["Bins", String(sel.length)]]} />
      <Bars bars={sel.map((r) => ({ label: `${prefix}${str(r.bin)}`, value: (n(r.mean_return) ?? 0) - (mode === "excess" ? avg : 0) }))} height={210}
        yLabel={mode === "excess" ? "Return vs average bin, per rebalance" : "Mean forward return per rebalance"} format={(v) => pct(v, 2)} />
      <p className="ml-note">{prefix}1 holds the names with the lowest predictions, {prefix}{sel.length} the highest. {ww === "value" ? "Value-weighted by 63-day dollar volume, so large names dominate as they would in a real portfolio." : "Equal-weighted; switch to value weighting to see whether the edge survives in large names."}</p>
    </div>
  );
}

/** Growth of $1 for each model after trading costs, held-out period only. */
export function AlphaNetCurve({ rows, result }: ViewProps) {
  const { data, keys } = useMemo(() => pivot(rows, "date", "model", "equity"), [rows]);
  if (!rows.length) return <Empty />;
  // The model is the accent; controls are neutral (dashed for the one it must beat), never red, which would read as "bad".
  const primary = str(out(result, "controls").find((r) => r.primary)?.model) || "ensemble";
  const style = (k: string, i: number) => (k === primary ? { color: "var(--accent)", width: 2.2 } : { color: quiet(i), width: 1.3 });
  return <TimeSeries data={data} x="date" height={260} yLabel="Growth of $1, net of costs" directLabels series={keys.map((k, i) => ({ key: k, label: nm(k), ...style(k, i) }))} refLines={[{ y: 1, color: "var(--line-3)", dash: true }]} />;
}

type Driver = { feature: string; delta: number };
/** Who entered and left the top of the ranking since the last rebalance, and which features moved them. */
export function AlphaWhatChanged({ rows, result }: ViewProps) {
  const meta = ((result.meta as Row).what_changed ?? {}) as { previous_date?: string; current_date?: string; top_n?: number; entered?: string[]; exited?: string[] };
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => Math.abs(n(b.rank_change) ?? 0) - Math.abs(n(a.rank_change) ?? 0)).slice(0, 12);
  return (
    <div>
      <p className="val-sentence" style={{ fontSize: 14 }}>
        {meta.entered?.length ? <>Entered the top {meta.top_n}: <b>{meta.entered.join(", ")}</b>. </> : null}
        {meta.exited?.length ? <>Left: <b>{meta.exited.join(", ")}</b>. </> : null}
        <span style={{ color: "var(--text-3)" }}>{meta.previous_date} → {meta.current_date}</span>
      </p>
      <div className="ml-moves">
        {sorted.map((r) => {
          const ch = n(r.rank_change) ?? 0;
          const Icon = ch > 0 ? ArrowUpRight : ArrowDownRight;
          return (
            <div key={str(r.ticker)} className="ml-move" data-move={str(r.move)}>
              <b>{str(r.ticker)}</b>
              <span className="num">{str(r.previous_rank)} → {str(r.rank)}</span>
              <em className="num" style={{ color: ch > 0 ? "var(--up)" : "var(--down)" }}><Icon size={12} aria-hidden />{Math.abs(ch)}</em>
              <span className="ml-drivers">{((r.top_drivers as Driver[]) ?? []).slice(0, 3).map((d) => <span key={d.feature} className={d.delta >= 0 ? "up" : "down"}>{label(d.feature)}</span>)}</span>
            </div>
          );
        })}
      </div>
      <p className="ml-note">Rank 1 is the strongest expected return. Drivers are the features whose SHAP contribution changed most for that name since the previous rebalance.</p>
    </div>
  );
}

/** How much each feature family contributes to predictions. */
export function AlphaFamilies({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].filter((r) => isNum(r.mean_abs_shap)).sort((a, b) => (b.mean_abs_shap as number) - (a.mean_abs_shap as number));
  const total = sorted.reduce((s, r) => s + (r.mean_abs_shap as number), 0) || 1;
  return <RankList title="Feature family contributions" items={sorted.map((r) => ({ label: label(str(r.family)), value: (r.mean_abs_shap as number) / total, note: (Array.isArray(r.features) ? r.features as string[] : []).map(label).join(", ") }))} format={(v) => pct(v, 1)} />;
}

/** Validation IC across LightGBM–Ridge blends; the chosen blend is the one validation preferred, never the test. */
export function AlphaEnsemble({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => (n(a.lightgbm) ?? 0) - (n(b.lightgbm) ?? 0));
  const chosen = rows.find((r) => r.chosen);
  return (
    <div>
      <Stats items={[["Chosen blend", chosen ? `${pct(chosen.lightgbm, 0)} LightGBM` : "–"], ["Validation IC", f3(chosen?.validation_ic)]]} />
      <Bars bars={sorted.map((r) => ({ label: pct(r.lightgbm, 0), value: n(r.validation_ic) ?? 0, color: r.chosen ? "var(--accent)" : undefined, muted: !r.chosen }))} signed={false} height={180} yLabel="Validation IC" format={(v) => v.toFixed(3)} />
      <p className="ml-note">x-axis: LightGBM&apos;s share of the blend, the rest Ridge.</p>
    </div>
  );
}

/* ---------------------------------------------------------------- Volatility and risk */

/** Where the likely return range sits around zero, on a scale shared by every horizon so they compare at a glance. */
function RangeGauge({ lo, hi, span }: { lo: number | null; hi: number | null; span: number }) {
  if (lo === null || hi === null) return null;
  const x = (v: number) => `${50 + (v / span) * 50}%`;
  return (
    <span className="gauge" aria-hidden>
      <i className="zero" />
      <i className="dn" style={{ left: x(lo), width: `calc(50% - ${x(lo)})` }} />
      <i className="up" style={{ left: "50%", width: `calc(${x(hi)} - 50%)` }} />
    </span>
  );
}

/** Today's risk in one card: forecast ranges, regime, suggested size and tail loss. */
export function RiskToday({ rows }: ViewProps) {
  const [i, setI] = useState(0);
  if (!rows.length) return <Empty />;
  const r = rows[Math.min(i, rows.length - 1)];
  const stress = n(r.stress_probability);
  return (
    <div className="risk-today">
      {rows.length > 1 ? (
        <div className="ml-bar"><select className="input" style={{ height: 28, width: "auto" }} aria-label="Asset" value={i} onChange={(e) => setI(Number(e.target.value))}>{rows.map((x, k) => <option key={str(x.asset)} value={k}>{str(x.asset)}</option>)}</select><span className="ml-sub" style={{ margin: 0 }}>{rows.length} names in the watchlist</span></div>
      ) : null}
      <div className="risk-head">
        <div className="risk-asset"><b>{str(r.asset)}</b><span className="risk-regime" data-r={str(r.regime)}>{label(str(r.regime))} regime</span>{stress !== null ? <span className="risk-prob num">stress probability {pct(stress, 0)}</span> : null}</div>
        <div className="risk-size"><span>Suggested size</span><b className="num">{isNum(r.size_multiple) ? `${r.size_multiple.toFixed(2)}×` : "–"}</b><em>vs 1.00× unmanaged{isNum(r.target_volatility) ? ` · target ${pct(r.target_volatility, 0)} vol` : ""}</em></div>
      </div>
      <div className="risk-horizons">
        {[1, 5, 21].map((h) => (
          <div key={h}>
            <span>{h === 1 ? "Next day" : h === 5 ? "Next week" : "Next month"}</span>
            <b className="num">{pct(r[`vol_${h}d`])}<small> vol</small></b>
            <em className="num">{pct(r[`range_${h}d_low`])} to {signed(r[`range_${h}d_high`], (x) => pct(x))}</em>
            <RangeGauge lo={n(r[`range_${h}d_low`])} hi={n(r[`range_${h}d_high`])} span={Math.max(...[1, 5, 21].map((k) => Math.max(Math.abs(n(r[`range_${k}d_low`]) ?? 0), Math.abs(n(r[`range_${k}d_high`]) ?? 0))), 1e-6)} />
          </div>
        ))}
      </div>
      <div className="risk-tail">
        {[["VaR 95%", "var_95"], ["ES 95%", "es_95"], ["VaR 99%", "var_99"], ["ES 99%", "es_99"]].map(([l, k]) => <div key={k}><span>{l}</span><b className="num" style={{ color: "var(--down)" }}>{pct(r[k], 2)}</b></div>)}
      </div>
      <p className="ml-note">Annualised volatility forecast, with the calibrated range of the return over that horizon below it. VaR and ES are one-day losses at the stated confidence. Size scales exposure to the target volatility, capped; the evidence for volatility timing is mixed, so the unmanaged line is always shown below.</p>
    </div>
  );
}

/** Tail loss by horizon at 95% and 99%, in one matrix; the one-day VaR carries its out-of-sample breach test. */
export function RiskVarEs({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const hs = [...new Set(rows.map((r) => Number(r.horizon)))].sort((a, b) => a - b);
  const levels = [...new Set(rows.map((r) => Number(r.level)))].sort((a, b) => a - b);
  const at = (h: number, l: number) => rows.find((r) => Number(r.horizon) === h && Number(r.level) === l);
  const maxEs = Math.max(...rows.map((r) => n(r.es) ?? 0), 1e-9);
  const horizon = (h: number) => (h === 1 ? "1 day" : h === 5 ? "1 week" : h === 21 ? "1 month" : h === 63 ? "3 months" : `${h} days`);
  const one = levels.map((l) => at(1, l)).filter(Boolean) as Row[];
  return (
    <div>
      {one.length ? (
        <div className="var-calib">
          {one.map((r) => {
            const p = n(r.kupiec_p_value), ok = p === null ? null : p >= 0.05;
            return (
              <div key={str(r.level)} data-ok={ok === null ? undefined : ok ? "1" : "0"}>
                <span>1-day VaR {pct(r.level, 0)} backtest</span>
                <b className="num">{pct(r.oos_breach_rate, 1)} breached</b>
                <em>expected {pct(r.expected_breach_rate, 0)} · Kupiec p {p === null ? "–" : p.toFixed(2)} · {ok === null ? "untested" : ok ? "calibrated" : "miscalibrated"}</em>
              </div>
            );
          })}
        </div>
      ) : null}
      <div className="ml-table-wrap">
        <table className="ml-table varm">
          <thead>
            <tr><th rowSpan={2}>Horizon</th>{levels.map((l) => <th key={l} colSpan={2} className="grp">{pct(l, 0)} confidence</th>)}</tr>
            <tr>{levels.map((l) => [<th key={`v${l}`}>VaR</th>, <th key={`e${l}`}>ES</th>])}</tr>
          </thead>
          <tbody>
            {hs.map((h) => (
              <tr key={h}>
                <td>{horizon(h)}</td>
                {levels.map((l) => {
                  const r = at(h, l);
                  return [
                    <td key={`v${l}`} className="num">{pct(r?.var, 2)}</td>,
                    <td key={`e${l}`} className="num es"><span style={{ width: `${((n(r?.es) ?? 0) / maxEs) * 100}%` }} /><b>{pct(r?.es, 2)}</b></td>,
                  ];
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ml-note">Losses as a share of position value. VaR is the loss exceeded on the worst {pct(1 - (levels[0] ?? 0.95), 0)} (or {pct(1 - (levels[levels.length - 1] ?? 0.99), 0)}) of periods; expected shortfall is the average loss on those periods. Filtered historical simulation.</p>
    </div>
  );
}

/** Any set of strategies compared on return, risk and drawdown, controls dimmed. */
export function StrategyCompare({ rows, feature }: ViewProps) {
  if (!rows.length) return <Empty />;
  const key = rows[0] && "strategy" in rows[0] ? "strategy" : "model";
  // The strategy under test is the accent; unmanaged and the controls are the yardsticks.
  const primary = rows.find((r) => r.kind === "chosen") ?? rows.find((r) => ["vol_targeted", "regime_filtered", "min_variance"].includes(str(r[key]))) ?? rows[0];
  const sorted = [...rows].sort((a, b) => (n(b.sharpe) ?? -9) - (n(a.sharpe) ?? -9));
  // With two or three strategies, the fair yardstick (same exposure, else unmanaged) against the one under test, metric by metric.
  const yard = rows.length <= 3 ? rows.find((r) => r[key] === "constant_exposure") ?? rows.find((r) => r[key] === "unmanaged" && r !== primary) ?? rows.find((r) => r !== primary) : undefined;
  return (
    <div>
      {yard ? (
        <Dumbbell aLabel={nm(yard[key])} bLabel={nm(primary[key])} rows={[
          { label: "Sharpe", a: nz(yard.sharpe), b: nz(primary.sharpe), format: (v) => v.toFixed(2) },
          { label: "Annual return", a: nz(yard.annual_return), b: nz(primary.annual_return), format: (v) => pct(v) },
          { label: "Volatility", a: nz(yard.annual_volatility), b: nz(primary.annual_volatility), format: (v) => pct(v), better: "low" },
          { label: "Max drawdown", a: nz(yard.max_drawdown), b: nz(primary.max_drawdown), format: (v) => pct(v) },
        ]} />
      ) : (
        <Bars bars={sorted.filter((r) => isNum(r.sharpe)).map((r) => ({ label: nm(r[key]), value: r.sharpe as number, color: r === primary ? "var(--accent)" : undefined, muted: r !== primary }))} signed={false} height={190} yLabel="Annualised Sharpe" format={(v) => v.toFixed(2)} />
      )}
      <div className="ml-table-wrap">
        <table className="ml-table">
          <thead><tr><th>{feature.id === "ml05" ? "Allocation" : "Strategy"}</th><th>Return</th><th>Volatility</th><th>Sharpe</th><th>Max drawdown</th>{"average_turnover" in primary ? <th>Turnover</th> : null}{"cost_drag_annual" in primary ? <th>Cost drag</th> : null}{"average_exposure" in primary || "mean_size" in primary ? <th>Avg exposure</th> : null}</tr></thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={str(r[key])} data-primary={r === primary || undefined}>
                <td>{nm(r[key])}</td><td className="num" style={{ color: tone(r.annual_return) }}>{pct(r.annual_return)}</td><td className="num">{pct(r.annual_volatility)}</td>
                <td className="num">{f2(r.sharpe)}</td><td className="num" style={{ color: "var(--down)" }}>{pct(r.max_drawdown)}</td>
                {"average_turnover" in primary ? <td className="num">{pct(r.average_turnover, 0)}</td> : null}
                {"cost_drag_annual" in primary ? <td className="num">{pct(r.cost_drag_annual, 2)}</td> : null}
                {"average_exposure" in primary || "mean_size" in primary ? <td className="num">{isNum(r.average_exposure ?? r.mean_size) ? `${(n(r.average_exposure ?? r.mean_size) ?? 0).toFixed(2)}×` : "–"}</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Market-wide stress probability through time, filtered forward with no look-ahead. */
export function RiskStress({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return <TimeSeries data={rows} x="date" height={200} yLabel="Stress probability" format={(v) => pct(v, 0)} series={[{ key: "stress_probability", label: "Stress probability", kind: "area", color: "var(--down)" }]} refLines={[{ y: 0.5, color: "var(--line-3)", dash: true, label: "50%" }]} />;
}

/* ---------------------------------------------------------------- Allocation */

/** Each holding's target weight with its bootstrap range, beside its share of portfolio risk. A name whose risk share
 * far exceeds its weight is where the risk really sits; a wide range means the weight is mostly estimation noise. */
export function AllocStability({ rows, result }: ViewProps) {
  const [all, setAll] = useState(false);
  if (!rows.length) return <Empty />;
  const risk = new Map(out(result, "risk_contribution_decomposition").map((r) => [str(r.asset), n(r.risk_contribution)]));
  const riskTotal = [...risk.values()].reduce<number>((t, v) => t + Math.max(0, v ?? 0), 0) || 1;
  const sorted = [...rows].filter((r) => isNum(r.weight)).sort((a, b) => (b.weight as number) - (a.weight as number));
  const held = sorted.filter((r) => (r.weight as number) > 1e-4);
  const shown = all ? sorted : held.slice(0, 15);
  const max = Math.max(...sorted.map((r) => n(r.p95) ?? (r.weight as number)), 1e-9);
  const unstable = sorted.filter((r) => (n(r.p95) ?? 0) - (n(r.p05) ?? 0) > Math.max(0.05, r.weight as number)).length;
  const top5 = held.slice(0, 5).reduce((t, r) => t + (r.weight as number), 0);
  const x = (v: number) => `${(v / max) * 100}%`;
  return (
    <div>
      <Stats items={[["Names held", `${held.length} of ${sorted.length}`], ["Top 5 weight", pct(top5, 0)], ["Unstable weights", String(unstable), unstable ? "var(--warn)" : "var(--up)", "Bootstrap range wider than the weight itself (or 5 points)"], ["Resamples", str(sorted[0]?.draws) || "–"]]} />
      <div className="wt">
        <div className="wt-h"><span>Asset</span><span>Weight and 5–95% bootstrap range</span><span>Weight</span><span>Risk share</span></div>
        {shown.map((r) => {
          const w = r.weight as number, lo = n(r.p05) ?? w, hi = n(r.p95) ?? w;
          const rs = Math.max(0, risk.get(str(r.asset)) ?? 0) / riskTotal;
          const tilt = rs - w;
          return (
            <div key={str(r.asset)} className="wt-r">
              <b>{str(r.asset)}</b>
              <span className="wt-track" title={`5–95%: ${pct(lo)} to ${pct(hi)}`}>
                <i className="bar" style={{ width: x(w) }} />
                <i className="rng" style={{ left: x(lo), width: `calc(${x(hi)} - ${x(lo)})` }} />
              </span>
              <em className="num">{pct(w)}</em>
              <em className="num" style={{ color: Math.abs(tilt) < 0.02 ? "var(--text-2)" : tilt > 0 ? "var(--warn)" : "var(--text-3)" }}>{risk.size ? pct(rs) : "–"}</em>
            </div>
          );
        })}
      </div>
      {sorted.length > 15 ? <button type="button" className="link" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setAll((v) => !v)}>{all ? "Show the 15 largest" : `Show all ${sorted.length} names`}</button> : null}
      <p className="ml-note">Bar: today&apos;s target weight. Whisker: where that weight lands across {str(sorted[0]?.draws) || "the"} bootstrap resamples of the estimation window. Risk share in amber when a name carries notably more risk than capital.</p>
    </div>
  );
}

/** The trades that move your holdings to the target, with their cost and the change in risk. */
export function AllocTrades({ rows, result }: ViewProps) {
  const sum = out(result, "rebalance_summary")[0];
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => Math.abs(n(b.trade_weight) ?? 0) - Math.abs(n(a.trade_weight) ?? 0));
  return (
    <div>
      {sum ? <Stats items={[["Trade?", sum.trade_recommended ? "Yes" : "Not worth it", sum.trade_recommended ? "var(--up)" : "var(--warn)"], ["Turnover", pct(sum.turnover)], ["Cost", usd(sum.total_cost)], ["Volatility", `${pct(sum.volatility_before)} → ${pct(sum.volatility_after)}`, tone(-(n(sum.volatility_change) ?? 0))]]} /> : null}
      <div className="ml-table-wrap">
        <table className="ml-table">
          <thead><tr><th>Asset</th><th>Side</th><th>Now</th><th>Target</th><th>Trade</th><th>Value</th><th>Shares</th><th>Cost</th></tr></thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={str(r.asset)}>
                <td>{str(r.asset)}</td><td style={{ color: str(r.side) === "buy" ? "var(--up)" : str(r.side) === "sell" ? "var(--down)" : undefined }}>{label(str(r.side))}</td>
                <td className="num">{pct(r.current_weight)}</td><td className="num">{pct(r.target_weight)}</td><td className="num" style={{ color: tone(r.trade_weight) }}>{signed(r.trade_weight, (x) => pct(x))}</td>
                <td className="num">{usd(Math.abs(n(r.trade_value) ?? 0))}</td><td className="num">{isNum(r.shares) ? Math.round(r.shares).toLocaleString() : "–"}</td><td className="num">{usd(r.cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Each walk-forward refit: was the expected gain worth the trading cost? */
export function AllocRebalances({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const traded = rows.filter((r) => r.traded).length;
  return (
    <div>
      <Stats items={[["Refits", String(rows.length)], ["Traded", String(traded)], ["Skipped", String(rows.length - traded)]]} />
      <div className="ml-refits" aria-label="Refits, traded or skipped">
        {rows.map((r) => <i key={str(r.date)} data-t={r.traded ? "1" : "0"} title={`${str(r.date)}: ${r.traded ? "traded" : "skipped"} · expected gain ${pct(r.expected_gain, 2)} vs cost ${pct(r.trade_cost, 2)}`} />)}
      </div>
      <p className="ml-note">Filled: the expected risk reduction beat the trading cost, so the portfolio rebalanced. Hollow: it did not, so the old weights were kept.</p>
    </div>
  );
}

/** How far each feature has moved from its training distribution, and whether the model should be retrained. */
export function AlphaDrift({ rows, result }: ViewProps) {
  const mon = ((result.meta as Row).monitoring ?? {}) as { retrain_recommended?: boolean; reasons?: string[]; drift_threshold_sd?: number; recent_sessions?: number; recent_ic?: number | null; test_ic?: number | null };
  if (!rows.length) return <Empty />;
  const top = [...rows].sort((a, b) => (n(b.drift) ?? 0) - (n(a.drift) ?? 0)).slice(0, 12);
  const thr = mon.drift_threshold_sd ?? 0.5;
  const max = Math.max(thr * 1.6, ...top.map((r) => n(r.drift) ?? 0));
  return (
    <div>
      <div className="drift-flag" data-on={mon.retrain_recommended || undefined}>
        <b>{mon.retrain_recommended ? "Retrain recommended" : "No retrain needed"}</b>
        <span>{mon.retrain_recommended ? (mon.reasons ?? []).join("; ") : `No top-5 feature has drifted past ${thr} training sd, and recent IC holds up.`}</span>
      </div>
      <Stats items={[["Recent IC (3 mo)", f3(mon.recent_ic)], ["Test IC", f3(mon.test_ic)], ["Features flagged", String(rows.filter((r) => r.flag).length), rows.some((r) => r.flag) ? "var(--warn)" : "var(--up)"]]} />
      <div className="ml-shares drift">
        {top.map((r) => (
          <div key={str(r.feature)}>
            <span>{label(str(r.feature))}<em className="num"> #{str(r.importance_rank)}</em></span>
            <span className="ml-share-bar"><i style={{ width: `${((n(r.drift) ?? 0) / max) * 100}%`, background: r.flag ? "var(--warn)" : "var(--s1)" }} /><s style={{ left: `${(thr / max) * 100}%` }} /></span>
            <b className="num">{f2(r.drift)}</b>
          </div>
        ))}
      </div>
      <p className="ml-note">Wasserstein distance between each feature&apos;s training distribution and its last {mon.recent_sessions ?? 63} sessions, in training standard deviations; the tick marks the {thr} sd threshold. #n is the feature&apos;s importance rank.</p>
    </div>
  );
}

/** Growth of $1 for every strategy, the one under test in the accent colour, with each one's drawdown underneath. */
export function EquityCompare({ rows, result }: ViewProps) {
  const key = rows[0] && "strategy" in rows[0] ? "strategy" : "model";
  const { data, keys, dd } = useMemo(() => {
    const p = pivot(rows, "date", key, "equity");
    const peak: Record<string, number> = {};
    const dd = p.data.map((r) => {
      const o: Row = { date: r.date };
      for (const k of p.keys) {
        const v = n(r[k]);
        if (v === null) continue;
        peak[k] = Math.max(peak[k] ?? v, v);
        o[k] = v / peak[k] - 1;
      }
      return o;
    });
    return { data: p.data, keys: p.keys, dd };
  }, [rows, key]);
  if (!rows.length) return <Empty />;
  const chosen = str(out(result, "controls_summary").find((r) => r.kind === "chosen")?.strategy) || keys[0];
  const style = (k: string, i: number) => (k === chosen ? { color: "var(--accent)", width: 2.2 } : k === "turnover_aware" ? { color: "var(--accent)", width: 1.4, dash: true } : { color: quiet(i), width: 1.3 });
  return (
    <div>
      <TimeSeries data={data} x="date" height={260} yLabel="Growth of $1, net of costs" directLabels series={keys.map((k, i) => ({ key: k, label: nm(k), ...style(k, i) }))} refLines={[{ y: 1, color: "var(--line-3)", dash: true }]} />
      <TimeSeries data={dd} x="date" height={110} legend={false} format={(v) => pct(v, 0)} yLabel="Drawdown" series={keys.map((k, i) => ({ key: k, label: nm(k), ...style(k, i), width: k === chosen ? 1.6 : 1 }))} />
    </div>
  );
}

/* ---------------------------------------------------------------- Improve my strategy (barriers) */

const TOUCH: Record<string, { label: string; color: string }> = {
  profit_taking: { label: "Profit-taking first", color: "var(--up)" },
  stop_loss: { label: "Stop-loss first", color: "var(--down)" },
  vertical: { label: "Time barrier", color: "var(--text-4)" },
};
const touchOf = (r: Row) => str(r.touch_type) || (n(r.label) === 1 ? "profit_taking" : n(r.label) === -1 ? "stop_loss" : "vertical");

/** How the label mix moves through time: month by month, which barrier events hit first. Drift here means the
 * barriers that suit one period do not suit another. */
export function BarrierTimeline({ rows }: ViewProps) {
  const { data, keys } = useMemo(() => {
    const by = new Map<string, Record<string, number>>();
    for (const r of rows) {
      const m = str(r.date).slice(0, 7);
      if (!m) continue;
      const o = by.get(m) ?? {};
      const t = touchOf(r);
      o[t] = (o[t] ?? 0) + 1;
      by.set(m, o);
    }
    const keys = ["stop_loss", "vertical", "profit_taking"].filter((k) => [...by.values()].some((o) => o[k]));
    const data = [...by.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([m, o]) => ({ date: `${m}-15`, ...Object.fromEntries(keys.map((k) => [k, o[k] ?? 0])) }));
    return { data, keys };
  }, [rows]);
  if (data.length < 2) return <Empty />;
  return (
    <div>
      <StackedArea data={data} keys={keys} height={220} labels={Object.fromEntries(keys.map((k) => [k, TOUCH[k].label]))} colors={Object.fromEntries(keys.map((k) => [k, TOUCH[k].color]))} />
      <p className="ml-note">Share of events each month by the barrier touched first, from the {rows.length.toLocaleString()} most recent events. A rising red band means the stop is being hit more often: the market has become noisier relative to your barriers.</p>
    </div>
  );
}

/** Fixed against volatility-scaled barriers, side by side, on the same events. */
export function BarrierMethods({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return (
    <div>
      <div className="mix">
        {rows.map((r) => (
          <div key={str(r.method)} className="mix-row">
            <b>{str(r.method) === "vol_scaled" ? "Volatility-scaled" : "Fixed"}</b>
            <span className="mix-bar">
              <i style={{ width: pct(r.negative_rate), background: "var(--down)" }} />
              <i style={{ width: pct(r.neutral_rate), background: "var(--text-4)" }} />
              <i style={{ width: pct(r.positive_rate), background: "var(--up)" }} />
            </span>
            <em className="num">{pct(r.positive_rate, 0)} PT · {pct(r.negative_rate, 0)} SL · {pct(r.neutral_rate, 0)} time</em>
          </div>
        ))}
      </div>
      <p className="ml-note">Volatility-scaled barriers widen in turbulent markets, so fewer events are stopped out by noise. Ambiguous same-bar touches: {rows.map((r) => `${str(r.method) === "vol_scaled" ? "scaled" : "fixed"} ${str(r.ambiguous)}`).join(", ")}.</p>
    </div>
  );
}

/** The meta-model's confidence in each trade; empty until a primary side is supplied. */
export function MetaProbability({ rows }: ViewProps) {
  const p = rows.map((r) => n(r.meta_probability)).filter((v): v is number => v !== null);
  if (!p.length) return <div className="val-unavail"><b>No meta-labels for this run</b><span>Meta-labels need a primary side for each trade: upload predictions in Validate, or send an Alpha ranking here with &ldquo;Filter with meta-labels&rdquo;.</span></div>;
  const bins = Array.from({ length: 10 }, (_, i) => ({ label: `${i * 10}%`, value: p.filter((v) => v >= i / 10 && (v < (i + 1) / 10 || (i === 9 && v === 1))).length }));
  const sure = p.filter((v) => v < 0.4 || v > 0.6).length / p.length;
  const kept = p.filter((v) => v >= 0.5).length / p.length;
  return (
    <div>
      <Stats items={[["Confident calls", pct(sure, 0), sure < 0.2 ? "var(--warn)" : "var(--up)", "Share of trades with probability below 40% or above 60%"], ["Kept at 50%", pct(kept, 0)], ["Trades", String(p.length)]]} />
      <Bars bars={bins} signed={false} height={190} yLabel="Trades" format={(v) => String(Math.round(v))} />
      <p className="ml-note">{sure < 0.2 ? "The meta-model is rarely confident: almost every trade sits near 50%, so it cannot separate good trades from bad. Filtering on it would mostly add noise; check the Improve section in Validate before using it." : "Trades away from 50% are where the meta-model has a view; sizing by this probability shrinks the uncertain ones."}</p>
    </div>
  );
}

/* ---------------------------------------------------------------- alternative lenses ("View as") */

/** The ranking seen by sector: where the model leans, with the strongest name in each. */
export function AlphaSectors({ rows }: ViewProps) {
  const by = new Map<string, Row[]>();
  for (const r of rows) by.set(str(r.sector) || "Unknown", [...(by.get(str(r.sector) || "Unknown") ?? []), r]);
  if (!by.size) return <Empty />;
  const items = [...by.entries()].map(([s, rs]) => {
    const p = rs.map((r) => n(r.prediction) ?? 0);
    const best = [...rs].sort((a, b) => (n(b.prediction) ?? 0) - (n(a.prediction) ?? 0))[0];
    return { label: s, value: p.reduce((t, v) => t + v, 0) / p.length, note: `${rs.length} names · best ${str(best.ticker)} ${pct(best.prediction, 2)}` };
  }).sort((a, b) => b.value - a.value);
  return (
    <div>
      <Diverging rows={items} format={(v) => pct(v, 2)} labelWidth={150} />
      <p className="ml-note">Average predicted 21-day return of the names in each sector. A model that only ranks sectors is a sector bet; check the within-sector spread before trusting it as stock selection.</p>
    </div>
  );
}

/** Weights and risk added up by sector, against an equal split across the names held. */
export function AllocSectors({ result }: ViewProps) {
  const w = out(result, "hrp_weight_vector");
  const risk = new Map(out(result, "risk_contribution_decomposition").map((r) => [str(r.asset), Math.max(0, n(r.risk_contribution) ?? 0)]));
  const rTot = [...risk.values()].reduce((t, v) => t + v, 0) || 1;
  const by = new Map<string, { w: number; r: number; k: number }>();
  for (const r of w) {
    const s = str(r.sector) || "Unknown", o = by.get(s) ?? { w: 0, r: 0, k: 0 };
    o.w += n(r.weight) ?? 0; o.r += (risk.get(str(r.asset)) ?? 0) / rTot; o.k += 1;
    by.set(s, o);
  }
  if (!by.size) return <Empty />;
  const rowsS = [...by.entries()].sort((a, b) => b[1].w - a[1].w);
  const max = Math.max(...rowsS.map(([, o]) => Math.max(o.w, o.r)), 1e-9);
  return (
    <div>
      <div className="wt">
        <div className="wt-h" style={{ gridTemplateColumns: "150px minmax(0, 1fr) 60px 70px" }}><span>Sector</span><span>Weight (bar) and risk share (tick)</span><span>Weight</span><span>Risk</span></div>
        {rowsS.map(([s, o]) => (
          <div key={s} className="wt-r" style={{ gridTemplateColumns: "150px minmax(0, 1fr) 60px 70px" }}>
            <b>{s}<em style={{ marginLeft: 6, color: "var(--text-4)", fontSize: 11 }}>{o.k}</em></b>
            <span className="wt-track"><i className="bar" style={{ width: `${(o.w / max) * 100}%` }} /><i className="tick" style={{ left: `${(o.r / max) * 100}%` }} /></span>
            <em className="num">{pct(o.w)}</em>
            <em className="num" style={{ color: o.r - o.w > 0.03 ? "var(--warn)" : undefined }}>{pct(o.r)}</em>
          </div>
        ))}
      </div>
      <p className="ml-note">The number after each sector is how many names it holds. A tick far right of its bar means the sector carries more risk than capital.</p>
    </div>
  );
}

/** Mean absolute SHAP per feature: the plain importance ranking behind the beeswarm. */
export function ShapImportance({ result }: ViewProps) {
  const rows = out(result, "shap_feature_importance");
  if (!rows.length) return <Empty />;
  const items = [...rows].filter((r) => isNum(r.mean_abs_shap)).sort((a, b) => (b.mean_abs_shap as number) - (a.mean_abs_shap as number))
    .map((r) => ({ label: label(str(r.feature)), value: r.mean_abs_shap as number, note: label(str(r.family)) }));
  return <RankList title="Feature importance" items={items} format={(v) => pct(v, 2)} top={15} />;
}

/** The regime history as a list of spells: when each state started, how long it lasted. */
export function RegimeSpells({ rows, result }: ViewProps) {
  const labels = ((result.meta as Row).state_labels ?? {}) as Record<string, string>;
  const keys = Object.keys(rows[0] ?? {}).filter((k) => /^state_\d+$/.test(k));
  if (!rows.length || !keys.length) return <Empty />;
  const spells: { state: string; from: string; to: string; days: number }[] = [];
  for (const r of rows) {
    const s = keys.reduce((a, k) => ((n(r[k]) ?? 0) > (n(r[a]) ?? 0) ? k : a), keys[0]);
    const last = spells[spells.length - 1];
    if (last && last.state === s) { last.to = str(r.date); last.days += 1; } else spells.push({ state: s, from: str(r.date), to: str(r.date), days: 1 });
  }
  const colour = (s: string) => (labels[s] === "Stress" ? "var(--stress)" : labels[s] === "Calm" ? "var(--calm)" : "var(--normal)");
  return (
    <div className="ml-table-wrap">
      <table className="ml-table">
        <thead><tr><th>State</th><th>From</th><th>To</th><th>Sessions</th></tr></thead>
        <tbody>
          {[...spells].reverse().slice(0, 20).map((sp) => (
            <tr key={`${sp.state}-${sp.from}`}><td><span className="dot" style={{ background: colour(sp.state) }} />{labels[sp.state] ?? label(sp.state)}</td><td className="num">{sp.from}</td><td className="num">{sp.to}</td><td className="num">{sp.days}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="ml-note">Most recent spells first; a spell is a run of sessions with the same most-likely state.</p>
    </div>
  );
}

/** Allocation by sector, with the same risk-share denominator as the sector report. */
export function AllocTreemap({ result }: ViewProps) {
  const weights = out(result, "hrp_weight_vector");
  const risks = out(result, "risk_contribution_decomposition");
  const total = risks.reduce((sum, r) => sum + Math.max(0, n(r.risk_contribution) ?? 0), 0);
  const risk = new Map(risks.filter((r) => isNum(r.risk_contribution)).map((r) => [str(r.asset), total > 0 ? Math.max(0, r.risk_contribution as number) / total : undefined]));
  return <Treemap title="Allocation by sector and name" sizeLabel="Weight" alternativeSizeLabel="Risk share" colorModes={[{ key: "risk-minus-weight", label: "Risk minus weight" }, { key: "risk", label: "Risk share" }]} format={(v) => pct(v, 1)} colorFormat={(v) => pct(v, 1)} items={weights.filter((r) => isNum(r.weight)).map((r) => {
    const share = risk.get(str(r.asset));
    const weight = r.weight as number;
    return {
      label: str(r.asset), group: str(r.sector) || "Unknown sector", size: weight, alternativeSize: share,
      colorValue: share === undefined ? undefined : share - weight,
      colors: { risk: share, "risk-minus-weight": share === undefined ? undefined : share - weight },
    };
  })} />;
}

export function ShapTreemap({ result }: ViewProps) {
  return <Treemap title="Feature contributions by family" sizeLabel="Mean absolute SHAP" colorLabel="Mean absolute SHAP" colorScale="sequential" format={(v) => pct(v, 2)} colorFormat={(v) => pct(v, 2)} items={out(result, "shap_feature_importance").filter((r) => isNum(r.mean_abs_shap)).map((r) => ({ label: label(str(r.feature)), group: label(str(r.family)) || "Unknown family", size: r.mean_abs_shap as number, colorValue: r.mean_abs_shap as number }))} />;
}
