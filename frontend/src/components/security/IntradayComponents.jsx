"use client";

import React, { useMemo } from 'react';

/**
 * Market Control Bar
 * Shows BUYERS IN CONTROL / SELLERS IN CONTROL / BALANCED
 * Based on close vs VWAP relationship
 */
export function MarketControlBar({ close, vwap }) {
    const control = useMemo(() => {
        if (!close || !vwap || vwap === 0) return { label: 'NO DATA', color: 'text-terminal-dim' };
        
        const deviation = (close - vwap) / vwap;
        
        if (deviation > 0.0015) {
            return { label: 'BUYERS IN CONTROL', color: 'text-terminal-green' };
        } else if (deviation < -0.0015) {
            return { label: 'SELLERS IN CONTROL', color: 'text-terminal-red' };
        } else {
            return { label: 'BALANCED', color: 'text-terminal-dim' };
        }
    }, [close, vwap]);

    return (
        <div className="w-full py-1 px-2 bg-terminal-dark border-t border-b border-terminal-gray">
            <span className={`font-mono text-[10px] uppercase ${control.color}`}>
                {control.label}
            </span>
        </div>
    );
}

/**
 * Realized Intraday Volatility Strip
 * Shows realized volatility based on log returns
 */
export function RealizedVolatilityStrip({ closes, barsPerDay = 78 }) {
    const volatility = useMemo(() => {
        if (!closes || closes.length < 2) return null;
        
        // Calculate log returns
        const returns = [];
        for (let i = 1; i < closes.length; i++) {
            if (closes[i-1] > 0 && closes[i] > 0) {
                returns.push(Math.log(closes[i] / closes[i-1]));
            }
        }
        
        if (returns.length === 0) return null;
        
        // Sum of squared returns
        const sumSquares = returns.reduce((acc, r) => acc + r * r, 0);
        
        // Annualized realized volatility
        const rv = Math.sqrt(sumSquares) * Math.sqrt(252 * barsPerDay);
        
        return (rv * 100).toFixed(2);
    }, [closes, barsPerDay]);

    if (!volatility) {
        return (
            <div className="w-full py-1 px-2 bg-terminal-dark border border-terminal-gray">
                <span className="font-mono text-[9px] text-terminal-dim">RV: --</span>
            </div>
        );
    }

    return (
        <div className="w-full py-1 px-2 bg-terminal-dark border border-terminal-gray flex items-center gap-4">
            <span className="font-mono text-[9px] text-terminal-dim">REALIZED VOL</span>
            <span className="font-mono text-[10px] text-terminal-text">{volatility}%</span>
        </div>
    );
}

/**
 * Session Range Context
 * Shows position in session range and range vs ATR
 */
export function SessionRangeContext({ high, low, close, atr }) {
    const context = useMemo(() => {
        if (!high || !low || !close || high === low) {
            return { position: '--', rangeVsAtr: '--' };
        }
        
        const sessionRange = high - low;
        const rangePos = ((close - low) / sessionRange) * 100;
        const rangeVsAtr = atr && atr > 0 ? ((sessionRange / atr) * 100) : null;
        
        return {
            position: rangePos.toFixed(0),
            rangeVsAtr: rangeVsAtr ? rangeVsAtr.toFixed(0) : '--'
        };
    }, [high, low, close, atr]);

    return (
        <div className="flex items-center gap-4 font-mono text-[9px]">
            <div>
                <span className="text-terminal-dim">RANGE POS: </span>
                <span className="text-terminal-text">{context.position}%</span>
            </div>
            <div>
                <span className="text-terminal-dim">RANGE/ATR: </span>
                <span className="text-terminal-text">{context.rangeVsAtr}%</span>
            </div>
        </div>
    );
}

/**
 * News and Events Feed
 * Compact scrollable list of news items
 * Format: HH:MM  SOURCE  HEADLINE
 */
export function NewsEventsFeed({ news, symbol, loading }) {
    const filteredNews = useMemo(() => {
        if (!news || !Array.isArray(news)) return [];
        
        // Filter system notices and map to display format
        return news
            .filter(item => item.source !== 'system') // Skip system notices
            .slice(0, 18) // Max 18 rows as per spec
            .map(item => ({
                // API uses 'publishedAt' not 'published_at_utc'
                time: item.publishedAt ? new Date(item.publishedAt).toLocaleTimeString('en-US', { 
                    hour: '2-digit', 
                    minute: '2-digit',
                    hour12: false 
                }) : '--:--',
                source: item.source?.toUpperCase() || 'NEWS',
                headline: item.title || item.headline || 'Untitled',
                url: item.url
            }));
    }, [news]);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center text-terminal-dim font-mono text-xs animate-pulse">
                LOADING NEWS...
            </div>
        );
    }

    if (filteredNews.length === 0) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-terminal-dim font-mono text-[10px] gap-1">
                <span>NEWS FEED</span>
                <span className="text-[9px]">No current news for {symbol}</span>
                <span className="text-[8px] text-terminal-gray">Requires RSS/GDELT integration</span>
            </div>
        );
    }

    return (
        <div className="h-full overflow-auto">
            <div className="flex flex-col">
                {filteredNews.map((item, idx) => (
                    <a 
                        key={idx}
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-start gap-2 py-1 px-1 hover:bg-terminal-gray/20 transition-colors border-b border-terminal-gray/30"
                    >
                        <span className="font-mono text-[9px] text-terminal-dim shrink-0 w-10">
                            {item.time}
                        </span>
                        <span className="font-mono text-[8px] text-terminal-yellow shrink-0 w-14 truncate">
                            {item.source}
                        </span>
                        <span className="font-mono text-[9px] text-terminal-text truncate flex-1">
                            {item.headline}
                        </span>
                    </a>
                ))}
            </div>
        </div>
    );
}

/**
 * Calculate VWAP from OHLCV bars
 * Returns array of cumulative VWAP values
 */
export function calculateVWAP(bars) {
    if (!bars || bars.length === 0) return [];
    
    let cumulativePV = 0;
    let cumulativeVolume = 0;
    
    return bars.map(bar => {
        const tp = (bar.high + bar.low + bar.close) / 3;
        cumulativePV += tp * bar.volume;
        cumulativeVolume += bar.volume;
        
        return cumulativeVolume > 0 ? cumulativePV / cumulativeVolume : bar.close;
    });
}

const IntradayComponents = {
    MarketControlBar,
    RealizedVolatilityStrip,
    SessionRangeContext,
    NewsEventsFeed,
    calculateVWAP
};

export default IntradayComponents;
