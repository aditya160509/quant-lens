"use client";
import React, { useRef, useEffect, useMemo, useState } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { setupHiDPI } from './visual-kernel/canvas';
import { createLinearScale } from './visual-kernel/scales';

/**
 * Equity Comparison Canvas
 * Renders equity curves with "Ghost" overlays for strategy comparison.
 * 
 * Production-grade implementation:
 * - Computes real equity curves from trading signals and candle data
 * - Calculates actual returns, drawdowns, and alpha metrics
 * - No mock data or random values
 */

// ============== METRIC CALCULATIONS ==============

/**
 * Calculate cumulative returns from equity curve
 */
const calculateCumulativeReturn = (equityCurve) => {
    if (!equityCurve || equityCurve.length < 2) return null;
    const start = equityCurve[0]?.value;
    const end = equityCurve[equityCurve.length - 1]?.value;
    if (!Number.isFinite(start) || !Number.isFinite(end) || start <= 0) return null;
    return ((end - start) / start) * 100;
};

/**
 * Calculate maximum drawdown from equity curve
 */
const calculateMaxDrawdown = (equityCurve) => {
    if (!equityCurve || equityCurve.length < 2) return null;
    
    let peak = -Infinity;
    let maxDD = 0;
    
    equityCurve.forEach(point => {
        const value = point.value;
        if (value > peak) peak = value;
        const dd = ((peak - value) / peak) * 100;
        if (dd > maxDD) maxDD = dd;
    });
    
    return maxDD;
};

// ============== MAIN COMPONENT ==============

