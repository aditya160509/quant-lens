"use client";

import { ChevronDown, LayoutDashboard, Plus, Save, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import type { ReactNode } from "react";
import { useServerPref } from "./serverPref";

export type PanelId = "rail" | "chart" | "preview" | "tester";
/** Sizes are percentages: rail and right of the width, tester of the centre height. */
export type Dock = { chart?: "left" | "right"; panel?: "center" | "full" | "left" | "right" };
export type Layout = { open: Record<PanelId, boolean>; size: { rail: number; right: number; tester: number; chart?: number; split?: number }; dock?: Dock; focus?: { tab?: "debug" | "output"; view?: "results" } };
export type Workspace = { id: string; name: string; builtin?: boolean; layout: Layout };

const L = (open: Partial<Record<PanelId, boolean>>, right = 42, tester = 24, rail = 16): Layout => ({ open: { rail: false, chart: false, preview: false, tester: false, ...open }, size: { rail, right, tester } });
const BUILTIN: Workspace[] = [
  { id: "code", name: "Code only", builtin: true, layout: L({}) },
  { id: "code-chart", name: "Code + Chart", builtin: true, layout: L({ chart: true }) },
  { id: "research", name: "Research", builtin: true, layout: L({ rail: true, chart: true }, 40) },
  { id: "debug", name: "Debug", builtin: true, layout: { ...L({ chart: true, tester: true }, 38, 34), focus: { tab: "debug" } } },
  { id: "review", name: "Review", builtin: true, layout: { ...L({}), focus: { view: "results" } } },
  { id: "tester", name: "Full tester", builtin: true, layout: L({ rail: true, chart: true, tester: true }, 34, 24, 16) },
  // Chart first (W-12): the chart is the main panel on the left, code docks on the right, the tester spans the bottom.
  { id: "chart-first", name: "Chart first", builtin: true, layout: { ...L({ chart: true, tester: true }, 66, 26), dock: { chart: "left", panel: "full" } } },
];
const KEY = "studio:dev:workspaces";
type Saved = { active: string; list: Workspace[] };

const load = (): Saved => {
  let s: Partial<Saved> = {};
  try { s = JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { /* blocked or corrupt */ }
  return merge(s);
};
/** Saved layouts plus any built-in added since, with old copies migrated. */
const merge = (s: Partial<Saved>): Saved => {
  const list = [...BUILTIN.filter((b) => !s.list?.some((w) => w.id === b.id)), ...(s.list ?? []).map((w) => {
    const { right, tester, rail } = w.layout.size;
    if (w.id === "tester" && right === 42 && tester === 36 && rail === 18) {
      return { ...w, layout: { ...w.layout, size: { ...w.layout.size, right: 34, tester: 24, rail: 16 } } };
    }
    if (w.id === "chart-first" && !w.layout.dock) return BUILTIN.find((b) => b.id === "chart-first")!;
    return w;
  })];
  return { list, active: list.some((w) => w.id === s.active) ? s.active! : "code" };
};

export function useWorkspaces() {
  const [s, setS] = useState<Saved>(() => (typeof window === "undefined" ? { active: "code", list: BUILTIN } : load()));
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* blocked */ } }, [s]);
  useServerPref("layouts", s, (v) => setS(merge(v)));
  const cur = s.list.find((w) => w.id === s.active) ?? s.list[0];
  const patch = useCallback((f: (l: Layout) => Layout) => setS((p) => ({ ...p, list: p.list.map((w) => (w.id === p.active ? { ...w, layout: f(w.layout) } : w)) })), []);
  const add = (name: string, layout: Layout) => setS((p) => { const id = `u${Date.now().toString(36)}`; return { active: id, list: [...p.list, { id, name, layout: structuredClone(layout) }] }; });
  const before = useRef("code-chart");
  return {
    list: s.list, cur, patch,
    /** One click between Chart first and the layout you came from. */
    flipChartFirst: () => setS((p) => { if (p.active !== "chart-first") { before.current = p.active; return { ...p, active: "chart-first" }; } return { ...p, active: p.list.some((w) => w.id === before.current) ? before.current : "code-chart" }; }),
    switchTo: (id: string) => setS((p) => ({ ...p, active: id })),
    add,
    rename: (id: string, name: string) => setS((p) => ({ ...p, list: p.list.map((w) => (w.id === id ? { ...w, name } : w)) })),
    reset: () => setS((p) => ({ ...p, list: p.list.map((w) => (w.id === p.active && w.builtin ? BUILTIN.find((b) => b.id === w.id) ?? w : w)) })),
    remove: (id: string) => setS((p) => { const list = p.list.filter((w) => w.id !== id || w.builtin); return { list, active: list.some((w) => w.id === p.active) ? p.active : "code" }; }),
  };
}

