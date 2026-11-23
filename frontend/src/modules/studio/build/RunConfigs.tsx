"use client";

import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useServerPref } from "./serverPref";

/** Run configurations: named settings for /build/run (universe, dates, costs, fill). "Default" sends none, so the server's quick-run defaults apply. */
export type RunConfig = { name: string; symbols?: string; top_n?: number; start?: string; end?: string; cost_profile?: string; fill?: string; params?: string };
const KEY = "studio:runconfigs";
const COSTS = ["US retail", "Crypto taker", "Zero (costs off)", "Custom"]; // backend features/inputs.py COST_PROFILES
const DEFAULT: RunConfig = { name: "Default" };

function load(): { active: string; list: RunConfig[]; runOnSave?: boolean } {
  try { const s = JSON.parse(localStorage.getItem(KEY) ?? ""); if (Array.isArray(s.list)) return s; } catch { /* none or blocked */ }
  return { active: "Default", list: [DEFAULT] };
}

export function useRunConfigs() {
  const [s, setS] = useState(() => (typeof window === "undefined" ? { active: "Default", list: [DEFAULT] } : load()));
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* blocked */ } }, [s]);
  useServerPref("runconfigs", s, setS);
  const cur = s.list.find((c) => c.name === s.active) ?? DEFAULT;
  const { name: _, ...rest } = cur;
  const settings = Object.fromEntries(Object.entries(rest).filter(([, v]) => v !== undefined && v !== ""));
  return {
    list: s.list, cur, settings,
    select: (name: string) => setS((p) => ({ ...p, active: name })),
    runOnSave: !!s.runOnSave, setRunOnSave: (v: boolean) => setS((p) => ({ ...p, runOnSave: v })),
    save: (list: RunConfig[]) => setS((p) => ({ ...p, list, active: list.some((c) => c.name === p.active) ? p.active : "Default" })),
  };
}
export type RunConfigs = ReturnType<typeof useRunConfigs>;

/** Run configurations table for the settings window: each row is a named universe, date range, costs and fill. */
export function RunConfigsEditor({ rc }: { rc: RunConfigs }) {
  const [rows, setRows] = useState(rc.list);
  const set = (i: number, k: keyof RunConfig, v: string) => setRows((r) => r.map((c, j) => (j === i ? { ...c, [k]: k === "top_n" ? (v ? Number(v) : undefined) : v } : c)));
  const names = rows.map((c) => c.name.trim());
  const bad = names.some((n, i) => !n || names.indexOf(n) !== i);
  const dirty = JSON.stringify(rows) !== JSON.stringify(rc.list);
  return (
    <div className="dv-rcfgs">
      <table className="dv-rcfg-t">
        <thead><tr><th /><th>Name</th><th>Symbols</th><th>Top N</th><th>Start</th><th>End</th><th>Costs</th><th>Fill</th><th>Inputs</th><th /></tr></thead>
        <tbody>{rows.map((c, i) => {
          const fixed = i === 0 && c.name === "Default";
          return (
            <tr key={i}>
              <td><input type="radio" name="rc-active" aria-label={`Use ${c.name}`} checked={rc.cur.name === c.name} disabled={dirty} onChange={() => rc.select(c.name)} /></td>
              <td><input aria-label="Name" value={c.name} disabled={fixed} onChange={(e) => set(i, "name", e.target.value)} /></td>
              <td><input aria-label="Symbols" placeholder="Top 50" value={c.symbols ?? ""} disabled={fixed} onChange={(e) => set(i, "symbols", e.target.value.toUpperCase())} /></td>
              <td><input aria-label="Top N" type="number" min={1} value={c.top_n ?? ""} disabled={fixed} onChange={(e) => set(i, "top_n", e.target.value)} /></td>
              <td><input aria-label="Start" type="date" value={c.start ?? ""} disabled={fixed} onChange={(e) => set(i, "start", e.target.value)} /></td>
              <td><input aria-label="End" type="date" value={c.end ?? ""} disabled={fixed} onChange={(e) => set(i, "end", e.target.value)} /></td>
              <td><select aria-label="Costs" value={c.cost_profile ?? ""} disabled={fixed} onChange={(e) => set(i, "cost_profile", e.target.value)}><option value="">Default</option>{COSTS.map((x) => <option key={x}>{x}</option>)}</select></td>
              <td><select aria-label="Fill" value={c.fill ?? ""} disabled={fixed} onChange={(e) => set(i, "fill", e.target.value)}><option value="">Next open</option><option value="same_close">Same close</option></select></td>
              <td><input aria-label="Inputs" placeholder="fast=10 slow=50" title="Input overrides, quick runs only" value={c.params ?? ""} disabled={fixed} onChange={(e) => set(i, "params", e.target.value)} /></td>
              <td>{fixed ? null : <button className="icon-btn" aria-label={`Delete ${c.name}`} onClick={() => setRows((r) => r.filter((_, j) => j !== i))}><X size={12} /></button>}</td>
            </tr>
          );
        })}</tbody>
      </table>
      <div className="dv-rcfg-ft">
        <button className="btn sm ghost" onClick={() => setRows((r) => [...r, { name: `Config ${r.length}` }])}><Plus size={13} />Add configuration</button>
        <span style={{ flex: 1 }} />
        {dirty ? <button className="btn sm ghost" onClick={() => setRows(rc.list)}>Revert</button> : null}
        <button className="btn sm primary" disabled={bad || !dirty} title={bad ? "Each configuration needs a unique name" : undefined} onClick={() => { const list = rows.map((c) => ({ ...c, name: c.name.trim() })); rc.save(list); setRows(list); }}>Save configurations</button>
      </div>
    </div>
  );
}
