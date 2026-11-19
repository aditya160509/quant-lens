"use client";

import { ChevronDown, ChevronRight, Copy, Eye, EyeOff, FolderPlus, Plus, X } from "lucide-react";
import { useRef, useState } from "react";
import toast from "react-hot-toast";
import { fromFormula, OPS, toFormula, type Group, type Item, type Leaf } from "./blocks";

export const KINDS: [string, string][] = [
  ["close > sma(close, 200)", "Compare"], ["crosses_above(sma(close, 50), sma(close, 200))", "Crosses"], ["between(rsi(close, 14), 30, 70)", "Between"],
  ["for_bars(close > open, 3)", "For N bars"], ["rising(close, 3)", "Rising"], ["falling(close, 3)", "Falling"],
  ["month_start()", "Month start"], ["weekday() == 4", "Weekday"], ["", "Formula"],
];
const isGroup = (x: Item): x is Group => typeof x === "object" && x !== null && "op" in x;
const leaf = (x: Item): Leaf => (typeof x === "string" ? { rule: x, enabled: true } : x as Leaf);

/** One rule as an Any/All tree of conditions, nested to any depth; each condition can be switched off without deleting it (B-105, B-107). */
export function GroupEditor({ id, group, onChange, suggestions, depth = 0, onRemove }: {
  id: string; group: Group; onChange: (g: Group) => void; suggestions: string[]; depth?: number; onRemove?: () => void;
}) {
  const [open, setOpen] = useState(true);
  const addRef = useRef<HTMLSelectElement>(null);
  const set = (i: number, next: Item | null) => onChange({ ...group, items: next === null ? group.items.filter((_, k) => k !== i) : group.items.map((x, k) => (k === i ? next : x)) });
  const add = (item: Item) => onChange({ ...group, items: [...group.items, item] });
  return (
    <div className="gx" data-depth={depth} tabIndex={depth === 0 ? -1 : undefined} onKeyDown={(e) => {
      if (e.key !== "/" || (e.target as HTMLElement).closest("input,select,textarea")) return;
      e.preventDefault(); e.stopPropagation(); setOpen(true); requestAnimationFrame(() => addRef.current?.focus());
    }}>
      {depth === 0 ? <datalist id={`${id}-dl`}>{suggestions.map((s) => <option key={s} value={s} />)}</datalist> : null}
      <div className="gx-head">
        <button className="icon-btn" aria-label={open ? "Collapse" : "Expand"} onClick={() => setOpen(!open)}>{open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</button>
        <div className="seg" role="group" aria-label="Group logic">
          <button type="button" aria-pressed={group.op === "all"} onClick={() => onChange({ ...group, op: "all" })}>All</button>
          <button type="button" aria-pressed={group.op === "any"} onClick={() => onChange({ ...group, op: "any" })}>Any</button>
        </div>
        <span className="gx-sum">{group.items.length} condition{group.items.length === 1 ? "" : "s"}</span>
        <span style={{ flex: 1 }} />
        <button className="icon-btn" title="Copy as code" aria-label="Copy as code" onClick={() => void navigator.clipboard?.writeText(groupFormula(group)).then(() => toast.success("Copied"))}><Copy size={12} /></button>
        {onRemove ? <button className="icon-btn" aria-label="Remove group" onClick={onRemove}><X size={12} /></button> : null}
      </div>
      {open ? (
        <div className="gx-body">
          {group.items.map((item, i) => isGroup(item)
            ? <GroupEditor key={i} id={id} group={item} depth={depth + 1} suggestions={suggestions} onChange={(g) => set(i, g)} onRemove={() => set(i, null)} />
            : <Condition key={i} id={id} item={leaf(item)} onChange={(l) => set(i, l)} onRemove={() => set(i, null)} onDuplicate={() => onChange({ ...group, items: [...group.items.slice(0, i + 1), leaf(item), ...group.items.slice(i + 1)] })} />)}
          <div className="gx-add">
            <select ref={addRef} className="input" aria-label="Add condition" aria-keyshortcuts="/" value="" onChange={(e) => { if (e.target.value !== "-") add({ rule: e.target.value, enabled: true }); }}>
              <option value="" disabled hidden>Condition</option>
              {paletteOrder().map(([v, l]) => <option key={l} value={v}>{l}</option>)}
            </select>
            <button className="btn sm ghost" onClick={() => add({ op: group.op === "all" ? "any" : "all", items: [{ rule: "", enabled: true }] })}><FolderPlus size={12} />Group</button>
          </div>
        </div>
      ) : <code className="gx-folded">{groupFormula(group) || "empty"}</code>}
    </div>
  );
}

function Condition({ id, item, onChange, onRemove, onDuplicate }: { id: string; item: Leaf; onChange: (l: Leaf) => void; onRemove: () => void; onDuplicate: () => void }) {
  const rows = fromFormula(item.rule);
  const row = rows && rows.length === 1 ? rows[0] : null;
  const on = item.enabled !== false;
  return (
    <div className="gx-row" data-off={!on || undefined} data-empty={!item.rule.trim() || undefined}>
      {row ? (
        <>
          <input className="input" list={`${id}-dl`} aria-label="Left" value={row.left} onChange={(e) => onChange({ ...item, rule: toFormula([{ ...row, left: e.target.value }]) || e.target.value })} />
          <select className="input" aria-label="Operator" value={row.op} onChange={(e) => onChange({ ...item, rule: toFormula([{ ...row, op: e.target.value }]) })}>
            {OPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input className="input" list={`${id}-dl`} aria-label="Right" value={row.right} onChange={(e) => onChange({ ...item, rule: toFormula([{ ...row, right: e.target.value }]) || e.target.value })} />
        </>
      ) : <input className="input gx-formula" list={`${id}-dl`} aria-label="Condition" placeholder="formula" value={item.rule} onChange={(e) => onChange({ ...item, rule: e.target.value })} />}
      <button className="icon-btn" title={on ? "Switch off" : "Switch on"} aria-label={on ? "Switch off" : "Switch on"} onClick={() => onChange({ ...item, enabled: !on })}>{on ? <Eye size={12} /> : <EyeOff size={12} />}</button>
      <button className="icon-btn" title="Duplicate" aria-label="Duplicate" onClick={onDuplicate}><Plus size={12} /></button>
      <button className="icon-btn" aria-label="Remove" onClick={onRemove}><X size={12} /></button>
    </div>
  );
}

/** Same as the server's group_formula: switched-off conditions and empty groups drop out. */
export function groupFormula(node: Item): string {
  if (!isGroup(node)) { const l = leaf(node); return l.enabled === false || !l.rule.trim() ? "" : `(${l.rule.trim()})`; }
  const parts = node.items.map(groupFormula).filter(Boolean);
  return parts.length ? `(${parts.join(node.op === "all" ? " & " : " | ")})` : "";
}

/** A flat formula as a group, or null when it is not a list of comparisons. */
export function toGroup(text: string): Group | null {
  const rows = fromFormula(text);
  if (!rows) return null;
  const any = rows.length > 1 && rows.slice(1).every((r) => r.join === "|");
  if (rows.length > 1 && !any && rows.slice(1).some((r) => r.join === "|")) return null;
  return { op: any ? "any" : "all", items: rows.map((r) => ({ rule: toFormula([{ ...r, join: "&" }]), enabled: true })) };
}

/** Condition kinds in the order set in Customise (B-135). */
export function paletteOrder(): [string, string][] {
  let order: string[] = [];
  try { order = (JSON.parse(localStorage.getItem("studio:build:defaults") ?? "{}") as { palette?: string[] }).palette ?? []; } catch { /* blocked */ }
  const at = (l: string) => { const i = order.indexOf(l); return i === -1 ? order.length + KINDS.findIndex(([, x]) => x === l) : i; };
  return [...KINDS].sort((a, b) => at(a[1]) - at(b[1]));
}