/** Group layouts for a workspace layout. */
export const targets = (l: Layout) => {
  const right = l.open.chart || l.open.preview ? l.size.right : 0, rail = l.open.rail ? l.size.rail : 0, t = l.open.tester ? l.size.tester : 0;
  return { h: { rail, center: 100 - rail - right, right }, v: { editor: 100 - t, tester: t } };
};

/** Reserve room for the editor before applying a saved split to the current window. */
export function fitWorkspace(layout: Layout, width: number, chartFirst: boolean): Layout {
  if (!width) return layout;
  const { open, size } = layout;
  const available = Math.max(1, width - (open.rail ? 6 : 0) - (open.chart ? 6 : 0));
  const editor = Math.min(available, chartFirst ? available * 0.3 : 430);
  const remaining = available - editor;
  const chart = open.chart && (!open.rail || remaining >= 390);
  const rightMin = chart ? Math.min(remaining, 235) : 0;
  const rail = open.rail ? Math.min(remaining - rightMin, Math.max(155, available * size.rail / 100)) : 0;
  const right = chart ? Math.min(remaining - rail, Math.max(rightMin, available * size.right / 100)) : 0;
  return { open: { ...open, chart }, size: { ...size, rail: rail / available * 100, right: right / available * 100 } };
}

export function WorkspaceMenu({ ws, children, onCustomise }: { ws: ReturnType<typeof useWorkspaces>; children?: ReactNode; onCustomise?: () => void }) {
  const { cur } = ws;
  return (
    <details className="dv-view" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false; }}>
      <summary className="btn sm ghost" aria-label={`Layout: ${cur.name}`} title={`Layout: ${cur.name}`}><LayoutDashboard size={15} /><ChevronDown size={12} /></summary>
      <div className="dv-menu" role="menu" onClick={(e) => { (e.currentTarget.parentElement as HTMLDetailsElement).open = false; }}>
        <div className="hd">Workspace</div>
        {ws.list.map((w) => <button key={w.id} role="menuitemradio" aria-checked={w.id === cur.id} onClick={() => ws.switchTo(w.id)}>{w.name}</button>)}
        <hr />
        {onCustomise ? <button role="menuitem" onClick={onCustomise}>Customise layouts…<kbd>{"⌘⇧\\"}</kbd></button> : null}
        <button role="menuitem" onClick={() => { const n = window.prompt("Save workspace as")?.trim(); if (n) ws.add(n, cur.layout); }}>Save as…</button>
        <button role="menuitem" onClick={() => ws.add(`${cur.name} copy`, cur.layout)}>Duplicate</button>
        {cur.builtin ? null : <button role="menuitem" onClick={() => { const n = window.prompt("Rename workspace", cur.name)?.trim(); if (n) ws.rename(cur.id, n); }}>Rename</button>}
        {cur.builtin ? null : <button role="menuitem" onClick={() => ws.remove(cur.id)}>Delete</button>}
        {children ? <><hr />{children}</> : null}
      </div>
    </details>
  );
}

type Ws = ReturnType<typeof useWorkspaces>;
const clamp = (v: number, lo: number, hi: number) => Math.round(Math.min(hi, Math.max(lo, v)));

