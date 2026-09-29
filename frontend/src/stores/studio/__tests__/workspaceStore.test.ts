import { useStudioWorkspaceStore } from '../workspaceStore';

describe('useStudioWorkspaceStore', () => {
    beforeEach(() => {
        useStudioWorkspaceStore.getState().resetWorkspaceInputs();
    });

    it('normalizes the retired stress mode into Validate', () => {
        useStudioWorkspaceStore.getState().setActiveTab('stress');
        expect(useStudioWorkspaceStore.getState().activeTab).toBe('validate');
    });

    it('normalizes market symbols and cost inputs', () => {
        const state = useStudioWorkspaceStore.getState();
        state.setTicker(' brk.b ');
        state.setBenchmark(' qqq ');
        state.setSlippageBps('2.5');

        expect(useStudioWorkspaceStore.getState()).toMatchObject({
            ticker: 'BRK.B',
            benchmark: 'QQQ',
            slippageBps: 2.5,
        });
    });

    it('preserves functional setter compatibility', () => {
        const state = useStudioWorkspaceStore.getState();
        state.setActiveTab(() => 'validate');
        state.setShowIndicatorSelect((current: boolean) => !current);

        expect(useStudioWorkspaceStore.getState()).toMatchObject({
            activeTab: 'validate',
            showIndicatorSelect: true,
        });
    });
});
