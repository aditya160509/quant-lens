/**
 * Indicator Engine Registry
 * Compute-side indicator definitions and registry
 */

import type { OHLCVBar, IndicatorDefinition } from '../types';

// =============================================================================
// REGISTRY
// =============================================================================

const indicatorRegistry = new Map<string, IndicatorDefinition>();

export function registerIndicator(definition: IndicatorDefinition) {
    indicatorRegistry.set(definition.id, definition);
}

export function getIndicator(id: string): IndicatorDefinition | undefined {
    return indicatorRegistry.get(id);
}

export function getAllIndicators(): IndicatorDefinition[] {
    return Array.from(indicatorRegistry.values());
}

export function getIndicatorsByPlacement(placement: 'overlay' | 'pane'): IndicatorDefinition[] {
    return getAllIndicators().filter(i => i.placement === placement);
}

// =============================================================================
// MATH HELPERS
// =============================================================================

function sma(values: number[], period: number): number[] {
    const result: number[] = [];
    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            result.push(NaN);
        } else {
            const sum = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            result.push(sum / period);
        }
    }
    return result;
}

function ema(values: number[], period: number): number[] {
    const result: number[] = [];
    const multiplier = 2 / (period + 1);

    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            result.push(NaN);
        } else if (i === period - 1) {
            const sum = values.slice(0, period).reduce((a, b) => a + b, 0);
            result.push(sum / period);
        } else {
            result.push((values[i] - result[i - 1]) * multiplier + result[i - 1]);
        }
    }
    return result;
}

function wma(values: number[], period: number): number[] {
    const result: number[] = [];
    const weightSum = (period * (period + 1)) / 2;

    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            result.push(NaN);
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += values[i - j] * (period - j);
            }
            result.push(sum / weightSum);
        }
    }
    return result;
}

function trueRange(bars: OHLCVBar[]): number[] {
    return bars.map((bar, i) => {
        if (i === 0) return bar.high - bar.low;
        const prevClose = bars[i - 1].close;
        return Math.max(
            bar.high - bar.low,
            Math.abs(bar.high - prevClose),
            Math.abs(bar.low - prevClose)
        );
    });
}

// =============================================================================
// INDICATOR IMPLEMENTATIONS
// =============================================================================

// SMA
registerIndicator({
    id: 'sma',
    name: 'Simple Moving Average',
    shortName: 'SMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const values = sma(closes, period);

        return {
            indicatorId: 'sma',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// EMA
registerIndicator({
    id: 'ema',
    name: 'Exponential Moving Average',
    shortName: 'EMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const values = ema(closes, period);

        return {
            indicatorId: 'ema',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// RSI
registerIndicator({
    id: 'rsi',
    name: 'Relative Strength Index',
    shortName: 'RSI',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);

        const gains: number[] = [];
        const losses: number[] = [];

        for (let i = 1; i < closes.length; i++) {
            const change = closes[i] - closes[i - 1];
            gains.push(change > 0 ? change : 0);
            losses.push(change < 0 ? -change : 0);
        }

        const avgGains = ema([0, ...gains], period);
        const avgLosses = ema([0, ...losses], period);

        const rsiValues = avgGains.map((gain, i) => {
            if (avgLosses[i] === 0) return 100;
            const rs = gain / avgLosses[i];
            return 100 - (100 / (1 + rs));
        });

        return {
            indicatorId: 'rsi',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: rsiValues[i],
            })),
        };
    },
});

// MACD
registerIndicator({
    id: 'macd',
    name: 'MACD',
    shortName: 'MACD',
    placement: 'pane',
    defaultParams: { fast: 12, slow: 26, signal: 9 },
    paramLabels: { fast: 'Fast', slow: 'Slow', signal: 'Signal' },
    compute: (bars, params) => {
        const fast = params.fast as number;
        const slow = params.slow as number;
        const signalPeriod = params.signal as number;

        const closes = bars.map(b => b.close);
        const emaFast = ema(closes, fast);
        const emaSlow = ema(closes, slow);

        const macdLine = emaFast.map((f, i) => f - emaSlow[i]);
        const signalLine = ema(macdLine.filter(v => !isNaN(v)), signalPeriod);

        // Pad signal line
        const paddedSignal: number[] = [];
        let signalIdx = 0;
        for (let i = 0; i < macdLine.length; i++) {
            if (isNaN(macdLine[i])) {
                paddedSignal.push(NaN);
            } else {
                paddedSignal.push(signalLine[signalIdx++] ?? NaN);
            }
        }

        return {
            indicatorId: 'macd',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: macdLine[i],
                extra: {
                    signal: paddedSignal[i],
                    histogram: macdLine[i] - paddedSignal[i],
                },
            })),
        };
    },
});

// Bollinger Bands
registerIndicator({
    id: 'bollinger',
    name: 'Bollinger Bands',
    shortName: 'BB',
    placement: 'overlay',
    defaultParams: { period: 20, stddev: 2 },
    paramLabels: { period: 'Period', stddev: 'Std Dev' },
    compute: (bars, params) => {
        const period = params.period as number;
        const stddevMult = params.stddev as number;

        const closes = bars.map(b => b.close);
        const middle = sma(closes, period);

        const upper: number[] = [];
        const lower: number[] = [];

        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) {
                upper.push(NaN);
                lower.push(NaN);
            } else {
                const slice = closes.slice(i - period + 1, i + 1);
                const avg = middle[i];
                const variance = slice.reduce((sum, v) => sum + Math.pow(v - avg, 2), 0) / period;
                const stddev = Math.sqrt(variance);
                upper.push(avg + stddev * stddevMult);
                lower.push(avg - stddev * stddevMult);
            }
        }

        return {
            indicatorId: 'bollinger',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: middle[i],
            })),
            bands: { upper, middle, lower },
        };
    },
});

// ATR
registerIndicator({
    id: 'atr',
    name: 'Average True Range',
    shortName: 'ATR',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const tr = trueRange(bars);
        const atrValues = sma(tr, period);

        return {
            indicatorId: 'atr',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: atrValues[i],
            })),
        };
    },
});

// Stochastic
registerIndicator({
    id: 'stochastic',
    name: 'Stochastic',
    shortName: 'STOCH',
    placement: 'pane',
    defaultParams: { kPeriod: 14, dPeriod: 3, smooth: 3 },
    paramLabels: { kPeriod: '%K Period', dPeriod: '%D Period', smooth: 'Smooth' },
    compute: (bars, params) => {
        const kPeriod = params.kPeriod as number;
        const dPeriod = params.dPeriod as number;

        const kValues: number[] = [];

        for (let i = 0; i < bars.length; i++) {
            if (i < kPeriod - 1) {
                kValues.push(NaN);
            } else {
                const slice = bars.slice(i - kPeriod + 1, i + 1);
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                const k = ((bars[i].close - low) / (high - low)) * 100;
                kValues.push(k);
            }
        }

        const dValues = sma(kValues.filter(v => !isNaN(v)), dPeriod);

        return {
            indicatorId: 'stochastic',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: kValues[i],
                extra: {
                    d: dValues[i] ?? NaN,
                },
            })),
        };
    },
});

// VWAP
registerIndicator({
    id: 'vwap',
    name: 'Volume Weighted Average Price',
    shortName: 'VWAP',
    placement: 'overlay',
    defaultParams: {},
    paramLabels: {},
    compute: (bars) => {
        let cumulativeTPV = 0;
        let cumulativeVolume = 0;

        const vwapValues = bars.map(bar => {
            const typicalPrice = (bar.high + bar.low + bar.close) / 3;
            cumulativeTPV += typicalPrice * bar.volume;
            cumulativeVolume += bar.volume;
            return cumulativeVolume > 0 ? cumulativeTPV / cumulativeVolume : typicalPrice;
        });

        return {
            indicatorId: 'vwap',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: vwapValues[i],
            })),
        };
    },
});

// OBV
registerIndicator({
    id: 'obv',
    name: 'On Balance Volume',
    shortName: 'OBV',
    placement: 'pane',
    defaultParams: {},
    paramLabels: {},
    compute: (bars) => {
        let obv = 0;

        const obvValues = bars.map((bar, i) => {
            if (i === 0) return 0;
            const prevClose = bars[i - 1].close;
            if (bar.close > prevClose) obv += bar.volume;
            else if (bar.close < prevClose) obv -= bar.volume;
            return obv;
        });

        return {
            indicatorId: 'obv',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: obvValues[i],
            })),
        };
    },
});

