"use client";

import { useState } from "react";
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
  colTitle?: string;
  highlightRow?: number;
  outline?: (r: number, c: number) => boolean;
};

/** Matrix heatmap rendered as a table so values stay readable and selectable; colour encodes magnitude. */
export function Heatmap({ rows, cols, values, format = (v) => v.toFixed(3), centered = true, margin, rowTitle = "", colTitle, highlightRow, outline }: Props) {
  const [hover, setHover] = useState<[number, number] | null>(null);
  const flat = values.flat().filter((v): v is number => v !== null && Number.isFinite(v));
  const maxAbs = Math.max(1e-12, ...flat.map(Math.abs));
  const min = Math.min(...flat), max = Math.max(...flat);
  const fill = (v: number | null) => {
    if (v === null || !Number.isFinite(v)) return "transparent";
    return centered ? diverging(v / maxAbs) : `color-mix(in oklch, var(--s1) ${Math.round(((v - min) / (max - min || 1)) * 75)}%, var(--panel-2))`;
  };
  const marginMax = margin ? Math.max(1e-12, ...margin.values.filter((v): v is number => v !== null).map(Math.abs)) : 1;

  return (
    <div style={{ overflowX: "auto" }}>
      {colTitle ? <div style={{ fontSize: 11.5, color: "var(--text-3)", margin: "0 0 6px", paddingLeft: 120 }}>{colTitle} →</div> : null}
      <table role="grid" style={{ borderCollapse: "separate", borderSpacing: 3, width: "100%", fontFamily: "var(--mono)", fontSize: 11.5 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", color: "var(--text-3)", fontFamily: "var(--font)", fontWeight: 500, fontSize: 11.5, padding: "0 6px", whiteSpace: "nowrap" }}>{rowTitle}</th>
            {cols.map((c, j) => <th key={c} style={{ color: hover?.[1] === j ? "var(--text)" : "var(--text-3)", fontWeight: 500, padding: "0 4px 4px", whiteSpace: "nowrap" }}>{c}</th>)}
            {margin ? <th style={{ color: "var(--text-3)", fontWeight: 500, padding: "0 4px 4px", fontFamily: "var(--font)", whiteSpace: "nowrap" }}>{margin.label}</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r}>
              <th scope="row" style={{ textAlign: "left", color: hover?.[0] === i || highlightRow === i ? "var(--text)" : "var(--text-2)", fontWeight: highlightRow === i ? 600 : 450, padding: "0 6px", whiteSpace: "nowrap", fontFamily: "var(--font)", fontSize: 12 }}>{r}</th>
              {cols.map((c, j) => {
                const v = values[i]?.[j] ?? null;
                const active = hover?.[0] === i && hover?.[1] === j;
                return (
                  <td key={c} onPointerEnter={() => setHover([i, j])} onPointerLeave={() => setHover(null)}
                    style={{
                      height: 34, minWidth: 58, textAlign: "center", borderRadius: 6, background: fill(v), color: "var(--text)",
                      boxShadow: active ? "inset 0 0 0 1.5px var(--text)" : outline?.(i, j) ? "inset 0 0 0 1.5px var(--warn)" : undefined,
                      transition: "box-shadow .12s",
                    }}>
                    {v === null ? "–" : format(v)}
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
      </table>
    </div>
  );
}
