import { useStudioResultStore } from '../resultStore';

describe('useStudioResultStore', () => {
    beforeEach(() => {
        useStudioResultStore.getState().resetResults();
    });

    it('updates result data through functional setters', () => {
        const state = useStudioResultStore.getState();
        state.setData((current: { candles: unknown[] }) => ({
            ...current,
            candles: [{ close: 100 }],
        }));
        state.setExecutionError('runner unavailable');

        expect(useStudioResultStore.getState().data.candles).toEqual([{ close: 100 }]);
        expect(useStudioResultStore.getState().executionError).toBe('runner unavailable');
    });

    it('resets server-derived data without retaining array references', () => {
        useStudioResultStore.getState().setGridData([{ candles: [1] }]);
        useStudioResultStore.getState().resetResults();

        expect(useStudioResultStore.getState()).toMatchObject({
            gridData: [],
            isExecuting: false,
            executionError: null,
            data: { candles: [], trades: [], equityCurve: [] },
        });
    });
});

