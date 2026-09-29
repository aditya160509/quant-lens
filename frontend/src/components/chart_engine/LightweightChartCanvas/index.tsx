/**
 * Lightweight Chart Canvas
 * Using TradingView's official lightweight-charts library (v5+)
 * Per CHART_ENGINE_SPEC.md and CHART_WORKSPACE_TECHNICAL_AUDIT_REPORT.md recommendations
 * 
 * This replaces the custom canvas implementation with the professional-grade
 * lightweight-charts library which provides:
 * - Native log/percent scaling out of the box
 * - GPU-accelerated canvas rendering
 * - Crosshair synchronization
 * - Multi-series overlays with proper normalization
 */

'use client';

import React, { useRef, useEffect, useCallback, useMemo } from 'react';
import {
    createChart,
    IChartApi,
    ISeriesApi,
    Time,
    CrosshairMode,
    PriceScaleMode,
    ColorType,
    CandlestickSeriesOptions,
    LineSeriesOptions,
    HistogramSeriesOptions,
    CandlestickSeries,
    LineSeries,
    HistogramSeries,
} from 'lightweight-charts';
import { useChart } from '../state/ChartContext';
import { CHART_THEME, type OHLCVBar } from '../types';

// =============================================================================
// TYPES
// =============================================================================

interface LightweightChartCanvasProps {
    width: number;
    height: number;
    onBarHover?: (index: number | null, bar: OHLCVBar | null) => void;
    onBarClick?: (index: number, bar: OHLCVBar) => void;
    compareData?: Record<string, OHLCVBar[]>;
    syncedCrosshairTimestamp?: number | null;
    onCrosshairMove?: (timestamp: number | null) => void;
}

// Compare symbol colors (Purple and Cyan as per spec)
const COMPARE_COLORS = ['#8b5cf6', '#06b6d4', '#f97316', '#10b981'];

// =============================================================================
// HELPER: Convert OHLCV bars to lightweight-charts format
// =============================================================================

interface CandlestickData {
    time: Time;
    open: number;
    high: number;
    low: number;
    close: number;
}

interface LineData {
    time: Time;
    value: number;
}

interface VolumeData {
    time: Time;
    value: number;
    color: string;
}

function toChartData(bars: OHLCVBar[]): CandlestickData[] {
    return bars.map(bar => ({
        time: (bar.timestamp / 1000) as Time, // Convert ms to seconds
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
    }));
}

