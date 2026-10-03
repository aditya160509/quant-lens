"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { FormState } from "./StudyForm";

type StudyStore = {
  forms: Record<string, FormState>;
  setForm: (featureId: string, updater: (cur: FormState) => FormState, defaults: FormState) => void;
  resetForm: (featureId: string) => void;
};

/** Study inputs per feature, kept while the user moves between features. */
export const useStudies = create<StudyStore>()((set) => ({
  forms: {},
  setForm: (featureId, updater, defaults) => set((s) => ({ forms: { ...s.forms, [featureId]: updater(s.forms[featureId] ?? defaults) } })),
  resetForm: (featureId) => set((s) => {
    const { [featureId]: _, ...rest } = s.forms;
    void _;
    return { forms: rest };
  }),
}));

type PresetStore = {
  presets: Record<string, { name: string; values: FormState }[]>;
  save: (featureId: string, name: string, values: FormState) => void;
  remove: (featureId: string, name: string) => void;
};

/** Named study settings per feature, persisted per device. */
export const usePresets = create<PresetStore>()(
  persist(
    (set) => ({
      presets: {},
      save: (featureId, name, values) => set((s) => ({ presets: { ...s.presets, [featureId]: [{ name, values }, ...(s.presets[featureId] ?? []).filter((p) => p.name !== name)] } })),
      remove: (featureId, name) => set((s) => ({ presets: { ...s.presets, [featureId]: (s.presets[featureId] ?? []).filter((p) => p.name !== name) } })),
    }),
    { name: "research-presets", storage: createJSONStorage(() => localStorage), version: 1 },
  ),
);

/** Parameter sweeps: per feature, per numeric field, a comma-separated list of values (empty = off). */
type SweepStore = { sweeps: Record<string, Record<string, string>>; setSweep: (featureId: string, key: string, list: string | null) => void };
export const useSweeps = create<SweepStore>()((set) => ({
  sweeps: {},
  setSweep: (featureId, key, list) => set((s) => {
    const { [key]: _, ...rest } = s.sweeps[featureId] ?? {};
    void _;
    return { sweeps: { ...s.sweeps, [featureId]: list === null ? rest : { ...rest, [key]: list } } };
  }),
}));

export const sweepValues = (list: string) => list.split(/[,\s]+/).map(Number).filter((n) => Number.isFinite(n));
