"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Region } from "./layout";

export type SavedView = { id: string; name: string; featureId: string | null; open: Record<Region, boolean>; form: Record<string, unknown> };

type Views = { views: SavedView[]; save: (v: Omit<SavedView, "id">) => void; remove: (id: string) => void };

/** Named workspaces: panel layout, active feature and its study form. */
export const useViews = create<Views>()(
  persist(
    (set) => ({
      views: [],
      save: (v) => set((s) => ({ views: [{ ...v, id: v.name.toLowerCase() }, ...s.views.filter((x) => x.id !== v.name.toLowerCase())].slice(0, 30) })),
      remove: (id) => set((s) => ({ views: s.views.filter((x) => x.id !== id) })),
    }),
    { name: "ws-views", storage: createJSONStorage(() => localStorage), version: 1 },
  ),
);
