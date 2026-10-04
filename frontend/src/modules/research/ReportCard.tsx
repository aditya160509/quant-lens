"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Check, ClipboardCheck, Download, FlaskConical, Link2, ListChecks, Play, ShieldCheck, Sigma, X } from "lucide-react";
import { DataTable } from "./outputs/tables";
import { DUR } from "@/workspace/prefs";
import { Chip, Segmented } from "@/workspace/ui";
import { reportUrl, shareJob, submitBatch, submitReportCard, submitValidation, useActiveSignal, useJob, useLibrary, type ReportCard } from "./api";
import type { FeatureSpec } from "./types";
import { label } from "./format";

type Mode = "card" | "batch" | "validate";

/**
 * The Report card page: one run grades the active signal on every dimension a referee checks,
 * follows the Novy-Marx & Velikov protocol, and exports a referee-style report. Batch screening
 * and walk-forward validation live here too, because they answer the same "is it real" question.
 */
export function ReportCardPage({ features }: { features: FeatureSpec[] }) {
  const active = useActiveSignal();
  const [mode, setMode] = useState<Mode>("card");
  const [jobs, setJobs] = useState<Partial<Record<Mode, string>>>({});
  const [err, setErr] = useState<string | null>(null);
  const [lookback, setLookback] = useState(3650);
  const [costBps, setCostBps] = useState(10);
  const [longOnly, setLongOnly] = useState(false);
  const base = useMemo(() => ({
    ...(active.expr ? { signal_expr: active.expr } : { signal: "momentum" }),
    ...(active.projectId ? { project_id: active.projectId } : {}),
    lookback_days: lookback, cost_model: { spread_bps: costBps, commission_bps: 1, impact: "sqrt" }, long_only: longOnly,
  }), [active.expr, active.projectId, lookback, costBps, longOnly]);
  const job = useJob(jobs[mode] ?? null);
  const status = job.data?.status;
  const running = status === "queued" || status === "running";
  void features;

  const run = async (m: Mode, fn: () => Promise<{ job_id: string }>) => {
    setErr(null);
    try { const r = await fn(); setJobs((j) => ({ ...j, [m]: r.job_id })); } catch (e) { setErr((e as Error).message); }
  };

  return (
    <div className="island" style={{ overflowY: "auto" }}>
      <div style={{ padding: "22px 22px 30px", maxWidth: 1320 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 14 }}>
          <div className="ov-icon" style={{ width: 40, height: 40, borderRadius: 11 }}><ClipboardCheck size={19} strokeWidth={1.6} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em" }}>Report card</h1>
            <p style={{ marginTop: 4, color: "var(--text-2)", fontSize: 13.5 }}>Every test on one signal, graded the way a referee would, following the Novy-Marx &amp; Velikov (2023) protocol.</p>
          </div>
          <Link href="/research/signal" className="btn sm ghost"><FlaskConical size={12} />{active.expr ? active.name ?? "Formula" : "Momentum (default)"}</Link>
        </div>

        <div className="rc-bar">
          <Segmented<Mode> label="Mode" value={mode} onChange={setMode} options={[{ value: "card", label: "Report card" }, { value: "batch", label: "Batch screen" }, { value: "validate", label: "Walk-forward" }]} />
          <label className="xc"><span>Window</span><select value={lookback} onChange={(e) => setLookback(Number(e.target.value))}>{[[1825, "5 years"], [2555, "7 years"], [3650, "10 years"], [5475, "15 years"], [9125, "25 years"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label className="xc"><span>Cost per trade</span><select value={costBps} onChange={(e) => setCostBps(Number(e.target.value))}>{[0, 5, 10, 20, 40].map((v) => <option key={v} value={v}>{v} bps</option>)}</select></label>
          <label className="xc"><span>Positions</span><select value={longOnly ? "lo" : "ls"} onChange={(e) => setLongOnly(e.target.value === "lo")}><option value="ls">Long-short</option><option value="lo">Long only</option></select></label>
          {mode === "card" ? <button className="btn primary" style={{ marginLeft: "auto" }} disabled={running} onClick={() => run("card", () => submitReportCard(base))}><Play size={11} fill="currentColor" />{running ? "Grading…" : "Run report card"}</button> : null}
        </div>
        {err ? <div className="card" style={{ height: "auto", margin: "10px 0", background: "var(--down-soft)" }}><div className="card-b" style={{ fontSize: 12.5 }}>{err.includes("404") ? "This server does not have the report service yet." : err}</div></div> : null}
        {running ? <div style={{ margin: "14px 0", fontSize: 12.5, color: "var(--text-3)" }}>{progressText(job.data?.progress)}</div> : null}

        {mode === "card" && status === "completed" && job.data?.result ? <Card r={job.data.result as unknown as ReportCard} jobId={jobs.card!} /> : null}
        {mode === "card" && !jobs.card ? <EmptyCard /> : null}
        {mode === "batch" ? <Batch base={base} onRun={(sigs) => run("batch", () => submitBatch(sigs, base))} rows={status === "completed" ? (job.data?.result as unknown as { rows?: Record<string, unknown>[] })?.rows ?? null : null} running={running} /> : null}
        {mode === "validate" ? <Validate onRun={(m, f, e) => run("validate", () => submitValidation(base, m, f, e))} result={status === "completed" ? job.data?.result as unknown as Record<string, unknown> : null} running={running} /> : null}
      </div>
    </div>
  );
}

const DIM_LABEL: Record<string, string> = { significance: "Pricing", factor_zoo: "Novelty", diagnostics: "Model checks" };

const GRADE_TONE: Record<string, string> = { A: "var(--up)", B: "var(--up)", C: "var(--warn)", D: "var(--down)", F: "var(--down)" };

function Card({ r, jobId }: { r: ReportCard; jobId: string }) {
  const [shared, setShared] = useState<string | null>(null);
  return (
    <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: DUR.base }} className="rc-hero">
        <div className="rc-overall" style={{ color: GRADE_TONE[r.overall.grade[0]] ?? "var(--text)" }}>{r.overall.grade}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{r.overall.verdict}</div>
          <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 2 }}>Overall score {Math.round(r.overall.score)} / 100</div>
        </div>
        <span style={{ display: "flex", gap: 6 }}>
          <a className="btn sm ghost" href={reportUrl(jobId, "tex")}><Download size={12} />LaTeX</a>
          <a className="btn sm ghost" href={reportUrl(jobId, "pdf")}><Download size={12} />PDF</a>
          <button className="btn sm ghost" onClick={() => shareJob(jobId).then((s) => { const url = `${location.origin}/research/shared/${s.token}`; void navigator.clipboard?.writeText(url); setShared(url); }).catch(() => setShared("Sharing is not available on this server"))}><Link2 size={12} />{shared ? "Link copied" : "Share"}</button>
        </span>
      </motion.div>

      <div className="rc-grades">
        {r.grades.map((g, i) => (
          <motion.div key={g.dimension} className="rc-grade" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: DUR.base, delay: Math.min(0.12, i * 0.015) }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span className="g" style={{ color: GRADE_TONE[g.grade[0]] ?? "var(--text)" }}>{g.grade}</span>
              <span className="d">{DIM_LABEL[g.dimension] ?? label(g.dimension)}</span>
            </div>
            <div className="bar"><span style={{ width: `${Math.max(2, Math.min(100, g.score))}%`, background: GRADE_TONE[g.grade[0]] ?? "var(--accent)" }} /></div>
            {g.metric ? <div className="m"><span>{g.metric.label}</span><b className="num">{typeof g.metric.value === "number" ? Number(g.metric.value.toPrecision(3)) : g.metric.value}</b></div> : null}
            <p>{g.summary}</p>
          </motion.div>
        ))}
      </div>

      <div className="sig-grid">
        <section className="card" style={{ height: "auto" }}>
          <header className="card-h"><div><h3><ListChecks size={14} /> What a referee will ask</h3><span className="sub">Each check, answered from this run</span></div></header>
          <div className="card-b"><Checks items={r.checklist.map((c) => ({ id: c.id, label: c.question, pass: c.pass, detail: c.detail }))} /></div>
        </section>
        <section className="card" style={{ height: "auto" }}>
          <header className="card-h"><div><h3><ShieldCheck size={14} /> {r.protocol.name}</h3><span className="sub">The academic protocol for testing a new predictor</span></div></header>
          <div className="card-b"><Checks items={r.protocol.steps} /></div>
        </section>
      </div>

      {r.explain?.length ? (
        <section className="card" style={{ height: "auto" }}>
          <header className="card-h"><div><h3><Sigma size={14} /> In plain language</h3><span className="sub">Written from this run&apos;s numbers</span></div></header>
          <div className="card-b" style={{ display: "grid", gap: 8, fontSize: 13.5, lineHeight: 1.6, color: "var(--text-2)" }}>{r.explain.map((s, i) => <p key={i}>{s}</p>)}</div>
        </section>
      ) : null}
    </div>
  );
}

