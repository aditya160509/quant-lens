"use client";

import { createElement, useEffect, useMemo, useState } from "react";
import { Pause, Play } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { send } from "./api";
import { Treemap } from "@/charts/Treemap";
import { DataTable, Empty } from "@/kit/DataTable";
import { useStudies } from "@/modules/research/store";
import { Monogram, openQuickLook } from "@/kit/QuickLook";
import { Spark } from "@/charts/RankList";
import { shapeOf } from "@/kit/Snowflake";
import { first, isNum, label, out, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import type { Row } from "@/modules/research/types";
import { ScreenScatter, SensitivityStrip } from "./trust/Charts";
import { NearMisses, runOf, WhyHere } from "./trust/Explain";
import { SCREENER_BASE } from "./base";
import "./screen.css";
import "./filters/universe.css";

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
const SPARK: [string, number][] = [["1M", 31], ["3M", 92], ["1Y", 365]];

export function ScreenTable({ rows, result, opts }: ViewProps) {
  const runId = runOf(result)?.id;
  const detail = runId ? (row: Record<string, unknown>) => (typeof row.ticker === "string" ? createElement(WhyHere, { ticker: row.ticker, runId }) : null) : undefined;
  // Price sparkline per row over the chosen range, fetched for the names shown.
  const [days, setDays] = useState(() => { try { return Number(localStorage.getItem("screener-spark-days")) || 92; } catch { return 92; } });
  const tickers = useMemo(() => rows.map((r) => String(r.ticker ?? "")).filter(Boolean).slice(0, 1000), [rows]);
  const spark = useQuery({ queryKey: ["screener", "spark", days, tickers.join(",")], queryFn: () => send<Record<string, number[]>>("POST", "/sparklines", { tickers, days }), enabled: tickers.length > 0, staleTime: 600_000, retry: false }).data;
  const withTrend = useMemo(() => rows.map((r) => ({ ...r, shape: shapeOf(r), ...(spark ? { trend: spark[String(r.ticker)] ?? null } : {}) })), [rows, spark]);
  const pick = (d: number) => { setDays(d); try { localStorage.setItem("screener-spark-days", String(d)); } catch { /* storage blocked */ } };
  return (
    <>
      <div className="ub-seg spark-range" role="radiogroup" aria-label="Sparkline range">
        {SPARK.map(([l, d]) => <button key={l} type="button" role="radio" aria-checked={days === d} onClick={() => pick(d)}>{l}</button>)}
      </div>
      <DataTable rows={withTrend} opts={{ ...opts, viewKey: "screener:results", xlsx: `${SCREENER_BASE}/export/xlsx`, detail, lead: [...SCREEN_LEAD, "shape", "trend"], freeze: SCREEN_LEAD, sets: SCREEN_SETS }} />
    </>
  );
}

export const NearMissView = ({ result }: ViewProps) => <NearMisses result={result} />;
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

type Rrg = { benchmark: string; series: Record<string, { date: string; rs_ratio: number; rs_momentum: number }[]>; quadrant: Record<string, string> };
const SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC"];
const QUAD = ["Leading", "Weakening", "Lagging", "Improving"];

/** Relative rotation against SPY: RS-ratio across, RS-momentum up, a tail of recent weeks behind each name. */
const quadOf = (x: number, y: number) => (x >= 100 ? (y >= 100 ? "leading" : "weakening") : y >= 100 ? "improving" : "lagging");
const TRAIL = 8;

/** C4: relative rotation against SPY, a year of weeks; each name trails its last eight weeks, fading with age. Play or scrub through time. */
export function RrgView({ rows }: ViewProps) {
  const [etfs, setEtfs] = useState(false);
  const names = (etfs ? SECTOR_ETFS : rows.map((r) => String(r.ticker ?? "")).filter(Boolean).slice(0, 12));
  const q = useQuery({ queryKey: ["screener", "rrg", 52, names.join(",")], queryFn: () => send<Rrg>("GET", `/rrg?tickers=${names.join(",")}&benchmark=SPY&weeks=52`), enabled: names.length > 0, staleTime: 600_000, retry: false });
  const series = Object.entries(q.data?.series ?? {});
  const dates = [...new Set(series.flatMap(([, p]) => p.map((x) => x.date)))].sort();
  const [at, setAt] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const t = at ?? dates.length - 1;
  useEffect(() => {
    if (!playing) return;
    if (t >= dates.length - 1) { setPlaying(false); return; }
    const id = setTimeout(() => setAt(t + 1), 260);
    return () => clearTimeout(id);
  }, [playing, t, dates.length]);
  const all = series.flatMap(([, p]) => p);
  const reach = Math.max(2, ...all.map((p) => Math.max(Math.abs(p.rs_ratio - 100), Math.abs(p.rs_momentum - 100)))) * 1.1;
  const W = 640, H = 440, X = (v: number) => ((v - 100 + reach) / (2 * reach)) * W, Y = (v: number) => H - ((v - 100 + reach) / (2 * reach)) * H;
  const day = dates[t];
  return (
    <div className="rrg">
      <div className="rrg-bar">
        <div className="ub-seg" role="radiogroup" aria-label="Names">
          {([[false, "Top results"], [true, "Sector ETFs"]] as const).map(([v, l]) => <button key={l} type="button" role="radio" aria-checked={etfs === v} onClick={() => { setEtfs(v); setAt(null); }}>{l}</button>)}
        </div>
        {dates.length > 1 ? <>
          <button type="button" className="btn sm" onClick={() => { if (t >= dates.length - 1) setAt(Math.min(TRAIL, dates.length - 1)); setPlaying((p) => !p); }} aria-label={playing ? "Pause" : "Play the rotation"}>{playing ? <Pause size={11} /> : <Play size={11} fill="currentColor" />}{playing ? "Pause" : "Play"}</button>
          <input className="br-scrub" type="range" min={0} max={dates.length - 1} value={t} aria-label="Week" onChange={(e) => { setPlaying(false); setAt(Number(e.target.value)); }} />
          <span className="num rrg-day">{day}</span>
        </> : null}
      </div>
      {q.error ? <p className="err" role="alert">{(q.error as Error).message}</p> : null}
      {series.length ? (
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Relative rotation graph, week of ${day}`}>
          <rect x={W / 2} y={0} width={W / 2} height={H / 2} className="rrg-leading" />
          <rect x={W / 2} y={H / 2} width={W / 2} height={H / 2} className="rrg-weakening" />
          <rect x={0} y={H / 2} width={W / 2} height={H / 2} className="rrg-lagging" />
          <rect x={0} y={0} width={W / 2} height={H / 2} className="rrg-improving" />
          {[[QUAD[0], W - 8, 18, "end"], [QUAD[1], W - 8, H - 8, "end"], [QUAD[2], 8, H - 8, "start"], [QUAD[3], 8, 18, "start"]].map(([tx, x, y, a]) => <text key={String(tx)} x={x as number} y={y as number} textAnchor={a as "start" | "end"} className="rrg-q">{tx}</text>)}
          {series.map(([tk, pts]) => {
            const upto = pts.filter((p) => p.date <= day);
            const trail = upto.slice(-TRAIL);
            const last = trail[trail.length - 1];
            if (!last) return null;
            return (
              <g key={tk} className={`rrg-${quadOf(last.rs_ratio, last.rs_momentum)}`}>
                {trail.slice(1).map((p, i) => <line key={p.date} x1={X(trail[i].rs_ratio)} y1={Y(trail[i].rs_momentum)} x2={X(p.rs_ratio)} y2={Y(p.rs_momentum)} style={{ opacity: 0.15 + (0.85 * (i + 1)) / trail.length }} />)}
                <circle cx={X(last.rs_ratio)} cy={Y(last.rs_momentum)} r={5}><title>{`${tk}: ratio ${last.rs_ratio.toFixed(1)}, momentum ${last.rs_momentum.toFixed(1)} on ${last.date}`}</title></circle>
                <text x={X(last.rs_ratio) + 8} y={Y(last.rs_momentum) + 4}>{tk}</text>
              </g>
            );
          })}
        </svg>
      ) : q.isLoading ? <div className="skel-card" style={{ height: 320 }} aria-busy="true" /> : null}
    </div>
  );
}

const pick = (r: Row | undefined, keys: string[]) => keys.find((k) => r && isNum(r[k]));

/** One row per tested variant (offset, holding period, weekday): annual return, Sharpe and worst drawdown as bars, best Sharpe marked. */
export function VariantBars({ rows: all }: ViewProps) {
  const by = ["rebalance_offset_days", "offset_days", "holding_days", "weekday"].find((k) => all.some((r) => r[k] !== undefined && r[k] !== null && r[k] !== ""));
  const rows = by ? all.filter((r) => r[by] !== undefined && r[by] !== null && r[by] !== "") : [];
  const ret = pick(rows[0], ["annualized_return", "cagr", "return", "total_return"]);
  if (!by || !rows.length) return <DataTable rows={all} />;
  const cols = [["Return", ret, (v: number) => pct(v, 1)], ["Sharpe", "sharpe", (v: number) => v.toFixed(2)], ["Worst drawdown", "max_drawdown", (v: number) => pct(v, 1)]] as const;
  const max = (k: string | undefined) => Math.max(1e-9, ...rows.map((r) => (k && isNum(r[k]) ? Math.abs(r[k]) : 0)));
  const best = rows.reduce((a, r) => (isNum(r.sharpe) && (!isNum(a.sharpe) || r.sharpe > a.sharpe) ? r : a), rows[0]);
  const name = (v: unknown) => (by === "weekday" ? String(v) : `${v} ${by.endsWith("offset_days") ? "day offset" : "day hold"}`);
  return (
    <div className="vb">
      <div className="vb-row vb-head"><span />{cols.map(([l]) => <span key={l}>{l}</span>)}</div>
      {rows.map((r, i) => (
        <div key={i} className="vb-row" data-best={r === best}>
          <span className="vb-name">{name(r[by])}</span>
          {cols.map(([l, k, f]) => {
            const v = k ? r[k] : null;
            return <span key={l} className="vb-cell">{isNum(v) ? <><i className={v < 0 ? "down" : "up"} style={{ width: `${(Math.abs(v) / max(k)) * 100}%` }} /><b className="num">{f(v)}</b></> : <b className="miss">—</b>}</span>;
          })}
        </div>
      ))}
    </div>
  );
}

/** Turnover on each rebalance date as bars, with the trading cost it implied. */
export function TurnoverBars({ rows }: ViewProps) {
  const pts = rows.filter((r) => isNum(r.turnover) && (r.rebalance === true || r.rebalance === "Yes" || (r.turnover as number) > 0));
  if (!pts.length) return <DataTable rows={rows} />;
  const top = Math.max(1e-9, ...pts.map((r) => r.turnover as number));
  const avg = pts.reduce((s, r) => s + (r.turnover as number), 0) / pts.length;
  const cost = rows.reduce((s, r) => s + (isNum(r.cost_fraction) ? r.cost_fraction : 0), 0);
  return (
    <div className="tb">
      <div className="tb-stats"><span>Rebalances <b className="num">{pts.length}</b></span><span>Average turnover <b className="num">{pct(avg, 0)}</b></span><span>Total cost <b className="num">{pct(cost, 2)}</b></span></div>
      <div className="tb-bars">{pts.map((r, i) => <i key={i} style={{ height: `${((r.turnover as number) / top) * 100}%` }} title={`${String(r.date).slice(0, 10)} · ${pct(r.turnover as number, 0)}`} />)}</div>
      <div className="ts-g-axis num" style={{ paddingLeft: 0 }}><span>{String(pts[0].date).slice(0, 10)}</span><span>{String(pts[pts.length - 1].date).slice(0, 10)}</span></div>
    </div>
  );
}

const QL_SCORES: [string, string][] = [["score", "Score"], ["valuation", "Valuation"], ["quality", "Quality"], ["momentum", "Momentum"], ["low_vol", "Low volatility"]];

/** The run's lead name: price path, percentile scores as bars, and the one-line thesis; opens the full quick look. */
export function QuickLookCardView({ result }: ViewProps) {
  const c = first(result, "quick_look_card");
  if (!c?.ticker) return <Empty text="No name to show." />;
  const t = String(c.ticker);
  const path = ((c.chart_windows as Record<string, { close: number }[]> | undefined)?.["1Y"] ?? []).map((p) => p.close);
  const change = path.length > 1 ? path[path.length - 1] / path[0] - 1 : null;
  return (
    <div className="qlc">
      <button type="button" className="qlc-head" onClick={() => openQuickLook(t)}>
        <Monogram ticker={t} />
        <span><b>{t}</b><small>{String(c.sector ?? "Unknown sector")}</small></span>
        <span className="qlc-px num">{isNum(c.price) ? c.price.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "–"}{change !== null ? <em className={change >= 0 ? "up" : "down"}>{change >= 0 ? "+" : ""}{(change * 100).toFixed(1)}% 1Y</em> : null}</span>
      </button>
      {path.length > 1 ? <Spark values={path} width={560} height={64} className="qlc-spark" color={change !== null && change < 0 ? "var(--down)" : "var(--up)"} /> : null}
      <div className="qlc-bars">
        {QL_SCORES.map(([k, l]) => isNum(c[k]) ? <div key={k}><span>{l}</span><i><b style={{ width: `${Math.max(0, Math.min(100, c[k] as number))}%` }} /></i><em className="num">{(c[k] as number).toFixed(0)}</em></div> : null)}
      </div>
      {c.thesis ? <p className="qlc-thesis">{String(c.thesis)}</p> : null}
    </div>
  );
}
