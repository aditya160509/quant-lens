"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import { Bars } from "@/charts/Bars";
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
  unmanaged: "Unmanaged", vol_targeted: "Volatility-targeted", regime_filtered: "Regime-filtered", constant_exposure: "Constant exposure",
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

/* ---------------------------------------------------------------- Alpha */

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
        label: nm(r.model), value: r[metric] as number, color: r.primary ? "var(--accent)" : r === best ? "var(--text-3)" : "var(--line-3)",
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

/** Ten portfolios sorted by prediction: a real signal climbs from the bottom bin to the top, under both weightings. */
export function AlphaDeciles({ rows }: ViewProps) {
  const models = useMemo(() => [...new Set(rows.map((r) => str(r.model)))], [rows]);
  const [model, setModel] = useState<string | null>(null);
  const [w, setW] = useState("equal");
  if (!rows.length) return <Empty />;
  const m = model ?? (models.includes("ensemble") ? "ensemble" : models[0]);
  const weights = [...new Set(rows.map((r) => str(r.weighting)))];
  const ww = weights.includes(w) ? w : weights[0];
  const sel = rows.filter((r) => str(r.model) === m && str(r.weighting) === ww).sort((a, b) => (n(a.bin) ?? 0) - (n(b.bin) ?? 0));
  const spread = sel.length > 1 ? (n(sel[sel.length - 1].mean_return) ?? 0) - (n(sel[0].mean_return) ?? 0) : null;
  return (
    <div>
      <div className="ml-bar">
        {models.length > 1 ? <select className="input" style={{ height: 28, width: "auto" }} aria-label="Model" value={m} onChange={(e) => setModel(e.target.value)}>{models.map((x) => <option key={x} value={x}>{nm(x)}</option>)}</select> : null}
        {weights.length > 1 ? <Segmented<string> label="Weighting" value={ww} onChange={setW} options={weights.map((x) => ({ value: x, label: label(x) }))} /> : null}
        <span className="ml-sub" style={{ margin: 0 }}>Top minus bottom: <b className="num" style={{ color: tone(spread) }}>{signed(spread, (x) => pct(x, 2))}</b> per rebalance</span>
      </div>
      <Bars bars={sel.map((r) => ({ label: `D${str(r.bin)}`, value: n(r.mean_return) ?? 0 }))} height={210} yLabel="Mean forward return per rebalance" format={(v) => pct(v, 2)} />
    </div>
  );
}

/** Growth of $1 for each model after trading costs, held-out period only. */
export function AlphaNetCurve({ rows }: ViewProps) {
  const { data, keys } = useMemo(() => pivot(rows, "date", "model", "equity"), [rows]);
  if (!rows.length) return <Empty />;
  return <TimeSeries data={data} x="date" height={240} yLabel="Growth of $1, net of costs" series={keys.map((k) => ({ key: k, label: nm(k), width: k === "ensemble" ? 2.2 : 1.4, muted: k !== "ensemble" && k !== "ic_composite" }))} refLines={[{ y: 1, color: "var(--line-3)", dash: true }]} />;
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
  return (
    <div className="ml-shares">
      {sorted.map((r) => (
        <div key={str(r.family)}>
          <span>{label(str(r.family))}</span>
          <span className="ml-share-bar"><i style={{ width: `${((r.mean_abs_shap as number) / total) * 100}%` }} /></span>
          <b className="num">{pct((r.mean_abs_shap as number) / total, 0)}</b>
          <em>{(Array.isArray(r.features) ? (r.features as string[]) : []).slice(0, 6).map(label).join(", ")}</em>
        </div>
      ))}
    </div>
  );
}

/** Validation IC across LightGBM–Ridge blends; the chosen blend is the one validation preferred, never the test. */
export function AlphaEnsemble({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => (n(a.lightgbm) ?? 0) - (n(b.lightgbm) ?? 0));
  const chosen = rows.find((r) => r.chosen);
  return (
    <div>
      <Stats items={[["Chosen blend", chosen ? `${pct(chosen.lightgbm, 0)} LightGBM` : "–"], ["Validation IC", f3(chosen?.validation_ic)]]} />
      <Bars bars={sorted.map((r) => ({ label: pct(r.lightgbm, 0), value: n(r.validation_ic) ?? 0, color: r.chosen ? "var(--accent)" : "var(--line-3)" }))} signed={false} height={180} yLabel="Validation IC" format={(v) => v.toFixed(3)} />
      <p className="ml-note">x-axis: LightGBM&apos;s share of the blend, the rest Ridge.</p>
    </div>
  );
}

