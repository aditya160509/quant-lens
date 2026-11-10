"use client";

import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { first, isNum, out } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./strategy.css";

const HUES = [258, 152, 32, 300, 200, 80, 350];

/** Ranked names with a bar split by factor: each segment is weight times that factor's score, so the bar shows why a name ranks where it does. */
export function FactorStack({ rows, result }: ViewProps) {
  const weights = out(result, "score_transparency_decomposition").filter((w) => typeof w.component === "string" && isNum(w.weight)) as { component: string; weight: number }[];
  if (!rows.length || !weights.length) return <Empty />;
  const neff = first(result, "effective_number_of_factors");
  const sorted = [...rows].sort((a, b) => (isNum(a.rank) ? a.rank : 1e9) - (isNum(b.rank) ? b.rank : 1e9)).slice(0, 200);
  return (
    <div className="fs">
      <div className="fs-legend">
        {weights.map((w, i) => <span key={w.component}><i style={{ background: `oklch(0.66 0.14 ${HUES[i % HUES.length]})` }} />{w.component} <b className="num">{(w.weight * 100).toFixed(0)}%</b></span>)}
        {isNum(neff?.n_eff) ? <span className="fs-neff">Effective factors <b className="num">{neff.n_eff.toFixed(1)}</b> of {String(neff.component_count ?? weights.length)}</span> : null}
      </div>
      <ol className="fs-list">
        {sorted.map((r) => (
          <li key={String(r.ticker)}>
            <span className="fs-rank num">{String(r.rank ?? "")}</span>
            <button type="button" className="tk-link fs-tk" onClick={() => openQuickLook(String(r.ticker))}>{String(r.ticker)}</button>
            <span className="fs-bar" role="img" aria-label={weights.map((w) => `${w.component} ${isNum(r[w.component]) ? (r[w.component] as number).toFixed(0) : "unknown"}`).join(", ")}>
              {weights.map((w, i) => { const v = r[w.component]; return isNum(v) ? <i key={w.component} title={`${w.component}: ${v.toFixed(0)} × ${(w.weight * 100).toFixed(0)}%`} style={{ width: `${Math.max(0, v) * w.weight}%`, background: `oklch(0.66 0.14 ${HUES[i % HUES.length]})` }} /> : null; })}
            </span>
            <b className="fs-score num">{isNum(r.composite_score) ? r.composite_score.toFixed(0) : "—"}</b>
          </li>
        ))}
      </ol>
    </div>
  );
}
