"use client";

import { useMemo } from "react";
import { CalendarHeatmap } from "@/charts/CalendarHeatmap";
import { Distribution } from "@/charts/Distribution";
import { Diverging } from "@/charts/Diverging";
import { DrawdownStrip, HoldingsTimeline } from "@/charts/Backtest";
import { Empty } from "@/kit/DataTable";
import { openQuickLook } from "@/kit/QuickLook";
import { isNum, pct } from "@/modules/research/format";
import type { Row } from "@/modules/research/types";
import type { ViewProps } from "@/modules/research/outputs/types";
import "./tearsheet.css";


/** Last equity value of each month, by key "YYYY-MM". */
function monthEnds(rows: Row[], key: "strategy") {
  const out = new Map<string, number>();
  rows.forEach((r) => { const v = r[key]; if (isNum(v) && typeof r.date === "string") out.set(r.date.slice(0, 7), v); });
  return out;
}

function monthlyReturns(rows: Row[], key: "strategy") {
  const ends = [...monthEnds(rows, key)];
  const first = rows.find((r) => isNum(r[key]))?.[key] as number | undefined;
  return new Map(ends.map(([m, v], i) => [m, v / (i ? ends[i - 1][1] : first ?? v) - 1]));
}

/** Monthly strategy returns on the shared calendar heatmap. */
export function MonthlyHeatmap({ rows }: ViewProps) {
  const data = useMemo(() => [...monthlyReturns(rows, "strategy")].map(([m, value]) => ({ date: `${m}-15`, value })), [rows]);
  return <CalendarHeatmap title="Monthly returns" data={data} aggregate="sum" format={(v) => pct(v, 1)} />;
}

/** Daily strategy returns on the shared distribution, worst 5% day marked. */
export function ReturnHistogram({ rows }: ViewProps) {
  const daily = useMemo(() => rows.flatMap((r, i) => { const a = rows[i - 1]?.strategy, b = r.strategy; return i && isNum(a) && isNum(b) && a ? [b / a - 1] : []; }), [rows]);
  if (daily.length < 20) return <Empty />;
  const var5 = [...daily].sort((x, y) => x - y)[Math.floor(daily.length * 0.05)];
  return <Distribution values={daily} observed={var5} tail="left" xLabel="Daily return" observedLabel="5% worst day" format={(v) => pct(v, 2)} />;
}

/** Net contribution per name on the shared diverging bars, best and worst 12; a bar opens the drawer. */
export function AttributionBars({ rows }: ViewProps) {
  const vals = rows.filter((r) => isNum(r.net_pnl_contribution)).map((r) => ({ label: String(r.ticker), value: r.net_pnl_contribution as number })).sort((a, b) => b.value - a.value);
  if (!vals.length) return <Empty />;
  return <Diverging rows={vals.length > 24 ? [...vals.slice(0, 12), ...vals.slice(-12)] : vals} format={(v) => pct(v, 2)} labelWidth={72} onSelect={(r) => openQuickLook(r.label)} />;
}

export function Underwater({ rows }: ViewProps) { return <DrawdownStrip rows={rows} />; }
export function HoldingsGantt({ rows }: ViewProps) { return <HoldingsTimeline rows={rows} onSelect={openQuickLook} />; }
