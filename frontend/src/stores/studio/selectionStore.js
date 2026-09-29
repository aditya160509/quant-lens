"use client";

import { create } from "zustand";

const DRAWINGS_KEY = "sovereign_studio_drawings";
const PATTERNS_KEY = "sovereign_studio_selected_patterns";
const OVERLAYS_KEY = "sovereign_studio_custom_overlays";

export const defaultStudioSelection = Object.freeze({
    hoverSnapshot: null,
    activeDrawingTool: null,
    drawings: [],
    selectedPatterns: [],
    customOverlays: [],
    activeIndicators: [],
});

const resolveUpdate = (nextValue, currentValue) => (
    typeof nextValue === "function" ? nextValue(currentValue) : nextValue
);

const persistJson = (key, value) => {
    if (typeof window !== "undefined") {
        window.localStorage.setItem(key, JSON.stringify(value));
    }
};

const readJsonArray = (key) => {
    if (typeof window === "undefined") return [];
    try {
        const value = JSON.parse(window.localStorage.getItem(key) || "[]");
        return Array.isArray(value) ? value : [];
    } catch {
        return [];
    }
};

const persistentSetter = (set, field, storageKey) => (nextValue) => set((state) => {
    const value = resolveUpdate(nextValue, state[field]);
    persistJson(storageKey, value);
    return { [field]: value };
});

export const useStudioSelectionStore = create((set) => ({
    ...defaultStudioSelection,
    setHoverSnapshot: (nextValue) => set((state) => ({
        hoverSnapshot: resolveUpdate(nextValue, state.hoverSnapshot),
    })),
    setActiveDrawingTool: (nextValue) => set((state) => ({
        activeDrawingTool: resolveUpdate(nextValue, state.activeDrawingTool),
    })),
    setDrawings: persistentSetter(set, "drawings", DRAWINGS_KEY),
    setSelectedPatterns: persistentSetter(set, "selectedPatterns", PATTERNS_KEY),
    setCustomOverlays: persistentSetter(set, "customOverlays", OVERLAYS_KEY),
    setActiveIndicators: (nextValue) => set((state) => ({
        activeIndicators: resolveUpdate(nextValue, state.activeIndicators),
    })),
    hydrateSelections: () => set({
        drawings: readJsonArray(DRAWINGS_KEY),
        selectedPatterns: readJsonArray(PATTERNS_KEY),
        customOverlays: readJsonArray(OVERLAYS_KEY),
    }),
    clearDrawings: () => {
        if (typeof window !== "undefined") window.localStorage.removeItem(DRAWINGS_KEY);
        set({ drawings: [] });
    },
    resetSelections: () => set({ ...defaultStudioSelection }),
}));

