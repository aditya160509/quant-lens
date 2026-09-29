"use client";

import React, { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ArrowRight, TrendingDown, TrendingUp } from 'lucide-react';

export const tradeReturn = (trade) => {
    const value = trade?.pnl_pct ?? trade?.pnl;
    return Number.isFinite(value) ? value : null;
};

const price = (value) => Number.isFinite(value) ? `$${value.toFixed(2)}` : 'Unavailable';
const date = (value) => {
    const parsed = value ? new Date(value) : null;
    return parsed && !Number.isNaN(parsed.getTime()) ? parsed.toLocaleDateString() : 'Unavailable';
};

export default function VirtualTradeLedger({ trades, onSelect, height = 360 }) {
    const scrollRef = useRef(null);
    // eslint-disable-next-line react-hooks/incompatible-library -- virtualization is an intentional imperative viewport boundary
    const virtualizer = useVirtualizer({ count: trades.length, getScrollElement: () => scrollRef.current, estimateSize: () => 66, overscan: 8 });

    if (!trades.length) return <div className="flex h-36 items-center justify-center rounded-xl border border-white/5 bg-[#0f0f14] text-xs font-mono text-[#64748b]">No closed trades in this run</div>;

    return (
        <div className="overflow-hidden rounded-xl border border-white/5 bg-[#0a0a0f]" role="table" aria-label="Virtualized execution records">
            <div role="row" className="grid grid-cols-6 gap-4 border-b border-white/5 px-4 py-2 text-[9px] font-mono uppercase tracking-wider text-[#64748b]">
                <div role="columnheader">Trade</div><div role="columnheader">Entry</div><div role="columnheader">Exit</div><div role="columnheader" className="text-center">Direction</div><div role="columnheader" className="text-center">Duration</div><div role="columnheader" className="text-right">Net return</div>
            </div>
            <div ref={scrollRef} style={{ height }} className="overflow-auto" tabIndex={0}>
                <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
                    {virtualizer.getVirtualItems().map((item) => {
                        const trade = trades[item.index];
                        const pnl = tradeReturn(trade);
                        const win = pnl !== null && pnl > 0;
                        return (
                            <button key={trade.id || item.index} type="button" role="row" aria-label={`Open trade ${trade.id || item.index + 1} on chart`} onClick={() => onSelect?.(trade, item.index)} className="absolute left-0 top-0 grid w-full grid-cols-6 items-center gap-4 border-b border-white/5 px-4 text-left font-mono hover:bg-amber-500/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-amber-500" style={{ height: item.size, transform: `translateY(${item.start}px)` }}>
                                <div role="cell" className="flex items-center gap-2 text-[11px] font-bold text-white"><span className={`flex h-7 w-7 items-center justify-center rounded ${trade.direction === 1 ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>{trade.direction === 1 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}</span>{trade.id || `#${item.index + 1}`}</div>
                                <div role="cell"><div className="text-[10px] text-white">{date(trade.entry_date)}</div><div className="text-[9px] text-[#64748b]">{price(trade.entry_price)}</div></div>
                                <div role="cell"><div className="text-[10px] text-white">{date(trade.exit_date)}</div><div className="text-[9px] text-[#64748b]">{price(trade.exit_price)}</div></div>
                                <div role="cell" className="text-center text-[9px] font-bold text-[#cbd5e1]">{trade.direction === 1 ? 'LONG' : 'SHORT'}</div>
                                <div role="cell" className="text-center text-[10px] text-[#64748b]">{Number.isFinite(trade.holding_period) ? `${trade.holding_period} bars` : 'Unavailable'}</div>
                                <div role="cell" className={`flex items-center justify-end gap-2 text-xs font-bold ${pnl === null ? 'text-[#64748b]' : win ? 'text-emerald-400' : 'text-red-400'}`}>{pnl === null ? 'Unavailable' : `${win ? '+' : ''}${(pnl * 100).toFixed(2)}%`}<ArrowRight size={12} /></div>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