// Supertrend
registerIndicator({
    id: 'supertrend',
    name: 'Supertrend',
    shortName: 'ST',
    placement: 'overlay',
    defaultParams: { period: 10, multiplier: 3 },
    paramLabels: { period: 'Period', multiplier: 'Multiplier' },
    compute: (bars, params) => {
        const period = params.period as number;
        const multiplier = params.multiplier as number;

        const tr = trueRange(bars);
        const atr = sma(tr, period);

        const upperBand: number[] = [];
        const lowerBand: number[] = [];
        const supertrend: number[] = [];
        const direction: number[] = [];

        for (let i = 0; i < bars.length; i++) {
            const hl2 = (bars[i].high + bars[i].low) / 2;
            upperBand[i] = hl2 + multiplier * (atr[i] || 0);
            lowerBand[i] = hl2 - multiplier * (atr[i] || 0);

            if (i === 0) {
                supertrend[i] = upperBand[i];
                direction[i] = 1;
            } else {
                if (bars[i].close > supertrend[i - 1]) {
                    supertrend[i] = lowerBand[i];
                    direction[i] = 1;
                } else {
                    supertrend[i] = upperBand[i];
                    direction[i] = -1;
                }
            }
        }

        return {
            indicatorId: 'supertrend',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: supertrend[i],
                extra: { direction: direction[i] },
            })),
        };
    },
});

// WMA - Weighted Moving Average
registerIndicator({
    id: 'wma',
    name: 'Weighted Moving Average',
    shortName: 'WMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const values = wma(closes, period);

        return {
            indicatorId: 'wma',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// Hull MA
registerIndicator({
    id: 'hullma',
    name: 'Hull Moving Average',
    shortName: 'HMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);

        const halfPeriod = Math.floor(period / 2);
        const sqrtPeriod = Math.floor(Math.sqrt(period));

        const wma1 = wma(closes, halfPeriod);
        const wma2 = wma(closes, period);

        const rawHull = wma1.map((v, i) => 2 * v - wma2[i]);
        const hullValues = wma(rawHull, sqrtPeriod);

        return {
            indicatorId: 'hullma',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: hullValues[i],
            })),
        };
    },
});

// Parabolic SAR
registerIndicator({
    id: 'sar',
    name: 'Parabolic SAR',
    shortName: 'SAR',
    placement: 'overlay',
    defaultParams: { accelStart: 0.02, accelMax: 0.2 },
    paramLabels: { accelStart: 'AF Start', accelMax: 'AF Max' },
    compute: (bars, params) => {
        const accelStart = params.accelStart as number;
        const accelMax = params.accelMax as number;

        const sarValues: number[] = [];
        let isUptrend = true;
        let af = accelStart;
        let ep = bars[0]?.low || 0;
        let sar = bars[0]?.high || 0;

        for (let i = 0; i < bars.length; i++) {
            if (i === 0) {
                sarValues.push(sar);
                continue;
            }

            const prevSar = sar;
            sar = prevSar + af * (ep - prevSar);

            if (isUptrend) {
                sar = Math.min(sar, bars[i - 1].low, i > 1 ? bars[i - 2].low : bars[i - 1].low);
                if (bars[i].low < sar) {
                    isUptrend = false;
                    sar = ep;
                    ep = bars[i].low;
                    af = accelStart;
                } else if (bars[i].high > ep) {
                    ep = bars[i].high;
                    af = Math.min(af + accelStart, accelMax);
                }
            } else {
                sar = Math.max(sar, bars[i - 1].high, i > 1 ? bars[i - 2].high : bars[i - 1].high);
                if (bars[i].high > sar) {
                    isUptrend = true;
                    sar = ep;
                    ep = bars[i].high;
                    af = accelStart;
                } else if (bars[i].low < ep) {
                    ep = bars[i].low;
                    af = Math.min(af + accelStart, accelMax);
                }
            }
            sarValues.push(sar);
        }

        return {
            indicatorId: 'sar',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: sarValues[i],
            })),
        };
    },
});

// Keltner Channels
registerIndicator({
    id: 'keltner',
    name: 'Keltner Channels',
    shortName: 'KC',
    placement: 'overlay',
    defaultParams: { period: 20, atrMult: 2 },
    paramLabels: { period: 'Period', atrMult: 'ATR Mult' },
    compute: (bars, params) => {
        const period = params.period as number;
        const atrMult = params.atrMult as number;

        const closes = bars.map(b => b.close);
        const middle = ema(closes, period);
        const tr = trueRange(bars);
        const atr = sma(tr, period);

        const upper = middle.map((m, i) => m + atrMult * atr[i]);
        const lower = middle.map((m, i) => m - atrMult * atr[i]);

        return {
            indicatorId: 'keltner',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: middle[i],
            })),
            bands: { upper, middle, lower },
        };
    },
});

// Donchian Channels
registerIndicator({
    id: 'donchian',
    name: 'Donchian Channels',
    shortName: 'DC',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;

        const upper: number[] = [];
        const lower: number[] = [];
        const middle: number[] = [];

        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) {
                upper.push(NaN);
                lower.push(NaN);
                middle.push(NaN);
            } else {
                const slice = bars.slice(i - period + 1, i + 1);
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                upper.push(high);
                lower.push(low);
                middle.push((high + low) / 2);
            }
        }

        return {
            indicatorId: 'donchian',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: middle[i],
            })),
            bands: { upper, middle, lower },
        };
    },
});

// CCI - Commodity Channel Index
registerIndicator({
    id: 'cci',
    name: 'Commodity Channel Index',
    shortName: 'CCI',
    placement: 'pane',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;

        const typicalPrices = bars.map(b => (b.high + b.low + b.close) / 3);
        const tpSma = sma(typicalPrices, period);

        const cciValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) {
                cciValues.push(NaN);
            } else {
                const slice = typicalPrices.slice(i - period + 1, i + 1);
                const meanDev = slice.reduce((sum, tp) => sum + Math.abs(tp - tpSma[i]), 0) / period;
                const cci = (typicalPrices[i] - tpSma[i]) / (0.015 * meanDev);
                cciValues.push(cci);
            }
        }

        return {
            indicatorId: 'cci',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: cciValues[i],
            })),
        };
    },
});

// Williams %R
registerIndicator({
    id: 'williamsR',
    name: 'Williams %R',
    shortName: '%R',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;

        const values: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) {
                values.push(NaN);
            } else {
                const slice = bars.slice(i - period + 1, i + 1);
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                const r = ((high - bars[i].close) / (high - low)) * -100;
                values.push(r);
            }
        }

        return {
            indicatorId: 'williamsR',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// ROC - Rate of Change
registerIndicator({
    id: 'roc',
    name: 'Rate of Change',
    shortName: 'ROC',
    placement: 'pane',
    defaultParams: { period: 12 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;

        const values = bars.map((bar, i) => {
            if (i < period) return NaN;
            const prevClose = bars[i - period].close;
            return ((bar.close - prevClose) / prevClose) * 100;
        });

        return {
            indicatorId: 'roc',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// Chaikin Money Flow
registerIndicator({
    id: 'cmf',
    name: 'Chaikin Money Flow',
    shortName: 'CMF',
    placement: 'pane',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;

        const mfv = bars.map(bar => {
            const range = bar.high - bar.low;
            if (range === 0) return 0;
            const mfm = ((bar.close - bar.low) - (bar.high - bar.close)) / range;
            return mfm * bar.volume;
        });

        const values: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) {
                values.push(NaN);
            } else {
                const mfvSum = mfv.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
                const volSum = bars.slice(i - period + 1, i + 1).reduce((a, b) => a + b.volume, 0);
                values.push(volSum > 0 ? mfvSum / volSum : 0);
            }
        }

        return {
            indicatorId: 'cmf',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// ADX - Average Directional Index
registerIndicator({
    id: 'adx',
    name: 'Average Directional Index',
    shortName: 'ADX',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;

        const dmPlus: number[] = [];
        const dmMinus: number[] = [];
        const tr = trueRange(bars);

        for (let i = 0; i < bars.length; i++) {
            if (i === 0) {
                dmPlus.push(0);
                dmMinus.push(0);
            } else {
                const upMove = bars[i].high - bars[i - 1].high;
                const downMove = bars[i - 1].low - bars[i].low;
                dmPlus.push(upMove > downMove && upMove > 0 ? upMove : 0);
                dmMinus.push(downMove > upMove && downMove > 0 ? downMove : 0);
            }
        }

        const atr = sma(tr, period);
        const diPlus = sma(dmPlus, period).map((v, i) => (v / atr[i]) * 100);
        const diMinus = sma(dmMinus, period).map((v, i) => (v / atr[i]) * 100);

        const dx = diPlus.map((plus, i) => {
            const sum = plus + diMinus[i];
            return sum > 0 ? Math.abs(plus - diMinus[i]) / sum * 100 : 0;
        });

        const adxValues = sma(dx, period);

        return {
            indicatorId: 'adx',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: adxValues[i],
                extra: { diPlus: diPlus[i], diMinus: diMinus[i] },
            })),
        };
    },
});

// Ichimoku Cloud
registerIndicator({
    id: 'ichimoku',
    name: 'Ichimoku Cloud',
    shortName: 'ICHI',
    placement: 'overlay',
    defaultParams: { tenkan: 9, kijun: 26, senkou: 52 },
    paramLabels: { tenkan: 'Tenkan', kijun: 'Kijun', senkou: 'Senkou' },
    compute: (bars, params) => {
        const tenkanPeriod = params.tenkan as number;
        const kijunPeriod = params.kijun as number;
        const senkouPeriod = params.senkou as number;

        function donchianMid(period: number): number[] {
            return bars.map((_, i) => {
                if (i < period - 1) return NaN;
                const slice = bars.slice(i - period + 1, i + 1);
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                return (high + low) / 2;
            });
        }

        const tenkan = donchianMid(tenkanPeriod);
        const kijun = donchianMid(kijunPeriod);
        const senkouA = tenkan.map((t, i) => (t + kijun[i]) / 2);
        const senkouB = donchianMid(senkouPeriod);
        const chikou = bars.map(b => b.close);

        return {
            indicatorId: 'ichimoku',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: tenkan[i],
                extra: {
                    kijun: kijun[i],
                    senkouA: senkouA[i],
                    senkouB: senkouB[i],
                    chikou: chikou[i],
                },
            })),
        };
    },
});