const EquityComparisonCanvas = ({
    primaryEquity = [],     // { x: number, value: number, time?: number }[]
    ghostEquity = [],       // { x: number, value: number, time?: number }[]  
    primaryLabel = 'Strategy',
    ghostLabel = 'Benchmark',
    primaryMetrics = {},    // Canonical backend metrics
    ghostMetrics = {},
    height = 180,
    showMetrics = true
}) => {
    const canvasRef = useRef(null);
    const [hoveredPoint, setHoveredPoint] = useState(null);

    // Calculate metrics from REAL data
    const metrics = useMemo(() => {
        if (primaryEquity.length < 2) return null;

        const canonicalReturn = primaryMetrics?.canonical?.total_return?.value;
        const primaryReturn = Number.isFinite(canonicalReturn)
            ? canonicalReturn * 100
            : calculateCumulativeReturn(primaryEquity);
        const canonicalGhostReturn = ghostMetrics?.canonical?.total_return?.value;
        const ghostReturn = Number.isFinite(canonicalGhostReturn) ? canonicalGhostReturn * 100 : calculateCumulativeReturn(ghostEquity);
        const excessReturn = Number.isFinite(primaryReturn) && Number.isFinite(ghostReturn)
            ? primaryReturn - ghostReturn
            : null;
        
        const canonicalDrawdown = primaryMetrics?.canonical?.max_drawdown?.value;
        const primaryMaxDD = Number.isFinite(canonicalDrawdown)
            ? Math.abs(canonicalDrawdown * 100)
            : calculateMaxDrawdown(primaryEquity);
        const canonicalGhostDrawdown = ghostMetrics?.canonical?.max_drawdown?.value;
        const ghostMaxDD = Number.isFinite(canonicalGhostDrawdown) ? Math.abs(canonicalGhostDrawdown * 100) : calculateMaxDrawdown(ghostEquity);
        const sharpe = Number.isFinite(primaryMetrics?.sharpe) ? primaryMetrics.sharpe : null;

        return { 
            primaryReturn, 
            ghostReturn, 
            excessReturn,
            primaryMaxDD, 
            ghostMaxDD,
            sharpe,
        };
    }, [primaryEquity, ghostEquity, ghostMetrics, primaryMetrics]);

    // Draw the equity curves — uses visual-kernel (P4-W1)
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || primaryEquity.length < 2) return;
        const rect = canvas.getBoundingClientRect();
        const { ctx, width } = setupHiDPI(canvas, { width: rect.width, height });
        // setupHiDPI sets canvas.height = height*dpr; preserve height semantics
        canvas.style.height = `${height}px`;
        const paddingTop = 30;
        const paddingBottom = 25;
        const paddingLeft = 55;
        const paddingRight = 20;
        const chartWidth = width - paddingLeft - paddingRight;
        const chartHeight = height - paddingTop - paddingBottom;

        // Clear
        ctx.fillStyle = '#0a0a0f';
        ctx.fillRect(0, 0, width, height);

        // Find value range across both curves
        const allValues = [
            ...primaryEquity.map(p => p.value),
            ...(ghostEquity.length > 0 ? ghostEquity.map(p => p.value) : [])
        ];
        const minVal = Math.min(...allValues) * 0.98;
        const maxVal = Math.max(...allValues) * 1.02;
        const valueRange = maxVal - minVal || 1;

        const xScale = createLinearScale([0, primaryEquity.length - 1], [paddingLeft, paddingLeft + chartWidth]);
        const yScale = createLinearScale([minVal, maxVal], [paddingTop + chartHeight, paddingTop]);
        const scaleX = (idx) => xScale(idx);
        const scaleXGhost = (idx, total) => {
            const s = createLinearScale([0, total - 1], [paddingLeft, paddingLeft + chartWidth]);
            return s(idx);
        };
        const scaleY = (val) => yScale(val);

        // Draw grid lines
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
            const y = paddingTop + (i / 4) * chartHeight;
            ctx.beginPath();
            ctx.moveTo(paddingLeft, y);
            ctx.lineTo(width - paddingRight, y);
            ctx.stroke();

            // Y-axis labels
            const val = maxVal - (i / 4) * valueRange;
            ctx.fillStyle = '#475569';
            ctx.font = '9px "JetBrains Mono", monospace';
            ctx.textAlign = 'right';
            ctx.fillText(val.toFixed(0), paddingLeft - 8, y + 3);
        }

        // Draw zero line if visible
        const startVal = primaryEquity[0]?.value || 100;
        if (startVal >= minVal && startVal <= maxVal) {
            const zeroY = scaleY(startVal);
            ctx.strokeStyle = 'rgba(255,255,255,0.1)';
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(paddingLeft, zeroY);
            ctx.lineTo(width - paddingRight, zeroY);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Draw Ghost Equity (behind, transparent)
        if (ghostEquity.length > 1) {
            // Fill area
            ctx.beginPath();
            ctx.moveTo(scaleXGhost(0, ghostEquity.length), height - paddingBottom);
            ghostEquity.forEach((p, i) => {
                ctx.lineTo(scaleXGhost(i, ghostEquity.length), scaleY(p.value));
            });
            ctx.lineTo(scaleXGhost(ghostEquity.length - 1, ghostEquity.length), height - paddingBottom);
            ctx.closePath();
            ctx.fillStyle = 'rgba(100, 116, 139, 0.1)';
            ctx.fill();
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(100, 116, 139, 0.5)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 4]);
            ghostEquity.forEach((p, i) => {
                if (i === 0) ctx.moveTo(scaleXGhost(i, ghostEquity.length), scaleY(p.value));
                else ctx.lineTo(scaleXGhost(i, ghostEquity.length), scaleY(p.value));
            });
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Draw Primary Equity (front, solid)
        if (primaryEquity.length > 1) {
            const isPositive = metrics && metrics.primaryReturn >= 0;
            const lineColor = isPositive ? '#ffd60a' : '#ef4444';
            const fillColorTop = isPositive ? 'rgba(255, 214, 10, 0.25)' : 'rgba(239, 68, 68, 0.25)';
            const fillColorBottom = isPositive ? 'rgba(255, 214, 10, 0.02)' : 'rgba(239, 68, 68, 0.02)';

            // Gradient fill
            const gradient = ctx.createLinearGradient(0, paddingTop, 0, height - paddingBottom);
            gradient.addColorStop(0, fillColorTop);
            gradient.addColorStop(1, fillColorBottom);

            ctx.beginPath();
            ctx.moveTo(scaleX(0, primaryEquity.length), height - paddingBottom);
            primaryEquity.forEach((p, i) => {
                ctx.lineTo(scaleX(i, primaryEquity.length), scaleY(p.value));
            });
            ctx.lineTo(scaleX(primaryEquity.length - 1, primaryEquity.length), height - paddingBottom);
            ctx.closePath();
            ctx.fillStyle = gradient;
            ctx.fill();

            // Solid line
            ctx.beginPath();
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 2;
            primaryEquity.forEach((p, i) => {
                if (i === 0) ctx.moveTo(scaleX(i, primaryEquity.length), scaleY(p.value));
                else ctx.lineTo(scaleX(i, primaryEquity.length), scaleY(p.value));
            });
            ctx.stroke();

            // End point marker
            const lastPt = primaryEquity[primaryEquity.length - 1];
            const endX = scaleX(primaryEquity.length - 1, primaryEquity.length);
            const endY = scaleY(lastPt.value);
            
            ctx.beginPath();
            ctx.arc(endX, endY, 4, 0, Math.PI * 2);
            ctx.fillStyle = lineColor;
            ctx.fill();
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        // Legend
        ctx.font = 'bold 9px "JetBrains Mono", monospace';
        ctx.textAlign = 'left';

        // Primary legend
        ctx.fillStyle = metrics && metrics.primaryReturn >= 0 ? '#ffd60a' : '#ef4444';
        ctx.fillRect(paddingLeft, 10, 14, 3);
        ctx.fillStyle = '#fff';
        ctx.fillText(primaryLabel, paddingLeft + 20, 14);

        // Ghost legend
        if (ghostEquity.length > 0) {
            ctx.strokeStyle = 'rgba(100, 116, 139, 0.5)';
            ctx.setLineDash([4, 4]);
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(paddingLeft + 100, 11);
            ctx.lineTo(paddingLeft + 114, 11);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.fillStyle = '#64748b';
            ctx.fillText(ghostLabel, paddingLeft + 120, 14);
        }

    }, [primaryEquity, ghostEquity, primaryLabel, ghostLabel, height, metrics]);

    // Handle mouse move for hover effect
    const handleMouseMove = (e) => {
        if (primaryEquity.length < 2) return;
        
        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        
        const paddingLeft = 55;
        const paddingRight = 20;
        const chartWidth = rect.width - paddingLeft - paddingRight;
        
        const idx = Math.round(((x - paddingLeft) / chartWidth) * (primaryEquity.length - 1));
        
        if (idx >= 0 && idx < primaryEquity.length) {
            const point = primaryEquity[idx];
            const ghostPoint = ghostEquity[idx];
            setHoveredPoint({
                x: e.clientX,
                y: e.clientY,
                value: point.value,
                ghostValue: ghostPoint?.value,
                time: point.time
            });
        }
    };

    if (primaryEquity.length < 2) {
        return (
            <div 
                className="flex items-center justify-center bg-[#0a0a0f] rounded-xl border border-white/5"
                style={{ height: `${height}px` }}
            >
                <span className="text-[10px] font-mono text-[#64748b]">
                    Execute strategy to see equity curve
                </span>
            </div>
        );
    }

    return (
        <div className="relative bg-[#0a0a0f] rounded-xl border border-white/5 overflow-hidden">
            <canvas 
                ref={canvasRef} 
                className="w-full cursor-crosshair" 
                style={{ height: `${height}px` }}
                onMouseMove={handleMouseMove}
                onMouseLeave={() => setHoveredPoint(null)}
            />

            {/* Metrics Overlay */}
            {showMetrics && metrics && (
                <div className="absolute top-2 right-2 flex items-center gap-2 px-3 py-1.5 bg-black/70 backdrop-blur rounded-lg">
                    <div className="text-center px-2">
                        <div className={`text-[11px] font-mono font-bold flex items-center gap-1 ${metrics.primaryReturn >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {metrics.primaryReturn >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                            {metrics.primaryReturn >= 0 ? '+' : ''}{metrics.primaryReturn.toFixed(2)}%
                        </div>
                        <div className="text-[7px] font-mono text-[#64748b] uppercase">Return</div>
                    </div>
                    
                    {ghostEquity.length > 0 && (
                        <>
                            <div className="w-px h-6 bg-white/10" />
                            <div className="text-center px-2">
                                <div className={`text-[11px] font-mono font-bold ${metrics.excessReturn >= 0 ? 'text-amber-400' : 'text-red-400'}`}>
                                    {metrics.excessReturn >= 0 ? '+' : ''}{metrics.excessReturn.toFixed(2)}%
                                </div>
                                <div className="text-[7px] font-mono text-[#64748b] uppercase">Total excess</div>
                            </div>
                        </>
                    )}
                    
                    <div className="w-px h-6 bg-white/10" />
                    <div className="text-center px-2">
                        <div className="text-[11px] font-mono font-bold text-red-400">
                            -{metrics.primaryMaxDD.toFixed(2)}%
                        </div>
                        <div className="text-[7px] font-mono text-[#64748b] uppercase">Max DD</div>
                    </div>
                    
                    {metrics.sharpe !== null && (
                        <>
                            <div className="w-px h-6 bg-white/10" />
                            <div className="text-center px-2">
                                <div className={`text-[11px] font-mono font-bold ${metrics.sharpe >= 1 ? 'text-emerald-400' : metrics.sharpe >= 0 ? 'text-amber-400' : 'text-red-400'}`}>
                                    {metrics.sharpe.toFixed(2)}
                                </div>
                                <div className="text-[7px] font-mono text-[#64748b] uppercase">Sharpe</div>
                            </div>
                        </>
                    )}
                </div>
            )}

            {/* Hover Tooltip */}
            {hoveredPoint && (
                <div 
                    className="fixed z-50 px-2 py-1 bg-black/90 border border-white/10 rounded text-[9px] font-mono pointer-events-none"
                    style={{ left: hoveredPoint.x + 10, top: hoveredPoint.y - 35 }}
                >
                    <div className="text-white font-bold">${hoveredPoint.value.toFixed(2)}</div>
                    {hoveredPoint.ghostValue && (
                        <div className="text-[#64748b]">Bench: ${hoveredPoint.ghostValue.toFixed(2)}</div>
                    )}
                    {hoveredPoint.time && (
                        <div className="text-[#64748b]">{new Date(hoveredPoint.time * 1000).toLocaleDateString()}</div>
                    )}
                </div>
            )}
        </div>
    );
};

export default EquityComparisonCanvas;
