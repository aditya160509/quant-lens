"use client";

import React, { useMemo } from 'react';
import { PlotlyChart } from '@/components/ui/plotly-chart';

/**
 * BreadthCharts - Three market breadth/regime graphs
 * 1. Advance/Decline Line (top, full width)
 * 2. Rolling Volatility Regime (bottom left)
 * 3. Advance/Decline Ratio Thrust (bottom right)
 */

// Shared chart layout config
const sharedLayout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'JetBrains Mono, monospace', size: 9, color: 'var(--terminal-dim)' },
    margin: { t: 2, r: 10, b: 5, l: 30 },
    xaxis: {
        showgrid: false,
        showline: false,
        tickfont: { size: 8, color: 'var(--terminal-dim)' },
        tickformat: '%b %d',
    },
    yaxis: {
        showgrid: true,
        gridcolor: 'var(--terminal-gray)',
        showline: false,
        tickfont: { size: 8, color: 'var(--terminal-dim)' },
        zeroline: false,
    },
    hovermode: 'x unified',
    showlegend: false,
};

/**
 * Advance/Decline Line Chart
 * ADL = cumulative sum of (advances - declines)
 */
export function AdvanceDeclineLineChart({ data, loading }) {
    const traces = useMemo(() => {
        if (!data?.dates || !data?.adl) return [];
        return [{
            x: data.dates,
            y: data.adl,
            type: 'scattergl',
            mode: 'lines',
            name: 'A/D Line',
            line: { 
                color: 'var(--terminal-yellow)', 
                width: 1.5,
            },
            hovertemplate: 'A/D Line: %{y:,.0f}<extra></extra>',
        }];
    }, [data]);

    if (loading) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-terminal-dark/50 rounded">
                <span className="text-terminal-dim text-xs font-mono animate-pulse">Loading A/D Line...</span>
            </div>
        );
    }

    if (!data?.dates?.length) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-terminal-dark/50 rounded">
                <span className="text-terminal-dim text-xs font-mono">No A/D data</span>
            </div>
        );
    }

    return (
        <div className="h-full w-full relative">
            <div className="absolute top-1 left-2 text-[10px] font-mono text-terminal-dim z-10">
                ADVANCE/DECLINE LINE
            </div>
            <PlotlyChart
                data={traces}
                layout={{
                    ...sharedLayout,
                    margin: { t: 20, r: 10, b: 25, l: 45 },
                }}
                config={{ displayModeBar: false, responsive: true }}
            />
        </div>
    );
}

/**
 * Rolling Volatility Regime Chart
 * Shows NIFTY and BANKNIFTY rolling 20-day annualized volatility
 */
export function VolatilityRegimeChart({ data, loading }) {
    const traces = useMemo(() => {
        if (!data?.dates) return [];
        
        const result = [];
        
        if (data.niftyVol) {
            result.push({
                x: data.dates,
                y: data.niftyVol,
                type: 'scattergl',
                mode: 'lines',
                name: 'NIFTY',
                line: { color: 'var(--terminal-green)', width: 1.5 },
                hovertemplate: 'NIFTY: %{y:.1f}%<extra></extra>',
            });
        }
        
        if (data.bankniftyVol) {
            result.push({
                x: data.dates,
                y: data.bankniftyVol,
                type: 'scattergl',
                mode: 'lines',
                name: 'BANKNIFTY',
                line: { color: 'var(--terminal-yellow)', width: 1.5 },
                hovertemplate: 'BANKNIFTY: %{y:.1f}%<extra></extra>',
            });
        }
        
        return result;
    }, [data]);

    if (loading) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-terminal-dark/50 rounded">
                <span className="text-terminal-dim text-xs font-mono animate-pulse">Loading Volatility...</span>
            </div>
        );
    }

    if (!data?.dates?.length) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-terminal-dark/50 rounded">
                <span className="text-terminal-dim text-xs font-mono">No volatility data</span>
            </div>
        );
    }

    return (
        <div className="h-full w-full relative">
            <div className="absolute top-1 left-2 text-[10px] font-mono text-terminal-dim z-10 flex gap-4">
                <span>VOLATILITY REGIME</span>
                <span className="text-terminal-green">NIFTY</span>
                <span className="text-terminal-yellow">BANKNIFTY</span>
            </div>
            <PlotlyChart
                data={traces}
                layout={{
                    ...sharedLayout,
                    margin: { t: 20, r: 10, b: 25, l: 35 },
                    yaxis: {
                        ...sharedLayout.yaxis,
                        ticksuffix: '%',
                    },
                }}
                config={{ displayModeBar: false, responsive: true }}
            />
        </div>
    );
}

