/**
 * Chart Canvas - Main Renderer
 * SVG + Canvas hybrid for high-performance chart rendering
 */

import React, { useRef, useEffect, useCallback, useMemo, useState } from 'react';
import { useChart } from '../state/ChartContext';
import { CHART_THEME, type OHLCVBar, type IndicatorOutput } from '../types';
import { toHeikinAshi, toRenko, toRangeBars } from '../DataAdapter/intraday';
import { getIndicator } from '../IndicatorEngine/registry';

// =============================================================================
// TYPES
// =============================================================================

interface ChartCanvasProps {
    width: number;
    height: number;
    onBarHover?: (index: number | null, bar: OHLCVBar | null) => void;
    onBarClick?: (index: number, bar: OHLCVBar) => void;
    compareData?: Record<string, OHLCVBar[]>;
    syncedCrosshairTimestamp?: number | null;
    onCrosshairMove?: (timestamp: number | null) => void;
    /** Optional external bars for grid rendering - if not provided, use context bars */
    externalBars?: OHLCVBar[];
    /** Optional previous close for percent normalization */
    previousClose?: number;
    /** Current symbol for this canvas (defaults to context symbol) */
    symbol?: string;
    onDoubleClick?: () => void;
    replayActive?: boolean;
    replayCursorIndex?: number;
    replaySelectMode?: boolean;
    anchorIndex?: number;
    visibleGhosts?: string[];
    alphaMode?: 'percent' | 'zscore' | 'ratio';
    /** Pattern detection results */
    detectedPatterns?: any[];
    /** Strategy signal results */
    strategySignals?: Map<string, any>;
    /** Hide the time axis at the bottom */
    hideTimeAxis?: boolean;
}

interface Dimensions {
    chartWidth: number;
    chartHeight: number;
    volumeHeight: number;
    priceAxisWidth: number;
    timeAxisHeight: number;
    marginLeft: number;
    marginTop: number;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const PRICE_AXIS_WIDTH = 60;
const TIME_AXIS_HEIGHT = 24;
const VOLUME_HEIGHT_RATIO = 0.20;
const CANDLE_PADDING = 0.2;

// =============================================================================
// SCALES
// =============================================================================

function createPriceScale(
    priceRange: { min: number; max: number },
    height: number,
    scaleMode: 'auto' | 'manual' | 'log' | 'percent',
    basePrice?: number
) {
    const { min, max } = priceRange;

    if (scaleMode === 'log') {
        const logMin = Math.log10(Math.max(0.01, min));
        const logMax = Math.log10(Math.max(0.01, max));

        return {
            toPixel: (price: number) => {
                const logPrice = Math.log10(Math.max(0.01, price));
                return height - ((logPrice - logMin) / (logMax - logMin)) * height;
            },
            toPrice: (pixel: number) => {
                const ratio = (height - pixel) / height;
                const logPrice = logMin + ratio * (logMax - logMin);
                return Math.pow(10, logPrice);
            },
        };
    }

    if (scaleMode === 'percent' && basePrice) {
        const minPct = ((min - basePrice) / basePrice) * 100;
        const maxPct = ((max - basePrice) / basePrice) * 100;

        return {
            toPixel: (price: number) => {
                const pct = ((price - basePrice) / basePrice) * 100;
                return height - ((pct - minPct) / (maxPct - minPct)) * height;
            },
            toPrice: (pixel: number) => {
                const ratio = (height - pixel) / height;
                const pct = minPct + ratio * (maxPct - minPct);
                return basePrice * (1 + pct / 100);
            },
        };
    }

    // Linear scale (auto/manual)
    return {
        toPixel: (price: number) => {
            return height - ((price - min) / (max - min)) * height;
        },
        toPrice: (pixel: number) => {
            return min + ((height - pixel) / height) * (max - min);
        },
    };
}

function createTimeScale(bars: OHLCVBar[], width: number) {
    if (bars.length === 0) {
        return {
            toPixel: () => 0,
            toIndex: () => 0,
            toTimestamp: () => 0,
            barWidth: 0,
        };
    }

    const barWidth = width / bars.length;

    return {
        toPixel: (index: number) => index * barWidth + barWidth / 2,
        toIndex: (pixel: number) => Math.floor(pixel / barWidth),
        toTimestamp: (pixel: number) => {
            const index = Math.floor(pixel / barWidth);
            if (index >= 0 && index < bars.length) {
                return bars[index].timestamp;
            }
            // Fallback for out of bounds?
            return 0;
        },
        barWidth: barWidth * (1 - CANDLE_PADDING),
        bars,
    };
}

// =============================================================================
// COMPONENT
// =============================================================================

import { getTool } from '../DrawingEngine/registry';
import type { Drawing, DrawingAnchor } from '../types';
import { generateDrawingId } from '../DrawingEngine/baseTool';

// ... (existing imports)

// =============================================================================
// COMPONENT
// =============================================================================

export default function ChartCanvas({ 
    width, 
    height, 
    onBarHover, 
    onBarClick, 
    compareData = {}, 
    syncedCrosshairTimestamp, 
    onCrosshairMove,
    externalBars,
    previousClose,
    symbol,
    onDoubleClick,
    replayActive,
    replayCursorIndex,
    replaySelectMode,
    anchorIndex = 0,
    visibleGhosts = [],
    alphaMode = 'percent',
    detectedPatterns = [],
    strategySignals = new Map(),
    hideTimeAxis = false
}: ChartCanvasProps) {
    const { state, dispatch } = useChart();
    const currentSymbol = symbol || state.symbol;
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const crosshairCanvasRef = useRef<HTMLCanvasElement>(null); // Separate canvas for crosshair
    const mousePosRef = useRef<{ x: number; y: number } | null>(null); // Use ref instead of state to avoid re-renders

    // Interaction State
    const [activeDrawing, setActiveDrawing] = useState<Drawing | null>(null);

    // Calculate dimensions
    const dims: Dimensions = useMemo(() => {
        const tHeight = hideTimeAxis ? 0 : TIME_AXIS_HEIGHT;
        const volumeHeight = state.config.showVolume ? height * VOLUME_HEIGHT_RATIO : 0;
        return {
            chartWidth: width - PRICE_AXIS_WIDTH,
            chartHeight: height - tHeight - volumeHeight,
            volumeHeight,
            priceAxisWidth: PRICE_AXIS_WIDTH,
            timeAxisHeight: tHeight,
            marginLeft: 0,
            marginTop: 0,
        };
    }, [width, height, state.config.showVolume, hideTimeAxis]);

    // Get transformed bars based on chart type, then apply zoom/pan
    const { displayBars, allBars, visibleStartIndex } = useMemo(() => {
        const bars = externalBars || state.data?.bars || [];
        const baseBars = state.replay.active
            ? bars.slice(0, state.replay.cursorIndex + 1)
            : bars;

        // Transform based on chart type
        let transformedBars: OHLCVBar[];
        switch (state.config.chartType) {
            case 'heikinAshi': transformedBars = toHeikinAshi(baseBars); break;
            case 'renko': transformedBars = toRenko(baseBars, state.config.renkoBoxSize || 1); break;
            case 'rangeBars': transformedBars = toRangeBars(baseBars, state.config.rangeBarSize || 1); break;
            default: transformedBars = baseBars;
        }

        // Apply zoom and pan for TradingView-like navigation
        const totalBars = transformedBars.length;
        if (totalBars === 0) return { displayBars: [], allBars: [], visibleStartIndex: 0 };

        // Calculate how many bars should be visible based on zoom level
        // Higher zoom = fewer bars visible (zoomed in), lower zoom = more bars visible (zoomed out)
        const baseBarsVisible = Math.min(totalBars, Math.max(50, Math.floor(dims.chartWidth / 8)));
        const visibleCount = Math.max(20, Math.floor(baseBarsVisible / state.zoomLevel));

        // Calculate start index based on pan offset
        // Pan offset is in bar units - positive means we've panned right (seeing older data)
        const maxPanOffset = Math.max(0, totalBars - visibleCount);
        const clampedOffset = Math.max(0, Math.min(maxPanOffset, Math.floor(state.panOffset)));
        
        // Start from the end minus visible count, adjusted by pan offset
        const startIdx = Math.max(0, totalBars - visibleCount - clampedOffset);
        const endIdx = Math.min(totalBars, startIdx + visibleCount);

        return { 
            displayBars: transformedBars.slice(startIdx, endIdx), 
            allBars: transformedBars,
            visibleStartIndex: startIdx
        };
    }, [externalBars, state.data?.bars, state.replay, state.config.chartType, state.config.renkoBoxSize, state.config.rangeBarSize, state.zoomLevel, state.panOffset, dims.chartWidth]);

    // Calculate price range from visible bars only
    const priceRange = useMemo(() => {
        if (displayBars.length === 0) return null;
        let min = Infinity;
        let max = -Infinity;
        for (const bar of displayBars) {
            if (bar.low < min) min = bar.low;
            if (bar.high > max) max = bar.high;
        }
        const padding = (max - min) * 0.12; // Increased padding to 12% to prevent "cutting from top"
        return { min: min - padding, max: max + padding };
    }, [displayBars]);

    // Create scales
    const scales = useMemo(() => {
        if (!priceRange || displayBars.length === 0) return null;

        const basePrice = previousClose || state.data?.previousClose;

        return {
            price: createPriceScale(priceRange, dims.chartHeight, state.config.scaleMode, basePrice),
            time: createTimeScale(displayBars, dims.chartWidth),
            volume: {
                toPixel: (vol: number) => {
                    const maxVol = Math.max(...displayBars.map(b => b.volume));
                    return dims.volumeHeight - (vol / maxVol) * dims.volumeHeight;
                },
            },
        };
    }, [priceRange, displayBars, dims, state.config.scaleMode, previousClose, state.data?.previousClose]);


    // Coordinate Conversion Helpers
    const getCoords = useCallback((e: React.MouseEvent) => {
        const rect = canvasRef.current?.getBoundingClientRect();
        if (!rect || !scales) return null;
        let x = e.clientX - rect.left;
        let y = e.clientY - rect.top;

        // Convert to data coords
        let index = scales.time.toIndex(x);
        const bar = displayBars[index];
        const time = bar ? bar.timestamp : 0;

        let price = scales.price.toPrice(y);

        return { x, y, price, time, index };
    }, [scales, displayBars]);


    // Render canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !scales || displayBars.length === 0) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Scale for retina
        const dpr = window.devicePixelRatio || 1;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);

