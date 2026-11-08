import { describe, it, expect, beforeEach } from "vitest";
import { defaultStudioPreferences, useStudioPreferenceStore } from '../preferenceStore';

describe('useStudioPreferenceStore', () => {
    beforeEach(() => {
        useStudioPreferenceStore.getState().resetPreferences();
    });

    it('updates individual preferences without replacing the slice', () => {
        const state = useStudioPreferenceStore.getState();
        state.setPlaySpeed(75);
        state.setKernelCollapsed(true);
        state.setLayoutPreset('1x2');

        expect(useStudioPreferenceStore.getState()).toMatchObject({
            playSpeed: 75,
            kernelCollapsed: true,
            layoutPreset: '1x2',
        });
    });

    it('supports functional sync-setting updates used by the facade', () => {
        useStudioPreferenceStore.getState().setSyncSettings((current: typeof defaultStudioPreferences.syncSettings) => ({
            ...current,
            time: false,
        }));

        expect(useStudioPreferenceStore.getState().syncSettings).toEqual({
            ...defaultStudioPreferences.syncSettings,
            time: false,
        });
    });
});

