"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { isNum, out, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import type { FeatureResult } from "@/modules/research/types";
import { send } from "./api";
import { useWatchlists } from "./watchlists";
import { BellRing } from "lucide-react";
import "./lenses.css";

export type LensRow = { ticker: string; company_name: string | null; sector: string | null; price: number | null; buffett: boolean; graham: boolean; dividend: boolean; momentum: boolean; passes: number; fair_low: number | null; fair_mid: number | null; fair_high: number | null; discount: number | null; fair_basis: number };
export type Lenses = { as_of: string; lenses: { key: "buffett" | "graham" | "dividend" | "momentum"; label: string; rule: string }[]; fair_basis: string; rows: LensRow[] };

/** Lens flags and fair-value ranges for the names a run returned, from the full panel. */
export function useLenses(result: FeatureResult, key = "ranked_screener_table") {
  const tickers = useMemo(() => out(result, key).map((r) => r.ticker).filter((t): t is string => typeof t === "string"), [result, key]);
  return useQuery({ queryKey: ["screener", "lenses", tickers.join(",")], queryFn: () => send<Lenses>("POST", "/lookup/lenses", { tickers }), enabled: tickers.length > 0, staleTime: 600_000, retry: false });
}

const on = (r: LensRow, k: string) => (r as unknown as Record<string, unknown>)[k] === true;