        // Clear
        ctx.fillStyle = CHART_THEME.bgPrimary;
        ctx.fillRect(0, 0, width, height);

        // Draw grid
        if (state.config.showGrid) {
            drawGrid(ctx, dims, scales, displayBars);
        }

        // Draw session shading
        if (state.config.sessionShading && state.data?.session) {
            drawSessionShading(ctx, dims, displayBars, state.data.session);
        }

        // Draw price chart
        drawPriceChart(ctx, dims, scales, displayBars, state.config.chartType);
        
        // Draw compare symbol overlays
        if (compareData && Object.keys(compareData).length > 0) {
            const colors = ['#A78BFA', '#FBBF24', '#6EE7B7'];
            
            Object.entries(compareData).forEach(([symbol, bars], idx) => {
                if (visibleGhosts.length > 0 && !visibleGhosts.includes(symbol)) return;

                const color = colors[idx % colors.length];
                const compareMap = new Map(bars.map(b => [b.timestamp, b]));
                
                // DATA ALIGNMENT: Find base prices at the anchor point
                let mainBaseClose = allBars[anchorIndex]?.close || allBars[0]?.close || 1;
                let compareBaseBar = compareMap.get(allBars[anchorIndex]?.timestamp || 0) || compareMap.get(allBars[0]?.timestamp || 0) || bars[0] || { close: 1 };
                let compareBaseClose = compareBaseBar.close;

                let renderValues: number[] = [];
                let renderLabel = symbol;

                if (alphaMode === 'percent') {
                    renderValues = displayBars.map((b) => {
                        const cb = compareMap.get(b.timestamp);
                        if (!cb) return mainBaseClose;
                        const change = (cb.close - compareBaseClose) / compareBaseClose;
                        return mainBaseClose * (1 + change);
                    });
                } else if (alphaMode === 'zscore') {
                    // Local z-score relative to visible viewport
                    const gCloses = displayBars.map(b => compareMap.get(b.timestamp)?.close || b.close);
                    const avg = gCloses.reduce((a, b) => a + b, 0) / gCloses.length;
                    const std = Math.sqrt(gCloses.reduce((a, b) => a + (b - avg)**2, 0) / gCloses.length) || 1;
                    const priceMid = (priceRange!.min + priceRange!.max) / 2;
                    const priceR = (priceRange!.max - priceRange!.min) * 0.4;

                    renderValues = gCloses.map(v => priceMid + (((v - avg) / std) * priceR / 3));
                    renderLabel = `${symbol} (σ)`;
                } else if (alphaMode === 'ratio') {
                    const ratios = displayBars.map((b) => {
                        const cb = compareMap.get(b.timestamp);
                        return cb ? cb.close / b.close : 1;
                    });
                    const rMin = Math.min(...ratios);
                    const rMax = Math.max(...ratios);
                    const rRange = rMax - rMin || 1;

                    renderValues = ratios.map(r => priceRange!.min + ((r - rMin) / rRange) * (priceRange!.max - priceRange!.min));
                    renderLabel = `${symbol}/${currentSymbol}`;
                }

                if (renderValues.length === 0) return;

                ctx.beginPath();
                ctx.strokeStyle = color;
                ctx.lineWidth = 1.5;
                ctx.lineJoin = 'round';
                ctx.lineCap = 'round';
                ctx.shadowBlur = 6;
                ctx.shadowColor = color + '60';

                const pixelPoints: {x: number, y: number}[] = [];
                let lastX = -999;
                renderValues.forEach((val, i) => {
                    const x = scales.time.toPixel(i);
                    const y = scales.price.toPixel(val);
                    if (Math.abs(x - lastX) > 1.5 || i === renderValues.length - 1) {
                        pixelPoints.push({x, y});
                        lastX = x;
                    }
                });

                if (pixelPoints.length > 2) {
                    ctx.moveTo(pixelPoints[0].x, pixelPoints[0].y);
                    for (let i = 1; i < pixelPoints.length - 2; i++) {
                        const xc = (pixelPoints[i].x + pixelPoints[i + 1].x) / 2;
                        const yc = (pixelPoints[i].y + pixelPoints[i + 1].y) / 2;
                        ctx.quadraticCurveTo(pixelPoints[i].x, pixelPoints[i].y, xc, yc);
                    }
                    ctx.quadraticCurveTo(pixelPoints[pixelPoints.length-2].x, pixelPoints[pixelPoints.length-2].y, pixelPoints[pixelPoints.length-1].x, pixelPoints[pixelPoints.length-1].y);
                } else if (pixelPoints.length > 0) {
                    ctx.moveTo(pixelPoints[0].x, pixelPoints[0].y);
                    pixelPoints.forEach(p => ctx.lineTo(p.x, p.y));
                }
                ctx.stroke();

                if (alphaMode === 'percent') {
                    ctx.save();
                    const gradient = ctx.createLinearGradient(0, 0, 0, dims.chartHeight);
                    gradient.addColorStop(0, color + '10');
                    gradient.addColorStop(1, 'transparent');
                    ctx.fillStyle = gradient;
                    ctx.beginPath();
                    pixelPoints.forEach((p, i) => { if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y); });
                    for (let i = displayBars.length - 1; i >= 0; i--) { ctx.lineTo(scales.time.toPixel(i), scales.price.toPixel(displayBars[i].close)); }
                    ctx.closePath();
                    ctx.fill();
                    ctx.restore();
                }

                const lastP = pixelPoints[pixelPoints.length - 1];
                if (lastP) {
                    ctx.fillStyle = color;
                    ctx.font = 'bold 9px "IBM Plex Sans"';
                    ctx.fillText(renderLabel, lastP.x + 8, lastP.y + 3);
                }
            });

