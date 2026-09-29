'use client';

/**
 * Trade Context Overlay
 * 
 * Passive informational panel per tradefeature.md §13:
 * - Trend direction (SMA comparison)
 * - Volatility state (ATR ratio)
 * - Volume behavior (vs average)
 * - Market condition summary
 */

import React, { useMemo, useState } from 'react';

// =============================================================================
// TYPES
// =============================================================================

export interface MarketContext {
    trend: {
        direction: 'up' | 'down' | 'neutral';
        strength: number; // 0-100
        description: string;
    };
    volatility: {
        state: 'high' | 'normal' | 'low';
        atrRatio: number;
        description: string;
    };
    volume: {
        state: 'above' | 'average' | 'below';
        ratio: number;
        description: string;
    };
    marketCondition: 'trending' | 'choppy' | 'quiet' | 'breakout';
}

interface TradeContextOverlayProps {
    context: MarketContext | null;
    visible?: boolean;
    position?: 'top-left' | 'top-right';
    onToggleVisibility?: () => void;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const THEME = {
    bg: 'rgba(30, 34, 45, 0.9)',
    border: '#363a45',
    text: '#d1d4dc',
    textMuted: '#787b86',
    up: '#26a69a',
    down: '#ef5350',
    neutral: '#787b86',
    warning: '#ff9800',
    info: '#2196f3',
};

// =============================================================================
// CONTEXT CALCULATOR
// =============================================================================

interface OHLCVBar {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export function calculateMarketContext(
    bars: OHLCVBar[],
    sma50?: number[],
    sma200?: number[],
    atr14?: number[]
): MarketContext | null {
    if (bars.length < 50) return null;

    const currentBar = bars[bars.length - 1];
    const currentPrice = currentBar.close;

    // Calculate SMA 50 and 200 if not provided
    const sma50Val = sma50?.[sma50.length - 1] ?? calculateSMA(bars.slice(-50).map(b => b.close));
    const sma200Val = sma200?.[sma200.length - 1] ?? (bars.length >= 200 
        ? calculateSMA(bars.slice(-200).map(b => b.close)) 
        : sma50Val);

    // Trend Analysis
    let trendDirection: 'up' | 'down' | 'neutral' = 'neutral';
    let trendStrength = 50;
    let trendDescription = 'Neutral - Price oscillating between moving averages';

    if (currentPrice > sma50Val && sma50Val > sma200Val) {
        trendDirection = 'up';
        trendStrength = Math.min(100, 50 + ((currentPrice - sma50Val) / sma50Val) * 1000);
        trendDescription = 'Uptrend - Price above 50 SMA, 50 SMA above 200 SMA';
    } else if (currentPrice < sma50Val && sma50Val < sma200Val) {
        trendDirection = 'down';
        trendStrength = Math.min(100, 50 + ((sma50Val - currentPrice) / sma50Val) * 1000);
        trendDescription = 'Downtrend - Price below 50 SMA, 50 SMA below 200 SMA';
    }

    // Volatility Analysis
    const recentTR = bars.slice(-14).map((bar, i, arr) => {
        if (i === 0) return bar.high - bar.low;
        const prevClose = arr[i - 1]?.close ?? bar.close;
        return Math.max(
            bar.high - bar.low,
            Math.abs(bar.high - prevClose),
            Math.abs(bar.low - prevClose)
        );
    });
    const currentATR = recentTR.reduce((a, b) => a + b, 0) / recentTR.length;
    
    const olderTR = bars.slice(-50, -14).map((bar, i, arr) => {
        if (i === 0) return bar.high - bar.low;
        const prevClose = arr[i - 1]?.close ?? bar.close;
        return Math.max(
            bar.high - bar.low,
            Math.abs(bar.high - prevClose),
            Math.abs(bar.low - prevClose)
        );
    });
    const avgATR = olderTR.length > 0 
        ? olderTR.reduce((a, b) => a + b, 0) / olderTR.length 
        : currentATR;

    const atrRatio = avgATR > 0 ? currentATR / avgATR : 1;
    let volatilityState: 'high' | 'normal' | 'low' = 'normal';
    let volatilityDescription = 'Normal volatility';

    if (atrRatio > 1.2) {
        volatilityState = 'high';
        volatilityDescription = `High volatility (${(atrRatio * 100).toFixed(0)}% of average)`;
    } else if (atrRatio < 0.8) {
        volatilityState = 'low';
        volatilityDescription = `Low volatility (${(atrRatio * 100).toFixed(0)}% of average)`;
    }

    // Volume Analysis
    const recentVolumes = bars.slice(-20).map(b => b.volume);
    const avgVolume = recentVolumes.reduce((a, b) => a + b, 0) / recentVolumes.length;
    const currentVolume = currentBar.volume;
    const volumeRatio = avgVolume > 0 ? currentVolume / avgVolume : 1;

    let volumeState: 'above' | 'average' | 'below' = 'average';
    let volumeDescription = 'Average volume';

    if (volumeRatio > 1.5) {
        volumeState = 'above';
        volumeDescription = `Above average (${(volumeRatio * 100).toFixed(0)}% of 20-bar avg)`;
    } else if (volumeRatio < 0.5) {
        volumeState = 'below';
        volumeDescription = `Below average (${(volumeRatio * 100).toFixed(0)}% of 20-bar avg)`;
    }

    // Market Condition Summary
    let marketCondition: 'trending' | 'choppy' | 'quiet' | 'breakout' = 'choppy';

    if (trendDirection !== 'neutral' && volumeState === 'above' && volatilityState !== 'low') {
        marketCondition = 'trending';
    } else if (trendDirection === 'neutral' && volatilityState === 'low' && volumeState === 'below') {
        marketCondition = 'quiet';
    } else if (volumeState === 'above' && volatilityState === 'high') {
        marketCondition = 'breakout';
    }

    return {
        trend: { direction: trendDirection, strength: trendStrength, description: trendDescription },
        volatility: { state: volatilityState, atrRatio, description: volatilityDescription },
        volume: { state: volumeState, ratio: volumeRatio, description: volumeDescription },
        marketCondition,
    };
}

function calculateSMA(values: number[]): number {
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function TradeContextOverlay({
    context,
    visible = true,
    position = 'top-left',
    onToggleVisibility,
}: TradeContextOverlayProps) {
    const [isHovered, setIsHovered] = useState(false);
    const [isCollapsed, setIsCollapsed] = useState(false);

    if (!visible || !context) return null;

    const positionStyles = position === 'top-left'
        ? { left: '12px', top: '12px' }
        : { right: '12px', top: '12px' };

    if (isCollapsed) {
        return (
            <button
                onClick={() => setIsCollapsed(false)}
                style={{
                    position: 'absolute',
                    ...positionStyles,
                    padding: '8px',
                    background: THEME.bg,
                    border: `1px solid ${THEME.border}`,
                    borderRadius: '6px',
                    color: THEME.text,
                    cursor: 'pointer',
                    zIndex: 50,
                    fontSize: '12px',
                }}
                title="Expand Market Context"
            >
                📊
            </button>
        );
    }

    const getTrendColor = () => {
        switch (context.trend.direction) {
            case 'up': return THEME.up;
            case 'down': return THEME.down;
            default: return THEME.neutral;
        }
    };

    const getVolatilityColor = () => {
        switch (context.volatility.state) {
            case 'high': return THEME.warning;
            case 'low': return THEME.neutral;
            default: return THEME.info;
        }
    };

    const getVolumeColor = () => {
        switch (context.volume.state) {
            case 'above': return THEME.up;
            case 'below': return THEME.down;
            default: return THEME.neutral;
        }
    };

    const getMarketConditionStyle = () => {
        switch (context.marketCondition) {
            case 'trending': return { bg: 'rgba(38, 166, 154, 0.2)', text: THEME.up };
            case 'breakout': return { bg: 'rgba(255, 152, 0, 0.2)', text: THEME.warning };
            case 'quiet': return { bg: 'rgba(120, 123, 134, 0.2)', text: THEME.neutral };
            default: return { bg: 'rgba(239, 83, 80, 0.2)', text: THEME.down };
        }
    };

    const marketStyle = getMarketConditionStyle();

    return (
        <div
            style={{
                position: 'absolute',
                ...positionStyles,
                width: '200px',
                background: THEME.bg,
                border: `1px solid ${THEME.border}`,
                borderRadius: '8px',
                padding: '12px',
                zIndex: 50,
                opacity: isHovered ? 1 : 0.7,
                transition: 'opacity 0.2s',
                backdropFilter: 'blur(8px)',
            }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ color: THEME.text, fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Market Context
                </span>
                <button
                    onClick={() => setIsCollapsed(true)}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: THEME.textMuted,
                        cursor: 'pointer',
                        fontSize: '14px',
                        padding: '2px',
                    }}
                    title="Collapse"
                >
                    ×
                </button>
            </div>

            {/* Trend */}
            <div style={{ marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '14px' }}>
                        {context.trend.direction === 'up' ? '↑' : context.trend.direction === 'down' ? '↓' : '→'}
                    </span>
                    <span style={{ color: getTrendColor(), fontSize: '12px', fontWeight: 500 }}>
                        Trend: {context.trend.direction.charAt(0).toUpperCase() + context.trend.direction.slice(1)}
                    </span>
                </div>
                <div style={{ color: THEME.textMuted, fontSize: '10px', marginTop: '2px', marginLeft: '20px' }}>
                    {context.trend.description}
                </div>
            </div>

            {/* Volatility */}
            <div style={{ marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '14px' }}>📈</span>
                    <span style={{ color: getVolatilityColor(), fontSize: '12px', fontWeight: 500 }}>
                        Volatility: {context.volatility.state.charAt(0).toUpperCase() + context.volatility.state.slice(1)}
                    </span>
                </div>
                <div style={{ color: THEME.textMuted, fontSize: '10px', marginTop: '2px', marginLeft: '20px' }}>
                    ATR: {(context.volatility.atrRatio * 100).toFixed(0)}% of average
                </div>
            </div>

            {/* Volume */}
            <div style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '14px' }}>📊</span>
                    <span style={{ color: getVolumeColor(), fontSize: '12px', fontWeight: 500 }}>
                        Volume: {context.volume.state === 'above' ? 'Above Avg' : context.volume.state === 'below' ? 'Below Avg' : 'Average'}
                    </span>
                </div>
                <div style={{ color: THEME.textMuted, fontSize: '10px', marginTop: '2px', marginLeft: '20px' }}>
                    {(context.volume.ratio * 100).toFixed(0)}% of 20-bar average
                </div>
            </div>

            {/* Market Condition */}
            <div
                style={{
                    background: marketStyle.bg,
                    borderRadius: '4px',
                    padding: '8px 10px',
                    textAlign: 'center',
                }}
            >
                <span style={{ color: marketStyle.text, fontSize: '11px', fontWeight: 600, textTransform: 'uppercase' }}>
                    {context.marketCondition === 'choppy' ? 'Choppy Market' :
                     context.marketCondition === 'trending' ? 'Trending Market' :
                     context.marketCondition === 'quiet' ? 'Quiet Market' : 'Breakout Potential'}
                </span>
            </div>
        </div>
    );
}

export default TradeContextOverlay;