/**
 * Advance/Decline Ratio Thrust Chart
 * Shows EMA(10) of advance ratio
 */
export function ADRatioThrustChart({ data, loading }) {
    const traces = useMemo(() => {
        if (!data?.dates || !data?.thrust) return [];
        
        return [{
            x: data.dates,
            y: data.thrust,
            type: 'scattergl',
            mode: 'lines',
            name: 'A/D Thrust',
            line: { color: 'var(--terminal-cyan)', width: 1.5 },
            hovertemplate: 'Thrust: %{y:.1%}<extra></extra>',
        }];
    }, [data]);

    // Reference levels
    const shapes = useMemo(() => {
        if (!data?.dates?.length) return [];
        return [
            {
                type: 'line',
                x0: data.dates[0],
                x1: data.dates[data.dates.length - 1],
                y0: 0.6,
                y1: 0.6,
                line: { color: 'var(--terminal-green)', width: 1, dash: 'dot', opacity: 0.3 },
            },
            {
                type: 'line',
                x0: data.dates[0],
                x1: data.dates[data.dates.length - 1],
                y0: 0.4,
                y1: 0.4,
                line: { color: 'var(--terminal-red)', width: 1, dash: 'dot', opacity: 0.3 },
            },
        ];
    }, [data]);

    if (loading) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-terminal-dark/50 rounded">
                <span className="text-terminal-dim text-xs font-mono animate-pulse">Loading Thrust...</span>
            </div>
        );
    }

    if (!data?.dates?.length) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-terminal-dark/50 rounded">
                <span className="text-terminal-dim text-xs font-mono">No thrust data</span>
            </div>
        );
    }

    return (
        <div className="h-full w-full relative">
            <div className="absolute top-1 left-2 text-[10px] font-mono text-terminal-dim z-10">
                A/D RATIO THRUST (EMA10)
            </div>
            <PlotlyChart
                data={traces}
                layout={{
                    ...sharedLayout,
                    margin: { t: 20, r: 10, b: 25, l: 35 },
                    shapes,
                    yaxis: {
                        ...sharedLayout.yaxis,
                        tickformat: '.0%',
                        range: [0, 1],
                    },
                }}
                config={{ displayModeBar: false, responsive: true }}
            />
        </div>
    );
}

/**
 * Combined BreadthCharts panel with 3-chart layout
 */
export default function BreadthCharts({ adlData, volData, thrustData, loading }) {
    return (
        <div className="h-full w-full flex flex-col gap-px">
            {/* Top: A/D Line - 45% height */}
            <div className="h-[45%] w-full">
                <AdvanceDeclineLineChart data={adlData} loading={loading} />
            </div>
            
            {/* Bottom row: 55% height, split 50/50 */}
            <div className="h-[55%] w-full flex gap-px">
                {/* Left: Volatility Regime */}
                <div className="w-1/2 h-full">
                    <VolatilityRegimeChart data={volData} loading={loading} />
                </div>
                
                {/* Right: A/D Ratio Thrust */}
                <div className="w-1/2 h-full">
                    <ADRatioThrustChart data={thrustData} loading={loading} />
                </div>
            </div>
        </div>
    );
}
