"use client";

import { ChevronDown, LayoutDashboard } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export type PanelId = "rail" | "chart" | "preview" | "tester";
/** Sizes are percentages: rail and right of the width, tester of the centre height. */
export type Layout = { open: Record<PanelId, boolean>; size: { rail: number; right: number; tester: number; chart?: number; split?: number } };
export type Workspace = { id: string; name: string; builtin?: boolean; layout: Layout };

const L = (open: Partial<Record<PanelId, boolean>>, right = 45, tester = 34, rail = 18): Layout => ({ open: { rail: false, chart: false, preview: false, tester: false, ...open }, size: { rail, right, tester } });
const BUILTIN: Workspace[] = [
  { id: "code", name: "Code only", builtin: true, layout: L({}) },
  { id: "code-chart", name: "Code + Chart", builtin: true, layout: L({ chart: true }) },
  { id: "tester", name: "Full tester", builtin: true, layout: L({ rail: true, chart: true, tester: true }, 42, 36) },
  { id: "chart-first", name: "Chart first", builtin: true, layout: L({ chart: true }, 72) },
];
const KEY = "studio:dev:workspaces";
type Saved = { active: string; list: Workspace[] };

const load = (): Saved => {
  let s: Partial<Saved> = {};
  try { s = JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { /* blocked or corrupt */ }
  const list = [...BUILTIN.filter((b) => !s.list?.some((w) => w.id === b.id)), ...(s.list ?? [])];
  return { list, active: list.some((w) => w.id === s.active) ? s.active! : "code" };
};

export function useWorkspaces() {
  const [s, setS] = useState<Saved>(() => (typeof window === "undefined" ? { active: "code", list: BUILTIN } : load()));
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* blocked */ } }, [s]);
  const cur = s.list.find((w) => w.id === s.active) ?? s.list[0];
  const patch = useCallback((f: (l: Layout) => Layout) => setS((p) => ({ ...p, list: p.list.map((w) => (w.id === p.active ? { ...w, layout: f(w.layout) } : w)) })), []);
  const add = (name: string, layout: Layout) => setS((p) => { const id = `u${Date.now().toString(36)}`; return { active: id, list: [...p.list, { id, name, layout: structuredClone(layout) }] }; });
  return {
    list: s.list, cur, patch,
    switchTo: (id: string) => setS((p) => ({ ...p, active: id })),
    add,
    rename: (id: string, name: string) => setS((p) => ({ ...p, list: p.list.map((w) => (w.id === id ? { ...w, name } : w)) })),
    remove: (id: string) => setS((p) => { const list = p.list.filter((w) => w.id !== id || w.builtin); return { list, active: list.some((w) => w.id === p.active) ? p.active : "code" }; }),
  };
}

/** Group layouts for a workspace layout. */
export const targets = (l: Layout) => {
  const right = l.open.chart || l.open.preview ? l.size.right : 0, rail = l.open.rail ? l.size.rail : 0, t = l.open.tester ? l.size.tester : 0;
  return { h: { rail, center: 100 - rail - right, right }, v: { editor: 100 - t, tester: t } };
};

export function WorkspaceMenu({ ws }: { ws: ReturnType<typeof useWorkspaces> }) {
  const { cur } = ws;
  return (
    <details className="dv-view" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
      <summary className="btn sm ghost" aria-label="Workspace"><LayoutDashboard size={14} />{cur.name}<ChevronDown size={12} /></summary>
      <div className="dv-menu" role="menu" onClick={(e) => { (e.currentTarget.parentElement as HTMLDetailsElement).open = false; }}>
        {ws.list.map((w) => <button key={w.id} role="menuitemradio" aria-checked={w.id === cur.id} onClick={() => ws.switchTo(w.id)}>{w.name}</button>)}
        <hr />
        <button role="menuitem" onClick={() => { const n = window.prompt("Save workspace as")?.trim(); if (n) ws.add(n, cur.layout); }}>Save as…</button>
        <button role="menuitem" onClick={() => ws.add(`${cur.name} copy`, cur.layout)}>Duplicate</button>
        {cur.builtin ? null : <button role="menuitem" onClick={() => { const n = window.prompt("Rename workspace", cur.name)?.trim(); if (n) ws.rename(cur.id, n); }}>Rename</button>}
        {cur.builtin ? null : <button role="menuitem" onClick={() => ws.remove(cur.id)}>Delete</button>}
      </div>
    </details>
  );
}
