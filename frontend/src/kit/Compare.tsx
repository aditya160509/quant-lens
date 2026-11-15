"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useQueries } from "@tanstack/react-query";
import { Link2, X } from "lucide-react";
import toast from "react-hot-toast";
import { Heatmap } from "@/charts/Heatmap";
import { Radar } from "@/charts/Radar";
import { TimeSeries } from "@/charts/TimeSeries";
import { isNum } from "@/modules/research/format";
import { Segmented } from "@/workspace/ui";
import { MAX_COMPARE, useQuickLook } from "./QuickLook";
import { statementsQuery, useBarsMany, useCompare, type Bars, type Compare } from "./QuickLookData";

export type CompareTab = "price" | "returns" | "fundamentals" | "scores" | "ranking";
const TABS: { id: CompareTab; label: string }[] = [{ id: "price", label: "Price" }, { id: "returns", label: "Returns" }, { id: "fundamentals", label: "Fundamentals" }, { id: "scores", label: "Scores" }, { id: "ranking", label: "Ranking" }];

const UNKNOWN = "Unknown";
const LABEL: Record<string, string> = { price: "Price", market_cap: "Mkt cap", return_1m: "1M return", return_12m: "12M return", trailing_pe: "P/E", pb_ratio: "P/B", ev_ebitda: "EV/EBITDA", fcf_yield: "FCF yield", roe: "ROE", net_margin: "Net margin", debt_equity: "Debt / equity", revenue_growth_yoy: "Rev growth", realized_vol_63d: "Volatility 63d", beta_252: "Beta", core_quant_score: "Score", valuation_percentile: "Valuation", quality_percentile: "Quality", momentum_percentile: "Momentum", low_vol_percentile: "Low volatility" };
const PCT = new Set(["return_1m", "return_12m", "fcf_yield", "roe", "net_margin", "revenue_growth_yoy", "realized_vol_63d"]);
const WHOLE = new Set(["core_quant_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile"]);
// Which way is better per metric; unlisted rows (price, size) are not judged.
const LOWER = new Set(["trailing_pe", "pb_ratio", "ev_ebitda", "debt_equity", "realized_vol_63d", "beta_252"]);
const HIGHER = new Set(["return_1m", "return_12m", "fcf_yield", "roe", "net_margin", "revenue_growth_yoy", ...WHOLE]);
const dirOf = (c: string) => (LOWER.has(c) ? -1 : HIGHER.has(c) ? 1 : 0);

const pctText = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;
const cell = (c: string, v: unknown): ReactNode => (!isNum(v) ? UNKNOWN : PCT.has(c) ? pctText(v) : c === "market_cap" ? v.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 }) : WHOLE.has(c) ? v.toFixed(0) : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const COLORS = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)", "var(--c7)", "var(--c8)"];

/** Best and worst value of a judged metric among the compared names. */
function edges(c: string, rows: Compare["rows"]) {
  const d = dirOf(c);
  const vals = rows.map((r) => r[c]).filter(isNum);
  if (!d || vals.length < 2 || Math.max(...vals) === Math.min(...vals)) return null;
  return { best: d > 0 ? Math.max(...vals) : Math.min(...vals), worst: d > 0 ? Math.min(...vals) : Math.max(...vals) };
}

/** Wins per name across every judged metric, most first. */
function wins(data: Compare) {
  const judged = data.columns.filter((c) => edges(c, data.rows));
  const count = new Map(data.rows.map((r) => [r.ticker, 0]));
  const leaders = judged.map((c) => { const e = edges(c, data.rows)!; const lead = data.rows.find((r) => r[c] === e.best)!; count.set(lead.ticker, (count.get(lead.ticker) ?? 0) + 1); return { c, lead: lead.ticker, value: e.best }; });
  return { judged, leaders, totals: [...count].sort((a, b) => b[1] - a[1]) };
}

