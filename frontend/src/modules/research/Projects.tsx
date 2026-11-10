"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, FolderKanban, Lock, NotebookPen, Plus, Unlock } from "lucide-react";
import { MenuItem, PopMenu, type MenuAt } from "@/workspace/ui";
import { createProject, preregister, setHoldout, useActiveSignal, useHoldout, useLedger, useProjects } from "./api";

/**
 * The project every run belongs to. A project is where trials are counted (the multiple-testing
 * ledger), where a holdout is sealed, and where hypotheses are written down before running.
 */
export function ProjectSwitcher() {
  const active = useActiveSignal();
  const projects = useProjects();
  const qc = useQueryClient();
  const [at, setAt] = useState<MenuAt | null>(null);
  const [naming, setNaming] = useState<string | null>(null);
  const current = projects.data?.find((p) => p.id === active.projectId);
  if (projects.isError) return null;
  const create = async () => {
    const name = naming?.trim();
    setNaming(null);
    if (!name) return;
    const p = await createProject(name);
    await qc.invalidateQueries({ queryKey: ["research", "projects"] });
    active.set({ projectId: p.id });
  };
  return (
    <div className="nav-proj" style={{ padding: "0 10px 6px" }}>
      {naming !== null ? (
        <input className="input" autoFocus value={naming} placeholder="Project name, then Enter" aria-label="Project name" style={{ height: 30 }}
          onChange={(e) => setNaming(e.target.value)} onBlur={() => void create()} onKeyDown={(e) => { if (e.key === "Enter") void create(); if (e.key === "Escape") setNaming(null); }} />
      ) : (
        <button className="proj-btn" aria-haspopup="menu" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setAt({ x: r.left, y: r.bottom + 4 }); }}>
          <FolderKanban size={13} /><span>{current?.name ?? "No project"}</span><ChevronDown size={12} style={{ marginLeft: "auto" }} />
        </button>
      )}
      <PopMenu at={at} onClose={() => setAt(null)} width={240}>
        <div className="hd">Projects</div>
        <MenuItem onClick={() => active.set({ projectId: null })}>No project</MenuItem>
        {(projects.data ?? []).map((p) => <MenuItem key={p.id} onClick={() => active.set({ projectId: p.id })}>{p.name}</MenuItem>)}
        <div className="sep" />
        <MenuItem icon={<Plus size={13} />} onClick={() => setNaming("")}>New project…</MenuItem>
      </PopMenu>
    </div>
  );
}

/** "Trials 37 · DSR hurdle 0.81": how many things were tried in this project, and what that costs. */
export function LedgerChip() {
  const { projectId } = useActiveSignal();
  const ledger = useLedger(projectId);
  const [open, setOpen] = useState(false);
  if (!projectId || !ledger.data) return null;
  const l = ledger.data;
  return (
    <span style={{ position: "relative" }}>
      <button className="chip" onClick={() => setOpen((v) => !v)} title="Multiple-testing ledger for this project">
        Trials <b className="num">{l.trials}</b>{l.deflated_sharpe_hurdle != null ? <> · SR hurdle <b className="num">{l.deflated_sharpe_hurdle.toFixed(2)}</b></> : null}{l.pbo != null ? <> · PBO <b className="num">{Math.round(l.pbo * 100)}%</b></> : null}
      </button>
      {open ? (
        <div className="menu" style={{ position: "absolute", top: "calc(100% + 6px)", left: 0, width: 380, zIndex: 20, padding: 12 }}>
          <div style={{ fontSize: 12.5, color: "var(--text-2)", lineHeight: 1.55, marginBottom: 8 }}>
            {l.trials} trials on {l.distinct_signals} signals in this project. Every extra trial raises the Sharpe ratio a result needs before it counts as real
            {l.deflated_sharpe_hurdle != null ? <> (now <b>{l.deflated_sharpe_hurdle.toFixed(2)}</b>, deflated Sharpe ratio)</> : null}.
            {l.haircut_sharpe ? <> The best result&apos;s Sharpe of {l.haircut_sharpe.observed.toFixed(2)} is worth about <b>{l.haircut_sharpe.haircut.toFixed(2)}</b> after the Harvey–Liu haircut.</> : null}
          </div>
          <div style={{ maxHeight: 220, overflow: "auto" }}>
            {l.entries.slice(0, 40).map((e) => (
              <div key={e.job_id} className="kv-row"><span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 240 }}>{e.signal}</span><b className="num">{e.t_stat != null ? `t ${e.t_stat.toFixed(2)}` : "–"}</b></div>
            ))}
          </div>
          <Holdout projectId={projectId} />
          <Prereg projectId={projectId} />
        </div>
      ) : null}
    </span>
  );
}

