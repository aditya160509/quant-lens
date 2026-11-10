"use client";

import { Check, Download, GitCompareArrows, Plus, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { create } from "zustand";
import { Radar } from "@/charts/Radar";
import { Spark } from "@/charts/RankList";
import { TimeSeries } from "@/charts/TimeSeries";
import { isNum } from "@/modules/research/format";
import { Chip, Segmented } from "@/workspace/ui";
import { pdfUrl, useCompare, useLookup, useStatements, type Lookup, type Stat } from "./QuickLookData";
import "./quicklook.css";

export const MAX_COMPARE = 25;
export type QuickTab = "overview" | "ratios" | "health" | "peers" | "financials" | "compare";

type QuickLookStore = {
  ticker: string | null;
  tab: QuickTab;
  range: string;
  basket: string[];
  open: (ticker: string, tab?: QuickTab) => void;
  close: () => void;
  setTab: (tab: QuickTab) => void;
  setRange: (range: string) => void;
  toggleBasket: (ticker: string) => void;
  setBasket: (tickers: string[]) => void;
};

/** One drawer for the whole workspace: any table, chart or search row opens a name with `openQuickLook(ticker)`. */
export const useQuickLook = create<QuickLookStore>()((set) => ({
  ticker: null, tab: "overview", range: "1Y", basket: [],
  open: (ticker, tab) => set((s) => ({ ticker: ticker.toUpperCase(), tab: tab ?? (s.ticker === ticker.toUpperCase() ? s.tab : "overview") })),
  close: () => set({ ticker: null }),
  setTab: (tab) => set({ tab }),
  setRange: (range) => set({ range }),
  toggleBasket: (ticker) => set((s) => ({ basket: s.basket.includes(ticker) ? s.basket.filter((t) => t !== ticker) : s.basket.length < MAX_COMPARE ? [...s.basket, ticker] : s.basket })),
  setBasket: (tickers) => set({ basket: [...new Set(tickers)].slice(0, MAX_COMPARE) }),
}));

export const openQuickLook = (ticker: string, tab?: QuickTab) => useQuickLook.getState().open(ticker, tab);

const UNKNOWN = "Unknown";
const pctText = (v: number | null | undefined, d = 1) => (isNum(v) ? `${(v * 100).toFixed(d)}%` : UNKNOWN);
const numText = (v: number | null | undefined, d = 2) => (isNum(v) ? v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : UNKNOWN);
const big = (v: number | null | undefined) => (isNum(v) ? v.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 }) : UNKNOWN);
const stat = (s: Pick<Stat, "unit" | "value">) => (s.unit === "pct" ? pctText(s.value) : numText(s.value));

export function Monogram({ ticker }: { ticker: string }) {
  return <span className="ql-mono" aria-hidden>{ticker.replace(/_.*/, "").slice(0, 2)}</span>;
}

const RANGES = ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y"];

