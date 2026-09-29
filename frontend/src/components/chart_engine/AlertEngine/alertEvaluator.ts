/**
 * Alert Evaluator
 * Deterministic condition evaluation logic for all alert types
 */

import type { OHLCVBar, IndicatorOutput } from '../types';
import type { Alert, AlertCondition, AlertTriggerEvent } from './alertTypes';
import { generateHistoryId } from './alertTypes';

// =============================================================================
// EVALUATION RESULT
// =============================================================================

export interface EvaluationResult {
    triggered: boolean;
    currentState: boolean;  // Current state of condition
    message: string;
    price: number;
}

// =============================================================================
// MAIN EVALUATOR
// =============================================================================

export function evaluateAlert(
    alert: Alert,
    bars: OHLCVBar[],
    indicatorOutputs: Map<string, IndicatorOutput>
): EvaluationResult {
    if (bars.length === 0) {
        return { triggered: false, currentState: false, message: '', price: 0 };
    }

    const currentBar = bars[bars.length - 1];
    const previousBar = bars.length > 1 ? bars[bars.length - 2] : null;
    const currentPrice = currentBar.close;

    const result = evaluateCondition(
        alert.condition,
        currentBar,
        previousBar,
        bars,
        indicatorOutputs,
        alert.lastState
    );

    // Edge detection: trigger only on state transition
    const triggered = result.currentState && (alert.lastState === false || alert.lastState === null);

    // Check cooldown
    if (triggered && alert.lastTriggerTime) {
        const timeSinceLastTrigger = Date.now() - alert.lastTriggerTime;
        if (timeSinceLastTrigger < alert.cooldownMs) {
            return { ...result, triggered: false, price: currentPrice };
        }
    }

    return { ...result, triggered, price: currentPrice };
}

// =============================================================================
// CONDITION EVALUATOR
// =============================================================================

