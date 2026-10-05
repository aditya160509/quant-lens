import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { getIndicator } from '../chart_engine/IndicatorEngine/registry';
import { scanForPatterns, CANDLESTICK_PATTERNS } from '../chart_engine/PatternScanner';
import { clampViewport, zoomAt, panBy } from './visual-kernel/viewport';
import { setupHiDPI, createResizeObserver, exportCanvasToPNG } from './visual-kernel/canvas';
import { hitTestCandle, drawCrosshair, magnetSnap } from './visual-kernel/interaction';
import { toHeikinAshi, toRenko, resampleCandles, createPriceScale } from './visual-kernel/scales';

const S = {
    void: '#020204',
    grid: 'rgba(255,255,255,0.03)',
    gridStrong: 'rgba(255,255,255,0.06)',
    signalLong: '#ffd60a',
    signalShort: '#f43f5e',
    muted: '#64748b',
    bull: '#22c55e',
    bear: '#ef4444',
    volumeUp: 'rgba(34,197,94,0.6)',
    volumeDown: 'rgba(239,68,68,0.6)',
    ghost: 'rgba(255,255,255,0.15)',
    volumeProfile: 'rgba(255,214,10,0.2)',
    volumeProfilePOC: 'rgba(255,214,10,0.5)'
};