export function QuickLook() {
  const { ticker, tab, basket, close, setTab, toggleBasket } = useQuickLook();
  const q = useLookup(ticker);
  const ref = useRef<HTMLElement>(null);
  const isOpen = ticker !== null;

  useEffect(() => {
    if (!isOpen) return;
    const opener = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !e.defaultPrevented) close(); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); opener?.focus?.(); };
  }, [isOpen, close]);

  if (!ticker) return null;
  const d = q.data;
  const inBasket = basket.includes(ticker);
  const tabs: { id: QuickTab; label: string }[] = [
    { id: "overview", label: "Overview" }, { id: "ratios", label: "Ratios" }, { id: "health", label: "Health" }, { id: "peers", label: "Peers" }, { id: "financials", label: "Financials" },
    ...(basket.length ? [{ id: "compare" as const, label: `Compare ${basket.length}` }] : []),
  ];
  return (
    <aside ref={ref} className="ql" role="dialog" aria-label={`${ticker} quick look`} tabIndex={-1}>
      <header className="ql-head">
        <Monogram ticker={ticker} />
        <div className="ql-title">
          <b>{ticker}</b><span>{d ? d.company_name ?? UNKNOWN : q.isLoading ? "" : UNKNOWN}</span>
          {d ? <small>{[d.sector, d.industry, d.exchange].filter(Boolean).join(" · ") || UNKNOWN}</small> : null}
        </div>
        <div className="ql-actions">
          <button className="btn sm" aria-pressed={inBasket} onClick={() => toggleBasket(ticker)} title={inBasket ? "Remove from compare" : "Add to compare"}>{inBasket ? <Check size={13} /> : <Plus size={13} />}Compare</button>
          <a className="btn sm" href={pdfUrl(ticker)} download title="One-page PDF"><Download size={13} />PDF</a>
          <button className="btn icon ghost" onClick={close} aria-label="Close quick look"><X size={15} /></button>
        </div>
      </header>
      <div className="ql-tabs" role="tablist" aria-label="Quick look sections">
        {tabs.map((t) => <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.id === "compare" ? <GitCompareArrows size={12} /> : null}{t.label}</button>)}
      </div>
      <div className="ql-body" role="tabpanel">
        {tab === "compare" ? <ComparePanel /> : q.isLoading ? <p className="ql-state" role="status">Loading {ticker}</p>
          : q.error ? <p className="ql-state err" role="alert">{(q.error as Error).message}</p>
          : d ? <Sections d={d} tab={tab} /> : null}
      </div>
      {d && tab !== "compare" ? <footer className="ql-foot">{d.limits.join(" · ")} · prices to {d.price_date}</footer> : null}
    </aside>
  );
}

function Sections({ d, tab }: { d: Lookup; tab: QuickTab }) {
  if (tab === "overview") return <Overview d={d} />;
  if (tab === "ratios") return <Ratios d={d} />;
  if (tab === "health") return <Health d={d} />;
  if (tab === "peers") return <Peers d={d} />;
  return <Financials d={d} />;
}

function Overview({ d }: { d: Lookup }) {
  const { range, setRange } = useQuickLook();
  const available = RANGES.filter((r) => (d.chart[r]?.length ?? 0) > 1);
  const shown = available.includes(range) ? range : available[available.length - 1];
  const series = (shown && d.chart[shown]) || [];
  const month = d.chart["1M"] ?? [];
  const day = month.length > 1 ? month[month.length - 1].close / month[month.length - 2].close - 1 : null;
  const change = series.length > 1 ? series[series.length - 1].close / series[0].close - 1 : null;
  return (
    <>
      <div className="ql-price">
        <b className="num">{numText(d.price)}</b><span>{d.currency ?? ""}</span>
        <Chip tone={day === null ? "neutral" : day >= 0 ? "up" : "down"} title="Last close against the close before">{day === null ? UNKNOWN : `${day >= 0 ? "+" : ""}${(day * 100).toFixed(2)}% 1D`}</Chip>
        <span className="ql-cap">Mkt cap {isNum(d.market_cap) ? `${d.market_cap_currency === "USD" ? "$" : ""}${big(d.market_cap)}${d.market_cap_currency && d.market_cap_currency !== "USD" ? ` ${d.market_cap_currency}` : ""}` : UNKNOWN}</span>
      </div>
      <div className="ql-chart">
        {shown ? <Segmented<string> label="Price range" value={shown} onChange={setRange} options={available.map((r) => ({ value: r, label: r }))} /> : null}
        {series.length > 1 ? <TimeSeries data={series} series={[{ key: "close", label: "Close" }]} height={230} legend={false} format={(v) => numText(v)} /> : <p className="ql-none">No price history held for {d.ticker}</p>}
        {change !== null ? <span className={`ql-change num ${change >= 0 ? "up" : "down"}`}>{change >= 0 ? "+" : ""}{(change * 100).toFixed(1)}% over the range</span> : null}
      </div>
      <h3 className="ql-h">Score profile</h3>
      <div className="ql-profile">
        <ProfileRadar scores={d.scores} />
        <div className="ql-scores">
          {d.scores.map((s) => <Bar key={s.key} label={s.label} value={s.value} />)}
        </div>
      </div>
      <p className="ql-thesis">{d.thesis}</p>
      <div className="ql-notes">
        {([["Pros", d.notes.pros, "up"], ["Cons", d.notes.cons, "down"], ["Red flags", d.notes.red_flags, "warn"]] as const).map(([title, items, tone]) => (
          <section key={title}>
            <h3 className="ql-h"><Chip tone={tone}>{title}</Chip></h3>
            {items.length ? <ul>{items.map((n) => <li key={n.text}>{n.text}</li>)}</ul> : <p className="ql-none">None triggered</p>}
          </section>
        ))}
      </div>
    </>
  );
}

