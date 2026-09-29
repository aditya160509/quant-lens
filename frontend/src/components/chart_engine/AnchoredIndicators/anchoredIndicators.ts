/**
 * Anchored Indicators
 * 
 * Per tradefeature.md §17:
 * - Anchored VWAP (from user-selected bar)
 * - Anchored Moving Averages
 * - Anchor selection UI support
 */

import type { OHLCVBar } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export interface AnchoredVWAPResult {
    values: number[];
    anchorTimestamp: number;
    anchorIndex: number;
    upperBand1?: number[];
    lowerBand1?: number[];
    upperBand2?: number[];
    lowerBand2?: number[];
}

export interface AnchoredMAResult {
    values: number[];
    type: 'sma' | 'ema';
    period: number;
    anchorTimestamp: number;
    anchorIndex: number;
}

export interface AnchorPoint {
    timestamp: number;
    index: number;
    label?: string;
    color?: string;
}

// =============================================================================
// ANCHORED VWAP
// =============================================================================

/**
 * Calculate VWAP from an anchor point
 */
export function calculateAnchoredVWAP(
    bars: OHLCVBar[],
    anchorIndex: number,
    stdDevBands: boolean = true
): AnchoredVWAPResult {
    if (anchorIndex < 0 || anchorIndex >= bars.length) {
        return {
            values: [],
            anchorTimestamp: 0,
            anchorIndex: -1,
        };
    }

    const values: number[] = new Array(bars.length).fill(NaN);
    const upperBand1: number[] = new Array(bars.length).fill(NaN);
    const lowerBand1: number[] = new Array(bars.length).fill(NaN);
    const upperBand2: number[] = new Array(bars.length).fill(NaN);
    const lowerBand2: number[] = new Array(bars.length).fill(NaN);

    let cumulativeTPV = 0;
    let cumulativeVolume = 0;
    const tpvList: number[] = [];

    for (let i = anchorIndex; i < bars.length; i++) {
        const bar = bars[i];
        const typicalPrice = (bar.high + bar.low + bar.close) / 3;
        const tpv = typicalPrice * bar.volume;

        cumulativeTPV += tpv;
        cumulativeVolume += bar.volume;
        tpvList.push(tpv);

        const vwap = cumulativeVolume > 0 ? cumulativeTPV / cumulativeVolume : typicalPrice;
        values[i] = vwap;

        // Calculate standard deviation bands
        if (stdDevBands && i > anchorIndex) {
            const barsFromAnchor = i - anchorIndex + 1;
            const avgTPV = cumulativeTPV / barsFromAnchor;
            
            // Variance calculation
            let sumSquaredDiff = 0;
            for (let j = anchorIndex; j <= i; j++) {
                const tp = (bars[j].high + bars[j].low + bars[j].close) / 3;
                sumSquaredDiff += Math.pow(tp - vwap, 2) * bars[j].volume;
            }
            const variance = cumulativeVolume > 0 ? sumSquaredDiff / cumulativeVolume : 0;
            const stdDev = Math.sqrt(variance);

            upperBand1[i] = vwap + stdDev;
            lowerBand1[i] = vwap - stdDev;
            upperBand2[i] = vwap + 2 * stdDev;
            lowerBand2[i] = vwap - 2 * stdDev;
        }
    }

    return {
        values,
        anchorTimestamp: bars[anchorIndex].timestamp,
        anchorIndex,
        upperBand1: stdDevBands ? upperBand1 : undefined,
        lowerBand1: stdDevBands ? lowerBand1 : undefined,
        upperBand2: stdDevBands ? upperBand2 : undefined,
        lowerBand2: stdDevBands ? lowerBand2 : undefined,
    };
}

// =============================================================================
// ANCHORED MOVING AVERAGES
// =============================================================================

/**
 * Calculate SMA from an anchor point
 */
export function calculateAnchoredSMA(
    bars: OHLCVBar[],
    anchorIndex: number,
    period: number = 20
): AnchoredMAResult {
    if (anchorIndex < 0 || anchorIndex >= bars.length) {
        return {
            values: [],
            type: 'sma',
            period,
            anchorTimestamp: 0,
            anchorIndex: -1,
        };
    }

    const values: number[] = new Array(bars.length).fill(NaN);
    
    for (let i = anchorIndex; i < bars.length; i++) {
        const lookbackStart = Math.max(anchorIndex, i - period + 1);
        const slice = bars.slice(lookbackStart, i + 1);
        const sum = slice.reduce((s, b) => s + b.close, 0);
        values[i] = sum / slice.length;
    }

    return {
        values,
        type: 'sma',
        period,
        anchorTimestamp: bars[anchorIndex].timestamp,
        anchorIndex,
    };
}

