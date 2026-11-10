"use client";

import { BookOpen, Bell, Copy, FlaskConical, LineChart, Sigma, Star } from "lucide-react";
import { downloadCsv, downloadJson, downloadTickers } from "@/charts/export";
import type { Row } from "@/modules/research/types";
import { useRouter } from "next/navigation";
import { openQuickLook } from "@/kit/QuickLook";
import { featureHref } from "@/modules/research/catalog";
import { useStudies } from "@/modules/research/store";
import { DEFAULT_LIST, useWatchlists } from "./watchlists";

const split = (v: unknown) => (Array.isArray(v) ? v.map(String) : String(v ?? "").split(/[\s,]+/)).filter(Boolean);

/** Per-row actions: star, alert on it, rank it in ML, read it in Research. */
export function RowActions({ ticker }: { ticker: string }) {
  const router = useRouter();
  const starred = useWatchlists((s) => (s.lists[DEFAULT_LIST] ?? []).includes(ticker));
  const toggleStar = useWatchlists((s) => s.toggle);
  const alerted = useStudies((s) => split(s.forms.sc06?.watchlist).includes(ticker));
  const edit = (id: string, key: string, on: boolean) => useStudies.setState((s) => {
    const form = s.forms[id] ?? {};
    const cur = split(form[key]);
    return { forms: { ...s.forms, [id]: { ...form, [key]: (on ? [...new Set([...cur, ticker])] : cur.filter((t) => t !== ticker)).join(",") } } };
  });
  return (
    <span style={{ display: "inline-flex", gap: 2 }}>
      <button type="button" className="btn sm icon ghost" aria-pressed={starred} aria-label={`${starred ? "Remove" : "Add"} ${ticker} ${starred ? "from" : "to"} watchlist`} onClick={() => toggleStar(ticker)}><Star size={12} fill={starred ? "currentColor" : "none"} /></button>
      <button type="button" className="btn sm icon ghost" aria-pressed={alerted} aria-label={`${alerted ? "Stop" : "Start"} alerts on ${ticker}`} onClick={() => edit("sc06", "watchlist", !alerted)}><Bell size={12} fill={alerted ? "currentColor" : "none"} /></button>
      <button type="button" className="btn sm icon ghost" aria-label={`Rank ${ticker} in ML`} onClick={() => { edit("ml02", "universe", true); router.push("/ml/alpha"); }}><FlaskConical size={12} /></button>
      <button type="button" className="btn sm icon ghost" aria-label={`Read ${ticker} statements`} onClick={() => openQuickLook(ticker, "financials")}><BookOpen size={12} /></button>
    </span>
  );
}

/** Actions on many selected rows: star, alert, send to Rank, Test or ML, copy tickers, CSV. */
export function BulkActions({ rows, clear }: { rows: Row[]; clear: () => void }) {
  const router = useRouter();
  const tickers = rows.map((r) => String(r.ticker ?? "")).filter(Boolean);
  const set = (id: string, key: string, merge = false) => useStudies.setState((s) => {
    const form = s.forms[id] ?? {};
    const next = merge ? [...new Set([...split(form[key]), ...tickers])] : tickers;
    return { forms: { ...s.forms, [id]: { ...form, [key]: next.join(",") } } };
  });
  const star = () => useWatchlists.setState((s) => ({ lists: { ...s.lists, [DEFAULT_LIST]: [...new Set([...(s.lists[DEFAULT_LIST] ?? []), ...tickers])] } }));
  return (
    <>
      <button type="button" className="btn sm ghost" onClick={() => { star(); clear(); }}><Star size={11} />Watchlist</button>
      <button type="button" className="btn sm ghost" onClick={() => { set("sc06", "watchlist", true); clear(); }}><Bell size={11} />Alert</button>
      <button type="button" className="btn sm ghost" onClick={() => { set("sc03", "universe"); router.push(featureHref("sc03")); }}><Sigma size={11} />Rank</button>
      <button type="button" className="btn sm ghost" onClick={() => { set("sc05", "universe"); router.push(featureHref("sc05")); }}><LineChart size={11} />Test</button>
      <button type="button" className="btn sm ghost" onClick={() => { set("ml02", "universe"); router.push("/ml/alpha"); }}><FlaskConical size={11} />ML</button>
      <button type="button" className="btn sm ghost" onClick={() => void navigator.clipboard?.writeText(tickers.join(", "))}><Copy size={11} />Tickers</button>
      <button type="button" className="btn sm ghost" onClick={() => downloadCsv(rows, "selected")}>CSV</button>
      <button type="button" className="btn sm ghost" onClick={() => downloadJson(rows, "selected")}>JSON</button>
      <button type="button" className="btn sm ghost" onClick={() => downloadTickers(rows, "selected")}>List</button>
    </>
  );
}