/** Score profile as a shape on the shared radar; an unknown score is left off its axis. */
function ProfileRadar({ scores }: { scores: Lookup["scores"] }) {
  if (scores.length < 3) return null;
  return <Radar height={190} axes={scores.map((x) => ({ key: x.key, label: x.label, format: (v: number) => v.toFixed(0) }))} series={[{ label: "Score", primary: true, values: Object.fromEntries(scores.map((x) => [x.key, x.value])) }]} />;
}

function Bar({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="ql-bar" title={isNum(value) ? `${label}: ${value.toFixed(0)} of 100` : `${label}: ${UNKNOWN}`}>
      <span>{label}</span>
      <i className={isNum(value) ? "" : "unknown"}>{isNum(value) ? <u style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /> : null}</i>
      <b className="num">{isNum(value) ? value.toFixed(0) : UNKNOWN}</b>
    </div>
  );
}

function Ratios({ d }: { d: Lookup }) {
  const groups = useMemo(() => [...new Set(d.stats.map((s) => s.group))], [d.stats]);
  return (
    <table className="ql-table">
      <thead><tr><th>Ratio</th><th className="r">Value</th><th className="r">Sector median</th><th>Sector percentile</th><th className="r">Own 3Y percentile</th></tr></thead>
      {groups.map((g) => (
        <tbody key={g}>
          <tr className="grp"><th colSpan={5}>{g}</th></tr>
          {d.stats.filter((s) => s.group === g).map((s) => (
            <tr key={s.key}>
              <td>{s.label}</td>
              <td className="r num">{stat(s)}</td>
              <td className="r num" title={`${s.sector_n} sector names with a value`}>{isNum(s.sector_median) ? stat({ unit: s.unit, value: s.sector_median }) : UNKNOWN}</td>
              <td><Bar label={s.label} value={s.sector_percentile} /></td>
              <td className="r num">{isNum(s.own_history_percentile) ? s.own_history_percentile.toFixed(0) : UNKNOWN}</td>
            </tr>
          ))}
        </tbody>
      ))}
    </table>
  );
}

function Health({ d }: { d: Lookup }) {
  const { piotroski: p, altman: a } = d;
  const zoneTone = a.zone === "Safe" ? "up" : a.zone === "Distress" ? "down" : a.zone === "Grey" ? "warn" : "neutral";
  const hist = a.history.filter((h) => isNum(h.altman_z_score));
  return (
    <>
      <h3 className="ql-h">Piotroski F-score <b className="num">{isNum(p.score) ? `${p.score.toFixed(0)} of 9` : UNKNOWN}</b>{p.available < 9 ? <span className="ql-sub">{p.available} of 9 checks known</span> : null}</h3>
      <div className="ql-grid9">
        {p.checks.map((c) => (
          <div key={c.key}>
            <Chip tone={c.passed === null ? "neutral" : c.passed ? "up" : "down"}>{c.passed === null ? UNKNOWN : c.passed ? "Pass" : "Fail"}</Chip>
            <span>{c.label}</span>
          </div>
        ))}
      </div>
      <h3 className="ql-h">Altman Z <b className="num">{numText(a.z)}</b><Chip tone={zoneTone}>{a.zone ?? UNKNOWN}</Chip></h3>
      {isNum(a.z_double_prime) ? <p className="ql-sub">Z″ for non-manufacturers <b className="num">{numText(a.z_double_prime)}</b></p> : null}
      {hist.length > 1 ? <TimeSeries data={hist.map((h) => ({ date: h.available_date, z: h.altman_z_score }))} series={[{ key: "z", label: "Altman Z" }]} refLines={[{ y: 2.99, label: "Safe" }, { y: 1.81, label: "Distress" }]} height={170} legend={false} format={(v) => numText(v)} /> : <p className="ql-none">Altman history: fewer than two quarters held</p>}
    </>
  );
}