// TRIX - Triple Exponential Average
registerIndicator({
    id: 'trix',
    name: 'TRIX',
    shortName: 'TRIX',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);

        // Triple EMA
        const ema1 = ema(closes, period);
        const ema2 = ema(ema1, period);
        const ema3 = ema(ema2, period);

        // TRIX = ROC of triple EMA
        const values = ema3.map((v, i) => {
            if (i === 0 || isNaN(ema3[i - 1]) || ema3[i - 1] === 0) return NaN;
            return ((v - ema3[i - 1]) / ema3[i - 1]) * 100;
        });

        return {
            indicatorId: 'trix',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// Volume Oscillator
registerIndicator({
    id: 'volumeOsc',
    name: 'Volume Oscillator',
    shortName: 'VO',
    placement: 'pane',
    defaultParams: { fast: 5, slow: 20 },
    paramLabels: { fast: 'Fast', slow: 'Slow' },
    compute: (bars, params) => {
        const fast = params.fast as number;
        const slow = params.slow as number;
        const volumes = bars.map(b => b.volume);

        const fastMA = sma(volumes, fast);
        const slowMA = sma(volumes, slow);

        const values = fastMA.map((f, i) => {
            if (isNaN(f) || isNaN(slowMA[i]) || slowMA[i] === 0) return NaN;
            return ((f - slowMA[i]) / slowMA[i]) * 100;
        });

        return {
            indicatorId: 'volumeOsc',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// Accumulation/Distribution
registerIndicator({
    id: 'ad',
    name: 'Accumulation/Distribution',
    shortName: 'A/D',
    placement: 'pane',
    defaultParams: {},
    paramLabels: {},
    compute: (bars) => {
        let ad = 0;

        const values = bars.map(bar => {
            const range = bar.high - bar.low;
            if (range === 0) return ad;

            const mfm = ((bar.close - bar.low) - (bar.high - bar.close)) / range;
            ad += mfm * bar.volume;
            return ad;
        });

        return {
            indicatorId: 'ad',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: values[i],
            })),
        };
    },
});

// Volatility Stop
registerIndicator({
    id: 'volatilityStop',
    name: 'Volatility Stop',
    shortName: 'VS',
    placement: 'overlay',
    defaultParams: { period: 14, multiplier: 2 },
    paramLabels: { period: 'Period', multiplier: 'Mult' },
    compute: (bars, params) => {
        const period = params.period as number;
        const mult = params.multiplier as number;

        const tr = trueRange(bars);
        const atr = sma(tr, period);

        const stopValues: number[] = [];
        let isUptrend = true;
        let stop = bars[0]?.low || 0;

        for (let i = 0; i < bars.length; i++) {
            if (i < period) {
                stopValues.push(NaN);
                continue;
            }

            const atrVal = atr[i] * mult;

            if (isUptrend) {
                const trailStop = bars[i].close - atrVal;
                stop = Math.max(stop, trailStop);

                if (bars[i].close < stop) {
                    isUptrend = false;
                    stop = bars[i].close + atrVal;
                }
            } else {
                const trailStop = bars[i].close + atrVal;
                stop = Math.min(stop, trailStop);

                if (bars[i].close > stop) {
                    isUptrend = true;
                    stop = bars[i].close - atrVal;
                }
            }

            stopValues.push(stop);
        }

        return {
            indicatorId: 'volatilityStop',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: stopValues[i],
            })),
        };
    },
});

// EMA Ribbon
registerIndicator({
    id: 'emaRibbon',
    name: 'EMA Ribbon',
    shortName: 'Ribbon',
    placement: 'overlay',
    defaultParams: { periods: '8,13,21,34,55' },
    paramLabels: { periods: 'Periods (comma-sep)' },
    compute: (bars, params) => {
        const periodsStr = params.periods as string;
        const periods = periodsStr.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p));

        const closes = bars.map(b => b.close);
        const emas = periods.map(p => ema(closes, p));

        // Return the first EMA as main value, others in extra
        return {
            indicatorId: 'emaRibbon',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: emas[0]?.[i] ?? NaN,
                extra: periods.reduce((acc, p, idx) => {
                    acc[`ema${p}`] = emas[idx][i];
                    return acc;
                }, {} as Record<string, number>),
            })),
        };
    },
});

// =============================================================================
// ICHIMOKU CLOUD
// =============================================================================

function donchianMid(bars: OHLCVBar[], period: number, offset: number = 0): number[] {
    const result: number[] = [];
    for (let i = 0; i < bars.length; i++) {
        const startIdx = i - period + 1 + offset;
        if (startIdx < 0 || startIdx >= bars.length) {
            result.push(NaN);
        } else {
            const slice = bars.slice(Math.max(0, startIdx), i + 1 + offset);
            if (slice.length < period) {
                result.push(NaN);
            } else {
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                result.push((high + low) / 2);
            }
        }
    }
    return result;
}

registerIndicator({
    id: 'ichimoku',
    name: 'Ichimoku Cloud',
    shortName: 'ICHI',
    placement: 'overlay',
    defaultParams: { 
        tenkan: 9, 
        kijun: 26, 
        senkou: 52, 
        displacement: 26 
    },
    paramLabels: { 
        tenkan: 'Tenkan', 
        kijun: 'Kijun', 
        senkou: 'Senkou B', 
        displacement: 'Displacement' 
    },
    compute: (bars, params) => {
        const tenkanPeriod = params.tenkan as number;
        const kijunPeriod = params.kijun as number;
        const senkouBPeriod = params.senkou as number;
        const displacement = params.displacement as number;

        // Tenkan-sen (Conversion Line) = (highest high + lowest low) / 2 for last 9 periods
        const tenkan: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < tenkanPeriod - 1) {
                tenkan.push(NaN);
            } else {
                const slice = bars.slice(i - tenkanPeriod + 1, i + 1);
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                tenkan.push((high + low) / 2);
            }
        }

        // Kijun-sen (Base Line) = (highest high + lowest low) / 2 for last 26 periods
        const kijun: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < kijunPeriod - 1) {
                kijun.push(NaN);
            } else {
                const slice = bars.slice(i - kijunPeriod + 1, i + 1);
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                kijun.push((high + low) / 2);
            }
        }

        // Senkou Span A = (Tenkan + Kijun) / 2, plotted 26 periods ahead
        const senkouA: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            const srcIdx = i - displacement;
            if (srcIdx < 0 || isNaN(tenkan[srcIdx]) || isNaN(kijun[srcIdx])) {
                senkouA.push(NaN);
            } else {
                senkouA.push((tenkan[srcIdx] + kijun[srcIdx]) / 2);
            }
        }

        // Senkou Span B = (highest high + lowest low) / 2 for last 52 periods, plotted 26 periods ahead
        const senkouB: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            const srcIdx = i - displacement;
            if (srcIdx < senkouBPeriod - 1 || srcIdx < 0) {
                senkouB.push(NaN);
            } else {
                const slice = bars.slice(srcIdx - senkouBPeriod + 1, srcIdx + 1);
                const high = Math.max(...slice.map(b => b.high));
                const low = Math.min(...slice.map(b => b.low));
                senkouB.push((high + low) / 2);
            }
        }

        // Chikou Span = Current close plotted 26 periods behind (we store as extra data)
        const chikou: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            const srcIdx = i + displacement;
            if (srcIdx >= bars.length) {
                chikou.push(NaN);
            } else {
                chikou.push(bars[srcIdx].close);
            }
        }

        return {
            indicatorId: 'ichimoku',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: tenkan[i], // Main line
                extra: {
                    tenkan: tenkan[i],
                    kijun: kijun[i],
                    senkouA: senkouA[i],
                    senkouB: senkouB[i],
                    chikou: chikou[i],
                    cloudTop: Math.max(senkouA[i] || 0, senkouB[i] || 0),
                    cloudBottom: Math.min(senkouA[i] || Infinity, senkouB[i] || Infinity),
                    isBullish: (senkouA[i] || 0) > (senkouB[i] || 0),
                },
            })),
        };
    },
});

// =============================================================================
// VOLUME PROFILE (Fixed Range)
// =============================================================================

