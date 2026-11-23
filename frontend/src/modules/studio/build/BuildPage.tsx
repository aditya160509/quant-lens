"use client";

import { Command as CommandIcon, BookmarkPlus, CircleCheck, CircleDashed, CircleX, Download, GitBranch, GitMerge, Settings2, Link2, ArrowLeft, ArrowUp, Bookmark, Code2, FilePlus2, FolderGit2, Keyboard, LayoutPanelLeft, Palette as PaletteIcon, RotateCcw, Search, SlidersHorizontal, PlayCircle, MoreHorizontal, Play, Plus, Save, Trash2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { minMax } from "./devStats";
import toast from "react-hot-toast";
import { defaultsFor } from "@/modules/research/StudyForm";
import { useStudies } from "@/modules/research/store";
import type { FeatureSpec } from "@/modules/research/types";
import { copyText, studio, useTemplates, type Compiled, type Ledger } from "../api";
import { TimeSeries } from "@/charts/TimeSeries";
import { TrialChip } from "../RunHeader";
import { GroupEditor, groupFormula, paletteOrder, toGroup } from "./BlockRows";
import { REBINDABLE } from "./CodeEditor";
import { FIXED, conflictWith } from "./keymap";
import { useServerPref } from "./serverPref";
import { BranchDialog } from "./Branches";
import { MenuItem, PopMenu, Segmented, type MenuAt } from "@/workspace/ui";
import { STUDIO_BASE } from "../base";
import type { Problem } from "./CodeEditor";
import { ChartPopout } from "./ChartPopout";
import { DevIDE, type DevPreview, type Logpoint, type QuickRun, type Saved } from "./DevIDE";
import { Palette, type Command } from "./Palette";
import { specDiff, type Group } from "./blocks";
import "../studio.css";

type Param = { value: number; min?: number | null; max?: number | null; step?: number | null; log?: boolean };
type Spec = {
  name: string; entry_long: string; exit_long: string; entry_short: string; exit_short: string; score: string; market_filter: string; scale_in: string; max_entries?: number; defensive?: string;
  params: Record<string, Param>;
  exits: Record<string, number>; sizing: { mode: string; value: number; max_positions: number };
  limits: Record<string, number | null>; code: string; hypothesis: string; regime_claim: string; notes: string; [k: string]: unknown;
};
type Version = { version: number; hash: string; actor: string; created: number };
type RunSum = { headline?: string; total_return?: number; sharpe?: number | null; trades?: number };
type Loaded = { id: string; name: string; version: number; latest: number; spec: Spec; draft: Spec | null; versions: Version[]; trials: Ledger; runs_by_version: Record<string, RunSum>; regime_written_after: boolean };

const BLANK: Spec = {
  name: "Untitled", entry_long: "", exit_long: "", entry_short: "", exit_short: "", score: "", market_filter: "", scale_in: "", params: {},
  exits: { stop: 0, stop_atr: 0, target: 0, trail: 0, time_stop: 0, breakeven: 0, scale_at: 0, scale_frac: 0 },
  sizing: { mode: "equal", value: 0, max_positions: 10 },
  limits: { max_drawdown: 0.25, max_drawdown_months: null, min_trades: 30, min_years: null, max_beta: null, max_cost_share: null, min_start_pass: null },
  code: "", hypothesis: "", regime_claim: "", notes: "",
};
const ROLES: [string, string][] = [["entry_long", "Enter long"], ["exit_long", "Exit long"], ["entry_short", "Enter short"], ["exit_short", "Exit short"], ["score", "Rank by"], ["market_filter", "Trade only when"], ["scale_in", "Add when"]];
const EXITS: [string, string, boolean][] = [["stop", "Stop", true], ["stop_atr", "Stop × ATR", false], ["target", "Target", true], ["trail", "Trailing stop", true], ["time_stop", "Time stop (bars)", false],
  ["breakeven", "Breakeven at", true], ["scale_at", "Scale out at", true], ["scale_frac", "Scale out share", true]];
const LIMITS: [string, string, boolean][] = [["max_drawdown", "Max drawdown", true], ["max_drawdown_months", "Max drawdown months", false], ["min_trades", "Min trades", false],
  ["min_years", "Min years", false], ["max_beta", "Max beta", false], ["max_cost_share", "Max cost share", true], ["min_start_pass", "Min start dates passing", true]];
type Defaults = { ui: "simple" | "dev"; mode: "blocks" | "formula" | "english"; exits: Record<string, number>; sizing: Spec["sizing"]; compact: boolean; plain: boolean; palette: string[]; keys: Record<string, string>; wrap: boolean; rulers: number; ligatures: boolean; minimap: boolean; lens: boolean };
type Profile = { name: string; defaults: Partial<Defaults>; layouts?: unknown; keys?: Record<string, string> };
/** What a profile captures besides the Build defaults: theme, appearance, run configurations, layouts, editor font. */
const PROFILE_KEYS = ["ws-theme", "ws-prefs", "studio:runconfigs", "studio:dev:workspaces", "studio:dev:font", "studio:dev:chartafterrun", "studio:chart:watch", "studio:chart:view"];
const writeDefaults = (d: Partial<Defaults>) => { try { localStorage.setItem("studio:build:defaults", JSON.stringify(d)); localStorage.removeItem("studio:build:ui"); } catch { /* blocked */ } void studio("PUT", "/build/prefs/settings", d).catch(() => undefined); };
const readDefaults = (): Partial<Defaults> => { try { return JSON.parse(localStorage.getItem("studio:build:defaults") ?? "{}") as Partial<Defaults>; } catch { return {}; } };
const fail = (e: unknown) => toast.error(e instanceof Error ? e.message : "Failed");

/** Percent fields are typed as percent and stored as fractions. */
function Num({ label, value, pct, onChange, empty }: { label: string; value: number | null | undefined; pct?: boolean; empty?: boolean; onChange: (v: number | null) => void }) {
  const show = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(pct ? +(v * 100).toFixed(4) : v));
  // The field keeps what was typed ("0.", "-", "") and commits each valid number; outside edits replace it only while unfocused.
  const [text, setText] = useState(() => show(value));
  const typing = useRef(false);
  useEffect(() => { if (!typing.current) setText(show(value)); }, [value, pct]); // eslint-disable-line react-hooks/exhaustive-deps
  const n = Number(text.trim()), bad = !!text.trim() && !Number.isFinite(n);
  return (
    <label className="bd-num"><span>{label}</span>
      <input className="input" inputMode="decimal" value={text} placeholder={empty ? "—" : "0"} aria-invalid={bad || undefined}
        onFocus={() => { typing.current = true; }}
        onChange={(e) => { const t = e.target.value; setText(t); const v = Number(t.trim()); if (t.trim() && Number.isFinite(v)) onChange(pct ? v / 100 : v); }}
        onBlur={() => { typing.current = false; if (!text.trim()) { onChange(empty ? null : 0); setText(empty ? "" : "0"); } else setText(show(value)); }} />
      {pct ? <i>%</i> : null}
    </label>
  );
}

/** Build: write the rule, see it compile as you type, save immutable versions, run. */
const noSub = () => () => undefined;
/** ?popout=chart opens only the chart, fed by the Build window (ChartPopout). */
export default function BuildPage(props: { features: FeatureSpec[]; id?: string }) {
  const popout = useSyncExternalStore(noSub, () => new URLSearchParams(window.location.search).get("popout") === "chart", () => false);
  return popout ? <ChartPopout /> : <BuildEditor {...props} />;
}