const PEER_LABEL: Record<string, string> = { market_cap: "Mkt cap", trailing_pe: "P/E", pb_ratio: "P/B", roe: "ROE", net_margin: "Net margin", revenue_growth_yoy: "Rev growth", return_12m: "12M return", core_quant_score: "Score" };
const PEER_PCT = new Set(["roe", "net_margin", "revenue_growth_yoy", "return_12m"]);
const peerText = (c: string, v: unknown) => (!isNum(v) ? UNKNOWN : PEER_PCT.has(c) ? pctText(v) : c === "market_cap" ? big(v) : c === "core_quant_score" ? v.toFixed(0) : numText(v));

function Peers({ d }: { d: Lookup }) {
  const { open, setBasket, setTab } = useQuickLook();
  const cols = d.peers.columns.filter((c) => c !== "ticker" && c !== "company_name");
  const tickers = d.peers.rows.map((r) => String(r.ticker));
  return (
    <>
      <nav className="ql-path" aria-label="Classification">{[d.sector, d.peers.scope === "industry group" ? d.industry : null].filter(Boolean).join(" › ") || UNKNOWN}<span>{d.peers.scope_n.toLocaleString()} names in the {d.peers.scope}, nearest {Math.max(0, d.peers.rows.length - 1)} by market cap</span></nav>
      {d.peers.rows.length > 1 ? (
        <>
          <div className="ql-scroll">
            <table className="ql-table">
              <thead><tr><th>Name</th>{cols.map((c) => <th key={c} className="r">{PEER_LABEL[c] ?? c}</th>)}</tr></thead>
              <tbody>
                {d.peers.rows.map((r) => (
                  <tr key={String(r.ticker)} className={r.ticker === d.ticker ? "self" : ""}>
                    <td><button className="ql-link" onClick={() => open(String(r.ticker), "peers")}><b>{String(r.ticker)}</b> {typeof r.company_name === "string" && r.company_name ? r.company_name : UNKNOWN}</button></td>
                    {cols.map((c) => <td key={c} className="r num">{peerText(c, r[c])}</td>)}
                  </tr>
                ))}
                <tr className="median"><td>Peer median</td>{cols.map((c) => <td key={c} className="r num">{peerText(c, d.peers.median[c])}</td>)}</tr>
              </tbody>
            </table>
          </div>
          <button className="btn sm" onClick={() => { setBasket(tickers); setTab("compare"); }}><GitCompareArrows size={13} />Compare with peers</button>
        </>
      ) : <p className="ql-none">No peers held in this {d.peers.scope}</p>}
    </>
  );
}

const fmtLine = (key: string, v: number | null) => (!isNum(v) ? UNKNOWN : key.includes("EPS") ? v.toFixed(2) : big(v));

function Financials({ d }: { d: Lookup }) {
  const [period, setPeriod] = useState<"annual" | "quarterly">("annual");
  const [all, setAll] = useState(false);
  const needsFetch = all || period === "quarterly";
  const detail = useStatements(d.ticker, period, needsFetch);
  const st = needsFetch ? detail.data : d.statements;
  return (
    <>
      <div className="ql-bar-row">
        <Segmented<"annual" | "quarterly"> label="Period" value={period} onChange={setPeriod} options={[{ value: "annual", label: "Annual" }, { value: "quarterly", label: "Quarterly" }]} />
        <button className="btn sm" aria-pressed={all} onClick={() => setAll((a) => !a)}>{all ? "Key lines" : "All line items"}</button>
      </div>
      {detail.isLoading && needsFetch ? <p className="ql-state" role="status">Loading statements</p> : detail.error && needsFetch ? <p className="ql-state err" role="alert">{(detail.error as Error).message}</p>
        : st && st.periods.length ? (
          <div className="ql-scroll">
            <table className="ql-table">
              <thead><tr><th>Line</th><th>Trend</th><th className="r">YoY</th>{st.periods.map((p) => <th key={p} className="r">{p}</th>)}</tr></thead>
              <tbody>{st.lines.map((l) => {
                // Periods may arrive newest first; the sparkline and YoY read oldest to newest.
                const desc = st.periods.length > 1 && st.periods[0] > st.periods[st.periods.length - 1];
                const chron = desc ? [...l.values].reverse() : l.values;
                const back = period === "quarterly" ? 4 : 1;
                const now = chron[chron.length - 1], then = chron[chron.length - 1 - back];
                const yoy = isNum(now) && isNum(then) && then !== 0 ? now / Math.abs(then) - Math.sign(then) : null;
                return <tr key={l.key}><td>{l.label}</td><td>{chron.filter(isNum).length > 1 ? <Spark values={chron.map((v) => (isNum(v) ? v : Number.NaN))} width={64} height={16} /> : null}</td><td className={`r num ${isNum(yoy) ? (yoy >= 0 ? "up" : "down") : ""}`}>{isNum(yoy) ? `${yoy >= 0 ? "+" : ""}${(yoy * 100).toFixed(0)}%` : ""}</td>{l.values.map((v, i) => <td key={i} className="r num">{fmtLine(l.key, v)}</td>)}</tr>;
              })}</tbody>
            </table>
          </div>
        ) : <p className="ql-none">No statements held for {d.ticker}</p>}
    </>
  );
}

