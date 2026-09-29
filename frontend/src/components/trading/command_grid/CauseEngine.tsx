'use client';

import React from 'react';
import { useTradingContext } from '@/context/TradingContext';
import { useTacticalData } from './tactical_charts/useTacticalData';
import TacticalCandleChart from './tactical_charts/TacticalCandleChart';
import VolumeProfileChart from './tactical_charts/VolumeProfileChart';

export default function CauseEngine() {
    const { state } = useTradingContext();
    const { data, intelligence, loading } = useTacticalData(state.symbol, state.timeframe);

    return (
        <div className="flex flex-col h-full bg-[#02040a] overflow-y-auto scrollbar-hide">
            {/* Pane 1: Chart */}
            <div className="flex-[7] min-h-[260px] relative border-b border-white/5 bg-black/40">
                <TacticalCandleChart data={data} intelligence={intelligence} loading={loading} height={260} />
            </div>

            {/* Pane 2: Liquidity Flow */}
            <div className="flex-[5] min-h-[220px] relative bg-black/20">
                <VolumeProfileChart data={data} intelligence={intelligence} loading={loading} height={220} />
            </div>

            {/* Status Footer */}
            <div className="h-4 border-t border-white/5 flex items-center px-3 bg-black/90 sticky bottom-0 z-30">
                <span className="text-[7px] font-mono text-gray-800 uppercase tracking-widest">
                    Telemetry: Synchronized
                </span>
            </div>
        </div>
    );
}
