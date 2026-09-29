/**
 * Professional Chart Container - TradingView-Inspired Design
 * 
 * Key Design Principles (from TradingView research):
 * 1. FIXED DIMENSIONS - No layout shifts, no bouncing
 * 2. DUAL-CANVAS - Main chart + crosshair overlay for smooth interaction
 * 3. CSS CONTAINMENT - Prevents layout thrashing
 * 4. GPU ACCELERATION - Uses transform3d and will-change
 * 5. STICKY LAYOUT - Chart fills container without overflow issues
 * 
 * This is a complete wrapper that ensures stable chart rendering.
 */

'use client';

import React, { useRef, useState, useEffect, useCallback, useMemo } from 'react';

// Theme constants matching TradingView dark mode
const CHART_COLORS = {
    background: '#131722',
    backgroundSecondary: '#1e222d',
    border: '#2a2e39',
    text: '#d1d4dc',
    textSecondary: '#787b86',
    upColor: '#26a69a',
    downColor: '#ef5350',
    crosshair: '#758696',
    grid: '#363a45',
    accent: '#2962ff',
};

interface StableChartContainerProps {
    /** Chart content to render */
    children: React.ReactNode;
    /** Minimum height in pixels */
    minHeight?: number;
    /** If true, uses fixed height instead of flex */
    fixedHeight?: number;
    /** Loading state */
    isLoading?: boolean;
    /** Error message */
    error?: string | null;
    /** Symbol being displayed */
    symbol?: string;
    /** Current interval */
    interval?: string;
    /** Price info */
    priceInfo?: {
        price: number;
        change: number;
        changePercent: number;
    };
}

/**
 * StableChartContainer - Prevents all bouncing and layout shifts
 * 
 * Uses:
 * - CSS containment to isolate layout calculations
 * - Fixed positioning context
 * - GPU acceleration hints
 * - No dimension-based re-renders
 */