const Q360Canvas = ({ 
    candles, 
    signals, 
    previousSignals = [],
    playIndex, 
    isPlaying = false,
    activeIndicators = [],
    showVolume = true,
    volumeProfile = [],
    benchmarkData = [],
    showBenchmark = false,
    selectedPatterns = [],
    activeTool = null,
    drawings = [],
    onDrawingsChange,
    customOverlayMatches = [],
    syncedOffset = null,
    syncedScale = null,
    syncedHover = null,
    onOffsetChange = null,
    onScaleChange = null,
    onHoverChange = null,
    syncYAxis = false,
    onHUDUpdate = null
}) => {
    const containerRef = useRef(null);
    const mainCanvasRef = useRef(null);
    const volumeCanvasRef = useRef(null);
    const oscCanvasRef = useRef(null);
    
    const [offset, setOffset] = useState(0);
    const [scale, setScale] = useState(6);
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, offset: 0 });
    const [hoverInfo, setHoverInfo] = useState(null);
    const [activeDrawing, setActiveDrawing] = useState(null);
    const [chartType, setChartType] = useState('candles'); // TradingView max: candles | heikinAshi | renko | line | area | baseline | histogram | columns
    const [timeframe, setTimeframe] = useState('1D'); // 1D | 1W | 1M
    const [priceMode, setPriceMode] = useState('linear'); // linear | log | percent | indexed100
    const [magnetEnabled, setMagnetEnabled] = useState(true);

    // Refs for coordinate conversion (to avoid scoping issues in event handlers)
    const chartStateRef = useRef({
        minP: 0,
        maxP: 0,
        bw: 0,
        offset: 0,
        scale: 1,
        width: 0,
        height: 0,
        paddingLeft: 50,
        paddingRight: 100
    });

    const overlays = useMemo(() => activeIndicators.filter(i => i.placement === 'overlay' && i.visible), [activeIndicators]);
    const oscillators = useMemo(() => activeIndicators.filter(i => i.placement === 'pane' && i.visible), [activeIndicators]);
    const displayCandles = useMemo(() => {
        let c = resampleCandles(candles, timeframe);
        if (chartType === 'heikinAshi') c = toHeikinAshi(c);
        else if (chartType === 'renko') c = toRenko(c);
        return c;
    }, [candles, chartType, timeframe]);
    const priceModeBase = displayCandles[0]?.close ?? 100;
    
    const oscHeight = oscillators.length > 0 ? Math.min(150, 80 * oscillators.length) : 0;
    const volumeHeight = showVolume ? 60 : 0;

    // Use synced props if available, otherwise internal state
    const effectiveOffset = syncedOffset !== null ? syncedOffset : offset;
    const effectiveScale = syncedScale !== null ? syncedScale : scale;
    const effectiveHover = syncedHover !== null ? syncedHover : hoverInfo;

    const activeHudData = useMemo(() => {
        const dataPoint = effectiveHover?.index !== undefined ? candles[effectiveHover.index] : candles[playIndex];
        if (!dataPoint) return null;
        const hud = {
            time: dataPoint.time,
            o: dataPoint.open,
            h: dataPoint.high,
            l: dataPoint.low,
            c: dataPoint.close,
            v: dataPoint.volume,
            change: ((dataPoint.close / dataPoint.open - 1) * 100).toFixed(2),
            isBull: dataPoint.close >= dataPoint.open
        };
        return hud;
    }, [effectiveHover, playIndex, candles]);

    useEffect(() => {
        if (onHUDUpdate) {
            onHUDUpdate(activeHudData);
        }
    }, [activeHudData, onHUDUpdate]);

    const handleWheel = useCallback((e) => {
        e.preventDefault();
        const sensitivity = 0.0015;
        const newScale = Math.max(0.1, Math.min(effectiveScale * (1 - e.deltaY * sensitivity), 50));
        
        if (onScaleChange) {
            onScaleChange(newScale);
        } else {
            setScale(newScale);
        }
    }, [effectiveScale, onScaleChange]);

    const handleMouseDown = useCallback((e) => {
        setIsDragging(true);
        setDragStart({ x: e.clientX, offset: effectiveOffset });
    }, [effectiveOffset]);

    const handleMouseMove = useCallback((e) => {
        const canvas = mainCanvasRef.current;
        if (!canvas) return;
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        if (isDragging) {
            const dx = e.clientX - dragStart.x;
            const newOffset = dragStart.offset + dx / effectiveScale;
            
            if (onOffsetChange) onOffsetChange(newOffset);
            else setOffset(newOffset);
        }

        // Always update hover info unless dragging (to keep crosshair sync alive)
        if (!isDragging) {
            const { paddingLeft, bw } = chartStateRef.current;
            const vis = candles.slice(0, playIndex + 1);
            if (vis.length > 0) {
                const idx = Math.round((mouseX - paddingLeft - effectiveOffset - (bw/2)) / bw);
                const safeIdx = Math.max(0, Math.min(idx, vis.length - 1));
                const bar = vis[safeIdx];
                if (bar) {
                    const dateObj = new Date(bar.time * 1000);
                    const hoverData = { 
                        x: mouseX, 
                        y: mouseY, 
                        index: safeIdx,
                        o: bar.open,
                        h: bar.high,
                        l: bar.low,
                        c: bar.close,
                        v: bar.volume,
                        isBull: bar.close >= bar.open,
                        date: `${dateObj.getMonth() + 1}/${dateObj.getDate()} ${dateObj.getHours()}:${dateObj.getMinutes().toString().padStart(2, '0')}`
                    };
                    
                    if (onHoverChange) onHoverChange(hoverData);
                    else setHoverInfo(hoverData);
                }
            }
        }
    }, [isDragging, dragStart, effectiveScale, effectiveOffset, candles, playIndex, onOffsetChange, onHoverChange]);

    // Auto-follow during playback
    useEffect(() => {
        if (isPlaying && playIndex > 0) {
            const { paddingLeft, bw, width } = chartStateRef.current;
            const x = paddingLeft + (playIndex * bw) + effectiveOffset;
            if (x > width - 150) {
                const diff = x - (width - 150);
                if (onOffsetChange) onOffsetChange(effectiveOffset - diff);
                else setOffset(o => o - diff);
            }
        }
    }, [playIndex, isPlaying, effectiveOffset, onOffsetChange]);

    const handleMouseUp = useCallback(() => {
        setIsDragging(false);
    }, []);

    const handleMouseLeave = useCallback(() => {
        setIsDragging(false);
        if (onHoverChange) onHoverChange(null);
        else setHoverInfo(null);
    }, [onHoverChange]);

    // Separate Effect for Resize Observer
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;
        
        const resize = () => {
            const rect = container.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            const mainHeight = rect.height - volumeHeight - oscHeight;
            
            if (mainCanvasRef.current) {
                mainCanvasRef.current.width = rect.width * dpr;
                mainCanvasRef.current.height = mainHeight * dpr;
                mainCanvasRef.current.style.width = `${rect.width}px`;
                mainCanvasRef.current.style.height = `${mainHeight}px`;
            }
            if (volumeCanvasRef.current && showVolume) {
                volumeCanvasRef.current.width = rect.width * dpr;
                volumeCanvasRef.current.height = volumeHeight * dpr;
                volumeCanvasRef.current.style.width = `${rect.width}px`;
                volumeCanvasRef.current.style.height = `${volumeHeight}px`;
            }
            if (oscCanvasRef.current && oscillators.length > 0) {
                oscCanvasRef.current.width = rect.width * dpr;
                oscCanvasRef.current.height = oscHeight * dpr;
                oscCanvasRef.current.style.width = `${rect.width}px`;
                oscCanvasRef.current.style.height = `${oscHeight}px`;
            }
        };

        const observer = new ResizeObserver(resize);
        observer.observe(container);
        resize(); // Initial resize
        
        return () => observer.disconnect();
    }, [volumeHeight, oscHeight, showVolume, oscillators.length]);

    // Native wheel event listener with passive: false to allow preventDefault
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;
        
        container.addEventListener('wheel', handleWheel, { passive: false });
        return () => container.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);

    // Main Draw Engine Effect
    useEffect(() => {
        const mainCanvas = mainCanvasRef.current;
        const volumeCanvas = volumeCanvasRef.current;
        const oscCanvas = oscCanvasRef.current;
        if (!mainCanvas) return;

        const rect = mainCanvas.getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;

        const draw = () => {
            const mainCtx = mainCanvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            mainCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
            
            // Clear
            mainCtx.fillStyle = S.void;
            mainCtx.fillRect(0, 0, width, height);

            // Draw Grid
            drawGrid(mainCtx, width, height);

            const vis = displayCandles.slice(0, playIndex + 1);
            if (vis.length === 0) return;

            const paddingRight = 100;
            const paddingLeft = 50;
            
            // Auto-follow: Keep latest candle in view if playIndex is advancing
            // (Only if not currently dragging or hovered over the right threshold)
            if (!isDragging && playIndex > 10 && !hoverInfo) {
                const bw_calc = Math.max(3, ((width - paddingRight - paddingLeft) / Math.max(vis.length, 50)) * effectiveScale);
                const lastX = paddingLeft + (playIndex * bw_calc) + effectiveOffset;
                if (lastX > width - 150) {
                    const adjustment = lastX - (width - 150);
                    if (onOffsetChange) {
                        onOffsetChange(effectiveOffset - adjustment);
                    } else {
                        setOffset(prev => prev - adjustment);
                    }
                }
            }

            const bw = Math.max(3, ((width - paddingRight - paddingLeft) / Math.max(vis.length, 50)) * effectiveScale);
            
            // Y-Axis Governance: Scale based on visible range only
            const visibleIndices = [];
            const visibleCandles = vis.filter((_, i) => {
                const x = paddingLeft + (i * bw) + effectiveOffset;
                const isVis = x + bw > 0 && x < width - paddingRight;
                if (isVis) visibleIndices.push(i);
                return isVis;
            });
            
            const rangeTarget = visibleCandles.length > 0 ? visibleCandles : vis.slice(-20);
            let prices = rangeTarget.flatMap(c => [c.high, c.low]);
            
            // Include benchmark in scaling if enabled
            if (showBenchmark && benchmarkData.length > 0) {
                const benchStart = benchmarkData[0].close;
                const stratStart = vis[0].close;
                const targetIndices = visibleIndices.length > 0 ? visibleIndices : [vis.length - 1];
                targetIndices.forEach(idx => {
                    if (benchmarkData[idx]) {
                        const benchVal = stratStart * (benchmarkData[idx].close / benchStart);
                        prices.push(benchVal);
                    }
                });
            }

            const rawMinP = Math.min(...prices.filter(p => !isNaN(p) && p !== null));
            const rawMaxP = Math.max(...prices.filter(p => !isNaN(p) && p !== null));
            
            const minP = isFinite(rawMinP) ? rawMinP * 0.998 : 100;
            const maxP = isFinite(rawMaxP) ? rawMaxP * 1.002 : 101;
            
            // Update ref for coordinate conversion
            chartStateRef.current = {
                minP, maxP, bw, offset: effectiveOffset, scale: effectiveScale, width, height,
                paddingLeft: 50, paddingRight: 100
            };
            
            // Visual-kernel price scale with TradingView modes (linear/log/percent/indexed)
            const scaleY = createPriceScale({ min: minP, max: maxP, height, paddingTop: 30, paddingBottom: 30, mode: priceMode, base: priceModeBase });

            // Relative Strength Background Glow
            if (showBenchmark && benchmarkData.length > 0) {
                drawRelativeStrength(mainCtx, vis, benchmarkData, paddingLeft, bw, effectiveOffset, width, height);
            }

            // Draw Grid
            drawGrid(mainCtx, width, height);
            // Draw Volume Profile (Value-at-Price)
            if (volumeProfile.length > 0) {
                drawVolumeProfile(mainCtx, volumeProfile, height, minP, maxP, scaleY);
            }

            // Draw Benchmark Ghost (if enabled)
            if (showBenchmark && benchmarkData.length > 0) {
                drawBenchmarkGhost(mainCtx, benchmarkData, vis, paddingLeft, bw, height, minP, maxP);
            }

            // Draw Overlays
            overlays.filter(o => o.visible).forEach(overlay => {
                drawOverlay(mainCtx, overlay, vis, paddingLeft, bw, scaleY);
            });

            // Draw Chart — TradingView max: candles | line | area | baseline | histogram | columns (+ heikinAshi/renko via displayCandles)
            if (chartType === 'line' || chartType === 'area' || chartType === 'baseline') {
                const isBaseline = chartType === 'baseline';
                const baseY = isBaseline ? scaleY(priceModeBase) : null;
                if (chartType === 'area' || isBaseline) {
                    const grad = mainCtx.createLinearGradient(0, 30, 0, height - 30);
                    grad.addColorStop(0, isBaseline ? 'rgba(59,130,246,0.3)' : 'rgba(255,214,10,0.2)');
                    grad.addColorStop(1, 'rgba(255,214,10,0)');
                    mainCtx.fillStyle = grad;
                    mainCtx.beginPath();
                    vis.forEach((c, i) => {
                        const x = paddingLeft + (i * bw) + bw/2 + effectiveOffset;
                        const y = scaleY(c.close);
                        if (i===0) { mainCtx.moveTo(x, height-30); mainCtx.lineTo(x, y); } else mainCtx.lineTo(x, y);
                    });
                    const lastX = paddingLeft + ((vis.length-1)*bw)+bw/2+effectiveOffset;
                    mainCtx.lineTo(lastX, height-30); mainCtx.closePath(); mainCtx.fill();
                }
                mainCtx.strokeStyle = chartType==='baseline' ? '#3b82f6' : '#ffd60a'; mainCtx.lineWidth = 1.8;
                mainCtx.beginPath();
                vis.forEach((c,i)=>{ const x=paddingLeft+(i*bw)+bw/2+effectiveOffset, y=scaleY(c.close); if(i===0) mainCtx.moveTo(x,y); else mainCtx.lineTo(x,y); });
                mainCtx.stroke();
                if (isBaseline) { mainCtx.strokeStyle='rgba(255,255,255,0.2)'; mainCtx.setLineDash([4,4]); mainCtx.beginPath(); mainCtx.moveTo(paddingLeft, baseY); mainCtx.lineTo(width-paddingRight, baseY); mainCtx.stroke(); mainCtx.setLineDash([]); }
            } else if (chartType === 'histogram' || chartType === 'columns') {
                vis.forEach((c,i)=>{ const x=paddingLeft+(i*bw)+effectiveOffset, h=Math.abs(scaleY(c.close)-scaleY(c.open)), y=Math.min(scaleY(c.close), scaleY(c.open)); mainCtx.fillStyle=c.close>=c.open?S.bull:S.bear; mainCtx.fillRect(x+1, y, Math.max(bw-2,1), Math.max(h,1)); });
            } else {
                // Candles (including heikinAshi/renko via displayCandles)
                vis.forEach((c, i) => {
                    const x = paddingLeft + (i * bw) + effectiveOffset;
                    if (x + bw < 0 || x > width - paddingRight) return;
                    const yC = scaleY(c.close); const yO = scaleY(c.open); const yH = scaleY(c.high); const yL = scaleY(c.low);
                    const bull = c.close >= c.open; mainCtx.strokeStyle = mainCtx.fillStyle = bull ? S.bull : S.bear;
                    mainCtx.lineWidth = 1; mainCtx.beginPath(); mainCtx.moveTo(x + bw / 2, yH); mainCtx.lineTo(x + bw / 2, yL); mainCtx.stroke();
                    const bodyWidth = Math.max(bw * 0.75, 2); const bodyX = x + (bw - bodyWidth) / 2; mainCtx.fillRect(bodyX, Math.min(yO, yC), bodyWidth, Math.max(Math.abs(yC - yO), 1));
                });
            }

            const drawSignals = (ctx, sigs, isGhost = false) => {
                if (!sigs) return;
                sigs.filter(s => s.idx <= playIndex && s.direction !== 0).forEach(sig => {
                    const c = vis[sig.idx];
                    if (!c) return;
                    const x = paddingLeft + (sig.idx * bw) + effectiveOffset + bw / 2;
                    if (x < 0 || x > width - paddingRight) return;
                    
                    const y = scaleY(sig.direction === 1 ? c.low : c.high);
                    
                    if (isGhost) {
                        ctx.fillStyle = sig.direction === 1 ? 'rgba(255, 214, 10, 0.25)' : 'rgba(244, 63, 94, 0.25)';
                        ctx.strokeStyle = sig.direction === 1 ? 'rgba(255, 214, 10, 0.5)' : 'rgba(244, 63, 94, 0.5)';
                        ctx.lineWidth = 1;
                        ctx.setLineDash([2, 2]);
                    } else {
                        ctx.fillStyle = sig.direction === 1 ? S.signalLong : S.signalShort;
                        ctx.setLineDash([]);
                    }

                    ctx.beginPath();
                    if (sig.direction === 1) {
                        ctx.moveTo(x, y + 8);
                        ctx.lineTo(x - 5, y + 16);
                        ctx.lineTo(x + 5, y + 16);
                    } else {
                        ctx.moveTo(x, y - 8);
                        ctx.lineTo(x - 5, y - 16);
                        ctx.lineTo(x + 5, y - 16);
                    }
                    ctx.closePath();
                    ctx.fill();
                    if (isGhost) ctx.stroke();
                    
                    if (!isGhost) {
                        ctx.fillStyle = '#000';
                        ctx.font = 'bold 7px JetBrains Mono';
                        ctx.textAlign = 'center';
                        ctx.fillText(sig.direction === 1 ? 'B' : 'S', x, sig.direction === 1 ? y + 14 : y - 10);
                    }
                });
                ctx.setLineDash([]);
            };

            // Draw Signals
            drawSignals(mainCtx, previousSignals, true); // Ghost signals
            drawSignals(mainCtx, signals, false); // Current signals

            // Price Axis
            drawPriceAxis(mainCtx, width, height, minP, maxP, scaleY);

            // Time Axis
            drawTimeAxis(mainCtx, vis, paddingLeft, bw, width, height);

            // Patterns (Auto-detect & User Selection)
            if (selectedPatterns.length > 0) {
                drawPatterns(mainCtx, vis, paddingLeft, bw, scaleY);
            }

            // Crosshair (Cursor Sync)
            if (effectiveHover) {
                drawCrosshair(mainCtx, effectiveHover, width, height, paddingLeft, bw, effectiveOffset, scaleY, minP, maxP);
            }

            // Current Price Label
            if (vis.length > 0) {
                const last = vis[vis.length - 1];
                const y = scaleY(last.close);
                mainCtx.fillStyle = last.close >= last.open ? S.bull : S.bear;
                mainCtx.fillRect(width - paddingRight + 5, y - 9, 85, 18);
                mainCtx.fillStyle = '#fff';
                mainCtx.font = 'bold 10px JetBrains Mono';
                mainCtx.textAlign = 'center';
                mainCtx.fillText(last.close.toPrecision(6), width - paddingRight + 47, y + 4);
                
                // Horizontal line to price
                mainCtx.strokeStyle = last.close >= last.open ? S.bull : S.bear;
                mainCtx.setLineDash([2, 2]);
                mainCtx.beginPath();
                mainCtx.moveTo(0, y);
                mainCtx.lineTo(width - paddingRight, y);
                mainCtx.stroke();
                mainCtx.setLineDash([]);
            }


            // Draw Volume Bars
            if (showVolume && volumeCanvas) {
                drawVolumeBars(volumeCanvas, vis, paddingLeft, bw, width);
            }

            // Draw Oscillators
            if (oscCanvas && oscillators.length > 0) {
                drawOscillators(oscCanvas, oscillators, vis, paddingLeft, bw, width);
            }
        };

        const drawRelativeStrength = (ctx, vis, benchmark, paddingLeft, bw, offset, width, height) => {
            if (benchmark.length === 0 || vis.length === 0) return;
            
            const benchStart = benchmark[0].close;
            const stratStart = vis[0].close;
            
            vis.forEach((c, i) => {
                const b = benchmark[i];
                if (!b) return;
                
                const stratRet = c.close / stratStart;
                const benchRet = b.close / benchStart;
                
                if (stratRet > benchRet) {
                    const x = paddingLeft + i * bw + offset;
                    if (x < 0 || x > width) return;
                    
                    ctx.fillStyle = 'rgba(16, 185, 129, 0.03)'; // Faint emerald glow
                    ctx.fillRect(x, 0, bw, height);
                }
            });
        };

        const drawCrosshair = (ctx, hover, width, height, paddingLeft, bw, offset, scaleY, minP, maxP) => {
            const paddingRight = 100;
            const x = hover.x;
            const y = hover.y;

            // Lines
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
            ctx.lineWidth = 0.5;

            // Horiz
            if (y > 0 && y < height - 30) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(width - paddingRight, y);
                ctx.stroke();

                // Price Label on Axis
                const price = maxP - ((y - 30) / (height - 60)) * (maxP - minP);
                ctx.setLineDash([]);
                ctx.fillStyle = '#f59e0b';
                ctx.fillRect(width - paddingRight, y - 9, paddingRight, 18);
                ctx.fillStyle = '#000';
                ctx.font = 'bold 9px JetBrains Mono';
                ctx.textAlign = 'center';
                ctx.fillText(price.toFixed(2), width - paddingRight/2, y + 4);
            }

            // Vert
            if (x > paddingLeft && x < width - paddingRight) {
                const { effectiveOffset } = chartStateRef.current;
                const idx = Math.round((x - paddingLeft - effectiveOffset - bw/2) / bw);
                const snapX = paddingLeft + idx * bw + effectiveOffset + bw/2;

                ctx.setLineDash([3, 3]);
                ctx.beginPath();
                ctx.moveTo(snapX, 0);
                ctx.lineTo(snapX, height - 30);
                ctx.stroke();

                // Time label could be added here if needed
            }
            ctx.setLineDash([]);
        };

        const drawGrid = (ctx, width, height) => {
            ctx.strokeStyle = S.grid;
            ctx.lineWidth = 0.5;
            const gridSpacingX = 80 * effectiveScale;
            for (let x = (effectiveOffset % gridSpacingX); x < width; x += gridSpacingX) {
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, height);
                ctx.stroke();
            }
            ctx.strokeStyle = S.gridStrong;
            for (let y = 40; y < height; y += 50) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(width - 60, y);
                ctx.stroke();
            }
        };

        const drawVolumeProfile = (ctx, profile, height, minP, maxP, scaleY) => {
            const maxWidth = 50;
            const pocIdx = profile.reduce((maxI, p, i, arr) => p.normalized > arr[maxI].normalized ? i : maxI, 0);
            
            profile.forEach((p, i) => {
                const y = scaleY(p.priceLevel);
                const barHeight = (maxP - minP) / profile.length / (maxP - minP) * (height - 60);
                const barWidth = p.normalized * maxWidth;
                
                ctx.fillStyle = i === pocIdx ? S.volumeProfilePOC : S.volumeProfile;
                ctx.fillRect(0, y - barHeight / 2, barWidth, barHeight);
            });
        };

        const drawBenchmarkGhost = (ctx, benchmark, vis, paddingLeft, bw, height, minP, maxP) => {
            if (benchmark.length === 0 || vis.length === 0) return;
            
            const strategyStart = vis[0].close;
            const benchStart = benchmark[0].close;
            
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)'; // Brighter blue for benchmark
            ctx.lineWidth = 1.2;
            ctx.setLineDash([4, 4]);
            
            const minLen = Math.min(vis.length, benchmark.length);
            let lastY = 0;
            let lastPrice = 0;

            for (let i = 0; i < minLen; i++) {
                const benchReturn = (benchmark[i].close / benchStart - 1);
                const normalizedPrice = strategyStart * (1 + benchReturn);
                const x = paddingLeft + i * bw + effectiveOffset + bw / 2;
                const y = height - 30 - ((normalizedPrice - minP) / (maxP - minP)) * (height - 60);
                
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);

                if (i === minLen - 1) {
                    lastY = y;
                    lastPrice = normalizedPrice;
                }
            }
            ctx.stroke();
            ctx.setLineDash([]);

            // Label and Price Tag
            ctx.fillStyle = 'rgba(59, 130, 246, 0.8)';
            ctx.font = 'bold 8px "JetBrains Mono"';
            ctx.textAlign = 'right';
            ctx.fillText("BENCHMARK (SPY)", paddingLeft + (minLen * bw) + effectiveOffset - 5, lastY - 5);

            // Right Axis Tag
            const canvasWidth = mainCanvasRef.current.width / (window.devicePixelRatio || 1);
            ctx.fillStyle = 'rgba(59, 130, 246, 0.9)';
            ctx.fillRect(canvasWidth - 60, lastY - 8, 60, 16);
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 8px JetBrains Mono';
            ctx.textAlign = 'center';
            ctx.fillText(lastPrice.toFixed(2), canvasWidth - 30, lastY + 3);
        };

        const drawOverlay = (ctx, indicator, vis, paddingLeft, bw, scaleY) => {
            const def = getIndicator(indicator.indicatorId);
            if (!def) return;

            // Map candles to BARS for engine
            const bars = vis.map(c => ({
                timestamp: c.time * 1000,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close,
                volume: c.volume
            }));

            try {
                const output = def.compute(bars, indicator.params || {});
                if (!output || !output.series) return;

                ctx.beginPath();
                ctx.strokeStyle = indicator.color || '#ffd60a';
                ctx.lineWidth = indicator.lineWidth || 1.2;
                
                let started = false;
                output.series.forEach((pt, i) => {
                    if (i >= vis.length || isNaN(pt.value) || pt.value === null) return;
                    const x = paddingLeft + i * bw + effectiveOffset + bw/2;
                    const y = scaleY(pt.value);
                    if (!started) { ctx.moveTo(x, y); started = true; }
                    else ctx.lineTo(x, y);
                });
                ctx.stroke();

                // Draw bands if present (e.g. Bollinger)
                if (output.bands) {
                    ['upper', 'lower'].forEach(key => {
                        const band = output.bands[key];
                        if (!band) return;
                        ctx.beginPath();
                        ctx.globalAlpha = 0.4;
                        let s = false;
                        band.forEach((val, i) => {
                            if (i >= vis.length || isNaN(val)) return;
                            const x = paddingLeft + i * bw + effectiveOffset + bw / 2;
                            const y = scaleY(val);
                            if (!s) { ctx.moveTo(x, y); s = true; }
                            else ctx.lineTo(x, y);
                        });
                        ctx.stroke();
                        ctx.globalAlpha = 1;
                    });
                }
            } catch (err) {
                console.error(`Indicator compute error (${indicator.indicatorId}):`, err);
            }
        };

        const drawPriceAxis = (ctx, width, height, minP, maxP, scaleY) => {
            const paddingRight = 100;
            ctx.fillStyle = 'rgba(255,255,255,0.02)';
            ctx.fillRect(width - paddingRight, 0, paddingRight, height);
            
            ctx.fillStyle = S.muted;
            ctx.font = '10px JetBrains Mono';
            ctx.textAlign = 'left';
            
            // Major grid labels
            const steps = 8;
            for (let i = 0; i <= steps; i++) {
                const pr = minP + (maxP - minP) * (i / steps);
                const y = scaleY(pr);
                
                // Tick
                ctx.strokeStyle = S.gridStrong;
                ctx.beginPath();
                ctx.moveTo(width - paddingRight, y);
                ctx.lineTo(width - paddingRight + 5, y);
                ctx.stroke();
                
                ctx.fillText(pr.toFixed(2), width - paddingRight + 10, y + 4);
            }
        };

        const drawPatterns = (ctx, vis, paddingLeft, bw, scaleY) => {
            if (!vis || vis.length === 0 || !selectedPatterns || selectedPatterns.length === 0) return;
            
            const bars = vis.map(c => ({
                timestamp: c.time,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close,
                volume: c.volume
            }));
            
            // Filter patterns based on user selection
            const activePatterns = CANDLESTICK_PATTERNS.filter(p => 
                selectedPatterns.includes(p.id) || selectedPatterns.includes(p.id.toLowerCase())
            );
            
            if (activePatterns.length === 0) return;

            const matches = scanForPatterns(bars, activePatterns);
            matches.forEach(m => {
                const x = paddingLeft + m.endIndex * bw + effectiveOffset + bw/2;
                const bar = vis[m.endIndex];
                if (!bar) return;
                
                const y = scaleY(m.type === 'bullish' ? bar.low : bar.high);
                const color = m.type === 'bullish' ? '#00ff88' : '#ff2d55';
                
                ctx.fillStyle = color;
                ctx.font = 'bold 9px JetBrains Mono';
                ctx.textAlign = 'center';
                ctx.fillText(m.pattern.substring(0, 4).toUpperCase(), x, m.type === 'bullish' ? y + 25 : y - 20);
                
                ctx.beginPath();
                ctx.arc(x, m.type === 'bullish' ? y + 12 : y - 10, 2.5, 0, Math.PI * 2);
                ctx.fill();
            });
        };

        // Draw custom overlay signals from CustomOverlayBuilder
        const drawCustomOverlays = (ctx, overlays, vis, paddingLeft, bw, scaleY) => {
            if (!overlays || overlays.length === 0) return;
            
            overlays.forEach(match => {
                // Only draw overlays within visible range up to playIndex
                if (match.index > playIndex) return;
                
                const x = paddingLeft + (match.index * bw) + effectiveOffset + bw/2;
                const y = scaleY(match.price);
                const color = match.action?.color || '#ffd60a';
                
                switch (match.action?.type) {
                    case 'arrow_up':
                        ctx.fillStyle = color;
                        ctx.beginPath();
                        ctx.moveTo(x, y + 15);
                        ctx.lineTo(x - 6, y + 25);
                        ctx.lineTo(x + 6, y + 25);
                        ctx.closePath();
                        ctx.fill();
                        break;
                        
                    case 'arrow_down':
                        ctx.fillStyle = color;
                        ctx.beginPath();
                        ctx.moveTo(x, y - 15);
                        ctx.lineTo(x - 6, y - 25);
                        ctx.lineTo(x + 6, y - 25);
                        ctx.closePath();
                        ctx.fill();
                        break;
                        
                    case 'paint_bar':
                        // Highlight the entire candle bar
                        const candle = candles[match.index];
                        if (candle) {
                            const barX = paddingLeft + (match.index * bw) + effectiveOffset;
                            const high = scaleY(candle.high);
                            const low = scaleY(candle.low);
                            ctx.fillStyle = color + '40'; // Transparent
                            ctx.fillRect(barX + 2, high, bw - 4, low - high);
                        }
                        break;
                        
                    case 'background':
                        // Highlight background stripe
                        const bgX = paddingLeft + (match.index * bw) + effectiveOffset;
                        ctx.fillStyle = color + '15';
                        ctx.fillRect(bgX, 0, bw, ctx.canvas.height);
                        break;
                        
                    default:
                        // Default: small diamond marker
                        ctx.fillStyle = color;
                        ctx.beginPath();
                        ctx.moveTo(x, y - 5);
                        ctx.lineTo(x + 4, y);
                        ctx.lineTo(x, y + 5);
                        ctx.lineTo(x - 4, y);
                        ctx.closePath();
                        ctx.fill();
                }
            });
        };



        const drawTimeAxis = (ctx, vis, paddingLeft, bw, width, height) => {
            ctx.fillStyle = S.muted;
            ctx.font = '9px JetBrains Mono';
            ctx.textAlign = 'center';
            const step = Math.max(1, Math.floor(vis.length / 8));
            for (let i = 0; i < vis.length; i += step) {
                const c = vis[i];
                if (!c) continue;
                const x = paddingLeft + i * bw + effectiveOffset + bw / 2;
                if (x < 0 || x > width - 60) continue;
                const date = new Date(c.time * 1000);
                ctx.fillText(`${date.getMonth() + 1}/${date.getDate()}`, x, height - 8);
            }
        };

        const drawVolumeBars = (canvas, vis, paddingLeft, bw, width) => {
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            
            ctx.fillStyle = S.void;
            ctx.fillRect(0, 0, width, volumeHeight);
            
            const volumes = vis.map(c => c.volume);
            const maxVol = Math.max(...volumes);
            
            vis.forEach((c, i) => {
                const x = paddingLeft + i * bw + effectiveOffset;
                if (x + bw < 0 || x > width) return;
                
                const barHeight = (c.volume / maxVol) * (volumeHeight - 10);
                const bull = c.close >= c.open;
                
                ctx.fillStyle = bull ? S.volumeUp : S.volumeDown;
                const bodyWidth = Math.max(bw * 0.7, 2);
                ctx.fillRect(x + (bw - bodyWidth) / 2, volumeHeight - barHeight - 5, bodyWidth, barHeight);
            });
        };

        const drawOscillators = (canvas, oscillators, vis, paddingLeft, bw, width) => {
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            
            ctx.fillStyle = '#0a0a0f';
            ctx.fillRect(0, 0, width, oscHeight);
            
            const n = oscillators.length;
            if (n === 0) return;
            
            const paneHeight = oscHeight / n;
            const bars = vis.map(c => ({
                timestamp: c.time * 1000,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close,
                volume: c.volume
            }));

            oscillators.forEach((osc, idx) => {
                const def = getIndicator(osc.indicatorId);
                if (!def) return;

                const top = idx * paneHeight;
                const bottom = top + paneHeight;
                const h = paneHeight - 20;

                // Grid/Base
                ctx.strokeStyle = 'rgba(255,255,255,0.05)';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(0, bottom); ctx.lineTo(width, bottom);
                ctx.stroke();

                try {
                    const output = def.compute(bars, osc.params || {});
                    if (!output || !output.series) return;

                    const vals = output.series.map(s => s.value);
                    const validVals = vals.filter(v => !isNaN(v) && v !== null);
                    if (validVals.length === 0) return;

                    const min = Math.min(...validVals);
                    const max = Math.max(...validVals);
                    const range = max - min || 1;

                    const scaleOsc = (v) => bottom - 10 - ((v - min) / range) * h;

                    // Specialized rendering (MACD histogram & signal, Stochastic %D)
                    if (osc.indicatorId === 'macd') {
                        // 1. Histogram
                        output.series.forEach((pt, i) => {
                            if (pt.extra?.histogram === undefined || isNaN(pt.extra.histogram)) return;
                            const x = paddingLeft + i * bw + effectiveOffset + bw/2;
                            if (x < 0 || x > width) return;
                            const val = pt.extra.histogram;
                            const y = scaleOsc(val);
                            const y0 = scaleOsc(0);
                            ctx.fillStyle = val >= 0 ? S.bull : S.bear;
                            const barW = Math.max(1, bw * 0.7);
                            ctx.fillRect(x - barW/2, Math.min(y, y0), barW, Math.max(1, Math.abs(y - y0)));
                        });

                        // 2. Signal Line
                        ctx.beginPath();
                        ctx.strokeStyle = '#f43f5e'; // Reddish for signal
                        ctx.lineWidth = 1;
                        let firstSignal = true;
                        output.series.forEach((pt, i) => {
                            if (pt.extra?.signal === undefined || isNaN(pt.extra.signal)) return;
                            const x = paddingLeft + i * bw + effectiveOffset + bw/2;
                            if (x < 0 || x > width) {
                                firstSignal = true;
                                return;
                            }
                            const y = scaleOsc(pt.extra.signal);
                            if (firstSignal) {
                                ctx.moveTo(x, y);
                                firstSignal = false;
                            } else {
                                ctx.lineTo(x, y);
                            }
                        });
                        ctx.stroke();
                    } else if (osc.indicatorId === 'stochastic' || osc.indicatorId === 'stochRsi') {
                        // Draw %D line
                        ctx.beginPath();
                        ctx.strokeStyle = '#f59e0b'; // Amber for %D
                        ctx.lineWidth = 1;
                        let firstD = true;
                        output.series.forEach((pt, i) => {
                            if (pt.extra?.d === undefined || isNaN(pt.extra.d)) return;
                            const x = paddingLeft + i * bw + effectiveOffset + bw/2;
                            if (x < 0 || x > width) {
                                firstD = true;
                                return;
                            }
                            const y = scaleOsc(pt.extra.d);
                            if (firstD) {
                                ctx.moveTo(x, y);
                                firstD = false;
                            } else {
                                ctx.lineTo(x, y);
                            }
                        });
                        ctx.stroke();
                    }

                    // Main series line
                    ctx.beginPath();
                    ctx.strokeStyle = osc.color || '#fff';
                    ctx.lineWidth = 1.2;
                    let started = false;
                    output.series.forEach((pt, i) => {
                        if (isNaN(pt.value) || pt.value === null) return;
                        const x = paddingLeft + i * bw + effectiveOffset + bw/2;
                        if (x < 0 || x > width) return;
                        const y = scaleOsc(pt.value);
                        if (!started) { ctx.moveTo(x, y); started = true; }
                        else ctx.lineTo(x, y);
                    });
                    ctx.stroke();

                    // Reference lines (RSI 30/70)
                    if (osc.indicatorId === 'rsi') {
                         ctx.strokeStyle = 'rgba(255,255,255,0.1)';
                         ctx.setLineDash([4,4]);
                         [30, 70].forEach(level => {
                             const y = scaleOsc(level);
                             ctx.beginPath(); ctx.moveTo(paddingLeft, y); ctx.lineTo(width - 60, y); ctx.stroke();
                         });
                         ctx.setLineDash([]);
                    }

                    // Label
                    ctx.fillStyle = osc.color || '#fff';
                    ctx.font = 'bold 9px JetBrains Mono';
                    ctx.textAlign = 'left';
                    const lastVal = validVals[validVals.length-1];
                    ctx.fillText(`${osc.shortName}: ${lastVal?.toFixed(2)}`, 8, top + 14);

                } catch (err) {
                    console.error(`Oscillator error (${osc.indicatorId}):`, err);
                }
            });
        };

        const frame = requestAnimationFrame(draw);
        return () => cancelAnimationFrame(frame);
    }, [candles, signals, playIndex, offset, scale, effectiveOffset, effectiveScale, overlays, oscillators, showVolume, volumeProfile, benchmarkData, showBenchmark, oscHeight, volumeHeight, selectedPatterns, drawings, activeDrawing, hoverInfo, effectiveHover, isDragging, customOverlayMatches, onOffsetChange, onHoverChange, previousSignals]);

    // Clamp viewport via kernel (deterministic)
    useEffect(() => {
        const c = clampViewport({ offset, scale, count: candles?.length || 0, width: 800 });
        if (c.offset === offset && c.scale === scale) return;
        const frame = requestAnimationFrame(() => {
            if (c.offset !== offset) setOffset(c.offset);
            if (c.scale !== scale) setScale(c.scale);
        });
        return () => cancelAnimationFrame(frame);
    }, [candles?.length, offset, scale]);
    return (
        <div 
            ref={containerRef} 
            className="w-full h-full bg-[#020204] overflow-hidden flex flex-col relative group"
            role="img"
            aria-label="Q360 Studio chart — TradingView max: use arrow keys to pan, plus/minus to zoom, Enter to reset, 1-8 for chart types"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'ArrowLeft') setOffset((o) => Math.max(0, o - 5));
                if (e.key === 'ArrowRight') setOffset((o) => o + 5);
                if (e.key === '+' || e.key === '=') setScale((s) => Math.min(40, s * 1.1));
                if (e.key === '-' || e.key === '_') setScale((s) => Math.max(2, s / 1.1));
                if (e.key === 'Enter') { setOffset(0); setScale(6); }
                if (e.key === 's' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); exportCanvasToPNG(mainCanvasRef.current, 'q360.png'); }
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={() => {
                handleMouseLeave();
                if (onHoverChange) onHoverChange(null);
                else setHoverInfo(null);
            }}
            style={{ cursor: isDragging ? 'grabbing' : 'crosshair' }}
        >
            {/* TradingView max toolbar — chart types, timeframes, price modes, magnet */}
            <div className="h-7 px-2 border-b border-white/5 bg-[#0a0a0f] flex items-center gap-1 overflow-x-auto">
                {[
                    ['candles','Candles'],['heikinAshi','Heikin'],['renko','Renko'],['line','Line'],['area','Area'],['baseline','Baseline'],['histogram','Hist'],['columns','Cols']
                ].map(([id,label])=>(
                    <button key={id} aria-label={`Chart type ${label}`} onClick={()=>setChartType(id)} className={`px-2 py-1 text-[9px] font-mono font-bold rounded ${chartType===id?'bg-amber-500 text-black':'bg-white/5 text-[#8b95a7] hover:text-white'}`}>{label}</button>
                ))}
                <div className="w-px h-4 bg-white/10 mx-1" />
                {['1D','1W','1M'].map(tf=>(
                    <button key={tf} aria-label={`Timeframe ${tf}`} onClick={()=>setTimeframe(tf)} className={`px-1.5 py-1 text-[9px] font-mono rounded ${timeframe===tf?'bg-blue-500/20 text-blue-400 border border-blue-500/30':'text-[#64748b] hover:text-white'}`}>{tf}</button>
                ))}
                <div className="w-px h-4 bg-white/10 mx-1" />
                {[
                    ['linear','Lin'],['log','Log'],['percent','%'],['indexed100','Idx']
                ].map(([id,label])=>(
                    <button key={id} aria-label={`Price scale ${label}`} onClick={()=>setPriceMode(id)} className={`px-1.5 py-1 text-[9px] font-mono rounded ${priceMode===id?'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20':'text-[#64748b] hover:text-white'}`}>{label}</button>
                ))}
                <div className="w-px h-4 bg-white/10 mx-1" />
                <button aria-label="Toggle magnet" onClick={()=>setMagnetEnabled(v=>!v)} className={`px-2 py-1 text-[9px] font-mono rounded ${magnetEnabled?'bg-amber-500/10 text-amber-500 border border-amber-500/20':'text-[#64748b] hover:text-white'}`}>Magnet {magnetEnabled?'ON':'OFF'}</button>
            </div>
            {/* Drawing tools 33 — TradingView max */}
            <div className="h-7 px-2 border-b border-white/5 bg-[#08080a] flex items-center gap-1 overflow-x-auto">
                {[
                    ['trendline','Trend'],['ray','Ray'],['extended','Ext'],['horizontal','H-Line'],['vertical','V-Line'],['rectangle','Rect'],['circle','Circle'],['triangle','Tri'],['parallelChannel','Channel'],['fibRetracement','Fib'],['fibExtension','FibEx'],['pitchfork','Fork'],['gann','Gann'],['brush','Brush'],['text','Text'],['longPosition','Long'],['shortPosition','Short'],['riskReward','R/R'],['measure','Measure'],['magnet','MagnetTool']
                ].map(([id,label])=>(
                    <button key={id} aria-label={`Drawing tool ${label}`} onClick={()=>{ const { setActiveDrawingTool } = require('@/stores/studio/selectionStore').useStudioSelectionStore.getState(); setActiveDrawingTool(id); }} className="px-1.5 py-1 text-[8px] font-mono rounded bg-white/5 text-[#8b95a7] hover:text-white hover:bg-white/10">{label}</button>
                ))}
                <button aria-label="Clear drawings" onClick={()=>{ const s=require('@/stores/studio/selectionStore').useStudioSelectionStore.getState(); s.clearDrawings(); }} className="px-2 py-1 text-[8px] font-mono rounded bg-red-500/10 text-red-400 border border-red-500/20">Clear</button>
            </div>

            {/* Indicator HUD (Below OHLC) */}
            {hoverInfo && activeIndicators.length > 0 && (
                <div className="absolute top-14 left-4 z-[70] flex flex-wrap gap-2 max-w-[400px] pointer-events-none">
                    {activeIndicators.filter(ind => ind.visible).map(ind => {
                        const def = getIndicator(ind.indicatorId);
                        if (!def) return null;
                        
                        try {
                            const bars = candles.map(c => ({
                                timestamp: c.time * 1000,
                                open: c.open,
                                high: c.high,
                                low: c.low,
                                close: c.close,
                                volume: c.volume
                            }));
                            // Only compute up to hover index for efficiency if possible, 
                            // but usually we need full history for EMA/RSI.
                            // The engine is fast enough for single point.
                            const output = def.compute(bars, ind.params || {});
                            const val = output.series[hoverInfo.index]?.value;
                            
                            if (val === undefined || val === null || isNaN(val)) return null;
                            
                            return (
                                <div key={ind.id} className="px-2 py-1 bg-[#0a0a0f]/80 border border-white/5 rounded backdrop-blur-sm flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: ind.color || '#fff' }} />
                                    <span className="text-[8px] font-mono text-[#64748b] uppercase">{ind.shortName || ind.indicatorId}:</span>
                                    <span className="text-[9px] font-mono text-white font-bold">{val.toFixed(2)}</span>
                                </div>
                            );
                        } catch (e) { return null; }
                    })}
                </div>
            )}

            <canvas ref={mainCanvasRef} className="block flex-1" />
            {showVolume && <canvas ref={volumeCanvasRef} className="block" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }} />}
            {oscillators.length > 0 && <canvas ref={oscCanvasRef} className="block" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }} />}
        </div>
    );
};

export default Q360Canvas;
