"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type StatUnder = "se" | "t" | "ci" | "p" | "none";
export type RegSettings = {
  stat: StatUnder;
  stars: boolean;
  thresholds: [number, number, number];
  rename: Record<string, string>;
  omit: string[];
  order: string[];
  gof: string[] | null; // null = all shared rows
  layout: "stacked" | "side";
  title: string;
  notes: string;
};
export const DEFAULT_REG: RegSettings = { stat: "se", stars: true, thresholds: [0.1, 0.05, 0.01], rename: {}, omit: [], order: [], gof: null, layout: "side", title: "", notes: "" };

type Store = {
  byScope: Record<string, RegSettings>;
  patch: (scope: string, p: Partial<RegSettings>) => void;
  reset: (scope: string) => void;
};

export const useTableSettings = create<Store>()(
  persist(
    (set) => ({
      byScope: {},
      patch: (scope, p) => set((s) => ({ byScope: { ...s.byScope, [scope]: { ...DEFAULT_REG, ...s.byScope[scope], ...p } } })),
      reset: (scope) => set((s) => { const { [scope]: _drop, ...rest } = s.byScope; void _drop; return { byScope: rest }; }),
    }),
    { name: "research-table-settings", version: 1 },
  ),
);

export function useRegSettings(scope: string): RegSettings {
  return useTableSettings((s) => s.byScope[scope]) ?? DEFAULT_REG;
}