            // Draw anchor line if visible in viewport
            const anchorInFull = anchorIndex;
            const viewportStart = visibleStartIndex;
            const viewportEnd = visibleStartIndex + displayBars.length;
            
            if (anchorInFull >= viewportStart && anchorInFull <= viewportEnd) {
                const relativeIdx = anchorInFull - viewportStart;
                const ax = scales.time.toPixel(relativeIdx);
                ctx.save();
                ctx.setLineDash([3, 6]);
                ctx.strokeStyle = CHART_THEME.accent + '90';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(ax, 0);
                ctx.lineTo(ax, dims.chartHeight);
                ctx.stroke();
                ctx.restore();
            }
        }

        // Draw volume
        if (state.config.showVolume) {
            drawVolume(ctx, dims, scales, displayBars);
        }

        const renderCtx = {
            ctx,
            priceToPixel: scales.price.toPixel,
            timestampToPixel: (ts: number) => {
                const index = displayBars.findIndex(b => b.timestamp === ts);
                return scales.time.toPixel(index >= 0 ? index : 0);
            },
            pixelToPrice: scales.price.toPrice,
            pixelToTimestamp: (px: number) => {
                const idx = scales.time.toIndex(px);
                return displayBars[idx]?.timestamp || 0;
            },
            width: dims.chartWidth,
            height: dims.chartHeight,
            bars: displayBars,
        };

        if (state.drawingsVisible) {
            state.drawings
                .filter(d => d.symbol === currentSymbol)
                .forEach(drawing => {
                    const tool = getTool(drawing.type);
                    if (tool) tool.render(drawing, renderCtx, false, false);
                });

            if (activeDrawing) {
                const tool = getTool(activeDrawing.type);
                if (tool) tool.render(activeDrawing, renderCtx, true, true);
            }
        }

        state.indicators.filter(ind => ind.placement === 'overlay' && ind.visible).forEach(indConfig => {
            const indDef = getIndicator(indConfig.type);
            if (!indDef) return;

            const output = indDef.compute(displayBars, indConfig.params);
            const color = indConfig.color || CHART_THEME.accent;

            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.lineWidth = indConfig.lineWidth || 1;
            let started = false;

            output.series.forEach((point, i) => {
                if (isNaN(point.value)) return;
                const x = scales.time.toPixel(i);
                const y = scales.price.toPixel(point.value);
                if (!started) { ctx.moveTo(x, y); started = true; }
                else { ctx.lineTo(x, y); }
            });
            ctx.stroke();

            if (output.bands) {
                ctx.strokeStyle = color;
                ctx.lineWidth = 0.5;
                ctx.setLineDash([4, 2]);
                [output.bands.upper, output.bands.lower].forEach(band => {
                    ctx.beginPath();
                    started = false;
                    band.forEach((val, i) => {
                        if (isNaN(val)) return;
                        const x = scales.time.toPixel(i);
                        const y = scales.price.toPixel(val);
                        if (!started) { ctx.moveTo(x, y); started = true; }
                        else { ctx.lineTo(x, y); }
                    });
                    ctx.stroke();
                });
                ctx.setLineDash([]);
            }
        });

        drawPriceAxis(ctx, dims, scales, priceRange!);
        if (!hideTimeAxis) {
            drawTimeAxis(ctx, dims, scales, displayBars, anchorIndex - visibleStartIndex);
        }

        // Draw Pattern Labels
        if (detectedPatterns && detectedPatterns.length > 0) {
            ctx.save();
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'center';
            
            detectedPatterns.forEach(p => {
                const relativeIdx = p.endIndex - visibleStartIndex;
                if (relativeIdx >= 0 && relativeIdx < displayBars.length) {
                    const bar = displayBars[relativeIdx];
                    const x = scales.time.toPixel(relativeIdx);
                    const isBullish = p.type === 'bullish';
                    const y = isBullish 
                        ? scales.price.toPixel(bar.low) + 20 
                        : scales.price.toPixel(bar.high) - 20;
                    
                    ctx.fillStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
                    ctx.fillText(p.name, x, y);
                    
                    // Small dot/marker
                    ctx.beginPath();
                    ctx.arc(x, isBullish ? y - 8 : y + 8, 2, 0, Math.PI * 2);
                    ctx.fill();
                }
            });
            ctx.restore();
        }

        // Draw Strategy Signals
        if (strategySignals && strategySignals.size > 0) {
            ctx.save();
            strategySignals.forEach((result: any, strategyId: string) => {
                if (!result || !result.signals) return;
                result.signals.forEach((sig: any) => {
                    const relativeIdx = sig.index - visibleStartIndex;
                    if (relativeIdx >= 0 && relativeIdx < displayBars.length) {
                        const x = scales.time.toPixel(relativeIdx);
                        const isBuy = sig.type === 'buy';
                        const y = isBuy 
                            ? scales.price.toPixel(sig.price) + 35 
                            : scales.price.toPixel(sig.price) - 35;
                        
                        // Draw Signal Box
                        const color = isBuy ? CHART_THEME.upColor : CHART_THEME.downColor;
                        ctx.fillStyle = color;
                        ctx.beginPath();
                        if (isBuy) {
                            // Up Arrow
                            ctx.moveTo(x, y - 5);
                            ctx.lineTo(x - 5, y + 5);
                            ctx.lineTo(x + 5, y + 5);
                        } else {
                            // Down Arrow
                            ctx.moveTo(x, y + 5);
                            ctx.lineTo(x - 5, y - 5);
                            ctx.lineTo(x + 5, y - 5);
                        }
                        ctx.fill();
                        
                        // Label
                        ctx.font = 'bold 8px monospace';
                        ctx.textAlign = 'center';
                        ctx.fillText(isBuy ? 'BUY' : 'SELL', x, isBuy ? y + 15 : y - 10);
                    }
                });
            });
            ctx.restore();
        }

    }, [width, height, displayBars, allBars, scales, dims, state.config, priceRange, state.drawings, activeDrawing, state.indicators, state.data?.session, compareData, currentSymbol, externalBars, state.data?.bars, state.drawingsVisible, anchorIndex, visibleGhosts, alphaMode, detectedPatterns, strategySignals, visibleStartIndex, hideTimeAxis]);

    // Separate effect for crosshair rendering (high frequency updates)
    useEffect(() => {
        const crosshairCanvas = crosshairCanvasRef.current;
        if (!crosshairCanvas || !scales || displayBars.length === 0) return;

        const ctx = crosshairCanvas.getContext('2d');
        if (!ctx) return;

        // Scale for retina
        const dpr = window.devicePixelRatio || 1;
        crosshairCanvas.width = width * dpr;
        crosshairCanvas.height = height * dpr;
        ctx.scale(dpr, dpr);

        // Clear
        ctx.clearRect(0, 0, width, height);

        // Draw crosshair if mouse is on chart
        if (mousePosRef.current) {
            drawCrosshair(ctx, dims, mousePosRef.current, scales, hideTimeAxis);
        }
        
        // =============================================================================
        // FIX: SYNCED CROSSHAIR FROM SIBLING CHARTS
        // Per CHART_WORKSPACE_TECHNICAL_AUDIT_REPORT.md Step 2
        // =============================================================================
        if (syncedCrosshairTimestamp && !mousePosRef.current) {
            // Find the bar index matching the synced timestamp
            const syncIndex = displayBars.findIndex(b => b.timestamp === syncedCrosshairTimestamp);
            if (syncIndex >= 0) {
                const x = scales.time.toPixel(syncIndex);
                // Draw ghost crosshair line (vertical only, dimmer)
                ctx.strokeStyle = 'rgba(255, 214, 10, 0.3)'; // CHART_THEME.accent with opacity
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, dims.chartHeight);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }
    }, [width, height, dims, scales, displayBars.length, syncedCrosshairTimestamp, displayBars, hideTimeAxis]);

    // -------------------------------------------------------------------------
    // HANDLERS
    // -------------------------------------------------------------------------

    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        const coords = getCoords(e);
        if (!coords) return;

        // Update mouse position ref (doesn't trigger re-render)
        mousePosRef.current = { x: coords.x, y: coords.y };
        
        // Manually update crosshair canvas
        const crosshairCanvas = crosshairCanvasRef.current;
        if (crosshairCanvas && scales && displayBars.length > 0) {
            const ctx = crosshairCanvas.getContext('2d');
            if (ctx) {
                const dpr = window.devicePixelRatio || 1;
                ctx.clearRect(0, 0, crosshairCanvas.width / dpr, crosshairCanvas.height / dpr);
                drawCrosshair(ctx, dims, mousePosRef.current, scales, hideTimeAxis);
            }
        }

        // Update active drawing last anchor
        if (activeDrawing && state.activeToolType) {
            const updatedDrawing = { ...activeDrawing };
            const lastIdx = updatedDrawing.anchors.length - 1;
            updatedDrawing.anchors[lastIdx] = { price: coords.price, timestamp: coords.time };
            setActiveDrawing(updatedDrawing);
        }

        if (scales && coords.x < dims.chartWidth && coords.y < dims.chartHeight) {
            onBarHover?.(coords.index, displayBars[coords.index] || null);
            // Broadcast crosshair timestamp for sync
            const bar = displayBars[coords.index];
            if (bar && onCrosshairMove) {
                onCrosshairMove(bar.timestamp);
            }
        } else {
            onBarHover?.(null, null);
            onCrosshairMove?.(null);
        }
    }, [scales, dims, displayBars, onBarHover, onCrosshairMove, getCoords, activeDrawing, state.activeToolType, hideTimeAxis]);

    const handleMouseLeave = useCallback(() => {
        mousePosRef.current = null;
        // Clear crosshair canvas
        const crosshairCanvas = crosshairCanvasRef.current;
        if (crosshairCanvas) {
            const ctx = crosshairCanvas.getContext('2d');
            if (ctx) {
                const dpr = window.devicePixelRatio || 1;
                ctx.clearRect(0, 0, crosshairCanvas.width / dpr, crosshairCanvas.height / dpr);
            }
        }
        onBarHover?.(null, null);
    }, [onBarHover]);

    const handleClick = useCallback((e: React.MouseEvent) => {
        const coords = getCoords(e);
        if (!coords) return;

        // If tool is active, handle creation
        if (state.activeToolType) {
            const tool = getTool(state.activeToolType);
            if (!tool) return;

            if (!activeDrawing) {
                // START NEW
                const newDrawing = {
                    ...tool.createDrawing([{ price: coords.price, timestamp: coords.time }]),
                    symbol: currentSymbol
                };
                // If minAnchors > 1, we need to add a temporary anchor for dragging
                if (tool.minAnchors > 1) {
                    newDrawing.anchors.push({ price: coords.price, timestamp: coords.time }); // Temp anchor
                    setActiveDrawing(newDrawing);
                } else {
                    // Single click tool (e.g. Marker)
                    dispatch({ type: 'ADD_DRAWING', payload: newDrawing });
                    dispatch({ type: 'SET_ACTIVE_TOOL', payload: null }); 
                }
            } else {
                // ADD ANCHOR / FINISH
                // We are dragging the 'last' anchor.
                // If we reached max anchors, finish.
                const currentAnchors = activeDrawing.anchors.length;

                // Note: activeDrawing already has the "temp" anchor at current mouse pos (via mouseMove)
                // So effectively we just "confirm" it.

                if (currentAnchors >= tool.maxAnchors) {
                    // Finish
                    dispatch({ type: 'ADD_DRAWING', payload: activeDrawing });
                    setActiveDrawing(null);
                    // Do we stay in tool mode? Standard behavior is usually yes for some, no for others.
                    // Let's stay in tool mode for continuous drawing.
                } else {
                    // Add another temp anchor for next segment
                    const nextDrawing = { ...activeDrawing };
                    nextDrawing.anchors.push({ price: coords.price, timestamp: coords.time });
                    setActiveDrawing(nextDrawing);
                }
            }
            return;
        }

        // Standard Bar Click
        if (coords.index >= 0 && displayBars[coords.index]) {
            // Return ABSOLUTE index into the full data array
            onBarClick?.(visibleStartIndex + coords.index, displayBars[coords.index]);
        }
    }, [displayBars, onBarClick, getCoords, state.activeToolType, activeDrawing, dispatch, currentSymbol, visibleStartIndex]);

    // -------------------------------------------------------------------------
    // PAN/ZOOM HANDLERS (TradingView-like navigation)
    // -------------------------------------------------------------------------
    const [isDragging, setIsDragging] = useState(false);
    const lastDragX = useRef(0);

    const handleWheel = useCallback((e: React.WheelEvent) => {
        e.preventDefault();
        
        // Zoom factor based on wheel delta
        const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1; // Zoom out if scrolling down, zoom in if up
        dispatch({ type: 'ZOOM', payload: zoomDelta });
    }, [dispatch]);

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        // Only start drag if not in drawing mode and using left button
        if (!state.activeToolType && e.button === 0) {
            setIsDragging(true);
            lastDragX.current = e.clientX;
        }
    }, [state.activeToolType]);

    const handleMouseUp = useCallback(() => {
        setIsDragging(false);
    }, []);

    const handleDragMove = useCallback((e: React.MouseEvent) => {
        if (isDragging && scales && scales.time.barWidth > 0) {
            const deltaX = e.clientX - lastDragX.current;
            lastDragX.current = e.clientX;
            
            // Convert pixel delta to bar units (positive delta = dragging right = seeing older data = increase pan offset)
            // Scale by barWidth to get accurate bar movement
            const barDelta = deltaX / scales.time.barWidth;
            dispatch({ type: 'PAN', payload: barDelta });
        }
    }, [isDragging, dispatch, scales]);

    // Combined mouse move handler
    const handleCombinedMouseMove = useCallback((e: React.MouseEvent) => {
        handleMouseMove(e);
        handleDragMove(e);
    }, [handleMouseMove, handleDragMove]);

    // Keyboard navigation for pan/zoom and cancel drawing on Escape
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Skip if typing in an input
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

            switch (e.key) {
                case 'Escape':
                    setActiveDrawing(null);
                    dispatch({ type: 'SET_ACTIVE_TOOL', payload: null });
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    dispatch({ type: 'PAN', payload: 5 }); // Pan to see older data
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    dispatch({ type: 'PAN', payload: -5 }); // Pan to see newer data
                    break;
                case '+':
                case '=':
                    e.preventDefault();
                    dispatch({ type: 'ZOOM', payload: 1.2 }); // Zoom in
                    break;
                case '-':
                case '_':
                    e.preventDefault();
                    dispatch({ type: 'ZOOM', payload: 0.8 }); // Zoom out
                    break;
                case 'Home':
                    e.preventDefault();
                    // Reset to show latest data
                    dispatch({ type: 'PAN', payload: -state.panOffset });
                    break;
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [dispatch, state.panOffset]);

    // Add global mouse up to handle release outside canvas
    useEffect(() => {
        const handleGlobalMouseUp = () => setIsDragging(false);
        window.addEventListener('mouseup', handleGlobalMouseUp);
        return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
    }, []);

    return (
        <div 
            style={{ 
                position: 'relative', 
                width, 
                height,
                // CRITICAL: CSS containment prevents layout bouncing
                contain: 'strict',
                // GPU acceleration for smooth rendering
                transform: 'translateZ(0)',
                willChange: 'contents',
                // Isolation for stacking context
                isolation: 'isolate',
                // Prevent any overflow issues
                overflow: 'hidden',
            }}
        >
            {/* Main chart canvas */}
            <canvas
                ref={canvasRef}
                style={{ 
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width, 
                    height, 
                    cursor: state.activeToolType ? 'crosshair' : (isDragging ? 'grabbing' : 'default') 
                }}
            />
            {/* Crosshair overlay canvas (for high-frequency mouse updates) */}
            <canvas
                ref={crosshairCanvasRef}
                style={{ 
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width, 
                    height,
                    pointerEvents: 'none', // Allow clicks to pass through
                }}
            />
            {/* Invisible interaction layer */}
            <div
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width,
                    height,
                    cursor: state.activeToolType ? 'crosshair' : (isDragging ? 'grabbing' : 'default'),
                }}
                onMouseMove={handleCombinedMouseMove}
                onMouseLeave={handleMouseLeave}
                onClick={handleClick}
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseUp={handleMouseUp}
                onDoubleClick={onDoubleClick}
            />
        </div>
    );
}

