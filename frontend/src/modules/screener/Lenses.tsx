"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { isNum, out, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import type { FeatureResult } from "@/modules/research/types";
import { send } from "./api";
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
            <button key={r.ticker} type="button" className="fv-row" onClick={() => openQuickLook(r.ticker, "ratios")} title={`${r.ticker}: price ${p.toFixed(2)}, fair ${(r.fair_low as number).toFixed(2)} to ${(r.fair_high as number).toFixed(2)} from ${r.fair_basis} multiples`}>
              <b>{r.ticker}</b>
              <span className="fv-track">
                <i className="fv-mid0" />
                <i className="fv-range" style={{ left: `${x(r.fair_low as number, p)}%`, width: `${Math.max(0.6, x(r.fair_high as number, p) - x(r.fair_low as number, p))}%` }} />
                <i className="fv-mark" style={{ left: `${x(r.fair_mid as number, p)}%` }} />
              </span>
              <em className={`num ${d >= 0 ? "up" : "down"}`}>{d >= 0 ? "+" : ""}{pct(d, 0)}</em>
            </button>
          );
        })}
      </div>
      <p className="fv-note">{q.data?.fair_basis}</p>
    </div>
  );
}
