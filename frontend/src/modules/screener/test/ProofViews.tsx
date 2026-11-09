"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { API_BASE_URL } from "@/lib/apiBase";
import { isNum, out, pct } from "@/modules/research/format";
import { useStudies } from "@/modules/research/store";
import type { ViewProps } from "@/modules/research/outputs/types";
import { SCREENER_BASE } from "../base";

type Ledger = { trials: number; deflated_sharpe_hurdle: number | null; pbo?: number | null; haircut_sharpe?: { observed: number | null; haircut: number | null } };
type Point = { date: string; strategy: number; benchmark: number | null };

const DAYS = 252;
const sharpe = (r: number[]) => {
  if (r.length < 2) return null;
  const m = r.reduce((a, b) => a + b, 0) / r.length;
  const sd = Math.sqrt(r.reduce((a, b) => a + (b - m) ** 2, 0) / (r.length - 1));
  return sd > 0 ? (m / sd) * Math.sqrt(DAYS) : null;
};
const returns = (v: number[]) => v.slice(1).map((x, i) => x / v[i] - 1);
const fmt = (v: number | null, d = 2) => (isNum(v) ? v.toFixed(d) : "Unknown");

/** Seeded so the same result always prints the same interval. */
function rng(seed: number) {
  return () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

/** Moving-block bootstrap of the Sharpe ratio: 1,000 resamples, 21-day blocks. */
function bootstrap(r: number[]): [number, number] | null {
  const block = 21, draws = 1000;
  if (r.length < block * 4) return null;
  const rand = rng(1), s: number[] = [];
  for (let d = 0; d < draws; d++) {
    const x: number[] = [];
    while (x.length < r.length) { const at = Math.floor(rand() * (r.length - block)); x.push(...r.slice(at, at + block)); }
    const v = sharpe(x.slice(0, r.length));
    if (v !== null) s.push(v);
  }
  s.sort((a, b) => a - b);
  return s.length ? [s[Math.floor(s.length * 0.025)], s[Math.floor(s.length * 0.975)]] : null;
}

function curve(result: ViewProps["result"]): Point[] {
  return out(result, "equity_curve").filter((r) => isNum(r.strategy) && typeof r.date === "string") as unknown as Point[];
}

/** Trial count on the Research ledger, deflated Sharpe, PBO, bootstrap and the benchmark control, then the ML Validate hand-off. */
export function ProofPanel({ result }: ViewProps) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ledger = useQuery({ queryKey: ["screener", "ledger", (result.meta as { data_version?: string }).data_version, curve(result).length], queryFn: async () => (await (await fetch(`${SCREENER_BASE}/ledger`)).json()) as Ledger, retry: false });
  const pts = curve(result), r = returns(pts.map((p) => p.strategy)), sr = sharpe(r);
  const bench = pts.filter((p) => isNum(p.benchmark)), br = sharpe(returns(bench.map((p) => p.benchmark as number)));
  const ci = bootstrap(r), l = ledger.data;
  const pbo = out(result, "cscv_pbo")[0]?.pbo;
  const hurdle = l?.deflated_sharpe_hurdle ?? null;

  const prove = async () => {
    setBusy(true); setError(null);
    try {
      const csv = `date,return\n${pts.slice(1).map((p, i) => `${p.date},${r[i]}`).join("\n")}\n`;
      const form = new FormData();
      form.append("file", new File([csv], "screen-returns.csv", { type: "text/csv" }));
      const res = await fetch(`${API_BASE_URL}/ml/v2/uploads?kind=returns`, { method: "POST", body: form });
      const body = (await res.json().catch(() => ({}))) as { upload_id?: string; detail?: string };
      if (!res.ok || !body.upload_id) throw new Error(typeof body.detail === "string" ? body.detail : `Upload failed (${res.status})`);
      useStudies.setState((s) => ({ forms: { ...s.forms, mlvalidate: { ...(s.forms.mlvalidate ?? {}), upload_id: body.upload_id, artifact_id: "" } } }));
      router.push("/ml/validate");
    } catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); } finally { setBusy(false); }
  };

  // Every start date from the curve's first, one per year, held to the end.
  const starts = pts.filter((p, i) => i === 0 || p.date.slice(0, 4) !== pts[i - 1].date.slice(0, 4)).map((p) => {
    const at = pts.indexOf(p), seg = pts.slice(at), rr = returns(seg.map((x) => x.strategy));
    return { date: p.date, total: seg[seg.length - 1].strategy / p.strategy - 1, sharpe: sharpe(rr), days: rr.length };
  }).filter((s) => s.days >= 63);

  return (
    <div className="proof">
      <div className="kv-row"><span>Trials on the Research ledger</span><b className="num">{l ? l.trials.toLocaleString() : ledger.isError ? "Unknown" : "…"}</b></div>
      <div className="kv-row"><span>Sharpe, this run</span><b className="num">{fmt(sr)}</b></div>
      <div className="kv-row"><span>Deflated Sharpe hurdle at that trial count</span><b className="num">{fmt(hurdle)}</b></div>
      <div className="kv-row"><span>Clears the hurdle</span><b>{isNum(sr) && isNum(hurdle) ? (sr > hurdle ? "Yes" : "No") : "Unknown"}</b></div>
      <div className="kv-row"><span>Probability of backtest overfitting</span><b className="num">{isNum(pbo) ? pct(pbo, 0) : "Unknown"}</b></div>
      <div className="kv-row"><span>Sharpe 95% interval, block bootstrap</span><b className="num">{ci ? `${ci[0].toFixed(2)} to ${ci[1].toFixed(2)}` : "Unknown"}</b></div>
      <div className="kv-row"><span>Benchmark Sharpe, same dates</span><b className="num">{fmt(br)}</b></div>
      <table className="num" style={{ width: "100%", marginTop: 12 }}>
        <thead><tr><th align="left">Start</th><th align="right">Total return</th><th align="right">Sharpe</th></tr></thead>
        <tbody>{starts.map((s) => <tr key={s.date}><td>{s.date}</td><td align="right">{pct(s.total, 1)}</td><td align="right">{fmt(s.sharpe)}</td></tr>)}</tbody>
      </table>
      <button className="btn" style={{ marginTop: 12 }} disabled={busy || r.length < 2} onClick={prove}>{busy ? "Uploading" : "Prove it in ML Validate"}</button>
      {error ? <div role="alert" style={{ color: "var(--down)", marginTop: 8 }}>{error}</div> : null}
    </div>
  );
}
