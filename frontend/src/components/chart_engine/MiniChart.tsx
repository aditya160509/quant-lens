/**
 * MiniChart Component
 * A context-free, lightweight chart for grid cells
 * Uses lightweight-charts library for rendering
 */

'use client';

import React, { useRef, useEffect, useMemo } from 'react';
import {
    createChart,
    IChartApi,
    ISeriesApi,
    Time,
    ColorType,
    CandlestickSeries,
} from 'lightweight-charts';
import { CHART_THEME, type OHLCVBar } from './types';

interface MiniChartProps {
    bars: OHLCVBar[];
    width: number;
    height: number;
    symbol?: string;
}

export default function MiniChart({ bars, width, height, symbol }: MiniChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const isInitializedRef = useRef(false);

    // Convert OHLCV bars to chart format
    const chartData = useMemo(() => {
        if (!bars || bars.length === 0) return [];
        return bars.map(bar => ({
            time: (bar.timestamp / 1000) as Time,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
        }));
    }, [bars]);

    // Initialize chart
    useEffect(() => {
        if (!containerRef.current || width <= 0 || height <= 0) return;

        // Remove existing chart if any
        if (chartRef.current) {
            chartRef.current.remove();
        }

        const chart = createChart(containerRef.current, {
            width,
            height,
            layout: {
                background: { type: ColorType.Solid, color: CHART_THEME.bgPrimary },
                textColor: CHART_THEME.textSecondary,
                fontFamily: CHART_THEME.fontMono,
                fontSize: 10,
                attributionLogo: false, // Hide TradingView attribution logo
            },
            grid: {
                vertLines: { color: CHART_THEME.gridColorLight },
                horzLines: { color: CHART_THEME.gridColorLight },
            },
            rightPriceScale: {
                borderColor: CHART_THEME.border,
                scaleMargins: { top: 0.1, bottom: 0.1 },
            },
            timeScale: {
                borderColor: CHART_THEME.border,
                timeVisible: true,
                secondsVisible: false,
            },
            handleScroll: true,
            handleScale: true,
        });

        chartRef.current = chart;

        // Create candlestick series
        const series = chart.addSeries(CandlestickSeries, {
            upColor: CHART_THEME.upColor,
            downColor: CHART_THEME.downColor,
            borderVisible: false,
            wickUpColor: CHART_THEME.upColor,
            wickDownColor: CHART_THEME.downColor,
        });
        seriesRef.current = series;
        isInitializedRef.current = true;

        // If we already have data, set it immediately
        if (chartData.length > 0) {
            series.setData(chartData);
            chart.timeScale().fitContent();
        }

        return () => {
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
            isInitializedRef.current = false;
        };
    }, [width, height, chartData]); // Added chartData to dependencies

    // Update data when bars change
    useEffect(() => {
        if (!seriesRef.current || !isInitializedRef.current) return;
        
        if (chartData.length > 0) {
            seriesRef.current.setData(chartData);
            
            // Fit content
            if (chartRef.current) {
                chartRef.current.timeScale().fitContent();
            }
        }
    }, [chartData]);

    // Handle resize
    useEffect(() => {
        if (chartRef.current && width > 0 && height > 0) {
            chartRef.current.applyOptions({ width, height });
        }
    }, [width, height]);

    return (
        <div style={{ position: 'relative', width, height }}>
            {/* Chart Container - always render */}
            <div 
                ref={containerRef}
                style={{ 
                    width, 
                    height, 
                    position: 'absolute',
                    top: 0,
                    left: 0,
                }}
            />
            
            {/* Loading overlay when no data */}
            {bars.length === 0 && (
                <div 
                    style={{ 
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width, 
                        height, 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        color: CHART_THEME.textMuted,
                        fontSize: 10,
                        fontFamily: CHART_THEME.fontMono,
                        background: CHART_THEME.bgPrimary,
                        zIndex: 5,
                    }}
                >
                    Loading {symbol}...
                </div>
            )}
        </div>
    );
}
