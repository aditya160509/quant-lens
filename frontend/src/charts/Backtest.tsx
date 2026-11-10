"use client";

import { isNum, pct } from "@/modules/research/format";
import type { Row } from "@/modules/research/types";
import "./backtest.css";

const Empty = () => <p className="chart-empty">Nothing to show.</p>;

/** Drawdown from the running peak, as a filled strip under the equity curve. */
export function DrawdownStrip({ rows }: { rows: Row[] }) {
  const pts = rows.filter((r) => isNum(r.drawdown)) as (Row & { drawdown: number })[];
  if (pts.length < 2) return <Empty />;
  const min = Math.min(-0.01, ...pts.map((r) => r.drawdown));
  const worst = pts.reduce((a, r) => (r.drawdown < a.drawdown ? r : a));
  const path = pts.map((r, i) => `${(i / (pts.length - 1)) * 100},${(r.drawdown / min) * 40}`).join(" L");
  return (
    <div className="ts-under">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={`Drawdown, worst ${pct(worst.drawdown, 1)}`}>
        <path d={`M0,0 L${path} L100,0 Z`} fill="color-mix(in oklch, var(--down) 30%, transparent)" stroke="var(--down)" strokeWidth={0.6} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="ts-legend"><span>Worst <b className="num" style={{ color: "var(--down)" }}>{pct(worst.drawdown, 1)}</b> on {String(worst.date).slice(0, 10)}</span><span>Now <b className="num">{pct(pts[pts.length - 1].drawdown, 1)}</b></span></div>
    </div>
  );
}


/** Every holding as a bar from entry to exit (open ones run to the end), coloured by its net result. */
export function HoldingsTimeline({ rows, onSelect }: { rows: Row[]; onSelect?: (ticker: string) => void }) {
  const eps = rows.filter((r) => r.entry_date);
  if (!eps.length) return <Empty />;
  const t = (d: unknown) => new Date(String(d)).getTime();
  // shortcut: open holdings end at the last date seen in the log, not the curve end; pass the curve end if bars look short.
  const start = Math.min(...eps.map((r) => t(r.entry_date))), end = Math.max(...eps.map((r) => t(r.exit_date ?? r.last_mark_date ?? r.entry_date)));
  const span = end - start || 1;
  const names = [...new Set(eps.map((r) => String(r.ticker)))].slice(0, 60);
  return (
    <div className="ts-gantt">
      {names.map((n) => (
        <div key={n} className="ts-g-row">
          <button type="button" className="tk-link" onClick={() => onSelect?.(n)}>{n}</button>
          <span className="ts-g-track">
            {eps.filter((r) => String(r.ticker) === n).map((r, i) => {
              const a = (t(r.entry_date) - start) / span, b = ((r.exit_date ? t(r.exit_date) : end) - start) / span;
              const v = isNum(r.net_pnl_contribution) ? r.net_pnl_contribution : isNum(r.price_return) ? r.price_return : 0;
              return <i key={i} className={v >= 0 ? "up" : "down"} data-open={!r.exit_date} style={{ left: `${a * 100}%`, width: `${Math.max(0.4, (b - a) * 100)}%` }} title={`${String(r.entry_date).slice(0, 10)} → ${r.exit_date ? String(r.exit_date).slice(0, 10) : "open"} · ${pct(v, 2)}`} />;
            })}
          </span>
        </div>
      ))}
      <div className="ts-g-axis num"><span>{new Date(start).toISOString().slice(0, 10)}</span><span>{new Date(end).toISOString().slice(0, 10)}</span></div>
    </div>
  );
}
