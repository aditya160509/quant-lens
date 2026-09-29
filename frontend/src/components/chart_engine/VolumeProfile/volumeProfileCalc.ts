/**
 * Volume Profile Calculator
 * Deterministic calculation of volume profile with POC and Value Area
 */

import type { OHLCVBar } from '../types';
import type { 
    VolumeProfileConfig, 
    VolumeProfileData, 
    PriceBin, 
    ValueArea,
    DEFAULT_VOLUME_PROFILE_CONFIG 
} from './volumeProfileTypes';
import { createEmptyProfile } from './volumeProfileTypes';

// =============================================================================
// MAIN CALCULATION FUNCTION
// =============================================================================

export function calculateVolumeProfile(
    bars: OHLCVBar[],
    config: Partial<VolumeProfileConfig> = {}
): VolumeProfileData {
    if (bars.length === 0) {
        return createEmptyProfile();
    }

    const cfg: VolumeProfileConfig = {
        scope: 'visible',
        rowCount: 48,
        valueAreaPercent: 70,
        showPOC: true,
        showValueArea: true,
        showDeveloping: true,
        position: 'left',
        width: 20,
        opacity: 0.6,
        colorScheme: 'gradient',
        ...config,
    };

    // Find price range
    let priceHigh = -Infinity;
    let priceLow = Infinity;
    let totalVolume = 0;

    for (const bar of bars) {
        if (bar.high > priceHigh) priceHigh = bar.high;
        if (bar.low < priceLow) priceLow = bar.low;
        totalVolume += bar.volume;
    }

    if (priceHigh === priceLow) {
        // All bars at same price - create single bin
        priceHigh += 0.01;
        priceLow -= 0.01;
    }

    const priceRange = priceHigh - priceLow;
    const binSize = priceRange / cfg.rowCount;

    // Initialize bins
    const bins: PriceBin[] = [];
    for (let i = 0; i < cfg.rowCount; i++) {
        const binLow = priceLow + i * binSize;
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

    // Distribute volume to bins
    for (const bar of bars) {
        const isBullish = bar.close >= bar.open;
        
        // Find bins that this bar spans
        for (const bin of bins) {
            // Calculate overlap between bar and bin
            const overlapLow = Math.max(bar.low, bin.priceLow);
            const overlapHigh = Math.min(bar.high, bin.priceHigh);
            
            if (overlapHigh > overlapLow) {
                // Bar overlaps this bin
                const barRange = bar.high - bar.low || 0.0001;
                const overlapRange = overlapHigh - overlapLow;
                const volumeFraction = overlapRange / barRange;
                const volumeContribution = bar.volume * volumeFraction;

                bin.volume += volumeContribution;
                bin.barCount += 1;
                
                if (isBullish) {
                    bin.buyVolume += volumeContribution;
                } else {
                    bin.sellVolume += volumeContribution;
                }
            }
        }
    }

    // Find POC (Point of Control) - highest volume bin
    let pocIndex = 0;
    let maxVolume = 0;
    for (let i = 0; i < bins.length; i++) {
        if (bins[i].volume > maxVolume) {
            maxVolume = bins[i].volume;
            pocIndex = i;
        }
    }

    const poc = {
        price: bins[pocIndex].priceMiddle,
        volume: bins[pocIndex].volume,
        binIndex: pocIndex,
    };

    // Calculate Value Area (70% of volume)
    const valueArea = calculateValueArea(bins, poc.binIndex, cfg.valueAreaPercent, totalVolume);

    return {
        bins,
        poc,
        valueArea,
        totalVolume,
        priceHigh,
        priceLow,
        barCount: bars.length,
        startTime: bars[0].timestamp,
        endTime: bars[bars.length - 1].timestamp,
    };
}

// =============================================================================
// VALUE AREA CALCULATION
// =============================================================================

function calculateValueArea(
    bins: PriceBin[],
    pocIndex: number,
    targetPercent: number,
    totalVolume: number
): ValueArea {
    if (bins.length === 0 || totalVolume === 0) {
        return { high: 0, low: 0, volume: 0, percent: 0 };
    }

    const targetVolume = totalVolume * (targetPercent / 100);
    
    // Start from POC and expand outward
    let lowIndex = pocIndex;
    let highIndex = pocIndex;
    let areaVolume = bins[pocIndex].volume;

    while (areaVolume < targetVolume && (lowIndex > 0 || highIndex < bins.length - 1)) {
        // Check which side to expand (the side with more volume)
        const canExpandDown = lowIndex > 0;
        const canExpandUp = highIndex < bins.length - 1;

        if (!canExpandDown && !canExpandUp) break;

        const volumeBelow = canExpandDown ? bins[lowIndex - 1].volume : 0;
        const volumeAbove = canExpandUp ? bins[highIndex + 1].volume : 0;

        // Expand in the direction with more volume
        // If only one direction available, expand that way
        if (!canExpandDown || (canExpandUp && volumeAbove >= volumeBelow)) {
            highIndex++;
            areaVolume += bins[highIndex].volume;
        } else {
            lowIndex--;
            areaVolume += bins[lowIndex].volume;
        }
    }

    return {
        high: bins[highIndex].priceHigh,
        low: bins[lowIndex].priceLow,
        volume: areaVolume,
        percent: (areaVolume / totalVolume) * 100,
    };
}

// =============================================================================
// SESSION PROFILE CALCULATION
// =============================================================================

export function calculateSessionProfiles(
    bars: OHLCVBar[],
    sessionStartHour: number = 9,  // Market open hour
    sessionStartMinute: number = 30,
    config: Partial<VolumeProfileConfig> = {}
): Map<string, VolumeProfileData> {
    const sessions = new Map<string, OHLCVBar[]>();

    // Group bars by session/date
    for (const bar of bars) {
        const date = new Date(bar.timestamp);
        const hour = date.getHours();
        const minute = date.getMinutes();
        
        // Determine session date (handle overnight sessions)
        let sessionDate = date.toISOString().split('T')[0];
        
        // If before session start, it belongs to previous session
        if (hour < sessionStartHour || (hour === sessionStartHour && minute < sessionStartMinute)) {
            const prevDay = new Date(date);
            prevDay.setDate(prevDay.getDate() - 1);
            sessionDate = prevDay.toISOString().split('T')[0];
        }

        if (!sessions.has(sessionDate)) {
            sessions.set(sessionDate, []);
        }
        sessions.get(sessionDate)!.push(bar);
    }

    // Calculate profile for each session
    const profiles = new Map<string, VolumeProfileData>();
    for (const [date, sessionBars] of sessions) {
        profiles.set(date, calculateVolumeProfile(sessionBars, config));
    }

    return profiles;
}

// =============================================================================
// COMPOSITE PROFILE (TPO-like time splits)
// =============================================================================

export interface TimeProfileSplit {
    startTime: number;
    endTime: number;
    bins: PriceBin[];
    letter: string; // A, B, C, etc. for TPO
}

export function calculateCompositeProfile(
    bars: OHLCVBar[],
    splitMinutes: number = 30, // TPO period length
    config: Partial<VolumeProfileConfig> = {}
): { profile: VolumeProfileData; splits: TimeProfileSplit[] } {
    if (bars.length === 0) {
        return { profile: createEmptyProfile(), splits: [] };
    }

    // Overall profile
    const profile = calculateVolumeProfile(bars, config);

    // Time-based splits
    const splits: TimeProfileSplit[] = [];
    const splitMs = splitMinutes * 60 * 1000;
    const startTime = bars[0].timestamp;
    const endTime = bars[bars.length - 1].timestamp;

    let splitStart = startTime;
    let letter = 'A';

    while (splitStart < endTime) {
        const splitEnd = splitStart + splitMs;
        const splitBars = bars.filter(b => b.timestamp >= splitStart && b.timestamp < splitEnd);

        if (splitBars.length > 0) {
            const splitProfile = calculateVolumeProfile(splitBars, config);
            splits.push({
                startTime: splitStart,
                endTime: splitEnd,
                bins: splitProfile.bins,
                letter,
            });
        }

        splitStart = splitEnd;
        letter = String.fromCharCode(letter.charCodeAt(0) + 1);
        if (letter > 'Z') letter = 'a'; // Continue with lowercase after Z
    }

    return { profile, splits };
}

// =============================================================================
// DEVELOPING PROFILE (real-time updates)
// =============================================================================

export class DevelopingVolumeProfile {
    private bars: OHLCVBar[] = [];
    private config: VolumeProfileConfig;
    private cachedProfile: VolumeProfileData | null = null;

    constructor(config: Partial<VolumeProfileConfig> = {}) {
        this.config = {
            scope: 'visible',
            rowCount: 48,
            valueAreaPercent: 70,
            showPOC: true,
            showValueArea: true,
            showDeveloping: true,
            position: 'left',
            width: 20,
            opacity: 0.6,
            colorScheme: 'gradient',
            ...config,
        };
    }

    addBar(bar: OHLCVBar): VolumeProfileData {
        this.bars.push(bar);
        this.cachedProfile = null; // Invalidate cache
        return this.getProfile();
    }

    updateLastBar(bar: OHLCVBar): VolumeProfileData {
        if (this.bars.length > 0) {
            this.bars[this.bars.length - 1] = bar;
            this.cachedProfile = null;
        }
        return this.getProfile();
    }

    getProfile(): VolumeProfileData {
        if (!this.cachedProfile) {
            this.cachedProfile = calculateVolumeProfile(this.bars, this.config);
        }
        return this.cachedProfile;
    }

    reset(): void {
        this.bars = [];
        this.cachedProfile = null;
    }

    setBars(bars: OHLCVBar[]): VolumeProfileData {
        this.bars = [...bars];
        this.cachedProfile = null;
        return this.getProfile();
    }
}