// ... (Rest of drawing functions: drawGrid, etc. KEEP THEM)


// =============================================================================
// DRAWING FUNCTIONS
// =============================================================================

function drawGrid(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: { toPixel: (price: number) => number }; time: { toPixel: (index: number) => number; barWidth: number } },
    bars: OHLCVBar[]
) {
    ctx.strokeStyle = CHART_THEME.gridColorLight;
    ctx.lineWidth = 0.5;

    // Horizontal lines
    const numHLines = 8;
    for (let i = 0; i <= numHLines; i++) {
        const y = (dims.chartHeight / numHLines) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(dims.chartWidth, y);
        ctx.stroke();
    }

    // Vertical lines (every N bars)
    const step = Math.max(1, Math.floor(bars.length / 10));
    for (let i = 0; i < bars.length; i += step) {
        const x = scales.time.toPixel(i);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, dims.chartHeight);
        ctx.stroke();
    }
}

function drawSessionShading(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    bars: OHLCVBar[],
    session: { regularStart: string; regularEnd: string }
) {
    // Simplified session shading - alternate background for pre/post market
    ctx.fillStyle = 'rgba(30, 39, 56, 0.3)';

    // This would need proper time parsing for real implementation
    // For now, just show subtle alternating regions
}

function drawPriceChart(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[],
    chartType: string
) {
    switch (chartType) {
        case 'candlestick':
        case 'heikinAshi':
            drawCandlesticks(ctx, dims, scales, bars, false);
            break;
        case 'hollowCandle':
            drawCandlesticks(ctx, dims, scales, bars, true);
            break;
        case 'volumeCandles':
            drawVolumeCandles(ctx, dims, scales, bars);
            break;
        case 'bars':
            drawBars(ctx, dims, scales, bars);
            break;
        case 'line':
            drawLine(ctx, dims, scales, bars, false, false);
            break;
        case 'lineWithMarkers':
            drawLine(ctx, dims, scales, bars, false, true);
            break;
        case 'stepLine':
            drawLine(ctx, dims, scales, bars, true, false);
            break;
        case 'area':
            drawArea(ctx, dims, scales, bars);
            break;
        case 'hlcArea':
            drawHLCArea(ctx, dims, scales, bars);
            break;
        case 'baseline':
            drawBaseline(ctx, dims, scales, bars, bars[0]?.close || 0);
            break;
        case 'renko':
            drawRenko(ctx, dims, scales, bars);
            break;
        case 'kagi':
            drawKagi(ctx, dims, scales, bars);
            break;
        case 'pointAndFigure':
            drawPointAndFigure(ctx, dims, scales, bars);
            break;
        case 'rangeBars':
            drawCandlesticks(ctx, dims, scales, bars, false); // Range bars use candlestick rendering
            break;
        case 'lineBreak':
            drawLineBreak(ctx, dims, scales, bars);
            break;
        default:
            drawCandlesticks(ctx, dims, scales, bars, false);
    }
}