/* ---------------------------------------------------------------- Volatility and risk */

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

/** VaR and expected shortfall by horizon, with how often the one-day VaR was actually breached out of sample. */
export function RiskVarEs({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].sort((a, b) => (n(a.horizon) ?? 0) - (n(b.horizon) ?? 0) || (n(a.level) ?? 0) - (n(b.level) ?? 0));
  return (
    <div className="ml-table-wrap">
      <table className="ml-table">
        <thead><tr><th>Horizon</th><th>Confidence</th><th>VaR</th><th>ES</th><th>Breaches (expected)</th><th>Kupiec p</th></tr></thead>
        <tbody>
          {sorted.map((r) => {
            const p = n(r.kupiec_p_value);
            return (
              <tr key={`${str(r.horizon)}-${str(r.level)}`}>
                <td className="num">{str(r.horizon)}d</td><td className="num">{pct(r.level, 0)}</td>
                <td className="num" style={{ color: "var(--down)" }}>{pct(r.var, 2)}</td><td className="num" style={{ color: "var(--down)" }}>{pct(r.es, 2)}</td>
                <td className="num">{isNum(r.oos_breach_rate) ? `${pct(r.oos_breach_rate, 1)} (${pct(r.expected_breach_rate, 0)})` : "–"}</td>
                <td className="num" style={{ color: p === null ? undefined : p < 0.05 ? "var(--down)" : "var(--up)" }}>{p === null ? "–" : p.toFixed(3)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="ml-note">Kupiec p below 0.05 means the breach rate is inconsistent with the stated confidence: the VaR is miscalibrated.</p>
    </div>
  );
}

/** Any set of strategies compared on return, risk and drawdown, controls dimmed. */
export function StrategyCompare({ rows, feature }: ViewProps) {
  if (!rows.length) return <Empty />;
  const key = rows[0] && "strategy" in rows[0] ? "strategy" : "model";
  const primary = rows[0];
  const sorted = [...rows].sort((a, b) => (n(b.sharpe) ?? -9) - (n(a.sharpe) ?? -9));
  return (
    <div>
      <Bars bars={sorted.filter((r) => isNum(r.sharpe)).map((r) => ({ label: nm(r[key]), value: r.sharpe as number, color: r === primary ? "var(--accent)" : "var(--line-3)" }))} signed={false} height={190} yLabel="Annualised Sharpe" format={(v) => v.toFixed(2)} />
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

/** Each weight with the range it takes across bootstrap resamples: a wide band means the estimate is noise. */
export function AllocStability({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  const sorted = [...rows].filter((r) => isNum(r.weight)).sort((a, b) => (b.weight as number) - (a.weight as number));
  const max = Math.max(...sorted.map((r) => n(r.p95) ?? (r.weight as number)), 1e-9);
  const draws = n(sorted[0]?.draws);
  const unstable = sorted.filter((r) => (n(r.p95) ?? 0) - (n(r.p05) ?? 0) > Math.max(0.05, (r.weight as number))).length;
  return (
    <div>
      <Stats items={[["Names held", String(sorted.filter((r) => (r.weight as number) > 1e-4).length)], ["Largest weight", pct(sorted[0]?.weight)], ["Unstable weights", String(unstable), unstable ? "var(--warn)" : "var(--up)", "Bands wider than the weight itself (or 5 points)"], ["Resamples", String(draws ?? "–")]]} />
      <div className="ml-bands">
        {sorted.map((r) => (
          <div key={str(r.asset)}>
            <b>{str(r.asset)}</b>
            <span className="ml-band-track" title={`5–95%: ${pct(r.p05)} – ${pct(r.p95)}`}>
              <i className="band" style={{ left: `${((n(r.p05) ?? 0) / max) * 100}%`, width: `${(((n(r.p95) ?? 0) - (n(r.p05) ?? 0)) / max) * 100}%` }} />
              <i className="w" style={{ width: `${((r.weight as number) / max) * 100}%` }} />
            </span>
            <em className="num">{pct(r.weight)}</em>
          </div>
        ))}
      </div>
      <p className="ml-note">Bar: weight today. Band: 5th–95th percentile of the weight when the estimation window is resampled.</p>
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
