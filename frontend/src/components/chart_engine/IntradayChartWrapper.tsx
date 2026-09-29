/**
 * Unified Chart Wrapper
 * Integration wrapper for Q360ChartCore in Security and Markets pages
 * Handles both intraday AND daily timeframes
 */

'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { CHART_THEME } from './types';
import type { Timeframe, SeriesData, OHLCVBar } from './types';
import { US_EQUITY_SESSION } from './DataAdapter/intraday';

// Dynamic import to avoid SSR issues with canvas
const Q360ChartCore = dynamic(() => import('./q360_chart_core'), {
    ssr: false,
    loading: () => (
        <div
            className="flex items-center justify-center h-full"
            style={{ background: CHART_THEME.bgPrimary }}
        >
            <span className="text-sm font-mono" style={{ color: CHART_THEME.textSecondary }}>
                Loading Chart Engine...
            </span>
        </div>
    ),
});

// =============================================================================
// TYPES
// =============================================================================

interface IntradayChartWrapperProps {
    symbol: string;
    interval: Timeframe;
    height?: number;
    width?: number; // Add width prop
    existingData?: {
        bars?: OHLCVBar[];
        dates?: string[];
        open?: number[];
        high?: number[];
        low?: number[];
        close?: number[];
        volume?: number[];
    };
    onSymbolChange?: (symbol: string) => void;
    onIntervalChange?: (interval: string) => void;
    onIndicatorsChange?: (indicators: Record<string, boolean>) => void;
}

export default function IntradayChartWrapper({
    symbol,
    interval,
    height = 500,
    width, // Destructure width
    existingData,
    onSymbolChange,
    onIntervalChange,
    onIndicatorsChange,
}: IntradayChartWrapperProps) {
    // ... (client check)

    const timeframe: Timeframe = interval as Timeframe;

    return (
        <Q360ChartCore
            symbol={symbol}
            timeframe={timeframe}
            mode="intraday"
            height={height}
            width={width} // Pass width
            onSymbolChange={onSymbolChange}
            onTimeframeChange={(tf) => onIntervalChange?.(tf)}
            onIndicatorsChange={onIndicatorsChange}
        />
    );
}

// =============================================================================
// UTILITY: Convert existing page data to OHLCV bars
// =============================================================================

export function convertToOHLCVBars(data: {
    dates?: string[];
    open?: number[];
    high?: number[];
    low?: number[];
    close?: number[];
    volume?: number[];
}): OHLCVBar[] {
    if (!data.dates || !data.close) return [];

    return data.dates.map((date, i) => ({
        timestamp: new Date(date).getTime(),
        open: data.open?.[i] ?? data.close?.[i] ?? 0,
        high: data.high?.[i] ?? data.close?.[i] ?? 0,
        low: data.low?.[i] ?? data.close?.[i] ?? 0,
        close: data.close?.[i] ?? 0,
        volume: data.volume?.[i] ?? 0,
    }));
}

export function createSeriesData(
    symbol: string,
    timeframe: Timeframe,
    bars: OHLCVBar[],
    previousClose?: number
): SeriesData {
    return {
        symbol,
        timeframe,
        bars,
        session: US_EQUITY_SESSION,
        previousClose,
    };
}
