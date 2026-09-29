/**
 * Candlestick Pattern Scanner
 * Detects classic candlestick patterns from OHLCV data
 */

import type { OHLCVBar } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export interface PatternMatch {
    pattern: string;
    name: string;
    type: 'bullish' | 'bearish' | 'neutral';
    startIndex: number;
    endIndex: number;
    reliability: 'low' | 'medium' | 'high';
    description: string;
}

export interface CandlestickPattern {
    id: string;
    name: string;
    displayName: string;
    type: 'bullish' | 'bearish' | 'neutral';
    complexity: number; // 1-3 stars
    category: 'single' | 'double' | 'triple' | 'complex';
    detect: (bars: OHLCVBar[], index: number) => boolean;
    description: string;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function bodySize(bar: OHLCVBar): number {
    return Math.abs(bar.close - bar.open);
}

function totalRange(bar: OHLCVBar): number {
    return bar.high - bar.low;
}

function upperWick(bar: OHLCVBar): number {
    return bar.high - Math.max(bar.open, bar.close);
}

function lowerWick(bar: OHLCVBar): number {
    return Math.min(bar.open, bar.close) - bar.low;
}

function isBullish(bar: OHLCVBar): boolean {
    return bar.close > bar.open;
}

function isBearish(bar: OHLCVBar): boolean {
    return bar.close < bar.open;
}

function isDoji(bar: OHLCVBar, threshold = 0.1): boolean {
    const range = totalRange(bar);
    if (range === 0) return true;
    return bodySize(bar) / range < threshold;
}

function isMarubozu(bar: OHLCVBar, threshold = 0.05): boolean {
    const range = totalRange(bar);
    if (range === 0) return false;
    const upperPercent = upperWick(bar) / range;
    const lowerPercent = lowerWick(bar) / range;
    return upperPercent < threshold && lowerPercent < threshold;
}

function hasLongUpperWick(bar: OHLCVBar, ratio = 2): boolean {
    return upperWick(bar) > bodySize(bar) * ratio;
}

function hasLongLowerWick(bar: OHLCVBar, ratio = 2): boolean {
    return lowerWick(bar) > bodySize(bar) * ratio;
}

function isSmallBody(bar: OHLCVBar, avgBodySize: number, threshold = 0.3): boolean {
    return bodySize(bar) < avgBodySize * threshold;
}

function isLargeBody(bar: OHLCVBar, avgBodySize: number, threshold = 1.5): boolean {
    return bodySize(bar) > avgBodySize * threshold;
}

function getAvgBodySize(bars: OHLCVBar[], lookback = 10): number {
    const slice = bars.slice(-lookback);
    return slice.reduce((sum, b) => sum + bodySize(b), 0) / slice.length;
}

function hasGapUp(current: OHLCVBar, previous: OHLCVBar): boolean {
    return current.low > previous.high;
}

function hasGapDown(current: OHLCVBar, previous: OHLCVBar): boolean {
    return current.high < previous.low;
}

// =============================================================================
// SINGLE CANDLE PATTERNS
// =============================================================================

export const DojiPattern: CandlestickPattern = {
    id: 'doji',
    name: 'Doji',
    displayName: 'Indecision Candle',
    type: 'neutral',
    complexity: 1,
    category: 'single',
    description: 'A candle with nearly equal open and close, signaling market indecision.',
    detect: (bars, index) => {
        if (index < 0 || index >= bars.length) return false;
        return isDoji(bars[index]);
    },
};

export const HammerPattern: CandlestickPattern = {
    id: 'hammer',
    name: 'Hammer',
    displayName: 'Hammer Reversal',
    type: 'bullish',
    complexity: 1,
    category: 'single',
    description: 'Small body at top with long lower wick, bullish reversal signal after downtrend.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const bar = bars[index];
        const prev = bars[index - 1];
        
        // Must be in downtrend
        if (bar.close >= prev.close) return false;
        
        // Long lower wick, small body at top
        const range = totalRange(bar);
        if (range === 0) return false;
        
        const lowerWickSize = lowerWick(bar);
        const body = bodySize(bar);
        const upperWickSize = upperWick(bar);
        
        return (
            lowerWickSize >= body * 2 &&
            upperWickSize < body * 0.5 &&
            body > 0
        );
    },
};

