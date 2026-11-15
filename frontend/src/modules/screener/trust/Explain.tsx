"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DataTable, Empty } from "@/kit/DataTable";
import { fmtKey, label, num } from "@/modules/research/format";
import { useRuns } from "@/modules/research/api";
import type { FeatureResult, Row } from "@/modules/research/types";
import { send } from "../api";
import { SymbolPick } from "../search/SymbolPick";

export type RunMeta = { id: string; feature_id: string; payload: Record<string, unknown>; metrics: { name: string; expression: string }[] };
export const runOf = (result: FeatureResult) => (result.meta as { run?: RunMeta }).run;

type Check = { filter: string; label: string; column: string; side: "min" | "max"; threshold: number; value: number | null; margin: number | null; passes: boolean; unknown: boolean; sector_percentile: number | null; evidence: { grade: "robust" | "mixed" | "weak"; cite: string } | null };
type Miss = { symbol: string; filter: string; label: string; side: "min" | "max"; value: number | null; threshold: number; relax_by: number | null; unknown: boolean };
type Diff = { filter: string; label: string; passed_value: number | null; failed_value: number | null; threshold: number; failed_unknown: boolean };

const known = (column: string, v: number | null) => (v === null ? "unknown" : fmtKey(column, v));
const bound = (side: "min" | "max", column: string, t: number) => `${side === "min" ? "≥" : "≤"} ${fmtKey(column, t)}`;

/** How well the filter held up out of sample, with its citation; a filter we have not graded shows nothing. */
function Evidence({ e }: { e: Check["evidence"] }) {
  return e ? <span className={`chip ${e.grade === "robust" ? "up" : e.grade === "mixed" ? "warn" : "down"}`} title={e.cite}>{label(e.grade)}</span> : <>–</>;
}

/** Row detail: each filter against this name's value, the margin, its place in its sector and what supports the filter. */
export function WhyHere({ ticker, runId }: { ticker: string; runId: string }) {
  const [other, setOther] = useState<string | null>(null);
  const why = useQuery({ queryKey: ["explain", "why", runId, ticker], queryFn: () => send<{ checks: Check[] }>("POST", "/explain/why", { run_id: runId, symbol: ticker }), retry: false });
  const diff = useQuery({ queryKey: ["explain", "difference", runId, ticker, other], queryFn: () => send<{ filters: Diff[] }>("POST", "/explain/difference", { run_id: runId, symbol: ticker, other }), enabled: other !== null, retry: false });
  if (why.error) return <div role="alert" style={{ color: "var(--down)", fontSize: 12 }}>{why.error.message}</div>;
  const checks = why.data?.checks ?? [];
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <h5 className="insp-h">Why {ticker} is here</h5>
      {why.isLoading ? <div aria-busy="true">Loading</div> : checks.length ? (
        <table className="tbl">
          <thead><tr><th>Filter</th><th className="r">Value</th><th className="r">Limit</th><th className="r">Margin</th><th className="r">Sector percentile</th><th>Evidence</th></tr></thead>
          <tbody>
            {checks.map((c) => (
              <tr key={c.filter}>
                <td className="strong">{c.label}</td>
                <td className="r num">{known(c.column, c.value)}</td>
                <td className="r num">{bound(c.side, c.column, c.threshold)}</td>
                <td className="r num">{c.margin === null ? "unknown" : num(c.margin, 3)}</td>
                <td className="r num">{c.sector_percentile === null ? "unknown" : `${c.sector_percentile.toFixed(0)}`}</td>
                <td><Evidence e={c.evidence} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <Empty text="No range filter set." />}
      {checks.some((c) => c.evidence) ? <ul className="stat-s" style={{ paddingLeft: 16 }}>{checks.filter((c) => c.evidence).map((c) => <li key={c.filter}>{c.label}: {c.evidence?.cite}</li>)}</ul> : null}
      <h5 className="insp-h">Why not another name</h5>
      <SymbolPick onPick={setOther} exclude={[ticker]} />
      {other && diff.data ? (
        diff.data.filters.length ? (
          <table className="tbl">
            <thead><tr><th>Filter</th><th className="r">{ticker}</th><th className="r">{other}</th><th className="r">Limit</th></tr></thead>
            <tbody>{diff.data.filters.map((d) => <tr key={d.filter}><td className="strong">{d.label}</td><td className="r num">{num(d.passed_value, 3)}</td><td className="r num">{d.failed_unknown ? "unknown" : num(d.failed_value, 3)}</td><td className="r num">{d.filter.endsWith("_min") ? "≥" : "≤"} {num(d.threshold, 3)}</td></tr>)}</tbody>
          </table>
        ) : <Empty text={`${other} misses no range filter.`} />
      ) : diff.error ? <div role="alert" style={{ color: "var(--down)", fontSize: 12 }}>{diff.error.message}</div> : null}
    </div>
  );
}

/** Names that miss exactly one range filter, by filter, with the value that would let each in. */
export function NearMisses({ result }: { result: FeatureResult }) {
  const runId = runOf(result)?.id;
  const [pick, setPick] = useState<string | null>(null);
  const res = useQuery({ queryKey: ["explain", "near", runId], queryFn: () => send<{ near_misses: Miss[] }>("POST", "/explain/near-miss", { run_id: runId }), enabled: Boolean(runId), retry: false });
  if (!runId) return <Empty text="No run record." />;
  if (res.error) return <div role="alert" style={{ color: "var(--down)", fontSize: 12 }}>{res.error.message}</div>;
  const all = res.data?.near_misses ?? [];
  if (res.isSuccess && !all.length) return <Empty text="No name misses by just one range filter." />;
  const labels = [...new Map(all.map((m) => [m.filter, m.label])).entries()].map(([filter, text]) => ({ filter, text, n: all.filter((m) => m.filter === filter).length }));
  const rows: Row[] = all.filter((m) => !pick || m.filter === pick).map((m) => ({ ticker: m.symbol, filter: m.label, limit: bound(m.side, "", m.threshold), value: m.value, relax_to: m.value, relax_by: m.relax_by }));
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }} role="group" aria-label="Filter">
        <span className="stat-s" style={{ alignSelf: "center" }}>{all.length.toLocaleString()} names miss exactly one filter</span>
        {labels.map((l) => <button key={l.filter} type="button" className="pill" aria-pressed={pick === l.filter} onClick={() => setPick(pick === l.filter ? null : l.filter)}>{l.text} · {l.n}</button>)}
      </div>
      {res.isLoading ? <div aria-busy="true">Loading</div> : rows.length ? <DataTable rows={rows} opts={{ max: 200, maxHeight: 420 }} /> : <Empty text="No names for this filter." />}
    </div>
  );
}

