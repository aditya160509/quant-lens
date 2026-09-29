/**
 * Market Structure Tools
 * 
 * Per tradefeature.md §18:
 * - Swing high/low detection
 * - HH/HL/LH/LL labeling
 * - Break of Structure (BOS) detection
 * - Change of Character (CHoCH) markers
 */

// =============================================================================
// TYPES
// =============================================================================

export interface SwingPoint {
    index: number;
    timestamp: number;
    price: number;
    type: 'high' | 'low';
    label?: 'HH' | 'HL' | 'LH' | 'LL';
}

export interface StructureBreak {
    index: number;
    timestamp: number;
    price: number;
    type: 'bullish' | 'bearish';
    isCHoCH: boolean; // Change of Character
    brokenLevel: number;
}

export interface MarketStructure {
    swingHighs: SwingPoint[];
    swingLows: SwingPoint[];
    breaks: StructureBreak[];
    currentTrend: 'bullish' | 'bearish' | 'neutral';
}

interface OHLCVBar {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

// =============================================================================
// SWING DETECTION
// =============================================================================

/**
 * Detect swing highs and lows using N-bar lookback
 */
export function detectSwings(
    bars: OHLCVBar[],
    lookback: number = 10
): { swingHighs: SwingPoint[]; swingLows: SwingPoint[] } {
    const swingHighs: SwingPoint[] = [];
    const swingLows: SwingPoint[] = [];

    if (bars.length < lookback * 2 + 1) {
        return { swingHighs, swingLows };
    }

    for (let i = lookback; i < bars.length - lookback; i++) {
        const current = bars[i];
        
        // Check for swing high
        let isSwingHigh = true;
        for (let j = i - lookback; j <= i + lookback; j++) {
            if (j !== i && bars[j].high >= current.high) {
                isSwingHigh = false;
                break;
            }
        }
        
        if (isSwingHigh) {
            swingHighs.push({
                index: i,
                timestamp: current.timestamp,
                price: current.high,
                type: 'high',
            });
        }

        // Check for swing low
        let isSwingLow = true;
        for (let j = i - lookback; j <= i + lookback; j++) {
            if (j !== i && bars[j].low <= current.low) {
                isSwingLow = false;
                break;
            }
        }
        
        if (isSwingLow) {
            swingLows.push({
                index: i,
                timestamp: current.timestamp,
                price: current.low,
                type: 'low',
            });
        }
    }

    return { swingHighs, swingLows };
}

// =============================================================================
// STRUCTURE LABELING
// =============================================================================

/**
 * Label swing points as HH/HL/LH/LL
 */
export function labelSwingPoints(
    swingHighs: SwingPoint[],
    swingLows: SwingPoint[]
): { labeledHighs: SwingPoint[]; labeledLows: SwingPoint[] } {
    const labeledHighs = [...swingHighs];
    const labeledLows = [...swingLows];

    // Label swing highs
    for (let i = 1; i < labeledHighs.length; i++) {
        const current = labeledHighs[i];
        const previous = labeledHighs[i - 1];
        current.label = current.price > previous.price ? 'HH' : 'LH';
    }
    if (labeledHighs.length > 0) {
        labeledHighs[0].label = 'HH'; // First one is reference
    }

    // Label swing lows
    for (let i = 1; i < labeledLows.length; i++) {
        const current = labeledLows[i];
        const previous = labeledLows[i - 1];
        current.label = current.price > previous.price ? 'HL' : 'LL';
    }
    if (labeledLows.length > 0) {
        labeledLows[0].label = 'HL'; // First one is reference
    }

    return { labeledHighs, labeledLows };
}

// =============================================================================
// BREAK OF STRUCTURE DETECTION
// =============================================================================

/**
 * Detect breaks of structure and changes of character
 */
export function detectStructureBreaks(
    bars: OHLCVBar[],
    swingHighs: SwingPoint[],
    swingLows: SwingPoint[]
): { breaks: StructureBreak[]; trend: 'bullish' | 'bearish' | 'neutral' } {
    const breaks: StructureBreak[] = [];
    let currentTrend: 'bullish' | 'bearish' | 'neutral' = 'neutral';

    // Determine initial trend from first swing labels
    if (swingHighs.length >= 2 && swingLows.length >= 2) {
        const lastHighLabel = swingHighs[swingHighs.length - 2]?.label;
        const lastLowLabel = swingLows[swingLows.length - 2]?.label;
        
        if (lastHighLabel === 'HH' && lastLowLabel === 'HL') {
            currentTrend = 'bullish';
        } else if (lastHighLabel === 'LH' && lastLowLabel === 'LL') {
            currentTrend = 'bearish';
        }
    }

    // Check each bar for structure breaks
    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        
        // Find most recent swing high/low before this bar
        const recentSwingHigh = [...swingHighs]
            .filter(s => s.index < i)
            .pop();
        const recentSwingLow = [...swingLows]
            .filter(s => s.index < i)
            .pop();

        // Check for bullish break (price closes above swing high)
        if (recentSwingHigh && bar.close > recentSwingHigh.price) {
            const isCHoCH = currentTrend === 'bearish';
            
            // Avoid duplicate breaks
            const alreadyBroken = breaks.some(
                b => b.brokenLevel === recentSwingHigh.price && b.type === 'bullish'
            );
            
            if (!alreadyBroken) {
                breaks.push({
                    index: i,
                    timestamp: bar.timestamp,
                    price: bar.close,
                    type: 'bullish',
                    isCHoCH,
                    brokenLevel: recentSwingHigh.price,
                });
                
                if (isCHoCH) currentTrend = 'bullish';
            }
        }

        // Check for bearish break (price closes below swing low)
        if (recentSwingLow && bar.close < recentSwingLow.price) {
            const isCHoCH = currentTrend === 'bullish';
            
            const alreadyBroken = breaks.some(
                b => b.brokenLevel === recentSwingLow.price && b.type === 'bearish'
            );
            
            if (!alreadyBroken) {
                breaks.push({
                    index: i,
                    timestamp: bar.timestamp,
                    price: bar.close,
                    type: 'bearish',
                    isCHoCH,
                    brokenLevel: recentSwingLow.price,
                });
                
                if (isCHoCH) currentTrend = 'bearish';
            }
        }
    }

