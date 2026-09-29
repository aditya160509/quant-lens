/**
 * Volume Profile Fixed Range Calculator
 * 
 * Extends the base volume profile to support fixed time/price ranges
 * per tradefeature.md §5 requirements
 */

import type { OHLCVBar } from '../types';
import type { VolumeProfileConfig, VolumeProfileData } from './volumeProfileTypes';
import { calculateVolumeProfile } from './volumeProfileCalc';

// =============================================================================
// FIXED RANGE TYPES
// =============================================================================

export interface FixedRangeConfig {
    startTimestamp: number;
    endTimestamp: number;
    startIndex?: number;  // Alternative: use bar indices
    endIndex?: number;
}

export interface PriceRangeConfig {
    priceHigh: number;
    priceLow: number;
}

export interface FixedRangeVolumeProfile extends VolumeProfileData {
    rangeType: 'time' | 'price' | 'both';
    timeRange?: FixedRangeConfig;
    priceRange?: PriceRangeConfig;
}

// =============================================================================
// FIXED TIME RANGE
// =============================================================================

/**
 * Calculate volume profile for a fixed time range
 */
export function calculateFixedRangeProfile(
    allBars: OHLCVBar[],
    range: FixedRangeConfig,
    config: Partial<VolumeProfileConfig> = {}
): FixedRangeVolumeProfile {
    let filteredBars: OHLCVBar[];

    if (range.startIndex !== undefined && range.endIndex !== undefined) {
        // Use indices
        const start = Math.max(0, range.startIndex);
        const end = Math.min(allBars.length - 1, range.endIndex);
        filteredBars = allBars.slice(start, end + 1);
    } else {
        // Use timestamps
        filteredBars = allBars.filter(
            bar => bar.timestamp >= range.startTimestamp && bar.timestamp <= range.endTimestamp
        );
    }

    const baseProfile = calculateVolumeProfile(filteredBars, { ...config, scope: 'fixed' });

    return {
        ...baseProfile,
        rangeType: 'time',
        timeRange: range,
    };
}

// =============================================================================
// FIXED PRICE RANGE
// =============================================================================

/**
 * Calculate volume profile constrained to a price range
 */
export function calculatePriceRangeProfile(
    bars: OHLCVBar[],
    priceRange: PriceRangeConfig,
    config: Partial<VolumeProfileConfig> = {}
): FixedRangeVolumeProfile {
    // Only include bars that overlap with the price range
    const filteredBars = bars.filter(
        bar => bar.high >= priceRange.priceLow && bar.low <= priceRange.priceHigh
    );

    if (filteredBars.length === 0) {
        return {
            bins: [],
            poc: { price: 0, volume: 0, binIndex: -1 },
            valueArea: { high: 0, low: 0, volume: 0, percent: 0 },
            totalVolume: 0,
            priceHigh: priceRange.priceHigh,
            priceLow: priceRange.priceLow,
            barCount: 0,
            startTime: 0,
            endTime: 0,
            rangeType: 'price',
            priceRange,
        };
    }

    // Calculate custom price range
    const priceRangeSpan = priceRange.priceHigh - priceRange.priceLow;
    const rowCount = config.rowCount || 48;
    const binSize = priceRangeSpan / rowCount;

    // Initialize bins within the specified price range
    const bins: { priceHigh: number; priceLow: number; priceMiddle: number; volume: number; buyVolume: number; sellVolume: number; barCount: number }[] = [];
    for (let i = 0; i < rowCount; i++) {
        const binLow = priceRange.priceLow + i * binSize;
        const binHigh = binLow + binSize;
        bins.push({
            priceLow: binLow,
            priceHigh: binHigh,
            priceMiddle: (binLow + binHigh) / 2,
            volume: 0,
            buyVolume: 0,
            sellVolume: 0,
            barCount: 0,
        });
    }

    let totalVolume = 0;

    // Distribute volume to bins (only for price range overlap)
    for (const bar of filteredBars) {
        const isBullish = bar.close >= bar.open;
        const barLow = Math.max(bar.low, priceRange.priceLow);
        const barHigh = Math.min(bar.high, priceRange.priceHigh);
        const barRange = barHigh - barLow;

        if (barRange <= 0) continue;

        for (const bin of bins) {
            // Calculate overlap between bar and bin within price range
            const overlapLow = Math.max(barLow, bin.priceLow);
            const overlapHigh = Math.min(barHigh, bin.priceHigh);
            const overlap = Math.max(0, overlapHigh - overlapLow);

            if (overlap > 0) {
                const volumeShare = (overlap / barRange) * bar.volume;
                bin.volume += volumeShare;
                bin.barCount++;
                totalVolume += volumeShare;

                if (isBullish) {
                    bin.buyVolume += volumeShare;
                } else {
                    bin.sellVolume += volumeShare;
                }
            }
        }
    }

    // Find POC
    let pocIndex = 0;
    let maxVolume = 0;
    for (let i = 0; i < bins.length; i++) {
        if (bins[i].volume > maxVolume) {
            maxVolume = bins[i].volume;
            pocIndex = i;
        }
    }

    // Calculate value area
    const valueAreaPercent = config.valueAreaPercent || 70;
    const valueArea = calculateValueArea(bins, pocIndex, valueAreaPercent, totalVolume);

    return {
        bins,
        poc: {
            price: bins[pocIndex]?.priceMiddle ?? 0,
            volume: maxVolume,
            binIndex: pocIndex,
        },
        valueArea,
        totalVolume,
        priceHigh: priceRange.priceHigh,
        priceLow: priceRange.priceLow,
        barCount: filteredBars.length,
        startTime: filteredBars[0]?.timestamp ?? 0,
        endTime: filteredBars[filteredBars.length - 1]?.timestamp ?? 0,
        rangeType: 'price',
        priceRange,
    };
}

