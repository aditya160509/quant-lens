/**
 * Trading Strategies Engine
 * Rule-based systems that generate BUY/SELL signals on the chart
 */

import type { OHLCVBar } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export type SignalType = 'buy' | 'sell' | 'hold';

export interface TradeSignal {
    type: SignalType;
    index: number;
    price: number;
    timestamp: number;
    strategy: string;
    confidence: number; // 0-1
    reason?: string;
}

export interface StrategyResult {
    signals: TradeSignal[];
    metrics?: {
        totalSignals: number;
        buySignals: number;
        sellSignals: number;
    };
}

export interface TradingStrategy {
    id: string;
    name: string;
    displayName: string;
    description: string;
    complexity: number; // 1-3 stars
    category: 'momentum' | 'trend' | 'volatility' | 'oscillator' | 'breakout' | 'reversal';
    params: Record<string, { default: number; min: number; max: number; step: number; label: string }>;
    compute: (bars: OHLCVBar[], params: Record<string, number>) => StrategyResult;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function sma(values: number[], period: number): number[] {
    const result: number[] = [];
    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            result.push(NaN);
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += values[i - j];
            }
            result.push(sum / period);
        }
    }
    return result;
}

function ema(values: number[], period: number): number[] {
    const result: number[] = [];
    const multiplier = 2 / (period + 1);
    
    for (let i = 0; i < values.length; i++) {
        if (i === 0) {
            result.push(values[0]);
        } else {
            result.push((values[i] - result[i - 1]) * multiplier + result[i - 1]);
        }
    }
    return result;
}

function standardDeviation(values: number[], period: number): number[] {
    const result: number[] = [];
    const means = sma(values, period);
    
    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            result.push(NaN);
        } else {
            let sumSquares = 0;
            for (let j = 0; j < period; j++) {
                sumSquares += Math.pow(values[i - j] - means[i], 2);
            }
            result.push(Math.sqrt(sumSquares / period));
        }
    }
    return result;
}

function rsi(closes: number[], period: number): number[] {
    const gains: number[] = [];
    const losses: number[] = [];
    const result: number[] = [];

    for (let i = 0; i < closes.length; i++) {
        if (i === 0) {
            gains.push(0);
            losses.push(0);
            result.push(50);
            continue;
        }

        const change = closes[i] - closes[i - 1];
        gains.push(change > 0 ? change : 0);
        losses.push(change < 0 ? -change : 0);

        if (i < period) {
            result.push(50);
            continue;
        }

        let avgGain = 0;
        let avgLoss = 0;
        for (let j = 0; j < period; j++) {
            avgGain += gains[i - j];
            avgLoss += losses[i - j];
        }
        avgGain /= period;
        avgLoss /= period;

        if (avgLoss === 0) {
            result.push(100);
        } else {
            const rs = avgGain / avgLoss;
            result.push(100 - (100 / (1 + rs)));
        }
    }

    return result;
}

function macd(closes: number[], fastPeriod: number, slowPeriod: number, signalPeriod: number) {
    const fastEma = ema(closes, fastPeriod);
    const slowEma = ema(closes, slowPeriod);
    const macdLine = fastEma.map((f, i) => f - slowEma[i]);
    const signalLine = ema(macdLine, signalPeriod);
    const histogram = macdLine.map((m, i) => m - signalLine[i]);
    return { macdLine, signalLine, histogram };
}

function stochastic(bars: OHLCVBar[], kPeriod: number, dPeriod: number, smooth: number) {
    const rawK: number[] = [];
    
    for (let i = 0; i < bars.length; i++) {
        if (i < kPeriod - 1) {
            rawK.push(50);
            continue;
        }
        
        let lowestLow = Infinity;
        let highestHigh = -Infinity;
        for (let j = 0; j < kPeriod; j++) {
            lowestLow = Math.min(lowestLow, bars[i - j].low);
            highestHigh = Math.max(highestHigh, bars[i - j].high);
        }
        
        const range = highestHigh - lowestLow;
        if (range === 0) {
            rawK.push(50);
        } else {
            rawK.push(((bars[i].close - lowestLow) / range) * 100);
        }
    }
    
    const k = sma(rawK, smooth);
    const d = sma(k, dPeriod);
    
    return { k, d };
}

function atr(bars: OHLCVBar[], period: number): number[] {
    const trueRanges: number[] = [];
    
    for (let i = 0; i < bars.length; i++) {
        if (i === 0) {
            trueRanges.push(bars[i].high - bars[i].low);
        } else {
            const tr = Math.max(
                bars[i].high - bars[i].low,
                Math.abs(bars[i].high - bars[i - 1].close),
                Math.abs(bars[i].low - bars[i - 1].close)
            );
            trueRanges.push(tr);
        }
    }
    
    return sma(trueRanges, period);
}

