"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Item } from "./layouts";

/** Per-feature card customisation: which outputs show, how wide, and in what order. Survives new runs. */
export type CardPref = { hidden?: boolean; span?: number; order?: number };
type Store = {
  prefs: Record<string, Record<string, CardPref>>;
  set: (feature: string, card: string, p: Partial<CardPref>) => void;
  reset: (feature: string) => void;
};

export const cardId = (i: Item) => i.keys.join("+") + (i.view ? `:${i.view}` : "");

export const useCardPrefs = create<Store>()(persist((set) => ({
  prefs: {},
  set: (feature, card, p) => set((s) => ({ prefs: { ...s.prefs, [feature]: { ...s.prefs[feature], [card]: { ...s.prefs[feature]?.[card], ...p } } } })),
  reset: (feature) => set((s) => {
    const { [feature]: _, ...rest } = s.prefs;
    void _;
    return { prefs: rest };
  }),
}), { name: "research-card-prefs", storage: createJSONStorage(() => localStorage) }));

const NONE: Record<string, CardPref> = {};
export const useFeaturePrefs = (feature: string) => useCardPrefs((s) => s.prefs[feature] ?? NONE);

/** Items in the reader's order with their chosen widths; hidden ones removed unless asked for. */
export function arrange(items: Item[], prefs: Record<string, CardPref>, keepHidden = false): Item[] {
  return items
    .map((it, i) => ({ it, i, p: prefs[cardId(it)] ?? {} }))
    .filter(({ p }) => keepHidden || !p.hidden)
    .sort((a, b) => (a.p.order ?? a.i) - (b.p.order ?? b.i))
    .map(({ it, p }) => (p.span ? { ...it, span: p.span } : it));
}
