import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const DEFAULT_LIST = "Watchlist";

type Store = {
  lists: Record<string, string[]>;
  toggle: (ticker: string, list?: string) => void;
  remove: (list: string) => void;
};

/** Named ticker lists, kept on this device. They feed the universe, the "only these" filter and alerts. */
export const useWatchlists = create<Store>()(persist(
  (set) => ({
    lists: {},
    toggle: (ticker, list = DEFAULT_LIST) => set((s) => {
      const cur = s.lists[list] ?? [];
      return { lists: { ...s.lists, [list]: cur.includes(ticker) ? cur.filter((t) => t !== ticker) : [...cur, ticker] } };
    }),
    remove: (list) => set((s) => {
      const { [list]: _, ...rest } = s.lists;
      void _;
      return { lists: rest };
    }),
  }),
  { name: "screener-watchlists", storage: createJSONStorage(() => localStorage), version: 1 },
));