function Holdout({ projectId }: { projectId: string }) {
  const h = useHoldout(projectId);
  const qc = useQueryClient();
  const [date, setDate] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["research", "holdout", projectId] });
  if (h.isError) return null;
  const sealed = h.data?.sealed_after && !h.data.unsealed;
  return (
    <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
      <div className="insp-h"><Lock size={12} /> Holdout vault</div>
      {sealed ? (
        <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12.5 }}>
          <span>Data after <b>{h.data!.sealed_after}</b> is sealed. Every run in this project stops before it.</span>
          <button className="btn sm ghost" style={{ marginLeft: "auto" }} onClick={() => { if (confirm("Unseal the holdout? You can only do this once; after that it no longer counts as untouched.")) void setHoldout(projectId, { unseal: true }).then(refresh); }}><Unlock size={12} />Unseal once</button>
        </div>
      ) : h.data?.unsealed ? (
        <span style={{ fontSize: 12.5, color: "var(--text-3)" }}>The holdout was unsealed; results that use it are no longer out of sample.</span>
      ) : (
        <div style={{ display: "flex", gap: 6 }}>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Seal data after" style={{ height: 28 }} />
          <button className="btn sm" disabled={!date} onClick={() => void setHoldout(projectId, { sealed_after: date }).then(refresh)}><Lock size={12} />Seal</button>
        </div>
      )}
    </div>
  );
}

function Prereg({ projectId }: { projectId: string }) {
  const { expr, name } = useActiveSignal();
  const [hyp, setHyp] = useState("");
  const [sign, setSign] = useState(1);
  const [test, setTest] = useState("Fama-MacBeth t-stat");
  const [done, setDone] = useState(false);
  return (
    <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
      <div className="insp-h"><NotebookPen size={12} /> Pre-register before running</div>
      {done ? <span style={{ fontSize: 12.5, color: "var(--up)" }}>Recorded. Runs on this signal are marked pre-registered.</span> : (
        <div style={{ display: "grid", gap: 6 }}>
          <textarea className="input" rows={2} placeholder="Hypothesis, e.g. high-momentum stocks outperform over the next month" value={hyp} onChange={(e) => setHyp(e.target.value)} aria-label="Hypothesis" />
          <div style={{ display: "flex", gap: 6 }}>
            <select className="input" value={sign} onChange={(e) => setSign(Number(e.target.value))} aria-label="Expected sign" style={{ height: 28 }}><option value={1}>Positive premium</option><option value={-1}>Negative premium</option></select>
            <select className="input" value={test} onChange={(e) => setTest(e.target.value)} aria-label="Primary test" style={{ height: 28 }}>{["Fama-MacBeth t-stat", "Long-short t-stat", "Spanning alpha", "Report card grade"].map((t) => <option key={t}>{t}</option>)}</select>
            <button className="btn sm primary" disabled={!hyp.trim()} onClick={() => void preregister({ project_id: projectId, hypothesis: hyp, expected_sign: sign, primary_test: test, signal: expr ?? name ?? "built-in" }).then(() => setDone(true))}>Record</button>
          </div>
        </div>
      )}
    </div>
  );
}