function drawCandlesticks(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[],
    hollow: boolean
) {
    const { barWidth } = scales.time;
    const halfWidth = barWidth / 2;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close >= bar.open;

        const color = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;

        // Wick
        ctx.strokeStyle = CHART_THEME.wickColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, scales.price.toPixel(bar.high));
        ctx.lineTo(x, scales.price.toPixel(bar.low));
        ctx.stroke();

        // Body
        const bodyTop = scales.price.toPixel(Math.max(bar.open, bar.close));
        const bodyBottom = scales.price.toPixel(Math.min(bar.open, bar.close));
        const bodyHeight = Math.max(1, bodyBottom - bodyTop);

        if (hollow && isUp) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.strokeRect(x - halfWidth, bodyTop, barWidth, bodyHeight);
        } else {
            ctx.fillStyle = color;
            ctx.fillRect(x - halfWidth, bodyTop, barWidth, bodyHeight);
        }
    }
}

function drawBars(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    const { barWidth } = scales.time;
    const tickWidth = barWidth / 2;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close >= bar.open;

        ctx.strokeStyle = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;
        ctx.lineWidth = 1;

        // High-Low line
        ctx.beginPath();
        ctx.moveTo(x, scales.price.toPixel(bar.high));
        ctx.lineTo(x, scales.price.toPixel(bar.low));
        ctx.stroke();

        // Open tick (left)
        ctx.beginPath();
        ctx.moveTo(x - tickWidth, scales.price.toPixel(bar.open));
        ctx.lineTo(x, scales.price.toPixel(bar.open));
        ctx.stroke();

        // Close tick (right)
        ctx.beginPath();
        ctx.moveTo(x, scales.price.toPixel(bar.close));
        ctx.lineTo(x + tickWidth, scales.price.toPixel(bar.close));
        ctx.stroke();
    }
}

