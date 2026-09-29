"use client";

import React from 'react';

/**
 * NanoSparkline - High-density trend visualization
 * Zero padding, hairline width
 */
function Sparkline({ data, color }) {
    if (!data || data.length < 2) return <div className="w-[60px] h-[12px]" />;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const width = 60;
    const height = 12;
    
    const points = data.map((val, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((val - min) / range) * height;
        return `${x},${y}`;
    }).join(' ');

    return (
        <svg width={width} height={height} className="block">
            <polyline
                fill="none"
                stroke={color}
                strokeWidth="1"
                strokeLinejoin="round"
                points={points}
            />
        </svg>
    );
}

export default function EnhancedLeadersTable({ data, loading }) {
    if (loading) {
        return (
            <div className="flex flex-col w-full bg-terminal-black">
                {[...Array(15)].map((_, i) => (
                    <div key={i} className="h-[22px] border-b border-terminal-gray/10 animate-pulse bg-terminal-gray/5" />
                ))}
            </div>
        );
    }

    const { gainers = [], losers = [] } = data || {};
    // Interleave gainers and losers or show top k of each? Usually best to show top gainers then top losers in high density
    const allItems = [...gainers.slice(0, 12), ...losers.slice(0, 12)];

    return (
        <div className="flex flex-col h-full w-full font-mono text-[10px] leading-none select-none bg-terminal-black border-t border-terminal-gray/40">
            {/* CHARACTER ALIGNED HEADER: Ultra-Dense Grid (12 Columns) */}
            <div className="grid grid-cols-[70px_60px_50px_45px_45px_45px_45px_45px_45px_45px_45px_40px_1fr] gap-0 px-0 h-[22px] items-center bg-terminal-dark/80 text-terminal-dim font-bold uppercase tracking-tighter">
                <div className="pl-2 border-r border-b border-[#2a2e39] h-full flex items-center">SYMBOL</div>
                <div className="text-right pr-2 border-r border-b border-[#2a2e39] h-full flex items-center justify-end">LAST</div>
                <div className="text-center border-r border-b border-[#2a2e39] h-full flex items-center justify-center">CHG%</div>
                <div className="text-center border-r border-b border-[#2a2e39] h-full flex items-center justify-center">GAP%</div>
                <div className="text-center border-r border-b border-[#2a2e39] h-full flex items-center justify-center">5D%</div>
                <div className="text-center border-r border-b border-[#2a2e39] h-full flex items-center justify-center">1M%</div>
                <div className="text-right pr-1 border-r border-b border-[#2a2e39] h-full flex items-center justify-end">SM20</div>
                <div className="text-right pr-1 border-r border-b border-[#2a2e39] h-full flex items-center justify-end">R.S.</div>
                <div className="text-right pr-1 border-r border-b border-[#2a2e39] h-full flex items-center justify-end">RNG</div>
                <div className="text-right pr-1 border-r border-b border-[#2a2e39] h-full flex items-center justify-end">ATR%</div>
                <div className="text-right pr-1 border-r border-b border-[#2a2e39] h-full flex items-center justify-end">REL.V</div>
                <div className="text-right pr-1 border-r border-b border-[#2a2e39] h-full flex items-center justify-end">RV</div>
                <div className="text-center border-r border-b border-[#2a2e39] h-full flex items-center justify-center">TREND</div>
            </div>

            {/* ZERO-WASTE BODY: Marked Square Lines */}
            <div className="flex-1 overflow-auto overflow-x-hidden border-l border-[#2a2e39]">
                {allItems.map((item, idx) => {
                    const isPositive = (item.changePct || 0) >= 0;
                    const absoluteMove = Math.abs(item.changePct || 0);
                    const opacity = Math.min(0.4, 0.1 + (absoluteMove / 10)); 
                    const bgColor = isPositive 
                        ? `rgba(0, 255, 102, ${opacity})` 
                        : `rgba(255, 51, 51, ${opacity})`;
                    const textColor = isPositive ? '#00ff66' : '#ff3333';

                    return (
                        <div 
                            key={item.symbol} 
                            className="grid grid-cols-[70px_60px_50px_45px_45px_45px_45px_45px_45px_45px_45px_40px_1fr] gap-0 h-[20px] items-center hover:bg-terminal-yellow/10 transition-colors bg-terminal-black"
                        >
                            {/* Symbol */}
                            <div className="pl-0 border-r border-b border-[#2a2e39] h-full flex items-center gap-1 overflow-hidden whitespace-nowrap">
                                <div className={`w-0.5 h-full shrink-0 ${isPositive ? 'bg-terminal-green/50' : 'bg-terminal-red/50'}`} />
                                <span className="text-terminal-yellow font-bold truncate pl-1">
                                    {item.symbol.replace('.NS', '').replace('.BO', '')}
                                </span>
                            </div>
                            
                            {/* Price */}
                            <div className="text-right pr-2 tabular-nums text-terminal-text border-r border-b border-[#2a2e39] h-full flex items-center justify-end">
                                {(item.last || 0).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                            </div>

                            {/* Move % */}
                            <div 
                                className="h-full flex items-center justify-center font-bold tabular-nums border-r border-b border-[#2a2e39]"
                                style={{ backgroundColor: bgColor, color: textColor }}
                            >
                                {isPositive ? '+' : ''}{(item.changePct || 0).toFixed(1)}
                            </div>

                            {/* GAP% */}
                            <div className={`text-center tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-center ${(item.gapPct || 0) > 0.5 ? 'text-terminal-green' : (item.gapPct || 0) < -0.5 ? 'text-terminal-red' : 'text-terminal-dim'}`}>
                                {(item.gapPct || 0).toFixed(1)}
                            </div>

                            {/* 5D% */}
                            <div className={`text-center tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-center font-bold ${(item.chg5d || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                {(item.chg5d || 0) >= 0 ? '+' : ''}{(item.chg5d || 0).toFixed(1)}
                            </div>

                            {/* 1M% */}
                            <div className={`text-center tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-center font-bold ${(item.chg1m || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                {(item.chg1m || 0) >= 0 ? '+' : ''}{(item.chg1m || 0).toFixed(1)}
                            </div>

                            {/* SM20 */}
                            <div className={`text-right pr-1 tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-end ${(item.sma20Dist || 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                {(item.sma20Dist || 0).toFixed(1)}
                            </div>

                            {/* R.S. (Rel Strength) */}
                            <div className={`text-right pr-1 tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-end font-bold ${item.relStrength > 0 ? 'text-terminal-cyan' : 'text-terminal-dim'}`}>
                                {item.relStrength > 0 ? '+' : ''}{(item.relStrength || 0).toFixed(1)}
                            </div>

                            {/* RNG (Day Range) */}
                            <div className="text-right pr-1 tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-end text-terminal-dim">
                                {(item.dayRangePct || 0).toFixed(0)}%
                            </div>

                            {/* ATR% (Daily Volatility) */}
                            <div className="text-right pr-1 tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-end text-terminal-yellow">
                                {(item.atrPct || 0).toFixed(1)}
                            </div>

                            {/* REL.V */}
                            <div className={`text-right pr-1 tabular-nums border-r border-b border-[#2a2e39] h-full flex items-center justify-end font-bold ${(item.relVolume || 0) > 2 ? 'text-terminal-green' : (item.relVolume || 0) > 1.2 ? 'text-terminal-yellow' : 'text-terminal-dim'}`}>
                                {(item.relVolume || 0).toFixed(1)}
                            </div>

                            {/* RV (Realized Vol) */}
                            <div className="text-right pr-1 tabular-nums text-terminal-dim border-r border-b border-[#2a2e39] h-full flex items-center justify-end uppercase">
                                {(item.volatility || 0).toFixed(0)}
                            </div>

                            {/* TREND (Sparkline) */}
                            <div className="flex justify-center flex-col items-center h-full border-r border-b border-[#2a2e39]">
                                <Sparkline 
                                    data={item.sparkline} 
                                    color={isPositive ? '#00ff66' : '#ff3333'} 
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
