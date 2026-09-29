"use client";

import { create } from "zustand";

export const defaultStudioPreferences = Object.freeze({
    playSpeed: 20,
    kernelCollapsed: false,
    layoutPreset: "1x1",
    syncSettings: {
        symbol: true,
        interval: true,
        crosshair: true,
        time: true,
        dateRange: true,
    },
});

const resolveUpdate = (nextValue, currentValue) => (
    typeof nextValue === "function" ? nextValue(currentValue) : nextValue
);

export const useStudioPreferenceStore = create((set) => ({
    ...defaultStudioPreferences,
    setPlaySpeed: (nextValue) => set((state) => ({
        playSpeed: resolveUpdate(nextValue, state.playSpeed),
    })),
    setKernelCollapsed: (nextValue) => set((state) => ({
        kernelCollapsed: resolveUpdate(nextValue, state.kernelCollapsed),
    })),
    setLayoutPreset: (nextValue) => set((state) => ({
        layoutPreset: resolveUpdate(nextValue, state.layoutPreset),
    })),
    setSyncSettings: (nextValue) => set((state) => ({
        syncSettings: resolveUpdate(nextValue, state.syncSettings),
    })),
    resetPreferences: () => set({ ...defaultStudioPreferences }),
}));

