"use client";

import { useState } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Row } from "@/modules/research/types";

export type Fn = "mean" | "median" | "sum" | "count";
export type Fmt = { mode: "bar" | "heat" | "sign" | "rule"; op?: ">" | "<"; value?: number };
export type TableView = {
  order: string[] | null;
  hidden: string[];
  pinned: string[];
  widths: Record<string, number>;
  sort: { key: string; dir: 1 | -1 } | null;
  /** Second sort key, set with shift-click. */
  sort2?: { key: string; dir: 1 | -1 } | null;
  density: "compact" | "comfortable";
  tint: boolean;
  fmt: Record<string, Fmt>;
  /** Show a column as its percentile among the shown names, or among those in the same sector. */
  pct: Record<string, "all" | "sector">;
  groupBy: string | null;
  summary: Exclude<Fn, "count">;
  /** Named column set shown as a tab; null shows every column. */
  set: string | null;
};

export const EMPTY_VIEW: TableView = { order: null, hidden: [], pinned: [], widths: {}, sort: null, density: "comfortable", tint: false, fmt: {}, pct: {}, groupBy: null, summary: "median", set: null };

export function reduce(values: number[], fn: Fn): number | null {
  if (fn === "count") return values.length;
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  if (fn === "sum") return values.reduce((a, b) => a + b, 0);
  if (fn === "mean") return values.reduce((a, b) => a + b, 0) / values.length;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Live view of each keyed table, so the URL and saved views can read and write what the reader arranged. */
export const useTableViews = create<{ live: Record<string, TableView>; set: (key: string, view: TableView) => void }>()((set) => ({
  live: {},
  set: (key, view) => set((s) => ({ live: { ...s.live, [key]: view } })),
}));

export function useTableView(key: string | undefined, initial: Partial<TableView>): [TableView, (next: (v: TableView) => TableView) => void] {
  const [local, setLocal] = useState<TableView>({ ...EMPTY_VIEW, ...initial });
  const stored = useTableViews((s) => (key ? s.live[key] : undefined));
  const view = key ? stored ?? { ...EMPTY_VIEW, ...initial } : local;
  const update = (next: (v: TableView) => TableView) => (key ? useTableViews.getState().set(key, next(view)) : setLocal(next));
  return [view, update];
}

export type SavedView = { id: string; name: string; scope: "here" | "all"; key: string; view: TableView };

/** Named arrangements kept on this device: for one table, or for every table. */
export const useSavedViews = create<{ views: SavedView[]; save: (v: Omit<SavedView, "id">) => void; remove: (id: string) => void }>()(
  persist((set) => ({
    views: [],
    save: (v) => set((s) => ({ views: [...s.views.filter((x) => !(x.name === v.name && x.key === v.key)), { ...v, id: `${Date.now()}` }] })),
    remove: (id) => set((s) => ({ views: s.views.filter((x) => x.id !== id) })),
  }), { name: "table-views", storage: createJSONStorage(() => localStorage), version: 1 }),
);

/** Each number as its percentile among the rows (or among the rows of its sector); unknowns stay unknown. */
export function withPercentiles(rows: Row[], pct: TableView["pct"]): Row[] {
  const cols = Object.keys(pct);
  if (!cols.length) return rows;
  const out = rows.map((r) => ({ ...r }));
  for (const c of cols) {
    const groups = new Map<string, number[]>();
    out.forEach((r, i) => {
      if (typeof r[c] === "number" && Number.isFinite(r[c])) {
        const g = pct[c] === "sector" ? String(r.sector ?? "Unknown") : "";
        groups.set(g, [...(groups.get(g) ?? []), i]);
      }
    });
    for (const idx of groups.values()) {
      const sorted = idx.map((i) => out[i][c] as number).sort((a, b) => a - b);
      const count = (v: number, inclusive: boolean) => { let lo = 0, hi = sorted.length; while (lo < hi) { const m = (lo + hi) >> 1; if (inclusive ? sorted[m] <= v : sorted[m] < v) lo = m + 1; else hi = m; } return lo; };
      idx.forEach((i) => {
        const v = rows[i][c] as number;
        const less = count(v, false);
        out[i][c] = sorted.length > 1 ? ((less + (count(v, true) - less - 1) / 2) / (sorted.length - 1)) * 100 : 50;
      });
    }
  }
  return out;
}
