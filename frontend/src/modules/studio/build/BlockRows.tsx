"use client";

import { GripVertical, Plus, X } from "lucide-react";
import { useState } from "react";
import { OPS, type Row } from "./blocks";

/** One rule as rows: [left] [op] [right], joined by and/or. Each operand is free text with the formula catalogue as suggestions. */
export function BlockRows({ id, rows, onChange, suggestions }: { id: string; rows: Row[]; onChange: (rows: Row[]) => void; suggestions: string[] }) {
  const [drag, setDrag] = useState<number | null>(null);
  const move = (from: number, to: number) => { const next = [...rows]; const [r] = next.splice(from, 1); next.splice(to, 0, r); onChange(next); };
  const set = (i: number, patch: Partial<Row>) => onChange(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  return (
    <div className="bk">
      <datalist id={`${id}-dl`}>{suggestions.map((s) => <option key={s} value={s} />)}</datalist>
      {rows.map((r, i) => (
        <div key={i} className={`bk-row${drag === i ? " dragging" : ""}`} onDragOver={(e) => { e.preventDefault(); if (drag !== null && drag !== i) { move(drag, i); setDrag(i); } }} onDrop={() => setDrag(null)}>
          <span className="bk-grip" draggable aria-label="Drag to reorder" role="button" tabIndex={-1} onDragStart={() => setDrag(i)} onDragEnd={() => setDrag(null)}><GripVertical size={12} /></span>
          {i ? (
            <select className="input bk-join" aria-label="Join" value={r.join} onChange={(e) => set(i, { join: e.target.value as Row["join"] })}>
              <option value="&">and</option><option value="|">or</option>
            </select>
          ) : <span className="bk-join">when</span>}
          <input className="input" list={`${id}-dl`} aria-label="Left" value={r.left} onChange={(e) => set(i, { left: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Enter") onChange([...rows, { left: "", op: ">", right: "", join: "&" }]); }} />
          <select className="input" aria-label="Operator" value={r.op} onChange={(e) => set(i, { op: e.target.value })}>
            {OPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input className="input" list={`${id}-dl`} aria-label="Right" value={r.right} onChange={(e) => set(i, { right: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Enter") onChange([...rows, { left: "", op: ">", right: "", join: "&" }]); }} />
          <button className="btn sm" aria-label="Remove row" onClick={() => onChange(rows.filter((_, k) => k !== i))}><X size={12} /></button>
        </div>
      ))}
      <button className="btn sm" onClick={() => onChange([...rows, { left: "", op: ">", right: "", join: "&" }])}><Plus size={12} />Condition</button>
    </div>
  );
}
