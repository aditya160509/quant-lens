"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type Density = "compact" | "comfortable";
export type Accent = "blue" | "teal" | "violet" | "amber";

type Prefs = {
  density: Density;
  invertColors: boolean;
  reducedMotion: boolean;
  accent: Accent;
  set: (patch: Partial<Omit<Prefs, "set">>) => void;
};

/** Workspace display preferences, persisted per device. */
export const usePrefs = create<Prefs>()(
  persist(
    (set) => ({ density: "comfortable", invertColors: false, reducedMotion: false, accent: "blue", set: (patch) => set(patch) }),
    { name: "ws-prefs", storage: createJSONStorage(() => localStorage), version: 1 },
  ),
);

/** Class names applied to every workspace root and portal so prefs reach overlays too. */
export const prefClasses = (p: Pick<Prefs, "density" | "invertColors" | "reducedMotion" | "accent">) =>
  ` d-${p.density} acc-${p.accent}${p.invertColors ? " inv" : ""}${p.reducedMotion ? " rm" : ""}`;

/** Motion scale in seconds: micro 120ms, standard 200ms, large 350ms. */
export const DUR = { micro: 0.12, base: 0.2, slow: 0.35 } as const;
