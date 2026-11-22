"use client";

import { Copy, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import toast from "react-hot-toast";
import { studio } from "../api";

/** One command and its result, shown as a block with a status, a duration and its output. */
type Block = { id: number; cmd: string; status: "run" | "ok" | "err"; ms: number; out: string; value?: unknown; at: string };
type Problem = { severity: string; line: number; message: string; code?: string };
type TestRow = { file: string; name: string; status: string; message?: string; error_line?: number | null };
type CellRow = { index: number | null; stdout: string; value: unknown; error: string | null; error_line: number | null };

export type TerminalHost = {
  files: Record<string, string>; code: string; extra: Record<string, string>; active: string; symbol: string; storeKey: string;
  /** Set while the debugger is paused: plain input is then a formula watched at that bar, as the old Console did. */
  paused: { symbol: string; date: string } | null; spec: unknown;
  run: (level: "quick" | "full", settings: Record<string, unknown>) => void; preview: () => void;
  goto: (file: string, line: number) => void; render: (value: unknown) => ReactNode;
};

const HELP = `atlas run [quick|full] [--symbols A,B] [--top 50] [--from 2018-01-01] [--to 2024-12-31] [--costs "US retail"] [--fill same_close]
atlas test [file]           run def test_* (all, or one file)
atlas cells <file> [n]      run the # %% cells of a file up to cell n
atlas check [file]          lint a file
atlas preview               refresh the preview
atlas compare SPY,QQQ,IWM   preview each symbol and compare return, trades, win rate
atlas task add <name> <cmd && cmd>   save a task;  atlas task <name>  run it;  atlas task list | rm <name>
clear                       clear the blocks;  reset  forget the Python session
Anything else is Python, run in a session that keeps its variables; load, np and pd are ready.
While the debugger is paused, plain input is a formula evaluated at the paused bar.`;
const PRELUDE = "from studio.research import load\nimport numpy as np\nimport pandas as pd";
const COMMANDS = ["atlas run quick", "atlas run full", "atlas test", "atlas cells", "atlas check", "atlas preview", "atlas compare", "atlas task list", "atlas task add", "atlas help", "clear", "reset"];

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
  const hist = useRef(-1), seq = useRef(0), end = useRef<HTMLDivElement>(null);
  useEffect(() => { save(`studio:repl:${host.storeKey}`, session); }, [session, host.storeKey]);
  useEffect(() => { save("studio:tasks", tasks); }, [tasks]);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [blocks.length]);

  const push = (cmd: string) => { const id = ++seq.current; setBlocks((b) => [...b.slice(-199), { id, cmd, status: "run", ms: 0, out: "", at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) }]); return id; };
  const done = (id: number, t0: number, patch: Partial<Block>) => setBlocks((b) => b.map((x) => (x.id === id ? { ...x, status: "ok", ms: performance.now() - t0, ...patch } : x)));
  const project = () => ({ code: host.code, files: host.extra });

  const python = async (src: string) => {
    const file = "__session__.py", cells = [...session, src];
    const text = [PRELUDE, ...cells].map((c) => `# %%\n${c}`).join("\n");
    const r = await studio<{ outputs: CellRow[] }>("POST", "/build/cells", { ...project(), files: { ...host.extra, [file]: text }, file, upto: cells.length, only: true, symbols: [host.symbol] });
    const last = r.outputs.at(-1);
    if (last?.error) return { status: "err" as const, out: `${last.stdout}${last.error}` };
    setSession(cells);
    return { status: "ok" as const, out: last?.stdout ?? "", value: last?.value ?? undefined };
  };

  const exec = async (line: string): Promise<{ status: "ok" | "err"; out: string; value?: unknown }> => {
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
      if (what === "add" && name && cmd.length) { setTasks((t) => ({ ...t, [name]: cmd.join(" ") })); return { status: "ok", out: `Saved task ${name}` }; }
      if (what === "rm" && name) { setTasks(({ [name]: _gone, ...t }) => t); return { status: "ok", out: `Removed task ${name}` }; }
      const steps = tasks[what];
      if (!steps) return { status: "err", out: `No task ${what}` };
      const outs: string[] = [];
      for (const step of steps.split("&&").map((s) => s.trim()).filter(Boolean)) {
        const r = await exec(step);
        outs.push(`› ${step}\n${r.out}`);
        if (r.status === "err") return { status: "err", out: outs.join("\n") };
      }
      return { status: "ok", out: outs.join("\n") };
    }
    return { status: "err", out: `Unknown command atlas ${sub}; try atlas help` };
  };

  const submit = (line: string) => {
    const cmd = line.trim();
    if (!cmd) return;
    setInput(""); hist.current = -1;
    if (cmd === "clear") return setBlocks([]);
    if (cmd === "reset") { setSession([]); return toast("Python session reset"); }
    const id = push(cmd), t0 = performance.now();
    void exec(cmd).then((r) => done(id, t0, r), (e: Error) => done(id, t0, { status: "err", out: e.message }));
  };
  const rerun = (cmd: string) => submit(cmd);
  // file.py:42 in output opens the line.
  const linked = (text: string) => text.split(/(\b[\w./-]+\.py:\d+\b)/g).map((part, i) => {
    const m = /^([\w./-]+\.py):(\d+)$/.exec(part);
    return m && m[1] in host.files ? <button key={i} className="dv-term-link" onClick={() => host.goto(m[1], Number(m[2]))}>{part}</button> : part;
  });

  return (
    <div className="dv-term" onClick={(e) => { if (e.target === e.currentTarget) (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus(); }}>
      {blocks.map((b) => (
        <section key={b.id} className="dv-term-block" data-st={b.status}>
          <header><span className="dv-con-q">› {b.cmd}</span><i>{b.status === "run" ? "running" : `${b.ms < 1000 ? `${Math.round(b.ms)} ms` : `${(b.ms / 1000).toFixed(1)} s`} · ${b.at}`}</i>
            <button className="icon-btn" aria-label="Run again" title="Run again" onClick={() => rerun(b.cmd)}><RotateCcw size={11} /></button>
            <button className="icon-btn" aria-label="Copy output" title="Copy output" onClick={() => void navigator.clipboard.writeText(`› ${b.cmd}\n${b.out}`).then(() => toast("Copied"))}><Copy size={11} /></button>
          </header>
          {b.out ? <pre data-err={b.status === "err" || undefined}>{linked(b.out)}</pre> : null}
          {b.value !== undefined && b.value !== null ? host.render(b.value) : null}
        </section>
      ))}
      <div ref={end} />
      <form onSubmit={(e) => { e.preventDefault(); submit(input); }}><span>›</span>
        <input aria-label="Terminal" list="dv-term-cmds" spellCheck={false} autoComplete="off" value={input} placeholder={host.paused ? `formula at ${host.paused.date}` : "atlas help, or Python"} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => {
          if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
          e.preventDefault(); const qs = blocks.map((b) => b.cmd); const n = hist.current === -1 ? qs.length : hist.current; const k = Math.max(0, Math.min(qs.length, n + (e.key === "ArrowUp" ? -1 : 1)));
          hist.current = k; setInput(qs[k] ?? "");
        }} />
        {session.length ? <button type="button" className="icon-btn" aria-label="Reset Python session" title={`Python session: ${session.length} statements · reset`} onClick={() => submit("reset")}><Trash2 size={11} /></button> : null}
        <datalist id="dv-term-cmds">{[...COMMANDS, ...Object.keys(tasks).map((t) => `atlas task ${t}`)].map((c) => <option key={c} value={c} />)}</datalist>
      </form>
    </div>
  );
}
