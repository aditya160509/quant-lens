"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, FileJson, Play, Plus, RotateCcw, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { DataTable } from "@/kit/DataTable";
import { pct } from "@/modules/research/format";
import { defaultsFor } from "@/modules/research/StudyForm";
import { useStudies } from "@/modules/research/store";
import type { FeatureSpec } from "@/modules/research/types";
import { STUDIO_BASE } from "../base";
import { studio, useHome, useTemplates, type Compiled, type StrategyCard, type Template } from "../api";
import { FreshnessPill } from "../RunHeader";
import { Segmented } from "@/workspace/ui";
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
  const [status, setStatus] = useState<string | null>(null);
  const [trashOpen, setTrashOpen] = useState(false);
  const term = q.trim();
  // Search reaches into rules, code, tags and hypotheses on the server; names alone filter instantly here.
  const found = useQuery({ queryKey: ["studio", "search", term], queryFn: () => studio<{ strategies: StrategyCard[] }>("GET", `/search?q=${encodeURIComponent(term)}`), enabled: term.length > 1, staleTime: 30_000 });
  const trash = useQuery({ queryKey: ["studio", "trash"], queryFn: () => studio<{ strategies: StrategyCard[]; days: number }>("GET", "/trash"), enabled: trashOpen });
  const [picked, setPicked] = useState<string | null>(null);
  const params = useSearchParams();
  const view = params?.get("layout") === "table" ? "table" : "cards";
  const setView = (v: "cards" | "table") => { const u = new URL(location.href); if (v === "table") u.searchParams.set("layout", "table"); else u.searchParams.delete("layout"); router.replace(u.pathname + u.search, { scroll: false }); };
  const [slow, setSlow] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["studio", "home"] });
  // Skeletons wait 150 ms, so a fast load never flashes them.
  useEffect(() => { const id = setTimeout(() => setSlow(true), 150); return () => clearTimeout(id); }, []);

  /** Point the Backtest form at this strategy and go there; `go` runs it at once. */
  const openIn = (id: string, query: string) => {
    try { localStorage.setItem("studio:strategy", id); } catch { /* storage blocked */ }
    const f = features.find((x) => x.id === "st01");
    if (f) useStudies.getState().setForm("st01", (cur) => ({ ...cur, strategy_id: id }), defaultsFor(f));
    router.push(`/studio/backtest?${query}`);
  };
  const open = (s: StrategyCard) => openIn(s.id, s.last_run ? `run=${s.last_run.job_id}` : "go=1");
  const fromTemplate = (t: Template) => studio<StrategyCard>("POST", "/strategies", { spec: t.spec }).then((s) => { void refresh(); openIn(s.id, "go=1"); }, fail);
  const duplicate = (id: string) => studio("POST", `/strategies/${id}/duplicate`).then(() => { void refresh(); toast.success("Duplicated"); }, fail);
  const toTrash = (s: StrategyCard) => studio("POST", `/strategies/${s.id}/trash`).then(() => {
    void refresh();
    toast((t) => <span style={{ display: "inline-flex", gap: 10, alignItems: "center" }}>{s.name} moved to trash<button className="btn sm" onClick={() => { toast.dismiss(t.id); void restore(s.id); }}>Undo</button></span>);
  }, fail);
  const restore = (id: string) => studio("POST", `/strategies/${id}/trash?restore=true`).then(() => { void refresh(); void qc.invalidateQueries({ queryKey: ["studio", "trash"] }); }, fail);
  const purge = (s: StrategyCard) => {
    const typed = window.prompt(`Delete ${s.name} for good? Type its name to confirm.`);
    if (typed === null) return;
    void studio("DELETE", `/strategies/${s.id}?confirm=${encodeURIComponent(typed)}`).then(() => { void qc.invalidateQueries({ queryKey: ["studio", "trash"] }); toast.success("Deleted"); }, fail);
  };
  const rerun = (ids: string[]) => studio<{ jobs: unknown[]; refused: { reason: string }[] }>("POST", "/strategies/rerun", { ids, payload: {} }).then((r) => toast.success(`${r.jobs.length} queued${r.refused.length ? `, ${r.refused.length} refused` : ""}`), fail);
  const exportZip = (ids: string[]) => fetch(`${STUDIO_BASE}/strategies/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) })
    .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(`Export failed (${r.status})`))))
    .then((b) => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "strategies.zip"; a.click(); URL.revokeObjectURL(a.href); }, fail);
  const combine = (ids: string[]) => {
    const f = features.find((x) => x.id === "st04");
    if (f) useStudies.getState().setForm("st04", (cur) => ({ ...cur, strategy_ids: ids.join(" ") }), defaultsFor(f));
    router.push("/studio/portfolio");
  };

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
  const all = (home.data?.strategies ?? []).filter((s) => !s.trashed && !s.archived);
  const hitIds = term.length > 1 && found.data ? new Set(found.data.strategies.map((x) => x.id)) : null;
  const counts = all.reduce<Record<string, number>>((m, s) => ({ ...m, [s.status ?? "Draft"]: (m[s.status ?? "Draft"] ?? 0) + 1 }), {});
  const list = all.filter((s) => (!status || (s.status ?? "Draft") === status) && (!term || (hitIds ? hitIds.has(s.id) : `${s.name} ${s.tags.join(" ")} ${s.folder}`.toLowerCase().includes(term.toLowerCase()))))
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
          <Segmented<"cards" | "table"> label="Layout" value={view} onChange={setView} options={[{ value: "cards", label: "Cards" }, { value: "table", label: "Table" }]} />
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

        {home.data?.live?.strategies.length ? (
          <section>
            <h2>Running</h2>
            <div className="sh-live" data-testid="live-strip">
              {home.data.live.strategies.map((l) => (
                <Link key={l.id} href="/studio/live" className="sh-live-item">
                  <b>{l.name}</b><span className="chip">{l.status}</span>
                  {l.today_pnl != null ? <span className={l.today_pnl >= 0 ? "st-up" : "st-down"}>today {l.today_pnl > 0 ? "+" : ""}{pct(l.today_pnl, 2)}</span> : null}
                  {l.paper_return != null ? <span>paper {pct(l.paper_return, 1)}</span> : null}
                </Link>
              ))}
              <span className="sh-live-meta">{home.data.live.alerts} alerts today{home.data.live.heartbeat ? <>, last check {day(home.data.live.heartbeat)}</> : null}</span>
            </div>
          </section>
        ) : null}

        <section>
          <div className="sh-head">
            <h2>Strategies</h2>
            <div className="sh-status" role="group" aria-label="Filter by status">
              {(["Draft", "Backtested", "Validated", "Paper", "Live"] as const).filter((k) => counts[k]).map((k) => (
                <button key={k} type="button" className="pill" aria-pressed={status === k} onClick={() => setStatus(status === k ? null : k)}>{k}<span className="num">{counts[k]}</span></button>
              ))}
            </div>
            <button type="button" className="btn sm ghost" aria-pressed={trashOpen} onClick={() => setTrashOpen(!trashOpen)}><Trash2 size={12} />Trash</button>
          </div>
          {loading ? (slow ? <div className="sh-grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skel-card" style={{ height: 168 }} />)}</div> : null) : !all.length ? (
            <div className="sh-empty" data-testid="home-empty">
              <Link href="/studio/build"><Plus size={18} />Blank strategy</Link>
              <a href="#templates"><Copy size={18} />From a template</a>
              <button type="button" onClick={() => dialog.current?.showModal()}><FileJson size={18} />Import a JSON spec</button>
            </div>
          ) : view === "table" ? (
            <DataTable rows={list.map((s) => ({ strategy: s.name, version: s.version, total_return: s.last_run?.total_return ?? null, sharpe: s.last_run?.sharpe ?? null, trades: s.last_run?.trades ?? null,
              status: s.status ?? "Draft", trend: s.last_run?.spark ?? [], last_run: s.last_run ? day(s.last_run.at) : null, raw_trials: s.trials.raw, effective_trials: s.trials.effective }))}
              opts={{ bulk: (rows: Record<string, unknown>[], clear: () => void) => { const ids = rows.map((r) => list.find((x) => x.name === r.strategy && x.version === r.version)?.id).filter((x): x is string => Boolean(x)); return (<>
                <button className="btn sm" onClick={() => { void rerun(ids); clear(); }}>Re-run</button>
                <button className="btn sm" disabled={ids.length < 2} onClick={() => combine(ids)}>Combine</button>
                <button className="btn sm" onClick={() => void exportZip(ids)}>Export</button>
              </>); }, rowActions: (r: Record<string, unknown>) => { const s = list.find((x) => x.name === r.strategy && x.version === r.version); return s ? (
                <span style={{ display: "inline-flex", gap: 4 }}>
                  <button className="btn sm" onClick={() => (s.last_run ? open(s) : openIn(s.id, "go=1"))}><Play size={12} />{s.last_run ? "Open" : "Run"}</button>
                  <Link className="btn sm ghost" href={`/studio/build/${s.id}`}>Edit</Link>
                  <button className="btn sm ghost icon" aria-label={`Duplicate ${s.name}`} title="Duplicate" onClick={() => duplicate(s.id)}><Copy size={12} /></button>
                </span>) : null; } }} />
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
                        <span>Sharpe {s.last_run.sharpe?.toFixed(2) ?? "—"}</span><span>{s.last_run.trades} trades</span><span>{day(s.last_run.at)}</span></div>
                    </>
                  ) : <div className="st-skip" style={{ minHeight: 76 }}>not run</div>}
                  <div className="sh-chips">
                    <span className={`chip${s.validation_expired ? " warn" : ""}`}>{s.validation_expired ? "validation expired" : (s.status ?? "Draft")}</span>
                    <span className="chip">{s.trials.raw} raw / {s.trials.effective} effective trials</span>
                    {s.has_draft ? <span className="chip warn">draft</span> : null}
                  </div>
                  <div className="sh-actions" onClick={(e) => e.stopPropagation()}>
                    <button className="btn sm" onClick={() => (s.last_run ? open(s) : openIn(s.id, "go=1"))}><Play size={12} />{s.last_run ? "Open" : "Run"}</button>
                    <Link className="btn sm ghost" href={`/studio/build/${s.id}`}>Edit</Link>
                    <button className="btn sm ghost" onClick={() => duplicate(s.id)}><Copy size={12} />Duplicate</button>
                    <button className="btn sm ghost icon" aria-label={`Move ${s.name} to trash`} title="Move to trash" style={{ marginLeft: "auto" }} onClick={() => toTrash(s)}><Trash2 size={12} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {trashOpen ? (
          <section>
            <h2>Trash</h2>
            {trash.data?.strategies.length ? (
              <div className="sh-trash">
                {trash.data.strategies.map((s) => (
                  <div key={s.id}><b>{s.name}</b><span>v{s.version}</span>{s.purge_at ? <span>deleted for good {day(s.purge_at)}</span> : null}
                    <button className="btn sm" onClick={() => void restore(s.id)}><RotateCcw size={12} />Restore</button>
                    <button className="btn sm ghost" onClick={() => purge(s)}>Delete now</button>
                  </div>
                ))}
              </div>
            ) : <p className="sh-trash-empty">{trash.isLoading ? "Loading…" : `Empty. Strategies stay here ${trash.data?.days ?? 30} days.`}</p>}
          </section>
        ) : null}

        {home.data?.recent_runs.length ? (
          <section>
            <h2>Recent runs</h2>
            <DataTable rows={home.data.recent_runs.map((r) => ({ strategy: r.strategy ?? (r.feature === "st04" ? "Portfolio" : "Unsaved draft"), version: r.version, result: r.headline, run: new Date(r.at * 1000).toLocaleString(), changed_since: r.settings_changed ? "yes" : "" }))} opts={{ maxHeight: 260 }} />
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
