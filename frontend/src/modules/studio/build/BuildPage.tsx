"use client";

import { Command as CommandIcon, Play, Plus, Save, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { defaultsFor } from "@/modules/research/StudyForm";
import { useStudies } from "@/modules/research/store";
import type { FeatureSpec } from "@/modules/research/types";
import { studio, useTemplates, type Compiled, type Ledger } from "../api";
import { TimeSeries } from "@/charts/TimeSeries";
import { TrialChip } from "../RunHeader";
import { BlockRows } from "./BlockRows";
import { CodeEditor } from "./CodeEditor";
import { Palette, type Command } from "./Palette";
import { fromFormula, toFormula, type Row } from "./blocks";
import "../studio.css";

type Param = { value: number; min?: number | null; max?: number | null; step?: number | null };
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

/** Field-by-field changes between two specs, flattened to dotted keys. */
function specDiff(a: Spec, b: Spec): [string, string, string][] {
  const flat = (o: unknown, pre = ""): Record<string, string> => (o && typeof o === "object" && !Array.isArray(o)
    ? Object.assign({}, ...Object.entries(o).map(([k, v]) => flat(v, pre ? `${pre}.${k}` : k))) : { [pre]: o === null || o === undefined ? "" : typeof o === "object" ? JSON.stringify(o) : String(o) });
  const fa = flat(a), fb = flat(b);
  return [...new Set([...Object.keys(fa), ...Object.keys(fb)])].filter((k) => k !== "blocks" && (fa[k] ?? "") !== (fb[k] ?? "")).map((k) => [k, fa[k] ?? "", fb[k] ?? ""]);
}

/** Build: write the rule, see it compile as you type, save immutable versions, run. */
export default function BuildPage({ features, id }: { features: FeatureSpec[]; id?: string }) {
  const router = useRouter();
  const templates = useTemplates();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [spec, setSpec] = useState<Spec>(BLANK);
  const [compiled, setCompiled] = useState<Compiled | null>(null);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<"blocks" | "formula" | "python" | "english">("formula");
  const [english, setEnglish] = useState("");
  const [symbol, setSymbol] = useState("SPY");
  type Preview = { status: string; reason?: string; line?: number | null; bars: { date: string; close: number }[]; trades: { entry_date: string; exit_date: string; side: string; return: number }[]; total_return?: number; repaint?: { cuts: number; changed: number; dates: string[] } };
  const [prev, setPrev] = useState<Preview | null>(null);
  const [diff, setDiff] = useState<{ version: number; rows: [string, string, string][] } | null>(null);
  const [proposal, setProposal] = useState<{ fields: Record<string, string>; exits: Record<string, number>; unmatched: string[] } | { error: string } | null>(null);
  const [catalogue, setCatalogue] = useState<string[]>([]);
  useEffect(() => { void studio<{ formula: { fields: { name: string }[]; operators: { example: string }[] } }>("GET", "/manifest").then((m) => setCatalogue([...m.formula.fields.map((f) => f.name), ...m.formula.operators.map((o) => o.example)]), () => undefined); }, []);
  const history = useRef<{ past: Spec[]; future: Spec[] }>({ past: [], future: [] });
  const [palette, setPalette] = useState(false);
  const focus = useRef<{ role: string; start: number; end: number } | null>(null);
  const track = (role: string) => (e: React.SyntheticEvent<HTMLTextAreaElement>) => { const t = e.currentTarget; focus.current = { role, start: t.selectionStart, end: t.selectionEnd }; };

  const load = useCallback((sid: string, version?: number) => studio<Loaded>("GET", `/strategies/${sid}${version ? `?version=${version}` : ""}`).then((s) => {
    const next = { ...BLANK, ...(version ? s.spec : s.draft ?? s.spec) };
    setLoaded(s); setSpec(next); if (next.code.trim()) setMode("python"); setDirty(!version && !!s.draft); history.current = { past: [], future: [] };
  }, fail), []);
  useEffect(() => { if (id) void load(id); else { setLoaded(null); setSpec(BLANK); } }, [id, load]);

  function switchMode(m: "blocks" | "formula" | "python" | "english") {
    setMode(m);
    if (m === "python" && !spec.code.trim()) void studio<{ code: string }>("POST", "/to-python", { spec }).then((r) => edit({ code: r.code }), fail);
  }
  const edit = (next: Partial<Spec>) => setSpec((cur) => { history.current.past.push(cur); history.current.future = []; setDirty(true); return { ...cur, ...next }; });

  // Live compile, 250 ms after typing stops.
  useEffect(() => {
    const t = setTimeout(() => studio<Compiled>("POST", "/compile", { spec }).then(setCompiled, (e) => setCompiled({ ok: false, findings: [{ severity: "error", role: "spec", line: 1, start: 0, end: 0, token: "", message: e instanceof Error ? e.message : "Invalid" }], hash: "", description: "" })), 250);
    return () => clearTimeout(t);
  }, [spec]);

  // Preview on one name, 300 ms after typing stops (B-5).
  useEffect(() => {
    if (!compiled?.ok || !symbol.trim()) return;
    const t = setTimeout(() => void studio<Preview>("POST", "/preview", { spec, symbol: symbol.trim().toUpperCase() }).then(setPrev, (e) => setPrev({ status: "skipped", reason: e instanceof Error ? e.message : "failed", bars: [], trades: [] })), 300);
    return () => clearTimeout(t);
  }, [spec, symbol, compiled?.ok]);

  // Autosave the draft every 2 s while there are unsaved edits (B-6).
  useEffect(() => {
    if (!dirty || !loaded) return;
    const t = setTimeout(() => void studio("PUT", `/strategies/${loaded.id}/draft`, { spec }).catch(() => undefined), 2000);
    return () => clearTimeout(t);
  }, [spec, dirty, loaded]);

  const save = useCallback(async (): Promise<string | null> => {
    try {
      const s = loaded ? await studio<Loaded>("PUT", `/strategies/${loaded.id}`, { spec }) : await studio<Loaded>("POST", "/strategies", { spec });
      setLoaded(s); setDirty(false); toast.success(`Saved version ${s.latest}`);
      if (!loaded) router.replace(`/studio/build/${s.id}`);
      return s.id;
    } catch (e) { fail(e); return null; }
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
    ...(["blocks", "formula", "python", "english"] as const).map((m) => ({ id: `mode-${m}`, group: "Mode", label: { blocks: "Blocks", formula: "Formula", python: "Python", english: "Plain English" }[m], run: () => switchMode(m) })),
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

  return (
    <div className="bd">
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
        <button className="btn" onClick={() => setPalette(true)}><CommandIcon size={14} />Commands<kbd>⌘⇧P</kbd></button>
        <button className="btn" onClick={() => void save()}><Save size={14} />Save<kbd>⌘S</kbd></button>
        <button className="btn primary" disabled={compiled ? !compiled.ok : true} onClick={() => void run()}><Play size={14} />Run backtest<kbd>⌘↵</kbd></button>
      </header>

      <Palette open={palette} onClose={() => setPalette(false)} commands={commands} />
      {blank && templates.data ? (
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
      <div className="bd-grid">
        <section className="bd-card bd-rules">
          <div className="bd-modes" role="tablist">
            {(["blocks", "formula", "python", "english"] as const).map((m) => <button key={m} role="tab" aria-selected={mode === m} className={`btn sm${mode === m ? " on" : ""}`} onClick={() => switchMode(m)}>{{ blocks: "Blocks", formula: "Formula", python: "Python", english: "Plain English" }[m]}</button>)}
            {spec.code.trim() && mode !== "python" ? <span className="bd-find warning" style={{ marginLeft: "auto" }}><b>Python runs</b>rules below are kept, not used<button className="btn sm" onClick={() => edit({ code: "" })}>Use rules</button></span> : null}
          </div>
          {mode === "python" ? (
            <>
              <CodeEditor value={spec.code} onChange={(code) => edit({ code })} findings={findings("code")} catalogue={catalogue} onSave={() => void save()} onRun={() => void run()}
                runtime={prev?.status === "error" ? { line: prev.line ?? null, message: prev.reason ?? "" } : null} />
              {findings("code").map((f, i) => <p key={i} className={`bd-find ${f.severity}`}><b>Line {f.line}</b>{f.message}</p>)}
              {prev?.status === "error" ? <p className="bd-find error"><b>{prev.line ? `Line ${prev.line}` : "Run"}</b>{prev.reason}</p> : null}
            </>
          ) : null}
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
            if (mode === "english" || mode === "python") return null;
            const rows = mode === "blocks" && role !== "score" ? fromFormula(spec[role] as string) : null;
            return (
            <div key={role} className="bd-rule">
              <label htmlFor={`r-${role}`}>{label}</label>
              {rows ? <BlockRows id={`b-${role}`} rows={rows.length ? rows : [{ left: "", op: ">", right: "", join: "&" } as Row]} suggestions={catalogue}
                onChange={(r) => edit({ [role]: toFormula(r) })} /> : null}
              {mode === "blocks" && role !== "score" && !rows ? <p className="bd-find warning"><b>Formula only</b>This rule is not a list of comparisons, so it stays as a formula.</p> : null}
              {rows ? null : <textarea id={`r-${role}`} className="input" spellCheck={false} rows={role === "score" || role === "market_filter" ? 1 : 2} placeholder={role === "market_filter" ? "market > sma(market, 200)" : undefined} value={spec[role] as string} onSelect={track(role)} onFocus={track(role)} onChange={(e) => edit({ [role]: e.target.value })} />}
              {findings(role).map((f, i) => <p key={i} className={`bd-find ${f.severity}`}><b>{f.severity === "error" ? "Error" : "Warning"}</b>{f.token ? <code>{f.token}</code> : null}{f.message}</p>)}
            </div>
          ); })}
          {findings("spec").map((f, i) => <p key={i} className="bd-find error"><b>Error</b>{f.message}</p>)}
        </section>

        <aside className="bd-side">
          <section className="bd-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h3 style={{ flex: 1 }}>Preview</h3>
              <input className="input" aria-label="Preview symbol" style={{ width: 90 }} value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </div>
            {prev?.status === "ok" ? (
              <>
                <p className="bd-meta" style={{ margin: 0 }}>{prev.trades.length} trades · {`${(prev.total_return ?? 0) >= 0 ? "+" : ""}${((prev.total_return ?? 0) * 100).toFixed(1)}%`} · last 2 years before the hold-out</p>
                {prev.repaint ? <p className={`bd-find ${prev.repaint.changed ? "error" : ""}`}><b style={{ color: prev.repaint.changed ? undefined : "var(--up)" }}>{prev.repaint.changed ? "Repaints" : "No look-ahead"}</b>
                  {prev.repaint.changed ? `signals changed at ${prev.repaint.changed} of ${prev.repaint.cuts} cuts (${prev.repaint.dates.join(", ")})` : `same signals at ${prev.repaint.cuts} history cuts`}</p> : null}
                <TimeSeries data={prev.bars} series={[{ key: "close", label: symbol.toUpperCase(), color: "var(--text-2)" }]} height={180} legend={false}
                  markers={prev.trades.flatMap((t) => [{ date: t.entry_date, label: t.side === "long" ? "▲" : "▼", color: "var(--up)" }, { date: t.exit_date, label: "×", color: "var(--down)" }])} />
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
          <section className="bd-card" id="bd-params">
            <h3>Parameters</h3>
            {params.map(([k, p]) => (
              <div key={k} className="bd-param">
                <code>{k}</code>
                <Num label="Value" value={p.value} onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, value: v ?? 0 } } })} />
                <Num label="Min" value={p.min} empty onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, min: v } } })} />
                <Num label="Max" value={p.max} empty onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, max: v } } })} />
                <Num label="Step" value={p.step} empty onChange={(v) => edit({ params: { ...spec.params, [k]: { ...p, step: v } } })} />
                <button className="btn sm" aria-label={`Remove ${k}`} onClick={() => { const { [k]: _, ...rest } = spec.params; edit({ params: rest }); }}><Trash2 size={12} /></button>
              </div>
            ))}
            {sweep ? <p className="bd-meta" style={{ margin: 0 }}>{sweep.toLocaleString()} settings in a full sweep</p> : null}
            <button className="btn sm" onClick={() => setPalette(true)}><Plus size={12} />Parameter</button>
          </section>
        </aside>

        <section className="bd-card" id="bd-exits">
          <h3>Exits</h3>
          <div className="bd-nums">{EXITS.map(([k, l, p]) => <Num key={k} label={l} pct={p} value={spec.exits[k]} onChange={(v) => edit({ exits: { ...spec.exits, [k]: v ?? 0 } })} />)}</div>
        </section>
        <section className="bd-card">
          <h3>Sizing</h3>
          <div className="bd-nums">
            <label className="bd-num"><span>Mode</span>
              <select className="input" value={spec.sizing.mode} onChange={(e) => edit({ sizing: { ...spec.sizing, mode: e.target.value } })}>
                <option value="equal">Equal</option><option value="pct_equity">% of equity</option><option value="risk">Risk per trade</option><option value="vol_target">Vol target</option><option value="cash">Fixed $</option><option value="shares">Fixed shares</option>
              </select>
            </label>
            {spec.sizing.mode !== "equal" ? <Num label={spec.sizing.mode === "shares" ? "Shares" : spec.sizing.mode === "cash" ? "Dollars" : spec.sizing.mode === "vol_target" ? "Annual vol" : "Percent"} pct={spec.sizing.mode === "pct_equity" || spec.sizing.mode === "risk" || spec.sizing.mode === "vol_target"}
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
      </div>
    </div>
  );
}
