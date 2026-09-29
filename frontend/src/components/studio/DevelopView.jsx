"use client";
import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Editor from './Editor';
import DataPreflightGate from './DataPreflightGate';
import GridChartCell from './GridChartCell';
import CustomOverlayBuilder, { evaluateOverlay } from './CustomOverlayBuilder';
import EquityComparisonCanvas from './EquityComparisonCanvas';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';
import { useStudioEditorStore } from '@/stores/studio/editorStore';
import { useStudioPreferenceStore } from '@/stores/studio/preferenceStore';
import { useStudioSelectionStore } from '@/stores/studio/selectionStore';
import { useStudioLayoutStore } from '@/stores/studio/layoutStore';
import { useStudioExecution } from '@/hooks/studio/useStudioExecution';
import { useStudioProjectStore } from '@/stores/studio/projectStore';
import ProjectTree from './develop/ProjectTree';
import ExecutionDock from './develop/ExecutionDock';
import { Play, Pause, BarChart2, Clock, Eye, EyeOff, X, Layers, ChevronLeft, ChevronRight, Zap, Activity, ChevronDown, LineChart, LayoutGrid, Terminal, Code2, Grid2X2, Settings, Maximize2, Minimize2, Search, TrendingUp, TrendingDown } from 'lucide-react';
import PatternSelector from '../chart_engine/PatternScanner/PatternSelector';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { useStableDimensions } from '@/components/chart_engine/StableChartContainer';
import { studioRequest } from '@/lib/studioApi';
import { studioComparisonCompatibility } from '@/lib/studioResults';
import { isStudioDataResponse, isStudioTickersResponse } from '@/lib/studioValidators';

// Use the WORKING chart from Trade page
const Q360Canvas = dynamic(
    () => import('./Q360Canvas'),
    { ssr: false, loading: () => <div className="w-full h-full flex items-center justify-center bg-[#03050a] text-white/30 text-xs tracking-widest uppercase italic font-mono animate-pulse">Initializing Canvas Engine...</div> }
);