function adx(bars: OHLCVBar[], period: number): number[] {
    const plusDM: number[] = [];
    const minusDM: number[] = [];
    const trueRanges: number[] = [];
    
    for (let i = 0; i < bars.length; i++) {
        if (i === 0) {
            plusDM.push(0);
            minusDM.push(0);
            trueRanges.push(bars[i].high - bars[i].low);
            continue;
        }
        
        const upMove = bars[i].high - bars[i - 1].high;
        const downMove = bars[i - 1].low - bars[i].low;
        
        plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
        minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
        
        trueRanges.push(Math.max(
            bars[i].high - bars[i].low,
            Math.abs(bars[i].high - bars[i - 1].close),
            Math.abs(bars[i].low - bars[i - 1].close)
        ));
    }
    
    const smoothedTR = ema(trueRanges, period);
    const smoothedPlusDM = ema(plusDM, period);
    const smoothedMinusDM = ema(minusDM, period);
    
    const plusDI = smoothedPlusDM.map((dm, i) => (dm / (smoothedTR[i] || 1)) * 100);
    const minusDI = smoothedMinusDM.map((dm, i) => (dm / (smoothedTR[i] || 1)) * 100);
    
    const dx = plusDI.map((pdi, i) => {
        const sum = pdi + minusDI[i];
        return sum === 0 ? 0 : (Math.abs(pdi - minusDI[i]) / sum) * 100;
    });
    
    return ema(dx, period);
}

// =============================================================================
// STRATEGIES
// =============================================================================