    return { breaks, trend: currentTrend };
}

// =============================================================================
// MAIN ANALYSIS FUNCTION
// =============================================================================

/**
 * Perform complete market structure analysis
 */
export function analyzeMarketStructure(
    bars: OHLCVBar[],
    lookback: number = 10
): MarketStructure {
    const { swingHighs, swingLows } = detectSwings(bars, lookback);
    const { labeledHighs, labeledLows } = labelSwingPoints(swingHighs, swingLows);
    const { breaks, trend } = detectStructureBreaks(bars, labeledHighs, labeledLows);

    return {
        swingHighs: labeledHighs,
        swingLows: labeledLows,
        breaks,
        currentTrend: trend,
    };
}

// =============================================================================
// LIQUIDITY SWEEP DETECTION (§21)
// =============================================================================

export interface LiquiditySweep {
    index: number;
    timestamp: number;
    type: 'bullish' | 'bearish';
    sweptLevel: number;
    wickRatio: number;
    rejectionStrength: 'strong' | 'weak';
}

/**
 * Detect liquidity sweeps (false breakouts with wick rejections)
 */
export function detectLiquiditySweeps(
    bars: OHLCVBar[],
    swingHighs: SwingPoint[],
    swingLows: SwingPoint[]
): LiquiditySweep[] {
    const sweeps: LiquiditySweep[] = [];

    for (let i = 1; i < bars.length; i++) {
        const bar = bars[i];
        const barRange = bar.high - bar.low;
        if (barRange === 0) continue;

        // Check for bullish sweep (wick below swing low, close above)
        const recentSwingLows = swingLows.filter(s => s.index < i && s.index > i - 50);
        for (const swing of recentSwingLows) {
            if (bar.low < swing.price && bar.close > swing.price) {
                const lowerWick = Math.min(bar.open, bar.close) - bar.low;
                const wickRatio = lowerWick / barRange;
                
                sweeps.push({
                    index: i,
                    timestamp: bar.timestamp,
                    type: 'bullish',
                    sweptLevel: swing.price,
                    wickRatio,
                    rejectionStrength: wickRatio > 0.5 ? 'strong' : 'weak',
                });
                break; // One sweep per bar
            }
        }

        // Check for bearish sweep (wick above swing high, close below)
        const recentSwingHighs = swingHighs.filter(s => s.index < i && s.index > i - 50);
        for (const swing of recentSwingHighs) {
            if (bar.high > swing.price && bar.close < swing.price) {
                const upperWick = bar.high - Math.max(bar.open, bar.close);
                const wickRatio = upperWick / barRange;
                
                sweeps.push({
                    index: i,
                    timestamp: bar.timestamp,
                    type: 'bearish',
                    sweptLevel: swing.price,
                    wickRatio,
                    rejectionStrength: wickRatio > 0.5 ? 'strong' : 'weak',
                });
                break;
            }
        }
    }

    return sweeps;
}