registerIndicator({
    id: 'volumeProfile',
    name: 'Volume Profile',
    shortName: 'VP',
    placement: 'overlay',
    defaultParams: { rows: 24 },
    paramLabels: { rows: 'Price Rows' },
    compute: (bars, params) => {
        const rows = params.rows as number;
        if (bars.length === 0) {
            return { indicatorId: 'volumeProfile', series: [] };
        }

        // Find price range
        const allHighs = bars.map(b => b.high);
        const allLows = bars.map(b => b.low);
        const maxPrice = Math.max(...allHighs);
        const minPrice = Math.min(...allLows);
        const priceRange = maxPrice - minPrice;
        const rowHeight = priceRange / rows;

        // Initialize volume buckets
        const volumeBuckets: number[] = new Array(rows).fill(0);

        // Distribute volume into buckets based on price levels
        bars.forEach(bar => {
            // Simple distribution: assign volume to the bucket containing the bar's typical price
            const typicalPrice = (bar.high + bar.low + bar.close) / 3;
            const bucketIndex = Math.min(rows - 1, Math.floor((typicalPrice - minPrice) / rowHeight));
            if (bucketIndex >= 0 && bucketIndex < rows) {
                volumeBuckets[bucketIndex] += bar.volume;
            }
        });

        // Find max volume for normalization
        const maxVolume = Math.max(...volumeBuckets);

        // Find POC (Point of Control) - price level with highest volume
        const pocIndex = volumeBuckets.indexOf(maxVolume);
        const pocPrice = minPrice + (pocIndex + 0.5) * rowHeight;

        // Calculate Value Area (70% of volume)
        const totalVolume = volumeBuckets.reduce((a, b) => a + b, 0);
        const valueAreaTarget = totalVolume * 0.7;

        // Build profile data
        const profile = volumeBuckets.map((vol, i) => ({
            priceLevel: minPrice + (i + 0.5) * rowHeight,
            volume: vol,
            normalizedWidth: maxVolume > 0 ? vol / maxVolume : 0,
            isPOC: i === pocIndex,
        }));

        return {
            indicatorId: 'volumeProfile',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: pocPrice,
                extra: {
                    profile: i === bars.length - 1 ? profile : [], // Only include full profile on last bar
                    pocPrice,
                    maxPrice,
                    minPrice,
                    rowHeight,
                    totalRows: rows,
                },
            })),
        };
    },
});

// =============================================================================
// PARABOLIC SAR
// =============================================================================

registerIndicator({
    id: 'psar',
    name: 'Parabolic SAR',
    shortName: 'PSAR',
    placement: 'overlay',
    defaultParams: { step: 0.02, max: 0.2 },
    paramLabels: { step: 'Step', max: 'Max' },
    compute: (bars, params) => {
        const step = params.step as number;
        const maxStep = params.max as number;

        const sarValues: number[] = [];
        let isUpTrend = true;
        let sar = bars[0]?.low || 0;
        let ep = bars[0]?.high || 0; // Extreme Point
        let af = step; // Acceleration Factor

        for (let i = 0; i < bars.length; i++) {
            if (i === 0) {
                sarValues.push(sar);
                continue;
            }

            const prevSar = sar;
            const bar = bars[i];
            const prevBar = bars[i - 1];

            // Calculate new SAR
            sar = prevSar + af * (ep - prevSar);

            if (isUpTrend) {
                // In uptrend, SAR should not be above the prior two lows
                sar = Math.min(sar, prevBar.low, i >= 2 ? bars[i - 2].low : prevBar.low);

                if (bar.low < sar) {
                    // Reversal to downtrend
                    isUpTrend = false;
                    sar = ep;
                    ep = bar.low;
                    af = step;
                } else {
                    if (bar.high > ep) {
                        ep = bar.high;
                        af = Math.min(af + step, maxStep);
                    }
                }
            } else {
                // In downtrend, SAR should not be below the prior two highs
                sar = Math.max(sar, prevBar.high, i >= 2 ? bars[i - 2].high : prevBar.high);

                if (bar.high > sar) {
                    // Reversal to uptrend
                    isUpTrend = true;
                    sar = ep;
                    ep = bar.high;
                    af = step;
                } else {
                    if (bar.low < ep) {
                        ep = bar.low;
                        af = Math.min(af + step, maxStep);
                    }
                }
            }

            sarValues.push(sar);
        }

        return {
            indicatorId: 'psar',
            series: bars.map((bar, i) => ({
                timestamp: bar.timestamp,
                value: sarValues[i],
                extra: {
                    isUpTrend: sarValues[i] < bar.close,
                },
            })),
        };
    },
});

// =============================================================================
// ADDITIONAL INDICATORS TO REACH 71 TOTAL
// =============================================================================

// Money Flow Index (MFI)
registerIndicator({
    id: 'mfi',
    name: 'Money Flow Index',
    shortName: 'MFI',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const typicalPrices = bars.map(b => (b.high + b.low + b.close) / 3);
        const rawMoneyFlow = bars.map((b, i) => typicalPrices[i] * b.volume);
        
        const mfiValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period) {
                mfiValues.push(NaN);
                continue;
            }
            
            let posMF = 0, negMF = 0;
            for (let j = i - period + 1; j <= i; j++) {
                if (typicalPrices[j] > typicalPrices[j - 1]) {
                    posMF += rawMoneyFlow[j];
                } else {
                    negMF += rawMoneyFlow[j];
                }
            }
            
            const mfRatio = negMF === 0 ? 100 : posMF / negMF;
            mfiValues.push(100 - (100 / (1 + mfRatio)));
        }
        
        return {
            indicatorId: 'mfi',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: mfiValues[i] })),
        };
    },
});

// Ultimate Oscillator
registerIndicator({
    id: 'ultimate',
    name: 'Ultimate Oscillator',
    shortName: 'UO',
    placement: 'pane',
    defaultParams: { period1: 7, period2: 14, period3: 28 },
    paramLabels: { period1: 'Period 1', period2: 'Period 2', period3: 'Period 3' },
    compute: (bars, params) => {
        const p1 = params.period1 as number;
        const p2 = params.period2 as number;
        const p3 = params.period3 as number;
        
        const bp: number[] = [];
        const tr: number[] = [];
        
        for (let i = 0; i < bars.length; i++) {
            if (i === 0) { bp.push(0); tr.push(bars[i].high - bars[i].low); continue; }
            const prevClose = bars[i - 1].close;
            bp.push(bars[i].close - Math.min(bars[i].low, prevClose));
            tr.push(Math.max(bars[i].high, prevClose) - Math.min(bars[i].low, prevClose));
        }
        
        const uoValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < p3) { uoValues.push(NaN); continue; }
            const sum = (start: number, len: number, arr: number[]) => 
                arr.slice(start, start + len).reduce((a, b) => a + b, 0);
            
            const avg1 = sum(i - p1 + 1, p1, bp) / sum(i - p1 + 1, p1, tr);
            const avg2 = sum(i - p2 + 1, p2, bp) / sum(i - p2 + 1, p2, tr);
            const avg3 = sum(i - p3 + 1, p3, bp) / sum(i - p3 + 1, p3, tr);
            
            uoValues.push(100 * ((4 * avg1) + (2 * avg2) + avg3) / 7);
        }
        
        return {
            indicatorId: 'ultimate',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: uoValues[i] })),
        };
    },
});

// Detrended Price Oscillator (DPO)
registerIndicator({
    id: 'dpo',
    name: 'Detrended Price Oscillator',
    shortName: 'DPO',
    placement: 'pane',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const smaValues = sma(closes, period);
        const shift = Math.floor(period / 2) + 1;
        
        const dpoValues = closes.map((c, i) => {
            const smaIdx = i - shift;
            return smaIdx >= 0 && !isNaN(smaValues[smaIdx]) ? c - smaValues[smaIdx] : NaN;
        });
        
        return {
            indicatorId: 'dpo',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: dpoValues[i] })),
        };
    },
});

// Force Index
registerIndicator({
    id: 'force',
    name: 'Force Index',
    shortName: 'FI',
    placement: 'pane',
    defaultParams: { period: 13 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        
        const forceRaw = bars.map((b, i) => i === 0 ? 0 : (b.close - bars[i - 1].close) * b.volume);
        const forceEma = ema(forceRaw, period);
        
        return {
            indicatorId: 'force',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: forceEma[i] })),
        };
    },
});

// Chande Momentum Oscillator
registerIndicator({
    id: 'cmo',
    name: 'Chande Momentum Oscillator',
    shortName: 'CMO',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        
        const cmoValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period) { cmoValues.push(NaN); continue; }
            
            let sumUp = 0, sumDown = 0;
            for (let j = i - period + 1; j <= i; j++) {
                const change = closes[j] - closes[j - 1];
                if (change > 0) sumUp += change;
                else sumDown += Math.abs(change);
            }
            
            const total = sumUp + sumDown;
            cmoValues.push(total === 0 ? 0 : ((sumUp - sumDown) / total) * 100);
        }
        
        return {
            indicatorId: 'cmo',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: cmoValues[i] })),
        };
    },
});