export const ShootingStarPattern: CandlestickPattern = {
    id: 'shootingStar',
    name: 'Shooting Star',
    displayName: 'Star Reversal',
    type: 'bearish',
    complexity: 1,
    category: 'single',
    description: 'Small body at bottom with long upper wick, bearish reversal after uptrend.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const bar = bars[index];
        const prev = bars[index - 1];
        
        // Must be in uptrend
        if (bar.close <= prev.close) return false;
        
        const range = totalRange(bar);
        if (range === 0) return false;
        
        const upperWickSize = upperWick(bar);
        const body = bodySize(bar);
        const lowerWickSize = lowerWick(bar);
        
        return (
            upperWickSize >= body * 2 &&
            lowerWickSize < body * 0.5 &&
            body > 0
        );
    },
};

export const MarubozuPattern: CandlestickPattern = {
    id: 'marubozu',
    name: 'Marubozu',
    displayName: 'Full Body Candle',
    type: 'neutral', // Direction depends on candle color
    complexity: 1,
    category: 'single',
    description: 'Candle with no or tiny wicks, showing strong momentum.',
    detect: (bars, index) => {
        if (index < 0 || index >= bars.length) return false;
        return isMarubozu(bars[index]);
    },
};

export const SpinningTopPattern: CandlestickPattern = {
    id: 'spinningTop',
    name: 'Spinning Top',
    displayName: 'Spinning Formation',
    type: 'neutral',
    complexity: 1,
    category: 'single',
    description: 'Small body with long wicks on both sides, showing indecision.',
    detect: (bars, index) => {
        if (index < 0 || index >= bars.length) return false;
        const bar = bars[index];
        const range = totalRange(bar);
        if (range === 0) return false;
        
        const body = bodySize(bar);
        const upperW = upperWick(bar);
        const lowerW = lowerWick(bar);
        
        return (
            body / range < 0.3 &&
            upperW > body &&
            lowerW > body
        );
    },
};

// =============================================================================
// DOUBLE CANDLE PATTERNS
// =============================================================================

export const BullishEngulfingPattern: CandlestickPattern = {
    id: 'bullishEngulfing',
    name: 'Bullish Engulfing',
    displayName: 'Bull Engulf Pattern',
    type: 'bullish',
    complexity: 1,
    category: 'double',
    description: 'Large bullish candle engulfs previous bearish candle.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        return (
            isBearish(prev) &&
            isBullish(current) &&
            current.open < prev.close &&
            current.close > prev.open
        );
    },
};

export const BearishEngulfingPattern: CandlestickPattern = {
    id: 'bearishEngulfing',
    name: 'Bearish Engulfing',
    displayName: 'Bear Engulf Pattern',
    type: 'bearish',
    complexity: 1,
    category: 'double',
    description: 'Large bearish candle engulfs previous bullish candle.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        return (
            isBullish(prev) &&
            isBearish(current) &&
            current.open > prev.close &&
            current.close < prev.open
        );
    },
};

export const DarkCloudCoverPattern: CandlestickPattern = {
    id: 'darkCloudCover',
    name: 'Dark Cloud Cover',
    displayName: 'Cloud Cover',
    type: 'bearish',
    complexity: 2,
    category: 'double',
    description: 'Bearish candle opens above prior high and closes below midpoint of prior body.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        if (!isBullish(prev) || !isBearish(current)) return false;
        
        const prevMidpoint = (prev.open + prev.close) / 2;
        
        return (
            current.open > prev.high &&
            current.close < prevMidpoint &&
            current.close > prev.open
        );
    },
};

export const PiercingPattern: CandlestickPattern = {
    id: 'piercing',
    name: 'Piercing',
    displayName: 'Pierce Pattern',
    type: 'bullish',
    complexity: 2,
    category: 'double',
    description: 'Bullish candle opens below prior low and closes above midpoint of prior body.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        if (!isBearish(prev) || !isBullish(current)) return false;
        
        const prevMidpoint = (prev.open + prev.close) / 2;
        
        return (
            current.open < prev.low &&
            current.close > prevMidpoint &&
            current.close < prev.open
        );
    },
};

