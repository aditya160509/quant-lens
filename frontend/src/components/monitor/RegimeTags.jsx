"use client";

import React, { useState } from 'react';

/**
 * RegimeTags - Volatility, Trend, Liquidity regime indicators
 * Shows score and label with hover for drivers/evidence
 */
export default function RegimeTags({ data, loading = false, compact = false }) {
    const [hoveredTag, setHoveredTag] = useState(null);

    if (loading) {
        return (
            <div className="flex flex-col gap-1">
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-6 w-24 bg-terminal-gray animate-pulse rounded" />
                ))}
            </div>
        );
    }

    if (!data) {
        return (
            <div className="text-terminal-dim text-xs font-mono">
                Regime unavailable
            </div>
        );
    }

    const { volatility, trend, liquidity, drivers = [] } = data;

    const getLabelColor = (label, type) => {
        if (type === 'volatility') {
            if (label === 'low') return 'text-terminal-green bg-terminal-green/10 border-terminal-green/30';
            if (label === 'high') return 'text-terminal-red bg-terminal-red/10 border-terminal-red/30';
            return 'text-terminal-dim bg-terminal-gray/30 border-terminal-gray/50';
        }
        if (type === 'trend') {
            if (label === 'uptrend') return 'text-terminal-green bg-terminal-green/10 border-terminal-green/30';
            if (label === 'downtrend') return 'text-terminal-red bg-terminal-red/10 border-terminal-red/30';
            return 'text-terminal-orange bg-terminal-orange/10 border-terminal-orange/30';
        }
        if (type === 'liquidity') {
            if (label === 'high') return 'text-terminal-green bg-terminal-green/10 border-terminal-green/30';
            if (label === 'thin') return 'text-terminal-red bg-terminal-red/10 border-terminal-red/30';
            return 'text-terminal-dim bg-terminal-gray/30 border-terminal-gray/50';
        }
        return 'text-terminal-dim bg-terminal-gray/30 border-terminal-gray/50';
    };

    const tags = [
        { key: 'volatility', label: 'VOL', value: volatility?.label, score: volatility?.score },
        { key: 'trend', label: 'TREND', value: trend?.label, score: trend?.score },
        { key: 'liquidity', label: 'LIQ', value: liquidity?.label, score: liquidity?.score },
    ];

    return (
        <div className={`flex ${compact ? 'flex-row gap-2' : 'flex-col gap-1'}`}>
            {tags.map((tag) => (
                <div key={tag.key} className="relative">
                    <div
                        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border font-mono text-[10px] cursor-help
                            ${getLabelColor(tag.value, tag.key)}`}
                        onMouseEnter={() => setHoveredTag(tag.key)}
                        onMouseLeave={() => setHoveredTag(null)}
                    >
                        <span className="font-bold">{tag.label}</span>
                        <span className="uppercase">{tag.value || 'N/A'}</span>
                        {tag.score !== undefined && (
                            <span className="text-terminal-dim">({tag.score})</span>
                        )}
                    </div>

                    {/* Hover tooltip with drivers */}
                    {hoveredTag === tag.key && drivers.length > 0 && (
                        <div className="absolute top-full right-0 mt-1 z-50
                            bg-terminal-black border border-terminal-gray rounded shadow-lg p-2 text-[10px] font-mono min-w-48">
                            <div className="text-terminal-yellow mb-1 font-bold">{tag.label} Drivers</div>
                            {drivers.filter(d => d.name.toLowerCase().includes(tag.key.slice(0, 3))).map((d, i) => (
                                <div key={i} className="grid grid-cols-2 gap-2 py-0.5">
                                    <span className="text-terminal-dim">{d.name}:</span>
                                    <span className="text-terminal-text">{d.value} {d.unit}</span>
                                </div>
                            ))}
                            {drivers.filter(d => d.name.toLowerCase().includes(tag.key.slice(0, 3))).length === 0 && (
                                <div className="text-terminal-dim">No specific drivers</div>
                            )}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}