function drawLine(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[],
    step: boolean,
    withMarkers: boolean = false
) {
    if (bars.length === 0) return;

    ctx.strokeStyle = CHART_THEME.accentBlue;
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    const points: { x: number; y: number }[] = [];

    for (let i = 0; i < bars.length; i++) {
        const x = scales.time.toPixel(i);
        const y = scales.price.toPixel(bars[i].close);
        points.push({ x, y });

        if (i === 0) {
            ctx.moveTo(x, y);
        } else if (step) {
            ctx.lineTo(x, scales.price.toPixel(bars[i - 1].close));
            ctx.lineTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }

    ctx.stroke();

    // Draw markers if requested
    if (withMarkers && points.length > 0) {
        ctx.fillStyle = CHART_THEME.accentBlue;
        const markerSize = 3;
        // Draw marker every N points to avoid clutter
        const step = Math.max(1, Math.floor(points.length / 50));
        for (let i = 0; i < points.length; i += step) {
            ctx.beginPath();
            ctx.arc(points[i].x, points[i].y, markerSize, 0, Math.PI * 2);
            ctx.fill();
        }
        // Always draw last point
        if (points.length > 1) {
            ctx.beginPath();
            ctx.arc(points[points.length - 1].x, points[points.length - 1].y, markerSize, 0, Math.PI * 2);
            ctx.fill();
        }
    }
}

function drawArea(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    if (bars.length === 0) return;

    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, dims.chartHeight);
    gradient.addColorStop(0, 'rgba(0, 212, 255, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 212, 255, 0.02)');

    // Area
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.moveTo(0, dims.chartHeight);

    for (let i = 0; i < bars.length; i++) {
        const x = scales.time.toPixel(i);
        const y = scales.price.toPixel(bars[i].close);
        ctx.lineTo(x, y);
    }

    ctx.lineTo(scales.time.toPixel(bars.length - 1), dims.chartHeight);
    ctx.closePath();
    ctx.fill();

    // Line on top
    drawLine(ctx, dims, scales, bars, false, false);
}

function drawBaseline(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[],
    baseline: number
) {
    if (bars.length === 0) return;

    const baseY = scales.price.toPixel(baseline);

    // Baseline
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = CHART_THEME.textSecondary;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, baseY);
    ctx.lineTo(dims.chartWidth, baseY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw line with color based on position relative to baseline
    for (let i = 1; i < bars.length; i++) {
        const x1 = scales.time.toPixel(i - 1);
        const x2 = scales.time.toPixel(i);
        const y1 = scales.price.toPixel(bars[i - 1].close);
        const y2 = scales.price.toPixel(bars[i].close);

        ctx.strokeStyle = bars[i].close >= baseline ? CHART_THEME.upColor : CHART_THEME.downColor;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
    }
}