function toLineData(bars: OHLCVBar[], normalize = false, basePrice?: number): LineData[] {
    const firstClose = bars[0]?.close || 1;
    
    return bars.map(bar => ({
        time: (bar.timestamp / 1000) as Time,
        value: normalize && basePrice 
            ? ((bar.close - basePrice) / basePrice) * 100 // Percent change
            : bar.close,
    }));
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function LightweightChartCanvas({
    width,
    height,
    onBarHover,
    onBarClick,
    compareData = {},
    syncedCrosshairTimestamp,
    onCrosshairMove,
}: LightweightChartCanvasProps) {
    const { state } = useChart();
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const mainSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const compareSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
    const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

    // Store callbacks in refs to avoid stale closures
    const onBarHoverRef = useRef(onBarHover);
    const onBarClickRef = useRef(onBarClick);
    const onCrosshairMoveRef = useRef(onCrosshairMove);
    const barsRef = useRef(state.data?.bars);
    
    useEffect(() => {
        onBarHoverRef.current = onBarHover;
        onBarClickRef.current = onBarClick;
        onCrosshairMoveRef.current = onCrosshairMove;
        barsRef.current = state.data?.bars;
    });

    // Get display bars (apply replay cursor if active)
    const displayBars = useMemo(() => {
        const bars = state.data?.bars || [];
        if (state.replay.active) {
            return bars.slice(0, state.replay.cursorIndex + 1);
        }
        return bars;
    }, [state.data?.bars, state.replay.active, state.replay.cursorIndex]);

    // Determine if we should use percent scale mode (when comparing)
    const hasCompareSymbols = Object.keys(compareData).length > 0;
    const scaleMode = hasCompareSymbols || state.config.scaleMode === 'percent'
        ? PriceScaleMode.Percentage
        : state.config.scaleMode === 'log'
            ? PriceScaleMode.Logarithmic
            : PriceScaleMode.Normal;

    // ==========================================================================
    // Initialize Chart
    // ==========================================================================
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // Create chart instance
        const chart = createChart(chartContainerRef.current, {
            width,
            height,
            layout: {
                background: { type: ColorType.Solid, color: CHART_THEME.bgPrimary },
                textColor: CHART_THEME.textSecondary,
                fontFamily: CHART_THEME.fontMono,
                attributionLogo: false, // Hide TradingView attribution logo
            },
            grid: {
                vertLines: { color: state.config.showGrid ? CHART_THEME.gridColorLight : 'transparent' },
                horzLines: { color: state.config.showGrid ? CHART_THEME.gridColorLight : 'transparent' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: {
                    color: CHART_THEME.accent,
                    width: 1,
                    style: 2, // Dashed
                    labelBackgroundColor: CHART_THEME.bgPanel,
                },
                horzLine: {
                    color: CHART_THEME.accent,
                    width: 1,
                    style: 2,
                    labelBackgroundColor: CHART_THEME.bgPanel,
                },
            },
            rightPriceScale: {
                borderColor: CHART_THEME.border,
                scaleMargins: { top: 0.1, bottom: 0.2 },
                mode: scaleMode,
            },
            timeScale: {
                borderColor: CHART_THEME.border,
                timeVisible: true,
                secondsVisible: false,
            },
            handleScroll: { vertTouchDrag: false },
            handleScale: { axisPressedMouseMove: true },
        });

        chartRef.current = chart;

        // Subscribe to crosshair move for sync
        chart.subscribeCrosshairMove((param) => {
            // Only broadcast if it's a user-driven move (has point coordinates)
            // This prevents loops where setCrosshairPosition triggers another broadcast
            if (param.time && param.point && onCrosshairMoveRef.current) {
                onCrosshairMoveRef.current(Number(param.time) * 1000); // Convert back to ms
            }
            
            // Still update hovered bar even for synced moves
            const currentBars = barsRef.current;
            if (param.time && currentBars) {
                const timestamp = Number(param.time) * 1000;
                const index = currentBars.findIndex(b => b.timestamp === timestamp);
                if (index >= 0 && onBarHoverRef.current) {
                    onBarHoverRef.current(index, currentBars[index]);
                }
            }
        });

        // Subscribe to click
        chart.subscribeClick((param) => {
            const currentBars = barsRef.current;
            if (param.time && currentBars) {
                const timestamp = Number(param.time) * 1000;
                const index = currentBars.findIndex(b => b.timestamp === timestamp);
                if (index >= 0 && onBarClickRef.current) {
                    onBarClickRef.current(index, currentBars[index]);
                }
            }
        });

        // Create main candlestick series (v5+ API uses addSeries with type)
        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: CHART_THEME.upColor,
            downColor: CHART_THEME.downColor,
            borderVisible: false,
            wickUpColor: CHART_THEME.upColor,
            wickDownColor: CHART_THEME.downColor,
        });
        mainSeriesRef.current = candleSeries;

        // Create volume series if enabled
        if (state.config.showVolume) {
            const volumeSeries = chart.addSeries(HistogramSeries, {
                color: CHART_THEME.accentBlue,
                priceFormat: { type: 'volume' },
                priceScaleId: '', // Overlay on same pane
            });
            volumeSeries.priceScale().applyOptions({
                scaleMargins: { top: 0.85, bottom: 0 },
            });
            volumeSeriesRef.current = volumeSeries;
        }

        // Store refs for cleanup
        const compareSeriesMap = compareSeriesRef.current;

        return () => {
            chart.remove();
            chartRef.current = null;
            mainSeriesRef.current = null;
            volumeSeriesRef.current = null;
            compareSeriesMap.clear();
        };
    }, [width, height, scaleMode, state.config.showGrid, state.config.showVolume]);

    // ==========================================================================
    // Update Main Series Data
    // ==========================================================================
    useEffect(() => {
        if (!mainSeriesRef.current || displayBars.length === 0) return;

        const chartData = toChartData(displayBars);
        mainSeriesRef.current.setData(chartData);

        // Update volume data
        if (volumeSeriesRef.current) {
            const volumeData: VolumeData[] = displayBars.map(bar => ({
                time: (bar.timestamp / 1000) as Time,
                value: bar.volume,
                color: bar.close >= bar.open 
                    ? 'rgba(0, 255, 136, 0.3)' 
                    : 'rgba(255, 45, 85, 0.3)',
            }));
            volumeSeriesRef.current.setData(volumeData);
        }
    }, [displayBars]);

    // ==========================================================================
    // Update Compare Series (Overlay)
    // Per CHART_ENGINE_SPEC.md Section 1: Percentage-Based Normalization
    // ==========================================================================
    useEffect(() => {
        const chart = chartRef.current;
        if (!chart) return;

        // Store current map reference
        const currentCompareMap = compareSeriesRef.current;

        // Remove old compare series
        currentCompareMap.forEach((series, symbol) => {
            if (!compareData[symbol]) {
                chart.removeSeries(series);
                currentCompareMap.delete(symbol);
            }
        });

        // Add/update compare series
        let colorIndex = 0;
        const basePrice = displayBars[0]?.close || 1;

        Object.entries(compareData).forEach(([symbol, bars]) => {
            if (!bars || bars.length === 0) return;

            let series = currentCompareMap.get(symbol);
            
            if (!series) {
                // Create new line series for compare symbol (v5+ API)
                series = chart.addSeries(LineSeries, {
                    color: COMPARE_COLORS[colorIndex % COMPARE_COLORS.length],
                    lineWidth: 2,
                    priceLineVisible: false,
                    lastValueVisible: true,
                    title: symbol,
                });
                currentCompareMap.set(symbol, series);
            }

            // Normalize to percent change from main symbol's base price
            const lineData = toLineData(bars, hasCompareSymbols, basePrice);
            series.setData(lineData);

            colorIndex++;
        });
    }, [compareData, displayBars, hasCompareSymbols]);

    // ==========================================================================
    // Handle Synced Crosshair from Sibling Charts
    // Per CHART_WORKSPACE_TECHNICAL_AUDIT_REPORT.md Step 2
    // ==========================================================================
    useEffect(() => {
        const chart = chartRef.current;
        const mainSeries = mainSeriesRef.current;
        if (!chart || !mainSeries || !syncedCrosshairTimestamp) return;

        // Find the bar at the synced timestamp
        const timestamp = syncedCrosshairTimestamp / 1000; // Convert to seconds
        
        // Set crosshair position (v5+ API)
        try {
            chart.setCrosshairPosition(0, timestamp as Time, mainSeries);
        } catch {
            // Fallback: lightweight-charts might not support setCrosshairPosition in all versions
        }
    }, [syncedCrosshairTimestamp]);

    // ==========================================================================
    // Resize Handler
    // ==========================================================================
    useEffect(() => {
        if (chartRef.current) {
            chartRef.current.applyOptions({ width, height });
        }
    }, [width, height]);

    // ==========================================================================
    // Update Grid Options
    // ==========================================================================
    useEffect(() => {
        if (chartRef.current) {
            chartRef.current.applyOptions({
                grid: {
                    vertLines: { color: state.config.showGrid ? CHART_THEME.gridColorLight : 'transparent' },
                    horzLines: { color: state.config.showGrid ? CHART_THEME.gridColorLight : 'transparent' },
                },
            });
        }
    }, [state.config.showGrid]);

    // ==========================================================================
    // Update Price Scale Mode
    // ==========================================================================
    useEffect(() => {
        if (chartRef.current) {
            chartRef.current.applyOptions({
                rightPriceScale: { mode: scaleMode },
            });
        }
    }, [scaleMode]);

    return (
        <div
            ref={chartContainerRef}
            style={{
                width,
                height,
                position: 'relative',
                contain: 'strict',
                transform: 'translateZ(0)',
                willChange: 'contents',
            }}
        />
    );
}
