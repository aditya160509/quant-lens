"use client";

import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { isNum, label } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./monitor.css";

const SEV: Record<string, number> = { high: 0, medium: 1, low: 2 };

/** Alerts newest and most severe first: type pill, the name, what happened and the value that triggered it. */
export function AlertFeed({ rows }: ViewProps) {
  if (!rows.length) return <Empty text="No alerts on this watchlist." />;
  const sorted = [...rows].sort((a, b) => (SEV[String(a.severity)] ?? 3) - (SEV[String(b.severity)] ?? 3));
  return (
    <ul className="af-feed">
      {sorted.map((r, i) => {
        const dir = isNum(r.direction) ? r.direction : 0;
        return (
          <li key={i} data-sev={String(r.severity ?? "low")}>
            <span className={`af-dir ${dir > 0 ? "up" : dir < 0 ? "down" : ""}`} aria-hidden>{dir > 0 ? "▲" : dir < 0 ? "▼" : "•"}</span>
            <button type="button" className="tk-link af-tk" onClick={() => openQuickLook(String(r.ticker))}>{String(r.ticker)}</button>
            <span className="af-type">{label(String(r.type ?? "alert").toLowerCase())}</span>
            <span className="af-msg">{String(r.message ?? "")}</span>
            {r.date || r.timestamp ? <time className="af-time num">{String(r.date ?? r.timestamp).slice(0, 10)}</time> : null}
          </li>
        );
      })}
    </ul>
  );
}

/** How often each alert type was followed by a rise, at 1, 5 and 21 sessions, with the sample size. */
export function HitRates({ rows }: ViewProps) {
  if (!rows.length) return <Empty text="No alert history yet." />;
  return (
    <div className="hit-grid">
      {rows.map((r) => {
        const rates = (r.hit_rates ?? {}) as Record<string, number | null>;
        const n = (r.sample_sizes ?? {}) as Record<string, number>;
        return (
          <section key={String(r.alert_type)} className="hit-card">
            <h4>{label(String(r.alert_type ?? "").toLowerCase())}</h4>
            {Object.entries(rates).map(([h, v]) => (
              <div key={h} className="hit-row">
                <span>{h}</span>
                <i><u style={{ width: `${isNum(v) ? v * 100 : 0}%` }} data-good={isNum(v) && v > 0.5} /><s aria-hidden /></i>
                <b className="num">{isNum(v) ? `${(v * 100).toFixed(0)}%` : "—"}</b>
                <small className="num">n {n[h] ?? 0}</small>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
