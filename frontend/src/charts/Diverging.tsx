"use client";

import { useState } from "react";
import { fmtTick } from "./core";

export type DivergingRow = {
  label: string;
  value: number;
  /** Optional split: loss part (<= 0) and gain part (>= 0); value is their sum. */
  neg?: number;
  pos?: number;
  /** Extra text shown in the hover readout. */
  note?: string;
};

export type DivergingProps = {
  rows: DivergingRow[];
  /** Optional first summary row, separated from the rest by a rule. */
  all?: DivergingRow;
  format?: (v: number) => string;
  labelWidth?: number;
  valueWidth?: number;
  rowHeight?: number;
  onSelect?: (row: DivergingRow) => void;
};

const tone = (v: number) => (v > 0 ? "var(--up)" : v < 0 ? "var(--down)" : "var(--text-3)");

/** Horizontal bars growing left (negative) or right (positive) from a centre axis. */
export function Diverging({ rows, all, format = fmtTick, labelWidth = 140, valueWidth = 72, rowHeight, onSelect }: DivergingProps) {
  const [hover, setHover] = useState<string | null>(null);
  const list = all ? [all, ...rows] : rows;
  const max = Math.max(1e-9, ...list.flatMap((r) => [Math.abs(r.value), Math.abs(r.neg ?? 0), Math.abs(r.pos ?? 0)]));
  const h = rowHeight ? `${rowHeight}px` : undefined;
  const hovered = list.find((r) => r.label === hover);

  const renderRow = (r: DivergingRow, i = -1) => {
    const seg = (v: number, c: string, from: "left" | "right") => (
      <div className="dv-bar" style={{ position: "absolute", top: 5, bottom: 5, [from]: "50%", width: `${(Math.abs(v) / max) * 50}%`, background: c, opacity: 0.85, borderRadius: from === "left" ? "2px 0 0 2px" : "0 2px 2px 0" }} />
    );
    const split = r.neg !== undefined || r.pos !== undefined;
    return (
      <div key={`${r.label}-${i}`} className="dv-row" role={onSelect ? "button" : undefined} tabIndex={onSelect ? 0 : undefined}
        style={{ gridTemplateColumns: `${labelWidth}px 1fr ${valueWidth}px`, minHeight: h, cursor: onSelect ? "pointer" : undefined, fontSize: 12 }}
        onMouseEnter={() => setHover(r.label)} onMouseLeave={() => setHover(null)}
        onClick={() => onSelect?.(r)} onKeyDown={(e) => { if (e.key === "Enter") onSelect?.(r); }}>
        <span style={{ color: "var(--text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: 8 }}>{r.label}</span>
        <div style={{ position: "relative", alignSelf: "stretch" }}>
          <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--line)" }} />
          {split ? <>{seg(r.neg ?? 0, "var(--down)", "right")}{seg(r.pos ?? 0, "var(--up)", "left")}</>
            : seg(r.value, tone(r.value), r.value < 0 ? "right" : "left")}
        </div>
        <span className="num" style={{ textAlign: "right", color: tone(r.value), fontFamily: "var(--mono)" }}>{format(r.value)}</span>
      </div>
    );
  };

  return (
    <div style={{ position: "relative" }}>
      {all ? <>{renderRow(all)}<div style={{ height: 1, background: "var(--line)", margin: "4px 0" }} /></> : null}
      {rows.map(renderRow)}
      <div style={{ minHeight: 18, marginTop: 6, fontSize: 11.5, color: "var(--text-3)" }} aria-live="polite">
        {hovered ? <><span style={{ color: "var(--text-2)" }}>{hovered.label}</span>{" "}
          <span className="num">{format(hovered.value)}</span>
          {hovered.neg !== undefined || hovered.pos !== undefined ? <span className="num">{` (${format(hovered.neg ?? 0)} / ${format(hovered.pos ?? 0)})`}</span> : null}
          {hovered.note ? ` ${hovered.note}` : null}</> : null}
      </div>
    </div>
  );
}
