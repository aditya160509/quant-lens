/**
 * Volume Profile Types
 * Types for volume profile calculation and rendering
 */

import type { OHLCVBar } from '../types';

// =============================================================================
// PROFILE TYPES
// =============================================================================

export type ProfileScope = 'visible' | 'session' | 'fixed' | 'custom';

export interface VolumeProfileConfig {
    scope: ProfileScope;
    rowCount: number;         // Number of price bins (24-100)
    valueAreaPercent: number; // Typically 70%
    showPOC: boolean;
    showValueArea: boolean;
    showDeveloping: boolean;  // Update in real-time
    position: 'left' | 'right';
    width: number;            // Width as percentage of chart (10-50%)
    opacity: number;          // Bar opacity (0-1)
    colorScheme: 'gradient' | 'single' | 'updown';
}

export const DEFAULT_VOLUME_PROFILE_CONFIG: VolumeProfileConfig = {
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
};

// =============================================================================
// CALCULATION TYPES
// =============================================================================

export interface PriceBin {
    priceHigh: number;
    priceLow: number;
    priceMiddle: number;
    volume: number;
    buyVolume: number;   // Volume from up candles
    sellVolume: number;  // Volume from down candles
    barCount: number;    // Number of bars contributing
}

export interface ValueArea {
    high: number;       // VAH (Value Area High)
    low: number;        // VAL (Value Area Low)
    volume: number;     // Total volume in value area
    percent: number;    // Actual percentage (may differ from target)
}

export interface VolumeProfileData {
    bins: PriceBin[];
    poc: {
        price: number;
        volume: number;
        binIndex: number;
    };
    valueArea: ValueArea;
    totalVolume: number;
    priceHigh: number;
    priceLow: number;
    barCount: number;
    startTime: number;
    endTime: number;
}

// =============================================================================
// RENDERING TYPES
// =============================================================================

export interface VolumeProfileRenderOptions {
    canvasWidth: number;
    canvasHeight: number;
    priceToY: (price: number) => number;
    yToPrice: (y: number) => number;
    config: VolumeProfileConfig;
    theme: {
        pocColor: string;
        vahColor: string;
        valColor: string;
        barColorUp: string;
        barColorDown: string;
        barColorNeutral: string;
        textColor: string;
    };
}

// =============================================================================
// SESSION TYPES (for session-based profiles)
// =============================================================================

export interface SessionProfile {
    sessionId: string;
    sessionDate: string;
    profile: VolumeProfileData;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

export function createEmptyProfile(): VolumeProfileData {
    return {
        bins: [],
        poc: { price: 0, volume: 0, binIndex: -1 },
        valueArea: { high: 0, low: 0, volume: 0, percent: 0 },
        totalVolume: 0,
        priceHigh: 0,
        priceLow: 0,
        barCount: 0,
        startTime: 0,
        endTime: 0,
    };
}