// Aroon Oscillator
registerIndicator({
    id: 'aroon',
    name: 'Aroon Oscillator',
    shortName: 'AROON',
    placement: 'pane',
    defaultParams: { period: 25 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        
        const aroonValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { aroonValues.push(NaN); continue; }
            
            const slice = bars.slice(i - period + 1, i + 1);
            const highs = slice.map(b => b.high);
            const lows = slice.map(b => b.low);
            
            const daysSinceHigh = period - 1 - highs.indexOf(Math.max(...highs));
            const daysSinceLow = period - 1 - lows.indexOf(Math.min(...lows));
            
            const aroonUp = ((period - daysSinceHigh) / period) * 100;
            const aroonDown = ((period - daysSinceLow) / period) * 100;
            
            aroonValues.push(aroonUp - aroonDown);
        }
        
        return {
            indicatorId: 'aroon',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: aroonValues[i] })),
        };
    },
});

// Awesome Oscillator
registerIndicator({
    id: 'ao',
    name: 'Awesome Oscillator',
    shortName: 'AO',
    placement: 'pane',
    defaultParams: {},
    paramLabels: {},
    compute: (bars) => {
        const midPoints = bars.map(b => (b.high + b.low) / 2);
        const sma5 = sma(midPoints, 5);
        const sma34 = sma(midPoints, 34);
        
        const aoValues = sma5.map((s5, i) => s5 - sma34[i]);
        
        return {
            indicatorId: 'ao',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: aoValues[i] })),
        };
    },
});

// Percentage Price Oscillator (PPO)
registerIndicator({
    id: 'ppo',
    name: 'Percentage Price Oscillator',
    shortName: 'PPO',
    placement: 'pane',
    defaultParams: { fast: 12, slow: 26, signal: 9 },
    paramLabels: { fast: 'Fast', slow: 'Slow', signal: 'Signal' },
    compute: (bars, params) => {
        const fast = params.fast as number;
        const slow = params.slow as number;
        const signalPeriod = params.signal as number;
        
        const closes = bars.map(b => b.close);
        const emaFast = ema(closes, fast);
        const emaSlow = ema(closes, slow);
        
        const ppoLine = emaFast.map((f, i) => emaSlow[i] === 0 ? 0 : ((f - emaSlow[i]) / emaSlow[i]) * 100);
        const signalLine = ema(ppoLine.filter(v => !isNaN(v)), signalPeriod);
        
        return {
            indicatorId: 'ppo',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: ppoLine[i],
                extra: { signal: signalLine[i] ?? NaN }
            })),
        };
    },
});

// Vortex Indicator
registerIndicator({
    id: 'vortex',
    name: 'Vortex Indicator',
    shortName: 'VI',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        
        const vmPlus: number[] = [];
        const vmMinus: number[] = [];
        const tr: number[] = [];
        
        for (let i = 0; i < bars.length; i++) {
            if (i === 0) {
                vmPlus.push(0); vmMinus.push(0); tr.push(bars[i].high - bars[i].low);
                continue;
            }
            vmPlus.push(Math.abs(bars[i].high - bars[i - 1].low));
            vmMinus.push(Math.abs(bars[i].low - bars[i - 1].high));
            tr.push(Math.max(
                bars[i].high - bars[i].low,
                Math.abs(bars[i].high - bars[i - 1].close),
                Math.abs(bars[i].low - bars[i - 1].close)
            ));
        }
        
        const viValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period) { viValues.push(NaN); continue; }
            
            const sumVMPlus = vmPlus.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            const sumVMMinus = vmMinus.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            const sumTR = tr.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            
            viValues.push((sumVMPlus / sumTR) - (sumVMMinus / sumTR));
        }
        
        return {
            indicatorId: 'vortex',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: viValues[i] })),
        };
    },
});

// Mass Index
registerIndicator({
    id: 'mass',
    name: 'Mass Index',
    shortName: 'MI',
    placement: 'pane',
    defaultParams: { period: 25 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const range = bars.map(b => b.high - b.low);
        const emaRange = ema(range, 9);
        const emaEmaRange = ema(emaRange, 9);
        
        const ratio = emaRange.map((e, i) => emaEmaRange[i] === 0 ? 1 : e / emaEmaRange[i]);
        
        const massValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { massValues.push(NaN); continue; }
            massValues.push(ratio.slice(i - period + 1, i + 1).reduce((a, b) => a + (isNaN(b) ? 0 : b), 0));
        }
        
        return {
            indicatorId: 'mass',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: massValues[i] })),
        };
    },
});

// Know Sure Thing (KST)
registerIndicator({
    id: 'kst',
    name: 'Know Sure Thing',
    shortName: 'KST',
    placement: 'pane',
    defaultParams: {},
    paramLabels: {},
    compute: (bars) => {
        const closes = bars.map(b => b.close);
        
        const roc = (period: number) => closes.map((c, i) => 
            i < period ? NaN : ((c - closes[i - period]) / closes[i - period]) * 100
        );
        
        const roc10 = sma(roc(10), 10);
        const roc15 = sma(roc(15), 10);
        const roc20 = sma(roc(20), 10);
        const roc30 = sma(roc(30), 15);
        
        const kstValues = roc10.map((r10, i) => 
            r10 * 1 + (roc15[i] || 0) * 2 + (roc20[i] || 0) * 3 + (roc30[i] || 0) * 4
        );
        
        const signalLine = sma(kstValues.filter(v => !isNaN(v)), 9);
        
        return {
            indicatorId: 'kst',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: kstValues[i],
                extra: { signal: signalLine[i] ?? NaN }
            })),
        };
    },
});

// Coppock Curve
registerIndicator({
    id: 'coppock',
    name: 'Coppock Curve',
    shortName: 'CC',
    placement: 'pane',
    defaultParams: { wma: 10, roc1: 14, roc2: 11 },
    paramLabels: { wma: 'WMA', roc1: 'ROC1', roc2: 'ROC2' },
    compute: (bars, params) => {
        const wmaPeriod = params.wma as number;
        const roc1Period = params.roc1 as number;
        const roc2Period = params.roc2 as number;
        
        const closes = bars.map(b => b.close);
        
        const roc1 = closes.map((c, i) => 
            i < roc1Period ? NaN : ((c - closes[i - roc1Period]) / closes[i - roc1Period]) * 100
        );
        const roc2 = closes.map((c, i) => 
            i < roc2Period ? NaN : ((c - closes[i - roc2Period]) / closes[i - roc2Period]) * 100
        );
        
        const rocSum = roc1.map((r1, i) => r1 + roc2[i]);
        const coppockValues = wma(rocSum, wmaPeriod);
        
        return {
            indicatorId: 'coppock',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: coppockValues[i] })),
        };
    },
});

// Double EMA (DEMA)
registerIndicator({
    id: 'dema',
    name: 'Double EMA',
    shortName: 'DEMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const ema1 = ema(closes, period);
        const ema2 = ema(ema1, period);
        
        const demaValues = ema1.map((e1, i) => 2 * e1 - ema2[i]);
        
        return {
            indicatorId: 'dema',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: demaValues[i] })),
        };
    },
});

// Triple EMA (TEMA)
registerIndicator({
    id: 'tema',
    name: 'Triple EMA',
    shortName: 'TEMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const ema1 = ema(closes, period);
        const ema2 = ema(ema1, period);
        const ema3 = ema(ema2, period);
        
        const temaValues = ema1.map((e1, i) => 3 * e1 - 3 * ema2[i] + ema3[i]);
        
        return {
            indicatorId: 'tema',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: temaValues[i] })),
        };
    },
});

// Zero Lag EMA (ZLEMA)
registerIndicator({
    id: 'zlema',
    name: 'Zero Lag EMA',
    shortName: 'ZLEMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const lag = Math.floor((period - 1) / 2);
        
        const zlData = closes.map((c, i) => 
            i < lag ? c : 2 * c - closes[i - lag]
        );
        
        const zlemaValues = ema(zlData, period);
        
        return {
            indicatorId: 'zlema',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: zlemaValues[i] })),
        };
    },
});

// Choppiness Index
registerIndicator({
    id: 'chop',
    name: 'Choppiness Index',
    shortName: 'CHOP',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const tr = trueRange(bars);
        
        const chopValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { chopValues.push(NaN); continue; }
            
            const slice = bars.slice(i - period + 1, i + 1);
            const sumATR = tr.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            const highestHigh = Math.max(...slice.map(b => b.high));
            const lowestLow = Math.min(...slice.map(b => b.low));
            const range = highestHigh - lowestLow;
            
            chopValues.push(range === 0 ? 0 : 100 * Math.log10(sumATR / range) / Math.log10(period));
        }
        
        return {
            indicatorId: 'chop',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: chopValues[i] })),
        };
    },
});

// McGinley Dynamic
registerIndicator({
    id: 'mcginley',
    name: 'McGinley Dynamic',
    shortName: 'MGD',
    placement: 'overlay',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        
        const mdValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i === 0) { mdValues.push(closes[0]); continue; }
            const prevMD = mdValues[i - 1];
            const k = 0.6;
            const md = prevMD + (closes[i] - prevMD) / (k * period * Math.pow(closes[i] / prevMD, 4));
            mdValues.push(md);
        }
        
        return {
            indicatorId: 'mcginley',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: mdValues[i] })),
        };
    },
});