// Volume Candles - candle width proportional to volume
function drawVolumeCandles(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    if (bars.length === 0) return;

    // Calculate max volume for scaling
    const maxVolume = Math.max(...bars.map(b => b.volume));
    const baseBarWidth = scales.time.barWidth;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close >= bar.open;

        // Width proportional to volume (min 30% width, max 100%)
        const volumeRatio = bar.volume / maxVolume;
        const barWidth = baseBarWidth * (0.3 + volumeRatio * 0.7);
        const halfWidth = barWidth / 2;

        const color = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;

        // Wick
        ctx.strokeStyle = CHART_THEME.wickColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, scales.price.toPixel(bar.high));
        ctx.lineTo(x, scales.price.toPixel(bar.low));
        ctx.stroke();

        // Body
        const bodyTop = scales.price.toPixel(Math.max(bar.open, bar.close));
        const bodyBottom = scales.price.toPixel(Math.min(bar.open, bar.close));
        const bodyHeight = Math.max(1, bodyBottom - bodyTop);

        ctx.fillStyle = color;
        ctx.fillRect(x - halfWidth, bodyTop, barWidth, bodyHeight);
    }
}

// HLC Area - High-Low-Close area chart
function drawHLCArea(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    if (bars.length === 0) return;

    // Create gradient for high-low range
    const gradient = ctx.createLinearGradient(0, 0, 0, dims.chartHeight);
    gradient.addColorStop(0, 'rgba(0, 255, 136, 0.15)');
    gradient.addColorStop(0.5, 'rgba(0, 212, 255, 0.1)');
    gradient.addColorStop(1, 'rgba(255, 45, 85, 0.15)');

    // Draw high-low area
    ctx.fillStyle = gradient;
    ctx.beginPath();
    
    // Draw high line
    ctx.moveTo(scales.time.toPixel(0), scales.price.toPixel(bars[0].high));
    for (let i = 1; i < bars.length; i++) {
        ctx.lineTo(scales.time.toPixel(i), scales.price.toPixel(bars[i].high));
    }
    
    // Draw low line (backwards)
    for (let i = bars.length - 1; i >= 0; i--) {
        ctx.lineTo(scales.time.toPixel(i), scales.price.toPixel(bars[i].low));
    }
    
    ctx.closePath();
    ctx.fill();

    // Draw close line on top
    ctx.strokeStyle = CHART_THEME.accentBlue;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(scales.time.toPixel(0), scales.price.toPixel(bars[0].close));
    for (let i = 1; i < bars.length; i++) {
        ctx.lineTo(scales.time.toPixel(i), scales.price.toPixel(bars[i].close));
    }
    ctx.stroke();
}

// Renko - brick chart
function drawRenko(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    const { barWidth } = scales.time;
    const halfWidth = barWidth / 2;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close > bar.open;

        const color = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;

        // Body (no wicks in Renko)
        const bodyTop = scales.price.toPixel(Math.max(bar.open, bar.close));
        const bodyBottom = scales.price.toPixel(Math.min(bar.open, bar.close));
        const bodyHeight = Math.max(1, bodyBottom - bodyTop);

        ctx.fillStyle = color;
        ctx.fillRect(x - halfWidth, bodyTop, barWidth, bodyHeight);

        // Add subtle border
        ctx.strokeStyle = isUp ? 'rgba(0, 255, 136, 0.6)' : 'rgba(255, 45, 85, 0.6)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x - halfWidth, bodyTop, barWidth, bodyHeight);
    }
}

// Kagi - trend reversal chart
function drawKagi(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    if (bars.length < 2) return;

    ctx.lineWidth = 2;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close > bar.open;

        ctx.strokeStyle = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;
        ctx.lineWidth = isUp ? 3 : 2; // Thick for up (yang), thin for down (yin)

        // Vertical line
        ctx.beginPath();
        ctx.moveTo(x, scales.price.toPixel(bar.open));
        ctx.lineTo(x, scales.price.toPixel(bar.close));
        ctx.stroke();

        // Horizontal connector to next bar
        if (i < bars.length - 1) {
            const nextX = scales.time.toPixel(i + 1);
            const nextBar = bars[i + 1];
            
            ctx.beginPath();
            ctx.moveTo(x, scales.price.toPixel(bar.close));
            ctx.lineTo(nextX, scales.price.toPixel(bar.close));
            ctx.stroke();
        }
    }
}

// Point & Figure - X and O chart
function drawPointAndFigure(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    const { barWidth } = scales.time;
    const boxSize = barWidth * 0.8;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close > bar.open; // X column (up) vs O column (down)

        const topY = scales.price.toPixel(bar.high);
        const bottomY = scales.price.toPixel(bar.low);
        const numBoxes = Math.max(1, Math.round((bottomY - topY) / boxSize));

        ctx.lineWidth = 2;
        ctx.strokeStyle = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;

        for (let j = 0; j < numBoxes; j++) {
            const boxY = topY + j * boxSize;
            
            if (isUp) {
                // Draw X
                ctx.beginPath();
                ctx.moveTo(x - boxSize / 2, boxY);
                ctx.lineTo(x + boxSize / 2, boxY + boxSize);
                ctx.moveTo(x + boxSize / 2, boxY);
                ctx.lineTo(x - boxSize / 2, boxY + boxSize);
                ctx.stroke();
            } else {
                // Draw O
                ctx.beginPath();
                ctx.arc(x, boxY + boxSize / 2, boxSize / 2 - 1, 0, Math.PI * 2);
                ctx.stroke();
            }
        }
    }
}

// Line Break - three line break chart
function drawLineBreak(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale>; time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[]
) {
    const { barWidth } = scales.time;
    const halfWidth = barWidth / 2;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close > bar.open;

        const color = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;
        const bodyTop = scales.price.toPixel(Math.max(bar.open, bar.close));
        const bodyBottom = scales.price.toPixel(Math.min(bar.open, bar.close));
        const bodyHeight = Math.max(1, bodyBottom - bodyTop);

        // Filled block (no wicks)
        ctx.fillStyle = color;
        ctx.fillRect(x - halfWidth, bodyTop, barWidth, bodyHeight);
    }
}

function drawVolume(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { time: ReturnType<typeof createTimeScale>; volume: { toPixel: (vol: number) => number } },
    bars: OHLCVBar[]
) {
    const { barWidth } = scales.time;
    const halfWidth = barWidth / 2;
    const volumeTop = dims.chartHeight;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const x = scales.time.toPixel(i);
        const isUp = bar.close >= bar.open;
        const volHeight = dims.volumeHeight - scales.volume.toPixel(bar.volume);

        ctx.fillStyle = isUp
            ? 'rgba(0, 255, 136, 0.6)'
            : 'rgba(255, 45, 85, 0.6)';

        ctx.fillRect(
            x - halfWidth,
            volumeTop + dims.volumeHeight - volHeight,
            barWidth,
            volHeight
        );
    }
}

