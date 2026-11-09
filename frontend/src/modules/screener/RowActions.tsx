"use client";

import { BookOpen, Bell, FlaskConical, Star } from "lucide-react";
import { useRouter } from "next/navigation";
import { openQuickLook } from "@/kit/QuickLook";
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