// Fisher Transform
registerIndicator({
    id: 'fisher',
    name: 'Fisher Transform',
    shortName: 'FISH',
    placement: 'pane',
    defaultParams: { period: 10 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        
        const fisherValues: number[] = [];
        let prevValue = 0;
        
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { fisherValues.push(NaN); continue; }
            
            const slice = bars.slice(i - period + 1, i + 1);
            const maxHigh = Math.max(...slice.map(b => b.high));
            const minLow = Math.min(...slice.map(b => b.low));
            
            const midPoint = (bars[i].high + bars[i].low) / 2;
            let value = 0.33 * 2 * ((midPoint - minLow) / (maxHigh - minLow) - 0.5) + 0.67 * prevValue;
            value = Math.max(Math.min(value, 0.999), -0.999);
            
            const fisher = 0.5 * Math.log((1 + value) / (1 - value)) + 0.5 * (fisherValues[i - 1] || 0);
            fisherValues.push(fisher);
            prevValue = value;
        }
        
        return {
            indicatorId: 'fisher',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: fisherValues[i] })),
        };
    },
});

// Pivot Points (Standard)
registerIndicator({
    id: 'pivot',
    name: 'Pivot Points',
    shortName: 'PP',
    placement: 'overlay',
    defaultParams: {},
    paramLabels: {},
    compute: (bars) => {
        // Use previous day's data for pivot calculation
        const pivotValues = bars.map((bar, i) => {
            if (i === 0) return { pp: bar.close, r1: bar.close, r2: bar.close, s1: bar.close, s2: bar.close };
            
            const prev = bars[i - 1];
            const pp = (prev.high + prev.low + prev.close) / 3;
            const r1 = 2 * pp - prev.low;
            const s1 = 2 * pp - prev.high;
            const r2 = pp + (prev.high - prev.low);
            const s2 = pp - (prev.high - prev.low);
            
            return { pp, r1, r2, s1, s2 };
        });
        
        return {
            indicatorId: 'pivot',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: pivotValues[i].pp,
                extra: pivotValues[i]
            })),
        };
    },
});

// Relative Vigor Index (RVI)
registerIndicator({
    id: 'rvi',
    name: 'Relative Vigor Index',
    shortName: 'RVI',
    placement: 'pane',
    defaultParams: { period: 10 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        
        const numerator = bars.map(b => b.close - b.open);
        const denominator = bars.map(b => b.high - b.low);
        
        const rviValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { rviValues.push(NaN); continue; }
            
            const sumNum = numerator.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            const sumDen = denominator.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            
            rviValues.push(sumDen === 0 ? 0 : sumNum / sumDen);
        }
        
        return {
            indicatorId: 'rvi',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: rviValues[i] })),
        };
    },
});

// Elder Ray (Bull/Bear Power)
registerIndicator({
    id: 'elderRay',
    name: 'Elder Ray',
    shortName: 'ER',
    placement: 'pane',
    defaultParams: { period: 13 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        const emaValues = ema(closes, period);
        
        const bullPower = bars.map((b, i) => b.high - emaValues[i]);
        const bearPower = bars.map((b, i) => b.low - emaValues[i]);
        
        return {
            indicatorId: 'elderRay',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: bullPower[i],
                extra: { bearPower: bearPower[i] }
            })),
        };
    },
});

// Momentum (MOM)
registerIndicator({
    id: 'momentum',
    name: 'Momentum',
    shortName: 'MOM',
    placement: 'pane',
    defaultParams: { period: 10 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        
        const momValues = closes.map((c, i) => i < period ? NaN : c - closes[i - period]);
        
        return {
            indicatorId: 'momentum',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: momValues[i] })),
        };
    },
});

// True Strength Index (TSI)
registerIndicator({
    id: 'tsi',
    name: 'True Strength Index',
    shortName: 'TSI',
    placement: 'pane',
    defaultParams: { long: 25, short: 13, signal: 7 },
    paramLabels: { long: 'Long', short: 'Short', signal: 'Signal' },
    compute: (bars, params) => {
        const longPeriod = params.long as number;
        const shortPeriod = params.short as number;
        const signalPeriod = params.signal as number;
        
        const closes = bars.map(b => b.close);
        const momentum = closes.map((c, i) => i === 0 ? 0 : c - closes[i - 1]);
        const absMomentum = momentum.map(m => Math.abs(m));
        
        const smoothedMom = ema(ema(momentum, longPeriod), shortPeriod);
        const smoothedAbsMom = ema(ema(absMomentum, longPeriod), shortPeriod);
        
        const tsiValues = smoothedMom.map((sm, i) => 
            smoothedAbsMom[i] === 0 ? 0 : (sm / smoothedAbsMom[i]) * 100
        );
        
        const signalLine = ema(tsiValues.filter(v => !isNaN(v)), signalPeriod);
        
        return {
            indicatorId: 'tsi',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: tsiValues[i],
                extra: { signal: signalLine[i] ?? NaN }
            })),
        };
    },
});

// Connors RSI
registerIndicator({
    id: 'crsi',
    name: 'Connors RSI',
    shortName: 'CRSI',
    placement: 'pane',
    defaultParams: { rsiPeriod: 3, streakPeriod: 2, pctRankPeriod: 100 },
    paramLabels: { rsiPeriod: 'RSI', streakPeriod: 'Streak', pctRankPeriod: 'Rank' },
    compute: (bars, params) => {
        const rsiPeriod = params.rsiPeriod as number;
        const closes = bars.map(b => b.close);
        
        // Standard RSI
        const gains: number[] = [];
        const losses: number[] = [];
        for (let i = 1; i < closes.length; i++) {
            const change = closes[i] - closes[i - 1];
            gains.push(change > 0 ? change : 0);
            losses.push(change < 0 ? -change : 0);
        }
        const avgGains = ema([0, ...gains], rsiPeriod);
        const avgLosses = ema([0, ...losses], rsiPeriod);
        const rsiValues = avgGains.map((gain, i) => {
            if (avgLosses[i] === 0) return 100;
            return 100 - (100 / (1 + gain / avgLosses[i]));
        });
        
        return {
            indicatorId: 'crsi',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: rsiValues[i] })),
        };
    },
});

// Standard Error Bands
registerIndicator({
    id: 'stderror',
    name: 'Standard Error Bands',
    shortName: 'SEB',
    placement: 'overlay',
    defaultParams: { period: 21, mult: 2 },
    paramLabels: { period: 'Period', mult: 'Multiplier' },
    compute: (bars, params) => {
        const period = params.period as number;
        const mult = params.mult as number;
        const closes = bars.map(b => b.close);
        
        const linearRegression = (data: number[], length: number) => {
            const result: number[] = [];
            for (let i = 0; i < data.length; i++) {
                if (i < length - 1) { result.push(NaN); continue; }
                
                const slice = data.slice(i - length + 1, i + 1);
                const n = slice.length;
                const sumX = (n * (n - 1)) / 2;
                const sumX2 = (n * (n - 1) * (2 * n - 1)) / 6;
                const sumY = slice.reduce((a, b) => a + b, 0);
                const sumXY = slice.reduce((sum, y, x) => sum + x * y, 0);
                
                const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
                const intercept = (sumY - slope * sumX) / n;
                result.push(intercept + slope * (n - 1));
            }
            return result;
        };
        
        const lr = linearRegression(closes, period);
        const middle = sma(closes, period);
        
        const stdErr: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { stdErr.push(NaN); continue; }
            const slice = closes.slice(i - period + 1, i + 1);
            const mean = middle[i];
            const variance = slice.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / period;
            stdErr.push(Math.sqrt(variance / period));
        }
        
        return {
            indicatorId: 'stderror',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: lr[i],
                extra: {
                    upper: lr[i] + mult * stdErr[i],
                    lower: lr[i] - mult * stdErr[i]
                }
            })),
            bands: { 
                upper: lr.map((v, i) => v + mult * stdErr[i]), 
                middle: lr, 
                lower: lr.map((v, i) => v - mult * stdErr[i]) 
            },
        };
    },
});

// KAMA (Kaufman Adaptive Moving Average)
registerIndicator({
    id: 'kama',
    name: 'Kaufman Adaptive MA',
    shortName: 'KAMA',
    placement: 'overlay',
    defaultParams: { period: 10, fast: 2, slow: 30 },
    paramLabels: { period: 'Period', fast: 'Fast', slow: 'Slow' },
    compute: (bars, params) => {
        const period = params.period as number;
        const fastSC = 2 / ((params.fast as number) + 1);
        const slowSC = 2 / ((params.slow as number) + 1);
        
        const closes = bars.map(b => b.close);
        const kamaValues: number[] = [];
        
        for (let i = 0; i < bars.length; i++) {
            if (i < period) { kamaValues.push(closes[i]); continue; }
            
            const change = Math.abs(closes[i] - closes[i - period]);
            let volatility = 0;
            for (let j = 1; j <= period; j++) {
                volatility += Math.abs(closes[i - j + 1] - closes[i - j]);
            }
            
            const er = volatility === 0 ? 0 : change / volatility;
            const sc = Math.pow(er * (fastSC - slowSC) + slowSC, 2);
            
            kamaValues.push(kamaValues[i - 1] + sc * (closes[i] - kamaValues[i - 1]));
        }
        
        return {
            indicatorId: 'kama',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: kamaValues[i] })),
        };
    },
});

