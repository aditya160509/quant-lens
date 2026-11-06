const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const isNullableFiniteNumber = (value) => value === null || isFiniteNumber(value);

const isCandle = (value) => isObject(value)
    && isFiniteNumber(value.time)
    && isFiniteNumber(value.open)
    && isFiniteNumber(value.high)
    && isFiniteNumber(value.low)
    && isFiniteNumber(value.close)
    && isFiniteNumber(value.volume);

export const isStudioDataResponse = (value) => isObject(value)
    && value.status === 'success'
    && Array.isArray(value.candles)
    && value.candles.every(isCandle)
    && isObject(value.metadata);

export const isStudioExecutionResponse = (value) => isStudioDataResponse(value)
    && Array.isArray(value.signals)
    && Array.isArray(value.trades)
    && Array.isArray(value.equity_curve)
    && value.equity_curve.every(isFiniteNumber)
    && isObject(value.metrics)
    && (value.series === undefined || value.series === null || (isObject(value.series)
        && ['equity_net', 'equity_gross', 'drawdown', 'exposure', 'turnover', 'costs'].every((name) => (
            value.series[name] === undefined
            || (Array.isArray(value.series[name])
                && value.series[name].length === value.equity_curve.length
                && value.series[name].every(isFiniteNumber))
        ))
        && (value.series.benchmark_equity === undefined
            || (Array.isArray(value.series.benchmark_equity)
                && value.series.benchmark_equity.every(isFiniteNumber)
                && (value.series.benchmark_equity.length === 0 || value.series.benchmark_equity.length === value.equity_curve.length)))))
    && (value.orders === undefined || (Array.isArray(value.orders) && value.orders.every(isObject)))
    && (value.fills === undefined || value.fills === null || Array.isArray(value.fills));

export const isSensitivityResponse = (value) => isObject(value)
    && value.status === 'success'
    && Array.isArray(value.lookbacks)
    && Array.isArray(value.thresholds)
    && Array.isArray(value.cells)
    && value.cells.every((cell) => isObject(cell)
        && Number.isInteger(cell.lookback)
        && Number.isFinite(cell.threshold)
        && (cell.sharpe === null || Number.isFinite(cell.sharpe))
        && ['observed', 'unavailable'].includes(cell.status));

export const isScenarioResponse = (value) => isObject(value)
    && value.status === 'success'
    && Array.isArray(value.scenarios)
    && Array.isArray(value.skipped)
    && value.skipped.every((item) => isObject(item) && item.status === 'skipped' && typeof item.reason === 'string');

export const isStudioMonteCarloResponse = (value) => isObject(value)
    && value.status === 'success'
    && isObject(value.summary)
    && [
        'simulations', 'timeHorizon', 'meanFinalValue', 'medianFinalValue', 'stdFinalValue',
        'riskOfRuin', 'ruinThreshold', 'meanMaxDrawdown', 'worstDrawdown', 'bestFinal',
        'worstFinal', 'probPositive', 'probDouble', 'var95', 'p10', 'p90',
    ].every((field) => isFiniteNumber(value.summary[field]))
    && Array.isArray(value.samplePaths)
    && value.samplePaths.every(path => Array.isArray(path) && path.every(isFiniteNumber))
    && isObject(value.histogram)
    && Array.isArray(value.histogram.counts)
    && value.histogram.counts.every(isFiniteNumber)
    && Array.isArray(value.histogram.edges)
    && value.histogram.edges.every(isFiniteNumber)
    && value.histogram.edges.length === value.histogram.counts.length + 1
    && isObject(value.percentiles)
    && Object.values(value.percentiles).every(isFiniteNumber)
    && isObject(value.dailyReturns)
    && isFiniteNumber(value.dailyReturns.mean)
    && isFiniteNumber(value.dailyReturns.std)
    && isNullableFiniteNumber(value.dailyReturns.sharpeImplied)
    && isObject(value.assumptions)
    && ['gaussian', 'historical_bootstrap', 'moving_block_bootstrap'].includes(value.assumptions.method)
    && isFiniteNumber(value.assumptions.seed)
    && isNullableFiniteNumber(value.assumptions.blockSize)
    && isFiniteNumber(value.assumptions.inputObservations)
    && value.assumptions.returnConvention === 'simple';

export const isStudioWalkForwardResponse = (value) => isObject(value)
    && value.status === 'success'
    && isObject(value.summary)
    && isNullableFiniteNumber(value.summary.avgIsSharpe)
    && isNullableFiniteNumber(value.summary.avgOosSharpe)
    && isNullableFiniteNumber(value.summary.consistency)
    && isNullableFiniteNumber(value.summary.alphaDecay)
    && isFiniteNumber(value.summary.oosWindow)
    && isFiniteNumber(value.summary.totalFolds)
    && Array.isArray(value.folds)
    && value.folds.every((fold) => isObject(fold)
        && isFiniteNumber(fold.fold)
        && isNullableFiniteNumber(fold.isSharpe)
        && isNullableFiniteNumber(fold.oosSharpe)
        && isFiniteNumber(fold.isReturn)
        && isFiniteNumber(fold.oosReturn)
        && isNullableFiniteNumber(fold.degradation)
        && ['trainStart', 'trainEnd', 'testStart', 'testEnd', 'purgeDays', 'embargoDays'].every((field) => isFiniteNumber(fold[field]))
        && fold.trainStart >= 0
        && fold.trainStart < fold.trainEnd
        && fold.trainEnd + fold.purgeDays + fold.embargoDays === fold.testStart
        && fold.testStart < fold.testEnd)
    && isObject(value.alphaShield)
    && ['STRONG', 'WEAK', 'FAILED', 'UNAVAILABLE'].includes(value.alphaShield.status)
    && isNullableFiniteNumber(value.alphaShield.confidence)
    && isObject(value.verdict)
    && ['PASSED', 'FAILED', 'UNAVAILABLE'].includes(value.verdict.status)
    && value.verdict.methodology === 'deterministic_threshold_rules_not_statistical_confidence'
    && isObject(value.verdict.thresholds)
    && isFiniteNumber(value.verdict.thresholds.minOosSharpe)
    && isFiniteNumber(value.verdict.thresholds.minConsistencyPct)
    && Array.isArray(value.verdict.tests)
    && value.verdict.tests.length > 0
    && value.verdict.tests.every((test) => isObject(test)
        && typeof test.id === 'string'
        && typeof test.label === 'string'
        && ['pass', 'fail', 'unavailable'].includes(test.status)
        && isNullableFiniteNumber(test.value)
        && isFiniteNumber(test.threshold)
        && test.operator === '>=');

export const isStudioTickersResponse = (value) => isObject(value)
    && value.status === 'success'
    && (value.contract_version === undefined || value.contract_version === '1.0')
    && Array.isArray(value.tickers)
    && value.tickers.every((ticker) => typeof ticker === 'string' && ticker.length > 0)
    && isFiniteNumber(value.total)
    && Array.isArray(value.universes)
    && value.universes.every((name) => typeof name === 'string');

export const isStudioHealthResponse = (value) => isObject(value)
    && value.status === 'ok'
    && (value.contract_version === undefined || value.contract_version === '1.0')
    && typeof value.check === 'string'
    && isObject(value.execution)
    && typeof value.execution.mode === 'string';

export const isStudioErrorEnvelope = (value) => isObject(value)
    && value.status === 'error'
    && isObject(value.detail)
    && typeof value.detail.code === 'string'
    && typeof value.detail.message === 'string';
