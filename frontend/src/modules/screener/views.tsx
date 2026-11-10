"use client";

import { createElement } from "react";
import { Treemap } from "@/charts/Treemap";
import { DataTable } from "@/kit/DataTable";
import { useStudies } from "@/modules/research/store";
import { openQuickLook } from "@/kit/QuickLook";
import { Spark } from "@/charts/RankList";
import { isNum, label, out, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import { ScreenScatter, SensitivityStrip } from "./trust/Charts";
import { NearMisses, RunInfo, runOf, ScreenDiff, WhyHere } from "./trust/Explain";
import { SCREENER_BASE } from "./base";
import "./screen.css";

/** Every passing name as a rectangle: area is market cap, colour is the 1-month return, grouped by sector. */
export function ScreenTreemap({ result }: ViewProps) {
  const items = out(result, "ranked_screener_table").filter((r) => isNum(r.market_cap) && r.market_cap > 0).map((r) => ({
    label: String(r.ticker), group: typeof r.sector === "string" && r.sector ? r.sector : "Unknown sector",
    size: r.market_cap as number, colorValue: isNum(r.return_1m) ? r.return_1m : undefined,
  }));
  const filterTo = (sector: string) => useStudies.setState((st) => ({ forms: { ...st.forms, sc01: { ...st.forms.sc01, sector } } }));
  return <Treemap onFilterGroup={filterTo} title="Passing names by sector" sizeLabel="Market cap" colorLabel={`Mean ${label("return_1m").toLowerCase()}`} colorAggregate="mean" format={(v) => `$${(v / 1e9).toLocaleString("en-US", { maximumFractionDigits: 0 })}B`} colorFormat={(v) => pct(v, 1)} items={items} />;
}

const SCREEN_LEAD = ["rank", "ticker", "company_name"];
/** Column sets as tabs, in the order screeners use them. */
const SCREEN_SETS: Record<string, string[]> = {
  Overview: ["sector", "industry", "country", "market_cap", "price_usd", "return_1d", "return_1m", "trend_3m", "core_quant_score"],
  Performance: ["return_1d", "return_1m", "return_6m", "trend_3m", "prox52", "max_drawdown_252d", "realized_vol_63d", "momentum_percentile"],
  Valuation: ["market_cap", "trailing_pe", "forward_pe", "pb_ratio", "ps_ratio", "p_cf", "ev_ebit", "ev_ebitda", "valuation_percentile"],
  Growth: ["revenue_growth_yoy", "eps_growth_yoy", "qtr_sales_yoy", "qtr_profit_yoy"],
  Health: ["roe", "interest_coverage", "altman_z_score", "piotroski_passed", "piotroski_available_criteria", "quality_percentile"],
  Technical: ["price", "adx_14", "macd_histogram", "bollinger_pct_b", "atr_pct_price", "beta_252", "vratio", "dollar_volume_20d"],
  Scores: ["core_quant_score", "sector_relative_score", "quality_percentile", "valuation_percentile", "momentum_percentile", "low_vol_percentile"],
  Trust: ["data_coverage", "statement_age_days", "price_observation_date", "market_cap_basis", "fundamental_basis", "quote_currency"],
};

/** The results table: its arrangement lives in the URL and in saved views, and a row opens its reasons. */
export function ScreenTable({ rows, result, opts }: ViewProps) {
  const runId = runOf(result)?.id;
  const detail = runId ? (row: Record<string, unknown>) => (typeof row.ticker === "string" ? createElement(WhyHere, { ticker: row.ticker, runId }) : null) : undefined;
  return <DataTable rows={rows} opts={{ ...opts, viewKey: "screener:results", xlsx: `${SCREENER_BASE}/export/xlsx`, detail, lead: SCREEN_LEAD, sets: SCREEN_SETS }} />;
}

export const NearMissView = ({ result }: ViewProps) => <NearMisses result={result} />;
export const RunView = ({ result }: ViewProps) => <RunInfo result={result} />;
export const DiffView = ({ result, feature }: ViewProps) => <ScreenDiff result={result} featureId={feature.id} />;
export const ScatterView = ({ rows, feature }: ViewProps) => <ScreenScatter rows={rows} feature={feature} />;
export const SensitivityView = ({ result }: ViewProps) => <SensitivityStrip result={result} />;

/** Names left after each filter as a shrinking bar; the step that removed the most is the bottleneck. */
export function FunnelView({ rows }: ViewProps) {
  const steps = rows.filter((r) => isNum(r.remaining));
  if (!steps.length) return null;
  const top = Math.max(1, ...steps.map((r) => r.remaining as number));
  const worst = Math.max(0, ...steps.map((r) => (isNum(r.removed) ? r.removed : 0)));
  return (
    <ol className="fn">
      {steps.map((r, i) => {
        const removed = isNum(r.removed) ? r.removed : 0;
        const neck = removed > 0 && (r.bottleneck === true || removed === worst);
        return (
          <li key={i} data-neck={neck}>
            <span className="fn-name">{String(r.stage ?? r.key ?? `Step ${i + 1}`)}</span>
            <span className="fn-bar"><i style={{ width: `${((r.remaining as number) / top) * 100}%` }} /></span>
            <span className="fn-left num">{(r.remaining as number).toLocaleString()}</span>
            <span className="fn-cut num">{removed ? `−${removed.toLocaleString()}` : ""}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** Each passing name as a small card with its 3-month trend, price and 1-month move; a card opens the drawer. */
export function ChartGrid({ rows }: ViewProps) {
  const shown = rows.slice(0, 120);
  return (
    <div className="cg">
      {shown.map((r) => {
        const t = String(r.ticker ?? "");
        const trend = Array.isArray(r.trend_3m) ? (r.trend_3m as unknown[]).filter(isNum) : [];
        const m = isNum(r.return_1m) ? r.return_1m : null;
        return (
          <button type="button" key={t} className="cg-card" onClick={() => openQuickLook(t)}>
            <span className="cg-top"><b>{t}</b><em className={m === null ? "" : m >= 0 ? "up" : "down"}>{m === null ? "" : pct(m, 1)}</em></span>
            <span className="cg-name">{String(r.company_name ?? r.sector ?? "")}</span>
            {trend.length > 1 ? <Spark values={trend} width={180} height={44} color={trend[trend.length - 1] >= trend[0] ? "var(--up)" : "var(--down)"} className="cg-spark" /> : <span className="cg-none">No trend</span>}
            <span className="cg-foot num">{isNum(r.price) ? r.price.toLocaleString("en-US", { maximumFractionDigits: 2 }) : ""}{isNum(r.core_quant_score) ? <i>Score {r.core_quant_score.toFixed(0)}</i> : null}</span>
          </button>
        );
      })}
      {rows.length > shown.length ? <p className="cg-more">{rows.length - shown.length} more in the table</p> : null}
    </div>
  );
}