export function ComparePanel() {
  const { basket, toggleBasket, setBasket, open, ctab, setCtab } = useQuickLook();
  const q = useCompare(basket);
  if (basket.length < 2) return <p className="ql-none">Tick two to {MAX_COMPARE} names in any table and press C{basket.length ? `; ${basket[0]} is in` : ""}</p>;
  const w = q.data ? wins(q.data) : null;
  const share = () => {
    const u = new URL(location.href);
    u.searchParams.set("compare", basket.join(","));
    u.searchParams.set("ctab", ctab);
    u.searchParams.delete("stock");
    void navigator.clipboard?.writeText(u.toString()).then(() => toast.success("Compare link copied"));
  };
  return (
    <div className="cmp">
      <div className="cmp-head">
        <div className="cmp-names">
          {basket.map((t, i) => (
            <span key={t} className="cmp-name"><i style={{ background: COLORS[i % COLORS.length] }} /><button className="ql-link" onClick={() => open(t, "overview")}>{t}</button><button className="ql-x" aria-label={`Remove ${t}`} onClick={() => toggleBasket(t)}><X size={10} /></button></span>
          ))}
        </div>
        <button className="btn sm ghost" onClick={share}><Link2 size={12} />Copy link</button>
        <button className="btn sm ghost" onClick={() => setBasket([])}>Clear</button>
      </div>
      {w && w.judged.length ? <p className="cmp-verdict"><b>{w.totals[0][0]}</b> leads on {w.totals[0][1]} of {w.judged.length} metrics{w.totals[1] ? `; ${w.totals[1][0]} on ${w.totals[1][1]}` : ""}</p> : null}
      <div className="ql-tabs cmp-tabs" role="tablist" aria-label="Compare views">
        {TABS.map((t) => <button key={t.id} role="tab" aria-selected={ctab === t.id} onClick={() => setCtab(t.id)}>{t.label}</button>)}
      </div>
      {ctab === "price" ? <PriceTab tickers={basket} data={q.data} loading={q.isLoading} error={q.error as Error | null} />
        : ctab === "returns" ? <ReturnsTab tickers={basket} />
        : ctab === "fundamentals" ? <FundamentalsTab tickers={basket} />
        : ctab === "scores" ? (q.data ? <ScoresTab data={q.data} /> : null)
        : q.data && w ? <RankingTab data={q.data} w={w} /> : null}
    </div>
  );
}

const RANGES: { value: number; label: string }[] = [{ value: 92, label: "3M" }, { value: 183, label: "6M" }, { value: 365, label: "1Y" }, { value: 1095, label: "3Y" }, { value: 1825, label: "5Y" }];

