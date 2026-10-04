"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

/** A date note, or with `y` set, a horizontal level drawn across the chart. */
export type Note = {
  id: string; t: number; text: string; y?: number;
  /** Drawings: two-click trend line or rectangle. Absent on notes and levels (backward compatible). */
  kind?: "trend" | "rect"; t1?: number; y1?: number; t2?: number; y2?: number;
};

type NotesStore = {
  notes: Record<string, Note[]>;
  add: (scope: string, note: Note) => void;
  remove: (scope: string, id: string) => void;
};

/** Notes pinned to dates on charts, kept per chart scope on this device. */
export const useNotes = create<NotesStore>()(
  persist(
    (set) => ({
      notes: {},
      add: (scope, note) => set((s) => ({ notes: { ...s.notes, [scope]: [...(s.notes[scope] ?? []), note] } })),
      remove: (scope, id) => set((s) => ({ notes: { ...s.notes, [scope]: (s.notes[scope] ?? []).filter((n) => n.id !== id) } })),
    }),
    { name: "chart-notes", storage: createJSONStorage(() => localStorage), version: 1 },
  ),
);
