"use client";

import { create } from "zustand";

// Linked-selection pub/sub for the output composer. Selecting a metric or
// artifact in one block highlights every block referencing the same identity.
// No chart library is involved; subscribers re-render through zustand.
export const emptyComposerSelection = () => ({
    selectedArtifact: "",
    selectedMetric: "",
});

export const useComposerSelectionStore = create((set) => ({
    ...emptyComposerSelection(),
    setSelectedArtifact: (selectedArtifact) => set({ selectedArtifact: selectedArtifact || "" }),
    setSelectedMetric: (selectedMetric) => set({ selectedMetric: selectedMetric || "" }),
    resetComposerSelection: () => set(emptyComposerSelection()),
}));
