"use client";

import { createElement } from "react";
import { Treemap } from "@/charts/Treemap";
import { DataTable } from "@/kit/DataTable";
import { isNum, label, out, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";
import { ScreenScatter, SensitivityStrip } from "./trust/Charts";
import { NearMisses, RunInfo, runOf, ScreenDiff, WhyHere } from "./trust/Explain";
import { SCREENER_BASE } from "./base";

/** Every passing name as a rectangle: area is market cap, colour is the 1-month return, grouped by sector. */
export function ScreenTreemap({ result }: ViewProps) {
  const items = out(result, "ranked_screener_table").filter((r) => isNum(r.market_cap) && r.market_cap > 0).map((r) => ({
    label: String(r.ticker), group: typeof r.sector === "string" && r.sector ? r.sector : "Unknown sector",
    size: r.market_cap as number, colorValue: isNum(r.return_1m) ? r.return_1m : undefined,
  }));
  return <Treemap title="Passing names by sector" sizeLabel="Market cap" colorLabel={`Mean ${label("return_1m").toLowerCase()}`} colorAggregate="mean" format={(v) => `$${(v / 1e9).toLocaleString("en-US", { maximumFractionDigits: 0 })}B`} colorFormat={(v) => pct(v, 1)} items={items} />;
}

/** The results table: its arrangement lives in the URL and in saved views, and a row opens its reasons. */
export function ScreenTable({ rows, result, opts }: ViewProps) {
  const runId = runOf(result)?.id;
  const detail = runId ? (row: Record<string, unknown>) => (typeof row.ticker === "string" ? createElement(WhyHere, { ticker: row.ticker, runId }) : null) : undefined;
  return <DataTable rows={rows} opts={{ ...opts, viewKey: "screener:results", xlsx: `${SCREENER_BASE}/export/xlsx`, detail }} />;
}

export const NearMissView = ({ result }: ViewProps) => <NearMisses result={result} />;
export const RunView = ({ result }: ViewProps) => <RunInfo result={result} />;
export const DiffView = ({ result, feature }: ViewProps) => <ScreenDiff result={result} featureId={feature.id} />;
export const ScatterView = ({ rows, feature }: ViewProps) => <ScreenScatter rows={rows} feature={feature} />;
export const SensitivityView = ({ result }: ViewProps) => <SensitivityStrip result={result} />;
