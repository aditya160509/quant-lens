import { vi, describe, it, expect, beforeEach } from "vitest";
import { useStudioSelectionStore } from '../selectionStore';

describe('useStudioSelectionStore', () => {
    beforeEach(() => {
        vi.mocked(window.localStorage.getItem).mockReset();
        vi.mocked(window.localStorage.setItem).mockReset();
        vi.mocked(window.localStorage.removeItem).mockReset();
        useStudioSelectionStore.getState().resetSelections();
    });

    it('persists draft selections through functional setters', () => {
        const state = useStudioSelectionStore.getState();
        state.setSelectedPatterns((current: string[]) => [...current, 'hammer']);
        state.setCustomOverlays((current: unknown[]) => [...current, { id: 1 }]);

        expect(useStudioSelectionStore.getState().selectedPatterns).toEqual(['hammer']);
        expect(window.localStorage.setItem).toHaveBeenCalledWith(
            'sovereign_studio_selected_patterns',
            '["hammer"]',
        );
        expect(useStudioSelectionStore.getState().customOverlays).toEqual([{ id: 1 }]);
    });

    it('ignores malformed persisted selection data during hydration', () => {
        vi.mocked(window.localStorage.getItem).mockImplementation((key) => {
            if (key === 'sovereign_studio_drawings') return '{bad json';
            if (key === 'sovereign_studio_selected_patterns') return '["doji"]';
            return '{}';
        });

        useStudioSelectionStore.getState().hydrateSelections();

        expect(useStudioSelectionStore.getState()).toMatchObject({
            drawings: [],
            selectedPatterns: ['doji'],
            customOverlays: [],
        });
    });

    it('clears drawing drafts and their storage key', () => {
        useStudioSelectionStore.getState().setDrawings([{ id: 'line-1' }]);
        useStudioSelectionStore.getState().clearDrawings();

        expect(useStudioSelectionStore.getState().drawings).toEqual([]);
        expect(window.localStorage.removeItem).toHaveBeenCalledWith('sovereign_studio_drawings');
    });
});