function Checks({ items }: { items: { id: string; label: string; pass: boolean | null; detail: string }[] }) {
  return (
    <div>
      {items.map((c) => (
        <div key={c.id} className="rc-check">
          <span className="ic" style={{ color: c.pass === null ? "var(--text-4)" : c.pass ? "var(--up)" : "var(--down)" }}>{c.pass === null ? "–" : c.pass ? <Check size={13} /> : <X size={13} />}</span>
          <div><div style={{ color: "var(--text)" }}>{c.label}</div><div style={{ color: "var(--text-3)", fontSize: 12 }}>{c.detail}</div></div>
        </div>
      ))}
    </div>
  );
}

function EmptyCard() {
  const dims = ["Pricing", "Robustness", "Placebo", "Regimes", "Model checks", "Decay", "Novelty", "Costs"];
  return (
    <div className="rc-grades" style={{ marginTop: 14, opacity: 0.5 }}>
      {dims.map((d) => <div key={d} className="rc-grade"><div style={{ display: "flex", gap: 8, alignItems: "baseline" }}><span className="g">–</span><span className="d">{d}</span></div><div className="bar"><span style={{ width: "0%" }} /></div><p>Run the report card to grade this.</p></div>)}
    </div>
  );
}

function Batch({ onRun, rows, running }: { base: Record<string, unknown>; onRun: (s: string[]) => void; rows: Record<string, unknown>[] | null; running: boolean }) {
  const lib = useLibrary();
  const [picked, setPicked] = useState<string[]>([]);
  const [extra, setExtra] = useState("");
  const all = [...picked, ...extra.split("\n").map((s) => s.trim()).filter(Boolean)];
  return (
    <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
      <section className="card" style={{ height: "auto" }}>
        <header className="card-h"><div><h3>Screen many signals at once</h3><span className="sub">Each is tested the same way; p-values are corrected for the number tried (Benjamini–Hochberg–Yekutieli)</span></div></header>
        <div className="card-b" style={{ display: "grid", gap: 10 }}>
          <div className="xpills" style={{ maxHeight: 140, overflow: "auto" }}>
            {(lib.data ?? []).map((s) => <button key={s.id} className="pill" aria-pressed={picked.includes(s.id)} onClick={() => setPicked((p) => (p.includes(s.id) ? p.filter((x) => x !== s.id) : [...p, s.id]))}>{s.name}</button>)}
          </div>
          <textarea className="input formula" rows={3} placeholder="Or paste formulas, one per line" value={extra} onChange={(e) => setExtra(e.target.value)} aria-label="Formulas to screen" />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn sm ghost" onClick={() => setPicked((lib.data ?? []).map((s) => s.id))}>Select all published</button>
            <button className="btn primary sm" style={{ marginLeft: "auto" }} disabled={!all.length || running} onClick={() => onRun(all)}><Play size={11} fill="currentColor" />Screen {all.length || ""}</button>
          </div>
        </div>
      </section>
      {rows ? (
        <section className="card" style={{ height: "auto" }}>
          <header className="card-h"><div><h3>Results</h3><span className="sub">{rows.filter((r) => r.survives).length} of {rows.length} survive the multiple-testing correction</span></div></header>
          <div className="card-b flush"><DataTable rows={rows} opts={{ tint: true }} /></div>
        </section>
      ) : null}
    </div>
  );
}

