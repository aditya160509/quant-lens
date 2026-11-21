"use client";

import { memo, useState } from "react";
import { diverging } from "./core";

type Props = {
  rows: string[];
  cols: string[];
  values: (number | null)[][];
  format?: (v: number) => string;
  /** Symmetric scale around zero (correlations, returns). Otherwise a single-hue scale from the minimum. */
  centered?: boolean;
  /** Extra right-hand column, e.g. a long-short spread per row. */
  margin?: { label: string; values: (number | null)[] };
  rowTitle?: string;
  /** Optional upper header row grouping consecutive columns, e.g. one group per model. Spans should sum to cols.length. */
  colGroups?: { label: string; span: number }[];
  colTitle?: string;
  highlightRow?: number;
  /** Sum only additive quantities; never enable for correlations or rates. */
  totals?: boolean;
  outline?: (r: number, c: number) => boolean;
  /** Makes cells clickable. */
  onCell?: (r: number, c: number) => void;
};

/** Matrix heatmap rendered as a table so values stay readable and selectable; colour encodes magnitude. */
function HeatmapImpl({ rows, cols, values, format = (v) => v.toFixed(3), centered = true, margin, rowTitle = "", colGroups, colTitle, highlightRow, outline, onCell, totals = false }: Props) {
  const [sortRow, setSortRow] = useState<{ col: number; desc: boolean } | null>(null);
  const [sortCol, setSortCol] = useState<{ row: number; desc: boolean } | null>(null);
  const [hover, setHover] = useState<[number, number] | null>(null);
  const flat = values.flat().filter((v): v is number => v !== null && Number.isFinite(v));
  const maxAbs = Math.max(1e-12, ...flat.map(Math.abs));
  const min = Math.min(...flat), max = Math.max(...flat);
  const fill = (v: number | null) => {
    if (v === null || !Number.isFinite(v)) return "transparent";
    return centered ? diverging(v / maxAbs) : `color-mix(in oklch, var(--s1) ${Math.round(((v - min) / (max - min || 1)) * 75)}%, var(--panel-2))`;
  };
  const marginMax = margin ? Math.max(1e-12, ...margin.values.filter((v): v is number => v !== null).map(Math.abs)) : 1;

  const compare = (a: number | null | undefined, b: number | null | undefined, desc: boolean) => {
    if (a == null || !Number.isFinite(a)) return b == null || !Number.isFinite(b) ? 0 : 1;
    if (b == null || !Number.isFinite(b)) return -1;
    return (a - b) * (desc ? -1 : 1);
  };
  const rowIds = rows.map((_, i) => i).sort((a, b) => sortRow ? compare(values[a]?.[sortRow.col], values[b]?.[sortRow.col], sortRow.desc) : a - b);
  const colIds = cols.map((_, i) => i).sort((a, b) => sortCol && !colGroups?.length ? compare(values[sortCol.row]?.[a], values[sortCol.row]?.[b], sortCol.desc) : a - b);
  const totalFor = (j: number) => { const finite = values.map((row) => row[j]).filter((v): v is number => v != null && Number.isFinite(v)); return finite.length ? finite.reduce((a, b) => a + b, 0) : null; };
  return (
    <div style={{ overflowX: "auto" }}>
      {colTitle ? <div style={{ fontSize: 11.5, color: "var(--text-3)", margin: "0 0 6px", paddingLeft: 120 }}>{colTitle} →</div> : null}
      <div className="heat-key"><span>{format(centered ? -maxAbs : flat.length ? min : 0)}</span>{[0, .25, .5, .75, 1].map((v) => <i key={v} aria-hidden style={{ background: fill(centered ? (v * 2 - 1) * maxAbs : min + v * (max - min)) }} />)}<span>{format(centered ? maxAbs : flat.length ? max : 0)}</span><span>Missing: –</span>{sortRow || sortCol ? <button className="btn sm ghost" onClick={() => { setSortRow(null); setSortCol(null); }}>Reset order</button> : null}</div>
      <table aria-label={[rowTitle, colTitle].filter(Boolean).join(" by ") || "Heat table"} style={{ borderCollapse: "separate", borderSpacing: 3, width: "100%", fontFamily: "var(--mono)", fontSize: 11.5 }}>
        <thead>
          {colGroups?.length ? (
            <tr>
              <th />
              {colGroups.map((g, i) => <th key={`${g.label}-${i}`} colSpan={g.span} style={{ color: "var(--text-2)", fontFamily: "var(--font)", fontWeight: 600, fontSize: 11.5, padding: "0 4px 3px", borderBottom: "1px solid var(--line, var(--text-4))", whiteSpace: "nowrap" }}>{g.label}</th>)}
              {margin ? <th /> : null}
            </tr>
          ) : null}
          <tr>
            <th style={{ textAlign: "left", color: "var(--text-3)", fontFamily: "var(--font)", fontWeight: 500, fontSize: 11.5, padding: "0 6px", whiteSpace: "nowrap" }}>{rowTitle}</th>
            {colIds.map((j) => <th key={`${cols[j]}-${j}`} aria-sort={sortRow?.col === j ? sortRow.desc ? "descending" : "ascending" : "none"} style={{ color: hover?.[1] === j ? "var(--text)" : "var(--text-3)", fontWeight: 500, padding: "0 4px 4px", whiteSpace: "nowrap" }}><button className="heat-sort" title={`Sort rows by ${cols[j]}`} onClick={() => setSortRow((s) => ({ col: j, desc: s?.col === j ? !s.desc : true }))}>{cols[j]}{sortRow?.col === j ? sortRow.desc ? " ↓" : " ↑" : ""}</button></th>)}
            {margin ? <th style={{ color: "var(--text-3)", fontWeight: 500, padding: "0 4px 4px", fontFamily: "var(--font)", whiteSpace: "nowrap" }}>{margin.label}</th> : null}
          </tr>
        </thead>
        <tbody>
          {rowIds.map((i) => (
            <tr key={`${rows[i]}-${i}`}>
              <th scope="row" style={{ textAlign: "left", color: hover?.[0] === i || highlightRow === i ? "var(--text)" : "var(--text-2)", fontWeight: highlightRow === i ? 600 : 450, padding: "0 6px", whiteSpace: "nowrap", fontFamily: "var(--font)", fontSize: 12 }}>{colGroups?.length ? rows[i] : <button className="heat-sort" title={`Sort columns by ${rows[i]}`} onClick={() => setSortCol((s) => ({ row: i, desc: s?.row === i ? !s.desc : true }))}>{rows[i]}{sortCol?.row === i ? sortCol.desc ? " ↓" : " ↑" : ""}</button>}</th>
              {colIds.map((j) => {
                const c = cols[j];
                const v = values[i]?.[j] ?? null;
                const active = hover?.[0] === i && hover?.[1] === j;
                return (
                  <td key={`${c}-${j}`} onClick={onCell ? () => onCell(i, j) : undefined} onPointerEnter={() => setHover([i, j])} onPointerLeave={() => setHover(null)} title={`${rows[i]} · ${c}: ${v === null || !Number.isFinite(v) ? "No observation" : format(v)}`}
                    style={{
                      height: 34, minWidth: 58, textAlign: "center", borderRadius: 6, background: fill(v), color: "var(--text)",
                      boxShadow: active ? "inset 0 0 0 1.5px var(--text)" : outline?.(i, j) ? "inset 0 0 0 1.5px var(--warn)" : undefined,
                      transition: "box-shadow .12s", cursor: onCell ? "pointer" : undefined,
                    }}>
                    {v === null || !Number.isFinite(v) ? "–" : format(v)}
                  </td>
                );
              })}
              {margin ? (
                <td style={{ height: 34, minWidth: 64, textAlign: "center", borderRadius: 6, background: margin.values[i] === null ? "transparent" : diverging((margin.values[i] as number) / marginMax), color: "var(--text)", fontWeight: 600 }}>
                  {margin.values[i] === null ? "–" : format(margin.values[i] as number)}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
        {totals ? <tfoot><tr><th scope="row">Total</th>{colIds.map((j) => { const total = totalFor(j); return <td key={j} style={{ textAlign: "center", padding: 6 }}>{total === null ? "–" : format(total)}</td>; })}{margin ? <td /> : null}</tr></tfoot> : null}
      </table>
    </div>
  );
}

export const Heatmap = memo(HeatmapImpl);
