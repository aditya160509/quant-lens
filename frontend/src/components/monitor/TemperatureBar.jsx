"use client";

import React, { useState } from 'react';

/**
 * TemperatureBar - Market breadth visualization
 * Single thin bar showing advances/declines/unchanged proportions
 */
export default function TemperatureBar({ data, loading = false }) {
    const [hovered, setHovered] = useState(null);

    if (loading) {
        return (
            <div className="h-6 bg-terminal-gray animate-pulse rounded" />
        );
    }

    if (!data) {
        return (
            <div className="text-terminal-dim text-xs font-mono py-1">
                Breadth data unavailable
            </div>
        );
    }

    const { 
        advances = 0, 
        declines = 0, 
        unchanged = 0, 
        advPct = 0, 
        decPct = 0, 
        uncPct = 0, 
        universe 
    } = data;
    const total = advances + declines + unchanged;

    return (
        <div className="relative pt-0.5">
            {/* Bar */}
            <div 
                className="flex h-5 rounded-sm overflow-hidden cursor-pointer"
                onMouseEnter={() => setHovered(true)}
                onMouseLeave={() => setHovered(false)}
            >
                {/* Advances - Green */}
                <div 
                    className="bg-terminal-green/80 transition-all duration-300"
                    style={{ width: `${advPct}%` }}
                />
                {/* Unchanged - Gray */}
                <div 
                    className="bg-terminal-dim/50 transition-all duration-300"
                    style={{ width: `${uncPct}%` }}
                />
                {/* Declines - Red */}
                <div 
                    className="bg-terminal-red/80 transition-all duration-300"
                    style={{ width: `${decPct}%` }}
                />
            </div>

            {/* Labels below bar */}
            <div className="flex justify-between mt-1 text-[10px] font-mono">
                <span className="text-terminal-green">▲ {advances} ({advPct}%)</span>
                <span className="text-terminal-dim">— {unchanged} ({uncPct}%)</span>
                <span className="text-terminal-red">▼ {declines} ({decPct}%)</span>
            </div>

            {/* Hover tooltip */}
            {hovered && (
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 z-50
                    bg-terminal-black border border-terminal-gray rounded shadow-lg p-3 text-xs font-mono min-w-48">
                    <div className="text-terminal-yellow mb-2 font-bold">Market Breadth</div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        <span className="text-terminal-dim">Universe:</span>
                        <span className="text-terminal-text">{universe?.name || 'N/A'} ({universe?.count || total})</span>
                        <span className="text-terminal-green">Advances:</span>
                        <span className="text-terminal-green">{advances} ({advPct}%)</span>
                        <span className="text-terminal-dim">Unchanged:</span>
                        <span className="text-terminal-dim">{unchanged} ({uncPct}%)</span>
                        <span className="text-terminal-red">Declines:</span>
                        <span className="text-terminal-red">{declines} ({decPct}%)</span>
                    </div>
                    {data.quality?.confidenceLabel !== 'high' && (
                        <div className="mt-2 text-terminal-orange text-[10px]">
                            ⚠ {data.quality?.confidenceLabel} confidence
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
