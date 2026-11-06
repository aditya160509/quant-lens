import { buildStudioResultsCsv, buildStudioResultsHtml, buildStudioResultsJson, canonicalMetric, deriveOrdersFromSignals, formatCanonicalMetric, normalizeStudioExecutionResult, observedReturnDiagnostics, replayFillLinkage, studioComparisonCompatibility } from '../studioResults';

describe('canonical Studio results', () => {
    const metrics = {
        canonical: {
            total_return: { value: 0.125, unit: 'decimal', status: 'observed', sample_size: 20, methodology: 'ending / starting - 1' },
            beta: { value: null, unit: 'ratio', status: 'unavailable', sample_size: 0, methodology: 'benchmark missing' },
        },
    };

    it('refuses comparisons with incompatible conventions or observation calendars', () => {
        const artifact = (currency = 'USD', times = [1, 2]) => ({ candles: times.map((time) => ({ time })), metadata: { data_quality: { currency, calendar: 'XNYS', source: 'market_universe_daily' }, provenance: { dataset_id: 'market_universe_daily', engine_version: 'studio/1', parameters: { return_convention: 'simple_returns_compounded_to_net_equity' } } } });
        expect(studioComparisonCompatibility(artifact(), artifact())).toEqual({ compatible: true, reasons: [] });
        expect(studioComparisonCompatibility(artifact('USD'), artifact('EUR', [1, 3]))).toMatchObject({ compatible: false, reasons: expect.arrayContaining([expect.stringContaining('currency'), expect.stringContaining('timestamps')]) });
    });

    it('derives deterministic empirical tails and rolling volatility from net equity', () => {
        const diagnostics = observedReturnDiagnostics([1, 1.01, 0.9999, 1.019898, 1.00969902], 2);
        expect(diagnostics).toMatchObject({ observations: 4, rollingWindow: 2, histogram: expect.any(Array) });
        expect(diagnostics?.histogram.reduce((sum, count) => sum + count, 0)).toBe(4);
        expect(diagnostics?.rollingVolatility).toHaveLength(3);
        expect(diagnostics?.worst).toBeCloseTo(-0.01);
        expect(diagnostics?.best).toBeCloseTo(0.02);
    });

    it('formats observed values and never turns unavailable into zero', () => {
        expect(formatCanonicalMetric(canonicalMetric(metrics, 'total_return'), { signed: true })).toBe('+12.50%');
        expect(formatCanonicalMetric(canonicalMetric(metrics, 'beta'))).toBe('Unavailable');
        expect(formatCanonicalMetric(canonicalMetric(metrics, 'missing'))).toBe('Unavailable');
    });

    it('exports visible metrics, series, and lineage in one CSV', () => {
        const csv = buildStudioResultsCsv({
            metrics,
            series: { equity_net: [1, 1.125] },
            metadata: { provenance: { engine_version: 'engine/1', code_hash: 'abc' }, data_quality: { source: 'observed' } },
            runId: 'run-1',
        });
        expect(csv).toContain('"metric","total_return"');
        expect(csv).toContain('"series","equity_net","1","1.125"');
        expect(csv).toContain('"manifest","run_id","","run-1"');
        expect(csv).toContain('"manifest","code_hash","","abc"');
    });

    it('derives orders only from nonzero signals and never synthesizes fills', () => {
        const orders = deriveOrdersFromSignals([
            { date: 'd1', direction: 0, price: 100, idx: 0 },
            { date: 'd2', direction: 1, price: 101, idx: 1 },
        ]);
        expect(orders).toHaveLength(1);
        expect(orders[0]).toMatchObject({ direction: 1, source: 'observed_signal' });
        const normalized = normalizeStudioExecutionResult({ signals: [{ date: 'd2', direction: 1, price: 101, idx: 1 }], fills: undefined }, 'run-9');
        expect(normalized.orders).toHaveLength(1);
        expect(normalized.fills).toBeNull();
        expect(replayFillLinkage(normalized).fillsAvailable).toBe(false);
    });

    it('exports deterministic JSON and print-friendly HTML with provenance', () => {
        const result = { metrics, series: { equity_net: [1, 1.125] }, metadata: { provenance: { engine_version: 'engine/1', code_hash: 'abc' }, data_quality: { source: 'observed' }, warnings: [] }, runId: 'run-1', orders: [], fillsStatus: { status: 'unavailable', reason: 'no fills' } };
        const json = JSON.parse(buildStudioResultsJson(result));
        expect(json.run_id).toBe('run-1');
        expect(json.fills).toBeNull();
        expect(json.arrow_export.status).toBe('deferred');
        const html = buildStudioResultsHtml(result);
        expect(html).toContain('Save as PDF via print');
        expect(html).toContain('engine/1');
    });
});
