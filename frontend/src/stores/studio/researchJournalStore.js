"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const useResearchJournalStore = create(
  persist(
    (set) => ({
      entries: [],
      tags: [],
      activeEntryId: null,
      filterTag: "",
      query: "",
      editorOpen: false,
      error: null,
      setEntries: (entries) => set({ entries: Array.isArray(entries) ? entries : [], error: null }),
      setTags: (tags) => set({ tags: Array.isArray(tags) ? tags : [] }),
      upsertEntry: (entry) => set((state) => ({
        entries: [entry, ...state.entries.filter((item) => item.id !== entry.id)],
        activeEntryId: entry.id,
        editorOpen: false,
        error: null,
      })),
      removeEntry: (id) => set((state) => ({
        entries: state.entries.filter((item) => item.id !== id),
        activeEntryId: state.activeEntryId === id ? null : state.activeEntryId,
      })),
      setJournalState: (patch) => set(patch),
      setError: (error) => set({ error }),
    }),
    {
      name: "quant360-studio-journal",
      version: 1,
      storage: createJSONStorage(() => localStorage),
      partialize: ({ filterTag, query }) => ({ filterTag, query }),
    },
  ),
);
