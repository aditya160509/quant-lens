"use client";

import { create } from "zustand";
import { STRATEGIES } from "@/components/studio/constants";

const CODE_A_STORAGE_KEY = "sovereign_studio_code_a";
const CODE_B_STORAGE_KEY = "sovereign_studio_code_b";
const defaultCode = STRATEGIES.momentum?.code || "";

export const defaultEditorState = Object.freeze({
    selectedStrategy: "momentum",
    codeA: defaultCode,
    codeB: defaultCode,
    vsModeActive: false,
    // Most recent Monaco selection text (P5-W2 selection run). Empty when
    // nothing is selected; never treated as authoritative file content.
    selectedCode: "",
});

const resolveUpdate = (nextValue, currentValue) => (
    typeof nextValue === "function" ? nextValue(currentValue) : nextValue
);

const persistDraft = (key, value) => {
    if (typeof window === "undefined") return;
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
};

export const useStudioEditorStore = create((set) => ({
    ...defaultEditorState,
    setSelectedStrategy: (nextValue) => set((state) => ({
        selectedStrategy: resolveUpdate(nextValue, state.selectedStrategy),
    })),
    setCodeA: (nextValue) => set((state) => {
        const codeA = resolveUpdate(nextValue, state.codeA);
        persistDraft(CODE_A_STORAGE_KEY, codeA);
        return { codeA };
    }),
    setCodeB: (nextValue) => set((state) => {
        const codeB = resolveUpdate(nextValue, state.codeB);
        persistDraft(CODE_B_STORAGE_KEY, codeB);
        return { codeB };
    }),
    setVsModeActive: (nextValue) => set((state) => ({
        vsModeActive: resolveUpdate(nextValue, state.vsModeActive),
    })),
    setSelectedCode: (nextValue) => set((state) => ({
        selectedCode: resolveUpdate(nextValue, state.selectedCode),
    })),
    applyStrategy: (strategyId) => set(() => {
        const strategy = STRATEGIES[strategyId];
        if (!strategy) return { selectedStrategy: strategyId };

        persistDraft(CODE_A_STORAGE_KEY, strategy.code);
        persistDraft(CODE_B_STORAGE_KEY, strategy.code);
        return {
            selectedStrategy: strategyId,
            codeA: strategy.code,
            codeB: strategy.code,
        };
    }),
    hydrateDrafts: () => {
        if (typeof window === "undefined") return;
        set({
            codeA: window.localStorage.getItem(CODE_A_STORAGE_KEY) || defaultCode,
            codeB: window.localStorage.getItem(CODE_B_STORAGE_KEY) || defaultCode,
        });
    },
    resetEditor: () => set({ ...defaultEditorState }),
}));

