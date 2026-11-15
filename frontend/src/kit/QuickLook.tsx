"use client";

import { Check, Download, GitCompareArrows, ListPlus, Maximize2, Minimize2, Pencil, Plus, X } from "lucide-react";
import toast from "react-hot-toast";
import { PriceChart, type TradeMark } from "@/charts/PriceChart";
import { useQuery } from "@tanstack/react-query";
import { latestRun, useRuns } from "@/modules/research/api";
import { SCREENER_BASE } from "@/modules/screener/base";
import { RowActions } from "@/modules/screener/RowActions";
import { useStudies } from "@/modules/research/store";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { create } from "zustand";
import { Radar } from "@/charts/Radar";
import { Spark } from "@/charts/RankList";
import { TimeSeries } from "@/charts/TimeSeries";
import { isNum } from "@/modules/research/format";
import { Chip, Segmented } from "@/workspace/ui";
import { ComparePanel, type CompareTab } from "./Compare";
import { pdfUrl, useBars, useLookup, usePeHistory, useStatements, type Lookup, type Stat } from "./QuickLookData";
import "./quicklook.css";

export const MAX_COMPARE = 8;
export type QuickTab = "overview" | "ratios" | "health" | "peers" | "financials" | "compare";

type QuickLookStore = {
  ticker: string | null;
  tab: QuickTab;
  range: string;
  basket: string[];
  full: boolean;
  setFull: (full: boolean) => void;
  open: (ticker: string, tab?: QuickTab) => void;
  close: () => void;
  setTab: (tab: QuickTab) => void;
  setRange: (range: string) => void;
  toggleBasket: (ticker: string) => void;
  setBasket: (tickers: string[]) => void;
  ctab: CompareTab;
  setCtab: (tab: CompareTab) => void;
};

/** One drawer for the whole workspace: any table, chart or search row opens a name with `openQuickLook(ticker)`. */
export const useQuickLook = create<QuickLookStore>()((set) => ({
  ticker: null, tab: "overview", range: "1Y", basket: [], full: false, ctab: "price",
  setCtab: (ctab) => set({ ctab }),
  setFull: (full) => set({ full }),
  open: (ticker, tab) => set((s) => ({ ticker: ticker.toUpperCase(), tab: tab ?? (s.ticker === ticker.toUpperCase() ? s.tab : "overview") })),
  close: () => set({ ticker: null, full: false }),
  setTab: (tab) => set({ tab }),
  setRange: (range) => set({ range }),
  toggleBasket: (ticker) => set((s) => ({ basket: s.basket.includes(ticker) ? s.basket.filter((t) => t !== ticker) : s.basket.length < MAX_COMPARE ? [...s.basket, ticker] : s.basket })),
  setBasket: (tickers) => set({ basket: [...new Set(tickers)].slice(0, MAX_COMPARE) }),
}));

export const openQuickLook = (ticker: string, tab?: QuickTab) => useQuickLook.getState().open(ticker, tab);
/** Opens the full-page compare view on exactly these names. */
export const openCompare = (tickers: string[], ctab?: CompareTab) => {
  const s = useQuickLook.getState();
  s.setBasket(tickers);
  if (ctab) s.setCtab(ctab);
  s.open(tickers[0], "compare");
  s.setFull(true);
};

const UNKNOWN = "Unknown";
const pctText = (v: number | null | undefined, d = 1) => (isNum(v) ? `${(v * 100).toFixed(d)}%` : UNKNOWN);
const numText = (v: number | null | undefined, d = 2) => (isNum(v) ? v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : UNKNOWN);
const big = (v: number | null | undefined) => (isNum(v) ? v.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 }) : UNKNOWN);
const stat = (s: Pick<Stat, "unit" | "value">) => (s.unit === "pct" ? pctText(s.value) : numText(s.value));

export function Monogram({ ticker }: { ticker: string }) {
  return <span className="ql-mono" aria-hidden>{ticker.replace(/_.*/, "").slice(0, 2)}</span>;
}

const RANGES = ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y"];
const RANGE_DAYS: Record<string, number> = { "1M": 31, "3M": 92, "6M": 183, "1Y": 365, "3Y": 1095, "5Y": 1825, "10Y": 3650 };

/** Adds a name to the Screen study's explicit universe. */
function addToScreen(ticker: string) {
  useStudies.setState((s) => {
    const form = s.forms.sc01 ?? {};
    const cur = String(form.universe ?? "").split(/[\s,]+/).filter((t) => t && !["master", "all", "default"].includes(t.toLowerCase()));
    return { forms: { ...s.forms, sc01: { ...form, universe: [...new Set([...cur, ticker])].join(","), max_symbols: Math.max(cur.length + 1, 25) } } };
  });
  toast.success(`${ticker} added to the Screen universe`);
}