// =============================================================================
// COMBINED RANGE
// =============================================================================

/**
 * Calculate volume profile for both time and price constraints
 */
export function calculateCombinedRangeProfile(
    allBars: OHLCVBar[],
    timeRange: FixedRangeConfig,
    priceRange: PriceRangeConfig,
    config: Partial<VolumeProfileConfig> = {}
): FixedRangeVolumeProfile {
    // First filter by time
    let filteredBars: OHLCVBar[];

    if (timeRange.startIndex !== undefined && timeRange.endIndex !== undefined) {
        const start = Math.max(0, timeRange.startIndex);
        const end = Math.min(allBars.length - 1, timeRange.endIndex);
        filteredBars = allBars.slice(start, end + 1);
    } else {
        filteredBars = allBars.filter(
            bar => bar.timestamp >= timeRange.startTimestamp && bar.timestamp <= timeRange.endTimestamp
        );
    }

    // Then calculate price range profile
    const profile = calculatePriceRangeProfile(filteredBars, priceRange, config);

    return {
        ...profile,
        rangeType: 'both',
        timeRange,
        priceRange,
    };
}

// =============================================================================
// VALUE AREA CALCULATION
// =============================================================================

function calculateValueArea(
    bins: { priceHigh: number; priceLow: number; volume: number }[],
    pocIndex: number,
    targetPercent: number,
    totalVolume: number
): { high: number; low: number; volume: number; percent: number } {
    if (bins.length === 0 || totalVolume === 0) {
        return { high: 0, low: 0, volume: 0, percent: 0 };
    }

    const targetVolume = totalVolume * (targetPercent / 100);
    let currentVolume = bins[pocIndex].volume;
    let lowIndex = pocIndex;
    let highIndex = pocIndex;

    // Expand outward from POC until we reach target volume
    while (currentVolume < targetVolume && (lowIndex > 0 || highIndex < bins.length - 1)) {
        const nextLowVolume = lowIndex > 0 ? bins[lowIndex - 1].volume : 0;
        const nextHighVolume = highIndex < bins.length - 1 ? bins[highIndex + 1].volume : 0;

        if (nextLowVolume >= nextHighVolume && lowIndex > 0) {
            lowIndex--;
            currentVolume += bins[lowIndex].volume;
        } else if (highIndex < bins.length - 1) {
            highIndex++;
            currentVolume += bins[highIndex].volume;
        } else if (lowIndex > 0) {
            lowIndex--;
            currentVolume += bins[lowIndex].volume;
        } else {
            break;
        }
    }

    return {
        high: bins[highIndex].priceHigh,
        low: bins[lowIndex].priceLow,
        volume: currentVolume,
        percent: (currentVolume / totalVolume) * 100,
    };
}

// =============================================================================
// RANGE SELECTOR UTILITY
// =============================================================================

export interface RangeSelection {
    id: string;
    type: 'time' | 'price' | 'both';
    timeRange?: FixedRangeConfig;
    priceRange?: PriceRangeConfig;
    label?: string;
    color?: string;
}

export class FixedRangeManager {
    private ranges: Map<string, RangeSelection> = new Map();
    private profiles: Map<string, FixedRangeVolumeProfile> = new Map();

    addRange(selection: RangeSelection): void {
        this.ranges.set(selection.id, selection);
    }

    removeRange(id: string): void {
        this.ranges.delete(id);
        this.profiles.delete(id);
    }

    calculateProfile(
        id: string,
        bars: OHLCVBar[],
        config: Partial<VolumeProfileConfig> = {}
    ): FixedRangeVolumeProfile | null {
        const range = this.ranges.get(id);
        if (!range) return null;

        let profile: FixedRangeVolumeProfile;

        if (range.type === 'time' && range.timeRange) {
            profile = calculateFixedRangeProfile(bars, range.timeRange, config);
        } else if (range.type === 'price' && range.priceRange) {
            profile = calculatePriceRangeProfile(bars, range.priceRange, config);
        } else if (range.type === 'both' && range.timeRange && range.priceRange) {
            profile = calculateCombinedRangeProfile(bars, range.timeRange, range.priceRange, config);
        } else {
            return null;
        }

        this.profiles.set(id, profile);
        return profile;
    }

    getProfile(id: string): FixedRangeVolumeProfile | undefined {
        return this.profiles.get(id);
    }

    getAllProfiles(): Map<string, FixedRangeVolumeProfile> {
        return new Map(this.profiles);
    }

    clear(): void {
        this.ranges.clear();
        this.profiles.clear();
    }
}

// Singleton instance
let fixedRangeManagerInstance: FixedRangeManager | null = null;

export function getFixedRangeManager(): FixedRangeManager {
    if (!fixedRangeManagerInstance) {
        fixedRangeManagerInstance = new FixedRangeManager();
    }
    return fixedRangeManagerInstance;
}