export const TweezerTopPattern: CandlestickPattern = {
    id: 'tweezerTop',
    name: 'Tweezer Top',
    displayName: 'Tweezer Top Formation',
    type: 'bearish',
    complexity: 2,
    category: 'double',
    description: 'Two candles with matching highs at top of uptrend.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        const tolerance = totalRange(current) * 0.02;
        
        return (
            isBullish(prev) &&
            isBearish(current) &&
            Math.abs(current.high - prev.high) < tolerance
        );
    },
};

export const TweezerBottomPattern: CandlestickPattern = {
    id: 'tweezerBottom',
    name: 'Tweezer Bottom',
    displayName: 'Tweezer Bottom Formation',
    type: 'bullish',
    complexity: 2,
    category: 'double',
    description: 'Two candles with matching lows at bottom of downtrend.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        const tolerance = totalRange(current) * 0.02;
        
        return (
            isBearish(prev) &&
            isBullish(current) &&
            Math.abs(current.low - prev.low) < tolerance
        );
    },
};

export const KickingBullishPattern: CandlestickPattern = {
    id: 'kickingBullish',
    name: 'Bullish Kicking',
    displayName: 'Bull Kick Pattern',
    type: 'bullish',
    complexity: 2,
    category: 'double',
    description: 'Bearish marubozu followed by bullish marubozu with gap up.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        return (
            isBearish(prev) &&
            isMarubozu(prev, 0.1) &&
            isBullish(current) &&
            isMarubozu(current, 0.1) &&
            hasGapUp(current, prev)
        );
    },
};

export const KickingBearishPattern: CandlestickPattern = {
    id: 'kickingBearish',
    name: 'Bearish Kicking',
    displayName: 'Bear Kick Pattern',
    type: 'bearish',
    complexity: 2,
    category: 'double',
    description: 'Bullish marubozu followed by bearish marubozu with gap down.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const current = bars[index];
        const prev = bars[index - 1];
        
        return (
            isBullish(prev) &&
            isMarubozu(prev, 0.1) &&
            isBearish(current) &&
            isMarubozu(current, 0.1) &&
            hasGapDown(current, prev)
        );
    },
};

export const GapUpPattern: CandlestickPattern = {
    id: 'gapUp',
    name: 'Rising Window',
    displayName: 'Gap Up Pattern',
    type: 'bullish',
    complexity: 1,
    category: 'double',
    description: 'Price gaps up, showing strong buying pressure.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        return hasGapUp(bars[index], bars[index - 1]);
    },
};

export const GapDownPattern: CandlestickPattern = {
    id: 'gapDown',
    name: 'Falling Window',
    displayName: 'Gap Down Pattern',
    type: 'bearish',
    complexity: 1,
    category: 'double',
    description: 'Price gaps down, showing strong selling pressure.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        return hasGapDown(bars[index], bars[index - 1]);
    },
};

// =============================================================================
// TRIPLE CANDLE PATTERNS
// =============================================================================

export const MorningStarPattern: CandlestickPattern = {
    id: 'morningStar',
    name: 'Morning Star',
    displayName: 'Morning Signal',
    type: 'bullish',
    complexity: 2,
    category: 'triple',
    description: 'Three-candle reversal: bearish, small body, bullish.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        const avgBody = getAvgBodySize(bars.slice(0, index), 10);
        
        return (
            isBearish(first) &&
            isLargeBody(first, avgBody) &&
            isSmallBody(second, avgBody) &&
            second.high < first.close &&
            isBullish(third) &&
            isLargeBody(third, avgBody) &&
            third.close > (first.open + first.close) / 2
        );
    },
};