export function QuickLook() {
  const { ticker, tab, basket, full, ctab, close, setTab, setFull, toggleBasket } = useQuickLook();
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

  // The open name lives in the URL (?stock=XOM, &view=full) so a stock page can be linked and reloaded.
  useEffect(() => {
    const p = new URLSearchParams(location.search);
    const t = p.get("stock"), cmp = p.get("compare")?.split(",").filter(Boolean);
    if (cmp && cmp.length > 1) openCompare(cmp, (p.get("ctab") as CompareTab | null) ?? undefined);
    else if (t) { useQuickLook.getState().open(t); setFull(p.get("view") === "full"); }
  }, [setFull]);
  useEffect(() => {
    const u = new URL(location.href);
    if (ticker) u.searchParams.set("stock", ticker); else u.searchParams.delete("stock");
    if (ticker && full) u.searchParams.set("view", "full"); else u.searchParams.delete("view");
    // An open compare is shareable: its names and tab ride in the URL.
    if (ticker && tab === "compare" && basket.length > 1) { u.searchParams.set("compare", basket.join(",")); u.searchParams.set("ctab", ctab); } else { u.searchParams.delete("compare"); u.searchParams.delete("ctab"); }
    if (u.href !== location.href) history.replaceState(history.state, "", u);
  }, [ticker, full, tab, basket, ctab]);

  if (!ticker) return null;
  const d = q.data;
  const inBasket = basket.includes(ticker);
  const tabs: { id: QuickTab; label: string }[] = [
    { id: "overview", label: "Overview" }, { id: "ratios", label: "Ratios" }, { id: "health", label: "Health" }, { id: "peers", label: "Peers" }, { id: "financials", label: "Financials" },
    ...(basket.length ? [{ id: "compare" as const, label: `Compare ${basket.length}` }] : []),
  ];
  return (
    <aside ref={ref} className={`ql${full ? " full" : ""}`} role="dialog" aria-label={`${ticker} quick look`} tabIndex={-1}>
      <header className="ql-head">
        <Monogram ticker={ticker} />
        <div className="ql-title">
          <b>{ticker}</b><span>{d ? d.company_name ?? UNKNOWN : q.isLoading ? "" : UNKNOWN}</span>
          {d ? <small>{[d.exchange, d.sector, d.industry].filter(Boolean).join(" · ") || UNKNOWN}</small> : null}
          {d ? <HeadPrice d={d} /> : null}
        </div>
        <div className="ql-actions">
          <RowActions ticker={ticker} />
          <button className="btn sm icon ghost" onClick={() => addToScreen(ticker)} aria-label={`Add ${ticker} to the Screen universe`} title="Add to screen"><ListPlus size={13} /></button>
          <button className="btn sm" aria-pressed={inBasket} onClick={() => toggleBasket(ticker)} title={inBasket ? "Remove from compare" : "Add to compare"}>{inBasket ? <Check size={13} /> : <Plus size={13} />}Compare</button>
          <a className="btn sm" href={pdfUrl(ticker)} download title="One-page PDF"><Download size={13} />PDF</a>
          <button className="btn sm icon ghost" onClick={() => setFull(!full)} aria-label={full ? "Back to drawer" : "Open as full page"} title={full ? "Drawer" : "Full page"}>{full ? <Minimize2 size={13} /> : <Maximize2 size={13} />}</button>
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

function HeadPrice({ d }: { d: Lookup }) {
  const month = d.chart["1M"] ?? [];
  const day = month.length > 1 ? month[month.length - 1].close / month[month.length - 2].close - 1 : null;
  return (
    <span className="ql-hp">
      <b className="num">{numText(d.price)}</b><em>{d.currency ?? ""}</em>
      {day !== null ? <i className={`num ${day >= 0 ? "up" : "down"}`}>{day >= 0 ? "+" : ""}{(day * 100).toFixed(2)}%</i> : null}
    </span>
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
        {series.length > 1 ? <Candles ticker={d.ticker} range={shown} fallback={<TimeSeries data={series} series={[{ key: "close", label: "Close" }]} height={230} legend={false} format={(v) => numText(v)} />} /> : <p className="ql-none">No price history held for {d.ticker}</p>}
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

/** Candles, volume and SMA 50/200 for the range; the close line stands in while bars load or if they fail. */
function Candles({ ticker, range, fallback }: { ticker: string; range: string; fallback: ReactNode }) {
  const days = RANGE_DAYS[range] ?? 365;
  const [mode, setMode] = useState<"price" | "pe">("price");
  const bars = useBars(ticker, days).data?.bars;
  const pe = usePeHistory(ticker, days, mode === "pe").data?.series;
  const line = useMemo(() => (mode === "pe" && pe ? pe.filter((p) => isNum(p.valuation_metric)).map((p) => ({ time: p.date.slice(0, 10), value: p.valuation_metric as number })) : undefined), [mode, pe]);
  const marks = useTradeMarks(ticker);
  return (
    <>
      <div className="ql-mode"><Segmented<"price" | "pe"> label="Chart" value={mode} onChange={setMode} options={[{ value: "price", label: "Price" }, { value: "pe", label: "P/E" }]} /></div>
      {bars && bars.length > 1 ? <PriceChart bars={bars} height={260} marks={marks} line={line && line.length > 1 ? line : undefined} /> : <>{fallback}</>}
    </>
  );
}

/** Entry and exit dates of this name in the latest finished backtest, as chart marks. */
function useTradeMarks(ticker: string): TradeMark[] | undefined {
  const job = useRuns((s) => latestRun(s.runs, "sc05")?.jobId ?? null);
  const res = useQuery({ queryKey: ["screener", "job", job], queryFn: () => fetch(`${SCREENER_BASE}/jobs/${job}`).then((r) => r.json() as Promise<{ result?: { tables?: Record<string, unknown> } }>), enabled: !!job, staleTime: Infinity, retry: false }).data;
  return useMemo(() => {
    const t = res?.result?.tables?.position_entry_exit_log as { rows?: Record<string, unknown>[] } | Record<string, unknown>[] | undefined;
    const rows = (Array.isArray(t) ? t : t?.rows ?? []).filter((r) => r.ticker === ticker);
    return rows.flatMap((r) => [...(r.entry_date ? [{ time: String(r.entry_date).slice(0, 10), side: "entry" as const, label: "Buy" }] : []), ...(r.exit_date ? [{ time: String(r.exit_date).slice(0, 10), side: "exit" as const, label: "Sell" }] : [])]);
  }, [res, ticker]);
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

const RATIO_KEY = "quicklook-ratios-hidden";

/** Ratio cards with a tick for where the name sits in its sector; Edit picks which ratios show, kept on this device. */
function Ratios({ d }: { d: Lookup }) {
  const [hidden, setHidden] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(RATIO_KEY) ?? "[]") as string[]; } catch { return []; } });
  const [editing, setEditing] = useState(false);
  const groups = useMemo(() => [...new Set(d.stats.map((s) => s.group))], [d.stats]);
  const flip = (k: string) => setHidden((h) => { const next = h.includes(k) ? h.filter((x) => x !== k) : [...h, k]; try { localStorage.setItem(RATIO_KEY, JSON.stringify(next)); } catch { /* storage blocked */ } return next; });
  return (
    <>
      <div className="ql-rbar">
        <button type="button" className="btn sm ghost" aria-pressed={editing} onClick={() => setEditing(!editing)}><Pencil size={12} />{editing ? "Done" : "Edit ratios"}</button>
        {hidden.length && !editing ? <button type="button" className="btn sm ghost" onClick={() => setEditing(true)}><Plus size={12} />{hidden.length} hidden</button> : null}
      </div>
      {groups.map((g) => {
        const list = d.stats.filter((s) => s.group === g && (editing || !hidden.includes(s.key)));
        return list.length ? (
          <section key={g}>
            <h3 className="ql-h">{g}</h3>
            <div className="ql-rgrid">
              {list.map((s) => (
                <div key={s.key} className={`ql-ratio${hidden.includes(s.key) ? " off" : ""}`} title={`${s.sector_n} sector names with a value; own 3Y percentile ${isNum(s.own_history_percentile) ? s.own_history_percentile.toFixed(0) : UNKNOWN}`}>
                  {editing ? <input type="checkbox" aria-label={`Show ${s.label}`} checked={!hidden.includes(s.key)} onChange={() => flip(s.key)} /> : null}
                  <span>{s.label}</span>
                  <b className="num">{stat(s)}</b>
                  <i className="ql-strip" aria-label={`Sector percentile ${isNum(s.sector_percentile) ? s.sector_percentile.toFixed(0) : UNKNOWN}`}>{isNum(s.sector_percentile) ? <u style={{ left: `${Math.max(0, Math.min(100, s.sector_percentile))}%` }} /> : null}</i>
                  <small className="num">Sector {isNum(s.sector_median) ? stat({ unit: s.unit, value: s.sector_median }) : UNKNOWN}</small>
                </div>
              ))}
            </div>
          </section>
        ) : null;
      })}
    </>
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
