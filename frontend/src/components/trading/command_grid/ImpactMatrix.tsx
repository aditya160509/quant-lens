'use client';

import React, { useMemo } from 'react';
import { useTradingContext } from '@/context/TradingContext';
import { getSignalIntelligence } from '@/lib/signal-intelligence';
import { useTacticalData } from './tactical_charts/useTacticalData';
import PeerPerformanceChart from './tactical_charts/PeerPerformanceChart';
import VolatilityRegimeChart from './tactical_charts/VolatilityRegimeChart';

export default function ImpactMatrix() {
    const { state } = useTradingContext();
    const { data, intelligence: tacticalIntelligence, loading } = useTacticalData(state.symbol, state.timeframe);
    
    const intelligence = useMemo(() => 
        getSignalIntelligence(state.symbol, state.exchange), 
    [state.symbol, state.exchange]);

    const peers = intelligence.peers;

    return (
        <div className="flex flex-col h-full bg-[#02040a] overflow-y-auto scrollbar-hide">
            {/* Pane 1: Peer List */}
            <div className="flex-[2] min-h-[100px] border-b border-white/5 px-3 pt-2 bg-black/20 overflow-hidden">
                <div className="flex text-[7px] font-mono text-gray-700 px-1 uppercase mb-1 tracking-widest">
                    <span className="w-20">PEER</span>
                    <span className="w-12 text-center">BETA</span>
                    <span className="flex-1 text-right">SESSION</span>
                </div>
                <div className="flex flex-col gap-0.5">
                    {peers.map((peer, idx) => (
                        <div key={idx} className="flex items-center justify-between px-1.5 py-0.5 rounded-sm hover:bg-white/5 transition-colors">
                            <span className="text-[10px] font-mono font-bold text-gray-300 w-20 truncate">{peer.symbol}</span>
                            <span className="text-[10px] font-mono text-gray-500 w-12 text-center">{peer.beta.toFixed(2)}</span>
                            <span className={`text-[10px] font-mono font-bold text-right flex-1 ${peer.spillover.startsWith('+') ? 'text-emerald-500' : 'text-rose-500'}`}>
                                {peer.spillover}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Pane 2: Dispersion Analysis */}
            <div className="flex-[3] min-h-[160px] relative border-b border-white/5 bg-black/40">
                <PeerPerformanceChart 
                    data={data} 
                    loading={loading} 
                    height={160} 
                    peers={peers} 
                />
            </div>

            {/* Pane 3: Volatility Momentum */}
            <div className="flex-[6] min-h-[280px] relative bg-black/20">
                <VolatilityRegimeChart 
                    data={data} 
                    intelligence={tacticalIntelligence} 
                    loading={loading} 
                    height={280} 
                />
            </div>

            {/* Terminal Status Footer */}
            <div className="h-5 border-t border-white/5 flex items-center px-3 bg-black/90 sticky bottom-0 z-30">
                <span className="text-[7px] font-mono text-gray-800 uppercase tracking-widest">Contagion Engine: Trace Active // Beta Mapped</span>
            </div>
        </div>
    );
}
