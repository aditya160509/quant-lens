'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { useTradingContext } from '@/context/TradingContext';
import { getSignalIntelligence } from '@/lib/signal-intelligence';

export default function SignalSummary() {
    const { state } = useTradingContext();
    const intelligence = useMemo(() => 
        getSignalIntelligence(state.symbol, state.exchange), 
    [state.symbol, state.exchange]);

    const isIndian = state.symbol?.endsWith('.NS') || state.symbol?.endsWith('.BO') || state.exchange === 'NSE';
    const currency = isIndian ? '₹' : '$';
    
    const score = intelligence.confidence; 
    const isHighConfidence = score > 80;

    return (
        <div className="flex items-center w-full px-4 h-full relative overflow-hidden">
            {/* Background Accent */}
            <div className="absolute inset-y-0 left-0 w-1 bg-violet-600" />
            
            {/* Confidence Score Badge */}
            <div className="flex items-center gap-3 pr-6 border-r border-white/10">
                <span className="text-[8px] font-mono text-gray-500 uppercase tracking-widest hidden xl:block">Intelligence</span>
                <div className="flex items-baseline gap-1.5">
                    <span className={`text-2xl font-mono font-black italic tracking-tighter ${isHighConfidence ? 'text-emerald-500' : 'text-violet-500'}`}>
                        {score}
                    </span>
                    <span className="text-[9px] font-mono text-gray-700">/100</span>
                </div>
            </div>

            {/* Timing Stats */}
            <div className="flex items-center gap-6 px-6 border-r border-white/10">
                <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)] animate-pulse" />
                    <span className="text-sm font-mono font-bold text-white tabular-nums tracking-tight">{intelligence.lineageAge}</span>
                    <span className="text-[7px] font-mono text-gray-600 uppercase tracking-widest">since_conf</span>
                </div>
            </div>

            {/* Risk Slider - Compressed */}
            <div className="flex items-center gap-4 px-6 flex-1 max-w-[300px]">
                <span className="text-[8px] font-mono text-gray-600 uppercase tracking-widest leading-none">Risk_Exposure</span>
                <div className="relative h-1 w-full bg-white/5 rounded-full overflow-hidden">
                    <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${intelligence.riskExposure}%` }}
                        className="h-full bg-gradient-to-r from-emerald-500 via-yellow-500 to-rose-500" 
                    />
                    <div className="absolute top-0 bottom-0 w-0.5 bg-white" style={{ left: `${intelligence.riskExposure}%` }} />
                </div>
            </div>

            {/* Session Economics */}
            <div className="flex items-center gap-6 ml-auto pl-6 border-l border-white/10">
                <div className="flex flex-col items-end">
                    <span className="text-[7px] font-mono text-gray-700 uppercase leading-none mb-1">Current_RR</span>
                    <span className="text-[10px] font-mono font-bold text-white">{intelligence.rr}</span>
                </div>
                <div className="flex flex-col items-end">
                    <span className="text-[7px] font-mono text-gray-700 uppercase leading-none mb-1">Expected_EV</span>
                    <span className="text-[10px] font-mono font-bold text-emerald-500">+{currency}{intelligence.expectedEv.toLocaleString()}</span>
                </div>
            </div>
        </div>
    );
}
