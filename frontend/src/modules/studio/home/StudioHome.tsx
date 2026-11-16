"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Archive, Copy, FileJson, Play, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { DataTable } from "@/kit/DataTable";
import { pct } from "@/modules/research/format";
import { defaultsFor } from "@/modules/research/StudyForm";
import { useStudies } from "@/modules/research/store";
import type { FeatureSpec } from "@/modules/research/types";
import { studio, useHome, useTemplates, type Compiled, type StrategyCard, type Template } from "../api";
import { FreshnessPill } from "../RunHeader";
import "../studio.css";

const fail = (e: unknown) => toast.error(e instanceof Error ? e.message : "Failed");
const day = (t: number) => new Date(t * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="sh-spark" />;
  const lo = Math.min(...values), hi = Math.max(...values);
  const d = values.map((v, i) => `${i ? "L" : "M"}${(i / (values.length - 1)) * 100},${(28 - ((v - lo) / (hi - lo || 1)) * 26).toFixed(2)}`).join("");
  return <svg className="sh-spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden><path d={d} fill="none" stroke={values.at(-1)! >= values[0] ? "var(--up)" : "var(--down)"} strokeWidth={1.5} vectorEffect="non-scaling-stroke" /></svg>;
}

/** Studio Home: find a strategy, see what needs attention, start a new one. */
export default function StudioHome({ features }: { features: FeatureSpec[] }) {
  const home = useHome();
  const templates = useTemplates();
  const qc = useQueryClient();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"last" | "name">("last");
  const [picked, setPicked] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["studio", "home"] });
  // Skeletons wait 150 ms, so a fast load never flashes them.
  useEffect(() => { const id = setTimeout(() => setSlow(true), 150); return () => clearTimeout(id); }, []);

  /** Point the Backtest form at this strategy and go there; `go` runs it at once. */
  const openIn = (id: string, query: string) => {
    const f = features.find((x) => x.id === "st01");
    if (f) useStudies.getState().setForm("st01", (cur) => ({ ...cur, strategy_id: id }), defaultsFor(f));
    router.push(`/studio/backtest?${query}`);
  };
  const open = (s: StrategyCard) => openIn(s.id, s.last_run ? `run=${s.last_run.job_id}` : "go=1");
  const fromTemplate = (t: Template) => studio<StrategyCard>("POST", "/strategies", { spec: t.spec }).then((s) => { void refresh(); openIn(s.id, "go=1"); }, fail);
  const duplicate = (id: string) => studio("POST", `/strategies/${id}/duplicate`).then(() => { void refresh(); toast.success("Duplicated"); }, fail);
  const archive = (id: string) => studio("PATCH", `/strategies/${id}`, { archived: true }).then(() => { void refresh(); toast.success("Archived"); }, fail);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || document.querySelector("dialog[open]")) return;
      if (e.key === "/") { e.preventDefault(); search.current?.focus(); }
      if (e.key.toLowerCase() === "n") { e.preventDefault(); router.push("/studio/build"); }
      if (e.key.toLowerCase() === "d" && picked) { e.preventDefault(); void duplicate(picked); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (home.isError && !home.data) {
    return <div className="island"><div className="st-skip" role="alert">Strategy list failed: {(home.error as Error).message}<button className="btn sm" style={{ marginTop: 10 }} onClick={() => home.refetch()}>Retry</button></div></div>;
  }
  const all = home.data?.strategies ?? [];
  const list = all.filter((s) => !q || `${s.name} ${s.tags.join(" ")} ${s.folder}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => (sort === "name" ? a.name.localeCompare(b.name) : (b.last_run?.at ?? b.updated) - (a.last_run?.at ?? a.updated)));
  const loading = home.isLoading;

  return (
    <div className="island">
      <div className="sh" data-testid="studio-home">
        <div className="sh-top">
          <h1>Studio</h1>
          {home.data ? <FreshnessPill f={home.data.freshness} /> : null}
          <label className="sh-q"><Search size={13} /><input ref={search} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" aria-label="Search strategies" /></label>
          <select className="input" style={{ width: 120, height: 30 }} aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value as "last" | "name")}><option value="last">Last run</option><option value="name">Name</option></select>
          <button className="btn" onClick={() => dialog.current?.showModal()}><FileJson size={14} />Import</button>
          <Link className="btn primary" href="/studio/build"><Plus size={14} />New</Link>
        </div>

        {home.data?.attention.length ? (
          <section>
            <h2>Needs attention</h2>
            <div className="sh-attn" data-testid="attention">
              {home.data.attention.map((a, i) => <div key={i}><i className={a.tone === "red" ? "red" : ""} /><span>{a.text}</span><Link className="btn sm" href={a.action.href}>{a.action.label}</Link></div>)}
            </div>
          </section>
        ) : null}

        <section>
          <h2>Strategies</h2>
          {loading ? (slow ? <div className="sh-grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skel-card" style={{ height: 168 }} />)}</div> : null) : !all.length ? (
            <div className="sh-empty" data-testid="home-empty">
              <Link href="/studio/build"><Plus size={18} />Blank strategy</Link>
              <a href="#templates"><Copy size={18} />From a template</a>
              <button type="button" onClick={() => dialog.current?.showModal()}><FileJson size={18} />Import a JSON spec</button>
            </div>
          ) : (
            <div className="sh-grid" data-testid="strategy-cards">
              {list.map((s) => (
                <div key={s.id} className="sh-card" role="button" tabIndex={0} aria-pressed={picked === s.id} onClick={() => setPicked(picked === s.id ? null : s.id)} onDoubleClick={() => open(s)}
                  onKeyDown={(e) => { if (e.key === "Enter") open(s); }}>
                  <div className="sh-name"><span>{s.name}</span><em>v{s.version}</em></div>
                  {s.last_run ? (
                    <>
                      <Spark values={s.last_run.spark} />
                      <div className="sh-fig"><b className={s.last_run.total_return >= 0 ? "st-up" : "st-down"}>{s.last_run.total_return > 0 ? "+" : ""}{pct(s.last_run.total_return, 0)}</b>
                        <span>Sharpe {s.last_run.sharpe?.toFixed(2) ?? "—"} · {s.last_run.trades} trades · {day(s.last_run.at)}</span></div>
                    </>
                  ) : <div className="st-skip" style={{ minHeight: 76 }}>not run</div>}
                  <div className="sh-chips">
                    <span className="chip">not validated</span>
                    <span className="chip">{s.trials.raw} raw / {s.trials.effective} effective trials</span>
                    {s.has_draft ? <span className="chip warn">draft</span> : null}
                  </div>
                  <div className="sh-actions" onClick={(e) => e.stopPropagation()}>
                    <button className="btn sm" onClick={() => (s.last_run ? open(s) : openIn(s.id, "go=1"))}><Play size={12} />{s.last_run ? "Open" : "Run"}</button>
                    <Link className="btn sm ghost" href={`/studio/build/${s.id}`}>Edit</Link>
                    <button className="btn sm ghost" onClick={() => duplicate(s.id)}><Copy size={12} />Duplicate</button>
                    <button className="btn sm ghost icon" aria-label={`Archive ${s.name}`} title="Archive" style={{ marginLeft: "auto" }} onClick={() => archive(s.id)}><Archive size={12} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {home.data?.recent_runs.length ? (
          <section>
            <h2>Recent runs</h2>
            <DataTable rows={home.data.recent_runs.map((r) => ({ strategy: r.strategy ?? "Unsaved draft", version: r.version, result: r.headline, run: new Date(r.at * 1000).toLocaleString() }))} opts={{ maxHeight: 260 }} />
          </section>
        ) : null}

        <section id="templates">
          <h2>Templates</h2>
          <div className="sh-grid">
            {(templates.data ?? []).map((t) => (
              <button key={t.name} type="button" className="sh-card" onClick={() => fromTemplate(t)} data-testid="template">
                <div className="sh-name"><span>{t.name}</span></div>
                <p className="sh-rule">{t.rule}</p>
              </button>
            ))}
          </div>
        </section>
      </div>
      <ImportDialog ref={dialog} onSaved={(s) => { void refresh(); dialog.current?.close(); openIn(s.id, "go=1"); }} />
    </div>
  );
}

/** Paste or load a Studio JSON spec; it is recompiled and its findings shown before anything is saved (H-4). */
function ImportDialog({ ref, onSaved }: { ref: React.RefObject<HTMLDialogElement | null>; onSaved: (s: StrategyCard) => void }) {
  const [text, setText] = useState("");
  const [checked, setChecked] = useState<Compiled | null>(null);
  const [error, setError] = useState<string | null>(null);
  const send = (save: boolean) => {
    setError(null);
    let spec: unknown;
    try { spec = JSON.parse(text); } catch { setError("Not valid JSON"); return; }
    void studio<{ compile: Compiled; saved: StrategyCard | null }>("POST", `/strategies/import${save ? "?save=true" : ""}`, { spec: (spec as { spec?: unknown }).spec ?? spec }).then((d) => {
      setChecked(d.compile);
      if (d.saved) onSaved(d.saved);
    }, (e: Error) => { setChecked(null); setError(e.message); });
  };
  return (
    <dialog ref={ref} className="sh-import" aria-label="Import a strategy" onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <b style={{ fontSize: 15 }}>Import a strategy</b>
      <textarea className="input" value={text} onChange={(e) => { setText(e.target.value); setChecked(null); }} placeholder='{"name": "…", "entry_long": "close > sma(close, 200)"}' aria-label="Strategy JSON" spellCheck={false} />
      <input type="file" accept="application/json,.json" aria-label="JSON file" onChange={(e) => { const f = e.target.files?.[0]; if (f) void f.text().then((t) => { setText(t); setChecked(null); }); }} />
      {error ? <div className="sh-find" role="alert"><b className="error">error</b>{error}</div> : null}
      {checked ? (
        <div style={{ display: "grid", gap: 4 }} data-testid="import-findings">
          {checked.findings.length ? checked.findings.map((f, i) => <div key={i} className="sh-find"><b className={f.severity}>{f.severity}</b><span>{f.message}{f.token ? ` (line ${f.line}: ${f.token})` : ""}</span></div>) : <div className="sh-find"><b className="st-up">compiles</b><span style={{ whiteSpace: "pre-line" }}>{checked.description}</span></div>}
        </div>
      ) : null}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn" onClick={() => ref.current?.close()}>Cancel</button>
        <button className="btn" disabled={!text.trim()} onClick={() => send(false)}>Check</button>
        <button className="btn primary" disabled={!checked?.ok} onClick={() => send(true)}>Save</button>
      </div>
    </dialog>
  );
}
