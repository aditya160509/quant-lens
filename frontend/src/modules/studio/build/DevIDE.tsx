"use client";

import { DiffEditor } from "@monaco-editor/react";
import Link from "next/link";
import { BookOpen, Bug, CaseSensitive, Columns2, Lock, RotateCcw, Tag, Unlock, FileCode2, FilePlus2, GitBranch, LayoutTemplate, ListTree, Pencil, Regex, Search, Trash2, Upload, WholeWord, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import toast from "react-hot-toast";
import { SERIES } from "@/charts/core";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import { studio, usePyTemplates } from "../api";
import { CodeEditor, type EditorAction, type Problem } from "./CodeEditor";

type Log = { date: string; symbol: string | null; line: number; text: string; level: string; fields?: Record<string, unknown> | null };
type Point = { date: string; symbol: string | null; value: number | null };
type Frame = { file: string; line: number; column: number; function: string };
export type DevPreview = {
  status: string; reason?: string; line?: number | null;
  problem?: { file?: string | null; line?: number | null; column?: number | null; exception_type?: string | null; traceback?: Frame[] | null } | null;
  trades: Record<string, unknown>[]; bars?: { date: string; close: number }[]; logs?: Log[] | null; plots?: Record<string, Point[]> | null; plot_charts?: Record<string, string> | null;
  marks?: { date: string; symbol: string; label: string }[] | null; tables?: Record<string, { date: string; symbol: string | null; cells: Record<string, unknown> }[]> | null;
  warmup?: { bars: number; first_eligible_date: string | null } | null; settings_overrides?: Record<string, unknown> | null;
  order_lines?: { file: string; line: number; count: number; dates: string[] }[] | null; locals?: Record<string, unknown> | null;
  invariants?: { count: number; rows: { date: string; symbol: string | null; file: string; line: number; text: string }[] } | null;
};
type Profile = { lines?: { file?: string; line: number; seconds: number; hits?: number; source?: string }[]; functions?: { function?: string; name?: string; seconds: number; calls?: number }[] };
export type QuickRun = { job_id: string; level: "quick" | "full"; status: string; progress?: { percent?: number; message?: string; partial?: { symbols?: number; bars?: number; elapsed_seconds?: number; budget_seconds?: number } } | null;
  error?: string | null; delta?: { total_return: number | null; sharpe: number | null; trades: number | null } | null; result?: { meta?: { headline?: string; total_return?: number; metrics?: Record<string, number | null> } } };
type Sym = { name: string; kind: string; line: number; column: number; children: Sym[] };
type Debug = { date: string; symbol: string; bar_index: number; state: Record<string, unknown>; context: Record<string, number | null>; orders: Record<string, unknown>[]; fills: Record<string, unknown>[];
  previous_date: string | null; next_date: string | null; breakpoint?: { file: string; line: number; hit_count: number; locals: Record<string, unknown> } | null; equity_change?: number | null };
type QC = { ok: boolean; code: string; symbols: string[]; converted: { line: number; before: string; after: string }[]; unconverted: { line: number; source: string; reason: string }[] };
type Member = { name: string; kind: string; signature: string | null; documentation: string | null };
type Version = { version: number; created: number; actor: string };
type Timeline = Version & { name: string; tags: string[]; locked: boolean; sharpe: number | null; total_return: number | null; spark: number[] };
type Snapshot = { at: number; files: Record<string, string> };
type Snippet = { id: string; name: string; prefix: string; body: string; description: string };
type RunSum = { total_return?: number; sharpe?: number | null; trades?: number };
type Tab = "problems" | "output" | "plots" | "trades" | "results" | "debug";
type Rail = "files" | "outline" | "search" | "versions" | "docs" | "templates";
type Spec = { code: string; files?: Record<string, string>; params: Record<string, { value: number; min?: number | null; max?: number | null; step?: number | null }>; [k: string]: unknown };
export type Saved = "saved" | "draft" | "saving" | "conflict" | "new";

const store = {
  get: (k: string, f: number) => { try { return Number(localStorage.getItem(k)) || f; } catch { return f; } },
  set: (k: string, v: number) => { try { localStorage.setItem(k, String(v)); } catch { /* blocked */ } },
};
const show = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(4)) : typeof v === "object" ? JSON.stringify(v) : String(v));
const pct = (v?: number) => (v === undefined ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
const DOC_SCOPES = ["ctx", "portfolio_ctx", "numpy", "pandas", "math", "statistics"];
const RAILS: [Rail, ReactNode, string][] = [
  ["files", <FileCode2 key="f" size={15} />, "Files"], ["outline", <ListTree key="o" size={15} />, "Outline"], ["search", <Search key="s" size={15} />, "Search"],
  ["versions", <GitBranch key="v" size={15} />, "Versions"], ["docs", <BookOpen key="d" size={15} />, "Docs"], ["templates", <LayoutTemplate key="t" size={15} />, "Starters"],
];

/** Variables at a paused bar: name and value, numbers right-aligned. */
function KV({ rows }: { rows: Record<string, unknown> }) {
  return <dl className="dv-kv">{Object.entries(rows).map(([k, v]) => <div key={k}><dt>{k}</dt><dd data-num={typeof v === "number" || undefined}>{show(v)}</dd></div>)}</dl>;
}

/** Find every match of a query in the project files. */
function finder(query: string, opt: { regex: boolean; caseSensitive: boolean; word: boolean }): RegExp | null {
  if (!query) return null;
  try {
    const body = opt.regex ? query : query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(opt.word ? `\\b(?:${body})\\b` : body, opt.caseSensitive ? "g" : "gi");
  } catch { return null; }
}

/** Build › Dev: a project rail, the editor in tabs, Problems / Output / Plots / Trades / Debug below, preview and checks on the right, a status bar. */
export function DevIDE({ spec, edit, symbol, prev, side, onSave, onRun, onFullRun, compileProblems, strategyId, versions, runs, saved, trial, readOnly, onReload, version, stale, onPause, font, quick, onQuickRun, onCancel }: {
  spec: Spec; edit: (next: Partial<Spec>) => void; symbol: string; prev: DevPreview | null; side: ReactNode;
  onSave: () => void; onRun: () => void; onFullRun: () => void; compileProblems: Problem[];
  strategyId?: string; versions: Version[]; runs: Record<string, RunSum>; saved: Saved; trial?: ReactNode; readOnly?: boolean; onReload?: () => void; version?: number; stale?: boolean; onPause?: (date: string | null) => void; font?: number;
  quick?: QuickRun | null; onQuickRun?: (level: "quick" | "full") => void; onCancel?: () => void;
}) {
  const files = useMemo(() => ({ "main.py": spec.code, ...(spec.files ?? {}) }), [spec.code, spec.files]);
  const [open, setOpen] = useState<string[]>(["main.py"]);
  const [active, setActive] = useState("main.py");
  const [rail, setRail] = useState<Rail>("files");
  const [railOpen, setRailOpen] = useState(true);
  const [panelOpen, setPanelOpen] = useState(true);
  const [tab, setTab] = useState<Tab>("problems");
  const [lint, setLint] = useState<Problem[]>([]);
  const [outline, setOutline] = useState<Sym[]>([]);
  const [cursor, setCursor] = useState({ line: 1, column: 1 });
  const [reveal, setReveal] = useState<{ line: number; column?: number; n: number } | null>(null);
  const [panel, setPanel] = useState(() => store.get("studio:dev:panel", 260));
  const [logQ, setLogQ] = useState("");
  const [logLevel, setLogLevel] = useState<string>("all");
  const [plotsOn, setPlotsOn] = useState<Record<string, boolean>>({});
  const [dbg, setDbg] = useState<Debug | null>(null);
  const [dbgDate, setDbgDate] = useState("");
  const [cond, setCond] = useState("");
  const [bps, setBps] = useState<Record<string, number[]>>({});
  const [q, setQ] = useState(""); const [rep, setRep] = useState("");
  const [opt, setOpt] = useState({ regex: false, caseSensitive: false, word: false });
  const [docs, setDocs] = useState<(Member & { scope: string })[] | null>(null);
  const [docQ, setDocQ] = useState("");
  const [diff, setDiff] = useState<{ version: number; files: Record<string, string> } | null>(null);
  const [lastPreview, setLastPreview] = useState<string | null>(null);
  const [qc, setQc] = useState<QC | null>(null);
  const [split, setSplit] = useState<string | null>(null);
  const [profile, setProfile] = useState<Profile | "loading" | null>(null);
  const [strict, setStrict] = useState(() => { try { return localStorage.getItem("studio:dev:strict") === "1"; } catch { return false; } });
  const [timeline, setTimeline] = useState<Timeline[]>([]);
  const [snaps, setSnaps] = useState<Snapshot[]>([]);
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  const selection = useRef("");
  const insertAt = useRef<((text: string) => void) | null>(null);
  const qcRef = useRef<HTMLDialogElement>(null);
  const pyTemplates = usePyTemplates();
  const source = files[active] ?? "";

  const setFile = (name: string, text: string) => (name === "main.py" ? edit({ code: text }) : edit({ files: { ...(spec.files ?? {}), [name]: text } }));
  const replaceFiles = (next: Record<string, string>) => {
    const all = { ...files, ...next };
    const { "main.py": code, ...rest } = all;
    edit({ code, files: rest });
  };
  const goto = (file: string, line: number, column?: number) => { if (!(file in files)) return; setDiff(null); setOpen((o) => (o.includes(file) ? o : [...o, file])); setActive(file); setReveal({ line, column, n: Date.now() }); };
  const close = (f: string) => { const rest = open.filter((x) => x !== f); setOpen(rest.length ? rest : ["main.py"]); if (active === f) setActive(rest.at(-1) ?? "main.py"); };
  const toggleBp = (line: number) => setBps((b) => { const cur = b[active] ?? []; return { ...b, [active]: cur.includes(line) ? cur.filter((x) => x !== line) : [...cur, line].sort((x, y) => x - y) }; });

  useEffect(() => {
    if (!source.trim()) { setLint([]); setOutline([]); return; }
    const t = setTimeout(() => {
      void studio<{ problems: Problem[] }>("POST", "/build/check", { code: source, file: active, files, strictness: strict ? "strict" : "basic", params: Object.fromEntries(Object.entries(spec.params).map(([k, p]) => [k, p.value])) }).then((r) => setLint(r.problems), () => undefined);
      void studio<Sym[]>("POST", "/build/outline", { code: source }).then(setOutline, () => undefined);
    }, 300);
    return () => clearTimeout(t);
  }, [source, active, files, spec.params, strict]);
  useEffect(() => {
    if (rail !== "versions" || !strategyId) return;
    void studio<Timeline[]>("GET", `/strategies/${strategyId}/timeline`).then(setTimeline, () => undefined);
    void studio<Snapshot[]>("GET", `/strategies/${strategyId}/history`).then(setSnaps, () => undefined);
  }, [rail, strategyId, versions.length, saved]);
  useEffect(() => { void studio<Snippet[]>("GET", "/snippets").then(setSnippets, () => undefined); }, []);
  const versionAct = (path: string, body?: unknown, msg?: string) => strategyId && void studio("POST", `/strategies/${strategyId}${path}`, body).then(() => { if (msg) toast.success(msg); onReload?.(); }, (e: Error) => toast.error(e.message));
  const labelVersion = (v: Timeline) => {
    const name = window.prompt(`Name v${v.version}`, v.name); if (name === null) return;
    const tags = window.prompt("Tags, comma separated", v.tags.join(", ")); if (tags === null) return;
    void studio("PUT", `/strategies/${strategyId}/versions/${v.version}/label`, { name, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) }).then(() => studio<Timeline[]>("GET", `/strategies/${strategyId}/timeline`).then(setTimeline), (e: Error) => toast.error(e.message));
  };
  const lockVersion = (v: number | null) => void studio("PUT", `/strategies/${strategyId}/lock`, { version: v }).then(() => studio<Timeline[]>("GET", `/strategies/${strategyId}/timeline`).then(setTimeline), (e: Error) => toast.error(e.message));
  const saveSnippet = () => {
    const body = selection.current; if (!body.trim()) return toast.error("Select some code first");
    const name = window.prompt("Snippet name")?.trim(); if (!name) return;
    const prefix = window.prompt("Trigger prefix", name.toLowerCase().replace(/\W+/g, "_").slice(0, 20))?.trim(); if (!prefix) return;
    void studio<Snippet>("POST", "/snippets", { name, prefix, body }).then((sn) => { setSnippets((x) => [...x, sn]); toast.success(`Saved ${name}`); }, (e: Error) => toast.error(e.message));
  };
  useEffect(() => { if (prev) setLastPreview(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })); }, [prev]);
  useEffect(() => {
    if (rail !== "docs" || docs) return;
    void Promise.all(DOC_SCOPES.map((scope) => studio<Member[]>("POST", "/build/complete", { scope, code: "" }).then((ms) => ms.map((m) => ({ ...m, scope })), () => []))).then((all) => setDocs(all.flat()));
  }, [rail, docs]);

  const runtime: Problem[] = prev?.status === "error" ? [{ severity: "error", file: prev.problem?.file ?? "main.py", line: prev.problem?.line ?? prev.line ?? 1, column: prev.problem?.column ?? 1, end_column: 200, code: prev.problem?.exception_type ?? "runtime", message: prev.reason ?? "Run failed" }] : [];
  const broken: Problem[] = (prev?.invariants?.rows ?? []).filter((r) => r.file === active).slice(0, 50).map((r) => ({ severity: "error", file: r.file, line: r.line, column: 1, end_column: 200, code: "invariant", message: `${r.text} (${r.symbol ?? ""} ${r.date})` }));
  const problems = [...lint, ...compileProblems.filter((p) => p.file === active), ...runtime, ...broken];
  const errors = problems.filter((p) => p.severity === "error").length, warnings = problems.length - errors;
  const logRe = finder(logQ, opt);
  const logs = (prev?.logs ?? []).filter((l) => (logLevel === "all" || l.level === logLevel) && (!logRe || (logRe.lastIndex = 0, logRe.test(`${l.date} ${l.symbol ?? ""} ${l.text}`))));
  const plots = Object.entries(prev?.plots ?? {});
  const re = finder(q, opt);
  const hits = re ? Object.entries(files).flatMap(([f, text]) => text.split("\n").flatMap((line, i) => { re.lastIndex = 0; return re.test(line) ? [{ file: f, line: i + 1, text: line }] : []; })) : [];

  const debug = (body: Record<string, unknown>) => {
    const date = String(body.date || dbg?.date || dbgDate || (prev?.trades.at(-1)?.entry_date ?? ""));
    if (!date) return toast.error("Pick a date to stop at");
    setTab("debug"); setPanelOpen(true);
    void studio<Debug>("POST", "/build/debug", { spec, symbol, date, ...body }).then((d) => { setDbg(d); setDbgDate(d.date); onPause?.(d.date); if (d.breakpoint) goto(d.breakpoint.file, d.breakpoint.line); }, (e: Error) => toast.error(e.message));
  };
  const startDebug = () => {
    const bp = Object.entries(bps).flatMap(([file, lines]) => lines.map((line) => ({ file, line })))[0];
    debug(bp ? { date: dbgDate || (prev?.bars?.[0]?.date ?? ""), breakpoint: { ...bp, condition: cond || null } } : {});
  };
  const addFile = () => {
    const n = window.prompt("File name", "helpers.py")?.trim();
    if (!n) return;
    if (!/^[a-z_][a-z0-9_]*\.py$/i.test(n)) return toast.error("Use a Python file name like helpers.py");
    if (n in files) return toast.error("That file exists");
    edit({ files: { ...(spec.files ?? {}), [n]: "" } }); goto(n, 1);
  };
  const renameFile = (f: string) => {
    const n = window.prompt("Rename to", f)?.trim();
    if (!n || n === f) return;
    if (!/^[a-z_][a-z0-9_]*\.py$/i.test(n) || n in files) return toast.error("Pick a new Python file name");
    const { [f]: text, ...rest } = spec.files ?? {};
    edit({ files: { ...rest, [n]: text ?? "" } }); setOpen((o) => o.map((x) => (x === f ? n : x))); if (active === f) setActive(n);
  };
  const dupFile = (f: string) => { let n = f.replace(/\.py$/, "_copy.py"); while (n in files) n = n.replace(/\.py$/, "_copy.py"); edit({ files: { ...(spec.files ?? {}), [n]: files[f] } }); goto(n, 1); };
  const dropFile = (f: string) => { const { [f]: _, ...rest } = spec.files ?? {}; edit({ files: rest }); close(f); toast(`${f} deleted · ⌘Z to undo`); };
  const replaceAll = () => {
    if (!re) return;
    const next = Object.fromEntries(Object.entries(files).map(([f, t]) => [f, t.replace(re, rep)]));
    replaceFiles(next); toast.success(`Replaced ${hits.length} line${hits.length === 1 ? "" : "s"}`);
  };
  const openDiff = (v: number) => {
    if (!strategyId) return;
    void studio<{ files: Record<string, string> }>("GET", `/strategies/${strategyId}/files?version=${v}`).then((r) => setDiff({ version: v, files: r.files }), (e: Error) => toast.error(e.message));
  };
  const runProfile = () => {
    setTab("results"); setPanelOpen(true); setProfile("loading");
    void studio<{ profile?: Profile }>("POST", "/build/profile", { spec, symbol }).then((r) => setProfile(r.profile ?? {}), (e: Error) => { setProfile(null); toast.error(e.message); });
  };
  useEffect(() => {
    if (!quick || !["queued", "running"].includes(quick.status)) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel?.(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [quick, onCancel]);
  const drag = (e: React.PointerEvent) => {
    const y0 = e.clientY, h0 = panel;
    const move = (m: PointerEvent) => setPanel(Math.min(Math.max(h0 - (m.clientY - y0), 120), window.innerHeight * 0.7));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); setPanel((h) => { store.set("studio:dev:panel", h); return h; }); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };

  const actions: EditorAction[] = [
    { id: "studio.debug", label: "Debug: start", keys: (m) => [m.KeyCode.F5], run: () => startDebug() },
    { id: "studio.bp", label: "Debug: toggle breakpoint", keys: (m) => [m.KeyCode.F9], run: (line) => toggleBp(line) },
    { id: "studio.step", label: "Debug: step one bar", keys: (m) => [m.KeyCode.F10], run: () => debug({ step: 1 }) },
    { id: "studio.stepback", label: "Debug: step back one bar", keys: (m) => [m.KeyMod.Shift | m.KeyCode.F10], run: () => debug({ step: -1 }) },
    { id: "studio.panel", label: "View: toggle panel", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyJ], run: () => setPanelOpen((o) => !o) },
    { id: "studio.rail", label: "View: toggle side bar", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyB], run: () => setRailOpen((o) => !o) },
    { id: "studio.files", label: "Go to file", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyP], run: () => { setRailOpen(true); setRail("files"); } },
    { id: "studio.search", label: "Search project", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.KeyF], run: () => { setRailOpen(true); setRail("search"); } },
    { id: "studio.docs", label: "Docs: open reference", keys: (m) => [m.KeyCode.F1], run: () => { setRailOpen(true); setRail("docs"); } },
    { id: "studio.fullrun", label: "Run: full backtest (recorded)", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.Enter], run: () => { setTab("results"); setPanelOpen(true); if (onQuickRun) onQuickRun("full"); else onFullRun(); } },
    { id: "studio.quickrun", label: "Run: quick (top 50, 5 years)", run: () => { setTab("results"); setPanelOpen(true); if (onQuickRun) onQuickRun("quick"); else onRun(); } },
    { id: "studio.cancel", label: "Run: cancel", run: () => onCancel?.() },
    { id: "studio.profile", label: "Run: profile the preview", run: () => runProfile() },
    { id: "studio.save", label: "Strategy: save version", run: () => onSave() },
    { id: "studio.newfile", label: "File: new", run: () => addFile() },
    { id: "studio.split", label: "View: split editor", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.Backslash], run: () => setSplit((x) => (x ? null : Object.keys(files).find((f) => f !== active) ?? active)) },
    { id: "studio.snippet", label: "Snippet: save selection", run: () => saveSnippet() },
    { id: "studio.snippets", label: "Snippet: insert", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.KeyS], run: () => { setRailOpen(true); setRail("templates"); } },
  ];
  const outlineRows = (items: Sym[], depth = 0): ReactNode => items.map((s) => (
    <div key={`${s.name}${s.line}`}>
      <button className="dv-item" style={{ paddingLeft: 10 + depth * 14 }} onClick={() => goto(active, s.line, s.column)}><i className={`dv-k dv-k-${s.kind}`}>{s.kind[0]}</i>{s.name}<span>{s.line}</span></button>
      {outlineRows(s.children, depth + 1)}
    </div>
  ));
  const docRows = (docs ?? []).filter((d) => !docQ || `${d.scope}.${d.name} ${d.documentation ?? ""}`.toLowerCase().includes(docQ.toLowerCase()));
  const TABS: [Tab, string, number | null][] = [["problems", "Problems", problems.length], ["output", "Output", prev?.logs?.length ?? null], ["plots", "Plots", plots.length + Object.keys(prev?.tables ?? {}).length || null], ["trades", "Trades", prev?.trades.length ?? null], ["results", "Results", null], ["debug", "Debug", null]];
  const toggles = <span className="dv-toggles">
    <button className="icon-btn" aria-pressed={opt.caseSensitive} title="Match case" onClick={() => setOpt((o) => ({ ...o, caseSensitive: !o.caseSensitive }))}><CaseSensitive size={14} /></button>
    <button className="icon-btn" aria-pressed={opt.word} title="Whole word" onClick={() => setOpt((o) => ({ ...o, word: !o.word }))}><WholeWord size={14} /></button>
    <button className="icon-btn" aria-pressed={opt.regex} title="Regular expression" onClick={() => setOpt((o) => ({ ...o, regex: !o.regex }))}><Regex size={14} /></button>
  </span>;
  const priceRows = (prev?.bars ?? []).map((b) => ({ date: b.date, close: b.close, ...Object.fromEntries(plots.filter(([n]) => prev?.plot_charts?.[n] === "main" && plotsOn[n] !== false).map(([n, pts]) => [n, pts.find((p) => p.date === b.date)?.value ?? null])) }));
  const mainPlots = plots.filter(([n]) => prev?.plot_charts?.[n] === "main");

  return (
    <div className="dv" data-rail={railOpen || undefined} style={{ ["--panel-h" as string]: panelOpen ? `${panel}px` : "0px" }}>
      <nav className="dv-icons" aria-label="Side bar">
        {RAILS.map(([k, icon, l]) => <button key={k} className="icon-btn" title={l} aria-label={l} aria-pressed={railOpen && rail === k} onClick={() => { if (railOpen && rail === k) setRailOpen(false); else { setRail(k); setRailOpen(true); } }}>{icon}</button>)}
      </nav>
      {railOpen ? (
        <nav className="dv-rail" aria-label={RAILS.find((r) => r[0] === rail)?.[2]}>
          <h4>{RAILS.find((r) => r[0] === rail)?.[2]}</h4>
          {rail === "files" ? (
            <div className="dv-list">
              {Object.keys(files).map((f) => (
                <div key={f} className="dv-file" data-on={f === active || undefined}>
                  <button className="dv-item" onClick={() => goto(f, 1)}><FileCode2 size={13} />{f}</button>
                  <button className="icon-btn" title="Duplicate" aria-label={`Duplicate ${f}`} onClick={() => dupFile(f)}><FilePlus2 size={12} /></button>
                  {f !== "main.py" ? <><button className="icon-btn" title="Rename" aria-label={`Rename ${f}`} onClick={() => renameFile(f)}><Pencil size={12} /></button><button className="icon-btn" title="Delete" aria-label={`Delete ${f}`} onClick={() => dropFile(f)}><Trash2 size={12} /></button></> : null}
                </div>
              ))}
              <button className="btn sm ghost" onClick={addFile}><FilePlus2 size={13} />New file</button>
            </div>
          ) : rail === "outline" ? (
            <div className="dv-list">{outline.length ? outlineRows(outline) : <p className="dv-empty">No classes or functions</p>}</div>
          ) : rail === "search" ? (
            <div className="dv-list">
              <div className="dv-search"><input className="input" autoFocus placeholder="Search" aria-label="Search project" value={q} onChange={(e) => setQ(e.target.value)} />{toggles}</div>
              <div className="dv-search"><input className="input" placeholder="Replace" aria-label="Replace with" value={rep} onChange={(e) => setRep(e.target.value)} /><button className="btn sm" disabled={!hits.length} onClick={replaceAll}>All</button></div>
              {q && !re ? <p className="dv-empty">Invalid pattern</p> : null}
              {re ? <p className="dv-count">{hits.length} line{hits.length === 1 ? "" : "s"} in {new Set(hits.map((h) => h.file)).size} file{new Set(hits.map((h) => h.file)).size === 1 ? "" : "s"}</p> : null}
              {hits.slice(0, 400).map((h, i) => {
                re!.lastIndex = 0;
                const after = rep && re ? h.text.replace(re, rep) : null;
                return <button key={i} className="dv-hit" onClick={() => goto(h.file, h.line)}><i>{h.file}:{h.line}</i><code>{h.text.trim()}</code>{after !== null && after !== h.text ? <code className="dv-after">{after.trim()}</code> : null}</button>;
              })}
            </div>
          ) : rail === "versions" ? (
            <div className="dv-list">
              {timeline.length ? [...timeline].reverse().map((v) => (
                <div key={v.version} className="dv-ver" data-on={diff?.version === v.version || undefined}>
                  <button className="dv-tpl" onClick={() => (diff?.version === v.version ? setDiff(null) : openDiff(v.version))}>
                    <b>v{v.version}{v.name ? ` ${v.name}` : ""}{v.locked ? <Lock size={11} style={{ marginLeft: 5 }} aria-label="Locked" /> : null} <span className="dv-muted">{new Date(v.created * 1000).toLocaleDateString()} · {v.actor}</span></b>
                    {v.tags.length ? <span className="dv-tags">{v.tags.map((t) => <i key={t}>{t}</i>)}</span> : null}
                    <span>{v.total_return != null ? `${pct(v.total_return)} · Sharpe ${v.sharpe?.toFixed(2) ?? "—"}` : "not run"}</span>
                  </button>
                  <div className="dv-vact">
                    <button className="icon-btn" title="Name and tags" aria-label={`Name v${v.version}`} onClick={() => labelVersion(v)}><Tag size={12} /></button>
                    <button className="icon-btn" title={v.locked ? "Unlock" : "Lock (live)"} aria-label={v.locked ? "Unlock" : "Lock"} onClick={() => lockVersion(v.locked ? null : v.version)}>{v.locked ? <Unlock size={12} /> : <Lock size={12} />}</button>
                    <button className="icon-btn" title="Restore as latest" aria-label={`Restore v${v.version}`} onClick={() => versionAct(`/versions/${v.version}/restore`, undefined, `Restored v${v.version}`)}><RotateCcw size={12} /></button>
                    <button className="icon-btn" title="Branch" aria-label={`Branch v${v.version}`} onClick={() => strategyId && void studio<{ id: string }>("POST", `/strategies/${strategyId}/versions/${v.version}/branch`).then((b) => window.location.assign(`/studio/build/${b.id}?ui=dev`), (e: Error) => toast.error(e.message))}><GitBranch size={12} /></button>
                  </div>
                </div>
              )) : versions.length ? null : <p className="dv-empty">Save to start versions</p>}
              {snaps.length ? <><h4 className="dv-sub">Local history · 7 days</h4>
                {snaps.slice(0, 60).map((sn) => <button key={sn.at} className="dv-item" title="Restore these files into the draft" onClick={() => { replaceFiles(sn.files); toast("Snapshot restored into the draft · ⌘Z to undo"); }}>
                  {new Date(sn.at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}<span>{Object.keys(sn.files).length} file{Object.keys(sn.files).length === 1 ? "" : "s"}</span></button>)}</> : null}
            </div>
          ) : rail === "docs" ? (
            <div className="dv-list">
              <input className="input" placeholder="Search the API" aria-label="Search the API" value={docQ} onChange={(e) => setDocQ(e.target.value)} />
              {docs === null ? <p className="dv-empty">Loading…</p> : docRows.slice(0, 300).map((d) => (
                <details key={`${d.scope}.${d.name}`} className="dv-doc"><summary><code>{d.scope === "portfolio_ctx" ? "ctx" : d.scope}.{d.name}</code><i>{d.kind}</i>
                  <button className="icon-btn" title="Insert at the cursor" aria-label={`Insert ${d.name}`} onClick={(e) => { e.preventDefault(); insertAt.current?.(`${d.scope === "portfolio_ctx" ? "ctx" : d.scope === "numpy" ? "np" : d.scope === "pandas" ? "pd" : d.scope}.${d.signature ? d.signature.replace(/\(.*\)/, "($1)") : d.name}`); }}><FilePlus2 size={12} /></button></summary>
                  {d.signature ? <code className="dv-sig">{d.signature}</code> : null}{d.documentation ? <p>{d.documentation}</p> : null}</details>
              ))}
            </div>
          ) : (
            <div className="dv-list">
              {(pyTemplates.data ?? []).map((t) => <button key={t.name} className="dv-tpl" onClick={() => { edit({ ...(t.spec as Partial<Spec>) }); setOpen(["main.py"]); setActive("main.py"); }}><b>{t.name}</b><span>{t.rule}</span></button>)}
              <button className="btn sm ghost" onClick={() => { setQc(null); qcRef.current?.showModal(); }}><Upload size={13} />QuantConnect algorithm</button>
              <h4 className="dv-sub">My snippets</h4>
              {snippets.map((sn) => (
                <div key={sn.id} className="dv-file">
                  <button className="dv-item" title={sn.body} onClick={() => insertAt.current?.(sn.body)}><code>{sn.prefix}</code>{sn.name}</button>
                  <button className="icon-btn" aria-label={`Delete ${sn.name}`} onClick={() => void studio("DELETE", `/snippets/${sn.id}`).then(() => setSnippets((x) => x.filter((y) => y.id !== sn.id)))}><Trash2 size={12} /></button>
                </div>
              ))}
              <button className="btn sm ghost" onClick={saveSnippet}><FilePlus2 size={13} />Save selection as snippet</button>
            </div>
          )}
        </nav>
      ) : null}

      <section className="dv-main">
        <div className="dv-tabs" role="tablist">
          {open.map((f) => (
            <div key={f} role="tab" aria-selected={!diff && f === active} className="dv-tab" onClick={() => { setDiff(null); setActive(f); }} onAuxClick={(e) => { if (e.button === 1) close(f); }}>
              {f}{open.length > 1 ? <button className="icon-btn" aria-label={`Close ${f}`} onClick={(e) => { e.stopPropagation(); close(f); }}><X size={11} /></button> : null}
            </div>
          ))}
          <span style={{ flex: 1 }} />
          <button className="icon-btn dv-splitbtn" aria-pressed={!!split} title="Split editor" aria-label="Split editor" onClick={() => setSplit((x) => (x ? null : Object.keys(files).find((f) => f !== active) ?? active))}><Columns2 size={14} /></button>
          {diff ? <div role="tab" aria-selected className="dv-tab">v{diff.version} ↔ draft · {active}<button className="icon-btn" aria-label="Close diff" onClick={() => setDiff(null)}><X size={11} /></button></div> : null}
        </div>
        <div className="dv-editor" data-split={(split && !diff) || undefined}>
          {!spec.code.trim() && active === "main.py" && !diff ? (
            <div className="dv-blank">
              <b>This strategy runs on its rules</b>
              <div><button className="btn primary" onClick={() => void studio<{ code: string }>("POST", "/to-python", { spec }).then((r) => edit({ code: r.code }), (e: Error) => toast.error(e.message))}>Convert rules to Python</button>
                <button className="btn" onClick={() => { setRailOpen(true); setRail("templates"); }}>Start from a starter</button></div>
            </div>
          ) : null}
          {split && !diff ? (
            <div className="dv-split">
              <div className="dv-splithead"><select className="input" aria-label="File in the second group" value={split} onChange={(e) => setSplit(e.target.value)}>{Object.keys(files).map((f) => <option key={f}>{f}</option>)}</select>
                <button className="icon-btn" aria-label="Close split" onClick={() => setSplit(null)}><X size={12} /></button></div>
              <CodeEditor path={`split/${split}`} value={files[split] ?? ""} onChange={(t) => setFile(split, t)} problems={[]} onSave={onSave} onRun={onRun} readOnly={readOnly}
                project={{ file: split, files, params: Object.keys(spec.params), symbols: [symbol], goto, replace: replaceFiles }} />
            </div>
          ) : null}
          {diff ? (
            <DiffEditor language="python" original={diff.files[active] ?? ""} modified={source} theme="studio" height="100%"
              options={{ readOnly: true, renderSideBySide: true, minimap: { enabled: false }, fontSize: 13, lineHeight: 20, scrollBeyondLastLine: false, automaticLayout: true, fontFamily: "'JetBrains Mono', var(--font-mono), ui-monospace, monospace" }} />
          ) : (
            <CodeEditor path={active} value={source} onChange={(t) => setFile(active, t)} problems={problems} onSave={onSave} onRun={() => { setTab("results"); setPanelOpen(true); if (onQuickRun) onQuickRun("quick"); else onRun(); }} reveal={reveal} onCursor={(line, column) => setCursor({ line, column })}
              font={font} actions={actions} breakpoints={bps[active] ?? []} ran={(prev?.order_lines ?? []).filter((o) => o.file === active)} onGutter={toggleBp} readOnly={readOnly} snippets={snippets}
              onSelection={(t) => { selection.current = t; }} insertRef={insertAt}
              project={{ file: active, files, params: Object.keys(spec.params), symbols: [symbol], goto, replace: replaceFiles, paramSpecs: spec.params, problems,
                addParam: (name, value) => edit({ params: { ...spec.params, [name]: { value, min: +(value / 2).toPrecision(3), max: +(value * 2).toPrecision(3), step: Math.max(1, Math.round(value / 10)) } } }),
                lens: (command, args) => { if (command === "debug") debug({ date: String(args.date ?? "") }); else if (command === "inspect_condition") { setTab("output"); toast(`${String(args.expression)} on ${String(args.symbol)}`); } else onRun(); } }} />
          )}
        </div>
        <div className="dv-grip" role="separator" aria-orientation="horizontal" aria-label="Resize panel" onPointerDown={drag} onDoubleClick={() => setPanelOpen((o) => !o)} />
        {panelOpen ? (
          <div className="dv-panel">
            <div className="dv-ptabs" role="tablist">
              {TABS.map(([k, l, n]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{n ? <span className="num">{n}</span> : null}</button>)}
              <span style={{ flex: 1 }} />
              <button className="icon-btn" aria-label="Hide panel" title="Hide panel ⌘J" onClick={() => setPanelOpen(false)}><X size={13} /></button>
            </div>
            <div className="dv-pbody">
              {tab === "problems" ? <label className="dv-strict"><input type="checkbox" checked={strict} onChange={(e) => { setStrict(e.target.checked); try { localStorage.setItem("studio:dev:strict", e.target.checked ? "1" : "0"); } catch { /* blocked */ } }} />Strict</label> : null}
              {tab === "problems" ? (problems.length ? <>
                {problems.map((p, i) => (
                  <button key={i} className="dv-prob" onClick={() => goto(p.file, p.line, p.column)}><b className={p.severity}>{p.severity}</b><span>{p.message}</span><i>{p.file}:{p.line}:{p.column}{p.code ? ` ${p.code}` : ""}</i></button>
                ))}
                {prev?.locals ? <div className="dv-trace"><h4 className="dv-sub">At the failing bar</h4><KV rows={prev.locals} /></div> : null}
                {prev?.problem?.traceback?.length ? <div className="dv-trace">{prev.problem.traceback.map((f, i) => <button key={i} className="dv-item" onClick={() => goto(f.file, f.line, f.column)}>{f.function}<span>{f.file}:{f.line}</span></button>)}</div> : null}
              </> : <p className="dv-empty">No problems</p>) : null}
              {tab === "output" ? (
                <>
                  <div className="dv-search dv-logbar">
                    <input className="input" placeholder="Filter" aria-label="Filter output" value={logQ} onChange={(e) => setLogQ(e.target.value)} />{toggles}
                    <div className="seg" role="group" aria-label="Level">{["all", "info", "warning", "error"].map((l) => <button key={l} type="button" aria-pressed={logLevel === l} onClick={() => setLogLevel(l)}>{l}</button>)}</div>
                    <span className="dv-count">{logs.length.toLocaleString()} of {(prev?.logs?.length ?? 0).toLocaleString()}</span>
                  </div>
                  {logs.length ? <div className="dv-logs">{logs.slice(0, 2000).map((l, i) => (
                    <button key={i} className="dv-log" data-level={l.level} onClick={() => goto("main.py", l.line)}><time>{l.date}</time><span>{l.symbol ?? ""}</span>
                      <code>{l.text}{l.fields ? <em>{Object.entries(l.fields).map(([k, v]) => ` ${k}=${show(v)}`).join("")}</em> : null}</code><i>:{l.line}</i></button>
                  ))}</div> : <p className="dv-empty">{prev?.logs?.length ? "Nothing matches" : "No output"}</p>}
                </>
              ) : null}
              {tab === "plots" ? (
                <div className="dv-plots">
                  {plots.length ? <div className="dv-chips">{plots.map(([n], i) => <button key={n} className="pill" aria-pressed={plotsOn[n] !== false} onClick={() => setPlotsOn((o) => ({ ...o, [n]: o[n] === false }))}><i style={{ background: SERIES[i % SERIES.length] }} />{n}</button>)}</div> : null}
                  {mainPlots.length && priceRows.length ? <div className="dv-plot"><b>Price · {symbol}</b><TimeSeries data={priceRows} height={200} legend={false}
                    series={[{ key: "close", label: symbol, color: "var(--text-3)" }, ...mainPlots.filter(([n]) => plotsOn[n] !== false).map(([n]) => ({ key: n, label: n, color: SERIES[plots.findIndex(([x]) => x === n) % SERIES.length] }))]}
                    markers={(prev?.marks ?? []).filter((m) => m.symbol === symbol).map((m) => ({ date: m.date, label: m.label, color: "var(--accent)" }))} /></div> : null}
                  {plots.filter(([n]) => prev?.plot_charts?.[n] !== "main" && plotsOn[n] !== false).map(([name, pts]) => (
                    <div key={name} className="dv-plot"><b>{name}</b><TimeSeries data={pts.filter((p) => p.value !== null).map((p) => ({ date: p.date, v: p.value }))} series={[{ key: "v", label: name, color: SERIES[plots.findIndex(([x]) => x === name) % SERIES.length] }]} height={140} legend={false} /></div>
                  ))}
                  {Object.entries(prev?.tables ?? {}).map(([name, rows]) => <div key={name} className="dv-plot"><b>{name}</b><DataTable rows={rows.map((r) => ({ date: r.date, symbol: r.symbol, ...r.cells }))} opts={{ viewKey: `studio:dev:table:${name}` }} /></div>)}
                  {!plots.length && !Object.keys(prev?.tables ?? {}).length ? <p className="dv-empty">No plots</p> : null}
                </div>
              ) : null}
              {tab === "trades" ? (prev?.trades.length ? <DataTable rows={prev.trades} opts={{ viewKey: "studio:dev:trades" }} /> : <p className="dv-empty">No trades in the preview</p>) : null}
              {tab === "results" ? (() => {
                const r = version ? runs[version] : undefined;
                const m = quick?.result?.meta;
                const running = quick && ["queued", "running"].includes(quick.status);
                const d = quick?.delta;
                const sign = (v: number | null | undefined, f: (x: number) => string) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${f(v)}`);
                return (
                  <div className="dv-results">
                    <div className="dv-dbar">
                      <button className="btn sm primary" disabled={!!running} onClick={() => onQuickRun?.("quick")}>Quick run<kbd>⌘↵</kbd></button>
                      <button className="btn sm" disabled={!!running} onClick={() => onQuickRun?.("full")}>Full run<kbd>⌘⇧↵</kbd></button>
                      <button className="btn sm" onClick={runProfile}>Profile</button>
                      {running ? <button className="btn sm" onClick={onCancel}>Cancel<kbd>Esc</kbd></button> : null}
                      {quick ? <span className="dv-count">{quick.level === "quick" ? "Top 50 names, 5 years, not in the ledger" : "Full period, recorded in the ledger"}</span> : null}
                    </div>
                    {running ? <div className="dv-prog"><i style={{ width: `${quick!.progress?.percent ?? 2}%` }} /><span>{quick!.progress?.message ?? "Queued"}</span></div> : null}
                    {quick?.status === "failed" ? <p className="bd-find error"><b>Failed</b>{quick.error}</p> : null}
                    {quick?.status === "cancelled" ? <p className="dv-empty">Cancelled</p> : null}
                    {m ? <>
                      <div className="kpis">
                        <div className="kpi"><span>Return</span><b>{pct(m.total_return)}</b>{d ? <i className="dv-delta">{sign(d.total_return, (x) => `${(x * 100).toFixed(1)} pts`)}</i> : null}</div>
                        <div className="kpi"><span>Sharpe</span><b>{m.metrics?.sharpe?.toFixed(2) ?? "—"}</b>{d ? <i className="dv-delta">{sign(d.sharpe, (x) => x.toFixed(2))}</i> : null}</div>
                        <div className="kpi"><span>Max drawdown</span><b>{m.metrics?.max_drawdown != null ? pct(m.metrics.max_drawdown) : "—"}</b></div>
                        <div className="kpi"><span>Trades</span><b>{m.metrics?.trades ?? "—"}</b>{d ? <i className="dv-delta">{sign(d.trades, (x) => String(x))}</i> : null}</div>
                      </div>
                      {m.headline ? <p className="bd-desc">{m.headline}</p> : null}
                      {quick?.level === "full" ? <Link className="btn sm" href="/studio/backtest">Open in Backtest</Link> : null}
                    </> : !quick && r ? (
                      <div className="kpis">
                        <div className="kpi"><span>v{version} return</span><b>{pct(r.total_return)}</b></div>
                        <div className="kpi"><span>Sharpe</span><b>{r.sharpe?.toFixed(2) ?? "—"}</b></div>
                        <div className="kpi"><span>Trades</span><b>{r.trades ?? "—"}</b></div>
                      </div>
                    ) : null}
                    {stale && (m || r) ? <p className="bd-find warning"><b>Edited</b>the code differs from the run shown</p> : null}
                    {profile === "loading" ? <p className="dv-empty">Profiling…</p> : profile ? <div className="dv-dgrid">
                      <div><h4>Slowest lines</h4>{profile.lines?.length ? <DataTable rows={profile.lines.map((l) => ({ line: l.line, file: l.file ?? "main.py", seconds: l.seconds, hits: l.hits ?? null, source: l.source ?? "" }))} /> : <p className="dv-empty">No data</p>}</div>
                      <div><h4>Time per function</h4>{profile.functions?.length ? <DataTable rows={profile.functions.map((f) => ({ function: f.function ?? f.name ?? "", seconds: f.seconds, calls: f.calls ?? null }))} /> : <p className="dv-empty">No data</p>}</div>
                    </div> : null}
                  </div>
                );
              })() : null}
              {tab === "debug" ? (
                <div className="dv-debug">
                  <div className="dv-dbar">
                    <input className="input" type="date" aria-label="Stop at date" value={dbgDate} onChange={(e) => setDbgDate(e.target.value)} />
                    <button className="btn sm primary" onClick={() => debug({ date: dbgDate })}><Bug size={13} />Stop here<kbd>F5</kbd></button>
                    <button className="btn sm" disabled={!dbg?.previous_date} onClick={() => debug({ step: -1 })}>◀ Bar</button>
                    <button className="btn sm" disabled={!dbg?.next_date} onClick={() => debug({ step: 1 })}>Bar ▶<kbd>F10</kbd></button>
                    <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "order" })}>Next order</button>
                    <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "fill" })}>Next fill</button>
                    <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "equity", loss_fraction: 0.05 })}>Next 5% loss day</button>
                    <span className="dv-sep" />
                    <input className="input" aria-label="Breakpoint condition" placeholder="condition" value={cond} onChange={(e) => setCond(e.target.value)} />
                    <button className="btn sm" onClick={() => debug({ breakpoint: { file: active, line: cursor.line, condition: cond || null } })}>Break at {active}:{cursor.line}</button>
                  </div>
                  {dbg ? (
                    <div className="dv-dgrid">
                      <div><h4>{dbg.symbol} · {dbg.date} · bar {dbg.bar_index}{dbg.breakpoint ? ` · hit ${dbg.breakpoint.hit_count}` : ""}{dbg.equity_change != null ? ` · ${pct(dbg.equity_change)}` : ""}</h4>
                        <KV rows={dbg.context} /></div>
                      <div><h4>{dbg.breakpoint ? "Locals and self" : "self"}</h4>
                        {Object.keys({ ...dbg.state, ...(dbg.breakpoint?.locals ?? {}) }).length ? <KV rows={{ ...dbg.state, ...(dbg.breakpoint?.locals ?? {}) }} /> : <p className="dv-empty">No attributes</p>}</div>
                      <div><h4>Orders</h4>{dbg.orders.length ? <DataTable rows={dbg.orders} /> : <p className="dv-empty">None this bar</p>}
                        <h4>Fills</h4>{dbg.fills.length ? <DataTable rows={dbg.fills} /> : <p className="dv-empty">None this bar</p>}</div>
                    </div>
                  ) : <p className="dv-empty">Stops at the last preview trade, or the date set</p>}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      <aside className="dv-side">{side}</aside>

      <footer className="dv-status">
        <span>{active}</span><span>Ln {cursor.line}, Col {cursor.column}</span>
        <button className="dv-sbtn" onClick={() => { setPanelOpen(true); setTab("problems"); }}><b className="error">{errors}</b> errors <b className="warning">{warnings}</b> warnings</button>
        <span className={`dv-save dv-save-${saved}`}>{{ saved: "Saved", draft: "Draft", saving: "Saving…", conflict: "Conflict: reload", new: "Not saved" }[saved]}</span>
        {prev?.warmup ? <span>warm-up {prev.warmup.bars} bars{prev.warmup.first_eligible_date ? ` · trades from ${prev.warmup.first_eligible_date}` : ""}</span> : null}
        {prev?.settings_overrides && Object.keys(prev.settings_overrides).length ? <span className="dv-over" title={Object.entries(prev.settings_overrides).map(([k, v]) => `${k} = ${String(v)}`).join("\n")}>code sets {Object.keys(prev.settings_overrides).join(", ")}</span> : null}
        {Object.values(bps).flat().length ? <span>{Object.values(bps).flat().length} breakpoint{Object.values(bps).flat().length === 1 ? "" : "s"}</span> : null}
        <span style={{ flex: 1 }} />
        {quick && ["queued", "running"].includes(quick.status) ? <span className="dv-run">{quick.progress?.partial ? `bar ${quick.progress.partial.bars?.toLocaleString() ?? "…"} · ${quick.progress.partial.symbols ?? "…"} symbols · ${quick.progress.partial.elapsed_seconds?.toFixed(1) ?? "0"} s of ${quick.progress.partial.budget_seconds ?? "…"} s` : `${quick.level} run ${quick.progress?.percent ?? 0}%`}</span> : null}
        {trial}
        <span>{prev ? `${prev.status === "ok" ? `preview ${symbol}` : prev.status}${lastPreview ? ` · ${lastPreview}` : ""}` : "no preview"}</span><span>Python 3.12</span>
      </footer>

      <dialog ref={qcRef} className="sh-import" aria-label="Open a QuantConnect algorithm" onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
        <b style={{ fontSize: 15 }}>Open a QuantConnect algorithm</b>
        <textarea className="input" id="dv-qc" placeholder={"class MyAlgo(QCAlgorithm):\n    def initialize(self):\n        …"} spellCheck={false} onChange={() => setQc(null)} />
        {qc ? (
          <div className="dv-qc">
            <p><b className="st-up">{qc.converted.length} converted</b> <b className={qc.unconverted.length ? "warning" : "st-up"}>{qc.unconverted.length} not converted</b>{qc.symbols.length ? ` · ${qc.symbols.join(", ")}` : ""}</p>
            {qc.unconverted.map((u, i) => <div key={i} className="sh-find"><b className="warning">line {u.line}</b><span><code>{u.source.trim()}</code> {u.reason}</span></div>)}
          </div>
        ) : null}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn" onClick={() => qcRef.current?.close()}>Cancel</button>
          <button className="btn" onClick={() => { const src = (document.getElementById("dv-qc") as HTMLTextAreaElement).value; if (src.trim()) void studio<QC>("POST", "/build/import-quantconnect", { source: src }).then(setQc, (e: Error) => toast.error(e.message)); }}>Convert</button>
          <button className="btn primary" disabled={!qc?.code} onClick={() => { if (qc) { edit({ code: qc.code }); goto("main.py", 1); qcRef.current?.close(); } }}>Open in main.py</button>
        </div>
      </dialog>
    </div>
  );
}