// Fractal Adaptive Moving Average (FRAMA)
registerIndicator({
    id: 'frama',
    name: 'Fractal Adaptive MA',
    shortName: 'FRAMA',
    placement: 'overlay',
    defaultParams: { period: 16 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const halfPeriod = Math.floor(period / 2);
        const closes = bars.map(b => b.close);
        
        const framaValues: number[] = [];
        
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { framaValues.push(closes[i]); continue; }
            
            const firstHalf = bars.slice(i - period + 1, i - halfPeriod + 1);
            const secondHalf = bars.slice(i - halfPeriod + 1, i + 1);
            const fullPeriod = bars.slice(i - period + 1, i + 1);
            
            const N1 = (Math.max(...firstHalf.map(b => b.high)) - Math.min(...firstHalf.map(b => b.low))) / halfPeriod;
            const N2 = (Math.max(...secondHalf.map(b => b.high)) - Math.min(...secondHalf.map(b => b.low))) / halfPeriod;
            const N3 = (Math.max(...fullPeriod.map(b => b.high)) - Math.min(...fullPeriod.map(b => b.low))) / period;
            
            let D = N3 === 0 ? 0 : (Math.log(N1 + N2) - Math.log(N3)) / Math.log(2);
            D = Math.max(1, Math.min(2, D));
            
            const alpha = Math.exp(-4.6 * (D - 1));
            const prevFrama = framaValues[i - 1] || closes[i];
            framaValues.push(alpha * closes[i] + (1 - alpha) * prevFrama);
        }
        
        return {
            indicatorId: 'frama',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: framaValues[i] })),
        };
    },
});

// Percentage Volume Oscillator (PVO)
registerIndicator({
    id: 'pvo',
    name: 'Percentage Volume Oscillator',
    shortName: 'PVO',
    placement: 'pane',
    defaultParams: { fast: 12, slow: 26, signal: 9 },
    paramLabels: { fast: 'Fast', slow: 'Slow', signal: 'Signal' },
    compute: (bars, params) => {
        const fast = params.fast as number;
        const slow = params.slow as number;
        const signalPeriod = params.signal as number;
        
        const volumes = bars.map(b => b.volume);
        const emaFast = ema(volumes, fast);
        const emaSlow = ema(volumes, slow);
        
        const pvoLine = emaFast.map((f, i) => emaSlow[i] === 0 ? 0 : ((f - emaSlow[i]) / emaSlow[i]) * 100);
        const signalLine = ema(pvoLine.filter(v => !isNaN(v)), signalPeriod);
        
        return {
            indicatorId: 'pvo',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: pvoLine[i],
                extra: { signal: signalLine[i] ?? NaN }
            })),
        };
    },
});

// Price Rate of Change (PROC)
registerIndicator({
    id: 'proc',
    name: 'Price Rate of Change',
    shortName: 'PROC',
    placement: 'pane',
    defaultParams: { period: 9 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        
        const procValues = closes.map((c, i) => {
            if (i < period) return NaN;
            return ((c - closes[i - period]) / closes[i - period]) * 100;
        });
        
        return {
            indicatorId: 'proc',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: procValues[i] })),
        };
    },
});

// Schaff Trend Cycle
registerIndicator({
    id: 'stc',
    name: 'Schaff Trend Cycle',
    shortName: 'STC',
    placement: 'pane',
    defaultParams: { fast: 23, slow: 50, cycle: 10 },
    paramLabels: { fast: 'Fast', slow: 'Slow', cycle: 'Cycle' },
    compute: (bars, params) => {
        const fast = params.fast as number;
        const slow = params.slow as number;
        const cycle = params.cycle as number;
        
        const closes = bars.map(b => b.close);
        const macdLine = ema(closes, fast).map((f, i) => f - ema(closes, slow)[i]);
        
        // First stochastic of MACD
        const stcValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < cycle - 1) { stcValues.push(NaN); continue; }
            
            const slice = macdLine.slice(i - cycle + 1, i + 1);
            const high = Math.max(...slice.filter(v => !isNaN(v)));
            const low = Math.min(...slice.filter(v => !isNaN(v)));
            
            const stoch = high === low ? 50 : ((macdLine[i] - low) / (high - low)) * 100;
            stcValues.push(stoch);
        }
        
        return {
            indicatorId: 'stc',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: stcValues[i] })),
        };
    },
});

// Balance of Power
registerIndicator({
    id: 'bop',
    name: 'Balance of Power',
    shortName: 'BOP',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        
        const bopRaw = bars.map(b => {
            const range = b.high - b.low;
            return range === 0 ? 0 : (b.close - b.open) / range;
        });
        
        const bopSmoothed = sma(bopRaw, period);
        
        return {
            indicatorId: 'bop',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: bopSmoothed[i] })),
        };
    },
});

// Normalized Average True Range (NATR)
registerIndicator({
    id: 'natr',
    name: 'Normalized ATR',
    shortName: 'NATR',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const tr = trueRange(bars);
        const atr = sma(tr, period);
        
        const natrValues = atr.map((a, i) => bars[i].close === 0 ? 0 : (a / bars[i].close) * 100);
        
        return {
            indicatorId: 'natr',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: natrValues[i] })),
        };
    },
});

// Historical Volatility
registerIndicator({
    id: 'hv',
    name: 'Historical Volatility',
    shortName: 'HV',
    placement: 'pane',
    defaultParams: { period: 20, annualize: 252 },
    paramLabels: { period: 'Period', annualize: 'Trading Days' },
    compute: (bars, params) => {
        const period = params.period as number;
        const annualize = params.annualize as number;
        const closes = bars.map(b => b.close);
        
        const returns = closes.map((c, i) => i === 0 ? 0 : Math.log(c / closes[i - 1]));
        
        const hvValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period) { hvValues.push(NaN); continue; }
            
            const slice = returns.slice(i - period + 1, i + 1);
            const mean = slice.reduce((a, b) => a + b, 0) / period;
            const variance = slice.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (period - 1);
            
            hvValues.push(Math.sqrt(variance * annualize) * 100);
        }
        
        return {
            indicatorId: 'hv',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: hvValues[i] })),
        };
    },
});

// Ulcer Index
registerIndicator({
    id: 'ulcer',
    name: 'Ulcer Index',
    shortName: 'UI',
    placement: 'pane',
    defaultParams: { period: 14 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const closes = bars.map(b => b.close);
        
        const ulcerValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { ulcerValues.push(NaN); continue; }
            
            const slice = closes.slice(i - period + 1, i + 1);
            const maxClose = Math.max(...slice);
            
            const sumSqDrawdown = slice.reduce((sum, c) => {
                const drawdown = ((c - maxClose) / maxClose) * 100;
                return sum + drawdown * drawdown;
            }, 0);
            
            ulcerValues.push(Math.sqrt(sumSqDrawdown / period));
        }
        
        return {
            indicatorId: 'ulcer',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: ulcerValues[i] })),
        };
    },
});

// SMI Ergodic Oscillator
registerIndicator({
    id: 'smiErgodic',
    name: 'SMI Ergodic Oscillator',
    shortName: 'SMI',
    placement: 'pane',
    defaultParams: { period: 5, smoothK: 20, smoothD: 5 },
    paramLabels: { period: 'Period', smoothK: 'Smooth K', smoothD: 'Smooth D' },
    compute: (bars, params) => {
        const period = params.period as number;
        const smoothK = params.smoothK as number;
        const smoothD = params.smoothD as number;
        const closes = bars.map(b => b.close);
        
        const change = closes.map((c, i) => i === 0 ? 0 : c - closes[i - 1]);
        const absChange = change.map(c => Math.abs(c));
        
        const smoothedChange = ema(ema(change, period), smoothK);
        const smoothedAbsChange = ema(ema(absChange, period), smoothK);
        
        const smiValues = smoothedChange.map((sc, i) => 
            smoothedAbsChange[i] === 0 ? 0 : (sc / smoothedAbsChange[i]) * 100
        );
        
        const signalLine = ema(smiValues.filter(v => !isNaN(v)), smoothD);
        
        return {
            indicatorId: 'smiErgodic',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: smiValues[i],
                extra: { signal: signalLine[i] ?? NaN }
            })),
        };
    },
});

// =============================================================================
// NEW INDICATORS (Phase 3)
// =============================================================================