export const EveningStarPattern: CandlestickPattern = {
    id: 'eveningStar',
    name: 'Evening Star',
    displayName: 'Evening Signal',
    type: 'bearish',
    complexity: 2,
    category: 'triple',
    description: 'Three-candle reversal: bullish, small body, bearish.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        const avgBody = getAvgBodySize(bars.slice(0, index), 10);
        
        return (
            isBullish(first) &&
            isLargeBody(first, avgBody) &&
            isSmallBody(second, avgBody) &&
            second.low > first.close &&
            isBearish(third) &&
            isLargeBody(third, avgBody) &&
            third.close < (first.open + first.close) / 2
        );
    },
};

export const ThreeWhiteSoldiersPattern: CandlestickPattern = {
    id: 'threeWhiteSoldiers',
    name: 'Three White Soldiers',
    displayName: 'Triple Bull',
    type: 'bullish',
    complexity: 2,
    category: 'triple',
    description: 'Three consecutive bullish candles with higher closes and small wicks.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        const avgBody = getAvgBodySize(bars.slice(0, index), 10);
        
        return (
            isBullish(first) && isBullish(second) && isBullish(third) &&
            second.close > first.close &&
            third.close > second.close &&
            second.open > first.open && second.open < first.close &&
            third.open > second.open && third.open < second.close &&
            !hasLongUpperWick(first) && !hasLongUpperWick(second) && !hasLongUpperWick(third)
        );
    },
};

export const ThreeBlackCrowsPattern: CandlestickPattern = {
    id: 'threeBlackCrows',
    name: 'Three Black Crows',
    displayName: 'Triple Bear',
    type: 'bearish',
    complexity: 2,
    category: 'triple',
    description: 'Three consecutive bearish candles with lower closes.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        return (
            isBearish(first) && isBearish(second) && isBearish(third) &&
            second.close < first.close &&
            third.close < second.close &&
            second.open < first.open && second.open > first.close &&
            third.open < second.open && third.open > second.close &&
            !hasLongLowerWick(first) && !hasLongLowerWick(second) && !hasLongLowerWick(third)
        );
    },
};

export const BullishAbandonedBabyPattern: CandlestickPattern = {
    id: 'bullishAbandonedBaby',
    name: 'Bullish Abandoned Baby',
    displayName: 'Bull Orphan Candle',
    type: 'bullish',
    complexity: 2,
    category: 'triple',
    description: 'Doji gaps below bearish candle, then bullish candle gaps above doji.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        return (
            isBearish(first) &&
            isDoji(second) &&
            hasGapDown(second, first) &&
            isBullish(third) &&
            hasGapUp(third, second)
        );
    },
};

export const BearishAbandonedBabyPattern: CandlestickPattern = {
    id: 'bearishAbandonedBaby',
    name: 'Bearish Abandoned Baby',
    displayName: 'Bear Orphan Candle',
    type: 'bearish',
    complexity: 2,
    category: 'triple',
    description: 'Doji gaps above bullish candle, then bearish candle gaps below doji.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        return (
            isBullish(first) &&
            isDoji(second) &&
            hasGapUp(second, first) &&
            isBearish(third) &&
            hasGapDown(third, second)
        );
    },
};

export const BullishDojiStarPattern: CandlestickPattern = {
    id: 'bullishDojiStar',
    name: 'Bullish Doji Star',
    displayName: 'Bull Star Doji',
    type: 'bullish',
    complexity: 2,
    category: 'double',
    description: 'Doji gaps below prior bearish candle, signaling potential reversal.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const prev = bars[index - 1];
        const current = bars[index];
        
        return (
            isBearish(prev) &&
            isLargeBody(prev, bodySize(prev)) &&
            isDoji(current) &&
            current.high < prev.close
        );
    },
};

export const BearishDojiStarPattern: CandlestickPattern = {
    id: 'bearishDojiStar',
    name: 'Bearish Doji Star',
    displayName: 'Bear Star Doji',
    type: 'bearish',
    complexity: 2,
    category: 'double',
    description: 'Doji gaps above prior bullish candle, signaling potential reversal.',
    detect: (bars, index) => {
        if (index < 1 || index >= bars.length) return false;
        const prev = bars[index - 1];
        const current = bars[index];
        
        return (
            isBullish(prev) &&
            isLargeBody(prev, bodySize(prev)) &&
            isDoji(current) &&
            current.low > prev.close
        );
    },
};

