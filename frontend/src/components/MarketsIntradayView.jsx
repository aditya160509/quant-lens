"use client";

import React, { useState } from 'react';
import dynamic from 'next/dynamic';

// Dynamic import for Q360ChartCore (avoid SSR issues)
const IntradayChartWrapper = dynamic(
    () => import('@/components/chart_engine/IntradayChartWrapper'),
    { ssr: false, loading: () => <div className="h-full flex items-center justify-center text-terminal-dim font-mono">Loading Chart Engine...</div> }
);

/**
 * Markets View
 * Simple full-screen chart using unified chart engine
 * Supports ALL timeframes (1m-5y)
 */
export default function MarketsIntradayView() {
    const [symbol, setSymbol] = useState("SPY");
    const [interval, setInterval] = useState("5m");

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Chart fills entire space - chart engine has its own header with controls */}
            <div className="flex-1">
                <IntradayChartWrapper
                    symbol={symbol}
                    interval={interval}
                    height={700}
                    onSymbolChange={(sym) => setSymbol(sym)}
                    onIntervalChange={(tf) => setInterval(tf)}
                />
            </div>
        </div>
    );
}
