"use client";

import { Bug, FileCode2, FilePlus2, LayoutTemplate, ListTree, Pencil, Trash2, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import toast from "react-hot-toast";
import { SERIES } from "@/charts/core";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import { studio, usePyTemplates } from "../api";
import { CodeEditor, type Problem } from "./CodeEditor";

type Log = { date: string; symbol: string | null; line: number; text: string; level: string };
type Point = { date: string; symbol: string | null; value: number | null };
export type DevPreview = {
  status: string; reason?: string; line?: number | null; problem?: { file?: string | null; line?: number | null; column?: number | null; exception_type?: string | null } | null;
  trades: Record<string, unknown>[]; logs?: Log[]; plots?: Record<string, Point[]>; warmup?: { bars: number; first_eligible_date: string | null } | null;
};
type Sym = { name: string; kind: string; line: number; column: number; children: Sym[] };
type Debug = { date: string; symbol: string; bar_index: number; state: Record<string, unknown>; context: Record<string, number | null>; orders: Record<string, unknown>[]; fills: Record<string, unknown>[];
  previous_date: string | null; next_date: string | null; breakpoint?: { file: string; line: number; hit_count: number; locals: Record<string, unknown> } | null; equity_change?: number | null };
type QC = { ok: boolean; code: string; symbols: string[]; converted: { line: number; before: string; after: string }[]; unconverted: { line: number; source: string; reason: string }[] };
type Tab = "problems" | "output" | "plots" | "trades" | "debug";
type Spec = { code: string; files?: Record<string, string>; params: Record<string, { value: number }>; [k: string]: unknown };

const store = { get: (k: string, f: number) => { try { return Number(localStorage.getItem(k)) || f; } catch { return f; } }, set: (k: string, v: number) => { try { localStorage.setItem(k, String(v)); } catch { /* blocked */ } } };
const show = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(4)) : typeof v === "object" ? JSON.stringify(v) : String(v));

