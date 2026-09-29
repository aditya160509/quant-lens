"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2, Play, RotateCcw, Search, SlidersHorizontal, Square, X } from "lucide-react";
import { useFeature, useResearchJob, useResearchManifest } from "./api";
import { fmt } from "./format";
import { RenderOutput } from "./renderers";
import { StudyForm, defaultsFor, toPayload, validate } from "./StudyForm";
import "./research-v2.css";

function Elapsed({ since }) {
  const [now, setNow] = useState(since);
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(id); }, []);
  return <>{Math.max(0, Math.round((now - since) / 1000))}s</>;
}

export function ResearchV2Workbench({ featureId }) {
  const { data: feature, isLoading, error } = useFeature(featureId);
  if (isLoading) return <main className="rv2"><div className="rv2-center"><Loader2 className="spin" /> Loading module…</div></main>;
  if (error || !feature) return <main className="rv2"><div className="rv2-center rv2-error">Research V2 is unreachable: {error?.message ?? "unknown feature"}.</div></main>;
  return <Workbench feature={feature} />;
}

function Workbench({ feature }) {
  const [form, setForm] = useState(() => defaultsFor(feature));
  const [formOpen, setFormOpen] = useState(true);
  const [filter, setFilter] = useState("");
  const job = useResearchJob(feature.id);
  const errors = validate(feature, form);
  const running = ["submitting", "queued", "running"].includes(job.status);
  const result = job.result;
  const outputs = useMemo(() => feature.outputs.filter((o) => o.title.toLowerCase().includes(filter.toLowerCase())), [feature, filter]);
  const produced = (o) => {
    const v = result?.[o.source]?.[o.key];
    return v !== undefined && v !== null && !(Array.isArray(v) && !v.length);
  };
  const run = () => {
    if (Object.keys(errors).length) return;
    job.run(toPayload(feature, form));
    setFormOpen(false);
  };
  const caveats = result?.meta?.research_caveats ?? [];
  const notRun = Object.entries(result?.tables ?? {}).filter(([k]) => k.endsWith("_status")).flatMap(([, v]) => v);

  return <main className="rv2">
    <header className="rv2-top">
      <Link href="/labs/research-v2" className="rv2-brand">ATLAS <span>/ RESEARCH</span></Link>
      <div className="rv2-crumb">F{feature.id} / {feature.name}</div>
      <div className="rv2-spacer" />
      <RunStatus job={job} />
      <button type="button" className="rv2-btn ghost" onClick={() => setFormOpen((o) => !o)}><SlidersHorizontal size={14} /> {formOpen ? "Hide study" : "Configure study"}</button>
      {running
        ? <button type="button" className="rv2-btn" onClick={job.cancel}><Square size={13} /> Cancel</button>
        : <button type="button" className="rv2-btn primary" onClick={run} disabled={Object.keys(errors).length > 0}><Play size={14} /> Run study</button>}
    </header>

    <section className="rv2-head"><p>Research V2 · Feature {feature.id}</p><h1>{feature.name}</h1><span>{feature.description}</span></section>

    {formOpen ? <section className="rv2-panel">
      <StudyForm feature={feature} form={form} setForm={setForm} errors={errors} />
      <footer><button type="button" className="rv2-btn ghost" onClick={() => setForm(defaultsFor(feature))}><RotateCcw size={13} /> Defaults</button><button type="button" className="rv2-btn primary" onClick={run} disabled={running || Object.keys(errors).length > 0}><Play size={14} /> Run study</button></footer>
    </section> : null}

    {job.error ? <div className="rv2-alert"><AlertTriangle size={15} /><div><strong>The study did not run.</strong><span>{job.error}</span></div></div> : null}
    {notRun.map((r) => <div className="rv2-alert" key={r.design}><AlertTriangle size={15} /><div><strong>{r.design} not run</strong><span>{r.reason}</span></div></div>)}
    {caveats.length ? <div className="rv2-caveats">{caveats.map((c) => <p key={c}>{c}</p>)}</div> : null}

    {result?.summary_cards?.length ? <section className="rv2-cards">{result.summary_cards.map((c) => <div key={c.label}><span>{c.label}</span><strong>{fmt(c.value, 4)}</strong></div>)}</section> : null}
    {result?.meta?.headline ? <p className="rv2-headline">{result.meta.headline}</p> : null}

    <section className="rv2-work">
      <aside className="rv2-rail">
        <label><Search size={13} /><input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter outputs" />{filter ? <button type="button" onClick={() => setFilter("")} aria-label="Clear filter"><X size={12} /></button> : null}</label>
        <nav>{outputs.map((o) => <a key={o.key} href={`#out-${o.key}`} className={result && !produced(o) ? "muted" : ""}>{o.title}</a>)}</nav>
      </aside>
      <div className="rv2-stack">
        {!result && !running ? <div className="rv2-center muted">Configure the study and press <b>Run study</b>. {feature.outputs.length} outputs will appear here.</div> : null}
        {running && !result ? <div className="rv2-center"><Loader2 className="spin" /> Running {feature.name}…</div> : null}
        {result ? outputs.map((o) => <article key={o.key} id={`out-${o.key}`} className={`rv2-card ${o.primary ? "primary" : ""}`}>
          <header><h3>{o.title}</h3>{o.description ? <p>{o.description}</p> : null}</header>
          <RenderOutput output={o} response={result} />
        </article>) : null}
      </div>
    </section>
  </main>;
}

function RunStatus({ job }) {
  const label = { idle: "Not run", submitting: "Submitting", queued: "Queued", running: "Running", completed: "Complete", failed: "Failed", cancelled: "Cancelled" }[job.status] ?? job.status;
  return <span className={`rv2-status ${job.status}`}>{["submitting", "queued", "running"].includes(job.status) ? <Loader2 size={12} className="spin" /> : null}{label}{job.startedAt && job.status === "running" ? <> · <Elapsed since={job.startedAt} /></> : null}</span>;
}

export function ResearchV2Home() {
  const { data: features, isLoading, error } = useResearchManifest();
  return <main className="rv2 rv2-home">
    <section className="rv2-hero"><p>ATLAS / RESEARCH V2</p><h1>Evidence before conviction.</h1><span>Ten modules for testing a signal, trying to break it, and documenting what survives, with point-in-time data and the estimators a referee expects.</span></section>
    {isLoading ? <div className="rv2-center"><Loader2 className="spin" /> Loading modules…</div> : null}
    {error ? <div className="rv2-center rv2-error">Research V2 is unreachable: {error.message}</div> : null}
    <section className="rv2-grid">{(features ?? []).map((f) => <Link key={f.id} href={`/labs/research-v2/feature-${f.id}`}><p>F{f.id}</p><h2>{f.name}</h2><span>{f.description}</span><b>{f.outputs.length} outputs · {f.inputs.length} inputs</b></Link>)}</section>
  </main>;
}
