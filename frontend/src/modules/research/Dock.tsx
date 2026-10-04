"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Maximize2, Minimize2, Minus, Trash2 } from "lucide-react";
import { useLayout } from "@/workspace/layout";
import { Chip, Tabs } from "@/workspace/ui";
import { useRuns } from "./api";
import { featureHref, metaFor } from "./catalog";
import { label } from "./format";
import { XYPlot } from "@/charts/XYPlot";
import type { RunRecord } from "./types";

type View = "runs" | "log" | "sweep";

const STATUS: Record<RunRecord["status"], { text: string; tone?: "accent" | "down" }> = {
  queued: { text: "Queued", tone: "accent" },
  running: { text: "Running", tone: "accent" },
  completed: { text: "Done" },
  failed: { text: "Failed", tone: "down" },
  cancelled: { text: "Cancelled" },
};

const time = (t: number) => new Date(t).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export function Dock({ runs, activeFeature, onMaximize }: { runs: RunRecord[]; activeFeature: string | null; onMaximize: (on: boolean) => void }) {
  const [big, setBig] = useState(false);
  const [view, setView] = useState<View>("runs");
  const [onlyThis, setOnlyThis] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  useEffect(() => {
    const on = (e: Event) => { setView("runs"); setPicked((e as CustomEvent<string[]>).detail.slice(0, 2)); };
    window.addEventListener("research:compare", on);
    return () => window.removeEventListener("research:compare", on);
  }, []);
  const pick = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));
  const pair = picked.map((id) => runs.find((r) => r.jobId === id)).filter((r): r is RunRecord => Boolean(r));
  const remove = useRuns((s) => s.remove);
  const close = () => useLayout.getState().set("bottom", false, true);
  const shown = onlyThis && activeFeature ? runs.filter((r) => r.featureId === activeFeature) : runs;
  const running = runs.filter((r) => r.status === "running" || r.status === "queued").length;
  const last = runs[0];
  const sweeps = sweepGroups(runs);
  const log = runs.flatMap((r) => (r.log ?? []).map((e) => ({ ...e, run: r }))).sort((a, b) => b.t - a.t).slice(0, 200);

  return (
    <section className="island" aria-label="Runs and log">
      <div style={{ display: "flex", alignItems: "center", gap: 8, height: 42, padding: "0 8px 0 10px", borderBottom: "1px solid var(--line)", flex: "none" }}>
        <Tabs<View> value={view} onChange={setView} tabs={[{ id: "runs", label: "Runs", count: runs.length }, ...(sweeps.length ? [{ id: "sweep" as const, label: "Sweep", count: sweeps[0].runs.length }] : []), { id: "log", label: "Log", count: log.length }]} />
        {view === "runs" && activeFeature ? (
          <button className="pill" aria-pressed={onlyThis} onClick={() => setOnlyThis((v) => !v)} style={{ height: 24 }}>This feature only</button>
        ) : null}
        <span style={{ marginLeft: "auto", display: "flex", gap: 2 }}>
          <button className="btn sm icon ghost" onClick={() => { setBig(false); onMaximize(false); close(); }} aria-label="Minimize runs and log" title="Minimize (⌘J)"><Minus size={13} /></button>
          <button className="btn sm icon ghost" onClick={() => { onMaximize(!big); setBig(!big); }} aria-label={big ? "Restore panel size" : "Maximize panel"} title={big ? "Restore" : "Maximize"}>{big ? <Minimize2 size={13} /> : <Maximize2 size={13} />}</button>
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {view === "sweep" && sweeps.length ? <SweepView group={sweeps[0]} /> : view === "runs" || view === "sweep" ? (
          shown.length ? (
            <>{pair.length === 2 ? <Compare a={pair[0]} b={pair[1]} onClear={() => setPicked([])} /> : null}
            <table className="tbl">
              <thead><tr><th style={{ width: 30 }} /><th>Feature</th><th>Study</th><th style={{ width: 96 }}>Status</th><th>Verdict</th><th className="r" style={{ width: 130 }}>Started</th><th style={{ width: 36 }} /></tr></thead>
              <tbody>
                {shown.map((r) => {
                  const m = metaFor(r.featureId, r.featureName);
                  const Icon = m.icon;
                  const href = `${featureHref(r.featureId)}?run=${r.jobId}`;
                  return (
                    <tr key={r.jobId} aria-selected={picked.includes(r.jobId)}>
                      <td><input type="checkbox" aria-label={`Compare ${m.name} run`} checked={picked.includes(r.jobId)} onChange={() => pick(r.jobId)} disabled={r.status !== "completed"} /></td>
                      <td className="strong"><Link href={href} style={{ color: "inherit", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8 }}><Icon size={13} strokeWidth={1.7} style={{ color: "var(--text-3)" }} />{m.name}</Link></td>
                      <td>{r.signal ? label(r.signal) : "–"}</td>
                      <td><Chip tone={r.status === "completed" ? r.tone ?? "neutral" : STATUS[r.status].tone}>{r.status === "completed" && r.tone ? { up: "Pass", down: "Fail", warn: "Mixed" }[r.tone] : STATUS[r.status].text}</Chip></td>
                      <td style={{ maxWidth: 520, overflow: "hidden", textOverflow: "ellipsis", color: "var(--text-2)" }}>{r.headline ?? ""}</td>
                      <td className="r num">{time(r.startedAt)}</td>
                      <td><button className="btn sm icon ghost" aria-label="Remove from history" onClick={() => remove(r.jobId)}><Trash2 size={12} /></button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table></>
          ) : <div style={{ padding: "16px", color: "var(--text-3)", fontSize: 12.5 }}>Runs appear here as you start them. They stay on this device.</div>
        ) : log.length ? (
          <div style={{ padding: "6px 0" }}>
            {log.map((e, i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "120px 150px 1fr", gap: 12, padding: "5px 14px", fontSize: 12, borderBottom: "1px solid var(--grid)" }}>
                <span className="num" style={{ color: "var(--text-3)" }}>{time(e.t)}</span>
                <span style={{ color: "var(--text-2)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{metaFor(e.run.featureId, e.run.featureName).name}</span>
                <span style={{ color: e.tone === "down" ? "var(--down)" : e.tone === "warn" ? "var(--warn)" : e.tone === "up" ? "var(--up)" : "var(--text-2)" }}>{e.text}</span>
              </div>
            ))}
          </div>
        ) : <div style={{ padding: "16px", color: "var(--text-3)", fontSize: 12.5 }}>Job events and data caveats appear here.</div>}
      </div>
      <div className="statusbar" role="status">
        <span><span className="num">{running}</span> running</span>
        <span>{last ? `Last run ${time(last.startedAt)}` : "No runs yet"}</span>
      </div>
    </section>
  );
}

type SweepGroup = { id: string; featureId: string; featureName: string; key: string; runs: RunRecord[] };

/** Runs grouped by sweep, newest sweep first. */
function sweepGroups(runs: RunRecord[]): SweepGroup[] {
  const by = new Map<string, SweepGroup>();
  for (const r of runs) {
    if (!r.sweep) continue;
    const g = by.get(r.sweep.group) ?? { id: r.sweep.group, featureId: r.featureId, featureName: r.featureName, key: r.sweep.key, runs: [] };
    g.runs.push(r);
    by.set(r.sweep.group, g);
  }
  return [...by.values()];
}

/** One headline figure plotted against the swept setting, QuantConnect-optimizer style. */
function SweepView({ group }: { group: SweepGroup }) {
  const done = group.runs.filter((r) => r.metrics && r.sweep).sort((a, b) => a.sweep!.value - b.sweep!.value);
  const names = [...new Set(done.flatMap((r) => Object.keys(r.metrics ?? {})))];
  const [picked, setPicked] = useState<string | null>(null);
  const metric = picked && names.includes(picked) ? picked : names[0];
  const pending = group.runs.filter((r) => r.status === "queued" || r.status === "running").length;
  const failed = group.runs.filter((r) => r.status === "failed" || r.status === "cancelled").length;
  const pts = metric ? done.filter((r) => Number.isFinite(r.metrics![metric])).map((r) => ({ x: r.sweep!.value, y: r.metrics![metric], label: `${label(group.key)} = ${r.sweep!.value}`, emphasis: r.tone === "up" })) : [];
  const best = pts.length ? pts.reduce((a, b) => (Math.abs(b.y) > Math.abs(a.y) ? b : a)) : null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 280px", gap: 16, padding: "12px 14px", height: "100%", minHeight: 0 }}>
      <div style={{ minWidth: 0 }}>
        {pts.length ? (
          <XYPlot points={pts} lines={pts.length > 1 ? [{ label: metric!, points: pts.map(({ x, y }) => ({ x, y })) }] : undefined} xLabel={label(group.key)} yLabel={metric ?? ""} height={200} refY={[{ y: 0 }]} />
        ) : <div style={{ color: "var(--text-3)", fontSize: 12.5, paddingTop: 8 }}>{pending ? `Waiting for ${pending} run${pending > 1 ? "s" : ""} to finish.` : failed ? `${failed} of ${group.runs.length} runs failed. See the Log tab for why.` : "No numeric results to compare."}</div>}
      </div>
      <aside style={{ display: "grid", alignContent: "start", gap: 10, fontSize: 12.5 }}>
        <div style={{ color: "var(--text-3)" }}>{metaFor(group.featureId, group.featureName).name} · sweep of <b style={{ color: "var(--text)" }}>{label(group.key)}</b></div>
        {names.length > 1 ? (
          <select className="input" aria-label="Figure to plot" value={metric} onChange={(e) => setPicked(e.target.value)} style={{ height: 30 }}>
            {names.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        ) : null}
        <div className="kv" style={{ display: "grid", gap: 4 }}>
          <span style={{ color: "var(--text-3)" }}>Runs finished: <b className="num" style={{ color: "var(--text)" }}>{done.length}/{group.runs.length}</b></span>
          {best ? <span style={{ color: "var(--text-3)" }}>Strongest: <b className="num" style={{ color: "var(--text)" }}>{best.label.split(" = ")[1]}</b></span> : null}
        </div>
        <div style={{ display: "grid", gap: 2 }}>
          {group.runs.slice().sort((a, b) => a.sweep!.value - b.sweep!.value).map((r) => (
            <Link key={r.jobId} href={`${featureHref(r.featureId)}?run=${r.jobId}`} className="nav-item" style={{ height: 26, fontSize: 12 }}>
              <span className="num" style={{ width: 54 }}>{r.sweep!.value}</span>
              <span className="num" style={{ marginLeft: "auto", color: r.metrics && metric ? "var(--text)" : "var(--text-4)" }}>{r.metrics && metric && Number.isFinite(r.metrics[metric]) ? r.metrics[metric].toPrecision(4) : STATUS[r.status].text}</span>
            </Link>
          ))}
        </div>
      </aside>
    </div>
  );
}

/** Two finished runs side by side: every headline figure, the change, and the settings that differ. */
function Compare({ a, b, onClear }: { a: RunRecord; b: RunRecord; onClear: () => void }) {
  const keys = [...new Set([...Object.keys(a.metrics ?? {}), ...Object.keys(b.metrics ?? {})])];
  const diff = Object.keys({ ...a.payload, ...b.payload }).filter((k) => JSON.stringify(a.payload?.[k]) !== JSON.stringify(b.payload?.[k]));
  const fmt = (v: unknown) => (typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toPrecision(4)) : v === undefined ? "–" : Array.isArray(v) ? `${v.length} items` : String(v));
  const name = (r: RunRecord) => `${metaFor(r.featureId, r.featureName).name} · ${time(r.startedAt)}`;
  return (
    <div style={{ margin: 10, padding: "10px 12px", borderRadius: 10, boxShadow: "inset 0 0 0 1px var(--line)", background: "var(--panel)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12.5 }}>
        <b>Compare</b><span style={{ color: "var(--text-3)" }}>A = {name(a)} · B = {name(b)}</span>
        <button className="btn sm ghost" style={{ marginLeft: "auto" }} onClick={onClear}>Clear</button>
      </div>
      <table className="tbl">
        <thead><tr><th>Figure</th><th className="r">A</th><th className="r">B</th><th className="r">B − A</th></tr></thead>
        <tbody>
          {keys.map((k) => {
            const x = a.metrics?.[k], y = b.metrics?.[k];
            const d = x !== undefined && y !== undefined ? y - x : undefined;
            return (
              <tr key={k}><td>{k}</td><td className="r num">{fmt(x)}</td><td className="r num">{fmt(y)}</td>
                <td className="r num" style={{ color: d === undefined || d === 0 ? "var(--text-3)" : d > 0 ? "var(--up)" : "var(--down)" }}>{d === undefined ? "–" : `${d > 0 ? "▲" : d < 0 ? "▼" : ""} ${fmt(Math.abs(d))}`}</td></tr>
            );
          })}
          {diff.map((k) => <tr key={`p-${k}`} style={{ color: "var(--text-3)" }}><td>Setting: {label(k)}</td><td className="r num">{fmt(a.payload?.[k])}</td><td className="r num">{fmt(b.payload?.[k])}</td><td /></tr>)}
        </tbody>
      </table>
    </div>
  );
}