export function StableChartContainer({
    children,
    minHeight = 400,
    fixedHeight,
    isLoading,
    error,
    symbol,
    interval,
    priceInfo,
}: StableChartContainerProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    
    // Use CSS variables for dimensions - no React state needed
    useEffect(() => {
        if (containerRef.current) {
            const updateSize = () => {
                const el = containerRef.current;
                if (el) {
                    el.style.setProperty('--chart-width', `${el.clientWidth}px`);
                    el.style.setProperty('--chart-height', `${el.clientHeight}px`);
                }
            };
            
            updateSize();
            
            // Throttled resize observer
            let timeout: NodeJS.Timeout;
            const observer = new ResizeObserver(() => {
                clearTimeout(timeout);
                timeout = setTimeout(updateSize, 100);
            });
            
            observer.observe(containerRef.current);
            
            return () => {
                clearTimeout(timeout);
                observer.disconnect();
            };
        }
    }, []);

    return (
        <div
            ref={containerRef}
            className="stable-chart-container"
            style={{
                // Core layout
                position: 'relative',
                width: '100%',
                height: fixedHeight ? `${fixedHeight}px` : '100%',
                minHeight: `${minHeight}px`,
                
                // TradingView-style dark background
                background: CHART_COLORS.background,
                borderRadius: '4px',
                overflow: 'hidden',
                
                // CSS Containment - CRITICAL for preventing layout thrashing
                contain: 'strict',
                
                // GPU acceleration
                transform: 'translateZ(0)',
                willChange: 'transform',
                
                // Isolation for stacking context
                isolation: 'isolate',
                
                // Prevent any content from causing reflow
                boxSizing: 'border-box',
            }}
        >
            {/* Header Bar - TradingView style */}
            <div
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '40px',
                    background: 'linear-gradient(180deg, rgba(19,23,34,0.95) 0%, rgba(19,23,34,0.8) 100%)',
                    backdropFilter: 'blur(8px)',
                    borderBottom: `1px solid ${CHART_COLORS.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    padding: '0 12px',
                    gap: '16px',
                    zIndex: 100,
                    pointerEvents: 'none', // Allow clicks through to chart
                }}
            >
                {symbol && (
                    <span style={{ 
                        color: CHART_COLORS.text, 
                        fontWeight: 600,
                        fontSize: '14px',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                    }}>
                        {symbol}
                    </span>
                )}
                {interval && (
                    <span style={{ 
                        color: CHART_COLORS.textSecondary,
                        fontSize: '12px',
                        background: CHART_COLORS.backgroundSecondary,
                        padding: '2px 8px',
                        borderRadius: '4px',
                    }}>
                        {interval}
                    </span>
                )}
                {priceInfo && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ 
                            color: CHART_COLORS.text,
                            fontSize: '14px',
                            fontWeight: 500,
                        }}>
                            {priceInfo.price.toFixed(2)}
                        </span>
                        <span style={{ 
                            color: priceInfo.change >= 0 ? CHART_COLORS.upColor : CHART_COLORS.downColor,
                            fontSize: '12px',
                        }}>
                            {priceInfo.change >= 0 ? '+' : ''}{priceInfo.change.toFixed(2)} ({priceInfo.changePercent.toFixed(2)}%)
                        </span>
                    </div>
                )}
            </div>

            {/* Chart Area - Full bleed */}
            <div
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    // Containment for the chart content
                    contain: 'layout size style',
                }}
            >
                {children}
            </div>

            {/* Loading Overlay */}
            {isLoading && (
                <div
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(19, 23, 34, 0.8)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 200,
                    }}
                >
                    <div style={{ textAlign: 'center' }}>
                        <div
                            style={{
                                width: '32px',
                                height: '32px',
                                border: `3px solid ${CHART_COLORS.border}`,
                                borderTopColor: CHART_COLORS.accent,
                                borderRadius: '50%',
                                animation: 'spin 1s linear infinite',
                                margin: '0 auto 12px',
                            }}
                        />
                        <span style={{ color: CHART_COLORS.textSecondary, fontSize: '13px' }}>
                            Loading chart...
                        </span>
                    </div>
                </div>
            )}

            {/* Error Overlay */}
            {error && (
                <div
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        background: 'rgba(19, 23, 34, 0.9)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 200,
                    }}
                >
                    <div style={{ textAlign: 'center', padding: '20px' }}>
                        <div style={{ 
                            fontSize: '24px', 
                            marginBottom: '8px',
                            color: CHART_COLORS.downColor,
                        }}>
                            ⚠️
                        </div>
                        <span style={{ color: CHART_COLORS.text, fontSize: '14px' }}>
                            {error}
                        </span>
                    </div>
                </div>
            )}

            {/* CSS for animations */}
            <style jsx>{`
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
}

/**
 * useStableDimensions - Hook for stable chart dimensions
 * 
 * Returns memoized dimensions that only update on significant changes
 * to prevent chart bouncing during minor resize events.
 */
export function useStableDimensions(containerRef: React.RefObject<HTMLDivElement>) {
    const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
    const lastUpdateRef = useRef(0);
    
    useEffect(() => {
        if (!containerRef.current) return;
        
        const updateDimensions = () => {
            const el = containerRef.current;
            if (!el) return;
            
            const rect = el.getBoundingClientRect();
            const now = Date.now();
            
            // Throttle updates to prevent rapid re-renders
            if (now - lastUpdateRef.current < 100) return;
            
            // Only update if change is significant (> 5px)
            setDimensions(prev => {
                const widthDiff = Math.abs(prev.width - rect.width);
                const heightDiff = Math.abs(prev.height - rect.height);
                
                if (widthDiff > 5 || heightDiff > 5) {
                    lastUpdateRef.current = now;
                    return {
                        width: Math.floor(rect.width),
                        height: Math.floor(rect.height),
                    };
                }
                return prev;
            });
        };
        
        // Initial measurement
        updateDimensions();
        
        // Throttled resize observer
        let timeout: NodeJS.Timeout;
        const observer = new ResizeObserver(() => {
            clearTimeout(timeout);
            timeout = setTimeout(updateDimensions, 100);
        });
        
        observer.observe(containerRef.current);
        
        return () => {
            clearTimeout(timeout);
            observer.disconnect();
        };
    }, [containerRef]);
    
    return dimensions;
}

/**
 * CrosshairOverlay - Separate layer for crosshair to prevent main chart re-renders
 */
export function CrosshairOverlay({
    width,
    height,
    mouseX,
    mouseY,
    priceLabel,
    timeLabel,
    visible,
}: {
    width: number;
    height: number;
    mouseX: number;
    mouseY: number;
    priceLabel?: string;
    timeLabel?: string;
    visible: boolean;
}) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        
        // Scale for retina
        const dpr = window.devicePixelRatio || 1;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);
        
        // Clear
        ctx.clearRect(0, 0, width, height);
        
        if (!visible || mouseX < 0 || mouseY < 0) return;
        
        // Draw crosshair lines
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = CHART_COLORS.crosshair;
        ctx.lineWidth = 1;
        
        // Vertical line
        ctx.beginPath();
        ctx.moveTo(mouseX, 0);
        ctx.lineTo(mouseX, height);
        ctx.stroke();
        
        // Horizontal line
        ctx.beginPath();
        ctx.moveTo(0, mouseY);
        ctx.lineTo(width, mouseY);
        ctx.stroke();
        
        ctx.setLineDash([]);
        
        // Price label on right axis
        if (priceLabel) {
            ctx.fillStyle = CHART_COLORS.crosshair;
            ctx.fillRect(width - 60, mouseY - 10, 60, 20);
            ctx.fillStyle = CHART_COLORS.text;
            ctx.font = '11px system-ui';
            ctx.textAlign = 'center';
            ctx.fillText(priceLabel, width - 30, mouseY + 4);
        }
        
        // Time label on bottom axis
        if (timeLabel) {
            ctx.fillStyle = CHART_COLORS.crosshair;
            ctx.fillRect(mouseX - 30, height - 20, 60, 20);
            ctx.fillStyle = CHART_COLORS.text;
            ctx.font = '11px system-ui';
            ctx.textAlign = 'center';
            ctx.fillText(timeLabel, mouseX, height - 6);
        }
        
    }, [width, height, mouseX, mouseY, priceLabel, timeLabel, visible]);
    
    return (
        <canvas
            ref={canvasRef}
            style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width,
                height,
                pointerEvents: 'none',
                zIndex: 50,
            }}
        />
    );
}

export { CHART_COLORS };
export default StableChartContainer;