/** Zone rectangles in percent for a layout: shared by the thumbnail and the zone editor. */
function zones(l: Layout) {
  const rail = l.open.rail ? l.size.rail : 0, right = l.open.chart ? l.size.right : 0, t = l.open.tester ? l.size.tester : 0;
  const left = l.dock?.chart === "left", full = l.dock?.panel === "full";
  const top = 100 - t, ed = { x: rail + (left ? right : 0), w: 100 - rail - right };
  const ch = { x: left ? rail : 100 - right, w: right };
  return {
    rail: { x: 0, y: 0, w: rail, h: full ? top : 100 },
    ...(l.dock?.panel === "left" || l.dock?.panel === "right" ? (() => {
      // Panel beside the editor: the tester share is a width, not a height.
      const pw = ed.w * t / 100, pl = l.dock?.panel === "left";
      return { editor: { x: ed.x + (pl ? pw : 0), y: 0, w: ed.w - pw, h: 100 }, tester: { x: pl ? ed.x : ed.x + ed.w - pw, y: 0, w: pw, h: 100 } };
    })() : {
      editor: { x: ed.x, y: 0, w: ed.w, h: top },
      tester: full ? { x: 0, y: top, w: 100, h: t } : { x: ed.x, y: top, w: ed.w, h: t },
    }),
    chart: { x: ch.x, y: 0, w: ch.w, h: full ? top : 100 },
    edges: { rail, right, t, left, full },
  };
}

/** A layout drawn small: side bar, editor, bottom panel and chart where the layout docks them. */
function Thumb({ l }: { l: Layout }) {
  const z = zones(l), W = 96, H = 60, g = 1;
  const r = (k: "rail" | "editor" | "tester" | "chart") => { const q = z[k]; return q.w > 0 && q.h > 0 ? <rect key={k} x={(q.x * W) / 100 + g} y={(q.y * H) / 100 + g} width={(q.w * W) / 100 - 2 * g} height={(q.h * H) / 100 - 2 * g} rx={2} data-z={k} /> : null; };
  return <svg viewBox={`0 0 ${W} ${H}`} aria-hidden className="dv-thumb">{r("rail")}{r("editor")}{r("tester")}{r("chart")}</svg>;
}

const ZONES: ["rail" | "editor" | "tester" | "chart", string][] = [["rail", "Files"], ["editor", "Editor"], ["tester", "Bottom panel"], ["chart", "Chart"]];
const PRESETS: [string, Partial<Record<PanelId, boolean>>][] = [["Columns", { rail: true, chart: true }], ["Rows", { tester: true }], ["Grid", { rail: true, chart: true, tester: true }], ["Editor", {}]];

