
import React, { useState } from 'react';
import { 
    Globe, Calendar, Zap, LayoutGrid, 
    ChevronDown, X, Database, Clock,
    Filter, RefreshCw
} from 'lucide-react';
import UniverseModal from './UniverseModal';

export default function SovereignCommandBar({ 
    tickers, 
    onTickersChange, 
    startDate, 
    onStartDateChange,
    endDate,
    onEndDateChange,
    onExecute,
    loading,
    title = "Sovereign Command"
}) {
    const [isUniverseOpen, setIsUniverseOpen] = useState(false);

    return (
        <div className="flex flex-col gap-2 bg-[#050505] border border-white/10 rounded-xl p-3 shadow-2xl relative overflow-hidden group">
            {/* Background Decorative Element */}
            <div className="absolute right-[-20px] top-[-20px] opacity-[0.02] pointer-events-none group-hover:scale-110 transition-transform duration-1000">
                <Database size={150} />
            </div>

            <div className="flex flex-wrap items-center gap-4 relative z-10">
                {/* Title & Universe Trigger */}
                <div className="flex items-center gap-3 pr-4 border-r border-white/10">
                    <div className="p-2 bg-terminal-yellow/10 rounded-lg">
                        <LayoutGrid size={18} className="text-terminal-yellow" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] font-black text-terminal-dim uppercase tracking-widest">{title}</span>
                        <button 
                            onClick={() => setIsUniverseOpen(true)}
                            className="flex items-center gap-2 text-sm font-black text-white hover:text-terminal-yellow transition-colors"
                        >
                            SELECT UNIVERSE <ChevronDown size={14} />
                        </button>
                    </div>
                </div>

                {/* Timeframe Presets */}
                <div className="flex items-center gap-2 pr-4 border-r border-white/10">
                    <span className="text-[9px] font-black text-terminal-dim uppercase flex items-center gap-1 mr-1">
                        <Clock size={10} /> Timeframe
                    </span>
                    <div className="flex flex-wrap gap-1 max-w-[300px]">
                        {['1M', '2M', '3M', '6M', '1Y', '2Y', '3Y', '4Y', 'MAX'].map((p) => {
                            const isSelected = p === startDate; // Simplified check for now
                            return (
                                <button
                                    key={p}
                                    onClick={() => onStartDateChange(p)}
                                    className={`px-2 py-1 rounded text-[10px] font-bold transition-all ${
                                        isSelected 
                                        ? 'bg-terminal-yellow text-black' 
                                        : 'bg-[#0d0d0d] text-terminal-dim hover:text-terminal-yellow border border-white/5'
                                    }`}
                                >
                                    {p}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Ticker Count & Metadata */}
                <div className="flex-1 flex flex-col gap-1">
                    <span className="text-[9px] font-black text-terminal-dim uppercase">Vector Count</span>
                    <div className="flex items-center gap-2">
                        <div className="px-2 py-0.5 bg-terminal-yellow/20 border border-terminal-yellow/40 rounded text-[10px] font-bold text-terminal-yellow">
                            {tickers.length} ASSETS READY
                        </div>
                        <div className="px-2 py-0.5 bg-terminal-blue/20 border border-terminal-blue/40 rounded text-[10px] font-bold text-terminal-blue">
                            PURE PARQUET
                        </div>
                    </div>
                </div>

                {/* Execute Button */}
                <button 
                    onClick={onExecute}
                    disabled={loading || tickers.length === 0}
                    className={`
                        flex items-center gap-2 px-8 py-3 bg-terminal-yellow font-black text-xs text-black uppercase tracking-[0.2em] rounded-lg transition-all shadow-lg
                        ${loading || tickers.length === 0 ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 hover:bg-yellow-400 active:scale-95'}
                    `}
                >
                    {loading ? <RefreshCw className="animate-spin" size={16} /> : <Zap size={16} fill="currentColor" />}
                    {loading ? "Computing..." : "Execute Vector Analysis"}
                </button>
            </div>

            {/* Active Tickers Ribbon */}
            <div className="mt-2 flex items-center gap-2 overflow-x-auto no-scrollbar scroll-smooth pb-1">
                {tickers.length === 0 ? (
                    <span className="text-[10px] text-terminal-dim italic px-2">No vectors loaded. Use Universe Selector or Batch Injector.</span>
                ) : (
                    tickers.map(ticker => (
                        <div 
                            key={ticker}
                            className="shrink-0 flex items-center gap-2 px-2 py-1 bg-white/5 border border-white/5 rounded text-[10px] font-bold text-white hover:border-terminal-yellow/30 transition-all group"
                        >
                            {ticker}
                            <button 
                                onClick={() => onTickersChange(tickers.filter(t => t !== ticker))}
                                className="text-terminal-dim hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                            >
                                <X size={12} />
                            </button>
                        </div>
                    ))
                )}
            </div>

            <UniverseModal 
                isOpen={isUniverseOpen}
                onClose={() => setIsUniverseOpen(false)}
                onSelect={onTickersChange}
                currentTickers={tickers}
            />
        </div>
    );
}