/** Closes rebased to 100 at the start, SPY drawn as the reference, then every metric side by side with the sector medians. */
function PriceTab({ tickers, data, loading, error }: { tickers: string[]; data?: Compare; loading: boolean; error: Error | null }) {
  const [days, setDays] = useState(365);
  const names = useMemo(() => [...tickers, ...(tickers.includes("SPY") ? [] : ["SPY"])], [tickers]);
  const qs = useBarsMany(names, days);
  const series = useMemo(() => {
    const by = new Map<string, Record<string, number | string>>();
    qs.forEach((q, i) => {
      const bars = q.data?.bars ?? [];
      const base = bars.find((b) => b.close > 0)?.close;
      if (base) bars.forEach((b) => { const r = by.get(b.time) ?? { date: b.time }; r[names[i]] = (b.close / base) * 100; by.set(b.time, r); });
    });
    return [...by.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [qs, names]);
  return (
    <>
      <div className="cmp-row"><Segmented<number> label="Range" value={days} options={RANGES} onChange={setDays} /></div>
      {series.length > 1 ? <TimeSeries data={series} series={names.map((t, i) => ({ key: t, label: t, color: t === "SPY" && !tickers.includes("SPY") ? "var(--text-3)" : COLORS[i % COLORS.length], dash: t === "SPY" && !tickers.includes("SPY") }))} height={280} refLines={[{ y: 100, label: "" }]} format={(v) => v.toFixed(0)} directLabels /> : qs.some((q) => q.isLoading) ? <p className="ql-state" role="status">Loading</p> : null}
      {loading ? <p className="ql-state" role="status">Loading</p> : error ? <p className="ql-state err" role="alert">{error.message}</p> : data ? (
        <div className="ql-scroll">
          <table className="ql-table ql-cmp">
            <thead><tr><th>Metric</th>{data.rows.map((r) => <th key={r.ticker} className="r">{r.ticker}</th>)}{(data.medians ?? []).map((m) => <th key={m.label} className="r cmp-med" title={`${m.n} names`}>{m.label}</th>)}</tr></thead>
            <tbody>
              <tr><td>Name</td>{data.rows.map((r) => <td key={r.ticker} className="r ql-nm">{r.company_name ?? UNKNOWN}</td>)}{(data.medians ?? []).map((m) => <td key={m.label} />)}</tr>
              <tr><td>Sector</td>{data.rows.map((r) => <td key={r.ticker} className="r ql-nm">{r.sector ?? UNKNOWN}</td>)}{(data.medians ?? []).map((m) => <td key={m.label} />)}</tr>
              {data.columns.map((c) => {
                const e = edges(c, data.rows);
                return <tr key={c}><td>{LABEL[c] ?? c}</td>{data.rows.map((r) => <td key={r.ticker} className={`r num${e && r[c] === e.best ? " ql-best" : e && r[c] === e.worst ? " ql-worst" : ""}`}>{cell(c, r[c])}</td>)}{(data.medians ?? []).map((m) => <td key={m.label} className="r num cmp-med">{cell(c, m[c])}</td>)}</tr>;
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}

/** Month-end and year-end closes to returns; "against SPY" subtracts SPY's return for the same period. */
function periodReturns(bars: Bars["bars"], key: (d: string) => string) {
  const ends = new Map<string, number>();
  bars.forEach((b) => { if (b.close > 0) ends.set(key(b.time), b.close); });
  const ks = [...ends.keys()];
  return new Map(ks.slice(1).map((k, i) => [k, ends.get(k)! / ends.get(ks[i])! - 1]));
}

function ReturnsTab({ tickers }: { tickers: string[] }) {
  const [rel, setRel] = useState<"abs" | "rel">("abs");
  const names = useMemo(() => [...tickers, ...(tickers.includes("SPY") ? [] : ["SPY"])], [tickers]);
  const qs = useBarsMany(names, 1825);
  const grids = useMemo(() => {
    const bars = qs.map((q) => q.data?.bars ?? []);
    if (bars.some((b, i) => !b.length && qs[i].isLoading)) return null;
    const month = bars.map((b) => periodReturns(b, (d) => d.slice(0, 7)));
    const year = bars.map((b) => periodReturns(b, (d) => d.slice(0, 4)));
    const spy = names.indexOf("SPY");
    const build = (maps: Map<string, number>[], keep: number) => {
      const cols = [...new Set(maps.flatMap((m) => [...m.keys()]))].sort().slice(-keep);
      const rows = rel === "rel" ? names.filter((n) => n !== "SPY") : names;
      return { cols, rows, values: rows.map((n) => cols.map((c) => { const v = maps[names.indexOf(n)].get(c); const s = maps[spy]?.get(c); return isNum(v) ? (rel === "rel" ? (isNum(s) ? v - s : null) : v) : null; })) };
    };
    return { month: build(month, 12), year: build(year, 6) };
  }, [qs, names, rel]);
  if (!grids) return <p className="ql-state" role="status">Loading</p>;
  const mon = (k: string) => new Date(`${k}-15`).toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  return (
    <>
      <div className="cmp-row"><Segmented<"abs" | "rel"> label="Returns" value={rel} options={[{ value: "abs", label: "Return" }, { value: "rel", label: "Against SPY" }]} onChange={setRel} /></div>
      <h4 className="cmp-h">Last 12 months</h4>
      <Heatmap rows={grids.month.rows} cols={grids.month.cols.map(mon)} values={grids.month.values} centered format={(v) => pctText(v, 1)} />
      <h4 className="cmp-h">By year</h4>
      <Heatmap rows={grids.year.rows} cols={grids.year.cols} values={grids.year.values} centered format={(v) => pctText(v, 1)} />
    </>
  );
}

/** Any statement line per period, one bar per name: grouped side by side or stacked. */
function FundamentalsTab({ tickers }: { tickers: string[] }) {
  const [period, setPeriod] = useState<"annual" | "quarterly">("annual");
  const [mode, setMode] = useState<"grouped" | "stacked">("grouped");
  const qs = useQueries({ queries: tickers.map((t) => statementsQuery(t, period)) });
  const lines = useMemo(() => {
    const seen = new Map<string, string>();
    qs.forEach((q) => q.data?.lines.forEach((l) => seen.set(l.key, l.label)));
    return [...seen];
  }, [qs]);
  const [pick, setPick] = useState<string | null>(null);
  const line = pick && lines.some(([k]) => k === pick) ? pick : lines[0]?.[0];
  // Periods align across companies by fiscal year (annual) or calendar quarter (quarterly).
  const keyOf = (d: string) => (period === "annual" ? d.slice(0, 4) : `${d.slice(0, 4)} Q${Math.floor((Number(d.slice(5, 7)) - 1) / 3) + 1}`);
  const table = useMemo(() => {
    const by = tickers.map((_, i) => {
      const s = qs[i].data;
      const l = s?.lines.find((x) => x.key === line);
      return new Map((s?.periods ?? []).map((p, j) => [keyOf(p), l?.values[j] ?? null]));
    });
    const cols = [...new Set(by.flatMap((m) => [...m.keys()]))].sort().slice(period === "annual" ? -5 : -8);
    return { cols, values: by.map((m) => cols.map((c) => m.get(c) ?? null)) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qs, tickers, line, period]);
  if (qs.some((q) => q.isLoading)) return <p className="ql-state" role="status">Loading</p>;
  if (!line) return <p className="ql-none">No statements held for these names</p>;
  const flat = table.values.flat().filter(isNum);
  const sums = table.cols.map((_, j) => table.values.reduce((a, r) => a + Math.max(0, r[j] ?? 0), 0));
  const top = mode === "stacked" ? Math.max(...sums, 1e-9) : Math.max(0, ...flat), bot = mode === "stacked" ? 0 : Math.min(0, ...flat);
  const span = top - bot || 1;
  const fmt = (v: number) => v.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 1 });
  return (
    <>
      <div className="cmp-row">
        <select className="cmp-select" value={line} onChange={(e) => setPick(e.target.value)} aria-label="Statement line">{lines.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <Segmented<"annual" | "quarterly"> label="Period" value={period} options={[{ value: "annual", label: "Yearly" }, { value: "quarterly", label: "Quarterly" }]} onChange={setPeriod} />
        <Segmented<"grouped" | "stacked"> label="Bars" value={mode} options={[{ value: "grouped", label: "Grouped" }, { value: "stacked", label: "Stacked" }]} onChange={setMode} />
      </div>
      <div className="cmp-bars" role="img" aria-label={`${lines.find(([k]) => k === line)?.[1]} by ${period === "annual" ? "year" : "quarter"}`}>
        {table.cols.map((c, j) => {
          let acc = 0;
          return (
            <div key={c} className="cmp-col">
              <div className={`cmp-plot ${mode}`}>
                <span className="cmp-zero" style={{ bottom: `${(-bot / span) * 100}%` }} />
                {tickers.map((t, i) => {
                  const v = table.values[i][j];
                  if (!isNum(v)) return mode === "grouped" ? <span key={t} className="cmp-slot" /> : null;
                  const h = (Math.abs(mode === "stacked" ? Math.max(0, v) : v) / span) * 100;
                  const b = mode === "stacked" ? (acc / span) * 100 : ((Math.min(0, v) - bot) / span) * 100;
                  if (mode === "stacked") acc += Math.max(0, v);
                  return <span key={t} className="cmp-slot"><i title={`${t} ${c}: ${fmt(v)}`} style={{ bottom: `${b}%`, height: `${h}%`, background: COLORS[i % COLORS.length], opacity: v < 0 ? 0.55 : 1 }} /></span>;
                })}
              </div>
              <span className="cmp-x">{c}</span>
            </div>
          );
        })}
      </div>
      <div className="cmp-key">{tickers.map((t, i) => <span key={t}><i style={{ background: COLORS[i % COLORS.length] }} />{t}</span>)}</div>
    </>
  );
}

const SCORE_AXES = ["valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile", "core_quant_score"];

/** Each name's score shape overlaid on one radar. */
function ScoresTab({ data }: { data: Compare }) {
  const axes = SCORE_AXES.filter((k) => data.columns.includes(k)).map((k) => ({ key: k, label: LABEL[k] ?? k, format: (v: number) => v.toFixed(0) }));
  if (axes.length < 3) return <p className="ql-none">No scores held for these names</p>;
  return <Radar height={360} axes={axes} series={data.rows.map((r, i) => ({ label: r.ticker, color: COLORS[i % COLORS.length], values: Object.fromEntries(axes.map((a) => [a.key, isNum(r[a.key]) ? (r[a.key] as number) : null])) }))} />;
}

/** Who leads each judged metric, then wins per name. */
function RankingTab({ data, w }: { data: Compare; w: ReturnType<typeof wins> }) {
  const top = Math.max(1, ...w.totals.map(([, n]) => n));
  return (
    <div className="cmp-rank">
      <div className="cmp-tally">
        {w.totals.map(([t, n]) => <div key={t}><b>{t}</b><span className="cmp-tbar"><i style={{ width: `${(n / top) * 100}%`, background: COLORS[data.rows.findIndex((r) => r.ticker === t) % COLORS.length] }} /></span><em className="num">{n}</em></div>)}
      </div>
      <table className="ql-table">
        <thead><tr><th>Metric</th><th>Leader</th><th className="r">Value</th><th>Better</th></tr></thead>
        <tbody>{w.leaders.map((l) => <tr key={l.c}><td>{LABEL[l.c] ?? l.c}</td><td><b>{l.lead}</b></td><td className="r num">{cell(l.c, l.value)}</td><td className="ql-nm">{dirOf(l.c) > 0 ? "Higher" : "Lower"}</td></tr>)}</tbody>
      </table>
    </div>
  );
}