/** Build › Dev: files and outline on the left, the editor in tabs, Problems / Output / Plots / Trades / Debug below, preview and checks on the right. */
export function DevIDE({ spec, edit, symbol, prev, side, onSave, onRun, compileProblems }: {
  spec: Spec; edit: (next: Partial<Spec>) => void; symbol: string; prev: DevPreview | null; side: ReactNode;
  onSave: () => void; onRun: () => void; compileProblems: Problem[];
}) {
  const files = useMemo(() => ({ "main.py": spec.code, ...(spec.files ?? {}) }), [spec.code, spec.files]);
  const [open, setOpen] = useState<string[]>(["main.py"]);
  const [active, setActive] = useState("main.py");
  const [rail, setRail] = useState<"files" | "outline" | "templates">("files");
  const [tab, setTab] = useState<Tab>("problems");
  const [lint, setLint] = useState<Problem[]>([]);
  const [outline, setOutline] = useState<Sym[]>([]);
  const [cursor, setCursor] = useState({ line: 1, column: 1 });
  const [reveal, setReveal] = useState<{ line: number; column?: number; n: number } | null>(null);
  const [panel, setPanel] = useState(() => store.get("studio:dev:panel", 260));
  const [logFilter, setLogFilter] = useState("");
  const [dbg, setDbg] = useState<Debug | null>(null);
  const [dbgDate, setDbgDate] = useState("");
  const [cond, setCond] = useState("");
  const [qc, setQc] = useState<QC | null>(null);
  const qcRef = useRef<HTMLDialogElement>(null);
  const pyTemplates = usePyTemplates();
  const source = files[active] ?? "";

  const setFile = (name: string, text: string) => (name === "main.py" ? edit({ code: text }) : edit({ files: { ...(spec.files ?? {}), [name]: text } }));
  const goto = (file: string, line: number, column?: number) => { if (!(file in files)) return; setOpen((o) => (o.includes(file) ? o : [...o, file])); setActive(file); setReveal({ line, column, n: Date.now() }); };
  const close = (f: string) => { const rest = open.filter((x) => x !== f); setOpen(rest.length ? rest : ["main.py"]); if (active === f) setActive(rest.at(-1) ?? "main.py"); };

  // Lint and outline the open file 300 ms after typing stops.
  useEffect(() => {
    const t = setTimeout(() => {
      void studio<{ problems: Problem[] }>("POST", "/build/check", { code: source, file: active, files, params: Object.fromEntries(Object.entries(spec.params).map(([k, p]) => [k, p.value])) }).then((r) => setLint(r.problems), () => undefined);
      void studio<Sym[]>("POST", "/build/outline", { code: source }).then(setOutline, () => undefined);
    }, 300);
    return () => clearTimeout(t);
  }, [source, active, files, spec.params]);

  const runtime: Problem[] = prev?.status === "error" ? [{ severity: "error", file: prev.problem?.file ?? "main.py", line: prev.problem?.line ?? prev.line ?? 1, column: prev.problem?.column ?? 1, end_column: 200, code: prev.problem?.exception_type ?? "runtime", message: prev.reason ?? "Run failed" }] : [];
  const problems = [...lint, ...compileProblems.filter((p) => p.file === active), ...runtime];
  const errors = problems.filter((p) => p.severity === "error").length, warnings = problems.length - errors;
  const logs = (prev?.logs ?? []).filter((l) => !logFilter || `${l.date} ${l.symbol ?? ""} ${l.text}`.toLowerCase().includes(logFilter.toLowerCase()));
  const plots = Object.entries(prev?.plots ?? {});

  const debug = (body: Record<string, unknown>) => {
    const date = String(body.date || dbg?.date || dbgDate || (prev?.trades.at(-1)?.entry_date ?? ""));
    if (!date) return toast.error("Pick a date to stop at");
    void studio<Debug>("POST", "/build/debug", { spec, symbol, date, ...body }).then((d) => { setDbg(d); setDbgDate(d.date); if (d.breakpoint) goto(d.breakpoint.file, d.breakpoint.line); }, (e: Error) => toast.error(e.message));
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
  const dropFile = (f: string) => { const { [f]: _, ...rest } = spec.files ?? {}; edit({ files: rest }); close(f); toast(`${f} deleted · ⌘Z to undo`); };
  const drag = (e: React.PointerEvent) => {
    const y0 = e.clientY, h0 = panel;
    const move = (m: PointerEvent) => setPanel(Math.min(Math.max(h0 - (m.clientY - y0), 120), window.innerHeight * 0.7));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); setPanel((h) => { store.set("studio:dev:panel", h); return h; }); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const outlineRows = (items: Sym[], depth = 0): ReactNode => items.map((s) => (
    <div key={`${s.name}${s.line}`}>
      <button className="dv-item" style={{ paddingLeft: 10 + depth * 14 }} onClick={() => goto(active, s.line, s.column)}><i className={`dv-k dv-k-${s.kind}`}>{s.kind[0]}</i>{s.name}<span>{s.line}</span></button>
      {outlineRows(s.children, depth + 1)}
    </div>
  ));
  const TABS: [Tab, string, number | null][] = [["problems", "Problems", problems.length], ["output", "Output", prev?.logs?.length ?? null], ["plots", "Plots", plots.length || null], ["trades", "Trades", prev?.trades.length ?? null], ["debug", "Debug", null]];

  return (
    <div className="dv" style={{ ["--panel-h" as string]: `${panel}px` }}>
      <nav className="dv-rail" aria-label="Project">
        <div className="seg dv-railtabs" role="group" aria-label="Side panel">
          {([["files", <FileCode2 key="f" size={14} />, "Files"], ["outline", <ListTree key="o" size={14} />, "Outline"], ["templates", <LayoutTemplate key="t" size={14} />, "Starters"]] as const).map(([k, icon, l]) => (
            <button key={k} type="button" aria-pressed={rail === k} title={l} onClick={() => setRail(k)}>{icon}<span>{l}</span></button>
          ))}
        </div>
        {rail === "files" ? (
          <div className="dv-list">
            {Object.keys(files).map((f) => (
              <div key={f} className="dv-file" data-on={f === active || undefined}>
                <button className="dv-item" onClick={() => goto(f, reveal?.line ?? 1)}><FileCode2 size={13} />{f}</button>
                {f !== "main.py" ? <><button className="icon-btn" aria-label={`Rename ${f}`} onClick={() => renameFile(f)}><Pencil size={12} /></button><button className="icon-btn" aria-label={`Delete ${f}`} onClick={() => dropFile(f)}><Trash2 size={12} /></button></> : null}
              </div>
            ))}
            <button className="btn sm ghost" onClick={addFile}><FilePlus2 size={13} />New file</button>
          </div>
        ) : rail === "outline" ? (
          <div className="dv-list">{outline.length ? outlineRows(outline) : <p className="dv-empty">No classes or functions</p>}</div>
        ) : (
          <div className="dv-list">
            {(pyTemplates.data ?? []).map((t) => <button key={t.name} className="dv-tpl" onClick={() => { edit({ ...(t.spec as Partial<Spec>) }); setOpen(["main.py"]); setActive("main.py"); }}><b>{t.name}</b><span>{t.rule}</span></button>)}
            <button className="btn sm ghost" onClick={() => { setQc(null); qcRef.current?.showModal(); }}><Upload size={13} />QuantConnect algorithm</button>
          </div>
        )}
      </nav>

      <section className="dv-main">
        <div className="dv-tabs" role="tablist">
          {open.map((f) => (
            <div key={f} role="tab" aria-selected={f === active} className="dv-tab" onClick={() => setActive(f)} onAuxClick={(e) => { if (e.button === 1) close(f); }}>
              {f}{open.length > 1 ? <button className="icon-btn" aria-label={`Close ${f}`} onClick={(e) => { e.stopPropagation(); close(f); }}><X size={11} /></button> : null}
            </div>
          ))}
        </div>
        <div className="dv-editor">
          {!spec.code.trim() && active === "main.py" ? (
            <div className="dv-blank">
              <b>This strategy runs on its rules</b>
              <div><button className="btn primary" onClick={() => void studio<{ code: string }>("POST", "/to-python", { spec }).then((r) => edit({ code: r.code }), (e: Error) => toast.error(e.message))}>Convert rules to Python</button>
                <button className="btn" onClick={() => setRail("templates")}>Start from a starter</button></div>
            </div>
          ) : null}
          <CodeEditor path={active} value={source} onChange={(t) => setFile(active, t)} problems={problems} onSave={onSave} onRun={onRun} reveal={reveal} onCursor={(line, column) => setCursor({ line, column })}
            project={{ file: active, files, params: Object.keys(spec.params), symbols: [symbol], goto }} />
        </div>
        <div className="dv-grip" role="separator" aria-orientation="horizontal" aria-label="Resize panel" onPointerDown={drag} />
        <div className="dv-panel">
          <div className="dv-ptabs" role="tablist">
            {TABS.map(([k, l, n]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{n ? <span className="num">{n}</span> : null}</button>)}
          </div>
          <div className="dv-pbody">
            {tab === "problems" ? (problems.length ? problems.map((p, i) => (
              <button key={i} className="dv-prob" onClick={() => goto(p.file, p.line, p.column)}><b className={p.severity}>{p.severity}</b><span>{p.message}</span><i>{p.file}:{p.line}:{p.column}{p.code ? ` ${p.code}` : ""}</i></button>
            )) : <p className="dv-empty">No problems</p>) : null}
            {tab === "output" ? (
              <>
                <input className="input dv-filter" placeholder="Filter by date, symbol or text" aria-label="Filter output" value={logFilter} onChange={(e) => setLogFilter(e.target.value)} />
                {logs.length ? <div className="dv-logs">{logs.map((l, i) => <button key={i} className="dv-log" data-level={l.level} onClick={() => goto("main.py", l.line)}><time>{l.date}</time><span>{l.symbol ?? ""}</span><code>{l.text}</code><i>:{l.line}</i></button>)}</div>
                  : <p className="dv-empty">{prev?.logs ? "Nothing matches" : "print() and ctx.log() appear here after a preview"}</p>}
              </>
            ) : null}
            {tab === "plots" ? (plots.length ? plots.map(([name, pts], i) => (
              <div key={name} className="dv-plot"><b>{name}</b><TimeSeries data={pts.filter((p) => p.value !== null).map((p) => ({ date: p.date, v: p.value }))} series={[{ key: "v", label: name, color: SERIES[i % SERIES.length] }]} height={140} legend={false} /></div>
            )) : <p className="dv-empty">ctx.plot(name, value) draws here</p>) : null}
            {tab === "trades" ? (prev?.trades.length ? <DataTable rows={prev.trades} opts={{ viewKey: "studio:dev:trades" }} /> : <p className="dv-empty">No trades in the preview</p>) : null}
            {tab === "debug" ? (
              <div className="dv-debug">
                <div className="dv-dbar">
                  <input className="input" type="date" aria-label="Stop at date" value={dbgDate} onChange={(e) => setDbgDate(e.target.value)} />
                  <button className="btn sm primary" onClick={() => debug({ date: dbgDate })}><Bug size={13} />Stop here</button>
                  <button className="btn sm" disabled={!dbg?.previous_date} onClick={() => debug({ step: -1 })}>◀ Bar</button>
                  <button className="btn sm" disabled={!dbg?.next_date} onClick={() => debug({ step: 1 })}>Bar ▶</button>
                  <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "order" })}>Next order</button>
                  <button className="btn sm" disabled={!dbg} onClick={() => debug({ event: "fill" })}>Next fill</button>
                  <span className="dv-sep" />
                  <input className="input" aria-label="Breakpoint condition" placeholder="condition" value={cond} onChange={(e) => setCond(e.target.value)} />
                  <button className="btn sm" onClick={() => debug({ breakpoint: { file: active, line: cursor.line, condition: cond || null } })}>Break at {active}:{cursor.line}</button>
                </div>
                {dbg ? (
                  <div className="dv-dgrid">
                    <div><h4>{dbg.symbol} · {dbg.date} · bar {dbg.bar_index}{dbg.breakpoint ? ` · hit ${dbg.breakpoint.hit_count}` : ""}</h4>
                      <DataTable rows={Object.entries(dbg.context).map(([k, v]) => ({ ctx: k, value: v }))} /></div>
                    <div><h4>self</h4>
                      <DataTable rows={Object.entries({ ...dbg.state, ...(dbg.breakpoint?.locals ?? {}) }).map(([k, v]) => ({ name: k, value: show(v) }))} /></div>
                    <div><h4>Orders</h4>{dbg.orders.length ? <DataTable rows={dbg.orders} /> : <p className="dv-empty">None this bar</p>}
                      <h4>Fills</h4>{dbg.fills.length ? <DataTable rows={dbg.fills} /> : <p className="dv-empty">None this bar</p>}</div>
                  </div>
                ) : <p className="dv-empty">Stops at the last preview trade, or the date set</p>}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <aside className="dv-side">{side}</aside>

      <footer className="dv-status">
        <span>{active}</span><span>Ln {cursor.line}, Col {cursor.column}</span>
        <button className="dv-sbtn" onClick={() => setTab("problems")}><b className="error">{errors}</b> errors <b className="warning">{warnings}</b> warnings</button>
        {prev?.warmup ? <span>warm-up {prev.warmup.bars} bars</span> : null}
        <span style={{ flex: 1 }} />
        <span>{prev ? (prev.status === "ok" ? `preview ${symbol}` : prev.status) : "no preview"}</span><span>Python 3.12</span>
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
