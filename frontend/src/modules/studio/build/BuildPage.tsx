"use client";

import { Command as CommandIcon, Download, GitBranch, GitMerge, Settings2, Link2, MoreHorizontal, Play, Plus, Save, Trash2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { defaultsFor } from "@/modules/research/StudyForm";
import { useStudies } from "@/modules/research/store";
import type { FeatureSpec } from "@/modules/research/types";
import { studio, useTemplates, type Compiled, type Ledger } from "../api";
import { TimeSeries } from "@/charts/TimeSeries";
import { TrialChip } from "../RunHeader";
import { GroupEditor, groupFormula, toGroup } from "./BlockRows";
import { BranchDialog } from "./Branches";
import { MenuItem, PopMenu, Segmented, type MenuAt } from "@/workspace/ui";
import { STUDIO_BASE } from "../base";
import type { Problem } from "./CodeEditor";
import { DevIDE, type DevPreview, type QuickRun, type Saved } from "./DevIDE";
import { Palette, type Command } from "./Palette";
import { specDiff, type Group } from "./blocks";
import "../studio.css";

type Param = { value: number; min?: number | null; max?: number | null; step?: number | null; log?: boolean };
type Spec = {
  name: string; entry_long: string; exit_long: string; entry_short: string; exit_short: string; score: string; market_filter: string;
  params: Record<string, Param>;
  exits: Record<string, number>; sizing: { mode: string; value: number; max_positions: number };
  limits: Record<string, number | null>; code: string; hypothesis: string; regime_claim: string; notes: string; [k: string]: unknown;
};
type Version = { version: number; hash: string; actor: string; created: number };
type RunSum = { headline?: string; total_return?: number; sharpe?: number | null; trades?: number };
type Loaded = { id: string; name: string; version: number; latest: number; spec: Spec; draft: Spec | null; versions: Version[]; trials: Ledger; runs_by_version: Record<string, RunSum>; regime_written_after: boolean };

const BLANK: Spec = {
  name: "Untitled", entry_long: "", exit_long: "", entry_short: "", exit_short: "", score: "", market_filter: "", params: {},
  exits: { stop: 0, stop_atr: 0, target: 0, trail: 0, time_stop: 0, breakeven: 0, scale_at: 0, scale_frac: 0 },
  sizing: { mode: "equal", value: 0, max_positions: 10 },
  limits: { max_drawdown: 0.25, max_drawdown_months: null, min_trades: 30, min_years: null, max_beta: null, max_cost_share: null, min_start_pass: null },
  code: "", hypothesis: "", regime_claim: "", notes: "",
};
const ROLES: [string, string][] = [["entry_long", "Enter long"], ["exit_long", "Exit long"], ["entry_short", "Enter short"], ["exit_short", "Exit short"], ["score", "Rank by"], ["market_filter", "Trade only when"]];
const EXITS: [string, string, boolean][] = [["stop", "Stop", true], ["stop_atr", "Stop × ATR", false], ["target", "Target", true], ["trail", "Trailing stop", true], ["time_stop", "Time stop (bars)", false],
  ["breakeven", "Breakeven at", true], ["scale_at", "Scale out at", true], ["scale_frac", "Scale out share", true]];
const LIMITS: [string, string, boolean][] = [["max_drawdown", "Max drawdown", true], ["max_drawdown_months", "Max drawdown months", false], ["min_trades", "Min trades", false],
  ["min_years", "Min years", false], ["max_beta", "Max beta", false], ["max_cost_share", "Max cost share", true], ["min_start_pass", "Min start dates passing", true]];
type Defaults = { ui: "simple" | "dev"; mode: "blocks" | "formula" | "english"; exits: Record<string, number>; sizing: Spec["sizing"] };
const readDefaults = (): Partial<Defaults> => { try { return JSON.parse(localStorage.getItem("studio:build:defaults") ?? "{}") as Partial<Defaults>; } catch { return {}; } };
const fail = (e: unknown) => toast.error(e instanceof Error ? e.message : "Failed");

/** Percent fields are typed as percent and stored as fractions. */
function Num({ label, value, pct, onChange, empty }: { label: string; value: number | null | undefined; pct?: boolean; empty?: boolean; onChange: (v: number | null) => void }) {
  const shown = value === null || value === undefined ? "" : pct ? +(value * 100).toFixed(4) : value;
  return (
    <label className="bd-num"><span>{label}</span>
      <input className="input" inputMode="decimal" value={shown} placeholder={empty ? "—" : "0"}
        onChange={(e) => { const t = e.target.value.trim(); if (!t) return onChange(empty ? null : 0); const n = Number(t); if (Number.isFinite(n)) onChange(pct ? n / 100 : n); }} />
      {pct ? <i>%</i> : null}
    </label>
  );
}

/** Build: write the rule, see it compile as you type, save immutable versions, run. */
export default function BuildPage({ features, id }: { features: FeatureSpec[]; id?: string }) {
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
  const [symbol, setSymbol] = useState("SPY");
  const [auto, setAuto] = useState(() => { try { return localStorage.getItem("studio:build:auto") !== "off"; } catch { return true; } });
  const [previewed, setPreviewed] = useState<string | null>(null);
  const [nudge, setNudge] = useState(0);
  const [recover, setRecover] = useState<{ spec: Spec; at: number } | null>(null);
  const [pausedAt, setPausedAt] = useState<string | null>(null);
  const [quick, setQuick] = useState<QuickRun | null>(null);
  const quickRun = async (level: "quick" | "full") => {
    let sid: string | null = loaded?.id ?? null;
    if (level === "full") { sid = await save(); if (!sid) return; }
    try {
      const j = await studio<QuickRun>("POST", "/build/run", level === "full" ? { level, strategy_id: sid } : { level, spec, ...(sid ? { strategy_id: sid } : {}) });
      setQuick({ ...j, level, status: "queued" });
      const poll = async () => {
        const st = await studio<QuickRun>("GET", `/build/run/${j.job_id}`).catch(() => null);
        if (!st) return;
        setQuick((q) => (q?.job_id === j.job_id ? { ...st, level } : q));
        if (["queued", "running"].includes(st.status)) setTimeout(() => void poll(), 700);
        else if (level === "full" && loaded) void load(loaded.id);
      };
      setTimeout(() => void poll(), 400);
    } catch (e) { fail(e); }
  };
  const cancelRun = () => { if (quick) void studio("POST", `/jobs/${quick.job_id}/cancel`).then(() => setQuick((q) => (q ? { ...q, status: "cancelled" } : q)), fail); };
  const [font, setFont] = useState(() => { try { return Number(localStorage.getItem("studio:dev:font")) || 13; } catch { return 13; } });
  type Preview = Omit<DevPreview, "trades"> & { bars: { date: string; close: number }[]; trades: { entry_date: string; exit_date: string; side: string; return: number }[]; total_return?: number; repaint?: { cuts: number; changed: number; dates: string[] } };
  const [prev, setPrev] = useState<Preview | null>(null);
  const [diff, setDiff] = useState<{ version: number; rows: [string, string, string][] } | null>(null);
  const [proposal, setProposal] = useState<{ fields: Record<string, string>; exits: Record<string, number>; unmatched: string[] } | { error: string } | null>(null);
  const [catalogue, setCatalogue] = useState<string[]>([]);
  type Ref = { name: string; doc: string; example?: string; args?: string[] };
  const [reference, setReference] = useState<Ref[]>([]);
  const [refQ, setRefQ] = useState("");
  type Cond = { true_rate: number | null; last_true_date: string | null; fired_dates: string[]; constant: boolean | null; observations: number };
  const [conds, setConds] = useState<Record<string, Cond | { error: string }>>({});
  const [fired, setFired] = useState<{ role: string; dates: string[] } | null>(null);
  const [pyView, setPyView] = useState<string | null>(null);
  useEffect(() => { void studio<{ formula: { fields: Ref[]; operators: Ref[] } }>("GET", "/manifest").then((m) => { setCatalogue([...m.formula.fields.map((f) => f.name), ...m.formula.operators.map((o) => o.example ?? o.name)]); setReference([...m.formula.operators, ...m.formula.fields]); }, () => undefined); }, []);
  const history = useRef<{ past: Spec[]; future: Spec[] }>({ past: [], future: [] });
  const [palette, setPalette] = useState(false);
  const focus = useRef<{ role: string; start: number; end: number } | null>(null);
  const track = (role: string) => (e: React.SyntheticEvent<HTMLTextAreaElement>) => { const t = e.currentTarget; focus.current = { role, start: t.selectionStart, end: t.selectionEnd }; };

  const load = useCallback((sid: string, version?: number) => studio<Loaded>("GET", `/strategies/${sid}${version ? `?version=${version}` : ""}`).then((s) => {
    const next = { ...BLANK, ...(version ? s.spec : s.draft ?? s.spec) };
    setLoaded(s); setSpec(next); if (next.code.trim() && !new URLSearchParams(window.location.search).get("ui")) setUi("dev"); setDirty(!version && !!s.draft); history.current = { past: [], future: [] };
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
    return () => { clearInterval(t); void fetch(`${STUDIO_BASE}/strategies/${sid}/lease?session=${s}`, { method: "DELETE", keepalive: true }).catch(() => undefined); };
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
  const formatSave = () => void studio<{ code: string }>("POST", "/format-python", { code: spec.code }).then((r) => { const next = { ...spec, code: r.code }; if (r.code !== spec.code) edit({ code: r.code }); return save(next); }, fail);
  const edit = (next: Partial<Spec>) => readOnly ? void toast("Read-only", { id: "ro" }) : setSpec((cur) => { history.current.past.push(cur); history.current.future = []; setDirty(true); return { ...cur, ...next }; });

  // Live compile, 250 ms after typing stops.
  useEffect(() => {
    const t = setTimeout(() => studio<Compiled>("POST", "/compile", { spec }).then(setCompiled, (e) => setCompiled({ ok: false, findings: [{ severity: "error", role: "spec", line: 1, start: 0, end: 0, token: "", message: e instanceof Error ? e.message : "Invalid" }], hash: "", description: "" })), 250);
    return () => clearTimeout(t);
  }, [spec]);

  // Preview on one name, 300 ms after typing stops (B-5).
  useEffect(() => {
    if (!compiled?.ok || !symbol.trim() || (!auto && !nudge)) return;
    const hash = compiled.hash;
    const t = setTimeout(() => void studio<Preview>("POST", "/preview", { spec, symbol: symbol.trim().toUpperCase() }).then((r) => { setPrev(r); setPreviewed(hash); setNudge(0); }, (e) => setPrev({ status: "skipped", reason: e instanceof Error ? e.message : "failed", bars: [], trades: [] })), 300);
    return () => clearTimeout(t);
  }, [spec, symbol, compiled?.ok, auto, nudge]); // eslint-disable-line react-hooks/exhaustive-deps
  const stale = !!prev && !!previewed && !!compiled?.hash && previewed !== compiled.hash;

  // Browser copy of unsaved edits, offered back when the page reopens with something different (B-27).
  const backupKey = `studio:draft:${loaded?.id ?? id ?? "new"}`;
  useEffect(() => {
    if (!dirty) return;
    const t = setTimeout(() => { try { localStorage.setItem(backupKey, JSON.stringify({ spec, at: Date.now() })); } catch { /* full or blocked */ } }, 500);
    return () => clearTimeout(t);
  }, [spec, dirty, backupKey]);
  useEffect(() => {
    if (!loaded) return;
    try {
      const raw = localStorage.getItem(`studio:draft:${loaded.id}`); if (!raw) return;
      const b = JSON.parse(raw) as { spec: Spec; at: number };
      if (JSON.stringify({ ...BLANK, ...b.spec }) !== JSON.stringify({ ...BLANK, ...(loaded.draft ?? loaded.spec) })) setRecover(b); else localStorage.removeItem(`studio:draft:${loaded.id}`);
    } catch { /* blocked */ }
  }, [loaded?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // True-rate and last true date of every rule on the preview name, 600 ms after typing stops (B-108, B-111, B-116).
  useEffect(() => {
    if (!compiled?.ok || !symbol.trim() || ui === "dev") return;
    const t = setTimeout(() => {
      for (const [role] of ROLES) {
        const expr = (spec[role] as string).trim();
        if (!expr || role === "score") continue;
        void studio<Cond>("POST", "/build/condition", { spec, symbol: symbol.trim().toUpperCase(), expression: expr })
          .then((c) => setConds((o) => ({ ...o, [role]: c })), (e: Error) => setConds((o) => ({ ...o, [role]: { error: e.message } })));
      }
    }, 600);
    return () => clearTimeout(t);
  }, [spec, symbol, compiled?.ok, ui]);
  useEffect(() => {
    if (pyView === null) return;
    const t = setTimeout(() => void studio<{ code: string }>("POST", "/to-python", { spec: { ...spec, code: "" } }).then((r) => setPyView(r.code), () => undefined), 400);
    return () => clearTimeout(t);
  }, [spec, pyView === null]); // eslint-disable-line react-hooks/exhaustive-deps

  // Autosave the draft every 2 s while there are unsaved edits (B-6).
  useEffect(() => {
    if (!dirty || !loaded) return;
    const t = setTimeout(() => void studio("PUT", `/strategies/${loaded.id}/draft`, { spec }).catch(() => undefined), 2000);
    return () => clearTimeout(t);
  }, [spec, dirty, loaded]);

  const save = useCallback(async (over?: Spec): Promise<string | null> => {
    const body = { spec: over ?? spec };
    setSaving("saving");
    try {
      const s = loaded ? await studio<Loaded>("PUT", `/strategies/${loaded.id}`, body) : await studio<Loaded>("POST", "/strategies", body);
      setLoaded(s); setDirty(false); setSaving("idle"); toast.success(`Saved version ${s.latest}`);
      try { localStorage.removeItem(`studio:draft:${s.id}`); localStorage.removeItem("studio:draft:new"); } catch { /* blocked */ }
      if (!loaded) router.replace(`/studio/build/${s.id}`);
      return s.id;
    } catch (e) { setSaving(e instanceof Error && /409|version/i.test(e.message) ? "conflict" : "idle"); fail(e); return null; }
  }, [loaded, spec, router]);

  const run = useCallback(async () => {
    const sid = await save(); if (!sid) return;
    try { localStorage.setItem("studio:strategy", sid); } catch { /* storage blocked */ }
    const f = features.find((x) => x.id === "st01");
    if (f) useStudies.getState().setForm("st01", (cur) => ({ ...cur, strategy_id: sid }), defaultsFor(f));
    router.push("/studio/backtest?go=1");
  }, [save, features, router]);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key.toLowerCase() === "p" && e.shiftKey) { e.preventDefault(); setPalette((o) => !o); }
      else if (e.key === "s") { e.preventDefault(); void save(); }
      else if (e.key === "Enter") { e.preventDefault(); void run(); }
      else if (e.key === "z" && !(e.target as HTMLElement).matches("input, textarea")) {
        e.preventDefault(); const h = history.current, from = e.shiftKey ? h.future : h.past, to = e.shiftKey ? h.past : h.future;
        const prev = from.pop(); if (prev) setSpec((cur) => { to.push(cur); return prev; });
      }
    };
    window.addEventListener("keydown", on); return () => window.removeEventListener("keydown", on);
  }, [save, run]);

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
  const applyTemplate = (t: { spec: Record<string, unknown> }) => { edit({ ...BLANK, ...(t.spec as Partial<Spec>) }); setMode("formula"); };

  const findings = (role: string) => (blank ? [] : compiled?.findings.filter((f) => f.role === role) ?? []);
  const params = Object.entries(spec.params);
  const sweep = params.reduce((n, [, p]) => (p.min != null && p.max != null && p.step ? n * (Math.floor((p.max - p.min) / p.step + 1e-9) + 1) : n), params.length ? 1 : 0);
  const blank = !loaded && !spec.code.trim() && ROLES.every(([r]) => !(spec[r] as string).trim());
  const commands: Command[] = [
    { id: "lift", group: "Edit", label: "Lift number to parameter", ask: "Parameter name for the number at the cursor", run: (n) => lift(n) },
    { id: "param", group: "Edit", label: "Add parameter", ask: "Parameter name", run: (n) => { if (n && /^[a-z_][a-z0-9_]*$/i.test(n)) edit({ params: { ...spec.params, [n]: { value: 0 } } }); } },
    ...(["blocks", "formula", "english"] as const).map((m) => ({ id: `mode-${m}`, group: "Mode", label: { blocks: "Blocks", formula: "Formula", english: "Plain English" }[m], run: () => { switchUi("simple"); switchMode(m); } })),
    { id: "ui-dev", group: "Mode", label: "Dev: Python IDE", run: () => switchUi("dev") },
    { id: "save", group: "Strategy", label: "Save version", hint: "⌘S", run: () => void save() },
    { id: "run", group: "Strategy", label: "Run backtest", hint: "⌘↵", run: () => void run() },
    { id: "new", group: "Strategy", label: "New blank strategy", run: () => router.push("/studio/build") },
    ...(templates.data ?? []).map((t) => ({ id: `t-${t.name}`, group: "Template", label: `${t.name}: ${t.rule}`, run: () => applyTemplate(t) })),
  ];
  const rp = prev?.repaint;
  const errors = compiled?.findings.filter((f) => f.severity === "error").length ?? 0;
  const checks: { ok: boolean | null; label: string; detail: string; go?: string }[] = [
    { ok: compiled ? errors === 0 : null, label: "Compiles", detail: errors ? `${errors} error${errors === 1 ? "" : "s"}` : compiled ? `${compiled.ms ?? 0} ms` : "checking" },
    { ok: prev?.status === "ok" ? (rp ? rp.changed === 0 : null) : null, label: "No look-ahead", detail: rp ? (rp.changed ? `changed at ${rp.changed} of ${rp.cuts} cuts` : `same at ${rp.cuts} cuts`) : "needs a preview" },
    { ok: prev?.status === "ok" ? prev.trades.length > 0 : null, label: "Signals fire", detail: prev?.status === "ok" ? `${prev.trades.length} trades on ${symbol.toUpperCase()}, 2 years` : prev?.reason ?? "needs a preview" },
    { ok: prev?.status === "ok" && prev.trades.length >= 5 ? true : null, label: "Trades on one name", detail: prev?.status === "ok" ? (prev.trades.length >= 5 ? `${prev.trades.length}, enough to judge the rule here` : `${prev.trades.length}: judge it on the full universe`) : "—" },
    { ok: !(compiled?.findings.some((f) => f.role.startsWith("exit_")) ?? false), label: "Every entry has an exit", detail: compiled?.findings.find((f) => f.role.startsWith("exit_"))?.message ?? "stop, target or rule set", go: "exits" },
    { ok: !(compiled?.findings.some((f) => f.role === "params") ?? false), label: "Parameters used", detail: compiled?.findings.filter((f) => f.role === "params").map((f) => f.token).join(", ") || "all used", go: "params" },
  ];

  const side = (
    <>
          <section className="bd-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h3 style={{ flex: 1 }}>Preview</h3>
              <label className="bd-auto" title="Preview after each edit"><input type="checkbox" checked={auto} onChange={(e) => { setAuto(e.target.checked); try { localStorage.setItem("studio:build:auto", e.target.checked ? "on" : "off"); } catch { /* blocked */ } }} />Auto</label>
              {!auto || stale ? <button className="btn sm" onClick={() => setNudge((n) => n + 1)}>Preview</button> : null}
              <input className="input" aria-label="Preview symbol" style={{ width: 90 }} value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </div>
            {stale ? <p className="bd-find warning" style={{ margin: 0 }}><b>Edited</b>since this preview</p> : null}
            {prev?.invariants?.count ? <p className="bd-find error" style={{ margin: 0 }}><b>Invariant</b>broken on {prev.invariants.count} bar{prev.invariants.count === 1 ? "" : "s"}; Validate will fail</p> : null}
            {prev?.status === "ok" ? (
              <>
                <p className="bd-meta" style={{ margin: 0 }}>{prev.trades.length} trades · {`${(prev.total_return ?? 0) >= 0 ? "+" : ""}${((prev.total_return ?? 0) * 100).toFixed(1)}%`} · last 2 years before the hold-out</p>
                {prev.repaint ? <p className={`bd-find ${prev.repaint.changed ? "error" : ""}`}><b style={{ color: prev.repaint.changed ? undefined : "var(--up)" }}>{prev.repaint.changed ? "Repaints" : "No look-ahead"}</b>
                  {prev.repaint.changed ? `signals changed at ${prev.repaint.changed} of ${prev.repaint.cuts} cuts (${prev.repaint.dates.join(", ")})` : `same signals at ${prev.repaint.cuts} history cuts`}</p> : null}
                <TimeSeries data={prev.bars} series={[{ key: "close", label: symbol.toUpperCase(), color: "var(--text-2)" }]} height={180} legend={false}
                  markers={prev.invariants?.rows.length ? [...prev.invariants.rows.filter((r) => !r.symbol || r.symbol === symbol.toUpperCase()).map((r) => ({ date: r.date, label: "!", color: "var(--down)" })), ...prev.trades.flatMap((t) => [{ date: t.entry_date, label: "▲", color: "var(--up)" }])] : pausedAt && ui === "dev" ? [{ date: pausedAt, label: "❚❚", color: "var(--warn)" }, ...prev.trades.flatMap((t) => [{ date: t.entry_date, label: "▲", color: "var(--up)" }, { date: t.exit_date, label: "×", color: "var(--down)" }])] : fired ? fired.dates.map((d) => ({ date: d, label: "●", color: "var(--accent)" })) : prev.trades.flatMap((t) => [{ date: t.entry_date, label: t.side === "long" ? "▲" : "▼", color: "var(--up)" }, { date: t.exit_date, label: "×", color: "var(--down)" }])} />
                {fired ? <p className="bd-meta" style={{ margin: 0 }}>{ROLES.find((r) => r[0] === fired.role)?.[1]}: {fired.dates.length} bars marked <button className="bd-link" onClick={() => setFired(null)}>Show trades</button></p> : null}
              </>
            ) : <div className="st-skip">{prev?.reason ? `${prev.status === "error" ? "error" : "skipped"}: ${prev.reason}` : "—"}</div>}
          </section>
          <section className="bd-card">
            <h3>Checks</h3>
            <ul className="bd-checks">
              {checks.map((c) => (
                <li key={c.label} className={c.ok === null ? "" : c.ok ? "ok" : "bad"}>
                  <i aria-hidden /> <b>{c.label}</b>
                  {c.go && c.ok === false ? <button className="bd-link" onClick={() => document.getElementById(`bd-${c.go}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}>{c.detail}</button> : <span>{c.detail}</span>}
                </li>
              ))}
            </ul>
          </section>
          <section className="bd-card">
            <h3>What it does</h3>
            <p className="bd-desc">{compiled?.description || "—"}</p>
          </section>
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

  return (
    <div className="bd" data-ui={ui}>
      <header className="bd-head">
        <input className="bd-name" aria-label="Strategy name" value={spec.name} onChange={(e) => edit({ name: e.target.value })} />
        <span className="bd-meta">{loaded ? `v${loaded.latest}${dirty ? " · draft" : " · saved"}` : "new"}{compiled?.ms !== undefined ? ` · compiled in ${compiled.ms} ms` : ""}</span>
        {loaded ? <TrialChip ledger={loaded.trials} strategyId={loaded.id} /> : null}
        <span style={{ flex: 1 }} />
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
        <span className="bd-ui"><Segmented<"simple" | "dev"> label="Interface" value={ui} onChange={switchUi} options={[{ value: "simple", label: "Simple" }, { value: "dev", label: "Dev" }]} /></span>
        <button className="btn" onClick={() => setPalette(true)}><CommandIcon size={14} />Commands<kbd>⌘⇧P</kbd></button>
        <button className="btn icon" aria-label="More" aria-haspopup="menu" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMore({ x: r.right - 220, y: r.bottom + 4 }); }}><MoreHorizontal size={15} /></button>
        <PopMenu at={more} onClose={() => setMore(null)} width={220}>
          <MenuItem icon={<Link2 size={13} />} disabled={!loaded} onClick={() => { setMore(null); if (loaded) void studio<{ token: string }>("POST", `/strategies/${loaded.id}/share`).then((r) => { const u = `${location.origin}/studio/build?share=${r.token}`; void navigator.clipboard?.writeText(u); toast.success("Read-only link copied"); }, fail); }}>Copy read-only link</MenuItem>
          <MenuItem icon={<GitBranch size={13} />} disabled={!loaded} onClick={() => { setMore(null); if (loaded) void studio<{ id: string }>("POST", `/strategies/${loaded.id}/versions/${loaded.version}/branch`).then((b) => router.push(`/studio/build/${b.id}`), fail); }}>Branch from v{loaded?.version ?? 1}</MenuItem>
          <MenuItem icon={<Download size={13} />} disabled={!loaded} onClick={() => { setMore(null); if (loaded) window.location.assign(`${STUDIO_BASE}/strategies/${loaded.id}/export.zip`); }}>Export project (.zip)</MenuItem>
          <MenuItem icon={<Upload size={13} />} onClick={() => { setMore(null); zipInput.current?.click(); }}>Import project (.zip)</MenuItem>
          <MenuItem icon={<GitMerge size={13} />} disabled={!loaded} onClick={() => { setMore(null); setDialog("branches"); }}>Compare and merge…</MenuItem>
          <MenuItem icon={<Settings2 size={13} />} onClick={() => { setMore(null); setDialog("customise"); }}>Customise…</MenuItem>
          <div className="hd">Editor font</div>
          <div style={{ padding: "2px 8px 8px" }}><Segmented<number> label="Editor font size" value={font} onChange={(v) => { setFont(v); try { localStorage.setItem("studio:dev:font", String(v)); } catch { /* blocked */ } }} options={[12, 13, 14, 15].map((v) => ({ value: v, label: String(v) }))} /></div>
        </PopMenu>
        <input ref={zipInput} type="file" accept=".zip,application/zip" hidden onChange={(e) => {
          const f = e.target.files?.[0]; e.target.value = ""; if (!f) return;
          void fetch(`${STUDIO_BASE}/strategies/import-zip?name=${encodeURIComponent(f.name.replace(/\.zip$/i, ""))}`, { method: "POST", headers: { "Content-Type": "application/zip" }, body: f })
            .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.detail?.message ?? j.detail ?? "Import failed"); router.push(`/studio/build/${j.id}?ui=dev`); }).catch(fail);
        }} />
        <button className="btn" onClick={() => void save()}><Save size={14} />Save<kbd>⌘S</kbd></button>
        <button className="btn primary" disabled={compiled ? !compiled.ok : true} onClick={() => void run()}><Play size={14} />Run backtest<kbd>⌘↵</kbd></button>
      </header>

      <Palette open={palette} onClose={() => setPalette(false)} commands={commands} />
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
            {templates.data.map((t) => (
              <button key={t.name} className="bd-tpl" onClick={() => applyTemplate(t)}><b>{t.name}</b><span>{t.rule}</span></button>
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
      {ui === "dev" ? <DevIDE spec={spec} edit={edit} symbol={symbol} prev={prev} side={<>{side}{paramsCard}</>} onSave={formatSave} onRun={() => void run()} onFullRun={() => void run()} compileProblems={compileProblems}
        strategyId={loaded?.id} versions={loaded?.versions ?? []} runs={loaded?.runs_by_version ?? {}} saved={savedState} readOnly={!!readOnly} version={loaded?.version} stale={stale} onPause={setPausedAt} font={font} quick={quick} onQuickRun={(l) => void quickRun(l)} onCancel={cancelRun} trial={loaded ? <TrialChip ledger={loaded.trials} strategyId={loaded.id} /> : null} onReload={() => loaded && void load(loaded.id)} /> : <div className="bd-grid">
        <section className="bd-card bd-rules">
          <div className="bd-modes" role="tablist">
            {(["blocks", "formula", "english"] as const).map((m) => <button key={m} role="tab" aria-selected={mode === m} className={`btn sm${mode === m ? " on" : ""}`} onClick={() => switchMode(m)}>{{ blocks: "Blocks", formula: "Formula", english: "Plain English" }[m]}</button>)}
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
                  {Object.entries(proposal.fields).map(([k, v]) => <p key={k}><span>{ROLES.find((r) => r[0] === k)?.[1]}</span><code>{v}</code></p>)}
                  {Object.entries(proposal.exits).map(([k, v]) => <p key={k}><span>{EXITS.find((r) => r[0] === k)?.[1]}</span><code>{k === "time_stop" ? `${v} bars` : `${+(v * 100).toFixed(2)}%`}</code></p>)}
                  {proposal.unmatched.length ? <p className="bd-find warning"><b>Ignored</b>{proposal.unmatched.join(", ")}</p> : null}
                </div>
              ) : null}
            </div>
          ) : null}
          {ROLES.map(([role, label]) => {
            if (mode === "english") return null;
            const groups = (spec.groups ?? {}) as Record<string, Group>;
            const tree: Group | null = mode === "blocks" && role !== "score" ? groups[role] ?? toGroup(spec[role] as string) ?? { op: "all", items: [{ rule: spec[role] as string, enabled: true }] } : null;
            const dropGroup = () => { const { [role]: _, ...rest } = groups; return rest; };
            return (
            <div key={role} className="bd-rule">
              <label htmlFor={`r-${role}`}>{label}</label>
              {tree ? <GroupEditor id={`b-${role}`} group={tree} suggestions={catalogue} onChange={(g) => edit({ [role]: groupFormula(g), groups: { ...groups, [role]: g } })} /> : null}
              {tree ? null : <textarea id={`r-${role}`} className="input" spellCheck={false} rows={role === "score" || role === "market_filter" ? 1 : 2} placeholder={role === "market_filter" ? "market > sma(market, 200)" : undefined} value={spec[role] as string} onSelect={track(role)} onFocus={track(role)} onChange={(e) => edit({ [role]: e.target.value, ...(role in groups ? { groups: dropGroup() } : {}) })} />}
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
          <details className="bd-more" onToggle={(e) => { if ((e.currentTarget as HTMLDetailsElement).open && pyView === null) setPyView(""); }}>
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
                  if (!f) return void navigator.clipboard?.writeText(text).then(() => toast.success("Copied"));
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

/** Defaults for new strategies and how Build opens (B-66, B-100, B-135). Kept in this browser. */
function CustomiseDialog({ spec, onClose }: { spec: Spec; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [d, setD] = useState<Partial<Defaults>>(readDefaults);
  useEffect(() => { ref.current?.showModal(); }, []);
  const save = () => { try { localStorage.setItem("studio:build:defaults", JSON.stringify(d)); localStorage.removeItem("studio:build:ui"); } catch { /* blocked */ } toast.success("Defaults saved"); ref.current?.close(); };
  const exits = { ...BLANK.exits, ...d.exits }, sizing = { ...BLANK.sizing, ...d.sizing };
  return (
    <dialog ref={ref} className="sh-import" aria-label="Customise Build" onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <b style={{ fontSize: 15 }}>Customise Build</b>
      <div className="bd-nums">
        <label className="bd-num"><span>Open in</span><Segmented<"simple" | "dev"> label="Default interface" value={d.ui ?? "simple"} onChange={(ui) => setD({ ...d, ui })} options={[{ value: "simple", label: "Simple" }, { value: "dev", label: "Dev" }]} /></label>
        <label className="bd-num"><span>Simple starts in</span><select className="input" value={d.mode ?? "formula"} onChange={(e) => setD({ ...d, mode: e.target.value as Defaults["mode"] })}><option value="blocks">Blocks</option><option value="formula">Formula</option><option value="english">Plain English</option></select></label>
      </div>
      <h3 style={{ margin: 0, fontSize: 13 }}>New strategy exits</h3>
      <div className="bd-nums">{EXITS.map(([k, l, p]) => <Num key={k} label={l} pct={p} value={exits[k]} onChange={(v) => setD({ ...d, exits: { ...exits, [k]: v ?? 0 } })} />)}</div>
      <h3 style={{ margin: 0, fontSize: 13 }}>New strategy sizing</h3>
      <div className="bd-nums">
        <label className="bd-num"><span>Mode</span><select className="input" value={sizing.mode} onChange={(e) => setD({ ...d, sizing: { ...sizing, mode: e.target.value } })}>
          <option value="equal">Equal</option><option value="pct_equity">% of equity</option><option value="risk">Risk per trade</option><option value="vol_target">Vol target</option><option value="score">Weight by score</option><option value="kelly">Kelly (capped)</option></select></label>
        <Num label="Value" value={sizing.value} onChange={(v) => setD({ ...d, sizing: { ...sizing, value: v ?? 0 } })} />
        <Num label="Max positions" value={sizing.max_positions} onChange={(v) => setD({ ...d, sizing: { ...sizing, max_positions: v ?? 0 } })} />
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn" onClick={() => setD({ ...d, exits: spec.exits, sizing: spec.sizing })}>Use this strategy's</button>
        <button className="btn" onClick={() => ref.current?.close()}>Cancel</button>
        <button className="btn primary" onClick={save}>Save</button>
      </div>
    </dialog>
  );
}
