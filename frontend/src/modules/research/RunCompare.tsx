"use client";

import { X } from "lucide-react";
import { useMemo } from "react";
import { TimeSeries } from "@/charts/TimeSeries";
import { openCompare, openQuickLook } from "@/kit/QuickLook";
import { useJob, useRuns } from "./api";
import { isNum, label, num, out } from "./format";
import type { FeatureResult, FeatureSpec } from "./types";

const when = (t: number) => new Date(t).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
const show = (v: unknown) => (isNum(v) ? (Math.abs(v) < 10 && !Number.isInteger(v) ? num(v, 3) : num(v, Number.isInteger(v) ? 0 : 1)) : v === null || v === undefined ? "–" : String(v));

/** X4: this run against an earlier run of the same page: settings changed, headline numbers, names in and out, curves on one axis. */
export function RunCompare({ feature, result, jobId, againstId, onClose }: { feature: FeatureSpec; result: FeatureResult; jobId?: string | null; againstId: string; onClose: () => void }) {
  const runs = useRuns((s) => s.runs);
  const mine = runs.find((r) => r.jobId === jobId), theirs = runs.find((r) => r.jobId === againstId);
  const other = useJob(againstId).data?.result;
  const settings = useMemo(() => {
    const a = mine?.payload ?? {}, b = theirs?.payload ?? {};
    return [...new Set([...Object.keys(a), ...Object.keys(b)])].filter((k) => JSON.stringify(a[k] ?? "") !== JSON.stringify(b[k] ?? "")).map((k) => ({ k, was: b[k], now: a[k] }));
  }, [mine, theirs]);
  // The first output listing names, and the first with a dated strategy curve.
  const nameKey = feature.outputs.find((o) => out(result, o.key).some((r) => typeof r.ticker === "string"))?.key;
  const curveKey = feature.outputs.find((o) => out(result, o.key).some((r) => typeof r.date === "string" && isNum(r.strategy)))?.key;
  if (!other) return <div className="rc card"><div className="card-b">Loading the earlier run</div></div>;
  const before = new Map((other.summary_cards ?? []).map((c) => [c.label, c.value]));
  const cards = (result.summary_cards ?? []).map((c) => ({ label: c.label, now: c.value, was: before.get(c.label) }));
  const names = (r: FeatureResult) => new Set(nameKey ? out(r, nameKey).map((x) => String(x.ticker ?? "")).filter(Boolean) : []);
  const a = names(result), b = names(other);
  const entered = [...a].filter((t) => !b.has(t)), left = [...b].filter((t) => !a.has(t));
  const rankOf = (r: FeatureResult) => new Map(nameKey ? out(r, nameKey).filter((x) => isNum(x.rank)).map((x) => [String(x.ticker), x.rank as number]) : []);
  const ra = rankOf(result), rb = rankOf(other);
  const moved = [...ra].flatMap(([t, now]) => (rb.has(t) && rb.get(t) !== now ? [{ t, by: rb.get(t)! - now }] : [])).sort((x, y) => Math.abs(y.by) - Math.abs(x.by));
  const curve = (r: FeatureResult) => { const rows = curveKey ? out(r, curveKey).filter((x) => typeof x.date === "string" && isNum(x.strategy)) : []; const base = rows[0]?.strategy as number | undefined; return new Map(rows.map((x) => [String(x.date).slice(0, 10), base ? (x.strategy as number) / base : null])); };
  const cn = curve(result), co = curve(other);
  const series = [...new Set([...cn.keys(), ...co.keys()])].sort().map((d) => ({ date: d, now: cn.get(d) ?? null, was: co.get(d) ?? null }));
  return (
    <div className="rc card">
      <div className="card-h"><h3>This run against {theirs ? when(theirs.startedAt) : "an earlier run"}</h3><button className="btn sm icon ghost" aria-label="Close the comparison" onClick={onClose}><X size={13} /></button></div>
      <div className="card-b rc-b">
        {settings.length ? <p className="rc-set">{settings.map((s) => <span key={s.k} className="chip"><span style={{ color: "var(--text-4)" }}>{label(s.k)}</span>{show(s.was)} → {show(s.now)}</span>)}</p> : <p className="rc-set">Same settings</p>}
        <table className="tbl rc-t">
          <thead><tr><th>Figure</th><th className="r">Then</th><th className="r">Now</th><th className="r">Change</th></tr></thead>
          <tbody>{cards.map((c) => {
            const d = isNum(c.now) && isNum(c.was) ? c.now - c.was : null;
            return <tr key={c.label}><td>{c.label}</td><td className="r num">{show(c.was)}</td><td className="r num">{show(c.now)}</td><td className={`r num${d ? (d > 0 ? " up" : " down") : ""}`}>{d ? `${d > 0 ? "+" : ""}${show(d)}` : ""}</td></tr>;
          })}</tbody>
        </table>
        {nameKey ? (
          <div className="rc-names">
            <div><b className="num">{entered.length}</b> entered {entered.slice(0, 40).map((t) => <button key={t} type="button" className="chip" style={{ color: "var(--up)" }} onClick={() => openQuickLook(t)}>{t}</button>)}</div>
            <div><b className="num">{left.length}</b> left {left.slice(0, 40).map((t) => <button key={t} type="button" className="chip" style={{ color: "var(--down)" }} onClick={() => openQuickLook(t)}>{t}</button>)}</div>
            {moved.length ? <div><b className="num">{moved.length}</b> moved {moved.slice(0, 20).map((m) => <button key={m.t} type="button" className="chip" onClick={() => openQuickLook(m.t)}>{m.t} <span className="num" style={{ color: m.by > 0 ? "var(--up)" : "var(--down)" }}>{m.by > 0 ? "▲" : "▼"}{Math.abs(m.by)}</span></button>)}</div> : null}
            {entered.length + left.length >= 2 && entered.length + left.length <= 8 ? <button type="button" className="btn sm ghost" onClick={() => openCompare([...entered, ...left])}>Compare the names that moved</button> : null}
          </div>
        ) : null}
        {series.length > 2 ? <TimeSeries data={series} series={[{ key: "now", label: "This run", color: "var(--accent)" }, { key: "was", label: "Earlier run", color: "var(--text-3)", dash: true }]} height={220} refLines={[{ y: 1, label: "" }]} format={(v) => `${v.toFixed(2)}×`} /> : null}
      </div>
    </div>
  );
}
