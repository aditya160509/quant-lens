"use client";

import { Dendrogram } from "@/charts/Dendrogram";
import { StackedArea } from "@/charts/StackedArea";
import type { ViewProps } from "@/modules/research/outputs/types";
import { Skipped } from "./BacktestViews";

type PMeta = { names: string[]; tree: { link: number[][]; order: number[] } | null };

/** Members clustered by correlation distance: the tree HRP splits risk down. */
export function Tree({ result }: ViewProps) {
  const m = result.meta as unknown as PMeta;
  if (!m.tree) return <Skipped reason="needs three or more members" />;
  return <Dendrogram merges={m.tree.link.map(([l, r, d, c]) => ({ left: l, right: r, distance: d, count: c }))} leaves={m.names} />;
}

/** Weights as they were re-estimated (quarterly, or each rotation). */
export function WeightsOverTime({ rows, result }: ViewProps) {
  const names = (result.meta as unknown as PMeta).names;
  if (rows.length < 2) return <Skipped reason="weights are fixed; set Weights to quarterly or turn on rotation" />;
  return <StackedArea data={rows} keys={names} title="Weights" />;
}
