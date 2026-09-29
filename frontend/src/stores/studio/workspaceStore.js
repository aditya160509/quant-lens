"use client";

import { create } from "zustand";

export const defaultStudioWorkspace = Object.freeze({
    activeTab: "develop",
    ticker: "SPY",
    benchmark: "",
    slippageBps: 1,
    commissionPct: 0.01,
    showIndicatorSelect: false,
});

const resolveUpdate = (nextValue, currentValue) => (
    typeof nextValue === "function" ? nextValue(currentValue) : nextValue
);

const setter = (set, field, normalize = (value) => value) => (nextValue) => set((state) => ({
    [field]: normalize(resolveUpdate(nextValue, state[field])),
}));

export const useStudioWorkspaceStore = create((set) => ({
    ...defaultStudioWorkspace,
    setActiveTab: setter(set, "activeTab", (value) => value === "stress" ? "validate" : value),
    setTicker: setter(set, "ticker", (value) => String(value || "").trim().toUpperCase()),
    setBenchmark: setter(set, "benchmark", (value) => String(value || "").trim().toUpperCase()),
    setSlippageBps: setter(set, "slippageBps", Number),
    setCommissionPct: setter(set, "commissionPct", Number),
    setShowIndicatorSelect: setter(set, "showIndicatorSelect", Boolean),
    resetWorkspaceInputs: () => set({ ...defaultStudioWorkspace }),
}));