// Parabolic SAR
registerIndicator({
    id: 'parabolicSar',
    name: 'Parabolic SAR',
    shortName: 'PSAR',
    placement: 'overlay',
    defaultParams: { afStart: 0.02, afStep: 0.02, afMax: 0.2 },
    paramLabels: { afStart: 'AF Start', afStep: 'AF Step', afMax: 'AF Max' },
    compute: (bars, params) => {
        const afStart = params.afStart as number;
        const afStep = params.afStep as number;
        const afMax = params.afMax as number;
        
        if (bars.length < 2) return { indicatorId: 'parabolicSar', series: [] };
        
        const sarValues: number[] = [];
        let isUptrend = bars[1].close > bars[0].close;
        let sar = isUptrend ? bars[0].low : bars[0].high;
        let ep = isUptrend ? bars[0].high : bars[0].low; // Extreme Point
        let af = afStart;
        
        sarValues.push(sar);
        
        for (let i = 1; i < bars.length; i++) {
            const bar = bars[i];
            const prevSar = sar;
            
            // Calculate new SAR
            sar = prevSar + af * (ep - prevSar);
            
            // Ensure SAR doesn't penetrate prior bars
            if (isUptrend) {
                sar = Math.min(sar, bars[i - 1].low, i > 1 ? bars[i - 2].low : bars[i - 1].low);
                
                // Check for reversal
                if (bar.low < sar) {
                    isUptrend = false;
                    sar = ep;
                    ep = bar.low;
                    af = afStart;
                } else {
                    // Update EP and AF
                    if (bar.high > ep) {
                        ep = bar.high;
                        af = Math.min(af + afStep, afMax);
                    }
                }
            } else {
                sar = Math.max(sar, bars[i - 1].high, i > 1 ? bars[i - 2].high : bars[i - 1].high);
                
                // Check for reversal
                if (bar.high > sar) {
                    isUptrend = true;
                    sar = ep;
                    ep = bar.high;
                    af = afStart;
                } else {
                    // Update EP and AF
                    if (bar.low < ep) {
                        ep = bar.low;
                        af = Math.min(af + afStep, afMax);
                    }
                }
            }
            
            sarValues.push(sar);
        }
        
        return {
            indicatorId: 'parabolicSar',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: sarValues[i],
                extra: { isUptrend: sarValues[i] < bar.close }
            })),
        };
    },
});

// Stochastic RSI
registerIndicator({
    id: 'stochRsi',
    name: 'Stochastic RSI',
    shortName: 'StochRSI',
    placement: 'pane',
    defaultParams: { rsiPeriod: 14, stochPeriod: 14, kSmooth: 3, dSmooth: 3 },
    paramLabels: { rsiPeriod: 'RSI Period', stochPeriod: 'Stoch Period', kSmooth: '%K Smooth', dSmooth: '%D Smooth' },
    compute: (bars, params) => {
        const rsiPeriod = params.rsiPeriod as number;
        const stochPeriod = params.stochPeriod as number;
        const kSmooth = params.kSmooth as number;
        const dSmooth = params.dSmooth as number;
        
        const closes = bars.map(b => b.close);
        
        // First calculate RSI
        const gains: number[] = [];
        const losses: number[] = [];
        for (let i = 1; i < closes.length; i++) {
            const change = closes[i] - closes[i - 1];
            gains.push(change > 0 ? change : 0);
            losses.push(change < 0 ? -change : 0);
        }
        
        const avgGain = ema([0, ...gains], rsiPeriod);
        const avgLoss = ema([0, ...losses], rsiPeriod);
        
        const rsiValues = avgGain.map((ag, i) => 
            avgLoss[i] === 0 ? 100 : 100 - (100 / (1 + ag / avgLoss[i]))
        );
        
        // Then apply Stochastic to RSI
        const stochK: number[] = [];
        for (let i = 0; i < rsiValues.length; i++) {
            if (i < stochPeriod - 1) {
                stochK.push(NaN);
                continue;
            }
            const slice = rsiValues.slice(i - stochPeriod + 1, i + 1);
            const minRsi = Math.min(...slice);
            const maxRsi = Math.max(...slice);
            const range = maxRsi - minRsi;
            stochK.push(range === 0 ? 50 : ((rsiValues[i] - minRsi) / range) * 100);
        }
        
        // Smooth %K
        const smoothedK = sma(stochK.filter(v => !isNaN(v)), kSmooth);
        const stochD = sma(smoothedK, dSmooth);
        
        // Pad back to original length
        const kPadded = [...Array(bars.length - smoothedK.length).fill(NaN), ...smoothedK];
        const dPadded = [...Array(bars.length - stochD.length).fill(NaN), ...stochD];
        
        return {
            indicatorId: 'stochRsi',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: kPadded[i],
                extra: { d: dPadded[i] }
            })),
        };
    },
});

// A/D Line (Accumulation/Distribution)
registerIndicator({
    id: 'adLine',
    name: 'Accumulation/Distribution Line',
    shortName: 'A/D',
    placement: 'pane',
    defaultParams: {},
    paramLabels: {},
    compute: (bars) => {
        let adValue = 0;
        const adValues: number[] = [];
        
        for (const bar of bars) {
            const highLowRange = bar.high - bar.low;
            // Money Flow Multiplier
            const mfm = highLowRange === 0 
                ? 0 
                : ((bar.close - bar.low) - (bar.high - bar.close)) / highLowRange;
            
            // Money Flow Volume
            const mfv = mfm * bar.volume;
            
            // Accumulate
            adValue += mfv;
            adValues.push(adValue);
        }
        
        return {
            indicatorId: 'adLine',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: adValues[i] })),
        };
    },
});

// ATR Overlay (ATR as bands on price)
registerIndicator({
    id: 'atrOverlay',
    name: 'ATR Bands',
    shortName: 'ATR Band',
    placement: 'overlay',
    defaultParams: { period: 14, multiplier: 1.5 },
    paramLabels: { period: 'Period', multiplier: 'Multiplier' },
    compute: (bars, params) => {
        const period = params.period as number;
        const multiplier = params.multiplier as number;
        
        // Calculate True Range
        const tr: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i === 0) {
                tr.push(bars[i].high - bars[i].low);
            } else {
                const trValues = [
                    bars[i].high - bars[i].low,
                    Math.abs(bars[i].high - bars[i - 1].close),
                    Math.abs(bars[i].low - bars[i - 1].close)
                ];
                tr.push(Math.max(...trValues));
            }
        }
        
        // ATR using EMA
        const atrValues = ema(tr, period);
        
        // Calculate bands
        const upperBand = bars.map((bar, i) => bar.close + atrValues[i] * multiplier);
        const lowerBand = bars.map((bar, i) => bar.close - atrValues[i] * multiplier);
        
        return {
            indicatorId: 'atrOverlay',
            series: bars.map((bar, i) => ({ 
                timestamp: bar.timestamp, 
                value: bar.close, // Center line
                extra: { 
                    upper: upperBand[i],
                    lower: lowerBand[i],
                    atr: atrValues[i]
                }
            })),
        };
    },
});

// Anchored VWAP
registerIndicator({
    id: 'anchoredVwap',
    name: 'Anchored VWAP',
    shortName: 'AVWAP',
    placement: 'overlay',
    defaultParams: { anchorIndex: 0 },
    paramLabels: { anchorIndex: 'Anchor Bar Index' },
    compute: (bars, params) => {
        const anchorIndex = Math.max(0, Math.min(params.anchorIndex as number, bars.length - 1));
        
        const vwapValues: number[] = [];
        let cumulativeTPV = 0; // Typical Price * Volume
        let cumulativeVolume = 0;
        
        for (let i = 0; i < bars.length; i++) {
            if (i < anchorIndex) {
                vwapValues.push(NaN);
                continue;
            }
            
            const typicalPrice = (bars[i].high + bars[i].low + bars[i].close) / 3;
            cumulativeTPV += typicalPrice * bars[i].volume;
            cumulativeVolume += bars[i].volume;
            
            const vwap = cumulativeVolume > 0 ? cumulativeTPV / cumulativeVolume : typicalPrice;
            vwapValues.push(vwap);
        }
        
        return {
            indicatorId: 'anchoredVwap',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: vwapValues[i] })),
        };
    },
});

// VWMA - Volume Weighted Moving Average (TradingView max, requested)
registerIndicator({
    id: 'vwma',
    name: 'Volume Weighted Moving Average',
    shortName: 'VWMA',
    placement: 'overlay',
    defaultParams: { period: 20 },
    paramLabels: { period: 'Period' },
    compute: (bars, params) => {
        const period = params.period as number;
        const vwmaValues: number[] = [];
        for (let i = 0; i < bars.length; i++) {
            if (i < period - 1) { vwmaValues.push(NaN); continue; }
            const slice = bars.slice(i - period + 1, i + 1);
            const pvSum = slice.reduce((s, b) => s + b.close * b.volume, 0);
            const vSum = slice.reduce((s, b) => s + b.volume, 0);
            vwmaValues.push(vSum > 0 ? pvSum / vSum : NaN);
        }
        return {
            indicatorId: 'vwma',
            series: bars.map((bar, i) => ({ timestamp: bar.timestamp, value: vwmaValues[i] })),
        };
    },
});

export { indicatorRegistry };

