"use client";

import { Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/** Run configurations: named settings for /build/run (universe, dates, costs, fill). "Default" sends none, so the server's quick-run defaults apply. */
export type RunConfig = { name: string; symbols?: string; top_n?: number; start?: string; end?: string; cost_profile?: string; fill?: string };
const KEY = "studio:runconfigs";
const COSTS = ["US retail", "Crypto taker", "Zero (costs off)", "Custom"]; // backend features/inputs.py COST_PROFILES
const DEFAULT: RunConfig = { name: "Default" };

// shortcut: configs live in this browser only; move them into the strategy spec when they need to be shared.
function load(): { active: string; list: RunConfig[] } {
  try { const s = JSON.parse(localStorage.getItem(KEY) ?? ""); if (Array.isArray(s.list)) return s; } catch { /* none or blocked */ }
  return { active: "Default", list: [DEFAULT] };
}

export function useRunConfigs() {
  const [s, setS] = useState(() => (typeof window === "undefined" ? { active: "Default", list: [DEFAULT] } : load()));
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* blocked */ } }, [s]);
  const cur = s.list.find((c) => c.name === s.active) ?? DEFAULT;
  const { name: _, ...rest } = cur;
  const settings = Object.fromEntries(Object.entries(rest).filter(([, v]) => v !== undefined && v !== ""));
  return {
    list: s.list, cur, settings,
    select: (name: string) => setS((p) => ({ ...p, active: name })),
    save: (list: RunConfig[]) => setS((p) => ({ list, active: list.some((c) => c.name === p.active) ? p.active : "Default" })),
  };
}
export type RunConfigs = ReturnType<typeof useRunConfigs>;

export function RunConfigPicker({ rc, onEdit }: { rc: RunConfigs; onEdit: () => void }) {
  return (
    <select className="dv-rcfg" aria-label="Run configuration" title="Run configuration" value={rc.cur.name}
      onChange={(e) => (e.target.value === "\u0000edit" ? onEdit() : rc.select(e.target.value))}>
      {rc.list.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
      <option value={"\u0000edit"}>Edit configurations…</option>
    </select>
  );
}

export function RunConfigsDialog({ rc, open, onClose }: { rc: RunConfigs; open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [rows, setRows] = useState(rc.list);
  useEffect(() => { const d = ref.current; if (!d) return; if (open && !d.open) { setRows(rc.list); d.showModal(); } if (!open && d.open) d.close(); }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (i: number, k: keyof RunConfig, v: string) => setRows((r) => r.map((c, j) => (j === i ? { ...c, [k]: k === "top_n" ? (v ? Number(v) : undefined) : v } : c)));
  const names = rows.map((c) => c.name.trim());
  const bad = names.some((n, i) => !n || names.indexOf(n) !== i);
  return (
    <dialog ref={ref} className="dv-layouts dv-rcfgs" data-wide onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dv-layouts-hd"><b>Run configurations</b><span style={{ flex: 1 }} />
        <button className="btn sm ghost" onClick={onClose}>Cancel</button>
        <button className="btn sm" disabled={bad} title={bad ? "Each configuration needs a unique name" : undefined} onClick={() => { rc.save(rows.map((c) => ({ ...c, name: c.name.trim() }))); onClose(); }}>Save</button>
      </div>
      <table className="dv-rcfg-t">
        <thead><tr><th>Name</th><th>Symbols</th><th>Top N</th><th>Start</th><th>End</th><th>Costs</th><th>Fill</th><th /></tr></thead>
        <tbody>{rows.map((c, i) => {
          const fixed = i === 0 && c.name === "Default";
          return (
            <tr key={i}>
              <td><input aria-label="Name" value={c.name} disabled={fixed} onChange={(e) => set(i, "name", e.target.value)} /></td>
              <td><input aria-label="Symbols" placeholder="Top 50" value={c.symbols ?? ""} disabled={fixed} onChange={(e) => set(i, "symbols", e.target.value.toUpperCase())} /></td>
              <td><input aria-label="Top N" type="number" min={1} value={c.top_n ?? ""} disabled={fixed} onChange={(e) => set(i, "top_n", e.target.value)} /></td>
              <td><input aria-label="Start" type="date" value={c.start ?? ""} disabled={fixed} onChange={(e) => set(i, "start", e.target.value)} /></td>
              <td><input aria-label="End" type="date" value={c.end ?? ""} disabled={fixed} onChange={(e) => set(i, "end", e.target.value)} /></td>
              <td><select aria-label="Costs" value={c.cost_profile ?? ""} disabled={fixed} onChange={(e) => set(i, "cost_profile", e.target.value)}><option value="">Default</option>{COSTS.map((x) => <option key={x}>{x}</option>)}</select></td>
              <td><select aria-label="Fill" value={c.fill ?? ""} disabled={fixed} onChange={(e) => set(i, "fill", e.target.value)}><option value="">Next open</option><option value="same_close">Same close</option></select></td>
              <td>{fixed ? null : <button className="icon-btn" aria-label={`Delete ${c.name}`} onClick={() => setRows((r) => r.filter((_, j) => j !== i))}><X size={12} /></button>}</td>
            </tr>
          );
        })}</tbody>
      </table>
      <button className="btn sm ghost dv-layouts-new" onClick={() => setRows((r) => [...r, { name: `Config ${r.length}` }])}><Plus size={13} />Add configuration</button>
    </dialog>
  );
}
