"use client";

import { Columns2, Copy, Download, Pin, RotateCcw, Tag, Trash2 } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import toast from "react-hot-toast";
import { copyText, studio } from "../api";

/** One command and its result, shown as a block with a status, a duration and its output. */
type Block = { id: number; cmd: string; status: "run" | "ok" | "err"; ms: number; out: string; value?: unknown; plots?: unknown[]; at: string };
type Problem = { severity: string; line: number; message: string; code?: string };
type TestRow = { file: string; name: string; status: string; message?: string; error_line?: number | null };
type CellRow = { index: number | null; stdout: string; value: unknown; error: string | null; error_line: number | null; plots?: unknown[] };

export type TerminalHost = {
  files: Record<string, string>; code: string; extra: Record<string, string>; active: string; symbol: string; storeKey: string;
  /** Set while the debugger is paused: plain input is then a formula watched at that bar, as the old Console did. */
  paused: { symbol: string; date: string } | null; spec: unknown;
  run: (level: "quick" | "full", settings: Record<string, unknown>) => void; preview: () => void;
  goto: (file: string, line: number) => void; render: (value: unknown) => ReactNode; plots: (plots: unknown[]) => ReactNode;
  /** Pause the debugger at a date (dates in output are links). */ atDate: (date: string) => void;
  /** Bumped on every save: tasks added with --on-save run then. */ saved: number;
  split?: { on: boolean; toggle: () => void };
  /** Code sent from the editor (Run selection in Console); runs when n changes. */ inject?: { cmd: string; n: number };
};

const HELP = `atlas run [quick|full] [--symbols A,B] [--top 50] [--from 2018-01-01] [--to 2024-12-31] [--costs "US retail"] [--fill same_close]
atlas test [file]           run def test_* (all, or one file)
atlas cells <file> [n]      run the # %% cells of a file up to cell n
atlas check [file]          lint a file
atlas preview               refresh the preview
atlas compare SPY,QQQ,IWM   preview each symbol and compare return, trades, win rate
atlas task add <name> [--on-save] <cmd && cmd>   save a task (--on-save: run it on every save);  atlas task <name>  run it;  atlas task list | rm <name>
clear                       clear the blocks;  reset  forget the Python session
Ctrl+R search history · Ctrl+↑/↓ jump between commands
Anything else is Python, run in a session that keeps its variables; load, plot, sql, np and pd are ready.
While the debugger is paused, plain input is a formula evaluated at the paused bar.`;
const PRELUDE = "from studio.research import load, plot, sql\nimport numpy as np\nimport pandas as pd";
const COMMANDS = ["atlas run quick", "atlas run full", "atlas run quick --symbols ", "atlas run quick --from ", "atlas test", "atlas cells", "atlas check", "atlas preview", "atlas compare ", "atlas task list", "atlas task add ", "atlas task add --on-save ", "atlas help", "clear", "reset"];
const TERM_COLORS = ["blue", "green", "amber", "red", "violet"];
const SUBS = ["run", "test", "cells", "check", "preview", "compare", "task", "help"];
/** Edit distance, for "did you mean". */
function dist(a: string, b: string) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array<number>(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0]![j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) d[i]![j] = Math.min(d[i - 1]![j]! + 1, d[i]![j - 1]! + 1, d[i - 1]![j - 1]! + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length]![b.length]!;
}
const nearest = (word: string, pool: string[]) => pool.filter((w) => w !== word).map((w) => [w, dist(word, w)] as const).filter(([, n]) => n <= 2).sort((x, y) => x[1] - y[1])[0]?.[0];
/** Characters of q in order inside s (history search). */
export const fuzzy = (q: string, s: string) => { let i = 0; for (const c of s.toLowerCase()) if (c === q[i]?.toLowerCase()) i++; return i === q.length; };

/** Split a command line on spaces, keeping "quoted parts" together. */
export const words = (line: string) => [...line.matchAll(/"([^"]*)"|(\S+)/g)].map((m) => m[1] ?? m[2]);

