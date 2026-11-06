import {
    isStudioDataResponse,
    isStudioExecutionResponse,
    isStudioMonteCarloResponse,
    isStudioWalkForwardResponse,
    isStudioTickersResponse,
    isStudioHealthResponse,
    isStudioErrorEnvelope,
} from '../studioValidators';

const candle = { time: 1, open: 100, high: 102, low: 99, close: 101, volume: 1000 };

describe('Studio response validators', () => {
    it('accepts observed data and rejects non-finite candles', () => {
        expect(isStudioDataResponse({ status: 'success', candles: [candle], metadata: {} })).toBe(true);
        expect(isStudioDataResponse({
            status: 'success',
            candles: [{ ...candle, close: Number.NaN }],
            metadata: {},
        })).toBe(false);
    });

    it('requires the execution result collections', () => {
        expect(isStudioExecutionResponse({
            status: 'success',
            candles: [candle],
            metadata: {},
            signals: [],
            trades: [],
            equity_curve: [1, 1.01],
            metrics: {},
        })).toBe(true);
        expect(isStudioExecutionResponse({ status: 'success', candles: [candle], metadata: {} })).toBe(false);
    });

    it('rejects malformed simulation and validation payloads', () => {
        expect(isStudioMonteCarloResponse({
            status: 'success',
            summary: {
                simulations: 100,
                timeHorizon: 20,
                meanFinalValue: 1.1,
                medianFinalValue: 1.05,
                stdFinalValue: 0.2,
                riskOfRuin: 1,
                ruinThreshold: 0.5,
                meanMaxDrawdown: -10,
                worstDrawdown: -20,
                bestFinal: 2,
                worstFinal: 0.4,
                probPositive: 60,
                probDouble: 2,
                var95: 0.7,
                p10: 0.8,
                p90: 1.4,
            },
            samplePaths: [[1, 1.1]],
            histogram: { counts: [1], edges: [1, 2] },
            percentiles: { p5: 0.7, p95: 1.5 },
            dailyReturns: { mean: 0.001, std: 0.01, sharpeImplied: 1.5 },
            assumptions: {
                method: 'moving_block_bootstrap',
                seed: 42,
                blockSize: 5,
                inputObservations: 100,
                returnConvention: 'simple',
            },
        })).toBe(true);
        expect(isStudioMonteCarloResponse({ status: 'success', samplePaths: 'bad' })).toBe(false);
        expect(isStudioWalkForwardResponse({
            status: 'success',
            summary: {
                avgIsSharpe: null,
                avgOosSharpe: null,
                consistency: null,
                alphaDecay: null,
                oosWindow: 20,
                totalFolds: 1,
            },
            folds: [{
                fold: 1,
                isSharpe: null,
                oosSharpe: null,
                isReturn: 0,
                oosReturn: 0,
                degradation: null,
                trainStart: 0,
                trainEnd: 79,
                testStart: 82,
                testEnd: 102,
                purgeDays: 2,
                embargoDays: 1,
            }],
            alphaShield: { status: 'UNAVAILABLE', confidence: null },
            verdict: {
                status: 'UNAVAILABLE',
                methodology: 'deterministic_threshold_rules_not_statistical_confidence',
                thresholds: { minOosSharpe: 0.5, minConsistencyPct: 50 },
                tests: [
                    { id: 'minimum_oos_sharpe', label: 'Average out-of-sample Sharpe', value: null, operator: '>=', threshold: 0.5, status: 'unavailable' },
                    { id: 'minimum_profitable_fold_consistency', label: 'Profitable out-of-sample folds', value: null, operator: '>=', threshold: 50, unit: 'percent', status: 'unavailable' },
                ],
            },
        })).toBe(true);
        expect(isStudioWalkForwardResponse({ status: 'success', folds: null })).toBe(false);
        expect(isStudioWalkForwardResponse({
            status: 'success',
            summary: {
                avgIsSharpe: Number.NaN,
                avgOosSharpe: 1,
                consistency: 50,
                alphaDecay: 10,
                oosWindow: 20,
                totalFolds: 1,
            },
            folds: [],
            alphaShield: { status: 'WEAK', confidence: 50 },
        })).toBe(false);
        expect(isStudioWalkForwardResponse({
            status: 'success',
            summary: { avgIsSharpe: 1, avgOosSharpe: 0.5, consistency: 50, alphaDecay: 50, oosWindow: 20, totalFolds: 1 },
            folds: [{ fold: 1, isSharpe: 1, oosSharpe: 0.5, isReturn: 2, oosReturn: 1, degradation: 50, trainStart: 0, trainEnd: 90, testStart: 80, testEnd: 100, purgeDays: 0, embargoDays: 0 }],
            alphaShield: { status: 'WEAK', confidence: 50 },
            verdict: {
                status: 'FAILED',
                methodology: 'deterministic_threshold_rules_not_statistical_confidence',
                thresholds: { minOosSharpe: 0.5, minConsistencyPct: 50 },
                tests: [{ id: 'minimum_oos_sharpe', label: 'Average out-of-sample Sharpe', value: 0.5, operator: '>=', threshold: 0.5, status: 'pass' }],
            },
        })).toBe(false);
    });

    it('validates tickers, health, and error envelopes', () => {
        expect(isStudioTickersResponse({ status: 'success', contract_version: '1.0', tickers: ['SPY'], total: 1, universes: ['all'] })).toBe(true);
        expect(isStudioTickersResponse({ status: 'success', tickers: [], total: 0, universes: [] })).toBe(true);
        expect(isStudioTickersResponse({ status: 'success', tickers: 'bad', total: 0, universes: [] })).toBe(false);
        expect(isStudioTickersResponse({ status: 'success', contract_version: '9.9', tickers: ['SPY'], total: 1, universes: ['all'] })).toBe(false);
        expect(isStudioHealthResponse({ status: 'ok', contract_version: '1.0', check: 'liveness', execution: { mode: 'isolated_one_shot' } })).toBe(true);
        expect(isStudioHealthResponse({ status: 'ok', check: 'liveness', execution: { mode: 'isolated_one_shot' } })).toBe(true);
        expect(isStudioHealthResponse({ status: 'ok', check: 'liveness', execution: {} })).toBe(false);
        expect(isStudioErrorEnvelope({ status: 'error', detail: { code: 'DATA_UNAVAILABLE', message: 'missing' } })).toBe(true);
        expect(isStudioErrorEnvelope({ status: 'error', detail: { code: 'X' } })).toBe(false);
    });

    it('rejects unavailable and cancelled partial shapes', () => {
        expect(isStudioDataResponse({ status: 'error', detail: { code: 'DATA_UNAVAILABLE', message: 'no data' } })).toBe(false);
        expect(isStudioExecutionResponse({ status: 'success', candles: [candle], metadata: {}, signals: [], trades: [], equity_curve: [Number.POSITIVE_INFINITY], metrics: {} })).toBe(false);
        expect(isStudioMonteCarloResponse({ status: 'success', summary: { simulations: Number.NaN, timeHorizon: 20, meanFinalValue: 1, medianFinalValue: 1, stdFinalValue: 1, riskOfRuin: 1, ruinThreshold: 1, meanMaxDrawdown: 1, worstDrawdown: 1, bestFinal: 1, worstFinal: 1, probPositive: 1, probDouble: 1, var95: 1, p10: 1, p90: 1 }, samplePaths: [[1]], histogram: { counts: [1], edges: [1, 2] }, percentiles: { p5: 1 }, dailyReturns: { mean: 1, std: 1, sharpeImplied: null }, assumptions: { method: 'gaussian', seed: 42, blockSize: null, inputObservations: 20, returnConvention: 'simple' } })).toBe(false);
    });
});