export const TasukiGapUpPattern: CandlestickPattern = {
    id: 'tasukiGapUp',
    name: 'Upside Tasuki Gap',
    displayName: 'Bull Tasuki Formation',
    type: 'bullish',
    complexity: 2,
    category: 'triple',
    description: 'Gap up continuation with partial fill that holds.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        return (
            isBullish(first) &&
            isBullish(second) &&
            hasGapUp(second, first) &&
            isBearish(third) &&
            third.open > second.open &&
            third.close < second.open &&
            third.close > first.high
        );
    },
};

export const TasukiGapDownPattern: CandlestickPattern = {
    id: 'tasukiGapDown',
    name: 'Downside Tasuki Gap',
    displayName: 'Bear Tasuki Formation',
    type: 'bearish',
    complexity: 2,
    category: 'triple',
    description: 'Gap down continuation with partial fill that holds.',
    detect: (bars, index) => {
        if (index < 2 || index >= bars.length) return false;
        const first = bars[index - 2];
        const second = bars[index - 1];
        const third = bars[index];
        
        return (
            isBearish(first) &&
            isBearish(second) &&
            hasGapDown(second, first) &&
            isBullish(third) &&
            third.open < second.open &&
            third.close > second.open &&
            third.close < first.low
        );
    },
};

// =============================================================================
// PATTERN REGISTRY
// =============================================================================

export const CANDLESTICK_PATTERNS: CandlestickPattern[] = [
    // Single Candle
    DojiPattern,
    HammerPattern,
    ShootingStarPattern,
    MarubozuPattern,
    SpinningTopPattern,
    // Double Candle
    BullishEngulfingPattern,
    BearishEngulfingPattern,
    DarkCloudCoverPattern,
    PiercingPattern,
    TweezerTopPattern,
    TweezerBottomPattern,
    KickingBullishPattern,
    KickingBearishPattern,
    GapUpPattern,
    GapDownPattern,
    BullishDojiStarPattern,
    BearishDojiStarPattern,
    // Triple Candle
    MorningStarPattern,
    EveningStarPattern,
    ThreeWhiteSoldiersPattern,
    ThreeBlackCrowsPattern,
    BullishAbandonedBabyPattern,
    BearishAbandonedBabyPattern,
    TasukiGapUpPattern,
    TasukiGapDownPattern,
];

// =============================================================================
// SCANNER FUNCTION
// =============================================================================

export function scanForPatterns(
    bars: OHLCVBar[],
    patterns: CandlestickPattern[] = CANDLESTICK_PATTERNS,
    startIndex = 0,
    endIndex?: number
): PatternMatch[] {
    const matches: PatternMatch[] = [];
    const end = endIndex ?? bars.length;

    for (let i = Math.max(startIndex, 2); i < end; i++) {
        for (const pattern of patterns) {
            if (pattern.detect(bars, i)) {
                // Determine how many candles back this pattern spans
                let patternStart = i;
                if (pattern.category === 'double') patternStart = i - 1;
                if (pattern.category === 'triple') patternStart = i - 2;
                if (pattern.category === 'complex') patternStart = i - 3;

                matches.push({
                    pattern: pattern.id,
                    name: pattern.displayName,
                    type: pattern.type,
                    startIndex: patternStart,
                    endIndex: i,
                    reliability: pattern.complexity === 1 ? 'high' : pattern.complexity === 2 ? 'medium' : 'low',
                    description: pattern.description,
                });
            }
        }
    }

    return matches;
}

export function getPatternById(id: string): CandlestickPattern | undefined {
    return CANDLESTICK_PATTERNS.find(p => p.id === id);
}

export function getPatternsByType(type: 'bullish' | 'bearish' | 'neutral'): CandlestickPattern[] {
    return CANDLESTICK_PATTERNS.filter(p => p.type === type);
}

export function getPatternsByCategory(category: CandlestickPattern['category']): CandlestickPattern[] {
    return CANDLESTICK_PATTERNS.filter(p => p.category === category);
}
