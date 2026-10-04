"use client";

import { create } from "zustand";

export type DataWindowEntry = {
  chartId: string;
  title: string;
  series: { label: string; color: string }[];
  /** Values (formatted) for each series at time t, or null when the chart has no point there. */
  valueAt: (t: number) => (string | null)[];
};

type Store = {
  entries: Record<string, DataWindowEntry>;
  register: (e: DataWindowEntry) => void;
  unregister: (chartId: string) => void;
};

/** Charts that are mounted and willing to report values at the crosshair time. */
export const useDataWindow = create<Store>()((set) => ({
  entries: {},
  register: (e) => set((s) => ({ entries: { ...s.entries, [e.chartId]: e } })),
  unregister: (id) => set((s) => { const { [id]: _drop, ...rest } = s.entries; return { entries: rest }; }),
}));
