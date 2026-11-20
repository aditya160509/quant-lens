"use client";

import { DiffEditor } from "@monaco-editor/react";
import { Group, Panel, Separator, type GroupImperativeHandle } from "react-resizable-panels";
import Link from "next/link";
import { BookOpen, Bug, ChevronDown, LayoutPanelLeft, PanelRight, Maximize2, Minimize2, CaseSensitive, Columns2, Pin, PinOff, Lock, RotateCcw, Tag, Unlock, FileCode2, FilePlus2, GitBranch, LayoutTemplate, ListTree, Pencil, Regex, Search, Trash2, Upload, WholeWord, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import toast from "react-hot-toast";
import { SERIES } from "@/charts/core";
import { Distribution } from "@/charts/Distribution";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import { studio, usePyTemplates } from "../api";
import { RECIPES } from "./recipes";
import { useLayout } from "@/workspace/layout";
import { CodeEditor, type EditorAction, type Problem } from "./CodeEditor";
import { DevChart } from "./DevChart";
import { snap, springTo, targets, useWorkspaces, WorkspaceMenu, type PanelId } from "./Workspace";
import { DevRobust } from "./DevRobust";
import { DevRuns, type RunEntry } from "./DevRuns";
import { DevTearsheet } from "./DevTearsheet";

type Log = { date: string; symbol: string | null; line: number; text: string; level: string; fields?: Record<string, unknown> | null };
type Point = { date: string; symbol: string | null; value: number | null };
type Frame = { file: string; line: number; column: number; function: string };
export type Draw = { styles: Record<string, { color: string | null; width: number; style: string }>; hlines: { value: number; chart: string; color: string | null; name: string }[]; fills: { a: string; b: string; color: string | null }[]; bg: { date: string; color: string }[] };
export type DevPreview = {
  status: string; reason?: string; line?: number | null;
  problem?: { file?: string | null; line?: number | null; column?: number | null; exception_type?: string | null; traceback?: Frame[] | null } | null;
  trades: Record<string, unknown>[]; bars?: { date: string; close: number }[]; logs?: Log[] | null; plots?: Record<string, Point[]> | null; plot_charts?: Record<string, string> | null; draw?: Draw | null;
  marks?: { date: string; symbol: string; label: string }[] | null; tables?: Record<string, { date: string; symbol: string | null; cells: Record<string, unknown> }[]> | null;
  warmup?: { bars: number; first_eligible_date: string | null } | null; settings_overrides?: Record<string, unknown> | null;
  order_lines?: { file: string; line: number; count: number; dates: string[] }[] | null; locals?: Record<string, unknown> | null;
  invariants?: { count: number; rows: { date: string; symbol: string | null; file: string; line: number; text: string }[] } | null;
};
type Profile = { lines?: { file?: string; line: number; seconds: number; hits?: number; source?: string }[]; functions?: { function?: string; name?: string; seconds: number; calls?: number }[] };
export type QuickRun = { job_id: string; level: "quick" | "full"; status: string; progress?: { percent?: number; message?: string; partial?: { symbols?: number; bars?: number; elapsed_seconds?: number; budget_seconds?: number } } | null;
  error?: string | null; delta?: { total_return: number | null; sharpe: number | null; trades: number | null } | null;
  result?: { summary_cards?: { label: string; value: number | null }[]; charts?: { equity_curve?: { date: string; strategy: number; benchmark: number | null }[] }; tables?: { trades?: Record<string, unknown>[] };
    meta?: { headline?: string; total_return?: number; metrics?: Record<string, number | null>; trade_split?: Record<string, Record<string, number>> } } };
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
type Tab = "problems" | "output" | "plots" | "trades" | "debug" | "console";
type View = "code" | "results" | "tearsheet" | "robust" | "runs";
const VIEW_LABEL: Record<Exclude<View, "code">, string> = { results: "Results", tearsheet: "Tearsheet", robust: "Robustness", runs: "Runs" };
type Rail = "files" | "outline" | "search" | "versions" | "docs" | "templates";
type Spec = { code: string; files?: Record<string, string>; params: Record<string, { value: number; min?: number | null; max?: number | null; step?: number | null }>; [k: string]: unknown };
export type Saved = "saved" | "draft" | "saving" | "conflict" | "new";

const show = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(4)) : typeof v === "object" ? JSON.stringify(v) : String(v));
const pct = (v?: number) => (v === undefined ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
const DOC_SCOPES = ["ctx", "portfolio_ctx", "numpy", "pandas", "math", "statistics"];
const RAILS: [Rail, ReactNode, string][] = [
  ["files", <FileCode2 key="f" size={15} />, "Explorer"], ["outline", <ListTree key="o" size={15} />, "Outline"], ["search", <Search key="s" size={15} />, "Search"],
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
export function DevIDE({ title, tools, spec, edit, symbol, prev, side, onSave, onRun, onFullRun, compileProblems, strategyId, versions, runs, saved, trial, readOnly, onReload, version, stale, onPause, font, quick, onQuickRun, onCancel, savedFiles }: {
  title?: ReactNode; tools?: ReactNode; spec: Spec; edit: (next: Partial<Spec>) => void; symbol: string; prev: DevPreview | null; side: ReactNode;
  onSave: () => void; onRun: () => void; onFullRun: () => void; compileProblems: Problem[];
  strategyId?: string; versions: Version[]; runs: Record<string, RunSum>; saved: Saved; trial?: ReactNode; readOnly?: boolean; onReload?: () => void; version?: number; stale?: boolean; onPause?: (date: string | null, label?: string) => void; font?: number; savedFiles?: Record<string, string>;
  quick?: QuickRun | null; onQuickRun?: (level: "quick" | "full") => void; onCancel?: () => void;
}) {
  const files = useMemo(() => ({ "main.py": spec.code, ...(spec.files ?? {}) }), [spec.code, spec.files]);
  const [open, setOpen] = useState<string[]>(["main.py"]);
  const [active, setActive] = useState("main.py");
  const [rail, setRail] = useState<Rail>("files");
  const ws = useWorkspaces();
  const open_ = ws.cur.layout.open;
  const setOpenP = (p: PanelId, v: boolean | ((o: boolean) => boolean)) => ws.patch((l) => ({ ...l, open: { ...l.open, [p]: typeof v === "function" ? v(l.open[p]) : v } }));
  const railOpen = open_.rail, setRailOpen = (v: boolean | ((o: boolean) => boolean)) => setOpenP("rail", v);
  const panelOpen = open_.tester, setPanelOpen = (v: boolean | ((o: boolean) => boolean)) => setOpenP("tester", v);
  const hRef = useRef<GroupImperativeHandle>(null), vRef = useRef<GroupImperativeHandle>(null);
  const chartSeen = useRef(false);
  if (open_.chart) chartSeen.current = true;
  const [view, setView] = useState<View>("code");
  const [extra, setExtra] = useState<Exclude<View, "code">[]>([]);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const stepping = useRef(false);
  const debugRef = useRef<(b: Record<string, unknown>, quiet?: boolean) => Promise<void> | void>(() => undefined);
  const [panelMax, setPanelMax] = useState(false);
  const [tab, setTab] = useState<Tab>("problems");
  const [lint, setLint] = useState<Problem[]>([]);
  const [types, setTypes] = useState<Problem[]>([]);
  const [outline, setOutline] = useState<Sym[]>([]);
  const [cursor, setCursor] = useState({ line: 1, column: 1 });
  const [reveal, setReveal] = useState<{ line: number; column?: number; n: number } | null>(null);
  // Dev wants the width: the workspace sidebar closes while Dev is open and comes back after (user feedback 2026-11-20).
  useEffect(() => { const was = useLayout.getState().open.left; useLayout.getState().set("left", false, true); return () => useLayout.getState().set("left", was, true); }, []);
  const [logQ, setLogQ] = useState("");
  const [logLevel, setLogLevel] = useState<string>("all");
  const [logSym, setLogSym] = useState("");
  const [logFrom, setLogFrom] = useState("");
  const [plotsOn, setPlotsOn] = useState<Record<string, boolean>>({});
  const [dbg, setDbg] = useState<Debug | null>(null);
  const [dbgDate, setDbgDate] = useState("");
  const [watches, setWatches] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem("studio:watch") ?? "[]"); } catch { return []; } });
  const [watchRows, setWatchRows] = useState<{ expression: string; error: string | null; value: unknown; history: { date: string; value: number }[] }[]>([]);
  const [watchIn, setWatchIn] = useState("");
  const [con, setCon] = useState<{ q: string; at: string; out: string; err?: boolean }[]>([]);
  const [conIn, setConIn] = useState("");
  const conHist = useRef(-1);
  const runCon = (q: string) => {
    const date = dbg?.date || prev?.bars?.at(-1)?.date;
    if (!q.trim() || !date) return;
    setConIn(""); conHist.current = -1;
    void studio<{ error: string | null; value: unknown }[]>("POST", "/build/watch", { spec, symbol: dbg?.symbol ?? symbol, date, expressions: [q], history: 1 })
      .then(([r]) => setCon((c) => [...c, { q, at: date, out: r.error ?? (typeof r.value === "number" ? String(+r.value.toFixed(6)) : JSON.stringify(r.value)), err: !!r.error }]), (e: Error) => setCon((c) => [...c, { q, at: date, out: e.message, err: true }]));
  };
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
  const [splitDown, setSplitDown] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string[]>([]);
  const [logTop, setLogTop] = useState(0);
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

  const setFile = (name: string, text: string) => (keep(name), name === "main.py" ? edit({ code: text }) : edit({ files: { ...(spec.files ?? {}), [name]: text } }));
  const replaceFiles = (next: Record<string, string>) => {
    const all = { ...files, ...next };
    const { "main.py": code, ...rest } = all;
    edit({ code, files: rest });
  };
  const goto = (file: string, line: number, column?: number) => { if (!(file in files)) return; setDiff(null); setOpen((o) => (o.includes(file) ? o : [...o, file])); setActive(file); setReveal({ line, column, n: Date.now() }); };
  // Single click opens a preview tab that the next single click replaces; double click or an edit keeps it (B-13).
  const peek = (f: string) => { if (!(f in files)) return; setDiff(null); setOpen((o) => (o.includes(f) ? o : [...o.filter((x) => x !== preview || pinned.includes(x)), f])); if (!open.includes(f)) setPreview(f); setActive(f); };
  const keep = (f: string) => { if (preview === f) setPreview(null); };
  const close = (f: string) => { const rest = open.filter((x) => x !== f); setOpen(rest.length ? rest : ["main.py"]); if (active === f) setActive(rest.at(-1) ?? "main.py"); };
  const toggleBp = (line: number) => setBps((b) => { const cur = b[active] ?? []; return { ...b, [active]: cur.includes(line) ? cur.filter((x) => x !== line) : [...cur, line].sort((x, y) => x - y) }; });

  useEffect(() => {
    if (!source.trim()) { setLint([]); setTypes([]); setOutline([]); return; }
    const t = setTimeout(() => {
      void studio<{ problems: Problem[] }>("POST", "/build/check", { code: source, file: active, files, strictness: strict ? "strict" : "basic", params: Object.fromEntries(Object.entries(spec.params).map(([k, p]) => [k, p.value])) }).then((r) => setLint(r.problems), () => undefined);
      void studio<Sym[]>("POST", "/build/outline", { code: source }).then(setOutline, () => undefined);
      void studio<{ problems: Problem[] }>("POST", "/build/typecheck", { code: source, file: active, files }).then((r) => setTypes(r.problems), () => setTypes([]));
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
  const actionsRef = useRef<EditorAction[]>([]);
  useEffect(() => {
    const on = (e: Event) => {
      const id = (e as CustomEvent<string>).detail;
      if (id.startsWith("goto:")) { setOpenP("chart", true); replayGo(id.slice(5), undefined); return; }
      actionsRef.current.find((a) => a.id === id)?.run(cursor.line);
    };
    window.addEventListener("studio:dev", on); return () => window.removeEventListener("studio:dev", on);
  }, [cursor.line]);
  useEffect(() => { if (prev) setLastPreview(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })); }, [prev]);
  useEffect(() => {
    if (rail !== "docs" || docs) return;
    void Promise.all(DOC_SCOPES.map((scope) => studio<Member[]>("POST", "/build/complete", { scope, code: "" }).then((ms) => ms.map((m) => ({ ...m, scope })), () => []))).then((all) => setDocs(all.flat()));
  }, [rail, docs]);

  const runtime: Problem[] = prev?.status === "error" ? [{ severity: "error", file: prev.problem?.file ?? "main.py", line: prev.problem?.line ?? prev.line ?? 1, column: prev.problem?.column ?? 1, end_column: 200, code: prev.problem?.exception_type ?? "runtime", message: prev.reason ?? "Run failed" }] : [];
  const broken: Problem[] = (prev?.invariants?.rows ?? []).filter((r) => r.file === active).slice(0, 50).map((r) => ({ severity: "error", file: r.file, line: r.line, column: 1, end_column: 200, code: "invariant", message: `${r.text} (${r.symbol ?? ""} ${r.date})` }));
  const problems = [...lint, ...types, ...compileProblems.filter((p) => p.file === active), ...runtime, ...broken];
  const errors = problems.filter((p) => p.severity === "error").length, warnings = problems.length - errors;
  // The editor keeps the space; the panel opens on its own only when an error appears.
  const hadErrors = useRef(0);
  useEffect(() => { if (errors && !hadErrors.current) { setPanelOpen(true); setTab("problems"); } hadErrors.current = errors; }, [errors]);
  const logRe = finder(logQ, opt);
  const logs = (prev?.logs ?? []).filter((l) => (logLevel === "all" || l.level === logLevel) && (!logSym || l.symbol === logSym) && (!logFrom || l.date >= logFrom) && (!logRe || (logRe.lastIndex = 0, logRe.test(`${l.date} ${l.symbol ?? ""} ${l.text}${l.fields ? Object.entries(l.fields).map(([k, v]) => ` ${k}=${show(v)}`).join("") : ""}`))));
  const plots = Object.entries(prev?.plots ?? {});
  // B-81: the plots of the preview before this one, overlaid dashed when "Previous run" is on.
  const [before, setBefore] = useState<Record<string, Point[]> | null>(null);
  const [showBefore, setShowBefore] = useState(false);
  const lastPlots = useRef(prev?.plots);
  useEffect(() => { if (lastPlots.current && prev?.plots && lastPlots.current !== prev.plots) setBefore(lastPlots.current); if (prev?.plots) lastPlots.current = prev.plots; }, [prev?.plots]);
  const re = finder(q, opt);
  const hits = re ? Object.entries(files).flatMap(([f, text]) => text.split("\n").flatMap((line, i) => { re.lastIndex = 0; return re.test(line) ? [{ file: f, line: i + 1, text: line }] : []; })) : [];

  useEffect(() => {
    if (!dbg || !watches.length) { setWatchRows([]); return; }
    void studio<typeof watchRows>("POST", "/build/watch", { spec, symbol: dbg.symbol, date: dbg.date, expressions: watches }).then(setWatchRows, () => undefined);
  }, [dbg, watches]); // eslint-disable-line react-hooks/exhaustive-deps
  type Cmt = { id: string; thread_id: string; file: string; line: number; text: string; author: string; created: number };
  const [cmts, setCmts] = useState<Cmt[]>([]);
  const [thread, setThread] = useState<{ file: string; line: number } | null>(null);
  const [cmtText, setCmtText] = useState("");
  const loadCmts = () => { if (strategyId) void studio<Cmt[]>("GET", `/strategies/${strategyId}/comments`).then(setCmts, () => undefined); };
  useEffect(loadCmts, [strategyId]); // eslint-disable-line react-hooks/exhaustive-deps
  const openThread = (line: number) => { if (!strategyId) return toast.error("Save the strategy to comment"); setThread({ file: active, line }); setCmtText(""); setTimeout(() => document.querySelector<HTMLInputElement>(".dv-thread input")?.focus(), 80); };
  const postCmt = () => {
    if (!thread || !cmtText.trim()) return;
    const first = cmts.find((c) => c.file === thread.file && c.line === thread.line);
    void studio("POST", `/strategies/${strategyId}/comments`, { ...thread, text: cmtText.trim(), ...(first ? { thread_id: first.thread_id } : {}) }).then(() => { setCmtText(""); loadCmts(); }, (e: Error) => toast.error(e.message));
  };
  const dropCmt = (id: string) => void studio("DELETE", `/strategies/${strategyId}/comments/${id}`).then(loadCmts, (e: Error) => toast.error(e.message));
  const stepLine = (cursorLine?: number) => {
    const b = dbg?.breakpoint;
    debug({ date: dbg?.date, step_line: true, breakpoint: { file: b?.file ?? active, line: b?.line ?? cursorLine ?? cursor.line } });
  };
  const debug = (body: Record<string, unknown>, quiet = false): Promise<void> | void => {
    const date = String(body.date || dbg?.date || dbgDate || (prev?.trades.at(-1)?.entry_date ?? prev?.bars?.[0]?.date ?? ""));
    if (!date) return void toast.error("Pick a date to stop at");
    if (!quiet) { setTab("debug"); setPanelOpen(true); }
    return studio<Debug>("POST", "/build/debug", { spec, symbol, date, ...body }).then((d) => { setDbg(d); setDbgDate(d.date); onPause?.(d.date, `❚❚ ${Math.round(Number(d.context.quantity ?? 0))} held${d.orders.length ? ` · ${d.orders.length} pending` : ""}`); if (d.breakpoint) goto(d.breakpoint.file, d.breakpoint.line); if (!d.next_date) setPlaying(false); }, (e: Error) => { setPlaying(false); toast.error(e.message); });
  };
  /** Replay moves the debugger one bar or to a date; chart, Debug locals, watches and Console follow dbg. Overlapping requests are dropped. */
  const replayGo = useCallback((date: string | null, step?: 1 | -1) => {
    if (stepping.current) return;
    stepping.current = true;
    void Promise.resolve(date ? debugRef.current({ date }, true) : debugRef.current({ step }, true)).finally(() => { stepping.current = false; });
  }, []);
  const [runLog, setRunLog] = useState<RunEntry[]>([]);
  useEffect(() => {
    if (quick?.status !== "completed" || !quick.result?.meta) return;
    setRunLog((l) => (l.some((r) => r.id === quick.job_id) ? l : [{ id: quick.job_id, label: `Run ${l.length + 1} · ${quick.level}`, at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), pinned: false, run: quick }, ...l].slice(0, 20)));
  }, [quick]);
  const pinRun = (id: string) => setRunLog((l) => l.map((r) => (r.id === id ? { ...r, pinned: !r.pinned } : r)));
  const renameRun = (id: string) => { const n = window.prompt("Name this run")?.trim(); if (n) setRunLog((l) => l.map((r) => (r.id === id ? { ...r, label: n } : r))); };
  const openView = (v: Exclude<View, "code">) => { setExtra((x) => (x.includes(v) ? x : [...x, v])); setView(v); };
  const closeView = (v: Exclude<View, "code">) => { setExtra((x) => x.filter((y) => y !== v)); if (view === v) setView("code"); };
  useEffect(() => { if (!open_.chart) setPlaying(false); }, [open_.chart]);
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
    openView("results"); setProfile("loading");
    void studio<{ profile?: Profile }>("POST", "/build/profile", { spec, symbol }).then((r) => setProfile(r.profile ?? {}), (e: Error) => { setProfile(null); toast.error(e.message); });
  };
  useEffect(() => { if (quick?.job_id) openView("results"); }, [quick?.job_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!quick || !["queued", "running"].includes(quick.status)) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel?.(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [quick, onCancel]);
  useEffect(() => { const t = targets(ws.cur.layout); springTo(hRef.current, t.h); springTo(vRef.current, t.v); }, [ws.cur.id, open_.rail, open_.chart || open_.preview, open_.tester]); // eslint-disable-line react-hooks/exhaustive-deps
  /** After a drag: snap the chart to 30/50/70, close a panel pulled to the edge, remember the size. */
  const onH = (l: Record<string, number>, m: { isUserInteraction: boolean }) => {
    if (!m.isUserInteraction) return;
    const right = snap(l.right, [30, 50, 70]);
    ws.patch((x) => ({ open: { ...x.open, rail: x.open.rail && l.rail >= 6, chart: x.open.chart && right >= 8, preview: x.open.preview && right >= 8 },
      size: { ...x.size, rail: x.open.rail && l.rail >= 6 ? l.rail : x.size.rail, right: right >= 8 ? right : x.size.right } }));
    if (right !== l.right && right >= 8) springTo(hRef.current, { rail: l.rail, center: 100 - l.rail - right, right });
  };
  const onV = (l: Record<string, number>, m: { isUserInteraction: boolean }) => {
    if (!m.isUserInteraction) return;
    ws.patch((x) => ({ open: { ...x.open, tester: x.open.tester && l.tester >= 8 }, size: { ...x.size, tester: x.open.tester && l.tester >= 8 ? l.tester : x.size.tester } }));
  };
  const maxTester = () => { const next = !panelMax; setPanelMax(next); const t = next ? 85 : 34; ws.patch((x) => ({ ...x, size: { ...x.size, tester: t } })); springTo(vRef.current, { editor: 100 - t, tester: t }); };

  const actions: EditorAction[] = [
    { id: "studio.debug", label: "Debug: start", keys: (m) => [m.KeyCode.F5], run: () => startDebug() },
    { id: "studio.bp", label: "Debug: toggle breakpoint", keys: (m) => [m.KeyCode.F9], run: (line) => toggleBp(line) },
    { id: "studio.step", label: "Debug: step one bar", keys: (m) => [m.KeyCode.F10], run: () => debug({ step: 1 }) },
    { id: "studio.stepline", label: "Debug: step line", keys: (m) => [m.KeyCode.F11], run: (l) => stepLine(l) },
    { id: "studio.stepback", label: "Debug: step back one bar", keys: (m) => [m.KeyMod.Shift | m.KeyCode.F10], run: () => debug({ step: -1 }) },
    { id: "studio.panel", label: "View: toggle panel", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyJ], run: () => setPanelOpen((o) => !o) },
    { id: "studio.rail", label: "View: toggle side bar", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyB], run: () => setRailOpen((o) => !o) },
    { id: "studio.files", label: "Go to file", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyP], run: () => { setRailOpen(true); setRail("files"); } },
    { id: "studio.search", label: "Search project", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.KeyF], run: () => { setRailOpen(true); setRail("search"); } },
    { id: "studio.docs", label: "Docs: open reference", keys: (m) => [m.KeyCode.F1], run: () => { setRailOpen(true); setRail("docs"); } },
    { id: "studio.fullrun", label: "Run: full backtest (recorded)", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.Enter], run: () => { openView("results"); if (onQuickRun) onQuickRun("full"); else onFullRun(); } },
    { id: "studio.quickrun", label: "Run: quick (top 50, 5 years)", run: () => { openView("results"); if (onQuickRun) onQuickRun("quick"); else onRun(); } },
    { id: "studio.cancel", label: "Run: cancel", run: () => onCancel?.() },
    { id: "studio.chart", label: "View: chart with replay", run: () => setOpenP("chart", true) },
    { id: "studio.results", label: "View: results", run: () => openView("results") },
    { id: "studio.tearsheet", label: "View: tearsheet", run: () => openView("tearsheet") },
    { id: "studio.runs", label: "View: compare runs", run: () => openView("runs") },
    { id: "studio.robust", label: "Run: robustness (Monte Carlo)", run: () => openView("robust") },
    { id: "studio.profile", label: "Run: profile the preview", run: () => runProfile() },
    { id: "studio.save", label: "Strategy: save version", run: () => onSave() },
    { id: "studio.newfile", label: "File: new", run: () => addFile() },
    { id: "studio.split", label: "View: split editor", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.Backslash], run: () => setSplit((x) => (x ? null : Object.keys(files).find((f) => f !== active) ?? active)) },
    { id: "studio.snippet", label: "Snippet: save selection", run: () => saveSnippet() },
    { id: "studio.snippets", label: "Snippet: insert", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.KeyS], run: () => { setRailOpen(true); setRail("templates"); } },
  ];
  actionsRef.current = actions;
  debugRef.current = debug;
  const outlineRows = (items: Sym[], depth = 0): ReactNode => items.map((s) => (
    <div key={`${s.name}${s.line}`}>
      <button className="dv-item" style={{ paddingLeft: 10 + depth * 14 }} onClick={() => goto(active, s.line, s.column)}><i className={`dv-k dv-k-${s.kind}`}>{s.kind[0]}</i>{s.name}<span>{s.line}</span></button>
      {outlineRows(s.children, depth + 1)}
    </div>
  ));
  const docRows = (docs ?? []).filter((d) => !docQ || `${d.scope}.${d.name} ${d.documentation ?? ""}`.toLowerCase().includes(docQ.toLowerCase()));
  const TABS: [Tab, string, number | null][] = [["problems", "Problems", problems.length], ["output", "Output", prev?.logs?.length ?? null], ["plots", "Plots", plots.length + Object.keys(prev?.tables ?? {}).length || null], ["trades", "Trades", prev?.trades.length ?? null], ["debug", "Debug", null], ["console", "Console", null]];
  const toggles = <span className="dv-toggles">
    <button className="icon-btn" aria-pressed={opt.caseSensitive} title="Match case" onClick={() => setOpt((o) => ({ ...o, caseSensitive: !o.caseSensitive }))}><CaseSensitive size={14} /></button>
    <button className="icon-btn" aria-pressed={opt.word} title="Whole word" onClick={() => setOpt((o) => ({ ...o, word: !o.word }))}><WholeWord size={14} /></button>
    <button className="icon-btn" aria-pressed={opt.regex} title="Regular expression" onClick={() => setOpt((o) => ({ ...o, regex: !o.regex }))}><Regex size={14} /></button>
  </span>;
  const priceRows = (prev?.bars ?? []).map((b) => ({ date: b.date, close: b.close, ...Object.fromEntries(plots.filter(([n]) => prev?.plot_charts?.[n] === "main" && plotsOn[n] !== false).map(([n, pts]) => [n, pts.find((p) => p.date === b.date)?.value ?? null])) }));
  const mainPlots = plots.filter(([n]) => prev?.plot_charts?.[n] === "main");

  const resultsView = (() => {
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
                      {quick?.result?.summary_cards?.length ? <div className="dv-cards">{quick.result.summary_cards.filter((c) => !/^(sharpe|max drawdown|trades)$/i.test(c.label)).map((c) => <span key={c.label}><i>{c.label}</i><b>{c.value == null ? "—" : /win/i.test(c.label) ? `${(c.value * 100).toFixed(1)}%` : /drawdown|cagr/i.test(c.label) ? pct(c.value) : c.value.toFixed(2)}</b></span>)}</div> : null}
                      {quick?.result?.charts?.equity_curve?.length ? <div className="dv-plot"><b>Equity vs benchmark</b><TimeSeries data={quick.result.charts.equity_curve} height={200}
                        series={[{ key: "strategy", label: "Strategy", color: SERIES[0] }, { key: "benchmark", label: "Benchmark", color: "var(--text-3)" }]} /></div> : null}
                      {m.trade_split ? <div className="dv-plot"><b>All, long and short</b><DataTable rows={Object.entries(m.trade_split).map(([side, v]) => ({ side, trades: v.count ?? 0, win_rate: v.win_rate ?? null, profit_factor: v.profit_factor ?? null, avg_win: v.avg_win ?? null, avg_loss: v.avg_loss ?? null, expectancy: v.expectancy ?? null }))} /></div> : null}
                      {quick?.result?.tables?.trades?.length ? <div className="dv-dgrid">
                        <div className="dv-plot"><b>Trade returns</b><Distribution values={quick.result.tables.trades.map((t) => Number(t.return)).filter(Number.isFinite)} xLabel="Return per trade" height={180} format={(v) => `${(v * 100).toFixed(1)}%`} /></div>
                        <div className="dv-plot"><b>Trades</b><DataTable rows={quick.result.tables.trades} opts={{ viewKey: "studio:dev:quicktrades" }} /></div>
                      </div> : null}
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
              })();

  return (
    <div className="dv">
      <div className="dv-bar">
        <div className="dv-title">{title}</div>
        <div className="dv-tabs" role="tablist">
          {open.map((f) => (
            <div key={f} role="tab" aria-selected={view === "code" && !diff && f === active} className="dv-tab" data-preview={preview === f || undefined} data-pinned={pinned.includes(f) || undefined}
              onClick={() => { setDiff(null); setView("code"); setActive(f); }} onDoubleClick={() => keep(f)} onAuxClick={(e) => { if (e.button === 1) close(f); }}>
              {pinned.includes(f) ? <Pin size={10} aria-label="Pinned" /> : null}{f}
              {savedFiles && (savedFiles[f] ?? "") !== (files[f] ?? "") ? <i className="dv-dirty" aria-label="Unsaved" /> : null}
              <button className="icon-btn" aria-label={pinned.includes(f) ? `Unpin ${f}` : `Pin ${f}`} title={pinned.includes(f) ? "Unpin" : "Pin"} onClick={(e) => { e.stopPropagation(); keep(f); setPinned((p) => (p.includes(f) ? p.filter((x) => x !== f) : [...p, f])); }}>{pinned.includes(f) ? <PinOff size={11} /> : <Pin size={11} />}</button>
              {open.length > 1 && !pinned.includes(f) ? <button className="icon-btn" aria-label={`Close ${f}`} onClick={(e) => { e.stopPropagation(); close(f); }}><X size={11} /></button> : null}
            </div>
          ))}
          {extra.map((v) => <div key={v} role="tab" aria-selected={view === v} className="dv-tab" onClick={() => setView(v)}>{VIEW_LABEL[v]}<button className="icon-btn" aria-label={`Close ${v}`} onClick={(e) => { e.stopPropagation(); closeView(v); }}><X size={11} /></button></div>)}
          {diff ? <div role="tab" aria-selected className="dv-tab">v{diff.version} ↔ draft · {active}<button className="icon-btn" aria-label="Close diff" onClick={() => setDiff(null)}><X size={11} /></button></div> : null}
        </div>
        <div className="dv-tools">
          <WorkspaceMenu ws={ws} />
          <details className="dv-view" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
            <summary className="btn sm ghost" aria-label="View menu"><LayoutPanelLeft size={14} />View<ChevronDown size={12} /></summary>
            <div className="dv-menu" role="menu" onClick={(e) => { (e.currentTarget.parentElement as HTMLDetailsElement).open = false; }}>
                            <button role="menuitem" onClick={() => openView("results")}>Results</button>
              <button role="menuitem" onClick={() => openView("tearsheet")}>Tearsheet</button>
              <button role="menuitem" onClick={() => openView("robust")}>Robustness</button>
              <button role="menuitem" onClick={() => openView("runs")}>Compare runs</button>
              <hr />
              <button role="menuitemcheckbox" aria-checked={open_.chart} onClick={() => setOpenP("chart", (o) => !o)}>Chart</button>
              <button role="menuitemcheckbox" aria-checked={open_.preview} onClick={() => setOpenP("preview", (o) => !o)}>Preview</button>
              <button role="menuitemcheckbox" aria-checked={!!split} onClick={() => setSplit((x) => (x ? null : Object.keys(files).find((f) => f !== active) ?? active))}>Split editor</button>
              <button role="menuitemcheckbox" aria-checked={panelOpen} onClick={() => setPanelOpen((o) => !o)}>Panel</button>
              <button role="menuitemcheckbox" aria-checked={railOpen} onClick={() => setRailOpen((o) => !o)}>Side bar</button>
            </div>
          </details>
        </div>
        {tools}
        </div>
      <nav className="dv-icons" aria-label="Side bar">
        {RAILS.map(([k, icon, l]) => <button key={k} className="icon-btn" title={l} aria-label={l} aria-pressed={railOpen && rail === k} onClick={() => { if (railOpen && rail === k) setRailOpen(false); else { setRail(k); setRailOpen(true); } }}>{icon}</button>)}
      </nav>
      <Group className="dv-body" orientation="horizontal" id="dv-h" groupRef={hRef} defaultLayout={targets(ws.cur.layout).h} onLayoutChanged={onH}>
      <Panel id="rail" minSize={0}>
        <nav className="dv-rail" aria-hidden={!railOpen} aria-label={RAILS.find((r) => r[0] === rail)?.[2]}>
          <h4>{RAILS.find((r) => r[0] === rail)?.[2]}</h4>
          {rail === "files" ? (
            <div className="dv-list dv-explorer">
              <details open><summary>Files</summary>
              {Object.keys(files).map((f) => (
                <div key={f} className="dv-file" data-on={f === active || undefined}>
                  <button className="dv-item" onClick={() => peek(f)} onDoubleClick={() => { goto(f, 1); keep(f); }}><FileCode2 size={13} />{f}</button>
                  <button className="icon-btn" title="Duplicate" aria-label={`Duplicate ${f}`} onClick={() => dupFile(f)}><FilePlus2 size={12} /></button>
                  {f !== "main.py" ? <><button className="icon-btn" title="Rename" aria-label={`Rename ${f}`} onClick={() => renameFile(f)}><Pencil size={12} /></button><button className="icon-btn" title="Delete" aria-label={`Delete ${f}`} onClick={() => dropFile(f)}><Trash2 size={12} /></button></> : null}
                </div>
              ))}
              <button className="btn sm ghost" onClick={addFile}><FilePlus2 size={13} />New file</button>
              </details>
              <details open><summary>Parameters<span>{Object.keys(spec.params).length}</span></summary>
                {Object.entries(spec.params).map(([n, p]) => <div key={n} className="dv-row"><code>{n}</code><span>{p.value}</span></div>)}
                {Object.keys(spec.params).length ? null : <p className="dv-empty">None</p>}
              </details>
              <details><summary>Libraries<span>{DOC_SCOPES.length}</span></summary>
                {DOC_SCOPES.map((n) => <button key={n} className="dv-item" onClick={() => setRail("docs")}><BookOpen size={13} />{n}</button>)}
              </details>
              <details><summary>Versions<span>{versions.length}</span></summary>
                {[...versions].reverse().slice(0, 6).map((v) => <button key={v.version} className="dv-item" onClick={() => setRail("versions")}><GitBranch size={13} />v{v.version}<span>{v.actor}</span></button>)}
                {versions.length ? null : <p className="dv-empty">Not saved</p>}
              </details>
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
                    {v.spark?.length > 1 ? <Spark values={v.spark} /> : null}
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
              {RECIPES.filter(([t]) => !docQ || t.toLowerCase().includes(docQ.toLowerCase())).map(([title, code]) => (
                <details key={title} className="dv-doc"><summary><code>{title}</code><i>recipe</i>
                  <button className="icon-btn" title="Insert at the cursor" aria-label={`Insert ${title}`} onClick={(e) => { e.preventDefault(); insertAt.current?.(code); }}><FilePlus2 size={12} /></button></summary>
                  <pre className="bd-code">{code}</pre></details>
              ))}
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
      </Panel>
      <Separator className="dv-gutter" disabled={!railOpen} />
      <Panel id="center" minSize={20}>
      <Group className="dv-main" orientation="vertical" id="dv-v" groupRef={vRef} defaultLayout={targets(ws.cur.layout).v} onLayoutChanged={onV}>
      <Panel id="editor" minSize={10} className="dv-edpane">
        <div className="dv-editor" data-split={split && !diff ? (splitDown ? "down" : "right") : undefined}>
          {view !== "code" ? (
            <div className="dv-view-pane" data-kind={view}>
              <div className="dv-pbody">{view === "tearsheet" ? <DevTearsheet quick={quick ?? null} /> : view === "robust" ? <DevRobust quick={quick ?? null} /> : view === "runs" ? <DevRuns runs={runLog} onPin={pinRun} onRename={renameRun} /> : resultsView}</div>
            </div>
          ) : null}
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
                <button className="btn sm ghost" aria-pressed={splitDown} onClick={() => setSplitDown(!splitDown)}>{splitDown ? "Split right" : "Split down"}</button>
                <button className="icon-btn" aria-label="Close split" onClick={() => setSplit(null)}><X size={12} /></button></div>
              <CodeEditor path={`split/${split}`} value={files[split] ?? ""} onChange={(t) => setFile(split, t)} problems={[]} onSave={onSave} onRun={onRun} readOnly={readOnly}
                project={{ file: split, files, params: Object.keys(spec.params), symbols: [symbol], goto, replace: replaceFiles }} />
            </div>
          ) : null}
          {diff ? (
            <DiffEditor language="python" original={diff.files[active] ?? ""} modified={source} theme="studio" height="100%"
              options={{ readOnly: true, renderSideBySide: true, minimap: { enabled: false }, fontSize: 13, lineHeight: 20, scrollBeyondLastLine: false, automaticLayout: true, fontFamily: "'JetBrains Mono', var(--font-mono), ui-monospace, monospace" }} />
          ) : (
            <CodeEditor path={active} value={source} onChange={(t) => setFile(active, t)} problems={problems} onSave={onSave} onRun={() => { openView("results"); if (onQuickRun) onQuickRun("quick"); else onRun(); }} reveal={reveal} onCursor={(line, column) => setCursor({ line, column })}
              font={font} actions={actions} breakpoints={bps[active] ?? []} ran={(prev?.order_lines ?? []).filter((o) => o.file === active)} onGutter={toggleBp} onComment={openThread} commentLines={cmts.filter((c) => c.file === active).map((c) => c.line)} readOnly={readOnly} snippets={snippets}
              onSelection={(t) => { selection.current = t; }} insertRef={insertAt}
              project={{ file: active, files, params: Object.keys(spec.params), symbols: [symbol], goto, replace: replaceFiles, paramSpecs: spec.params, problems,
                addParam: (name, value) => edit({ params: { ...spec.params, [name]: { value, min: +(value / 2).toPrecision(3), max: +(value * 2).toPrecision(3), step: Math.max(1, Math.round(value / 10)) } } }),
                lens: (command, args) => { if (command === "debug") debug({ date: String(args.date ?? "") }); else if (command === "inspect_condition") { setTab("output"); toast(`${String(args.expression)} on ${String(args.symbol)}`); } else onRun(); } }} />
          )}
        </div>
        {thread ? (
          <div className="dv-thread" role="dialog" aria-label={`Comments on ${thread.file}:${thread.line}`}>
            <header><b>{thread.file}:{thread.line}</b><button className="icon-btn" aria-label="Close thread" onClick={() => setThread(null)}><X size={12} /></button></header>
            {cmts.filter((c) => c.file === thread.file && c.line === thread.line).map((c) => (
              <p key={c.id}><i>{c.author}</i>{c.text}<button className="icon-btn" aria-label="Delete comment" onClick={() => dropCmt(c.id)}><Trash2 size={12} /></button></p>
            ))}
            <form onSubmit={(e) => { e.preventDefault(); postCmt(); }}><input className="input" autoFocus aria-label="Reply" placeholder="Comment" value={cmtText} onChange={(e) => setCmtText(e.target.value)} /><button className="btn sm primary" disabled={!cmtText.trim()}>Post</button></form>
          </div>
        ) : null}
      </Panel>
      <Separator className="dv-gutter" disabled={!panelOpen} />
      <Panel id="tester" minSize={0}>
          <div className="dv-panel" aria-hidden={!panelOpen}>
            <div className="dv-ptabs" role="tablist">
              {TABS.map(([k, l, n]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{n ? <span className="num">{n}</span> : null}</button>)}
              <span style={{ flex: 1 }} />
              <button className="icon-btn" aria-label={panelMax ? "Restore panel" : "Maximise panel"} title={panelMax ? "Restore panel" : "Maximise panel"} onClick={maxTester}>{panelMax ? <Minimize2 size={14} /> : <Maximize2 size={14} />}</button>
              <button className="icon-btn" aria-label="Hide panel" title="Hide panel ⌘J" onClick={() => setPanelOpen(false)}><X size={13} /></button>
            </div>
            <div className="dv-pbody" onScroll={(e) => { if (tab === "output") setLogTop(e.currentTarget.scrollTop); }}>
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
                    {(() => { const syms = [...new Set((prev?.logs ?? []).map((l) => l.symbol).filter(Boolean))] as string[]; return syms.length > 1 ? <select className="input" aria-label="Symbol" style={{ width: "auto" }} value={logSym} onChange={(e) => setLogSym(e.target.value)}><option value="">All symbols</option>{syms.map((x) => <option key={x}>{x}</option>)}</select> : null; })()}
                    <input className="input" type="date" aria-label="From date" style={{ width: "auto" }} value={logFrom} onChange={(e) => setLogFrom(e.target.value)} />
                    <button className="btn sm ghost" disabled={!logs.length} onClick={() => { const q = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`; const csv = ["level,date,symbol,line,message", ...logs.map((l) => [l.level, l.date, l.symbol, l.line, l.text].map(q).join(","))].join("\n"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); a.download = "output.csv"; a.click(); URL.revokeObjectURL(a.href); }}>CSV</button>
                    <span className="dv-count">{logs.length.toLocaleString()} of {(prev?.logs?.length ?? 0).toLocaleString()}</span>
                  </div>
                  {logs.length ? (() => {
                    // Virtual list: only the rows in view (plus a margin) are in the page, so 5,000 lines scroll smoothly (B-79).
                    const ROW = 24, first = Math.max(0, Math.floor(logTop / ROW) - 20), rows = logs.slice(first, first + 80);
                    return <div className="dv-logs" style={{ height: logs.length * ROW }}>
                      {rows.map((l, i) => (
                        <button key={first + i} className="dv-log" data-level={l.level} style={{ top: (first + i) * ROW }} onClick={() => { goto("main.py", l.line); onPause?.(l.date); }}><time>{l.date}</time><span>{l.symbol ?? ""}</span>
                          <code>{l.text}{l.fields ? <em>{Object.entries(l.fields).map(([k, v]) => ` ${k}=${show(v)}`).join("")}</em> : null}</code><i>:{l.line}</i></button>
                      ))}</div>;
                  })() : <p className="dv-empty">{prev?.logs?.length ? "Nothing matches" : "No output"}</p>}
                </>
              ) : null}
              {tab === "plots" ? (
                <div className="dv-plots">
                  {plots.length ? <div className="dv-chips">{plots.map(([n], i) => <button key={n} className="pill" aria-pressed={plotsOn[n] !== false} onClick={() => setPlotsOn((o) => ({ ...o, [n]: o[n] === false }))}><i style={{ background: SERIES[i % SERIES.length] }} />{n}</button>)}{before ? <button className="pill" aria-pressed={showBefore} onClick={() => setShowBefore(!showBefore)}>Previous run</button> : null}</div> : null}
                  {mainPlots.length && priceRows.length ? <div className="dv-plot"><b>Price · {symbol}</b><TimeSeries data={priceRows} height={200} legend={false}
                    series={[{ key: "close", label: symbol, color: "var(--text-3)" }, ...mainPlots.filter(([n]) => plotsOn[n] !== false).map(([n]) => ({ key: n, label: n, color: SERIES[plots.findIndex(([x]) => x === n) % SERIES.length] }))]}
                    markers={(prev?.marks ?? []).filter((m) => m.symbol === symbol).map((m) => ({ date: m.date, label: m.label, color: "var(--accent)" }))} /></div> : null}
                  {plots.filter(([n]) => prev?.plot_charts?.[n] !== "main" && plotsOn[n] !== false).map(([name, pts]) => (
                    <div key={name} className="dv-plot"><b>{name}</b>{(() => {
                      const old = showBefore ? new Map((before?.[name] ?? []).map((p) => [p.date, p.value])) : null;
                      const color = SERIES[plots.findIndex(([x]) => x === name) % SERIES.length];
                      return <TimeSeries data={pts.filter((p) => p.value !== null).map((p) => ({ date: p.date, v: p.value, ...(old ? { b: old.get(p.date) ?? null } : {}) }))} series={[{ key: "v", label: name, color }, ...(old?.size ? [{ key: "b", label: `${name} (previous)`, color: "var(--text-4)" }] : [])]} height={140} legend={!!old?.size} />;
                    })()}</div>
                  ))}
                  {Object.entries(prev?.tables ?? {}).map(([name, rows]) => <div key={name} className="dv-plot"><b>{name}</b><DataTable rows={rows.map((r) => ({ date: r.date, symbol: r.symbol, ...r.cells }))} opts={{ viewKey: `studio:dev:table:${name}` }} /></div>)}
                  {!plots.length && !Object.keys(prev?.tables ?? {}).length ? <p className="dv-empty">No plots</p> : null}
                </div>
              ) : null}
              {tab === "trades" ? (prev?.trades.length ? <DataTable rows={prev.trades} opts={{ viewKey: "studio:dev:trades" }} /> : <p className="dv-empty">No trades in the preview</p>) : null}
              {tab === "console" ? (
                <div className="dv-console" onClick={(e) => (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus()}>
                  {con.map((c, i) => <div key={i}><span className="dv-con-q">› {c.q}</span><i>{c.at}</i><pre data-err={c.err || undefined}>{c.out}</pre></div>)}
                  <form onSubmit={(e) => { e.preventDefault(); runCon(conIn); }}><span>›</span>
                    <input aria-label="Console" spellCheck={false} autoComplete="off" value={conIn} onChange={(e) => setConIn(e.target.value)} onKeyDown={(e) => {
                      if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
                      e.preventDefault(); const qs = con.map((c) => c.q); const n = conHist.current === -1 ? qs.length : conHist.current; const k = Math.max(0, Math.min(qs.length, n + (e.key === "ArrowUp" ? -1 : 1)));
                      conHist.current = k; setConIn(qs[k] ?? "");
                    }} /><i className="dv-con-at">{dbg?.date ?? prev?.bars?.at(-1)?.date}</i></form>
                </div>
              ) : null}
              {tab === "debug" ? (
                <div className="dv-debug">
                  <div className="dv-dbar">
                    <input className="input" type="date" aria-label="Stop at date" value={dbgDate} onChange={(e) => setDbgDate(e.target.value)} />
                    <button className="btn sm primary" onClick={() => debug({ date: dbgDate })}><Bug size={13} />Stop here<kbd>F5</kbd></button>
                    <button className="btn sm" disabled={!dbg?.previous_date} onClick={() => debug({ step: -1 })}>◀ Bar</button>
                    <button className="btn sm" disabled={!dbg?.next_date} onClick={() => debug({ step: 1 })}>Bar ▶<kbd>F10</kbd></button>
                    <button className="btn sm" disabled={!dbg} onClick={() => stepLine()}>Line ▶<kbd>F11</kbd></button>
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
                      <div><h4>Watch</h4>
                        <form className="dv-dbar" onSubmit={(e) => { e.preventDefault(); if (!watchIn.trim()) return; const w = [...watches, watchIn.trim()]; setWatches(w); setWatchIn(""); try { localStorage.setItem("studio:watch", JSON.stringify(w)); } catch { /* private window */ } }}>
                          <input className="input" aria-label="Watch expression" placeholder="rsi(close, 14)" value={watchIn} onChange={(e) => setWatchIn(e.target.value)} />
                        </form>
                        {watchRows.map((r, i) => <div key={r.expression} className="dv-watch"><code>{r.expression}</code><b className={r.error ? "error" : undefined} title={r.error ?? r.history.map((h) => `${h.date}  ${h.value}`).join("\n")}>{r.error ?? (typeof r.value === "number" ? +r.value.toFixed(4) : String(r.value))}</b>
                          <button className="icon-btn" aria-label="Remove watch" onClick={() => { const w = watches.filter((_, k) => k !== i); setWatches(w); try { localStorage.setItem("studio:watch", JSON.stringify(w)); } catch { /* private window */ } }}>×</button></div>)}</div>
                      <div><h4>Orders</h4>{dbg.orders.length ? <DataTable rows={dbg.orders} /> : <p className="dv-empty">None this bar</p>}
                        <h4>Fills</h4>{dbg.fills.length ? <DataTable rows={dbg.fills} /> : <p className="dv-empty">None this bar</p>}</div>
                    </div>
                  ) : <p className="dv-empty">Stops at the last preview trade, or the date set</p>}
                </div>
              ) : null}
            </div>
          </div>
      </Panel>
      </Group>
      </Panel>
      <Separator className="dv-gutter" disabled={!open_.chart && !open_.preview} />
      <Panel id="right" minSize={0}>
      <aside className="dv-side" data-both={(open_.chart && open_.preview) || undefined}>
        {chartSeen.current ? <div className="dv-chartpane" hidden={!open_.chart}><DevChart symbol={symbol} prev={prev} pausedAt={dbg?.date ?? null} playing={playing} speed={speed} onPlay={setPlaying} onSpeed={setSpeed} onGo={(d, st) => replayGo(d, st)} /></div> : null}
        {open_.preview ? <div className="dv-prevpane">{side}</div> : null}
      </aside>
      </Panel>
      </Group>

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
        {open_.chart ? <a href="https://www.vela.dev" target="_blank" rel="noreferrer">Vela™</a> : null}
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

function Spark({ values }: { values: number[] }) {
  const lo = Math.min(...values), hi = Math.max(...values), w = 120, h = 22;
  const d = values.map((v, i) => `${i ? "L" : "M"}${(i / (values.length - 1)) * w},${h - ((v - lo) / (hi - lo || 1)) * h}`).join("");
  return <svg className="dv-spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden><path d={d} fill="none" stroke={values.at(-1)! >= values[0] ? "var(--up)" : "var(--down)"} strokeWidth="1.5" /></svg>;
}
