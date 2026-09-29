'use client';

import React, { useState } from 'react';
import { useTradingContext } from '@/context/TradingContext';
import { usePortfolioStore } from '@/lib/portfolioStore';
import { Zap, Shield, ChevronRight } from 'lucide-react';

export default function QuickTradePanel() {
    const { state } = useTradingContext();
    const { snapshot, risk } = usePortfolioStore();
    const [qty, setQty] = useState('100');
    
    const cash = snapshot?.cash || 0;
    const currentPos = snapshot?.positions?.find(p => p.ticker === state.symbol);
    
    const handleQuickOrder = (side: 'BUY' | 'SELL') => {
        // Just a placeholder for now, would link to execution engine
        alert(`Quick ${side}: ${qty} ${state.symbol}`);
    };

    return (
        <div className="flex flex-col h-full bg-[#05070a] border-l border-white/5 font-mono">
            {/* Context Header */}
            <div className="p-3 border-b border-white/5 bg-white/[0.02]">
                <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Execution Dock</span>
                    <Zap size={10} className="text-amber-500" />
                </div>
                <div className="text-xs font-bold text-white">{state.symbol} :: {state.lastPrice.toFixed(2)}</div>
            </div>

            {/* Quick Stats */}
            <div className="p-3 space-y-2 border-b border-white/5 text-[9px]">
                <div className="flex justify-between">
                    <span className="text-gray-500">Available Cash</span>
                    <span className="text-white">${cash.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-500">Current Pos</span>
                    <span className={currentPos ? 'text-cyan-400' : 'text-gray-600'}>
                        {currentPos ? `${currentPos.qty} units` : 'NONE'}
                    </span>
                </div>
            </div>

            {/* Order Form */}
            <div className="p-3 flex-1 space-y-4">
                <div className="space-y-1.5">
                    <label className="text-[8px] text-gray-500 uppercase font-black">Quantity Selection</label>
                    <div className="relative">
                        <input 
                            type="text" 
                            value={qty}
                            onChange={(e) => setQty(e.target.value)}
                            className="w-full bg-black border border-white/10 rounded px-2 py-1.5 text-xs text-white outline-none focus:border-amber-500/50"
                        />
                        <div className="absolute right-2 top-1.5 text-[8px] text-gray-600 font-bold">UNITS</div>
                    </div>
                    <div className="grid grid-cols-4 gap-1">
                        {['10', '50', '100', 'MAX'].map(v => (
                            <button 
                                key={v}
                                onClick={() => v === 'MAX' ? setQty(Math.floor(cash / state.lastPrice).toString()) : setQty(v)}
                                className="py-1 bg-white/5 rounded text-[8px] hover:bg-white/10 transition-colors"
                            >
                                {v}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                    <button 
                        onClick={() => handleQuickOrder('BUY')}
                        className="py-3 bg-emerald-500/20 text-emerald-500 border border-emerald-500/30 rounded flex flex-col items-center justify-center group hover:bg-emerald-500/30 transition-all"
                    >
                        <span className="text-[10px] font-black">BUY</span>
                        <span className="text-[8px] opacity-60">LMT @ {state.lastPrice.toFixed(2)}</span>
                    </button>
                    <button 
                        onClick={() => handleQuickOrder('SELL')}
                        className="py-3 bg-rose-500/20 text-rose-500 border border-rose-500/30 rounded flex flex-col items-center justify-center group hover:bg-rose-500/30 transition-all"
                    >
                        <span className="text-[10px] font-black">SELL</span>
                        <span className="text-[8px] opacity-60">LMT @ {state.lastPrice.toFixed(2)}</span>
                    </button>
                </div>

                {/* Risk Guard One-Liner */}
                <div className="p-2 rounded bg-amber-500/5 border border-amber-500/10 flex items-center gap-2">
                    <Shield size={12} className="text-amber-500/50" />
                    <div className="text-[7px] text-amber-500/80 leading-tight">
                        POSITION WILL OFFSET PORTFOLIO BETA BY {(parseFloat(qty) * 0.002).toFixed(3)}
                    </div>
                </div>
            </div>

            {/* Footer */}
            <button className="w-full p-2 bg-white/5 hover:bg-white/10 text-[8px] text-gray-500 flex items-center justify-center gap-1 transition-all border-t border-white/5">
                FULL ORDER TICKET <ChevronRight size={10} />
            </button>
        </div>
    );
}
