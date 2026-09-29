"use client";

import { create } from "zustand";

export const defaultStudioLayout = Object.freeze({
    showLayoutManager: false,
    gridConfig: { layoutId: "1x1", tickers: ["SPY"] },
    layoutInitState: {
        isActive: false,
        step: 0,
        total: 1,
        pendingTickers: [],
        requestedLayoutId: "1x1",
    },
});

const resolveUpdate = (nextValue, currentValue) => (
    typeof nextValue === "function" ? nextValue(currentValue) : nextValue
);

const layoutSize = (layoutId) => {
    const [rows, columns] = String(layoutId).split("x").map(Number);
    return Number.isFinite(rows) && Number.isFinite(columns) ? rows * columns : 1;
};

export const useStudioLayoutStore = create((set) => ({
    ...defaultStudioLayout,
    setShowLayoutManager: (nextValue) => set((state) => ({
        showLayoutManager: resolveUpdate(nextValue, state.showLayoutManager),
    })),
    setGridConfig: (nextValue) => set((state) => ({
        gridConfig: resolveUpdate(nextValue, state.gridConfig),
    })),
    startLayoutInitialization: (layoutId, ticker = "SPY") => {
        const total = layoutSize(layoutId);
        const primaryTicker = ticker || "SPY";
        if (total === 1) {
            set({ gridConfig: { layoutId: "1x1", tickers: [primaryTicker] } });
            return;
        }
        set({
            layoutInitState: {
                isActive: true,
                step: 1,
                total,
                pendingTickers: [primaryTicker],
                requestedLayoutId: layoutId,
            },
        });
    },
    addTickerToLayout: (ticker) => set((state) => {
        const nextTickers = [...state.layoutInitState.pendingTickers, ticker];
        if (nextTickers.length >= state.layoutInitState.total) {
            return {
                gridConfig: {
                    layoutId: state.layoutInitState.requestedLayoutId,
                    tickers: nextTickers,
                },
                layoutInitState: { ...state.layoutInitState, isActive: false },
            };
        }
        return {
            layoutInitState: {
                ...state.layoutInitState,
                step: state.layoutInitState.step + 1,
                pendingTickers: nextTickers,
            },
        };
    }),
    resetLayoutInitialization: () => set({
        layoutInitState: { ...defaultStudioLayout.layoutInitState },
    }),
    resetLayout: () => set({
        ...defaultStudioLayout,
        gridConfig: { ...defaultStudioLayout.gridConfig, tickers: ["SPY"] },
        layoutInitState: { ...defaultStudioLayout.layoutInitState },
    }),
}));