/** P1: which names pass two or more investor lenses; the overlap is the headline. */
export function LensOverlap({ result }: ViewProps) {
  const q = useLenses(result);
  const [only, setOnly] = useState<string | null>(null);
  if (q.isLoading) return <div aria-busy="true" className="ln-load">Checking lenses</div>;
  if (q.error) return <Empty text={(q.error as Error).message} />;
  const d = q.data;
  if (!d?.rows.length) return <Empty />;
  const overlap = d.rows.filter((r) => r.passes >= 2 && (!only || on(r, only))).sort((a, b) => b.passes - a.passes || (b.discount ?? -9) - (a.discount ?? -9));
  const count = (k: string) => d.rows.filter((r) => on(r, k)).length;
  const all = d.rows.filter((r) => r.passes >= 2).length;
  return (
    <div className="ln">
      <p className="ln-head"><b className="num">{all.toLocaleString()}</b> of {d.rows.length.toLocaleString()} names pass two or more lenses{d.rows.some((r) => r.passes === 4) ? <>; <b>{d.rows.filter((r) => r.passes === 4).map((r) => r.ticker).join(", ")}</b> pass all four</> : null}</p>
      <div className="ln-lenses">
        {d.lenses.map((l) => (
          <button key={l.key} type="button" className="ln-lens" aria-pressed={only === l.key} title={l.rule} onClick={() => setOnly(only === l.key ? null : l.key)}>
            <span>{l.label}</span><b className="num">{count(l.key)}</b>
          </button>
        ))}
      </div>
      {overlap.length ? (
        <div className="ln-scroll">
          <table className="tbl ln-table">
            <thead><tr><th>Name</th>{d.lenses.map((l) => <th key={l.key} title={l.rule}>{l.label}</th>)}<th className="r">Lenses</th></tr></thead>
            <tbody>{overlap.map((r) => (
              <tr key={r.ticker}>
                <td><button type="button" className="tk-link" onClick={() => openQuickLook(r.ticker)}>{r.ticker}</button><span className="ln-co">{r.company_name ?? ""}</span></td>
                {d.lenses.map((l) => <td key={l.key} className="ln-cell" data-on={on(r, l.key)}><i /></td>)}
                <td className="r num ln-n">{r.passes}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : <Empty text="No name passes two lenses here." />}
    </div>
  );
}

/** P2: every name's price against its fair-value range on one axis (fair ÷ price, log scale), most discounted first. */
export function FairValueStrip({ result }: ViewProps) {
  const q = useLenses(result);
  if (q.isLoading) return <div aria-busy="true" className="ln-load">Pricing names</div>;
  if (q.error) return <Empty text={(q.error as Error).message} />;
  const rows = (q.data?.rows ?? []).filter((r) => isNum(r.discount) && isNum(r.price) && isNum(r.fair_low) && isNum(r.fair_high)).sort((a, b) => (b.discount as number) - (a.discount as number));
  if (!rows.length) return <Empty text="Too few multiples to price these names." />;
  // Axis: fair value as a multiple of price, 1/4× to 4×, so cheap and dear names read symmetrically.
  const R = Math.log(4);
  const x = (v: number, price: number) => Math.max(0, Math.min(100, ((Math.log(v / price) + R) / (2 * R)) * 100));
  const under = rows.filter((r) => (r.discount as number) > 0).length;
  return (
    <div className="fv">
      <p className="ln-head"><b className="num">{under.toLocaleString()}</b> of {rows.length.toLocaleString()} trade below the middle of their range</p>
      <div className="fv-axis num"><span>¼× price</span><span>½×</span><span>Price</span><span>2×</span><span>4×</span></div>
      <div className="fv-rows">
        {rows.map((r) => {
          const p = r.price as number, d = r.discount as number;
          return (
            <div key={r.ticker} className="fv-line">
            <FairAlertToggle ticker={r.ticker} />
            <button type="button" className="fv-row" onClick={() => openQuickLook(r.ticker, "ratios")} title={`${r.ticker}: price ${p.toFixed(2)}, fair ${(r.fair_low as number).toFixed(2)} to ${(r.fair_high as number).toFixed(2)} from ${r.fair_basis} multiples`}>
              <b>{r.ticker}</b>
              <span className="fv-track">
                <i className="fv-mid0" />
                <i className="fv-range" style={{ left: `${x(r.fair_low as number, p)}%`, width: `${Math.max(0.6, x(r.fair_high as number, p) - x(r.fair_low as number, p))}%` }} />
                <i className="fv-mark" style={{ left: `${x(r.fair_mid as number, p)}%` }} />
              </span>
              <em className={`num ${d >= 0 ? "up" : "down"}`}>{d >= 0 ? "+" : ""}{pct(d, 0)}</em>
            </button>
            </div>
          );
        })}
      </div>
      <p className="fv-note">{q.data?.fair_basis}</p>
    </div>
  );
}

type Flags = { as_of: string; rows: { ticker: string; flag: string; quarter: string | null; detail: string }[] };

/** P3: warning signs among the names, newest quarter first; a flag type filters the list. */
export function RedFlagFeed({ result }: ViewProps) {
  const tickers = useMemo(() => out(result, "ranked_screener_table").map((r) => r.ticker).filter((t): t is string => typeof t === "string"), [result]);
  const q = useQuery({ queryKey: ["screener", "red-flags", tickers.join(",")], queryFn: () => send<Flags>("POST", "/lookup/red-flags", { tickers }), enabled: tickers.length > 0, staleTime: 600_000, retry: false });
  const [only, setOnly] = useState<string | null>(null);
  if (q.isLoading) return <div aria-busy="true" className="ln-load">Reading statements</div>;
  if (q.error) return <Empty text={(q.error as Error).message} />;
  const rows = q.data?.rows ?? [];
  if (!rows.length) return <Empty text="No red flags among these names." />;
  const kinds = [...new Set(rows.map((r) => r.flag))];
  const names = new Set(rows.map((r) => r.ticker)).size;
  const shown = only ? rows.filter((r) => r.flag === only) : rows;
  return (
    <div className="ln">
      <p className="ln-head"><b className="num">{names.toLocaleString()}</b> of {tickers.length.toLocaleString()} names carry a red flag</p>
      <div className="ln-lenses">
        {kinds.map((k) => <button key={k} type="button" className="ln-lens rf-kind" aria-pressed={only === k} onClick={() => setOnly(only === k ? null : k)}><span>{k}</span><b className="num">{rows.filter((r) => r.flag === k).length}</b></button>)}
      </div>
      <ol className="rf">
        {shown.slice(0, 300).map((r, i) => (
          <li key={`${r.ticker}-${r.flag}-${i}`}>
            <span className="rf-q num">{r.quarter ?? "Latest"}</span>
            <button type="button" className="tk-link" onClick={() => openQuickLook(r.ticker, "health")}>{r.ticker}</button>
            <span className="rf-flag">{r.flag}</span>
            <span className="rf-d">{r.detail}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** The watchlist that holds fair-value alerts; Monitor checks it on every visit. */
export const FAIR_LIST = "Below fair value";
const NONE: string[] = [];

/** P4: a bell that adds a name to the fair-value alerts. */
export function FairAlertToggle({ ticker }: { ticker: string }) {
  const on = useWatchlists((st) => (st.lists[FAIR_LIST] ?? []).includes(ticker));
  const toggle = useWatchlists((st) => st.toggle);
  return <button type="button" className="btn sm icon ghost fv-bell" aria-pressed={on} aria-label={`${on ? "Stop" : "Tell me"} when ${ticker} trades below its fair value`} title={on ? "Alert on: below fair value" : "Alert me below fair value"} onClick={() => toggle(ticker, FAIR_LIST)}><BellRing size={12} fill={on ? "currentColor" : "none"} /></button>;
}

/** P4 in Monitor: each alerted name's price against the middle of its fair-value range; below it, the alert has fired. */
export function FairValueWatch(_: ViewProps) {
  const tickers = useWatchlists((st) => st.lists[FAIR_LIST] ?? NONE);
  const q = useQuery({ queryKey: ["screener", "lenses", "watch", tickers.join(",")], queryFn: () => send<Lenses>("POST", "/lookup/lenses", { tickers }), enabled: tickers.length > 0, staleTime: 300_000, retry: false });
  if (!tickers.length) return <Empty text="No fair-value alerts. Use the bell on the fair-value strip or in a stock's drawer." />;
  if (q.isLoading) return <div aria-busy="true" className="ln-load">Pricing names</div>;
  if (q.error) return <Empty text={(q.error as Error).message} />;
  const rows = (q.data?.rows ?? []).sort((a, b) => (b.discount ?? -9) - (a.discount ?? -9));
  const fired = rows.filter((r) => isNum(r.discount) && r.discount > 0);
  return (
    <div className="ln">
      <p className="ln-head"><b className="num">{fired.length}</b> of {rows.length} trade below fair value{q.data?.as_of ? ` as of ${q.data.as_of}` : ""}</p>
      <table className="tbl">
        <thead><tr><th>Name</th><th className="r">Price</th><th className="r">Fair value</th><th className="r">Gap</th><th /></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.ticker} data-fired={isNum(r.discount) && r.discount > 0}>
            <td><button type="button" className="tk-link" onClick={() => openQuickLook(r.ticker, "ratios")}>{r.ticker}</button></td>
            <td className="r num">{isNum(r.price) ? r.price.toFixed(2) : "–"}</td>
            <td className="r num">{isNum(r.fair_mid) ? `${r.fair_mid.toFixed(2)} (${(r.fair_low ?? 0).toFixed(0)} to ${(r.fair_high ?? 0).toFixed(0)})` : "Too few multiples"}</td>
            <td className={`r num ${isNum(r.discount) ? (r.discount > 0 ? "up" : "down") : ""}`}>{isNum(r.discount) ? `${r.discount > 0 ? "below by " : "above by "}${pct(Math.abs(r.discount) / (1 + r.discount), 0)}` : ""}</td>
            <td className="r"><FairAlertToggle ticker={r.ticker} /></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
