"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { studio, type StrategyCard } from "../api";
import { specDiff } from "./blocks";
import { minMax } from "./devStats";

type RunSum = { total_return?: number; sharpe?: number | null; trades?: number };
type Compared = { a: string; b: string; diffs: Record<string, string>; runs: Record<string, RunSum> };
/** Growth of 1 over the finite points; null when there are under two or the first is not a positive level. */
const norm = (c: number[]) => { const f = c.filter(Number.isFinite); return f.length > 1 && f[0]! > 0 ? f.map((v) => v / f[0]!) : null; };
const pct = (v?: number) => (v === undefined ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);

/** Compare this strategy with another (usually its branch or parent): file diffs, latest results side by side, and merge a branch back (B-128). */
export function BranchDialog({ id, name, spec, onClose, onMerged }: { id: string; name: string; spec: Record<string, unknown>; onClose: () => void; onMerged: (target: string) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [list, setList] = useState<StrategyCard[]>([]);
  const [other, setOther] = useState("");
  const [cmp, setCmp] = useState<Compared | null>(null);
  const [conflicts, setConflicts] = useState<string[] | null>(null);
  const [fields, setFields] = useState<[string, string, string][]>([]);
  const [curves, setCurves] = useState<Record<string, number[]>>({});
  const [status, setStatus] = useState<"idle" | "loading" | { error: string }>("idle");
  useEffect(() => { ref.current?.showModal(); void studio<{ strategies: StrategyCard[] }>("GET", "/strategies").then((r) => setList(r.strategies.filter((s) => s.id !== id)), () => undefined); }, [id]);
  useEffect(() => {
    setCmp(null); setFields([]); setCurves({});
    if (!other) { setStatus("idle"); return; }
    // One request set per selection; switching aborts the last, so a late answer for an earlier pick never lands.
    const request = new AbortController(), signal = request.signal;
    setStatus("loading");
    const last = (sid: string) => studio<{ spark?: number[] }[]>("GET", `/strategies/${sid}/timeline`, undefined, signal).then((t) => [...t].reverse().find((v) => (v.spark?.length ?? 0) > 1)?.spark ?? [], () => []);
    void Promise.all([
      studio<Compared>("GET", `/strategies/${id}/compare/${other}`, undefined, signal),
      last(id), last(other),
      studio<{ spec: Record<string, unknown> }>("GET", `/strategies/${other}`, undefined, signal).then((o) => specDiff(spec, o.spec).filter(([k]) => !/^(code|files|name|groups)/.test(k)), () => []),
    ]).then(([c, a, b, f]) => { if (signal.aborted) return; setCmp(c); setCurves({ [id]: a, [other]: b }); setFields(f); setStatus("idle"); },
      (e: Error) => { if (!signal.aborted) setStatus({ error: e.message }); });
    return () => request.abort();
  }, [id, other, spec]);
  const label = (sid: string) => (sid === id ? name : list.find((s) => s.id === sid)?.name ?? sid);
  const merge = (resolution?: "ours" | "theirs") => void studio<{ version: number }>("POST", `/strategies/${other}/merge`, { source: id, ...(resolution ? { resolution } : {}) })
    .then((r) => { toast.success(`Merged into ${label(other)} as v${r.version}`); onMerged(other); }, (e: Error & { status?: number; detail?: { conflicts?: string[] } }) => { if (e.status === 409) setConflicts(e.detail?.conflicts ?? []); else toast.error(e.message); });

  return (
    <dialog ref={ref} className="sh-compare" aria-label="Compare branches" onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <div className="sh-compare-head">
        <b>{name} vs</b>
        <select className="input" aria-label="Compare with" value={other} onChange={(e) => { setOther(e.target.value); setConflicts(null); }} style={{ width: "auto" }}>
          <option value="">Pick a strategy…</option>
          {list.map((s) => <option key={s.id} value={s.id}>{s.name} · v{s.version}</option>)}
        </select>
        <span style={{ flex: 1 }} />
        {other ? <button className="btn sm primary" onClick={() => merge()}>Merge into {label(other)}</button> : null}
        <button className="btn sm ghost" onClick={() => ref.current?.close()}>Close</button>
      </div>
      {conflicts ? (
        <div className="bd-ro"><b>Both changed</b><span>{conflicts.join(", ")}</span>
          <button className="btn sm" onClick={() => merge("ours")}>Keep {label(other)}</button><button className="btn sm" onClick={() => merge("theirs")}>Take {name}</button></div>
      ) : null}
      {status === "loading" ? <p className="dv-empty">Loading comparison</p> : typeof status === "object" ? <p className="dv-empty">Compare failed: {status.error}</p> : null}
      {cmp ? (
        <div className="sh-compare-body">
          <div className="kpis">
            {[cmp.a, cmp.b].map((sid) => <div key={sid} className="kpi"><span>{label(sid)}</span><b>{pct(cmp.runs[sid]?.total_return)}</b><i className="dv-delta">Sharpe {cmp.runs[sid]?.sharpe?.toFixed(2) ?? "—"} · {cmp.runs[sid]?.trades ?? "—"} trades</i></div>)}
          </div>
          {Object.values(curves).some((c) => c.length > 1) ? (() => {
            const n = [cmp.a, cmp.b].map((sid) => norm(curves[sid] ?? []));
            if (!n.some(Boolean)) return <section><h3>Equity</h3><p className="dv-empty">No positive starting equity to compare</p></section>;
            const [lo, hi] = minMax(n.flatMap((c) => c ?? [])), W = 600, H = 120;
            return <section><h3>Equity</h3><svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="Equity of both strategies">
              {n.map((c, k) => (c ? <path key={k} fill="none" strokeWidth="1.6" stroke={k ? "var(--s2)" : "var(--s1)"} d={c.map((v, i) => `${i ? "L" : "M"}${(i / (c.length - 1)) * W},${H - ((v - lo) / (hi - lo || 1)) * H}`).join("")} /> : null))}
            </svg><p className="bd-meta bd-legend"><i style={{ background: "var(--s1)" }} />{label(cmp.a)}<i style={{ background: "var(--s2)" }} />{label(cmp.b)}</p></section>;
          })() : null}
          {fields.length ? <section><h3>Rules and settings</h3>{fields.map(([k, a, b]) => <div key={k} className="bd-diff"><span>{k}</span><del>{a || "—"}</del><ins>{b || "—"}</ins></div>)}</section> : null}
          {Object.keys(cmp.diffs).length ? Object.entries(cmp.diffs).map(([f, d]) => (
            <details key={f} open><summary>{f}</summary><pre className="bd-code bd-udiff">{d.split("\n").map((l, i) => <span key={i} data-k={l.startsWith("+") && !l.startsWith("+++") ? "add" : l.startsWith("-") && !l.startsWith("---") ? "del" : l.startsWith("@@") ? "hunk" : undefined}>{l}{"\n"}</span>)}</pre></details>
          )) : fields.length ? null : <p className="dv-empty">No differences</p>}
        </div>
      ) : null}
    </dialog>
  );
}