export const MACrossoverStrategy: TradingStrategy = {
    id: 'maCrossover',
    name: 'Moving Avg Cross',
    displayName: 'MA Crossover System',
    description: 'Generates signals when fast MA crosses slow MA.',
    complexity: 1,
    category: 'trend',
    params: {
        fastPeriod: { default: 10, min: 2, max: 50, step: 1, label: 'Fast Period' },
        slowPeriod: { default: 20, min: 5, max: 200, step: 1, label: 'Slow Period' },
    },
    compute: (bars, params) => {
        const closes = bars.map(b => b.close);
        const fastMA = sma(closes, params.fastPeriod);
        const slowMA = sma(closes, params.slowPeriod);
        
        const signals: TradeSignal[] = [];
        
        for (let i = 1; i < bars.length; i++) {
            if (isNaN(fastMA[i]) || isNaN(slowMA[i])) continue;
            
            // Bullish crossover
            if (fastMA[i - 1] <= slowMA[i - 1] && fastMA[i] > slowMA[i]) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'maCrossover',
                    confidence: 0.7,
                    reason: 'Fast MA crossed above Slow MA',
                });
            }
            // Bearish crossover
            else if (fastMA[i - 1] >= slowMA[i - 1] && fastMA[i] < slowMA[i]) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'maCrossover',
                    confidence: 0.7,
                    reason: 'Fast MA crossed below Slow MA',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const DualMACrossStrategy: TradingStrategy = {
    id: 'dualMACross',
    name: 'Moving Avg 2 Line Cross',
    displayName: 'Dual MA Cross System',
    description: 'Two-line MA crossover with confirmation.',
    complexity: 1,
    category: 'trend',
    params: {
        shortPeriod: { default: 5, min: 2, max: 20, step: 1, label: 'Short Period' },
        mediumPeriod: { default: 10, min: 5, max: 50, step: 1, label: 'Medium Period' },
        longPeriod: { default: 20, min: 10, max: 100, step: 1, label: 'Long Period' },
    },
    compute: (bars, params) => {
        const closes = bars.map(b => b.close);
        const shortMA = sma(closes, params.shortPeriod);
        const mediumMA = sma(closes, params.mediumPeriod);
        const longMA = sma(closes, params.longPeriod);
        
        const signals: TradeSignal[] = [];
        
        for (let i = 1; i < bars.length; i++) {
            if (isNaN(longMA[i])) continue;
            
            // All MAs aligned bullish
            if (shortMA[i] > mediumMA[i] && mediumMA[i] > longMA[i] &&
                (shortMA[i - 1] <= mediumMA[i - 1] || mediumMA[i - 1] <= longMA[i - 1])) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'dualMACross',
                    confidence: 0.8,
                    reason: 'MAs aligned bullish',
                });
            }
            // All MAs aligned bearish
            else if (shortMA[i] < mediumMA[i] && mediumMA[i] < longMA[i] &&
                     (shortMA[i - 1] >= mediumMA[i - 1] || mediumMA[i - 1] >= longMA[i - 1])) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'dualMACross',
                    confidence: 0.8,
                    reason: 'MAs aligned bearish',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const RSIStrategy: TradingStrategy = {
    id: 'rsiStrategy',
    name: 'RSI Strategy',
    displayName: 'RSI Extremes System',
    description: 'Signals on RSI overbought/oversold levels.',
    complexity: 2,
    category: 'oscillator',
    params: {
        period: { default: 14, min: 2, max: 50, step: 1, label: 'Period' },
        oversold: { default: 30, min: 10, max: 40, step: 1, label: 'Oversold' },
        overbought: { default: 70, min: 60, max: 90, step: 1, label: 'Overbought' },
    },
    compute: (bars, params) => {
        const closes = bars.map(b => b.close);
        const rsiValues = rsi(closes, params.period);
        
        const signals: TradeSignal[] = [];
        
        for (let i = 1; i < bars.length; i++) {
            // RSI crossing above oversold
            if (rsiValues[i - 1] < params.oversold && rsiValues[i] >= params.oversold) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'rsiStrategy',
                    confidence: 0.65,
                    reason: `RSI crossed above ${params.oversold}`,
                });
            }
            // RSI crossing below overbought
            else if (rsiValues[i - 1] > params.overbought && rsiValues[i] <= params.overbought) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'rsiStrategy',
                    confidence: 0.65,
                    reason: `RSI crossed below ${params.overbought}`,
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const MACDStrategy: TradingStrategy = {
    id: 'macdStrategy',
    name: 'MACD Strategy',
    displayName: 'MACD Signal System',
    description: 'MACD line crossing signal line.',
    complexity: 2,
    category: 'momentum',
    params: {
        fastPeriod: { default: 12, min: 5, max: 30, step: 1, label: 'Fast Period' },
        slowPeriod: { default: 26, min: 10, max: 50, step: 1, label: 'Slow Period' },
        signalPeriod: { default: 9, min: 3, max: 20, step: 1, label: 'Signal Period' },
    },
    compute: (bars, params) => {
        const closes = bars.map(b => b.close);
        const { macdLine, signalLine } = macd(closes, params.fastPeriod, params.slowPeriod, params.signalPeriod);
        
        const signals: TradeSignal[] = [];
        
        for (let i = params.slowPeriod; i < bars.length; i++) {
            // MACD crosses above signal
            if (macdLine[i - 1] <= signalLine[i - 1] && macdLine[i] > signalLine[i]) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'macdStrategy',
                    confidence: 0.7,
                    reason: 'MACD crossed above signal',
                });
            }
            // MACD crosses below signal
            else if (macdLine[i - 1] >= signalLine[i - 1] && macdLine[i] < signalLine[i]) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'macdStrategy',
                    confidence: 0.7,
                    reason: 'MACD crossed below signal',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const BollingerBandsStrategy: TradingStrategy = {
    id: 'bollingerBands',
    name: 'Bollinger Bands Strategy',
    displayName: 'Band Breakout System',
    description: 'Signals on Bollinger Band touches/breakouts.',
    complexity: 2,
    category: 'volatility',
    params: {
        period: { default: 20, min: 5, max: 50, step: 1, label: 'Period' },
        stdDev: { default: 2, min: 1, max: 4, step: 0.5, label: 'Std Dev' },
    },
    compute: (bars, params) => {
        const closes = bars.map(b => b.close);
        const middle = sma(closes, params.period);
        const std = standardDeviation(closes, params.period);
        
        const signals: TradeSignal[] = [];
        
        for (let i = params.period; i < bars.length; i++) {
            const upper = middle[i] + params.stdDev * std[i];
            const lower = middle[i] - params.stdDev * std[i];
            
            // Price touches lower band
            if (bars[i].low <= lower && bars[i - 1].low > (middle[i - 1] - params.stdDev * std[i - 1])) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'bollingerBands',
                    confidence: 0.6,
                    reason: 'Price touched lower band',
                });
            }
            // Price touches upper band
            else if (bars[i].high >= upper && bars[i - 1].high < (middle[i - 1] + params.stdDev * std[i - 1])) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'bollingerBands',
                    confidence: 0.6,
                    reason: 'Price touched upper band',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const StochasticSlowStrategy: TradingStrategy = {
    id: 'stochasticSlow',
    name: 'Stochastic Slow Strategy',
    displayName: 'Slow Stochastic System',
    description: 'Stochastic K/D crossover signals.',
    complexity: 2,
    category: 'oscillator',
    params: {
        kPeriod: { default: 14, min: 5, max: 30, step: 1, label: 'K Period' },
        dPeriod: { default: 3, min: 1, max: 10, step: 1, label: 'D Period' },
        smooth: { default: 3, min: 1, max: 10, step: 1, label: 'Smooth' },
        oversold: { default: 20, min: 5, max: 30, step: 1, label: 'Oversold' },
        overbought: { default: 80, min: 70, max: 95, step: 1, label: 'Overbought' },
    },
    compute: (bars, params) => {
        const { k, d } = stochastic(bars, params.kPeriod, params.dPeriod, params.smooth);
        
        const signals: TradeSignal[] = [];
        
        for (let i = params.kPeriod + params.dPeriod; i < bars.length; i++) {
            // K crosses above D in oversold zone
            if (k[i - 1] <= d[i - 1] && k[i] > d[i] && k[i] < params.oversold + 10) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'stochasticSlow',
                    confidence: 0.65,
                    reason: 'K crossed above D in oversold',
                });
            }
            // K crosses below D in overbought zone
            else if (k[i - 1] >= d[i - 1] && k[i] < d[i] && k[i] > params.overbought - 10) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'stochasticSlow',
                    confidence: 0.65,
                    reason: 'K crossed below D in overbought',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const MomentumStrategy: TradingStrategy = {
    id: 'momentum',
    name: 'Momentum Strategy',
    displayName: 'Momentum Thrust System',
    description: 'Signals based on momentum indicator.',
    complexity: 2,
    category: 'momentum',
    params: {
        period: { default: 10, min: 3, max: 50, step: 1, label: 'Period' },
    },
    compute: (bars, params) => {
        const signals: TradeSignal[] = [];
        
        for (let i = params.period; i < bars.length; i++) {
            const momentum = bars[i].close - bars[i - params.period].close;
            const prevMomentum = bars[i - 1].close - bars[i - params.period - 1].close;
            
            // Momentum crosses above zero
            if (prevMomentum <= 0 && momentum > 0) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'momentum',
                    confidence: 0.6,
                    reason: 'Momentum crossed above zero',
                });
            }
            // Momentum crosses below zero
            else if (prevMomentum >= 0 && momentum < 0) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'momentum',
                    confidence: 0.6,
                    reason: 'Momentum crossed below zero',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const ConsecutiveUpDownStrategy: TradingStrategy = {
    id: 'consecutiveUpDown',
    name: 'Consecutive Up/Down Strategy',
    displayName: 'Momentum Streak System',
    description: 'Signals after consecutive up or down days.',
    complexity: 1,
    category: 'momentum',
    params: {
        consecutiveBars: { default: 3, min: 2, max: 7, step: 1, label: 'Consecutive Bars' },
    },
    compute: (bars, params) => {
        const signals: TradeSignal[] = [];
        
        for (let i = params.consecutiveBars; i < bars.length; i++) {
            let upCount = 0;
            let downCount = 0;
            
            for (let j = 0; j < params.consecutiveBars; j++) {
                const idx = i - j;
                if (bars[idx].close > bars[idx].open) upCount++;
                if (bars[idx].close < bars[idx].open) downCount++;
            }
            
            // All consecutive bars up - expecting reversal
            if (downCount === params.consecutiveBars) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'consecutiveUpDown',
                    confidence: 0.55,
                    reason: `${params.consecutiveBars} consecutive down bars`,
                });
            }
            // All consecutive bars down - expecting reversal
            else if (upCount === params.consecutiveBars) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'consecutiveUpDown',
                    confidence: 0.55,
                    reason: `${params.consecutiveBars} consecutive up bars`,
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const BarUpDownStrategy: TradingStrategy = {
    id: 'barUpDown',
    name: 'BarUpDn Strategy',
    displayName: 'Q360 Bar Direction System',
    description: 'Simple bar direction signals.',
    complexity: 1,
    category: 'trend',
    params: {},
    compute: (bars) => {
        const signals: TradeSignal[] = [];
        
        for (let i = 1; i < bars.length; i++) {
            const prev = bars[i - 1];
            const curr = bars[i];
            
            // Bar turned up
            if (prev.close <= prev.open && curr.close > curr.open) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: curr.close,
                    timestamp: curr.timestamp,
                    strategy: 'barUpDown',
                    confidence: 0.5,
                    reason: 'Bar turned bullish',
                });
            }
            // Bar turned down
            else if (prev.close >= prev.open && curr.close < curr.open) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: curr.close,
                    timestamp: curr.timestamp,
                    strategy: 'barUpDown',
                    confidence: 0.5,
                    reason: 'Bar turned bearish',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const InsideBarStrategy: TradingStrategy = {
    id: 'insideBar',
    name: 'Inside Bar Strategy',
    displayName: 'Consolidation Break System',
    description: 'Signals on inside bar breakouts.',
    complexity: 2,
    category: 'breakout',
    params: {},
    compute: (bars) => {
        const signals: TradeSignal[] = [];
        
        for (let i = 2; i < bars.length; i++) {
            const mother = bars[i - 2];
            const inside = bars[i - 1];
            const breakout = bars[i];
            
            // Check if middle bar is inside bar
            if (inside.high < mother.high && inside.low > mother.low) {
                // Bullish breakout
                if (breakout.close > mother.high) {
                    signals.push({
                        type: 'buy',
                        index: i,
                        price: breakout.close,
                        timestamp: breakout.timestamp,
                        strategy: 'insideBar',
                        confidence: 0.7,
                        reason: 'Inside bar bullish breakout',
                    });
                }
                // Bearish breakout
                else if (breakout.close < mother.low) {
                    signals.push({
                        type: 'sell',
                        index: i,
                        price: breakout.close,
                        timestamp: breakout.timestamp,
                        strategy: 'insideBar',
                        confidence: 0.7,
                        reason: 'Inside bar bearish breakout',
                    });
                }
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const OutsideBarStrategy: TradingStrategy = {
    id: 'outsideBar',
    name: 'Outside Bar Strategy',
    displayName: 'Expansion Bar System',
    description: 'Signals on outside bar patterns.',
    complexity: 2,
    category: 'breakout',
    params: {},
    compute: (bars) => {
        const signals: TradeSignal[] = [];
        
        for (let i = 1; i < bars.length; i++) {
            const prev = bars[i - 1];
            const curr = bars[i];
            
            // Outside bar (engulfs previous bar's range)
            if (curr.high > prev.high && curr.low < prev.low) {
                if (curr.close > curr.open) {
                    signals.push({
                        type: 'buy',
                        index: i,
                        price: curr.close,
                        timestamp: curr.timestamp,
                        strategy: 'outsideBar',
                        confidence: 0.65,
                        reason: 'Bullish outside bar',
                    });
                } else if (curr.close < curr.open) {
                    signals.push({
                        type: 'sell',
                        index: i,
                        price: curr.close,
                        timestamp: curr.timestamp,
                        strategy: 'outsideBar',
                        confidence: 0.65,
                        reason: 'Bearish outside bar',
                    });
                }
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const TrendCaptureStrategy: TradingStrategy = {
    id: 'trendCapture',
    name: 'Greedy Strategy',
    displayName: 'Trend Capture System',
    description: 'Aggressive trend following.',
    complexity: 1,
    category: 'trend',
    params: {
        period: { default: 10, min: 3, max: 30, step: 1, label: 'Period' },
    },
    compute: (bars, params) => {
        const closes = bars.map(b => b.close);
        const ma = sma(closes, params.period);
        
        const signals: TradeSignal[] = [];
        
        for (let i = params.period; i < bars.length; i++) {
            // Price above MA and rising
            if (bars[i].close > ma[i] && bars[i].close > bars[i - 1].close) {
                if (i === params.period || signals[signals.length - 1]?.type !== 'buy') {
                    signals.push({
                        type: 'buy',
                        index: i,
                        price: bars[i].close,
                        timestamp: bars[i].timestamp,
                        strategy: 'trendCapture',
                        confidence: 0.55,
                        reason: 'Price above MA and rising',
                    });
                }
            }
            // Price below MA and falling
            else if (bars[i].close < ma[i] && bars[i].close < bars[i - 1].close) {
                if (i === params.period || signals[signals.length - 1]?.type !== 'sell') {
                    signals.push({
                        type: 'sell',
                        index: i,
                        price: bars[i].close,
                        timestamp: bars[i].timestamp,
                        strategy: 'trendCapture',
                        confidence: 0.55,
                        reason: 'Price below MA and falling',
                    });
                }
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const ChannelBreakoutStrategy: TradingStrategy = {
    id: 'channelBreakout',
    name: 'Channel Breakout Strategy',
    displayName: 'Channel Break System',
    description: 'Price channel breakout signals.',
    complexity: 2,
    category: 'breakout',
    params: {
        period: { default: 20, min: 5, max: 50, step: 1, label: 'Period' },
    },
    compute: (bars, params) => {
        const signals: TradeSignal[] = [];
        
        for (let i = params.period; i < bars.length; i++) {
            let highestHigh = -Infinity;
            let lowestLow = Infinity;
            
            for (let j = 1; j <= params.period; j++) {
                highestHigh = Math.max(highestHigh, bars[i - j].high);
                lowestLow = Math.min(lowestLow, bars[i - j].low);
            }
            
            // Breakout above channel
            if (bars[i].close > highestHigh && bars[i - 1].close <= highestHigh) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'channelBreakout',
                    confidence: 0.7,
                    reason: `Breakout above ${params.period}-bar high`,
                });
            }
            // Breakdown below channel
            else if (bars[i].close < lowestLow && bars[i - 1].close >= lowestLow) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'channelBreakout',
                    confidence: 0.7,
                    reason: `Breakdown below ${params.period}-bar low`,
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const SupertrendStrategy: TradingStrategy = {
    id: 'supertrend',
    name: 'Supertrend Strategy',
    displayName: 'Supertrend Follow System',
    description: 'Trend following using Supertrend indicator.',
    complexity: 2,
    category: 'trend',
    params: {
        period: { default: 10, min: 5, max: 30, step: 1, label: 'ATR Period' },
        multiplier: { default: 3, min: 1, max: 5, step: 0.5, label: 'Multiplier' },
    },
    compute: (bars, params) => {
        const atrValues = atr(bars, params.period);
        const signals: TradeSignal[] = [];
        
        let trend = 1; // 1 = up, -1 = down
        let upperBand = 0;
        let lowerBand = 0;
        
        for (let i = params.period; i < bars.length; i++) {
            const hl2 = (bars[i].high + bars[i].low) / 2;
            const newUpper = hl2 + params.multiplier * atrValues[i];
            const newLower = hl2 - params.multiplier * atrValues[i];
            
            upperBand = bars[i - 1].close > upperBand ? Math.min(newUpper, upperBand) : newUpper;
            lowerBand = bars[i - 1].close < lowerBand ? Math.max(newLower, lowerBand) : newLower;
            
            const prevTrend = trend;
            
            if (bars[i].close > upperBand) {
                trend = 1;
            } else if (bars[i].close < lowerBand) {
                trend = -1;
            }
            
            // Trend changed
            if (trend !== prevTrend) {
                signals.push({
                    type: trend === 1 ? 'buy' : 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'supertrend',
                    confidence: 0.7,
                    reason: trend === 1 ? 'Supertrend turned bullish' : 'Supertrend turned bearish',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const ParabolicSARStrategy: TradingStrategy = {
    id: 'parabolicSar',
    name: 'Parabolic SAR Strategy',
    displayName: 'SAR Reversal System',
    description: 'Parabolic SAR trend reversal signals.',
    complexity: 2,
    category: 'reversal',
    params: {
        acceleration: { default: 0.02, min: 0.01, max: 0.1, step: 0.01, label: 'Acceleration' },
        maximum: { default: 0.2, min: 0.1, max: 0.5, step: 0.05, label: 'Maximum' },
    },
    compute: (bars, params) => {
        const signals: TradeSignal[] = [];
        
        let trend = 1;
        let sar = bars[0].low;
        let ep = bars[0].high;
        let af = params.acceleration;
        
        for (let i = 1; i < bars.length; i++) {
            const prevSar = sar;
            
            // Calculate new SAR
            sar = sar + af * (ep - sar);
            
            // Constrain SAR
            if (trend === 1) {
                sar = Math.min(sar, bars[i - 1].low);
                if (i > 1) sar = Math.min(sar, bars[i - 2].low);
            } else {
                sar = Math.max(sar, bars[i - 1].high);
                if (i > 1) sar = Math.max(sar, bars[i - 2].high);
            }
            
            // Check for trend reversal
            const prevTrend = trend;
            if (trend === 1 && bars[i].low < sar) {
                trend = -1;
                sar = ep;
                ep = bars[i].low;
                af = params.acceleration;
            } else if (trend === -1 && bars[i].high > sar) {
                trend = 1;
                sar = ep;
                ep = bars[i].high;
                af = params.acceleration;
            }
            
            // Update EP and AF
            if (trend === 1 && bars[i].high > ep) {
                ep = bars[i].high;
                af = Math.min(af + params.acceleration, params.maximum);
            } else if (trend === -1 && bars[i].low < ep) {
                ep = bars[i].low;
                af = Math.min(af + params.acceleration, params.maximum);
            }
            
            // Generate signal on trend change
            if (trend !== prevTrend) {
                signals.push({
                    type: trend === 1 ? 'buy' : 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'parabolicSar',
                    confidence: 0.65,
                    reason: trend === 1 ? 'SAR flipped bullish' : 'SAR flipped bearish',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const KeltnerChannelStrategy: TradingStrategy = {
    id: 'keltnerChannel',
    name: 'Keltner Channels Strategy',
    displayName: 'Keltner Flow System',
    description: 'Keltner Channel breakout signals.',
    complexity: 2,
    category: 'volatility',
    params: {
        emaPeriod: { default: 20, min: 5, max: 50, step: 1, label: 'EMA Period' },
        atrPeriod: { default: 10, min: 5, max: 30, step: 1, label: 'ATR Period' },
        multiplier: { default: 2, min: 1, max: 4, step: 0.5, label: 'Multiplier' },
    },
    compute: (bars, params) => {
        const closes = bars.map(b => b.close);
        const middle = ema(closes, params.emaPeriod);
        const atrValues = atr(bars, params.atrPeriod);
        
        const signals: TradeSignal[] = [];
        
        for (let i = Math.max(params.emaPeriod, params.atrPeriod); i < bars.length; i++) {
            const upper = middle[i] + params.multiplier * atrValues[i];
            const lower = middle[i] - params.multiplier * atrValues[i];
            
            // Breakout above upper channel
            if (bars[i].close > upper && bars[i - 1].close <= (middle[i - 1] + params.multiplier * atrValues[i - 1])) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'keltnerChannel',
                    confidence: 0.65,
                    reason: 'Breakout above Keltner upper',
                });
            }
            // Breakdown below lower channel
            else if (bars[i].close < lower && bars[i - 1].close >= (middle[i - 1] - params.multiplier * atrValues[i - 1])) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'keltnerChannel',
                    confidence: 0.65,
                    reason: 'Breakdown below Keltner lower',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const ADXBreakoutStrategy: TradingStrategy = {
    id: 'adxBreakout',
    name: 'Rob Booker – ADX Breakout',
    displayName: 'ADX Trend Strength System',
    description: 'ADX-based trend strength breakout.',
    complexity: 3,
    category: 'breakout',
    params: {
        adxPeriod: { default: 14, min: 5, max: 30, step: 1, label: 'ADX Period' },
        adxThreshold: { default: 25, min: 15, max: 40, step: 1, label: 'ADX Threshold' },
    },
    compute: (bars, params) => {
        const adxValues = adx(bars, params.adxPeriod);
        const signals: TradeSignal[] = [];
        
        for (let i = params.adxPeriod * 2; i < bars.length; i++) {
            // ADX crosses above threshold
            if (adxValues[i - 1] < params.adxThreshold && adxValues[i] >= params.adxThreshold) {
                // Determine direction
                const direction = bars[i].close > bars[i - 5].close ? 'buy' : 'sell';
                signals.push({
                    type: direction,
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'adxBreakout',
                    confidence: 0.75,
                    reason: `ADX crossed ${params.adxThreshold} (${direction === 'buy' ? 'bullish' : 'bearish'} trend)`,
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const PriceChannelStrategy: TradingStrategy = {
    id: 'priceChannel',
    name: 'Price Channel Strategy',
    displayName: 'Price Range System',
    description: 'Donchian-style price channel signals.',
    complexity: 2,
    category: 'breakout',
    params: {
        period: { default: 20, min: 5, max: 55, step: 1, label: 'Period' },
    },
    compute: (bars, params) => {
        const signals: TradeSignal[] = [];
        
        for (let i = params.period; i < bars.length; i++) {
            let channelHigh = -Infinity;
            let channelLow = Infinity;
            
            for (let j = 1; j <= params.period; j++) {
                channelHigh = Math.max(channelHigh, bars[i - j].high);
                channelLow = Math.min(channelLow, bars[i - j].low);
            }
            
            // New high
            if (bars[i].high > channelHigh) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'priceChannel',
                    confidence: 0.65,
                    reason: `New ${params.period}-bar high`,
                });
            }
            // New low
            else if (bars[i].low < channelLow) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'priceChannel',
                    confidence: 0.65,
                    reason: `New ${params.period}-bar low`,
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const VolatilityExpansionStrategy: TradingStrategy = {
    id: 'volatilityExpansion',
    name: 'Volty Expan Close Strategy',
    displayName: 'Volatility Expansion System',
    description: 'Volatility expansion breakout signals.',
    complexity: 3,
    category: 'volatility',
    params: {
        period: { default: 5, min: 2, max: 20, step: 1, label: 'Period' },
        multiplier: { default: 2, min: 1, max: 4, step: 0.5, label: 'Multiplier' },
    },
    compute: (bars, params) => {
        const atrValues = atr(bars, params.period);
        const signals: TradeSignal[] = [];
        
        for (let i = params.period + 1; i < bars.length; i++) {
            const moveUp = bars[i].close - bars[i - 1].close;
            const moveDown = bars[i - 1].close - bars[i].close;
            const threshold = params.multiplier * atrValues[i];
            
            if (moveUp > threshold) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'volatilityExpansion',
                    confidence: 0.7,
                    reason: `Volatility expansion up (${(moveUp / atrValues[i]).toFixed(1)}x ATR)`,
                });
            } else if (moveDown > threshold) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'volatilityExpansion',
                    confidence: 0.7,
                    reason: `Volatility expansion down (${(moveDown / atrValues[i]).toFixed(1)}x ATR)`,
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

export const PivotReversalStrategy: TradingStrategy = {
    id: 'pivotReversal',
    name: 'Pivot Reversal Strategy',
    displayName: 'Pivot Reversal System',
    description: 'Pivot point reversal signals.',
    complexity: 3,
    category: 'reversal',
    params: {
        leftBars: { default: 4, min: 2, max: 10, step: 1, label: 'Left Bars' },
        rightBars: { default: 2, min: 1, max: 5, step: 1, label: 'Right Bars' },
    },
    compute: (bars, params) => {
        const signals: TradeSignal[] = [];
        const lookback = params.leftBars + params.rightBars + 1;
        
        for (let i = lookback; i < bars.length; i++) {
            const pivotIndex = i - params.rightBars;
            const pivotBar = bars[pivotIndex];
            
            // Check for pivot high
            let isPivotHigh = true;
            for (let j = pivotIndex - params.leftBars; j < pivotIndex; j++) {
                if (bars[j].high >= pivotBar.high) isPivotHigh = false;
            }
            for (let j = pivotIndex + 1; j <= pivotIndex + params.rightBars; j++) {
                if (bars[j].high >= pivotBar.high) isPivotHigh = false;
            }
            
            // Check for pivot low
            let isPivotLow = true;
            for (let j = pivotIndex - params.leftBars; j < pivotIndex; j++) {
                if (bars[j].low <= pivotBar.low) isPivotLow = false;
            }
            for (let j = pivotIndex + 1; j <= pivotIndex + params.rightBars; j++) {
                if (bars[j].low <= pivotBar.low) isPivotLow = false;
            }
            
            if (isPivotHigh) {
                signals.push({
                    type: 'sell',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'pivotReversal',
                    confidence: 0.75,
                    reason: 'Pivot high confirmed',
                });
            }
            
            if (isPivotLow) {
                signals.push({
                    type: 'buy',
                    index: i,
                    price: bars[i].close,
                    timestamp: bars[i].timestamp,
                    strategy: 'pivotReversal',
                    confidence: 0.75,
                    reason: 'Pivot low confirmed',
                });
            }
        }
        
        return {
            signals,
            metrics: {
                totalSignals: signals.length,
                buySignals: signals.filter(s => s.type === 'buy').length,
                sellSignals: signals.filter(s => s.type === 'sell').length,
            },
        };
    },
};

// =============================================================================
// STRATEGY REGISTRY
// =============================================================================

export const TRADING_STRATEGIES: TradingStrategy[] = [
    // Easy (Complexity 1)
    BarUpDownStrategy,
    MACrossoverStrategy,
    DualMACrossStrategy,
    ConsecutiveUpDownStrategy,
    TrendCaptureStrategy,
    
    // Medium (Complexity 2)
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    StochasticSlowStrategy,
    MomentumStrategy,
    InsideBarStrategy,
    OutsideBarStrategy,
    ChannelBreakoutStrategy,
    SupertrendStrategy,
    ParabolicSARStrategy,
    KeltnerChannelStrategy,
    PriceChannelStrategy,
    
    // Hard (Complexity 3)
    ADXBreakoutStrategy,
    VolatilityExpansionStrategy,
    PivotReversalStrategy,
];

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

export function getStrategyById(id: string): TradingStrategy | undefined {
    return TRADING_STRATEGIES.find(s => s.id === id);
}

export function getStrategiesByCategory(category: TradingStrategy['category']): TradingStrategy[] {
    return TRADING_STRATEGIES.filter(s => s.category === category);
}

export function getStrategiesByComplexity(complexity: number): TradingStrategy[] {
    return TRADING_STRATEGIES.filter(s => s.complexity === complexity);
}

export function runStrategies(
    bars: OHLCVBar[],
    strategyIds: string[],
    paramsOverrides?: Record<string, Record<string, number>>
): Map<string, StrategyResult> {
    const results = new Map<string, StrategyResult>();
    
    for (const id of strategyIds) {
        const strategy = getStrategyById(id);
        if (!strategy) continue;
        
        const params: Record<string, number> = {};
        for (const [key, config] of Object.entries(strategy.params)) {
            params[key] = paramsOverrides?.[id]?.[key] ?? config.default;
        }
        
        results.set(id, strategy.compute(bars, params));
    }
    
    return results;
}