/**
 * Calculate EMA from an anchor point
 */
export function calculateAnchoredEMA(
    bars: OHLCVBar[],
    anchorIndex: number,
    period: number = 20
): AnchoredMAResult {
    if (anchorIndex < 0 || anchorIndex >= bars.length) {
        return {
            values: [],
            type: 'ema',
            period,
            anchorTimestamp: 0,
            anchorIndex: -1,
        };
    }

    const values: number[] = new Array(bars.length).fill(NaN);
    const multiplier = 2 / (period + 1);

    // Start with SMA for first value
    let ema = bars[anchorIndex].close;
    values[anchorIndex] = ema;

    for (let i = anchorIndex + 1; i < bars.length; i++) {
        ema = (bars[i].close - ema) * multiplier + ema;
        values[i] = ema;
    }

    return {
        values,
        type: 'ema',
        period,
        anchorTimestamp: bars[anchorIndex].timestamp,
        anchorIndex,
    };
}

// =============================================================================
// ANCHOR MANAGER
// =============================================================================

export class AnchorManager {
    private anchors: Map<string, AnchorPoint> = new Map();
    private vwapResults: Map<string, AnchoredVWAPResult> = new Map();
    private maResults: Map<string, AnchoredMAResult> = new Map();

    /**
     * Add an anchor point
     */
    addAnchor(id: string, timestamp: number, index: number, label?: string, color?: string): void {
        this.anchors.set(id, { timestamp, index, label, color });
    }

    /**
     * Remove an anchor point
     */
    removeAnchor(id: string): void {
        this.anchors.delete(id);
        this.vwapResults.delete(id);
        this.maResults.delete(id);
    }

    /**
     * Get all anchor points
     */
    getAnchors(): Map<string, AnchorPoint> {
        return new Map(this.anchors);
    }

    /**
     * Calculate anchored VWAP for an anchor
     */
    calculateVWAP(id: string, bars: OHLCVBar[], stdDevBands: boolean = true): AnchoredVWAPResult | null {
        const anchor = this.anchors.get(id);
        if (!anchor) return null;

        const result = calculateAnchoredVWAP(bars, anchor.index, stdDevBands);
        this.vwapResults.set(id, result);
        return result;
    }

    /**
     * Calculate anchored MA for an anchor
     */
    calculateMA(
        id: string, 
        bars: OHLCVBar[], 
        type: 'sma' | 'ema' = 'sma',
        period: number = 20
    ): AnchoredMAResult | null {
        const anchor = this.anchors.get(id);
        if (!anchor) return null;

        const result = type === 'ema'
            ? calculateAnchoredEMA(bars, anchor.index, period)
            : calculateAnchoredSMA(bars, anchor.index, period);
        
        this.maResults.set(id, result);
        return result;
    }

    /**
     * Get all VWAP results
     */
    getVWAPResults(): Map<string, AnchoredVWAPResult> {
        return new Map(this.vwapResults);
    }

    /**
     * Get all MA results
     */
    getMAResults(): Map<string, AnchoredMAResult> {
        return new Map(this.maResults);
    }

    /**
     * Clear all anchors
     */
    clear(): void {
        this.anchors.clear();
        this.vwapResults.clear();
        this.maResults.clear();
    }

    /**
     * Serialize for persistence
     */
    serialize(): string {
        return JSON.stringify({
            anchors: Array.from(this.anchors.entries()),
        });
    }

    /**
     * Deserialize from persistence
     */
    deserialize(data: string): void {
        try {
            const parsed = JSON.parse(data);
            this.anchors = new Map(parsed.anchors);
        } catch (e) {
            console.error('Failed to deserialize anchor data', e);
        }
    }
}

// =============================================================================
// SINGLETON
// =============================================================================

let anchorManagerInstance: AnchorManager | null = null;

export function getAnchorManager(): AnchorManager {
    if (!anchorManagerInstance) {
        anchorManagerInstance = new AnchorManager();
    }
    return anchorManagerInstance;
}
