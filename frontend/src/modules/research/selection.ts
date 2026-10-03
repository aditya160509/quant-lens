"use client";

import { create } from "zustand";
import type { ReactNode } from "react";

export type Selection = { title: string; rows: [string, ReactNode][]; note?: string } | null;

/** What the user is pointing at in any chart; the inspector shows it in full. */
export const useSelection = create<{ selection: Selection; select: (s: Selection) => void }>()((set) => ({
  selection: null,
  select: (selection) => set({ selection }),
}));
