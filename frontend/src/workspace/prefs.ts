"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type Density = "compact" | "comfortable";
export type Accent = "blue" | "teal" | "violet" | "amber";
export type Palette = "default" | "colorblind" | "vivid" | "mono";
export type LineWeight = "thin" | "regular" | "bold";

type Prefs = {
  density: Density;
  invertColors: boolean;
  reducedMotion: boolean;
  accent: Accent;
  palette: Palette;
  grid: boolean;
  lineWeight: LineWeight;
  set: (patch: Partial<Omit<Prefs, "set">>) => void;
};

/** Workspace display preferences, persisted per device. */
export const usePrefs = create<Prefs>()(
  persist(
    (set) => ({ density: "comfortable", invertColors: false, reducedMotion: false, accent: "blue", palette: "default", grid: true, lineWeight: "regular", set: (patch) => set(patch) }),
    { name: "ws-prefs", storage: createJSONStorage(() => localStorage), version: 2, migrate: (s) => ({ palette: "default", grid: true, lineWeight: "regular", ...(s as object) }) as Prefs },
  ),
);

/** Class names applied to every workspace root and portal so prefs reach overlays too. */
export const prefClasses = (p: Pick<Prefs, "density" | "invertColors" | "reducedMotion" | "accent" | "palette" | "grid" | "lineWeight">) =>
  ` d-${p.density} acc-${p.accent} pal-${p.palette ?? "default"} lw-${p.lineWeight ?? "regular"}${p.grid === false ? " no-grid" : ""}${p.invertColors ? " inv" : ""}${p.reducedMotion ? " rm" : ""}`;

/** Motion scale in seconds: micro 120ms, standard 200ms, large 350ms. */
export const DUR = { micro: 0.12, base: 0.2, slow: 0.35 } as const;