/** Zone editor: show or hide each zone, drag the shared edges to size them, save as a named layout. */
function ZoneEditor({ start, onSave, onCancel }: { start: Layout; onSave: (name: string, l: Layout) => void; onCancel: () => void }) {
  const [l, setL] = useState<Layout>(() => structuredClone(start));
  const [name, setName] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const z = zones(l), { rail, right, t, left, full } = z.edges;
  const drag = (edge: "rail" | "right" | "tester") => (e: ReactPointerEvent) => {
    e.preventDefault();
    const r = box.current!.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const x = ((ev.clientX - r.left) / r.width) * 100, y = ((ev.clientY - r.top) / r.height) * 100;
      setL((p) => ({ ...p, size: { ...p.size, ...(edge === "rail" ? { rail: clamp(x, 8, 40) } : edge === "right" ? { right: clamp(left ? x - rail : 100 - x, 15, 75) } : { tester: clamp(100 - y, 10, 70) }) } }));
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const toggle = (z: PanelId | "editor") => { if (z !== "editor") setL((p) => ({ ...p, open: { ...p.open, [z]: !p.open[z] } })); };
  const pct = (k: "rail" | "editor" | "tester" | "chart"): CSSProperties => ({ left: `${z[k].x}%`, top: `${z[k].y}%`, width: `${z[k].w}%`, height: `${z[k].h}%` });
  const setDock = (d: Dock) => setL((p) => ({ ...p, dock: { ...p.dock, ...d } }));

  const on = (z: PanelId | "editor") => z === "editor" || l.open[z];
  return (
    <div className="dv-zones">
      <div className="dv-zones-hd">
        <b>Zone editor</b>
        <span className="seg">
          <button className="btn sm ghost" aria-pressed={left} onClick={() => setDock({ chart: left ? "right" : "left" })}>Chart {left ? "left" : "right"}</button>
          <button className="btn sm ghost" aria-pressed={full} onClick={() => setDock({ panel: full ? "center" : "full" })}>Panel {full ? "full width" : "under editor"}</button>
        </span>
        <span className="seg">{PRESETS.map(([n, o]) => <button key={n} className="btn sm ghost" onClick={() => setL((p) => ({ ...p, open: { rail: false, chart: false, preview: false, tester: false, ...o } }))}>{n}</button>)}</span>
      </div>
      <div className="dv-zones-box" ref={box}>
        {ZONES.filter(([z]) => on(z)).map(([z, label]) => (
          <div key={z} className="dv-zone" style={pct(z === "editor" ? "editor" : z)}>
            <span>{label}</span>
            {z !== "editor" ? <button className="icon-btn" aria-label={`Hide ${label}`} onClick={() => toggle(z)}><X size={13} /></button> : null}
          </div>
        ))}
        {rail ? <i className="dv-edge v" style={{ left: `${rail}%`, height: `${z.rail.h}%`, bottom: "auto" }} onPointerDown={drag("rail")} /> : null}
        {right ? <i className="dv-edge v" style={{ left: `${left ? rail + right : 100 - right}%`, height: `${z.chart.h}%`, bottom: "auto" }} onPointerDown={drag("right")} /> : null}
        {t ? <i className="dv-edge h" style={{ top: `${100 - t}%`, left: `${z.tester.x}%`, width: `${z.tester.w}%` }} onPointerDown={drag("tester")} /> : null}
      </div>
      <div className="dv-zones-ft">
        {ZONES.filter(([z]) => !on(z)).map(([z, label]) => <button key={z} className="btn sm ghost" onClick={() => toggle(z)}><Plus size={12} />{label}</button>)}
        <span style={{ flex: 1 }} />
        <input className="input sm" aria-label="Layout name" placeholder="Layout name" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn sm primary" onClick={() => onSave(name.trim() || "Custom layout", l)}>Save and apply</button>
        <button className="btn sm ghost" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

/** Layouts (⌘⇧\): every saved layout as a thumbnail, a zone editor for new ones, save the current arrangement. The active layout is remembered as the default. */
export function LayoutsDialog({ ws, open, onClose }: { ws: Ws; open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [editing, setEditing] = useState(false);
  useEffect(() => { const d = ref.current; if (!d) return; if (open && !d.open) d.showModal(); if (!open && d.open) d.close(); if (!open) setEditing(false); }, [open]);
  return (
    <dialog ref={ref} className="dv-layouts" data-wide={editing || undefined} onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      {editing ? <ZoneEditor start={ws.cur.layout} onCancel={() => setEditing(false)} onSave={(n, l) => { ws.add(n, l); setEditing(false); onClose(); }} /> : (
        <>
          <div className="dv-layouts-hd"><b>Layouts</b><span style={{ flex: 1 }} />{ws.cur.builtin ? <button className="btn sm ghost" onClick={ws.reset}>Reset</button> : null}<button className="btn sm" onClick={onClose}>Done</button></div>
          <div className="dv-layouts-grid">
            {ws.list.map((w) => (
              <div key={w.id} className="dv-layout" aria-current={w.id === ws.cur.id || undefined}>
                <button onClick={() => ws.switchTo(w.id)}><Thumb l={w.layout} /><span>{w.name}</span></button>
                {w.builtin ? null : <button className="icon-btn" aria-label={`Delete ${w.name}`} onClick={() => ws.remove(w.id)}><X size={12} /></button>}
              </div>
            ))}
          </div>
          <button className="btn sm ghost dv-layouts-new" onClick={() => setEditing(true)}><Plus size={13} />New grid layout</button>
          <button className="btn sm ghost" onClick={() => { const n = window.prompt("Save current arrangement as")?.trim(); if (n) ws.add(n, ws.cur.layout); }}><Save size={13} />Save current arrangement as a template</button>
        </>
      )}
    </dialog>
  );
}

