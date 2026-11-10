"use client";

import type { CSSProperties } from "react";
import { openQuickLook } from "@/kit/QuickLook";
import { Empty } from "@/kit/DataTable";
import { isNum } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./strategy.css";

const CHECKS: [string, string][] = [
  ["f1_positive_roa", "ROA > 0"], ["f2_positive_cfo_assets", "CFO > 0"], ["f3_roa_improving", "ROA up"],
  ["f4_cfo_exceeds_roa", "Accruals"], ["f5_leverage_declining", "Leverage down"], ["f6_liquidity_improving", "Liquidity up"],
  ["f7_no_equity_issuance", "No dilution"], ["f8_margin_improving", "Margin up"], ["f9_turnover_improving", "Turnover up"],
];

/** Nine Piotroski checks per name: pass, fail or unknown, with the score out of the checks known. */
export function PiotroskiMatrix({ rows }: ViewProps) {
  if (!rows.length) return <Empty />;
  return (
    <div className="pio-wrap">
      <table className="pio">
        <thead><tr><th>Ticker</th>{CHECKS.map(([k, l]) => <th key={k} title={k}><span>{l}</span></th>)}<th>Score</th></tr></thead>
        <tbody>
          {rows.map((r) => {
            const known = isNum(r.piotroski_available_criteria) ? r.piotroski_available_criteria : CHECKS.filter(([k]) => isNum(r[k])).length;
            const passed = isNum(r.piotroski_passed) ? r.piotroski_passed : CHECKS.filter(([k]) => r[k] === 1).length;
            return (
              <tr key={String(r.ticker)}>
                <td><button type="button" className="tk-link" onClick={() => openQuickLook(String(r.ticker))}>{String(r.ticker)}</button></td>
                {CHECKS.map(([k, l]) => {
                  const v = r[k];
                  const state = v === 1 ? "pass" : v === 0 ? "fail" : "unk";
                  return <td key={k} className="c"><span className={`pio-cell ${state}`} aria-label={`${l}: ${state === "unk" ? "unknown" : state}`}>{state === "pass" ? "✓" : state === "fail" ? "✕" : "?"}</span></td>;
                })}
                <td className="num"><span className="pio-score" style={{ "--p": `${(passed / 9) * 100}%` } as CSSProperties}>{passed}<small>/{known}</small></span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const ZONES = [{ id: "Distress", max: 1.81 }, { id: "Grey", max: 2.99 }, { id: "Safe", max: Infinity }];
const zoneOf = (z: number) => ZONES.find((x) => z < x.max)?.id ?? "Safe";

/** Altman Z: count per zone, each name placed on one strip with the 1.81 and 2.99 cut lines. */
export function AltmanZones({ rows }: ViewProps) {
  const scored = rows.filter((r) => isNum(r.altman_z_score)) as (Record<string, unknown> & { altman_z_score: number })[];
  if (!scored.length) return <Empty text="No Altman Z for these names." />;
  const lo = Math.min(0, ...scored.map((r) => r.altman_z_score)), hi = Math.max(6, ...scored.map((r) => Math.min(r.altman_z_score, 12)));
  const x = (v: number) => ((Math.min(Math.max(v, lo), hi) - lo) / (hi - lo)) * 100;
  const counts = Object.fromEntries(ZONES.map((z) => [z.id, scored.filter((r) => zoneOf(r.altman_z_score) === z.id).length]));
  return (
    <div className="alt">
      <div className="alt-pills">
        {ZONES.map((z) => <span key={z.id} className={`alt-pill ${z.id.toLowerCase()}`}><b className="num">{counts[z.id]}</b>{z.id}</span>)}
        <span className="alt-miss">{rows.length - scored.length} unknown</span>
      </div>
      <div className="alt-strip" role="img" aria-label="Altman Z of each name">
        <i className="band distress" style={{ left: 0, width: `${x(1.81)}%` }} />
        <i className="band grey" style={{ left: `${x(1.81)}%`, width: `${x(2.99) - x(1.81)}%` }} />
        <i className="band safe" style={{ left: `${x(2.99)}%`, right: 0 }} />
        {scored.map((r) => <button type="button" key={String(r.ticker)} className={`alt-dot ${zoneOf(r.altman_z_score).toLowerCase()}`} style={{ left: `${x(r.altman_z_score)}%` }} title={`${String(r.ticker)} ${r.altman_z_score.toFixed(2)}`} aria-label={`${String(r.ticker)} ${r.altman_z_score.toFixed(2)}`} onClick={() => openQuickLook(String(r.ticker))} />)}
      </div>
      <div className="alt-axis num"><span>{lo.toFixed(0)}</span><span style={{ left: `${x(1.81)}%` }}>1.81</span><span style={{ left: `${x(2.99)}%` }}>2.99</span><span>{hi.toFixed(0)}{hi >= 12 ? "+" : ""}</span></div>
    </div>
  );
}