type DiffResult = { entered: string[]; left: string[]; moved: { symbol: string; from: number; to: number }[]; as_of: (string | null)[]; changed_settings: string[]; counts: number[] };

/** Who entered, left or moved between an earlier run of this screen and this one. */
export function ScreenDiff({ result, featureId }: { result: FeatureResult; featureId: string }) {
  const run = runOf(result);
  const others = useRuns((s) => s.runs).filter((r) => r.featureId === featureId && r.status === "completed" && r.jobId !== run?.id).slice(0, 12);
  const [before, setBefore] = useState<string | null>(null);
  const diff = useQuery({ queryKey: ["explain", "diff", before, run?.id], queryFn: () => send<DiffResult>("POST", "/explain/diff", { before, after: run?.id }), enabled: Boolean(before && run), retry: false });
  if (!run) return <Empty text="No run record." />;
  const d = diff.data;
  const rows: Row[] = d ? [...d.entered.map((t) => ({ ticker: t, change: "Entered" })), ...d.left.map((t) => ({ ticker: t, change: "Left" })), ...d.moved.map((m) => ({ ticker: m.symbol, change: "Moved", from_rank: m.from + 1, to_rank: m.to + 1 }))] : [];
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {others.length ? (
        <label className="xc"><span>Compare with run</span>
          <select value={before ?? ""} onChange={(e) => setBefore(e.target.value || null)}>
            <option value="">Choose</option>
            {others.map((r) => <option key={r.jobId} value={r.jobId}>{new Date(r.startedAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</option>)}
          </select>
        </label>
      ) : <Empty text="No other run." />}
      {diff.error ? <div role="alert" style={{ color: "var(--down)", fontSize: 12 }}>{diff.error.message}</div> : null}
      {d ? (
        <>
          <div className="stat-s">{d.counts[0].toLocaleString()} names as of {d.as_of[0] ?? "unknown"} → {d.counts[1].toLocaleString()} names as of {d.as_of[1] ?? "unknown"} · {d.entered.length} entered · {d.left.length} left · {d.moved.length} moved{d.changed_settings.length ? ` · settings changed: ${d.changed_settings.map(label).join(", ")}` : ""}</div>
          {rows.length ? <DataTable rows={rows} opts={{ max: 200, maxHeight: 420 }} /> : <Empty text="No change." />}
        </>
      ) : null}
    </div>
  );
}