function drawCrosshair(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    mousePos: { x: number; y: number },
    scales: any,
    hideTimeAxis: boolean = false
) {
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = CHART_THEME.textSecondary;
    ctx.lineWidth = 0.5;

    // Vertical line
    ctx.beginPath();
    ctx.moveTo(mousePos.x, 0);
    ctx.lineTo(mousePos.x, dims.chartHeight + dims.volumeHeight);
    ctx.stroke();

    // Horizontal line
    if (mousePos.y < dims.chartHeight) {
        ctx.beginPath();
        ctx.moveTo(0, mousePos.y);
        ctx.lineTo(dims.chartWidth, mousePos.y);
        ctx.stroke();
    }

    // Floating axis labels
    const barIdx = scales.time.toIndex(mousePos.x);
    if (barIdx >= 0 && barIdx < scales.time.bars.length) {
        const bar = scales.time.bars[barIdx];
        const date = new Date(bar.timestamp);
        
        // Time Label
        const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
        const dateStr = date.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short', year: '2-digit' });
        const fullLabel = `${dateStr}  ${timeStr}`;
        
        ctx.font = `bold 10px ${CHART_THEME.fontMono}`;
        const labelWidth = ctx.measureText(fullLabel).width + 16;
        const labelX = Math.max(labelWidth/2, Math.min(dims.chartWidth - labelWidth/2, mousePos.x));
        
        if (!hideTimeAxis) {
            ctx.fillStyle = '#0a0a0a';
            ctx.fillRect(labelX - labelWidth/2, dims.chartHeight + dims.volumeHeight, labelWidth, dims.timeAxisHeight);
            ctx.fillStyle = CHART_THEME.accent;
            ctx.textAlign = 'center';
            ctx.fillText(fullLabel, labelX, dims.chartHeight + dims.volumeHeight + 15);
        }
    }
}

function drawPriceAxis(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { price: ReturnType<typeof createPriceScale> },
    priceRange: { min: number; max: number }
) {
    const axisX = dims.chartWidth;

    // Background
    ctx.fillStyle = CHART_THEME.bgSecondary;
    ctx.fillRect(axisX, 0, dims.priceAxisWidth, dims.chartHeight);

    // Border
    ctx.strokeStyle = CHART_THEME.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(axisX, 0);
    ctx.lineTo(axisX, dims.chartHeight);
    ctx.stroke();

    // Labels
    ctx.fillStyle = CHART_THEME.textPrimary;
    ctx.font = `11px ${CHART_THEME.fontMono}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';

    const numLabels = 10; // Increase number of labels
    const step = (priceRange.max - priceRange.min) / numLabels;

    for (let i = 0; i <= numLabels; i++) {
        const price = priceRange.min + step * i;
        const y = scales.price.toPixel(price);
        
        // Relaxed clipping - only skip if truly off the edge
        if (y < 2 || y > dims.chartHeight - 2) continue;
        
        ctx.fillText(price.toFixed(2), axisX + 8, y);
    }
}

function drawTimeAxis(
    ctx: CanvasRenderingContext2D,
    dims: Dimensions,
    scales: { time: ReturnType<typeof createTimeScale> },
    bars: OHLCVBar[],
    anchorIndex?: number | null
) {
    const axisY = dims.chartHeight + dims.volumeHeight;

    // Background
    ctx.fillStyle = CHART_THEME.bgSecondary;
    ctx.fillRect(0, axisY, dims.chartWidth, dims.timeAxisHeight);

    // Border
    ctx.strokeStyle = CHART_THEME.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, axisY);
    ctx.lineTo(dims.chartWidth, axisY);
    ctx.stroke();

    // Labels
    ctx.fillStyle = CHART_THEME.textSecondary;
    ctx.font = `9px ${CHART_THEME.fontMono}`;
    ctx.textAlign = 'center';

    if (bars.length === 0) return;

    // Detect if this is daily data by checking if timestamps are more than 1 hour apart
    const isDaily = bars.length >= 2 && (bars[1].timestamp - bars[0].timestamp) > 60 * 60 * 1000;
    
    // For daily data spanning years, check if we need year labels
    const firstDate = new Date(bars[0].timestamp);
    const lastDate = new Date(bars[bars.length - 1].timestamp);
    const spanYears = lastDate.getFullYear() !== firstDate.getFullYear();
    const spanMonths = (lastDate.getMonth() !== firstDate.getMonth()) || spanYears;

    const step = Math.max(1, Math.floor(bars.length / 8));

    for (let i = 0; i < bars.length; i += step) {
        const x = scales.time.toPixel(i);
        const date = new Date(bars[i].timestamp);
        const prevDate = i > 0 ? new Date(bars[i - step].timestamp) : null;
        
        // Show date if it's a first label or date changed
        const dateChanged = !prevDate || date.toDateString() !== prevDate.toDateString();
        
        let label: string;
        if (isDaily) {
            if (spanYears) {
                label = date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
            } else {
                label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            }
        } else {
            // Intraday: show Date on transition or first bar, otherwise Time
            if (dateChanged) {
                ctx.save();
                ctx.fillStyle = CHART_THEME.textPrimary;
                ctx.font = `bold 9px ${CHART_THEME.fontMono}`;
                label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                ctx.fillText(label, x, axisY + 15);
                ctx.restore();
                continue;
            } else {
                label = date.toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
            }
        }
        ctx.fillText(label, x, axisY + 15);
    }

    // Persistent Selected Label (anchorIndex)
    if (anchorIndex !== null && anchorIndex !== undefined && anchorIndex >= 0 && anchorIndex < bars.length) {
        const x = scales.time.toPixel(anchorIndex);
        const bar = bars[anchorIndex];
        const date = new Date(bar.timestamp);
        const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
        ctx.font = `bold 9px ${CHART_THEME.fontMono}`;
        const tw = ctx.measureText(label).width + 10;
        ctx.fillStyle = '#363c4e'; // Dark selection color
        ctx.fillRect(x - tw/2, axisY, tw, dims.timeAxisHeight);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, x, axisY + 15);
    }

    // Last Bar Label (Current Time)
    if (bars.length > 0) {
        const lastBar = bars[bars.length - 1];
        const x = scales.time.toPixel(bars.length - 1);
        // Only show if the bar is visible on the far right
        if (x > dims.chartWidth - 50) {
            const date = new Date(lastBar.timestamp);
            const label = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
            ctx.font = `bold 9px ${CHART_THEME.fontMono}`;
            const tw = ctx.measureText(label).width + 10;
            ctx.fillStyle = CHART_THEME.bgSecondary;
            ctx.fillRect(dims.chartWidth - tw, axisY, tw, dims.timeAxisHeight);
            ctx.fillStyle = CHART_THEME.textPrimary;
            ctx.fillText(label, dims.chartWidth - tw/2, axisY + 15);
        }
    }
}