const CMP_LABEL: Record<string, string> = { price: "Price", market_cap: "Mkt cap", return_1m: "1M return", return_12m: "12M return", trailing_pe: "P/E", pb_ratio: "P/B", ev_ebitda: "EV/EBITDA", fcf_yield: "FCF yield", roe: "ROE", net_margin: "Net margin", debt_equity: "Debt / equity", revenue_growth_yoy: "Rev growth", realized_vol_63d: "Volatility 63d", beta_252: "Beta", core_quant_score: "Score", valuation_percentile: "Valuation", quality_percentile: "Quality", momentum_percentile: "Momentum", low_vol_percentile: "Low volatility" };
const CMP_PCT = new Set(["return_1m", "return_12m", "fcf_yield", "roe", "net_margin", "revenue_growth_yoy", "realized_vol_63d"]);
const CMP_WHOLE = new Set(["core_quant_score", "valuation_percentile", "quality_percentile", "momentum_percentile", "low_vol_percentile"]);

function ComparePanel() {
  const { basket, toggleBasket, setBasket, open } = useQuickLook();
  const q = useCompare(basket);
  if (basket.length < 2) return <p className="ql-none">Add at least two names to compare{basket.length ? `, ${basket[0]} is in` : ""}</p>;
  const cell = (c: string, v: unknown): ReactNode => (!isNum(v) ? UNKNOWN : CMP_PCT.has(c) ? pctText(v) : c === "market_cap" ? big(v) : CMP_WHOLE.has(c) ? v.toFixed(0) : numText(v));
  return (
    <>
      <div className="ql-bar-row"><span className="ql-sub">{basket.length} of {MAX_COMPARE} names</span><button className="btn sm ghost" onClick={() => setBasket([])}>Clear</button></div>
      {q.isLoading ? <p className="ql-state" role="status">Loading</p> : q.error ? <p className="ql-state err" role="alert">{(q.error as Error).message}</p> : q.data ? (
        <div className="ql-scroll">
          <table className="ql-table ql-cmp">
            <thead><tr><th>Metric</th>{q.data.rows.map((r) => <th key={r.ticker} className="r"><button className="ql-link" onClick={() => open(r.ticker, "overview")}>{r.ticker}</button><button className="ql-x" aria-label={`Remove ${r.ticker}`} onClick={() => toggleBasket(r.ticker)}><X size={10} /></button></th>)}</tr></thead>
            <tbody>
              <tr><td>Name</td>{q.data.rows.map((r) => <td key={r.ticker} className="r ql-nm">{r.company_name ?? UNKNOWN}</td>)}</tr>
              <tr><td>Sector</td>{q.data.rows.map((r) => <td key={r.ticker} className="r ql-nm">{r.sector ?? UNKNOWN}</td>)}</tr>
              {q.data.columns.map((c) => <tr key={c}><td>{CMP_LABEL[c] ?? c}</td>{q.data!.rows.map((r) => <td key={r.ticker} className="r num">{cell(c, r[c])}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}
