"use client";
import React from 'react';
import { Play, Pause, Link2, Unlink, Terminal, LayoutGrid } from 'lucide-react';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioLayoutStore } from '@/stores/studio/layoutStore';
import { useStudioPreferenceStore } from '@/stores/studio/preferenceStore';
import { useStudioSelectionStore } from '@/stores/studio/selectionStore';
import { useStudioEditorStore } from '@/stores/studio/editorStore';

export default function StudioContextToolbar() {
    const ticker = useStudioWorkspaceStore((s) => s.ticker);
    const setTicker = useStudioWorkspaceStore((s) => s.setTicker);
    const hoverSnapshot = useStudioSelectionStore((s) => s.hoverSnapshot);
    const data = useStudioResultStore((s) => s.data);
    const isPlaying = useStudioResultStore((s) => s.isPlaying);
    const setIsPlaying = useStudioResultStore((s) => s.setIsPlaying);
    const setPlayIndex = useStudioResultStore((s) => s.setPlayIndex);
    const playIndex = useStudioResultStore((s) => s.playIndex);
    const playSpeed = useStudioPreferenceStore((s) => s.playSpeed);
    const setPlaySpeed = useStudioPreferenceStore((s) => s.setPlaySpeed);
    const layoutPreset = useStudioPreferenceStore((s) => s.layoutPreset);
    const setLayoutPreset = useStudioPreferenceStore((s) => s.setLayoutPreset);
    const syncSettings = useStudioPreferenceStore((s) => s.syncSettings);
    const setSyncSettings = useStudioPreferenceStore((s) => s.setSyncSettings);
    const vsModeActive = useStudioEditorStore((s) => s.vsModeActive);
    const setVsModeActive = useStudioEditorStore((s) => s.setVsModeActive);
    const showLayoutManager = useStudioLayoutStore((s) => s.showLayoutManager);
    const setShowLayoutManager = useStudioLayoutStore((s) => s.setShowLayoutManager);
    const isExecuting = useStudioResultStore((s) => s.isExecuting);
    const gridConfig = useStudioLayoutStore((s) => s.gridConfig);
    const stopPlayback = () => setIsPlaying(false);
    const isBusy = isExecuting || isPlaying;

    return (
        <div className="h-10 px-4 border-b border-[rgba(255,255,255,0.06)] flex items-center justify-between bg-[#0a0a0f]">
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-3">
                    <div className="w-[180px]">
                        <TradingViewSearch value={ticker} onSelect={(s) => setTicker(s)} placeholder="SEARCH TICKER..." />
                    </div>
                    <div className="h-6 w-px bg-white/10 mx-2" />
                    <div className="flex items-center gap-4 overflow-hidden">
                        {hoverSnapshot ? (
                            <div className="flex items-center gap-4 animate-in fade-in duration-300">
                                <div className="flex flex-col">
                                    <span className="text-[7px] text-[#64748b] font-mono leading-none">TIME</span>
                                    <span className="text-[9px] text-amber-500 font-mono font-bold leading-tight">{hoverSnapshot.date}</span>
                                </div>
                                {[{ label: 'O', val: hoverSnapshot.o }, { label: 'H', val: hoverSnapshot.h }, { label: 'L', val: hoverSnapshot.l }].map(item => (
                                    <div key={item.label} className="flex flex-col">
                                        <span className="text-[7px] text-[#64748b] font-mono leading-none">{item.label}</span>
                                        <span className="text-[9px] text-white font-mono font-bold leading-tight">{typeof item.val === 'number' ? item.val.toFixed(2) : '--'}</span>
                                    </div>
                                ))}
                                <div className="flex flex-col">
                                    <span className="text-[7px] text-[#64748b] font-mono leading-none">C</span>
                                    <span className={`text-[9px] font-mono font-bold leading-tight ${hoverSnapshot.isBull ? 'text-emerald-500' : 'text-red-500'}`}>{typeof hoverSnapshot.c === 'number' ? hoverSnapshot.c.toFixed(2) : '--'}</span>
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-[7px] text-[#64748b] font-mono leading-none">VOL</span>
                                    <span className="text-[9px] text-white/60 font-mono font-bold leading-tight">{typeof hoverSnapshot.v === 'number' ? (hoverSnapshot.v / 1000000).toFixed(1) : '--'}M</span>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center gap-2">
                                <div className="w-1 h-1 rounded-full bg-[#64748b]" />
                                <span className="text-[9px] font-mono text-[#64748b] tracking-tighter uppercase">{data.candles.length} BARS</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <button
                        aria-label={isPlaying ? 'Stop playback' : 'Start playback'}
                        onClick={() => {
                            if (isPlaying) stopPlayback();
                            else { setIsPlaying(true); if (playIndex >= data.candles.length - 1) setPlayIndex(0); }
                        }}
                        className={`h-7 px-4 rounded-md flex items-center gap-2 transition-all text-[10px] font-mono font-bold ${isPlaying ? 'bg-amber-500 text-black shadow-[0_0_15px_rgba(245,158,11,0.2)]' : 'bg-white/5 text-[#64748b] hover:text-white hover:bg-white/10'}`}
                    >
                        {isPlaying ? <Pause size={12} fill="currentColor" /> : <Play size={12} fill="currentColor" />}
                        {isPlaying ? 'STOP' : 'PLAYBACK'}
                    </button>
                    <div className="flex items-center gap-2 px-3 bg-[#0f0f14] border border-white/5 rounded h-7">
                        <span className="text-[9px] font-mono text-[#64748b] uppercase tracking-tighter">SPEED</span>
                        <input aria-label="Playback speed" type="range" min={5} max={100} value={105 - playSpeed} onChange={e => setPlaySpeed(105 - Number(e.target.value))} className="w-16 h-1 accent-amber-500 cursor-pointer" />
                    </div>
                </div>
                <div className="h-4 w-px bg-white/10" />
                <div className="h-4 w-px bg-white/10" />
                <button aria-label="Toggle VS mode" onClick={() => { setVsModeActive(!vsModeActive); if (!vsModeActive) { setLayoutPreset('1x2'); setSyncSettings(prev => ({ ...prev, time: true, crosshair: true })); } }} className={`flex items-center gap-2 h-7 px-3 rounded text-[10px] font-mono font-bold transition-all ${vsModeActive ? 'text-amber-500 bg-amber-500/10 border border-amber-500/20' : 'text-[#64748b] hover:text-white hover:bg-white/5'}`}>
                    <Terminal size={12} /> VS MODE
                </button>
                <div className={`relative flex items-center gap-1 scale-90 origin-right transition-opacity ${isBusy ? 'opacity-80' : ''}`}>
                    <button aria-label="Open layout manager" onClick={() => setShowLayoutManager(true)} className={`flex items-center gap-2 h-7 px-3 rounded text-[10px] font-mono font-bold uppercase tracking-widest transition-all ${gridConfig.layoutId !== '1x1' ? 'text-blue-400 bg-blue-400/10 border border-blue-400/20' : 'text-[#64748b] hover:text-white hover:bg-white/5 border border-white/5'}`}>
                        <LayoutGrid size={12} /> LAYOUT: {gridConfig.layoutId === '1x1' ? 'SINGLE' : gridConfig.layoutId.toUpperCase()}
                    </button>
                </div>
                <button aria-label="Toggle dual sync" onClick={() => setSyncSettings({ ...syncSettings, time: !syncSettings.time })} className={`flex items-center gap-2 h-7 px-3 rounded text-[10px] font-mono font-bold transition-all ${syncSettings.time ? 'text-emerald-400 bg-emerald-400/10 border border-emerald-400/20' : 'text-[#64748b] hover:text-white hover:bg-white/5'}`}>
                    {syncSettings.time ? <Link2 size={12} /> : <Unlink size={12} />} DUAL SYNC
                </button>
            </div>
        </div>
    );
}
