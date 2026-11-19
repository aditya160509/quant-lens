"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { studio, type StrategyCard } from "../api";
import { specDiff } from "./blocks";

type RunSum = { total_return?: number; sharpe?: number | null; trades?: number };
type Compared = { a: string; b: string; diffs: Record<string, string>; runs: Record<string, RunSum> };
const pct = (v?: number) => (v === undefined ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);

/** Compare this strategy with another (usually its branch or parent): file diffs, latest results side by side, and merge a branch back (B-128). */
export function BranchDialog({ id, name, spec, onClose, onMerged }: { id: string; name: string; spec: Record<string, unknown>; onClose: () => void; onMerged: (target: string) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [list, setList] = useState<StrategyCard[]>([]);
  const [other, setOther] = useState("");
  const [cmp, setCmp] = useState<Compared | null>(null);
  const [conflicts, setConflicts] = useState<string[] | null>(null);
  const [fields, setFields] = useState<[string, string, string][]>([]);
  useEffect(() => { ref.current?.showModal(); void studio<{ strategies: StrategyCard[] }>("GET", "/strategies").then((r) => setList(r.strategies.filter((s) => s.id !== id)), () => undefined); }, [id]);
  useEffect(() => {
    if (!other) { setCmp(null); setFields([]); return; }
    void studio<Compared>("GET", `/strategies/${id}/compare/${other}`).then(setCmp, (e: Error) => toast.error(e.message));
    void studio<{ spec: Record<string, unknown> }>("GET", `/strategies/${other}`).then((o) => setFields(specDiff(spec, o.spec).filter(([k]) => !/^(code|files|name|groups)/.test(k))), () => undefined);
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
      {cmp ? (
        <div className="sh-compare-body">
          <div className="kpis">
            {[cmp.a, cmp.b].map((sid) => <div key={sid} className="kpi"><span>{label(sid)}</span><b>{pct(cmp.runs[sid]?.total_return)}</b><i className="dv-delta">Sharpe {cmp.runs[sid]?.sharpe?.toFixed(2) ?? "—"} · {cmp.runs[sid]?.trades ?? "—"} trades</i></div>)}
          </div>
          {fields.length ? <section><h3>Rules and settings</h3>{fields.map(([k, a, b]) => <div key={k} className="bd-diff"><span>{k}</span><del>{a || "—"}</del><ins>{b || "—"}</ins></div>)}</section> : null}
          {Object.keys(cmp.diffs).length ? Object.entries(cmp.diffs).map(([f, d]) => (
            <details key={f} open><summary>{f}</summary><pre className="bd-code bd-udiff">{d.split("\n").map((l, i) => <span key={i} data-k={l.startsWith("+") && !l.startsWith("+++") ? "add" : l.startsWith("-") && !l.startsWith("---") ? "del" : l.startsWith("@@") ? "hunk" : undefined}>{l}{"\n"}</span>)}</pre></details>
          )) : fields.length ? null : <p className="dv-empty">No differences</p>}
        </div>
      ) : null}
    </dialog>
  );
}