// =============================================================================
// RENDERING DATA
// =============================================================================

export interface MarketStructureRenderData {
    swingMarkers: Array<{
        x: number;
        y: number;
        type: 'high' | 'low';
        label: string;
        color: string;
    }>;
    structureLines: Array<{
        x1: number;
        y1: number;
        x2: number;
        y2: number;
        color: string;
    }>;
    breakMarkers: Array<{
        x: number;
        y: number;
        type: 'BOS' | 'CHoCH';
        direction: 'bullish' | 'bearish';
    }>;
    sweepMarkers: Array<{
        x: number;
        y: number;
        type: 'bullish' | 'bearish';
        level: number;
    }>;
}

export function createRenderData(
    structure: MarketStructure,
    sweeps: LiquiditySweep[],
    xScale: (index: number) => number,
    yScale: (price: number) => number
): MarketStructureRenderData {
    const swingMarkers = [
        ...structure.swingHighs.map(s => ({
            x: xScale(s.index),
            y: yScale(s.price),
            type: 'high' as const,
            label: s.label || '',
            color: s.label === 'HH' || s.label === 'HL' ? '#26a69a' : '#ef5350',
        })),
        ...structure.swingLows.map(s => ({
            x: xScale(s.index),
            y: yScale(s.price),
            type: 'low' as const,
            label: s.label || '',
            color: s.label === 'HH' || s.label === 'HL' ? '#26a69a' : '#ef5350',
        })),
    ];

    // Connect swing points with lines
    const structureLines: MarketStructureRenderData['structureLines'] = [];
    for (let i = 1; i < structure.swingHighs.length; i++) {
        const prev = structure.swingHighs[i - 1];
        const curr = structure.swingHighs[i];
        structureLines.push({
            x1: xScale(prev.index),
            y1: yScale(prev.price),
            x2: xScale(curr.index),
            y2: yScale(curr.price),
            color: curr.label === 'HH' ? '#26a69a' : '#ef5350',
        });
    }
    for (let i = 1; i < structure.swingLows.length; i++) {
        const prev = structure.swingLows[i - 1];
        const curr = structure.swingLows[i];
        structureLines.push({
            x1: xScale(prev.index),
            y1: yScale(prev.price),
            x2: xScale(curr.index),
            y2: yScale(curr.price),
            color: curr.label === 'HL' ? '#26a69a' : '#ef5350',
        });
    }

    const breakMarkers = structure.breaks.map(b => ({
        x: xScale(b.index),
        y: yScale(b.price),
        type: b.isCHoCH ? 'CHoCH' as const : 'BOS' as const,
        direction: b.type,
    }));

    const sweepMarkers = sweeps.map(s => ({
        x: xScale(s.index),
        y: yScale(s.sweptLevel),
        type: s.type,
        level: s.sweptLevel,
    }));

    return {
        swingMarkers,
        structureLines,
        breakMarkers,
        sweepMarkers,
    };
}