/** `atlas run` flags to run settings (the same keys as run configurations). */
export function runArgs(args: string[]): { level: "quick" | "full"; settings: Record<string, unknown> } {
  const settings: Record<string, unknown> = {};
  let level: "quick" | "full" = "quick";
  for (let i = 0; i < args.length; i++) {
    const a = args[i], v = args[i + 1];
    if (a === "full" || a === "quick") level = a;
    else if (a === "--symbols" && v) { settings.symbols = v.replace(/,/g, " ").toUpperCase(); i++; }
    else if (a === "--top" && v) { settings.top_n = Number(v); i++; }
    else if (a === "--from" && v) { settings.start = v; i++; }
    else if (a === "--to" && v) { settings.end = v; i++; }
    else if (a === "--costs" && v) { settings.cost_profile = v; i++; }
    else if (a === "--fill" && v) { settings.fill = v; i++; }
    else throw new Error(`Unknown flag ${a}; try atlas help`);
  }
  return { level, settings };
}

const load = <T,>(key: string, fallback: T): T => { try { return JSON.parse(localStorage.getItem(key) ?? "") as T; } catch { return fallback; } };
const save = (key: string, value: unknown) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* blocked */ } };

/** Terminal (bottom panel): `atlas` commands, a Python session that survives reloads, saved tasks, and blocks you can copy. */
export function Terminal({ host }: { host: TerminalHost }) {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [input, setInput] = useState("");
  const [tasks, setTasks] = useState<Record<string, string>>(() => load("studio:tasks", {}));
  // shortcut: the Python session is replayed from its saved statements on every input (no live kernel); fine for research-sized work.
  const [session, setSession] = useState<string[]>(() => load(`studio:repl:${host.storeKey}`, []));
  const taskStack = useRef<string[]>([]);
  const hist = useRef(-1), seq = useRef(0), end = useRef<HTMLDivElement>(null), box = useRef<HTMLDivElement>(null);
  const [history, setHistory] = useState<string[]>(() => load("studio:termhist", []));
  const [pins, setPins] = useState<string[]>(() => load("studio:termpins", []));
  const [pick, setPick] = useState(false); // Ctrl+R: fuzzy history search
  const listId = useId();
  // Name and colour per terminal (JetBrains tab rename / colour), remembered per terminal.
  const [label, setLabel] = useState<{ name: string; color: string }>(() => load(`studio:term:label:${host.storeKey}`, { name: "", color: "" }));
  const relabel = () => {
    const name = window.prompt("Terminal name (blank for none)", label.name); if (name === null) return;
    const color = window.prompt(`Colour: ${TERM_COLORS.join(", ")} (blank for none)`, label.color) ?? label.color;
    const next = { name: name.trim(), color: TERM_COLORS.includes(color.trim()) ? color.trim() : "" };
    setLabel(next); try { localStorage.setItem(`studio:term:label:${host.storeKey}`, JSON.stringify(next)); } catch { /* private mode */ }
  };
  // Console completions: names the session assigned, and load('SYM') from the market file's symbols.
  const names = [...new Set(session.flatMap((st) => [...st.matchAll(/^(\w+)\s*=(?!=)/gm)].map((m) => m[1]!)))];
  const symQ = /load\(['"]([A-Za-z0-9.^-]*)$/.exec(input)?.[1];
  const [syms, setSyms] = useState<string[]>([]);
  useEffect(() => {
    if (symQ === undefined) return;
    const t = setTimeout(() => void studio<{ symbols: { symbol: string }[] }>("GET", `/data/symbols?q=${encodeURIComponent(symQ)}&limit=20`).then((r) => setSyms(r.symbols.map((x) => x.symbol)), () => undefined), 150);
    return () => clearTimeout(t);
  }, [symQ]);
  useEffect(() => { save("studio:termhist", history); }, [history]);
  useEffect(() => { save("studio:termpins", pins); }, [pins]);
  useEffect(() => { save(`studio:repl:${host.storeKey}`, session); }, [session, host.storeKey]);
  useEffect(() => { save("studio:tasks", tasks); }, [tasks]);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [blocks.length]);

  const push = (cmd: string) => { const id = ++seq.current; setBlocks((b) => [...b.slice(-199), { id, cmd, status: "run", ms: 0, out: "", at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) }]); return id; };
  const done = (id: number, t0: number, patch: Partial<Block>) => setBlocks((b) => b.map((x) => (x.id === id ? { ...x, status: "ok", ms: performance.now() - t0, ...patch } : x)));
  const project = () => ({ code: host.code, files: host.extra });

  // Python runs in a live kernel (one per session): only the new statement runs; after a restart the saved statements replay once.
  const python = async (src: string) => {
    const file = "__session__.py", key = `console:${host.storeKey}`;
    const syms = [...new Set([host.symbol, ...[...[...session, src].join("\n").matchAll(/load\(\s*["']([\w.^=-]+)["']/g)].map((m) => m[1]!.toUpperCase())])].slice(0, 5);
    const call = (cells: string[], run: number[]) => studio<{ outputs: CellRow[]; restarted: boolean }>("POST", "/build/kernel", { key, ...project(), files: { ...host.extra, [file]: [PRELUDE, ...cells].map((c) => `# %%\n${c}`).join("\n") }, file, cells: run, symbols: syms });
    let r = await call([src], [1]);
    if (r.restarted) r = await call([...session, src], [...Array(session.length + 2).keys()]);
    const last = r.outputs.at(-1);
    if (last?.error) return { status: "err" as const, out: `${last.stdout}${last.error}` };
    setSession((x) => [...x, src]);
    return { status: "ok" as const, out: last?.stdout ?? "", value: last?.value ?? undefined, plots: last?.plots };
  };

  const exec = async (line: string): Promise<{ status: "ok" | "err"; out: string; value?: unknown; plots?: unknown[] }> => {
    const [head, sub, ...rest] = words(line);
    if (head !== "atlas") {
      if (host.paused) {
        const [r] = await studio<{ error: string | null; value: unknown }[]>("POST", "/build/watch", { spec: host.spec, symbol: host.paused.symbol, date: host.paused.date, expressions: [line], history: 1 });
        return r.error ? { status: "err", out: r.error } : { status: "ok", out: "", value: r.value };
      }
      return python(line);
    }
    if (!sub || sub === "help") return { status: "ok", out: HELP };
    if (sub === "run") { const { level, settings } = runArgs(rest); host.run(level, settings); return { status: "ok", out: `Started a ${level} run${Object.keys(settings).length ? ` with ${JSON.stringify(settings)}` : ""}. Results open beside the code.` }; }
    if (sub === "compare") {
      // Compound launch: preview each symbol over the same window and compare.
      const syms = rest.join(",").split(/[\s,]+/).map((x) => x.toUpperCase()).filter(Boolean).slice(0, 12);
      if (syms.length < 2) return { status: "err", out: "atlas compare SPY,QQQ,IWM (2 to 12 symbols)" };
      type P = { status: string; reason?: string; total_return?: number; trades: { return: number }[] };
      const rows = await Promise.all(syms.map((symbol) => studio<P>("POST", "/preview", { spec: host.spec, symbol, repaint: false }).then((r) => [symbol, r] as const, (e: Error) => [symbol, { status: "error", reason: e.message, trades: [] }] as const)));
      const pct = (x?: number) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
      const table = [["Symbol", "Return", "Trades", "Win rate"], ...rows.map(([sym, r]) => (r.status === "ok" ? [sym, pct(r.total_return), String(r.trades.length), r.trades.length ? pct(r.trades.filter((t) => t.return > 0).length / r.trades.length) : "—"] : [sym, r.reason ?? r.status, "", ""]))];
      const w = table[0]!.map((_, c) => Math.max(...table.map((r) => r[c]!.length)));
      return { status: "ok", out: table.map((r) => r.map((x, c) => (c ? x.padStart(w[c]!) : x.padEnd(w[c]!))).join("  ")).join("\n") };
    }
    if (sub === "preview") { host.preview(); return { status: "ok", out: "Preview refreshed" }; }
    if (sub === "test") {
      const r = await studio<{ tests: TestRow[] }>("POST", "/build/test", { ...project(), ...(rest[0] ? { file: rest[0] } : {}) });
      const bad = r.tests.filter((t) => t.status !== "passed");
      if (!r.tests.length) return { status: "ok", out: "No test_*.py files" };
      const out = r.tests.map((t) => `${t.status === "passed" ? "✓" : "✗"} ${t.file}:${t.error_line ?? ""} ${t.name}${t.message ? `  ${t.message}` : ""}`).join("\n");
      return { status: bad.length ? "err" : "ok", out: `${out}\n${r.tests.length - bad.length}/${r.tests.length} passed` };
    }
    if (sub === "cells") {
      const file = rest[0] ?? host.active;
      const r = await studio<{ outputs: CellRow[] }>("POST", "/build/cells", { ...project(), file, upto: rest[1] ? Number(rest[1]) - 1 : 999, only: false, symbols: [host.symbol] });
      const err = r.outputs.find((o) => o.error);
      return { status: err ? "err" : "ok", out: r.outputs.map((o) => `[${(o.index ?? 0) + 1}] ${o.stdout}${o.error ? `${file}:${o.error_line} ${o.error}` : ""}`).join("\n"), value: r.outputs.at(-1)?.value ?? undefined };
    }
    if (sub === "check") {
      const file = rest[0] ?? host.active;
      const r = await studio<{ problems: Problem[] }>("POST", "/build/check", { code: host.files[file] ?? "", file, files: host.files });
      return { status: r.problems.some((p) => p.severity === "error") ? "err" : "ok", out: r.problems.map((p) => `${p.severity} ${file}:${p.line} ${p.message}`).join("\n") || "No problems" };
    }
    if (sub === "task") {
      const [what, name, ...cmd] = rest;
      if (!what || what === "list") return { status: "ok", out: Object.entries(tasks).map(([k, v]) => `${k}: ${v}`).join("\n") || "No tasks. atlas task add <name> \"atlas check && atlas run quick\"" };
      if (what === "add" && name === "--on-save" && cmd.length > 1) { const [n, ...c] = cmd; setTasks((t) => ({ ...t, [n!]: `@save ${c.join(" ")}` })); return { status: "ok", out: `Saved task ${n}; it runs on every save` }; }
      if (what === "add" && name && cmd.length) { setTasks((t) => ({ ...t, [name]: cmd.join(" ") })); return { status: "ok", out: `Saved task ${name}` }; }
      if (what === "rm" && name) { setTasks(({ [name]: _gone, ...t }) => t); return { status: "ok", out: `Removed task ${name}` }; }
      const steps = tasks[what];
      if (!steps) return { status: "err", out: `No task ${what}` };
      // A task that calls itself, directly or through others, stops instead of looping forever.
      if (taskStack.current.includes(what) || taskStack.current.length >= 8) return { status: "err", out: `Task ${what} calls itself (${[...taskStack.current, what].join(" → ")})` };
      taskStack.current.push(what);
      try {
        const outs: string[] = [];
        for (const step of steps.replace(/^@save /, "").split("&&").map((s) => s.trim()).filter(Boolean)) {
          const r = await exec(step);
          outs.push(`› ${step}\n${r.out}`);
          if (r.status === "err") return { status: "err", out: outs.join("\n") };
        }
        return { status: "ok", out: outs.join("\n") };
      } finally { taskStack.current.pop(); }
    }
    const near = nearest(sub, SUBS);
    return { status: "err", out: `Unknown command atlas ${sub}${near ? `; did you mean atlas ${near}?` : ""}; try atlas help` };
  };

  const submit = (line: string) => {
    const cmd = line.trim();
    if (!cmd) return;
    setInput(""); hist.current = -1; setPick(false);
    setHistory((h) => [cmd, ...h.filter((x) => x !== cmd)].slice(0, 100));
    if (cmd === "clear") return setBlocks([]);
    if (cmd === "reset") { setSession([]); void studio("DELETE", `/build/kernel/console:${host.storeKey}`).catch(() => undefined); return toast("Python session reset"); }
    const id = push(cmd), t0 = performance.now();
    void exec(cmd).then((r) => done(id, t0, r), (e: Error) => done(id, t0, { status: "err", out: e.message }));
  };
  const rerun = (cmd: string) => submit(cmd);
  const injected = useRef(host.inject?.n ?? 0);
  useEffect(() => { if (host.inject && host.inject.n !== injected.current) { injected.current = host.inject.n; submit(host.inject.cmd); } }, [host.inject?.n]); // eslint-disable-line react-hooks/exhaustive-deps
  // Tasks added with --on-save run after each save.
  const lastSave = useRef(host.saved);
  useEffect(() => {
    if (host.saved === lastSave.current) return;
    lastSave.current = host.saved;
    for (const [name, steps] of Object.entries(tasks)) if (steps.startsWith("@save ")) submit(`atlas task ${name}`);
  }, [host.saved]); // eslint-disable-line react-hooks/exhaustive-deps
  // Quick fix: a NameError or an unknown atlas command offers the nearest known name.
  const fix = (b: Block) => {
    if (b.status !== "err") return null;
    const m = /NameError: name '(\w+)' is not defined/.exec(b.out);
    if (m) {
      const known = [...new Set([..."load plot sql np pd".split(" "), ...session.flatMap((c) => [...c.matchAll(/^\s*([A-Za-z_]\w*)\s*=(?!=)/gm)].map((x) => x[1]!))])];
      const near = nearest(m[1]!, known);
      return near ? [`Use ${near}`, b.cmd.replace(new RegExp(`\\b${m[1]}\\b`, "g"), near)] as const : null;
    }
    const a = /did you mean (atlas \w+)\?/.exec(b.out);
    return a ? [`Run ${a[1]}`, b.cmd.replace(/^atlas \S+/, a[1]!)] as const : null;
  };
  // Links in output: file.py:42 opens the line, a date pauses the debugger there, a URL opens in a new tab.
  const linked = (text: string) => text.split(/(\b[\w./-]+\.py:\d+\b|\b\d{4}-\d{2}-\d{2}\b|https?:\/\/[^\s)]+)/g).map((part, i) => {
    const m = /^([\w./-]+\.py):(\d+)$/.exec(part);
    if (m && m[1]! in host.files) return <button key={i} className="dv-term-link" onClick={() => host.goto(m[1]!, Number(m[2]))}>{part}</button>;
    if (/^\d{4}-\d{2}-\d{2}$/.test(part)) return <button key={i} className="dv-term-link" title="Pause the debugger at this date" onClick={() => host.atDate(part)}>{part}</button>;
    if (/^https?:\/\//.test(part)) return <a key={i} className="dv-term-link" href={part} target="_blank" rel="noreferrer noopener">{part}</a>;
    return part;
  });
  const md = (b: Block) => `\`\`\`\n› ${b.cmd}\n${b.out}\n\`\`\``;
  const saveMd = (b: Block) => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([md(b)], { type: "text/markdown" })); a.download = `atlas-${b.id}.md`; a.click(); URL.revokeObjectURL(a.href); };
  // Ctrl+Up/Down: move between command blocks.
  const hop = (from: HTMLElement | null, dir: 1 | -1) => {
    const all = [...(box.current?.querySelectorAll<HTMLElement>(".dv-term-block") ?? [])];
    const i = from ? all.indexOf(from) : all.length;
    all[Math.max(0, Math.min(all.length - 1, i + dir))]?.focus();
  };
  const picks = pick ? [...new Set([...pins, ...history])].filter((h) => fuzzy(input, h)).slice(0, 12) : [];

  return (
    <div className="dv-term-wrap" data-color={label.color || undefined}>
    <div className="dv-term" ref={box} onClick={(e) => { if (e.target === e.currentTarget) (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus(); }}>
      {blocks.map((b) => (
        <section key={b.id} className="dv-term-block" data-st={b.status} tabIndex={-1} data-block={b.id}
          onKeyDown={(e) => { if (e.ctrlKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) { e.preventDefault(); hop(e.currentTarget, e.key === "ArrowUp" ? -1 : 1); } }}>
          <header><span className="dv-con-q">› {b.cmd}</span><i>{b.status === "run" ? "running" : `${b.ms < 1000 ? `${Math.round(b.ms)} ms` : `${(b.ms / 1000).toFixed(1)} s`} · ${b.at}`}</i>
            <button className="icon-btn" aria-label="Run again" title="Run again" onClick={() => rerun(b.cmd)}><RotateCcw size={11} /></button>
            <button className="icon-btn" aria-label="Pin command" title={pins.includes(b.cmd) ? "Unpin" : "Pin to the top of history"} aria-pressed={pins.includes(b.cmd)} onClick={() => setPins((p) => (p.includes(b.cmd) ? p.filter((x) => x !== b.cmd) : [b.cmd, ...p]))}><Pin size={11} /></button>
            <button className="icon-btn" aria-label="Copy as Markdown" title="Copy as Markdown" onClick={() => void copyText(md(b))}><Copy size={11} /></button>
            <button className="icon-btn" aria-label="Save as Markdown" title="Save as Markdown" onClick={() => saveMd(b)}><Download size={11} /></button>
          </header>
          {b.out ? <pre data-err={b.status === "err" || undefined}>{linked(b.out)}</pre> : null}
          {(() => { const f = fix(b); return f ? <button className="btn sm ghost dv-term-fix" onClick={() => submit(f[1])}>{f[0]}</button> : null; })()}
          {b.plots?.length ? host.plots(b.plots) : null}
          {b.value !== undefined && b.value !== null ? host.render(b.value) : null}
        </section>
      ))}
      <div ref={end} />
      {pick ? <ul className="dv-term-pick" aria-label="History">{picks.length ? picks.map((h) => <li key={h}><button type="button" onClick={() => submit(h)}>{pins.includes(h) ? <Pin size={10} /> : null}{h}</button></li>) : <li className="dv-empty">No match</li>}</ul> : null}
      <form onSubmit={(e) => { e.preventDefault(); submit(pick && picks[0] && !input.startsWith("atlas ") ? picks[0] : input); }}>{label.name ? <span className="dv-term-name">{label.name}</span> : null}<span>{pick ? "⌕" : "›"}</span>
        <input aria-label="Terminal" list={listId} spellCheck={false} autoComplete="off" value={input} placeholder={host.paused ? `formula at ${host.paused.date}` : "atlas help, or Python"} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => {
          if (e.ctrlKey && e.key.toLowerCase() === "r") { e.preventDefault(); setPick((p) => !p); return; }
          if (e.key === "Escape" && pick) { setPick(false); return; }
          if (e.ctrlKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) { e.preventDefault(); hop(null, -1); return; }
          if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
          e.preventDefault(); const qs = blocks.map((b) => b.cmd); const n = hist.current === -1 ? qs.length : hist.current; const k = Math.max(0, Math.min(qs.length, n + (e.key === "ArrowUp" ? -1 : 1)));
          hist.current = k; setInput(qs[k] ?? "");
        }} />
        {session.length ? <button type="button" className="icon-btn" aria-label="Reset Python session" title={`Python session: ${session.length} statements · reset`} onClick={() => submit("reset")}><Trash2 size={11} /></button> : null}
        <button type="button" className="icon-btn" aria-label="Rename terminal" title="Name and colour this terminal" onClick={relabel}><Tag size={11} /></button>
        {host.split ? <button type="button" className="icon-btn" aria-label="Split terminal" title="Split terminal" aria-pressed={host.split.on} onClick={host.split.toggle}><Columns2 size={11} /></button> : null}
        <datalist id={listId}>{[...new Set([...(symQ !== undefined ? syms.map((x) => input.replace(/[A-Za-z0-9.^-]*$/, x) + "')") : []), ...pins, ...COMMANDS, ...names, ...Object.keys(tasks).map((t) => `atlas task ${t}`), ...history.slice(0, 30)])].map((c) => <option key={c} value={c} />)}</datalist>
      </form>
    </div>
    {/* Overview ruler: one mark per command, red when it failed; click to jump. */}
    <div className="dv-term-ruler" aria-hidden>{blocks.map((b, i) => <button key={b.id} tabIndex={-1} data-st={b.status} style={{ top: `${(i / Math.max(1, blocks.length)) * 100}%` }} onClick={() => box.current?.querySelector<HTMLElement>(`[data-block="${b.id}"]`)?.scrollIntoView({ block: "start" })} />)}</div>
    </div>
  );
}
