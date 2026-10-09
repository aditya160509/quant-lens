"use client";

import { memo } from "react";

export type DumbbellRow = { label: string; a: number | null; b: number | null; format: (v: number) => string; better?: "high" | "low" };

/**
 * Before and after, metric by metric: a grey dot for the yardstick (a), an accent dot for the
 * strategy under test (b), joined by a line that is green when b is better and red when worse.
 * Each row has its own scale, so metrics in different units sit together; the numbers are printed.
 */
function DumbbellImpl({ rows, aLabel, bLabel }: { rows: DumbbellRow[]; aLabel: string; bLabel: string }) {
  return (
    <div className="dumbbell" role="table" aria-label={`${bLabel} against ${aLabel}`}>
      <div className="db-key" role="row">
        <span />
        <span><i className="db-dot a" />{aLabel}<i className="db-dot b" style={{ marginLeft: 12 }} />{bLabel}</span>
        <span>Change</span>
      </div>
      {rows.filter((r) => r.a !== null && r.b !== null).map((r) => {
        const a = r.a as number, b = r.b as number;
        const lo = Math.min(a, b), hi = Math.max(a, b), pad = (hi - lo || Math.abs(hi) || 1) * 0.35;
        const x0 = lo - pad, x1 = hi + pad;
        const pos = (v: number) => `${((v - x0) / (x1 - x0)) * 100}%`;
        const better = r.better === "low" ? b < a : b > a;
        const tone = a === b ? "var(--text-4)" : better ? "var(--up)" : "var(--down)";
        const zero = x0 < 0 && x1 > 0 ? pos(0) : null;
        return (
          <div key={r.label} className="db-row" role="row">
            <span className="db-label">{r.label}</span>
            <span className="db-track">
              {zero ? <i className="db-zero" style={{ left: zero }} /> : null}
              <i className="db-line" style={{ left: pos(lo), width: `calc(${pos(hi)} - ${pos(lo)})`, background: tone }} />
              <i className="db-dot a" style={{ left: pos(a) }} title={`${aLabel}: ${r.format(a)}`}><span className="num">{r.format(a)}</span></i>
              <i className="db-dot b" style={{ left: pos(b) }} title={`${bLabel}: ${r.format(b)}`}><span className="num">{r.format(b)}</span></i>
            </span>
            <span className="num db-delta" style={{ color: tone }}>{b - a >= 0 ? "+" : "−"}{r.format(Math.abs(b - a))}</span>
          </div>
        );
      })}
    </div>
  );
}

export const Dumbbell = memo(DumbbellImpl);