function BuildEditor({ features, id }: { features: FeatureSpec[]; id?: string }) {
  // Settings sync: the server copy (saved from any browser) replaces this browser's on load.
  useEffect(() => { void studio<{ value: Partial<Defaults> | null }>("GET", "/build/prefs/settings").then((r) => { if (r.value) try { localStorage.setItem("studio:build:defaults", JSON.stringify(r.value)); } catch { /* blocked */ } }, () => undefined); }, []);
  const router = useRouter();
  const templates = useTemplates();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [spec, setSpec] = useState<Spec>(BLANK);
  const [compiled, setCompiled] = useState<Compiled | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState<"idle" | "saving" | "conflict">("idle");
  const [readOnly, setReadOnly] = useState<null | { kind: "lease"; since: number } | { kind: "share"; token: string }>(null);
  const [more, setMore] = useState<MenuAt | null>(null);
  const session = useRef(typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Math.random()));
  const zipInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"blocks" | "formula" | "english">(() => (typeof window === "undefined" ? "formula" : readDefaults().mode ?? "formula"));
  const [dialog, setDialog] = useState<"branches" | "customise" | null>(null);
  const [ui, setUiState] = useState<"simple" | "dev">(() => {
    if (typeof window === "undefined") return "simple";
    const q = new URLSearchParams(window.location.search).get("ui");
    if (q === "dev" || q === "simple") return q;
    try { return (localStorage.getItem("studio:build:ui") ?? readDefaults().ui) === "dev" ? "dev" : "simple"; } catch { return "simple"; }
  });
  const [english, setEnglish] = useState("");
  // ?symbol= opens the preview on a name (Backtest → "on the chart" links here).
  const [symbol, setSymbol] = useState(() => (typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("symbol")?.toUpperCase()) || "SPY");
  const [years, setYears] = useState(2);
  const [auto, setAuto] = useState(() => { try { return localStorage.getItem("studio:build:auto") !== "off"; } catch { return true; } });
  const [previewed, setPreviewed] = useState<string | null>(null);
  const [nudge, setNudge] = useState(0);
  const [recover, setRecover] = useState<{ spec: Spec; at: number } | null>(null);
  const [pausedAt, setPausedAt] = useState<string | null>(null);
  const [pausedLabel, setPausedLabel] = useState("❚❚");
  const [quick, setQuick] = useState<QuickRun | null>(null);
  const [logpoints, setLogpoints] = useState<Logpoint[]>([]);
  const [coverage, setCoverage] = useState(false);
  const runPending = useRef(false);
  // Run-status polling stops when the page unmounts.
  const alive = useRef(true), job = useRef<string | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [starting, setStarting] = useState(false);
  const quickRun = async (level: "quick" | "full", settings: Record<string, unknown> = {}) => {
    if (runPending.current) return;
    runPending.current = true;
    setStarting(true);
    try {
      // A full run of an unchanged, saved strategy reuses its version instead of adding one to the trial ledger.
      const sid = level === "full" ? (loaded && !dirty ? loaded.id : await save(undefined, false)) : loaded?.id;
      if (level === "full" && !sid) { runPending.current = false; return; }
      // Run-config input overrides ("fast=10 slow=50") change quick runs only; full runs stay on the saved version for the trial ledger.
      const { params: over, ...rest } = settings;
      const pairs = String(over ?? "").split(/[\s,]+/).map((x) => x.split("=")).filter(([k, v]) => k && spec.params[k] && v !== undefined && v !== "" && Number.isFinite(Number(v)));
      const runSpec = pairs.length ? { ...spec, params: { ...spec.params, ...Object.fromEntries(pairs.map(([k, v]) => [k!, { ...spec.params[k!]!, value: Number(v) }])) } } : spec;
      const j = await studio<QuickRun>("POST", "/build/run", level === "full" ? { level, strategy_id: sid, settings: rest } : { level, spec: runSpec, settings: rest, ...(sid ? { strategy_id: sid } : {}) });
      setQuick({ ...j, level, status: "queued" });
      job.current = j.job_id;
      const poll = async () => {
        // Stop when the page is gone or a newer run owns the display.
        if (!alive.current || job.current !== j.job_id) { if (job.current === j.job_id) runPending.current = false; return; }
        const st = await studio<QuickRun>("GET", `/build/run/${j.job_id}`).catch(() => null);
        if (!st) {
          runPending.current = false;
          setQuick((q) => q?.job_id === j.job_id && q.status !== "cancelled" ? { ...q, status: "failed", error: "Could not retrieve backtest status." } : q);
          return;
        }
        setQuick((q) => (q?.job_id === j.job_id ? { ...st, level } : q));
        if (["queued", "running"].includes(st.status)) setTimeout(() => void poll(), document.hidden ? 3000 : 700);
        else {
          runPending.current = false;
          if (level === "full" && sid) {
            void studio<Loaded>("GET", `/strategies/${sid}`).then(
              (updated) => setLoaded((current) => current?.id === sid ? updated : current),
              () => undefined,
            );
          }
        }
      };
      setTimeout(() => void poll(), 400);
    } catch (e) { runPending.current = false; fail(e); }
    finally { setStarting(false); }
  };
  const cancelRun = () => { if (quick) void studio("POST", `/jobs/${quick.job_id}/cancel`).then(() => setQuick((q) => (q ? { ...q, status: "cancelled" } : q)), fail); };
  const [font, setFont] = useState(() => { try { return Number(localStorage.getItem("studio:dev:font")) || 13; } catch { return 13; } });
  type Preview = Omit<DevPreview, "trades"> & { bars: { date: string; close: number }[]; trades: { entry_date: string; exit_date: string; side: string; return: number }[]; total_return?: number; repaint?: { cuts: number; changed: number; dates: string[] }; symbols?: string[]; bars_by_symbol?: Record<string, { date: string; close: number }[]> };
  const [prev, setPrev] = useState<Preview | null>(null);
  const [chartSym, setChartSym] = useState("");
  const [diff, setDiff] = useState<{ version: number; rows: [string, string, string][] } | null>(null);
  type Proposal = { fields: Record<string, string>; exits: Record<string, number>; unmatched: string[]; assumptions?: { word: string; start: number; end: number; meaning: string; formula: string }[]; restated?: string };
  const [proposal, setProposal] = useState<Proposal | { error: string } | null>(null);
  const [catalogue, setCatalogue] = useState<string[]>([]);
  type Ref = { name: string; doc: string; example?: string; args?: string[] };
  const [reference, setReference] = useState<Ref[]>([]);
  const [refQ, setRefQ] = useState("");
  type Cond = { true_rate: number | null; last_true_date: string | null; fired_dates: string[]; constant: boolean | null; observations: number };
  const [conds, setConds] = useState<Record<string, Cond | { error: string }>>({});
  const [fired, setFired] = useState<{ role: string; dates: string[] } | null>(null);
  const [pyView, setPyView] = useState<string | null>(null);
  useEffect(() => { void studio<{ formula: { fields: Ref[]; operators: Ref[] } }>("GET", "/manifest").then((m) => { setCatalogue([...m.formula.fields.map((f) => f.name), ...m.formula.operators.map((o) => o.example ?? o.name)]); setReference([...m.formula.operators, ...m.formula.fields]); }, () => undefined); }, []);
  const history = useRef<{ past: Spec[]; future: Spec[]; at: number }>({ past: [], future: [], at: 0 });
  const specRef = useRef<Spec | null>(null);
  const editRev = useRef(0), saveInFlight = useRef(false);
  const [palette, setPalette] = useState(false);
  const [seed, setSeed] = useState<{ q: string }>();
  const [devItems, setDevItems] = useState<{ id: string; group: string; label: string; hidden: boolean }[]>([]);
  useEffect(() => {
    const items = (e: Event) => setDevItems((e as CustomEvent).detail);
    const open = (e: Event) => { setSeed({ q: (e as CustomEvent<string>).detail }); setPalette(true); };
    let last = 0; // double Shift opens Search Everywhere
    const key = (e: KeyboardEvent) => { if (e.key !== "Shift" || e.isComposing) { last = 0; return; } if (e.repeat) return; const t = Date.now(); if (t - last < 400) { last = 0; open(new CustomEvent("x", { detail: "" })); } else last = t; };
    window.addEventListener("studio:devitems", items); window.addEventListener("studio:palette", open); window.addEventListener("keydown", key);
    return () => { window.removeEventListener("studio:devitems", items); window.removeEventListener("studio:palette", open); window.removeEventListener("keydown", key); };
  }, []);
  const focus = useRef<{ role: string; start: number; end: number } | null>(null);
  const track = (role: string) => (e: React.SyntheticEvent<HTMLTextAreaElement>) => { const t = e.currentTarget; focus.current = { role, start: t.selectionStart, end: t.selectionEnd }; };

  const load = useCallback((sid: string, version?: number) => studio<Loaded>("GET", `/strategies/${sid}${version ? `?version=${version}` : ""}`).then((s) => {
    const next = { ...BLANK, ...(version ? s.spec : s.draft ?? s.spec) };
    setLoaded(s); setSpec(next); if (next.code.trim() && !new URLSearchParams(window.location.search).get("ui")) setUi("dev"); setDirty(!version && !!s.draft); history.current = { past: [], future: [], at: 0 };
  }, fail), []);
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("share");
    if (token) {
      void studio<{ name: string; files: Record<string, string> }>("GET", `/share/${token}`).then((r) => { const { "main.py": code = "", ...files } = r.files; setSpec({ ...BLANK, name: r.name, code, files }); setReadOnly({ kind: "share", token }); setUi("dev"); }, fail);
      return;
    }
    if (id) void load(id); else { const d = readDefaults(); setLoaded(null); setSpec({ ...BLANK, exits: { ...BLANK.exits, ...d.exits }, sizing: { ...BLANK.sizing, ...d.sizing } }); }
  }, [id, load]); // eslint-disable-line react-hooks/exhaustive-deps

  // One editing session per strategy (B-14, B-132): renew a 60 s lease every 30 s; a second tab opens read-only.
  const takeLease = useCallback((takeOver = false) => {
    if (!loaded) return;
    void studio<{ since: number }>("POST", `/strategies/${loaded.id}/lease`, { session: session.current, take_over: takeOver })
      .then(() => setReadOnly((r) => (r?.kind === "lease" ? null : r)), (e: Error & { status?: number; detail?: { since?: number } }) => { if (e.status === 409) setReadOnly({ kind: "lease", since: e.detail?.since ?? Date.now() / 1000 }); });
  }, [loaded]);
  useEffect(() => {
    if (!loaded) return;
    takeLease();
    const t = setInterval(() => takeLease(), 30_000);
    const sid = loaded.id, s = session.current;
    const release = () => void fetch(`${STUDIO_BASE}/strategies/${sid}/lease?session=${s}`, { method: "DELETE", keepalive: true }).catch(() => undefined);
    // Renew as soon as a throttled or sleeping tab is visible again; release when the page is closed.
    const onVis = () => { if (!document.hidden) takeLease(); };
    document.addEventListener("visibilitychange", onVis); window.addEventListener("pagehide", release);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", onVis); window.removeEventListener("pagehide", release); release(); };
  }, [loaded?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 760px)");
    const on = () => { if (mq.matches) setUiState("simple"); };
    on(); mq.addEventListener("change", on); return () => mq.removeEventListener("change", on);
  }, []);
  function setUi(next: "simple" | "dev") {
    setUiState(next);
    try { localStorage.setItem("studio:build:ui", next); } catch { /* storage blocked */ }
    const u = new URL(window.location.href); u.searchParams.set("ui", next); window.history.replaceState(window.history.state, "", u);
  }
  function switchUi(next: "simple" | "dev") {
    setUi(next);
    if (next === "dev" && !spec.code.trim()) void studio<{ code: string }>("POST", "/to-python", { spec }).then((r) => edit({ code: r.code }), fail);
  }
  const switchMode = (m: "blocks" | "formula" | "english") => setMode(m);
  // Format main.py and every other .py file, then save.
  const formatSave = () => {
    const fmt = (code: string) => studio<{ code: string }>("POST", "/format-python", { code }).then((r) => r.code, () => code);
    const own = (spec.files ?? {}) as Record<string, string>;
    const py = Object.entries(own).filter(([f]) => f.endsWith(".py"));
    const at = editRev.current;
    void Promise.all([fmt(spec.code), ...py.map(([, c]) => fmt(c))]).then(([code, ...rest]) => {
      // Typing continued while formatting: keep those edits and save them unformatted.
      if (editRev.current !== at) return save();
      const files = { ...own, ...Object.fromEntries(py.map(([f], i) => [f, rest[i]!])) };
      const next = { ...spec, code: code!, files };
      if (code !== spec.code || py.some(([f, c]) => files[f] !== c)) edit({ code: code!, files });
      return save(next);
    }, fail);
  };
  // Undo history is recorded here, not inside the state updater (updaters must be pure); edits within 500 ms form one undo step.
  specRef.current = spec;
  const edit = (next: Partial<Spec>) => {
    if (readOnly) return void toast("Read-only", { id: "ro" });
    const h = history.current, now = Date.now(), cur = specRef.current!;
    if (now - h.at > 500) h.past = [...h.past.slice(-49), cur];
    h.at = now; h.future = []; editRev.current++;
    specRef.current = { ...cur, ...next };
    setDirty(true); setSpec((c) => ({ ...c, ...next }));
  };

  // Live compile, 250 ms after typing stops.
  // A newer edit aborts the older request, so a slow response never replaces a newer result.
  useEffect(() => {
    const ac = new AbortController();
    const t = setTimeout(() => studio<Compiled>("POST", "/compile", { spec }, ac.signal).then((c) => { if (!ac.signal.aborted) setCompiled(c); }, (e) => { if (!ac.signal.aborted) setCompiled({ ok: false, findings: [{ severity: "error", role: "spec", line: 1, start: 0, end: 0, token: "", message: e instanceof Error ? e.message : "Invalid" }], hash: "", description: "" }); }), 250);
    return () => { clearTimeout(t); ac.abort(); };
  }, [spec]);

  // Preview on one name once the compiled rule changes (B-5).
  useEffect(() => {
    if (!compiled?.ok || !symbol.trim() || (!auto && !nudge)) return;
    const hash = compiled.hash;
    const body = { spec, symbol: symbol.trim().toUpperCase(), years, logpoints, coverage };
    const request = new AbortController();
    let checked = false;
    const t = setTimeout(() => void studio<Preview>("POST", "/preview", { ...body, repaint: false }, request.signal).then((r) => { if (!request.signal.aborted && !checked) { setPrev(r); setPreviewed(hash); } }, (e) => { if (!request.signal.aborted && !checked) setPrev({ status: "skipped", reason: e instanceof Error ? e.message : "failed", bars: [], trades: [] }); }), 120);
    // The look-ahead replay is the slow part, so it runs once typing has stopped (B-5).
    const full = setTimeout(() => void studio<Preview>("POST", "/preview", body, request.signal).then((r) => { if (!request.signal.aborted) { checked = true; setPrev(r); setPreviewed(hash); } }, () => undefined).finally(() => { if (!request.signal.aborted) setNudge(0); }), 1200);
    return () => { clearTimeout(t); clearTimeout(full); request.abort(); };
  }, [compiled?.hash, symbol, years, compiled?.ok, auto, nudge, logpoints, coverage]); // eslint-disable-line react-hooks/exhaustive-deps -- keyed on the rule hash, so name and notes edits do not re-run the preview
  const stale = !!prev && !!previewed && !!compiled?.hash && previewed !== compiled.hash;

  // Browser copy of unsaved edits, offered back when the page reopens with something different (B-27).
  const backupKey = `studio:draft:${loaded?.id ?? id ?? "new"}`;
  useEffect(() => {
    if (!dirty) return;
    const t = setTimeout(() => {
      const raw = JSON.stringify({ spec, at: Date.now() });
      // Bounded: drafts over 1 MB are not mirrored, only the 20 newest drafts are kept, and a full store says so once.
      if (raw.length > 1_000_000) return void toast("This draft is too large for the browser backup; the server draft still saves", { id: "backup" });
      try {
        const fresh = localStorage.getItem(backupKey) === null;
        localStorage.setItem(backupKey, raw);
        if (!fresh) return;
        const old = Object.keys(localStorage).filter((k) => k.startsWith("studio:draft:")).map((k) => { try { return [k, (JSON.parse(localStorage.getItem(k)!) as { at?: number }).at ?? 0] as const; } catch { return [k, 0] as const; } });
        for (const [k] of old.sort((a, b) => b[1] - a[1]).slice(20)) localStorage.removeItem(k);
      } catch { toast.error("Browser storage is full; the local draft backup is off", { id: "backup" }); }
    }, 500);
    return () => clearTimeout(t);
  }, [spec, dirty, backupKey]);
  // Leaving with unsaved edits asks first (the local backup stays as a second safety net).
  useEffect(() => {
    if (!dirty || readOnly) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, readOnly]);
  useEffect(() => {
    if (!loaded) return;
    try {
      const raw = localStorage.getItem(`studio:draft:${loaded.id}`); if (!raw) return;
      const b = JSON.parse(raw) as { spec: Spec; at: number };
      if (JSON.stringify({ ...BLANK, ...b.spec }) !== JSON.stringify({ ...BLANK, ...(loaded.draft ?? loaded.spec) })) setRecover(b); else localStorage.removeItem(`studio:draft:${loaded.id}`);
    } catch { /* blocked */ }
  }, [loaded?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  // A new strategy has no server copy, so its browser draft comes back as it was (B-6).
  useEffect(() => {
    if (id || new URLSearchParams(location.search).has("share")) return;
    try { const raw = localStorage.getItem("studio:draft:new"); if (raw) edit((JSON.parse(raw) as { spec: Spec }).spec); } catch { /* blocked */ }
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  // True-rate and last true date of every rule on the preview name, 600 ms after typing stops (B-108, B-111, B-116).
  useEffect(() => {
    if (!compiled?.ok || !symbol.trim() || ui === "dev") return;
    const ac = new AbortController();
    const t = setTimeout(() => {
      for (const [role] of ROLES) {
        const expr = (spec[role] as string).trim();
        if (!expr || role === "score") continue;
        void studio<Cond>("POST", "/build/condition", { spec, symbol: symbol.trim().toUpperCase(), expression: expr }, ac.signal)
          .then((c) => { if (!ac.signal.aborted) setConds((o) => ({ ...o, [role]: c })); }, (e: Error) => { if (!ac.signal.aborted) setConds((o) => ({ ...o, [role]: { error: e.message } })); });
      }
    }, 600);
    return () => { clearTimeout(t); ac.abort(); };
  }, [spec, symbol, compiled?.ok, ui]);
  useEffect(() => {
    if (pyView === null) return;
    const t = setTimeout(() => void studio<{ code: string }>("POST", "/to-python", { spec: { ...spec, code: "" } }).then((r) => setPyView(r.code), () => undefined), 400);
    return () => clearTimeout(t);
  }, [spec, pyView === null]); // eslint-disable-line react-hooks/exhaustive-deps

  // Autosave the draft every 2 s while there are unsaved edits (B-6).
  useEffect(() => {
    if (!dirty || !loaded || readOnly || saving === "saving") return;
    const ac = new AbortController();
    const t = setTimeout(() => void studio("PUT", `/strategies/${loaded.id}/draft`, { spec }, ac.signal).catch(() => undefined), 2000);
    return () => { clearTimeout(t); ac.abort(); };
  }, [spec, dirty, loaded, readOnly, saving]);

  const save = useCallback(async (over?: Spec, navigate = true): Promise<string | null> => {
    if (readOnly) { toast("Read-only", { id: "ro" }); return null; }
    if (saveInFlight.current) return null;
    saveInFlight.current = true;
    const at = editRev.current;
    const body = { spec: over ?? spec, ...(loaded ? { base_version: loaded.latest } : {}) };
    setSaving("saving");
    try {
      const s = loaded ? await studio<Loaded>("PUT", `/strategies/${loaded.id}`, body) : await studio<Loaded>("POST", "/strategies", body);
      // Edits typed while the save was in flight stay marked unsaved.
      setLoaded(s); if (editRev.current === at) setDirty(false); setSaving("idle"); toast.success(`Saved version ${s.latest}`);
      try { localStorage.removeItem(`studio:draft:${s.id}`); localStorage.removeItem("studio:draft:new"); } catch { /* blocked */ }
      if (!loaded && navigate) router.replace(`/studio/build/${s.id}?ui=${ui}`);
      return s.id;
    } catch (e) { setSaving((e as { status?: number })?.status === 409 ? "conflict" : "idle"); fail(e); return null; }
    finally { saveInFlight.current = false; }
  }, [loaded, spec, router, ui, readOnly]);

  const run = useCallback(async () => {
    const sid = await save(); if (!sid) return;
    try { localStorage.setItem("studio:strategy", sid); } catch { /* storage blocked */ }
    const f = features.find((x) => x.id === "st01");
    if (f) useStudies.getState().setForm("st01", (cur) => ({ ...cur, strategy_id: sid }), defaultsFor(f));
    router.push("/studio/backtest?go=1");
  }, [save, features, router]);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.isComposing) return;
      if (e.key.toLowerCase() === "p" && e.shiftKey) { e.preventDefault(); setPalette((o) => !o); }
      else if (e.key.toLowerCase() === "s" && !e.shiftKey) { e.preventDefault(); void save(); }
      else if (e.key === "Enter" && ui !== "dev") { e.preventDefault(); void run(); }
      else if (e.key.toLowerCase() === "z" && !(e.target as HTMLElement).matches("input, textarea")) {
        e.preventDefault(); const h = history.current, from = e.shiftKey ? h.future : h.past, to = e.shiftKey ? h.past : h.future;
        const prev = from.pop(); if (prev) { to.push(specRef.current!); h.at = 0; editRev.current++; specRef.current = prev; setSpec(prev); setDirty(true); }
      }
    };
    window.addEventListener("keydown", on); return () => window.removeEventListener("keydown", on);
  }, [save, run, ui]);

  /** Lift the number under the cursor (or selected) in a rule to a named parameter with a sweep range around it. */
  const lift = (name?: string) => {
    const f = focus.current;
    if (!f) return toast.error("Put the cursor on a number in a rule first");
    const text = spec[f.role] as string;
    let a = f.start, b = f.end;
    if (a === b) { while (a > 0 && /[\d.]/.test(text[a - 1])) a--; while (b < text.length && /[\d.]/.test(text[b])) b++; }
    const raw = text.slice(a, b).trim(), v = Number(raw);
    if (!raw || !Number.isFinite(v)) return toast.error("No number at the cursor");
    if (!name || !/^[a-z_][a-z0-9_]*$/i.test(name)) return toast.error("Name: letters, digits and _");
    const step = Number.isInteger(v) ? Math.max(1, Math.round(v / 10)) : +(v / 10).toPrecision(2);
    edit({ [f.role]: text.slice(0, a) + name + text.slice(b), params: { ...spec.params, [name]: { value: v, min: +(v / 2).toPrecision(4), max: +(v * 2).toPrecision(4), step } } });
    toast.success(`${raw} is now ${name}`);
  };
  const [mine, setMine] = useState<{ name: string; rule: string; spec: Record<string, unknown> }[]>(() => { try { return JSON.parse(localStorage.getItem("studio:build:mytemplates") ?? "[]"); } catch { return []; } });
  const saveMine = (next: typeof mine) => { setMine(next); try { localStorage.setItem("studio:build:mytemplates", JSON.stringify(next)); } catch { /* private window */ } };
  const applyTemplate = (t: { spec: Record<string, unknown> }) => { edit({ ...BLANK, ...(t.spec as Partial<Spec>) }); setMode("formula"); };

  const params = Object.entries(spec.params);
  const sweep = params.reduce((n, [, p]) => (p.min != null && p.max != null && p.step ? n * (Math.floor((p.max - p.min) / p.step + 1e-9) + 1) : n), params.length ? 1 : 0);
  const blank = !loaded && !spec.code.trim() && ROLES.every(([r]) => !(spec[r] as string).trim());
  const findings = (role: string) => (blank ? [] : compiled?.findings.filter((f) => f.role === role) ?? []);
  const commands: Command[] = [
    ...(ui === "dev" ? devItems.map((d) => ({ ...d, run: () => window.dispatchEvent(new CustomEvent("studio:dev", { detail: d.id })) })) : []),
    ...(ui === "dev" ? [{ id: "line", group: "Go", label: "Go to line", ask: "Line number", run: (n?: string) => window.dispatchEvent(new CustomEvent("studio:dev", { detail: `line:${n}` })) }] : []),
    { id: "lift", group: "Edit", label: "Lift number to parameter", ask: "Parameter name for the number at the cursor", run: (n) => lift(n) },
    { id: "param", group: "Edit", label: "Add parameter", ask: "Parameter name", run: (n) => { if (n && /^[a-z_][a-z0-9_]*$/i.test(n)) edit({ params: { ...spec.params, [n]: { value: 0 } } }); } },
    ...(["blocks", "formula", "english"] as const).map((m) => ({ id: `mode-${m}`, group: "Mode", label: { blocks: "Blocks", formula: "Formula", english: "Plain English" }[m], run: () => { switchUi("simple"); switchMode(m); } })),
    { id: "ui-dev", group: "Mode", label: "Dev: Python IDE", run: () => switchUi("dev") },
    ...(ui === "dev" ? [{ id: "goto", group: "Debug", label: "Replay: go to date", ask: "Date (YYYY-MM-DD)", run: (d: string) => { if (/^\d{4}-\d{2}-\d{2}$/.test(d.trim())) window.dispatchEvent(new CustomEvent("studio:dev", { detail: `goto:${d.trim()}` })); } }] : []),
    ...(ui === "dev" ? ([["studio.quickrun", "Run", "Quick run (top 50, 5 years)", "⌘↵"], ["studio.fullrun", "Run", "Full run (recorded)", "⌘⇧↵"], ["studio.profile", "Run", "Profile the preview", ""], ["studio.tearsheet", "View", "Tearsheet", ""], ["studio.runs", "View", "Compare runs", ""], ["studio.robust", "Run", "Robustness: Monte Carlo on trades", ""], ["studio.chart", "View", "Chart with replay", ""], ["studio.cancel", "Run", "Cancel run", "Esc"],
      ["studio.debug", "Debug", "Start debugging", "F5"], ["studio.bp", "Debug", "Toggle breakpoint", "F9"], ["studio.step", "Debug", "Step one bar", "F10"], ["studio.stepback", "Debug", "Step back one bar", "⇧F10"],
      ["studio.layouts", "View", "Customise layouts", "⌘⇧\\"], ["studio.chartfirst", "View", "Chart first", ""], ["studio.panel", "View", "Toggle panel", "⌘J"], ["studio.rail", "View", "Toggle side bar", "⌘B"], ["studio.split", "View", "Split editor", "⌘\\"], ["studio.files", "View", "Go to file", "⌘P"], ["studio.search", "View", "Search project", "⌘⇧F"], ["studio.docs", "View", "Docs", "F1"],
      ["studio.back", "Go", "Back", "Ctrl -"], ["studio.fwd", "Go", "Forward", "Ctrl ⇧-"], ["studio.symproj", "Go", "Go to symbol in project", "⌘T"], ["studio.outline", "Go", "Go to symbol in file", "⌘⇧O"],
      ["studio.newfile", "Editor", "New file", ""], ["studio.snippet", "Editor", "Save selection as snippet", ""], ["studio.snippets", "Editor", "Insert snippet", "⌘⇧S"]] as const)
      .map(([cid, group, label, hint]) => ({ id: cid, group, label, hint: hint || undefined, run: () => window.dispatchEvent(new CustomEvent("studio:dev", { detail: cid })) })) : []),
    { id: "save", group: "Strategy", label: "Save version", hint: "⌘S", run: () => void save() },
    ...(ui === "simple" ? [{ id: "run", group: "Strategy", label: "Run backtest", hint: "⌘↵", run: () => void run() }] : []),
    { id: "new", group: "Strategy", label: "New blank strategy", run: () => router.push("/studio/build") },
    ...(templates.data ?? []).map((t) => ({ id: `t-${t.name}`, group: "Template", label: `${t.name}: ${t.rule}`, run: () => applyTemplate(t) })),
  ];
  const rp = prev?.repaint;
  const errors = compiled?.findings.filter((f) => f.severity === "error").length ?? 0;
  const checks: { ok: boolean | null; label: string; detail: string; go?: string }[] = [
    { ok: compiled ? errors === 0 : null, label: "Compiles", detail: errors ? `${errors} error${errors === 1 ? "" : "s"}` : compiled ? `${compiled.ms ?? 0} ms` : "checking" },
    { ok: prev?.status === "ok" ? (rp ? rp.changed === 0 : null) : null, label: "No look-ahead", detail: rp ? (rp.changed ? `changed at ${rp.changed} of ${rp.cuts} cuts` : `same at ${rp.cuts} cuts`) : "needs a preview" },
    { ok: prev?.status === "ok" ? prev.trades.length > 0 : null, label: "Signals fire", detail: prev?.status === "ok" ? `${prev.trades.length} trades on ${symbol.toUpperCase()}, ${years} years` : prev?.reason ?? "needs a preview" },
    { ok: prev?.status === "ok" && prev.trades.length >= 5 ? true : null, label: "Trades on one name", detail: prev?.status === "ok" ? (prev.trades.length >= 5 ? `${prev.trades.length}, enough to judge the rule here` : `${prev.trades.length}: judge it on the full universe`) : "—" },
    { ok: !(compiled?.findings.some((f) => f.role.startsWith("exit_")) ?? false), label: "Every entry has an exit", detail: compiled?.findings.find((f) => f.role.startsWith("exit_"))?.message ?? "stop, target or rule set", go: "exits" },
    { ok: !(compiled?.findings.some((f) => f.role === "params") ?? false), label: "Parameters used", detail: compiled?.findings.filter((f) => f.role === "params").map((f) => f.token).join(", ") || "all used", go: "params" },
  ];

  const checkList = (
            <ul className="bd-checks">
              {checks.map((c) => (
                <li key={c.label} className={c.ok === null ? "" : c.ok ? "ok" : "bad"}>
                  <span className="bd-check-icon">{c.ok === null ? <CircleDashed aria-label="Pending" /> : c.ok ? <CircleCheck aria-label="Passed" /> : <CircleX aria-label="Failed" />}</span><b>{c.label}</b>
                  {c.go && c.ok === false ? <button className="bd-link" onClick={() => document.getElementById(`bd-${c.go}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}>{c.detail}</button> : <span>{c.detail}</span>}
                </li>
              ))}
            </ul>
  );
  const side = (
    <>
          <section className="bd-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h3 style={{ flex: 1 }}>Preview</h3>
              <label className="bd-auto" title="Preview after each edit"><input type="checkbox" checked={auto} onChange={(e) => { setAuto(e.target.checked); try { localStorage.setItem("studio:build:auto", e.target.checked ? "on" : "off"); } catch { /* blocked */ } }} />Auto</label>
              {!auto || stale ? <button className="btn sm" onClick={() => setNudge((n) => n + 1)}>Preview</button> : null}
              <input className="input" aria-label="Preview symbol" style={{ width: 90 }} value={symbol} onChange={(e) => setSymbol(e.target.value)} />
              <select className="input" aria-label="Preview window" style={{ width: "auto" }} value={years} onChange={(e) => setYears(+e.target.value)}>{[1, 2, 3, 5].map((y) => <option key={y} value={y}>{y}y</option>)}</select>
            </div>
            {stale ? <p className="bd-find warning" style={{ margin: 0 }}><b>Edited</b>since this preview</p> : null}
            {prev?.invariants?.count ? <p className="bd-find error" style={{ margin: 0 }}><b>Invariant</b>broken on {prev.invariants.count} bar{prev.invariants.count === 1 ? "" : "s"}; Validate will fail</p> : null}
            {prev?.status === "ok" ? (
              <>
                <p className="bd-meta" style={{ margin: 0 }}>{prev.trades.length} trades · {`${(prev.total_return ?? 0) >= 0 ? "+" : ""}${((prev.total_return ?? 0) * 100).toFixed(1)}%`} · last {years} years before the hold-out</p>
                {prev.repaint ? <p className={`bd-find ${prev.repaint.changed ? "error" : ""}`}><b style={{ color: prev.repaint.changed ? undefined : "var(--up)" }}>{prev.repaint.changed ? "Repaints" : "No look-ahead"}</b>
                  {prev.repaint.changed ? `signals changed at ${prev.repaint.changed} of ${prev.repaint.cuts} cuts (${prev.repaint.dates.join(", ")})` : `same signals at ${prev.repaint.cuts} history cuts`}</p> : null}
                {Object.keys(prev.bars_by_symbol ?? {}).length > 1 ? <div className="dv-chips">{Object.keys(prev.bars_by_symbol!).map((x) => <button key={x} className="pill" aria-pressed={(chartSym || prev.symbols![0]) === x} onClick={() => setChartSym(x)}>{x}</button>)}</div> : null}
                <TimeSeries data={prev.bars_by_symbol?.[chartSym || prev.symbols?.[0] || ""] ?? prev.bars} series={[{ key: "close", label: (chartSym || prev.symbols?.[0] || symbol).toUpperCase(), color: "var(--text-2)" }]} height={ui === "dev" ? 300 : 180} legend={false}
                  markers={prev.invariants?.rows.length ? [...prev.invariants.rows.filter((r) => !r.symbol || r.symbol === symbol.toUpperCase()).map((r) => ({ date: r.date, label: "!", color: "var(--down)" })), ...prev.trades.flatMap((t) => [{ date: t.entry_date, label: "▲", color: "var(--up)" }])] : pausedAt && ui === "dev" ? [{ date: pausedAt, label: pausedLabel, color: "var(--warn)" }, ...prev.trades.flatMap((t) => [{ date: t.entry_date, label: "▲", color: "var(--up)" }, { date: t.exit_date, label: "×", color: "var(--down)" }])] : fired ? fired.dates.map((d) => ({ date: d, label: "●", color: "var(--accent)" })) : prev.trades.flatMap((t) => [{ date: t.entry_date, label: t.side === "long" ? "▲" : "▼", color: "var(--up)" }, { date: t.exit_date, label: "×", color: "var(--down)" }])} />
                {fired ? <p className="bd-meta" style={{ margin: 0 }}>{ROLES.find((r) => r[0] === fired.role)?.[1]}: {fired.dates.length} bars marked <button className="bd-link" onClick={() => setFired(null)}>Show trades</button></p> : null}
              </>
            ) : <div className="st-skip">{prev?.reason ? `${prev.status === "error" ? "error" : "skipped"}: ${prev.reason}` : "—"}</div>}
          </section>
          {ui === "dev" ? <details className="bd-card dv-preview-details" open>
            <summary>Checks</summary>
            {checkList}
          </details> : <section className="bd-card"><h3>Checks</h3>{checkList}</section>}
          {ui === "dev" ? <details className="bd-card dv-preview-details">
            <summary>What it does</summary>
            <p className="bd-desc">{compiled?.description || "—"}</p>
          </details> : <section className="bd-card"><h3>What it does</h3><p className="bd-desc">{compiled?.description || "—"}</p></section>}
    </>
  );
  const paramsCard = (
          <section className="bd-card" id="bd-params">
            <h3>Parameters</h3>
            {params.map(([k, p]) => (
              <div key={k} className="bd-param">
                <code>{k}</code>
                <Num label="Value" value={p.value} onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, value: v ?? 0 } } })} />
                <Num label="Min" value={p.min} empty onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, min: v } } })} />
                <Num label="Max" value={p.max} empty onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, max: v } } })} />
                <Num label="Step" value={p.step} empty onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, step: v } } })} />
                <label className="bd-num" title="Search on a log scale"><span>Log</span><input type="checkbox" checked={!!p.log} onChange={(e) => edit({ params: { ...spec.params, [k]: { ...p, log: e.target.checked } } })} /></label>
                <button className="btn sm" aria-label={`Remove ${k}`} onClick={() => { const { [k]: _, ...rest } = spec.params; edit({ params: rest }); }}><Trash2 size={12} /></button>
              </div>
            ))}
            {Object.entries(compiled?.parameters ?? {}).filter(([k]) => !(k in spec.params)).map(([k, p]) => (
              <div key={k} className="bd-param bd-param-code"><code>{k}</code><span>{p.value}</span><span>{p.min ?? "—"}</span><span>{p.max ?? "—"}</span><span>{p.step ?? "—"}</span><i>in code</i></div>
            ))}
            {sweep ? <p className="bd-meta" style={{ margin: 0 }}>{sweep.toLocaleString()} settings in a full sweep</p> : null}
            <button className="btn sm" onClick={() => setPalette(true)}><Plus size={12} />Parameter</button>
          </section>
  );
  const savedState: Saved = saving === "saving" ? "saving" : saving === "conflict" ? "conflict" : !loaded ? "new" : dirty ? "draft" : "saved";
  const compileProblems: Problem[] = (compiled?.findings ?? []).filter((f) => f.role === "code").map((f) => ({ severity: f.severity, file: "main.py", line: Math.max(1, f.line), column: f.start + 1, end_column: Math.max(f.end, f.start + 1) + 1, code: "compile", message: f.message }));

  const nameInput = <input className="bd-name" aria-label="Strategy name" value={spec.name} onChange={(e) => edit({ name: e.target.value })} />;
  const versionControls = (
    <>
        {loaded && loaded.versions.length > 1 ? (
          <select className="input" aria-label="Version" value={loaded.version} onChange={(e) => void load(loaded.id, Number(e.target.value))}>
            {[...loaded.versions].reverse().map((v) => <option key={v.version} value={v.version}>v{v.version} · {new Date(v.created * 1000).toLocaleDateString()} · {v.actor}</option>)}
          </select>
        ) : null}
        {loaded && loaded.versions.length > 1 ? (
          <select className="input" aria-label="Compare with" value={diff?.version ?? ""} onChange={(e) => {
            const v = Number(e.target.value); if (!v) return setDiff(null);
            void studio<Loaded>("GET", `/strategies/${loaded.id}?version=${v}`).then((o) => setDiff({ version: v, rows: specDiff(o.spec, spec) }), fail);
          }}>
            <option value="">Compare with…</option>
            {[...loaded.versions].reverse().map((v) => <option key={v.version} value={v.version}>v{v.version}</option>)}
          </select>
        ) : null}
    </>
  );
  // Project actions: the Simple page's More menu and the Dev settings window's Project page.
  const projectActions: [ReactNode, string, boolean, () => void][] = [
    [<Link2 key="l" size={13} />, "Copy read-only link", !loaded || !!readOnly, () => { if (loaded) void studio<{ token: string }>("POST", `/strategies/${loaded.id}/share`).then((r) => { const u = `${location.origin}/studio/build?share=${r.token}`; void copyText(u, "Read-only link copied"); }, fail); }],
    [<GitBranch key="b" size={13} />, `Branch from v${loaded?.version ?? 1}`, !loaded || !!readOnly, () => { if (loaded) void studio<{ id: string }>("POST", `/strategies/${loaded.id}/versions/${loaded.version}/branch`).then((b) => router.push(`/studio/build/${b.id}`), fail); }],
    [<Download key="d" size={13} />, "Export project (.zip)", !loaded, () => { if (loaded) window.location.assign(`${STUDIO_BASE}/strategies/${loaded.id}/export.zip`); }],
    [<Upload key="u" size={13} />, "Import project (.zip)", !!readOnly, () => zipInput.current?.click()],
    [<GitMerge key="m" size={13} />, "Compare and merge…", !loaded || !!readOnly, () => setDialog("branches")],
    [<BookmarkPlus key="t" size={13} />, "Save as my template", blank || !!readOnly, () => { const name = spec.name || "Untitled"; saveMine([{ name, rule: String(spec.entry ?? ""), spec: { ...spec } }, ...mine.filter((t) => t.name !== name)].slice(0, 24)); toast.success(`Saved "${name}" as a template`); }],
  ];
  const projectPage = (
    <>
      <h3>Strategy</h3>
      <div className="bd-nums"><div className="bd-num"><span>Name</span>{nameInput}</div><div className="bd-num"><span>Version</span><div className="bd-menu-fields">{versionControls}</div></div></div>
      <h3>Actions</h3>
      <div className="bd-nums">{projectActions.map(([icon, label, off, go]) => <div key={label} className="bd-num"><span>{label}</span><button type="button" className="btn sm" disabled={off} title={off ? (readOnly ? "Read-only" : "Save the strategy first") : undefined} onClick={go}>{icon}{label.split(" ")[0]}</button></div>)}</div>
    </>
  );
  const headRight = (
    <>
        {ui === "dev" ? null : versionControls}
        <span className="bd-ui"><Segmented<"simple" | "dev"> label="Interface" value={ui} onChange={switchUi} options={[{ value: "simple", label: "Simple" }, { value: "dev", label: "Dev" }]} /></span>
        {/* Dev keeps ⌘⇧P and the header search; the button would be a third way in. */}
        {ui === "dev" ? null : <button className="btn" title="Commands (⌘⇧P)" aria-label="Commands" onClick={() => setPalette(true)}><CommandIcon size={14} />Commands<kbd>⌘⇧P</kbd></button>}
        {ui === "dev" ? null : <button className="btn icon" aria-label="More" aria-haspopup="menu" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMore({ x: r.right - 220, y: r.bottom + 4 }); }}><MoreHorizontal size={15} /></button>}
        <PopMenu at={more} onClose={() => setMore(null)} width={220}>
          {projectActions.map(([icon, label, off, go]) => <MenuItem key={label} icon={icon} disabled={off} onClick={() => { setMore(null); go(); }}>{label}</MenuItem>)}
          <MenuItem icon={<Settings2 size={13} />} onClick={() => { setMore(null); setDialog("customise"); }}>Settings…</MenuItem>
        </PopMenu>
        <input ref={zipInput} type="file" accept=".zip,application/zip" hidden onChange={(e) => {
          const f = e.target.files?.[0]; e.target.value = ""; if (!f) return;
          void fetch(`${STUDIO_BASE}/strategies/import-zip?name=${encodeURIComponent(f.name.replace(/\.zip$/i, ""))}`, { method: "POST", headers: { "Content-Type": "application/zip" }, body: f })
            .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail?.message ?? j.detail ?? "Import failed"); router.push(`/studio/build/${j.id}?ui=dev`); }).catch(fail);
        }} />
        <button className={ui === "dev" ? "btn icon" : "btn"} title="Save (⌘S)" aria-label="Save" onClick={() => void save()}><Save size={14} />{ui === "dev" ? null : <>Save<kbd>⌘S</kbd></>}</button>
        {ui === "dev" ? null : <button className="btn primary" disabled={!compiled?.ok} onClick={() => void run()}><Play size={14} />Run backtest<kbd>⌘↵</kbd></button>}
    </>
  );

  return (
    <div className="bd" data-ui={ui}>
      {ui === "dev" ? null : (
      <header className="bd-head">
        {nameInput}
        <span className="bd-meta">{loaded ? `v${loaded.latest}${dirty ? " · draft" : " · saved"}` : "new"}{compiled?.ms !== undefined ? ` · compiled in ${compiled.ms} ms` : ""}</span>
        {loaded ? <TrialChip ledger={loaded.trials} strategyId={loaded.id} /> : null}
        <span style={{ flex: 1 }} />
        {headRight}
      </header>)}

      <Palette open={palette} onClose={() => setPalette(false)} commands={commands} seed={seed} />
      {dialog === "branches" && loaded ? <BranchDialog id={loaded.id} name={spec.name} spec={spec} onClose={() => setDialog(null)} onMerged={(t) => router.push(`/studio/build/${t}`)} /> : null}
      {dialog === "customise" ? <CustomiseDialog spec={spec} onClose={() => setDialog(null)} /> : null}
      {recover ? (
        <div className="bd-ro" role="status"><b>Unsaved edits</b><span>from this browser, {new Date(recover.at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
          <button className="btn sm primary" onClick={() => { edit(recover.spec); setRecover(null); }}>Restore</button>
          <button className="btn sm" onClick={() => { try { localStorage.removeItem(backupKey); } catch { /* blocked */ } setRecover(null); }}>Discard</button></div>
      ) : null}
      {readOnly ? (
        <div className="bd-ro" role="status">
          {readOnly.kind === "lease" ? <><b>Read-only</b><span>open for editing in another tab since {new Date(readOnly.since * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><button className="btn sm primary" onClick={() => takeLease(true)}>Take over</button></>
            : <><b>Shared, read-only</b><span>{spec.name}</span><button className="btn sm primary" onClick={() => void studio<{ id: string }>("POST", `/share/${readOnly.token}/fork`).then((s) => { window.location.assign(`/studio/build/${s.id}?ui=dev`); }, fail)}>Fork to edit</button></>}
        </div>
      ) : null}
      {ui === "simple" && blank && templates.data ? (
        <section className="bd-card">
          <h3>Start from</h3>
          <div className="bd-tpls">
            {mine.map((t) => (
              <div key={`m-${t.name}`} className="bd-tpl-mine"><button type="button" className="bd-tpl" onClick={() => applyTemplate(t)}><b>{t.name}</b><span>{t.rule}</span></button>
                <button type="button" className="icon-btn" aria-label={`Delete template ${t.name}`} onClick={() => saveMine(mine.filter((x) => x !== t))}><Trash2 size={12} /></button></div>
            ))}
            {templates.data.map((t) => (
              <button key={t.name} className="bd-tpl" onClick={() => applyTemplate(t)}><b>{t.name}</b><span>{t.rule}</span><TplStat name={t.name} /></button>
            ))}
          </div>
        </section>
      ) : null}
      {diff ? (
        <section className="bd-card">
          <h3>v{diff.version} → this draft {diff.rows.length ? `· ${diff.rows.length} change${diff.rows.length === 1 ? "" : "s"}` : "· no changes"}</h3>
          {diff.rows.map(([k, a, b]) => <div key={k} className="bd-diff"><span>{k}</span><del>{a || "—"}</del><ins>{b || "—"}</ins></div>)}
          {loaded ? (() => {
            const ra = loaded.runs_by_version[diff.version], rb = loaded.runs_by_version[loaded.version];
            const cell = (r?: RunSum) => (r ? `${(r.total_return ?? 0) >= 0 ? "+" : ""}${((r.total_return ?? 0) * 100).toFixed(1)}% · Sharpe ${r.sharpe?.toFixed(2) ?? "—"} · ${r.trades ?? "—"} trades` : "not run");
            return <div className="bd-diff"><span>backtest</span><del>{cell(ra)}</del><ins>{`v${loaded.version}: ${cell(rb)}`}</ins></div>;
          })() : null}
        </section>
      ) : null}
      {ui === "dev" ? <DevIDE tools={headRight} settings={(extra, start, close) => <CustomiseDialog spec={spec} onClose={close} start={start} sections={[...extra, ["Project", projectPage]]} font={font} onFont={(v) => { setFont(v); try { localStorage.setItem("studio:dev:font", String(v)); } catch { /* blocked */ } }} />} canRun={!!spec.code.trim() || ROLES.some(([role]) => !!String(spec[role] ?? "").trim())} starting={starting} onPreview={() => setNudge((n) => n + 1)} spec={spec} edit={edit} symbol={symbol} prev={prev} side={<>{side}{paramsCard}</>} onSave={formatSave} compileProblems={compileProblems}
        strategyId={loaded?.id} versions={loaded?.versions ?? []} runs={loaded?.runs_by_version ?? {}} saved={savedState} readOnly={!!readOnly} version={loaded?.version} stale={stale} onPause={(d, l) => { setPausedAt(d); setPausedLabel(l ?? "❚❚"); }} font={font} savedFiles={loaded ? { "main.py": (loaded.spec as Spec).code ?? "", ...(((loaded.spec as Spec).files as Record<string, string>) ?? {}) } : undefined} quick={quick} onQuickRun={(l, st) => void quickRun(l, st)} logpoints={logpoints} onLogpoints={setLogpoints} coverage={coverage} onCoverage={setCoverage} onCancel={cancelRun} trial={loaded ? <TrialChip ledger={loaded.trials} strategyId={loaded.id} /> : null} onReload={() => loaded && void load(loaded.id)} /> : <div className="bd-grid" data-compact={readDefaults().compact || undefined} data-plain={readDefaults().plain || undefined}>
        <section className="bd-card bd-rules">
          <div className="bd-modes" role="tablist">
            {(["blocks", "formula", "english"] as const).map((m) => <button key={m} role="tab" aria-selected={mode === m && !spec.code.trim()} className={`btn sm${mode === m && !spec.code.trim() ? " on" : ""}`} onClick={() => switchMode(m)}>{{ blocks: "Blocks", formula: "Formula", english: "Plain English" }[m]}</button>)}
            <button role="tab" aria-selected={!!spec.code.trim()} className={`btn sm${spec.code.trim() ? " on" : ""}`} onClick={() => switchUi("dev")}>Python</button>
            {compiled?.complexity ? <span className="bd-cx" title="Parameters, rules and the parameters a sweep can tune">{compiled.complexity.parameter_count} params · {compiled.complexity.formula_rule_count} rules · <b data-high={compiled.complexity.degrees_of_freedom > 8 || undefined}>{compiled.complexity.degrees_of_freedom} degrees of freedom</b></span> : null}
            {spec.code.trim() ? <span className="bd-find warning" style={{ marginLeft: "auto" }}><b>Python runs</b>rules below are kept, not used<button className="btn sm" onClick={() => switchUi("dev")}>Open in Dev</button><button className="btn sm" onClick={() => edit({ code: "", files: {} })}>Use rules</button></span> : null}
          </div>
          {mode === "english" ? (
            <div className="bd-rule">
              <textarea className="input" rows={3} aria-label="Describe the strategy" placeholder="buy when the 50 day sma crosses above the 200 day sma; sell when rsi(2) above 70; stop 8%" value={english}
                onChange={(e) => setEnglish(e.target.value)} />
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn sm" disabled={!english.trim()} onClick={() => void studio<{ fields: Record<string, string>; exits: Record<string, number>; unmatched: string[] }>("POST", "/plain-english", { text: english }).then(setProposal, (e) => setProposal({ error: e instanceof Error ? e.message : "Failed" }))}>Translate</button>
                {proposal && !("error" in proposal) ? <button className="btn sm primary" onClick={() => { edit({ ...proposal.fields, exits: { ...spec.exits, ...proposal.exits } }); setProposal(null); setMode("formula"); }}>Use this rule</button> : null}
              </div>
              {proposal && "error" in proposal ? <p className="bd-find error"><b>Not understood</b>{proposal.error}</p> : null}
              {proposal && !("error" in proposal) ? (
                <div className="bd-proposal">
                  <p className="bd-said">{(() => {
                    const marks = [...(proposal.assumptions ?? []).map((a) => ({ ...a, kind: "assumed" })), ...proposal.unmatched.flatMap((w) => { const i = english.toLowerCase().indexOf(w.toLowerCase()); return i < 0 ? [] : [{ word: w, start: i, end: i + w.length, meaning: "not understood", formula: "", kind: "ignored" }]; })].sort((a, b) => a.start - b.start);
                    const out: React.ReactNode[] = []; let at = 0;
                    for (const m of marks) { if (m.start < at) continue; out.push(english.slice(at, m.start)); out.push(<mark key={m.start} data-kind={m.kind} title={m.formula ? `${m.meaning}: ${m.formula}` : m.meaning}>{english.slice(m.start, m.end)}</mark>); at = m.end; }
                    out.push(english.slice(at)); return out;
                  })()}</p>
                  {proposal.assumptions?.length ? proposal.assumptions.map((a) => <p key={a.start}><span>“{a.word}” read as</span><code>{a.formula}</code></p>) : null}
                  {Object.entries(proposal.fields).map(([k, v]) => <div key={k} className="bd-rule"><span>{ROLES.find((r) => r[0] === k)?.[1]}</span>
                    <GroupEditor id={`p-${k}`} group={toGroup(v) ?? { op: "all", items: [{ rule: v, enabled: true }] }} suggestions={catalogue} onChange={(g) => setProposal({ ...proposal, fields: { ...proposal.fields, [k]: groupFormula(g) } })} /></div>)}
                  {proposal.restated ? <p className="bd-desc">{proposal.restated}</p> : null}
                  {Object.entries(proposal.exits).map(([k, v]) => <p key={k}><span>{EXITS.find((r) => r[0] === k)?.[1]}</span><code>{k === "time_stop" ? `${v} bars` : `${+(v * 100).toFixed(2)}%`}</code></p>)}
                  {proposal.unmatched.length ? <p className="bd-find warning"><b>Ignored</b>{proposal.unmatched.join(", ")}</p> : null}
                </div>
              ) : null}
            </div>
          ) : null}
          {ROLES.map(([role, label]) => {
            if (mode === "english") return null;
            const groups = (spec.groups ?? {}) as Record<string, Group>;
            const tree: Group | null = mode === "blocks" && role !== "score" && role !== "scale_in" ? groups[role] ?? toGroup(spec[role] as string) ?? { op: "all", items: [{ rule: spec[role] as string, enabled: true }] } : null;
            const dropGroup = () => { const { [role]: _, ...rest } = groups; return rest; };
            return (
            <div key={role} className="bd-rule" data-role={role}>
              <label htmlFor={`r-${role}`}>{label}</label>
              {tree ? <GroupEditor id={`b-${role}`} group={tree} suggestions={catalogue} onChange={(g) => edit({ [role]: groupFormula(g), groups: { ...groups, [role]: g } })} /> : null}
              {tree ? null : <textarea id={`r-${role}`} className="input" spellCheck={false} rows={role === "score" || role === "market_filter" || role === "scale_in" ? 1 : 2} placeholder={role === "market_filter" ? "market > sma(market, 200)" : undefined} value={spec[role] as string} onSelect={track(role)} onFocus={track(role)} onChange={(e) => edit({ [role]: e.target.value, ...(role in groups ? { groups: dropGroup() } : {}) })} />}
              {role === "scale_in" && spec.scale_in.trim() ? (
                <label className="bd-num"><span>Max fills</span><input className="input" type="number" min={1} max={20} aria-label="Most fills that build one position" style={{ width: 80 }} value={spec.max_entries ?? 3} onChange={(e) => edit({ max_entries: Math.max(1, Math.min(20, Number(e.target.value) || 1)) })} /></label>
              ) : null}
              {role === "market_filter" && spec.market_filter.trim() ? (
                <label className="bd-num"><span>Else hold</span><input className="input" aria-label="Symbol held while the market rule is false" placeholder="cash" style={{ width: 110 }} value={spec.defensive ?? ""} onChange={(e) => edit({ defensive: e.target.value.toUpperCase() })} /></label>
              ) : null}
              {findings(role).map((f, i) => <p key={i} className={`bd-find ${f.severity}`}><b>{f.severity === "error" ? "Error" : "Warning"}</b>{f.token ? <code>{f.token}</code> : null}{f.message}</p>)}
              {(() => {
                const c = conds[role];
                if (!c || !(spec[role] as string).trim() || role === "score") return null;
                if ("error" in c) return null;
                const on = fired?.role === role;
                return (
                  <p className={`bd-cond${c.constant !== null ? " warn" : ""}`}>
                    {c.constant === true ? <b>Always true on {symbol.toUpperCase()}</b> : c.constant === false ? <b>Never true on {symbol.toUpperCase()}</b> : null}
                    <span>true on {c.true_rate === null ? "—" : `${(c.true_rate * 100).toFixed(c.true_rate < 0.01 ? 2 : 0)}%`} of {c.observations} bars{c.last_true_date ? ` · last ${c.last_true_date}` : ""}</span>
                    {c.fired_dates.length ? <button className="bd-link" aria-pressed={on} onClick={() => setFired(on ? null : { role, dates: c.fired_dates })}>{on ? "Hide on chart" : "Show on chart"}</button> : null}
                  </p>
                );
              })()}
            </div>
          ); })}
          {[...findings("spec"), ...findings("blocks")].map((f, i) => <p key={i} className={`bd-find ${f.severity}`}><b>{f.severity === "error" ? "Error" : "Warning"}</b>{f.message}</p>)}
          <details className="bd-more bd-py" onToggle={(e) => { if ((e.currentTarget as HTMLDetailsElement).open && pyView === null) setPyView(""); }}>
            <summary>Python</summary>
            <pre className="bd-code">{pyView || "…"}</pre>
            <button className="btn sm" onClick={() => switchUi("dev")}>Open in Dev</button>
          </details>
          <details className="bd-more">
            <summary>Functions</summary>
            <input className="input" placeholder="Search" aria-label="Search functions" value={refQ} onChange={(e) => setRefQ(e.target.value)} />
            <div className="bd-ref">
              {reference.filter((r) => !refQ || `${r.name} ${r.doc}`.toLowerCase().includes(refQ.toLowerCase())).map((r) => (
                <button key={r.name} className="bd-refrow" title="Insert at the cursor" onClick={() => {
                  const f = focus.current, text = r.example ?? r.name;
                  if (!f) return void copyText(text);
                  const cur = spec[f.role] as string;
                  edit({ [f.role]: cur.slice(0, f.start) + text + cur.slice(f.end) });
                }}><code>{r.args ? `${r.name}(${r.args.join(", ")})` : r.name}</code><span>{r.doc}</span></button>
              ))}
            </div>
          </details>
        </section>

        <aside className="bd-side">{side}{paramsCard}</aside>

        <section className="bd-card" id="bd-exits">
          <h3>Exits</h3>
          <div className="bd-nums">{EXITS.map(([k, l, p]) => <Num key={k} label={l} pct={p} value={spec.exits[k]} onChange={(v) => edit({ exits: { ...spec.exits, [k]: v ?? 0 } })} />)}</div>
        </section>
        <section className="bd-card">
          <h3>Sizing</h3>
          <div className="bd-nums">
            <label className="bd-num"><span>Mode</span>
              <select className="input" value={spec.sizing.mode} onChange={(e) => edit({ sizing: { ...spec.sizing, mode: e.target.value } })}>
                <option value="equal">Equal</option><option value="pct_equity">% of equity</option><option value="risk">Risk per trade</option><option value="vol_target">Vol target</option><option value="score">Weight by score</option><option value="kelly">Kelly (capped)</option><option value="cash">Fixed $</option><option value="shares">Fixed shares</option>
              </select>
            </label>
            {spec.sizing.mode !== "equal" && spec.sizing.mode !== "score" ? <Num label={spec.sizing.mode === "shares" ? "Shares" : spec.sizing.mode === "cash" ? "Dollars" : spec.sizing.mode === "vol_target" ? "Annual vol" : spec.sizing.mode === "kelly" ? "Cap" : "Percent"} pct={["pct_equity", "risk", "vol_target", "kelly"].includes(spec.sizing.mode)}
              value={spec.sizing.value} onChange={(v) => edit({ sizing: { ...spec.sizing, value: v ?? 0 } })} /> : null}
            <Num label="Max positions" value={spec.sizing.max_positions} onChange={(v) => edit({ sizing: { ...spec.sizing, max_positions: v ?? 0 } })} />
          </div>
        </section>
        <section className="bd-card">
          <h3>My limits</h3>
          <div className="bd-nums">{LIMITS.map(([k, l, p]) => <Num key={k} label={l} pct={p} empty value={spec.limits[k]} onChange={(v) => edit({ limits: { ...spec.limits, [k]: v } })} />)}</div>
        </section>
        <section className="bd-card">
          <h3>Notes</h3>
          <label className="bd-rule"><span>Hypothesis</span><textarea className="input" rows={2} value={spec.hypothesis} onChange={(e) => edit({ hypothesis: e.target.value })} /></label>
          <label className="bd-rule"><span>Regime it should work in{loaded?.regime_written_after ? <b className="chip warn" style={{ marginLeft: 8 }}>written after a backtest</b> : null}</span><input className="input" value={spec.regime_claim} onChange={(e) => edit({ regime_claim: e.target.value })} /></label>
          <label className="bd-rule"><span>Decisions</span><textarea className="input" rows={3} value={spec.notes} onChange={(e) => edit({ notes: e.target.value })} /></label>
        </section>
      </div>}
    </div>
  );
}

const NAV_ICONS: Record<string, ReactNode> = { General: <SlidersHorizontal size={16} />, Editor: <Code2 size={16} />, Appearance: <PaletteIcon size={16} />, Layout: <LayoutPanelLeft size={16} />, Run: <PlayCircle size={16} />, Project: <FolderGit2 size={16} />, Keybindings: <Keyboard size={16} />, Profiles: <Bookmark size={16} />, "New strategy": <FilePlus2 size={16} /> };

/** The one settings window (T3 Code style): a page per area on the left, Build defaults, editor, keys and new-strategy defaults here, Dev adds appearance, layout, run and project pages. */
function CustomiseDialog({ spec, onClose, sections = [], start, font, onFont }: { spec: Spec; onClose: () => void; sections?: [string, ReactNode][]; start?: string; font?: number; onFont?: (v: number) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [d, setD] = useState<Partial<Defaults>>(readDefaults);
  const [kq, setKq] = useState("");
  const [q, setQ] = useState("");
  const [json, setJson] = useState<string | null>(null); // raw JSON view of the settings while editing
  const own = ["General", "Editor", "Keybindings", "New strategy", "Profiles"];
  const pages = [...own.slice(0, 2), ...sections.map(([n]) => n), ...own.slice(2)];
  const [page, setPage] = useState(start && pages.includes(start) ? start : pages[0]!);
  const body = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  // Search: hide every setting whose label does not match.
  useEffect(() => { for (const el of body.current?.querySelectorAll<HTMLElement>(".bd-num, h3") ?? []) el.hidden = !!q && !el.textContent?.toLowerCase().includes(q.toLowerCase()); }, [q, json, page]);
  const [profiles, setProfiles] = useState<Profile[]>(() => { try { return JSON.parse(localStorage.getItem("studio:build:profiles") ?? "[]"); } catch { return []; } });
  useEffect(() => { try { localStorage.setItem("studio:build:profiles", JSON.stringify(profiles)); } catch { /* blocked */ } }, [profiles]);
  useServerPref("profiles", profiles, setProfiles);
  const save = () => { writeDefaults(d); toast.success("Settings saved"); ref.current?.close(); };
  const fromJson = (text: string) => { try { const v: unknown = JSON.parse(text); if (!v || typeof v !== "object" || Array.isArray(v)) throw new Error("Settings must be a JSON object"); setD(v as Partial<Defaults>); setJson(null); } catch (e) { toast.error((e as Error).message); } };
  // A profile is everything in this window under one name: defaults, shortcuts, theme, appearance, run configurations, layouts, font.
  const saveProfile = (name: string) => {
    const keys: Record<string, string> = {}; for (const k of PROFILE_KEYS) { try { const v = localStorage.getItem(k); if (v !== null) keys[k] = v; } catch { /* blocked */ } }
    setProfiles((p) => [...p.filter((x) => x.name !== name), { name, defaults: d, keys }]);
    toast.success(`Saved profile ${name}`);
  };
  const applyProfile = (p: Profile) => {
    writeDefaults(p.defaults);
    try { if (p.layouts) localStorage.setItem("studio:dev:workspaces", JSON.stringify(p.layouts)); for (const [k, v] of Object.entries(p.keys ?? {})) localStorage.setItem(k, v); } catch { /* blocked */ }
    window.location.reload();
  };
  const exits = { ...BLANK.exits, ...d.exits }, sizing = { ...BLANK.sizing, ...d.sizing };
  const show = (n: string) => !!q || page === n;
  return (
    <dialog ref={ref} className="sh-import bd-set" aria-label="Settings" onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <nav className="bd-set-nav" aria-label="Settings pages">
        <label className="bd-set-search"><Search size={15} /><input type="search" aria-label="Search settings" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} /><kbd>/</kbd></label>
        {pages.map((n) => <button key={n} type="button" aria-current={!q && page === n ? "page" : undefined} onClick={() => { setQ(""); setJson(null); setPage(n); }}>{NAV_ICONS[n] ?? <SlidersHorizontal size={16} />}{n}</button>)}
        <span style={{ flex: 1 }} />
        <button type="button" onClick={() => ref.current?.close()}><ArrowLeft size={16} />Back</button>
      </nav>
      <div className="bd-set-main">
      <div className="bd-set-hd"><span className="bd-set-crumb">Settings <i>/</i> <b>{q ? "Search" : page}</b></span>
        <button className="bd-set-link" aria-pressed={json !== null} onClick={() => setJson(json === null ? JSON.stringify(d, null, 2) : null)}>JSON</button>
        <button className="bd-set-link" onClick={() => setD({})}><RotateCcw size={14} />Restore defaults</button></div>
      {json !== null ? <><textarea className="input bd-json" aria-label="Settings JSON" spellCheck={false} value={json} onChange={(e) => setJson(e.target.value)} /><button className="btn sm" onClick={() => fromJson(json)}>Apply JSON</button></> : null}
      <div ref={body} hidden={json !== null} className="bd-set-body"><div className="bd-set-col">
      {show("General") ? <div className="bd-nums">
        <label className="bd-num"><span>Open in</span><Segmented<"simple" | "dev"> label="Default interface" value={d.ui ?? "simple"} onChange={(ui) => setD({ ...d, ui })} options={[{ value: "simple", label: "Simple" }, { value: "dev", label: "Dev" }]} /></label>
        <label className="bd-num"><span>Simple starts in</span><select className="input" value={d.mode ?? "formula"} onChange={(e) => setD({ ...d, mode: e.target.value as Defaults["mode"] })}><option value="blocks">Blocks</option><option value="formula">Formula</option><option value="english">Plain English</option></select></label>
        <label className="bd-num"><span>Blocks</span><Segmented<"full" | "compact"> label="Block density" value={d.compact ? "compact" : "full"} onChange={(v) => setD({ ...d, compact: v === "compact" })} options={[{ value: "full", label: "Expanded" }, { value: "compact", label: "Compact" }]} /></label>
        <label className="bd-num"><span>Colour by role</span><input type="checkbox" checked={!d.plain} onChange={(e) => setD({ ...d, plain: !e.target.checked })} /></label>
        <div className="bd-num"><span>Condition order</span><ol className="bd-palette">{(d.palette?.length ? paletteOrder().sort((a, b) => d.palette!.indexOf(a[1]) - d.palette!.indexOf(b[1])) : paletteOrder()).map(([, l], i, all) => (
          <li key={l}>{l}<button type="button" className="icon-btn" aria-label={`Move ${l} up`} disabled={!i} onClick={() => { const n = all.map(([, x]) => x); [n[i - 1], n[i]] = [n[i], n[i - 1]]; setD({ ...d, palette: n }); }}><ArrowUp size={14} /></button></li>))}</ol></div>
      </div> : null}
      {show("Editor") ? <div className="bd-nums">
        <label className="bd-num"><span>Editor word wrap</span><input type="checkbox" checked={d.wrap !== false} onChange={(e) => setD({ ...d, wrap: e.target.checked })} /></label>
        <label className="bd-num"><span>Editor rulers</span><Segmented<number> label="Editor rulers" value={d.rulers ?? 0} onChange={(rulers) => setD({ ...d, rulers })} options={[0, 80, 100, 120].map((v) => ({ value: v, label: v ? String(v) : "None" }))} /></label>
        <label className="bd-num"><span>Editor minimap</span><input type="checkbox" checked={!!d.minimap} onChange={(e) => setD({ ...d, minimap: e.target.checked })} /></label>
        <label className="bd-num"><span>Editor ligatures</span><input type="checkbox" checked={!!d.ligatures} onChange={(e) => setD({ ...d, ligatures: e.target.checked })} /></label>
        {onFont ? <label className="bd-num"><span>Editor font size</span><Segmented<number> label="Editor font size" value={font ?? 13} onChange={onFont} options={[12, 13, 14, 15].map((v) => ({ value: v, label: String(v) }))} /></label> : null}
        <label className="bd-num"><span>Run and Debug lenses above Strategy</span><input type="checkbox" checked={!!d.lens} onChange={(e) => setD({ ...d, lens: e.target.checked })} /></label>
      </div> : null}
      {show("Keybindings") ? <div className="bd-nums">
        <div className="bd-num"><span>Dev shortcuts</span><div className="bd-keys">
          <div className="km-bar"><input className="input" aria-label="Search shortcuts" type="search" placeholder="Search" value={kq} onChange={(e) => setKq(e.target.value)} /><button type="button" className="btn" onClick={() => setD({ ...d, keys: {} })}>Reset</button></div>
          {FIXED.filter(([, l, k]) => `${l} ${k}`.toLowerCase().includes(kq.toLowerCase())).map(([kid, l, k]) => <div key={kid} className="km-fixed"><span>{l}</span><kbd>{k}</kbd></div>)}
          {REBINDABLE.filter(([kid, l]) => `${l} ${d.keys?.[kid] ?? ""}`.toLowerCase().includes(kq.toLowerCase())).map(([kid, l]) => { const v = d.keys?.[kid] ?? "", c = conflictWith(kid, v, d.keys ?? {}), cl = c && (FIXED.find((f) => f[0] === c)?.[1] ?? REBINDABLE.find((r) => r[0] === c)?.[1]); return (
          <label key={kid}><span>{l}</span><input className="input" aria-label={`Shortcut for ${l}`} aria-invalid={!!c} placeholder="default" value={v} onChange={(e) => setD({ ...d, keys: { ...d.keys, [kid]: e.target.value } })} />{c && <em className="km-conflict">Used by {cl}</em>}</label>); })}</div></div>
      </div> : null}
      {show("New strategy") ? <>
      <h3 style={{ margin: 0, fontSize: 13 }}>New strategy exits</h3>
      <div className="bd-nums">{EXITS.map(([k, l, p]) => <Num key={k} label={l} pct={p} value={exits[k]} onChange={(v) => setD({ ...d, exits: { ...exits, [k]: v ?? 0 } })} />)}</div>
      <h3 style={{ margin: 0, fontSize: 13 }}>New strategy sizing</h3>
      <div className="bd-nums">
        <label className="bd-num"><span>Mode</span><select className="input" value={sizing.mode} onChange={(e) => setD({ ...d, sizing: { ...sizing, mode: e.target.value } })}>
          <option value="equal">Equal</option><option value="pct_equity">% of equity</option><option value="risk">Risk per trade</option><option value="vol_target">Vol target</option><option value="score">Weight by score</option><option value="kelly">Kelly (capped)</option></select></label>
        <Num label="Value" value={sizing.value} onChange={(v) => setD({ ...d, sizing: { ...sizing, value: v ?? 0 } })} />
        <Num label="Max positions" value={sizing.max_positions} onChange={(v) => setD({ ...d, sizing: { ...sizing, max_positions: v ?? 0 } })} />
      </div>
      </> : null}
      {show("Profiles") ? <>
      <h3>Profiles</h3>
      <div className="bd-nums">
        {profiles.map((p) => <div key={p.name} className="bd-num"><span>{p.name}</span><span className="bd-row-acts">
          <button type="button" className="btn sm" onClick={() => applyProfile(p)}>Apply</button>
          <button type="button" className="icon-btn" aria-label={`Delete profile ${p.name}`} onClick={() => setProfiles((all) => all.filter((x) => x.name !== p.name))}><Trash2 size={14} /></button></span></div>)}
        <form className="bd-num" onSubmit={(e) => { e.preventDefault(); const i = e.currentTarget.elements.namedItem("profile") as HTMLInputElement, n = i.value.trim(); if (n) { saveProfile(n); i.value = ""; } }}>
          <input name="profile" className="input" placeholder="Name this setup" aria-label="Profile name" /><button className="btn sm primary">Save everything as profile</button></form>
      </div>
      </> : null}
      {q ? null : sections.map(([n, node]) => (page === n ? <div key={n} className="bd-set-extra">{node}</div> : null))}
      </div></div>
      <div className="bd-set-ft">
        <button className="btn" onClick={() => setD({ ...d, exits: spec.exits, sizing: spec.sizing })}>Use this strategy's</button>
        <button className="btn" onClick={() => ref.current?.close()}>Cancel</button>
        <button className="btn primary" onClick={save}>Save</button>
      </div>
      </div>
    </dialog>
  );
}

type TplStats = { status: string; stats: Record<string, { spark?: number[]; total_return?: number; sharpe?: number | null; max_drawdown?: number; trades?: number; symbols?: number; start?: string; end?: string; error?: string }> };
let tplStats: Promise<TplStats> | null = null;
// Polls while the server computes the starters' backtests, backing off and giving up after about two minutes.
const loadTplStats = (tries = 0): Promise<TplStats> => {
  tplStats ??= studio<TplStats>("GET", "/templates/stats").then((r) => { if (r.status !== "ready") { tplStats = null; if (tries >= 12) throw new Error("Starter stats not ready"); return new Promise<TplStats>((ok) => setTimeout(() => ok(loadTplStats(tries + 1)), Math.min(2000 * 1.5 ** tries, 15000))); } return r; }, (e) => { tplStats = null; throw e; });
  return tplStats;
};

/** A starter's backtest on its default universe (B-97). */
function TplStat({ name }: { name: string }) {
  const [r, setR] = useState<TplStats["stats"][string] | null>(null);
  useEffect(() => { void loadTplStats().then((s) => setR(s.stats[name] ?? null), () => undefined); }, [name]);
  if (!r || r.total_return == null) return null;
  const sp = r.spark ?? [], [lo, hi] = minMax(sp);
  const spark = sp.length > 1 ? <svg className="bd-tpl-spark" viewBox="0 0 60 16" preserveAspectRatio="none" aria-hidden><polyline fill="none" stroke="currentColor" strokeWidth="1.2" points={sp.map((v, i) => `${(i / (sp.length - 1)) * 60},${16 - ((v - lo) / (hi - lo || 1)) * 15}`).join(" ")} /></svg> : null;
  return <>{spark}<i className="bd-tpl-stat" data-neg={r.total_return < 0 || undefined} title={`${r.symbols} names, ${r.start} to ${r.end}`}>{r.total_return >= 0 ? "+" : ""}{(r.total_return * 100).toFixed(0)}% · Sharpe {r.sharpe?.toFixed(2) ?? "—"} · DD {((r.max_drawdown ?? 0) * 100).toFixed(0)}% · {r.trades} trades</i></>;
}
