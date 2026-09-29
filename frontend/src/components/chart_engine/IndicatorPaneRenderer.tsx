/**
 * Indicator Pane Renderer
 * Renders indicator data in a separate chart pane (RSI, MACD, etc.)
 */

'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import { CHART_THEME } from './types';
import type { IndicatorOutput, OHLCVBar } from './types';

// =============================================================================
// TYPES
// =============================================================================

interface IndicatorPaneRendererProps {
    indicatorId: string;
    indicatorName: string;
    output: IndicatorOutput | null;
    bars: OHLCVBar[];
    width: number;
    height: number;
    visibleRange: { startIndex: number; endIndex: number };
    hoveredIndex?: number | null;
    anchorIndex?: number | null;
    onHover?: (index: number | null) => void;
    /** Whether to show the time axis at the bottom of this pane */
    showTimeAxis?: boolean;
}

interface IndicatorRenderConfig {
    type: 'line' | 'histogram' | 'area' | 'overbought_oversold';
    color: string;
    secondaryColor?: string;
    fillOpacity?: number;
    levels?: { value: number; color: string; dashed?: boolean }[];
    zones?: { from: number; to: number; color: string }[];
}

// =============================================================================
// INDICATOR RENDER CONFIGS
// =============================================================================

const INDICATOR_CONFIGS: Record<string, IndicatorRenderConfig> = {
    rsi: {
        type: 'overbought_oversold',
        color: '#9b5de5',
        levels: [
            { value: 70, color: CHART_THEME.downColor, dashed: true },
            { value: 30, color: CHART_THEME.upColor, dashed: true },
            { value: 50, color: CHART_THEME.textMuted, dashed: true },
        ],
        zones: [
            { from: 0, to: 30, color: CHART_THEME.upColor + '15' },
            { from: 70, to: 100, color: CHART_THEME.downColor + '15' },
        ],
    },
    macd: {
        type: 'histogram',
        color: CHART_THEME.accentBlue,
        secondaryColor: CHART_THEME.accent,
        levels: [{ value: 0, color: CHART_THEME.textMuted, dashed: true }],
    },
    stochastic: {
        type: 'overbought_oversold',
        color: '#00bfff',
        secondaryColor: '#ff6b6b',
        levels: [
            { value: 80, color: CHART_THEME.downColor, dashed: true },
            { value: 20, color: CHART_THEME.upColor, dashed: true },
        ],
        zones: [
            { from: 0, to: 20, color: CHART_THEME.upColor + '15' },
            { from: 80, to: 100, color: CHART_THEME.downColor + '15' },
        ],
    },
    atr: {
        type: 'line',
        color: '#ff9f1c',
    },
    obv: {
        type: 'area',
        color: '#2ec4b6',
        fillOpacity: 0.2,
    },
    cci: {
        type: 'line',
        color: '#e056fd',
        levels: [
            { value: 100, color: CHART_THEME.downColor, dashed: true },
            { value: -100, color: CHART_THEME.upColor, dashed: true },
            { value: 0, color: CHART_THEME.textMuted, dashed: true },
        ],
    },
    mfi: {
        type: 'overbought_oversold',
        color: '#00d9ff',
        levels: [
            { value: 80, color: CHART_THEME.downColor, dashed: true },
            { value: 20, color: CHART_THEME.upColor, dashed: true },
        ],
        zones: [
            { from: 0, to: 20, color: CHART_THEME.upColor + '15' },
            { from: 80, to: 100, color: CHART_THEME.downColor + '15' },
        ],
    },
    adx: {
        type: 'line',
        color: '#ffd166',
        secondaryColor: CHART_THEME.upColor,
        levels: [
            { value: 25, color: CHART_THEME.textMuted, dashed: true },
        ],
    },
    momentum: {
        type: 'histogram',
        color: '#06d6a0',
        levels: [{ value: 0, color: CHART_THEME.textMuted, dashed: true }],
    },
    roc: {
        type: 'line',
        color: '#118ab2',
        levels: [{ value: 0, color: CHART_THEME.textMuted, dashed: true }],
    },
};

const DEFAULT_CONFIG: IndicatorRenderConfig = {
    type: 'line',
    color: CHART_THEME.accent,
};

