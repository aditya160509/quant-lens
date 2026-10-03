"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type Region = "left" | "right" | "bottom";

type LayoutStore = {
  open: Record<Region, boolean>;
  /** Set when a toggle came from a button or shortcut, so panels animate instead of snapping. */
  animate: boolean;
  toggle: (r: Region) => void;
  set: (r: Region, open: boolean, animate?: boolean) => void;
};

/** Which workspace regions are open. Shared by the top-bar toggles, the shortcuts and each module's panels. */
export const useLayout = create<LayoutStore>()(
  persist(
    (set) => ({
      open: { left: true, right: true, bottom: false },
      animate: false,
      toggle: (r) => set((s) => ({ open: { ...s.open, [r]: !s.open[r] }, animate: true })),
      set: (r, open, animate = false) => set((s) => (s.open[r] === open ? s : { open: { ...s.open, [r]: open }, animate })),
    }),
    { name: "ws-layout", storage: createJSONStorage(() => localStorage), partialize: (s) => ({ open: s.open }), version: 1 },
  ),
);

export const SHORTCUTS: Record<Region, { key: string; label: string }> = {
  left: { key: "b", label: "⌘B" },
  bottom: { key: "j", label: "⌘J" },
  right: { key: "i", label: "⌘I" },
};
