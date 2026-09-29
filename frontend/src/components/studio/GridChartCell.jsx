"use client";
import React, { useState } from 'react';
import { Maximize2, Minimize2, Info } from 'lucide-react';
import Q360Canvas from './Q360Canvas';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';

const GridChartCell = ({ 
    ticker, 
    data, 
    isLoading,
    error,
    onRetry,
    index, 
    total,
    playIndex,
    isPlaying,
    activeIndicators,
    showVolume,
    benchmarkData,
    showBenchmark,
    selectedPatterns,
    overlayMatches,
    setHoverSnapshot,
    syncedOffset,
    syncedScale,
    syncedHover,
    onOffsetChange,
    onScaleChange,
    onHoverChange,
    onTickerChange,
    versionLabel,
    isMaximized,
    onMaximize,
    onRestore
}) => {
    // Determine if any indicators are blocked (oscillators with placement: 'pane')
    const hasBlockedIndicators = activeIndicators.some(ind => ind.placement === 'pane');
    const [showTickerPicker, setShowTickerPicker] = useState(false);

    return (
        <div className={`flex flex-col border border-white/5 bg-[#020204] overflow-hidden transition-all duration-300 ${isMaximized ? 'fixed inset-0 z-[100]' : 'relative h-full w-full'}`}>
            {/* Cell Header */}
            <div className="h-7 px-3 flex items-center justify-between bg-[#0a0a0f] border-b border-white/5 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowTickerPicker(prev => !prev)}
                        className="text-[10px] font-mono font-bold text-amber-500 uppercase tracking-wider hover:text-amber-300"
                        title="Change panel ticker"
                    >
                        {ticker}
                    </button>
                    {versionLabel && (
                        <span className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold ${versionLabel === 'A' ? 'bg-amber-500/20 text-amber-400' : 'bg-blue-500/20 text-blue-300'}`}>
                            {versionLabel}
                        </span>
                    )}
                    <div className="h-3 w-px bg-white/10 mx-1" />
                    <span className="text-[8px] font-mono text-[#64748b] uppercase">Chart {index + 1} of {total}</span>
                    {hasBlockedIndicators && (
                        <div className="group relative flex items-center ml-2">
                            <Info size={10} className="text-amber-500/50" />
                            <div className="absolute left-full ml-2 px-2 py-1 bg-black border border-amber-500/30 rounded text-[8px] text-amber-500 font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-50">
                                OSCILLATORS DISABLED IN GRID MODE
                            </div>
                        </div>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {isMaximized ? (
                        <button onClick={onRestore} className="p-1 hover:bg-white/10 rounded-md text-[#64748b] hover:text-white transition-colors" title="Restore">
                            <Minimize2 size={12} />
                        </button>
                    ) : (
                        <button onClick={onMaximize} className="p-1 hover:bg-white/10 rounded-md text-[#64748b] hover:text-white transition-colors" title="Maximize">
                            <Maximize2 size={12} />
                        </button>
                    )}
                </div>
            </div>

            {showTickerPicker && (
                <div className="absolute top-8 left-2 right-2 z-[220] rounded-lg border border-white/10 bg-[#090b12] p-2 shadow-2xl">
                    <TradingViewSearch
                        placeholder={`Set ticker for panel ${index + 1}`}
                        autoFocus
                        dropdownZIndex={230}
                        onSelect={(symbol) => {
                            onTickerChange?.(index, symbol);
                            setShowTickerPicker(false);
                        }}
                    />
                </div>
            )}

            {/* Canvas Area */}
            <div className="flex-1 relative min-h-0 min-w-0">
                {data && data.candles && data.candles.length > 0 ? (
                    <Q360Canvas
                        candles={data.candles}
                        signals={data.signals}
                        playIndex={playIndex}
                        isPlaying={isPlaying}
                        activeIndicators={activeIndicators.filter(ind => ind.placement !== 'pane')}
                        showVolume={showVolume}
                        volumeProfile={data.volumeProfile}
                        benchmarkData={benchmarkData}
                        showBenchmark={showBenchmark}
                        selectedPatterns={selectedPatterns}
                        customOverlayMatches={overlayMatches}
                        syncedOffset={syncedOffset}
                        syncedScale={syncedScale}
                        syncedHover={syncedHover}
                        onOffsetChange={onOffsetChange}
                        onScaleChange={onScaleChange}
                        onHoverChange={(hover) => {
                            setHoverSnapshot(hover);
                            if (onHoverChange) onHoverChange(hover);
                        }}
                    />
                ) : (
                    <div className="absolute inset-0 flex items-center justify-center bg-[#050508]">
                        {error ? (
                            <div role="alert" className="max-w-xs p-5 text-center">
                                <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-red-400">Grid data unavailable</div>
                                <p className="mt-2 text-[9px] font-mono leading-relaxed text-[#64748b]">{error}</p>
                                <button onClick={onRetry} className="mt-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-[9px] font-mono font-bold uppercase text-red-300 hover:bg-red-500/20">Retry</button>
                            </div>
                        ) : (
                            <div className={`text-[10px] font-mono text-[#64748b] uppercase tracking-widest ${isLoading ? 'animate-pulse' : ''}`}>
                                {isLoading ? 'Loading observed market data…' : 'No grid data loaded'}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default GridChartCell;