const DevelopView = () => {
    const data = useStudioResultStore((s) => s.data);
    const dataLoading = useStudioResultStore((s) => s.dataLoading);
    const dataError = useStudioResultStore((s) => s.dataError);
    const gridLoading = useStudioResultStore((s) => s.gridLoading);
    const gridError = useStudioResultStore((s) => s.gridError);
    const playIndex = useStudioResultStore((s) => s.playIndex);
    const setPlayIndex = useStudioResultStore((s) => s.setPlayIndex);
    const isPlaying = useStudioResultStore((s) => s.isPlaying);
    const benchmarkData = useStudioResultStore((s) => s.benchmarkData);
    const gridData = useStudioResultStore((s) => s.gridData);
    const gridDataA = useStudioResultStore((s) => s.gridDataA);
    const gridDataB = useStudioResultStore((s) => s.gridDataB);
    const gridVsView = useStudioResultStore((s) => s.gridVsView);
    const setGridVsView = useStudioResultStore((s) => s.setGridVsView);
    const previousEquityCurve = useStudioResultStore((s) => s.previousEquityCurve);
    const previousSignals = useStudioResultStore((s) => s.previousSignals);
    const isExecuting = useStudioResultStore((s) => s.isExecuting);
    const executionError = useStudioResultStore((s) => s.executionError);
    const setExecutionError = useStudioResultStore((s) => s.setExecutionError);
    const dataA = useStudioResultStore((s) => s.dataA);
    const dataB = useStudioResultStore((s) => s.dataB);
    const analysisComplete = useStudioResultStore((s) => s.analysisComplete);
    const setGridDataA = useStudioResultStore((s) => s.setGridDataA);
    const setGridDataB = useStudioResultStore((s) => s.setGridDataB);
    const setGridConfigStore = useStudioResultStore((s) => s.setGridData);
    const kernelCollapsed = useStudioPreferenceStore((s) => s.kernelCollapsed);
    const setKernelCollapsed = useStudioPreferenceStore((s) => s.setKernelCollapsed);
    const ticker = useStudioWorkspaceStore((s) => s.ticker);
    const setTicker = useStudioWorkspaceStore((s) => s.setTicker);
    const benchmark = useStudioWorkspaceStore((s) => s.benchmark);
    const setBenchmark = useStudioWorkspaceStore((s) => s.setBenchmark);
    const customOverlays = useStudioSelectionStore((s) => s.customOverlays);
    const setCustomOverlays = useStudioSelectionStore((s) => s.setCustomOverlays);
    const activeIndicators = useStudioSelectionStore((s) => s.activeIndicators);
    const setActiveIndicators = useStudioSelectionStore((s) => s.setActiveIndicators);
    const drawings = useStudioSelectionStore((s) => s.drawings);
    const setDrawings = useStudioSelectionStore((s) => s.setDrawings);
    const activeDrawingTool = useStudioSelectionStore((s) => s.activeDrawingTool);
    const setActiveDrawingTool = useStudioSelectionStore((s) => s.setActiveDrawingTool);
    const selectedPatterns = useStudioSelectionStore((s) => s.selectedPatterns);
    const setSelectedPatterns = useStudioSelectionStore((s) => s.setSelectedPatterns);
    const setHoverSnapshot = useStudioSelectionStore((s) => s.setHoverSnapshot);
    const layoutPreset = useStudioPreferenceStore((s) => s.layoutPreset);
    const setLayoutPreset = useStudioPreferenceStore((s) => s.setLayoutPreset);
    const gridConfig = useStudioLayoutStore((s) => s.gridConfig);
    const setGridConfig = useStudioLayoutStore((s) => s.setGridConfig);
    const syncSettings = useStudioPreferenceStore((s) => s.syncSettings);
    const showIndicatorSelect = useStudioWorkspaceStore((s) => s.showIndicatorSelect);
    const setShowIndicatorSelect = useStudioWorkspaceStore((s) => s.setShowIndicatorSelect);
    const showLayoutManager = useStudioLayoutStore((s) => s.showLayoutManager);
    const setShowLayoutManager = useStudioLayoutStore((s) => s.setShowLayoutManager);
    const codeA = useStudioEditorStore((s) => s.codeA);
    const setCodeA = useStudioEditorStore((s) => s.setCodeA);
    const codeB = useStudioEditorStore((s) => s.codeB);
    const setCodeB = useStudioEditorStore((s) => s.setCodeB);
    const vsModeActive = useStudioEditorStore((s) => s.vsModeActive);
    const { executeStrategy, cancelExecution, fetchData, stopPlayback } = useStudioExecution();
    const retryData = useCallback(() => fetchData(ticker), [fetchData, ticker]);
    const retryGridData = useCallback(() => {}, []);
    const addIndicator = useCallback((config) => setActiveIndicators((prev) => [...prev, config]), [setActiveIndicators]);
    const removeIndicator = useCallback((id) => setActiveIndicators((prev) => prev.filter((i) => i.id !== id)), [setActiveIndicators]);
    const toggleIndicator = useCallback((id) => setActiveIndicators((prev) => prev.map((i) => i.id === id ? { ...i, visible: !i.visible } : i)), [setActiveIndicators]);

    const [maximizedChartIdx, setMaximizedChartIdx] = useState(null);

    // Grid Layout Mapping
    const getGridLayoutClass = (layoutId) => {
        switch (layoutId) {
            case '1x1': return 'flex-1';
            case '1x2': return 'grid grid-cols-2 h-full gap-2 p-2';
            case '2x1': return 'grid grid-rows-2 h-full gap-2 p-2';
            case '1x3': return 'grid grid-cols-3 h-full gap-2 p-2';
            case '3x1': return 'grid grid-rows-3 h-full gap-2 p-2';
            case '2x2': return 'grid grid-cols-2 grid-rows-2 h-full gap-2 p-2';
            case '1x4': return 'grid grid-cols-4 h-full gap-2 p-2';
            case '4x1': return 'grid grid-rows-4 h-full gap-2 p-2';
            case '2x3': return 'grid grid-cols-3 grid-rows-2 h-full gap-2 p-2';
            case '3x2': return 'grid grid-cols-2 grid-rows-3 h-full gap-2 p-2';
            case '2x4': return 'grid grid-cols-4 grid-rows-2 h-full gap-2 p-2';
            case '4x2': return 'grid grid-cols-2 grid-rows-4 h-full gap-2 p-2';
            case '3x3': return 'grid grid-cols-3 grid-rows-3 h-full gap-2 p-2';
            case '3x4': return 'grid grid-cols-4 grid-rows-3 h-full gap-2 p-2';
            case '4x3': return 'grid grid-cols-3 grid-rows-4 h-full gap-2 p-2';
            case '4x4': return 'grid grid-cols-4 grid-rows-4 h-full gap-2 p-2';
            default: return 'flex-1';
        }
    };
    
    const [showVolume, setShowVolume] = useState(true);
    const [showBenchmark, setShowBenchmark] = useState(false);
    const [showIndicators, setShowIndicators] = useState(false);
    const [showPatterns, setShowPatterns] = useState(true);
    const [patternModalOpen, setPatternModalOpen] = useState(false);
    const [showOverlayBuilder, setShowOverlayBuilder] = useState(false);
    const [benchmarkModalOpen, setBenchmarkModalOpen] = useState(false);
    const [benchmarkError, setBenchmarkError] = useState('');
    const [benchmarkLoading, setBenchmarkLoading] = useState(false);
    const [parquetTickers, setParquetTickers] = useState([]);
    
    // Cross-chart synchronization states
    const [syncedOffset, setSyncedOffset] = useState(null);
    const [syncedScale, setSyncedScale] = useState(null);
    const [syncedHover, setSyncedHover] = useState(null);

    const overlays = activeIndicators.filter(i => i.placement === 'overlay');
    // Automatically hide/stash oscillators when entering grid mode per audit report Section 2B
    useEffect(() => {
        if (gridConfig.layoutId !== '1x1') {
            const paneIndicators = activeIndicators.filter(ind => ind.placement === 'pane');
            if (paneIndicators.length > 0) {
                // Remove all pane indicators when grid is active
                paneIndicators.forEach(ind => removeIndicator(ind.id));
            }
        }
    }, [gridConfig.layoutId, activeIndicators, removeIndicator]);

    const oscillators = activeIndicators.filter(i => i.placement === 'pane');

    // Evaluate custom overlays against candle data
    const overlayMatches = useMemo(() => {
        if (!customOverlays || customOverlays.length === 0 || !data.candles || data.candles.length === 0) {
            return [];
        }
        
        const allMatches = [];
        customOverlays.forEach(overlay => {
            const matches = evaluateOverlay(overlay, data.candles);
            allMatches.push(...matches.map(m => ({ ...m, overlayName: overlay.name })));
        });
        return allMatches;
    }, [customOverlays, data.candles]);

    // Prepare equity curve for comparison canvas
    const primaryEquity = useMemo(() => {
        if (!data.equityCurve || data.equityCurve.length === 0) return [];
        return data.equityCurve.map((value, idx) => ({
            x: idx,
            value: value,
            time: data.candles[idx]?.time
        }));
    }, [data.equityCurve, data.candles]);
    const comparison = useMemo(() => vsModeActive && dataB?.equityCurve?.length ? studioComparisonCompatibility(dataA, dataB) : null, [dataA, dataB, vsModeActive]);

    // Prepare benchmark equity (buy & hold or previous version)
    const ghostEquity = useMemo(() => {
        if (vsModeActive && comparison?.compatible && dataB.equityCurve?.length > 0) {
            return dataB.equityCurve.map((value, idx) => ({ x: idx, value, time: dataB.candles[idx]?.time }));
        }
        if (vsModeActive) return [];
        // Mode 1: Previous Version Ghosting (Priority)
        if (previousEquityCurve && previousEquityCurve.length > 0) {
            return previousEquityCurve.map((val, idx) => ({
                x: idx,
                value: val,
                time: data.candles[idx]?.time
            }));
        }

        // Mode 2: SPY Benchmark Ghosting
        if (!benchmarkData || benchmarkData.length === 0 || !showBenchmark) return [];
        const startPrice = benchmarkData[0]?.close || 1;
        const startEquity = primaryEquity[0]?.value || 100;
        
        return benchmarkData.slice(0, data.candles.length).map((candle, idx) => ({
            x: idx,
            value: startEquity * (candle.close / startPrice),
            time: candle.time
        }));
    }, [benchmarkData, showBenchmark, primaryEquity, data.candles, previousEquityCurve, comparison, dataB, vsModeActive]);

    const handleOverlayCreate = (overlay) => {
        setCustomOverlays(prev => [...prev, overlay]);
    };

    const handleOverlayDelete = (overlayId) => {
        setCustomOverlays(prev => prev.filter(overlay => overlay.id !== overlayId));
    };

    const handleGridTickerChange = (index, symbol) => {
        const nextSymbol = (symbol || '').trim().toUpperCase();
        if (!nextSymbol) return;
        if (index === 0) {
            setTicker(nextSymbol);
        }
        setGridConfig(prev => {
            const nextTickers = [...(prev.tickers || [])];
            nextTickers[index] = nextSymbol;
            return { ...prev, tickers: nextTickers };
        });
    };

    useEffect(() => {
        const loadParquetTickers = async () => {
            try {
                const payload = await studioRequest('/tickers?universe=all', { validate: isStudioTickersResponse });
                if (payload?.status === 'success' && Array.isArray(payload?.tickers)) {
                    setParquetTickers(payload.tickers);
                }
            } catch (err) {
                console.warn('Failed to load studio ticker universe:', err);
            }
        };
        loadParquetTickers();
    }, []);

    const applyBenchmarkSymbol = async (symbol) => {
        const normalized = (symbol || '').trim().toUpperCase();
        if (!normalized) return;
        if (normalized === ticker) {
            setBenchmarkError('Benchmark cannot be the same as the main ticker');
            return;
        }

        if (parquetTickers.length > 0) {
            const alt = normalized.replace(/\./g, '_').replace(/-/g, '_').replace(/^\^/, '_IDX_');
            if (!parquetTickers.includes(normalized) && !parquetTickers.includes(alt)) {
                setBenchmarkError('Symbol not found in parquet universe');
                return;
            }
        }

        setBenchmarkLoading(true);
        setBenchmarkError('');
        try {
            const payload = await studioRequest(`/data?ticker=${encodeURIComponent(normalized)}&lookback_years=10`, {
                validate: isStudioDataResponse,
            });
            if (payload?.status !== 'success' || !Array.isArray(payload?.candles) || payload.candles.length === 0) {
                throw new Error('No parquet data found for this benchmark symbol');
            }
            setBenchmark(normalized);
            setShowBenchmark(true);
            setBenchmarkModalOpen(false);
        } catch (err) {
            setBenchmarkError(err?.message || 'Unable to load benchmark data');
        } finally {
            setBenchmarkLoading(false);
        }
    };

    // Sync active project file to editor (P5-W1 institutional)
    const activeFile = useStudioProjectStore((s) => s.files.find((f) => f.id === s.activeId));
    const updateDraft = useStudioProjectStore((s) => s.updateDraft);
    useEffect(() => {
        if (activeFile) setCodeA(activeFile.draft ?? activeFile.content);
    }, [activeFile, setCodeA]);
    useEffect(() => {
        if (activeFile && codeA !== activeFile.draft) updateDraft(activeFile.id, codeA);
    }, [activeFile, codeA, updateDraft]);

    return (
        <div className="flex-1 flex min-h-0 overflow-hidden relative">
            {/* P5-W1 Project Tree — react-arborist pattern, zero fake data */}
            <ProjectTree />
            {/* Sidebar: Kernel Editors */}
            <div className={`${kernelCollapsed ? 'w-0' : (vsModeActive ? 'w-[800px]' : 'w-[450px]')} border-r border-white/5 bg-[#050508] relative transition-all duration-300 flex flex-col overflow-hidden z-20`}>
                <div className="flex items-center justify-between h-9 px-4 border-b border-white/5 bg-white/[0.02] flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <Terminal size={12} className="text-amber-500" />
                        <span className="text-[10px] font-mono font-bold text-white tracking-widest uppercase">
                            {vsModeActive ? 'DUAL KERNEL ENGINE' : 'STRATEGY KERNEL'}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border ${executionError ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20'}`}>
                            <div className={`w-1 h-1 rounded-full ${executionError ? 'bg-red-500' : 'bg-emerald-500 animate-pulse'}`} />
                            <span className={`text-[8px] font-mono font-bold ${executionError ? 'text-red-400' : 'text-emerald-500'}`}>
                                {executionError ? 'UNAVAILABLE' : 'READY'}
                            </span>
                        </div>
                        <button onClick={() => setKernelCollapsed(true)} className="p-1 hover:bg-white/5 rounded text-[#64748b] hover:text-white">
                            <ChevronDown size={14} className="rotate-90" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 flex min-h-0">
                    <div className="flex-1 flex flex-col min-w-0">
                        {vsModeActive && (
                            <div className="h-6 px-4 flex items-center bg-white/5 border-b border-white/5">
                                <span className="text-[8px] font-mono text-amber-500 font-bold">VERSION A</span>
                            </div>
                        )}
                        <div className="flex-1 overflow-hidden">
                            <Editor
                                height="100%"
                                defaultLanguage="python"
                                theme="sovereign-dark"
                                value={codeA}
                                onChange={setCodeA}
                                options={{
                                    fontSize: 10,
                                    minimap: { enabled: false },
                                    scrollBeyondLastLine: false,
                                    lineNumbers: 'on',
                                }}
                            />
                        </div>
                    </div>

                    {vsModeActive && (
                        <div className="flex-1 flex flex-col border-l border-white/5 min-w-0 bg-black/20">
                            <div className="h-6 px-4 flex items-center bg-white/5 border-b border-white/5">
                                <span className="text-[8px] font-mono text-blue-400 font-bold">VERSION B</span>
                            </div>
                            <div className="flex-1 overflow-hidden">
                                <Editor
                                    height="100%"
                                    defaultLanguage="python"
                                    theme="sovereign-dark"
                                    value={codeB}
                                    onChange={setCodeB}
                                    options={{
                                        fontSize: 10,
                                        minimap: { enabled: false },
                                        scrollBeyondLastLine: false,
                                        lineNumbers: 'on',
                                    }}
                                />
                            </div>
                        </div>
                    )}
                </div>

                <div className="p-4 bg-[#050508] border-t border-white/5">
                    {executionError && (
                        <div role="alert" className="mb-3 rounded-md border border-red-500/20 bg-red-500/5 p-3 text-[10px] leading-relaxed text-red-300 font-mono">
                            <div className="flex items-start justify-between gap-3">
                                <span>{executionError}</span>
                                <button aria-label="Dismiss execution error" onClick={() => setExecutionError(null)} className="text-red-300/70 hover:text-red-200">
                                    <X size={12} />
                                </button>
                            </div>
                        </div>
                    )}
                    <button 
                        onClick={isExecuting ? cancelExecution : executeStrategy}
                        disabled={!ticker}
                        className={`w-full group relative h-10 ${isExecuting ? 'border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20' : 'bg-amber-500 text-black hover:bg-amber-400'} disabled:bg-white/10 disabled:text-[#64748b] rounded font-mono text-[11px] font-bold flex items-center justify-center gap-2 transition-all duration-300 shadow-[0_0_20px_rgba(245,158,11,0.2)]`}
                    >
                        <Activity size={14} className={isExecuting ? 'animate-spin' : ''} />
                        <span>{isExecuting ? 'STOP WAITING' : (vsModeActive ? 'EXECUTE BOTH' : 'EXECUTE STRATEGY')}</span>
                    </button>
                </div>
            </div>
            
            <div className="flex-1 flex flex-col min-w-0 bg-[#020204] relative">
                {/* Chart Toolbar */}
                <div className="h-9 px-4 border-b border-white/5 flex items-center justify-between bg-[#0a0a0f]/80 backdrop-blur-sm flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <button 
                            onClick={() => setShowIndicators(!showIndicators)}
                            className={`flex items-center gap-2 px-3 h-7 rounded-lg text-[10px] font-mono font-bold uppercase tracking-wider transition-all ${
                                activeIndicators.length > 0
                                ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' 
                                : 'bg-white/5 text-[#64748b] hover:text-white border border-transparent'
                            }`}
                        >
                            <Activity size={12} />
                            Indicators
                            {activeIndicators.length > 0 && (
                                <span className="px-1.5 py-0.5 bg-amber-500 text-black rounded text-[8px]">
                                    {activeIndicators.length}
                                </span>
                            )}
                        </button>
                        
                        <button 
                            onClick={() => setShowVolume(!showVolume)}
                            className={`flex items-center gap-1.5 px-2 h-7 rounded-lg text-[10px] font-mono font-bold transition-all ${
                                showVolume 
                                ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' 
                                : 'text-[#64748b] hover:text-white'
                            }`}
                        >
                            <BarChart2 size={11} />
                            Vol
                        </button>
                        
                        <button 
                            onClick={() => setBenchmarkModalOpen(true)}
                            className={`flex items-center gap-1.5 px-2 h-7 rounded-lg text-[10px] font-mono font-bold transition-all ${
                                showBenchmark 
                                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                                : 'text-[#64748b] hover:text-white'
                            }`}
                        >
                            <LineChart size={11} />
                            BENCHMARK
                        </button>
                        
                        <div className="w-px h-4 bg-white/10 mx-1" />

                        <div className="flex items-center group relative">
                            <button 
                                onClick={() => {
                                    if (selectedPatterns.length === 0) setSelectedPatterns(['hammer', 'engulfing', 'star', 'doji']);
                                    else setSelectedPatterns([]);
                                    setShowPatterns(true);
                                }}
                                className={`flex items-center gap-1.5 px-2 h-7 rounded-l-lg text-[10px] font-mono font-bold transition-all ${
                                    selectedPatterns.length > 0 && showPatterns
                                    ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' 
                                    : 'text-[#64748b] hover:text-white'
                                }`}
                            >
                                <LayoutGrid size={11} />
                                Patterns {selectedPatterns.length > 0 ? `(${selectedPatterns.length})` : ''}
                            </button>
                            <button 
                                onClick={() => setPatternModalOpen(true)}
                                className="px-1.5 h-7 bg-white/5 hover:bg-white/10 text-[#64748b] hover:text-white border-y border-r border-white/5 rounded-r-lg transition-all"
                            >
                                <ChevronDown size={10} />
                            </button>
                        </div>

                        <button 
                            onClick={() => setShowOverlayBuilder(true)}
                            className={`flex items-center gap-1.5 px-2 h-7 rounded-lg text-[10px] font-mono font-bold transition-all ${
                                customOverlays.length > 0
                                ? 'bg-purple-500/10 text-purple-500 border border-purple-500/20' 
                                : 'text-[#64748b] hover:text-white'
                            }`}
                        >
                            <Layers size={11} />
                            Overlays
                        </button>

                        {vsModeActive && gridConfig.layoutId !== '1x1' && (
                            <div className="flex items-center gap-1 ml-2 px-1 py-1 rounded-lg border border-white/10 bg-white/[0.02]">
                                <button
                                    onClick={() => setGridVsView('A')}
                                    className={`px-2 h-6 rounded text-[9px] font-mono font-bold ${gridVsView === 'A' ? 'bg-amber-500 text-black' : 'text-[#8b95a7] hover:text-white'}`}
                                >
                                    VERSION A
                                </button>
                                <button
                                    onClick={() => setGridVsView('B')}
                                    className={`px-2 h-6 rounded text-[9px] font-mono font-bold ${gridVsView === 'B' ? 'bg-blue-500 text-white' : 'text-[#8b95a7] hover:text-white'}`}
                                >
                                    VERSION B
                                </button>
                            </div>
                        )}

                        {/* ISA and Log toggles intentionally removed to avoid chart blanking issues */}
                    </div>
                </div>

                <div className="flex-1 flex min-h-0 overflow-hidden relative">
                    <div className="flex-1 flex flex-col min-w-0 relative">
                        {!ticker && gridConfig.layoutId === '1x1' ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#020204] z-50">
                                <div className="max-w-md w-full text-center space-y-8 p-12 relative">
                                    <div className="absolute inset-0 bg-amber-500/5 blur-[120px] rounded-full" />
                                    <div className="relative space-y-4">
                                        <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-[0_0_30px_rgba(245,158,11,0.2)]">
                                            <Zap size={32} className="text-black fill-black" />
                                        </div>
                                        <div className="space-y-1">
                                            <h2 className="text-2xl font-bold text-white tracking-widest uppercase italic font-mono">Workspace Inactive</h2>
                                            <p className="text-[10px] font-mono text-[#64748b] uppercase tracking-[0.3em] leading-relaxed">
                                                Select a valid instrument from the top navigation bar<br/>
                                                to initialize the quantitative analytical pipeline
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex-1 flex flex-col min-h-0">
                                {/* Professional Multi-Chart Grid System */}
                                <div className={`flex-1 relative min-h-0 ${gridConfig.layoutId !== '1x1' ? getGridLayoutClass(gridConfig.layoutId) : ''}`}>
                                    {gridConfig.layoutId === '1x1' ? (
                                        <div className="flex-1 relative h-full">
                                            {dataLoading && data.candles.length === 0 ? (
                                                <div className="absolute inset-0 flex items-center justify-center bg-[#050508] text-[10px] font-mono uppercase tracking-widest text-[#64748b]">
                                                    Loading observed market data…
                                                </div>
                                            ) : dataError ? (
                                                <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center bg-[#050508] p-8 text-center">
                                                    <div className="text-xs font-mono font-bold uppercase tracking-widest text-red-400">Market data unavailable</div>
                                                    <p className="mt-2 max-w-md text-[10px] font-mono leading-relaxed text-[#64748b]">{dataError}</p>
                                                    <button onClick={retryData} className="mt-4 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-2 text-[10px] font-mono font-bold uppercase text-red-300 hover:bg-red-500/20">
                                                        Retry data request
                                                    </button>
                                                </div>
                                            ) : (
                                                <Q360Canvas
                                                    candles={data.candles}
                                                    signals={data.signals}
                                                    previousSignals={previousSignals}
                                                    playIndex={playIndex}
                                                    isPlaying={isPlaying}
                                                    activeIndicators={activeIndicators}
                                                    showVolume={showVolume}
                                                    volumeProfile={data.volumeProfile}
                                                    benchmarkData={benchmarkData}
                                                    showBenchmark={showBenchmark}
                                                    selectedPatterns={selectedPatterns}
                                                    customOverlayMatches={overlayMatches}
                                                    syncedOffset={syncSettings.time ? syncedOffset : null}
                                                    syncedScale={syncSettings.time ? syncedScale : null}
                                                    syncedHover={syncSettings.crosshair ? syncedHover : null}
                                                    onOffsetChange={setSyncedOffset}
                                                    onScaleChange={setSyncedScale}
                                                    onHoverChange={(hover) => {
                                                        setHoverSnapshot(hover);
                                                        setSyncedHover(hover);
                                                    }}
                                                />
                                            )}
                                        </div>
                                    ) : (
                                        gridConfig.tickers.map((t, i) => (
                                            <GridChartCell 
                                                key={`${t}-${i}-${gridVsView}`}
                                                ticker={t}
                                                data={(vsModeActive && gridConfig.layoutId !== '1x1')
                                                    ? ((gridVsView === 'B' ? gridDataB : gridDataA)?.[i] || null)
                                                    : (gridData[i] || null)}
                                                isLoading={gridLoading}
                                                error={gridError}
                                                onRetry={retryGridData}
                                                index={i}
                                                total={gridConfig.tickers.length}
                                                playIndex={playIndex}
                                                isPlaying={isPlaying}
                                                activeIndicators={activeIndicators}
                                                showVolume={showVolume}
                                                benchmarkData={benchmarkData}
                                                showBenchmark={showBenchmark}
                                                selectedPatterns={selectedPatterns}
                                                overlayMatches={overlayMatches}
                                                setHoverSnapshot={setHoverSnapshot}
                                                syncedOffset={syncSettings.time ? syncedOffset : null}
                                                syncedScale={syncSettings.time ? syncedScale : null}
                                                syncedHover={syncSettings.crosshair ? syncedHover : null}
                                                onOffsetChange={setSyncedOffset}
                                                onScaleChange={setSyncedScale}
                                                onHoverChange={setSyncedHover}
                                                onTickerChange={handleGridTickerChange}
                                                versionLabel={vsModeActive && gridConfig.layoutId !== '1x1' ? gridVsView : null}
                                                isMaximized={maximizedChartIdx === i}
                                                onMaximize={() => setMaximizedChartIdx(i)}
                                                onRestore={() => setMaximizedChartIdx(null)}
                                            />
                                        ))
                                    )}
                                </div>
                                
                                {/* Strategy Execution Results - Only show if not in grid mode for clarity */}
                                {gridConfig.layoutId === '1x1' && analysisComplete && primaryEquity.length > 0 && (
                                    <div className="h-24 bg-[#050508] border-t border-white/5 relative flex-shrink-0">
                                        <div className="absolute top-2 left-4 z-10 flex items-center gap-2">
                                            <div className="w-1 h-3 bg-amber-500 rounded-full" />
                                            <span className="text-[8px] font-mono text-amber-500 font-bold uppercase tracking-widest">Comp Alpha</span>
                                        </div>
                                        {comparison && !comparison.compatible ? <div role="alert" className="absolute right-4 top-2 z-20 max-w-[55%] text-right text-[9px] font-mono text-red-300">Comparison refused: {comparison.reasons.join('; ')}</div> : null}
                                        <EquityComparisonCanvas 
                                            primaryEquity={primaryEquity}
                                            ghostEquity={ghostEquity}
                                            primaryMetrics={data.metrics}
                                            ghostMetrics={comparison?.compatible ? dataB.metrics : {}}
                                            isVsMode={vsModeActive}
                                        />
                                    </div>
                                )}

                            </div>
                        )}

                        {/* Control Strip */}
                        <div className="h-10 px-6 flex items-center gap-4 bg-[#0a0a0f] border-t border-white/5 flex-shrink-0">
                            <div className="flex items-center gap-3 text-amber-500/50">
                                <Clock size={12} />
                                <span className="text-[10px] font-mono text-white/40 uppercase tracking-tighter">Timeline</span>
                            </div>
                            <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5 border border-white/5">
                                <button 
                                    onClick={() => { stopPlayback(); setPlayIndex(Math.max(0, playIndex - 1)); }}
                                    className="p-1 hover:bg-white/10 rounded transition-all text-[#64748b] hover:text-white"
                                >
                                    <ChevronLeft size={14} />
                                </button>
                                <button 
                                    onClick={() => { stopPlayback(); setPlayIndex(Math.min(data.candles.length - 1, playIndex + 1)); }}
                                    className="p-1 hover:bg-white/10 rounded transition-all text-[#64748b] hover:text-white"
                                >
                                    <ChevronRight size={14} />
                                </button>
                            </div>
                            <div className="flex-1 relative group py-2">
                                <input 
                                    type="range" 
                                    min={0} 
                                    max={Math.max(0, data.candles.length - 1)} 
                                    value={playIndex} 
                                    onChange={e => {
                                        stopPlayback();
                                        setPlayIndex(Number(e.target.value));
                                    }}
                                    className="w-full h-1 bg-white/5 rounded-full appearance-none cursor-pointer accent-amber-500 transition-all"
                                />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-mono text-[#64748b]">
                                    {playIndex + 1} / {data.candles.length}
                                </span>
                                <div className="flex items-center gap-2 px-3 h-6 bg-white/5 rounded-full border border-white/5">
                                    <span className="text-[10px] font-mono text-amber-500 font-bold tracking-widest">
                                        {data.candles[playIndex] ? new Date(data.candles[playIndex].time * 1000).toLocaleDateString() : '----/--/--'}
                                    </span>
                                </div>
                            </div>
                        </div>
                        {/* P5-W2 Execution Dock — institutional kernel state + logs + variables */}
                        <ExecutionDock />
                    </div>

                </div>
            </div>

            {/* Modals */}
            {showIndicators && (
                <div className="fixed top-24 left-1/2 -translate-x-1/2 z-[100] w-[400px] bg-[#0a0a0f]/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl p-6 animate-in fade-in zoom-in-95 duration-200">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <Activity size={14} className="text-amber-500" />
                            <h3 className="text-xs font-bold text-white uppercase tracking-widest">Active Indicators</h3>
                        </div>
                        <button onClick={() => setShowIndicators(false)} className="p-1 hover:bg-white/5 rounded text-[#64748b]">
                            <X size={16} />
                        </button>
                    </div>
                    <div className="space-y-3">
                        {activeIndicators.map(ind => (
                            <div key={ind.id} className="flex items-center justify-between p-2 rounded-lg bg-white/5 border border-white/5">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: ind.color }} />
                                    <span className="text-[10px] font-mono font-bold text-white uppercase">{ind.shortName}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <button onClick={() => toggleIndicator(ind.id)} className="p-1.5 hover:bg-white/10 rounded">
                                        {ind.visible ? <Eye size={12} className="text-amber-500" /> : <EyeOff size={12} className="text-[#64748b]" />}
                                    </button>
                                    <button onClick={() => removeIndicator(ind.id)} className="p-1.5 hover:bg-white/10 rounded text-[#64748b] hover:text-red-500 font-bold">
                                        <X size={12} />
                                    </button>
                                </div>
                            </div>
                        ))}
                        <button 
                            onClick={() => { setShowIndicatorSelect(true); setShowIndicators(false); }}
                            className="w-full py-2 rounded-lg bg-amber-500 text-black text-[10px] font-bold uppercase tracking-widest hover:bg-amber-400 mt-2"
                        >
                            + ADD INDICATOR
                        </button>
                    </div>
                </div>
            )}

            <PatternSelector 
                isOpen={patternModalOpen}
                onClose={() => setPatternModalOpen(false)}
                selectedPatterns={selectedPatterns}
                onPatternToggle={(p) => {
                    setSelectedPatterns(prev => 
                        prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
                    );
                }}
                onClearAll={() => setSelectedPatterns([])}
            />

            <CustomOverlayBuilder 
                isOpen={showOverlayBuilder}
                onClose={() => setShowOverlayBuilder(false)}
                onOverlayCreate={handleOverlayCreate}
                onOverlayDelete={handleOverlayDelete}
                existingOverlays={customOverlays}
            />

            <DataPreflightGate 
                isOpen={showIndicatorSelect}
                onClose={() => setShowIndicatorSelect(false)}
                onExecute={executeStrategy}
                activeIndicators={activeIndicators}
                addIndicator={addIndicator}
                removeIndicator={removeIndicator}
                toggleIndicator={toggleIndicator}
                isGridMode={gridConfig.layoutId !== '1x1'}
                ticker={ticker}
                dataQuality={data.metadata?.data_quality}
            />

            {benchmarkModalOpen && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
                    <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={() => setBenchmarkModalOpen(false)} />
                    <div className="relative w-full max-w-2xl bg-[#0a0a0f] border border-white/10 rounded-2xl shadow-2xl p-8 space-y-6 overflow-visible">
                        <div className="flex items-center justify-between">
                            <div className="space-y-1">
                                <h3 className="text-sm font-bold text-white uppercase tracking-[0.2em]">Select Benchmark</h3>
                                <p className="text-[10px] text-[#64748b] font-mono">CHOOSE A SYMBOL TO OVERLAY PERFORMANCE GHOSTING</p>
                            </div>
                            <button onClick={() => setBenchmarkModalOpen(false)} className="p-2 hover:bg-white/5 rounded-lg text-[#64748b]">
                                <X size={18} />
                            </button>
                        </div>
                        
                        {/* Quick Select Buttons */}
                        <div className="space-y-3">
                            <span className="text-[9px] font-mono text-[#64748b] uppercase tracking-widest">Quick Select</span>
                            <div className="grid grid-cols-4 gap-2">
                                {[
                                    { symbol: 'SPY', label: 'S&P 500' },
                                    { symbol: 'QQQ', label: 'Nasdaq 100' },
                                    { symbol: 'IWM', label: 'Russell 2K' },
                                    { symbol: 'DIA', label: 'Dow Jones' },
                                    { symbol: 'GLD', label: 'Gold' },
                                    { symbol: 'TLT', label: '20Y Treasury' },
                                    { symbol: 'AAPL', label: 'Apple' },
                                    { symbol: 'MSFT', label: 'Microsoft' },
                                ].map(({ symbol, label }) => (
                                    <button
                                        key={symbol}
                                        onClick={() => applyBenchmarkSymbol(symbol)}
                                        disabled={benchmarkLoading}
                                        className="flex flex-col items-center gap-1 p-3 rounded-xl border border-white/10 hover:border-blue-400/40 hover:bg-blue-500/10 transition-all group disabled:opacity-50"
                                    >
                                        <span className="text-xs font-bold text-white group-hover:text-blue-300">{symbol}</span>
                                        <span className="text-[8px] font-mono text-[#64748b]">{label}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                        
                        {/* Custom Search */}
                        <div className="space-y-3">
                            <span className="text-[9px] font-mono text-[#64748b] uppercase tracking-widest">Or Search Any Symbol</span>
                            <div className="relative z-[250]">
                                <TradingViewSearch 
                                    onSelect={(s) => {
                                        applyBenchmarkSymbol(s);
                                    }}
                                    placeholder="TYPE SYMBOL (SPY, QQQ, BTC...)"
                                    autoFocus
                                    dropdownZIndex={380}
                                />
                            </div>
                        </div>

                        {(benchmarkLoading || benchmarkError) && (
                            <div className={`text-[10px] font-mono ${benchmarkError ? 'text-red-400' : 'text-amber-400'}`}>
                                {benchmarkLoading ? 'Validating benchmark against parquet data...' : benchmarkError}
                            </div>
                        )}
                        
                        {/* Clear Benchmark */}
                        {showBenchmark && benchmark && (
                            <button
                                onClick={() => {
                                    setShowBenchmark(false);
                                    setBenchmarkModalOpen(false);
                                    setBenchmarkError('');
                                }}
                                className="w-full py-3 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 text-xs font-mono font-bold uppercase tracking-widest hover:bg-red-500/20 transition-all"
                            >
                                Remove Benchmark Overlay ({benchmark})
                            </button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default DevelopView;
