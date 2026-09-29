"use client";

import React from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
} from 'recharts';

/**
 * NormalizedReturnsChart - Clean Institutional Style (Recharts)
 * Matches the Cumulative Factor Returns aesthetic
 */

// Institutional Color Palette
const COLORS = [
    '#ffd60a', // Nifty - Gold
    '#f97316', // Sensex - Orange
    '#ffffff', // S&P 500 - White
    '#22d3ee', // Nasdaq - Cyan
    '#10b981', // FTSE - Emerald
    '#a855f7', // DAX - Purple
    '#ec4899', // Hang Seng - Pink
    '#14b8a6', // Gold - Teal
];

export default function NormalizedReturnsChart({ data, loading }) {
    if (loading) {
        return (
            <div className="h-full w-full min-h-[280px] flex items-center justify-center bg-terminal-black">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-6 h-6 border-2 border-yellow-500/30 border-t-yellow-500 rounded-full animate-spin" />
                    <span className="text-[10px] font-mono text-gray-600 uppercase tracking-widest">Loading...</span>
                </div>
            </div>
        );
    }

    if (!data?.series?.length) {
        return (
            <div className="h-full w-full min-h-[280px] flex items-center justify-center bg-terminal-black">
                <span className="text-gray-700 font-mono text-[10px] uppercase tracking-widest">No Data</span>
            </div>
        );
    }

    // Transform data for Recharts format
    const chartData = [];
    const maxLen = Math.max(...data.series.map(s => s.data.length));
    
    for (let i = 0; i < maxLen; i++) {
        const point = { idx: i };
        
        // Get date from first series
        if (data.series[0]?.dates?.[i]) {
            const d = new Date(data.series[0].dates[i]);
            point.date = d;
            point.label = d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        }
        
        // Add each series value
        data.series.forEach((s, sIdx) => {
            point[`series${sIdx}`] = s.data[i] ?? null;
        });
        
        chartData.push(point);
    }

    // Custom Tooltip
    const CustomTooltip = ({ active, payload, label }) => {
        if (!active || !payload?.length) return null;
        
        const point = payload[0]?.payload;
        const dateStr = point?.date 
            ? point.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
            : '';
        
        return (
            <div className="bg-black/95 border border-white/10 rounded px-3 py-2 shadow-xl">
                <div className="text-[9px] font-mono text-gray-500 mb-1 pb-1 border-b border-white/10">
                    {dateStr}
                </div>
                {payload.map((entry, i) => {
                    const seriesIdx = parseInt(entry.dataKey.replace('series', ''));
                    const name = data.series[seriesIdx]?.name || `Series ${seriesIdx + 1}`;
                    const change = (entry.value - 100).toFixed(2);
                    return (
                        <div key={i} className="flex items-center justify-between gap-4 py-0.5">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-0.5 rounded" style={{ backgroundColor: entry.color }} />
                                <span className="text-[9px] font-mono text-white/70">{name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-mono font-bold text-white">
                                    {entry.value?.toFixed(1)}
                                </span>
                                <span className={`text-[9px] font-mono ${parseFloat(change) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {parseFloat(change) >= 0 ? '+' : ''}{change}%
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    };

    // Format X-axis ticks
    const formatXAxis = (value, index) => {
        const point = chartData[value];
        if (!point?.date) return '';
        return point.date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    };

    return (
        <div className="flex flex-col h-full w-full bg-terminal-black">
            {/* Chart Container */}
            <div className="flex-1 min-h-0 px-2 py-2">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                        {/* Grid */}
                        <defs>
                            <linearGradient id="gridGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="rgba(255,255,255,0.02)" />
                                <stop offset="100%" stopColor="rgba(255,255,255,0.02)" />
                            </linearGradient>
                        </defs>
                        
                        {/* Reference line at 100 */}
                        <ReferenceLine 
                            y={100} 
                            stroke="rgba(255,255,255,0.1)" 
                            strokeDasharray="4 4"
                            label={{ value: '0%', position: 'left', fill: '#555', fontSize: 9 }}
                        />
                        
                        <XAxis 
                            dataKey="idx"
                            tickFormatter={formatXAxis}
                            tick={{ fill: '#555', fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}
                            axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
                            tickLine={false}
                            interval={Math.floor(chartData.length / 5)}
                        />
                        
                        <YAxis 
                            domain={['auto', 'auto']}
                            tick={{ fill: '#555', fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}
                            axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
                            tickLine={false}
                            tickFormatter={(v) => (v - 100).toFixed(0)}
                            width={35}
                        />
                        
                        <Tooltip 
                            content={<CustomTooltip />}
                            cursor={{ stroke: 'rgba(255,214,10,0.3)', strokeDasharray: '4 4' }}
                        />
                        
                        {/* Lines */}
                        {data.series.map((s, i) => (
                            <Line
                                key={i}
                                type="monotone"
                                dataKey={`series${i}`}
                                stroke={COLORS[i % COLORS.length]}
                                strokeWidth={1.5}
                                dot={false}
                                activeDot={{ r: 4, fill: COLORS[i % COLORS.length] }}
                                connectNulls
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>
            
            {/* Legend */}
            <div className="px-4 py-2 border-t border-white/5">
                <div className="flex flex-wrap gap-x-4 gap-y-1 justify-center">
                    {data.series.map((s, i) => (
                        <div key={i} className="flex items-center gap-1.5">
                            <div 
                                className="w-4 h-0.5 rounded-full" 
                                style={{ backgroundColor: COLORS[i % COLORS.length] }}
                            />
                            <span className="text-[10px] font-mono text-white/60">{s.name}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