function evaluateCondition(
    condition: AlertCondition,
    currentBar: OHLCVBar,
    previousBar: OHLCVBar | null,
    bars: OHLCVBar[],
    indicatorOutputs: Map<string, IndicatorOutput>,
    lastState: boolean | null
): Omit<EvaluationResult, 'triggered'> {
    const currentPrice = currentBar.close;

    switch (condition.type) {
        case 'price_cross_above': {
            const currentState = currentPrice > condition.threshold;
            const message = `Price crossed above $${condition.threshold.toFixed(2)} (now $${currentPrice.toFixed(2)})`;
            return { currentState, message, price: currentPrice };
        }

        case 'price_cross_below': {
            const currentState = currentPrice < condition.threshold;
            const message = `Price crossed below $${condition.threshold.toFixed(2)} (now $${currentPrice.toFixed(2)})`;
            return { currentState, message, price: currentPrice };
        }

        case 'price_enter_range': {
            const currentState = currentPrice >= condition.lower && currentPrice <= condition.upper;
            const message = `Price entered range $${condition.lower.toFixed(2)} - $${condition.upper.toFixed(2)} (now $${currentPrice.toFixed(2)})`;
            return { currentState, message, price: currentPrice };
        }

        case 'price_exit_range': {
            const currentState = currentPrice < condition.lower || currentPrice > condition.upper;
            const message = `Price exited range $${condition.lower.toFixed(2)} - $${condition.upper.toFixed(2)} (now $${currentPrice.toFixed(2)})`;
            return { currentState, message, price: currentPrice };
        }

        case 'price_percent_change': {
            const lookbackBars = Math.ceil(condition.period / getTimeframeMins(bars));
            if (bars.length < lookbackBars + 1) {
                return { currentState: false, message: 'Insufficient data', price: currentPrice };
            }
            
            const referencePrice = bars[bars.length - 1 - lookbackBars].close;
            const percentChange = ((currentPrice - referencePrice) / referencePrice) * 100;
            
            let currentState = false;
            if (condition.direction === 'up') {
                currentState = percentChange >= condition.percent;
            } else if (condition.direction === 'down') {
                currentState = percentChange <= -condition.percent;
            } else {
                currentState = Math.abs(percentChange) >= condition.percent;
            }
            
            const message = `Price moved ${percentChange.toFixed(2)}% (target: ${condition.percent}% ${condition.direction})`;
            return { currentState, message, price: currentPrice };
        }

        case 'indicator_cross_above':
        case 'indicator_cross_below': {
            const output = indicatorOutputs.get(condition.indicatorId);
            if (!output || output.series.length < 2) {
                return { currentState: false, message: 'Indicator not available', price: currentPrice };
            }
            
            const currentValue = output.series[output.series.length - 1].value;
            const isAbove = condition.type === 'indicator_cross_above';
            const currentState = isAbove 
                ? currentValue > condition.threshold 
                : currentValue < condition.threshold;
            
            const direction = isAbove ? 'above' : 'below';
            const message = `${condition.indicatorType} crossed ${direction} ${condition.threshold} (now ${currentValue.toFixed(2)})`;
            return { currentState, message, price: currentPrice };
        }

        case 'indicator_enter_zone':
        case 'indicator_exit_zone': {
            const output = indicatorOutputs.get(condition.indicatorId);
            if (!output || output.series.length < 1) {
                return { currentState: false, message: 'Indicator not available', price: currentPrice };
            }
            
            const currentValue = output.series[output.series.length - 1].value;
            let inZone = false;
            
            if (condition.zone === 'overbought') {
                inZone = currentValue > (condition.upper || 70);
            } else if (condition.zone === 'oversold') {
                inZone = currentValue < (condition.lower || 30);
            } else {
                inZone = currentValue >= (condition.lower || 0) && currentValue <= (condition.upper || 100);
            }
            
            const currentState = condition.type === 'indicator_enter_zone' ? inZone : !inZone;
            const action = condition.type === 'indicator_enter_zone' ? 'entered' : 'exited';
            const message = `${condition.indicatorType} ${action} ${condition.zone} zone (now ${currentValue.toFixed(2)})`;
            return { currentState, message, price: currentPrice };
        }

        case 'ma_crossover':
        case 'ma_crossunder': {
            // Need to compute or find the MAs in indicator outputs
            const fastKey = `${condition.fastMA.type}_${condition.fastMA.period}`;
            const slowKey = `${condition.slowMA.type}_${condition.slowMA.period}`;
            
            const fastOutput = Array.from(indicatorOutputs.values()).find(
                o => o.indicatorId === `${condition.fastMA.type}_${condition.fastMA.period}` ||
                     (o.indicatorId.startsWith(condition.fastMA.type) &&
                      o.indicatorId.endsWith(String(condition.fastMA.period)))
            );
            const slowOutput = Array.from(indicatorOutputs.values()).find(
                o => o.indicatorId === `${condition.slowMA.type}_${condition.slowMA.period}` ||
                     (o.indicatorId.startsWith(condition.slowMA.type) &&
                      o.indicatorId.endsWith(String(condition.slowMA.period)))
            );
            
            if (!fastOutput || !slowOutput || fastOutput.series.length < 2 || slowOutput.series.length < 2) {
                return { currentState: false, message: 'MA indicators not available', price: currentPrice };
            }
            
            const fastCurrent = fastOutput.series[fastOutput.series.length - 1].value;
            const slowCurrent = slowOutput.series[slowOutput.series.length - 1].value;
            
            const isCrossover = condition.type === 'ma_crossover';
            const currentState = isCrossover 
                ? fastCurrent > slowCurrent 
                : fastCurrent < slowCurrent;
            
            const action = isCrossover ? 'crossed above' : 'crossed below';
            const message = `${condition.fastMA.type}(${condition.fastMA.period}) ${action} ${condition.slowMA.type}(${condition.slowMA.period})`;
            return { currentState, message, price: currentPrice };
        }

        case 'volume_spike': {
            if (bars.length < condition.period + 1) {
                return { currentState: false, message: 'Insufficient data', price: currentPrice };
            }
            
            const recentBars = bars.slice(-condition.period - 1, -1);
            const avgVolume = recentBars.reduce((sum, b) => sum + b.volume, 0) / condition.period;
            const currentVolume = currentBar.volume;
            const ratio = currentVolume / avgVolume;
            
            const currentState = ratio >= condition.multiplier;
            const message = `Volume spike: ${ratio.toFixed(1)}x average (threshold: ${condition.multiplier}x)`;
            return { currentState, message, price: currentPrice };
        }

        case 'candle_pattern': {
            if (!previousBar) {
                return { currentState: false, message: 'Insufficient data', price: currentPrice };
            }
            
            const pattern = detectCandlePattern(currentBar, previousBar, condition.pattern);
            const currentState = pattern.detected && 
                (!condition.direction || pattern.direction === condition.direction);
            
            const message = currentState 
                ? `${condition.direction || ''} ${condition.pattern} pattern detected`
                : '';
            return { currentState, message, price: currentPrice };
        }

        default:
            return { currentState: false, message: 'Unknown condition type', price: currentPrice };
    }
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function getTimeframeMins(bars: OHLCVBar[]): number {
    if (bars.length < 2) return 1;
    const diff = bars[1].timestamp - bars[0].timestamp;
    return Math.round(diff / 60000);
}

interface PatternResult {
    detected: boolean;
    direction?: 'bullish' | 'bearish';
}

function detectCandlePattern(
    current: OHLCVBar, 
    previous: OHLCVBar, 
    pattern: string
): PatternResult {
    const body = Math.abs(current.close - current.open);
    const range = current.high - current.low;
    const upperWick = current.high - Math.max(current.open, current.close);
    const lowerWick = Math.min(current.open, current.close) - current.low;
    const isBullish = current.close > current.open;

    switch (pattern) {
        case 'doji': {
            // Body is very small compared to range
            const isDoji = body < range * 0.1 && range > 0;
            return { detected: isDoji };
        }

        case 'hammer': {
            // Small body at top, long lower wick
            const isHammer = lowerWick >= body * 2 && upperWick < body * 0.5 && body < range * 0.3;
            return { detected: isHammer, direction: isHammer ? 'bullish' : undefined };
        }

        case 'engulfing': {
            // Current candle completely engulfs previous
            const prevBody = Math.abs(previous.close - previous.open);
            const prevBullish = previous.close > previous.open;
            
            const isBullishEngulfing = !prevBullish && isBullish && 
                current.open < previous.close && current.close > previous.open;
            const isBearishEngulfing = prevBullish && !isBullish && 
                current.open > previous.close && current.close < previous.open;
            
            if (isBullishEngulfing) return { detected: true, direction: 'bullish' };
            if (isBearishEngulfing) return { detected: true, direction: 'bearish' };
            return { detected: false };
        }

        case 'pinbar': {
            // Very small body, long wick on one side
            const isBullishPin = body < range * 0.2 && lowerWick >= range * 0.6;
            const isBearishPin = body < range * 0.2 && upperWick >= range * 0.6;
            
            if (isBullishPin) return { detected: true, direction: 'bullish' };
            if (isBearishPin) return { detected: true, direction: 'bearish' };
            return { detected: false };
        }

        case 'inside_bar': {
            // Current high/low completely within previous high/low
            const isInside = current.high < previous.high && current.low > previous.low;
            return { detected: isInside };
        }

        default:
            return { detected: false };
    }
}

// =============================================================================
// CREATE TRIGGER EVENT
// =============================================================================

export function createTriggerEvent(alert: Alert, result: EvaluationResult): AlertTriggerEvent {
    return {
        alertId: alert.id,
        timestamp: Date.now(),
        price: result.price,
        message: result.message,
        conditionMet: alert.condition,
    };
}