function Validate({ onRun, result, running }: { onRun: (m: string, folds: number, embargo: number) => void; result: Record<string, unknown> | null; running: boolean }) {
  const [method, setMethod] = useState("walk_forward");
  const [folds, setFolds] = useState(6);
  const [embargo, setEmbargo] = useState(21);
  const fRows = (result?.folds as Record<string, unknown>[] | undefined) ?? null;
  return (
    <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
      <section className="card" style={{ height: "auto" }}>
        <header className="card-h"><div><h3>Out-of-sample validation</h3><span className="sub">Walk-forward, or combinatorial purged cross-validation with an embargo (López de Prado)</span></div></header>
        <div className="card-b rc-bar" style={{ margin: 0 }}>
          <Segmented label="Method" value={method} onChange={setMethod} options={[{ value: "walk_forward", label: "Walk-forward" }, { value: "cpcv", label: "Purged CV" }]} />
          <label className="xc"><span>Folds</span><select value={folds} onChange={(e) => setFolds(Number(e.target.value))}>{[4, 6, 8, 10, 12].map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
          <label className="xc"><span>Embargo</span><select value={embargo} onChange={(e) => setEmbargo(Number(e.target.value))}>{[0, 5, 21, 63].map((v) => <option key={v} value={v}>{v} days</option>)}</select></label>
          <button className="btn primary sm" style={{ marginLeft: "auto" }} disabled={running} onClick={() => onRun(method, folds, embargo)}><Play size={11} fill="currentColor" />Validate</button>
        </div>
      </section>
      {result ? (
        <section className="card" style={{ height: "auto" }}>
          <header className="card-h"><div><h3>Folds</h3><span className="sub">{String(result.summary ?? "")}{typeof result.pbo === "number" ? ` · Probability of backtest overfitting ${(result.pbo * 100).toFixed(0)}%` : ""}</span></div>
            {typeof result.pbo === "number" ? <Chip tone={result.pbo < 0.3 ? "up" : result.pbo < 0.5 ? "warn" : "down"}>PBO {(result.pbo * 100).toFixed(0)}%</Chip> : null}</header>
          <div className="card-b flush">{fRows ? <DataTable rows={fRows} /> : null}</div>
        </section>
      ) : null}
    </div>
  );
}

/** The job's progress, however the backend phrases it: a number, a string, or {message, percent}. */
function progressText(p: unknown): string {
  if (typeof p === "number") return `Running every test… ${Math.round(p)}%`;
  if (typeof p === "string") return p;
  if (p && typeof p === "object") {
    const o = p as { message?: string; percent?: number };
    return `${o.message ?? "Running every test…"}${typeof o.percent === "number" ? ` ${Math.round(o.percent)}%` : ""}`;
  }
  return "Running every test…";
}
