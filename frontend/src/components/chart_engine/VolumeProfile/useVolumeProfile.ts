/**
 * Volume Profile Hook
 * React hook for managing volume profile state and calculations
 */

'use client';

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { OHLCVBar } from '../types';
import type { VolumeProfileConfig, VolumeProfileData } from './volumeProfileTypes';
import { DEFAULT_VOLUME_PROFILE_CONFIG } from './volumeProfileTypes';
import { calculateVolumeProfile, calculateSessionProfiles, DevelopingVolumeProfile } from './volumeProfileCalc';

// =============================================================================
// HOOK
// =============================================================================

interface UseVolumeProfileOptions {
    bars: OHLCVBar[];
    enabled?: boolean;
    config?: Partial<VolumeProfileConfig>;
    visibleRange?: { startIndex: number; endIndex: number };
    sessionBased?: boolean;
}

export function useVolumeProfile(options: UseVolumeProfileOptions) {
    const {
        bars,
        enabled = true,
        config: configOverrides = {},
        visibleRange,
        sessionBased = false,
    } = options;

    const [config, setConfig] = useState<VolumeProfileConfig>({
        ...DEFAULT_VOLUME_PROFILE_CONFIG,
        ...configOverrides,
    });

    const developingProfileRef = useRef(new DevelopingVolumeProfile(config));

    // Get visible bars
    const visibleBars = useMemo(() => {
        if (!visibleRange) return bars;
        return bars.slice(visibleRange.startIndex, visibleRange.endIndex + 1);
    }, [bars, visibleRange]);

    // Calculate main profile
    const profile = useMemo<VolumeProfileData>(() => {
        if (!enabled || visibleBars.length === 0) {
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

        if (config.scope === 'visible') {
            return calculateVolumeProfile(visibleBars, config);
        }

        return calculateVolumeProfile(bars, config);
    }, [enabled, visibleBars, bars, config]);

    // Calculate session profiles if enabled
    const sessionProfiles = useMemo<Map<string, VolumeProfileData>>(() => {
        if (!enabled || !sessionBased || bars.length === 0) {
            return new Map();
        }
        return calculateSessionProfiles(bars, 9, 30, config);
    }, [enabled, sessionBased, bars, config]);

    // Update developing profile when bars change
    useEffect(() => {
        if (enabled && config.showDeveloping) {
            developingProfileRef.current.setBars(bars);
        }
    }, [enabled, bars, config.showDeveloping]);

    // Config updates
    const updateConfig = useCallback((updates: Partial<VolumeProfileConfig>) => {
        setConfig(prev => ({ ...prev, ...updates }));
    }, []);

    const toggleEnabled = useCallback((value?: boolean) => {
        // This would be handled by parent component
    }, []);

    // Computed values
    const pocPrice = profile.poc.price;
    const vahPrice = profile.valueArea.high;
    const valPrice = profile.valueArea.low;

    // Find the bin at a specific price
    const getBinAtPrice = useCallback((price: number) => {
        return profile.bins.find(
            bin => price >= bin.priceLow && price <= bin.priceHigh
        ) || null;
    }, [profile.bins]);

    // Get volume-weighted average price for visible bars
    const vwap = useMemo(() => {
        if (visibleBars.length === 0) return 0;
        
        let sumPriceVolume = 0;
        let sumVolume = 0;
        
        for (const bar of visibleBars) {
            const typicalPrice = (bar.high + bar.low + bar.close) / 3;
            sumPriceVolume += typicalPrice * bar.volume;
            sumVolume += bar.volume;
        }
        
        return sumVolume > 0 ? sumPriceVolume / sumVolume : 0;
    }, [visibleBars]);

    return {
        // State
        enabled,
        config,
        profile,
        sessionProfiles,

        // Key levels
        pocPrice,
        vahPrice,
        valPrice,
        vwap,

        // Actions
        updateConfig,
        toggleEnabled,
        getBinAtPrice,

        // Stats
        totalVolume: profile.totalVolume,
        barCount: profile.barCount,
        maxBinVolume: Math.max(0, ...profile.bins.map(b => b.volume)),
    };
}

export type UseVolumeProfile = ReturnType<typeof useVolumeProfile>;

// =============================================================================
// INDEX EXPORT
// =============================================================================

export * from './volumeProfileTypes';
export * from './volumeProfileCalc';
export * from './volumeProfileRenderer';
