import { act, renderHook } from '@testing-library/react';
import { useStudioAnalysis } from '../useStudioAnalysis';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { createStudioJob, waitForStudioJobEvents } from '@/lib/studioApi';

jest.mock('@/lib/studioApi', () => ({
    createStudioJob: jest.fn(),
    waitForStudioJobEvents: jest.fn(),
    cancelStudioJob: jest.fn().mockResolvedValue({ status: 'success' }),
}));

const monteCarloResult = {
    status: 'success',
    summary: {
        simulations: 100, timeHorizon: 252, meanFinalValue: 1, medianFinalValue: 1,
        stdFinalValue: 0.1, riskOfRuin: 0, ruinThreshold: 0.5, meanMaxDrawdown: -5,
        worstDrawdown: -10, bestFinal: 1.5, worstFinal: 0.7, probPositive: 55,
        probDouble: 0, var95: 0.8, p10: 0.9, p90: 1.2,
    },
    samplePaths: [[1, 1.01]],
    histogram: { counts: [1], edges: [0.9, 1.1] },
    percentiles: { p5: 0.8 },
    dailyReturns: { mean: 0.001, std: 0.01, sharpeImplied: 1.5 },
    assumptions: { method: 'moving_block_bootstrap', seed: 42, blockSize: 5, inputObservations: 120, returnConvention: 'simple' },
};

const walkForwardResult = {
    status: 'success',
    summary: { avgIsSharpe: 1, avgOosSharpe: 0.5, consistency: 60, alphaDecay: 50, oosWindow: 20, totalFolds: 1 },
    folds: [{ fold: 1, isSharpe: 1, oosSharpe: 0.5, isReturn: 2, oosReturn: 1, degradation: 50, trainStart: 0, trainEnd: 99, testStart: 102, testEnd: 122, purgeDays: 2, embargoDays: 1 }],
    alphaShield: { status: 'WEAK', confidence: 60 },
    verdict: {
        status: 'PASSED',
        methodology: 'deterministic_threshold_rules_not_statistical_confidence',
        thresholds: { minOosSharpe: 0.5, minConsistencyPct: 50 },
        tests: [
            { id: 'minimum_oos_sharpe', label: 'Average out-of-sample Sharpe', value: 0.5, operator: '>=', threshold: 0.5, status: 'pass' },
            { id: 'minimum_profitable_fold_consistency', label: 'Profitable out-of-sample folds', value: 60, operator: '>=', threshold: 50, unit: 'percent', status: 'pass' },
        ],
    },
};

describe('useStudioAnalysis durable jobs', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        useStudioResultStore.getState().resetResults();
        useStudioResultStore.getState().setData((current) => ({
            ...current,
            equityCurve: Array.from({ length: 130 }, (_, index) => 1 + index * 0.001),
        }));
    });

    it('runs Monte Carlo through the durable job API with explicit assumptions', async () => {
        jest.mocked(createStudioJob).mockResolvedValue({ job_id: 'mc-job', status: 'queued', estimate: { work_units: 25200, budget_utilization_pct: 0.1, size: 'small', basis: 'simulation paths × horizon bars' } });
        jest.mocked(waitForStudioJobEvents).mockResolvedValue(monteCarloResult);
        const { result } = renderHook(() => useStudioAnalysis());

        await act(async () => result.current.runMonteCarlo(100, 'moving_block_bootstrap', 5));

        expect(createStudioJob).toHaveBeenCalledWith('monte-carlo', expect.objectContaining({
            simulations: 100, method: 'moving_block_bootstrap', block_size: 5, seed: 42,
        }), expect.objectContaining({ signal: expect.any(AbortSignal) }));
        expect(waitForStudioJobEvents).toHaveBeenCalledWith('mc-job', expect.objectContaining({ signal: expect.any(AbortSignal), onUpdate: expect.any(Function) }));
        expect(useStudioResultStore.getState().data.mcData).toEqual(monteCarloResult);
        expect(useStudioResultStore.getState().mcJob?.job_id).toBe('mc-job');
    });

    it('runs walk-forward through the durable job API with leakage controls', async () => {
        jest.mocked(createStudioJob).mockResolvedValue({ job_id: 'wf-job', status: 'queued', estimate: { work_units: 650, budget_utilization_pct: 0.03, size: 'small', basis: 'return observations × folds' } });
        jest.mocked(waitForStudioJobEvents).mockResolvedValue(walkForwardResult);
        const { result } = renderHook(() => useStudioAnalysis());

        await act(async () => result.current.runWalkForward(5, 2, 1));

        expect(createStudioJob).toHaveBeenCalledWith('walk-forward', expect.objectContaining({
            n_folds: 5, oos_days: 20, purge_days: 2, embargo_days: 1,
            min_oos_sharpe: 0.5, min_consistency_pct: 50,
        }), expect.objectContaining({ signal: expect.any(AbortSignal) }));
        expect(waitForStudioJobEvents).toHaveBeenCalledWith('wf-job', expect.objectContaining({ signal: expect.any(AbortSignal), onUpdate: expect.any(Function) }));
        expect(useStudioResultStore.getState().data.wfData).toEqual(walkForwardResult);
        expect(useStudioResultStore.getState().wfJob?.job_id).toBe('wf-job');
    });
});
