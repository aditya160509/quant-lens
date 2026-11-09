"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import UFuzzy from "@leeoniya/ufuzzy";
import { useQuickLook } from "@/kit/QuickLook";
import { useStudies } from "@/modules/research/store";

type Recent = { tickers: string[]; push: (t: string) => void };

/** Names opened from the overlay, a table or a chart, newest first; kept on this device. */
export const useRecent = create<Recent>()(persist(
  (set) => ({ tickers: [], push: (t) => set((s) => ({ tickers: [t, ...s.tickers.filter((x) => x !== t)].slice(0, 8) })) }),
  { name: "screener-recent-names", storage: createJSONStorage(() => localStorage), version: 1 },
));

if (typeof window !== "undefined") useQuickLook.subscribe((s, prev) => { if (s.ticker && s.ticker !== prev.ticker) useRecent.getState().push(s.ticker); });

const uf = new UFuzzy({ intraMode: 1, intraIns: 1 });

/** Fuzzy filter and rank with uFuzzy; an empty needle keeps every item in order. */
export function fuzzy<T>(items: T[], text: (t: T) => string, needle: string): T[] {
  const q = needle.trim();
  if (!q) return items;
  const hay = items.map(text);
  const [idxs, info, order] = uf.search(hay, q, 1);
  if (!idxs || !info || !order) return idxs ? idxs.map((i) => items[i]) : [];
  return order.map((o) => items[info.idx[o]]);
}

const UNIVERSE_KEYS = new Set(["", "master", "us_equities", "all"]);

/** Add a name to the Screener's universe, replacing the default "whole market". */
export function addToScreen(ticker: string) {
  useStudies.setState((s) => {
    const form = s.forms.sc01 ?? {};
    const cur = Array.isArray(form.universe) ? form.universe.join(",") : String(form.universe ?? "");
    const tokens = cur.split(",").map((x) => x.trim()).filter((x) => x && !UNIVERSE_KEYS.has(x.toLowerCase()));
    return { forms: { ...s.forms, sc01: { ...form, universe: [...new Set([...tokens, ticker])].join(",") } } };
  });
}

/** Restrict the Screener to one sector, the existing sector filter. */
export function screenSector(sector: string) {
  useStudies.setState((s) => ({ forms: { ...s.forms, sc01: { ...(s.forms.sc01 ?? {}), sector } } }));
}
