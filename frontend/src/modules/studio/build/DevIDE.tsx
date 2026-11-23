"use client";

import { DiffEditor } from "@monaco-editor/react";
import { Group, Panel, Separator, type GroupImperativeHandle } from "react-resizable-panels";
import Link from "next/link";
import { ArrowDownToLine, Eraser, WrapText, BookOpen, Bug, CircleAlert, Gauge, SquareTerminal, ChevronDown, Play, StepBack, StepForward, CornerDownRight, Maximize2, Minimize2, CaseSensitive, Pin, Lock, RotateCcw, Tag, Unlock, FileCode2, FilePlus2, FlaskConical, GitBranch, LayoutTemplate, ListTree, Pencil, Regex, Search, Trash2, Upload, WholeWord, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";
import { SERIES } from "@/charts/core";
import { Distribution } from "@/charts/Distribution";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import { studio, usePyTemplates } from "../api";
import { RECIPES } from "./recipes";
import { useLayout } from "@/workspace/layout";
import { CodeEditor, type EditorAction, type Problem } from "./CodeEditor";
import { useServerPref } from "./serverPref";
import { DevChart } from "./DevChart";
import { CHART_CHANNEL } from "./ChartPopout";
import { RunConfigPicker, RunConfigsDialog, useRunConfigs } from "./RunConfigs";
import { fitWorkspace, LayoutsDialog, targets, useWorkspaces, WorkspaceMenu, type PanelId } from "./Workspace";
import { DevRobust } from "./DevRobust";
import { DevRuns, type RunEntry } from "./DevRuns";
import { DevTearsheet } from "./DevTearsheet";
import { RunSummary } from "./RunSummary";
import { tradeSummary } from "./devStats";
import { NotifyBell } from "./NotifyBell";
import { Terminal, type TerminalHost } from "./Terminal";

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
  repaint?: { cuts: number; changed: number; dates: string[] } | null;
  invariants?: { count: number; rows: { date: string; symbol: string | null; file: string; line: number; text: string }[] } | null;
  coverage?: Record<string, { hit: number[]; lines: number[] }> | null;
};
/** Icicle chart: one row per stack depth, width = inclusive seconds; callees sit inside their caller's span. */
function Flame({ stacks }: { stacks: { path: string[]; seconds: number }[] }) {
  type N = { name: string; sec: number; kids: Map<string, N> };
  const root: N = { name: "", sec: 0, kids: new Map() };
  for (const { path, seconds } of stacks) {
    let n = root; // stacks are inclusive per path: a node's width is its own entry
    for (const f of path) { let k = n.kids.get(f); if (!k) { k = { name: f, sec: 0, kids: new Map() }; n.kids.set(f, k); } n = k; }
    n.sec = seconds;
  }
  const rows: { name: string; left: number; width: number; sec: number }[][] = [];
  const total = [...root.kids.values()].reduce((a, k) => a + k.sec, 0) || 1;
  const walk = (n: N, depth: number, left: number) => { let x = left; for (const k of [...n.kids.values()].sort((a, b) => b.sec - a.sec)) { (rows[depth] ??= []).push({ name: k.name, left: x, width: k.sec / total, sec: k.sec }); walk(k, depth + 1, x); x += k.sec / total; } };
  walk(root, 0, 0);
  return <div className="dv-flame">{rows.map((row, d) => <div key={d} className="dv-flame-row">{row.map((c, i) => <div key={i} title={`${c.name}  ${c.sec.toFixed(4)} s`} style={{ left: `${c.left * 100}%`, width: `${Math.max(c.width * 100, 0.2)}%` }}>{c.name}</div>)}</div>)}</div>;
}
type Profile = { lines?: { file?: string; line: number; seconds: number; hits?: number; source?: string }[]; functions?: { function?: string; name?: string; seconds: number; calls?: number }[]; stacks?: { path: string[]; seconds: number }[] };
export type QuickRun = { job_id: string; level: "quick" | "full"; status: string; progress?: { percent?: number; message?: string; partial?: { symbols?: number; bars?: number; elapsed_seconds?: number; budget_seconds?: number } } | null;
  error?: string | null; delta?: { total_return: number | null; sharpe: number | null; trades: number | null } | null;
  result?: { summary_cards?: { label: string; value: number | null }[]; charts?: { equity_curve?: { date: string; strategy: number; benchmark: number | null }[] }; tables?: { trades?: Record<string, unknown>[] };
    meta?: { headline?: string; total_return?: number; metrics?: Record<string, number | null>; trade_split?: Record<string, Record<string, number>> } } };
type Sym = { name: string; kind: string; line: number; column: number; children: Sym[] };
type Debug = { date: string; symbol: string; bar_index: number; state: Record<string, unknown>; context: Record<string, number | null>; orders: Record<string, unknown>[]; fills: Record<string, unknown>[];
  previous_date: string | null; next_date: string | null; breakpoint?: { file: string; line: number; hit_count: number; locals: Record<string, unknown>; watch?: { name: string; before: unknown; after: unknown } | null } | null; equity_change?: number | null };
type QC = { ok: boolean; code: string; symbols: string[]; converted: { line: number; before: string; after: string }[]; unconverted: { line: number; source: string; reason: string }[] };
type Member = { name: string; kind: string; signature: string | null; documentation: string | null };
type Version = { version: number; created: number; actor: string };
type Timeline = Version & { name: string; tags: string[]; locked: boolean; sharpe: number | null; total_return: number | null; spark: number[] };
type Snapshot = { at: number; files: Record<string, string> };
type Shelved = { name: string; at: number; files: Record<string, string> };
type Snippet = { id: string; name: string; prefix: string; body: string; description: string; tags?: string[] };
type RunSum = { total_return?: number; sharpe?: number | null; trades?: number };
export type Logpoint = { file: string; line: number; message: string };
type Tab = "tester" | "problems" | "output" | "plots" | "trades" | "debug" | "console" | "cells" | "preview";
/** The chart's crosshair date in the status bar (listens to studio:cursor-date, so DevIDE does not re-render on mouse moves). */
function CursorDate() {
  const [d, setD] = useState("");
  useEffect(() => { const on = (e: Event) => setD((e as CustomEvent<string>).detail); window.addEventListener("studio:cursor-date", on); return () => window.removeEventListener("studio:cursor-date", on); }, []);
  return d ? <span title="Chart cursor date">{d}</span> : null;
}
const hasCellsFor = (src?: string) => /^\s*# %%/m.test(src ?? "");
type CellPlot = { name: string; x: string[]; series: Record<string, (number | null)[]> };
type CellRow = { index: number | null; line?: number; stdout: string; value: unknown; error: string | null; error_line: number | null; seconds: number; plots?: CellPlot[] };
/** plot() output from a cell or the Console's Python session. */
export function CellPlots({ plots }: { plots?: CellPlot[] }) {
  return <>{(plots ?? []).map((p, i) => {
    const keys = Object.keys(p.series);
    return <div key={i} className="dv-plot"><b>{p.name}</b><TimeSeries data={p.x.map((d, j) => ({ date: d, ...Object.fromEntries(keys.map((k) => [k, p.series[k]![j]])) }))} series={keys.map((k, j) => ({ key: k, label: k, color: SERIES[j % SERIES.length]! }))} height={180} legend={keys.length > 1} /></div>;
  })}</>;
}
type View = "code" | "results" | "tearsheet" | "robust" | "runs" | "selection";
const VIEW_LABEL: Record<Exclude<View, "code">, string> = { results: "Results", tearsheet: "Tearsheet", robust: "Robustness", runs: "Runs", selection: "Selection" };
type Rail = "files" | "outline" | "search" | "versions" | "tests" | "docs" | "templates";
type TestRow = { file: string; name: string; line: number; status: "passed" | "failed" | "error"; seconds: number; message?: string; error_line?: number };
const TEST_FILE = "from studio.testing import bars\n\n\ndef test_closes_are_positive():\n    b = bars(50)\n    assert min(b[\"close\"]) > 0\n";
type Spec = { code: string; files?: Record<string, string>; params: Record<string, { value: number; min?: number | null; max?: number | null; step?: number | null }>; [k: string]: unknown };
export type Saved = "saved" | "draft" | "saving" | "conflict" | "new";

