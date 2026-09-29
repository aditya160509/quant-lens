'use client';

/**
 * Chart Tab - Simple wrapper that renders Q360ChartCore
 * All logic is in Q360ChartCore - this is just a container
 */

import React, { useRef } from 'react';
import { useTradingContext } from '@/context/TradingContext';
import dynamic from 'next/dynamic';
import { useStableDimensions } from '@/components/chart_engine/StableChartContainer';

// Single chart component - all logic is here
const Q360ChartCore = dynamic(
    () => import('@/components/chart_engine/q360_chart_core'),
    { ssr: false, loading: () => null }
);

/**
 * ChartTab is just a container that provides dimensions
 * ALL chart logic, tools, indicators, replay - handled by Q360ChartCore
 */
export default function ChartTab() {
    const { state, setSymbol, setTimeframe } = useTradingContext();
    const containerRef = useRef<HTMLDivElement>(null);
    const dimensions = useStableDimensions(containerRef);

    return (
        <div
            ref={containerRef}
            style={{
                width: '100%',
                height: '100%',
                background: '#03050a',
                overflow: 'hidden',
            }}
        >
            <Q360ChartCore
                symbol={state.symbol}
                timeframe={state.timeframe}
                mode="intraday"
                height={dimensions.height}
                width={dimensions.width}
                onSymbolChange={setSymbol}
                onTimeframeChange={setTimeframe}
            />
        </div>
    );
}
