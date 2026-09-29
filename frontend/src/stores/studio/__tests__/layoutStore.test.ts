import { useStudioLayoutStore } from '../layoutStore';

describe('useStudioLayoutStore', () => {
    beforeEach(() => {
        useStudioLayoutStore.getState().resetLayout();
    });

    it('applies a single-panel layout immediately', () => {
        useStudioLayoutStore.getState().startLayoutInitialization('1x1', 'QQQ');

        expect(useStudioLayoutStore.getState().gridConfig).toEqual({
            layoutId: '1x1',
            tickers: ['QQQ'],
        });
    });

    it('collects every ticker before activating a multi-panel layout', () => {
        const state = useStudioLayoutStore.getState();
        state.startLayoutInitialization('2x2', 'SPY');
        state.addTickerToLayout('QQQ');
        state.addTickerToLayout('IWM');

        expect(useStudioLayoutStore.getState().layoutInitState).toMatchObject({
            isActive: true,
            step: 3,
            pendingTickers: ['SPY', 'QQQ', 'IWM'],
        });

        state.addTickerToLayout('DIA');
        expect(useStudioLayoutStore.getState()).toMatchObject({
            gridConfig: { layoutId: '2x2', tickers: ['SPY', 'QQQ', 'IWM', 'DIA'] },
            layoutInitState: { isActive: false },
        });
    });
});