const show = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(4)) : typeof v === "object" ? JSON.stringify(v) : String(v));
const pct = (v?: number) => (v === undefined ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
const DOC_SCOPES = ["ctx", "portfolio_ctx", "numpy", "pandas", "math", "statistics"];
const RAILS: [Rail, ReactNode, string][] = [
  ["files", <FileCode2 key="f" size={18} />, "Explorer"], ["outline", <ListTree key="o" size={18} />, "Outline"], ["search", <Search key="s" size={18} />, "Search"],
  ["versions", <GitBranch key="v" size={18} />, "Versions"], ["tests", <FlaskConical key="x" size={18} />, "Tests"], ["docs", <BookOpen key="d" size={18} />, "Docs"], ["templates", <LayoutTemplate key="t" size={18} />, "Starters"],
];

const money = (v: number) => `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
/** Strategy Tester summary: every headline number on one screen, colour only where it means gain or loss. */
function Tester({ trades, inputs }: { trades: Record<string, unknown>[]; inputs: ReactNode }) {
  const s = useMemo(() => tradeSummary(trades), [trades]);
  // Run feedback in place: after a re-run, tiles that moved show a ±delta that fades out.
  const last = useRef<typeof s | null>(null);
  const [diff, setDiff] = useState<Record<string, string>>({});
  useEffect(() => {
    const p = last.current; last.current = s;
    if (!p?.trades || !s.trades) return;
    const sign = (v: number, f: (x: number) => string) => (v ? `${v > 0 ? "+" : "−"}${f(Math.abs(v))}` : "");
    const d: Record<string, string> = {
      "Net P&L": sign(s.net - p.net, money), "Max drawdown": sign(s.maxdd - p.maxdd, money), Trades: sign(s.trades - p.trades, String),
      "Win rate": s.win !== null && p.win !== null ? sign(Math.round((s.win - p.win) * 100), (x) => `${x}pp`) : "",
    };
    setDiff(d);
    const t = setTimeout(() => setDiff({}), 3000); return () => clearTimeout(t);
  }, [s]);
  const tiles: [string, string, "up" | "down" | null][] = [
    ["Net P&L", money(s.net), s.net >= 0 ? "up" : "down"], ["Max drawdown", money(s.maxdd), s.maxdd < 0 ? "down" : null],
    ["Win rate", s.win === null ? "–" : `${(s.win * 100).toFixed(0)}%`, null], ["Profit factor", s.pf === null ? "–" : s.pf.toFixed(2), s.pf === null ? null : s.pf >= 1 ? "up" : "down"],
    ["Trades", String(s.trades), null], ["Avg trade", s.avg === null ? "–" : money(s.avg), s.avg === null ? null : s.avg >= 0 ? "up" : "down"],
  ];
  return (
    <div className="dv-tester">
      <div className="dv-tester-main">
      {s.trades ? <dl className="dv-tiles">{tiles.map(([k, v, tone]) => <div key={k}><dt>{k}</dt><dd className="num" data-tone={tone ?? undefined}>{v}{diff[k] ? <small className="dv-tdelta">{diff[k]}</small> : null}</dd></div>)}</dl> : <p className="dv-empty">Run the preview to see results</p>}
      {s.curve.length > 1 ? <TimeSeries data={s.curve} series={[{ key: "net", label: "Cumulative P&L", color: "var(--text-2)" }, { key: "dd", label: "Drawdown", color: "var(--down)" }]} height={140} legend={false} /> : null}
      </div>
      <aside className="dv-tester-set" aria-label="Inputs"><h4>Inputs</h4>{inputs}</aside>
    </div>
  );
}

/** Variables at a paused bar: name and value, numbers right-aligned. */
type VarTable = { shape: number[]; columns: string[]; dtypes: string[]; summary: ({ min?: number; max?: number; mean?: number; missing: number } | null)[]; spark: ((number | null)[] | null)[];
  head: unknown[][]; head_index: (string | number)[]; index: (string | number)[]; rows: unknown[][] };
const tableOf = (v: unknown) => (v && typeof v === "object" && "__table__" in v ? (v as { __table__: VarTable }).__table__ : null);
/** Variable explorer: a DataFrame, Series or array local with types, a summary, a sparkline, and its first and last rows. */
function VarGrid({ t, open }: { t: VarTable; open?: boolean }) {
  const row = (r: unknown[], i: string | number) => <tr key={`r${i}`}><th>{i}</th>{r.map((x, j) => <td key={j}>{show(x)}</td>)}</tr>;
  return (
    <details className="dv-vgrid" open={open}><summary>{t.shape.join(" × ")}</summary>
      <div><table>
        <thead><tr><th />{t.columns.map((c, j) => <th key={c} title={t.dtypes[j]}>{c}<small>{t.dtypes[j]}</small></th>)}</tr></thead>
        {t.shape[0] > 10 ? <tbody className="dv-vsum">
          <tr><th>min · max</th>{t.summary.map((m, j) => <td key={j}>{m?.min !== undefined ? `${show(m.min)} · ${show(m.max)}` : "—"}</td>)}</tr>
          <tr><th>mean</th>{t.summary.map((m, j) => <td key={j}>{show(m?.mean)}</td>)}</tr>
          <tr><th>missing</th>{t.summary.map((m, j) => <td key={j}>{m ? m.missing : "—"}</td>)}</tr>
          <tr><th />{t.spark.map((v, j) => <td key={j}>{(v?.filter((x) => x !== null).length ?? 0) > 1 ? <Spark values={v!.filter((x): x is number => x !== null)} /> : null}</td>)}</tr>
        </tbody> : null}
        <tbody>{t.head.map((r, i) => row(r, t.head_index[i]))}{t.head.length ? <tr className="dv-vgap"><th>…</th>{t.columns.map((c) => <td key={c} />)}</tr> : null}{t.rows.map((r, i) => row(r, t.index[i]))}</tbody>
      </table></div>
    </details>
  );
}
function KV({ rows }: { rows: Record<string, unknown> }) {
  return <dl className="dv-kv">{Object.entries(rows).map(([k, v]) => { const t = tableOf(v); return <div key={k}><dt>{k}</dt><dd data-num={typeof v === "number" || undefined}>{t ? <VarGrid t={t} /> : show(v)}</dd></div>; })}</dl>;
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
export function DevIDE({ tools, spec, edit, symbol, prev, side, canRun, starting, onPreview, onSave, compileProblems, strategyId, versions, runs, saved, trial, readOnly, onReload, version, stale, onPause, font, quick, onQuickRun, onCancel, savedFiles, logpoints = [], onLogpoints, coverage = false, onCoverage }: {
  tools?: ReactNode; spec: Spec; edit: (next: Partial<Spec>) => void; symbol: string; prev: DevPreview | null; side: ReactNode; canRun: boolean; starting: boolean; onPreview: () => void;
  onSave: () => void; compileProblems: Problem[];
  strategyId?: string; versions: Version[]; runs: Record<string, RunSum>; saved: Saved; trial?: ReactNode; readOnly?: boolean; onReload?: () => void; version?: number; stale?: boolean; onPause?: (date: string | null, label?: string) => void; font?: number; savedFiles?: Record<string, string>;
  quick?: QuickRun | null; onQuickRun: (level: "quick" | "full", settings?: Record<string, unknown>) => void; onCancel?: () => void; logpoints?: Logpoint[]; onLogpoints?: (l: Logpoint[]) => void; coverage?: boolean; onCoverage?: (on: boolean) => void;
}) {
  // Scratch files live in this browser only: they sit in `files` for the editor but never reach the spec, runs or saves.
  const [scratch, setScratch] = useState<Record<string, string>>(() => { try { return JSON.parse(localStorage.getItem("studio:dev:scratch") ?? "{}"); } catch { return {}; } });
  useEffect(() => { try { localStorage.setItem("studio:dev:scratch", JSON.stringify(scratch)); } catch { /* blocked */ } }, [scratch]);
  const files = useMemo(() => ({ "main.py": spec.code, ...(spec.files ?? {}), ...scratch }), [spec.code, spec.files, scratch]);
  const [open, setOpen] = useState<string[]>(["main.py"]);
  const [active, setActive] = useState("main.py");
  const [rail, setRail] = useState<Rail>("files");
  const ws = useWorkspaces();
  const open_ = ws.cur.layout.open;
  const setOpenP = (p: PanelId, v: boolean | ((o: boolean) => boolean)) => ws.patch((l) => ({ ...l, open: { ...l.open, [p]: typeof v === "function" ? v(l.open[p]) : v } }));
  const [iconsOpen, setIconsOpen] = useState(true);
  // Zen hides the rail, icons, bottom panel and chart without touching the saved layout, so leaving it restores exactly.
  const [zen, setZen] = useState(false);
  // Maximised chart: the chart takes the whole body (CSS collapses the other panels), the saved layout is untouched.
  const [maxChart, setMaxChart] = useState(false);
  useEffect(() => {
    if (!maxChart) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape" && !(e.target instanceof Element && e.target.closest("input, textarea, select, .monaco-editor, [role=dialog]"))) setMaxChart(false); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [maxChart]);
  useEffect(() => {
    if (!zen) return;
    let last = 0;
    const esc = (e: KeyboardEvent) => { if (e.key !== "Escape") return; if (Date.now() - last < 600) setZen(false); last = Date.now(); };
    window.addEventListener("keydown", esc, true); return () => window.removeEventListener("keydown", esc, true);
  }, [zen]);
  // The workspace header has a slot for page controls; on phones the controls stay in their own bar.
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  useEffect(() => { if (!matchMedia("(max-width: 760px)").matches) setSlot(document.getElementById("ws-slot")); }, []);
  const setRailOpen = (v: boolean | ((o: boolean) => boolean)) => setOpenP("rail", v);
  const setPanelOpen = (v: boolean | ((o: boolean) => boolean)) => setOpenP("tester", v);
  const hRef = useRef<GroupImperativeHandle>(null), vRef = useRef<GroupImperativeHandle>(null);
  const chartSeen = useRef(false);
  const [view, setView] = useState<View>("code");
  const [reportSide, setReportSide] = useState(false);
  const showingSide = view === "code" || reportSide;
  const railOpen = iconsOpen && open_.rail && view === "code" && !zen;
  const panelOpen = open_.tester && (view === "code" || reportSide) && !zen;
  const bodyRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const body = bodyRef.current;
    if (!body) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(body);
    return () => observer.disconnect();
  }, []);
  const chartFirst = ws.cur.id === "chart-first";
  // A layout can bring its own focus: Debug opens the Debug tab, Review opens Results full width.
  const leftView = useRef(false);
  useEffect(() => {
    const f = ws.cur.layout.focus;
    if (f?.tab) setTab(f.tab);
    if (f?.view) openView(f.view); else if (leftView.current) setView("code");  // leaving Review returns to the code
    leftView.current = !!f?.view;
  }, [ws.cur.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const layout = fitWorkspace({ ...ws.cur.layout, open: { ...open_, rail: railOpen, tester: panelOpen, chart: showingSide && open_.chart && !zen, preview: false } }, width, chartFirst);
  const chartOpen = layout.open.chart;
  // Docking (W-5): the chart sits left or right of the editor; the bottom panel sits under the editor or across the full width.
  const dock = ws.cur.layout.dock ?? {};
  const full = dock.panel === "full", chartLeft = dock.chart === "left", pside = dock.panel === "left" || dock.panel === "right" ? dock.panel : null;
  const vKeys = (v: { editor: number; tester: number }) => (full ? { top: v.editor, tester: v.tester } : v);

  if (chartOpen) chartSeen.current = true;
  const [extra, setExtra] = useState<Exclude<View, "code">[]>([]);
  const tabStrip = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const strip = tabStrip.current;
    const selected = strip?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!strip || !selected) return;
    const bounds = strip.getBoundingClientRect();
    const tab = selected.getBoundingClientRect();
    if (tab.right > bounds.right) strip.scrollLeft += tab.right - bounds.right;
    else if (tab.left < bounds.left) strip.scrollLeft -= bounds.left - tab.left;
  }, [active, view, extra]);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const stepping = useRef(false);
  const debugRef = useRef<(b: Record<string, unknown>, quiet?: boolean) => Promise<void> | void>(() => undefined);
  const [panelMax, setPanelMax] = useState(false);
  const testerBeforeMax = useRef<number | null>(null);
  const [tab, setTab] = useState<Tab>("tester");
  const [lint, setLint] = useState<Problem[]>([]);
  const [types, setTypes] = useState<Problem[]>([]);
  const [sev, setSev] = useState<Record<string, string>>({});
  useServerPref("inspections", sev, setSev);
  const [scope, setScope] = useState<"file" | "project">("file");
  const [report, setReport] = useState<Problem[]>([]);
  const [outline, setOutline] = useState<Sym[]>([]);
  const [cursor, setCursor] = useState({ line: 1, column: 1 });
  const [reveal, setReveal] = useState<{ line: number; column?: number; n: number } | null>(null);
  // Dev wants the width: the workspace sidebar closes while Dev is open and comes back after (user feedback 2026-11-20).
  useEffect(() => { const was = useLayout.getState().open.left; useLayout.getState().set("left", false, true); return () => useLayout.getState().set("left", was, true); }, []);
  const [logQ, setLogQ] = useState("");
  const [logWrap, setLogWrap] = useState(false);
  const [logCleared, setLogCleared] = useState<unknown>(null); // the cleared logs array; the next preview brings new output back
  const [logLevel, setLogLevel] = useState<string>("all");
  const [logSym, setLogSym] = useState("");
  const [logFrom, setLogFrom] = useState("");
  const [plotsOn, setPlotsOn] = useState<Record<string, boolean>>({});
  const [dbg, setDbg] = useState<Debug | null>(null);
  const [dbgDate, setDbgDate] = useState("");
  const [watches, setWatches] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem("studio:watch") ?? "[]"); } catch { return []; } });
  const [watchRows, setWatchRows] = useState<{ expression: string; error: string | null; value: unknown; history: { date: string; value: number }[] }[]>([]);
  const [watchIn, setWatchIn] = useState("");
  const [cond, setCond] = useState("");
  const [hitN, setHitN] = useState("");
  const [trig, setTrig] = useState("");
  const [dwatch, setDwatch] = useState("");
  const lastRun = useRef<{ level: "quick" | "full"; settings: Record<string, unknown> } | null>(null);
  const [bps, setBps] = useState<Record<string, number[]>>({});
  const [q, setQ] = useState(""); const [rep, setRep] = useState("");
  const [opt, setOpt] = useState({ regex: false, caseSensitive: false, word: false });
  const [docs, setDocs] = useState<(Member & { scope: string })[] | null>(null);
  const [docQ, setDocQ] = useState("");
  const [diff, setDiff] = useState<{ version: number; files: Record<string, string>; to?: { version: number; files: Record<string, string> } } | null>(null);
  const shelfKey = `studio:shelf:${strategyId ?? "draft"}`;
  const [shelf, setShelf] = useState<Shelved[]>(() => { try { return JSON.parse(localStorage.getItem(shelfKey) ?? "[]"); } catch { return []; } });
  const writeShelf = (next: Shelved[]) => { setShelf(next); try { localStorage.setItem(shelfKey, JSON.stringify(next)); } catch { toast.error("Shelf could not be saved"); } };
  const [lastPreview, setLastPreview] = useState<string | null>(null);
  const [qc, setQc] = useState<QC | null>(null);
  const [split, setSplit] = useState<string | null>(null);
  const [layoutsOpen, setLayoutsOpen] = useState(false);
  const rc = useRunConfigs();
  const [rcOpen, setRcOpen] = useState(false);
  const [splitDown, setSplitDown] = useState(false);
  const editorSplitRef = useRef<GroupImperativeHandle>(null);
  const [dropSide, setDropSide] = useState<"main" | "split" | null>(null); // a tab dragged over the editor: right half opens it in the second group
  useEffect(() => {
    const primary = split && !diff ? (ws.cur.layout.size.split ?? 50) : 100;
    editorSplitRef.current?.setLayout({ primary, secondary: 100 - primary });
  }, [split, splitDown, diff, ws.cur.id, ws.cur.layout.size.split]);
  const [preview, setPreview] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string[]>([]);
  const [logTop, setLogTop] = useState(0);
  const [profile, setProfile] = useState<Profile | "loading" | null>(null);
  const [strict, setStrict] = useState(() => { try { return localStorage.getItem("studio:dev:strict") === "1"; } catch { return false; } });
  const [timeline, setTimeline] = useState<Timeline[]>([]);
  const [snaps, setSnaps] = useState<Snapshot[]>([]);
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  const [snipTag, setSnipTag] = useState<string | null>(null);
  // Artefacts: a file saved by name and kind (indicator, transform, filter, sweep, plot) that any strategy can add as lib_<name>.py.
  // Adding copies the code into the project, so a strategy's hash and results never change when the artefact is edited later.
  type Artefact = { name: string; kind: string; code: string; updated: number };
  const [artefacts, setArtefacts] = useState<Artefact[]>([]);
  useServerPref("artefacts", artefacts, setArtefacts);
  const saveArtefact = (file: string) => {
    const name = window.prompt("Artefact name", file.replace(/^lib_|\.py$/g, ""))?.trim().replace(/\W+/g, "_").toLowerCase(); if (!name) return;
    const kind = window.prompt("Kind: indicator, transform, filter, sweep or plot", "indicator")?.trim().toLowerCase() || "indicator";
    setArtefacts((a) => [...a.filter((x) => x.name !== name), { name, kind, code: files[file] ?? "", updated: Date.now() }]); toast.success(`Saved artefact ${name}`);
  };
  const addArtefact = (a: Artefact) => {
    const f = `lib_${a.name}.py`;
    if (f in files && files[f] !== a.code && !window.confirm(`${f} differs from the saved artefact. Replace it?`)) return;
    edit({ files: { ...(spec.files ?? {}), [f]: a.code } }); goto(f, 1); toast(`Added ${f}: import it with from lib_${a.name} import …`);
  };
  const selection = useRef("");
  const insertAt = useRef<((text: string) => void) | null>(null);
  const qcRef = useRef<HTMLDialogElement>(null);
  const pyTemplates = usePyTemplates();
  const source = files[active] ?? "";

  // Inputs: params = {"name": (default, min, max, step)} in class Strategy, plus saved overrides; editing one re-runs the preview.
  const inputs = useMemo(() => {
    const out: Spec["params"] = {};
    // Strategy's params, then each indicator class's inputs as Class_name (the backend reads both the same way).
    for (const cls of spec.code.split(/^class\s+/m).slice(1)) {
      const name = /^(\w+)/.exec(cls)?.[1] ?? "", strat = name === "Strategy";
      const body = new RegExp(`^\\s+${strat ? "params" : "inputs"}\\s*=\\s*\\{([^}]*)\\}`, "m").exec(cls)?.[1] ?? "";
      for (const m of body.matchAll(/["'](\w+)["']\s*:\s*\(\s*([-\d.e]+)\s*,\s*([-\d.e]+)\s*,\s*([-\d.e]+)\s*,\s*([-\d.e]+)\s*\)/g)) out[strat ? m[1] : `${name}_${m[1]}`] = { value: +m[2], min: +m[3], max: +m[4], step: +m[5] };
    }
    return { ...out, ...Object.fromEntries(Object.entries(spec.params).map(([k, p]) => [k, { ...out[k], ...p }])) };
  }, [spec.code, spec.params]);
  const setInput = (n: string, p: Spec["params"][string], value: number) => Number.isFinite(value) && edit({ params: { ...spec.params, [n]: { ...p, value } } });
  // One inputs list, shown in the Files rail and in the Tester's settings (TradingView Strategy Tester "Inputs").
  const inputList = Object.keys(inputs).length ? Object.entries(inputs).map(([n, p]) => (
    <label key={n} className="dv-input">
      <span><code>{n}</code><input className="input sm" type="number" value={p.value} min={p.min ?? undefined} max={p.max ?? undefined} step={p.step ?? "any"} onChange={(e) => setInput(n, p, +e.target.value)} /></span>
      {p.min != null && p.max != null ? <input type="range" aria-label={n} value={p.value} min={p.min} max={p.max} step={p.step ?? "any"} onChange={(e) => setInput(n, p, +e.target.value)} /> : null}
    </label>
  )) : <p className="dv-empty">None</p>;
  // Name the browser tab after the strategy.
  useEffect(() => { document.title = spec.name ? `${spec.name} · Build · ATLAS` : "Build · ATLAS"; }, [spec.name]);
  // Recent strategies (palette: "Open recent"), newest first.
  const [recentStrats, setRecentStrats] = useState<{ id: string; name: string }[]>([]);
  useEffect(() => {
    let list: { id: string; name: string }[] = [];
    try { list = JSON.parse(localStorage.getItem("studio:recent") ?? "[]"); } catch { /* none */ }
    if (strategyId) { list = [{ id: strategyId, name: String(spec.name || "Untitled") }, ...list.filter((r) => r.id !== strategyId)].slice(0, 10); try { localStorage.setItem("studio:recent", JSON.stringify(list)); } catch { /* blocked */ } }
    setRecentStrats(list.filter((r) => r.id !== strategyId));
  }, [strategyId, spec.name]);
  const setFile = (name: string, text: string) => (keep(name), name in scratch ? setScratch((s) => ({ ...s, [name]: text })) : name === "main.py" ? edit({ code: text }) : edit({ files: { ...(spec.files ?? {}), [name]: text } }));
  const replaceFiles = (next: Record<string, string>) => {
    const all: Record<string, string> = { ...files, ...next };
    const { "main.py": code, ...rest } = all;
    setScratch((s) => Object.fromEntries(Object.keys(s).map((f) => [f, rest[f] ?? s[f]])));
    edit({ code, files: Object.fromEntries(Object.entries(rest).filter(([f]) => !(f in scratch))) });
  };
  const params = () => Object.fromEntries(Object.entries(spec.params).map(([k, p]) => [k, p.value]));
  const inspectProject = async () => {
    const found: Problem[] = [];
    setPanelOpen(true); setTab("problems"); setScope("project"); setReport([]);
    for (const f of Object.keys(files).filter((n) => n.endsWith(".py") && files[n].trim())) {
      const body = { code: files[f], file: f, files, params: params() };
      const [a, b] = await Promise.all([
        studio<{ problems: Problem[] }>("POST", "/build/check", { ...body, strictness: strict ? "strict" : "basic", severity: sev }).catch(() => ({ problems: [] as Problem[] })),
        studio<{ problems: Problem[] }>("POST", "/build/typecheck", body).catch(() => ({ problems: [] as Problem[] })),
      ]);
      found.push(...[...a.problems, ...b.problems].map((p) => ({ ...p, file: f })));
      setReport([...found]);
    }
    toast(found.length ? `${found.length} problem${found.length === 1 ? "" : "s"} in ${new Set(found.map((p) => p.file)).size} file(s)` : "No problems in the project");
  };
  const setSeverity = (code: string) => {
    const v = window.prompt(`Severity for ${code} (error, warning, info, off; empty resets)`, sev[code] ?? "")?.trim().toLowerCase();
    if (v === undefined) return;
    if (v && !["error", "warning", "info", "off"].includes(v)) return toast.error("Use error, warning, info or off");
    setSev((m) => { const { [code]: _, ...rest } = m; return v ? { ...rest, [code]: v } : rest; });
  };
  const refactor = (r: Record<string, unknown>) => {
    let extra: Record<string, unknown> = {};
    if (r.op === "move") { const target = window.prompt("Move to file", "helpers.py")?.trim(); if (!target) return; extra = { target }; }
    if (r.op === "signature") {
      const list = window.prompt("Parameters in order: name, or name=default for a new one", (r.params as string[]).join(", "));
      if (list === null) return;
      extra = { params: list.split(",").map((x) => x.trim()).filter(Boolean).map((x) => { const [name, ...d] = x.split("="); return { name: name.trim(), default: d.join("=").trim() || undefined }; }) };
    }
    void studio<Record<string, string>>("POST", "/build/refactor", { code: source, file: active, files, ...r, ...extra }).then((out) => { replaceFiles(out); toast.success("Refactored · ⌘Z to undo"); }, (e: Error) => toast.error(e.message));
  };
  const addScratch = () => {
    let n = 1; while (`scratch_${n}.py` in files) n++;
    const name = `scratch_${n}.py`;
    setScratch((s) => ({ ...s, [name]: "" })); setDiff(null); setOpen((o) => [...o, name]); setActive(name);
  };
  const dropScratch = (f: string) => { setScratch(({ [f]: _, ...rest }) => rest); close(f); };
  const [cellOut, setCellOut] = useState<{ file: string; titles: string[]; rows: CellRow[] } | "running" | null>(null);
  const hasCells = /^\s*# %%/m.test(files[active] ?? "");
  // Cells run in a live kernel per file: variables survive between runs. If the kernel (re)started, the cells above re-run first.
  const cellParts = (src: string) => { const lines = src.split("\n"), starts = [0, ...lines.flatMap((t, i) => (i && /^\s*# %%/.test(t) ? [i] : []))]; return starts.map((a, k) => lines.slice(a, starts[k + 1] ?? lines.length).join("\n")); };
  const lastRan = useRef<Record<string, string[]>>({});
  const runCells = (want: number[], quiet = false) => {
    const file = active, src = files[file] ?? "", parts = cellParts(src), key = `cells:${strategyId ?? "draft"}:${file}`;
    if (!quiet) { setPanelOpen(true); setTab("cells"); }
    setCellOut("running");
    const call = (cells: number[]) => studio<{ cells: { title: string }[]; outputs: CellRow[]; restarted: boolean }>("POST", "/build/kernel", { key, code: spec.code, files: spec.files ?? {}, file, cells, symbols: [symbol] });
    void call(want).then(async (r) => {
      if (r.restarted && Math.min(...want) > 0) r = await call([...Array(Math.max(...want) + 1).keys()]);
      lastRan.current[file] = parts;
      setCellOut({ file, titles: r.cells.map((c) => c.title), rows: r.outputs.filter((o) => o.index == null || want.includes(o.index)) });
    }).catch((e: Error) => { setCellOut(null); toast.error(e.message); });
  };
  const runCell = (line: number, only = true, below = false, quiet = false) => {
    const starts = [1, ...(files[active] ?? "").split("\n").flatMap((t, i) => (i && /^\s*# %%/.test(t) ? [i + 1] : []))];
    const at = starts.filter((s0) => s0 <= line).length - 1, n = starts.length;
    runCells(below ? [...Array(n - at).keys()].map((k) => k + at) : only ? [at] : [...Array(at + 1).keys()], quiet);
  };
  // Reactive cells: with Auto-run on, an edit re-runs the changed cells and every later cell that reads a name they assign.
  const [autoCells, setAutoCells] = useState(false);
  const cellSrc = hasCellsFor(files[active]) ? files[active] : null;
  const reactive = () => {
    const parts = cellParts(files[active] ?? ""), before = lastRan.current[active] ?? [];
    const dirty = new Set(parts.flatMap((t, i) => (t !== before[i] ? [i] : [])));
    for (let i = 0; i < parts.length; i++) {
      if (!dirty.has(i)) continue;
      const names = [...parts[i]!.matchAll(/^\s*([A-Za-z_]\w*)\s*(?:[-+*/]?=)(?!=)/gm)].map((m) => m[1]!);
      for (let j = i + 1; j < parts.length; j++) if (names.some((n) => new RegExp(`\\b${n}\\b`).test(parts[j]!))) dirty.add(j);
    }
    if (dirty.size) runCells([...dirty].sort((a, b) => a - b), true);
  };
  useEffect(() => { if (!autoCells || !cellSrc) return; const t = setTimeout(reactive, 900); return () => clearTimeout(t); }, [autoCells, cellSrc]); // eslint-disable-line react-hooks/exhaustive-deps
  // Back/forward history: positions left behind by jumps and file switches, newest last, capped at 50.
  const nav = useRef({ s: [] as { file: string; line: number }[], i: -1, jumping: false });
  const mark = (file: string, line: number) => { const n = nav.current, l = n.s[n.i]; if (l?.file === file && l.line === line) return; n.s = [...n.s.slice(0, n.i + 1), { file, line }].slice(-50); n.i = n.s.length - 1; };
  const hop = (d: 1 | -1) => { const n = nav.current; if (n.i === n.s.length - 1) mark(active, cursor.line); const t = n.s[n.i + d]; if (!t) return; n.i += d; n.jumping = true; goto(t.file, t.line); n.jumping = false; };
  const goto = (file: string, line: number, column?: number) => { if (!(file in files)) return; if (!nav.current.jumping) { mark(active, cursor.line); mark(file, line); } setDiff(null); setOpen((o) => (o.includes(file) ? o : [...o, file])); setActive(file); setReveal({ line, column, n: Date.now() }); };
  // Single click opens a preview tab that the next single click replaces; double click or an edit keeps it (B-13).
  const peek = (f: string) => { if (!(f in files)) return; mark(active, cursor.line); setDiff(null); setOpen((o) => (o.includes(f) ? o : [...o.filter((x) => x !== preview || pinned.includes(x)), f])); if (!open.includes(f)) setPreview(f); setActive(f); };
  const keep = (f: string) => { if (preview === f) setPreview(null); };
  const close = (f: string) => { const rest = open.filter((x) => x !== f); setOpen(rest.length ? rest : ["main.py"]); if (active === f) setActive(rest.at(-1) ?? "main.py"); };
  const editLogpoint = (line: number) => {
    const old = logpoints.find((p) => p.file === active && p.line === line);
    const message = window.prompt(`Log at ${active}:${line} (an expression, or text with {expressions}; empty removes)`, old?.message ?? "")?.trim();
    if (message === undefined) return;
    onLogpoints?.([...logpoints.filter((p) => p !== old), ...(message ? [{ file: active, line, message }] : [])]);
  };
  const inlineValues = (() => {
    const b = dbg?.breakpoint; if (!b || b.file !== active) return [];
    const lines = source.split("\n"), at = Math.min(b.line, lines.length) - 1, indent = (t: string) => t.length - t.trimStart().length;
    let from = at; while (from > 0 && !/^\s*(async\s+)?def\s/.test(lines[from]!)) from--; // paused function starts at the nearest def above
    const out: { line: number; text: string }[] = [];
    for (let i = from; i <= at; i++) {
      const m = /^\s*(?:self\.)?([A-Za-z_]\w*)\s*(?:[-+*/]?=)(?!=)/.exec(lines[i]!); const v = m && b.locals[m[1]!];
      if (m && v !== undefined && indent(lines[i]!) >= indent(lines[from]!)) out.push({ line: i + 1, text: `${m[1]} = ${typeof v === "string" ? v : JSON.stringify(v)}`.slice(0, 80) });
    }
    return out;
  })();
  const toggleBp = (line: number) => setBps((b) => { const cur = b[active] ?? []; return { ...b, [active]: cur.includes(line) ? cur.filter((x) => x !== line) : [...cur, line].sort((x, y) => x - y) }; });
  const [bms, setBms] = useState<Record<string, number[]>>({});
  const toggleBm = (line: number) => setBms((b) => { const cur = b[active] ?? []; return { ...b, [active]: cur.includes(line) ? cur.filter((x) => x !== line) : [...cur, line].sort((x, y) => x - y) }; });
  // Numbered bookmarks (JetBrains): Ctrl+Shift+N sets mark N on this line, Ctrl+N jumps to it in any file.
  const [nbm, setNbm] = useState<Record<number, { file: string; line: number }>>({});
  const setNumbered = (n: number, line: number) => setNbm((b) => { const cur = b[n]; const { [n]: _gone, ...rest } = b; return cur && cur.file === active && cur.line === line ? rest : { ...rest, [n]: { file: active, line } }; });
  const goNumbered = (n: number) => { const m = nbm[n]; if (m) goto(m.file, m.line); else toast(`No bookmark ${n}`); };
  const orderLines = prev?.order_lines;
  const markToCode = useCallback((d: string) => { const o = orderLines?.find((x) => x.dates.some((y) => y.slice(0, 10) === d)); if (o) gotoRef.current(o.file, o.line); else toast(`No order line for ${d}`); }, [orderLines]);
  const bmJump = (dir: 1 | -1, line: number) => {
    const marks = [...(bms[active] ?? [])].sort((x, y) => x - y);
    if (!marks.length) return toast("No bookmarks in this file");
    goto(active, dir === 1 ? marks.find((x) => x > line) ?? marks[0] : marks.findLast((x) => x < line) ?? marks.at(-1)!);
  };

  useEffect(() => {
    if (!source.trim()) { setLint([]); setTypes([]); setOutline([]); return; }
    const t = setTimeout(() => {
      void studio<{ problems: Problem[] }>("POST", "/build/check", { code: source, file: active, files, strictness: strict ? "strict" : "basic", severity: sev, params: Object.fromEntries(Object.entries(spec.params).map(([k, p]) => [k, p.value])) }).then((r) => setLint(r.problems), () => undefined);
      void studio<Sym[]>("POST", "/build/outline", { code: source }).then(setOutline, () => undefined);
      void studio<{ problems: Problem[] }>("POST", "/build/typecheck", { code: source, file: active, files }).then((r) => setTypes(r.problems), () => setTypes([]));
    }, 300);
    return () => clearTimeout(t);
  }, [source, active, files, spec.params, strict, sev]);
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
    const tags = (window.prompt("Tags (comma separated)", "") ?? "").split(",").map((t) => t.trim()).filter(Boolean);
    void studio<Snippet>("POST", "/snippets", { name, prefix, body, tags }).then((sn) => { setSnippets((x) => [...x, sn]); toast.success(`Saved ${name}`); }, (e: Error) => toast.error(e.message));
  };
  const actionsRef = useRef<EditorAction[]>([]);
  const gotoRef = useRef<(f: string | null, l: number, c?: number) => void>(() => undefined);
  gotoRef.current = (f, l, c) => goto(f ?? active, l, c);
  // Recent files (newest first) and the symbols of every file feed the shared palette (Search Everywhere, go to symbol).
  const [recent, setRecent] = useState<string[]>([]);
  useEffect(() => setRecent((r) => [active, ...r.filter((x) => x !== active)].slice(0, 20)), [active]);
  const symCache = useRef(new Map<string, { code: string; syms: Sym[] }>());
  const [projSyms, setProjSyms] = useState<{ file: string; name: string; line: number; column: number }[]>([]);
  useEffect(() => {
    const t = setTimeout(() => {
      const flat = (ss: Sym[], q = ""): { name: string; line: number; column: number }[] => ss.flatMap((x) => [{ name: q + x.name, line: x.line, column: x.column }, ...flat(x.children, `${q}${x.name}.`)]);
      void Promise.all(Object.entries(files).map(async ([file, code]) => {
        const c = symCache.current.get(file);
        const syms = c?.code === code ? c.syms : code.trim() ? await studio<Sym[]>("POST", "/build/outline", { code }).catch(() => [] as Sym[]) : [];
        symCache.current.set(file, { code, syms });
        return flat(syms).map((x) => ({ file, ...x }));
      })).then((all) => setProjSyms(all.flat()));
    }, 600);
    return () => clearTimeout(t);
  }, [files]);
  useEffect(() => {
    const item = (group: string, label: string, file: string, line: number, column: number, hidden: boolean) => ({ id: `nav:${JSON.stringify([file, line, column, group])}`, group, label, hidden });
    const flat = (ss: Sym[], q = ""): Sym[] => ss.flatMap((x) => [{ ...x, name: q + x.name }, ...flat(x.children, `${q}${x.name}.`)]);
    const names = Object.keys(files), order = [...recent.filter((f) => names.includes(f)), ...names.filter((f) => !recent.includes(f))];
    window.dispatchEvent(new CustomEvent("studio:devitems", { detail: [
      ...order.map((f, i) => item("File", f, f, 1, 1, i >= 5)),
      ...flat(outline).map((x) => item("Outline", x.name, active, x.line, x.column, true)),
      ...projSyms.map((x) => item("Symbol", `${x.name}  ${x.file}:${x.line}`, x.file, x.line, x.column, true)),
    ] }));
  }, [files, recent, outline, projSyms, active]);
  useEffect(() => () => { window.dispatchEvent(new CustomEvent("studio:devitems", { detail: [] })); }, []);
  useEffect(() => {
    const on = (e: Event) => {
      const id = (e as CustomEvent<string>).detail;
      if (id.startsWith("nav:")) { const [f, l, c] = JSON.parse(id.slice(4)); gotoRef.current(f, l, c); return; }
      if (id.startsWith("line:")) { const n = Number(id.slice(5)); if (n >= 1) gotoRef.current(null, Math.floor(n)); return; }
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
  // Look-ahead guard: the preview re-runs on cut-off history; signals that change mean the code reads future bars.
  const lookahead: Problem[] = prev?.repaint?.changed && active === "main.py" ? [{ severity: "warning", file: active, line: 1, column: 1, end_column: 200, code: "look-ahead",
    message: `Signals changed at ${prev.repaint.changed} of ${prev.repaint.cuts} history cuts (${prev.repaint.dates.slice(0, 5).join(", ")}): the code reads bars that were not known yet` }] : [];
  const problems = [...lint, ...types, ...compileProblems.filter((p) => p.file === active), ...runtime, ...broken, ...lookahead];
  const errors = problems.filter((p) => p.severity === "error").length, warnings = problems.length - errors;
  // The editor keeps the space; the panel opens on its own only when an error appears.
  const hadErrors = useRef(0);
  useEffect(() => { if (errors && !hadErrors.current) { setPanelOpen(true); setTab("problems"); } hadErrors.current = errors; }, [errors]);
  const logRe = finder(logQ, opt);
  // Pinned outputs (JetBrains pin tab): keep a preview's Output under a name to compare with later previews.
  const [pinnedOut, setPinnedOut] = useState<{ id: number; label: string; logs: NonNullable<DevPreview["logs"]> }[]>([]);
  const [outSrc, setOutSrc] = useState(0); // 0 = the live preview
  const srcLogs = outSrc ? pinnedOut.find((p) => p.id === outSrc)?.logs : prev?.logs;
  const logs = (logCleared === srcLogs ? [] : srcLogs ?? []).filter((l) => (logLevel === "all" || l.level === logLevel) && (!logSym || l.symbol === logSym) && (!logFrom || l.date >= logFrom) && (!logRe || (logRe.lastIndex = 0, logRe.test(`${l.date} ${l.symbol ?? ""} ${l.text}${l.fields ? Object.entries(l.fields).map(([k, v]) => ` ${k}=${show(v)}`).join("") : ""}`))));
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
  type Cmt = { id: string; thread_id: string; file: string; line: number; text: string; author: string; created: number; date?: string | null; resolved?: boolean };
  const [cmts, setCmts] = useState<Cmt[]>([]);
  const [thread, setThread] = useState<{ file: string; line: number; date?: string } | null>(null);
  const inThread = (c: Cmt, t: { file: string; line: number; date?: string }) => (t.date ? c.date === t.date : !c.date && c.file === t.file && c.line === t.line);
  // Shift+click a chart bar: a comment thread on that bar's date.
  const openBarThread = useCallback((date: string) => { if (!strategyId) return toast.error("Save the strategy to comment"); setThread({ file: "main.py", line: 1, date }); setCmtText(""); }, [strategyId]);
  const resolveThread = (tid: string, resolved: boolean) => void studio("PUT", `/strategies/${strategyId}/comments/threads/${tid}/resolved?resolved=${resolved}`).then(loadCmts, (e: Error) => toast.error(e.message));
  const [cmtText, setCmtText] = useState("");
  const loadCmts = () => { if (strategyId) void studio<Cmt[]>("GET", `/strategies/${strategyId}/comments`).then(setCmts, () => undefined); };
  useEffect(loadCmts, [strategyId]); // eslint-disable-line react-hooks/exhaustive-deps
  const openThread = (line: number) => { if (!strategyId) return toast.error("Save the strategy to comment"); setThread({ file: active, line }); setCmtText(""); setTimeout(() => document.querySelector<HTMLInputElement>(".dv-thread input")?.focus(), 80); };
  const postCmt = () => {
    if (!thread || !cmtText.trim()) return;
    const first = cmts.find((c) => inThread(c, thread));
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
  // Pop-out chart: send it the chart's state; it sends replay moves back.
  const chartChan = useRef<BroadcastChannel | null>(null);
  const chartState = { type: "state", symbol: dbg?.symbol ?? symbol, prev, pausedAt: dbg?.date ?? null, drawKey: strategyId ?? "new" };
  const chartStateRef = useRef(chartState); chartStateRef.current = chartState;
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const c = chartChan.current = new BroadcastChannel(CHART_CHANNEL);
    c.onmessage = (e: MessageEvent<{ type: string; date: string | null; step?: 1 | -1 }>) => { if (e.data.type === "hello") c.postMessage(chartStateRef.current); else if (e.data.type === "go") replayRef.current(e.data.date, e.data.step); };
    return () => c.close();
  }, []);
  useEffect(() => { chartChan.current?.postMessage(chartState); }, [symbol, prev, dbg?.date, strategyId]); // eslint-disable-line react-hooks/exhaustive-deps
  const replayRef = useRef<(date: string | null, step?: 1 | -1) => void>(() => undefined);
  const replayGo = useCallback((date: string | null, step?: 1 | -1) => {
    if (stepping.current) return;
    stepping.current = true;
    void Promise.resolve(date ? debugRef.current({ date }, true) : debugRef.current({ step }, true)).finally(() => { stepping.current = false; });
  }, []);
  replayRef.current = replayGo;
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
  const bpExtra = () => { const [tf, tl] = trig.split(":"); return { condition: cond || null, hit: Number(hitN) > 0 ? Number(hitN) : null, trigger: trig ? { file: tf, line: Number(tl) } : null }; };
  const startDebug = () => {
    const bp = Object.entries(bps).flatMap(([file, lines]) => lines.map((line) => ({ file, line })))[0];
    debug(bp ? { date: dbgDate || (prev?.bars?.[0]?.date ?? ""), breakpoint: { ...bp, ...bpExtra() } } : {});
  };
  const [tests, setTests] = useState<TestRow[]>([]);
  const [testing, setTesting] = useState(false);
  const testFiles = Object.keys(files).filter((f) => /^test_.*\.py$/.test(f));
  const runTests = (only?: TestRow[]) => {
    setTesting(true);
    const call = (body: { file?: string; name?: string }) => studio<{ tests: TestRow[] }>("POST", "/build/test", { code: spec.code, files: spec.files ?? {}, ...body }).then((r) => r.tests);
    void Promise.all(only ? only.map((t) => call({ file: t.file, name: t.name })) : [call({})]).then((rs) => {
      const got = rs.flat();
      setTests((old) => (only ? old.map((t) => got.find((g) => g.file === t.file && g.name === t.name) ?? t) : got));
    }, (e: Error) => toast.error(e.message)).finally(() => setTesting(false));
  };
  const runTestFile = (file: string) => {
    setTesting(true);
    void studio<{ tests: TestRow[] }>("POST", "/build/test", { code: spec.code, files: spec.files ?? {}, file }).then((r) => setTests((old) => [...old.filter((t) => t.file !== file), ...r.tests]), (e: Error) => toast.error(e.message)).finally(() => setTesting(false));
  };
  const runTestAtCursor = (line: number) => {
    const name = (files[active] ?? "").split("\n").slice(0, line).reverse().map((t) => /^def (test_\w+)/.exec(t)?.[1]).find(Boolean);
    if (!/^test_.*\.py$/.test(active) || !name) return toast("Put the cursor in a def test_ function");
    revealRail("tests"); runTests([{ file: active, name, line, status: "passed", seconds: 0 }]);
    setTests((old) => (old.some((t) => t.file === active && t.name === name) ? old : [...old, { file: active, name, line, status: "passed", seconds: 0 }]));
  };
  // Snapshot test: pin the preview's headline numbers; every later preview is compared with them.
  const snapKey = `studio:snapshot:${strategyId ?? "draft"}`;
  const [snap, setSnap] = useState<{ total_return: number; trades: number; last: string; orders?: string } | null>(() => { try { return JSON.parse(localStorage.getItem(`studio:snapshot:${strategyId ?? "draft"}`) ?? "null"); } catch { return null; } });
  const nowSnap = prev?.status === "ok" ? { total_return: Number((prev as { total_return?: number }).total_return ?? 0), trades: prev.trades.length, last: String(prev.trades.at(-1)?.entry_date ?? ""), orders: JSON.stringify((prev.order_lines ?? []).map((o) => [o.file, o.line, o.count, o.dates[0]])) } : null;
  const pinSnap = (v: typeof snap) => { setSnap(v); try { if (v) localStorage.setItem(snapKey, JSON.stringify(v)); else localStorage.removeItem(snapKey); } catch { /* blocked */ } };
  const snapSame = !!snap && !!nowSnap && Math.abs(snap.total_return - nowSnap.total_return) < 1e-9 && snap.trades === nowSnap.trades && snap.last === nowSnap.last && (snap.orders ?? nowSnap.orders) === nowSnap.orders;
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
  // Diff a saved version against the draft, or against a second version when `right` is given.
  const openDiff = (v: number, right?: number) => {
    if (!strategyId) return;
    const load = (n: number) => studio<{ files: Record<string, string> }>("GET", `/strategies/${strategyId}/files?version=${n}`).then((r) => r.files);
    void Promise.all([load(v), right == null ? null : load(right)]).then(([files, to]) => setDiff({ version: v, files, to: right != null && to ? { version: right, files: to } : undefined }), (e: Error) => toast.error(e.message));
  };
  // Park the draft's files on the shelf, then reset the draft to the latest saved version (⌘Z undoes the reset).
  const shelveChanges = () => {
    const last = timeline[timeline.length - 1]?.version;
    if (!strategyId || last == null) return;
    const name = window.prompt("Shelf name", `Shelf ${shelf.length + 1}`)?.trim(); if (!name) return;
    const draft = files;
    void studio<{ files: Record<string, string> }>("GET", `/strategies/${strategyId}/files?version=${last}`).then((r) => {
      writeShelf([{ name, at: Date.now(), files: draft }, ...shelf]);
      const { "main.py": code = "", ...rest } = r.files;
      edit({ code, files: Object.fromEntries(Object.entries(rest).filter(([f]) => !(f in scratch))) });
      toast(`Shelved ${name} · draft reset to v${last} · ⌘Z to undo`);
    }, (e: Error) => toast.error(e.message));
  };
  const unshelve = (s: Shelved) => { replaceFiles(s.files); toast(`${s.name} unshelved · ⌘Z to undo`); };
  const dropShelf = (s: Shelved) => { if (window.confirm(`Delete shelf "${s.name}"? This cannot be undone.`)) writeShelf(shelf.filter((x) => x.at !== s.at)); };
  const runProfile = () => {
    openView("results"); setProfile("loading");
    void studio<{ profile?: Profile }>("POST", "/build/profile", { spec, symbol }).then((r) => setProfile(r.profile ?? {}), (e: Error) => { setProfile(null); toast.error(e.message); });
  };
  useEffect(() => {
    if (!quick || !["queued", "running"].includes(quick.status)) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel?.(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [quick, onCancel]);
  useEffect(() => { const t = targets(layout); hRef.current?.setLayout(t.h); vRef.current?.setLayout(vKeys(t.v)); }, [ws.cur.id, pside, railOpen, chartOpen, panelOpen, width, full, chartLeft]); // eslint-disable-line react-hooks/exhaustive-deps
  /** Remember the exact panel sizes and close a panel pulled to the edge. */
  const onH = (l: Record<string, number>, m: { isUserInteraction: boolean }) => {
    if (!m.isUserInteraction) return;
    const right = l.right;
    ws.patch((x) => ({ open: { ...x.open, rail: railOpen ? l.rail >= 6 : x.open.rail, chart: chartOpen ? x.open.chart && right >= 8 : x.open.chart },
      size: { ...x.size, rail: railOpen && l.rail >= 6 ? l.rail : x.size.rail, right: right >= 8 ? right : x.size.right } }));
  };
  const onV = (l: Record<string, number>, m: { isUserInteraction: boolean }) => {
    if (!m.isUserInteraction) return;
    ws.patch((x) => ({ open: { ...x.open, tester: x.open.tester && l.tester >= 8 }, size: { ...x.size, tester: x.open.tester && l.tester >= 8 ? l.tester : x.size.tester } }));
  };
  const maxTester = () => { const next = !panelMax; setPanelMax(next); if (next) testerBeforeMax.current = vRef.current?.getLayout().tester ?? ws.cur.layout.size.tester; const t = next ? 85 : (testerBeforeMax.current ?? 34); ws.patch((x) => ({ ...x, size: { ...x.size, tester: t } })); vRef.current?.setLayout(vKeys({ editor: 100 - t, tester: t })); };

  const running = quick?.status === "queued" || quick?.status === "running";
  const runCode = (level: "quick" | "full" = "quick") => {
    if (!canRun || starting || running) return;
    openView("results");
    lastRun.current = { level, settings: rc.settings };
    onQuickRun(level, rc.settings);
  };
  const rerunLast = () => { const l = lastRun.current; if (!l || !canRun || starting || running) return; openView("results"); onQuickRun(l.level, l.settings); };
  // Paper: the strategy's paper record (freeze, stop and flatten, debug a paper day) in the status bar.
  type PaperSeg = { version: number; from: string; to?: string; backdated: boolean };
  const [paper, setPaper] = useState<{ segments: PaperSeg[]; last: { total_return?: number; paper_day?: number; at?: number } | null; freshness: { tone: string; age_days: number } } | null>(null);
  const [paperOpen, setPaperOpen] = useState(false);
  const loadPaper = useCallback(() => { if (strategyId) void studio<NonNullable<typeof paper>>("GET", `/strategies/${strategyId}/paper`).then(setPaper, () => setPaper(null)); }, [strategyId]);
  useEffect(loadPaper, [loadPaper]);
  const paperRun = paper?.segments.find((x) => !x.to);
  const paperAct = (path: string, body: object, msg: string) => void studio("POST", `/strategies/${strategyId}${path}`, body).then(() => { toast.success(msg); loadPaper(); }, (e: Error) => toast.error(e.message));
  // ?debug=YYYY-MM-DD (from Live): open with the debugger paused on that paper day.
  useEffect(() => { const d = new URLSearchParams(window.location.search).get("debug"); if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) { setPanelOpen(true); setTab("debug"); debug({ date: d }); } }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [savedTick, setSavedTick] = useState(0); // terminal tasks added with --on-save run on each tick
  const [termSplit, setTermSplit] = useState(false);
  // Views moved from the bottom panel to the side bar (drag a panel tab onto the side bar; drag it back or use Move to panel).
  const [moved, setMoved] = useState<Tab[]>(() => { try { return JSON.parse(localStorage.getItem("studio:dev:moved") ?? "[]"); } catch { return []; } });
  useEffect(() => { try { localStorage.setItem("studio:dev:moved", JSON.stringify(moved)); } catch { /* blocked */ } }, [moved]);
  const [sideTab, setSideTab] = useState<Tab | null>(null);
  const movedTab = (t: Tab) => moved.includes(t);
  const toSide = (t: Tab) => { setMoved((m) => (m.includes(t) ? m : [...m, t])); setSideTab(t); setRailOpen(true); };
  const toPanel = (t: Tab) => { setMoved((m) => m.filter((x) => x !== t)); if (sideTab === t) setSideTab(null); setPanelOpen(true); setTab(t); };
  const [termCmd, setTermCmd] = useState({ cmd: "", n: 0 }); // "Run selection in Console" sends code here
  // Run selection on a date range: the selected code runs with load() cut to the range; its output opens in a Selection tab.
  const [selOut, setSelOut] = useState<{ code: string; range: string; row: CellRow | null } | null>(null);
  const runSelection = () => {
    const code = selection.current.trim(); if (!code) return toast("Select some Python first");
    const dflt = [rc.settings.start, rc.settings.end].filter(Boolean).join(" ");
    const range = window.prompt("Date range: from to (YYYY-MM-DD YYYY-MM-DD, blank for all)", String(dflt)); if (range === null) return;
    const [from = "", to = ""] = range.trim().split(/\s+/);
    const ok = (d: string) => !d || /^\d{4}-\d{2}-\d{2}$/.test(d); if (!ok(from) || !ok(to)) return toast.error("Use YYYY-MM-DD");
    const prelude = `from studio.research import load as load_all, plot, sql\nimport numpy as np\nimport pandas as pd\n\n\ndef load(symbol=""):\n    return load_all(symbol).loc[${from ? `"${from}"` : "None"}:${to ? `"${to}"` : "None"}]`;
    setSelOut({ code, range: range.trim() || "all dates", row: null }); openView("selection");
    void studio<{ outputs: CellRow[] }>("POST", "/build/cells", { code: spec.code, files: { ...(spec.files ?? {}), "__selection__.py": `# %%\n${prelude}\n# %%\n${code}` }, file: "__selection__.py", upto: 1, only: true, symbols: [symbol] })
      .then((r) => setSelOut((x) => x && { ...x, row: r.outputs.at(-1) ?? null }), (e: Error) => setSelOut((x) => x && { ...x, row: { index: null, stdout: "", value: null, error: e.message, error_line: null, seconds: 0 } }));
  };
  // Blame: walk saved versions newest to oldest while this line's text is still in the file; the last one is where it came from.
  const blame = (line: number) => {
    const text = (files[active] ?? "").split("\n")[line - 1]?.trim();
    if (!strategyId || !text) return toast(strategyId ? "Empty line" : "Save a version first");
    const vs = [...versions].sort((a, b) => b.version - a.version).slice(0, 30);
    void (async () => {
      let from: Version | null = null;
      for (const v of vs) {
        const r = await studio<{ files: Record<string, string> }>("GET", `/strategies/${strategyId}/files?version=${v.version}`).catch(() => null);
        if (!r || !(r.files[active] ?? "").split("\n").some((x) => x.trim() === text)) break;
        from = v;
      }
      toast(from ? `Line ${line} unchanged since v${from.version} · ${new Date(from.created * 1000).toLocaleDateString()} · ${from.actor}` : `Line ${line} is new in the draft`, { duration: 6000 });
    })();
  };
  const saveAndRun = () => { onSave(); setSavedTick((n) => n + 1); if (rc.runOnSave && !readOnly) runCode("quick"); };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === "\\" || e.key === "|")) { e.preventDefault(); setLayoutsOpen(true); return; }
      // Hide all tool windows (JetBrains Cmd+Shift+F12): outside the editor here, inside it through the action below.
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "F12" && !(e.target instanceof Element && e.target.closest(".monaco-editor"))) { e.preventDefault(); setZen((z) => !z); return; }
      if (e.defaultPrevented || e.repeat || e.key !== "Enter" || !(e.metaKey || e.ctrlKey) || (e.target instanceof Element && e.target.closest(".monaco-editor"))) return;
      e.preventDefault();
      runCode(e.shiftKey ? "full" : "quick");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const openPreview = () => {
    setTab("preview");
    setPanelOpen(true);
    if (view !== "code") setReportSide(true);
  };
  const revealRail = (next: Rail) => {
    setView("code");
    setIconsOpen(true);
    setRail(next); setSideTab(null);
    setRailOpen(true);
  };
  const actions: EditorAction[] = [
    { id: "studio.debug", label: "Debug: start", keys: (m) => [m.KeyCode.F5], run: () => startDebug() },
    { id: "studio.bp", label: "Debug: toggle breakpoint", keys: (m) => [m.KeyCode.F9], run: (line) => toggleBp(line) },
    { id: "studio.logpoint", label: "Debug: add or edit logpoint", keys: (m) => [m.KeyMod.Shift | m.KeyCode.F9], run: (line) => editLogpoint(line) },
    { id: "studio.step", label: "Debug: step one bar", keys: (m) => [m.KeyCode.F10], run: () => debug({ step: 1 }) },
    { id: "studio.stepline", label: "Debug: step line", keys: (m) => [m.KeyCode.F11], run: (l) => stepLine(l) },
    { id: "studio.stepback", label: "Debug: step back one bar", keys: (m) => [m.KeyMod.Shift | m.KeyCode.F10], run: () => debug({ step: -1 }) },
    { id: "studio.layouts", label: "View: customise layouts", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.Backslash], run: () => setLayoutsOpen(true) },
    { id: "studio.chartfirst", label: "View: chart first", run: () => ws.flipChartFirst() },
    { id: "studio.popchart", label: "View: pop out chart", run: () => window.open(`${window.location.pathname}?popout=chart`, "atlas-chart", "popup,width=1200,height=760") },
    { id: "studio.panel", label: "View: toggle panel", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyJ], run: () => setPanelOpen((o) => !o) },
    { id: "studio.rail", label: "View: toggle side bar", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyB], run: () => { if (railOpen) setRailOpen(false); else revealRail(rail); } },
    { id: "studio.files", label: "Go to file", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyP], run: () => revealRail("files") },
    { id: "studio.search", label: "Search project", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.KeyF], run: () => revealRail("search") },
    { id: "studio.docs", label: "Docs: open reference", keys: (m) => [m.KeyCode.F1], run: () => revealRail("docs") },
    { id: "studio.fullrun", label: "Run: full backtest (recorded)", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.Enter], run: () => runCode("full") },
    { id: "studio.quickrun", label: "Run: quick (top 50, 5 years)", run: () => runCode() },
    { id: "studio.runconfigs", label: "Run: edit configurations", run: () => setRcOpen(true) },
    { id: "studio.cell", label: "Cells: run cell", keys: (m) => [m.KeyMod.WinCtrl | m.KeyCode.Enter], run: (line) => runCell(line) },
    { id: "studio.cellabove", label: "Cells: run above and this cell", keys: (m) => [m.KeyMod.WinCtrl | m.KeyMod.Shift | m.KeyCode.Enter], run: (line) => runCell(line, false) },
    { id: "studio.tests", label: "Test: run all", run: () => { revealRail("tests"); runTests(); } },
    { id: "studio.testcursor", label: "Test: run at cursor", run: (line) => runTestAtCursor(line) },
    ...recentStrats.map((r) => ({ id: `studio.recent.${r.id}`, label: `Open recent: ${r.name}`, run: () => window.location.assign(`/studio/build/${r.id}?ui=dev`) })),
    { id: "studio.blame", label: "Blame: when did this line change", run: (line) => blame(line) },
    { id: "studio.runsel", label: "Run selection in Console", keys: (m) => [m.KeyMod.Shift | m.KeyMod.Alt | m.KeyCode.KeyE], run: () => { const t = selection.current.trim(); if (!t) return toast("Select some Python first"); setPanelOpen(true); setTab("console"); setTermCmd((c) => ({ cmd: t, n: c.n + 1 })); } },
    { id: "studio.runselrange", label: "Run selection on a date range", keys: (m) => [m.KeyMod.Shift | m.KeyMod.Alt | m.KeyCode.KeyR], run: () => runSelection() },
    { id: "studio.coverage", label: "Test: toggle coverage gutter", run: () => { onCoverage?.(!coverage); onPreview(); } },
    { id: "studio.cancel", label: "Run: cancel", run: () => onCancel?.() },
    { id: "studio.chart", label: "View: chart with replay", run: () => setOpenP("chart", true) },
    { id: "studio.results", label: "View: results", run: () => openView("results") },
    { id: "studio.tearsheet", label: "View: tearsheet", run: () => openView("tearsheet") },
    { id: "studio.runs", label: "View: compare runs", run: () => openView("runs") },
    { id: "studio.robust", label: "Run: robustness (Monte Carlo)", run: () => openView("robust") },
    { id: "studio.profile", label: "Run: profile the preview", run: () => runProfile() },
    { id: "studio.save", label: "Strategy: save version", run: () => saveAndRun() },
    { id: "studio.rerun", label: "Run: rerun last", run: () => rerunLast() },
    { id: "studio.runonsave", label: `Run: run on save ${rc.runOnSave ? "(on)" : "(off)"}`, run: () => rc.setRunOnSave(!rc.runOnSave) },
    { id: "studio.newfile", label: "File: new", run: () => addFile() },
    { id: "studio.newscratch", label: "File: new scratch file", run: () => addScratch() },
    { id: "studio.bm", label: "Bookmark: toggle", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Alt | m.KeyCode.KeyK], run: (line) => toggleBm(line) },
    { id: "studio.bmnext", label: "Bookmark: next", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Alt | m.KeyCode.Period], run: (line) => bmJump(1, line) },
    { id: "studio.bmprev", label: "Bookmark: previous", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Alt | m.KeyCode.Comma], run: (line) => bmJump(-1, line) },
    ...[1, 2, 3, 4, 5, 6, 7, 8, 9].flatMap((n): EditorAction[] => [
      { id: `studio.nbm${n}`, label: `Bookmark ${n}: set`, keys: (m) => [m.KeyMod.WinCtrl | m.KeyMod.Shift | (m.KeyCode.Digit0 + n)], run: (line) => setNumbered(n, line) },
      { id: `studio.nbmgo${n}`, label: `Bookmark ${n}: go`, keys: (m) => [m.KeyMod.WinCtrl | (m.KeyCode.Digit0 + n)], run: () => goNumbered(n) }]),
    { id: "studio.maxchart", label: "View: maximise chart", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.Enter], run: () => { setZen(false); if (!chartOpen) setOpenP("chart", true); setMaxChart((x) => !x); } },
    { id: "studio.zen", label: "View: zen mode", keys: (m) => [m.KeyMod.chord(m.KeyMod.CtrlCmd | m.KeyCode.KeyK, m.KeyMod.CtrlCmd | m.KeyCode.KeyZ)], run: () => setZen((z) => !z) },
    { id: "studio.hidetools", label: "View: hide all tool windows", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.F12], run: () => setZen((z) => !z) },
    { id: "studio.split", label: "View: split editor", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.Backslash], run: () => setSplit((x) => (x ? null : Object.keys(files).find((f) => f !== active) ?? active)) },
    { id: "studio.snippet", label: "Snippet: save selection", run: () => saveSnippet() },
    { id: "studio.back", label: "Go: back", keys: (m) => [m.KeyMod.WinCtrl | m.KeyCode.Minus], run: () => hop(-1) },
    { id: "studio.fwd", label: "Go: forward", keys: (m) => [m.KeyMod.WinCtrl | m.KeyMod.Shift | m.KeyCode.Minus], run: () => hop(1) },
    { id: "studio.symproj", label: "Go to symbol in project", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyCode.KeyT], run: () => window.dispatchEvent(new CustomEvent("studio:palette", { detail: "Symbol " })) },
    { id: "studio.outline", label: "Go to symbol in file", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.KeyO], run: () => window.dispatchEvent(new CustomEvent("studio:palette", { detail: "Outline " })) },
    { id: "studio.inspect", label: "Inspect: whole project", run: () => void inspectProject() },
    { id: "studio.snippets", label: "Snippet: insert", keys: (m) => [m.KeyMod.CtrlCmd | m.KeyMod.Shift | m.KeyCode.KeyS], run: () => revealRail("templates") },
  ];
  actionsRef.current = actions;
  debugRef.current = debug;
  // Breadcrumbs: at each depth the last symbol that starts at or above the cursor (the outline has no end lines).
  const crumbs: Sym[] = [];
  for (let level = outline; ;) { const s0 = level.filter((x) => x.line <= cursor.line).at(-1); if (!s0) break; crumbs.push(s0); level = s0.children; }
  const outlineRows = (items: Sym[], depth = 0): ReactNode => items.map((s) => (
    <div key={`${s.name}${s.line}`}>
      <button className="dv-item" style={{ paddingLeft: 10 + depth * 14 }} onClick={() => goto(active, s.line, s.column)}><i className={`dv-k dv-k-${s.kind}`}>{s.kind[0]}</i>{s.name}<span>{s.line}</span></button>
      {outlineRows(s.children, depth + 1)}
    </div>
  ));
  const todos = useMemo(() => Object.entries(files).filter(([f]) => !(f in scratch)).flatMap(([f, text]) => text.split("\n").flatMap((line, i) => /#.*\b(TODO|FIXME|XXX)\b/.test(line) ? [{ file: f, line: i + 1, text: line.trim().replace(/^#\s*/, "") }] : [])), [files, scratch]);
  const docRows = (docs ?? []).filter((d) => !docQ || `${d.scope}.${d.name} ${d.documentation ?? ""}`.toLowerCase().includes(docQ.toLowerCase()));
  const termHost: TerminalHost = { inject: termCmd, files, code: spec.code, extra: spec.files ?? {}, active, symbol, storeKey: strategyId ?? "draft", spec, paused: dbg ? { symbol: dbg.symbol ?? symbol, date: dbg.date } : null, preview: onPreview, goto, saved: savedTick, atDate: (d: string) => { setTab("debug"); debug({ date: d }); },
                  run: (level, settings) => { if (!canRun || starting || running) throw new Error("A run is already going or runs are off here"); const s = { ...rc.settings, ...settings }; openView("results"); lastRun.current = { level, settings: s }; onQuickRun(level, s); },
                  plots: (p) => <CellPlots plots={p as CellPlot[]} />,
                  render: (v) => (tableOf(v) ? <VarGrid t={tableOf(v)!} open /> : typeof v === "object" ? <KV rows={v as Record<string, unknown>} /> : <pre>{show(v)}</pre>) };
  const TABS: [Tab, string, number | null][] = [["tester", "Tester", null], ["problems", "Problems", problems.length], ["output", "Output", prev?.logs?.length ?? null], ["plots", "Plots", plots.length + Object.keys(prev?.tables ?? {}).length || null], ["trades", "Trades", prev?.trades.length ?? null], ["debug", "Debug", null], ["console", "Console", null], ...(hasCells || cellOut ? [["cells", "Cells", null] as [Tab, string, null]] : []), ["preview", "Preview", null]];
  const toggles = <span className="dv-toggles">
    <button className="icon-btn" aria-pressed={opt.caseSensitive} title="Match case" onClick={() => setOpt((o) => ({ ...o, caseSensitive: !o.caseSensitive }))}><CaseSensitive size={14} /></button>
    <button className="icon-btn" aria-pressed={opt.word} title="Whole word" onClick={() => setOpt((o) => ({ ...o, word: !o.word }))}><WholeWord size={14} /></button>
    <button className="icon-btn" aria-pressed={opt.regex} title="Regular expression" onClick={() => setOpt((o) => ({ ...o, regex: !o.regex }))}><Regex size={14} /></button>
  </span>;
  const priceRows = panelOpen && tab === "plots" ? (prev?.bars ?? []).map((b) => ({ date: b.date, close: b.close, ...Object.fromEntries(plots.filter(([n]) => prev?.plot_charts?.[n] === "main" && plotsOn[n] !== false).map(([n, pts]) => [n, pts.find((p) => p.date === b.date)?.value ?? null])) })) : [];
  const mainPlots = plots.filter(([n]) => prev?.plot_charts?.[n] === "main");

  const resultsView = view === "results" ? (() => {
                const r = version ? runs[version] : undefined;
                const m = quick?.result?.meta;
                return (
                  <div className="dv-results">
                    <div className="dv-dbar">
                      <button className="btn sm" disabled={!canRun || starting || running} onClick={() => runCode("full")}>Full backtest<kbd>⌘⇧↵</kbd></button>
                      <button className="btn sm" onClick={runProfile}>Profile</button>
                      {running ? <button className="btn sm" onClick={onCancel}>Cancel<kbd>Esc</kbd></button> : null}
                      {quick ? <span className="dv-count">{rc.cur.name !== "Default" ? `${rc.cur.name}, ${quick.level === "quick" ? "not in the ledger" : "recorded in the ledger"}` : quick.level === "quick" ? "Top 50 names, 5 years, not in the ledger" : "Full period, recorded in the ledger"}</span> : null}
                    </div>
                    {running ? <div className="dv-prog"><i style={{ width: `${quick!.progress?.percent ?? 2}%` }} /><span>{quick!.progress?.message ?? "Queued"}</span></div> : null}
                    {quick?.status === "failed" ? <p className="bd-find error"><b>Failed</b>{quick.error}</p> : null}
                    {quick?.status === "cancelled" ? <p className="dv-empty">Cancelled</p> : null}
                    {!quick && !r && !starting && !profile ? <p className="dv-empty">Run a backtest to see results.</p> : null}
                    {m ? <>
                      <RunSummary quick={quick!} />
                      <span className="dv-dbar">{quick?.job_id ? <><Link className="btn sm" href={`/studio/report/${quick.job_id}`}>Open report</Link><button className="btn sm ghost" title="Open the report in its own window" onClick={() => window.open(`/studio/report/${quick.job_id}`, "atlas-report", "popup,width=1180,height=820")}>Pop out</button></> : null}{quick?.level === "full" ? <Link className="btn sm" href="/studio/backtest">Open in Backtest</Link> : null}</span>
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
                      {profile.stacks?.length ? <div style={{ gridColumn: "1 / -1" }}><h4>Flame graph</h4><Flame stacks={profile.stacks} /></div> : null}
                      <div><h4>Time per function</h4>{profile.functions?.length ? <DataTable rows={profile.functions.map((f) => ({ function: f.function ?? f.name ?? "", seconds: f.seconds, calls: f.calls ?? null }))} /> : <p className="dv-empty">No data</p>}</div>
                    </div> : null}
                  </div>
                );
              })() : null;

  const focus = !iconsOpen && !railOpen && !panelOpen;
  // One Layout menu (JetBrains: header widgets hide actions in drop-downs): workspace, views, panels, focus.
  const bar = <>
    <WorkspaceMenu ws={ws} onCustomise={() => setLayoutsOpen(true)}>
      <div className="hd">Open</div>
      <button role="menuitem" onClick={() => openView("results")}>Results</button>
      <button role="menuitem" onClick={() => openView("tearsheet")}>Tearsheet</button>
      <button role="menuitem" onClick={() => openView("robust")}>Robustness</button>
      <button role="menuitem" onClick={() => openView("runs")}>Compare runs</button>
      <button role="menuitem" onClick={openPreview}>Preview</button>
      <hr />
      <div className="hd">Show</div>
      {view !== "code" ? <button role="menuitemcheckbox" aria-checked={reportSide} onClick={() => setReportSide((visible) => !visible)}>Chart and bottom panel</button> : null}
      <button role="menuitemcheckbox" aria-checked={chartOpen} onClick={() => { if (view !== "code") setReportSide(true); if (!chartOpen && open_.chart) setRailOpen(false); else setOpenP("chart", !chartOpen); }}>Chart</button>
      <button role="menuitemcheckbox" aria-checked={panelOpen} onClick={() => { setPanelOpen(!panelOpen); if (view !== "code") setReportSide(!panelOpen); }}>Bottom panel</button>
      <button role="menuitemradio" aria-checked={!full && !pside} onClick={() => ws.patch((l) => ({ ...l, dock: { ...l.dock, panel: "center" } }))}>Panel under editor</button>
      <button role="menuitemradio" aria-checked={pside === "left"} onClick={() => ws.patch((l) => ({ ...l, dock: { ...l.dock, panel: "left" } }))}>Panel left of editor</button>
      <button role="menuitemradio" aria-checked={pside === "right"} onClick={() => ws.patch((l) => ({ ...l, dock: { ...l.dock, panel: "right" } }))}>Panel right of editor</button>
      <button role="menuitemradio" aria-checked={full} onClick={() => ws.patch((l) => ({ ...l, dock: { ...l.dock, panel: "full" } }))}>Panel full width</button>
      <button role="menuitemcheckbox" aria-checked={!!split} onClick={() => setSplit((x) => (x ? null : Object.keys(files).find((f) => f !== active) ?? active))}>Split editor</button>
      <button role="menuitemcheckbox" aria-checked={iconsOpen} onClick={() => setIconsOpen((o) => !o)}>Tool strip</button>
      {view === "code" ? <button role="menuitemcheckbox" aria-checked={pinned.includes(active)} onClick={() => {
        keep(active);
        setPinned((current) => current.includes(active) ? current.filter((file) => file !== active) : [...current, active]);
      }}>Pin active file</button> : null}
      <hr />
      <button role="menuitemcheckbox" aria-checked={chartFirst} onClick={ws.flipChartFirst}>Chart first</button>
      <button role="menuitemcheckbox" aria-checked={focus} onClick={() => { const on = !focus; setIconsOpen(!on); setRailOpen(!on); setPanelOpen(!on); }}>Focus mode</button>
    </WorkspaceMenu>
    <LayoutsDialog ws={ws} open={layoutsOpen} onClose={() => setLayoutsOpen(false)} />
    <RunConfigsDialog rc={rc} open={rcOpen} onClose={() => setRcOpen(false)} />
    {tools}
    <RunConfigPicker rc={rc} onEdit={() => setRcOpen(true)} />
    <button className="btn dv-execute" disabled={!canRun || starting || running} title={!canRun ? "Add strategy code or rules to run" : "Run backtest (⌘↵)"} onClick={() => runCode()}>
      <Play size={14} />{starting || running ? "Running…" : "Run"}
    </button>
    {running && view !== "results" ? <button className="btn" onClick={onCancel}>Cancel</button> : null}
  </>;

  // One renderer for a bottom-panel view, so a view dragged to the side bar draws the same content there.
  const panelBody = (tab: Tab, inSide: boolean) => (
            <>
              {panelOpen && tab === "preview" ? side : null}
              {tab === "problems" ? <label className="dv-strict"><input type="checkbox" checked={strict} onChange={(e) => { setStrict(e.target.checked); try { localStorage.setItem("studio:dev:strict", e.target.checked ? "1" : "0"); } catch { /* blocked */ } }} />Strict</label> : null}
              {tab === "problems" ? <div className="seg dv-strict" role="group" aria-label="Scope">{(["file", "project"] as const).map((k) => <button key={k} type="button" aria-pressed={scope === k} onClick={() => (k === "project" && !report.length ? void inspectProject() : setScope(k))}>{k === "file" ? "Current file" : "Project"}</button>)}</div> : null}
              {tab === "problems" && scope === "project" ? (report.length ? Object.entries(Object.groupBy(report, (p) => p.file)).map(([f, list]) => (
                <div key={f}><h4 className="dv-sub">{f} · {list!.length}</h4>
                  {Object.entries(Object.groupBy(list!, (p) => p.code || "other")).map(([c, group]) => group!.map((p, i) => (
                    <button key={`${c}${i}`} className="dv-prob" onClick={() => { setScope("file"); goto(p.file, p.line, p.column); }}><b className={p.severity}>{p.severity}</b><span>{p.message}</span><i>{p.line}:{p.column} {c}</i></button>
                  )))}
                </div>
              )) : <p className="dv-empty">No problems</p>) : null}
              {tab === "problems" && scope === "file" ? (problems.length ? <>
                {problems.map((p, i) => (
                  <button key={i} className="dv-prob" title={lint.includes(p) ? "Right-click to set severity" : undefined} onContextMenu={(e) => { if (lint.includes(p) && p.code) { e.preventDefault(); setSeverity(p.code); } }} onClick={() => goto(p.file, p.line, p.column)}><b className={p.severity}>{p.severity}</b><span>{p.message}</span><i>{p.file}:{p.line}:{p.column}{p.code ? ` ${p.code}` : ""}</i></button>
                ))}
                {prev?.locals ? <div className="dv-trace"><h4 className="dv-sub">At the failing bar</h4><KV rows={prev.locals} /></div> : null}
                {prev?.problem?.traceback?.length ? <div className="dv-trace">{prev.problem.traceback.map((f, i) => <button key={i} className="dv-item" onClick={() => goto(f.file, f.line, f.column)}>{f.function}<span>{f.file}:{f.line}</span></button>)}</div> : null}
              </> : <p className="dv-empty">No problems</p>) : null}
              {tab === "output" ? (
                <>
                  <div className="dv-search dv-logbar">
                    <input className="input" placeholder="Filter" aria-label="Filter output" value={logQ} onChange={(e) => setLogQ(e.target.value)} />{toggles}
                    <div className="seg" role="group" aria-label="Level">{["all", "info", "warning", "error"].map((l) => <button key={l} type="button" aria-pressed={logLevel === l} onClick={() => setLogLevel(l)}>{l}</button>)}</div>
                    {(() => { const syms = [...new Set((srcLogs ?? []).map((l) => l.symbol).filter(Boolean))] as string[]; return syms.length > 1 ? <select className="input" aria-label="Symbol" style={{ width: "auto" }} value={logSym} onChange={(e) => setLogSym(e.target.value)}><option value="">All symbols</option>{syms.map((x) => <option key={x}>{x}</option>)}</select> : null; })()}
                    <input className="input" type="date" aria-label="From date" style={{ width: "auto" }} value={logFrom} onChange={(e) => setLogFrom(e.target.value)} />
                    <button className="btn sm ghost" disabled={!logs.length} onClick={() => { const q = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`; const csv = ["level,date,symbol,line,message", ...logs.map((l) => [l.level, l.date, l.symbol, l.line, l.text].map(q).join(","))].join("\n"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); a.download = "output.csv"; a.click(); URL.revokeObjectURL(a.href); }}>CSV</button>
                    <select className="input" aria-label="Output source" style={{ width: "auto" }} value={outSrc} onChange={(e) => setOutSrc(Number(e.target.value))}><option value={0}>Preview</option>{pinnedOut.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select>
                    <button className="icon-btn" aria-label="Pin output" title="Keep this preview's output in its own tab" disabled={!prev?.logs?.length || !!outSrc} onClick={() => { const id = Date.now(); setPinnedOut((x) => [...x.slice(-9), { id, label: `Pinned ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`, logs: prev!.logs! }]); setOutSrc(id); }}><Pin size={13} /></button>
                    {outSrc ? <button className="icon-btn" aria-label="Unpin output" title="Remove this pinned output" onClick={() => { setPinnedOut((x) => x.filter((p) => p.id !== outSrc)); setOutSrc(0); }}><X size={13} /></button> : null}
                    <button className="icon-btn" aria-label="Soft wrap" title="Soft wrap" aria-pressed={logWrap} onClick={() => setLogWrap((w) => !w)}><WrapText size={13} /></button>
                    <button className="icon-btn" aria-label="Scroll to end" title="Scroll to end" onClick={(e) => { const b = e.currentTarget.closest(".dv-pbody"); b?.scrollTo({ top: b.scrollHeight }); }}><ArrowDownToLine size={13} /></button>
                    <button className="icon-btn" aria-label="Clear output" title="Clear until the next preview" disabled={!srcLogs?.length} onClick={() => setLogCleared(srcLogs ?? null)}><Eraser size={13} /></button>
                    <span className="dv-count">{logs.length.toLocaleString()} of {(srcLogs?.length ?? 0).toLocaleString()}</span>
                  </div>
                  {logs.length ? (() => {
                    // Virtual list: only the rows in view (plus a margin) are in the page, so 5,000 lines scroll smoothly (B-79).
                    // Soft wrap gives rows their own height, so it renders the last 2,000 lines without the virtual list.
                    if (logWrap) return <div className="dv-logs-wrap">{logs.slice(-2000).map((l, i) => (
                      <button key={i} className="dv-log" data-level={l.level} onClick={() => { goto("main.py", l.line); onPause?.(l.date); }}><time>{l.date}</time><span>{l.symbol ?? ""}</span>
                        <code>{l.text}{l.fields ? <em>{Object.entries(l.fields).map(([k, v]) => ` ${k}=${show(v)}`).join("")}</em> : null}</code><i>:{l.line}</i></button>))}</div>;
                    const ROW = 24, first = Math.max(0, Math.floor(logTop / ROW) - 20), rows = logs.slice(first, first + 80);
                    return <div className="dv-logs" style={{ height: logs.length * ROW }}>
                      {rows.map((l, i) => (
                        <button key={first + i} className="dv-log" data-level={l.level} style={{ top: (first + i) * ROW }} onClick={() => { goto("main.py", l.line); onPause?.(l.date); }}><time>{l.date}</time><span>{l.symbol ?? ""}</span>
                          <code>{l.text}{l.fields ? <em>{Object.entries(l.fields).map(([k, v]) => ` ${k}=${show(v)}`).join("")}</em> : null}</code><i>:{l.line}</i></button>
                      ))}</div>;
                  })() : <p className="dv-empty">{srcLogs?.length ? "Nothing matches" : "No output"}</p>}
                </>
              ) : null}
              {tab === "plots" ? (
                <div className="dv-plotlist">
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
              {tab === "tester" ? <Tester trades={prev?.trades ?? []} inputs={inputList} /> : null}
              {tab === "trades" ? (prev?.trades.length ? <DataTable rows={prev.trades} opts={{ viewKey: "studio:dev:trades", rowActions: (r: Record<string, unknown>) => {
                const d = String(r.entry_date ?? "").slice(0, 10), o = d ? prev.order_lines?.find((x) => x.dates.some((y) => y.slice(0, 10) === d)) : undefined;
                return o ? <button className="icon-btn" title={`Go to ${o.file}:${o.line}`} aria-label="Go to the line that placed this order" onClick={() => goto(o.file, o.line)}><FileCode2 size={12} /></button> : null;
              } }} /> : <p className="dv-empty">No trades in the preview</p>) : null}
              {tab === "cells" ? <label className="dv-strict"><input type="checkbox" checked={autoCells} onChange={(e) => setAutoCells(e.target.checked)} />Auto-run on edit</label> : null}
              {tab === "cells" ? (cellOut === "running" ? <p className="dv-empty">Running…</p> : !cellOut ? <p className="dv-empty">Ctrl+Enter runs the cell at the cursor</p> : (
                <div className="dv-cells">{cellOut.rows.map((r, i) => (
                  <section key={i}>
                    <h4><button className="dv-item" onClick={() => r.line && goto(cellOut.file, r.line)}>{r.index === null ? "Cells" : `Cell ${r.index + 1}${cellOut.titles[r.index] ? ` · ${cellOut.titles[r.index]}` : ""}`}</button><i>{r.seconds.toFixed(3)} s</i></h4>
                    {r.stdout ? <pre>{r.stdout}</pre> : null}
                    <CellPlots plots={r.plots} />
                    {r.error ? <p className="bd-find error"><b>{r.error_line ? <button className="dv-item" onClick={() => goto(cellOut.file, r.error_line!)}>line {r.error_line}</button> : "Error"}</b>{r.error}</p> : null}
                    {r.value !== null && r.value !== undefined ? (tableOf(r.value) ? <VarGrid t={tableOf(r.value)!} open /> : typeof r.value === "object" ? <KV rows={r.value as Record<string, unknown>} /> : <pre>{show(r.value)}</pre>) : null}
                  </section>
                ))}</div>
              )) : null}
              {/* Kept mounted while the panel is open so --on-save tasks run from any tab. */}
              {inSide === moved.includes("console") ? <div hidden={tab !== "console"} className={termSplit ? "dv-term-split" : "dv-term-host"}>
                <Terminal host={{ ...termHost, split: { on: termSplit, toggle: () => setTermSplit((x) => !x) } }} />
                {termSplit ? <Terminal host={{ ...termHost, storeKey: `${termHost.storeKey}:2`, saved: 0 }} /> : null}
              </div> : null}
              {tab === "debug" ? (
                <div className="dv-debug">
                  <div className="dv-dbar">
                    <input className="input" type="date" aria-label="Stop at date" value={dbgDate} onChange={(e) => setDbgDate(e.target.value)} />
                    <button className="btn sm primary" onClick={() => debug({ date: dbgDate })}><Bug size={13} />Stop here<kbd>F5</kbd></button>
                    <button className="btn sm" disabled={!dbg?.previous_date} onClick={() => debug({ step: -1 })}><StepBack size={13} />Bar</button>
                    <button className="btn sm" disabled={!dbg?.next_date} onClick={() => debug({ step: 1 })}><StepForward size={13} />Bar<kbd>F10</kbd></button>
                    <button className="btn sm" disabled={!dbg} onClick={() => stepLine()}><CornerDownRight size={13} />Line<kbd>F11</kbd></button>
                    <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "order" })}>Next order</button>
                    <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "fill" })}>Next fill</button>
                    <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "equity", loss_fraction: 0.05 })}>Next 5% loss day</button>
                    <span className="dv-sep" />
                    <input className="input" aria-label="Breakpoint condition" placeholder="condition" value={cond} onChange={(e) => setCond(e.target.value)} />
                    <input className="input" type="number" min={1} style={{ width: 64 }} aria-label="Stop on hit number" placeholder="hit #" value={hitN} onChange={(e) => setHitN(e.target.value)} />
                    <select className="input" aria-label="Only after breakpoint" value={trig} onChange={(e) => setTrig(e.target.value)}><option value="">Always on</option>{Object.entries(bps).flatMap(([f, ls]) => ls.map((l) => <option key={`${f}:${l}`} value={`${f}:${l}`}>After {f}:{l}</option>))}</select>
                    <button className="btn sm" onClick={() => debug({ breakpoint: { file: active, line: cursor.line, ...bpExtra() } })}>Break at {active}:{cursor.line}</button>
                    <span className="dv-sep" />
                    <input className="input" style={{ width: 120 }} aria-label="Break when this value changes" placeholder="self.position" value={dwatch} onChange={(e) => setDwatch(e.target.value.trim())} />
                    <button className="btn sm" disabled={!/^(self\.)?[A-Za-z_]\w*$/.test(dwatch)} onClick={() => debug({ breakpoint: { file: active, line: 1, watch: dwatch, hit: Number(hitN) > 0 ? Number(hitN) : null } })}>Break on change</button>
                  </div>
                  {dbg ? (
                    <div className="dv-dgrid">
                      <div><h4>{dbg.symbol} · {dbg.date} · bar {dbg.bar_index}{dbg.breakpoint ? ` · hit ${dbg.breakpoint.hit_count}` : ""}{dbg.breakpoint?.watch ? ` · ${dbg.breakpoint.watch.name}: ${JSON.stringify(dbg.breakpoint.watch.before)} → ${JSON.stringify(dbg.breakpoint.watch.after)}` : ""}{dbg.equity_change != null ? ` · ${pct(dbg.equity_change)}` : ""}</h4>
                        <KV rows={dbg.context} /></div>
                      <div><h4>{dbg.breakpoint ? "Locals and self" : "self"}</h4>
                        {Object.entries({ ...dbg.state, ...(dbg.breakpoint?.locals ?? {}) }).filter(([, v]) => Array.isArray(v) && v.length > 0 && typeof v[0] === "object" && v[0] !== null && "entry_date" in v[0]).map(([k]) => <button key={k} className="btn sm ghost" onClick={() => setTab("trades")}>{k}: open in Trades</button>)}
                        {Object.keys({ ...dbg.state, ...(dbg.breakpoint?.locals ?? {}) }).length ? <KV rows={{ ...dbg.state, ...(dbg.breakpoint?.locals ?? {}) }} /> : <p className="dv-empty">No attributes</p>}</div>
                      <div><h4>Watch</h4>
                        <form className="dv-dbar" onSubmit={(e) => { e.preventDefault(); if (!watchIn.trim()) return; const w = [...watches, watchIn.trim()]; setWatches(w); setWatchIn(""); try { localStorage.setItem("studio:watch", JSON.stringify(w)); } catch { /* private window */ } }}>
                          <input className="input" aria-label="Watch expression" placeholder="rsi(close, 14)" value={watchIn} onChange={(e) => setWatchIn(e.target.value)} />
                        </form>
                        {watchRows.map((r, i) => <div key={r.expression} className="dv-watch"><code>{r.expression}</code><b className={r.error && !(r.expression in (dbg.breakpoint?.locals ?? {})) ? "error" : undefined} title={r.error ?? r.history.map((h) => `${h.date}  ${h.value}`).join("\n")}>{r.error ? String((dbg.breakpoint?.locals ?? {})[r.expression] ?? r.error) : (typeof r.value === "number" ? +r.value.toFixed(4) : String(r.value))}</b>
                          <button className="icon-btn" aria-label="Remove watch" onClick={() => { const w = watches.filter((_, k) => k !== i); setWatches(w); try { localStorage.setItem("studio:watch", JSON.stringify(w)); } catch { /* private window */ } }}>×</button></div>)}</div>
                      <div><h4>Orders</h4>{dbg.orders.length ? <DataTable rows={dbg.orders} /> : <p className="dv-empty">None this bar</p>}
                        <h4>Fills</h4>{dbg.fills.length ? <DataTable rows={dbg.fills} /> : <p className="dv-empty">None this bar</p>}</div>
                    </div>
                  ) : <p className="dv-empty">Stops at the last preview trade, or the date set</p>}
                </div>
              ) : null}
            </>
  );
  const railPanel = (
      <Panel id="rail" minSize={0} maxSize={sideTab ? "520px" : "210px"}>
        <nav className="dv-rail" inert={!railOpen} aria-hidden={!railOpen} aria-label={sideTab ? TABS.find(([k]) => k === sideTab)?.[1] : RAILS.find((r) => r[0] === rail)?.[2]}
          onDragOver={(e) => { if (e.dataTransfer.types.includes("text/x-studio-view")) e.preventDefault(); }} onDrop={(e) => { const t = e.dataTransfer.getData("text/x-studio-view") as Tab; if (t) { e.preventDefault(); toSide(t); } }}>
          {sideTab ? <>
            <h4><span className="dv-rail-tabs" role="tablist">{moved.map((k) => <button key={k} role="tab" aria-selected={sideTab === k} draggable onDragStart={(e) => e.dataTransfer.setData("text/x-studio-view", k)} onClick={() => setSideTab(k)}>{TABS.find(([x]) => x === k)?.[1] ?? k}</button>)}</span>
              <button className="icon-btn" aria-label="Move to panel" title="Move back to the bottom panel" onClick={() => toPanel(sideTab)}><Minimize2 size={12} /></button>
              <button className="icon-btn" aria-label="Close side bar" onClick={() => setRailOpen(false)}><X size={13} /></button></h4>
            <div className="dv-side-view">{panelBody(sideTab, true)}</div>
          </> : <>
          <h4>{rail === "files" || rail === "outline" ? (
            <span className="dv-rail-tabs" role="tablist">{(["files", "outline"] as const).map((k) => <button key={k} role="tab" aria-selected={rail === k} onClick={() => revealRail(k)}>{k === "files" ? "Files" : "Outline"}</button>)}</span>
          ) : RAILS.find((r) => r[0] === rail)?.[2]}<button className="icon-btn" aria-label="Close side bar" title="Close side bar (⌘B)" onClick={() => setRailOpen(false)}><X size={13} /></button></h4>
          {rail === "files" ? (
            <div className="dv-list dv-explorer">
              <details open><summary>Files</summary>
              {Object.keys(files).filter((f) => !(f in scratch)).map((f) => (
                <div key={f} className="dv-file dv-source-file" data-on={f === active || undefined}>
                  <button className="dv-item" onClick={() => peek(f)} onDoubleClick={() => { goto(f, 1); keep(f); }}><FileCode2 size={13} />{f}</button>
                  <span className="dv-file-actions"><button className="icon-btn" title="Duplicate" aria-label={`Duplicate ${f}`} onClick={() => dupFile(f)}><FilePlus2 size={12} /></button>
                  {f !== "main.py" ? <><button className="icon-btn" title="Rename" aria-label={`Rename ${f}`} onClick={() => renameFile(f)}><Pencil size={12} /></button><button className="icon-btn" title="Delete" aria-label={`Delete ${f}`} onClick={() => dropFile(f)}><Trash2 size={12} /></button></> : null}</span>
                </div>
              ))}
              <button className="btn sm ghost" onClick={addFile}><FilePlus2 size={13} />New file</button>
              </details>
              <details open><summary>Scratch</summary>
              {Object.keys(scratch).map((f) => (
                <div key={f} className="dv-file dv-source-file" data-on={f === active || undefined}>
                  <button className="dv-item" onClick={() => peek(f)}><FileCode2 size={13} />{f}</button>
                  <span className="dv-file-actions"><button className="icon-btn" title="Delete" aria-label={`Delete ${f}`} onClick={() => dropScratch(f)}><Trash2 size={12} /></button></span>
                </div>
              ))}
              <button className="btn sm ghost" onClick={addScratch}><FilePlus2 size={13} />New scratch file</button>
              </details>
              <details open><summary>Inputs<span>{Object.keys(inputs).length}</span></summary>
                {inputList}
              </details>
            </div>
          ) : rail === "outline" ? (
            <div className="dv-list">{outline.length ? outlineRows(outline) : <p className="dv-empty">No classes or functions</p>}
              <h4 className="dv-sub">TODO</h4>
              {todos.length ? todos.map((t) => <button key={`${t.file}:${t.line}`} className="dv-item" onClick={() => goto(t.file, t.line)}>{t.text}<span>{t.file}:{t.line}</span></button>) : <p className="dv-empty">No TODO, FIXME or XXX comments</p>}
            </div>
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
                  <button className="dv-tpl" onClick={(e) => (e.shiftKey && diff && diff.version !== v.version ? openDiff(diff.version, v.version) : diff?.version === v.version ? setDiff(null) : openDiff(v.version))} title="Shift-click another version to compare it with the open one">
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
              <div className="shelf-head"><h4 className="dv-sub">Shelf</h4><button className="btn sm ghost" disabled={!timeline.length} onClick={shelveChanges}>Shelve changes</button></div>
              {shelf.map((s) => <div key={s.at} className="dv-file shelf-row"><span className="dv-item" title={`${s.name} · ${new Date(s.at).toLocaleString()}`}>{s.name}<span>{Object.keys(s.files).length} files</span></span>
                <button className="btn sm ghost" onClick={() => unshelve(s)}>Unshelve</button>
                <button className="icon-btn" aria-label={`Delete shelf ${s.name}`} onClick={() => dropShelf(s)}><Trash2 size={12} /></button></div>)}
            </div>
          ) : rail === "tests" ? (
            <div className="dv-list">
              {testFiles.length ? <span className="dv-dbar">
                <button className="btn sm" disabled={testing} onClick={() => runTests()}><Play size={12} />{testing ? "Running…" : "Run all"}</button>
                <button className="btn sm ghost" disabled={testing || !tests.some((t) => t.status !== "passed")} onClick={() => runTests(tests.filter((t) => t.status !== "passed"))}><RotateCcw size={12} />Failed</button>
                {tests.length ? <span className="dv-count">{tests.filter((t) => t.status === "passed").length}/{tests.length}</span> : null}
              </span> : <button className="btn sm ghost" onClick={() => { const n = "test_main.py" in files ? `test_${Date.now().toString(36)}.py` : "test_main.py"; edit({ files: { ...(spec.files ?? {}), [n]: TEST_FILE } }); goto(n, 4); }}><FilePlus2 size={13} />New test file</button>}
              {testFiles.map((f) => (
                <div key={f} className="dv-tests">
                  <div className="dv-file"><button className="dv-item" onClick={() => goto(f, 1)}><FileCode2 size={12} />{f}</button><button className="icon-btn" aria-label={`Run ${f}`} disabled={testing} onClick={() => runTestFile(f)}><Play size={11} /></button></div>
                  {tests.filter((t) => t.file === f).map((t) => (
                    <div key={t.name} className="dv-file">
                      <button className="dv-item" data-st={t.status} title={t.message ?? `${t.seconds.toFixed(3)} s`} onClick={() => goto(f, t.error_line ?? t.line)}>
                        <i aria-label={t.status} />{t.name}{t.message ? <span>{t.message}</span> : null}</button>
                      <button className="icon-btn" aria-label={`Run ${t.name}`} disabled={testing} onClick={() => runTests([t])}><Play size={11} /></button>
                    </div>
                  ))}
                </div>
              ))}
              <h4 className="dv-sub">Snapshot</h4>
              {snap ? <div className="dv-tests"><div className="dv-file"><span className="dv-item" data-st={!nowSnap || stale ? undefined : snapSame ? "passed" : "failed"}><i aria-hidden />{!nowSnap || stale ? "Preview is out of date" : snapSame ? "Results unchanged" : `Changed: return ${pct(snap.total_return)} → ${pct(nowSnap.total_return)}, trades ${snap.trades} → ${nowSnap.trades}${snap.orders !== nowSnap.orders ? ", orders differ" : ""}`}</span>
                <button className="icon-btn" aria-label="Clear snapshot" onClick={() => pinSnap(null)}><X size={11} /></button></div></div> : null}
              <button className="btn sm ghost" disabled={!nowSnap} onClick={() => { pinSnap(nowSnap); toast("Results pinned"); }}>{snap ? "Pin these results instead" : "Pin current results"}</button>
              <label className="dv-strict"><input type="checkbox" checked={coverage} onChange={(e) => { onCoverage?.(e.target.checked); onPreview(); }} />Coverage gutter</label>
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
              {(() => { const all = [...new Set(snippets.flatMap((sn) => sn.tags ?? []))].sort(); return all.length ? <div className="dv-chips">{all.map((t) => <button key={t} className="pill" aria-pressed={snipTag === t} onClick={() => setSnipTag((x) => (x === t ? null : t))}>{t}</button>)}</div> : null; })()}
              {snippets.filter((sn) => !snipTag || sn.tags?.includes(snipTag)).map((sn) => (
                <div key={sn.id} className="dv-file">
                  <button className="dv-item" title={sn.body} onClick={() => insertAt.current?.(sn.body)}><code>{sn.prefix}</code>{sn.name}</button>
                  <button className="icon-btn" title="Try in Console" aria-label={`Try ${sn.name} in Console`} onClick={() => { setPanelOpen(true); setTab("console"); setTermCmd((c) => ({ cmd: sn.body, n: c.n + 1 })); }}><Play size={12} /></button>
                  <button className="icon-btn" aria-label={`Delete ${sn.name}`} onClick={() => void studio("DELETE", `/snippets/${sn.id}`).then(() => setSnippets((x) => x.filter((y) => y.id !== sn.id)))}><Trash2 size={12} /></button>
                </div>
              ))}
              <button className="btn sm ghost" onClick={saveSnippet}><FilePlus2 size={13} />Save selection as snippet</button>
              <h4 className="dv-sub">Artefacts</h4>
              {artefacts.map((a) => (
                <div key={a.name} className="dv-file">
                  <button className="dv-item" title={`Add lib_${a.name}.py to this strategy`} onClick={() => addArtefact(a)}><code>{a.kind}</code>{a.name}</button>
                  <button className="icon-btn" aria-label={`Delete artefact ${a.name}`} onClick={() => { if (window.confirm(`Delete artefact ${a.name}?`)) setArtefacts((x) => x.filter((y) => y.name !== a.name)); }}><Trash2 size={12} /></button>
                </div>
              ))}
              <button className="btn sm ghost" disabled={active === "main.py"} title={active === "main.py" ? "Open a module file to save it" : undefined} onClick={() => saveArtefact(active)}><FilePlus2 size={13} />Save {active} as artefact</button>
            </div>
          )}
          </>}
        </nav>
      </Panel>
  );
  const editorPanel = (
      <Panel id="editor" minSize="15%" className="dv-edpane" data-drop={dropSide ?? undefined}
        onDragOver={(e) => { if (!e.dataTransfer.types.includes("text/x-studio-file")) return; e.preventDefault(); const r = e.currentTarget.getBoundingClientRect(); setDropSide(e.clientX > r.left + r.width / 2 ? "split" : "main"); }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropSide(null); }}
        onDrop={(e) => { const f = e.dataTransfer.getData("text/x-studio-file"); setDropSide(null); if (!f || !(f in files)) return; e.preventDefault(); setDiff(null); setView("code"); if (dropSide === "split") setSplit(f); else setActive(f); }}>
        <div ref={tabStrip} className="dv-tabs" role="tablist" aria-label="Open files and reports" onDoubleClick={(e) => { if (e.target === e.currentTarget) setZen((z) => !z); }}>
          {open.map((f) => (
            <div key={f} role="tab" aria-selected={view === "code" && !diff && f === active} className="dv-tab" tabIndex={0} draggable onDragStart={(e) => { e.dataTransfer.setData("text/x-studio-file", f); e.dataTransfer.effectAllowed = "move"; }} onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); e.currentTarget.click(); } }} data-preview={preview === f || undefined} data-pinned={pinned.includes(f) || undefined}
              onClick={() => { setDiff(null); setView("code"); setActive(f); }} onDoubleClick={() => keep(f)} onAuxClick={(e) => { if (e.button === 1) close(f); }}>
              {pinned.includes(f) ? <Pin size={10} aria-label="Pinned" /> : null}{f}
              {savedFiles && !(f in scratch) && (savedFiles[f] ?? "") !== (files[f] ?? "") ? <i className="dv-dirty" aria-label="Unsaved" /> : null}
              {open.length > 1 && !pinned.includes(f) ? <button className="icon-btn" aria-label={`Close ${f}`} onClick={(e) => { e.stopPropagation(); close(f); }}><X size={11} /></button> : null}
            </div>
          ))}
          {extra.map((v) => <div key={v} role="tab" aria-selected={view === v} className="dv-tab" tabIndex={0} onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setView(v); } }} onClick={() => setView(v)}>{VIEW_LABEL[v]}<button className="icon-btn" aria-label={`Close ${v}`} onClick={(e) => { e.stopPropagation(); closeView(v); }}><X size={11} /></button></div>)}
          {diff ? <div role="tab" aria-selected className="dv-tab">v{diff.version} ↔ {diff.to ? `v${diff.to.version}` : "draft"} · {active}<button className="icon-btn" aria-label="Close diff" onClick={() => setDiff(null)}><X size={11} /></button></div> : null}
        </div>
        {view === "code" && !diff ? <nav className="dv-crumbs" aria-label="Breadcrumbs"><button onClick={() => revealRail("files")}>{active}</button>{crumbs.map((c) => <button key={`${c.name}${c.line}`} onClick={() => goto(active, c.line, c.column)}>{c.name}</button>)}</nav> : null}
        <div className="dv-editor">
          {view !== "code" ? (
            <div key={view} className="dv-view-pane" data-kind={view}>
              <div className="dv-pbody">{view === "selection" ? (selOut ? <div className="dv-cells"><section>
                <h4><span>{selOut.range}</span>{selOut.row ? <i>{selOut.row.seconds.toFixed(3)} s</i> : null}</h4>
                <pre className="dv-sel-code">{selOut.code}</pre>
                {!selOut.row ? <p className="dv-empty">Running…</p> : <>
                  {selOut.row.stdout ? <pre>{selOut.row.stdout}</pre> : null}
                  <CellPlots plots={selOut.row.plots} />
                  {selOut.row.error ? <p className="bd-find error"><b>Error</b>{selOut.row.error}</p> : null}
                  {selOut.row.value !== null && selOut.row.value !== undefined ? (tableOf(selOut.row.value) ? <VarGrid t={tableOf(selOut.row.value)!} open /> : typeof selOut.row.value === "object" ? <KV rows={selOut.row.value as Record<string, unknown>} /> : <pre>{show(selOut.row.value)}</pre>) : null}
                </>}</section></div> : <p className="dv-empty">Select code and press Shift+Alt+R</p>) : view === "tearsheet" ? <DevTearsheet quick={quick ?? null} /> : view === "robust" ? <DevRobust quick={quick ?? null} /> : view === "runs" ? <DevRuns runs={runLog} onPin={pinRun} onRename={renameRun} /> : resultsView}</div>
            </div>
          ) : null}
          <div className="dv-code" hidden={view !== "code"}>
          <Group orientation={splitDown ? "vertical" : "horizontal"} id="dv-editor-split" groupRef={editorSplitRef}
            defaultLayout={split && !diff ? { primary: ws.cur.layout.size.split ?? 50, secondary: 100 - (ws.cur.layout.size.split ?? 50) } : { primary: 100, secondary: 0 }}
            onLayoutChanged={(sizes, { isUserInteraction }) => {
              if (isUserInteraction && split && !diff) ws.patch((current) => ({ ...current, size: { ...current.size, split: sizes.primary } }));
            }}>
          <Panel id="primary" minSize="20%" className="dv-primary-editor">
          {!spec.code.trim() && active === "main.py" && !diff ? (
            <div className="dv-blank">
              <b>This strategy runs on its rules</b>
              <div><button className="btn primary" onClick={() => void studio<{ code: string }>("POST", "/to-python", { spec }).then((r) => edit({ code: r.code }), (e: Error) => toast.error(e.message))}>Convert rules to Python</button>
                <button className="btn" onClick={() => revealRail("templates")}>Start from a starter</button></div>
            </div>
          ) : null}
          {diff ? (
            <DiffEditor language="python" original={diff.files[active] ?? ""} modified={diff.to ? diff.to.files[active] ?? "" : source} theme="studio" height="100%"
              options={{ readOnly: true, renderSideBySide: true, minimap: { enabled: false }, fontSize: 13, lineHeight: 20, scrollBeyondLastLine: false, automaticLayout: true, fontFamily: "'JetBrains Mono', var(--font-mono), ui-monospace, monospace" }} />
          ) : (
            <CodeEditor path={active} value={source} onChange={(t) => setFile(active, t)} problems={problems} onSave={saveAndRun} onRun={runCode} reveal={reveal} onCursor={(line, column) => setCursor({ line, column })}
              font={font} when={{ debugPaused: !!dbg, panelOpen, cellsFile: hasCells, testFile: /(^|\/)test_[^/]*\.py$/.test(active) }} actions={actions} breakpoints={bps[active] ?? []} bookmarks={[...(bms[active] ?? []), ...Object.values(nbm).filter((b) => b.file === active).map((b) => b.line)]} logpoints={logpoints.filter((p) => p.file === active)} coverage={coverage ? prev?.coverage?.[active] ?? null : null} ran={(prev?.order_lines ?? []).filter((o) => o.file === active)} inline={inlineValues} onGutter={toggleBp} onComment={openThread} commentLines={cmts.filter((c) => c.file === active && !c.date && !c.resolved).map((c) => c.line)} readOnly={readOnly} snippets={snippets}
              onSelection={(t) => { selection.current = t; }} insertRef={insertAt}
              project={{ file: active, files, params: Object.keys(spec.params), symbols: [symbol], goto, replace: replaceFiles, paramSpecs: spec.params, problems,
                refactor, addParam: (name, value) => edit({ params: { ...spec.params, [name]: { value, min: +(value / 2).toPrecision(3), max: +(value * 2).toPrecision(3), step: Math.max(1, Math.round(value / 10)) } } }),
                lens: (command, args) => { if (command === "cell") runCell(Number(args.line), args.only !== false, args.below === true); else if (command === "debug") debug({ date: String(args.date ?? "") }); else if (command === "inspect_condition") { setTab("output"); toast(`${String(args.expression)} on ${String(args.symbol)}`); } else if (command === "run_symbol") { openPreview(); onPreview(); } else runCode("full"); } }} />
          )}
          </Panel>
          <Separator className={`dv-gutter ${splitDown ? "dv-gutter-vertical" : ""}`} disabled={!split || Boolean(diff)} />
          <Panel id="secondary" minSize={split && !diff ? "20%" : 0}>
            {split && !diff ? <div className="dv-split">
              <div className="dv-splithead"><select className="input" aria-label="File in the second group" value={split} onChange={(e) => setSplit(e.target.value)}>{Object.keys(files).map((f) => <option key={f}>{f}</option>)}</select>
                <button className="btn sm ghost" aria-pressed={splitDown} onClick={() => setSplitDown(!splitDown)}>{splitDown ? "Split right" : "Split down"}</button>
                <button className="icon-btn" aria-label="Close split" onClick={() => setSplit(null)}><X size={12} /></button></div>
              <CodeEditor path={`split/${split}`} value={files[split] ?? ""} onChange={(t) => setFile(split, t)} problems={[]} onSave={onSave} onRun={runCode} readOnly={readOnly}
                project={{ file: split, files, params: Object.keys(spec.params), symbols: [symbol], goto, replace: replaceFiles }} />
            </div> : null}
          </Panel>
          </Group>
          </div>
        </div>
        {thread ? (
          <div className="dv-thread" role="dialog" aria-label={thread.date ? `Comments on bar ${thread.date}` : `Comments on ${thread.file}:${thread.line}`}>
            <header><b>{thread.date ? `Bar ${thread.date}` : `${thread.file}:${thread.line}`}</b>
              {(() => { const head = cmts.find((c) => inThread(c, thread)); return head ? <button className="btn sm ghost" onClick={() => resolveThread(head.thread_id, !head.resolved)}>{head.resolved ? "Reopen" : "Resolve"}</button> : null; })()}
              <button className="icon-btn" aria-label="Close thread" onClick={() => setThread(null)}><X size={12} /></button></header>
            {cmts.filter((c) => inThread(c, thread)).map((c) => (
              <p key={c.id}><i>{c.author}</i>{c.text}<button className="icon-btn" aria-label="Delete comment" onClick={() => dropCmt(c.id)}><Trash2 size={12} /></button></p>
            ))}
            <form onSubmit={(e) => { e.preventDefault(); postCmt(); }}><input className="input" autoFocus aria-label="Reply" placeholder="Comment" value={cmtText} onChange={(e) => setCmtText(e.target.value)} /><button className="btn sm primary" disabled={!cmtText.trim()}>Post</button></form>
          </div>
        ) : null}
      </Panel>
  );
  const testerPanel = (
      <Panel id="tester" minSize={0}>
          <div className="dv-panel" inert={!panelOpen} aria-hidden={!panelOpen}>
            <div className="dv-phead">
              <div className="dv-ptabs" role="tablist" aria-label="Bottom panel" onDragOver={(e) => { if (e.dataTransfer.types.includes("text/x-studio-view")) e.preventDefault(); }} onDrop={(e) => { const t = e.dataTransfer.getData("text/x-studio-view") as Tab; if (t) { e.preventDefault(); toPanel(t); } }}>
              {TABS.filter(([k]) => !moved.includes(k)).map(([k, l, n]) => <button key={k} role="tab" aria-selected={tab === k} draggable onDragStart={(e) => e.dataTransfer.setData("text/x-studio-view", k)} onClick={() => setTab(k)}>{l}{n ? <span className="num">{n}</span> : null}</button>)}
              </div>
              <button className="icon-btn" aria-label={panelMax ? "Restore panel" : "Maximise panel"} title={panelMax ? "Restore panel" : "Maximise panel"} onClick={maxTester}>{panelMax ? <Minimize2 size={14} /> : <Maximize2 size={14} />}</button>
              <button className="icon-btn" aria-label="Hide panel" title="Hide panel ⌘J" onClick={() => setPanelOpen(false)}><X size={13} /></button>
            </div>
            <div className="dv-pbody" onScroll={(e) => { if (tab === "output") setLogTop(e.currentTarget.scrollTop); }}>
              {panelBody(movedTab(tab) ? TABS.find(([k]) => !moved.includes(k))?.[0] ?? "tester" : tab, false)}
            </div>
          </div>
      </Panel>
  );
  const rightPanel = (
      <Panel id="right" minSize={0}>
      <aside className="dv-side" inert={!chartOpen}>
        {chartSeen.current ? <div className="dv-chartpane" hidden={!chartOpen}><DevChart onMark={markToCode} onNote={openBarThread} notes={[...new Set(cmts.filter((c) => c.date && !c.resolved).map((c) => c.date!))]} symbol={dbg?.symbol ?? symbol} drawKey={strategyId ?? "new"} prev={prev} pausedAt={dbg?.date ?? null} playing={playing} speed={speed} onPlay={setPlaying} onSpeed={setSpeed} onGo={replayGo} max={maxChart} onMax={() => setMaxChart((x) => !x)} /></div> : null}
      </aside>
      </Panel>
  );
  const centerPanel = (
      <Panel id="center" minSize={chartFirst ? "30%" : "430px"}>
      <Group className="dv-main" orientation={pside ? "horizontal" : "vertical"} id={full ? "dv-v1" : `dv-v${pside ?? ""}`} key={full ? "one" : pside ?? "split"} groupRef={full ? undefined : vRef} defaultLayout={full ? { editor: 100 } : targets(layout).v} onLayoutChanged={full ? undefined : onV}>
      {pside === "left" ? <>{testerPanel}<Separator className="dv-gutter" disabled={!panelOpen} /></> : null}
      {editorPanel}
      {full || pside === "left" ? null : <><Separator className="dv-gutter" disabled={!panelOpen} />{testerPanel}</>}
      </Group>
      </Panel>
  );
  const hGroup = (
      <Group orientation="horizontal" id={chartLeft ? "dv-hl" : "dv-h"} key={chartLeft ? "left" : "right"} groupRef={hRef} defaultLayout={targets(layout).h} onLayoutChanged={onH}>
      {railPanel}
      <Separator className="dv-gutter" disabled={!railOpen} />
      {chartLeft ? <>{rightPanel}<Separator className="dv-gutter" disabled={!chartOpen} />{centerPanel}</> : <>{centerPanel}<Separator className="dv-gutter" disabled={!chartOpen} />{rightPanel}</>}
      </Group>
  );

  return (
    <div className="dv" data-activity={iconsOpen} data-head={slot ? "" : undefined} data-zen={zen || undefined} data-max={maxChart && chartOpen ? "chart" : undefined}>
      {slot ? createPortal(<div className="dv-bar in-head">{bar}</div>, slot) : <div className="dv-bar">{bar}</div>}
      <nav className="dv-icons" aria-label="Activity bar" hidden={!iconsOpen || zen}>
        {/* Four entry points; Outline sits beside Files in the side bar header, Starters opens from ⌘⇧S and the empty editor. */}
        {RAILS.filter(([k]) => k !== "outline" && k !== "templates").map(([k, icon, l]) => {
          const on = railOpen && (rail === k || (k === "files" && rail === "outline"));
          return <button key={k} className="icon-btn" title={l} aria-label={l} aria-pressed={on} onClick={() => { if (on) setRailOpen(false); else revealRail(k); }}>{icon}</button>;
        })}
        <span className="dv-icons-gap" />
        {/* Bottom group opens the bottom panel (JetBrains: lower stripe icons open horizontal tool windows). */}
        {([["tester", <Gauge key="g" size={18} />, "Tester"], ["problems", <CircleAlert key="p" size={18} />, "Problems"], ["console", <SquareTerminal key="c" size={18} />, "Console"]] as const).map(([k, icon, l]) => {
          const side = moved.includes(k), on = side ? railOpen && sideTab === k : panelOpen && tab === k;
          return <button key={k} className="icon-btn" title={l} aria-label={l} aria-pressed={on} onClick={() => { if (side) { if (on) setRailOpen(false); else { setSideTab(k); setRailOpen(true); } } else if (on) setPanelOpen(false); else { setPanelOpen(true); setTab(k); } }}>{icon}</button>;
        })}
      </nav>
      <div className="dv-body" ref={bodyRef}>
      {full ? (
        <Group orientation="vertical" id="dv-vf" key="full" groupRef={vRef} defaultLayout={vKeys(targets(layout).v)} onLayoutChanged={onV}>
          <Panel id="top" minSize="15%">{hGroup}</Panel>
          <Separator className="dv-gutter" disabled={!panelOpen} />
          {testerPanel}
        </Group>
      ) : hGroup}
      </div>

      <footer className="dv-status">
        <span>{active}</span><span>Ln {cursor.line}, Col {cursor.column}</span><CursorDate />
        {strategyId ? <span className="dv-paper"><button className="dv-sbtn" aria-expanded={paperOpen} onClick={() => setPaperOpen((o) => !o)} data-on={paperRun ? "" : undefined}>
          {paperRun ? `Paper v${paperRun.version}${paper?.last?.total_return != null ? ` · ${(paper.last.total_return * 100).toFixed(1)}%` : ""}${paper?.last?.paper_day != null ? ` · today ${(paper.last.paper_day * 100).toFixed(2)}%` : ""}` : "Paper off"}</button>
          {paperOpen ? <div className="dv-paper-pop" role="dialog" aria-label="Paper">
            {paper?.freshness.tone === "red" ? <p className="dv-empty">Data is {paper.freshness.age_days} days old; paper waits for fresh data.</p> : null}
            {paperRun ? <>
              <p>v{paperRun.version} on paper since {paperRun.from}{paperRun.backdated ? " (backdated)" : ""}</p>
              <button className="btn sm" onClick={() => { if (window.confirm(`Stop v${paperRun.version} on paper and close its paper positions?`)) paperAct("/paper/stop", { version: paperRun.version }, "Paper stopped"); }}>Stop and flatten</button>
              <label>Debug a paper day <input className="input" type="date" min={paperRun.from} onChange={(e) => { if (e.target.value) { setPaperOpen(false); setPanelOpen(true); setTab("debug"); debug({ date: e.target.value }); } }} /></label>
            </> : <button className="btn sm primary" disabled={!version} onClick={() => paperAct("/freeze", { version }, `v${version} frozen to paper`)}>Freeze v{version ?? ""} to paper</button>}
            <Link className="btn sm ghost" href="/studio/live">Open Live</Link>
          </div> : null}
        </span> : null}
        <button className="dv-sbtn" onClick={() => { setPanelOpen(true); setTab("problems"); }}><b className="error">{errors}</b> errors <b className="warning">{warnings}</b> warnings</button>
        <span className={`dv-save dv-save-${saved}`}>{{ saved: "Saved", draft: "Draft", saving: "Saving…", conflict: "Conflict: reload", new: "Not saved" }[saved]}</span>
        {prev?.warmup ? <span>warm-up {prev.warmup.bars} bars{prev.warmup.first_eligible_date ? ` · trades from ${prev.warmup.first_eligible_date}` : ""}</span> : null}
        {prev?.settings_overrides && Object.keys(prev.settings_overrides).length ? <span className="dv-over" title={Object.entries(prev.settings_overrides).map(([k, v]) => `${k} = ${String(v)}`).join("\n")}>code sets {Object.keys(prev.settings_overrides).join(", ")}</span> : null}
        {Object.values(bps).flat().length ? <span>{Object.values(bps).flat().length} breakpoint{Object.values(bps).flat().length === 1 ? "" : "s"}</span> : null}
        <span style={{ flex: 1 }} />
        {quick && ["queued", "running"].includes(quick.status) ? <span className="dv-runchip">{quick.progress?.partial ? `bar ${quick.progress.partial.bars?.toLocaleString() ?? "…"} · ${quick.progress.partial.symbols ?? "…"} symbols · ${quick.progress.partial.elapsed_seconds?.toFixed(1) ?? "0"} s of ${quick.progress.partial.budget_seconds ?? "…"} s` : `${quick.level} run ${quick.progress?.percent ?? 0}%`}</span> : null}
        {trial}
        {open_.chart ? <a href="https://www.vela.dev" target="_blank" rel="noreferrer">Vela™</a> : null}
        <span>{prev ? `${prev.status === "ok" ? `preview ${symbol}` : prev.status}${lastPreview ? ` · ${lastPreview}` : ""}` : "no preview"}</span><NotifyBell /><span>Python 3.12</span>
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