// =============================================================================
// COMPONENT
// =============================================================================

export function IndicatorPaneRenderer({
    indicatorId,
    indicatorName,
    output,
    bars,
    width,
    height,
    visibleRange,
    hoveredIndex,
    anchorIndex,
    onHover,
    showTimeAxis = false,
}: IndicatorPaneRendererProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const config = INDICATOR_CONFIGS[indicatorId] || DEFAULT_CONFIG;

    // Calculate Y scale
    const getYRange = useCallback(() => {
        if (!output || output.series.length === 0) {
            return { min: 0, max: 100 };
        }

        // Special Y-Range for common oscillators (TradingView Norm)
        if (['rsi', 'stochastic', 'mfi', 'williamsR'].includes(indicatorId)) {
            if (indicatorId === 'williamsR') return { min: -100, max: 0 };
            return { min: 0, max: 100 };
        }
        if (indicatorId === 'cci') return { min: -300, max: 300 };

        const visibleData = output.series.slice(visibleRange.startIndex, visibleRange.endIndex + 1);
        let min = Infinity;
        let max = -Infinity;

        visibleData.forEach(point => {
            if (point.value !== null && !isNaN(point.value)) {
                min = Math.min(min, point.value);
                max = Math.max(max, point.value);
            }
            // Also check extra values (e.g., MACD signal line)
            if (point.extra) {
                Object.values(point.extra).forEach(v => {
                    if (typeof v === 'number' && !isNaN(v)) {
                        min = Math.min(min, v);
                        max = Math.max(max, v);
                    }
                });
            }
        });

        // Add padding
        const range = max - min;
        const padding = range * 0.1 || 10;
        return { min: min - padding, max: max + padding };
    }, [output, visibleRange, indicatorId]);

    // Render
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !output) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);

        // Clear and Background
        ctx.fillStyle = CHART_THEME.bgPrimary;
        ctx.fillRect(0, 0, width, height);

        const yRange = getYRange();
        const TIME_AXIS_HEIGHT = showTimeAxis ? 24 : 0; // Match ChartCanvas exactly
        const VERTICAL_PADDING = 25; // TV style breathing room (top/bottom)
        const currentHeight = height - TIME_AXIS_HEIGHT;
        const drawableHeight = currentHeight - (VERTICAL_PADDING * 2);

        const priceToY = (value: number) => {
            if (!yRange) return 0;
            const normalized = (value - yRange.min) / (yRange.max - yRange.min);
            return currentHeight - VERTICAL_PADDING - (normalized * drawableHeight);
        };

        const AXIS_WIDTH = 60; // Locked to match ChartCanvas exactly
        const chartWidth = width - AXIS_WIDTH;
        const visibleCount = visibleRange.endIndex - visibleRange.startIndex + 1;
        const barWidth = chartWidth / visibleCount;

        // Draw zones
        if (config.zones) {
            config.zones.forEach(zone => {
                const y1 = priceToY(zone.to);
                const y2 = priceToY(zone.from);
                ctx.fillStyle = zone.color;
                ctx.fillRect(0, y1, chartWidth, y2 - y1);
            });
        }

        // Draw levels
        if (config.levels) {
            config.levels.forEach(level => {
                const y = priceToY(level.value);
                ctx.strokeStyle = level.color;
                ctx.lineWidth = 1;
                if (level.dashed) {
                    ctx.setLineDash([4, 4]);
                }
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(chartWidth, y);
                ctx.stroke();
                ctx.setLineDash([]);

                // Level label
                ctx.fillStyle = level.color;
                ctx.font = '9px monospace';
                ctx.textAlign = 'left';
                ctx.fillText(String(level.value), 5, y - 3);
            });
        }

        // Draw indicator data
        const visibleOutput = output.series.slice(visibleRange.startIndex, visibleRange.endIndex + 1);

        if (config.type === 'line' || config.type === 'overbought_oversold') {
            // Main line
            ctx.strokeStyle = config.color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();

            let started = false;
            visibleOutput.forEach((point, i) => {
                if (point.value === null || isNaN(point.value)) return;
                const x = i * barWidth + barWidth / 2;
                const y = priceToY(point.value);

                if (!started) {
                    ctx.moveTo(x, y);
                    started = true;
                } else {
                    ctx.lineTo(x, y);
                }
            });
            ctx.stroke();

            // Secondary line (e.g., %D for Stochastic)
            if (config.secondaryColor) {
                ctx.strokeStyle = config.secondaryColor;
                ctx.lineWidth = 1;
                ctx.beginPath();
                started = false;
                visibleOutput.forEach((point, i) => {
                    const d = point.extra?.d ?? point.extra?.signal;
                    if (d === undefined || isNaN(d as number)) return;
                    const x = i * barWidth + barWidth / 2;
                    const y = priceToY(d as number);

                    if (!started) {
                        ctx.moveTo(x, y);
                        started = true;
                    } else {
                        ctx.lineTo(x, y);
                    }
                });
                ctx.stroke();
            }
        }

        if (config.type === 'histogram') {
            visibleOutput.forEach((point, i) => {
                if (point.value === null || isNaN(point.value)) return;

                const x = i * barWidth;
                const y = priceToY(point.value);
                const zeroY = priceToY(0);
                const barHeight = Math.abs(y - zeroY);

                // Color based on positive/negative
                ctx.fillStyle = point.value >= 0 ? CHART_THEME.upColor : CHART_THEME.downColor;
                ctx.fillRect(
                    x + barWidth * 0.2,
                    point.value >= 0 ? y : zeroY,
                    barWidth * 0.6,
                    barHeight
                );
            });

            // MACD line and signal line
            if (indicatorId === 'macd') {
                // MACD line
                ctx.strokeStyle = config.color;
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                let started = false;
                visibleOutput.forEach((point, i) => {
                    const macdValue = point.value; // Use point.value as computed in registry.ts
                    if (macdValue === null || isNaN(macdValue as number)) return;
                    const x = i * barWidth + barWidth / 2;
                    const y = priceToY(macdValue as number);
                    if (!started) {
                        ctx.moveTo(x, y);
                        started = true;
                    } else {
                        ctx.lineTo(x, y);
                    }
                });
                ctx.stroke();

                // Signal line
                ctx.strokeStyle = config.secondaryColor || '#ff6b6b';
                ctx.lineWidth = 1;
                ctx.beginPath();
                started = false;
                visibleOutput.forEach((point, i) => {
                    const signal = point.extra?.signal;
                    if (signal === undefined || isNaN(signal as number)) return;
                    const x = i * barWidth + barWidth / 2;
                    const y = priceToY(signal as number);
                    if (!started) {
                        ctx.moveTo(x, y);
                        started = true;
                    } else {
                        ctx.lineTo(x, y);
                    }
                });
                ctx.stroke();
            }
        }

        if (config.type === 'area') {
            // Area fill
            ctx.fillStyle = config.color + Math.round((config.fillOpacity || 0.2) * 255).toString(16).padStart(2, '0');
            ctx.beginPath();
            ctx.moveTo(0, height);

            visibleOutput.forEach((point, i) => {
                if (point.value === null || isNaN(point.value)) return;
                const x = i * barWidth + barWidth / 2;
                const y = priceToY(point.value);
                ctx.lineTo(x, y);
            });

            ctx.lineTo(chartWidth, height);
            ctx.lineTo(0, height);
            ctx.closePath();
            ctx.fill();

            // Line
            ctx.strokeStyle = config.color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            let started = false;
            visibleOutput.forEach((point, i) => {
                if (point.value === null || isNaN(point.value)) return;
                const x = i * barWidth + barWidth / 2;
                const y = priceToY(point.value);
                if (!started) {
                    ctx.moveTo(x, y);
                    started = true;
                } else {
                    ctx.lineTo(x, y);
                }
            });
            ctx.stroke();
        }

        // Helper for compact labels (e.g., 1.2M)
        const formatValue = (val: number) => {
            if (Math.abs(val) >= 1000000) return (val / 1000000).toFixed(1) + 'M';
            if (Math.abs(val) >= 1000) return (val / 1000).toFixed(1) + 'K';
            return val.toFixed(2);
        };

        // Hover crosshair (Ghost Line)
        if (hoveredIndex !== null && hoveredIndex !== undefined) {
            const localIndex = hoveredIndex - visibleRange.startIndex;
            if (localIndex >= 0 && localIndex < visibleCount) {
                const x = localIndex * barWidth + barWidth / 2;
                
                // Draw Vertical Crosshair Line (Ghost Line)
                ctx.strokeStyle = CHART_THEME.textSecondary + '40';
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, height);
                ctx.stroke();
                ctx.setLineDash([]);

                const point = visibleOutput[localIndex];
                if (point && point.value !== null && !isNaN(point.value)) {
                    const y = priceToY(point.value);

                    // Value dot
                    ctx.fillStyle = config.color;
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, Math.PI * 2);
                    ctx.fill();

                    // Value label box on the Y-Axis
                    const valStr = formatValue(point.value);
                    ctx.fillStyle = config.color;
                    ctx.fillRect(chartWidth, y - 8, AXIS_WIDTH, 16);
                    ctx.fillStyle = '#000000';
                    ctx.font = 'bold 9px Inter, monospace';
                    ctx.textAlign = 'right';
                    ctx.fillText(valStr, width - 4, y + 3);
                }

                // If this is the last pane, draw the Yellow Date Label
                if (showTimeAxis) {
                    const bar = bars[hoveredIndex];
                    if (bar) {
                        const date = new Date(bar.timestamp);
                        const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
                        const dateStr = date.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: '2-digit' });
                        const fullLabel = `${dateStr} ${timeStr}`;

                        ctx.font = 'bold 10px Inter, monospace';
                        const labelWidth = ctx.measureText(fullLabel).width + 16;
                        const labelX = Math.max(labelWidth/2, Math.min(chartWidth - labelWidth/2, x));
                        
                        // Yellow background box
                        ctx.fillStyle = CHART_THEME.accent;
                        ctx.fillRect(labelX - labelWidth/2, currentHeight, labelWidth, TIME_AXIS_HEIGHT);
                        
                        // Black text
                        ctx.fillStyle = '#000000';
                        ctx.textAlign = 'center';
                        ctx.fillText(fullLabel, labelX, currentHeight + (TIME_AXIS_HEIGHT/2) + 4);
                    }
                }
            }
        }

        // Indicator name label - Bloomberg/TV style (Top Left, muted)
        ctx.font = 'bold 10px Inter, sans-serif';
        ctx.fillStyle = CHART_THEME.textSecondary;
        ctx.textAlign = 'left';
        ctx.fillText(indicatorName.toUpperCase(), 12, 18);

        // Y-AXIS - Right side (Clean Transparent Axis)
        // =====================================================================
        
        // Draw axis border only (no background for TV look)
        ctx.strokeStyle = CHART_THEME.border;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(chartWidth, 0);
        ctx.lineTo(chartWidth, height);
        ctx.stroke();
        
        // Calculate Y-axis values (Aligned with padded lines)
        const numLabels = 5;
        ctx.font = '10px Inter, monospace';
        ctx.textAlign = 'right';
        ctx.fillStyle = CHART_THEME.textSecondary;
        
        for (let i = 0; i <= numLabels; i++) {
            const ratio = i / numLabels;
            // Value is from max (top) to min (bottom)
            const value = yRange.max - (ratio * (yRange.max - yRange.min));
            const y = priceToY(value);
            
            // Draw tick
            ctx.strokeStyle = CHART_THEME.border;
            ctx.beginPath();
            ctx.moveTo(chartWidth, y);
            ctx.lineTo(chartWidth + 4, y);
            ctx.stroke();
            
            // Draw label
            ctx.fillText(formatValue(value), width - 4, y + 3);
        }
        
        // Current value label (last visible point)
        if (visibleOutput.length > 0) {
            const lastPoint = visibleOutput[visibleOutput.length - 1];
            if (lastPoint && lastPoint.value !== null && !isNaN(lastPoint.value)) {
                const currentY = priceToY(lastPoint.value);
                
                // Draw current value box
                ctx.fillStyle = config.color;
                ctx.fillRect(chartWidth, currentY - 8, AXIS_WIDTH, 16);
                
                // Draw current value text
                ctx.fillStyle = '#000000';
                ctx.font = 'bold 10px Inter, monospace';
                ctx.fillText(formatValue(lastPoint.value), width - 4, currentY + 4);
            }
        }

        // Draw Time Axis if requested (for the last pane)
        if (showTimeAxis) {
            const axisY = currentHeight;
            
            // Background
            ctx.fillStyle = CHART_THEME.bgSecondary;
            ctx.fillRect(0, axisY, chartWidth, TIME_AXIS_HEIGHT);
            
            // Border
            ctx.strokeStyle = CHART_THEME.border;
            ctx.lineWidth = 1;
            ctx.strokeRect(0, axisY, chartWidth, TIME_AXIS_HEIGHT);
            
            // 1. Periodic Simple labels
            ctx.fillStyle = CHART_THEME.textSecondary;
            ctx.font = '9px monospace';
            ctx.textAlign = 'center';
            
            const step = Math.max(1, Math.floor(visibleCount / 6));
            for (let i = 0; i < visibleCount; i += step) {
                const x = i * barWidth + barWidth / 2;
                const bar = bars[visibleRange.startIndex + i];
                if (bar) {
                    const date = new Date(bar.timestamp);
                    const label = date.getHours() === 0 ? date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'}) : date.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit', hour12: false});
                    ctx.fillText(label, x, axisY + 12);
                }
            }

            // 2. Persistent Selected Label (anchorIndex)
            if (anchorIndex !== null && anchorIndex !== undefined) {
                const localAnchorIdx = anchorIndex - visibleRange.startIndex;
                if (localAnchorIdx >= 0 && localAnchorIdx < visibleCount) {
                    const x = localAnchorIdx * barWidth + barWidth / 2;
                    const bar = bars[anchorIndex];
                    if (bar) {
                        const date = new Date(bar.timestamp);
                        const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
                        ctx.font = 'bold 9px Inter, monospace';
                        const tw = ctx.measureText(label).width + 10;
                        ctx.fillStyle = '#363c4e'; // Dark selection color
                        ctx.fillRect(x - tw/2, axisY, tw, TIME_AXIS_HEIGHT);
                        ctx.fillStyle = '#ffffff';
                        ctx.fillText(label, x, axisY + 12);
                    }
                }
            }

            // 3. Current Last Bar Label
            if (bars.length > 0) {
                const lastIdx = bars.length - 1;
                const localLastIdx = lastIdx - visibleRange.startIndex;
                if (localLastIdx >= visibleCount - 2) { // Only if at/near far right
                    const x = localLastIdx * barWidth + barWidth / 2;
                    const lastBar = bars[lastIdx];
                    const date = new Date(lastBar.timestamp);
                    const label = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
                    ctx.font = 'bold 9px monospace';
                    const tw = ctx.measureText(label).width + 10;
                    ctx.fillStyle = CHART_THEME.bgSecondary;
                    ctx.fillRect(chartWidth - tw, axisY, tw, TIME_AXIS_HEIGHT);
                    ctx.fillStyle = CHART_THEME.textPrimary;
                    ctx.fillText(label, chartWidth - tw/2, axisY + 12);
                }
            }
        }
    }, [output, width, height, visibleRange, hoveredIndex, anchorIndex, config, getYRange, indicatorId, indicatorName, showTimeAxis, bars]);

    // Handle mouse move for hover
    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!onHover || !output) return;

        const rect = (e.target as HTMLCanvasElement).getBoundingClientRect();
        const x = e.clientX - rect.left;
        
        const AXIS_WIDTH = 60;
        const chartWidth = width - AXIS_WIDTH;
        if (x > chartWidth) return;

        const visibleCount = visibleRange.endIndex - visibleRange.startIndex + 1;
        const barWidth = chartWidth / visibleCount;
        const index = Math.floor(x / barWidth) + visibleRange.startIndex;

        const totalBars = bars.length;
        if (index >= visibleRange.startIndex && index <= visibleRange.endIndex && index < totalBars) {
            onHover(index);
        }
    }, [onHover, output, visibleRange, width, bars.length]);

    const handleMouseLeave = useCallback(() => {
        if (onHover) onHover(null);
    }, [onHover]);

    return (
        <canvas
            ref={canvasRef}
            style={{ width, height }}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
        />
    );
}

export default IndicatorPaneRenderer;
