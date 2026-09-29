"use client";
import React, { createContext, useContext, useCallback, useEffect, useRef } from 'react';
import { studioRequest } from '@/lib/studioApi';
import { useStudioEditorStore } from '@/stores/studio/editorStore';
import { useStudioPreferenceStore } from '@/stores/studio/preferenceStore';
import { useStudioSelectionStore } from '@/stores/studio/selectionStore';
import { useStudioLayoutStore } from '@/stores/studio/layoutStore';
import { useStudioWorkspaceStore } from '@/stores/studio/workspaceStore';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import {
    isStudioDataResponse,
    isStudioExecutionResponse,
    isStudioMonteCarloResponse,
    isStudioWalkForwardResponse,
} from '@/lib/studioValidators';

const StudioContext = createContext();

export const StudioProvider = ({ children }) => {
    const activeTab = useStudioWorkspaceStore((state) => state.activeTab);
    const setActiveTab = useStudioWorkspaceStore((state) => state.setActiveTab);
    const ticker = useStudioWorkspaceStore((state) => state.ticker);
    const setTicker = useStudioWorkspaceStore((state) => state.setTicker);
    const benchmark = useStudioWorkspaceStore((state) => state.benchmark);
    const setBenchmark = useStudioWorkspaceStore((state) => state.setBenchmark);
    const selectedStrategy = useStudioEditorStore((state) => state.selectedStrategy);
    const setSelectedStrategy = useStudioEditorStore((state) => state.setSelectedStrategy);
    const codeA = useStudioEditorStore((state) => state.codeA);
    const setCodeA = useStudioEditorStore((state) => state.setCodeA);
    const codeB = useStudioEditorStore((state) => state.codeB);
    const setCodeB = useStudioEditorStore((state) => state.setCodeB);
    const vsModeActive = useStudioEditorStore((state) => state.vsModeActive);
    const setVsModeActive = useStudioEditorStore((state) => state.setVsModeActive);
    const applyStrategy = useStudioEditorStore((state) => state.applyStrategy);
    const hydrateDrafts = useStudioEditorStore((state) => state.hydrateDrafts);
    const hoverSnapshot = useStudioSelectionStore((state) => state.hoverSnapshot);
    const setHoverSnapshot = useStudioSelectionStore((state) => state.setHoverSnapshot);
    
    const dataA = useStudioResultStore((state) => state.dataA);
    const setDataA = useStudioResultStore((state) => state.setDataA);
    const dataB = useStudioResultStore((state) => state.dataB);
    const setDataB = useStudioResultStore((state) => state.setDataB);
    const gridDataA = useStudioResultStore((state) => state.gridDataA);
    const setGridDataA = useStudioResultStore((state) => state.setGridDataA);
    const gridDataB = useStudioResultStore((state) => state.gridDataB);
    const setGridDataB = useStudioResultStore((state) => state.setGridDataB);
    const gridVsView = useStudioResultStore((state) => state.gridVsView);
    const setGridVsView = useStudioResultStore((state) => state.setGridVsView);
    const isExecuting = useStudioResultStore((state) => state.isExecuting);
    const setIsExecuting = useStudioResultStore((state) => state.setIsExecuting);
    const executionError = useStudioResultStore((state) => state.executionError);
    const setExecutionError = useStudioResultStore((state) => state.setExecutionError);
    const isPlaying = useStudioResultStore((state) => state.isPlaying);
    const setIsPlaying = useStudioResultStore((state) => state.setIsPlaying);
    const playIndex = useStudioResultStore((state) => state.playIndex);
    const setPlayIndex = useStudioResultStore((state) => state.setPlayIndex);
    const playSpeed = useStudioPreferenceStore((state) => state.playSpeed);
    const setPlaySpeed = useStudioPreferenceStore((state) => state.setPlaySpeed);
    const kernelCollapsed = useStudioPreferenceStore((state) => state.kernelCollapsed);
    const setKernelCollapsed = useStudioPreferenceStore((state) => state.setKernelCollapsed);
    const activeDrawingTool = useStudioSelectionStore((state) => state.activeDrawingTool);
    const setActiveDrawingTool = useStudioSelectionStore((state) => state.setActiveDrawingTool);
    const drawings = useStudioSelectionStore((state) => state.drawings);
    const setDrawings = useStudioSelectionStore((state) => state.setDrawings);
    const selectedPatterns = useStudioSelectionStore((state) => state.selectedPatterns);
    const setSelectedPatterns = useStudioSelectionStore((state) => state.setSelectedPatterns);
    const layoutPreset = useStudioPreferenceStore((state) => state.layoutPreset);
    const setLayoutPreset = useStudioPreferenceStore((state) => state.setLayoutPreset);
    const customOverlays = useStudioSelectionStore((state) => state.customOverlays);
    const setCustomOverlays = useStudioSelectionStore((state) => state.setCustomOverlays);
    const activeIndicators = useStudioSelectionStore((state) => state.activeIndicators);
    const setActiveIndicators = useStudioSelectionStore((state) => state.setActiveIndicators);
    const hydrateSelections = useStudioSelectionStore((state) => state.hydrateSelections);
    const clearDrawings = useStudioSelectionStore((state) => state.clearDrawings);
    const showLayoutManager = useStudioLayoutStore((state) => state.showLayoutManager);
    const setShowLayoutManager = useStudioLayoutStore((state) => state.setShowLayoutManager);
    const syncSettings = useStudioPreferenceStore((state) => state.syncSettings);
    const setSyncSettings = useStudioPreferenceStore((state) => state.setSyncSettings);
    
    const slippageBps = useStudioWorkspaceStore((state) => state.slippageBps);
    const setSlippageBps = useStudioWorkspaceStore((state) => state.setSlippageBps);
    const commissionPct = useStudioWorkspaceStore((state) => state.commissionPct);
    const setCommissionPct = useStudioWorkspaceStore((state) => state.setCommissionPct);
    const showIndicatorSelect = useStudioWorkspaceStore((state) => state.showIndicatorSelect);
    const setShowIndicatorSelect = useStudioWorkspaceStore((state) => state.setShowIndicatorSelect);
    const analysisComplete = useStudioResultStore((state) => state.analysisComplete);
    const setAnalysisComplete = useStudioResultStore((state) => state.setAnalysisComplete);
    const benchmarkData = useStudioResultStore((state) => state.benchmarkData);
    const setBenchmarkData = useStudioResultStore((state) => state.setBenchmarkData);
    const dataLoading = useStudioResultStore((state) => state.dataLoading);
    const setDataLoading = useStudioResultStore((state) => state.setDataLoading);
    const dataError = useStudioResultStore((state) => state.dataError);
    const setDataError = useStudioResultStore((state) => state.setDataError);
    const gridLoading = useStudioResultStore((state) => state.gridLoading);
    const setGridLoading = useStudioResultStore((state) => state.setGridLoading);
    const gridError = useStudioResultStore((state) => state.gridError);
    const setGridError = useStudioResultStore((state) => state.setGridError);

    const gridConfig = useStudioLayoutStore((state) => state.gridConfig);
    const setGridConfig = useStudioLayoutStore((state) => state.setGridConfig);
    const layoutInitState = useStudioLayoutStore((state) => state.layoutInitState);
    const startLayout = useStudioLayoutStore((state) => state.startLayoutInitialization);
    const addTickerToLayout = useStudioLayoutStore((state) => state.addTickerToLayout);
    const resetLayoutInitialization = useStudioLayoutStore((state) => state.resetLayoutInitialization);

    const gridData = useStudioResultStore((state) => state.gridData);
    const setGridData = useStudioResultStore((state) => state.setGridData);

    const startLayoutInitialization = useCallback((layoutId) => {
        startLayout(layoutId, ticker || 'SPY');
    }, [startLayout, ticker]);
    
    const data = useStudioResultStore((state) => state.data);
    const setData = useStudioResultStore((state) => state.setData);
    const previousEquityCurve = useStudioResultStore((state) => state.previousEquityCurve);
    const setPreviousEquityCurve = useStudioResultStore((state) => state.setPreviousEquityCurve);
    const previousSignals = useStudioResultStore((state) => state.previousSignals);
    const setPreviousSignals = useStudioResultStore((state) => state.setPreviousSignals);
    const mcLoading = useStudioResultStore((state) => state.mcLoading);
    const setMcLoading = useStudioResultStore((state) => state.setMcLoading);
    const mcError = useStudioResultStore((state) => state.mcError);
    const setMcError = useStudioResultStore((state) => state.setMcError);
    const wfLoading = useStudioResultStore((state) => state.wfLoading);
    const setWfLoading = useStudioResultStore((state) => state.setWfLoading);
    const wfError = useStudioResultStore((state) => state.wfError);
    const setWfError = useStudioResultStore((state) => state.setWfError);
    
    const playIntervalRef = useRef(null);
    const executionControllerRef = useRef(null);

    useEffect(() => {
        hydrateDrafts();
    }, [hydrateDrafts]);

    useEffect(() => {
        hydrateSelections();
    }, [hydrateSelections]);

    useEffect(() => () => executionControllerRef.current?.abort(), []);

    // When strategy changes, update code
    const handleStrategyChange = (strat) => {
        applyStrategy(strat);
        setAnalysisComplete(false);
    };

    const addIndicator = useCallback((config) => {
        setActiveIndicators(prev => [...prev, config]);
    }, [setActiveIndicators]);

    const removeIndicator = useCallback((id) => {
        setActiveIndicators(prev => prev.filter(i => i.id !== id));
    }, [setActiveIndicators]);

    const toggleIndicator = useCallback((id) => {
        setActiveIndicators(prev => prev.map(i => i.id === id ? { ...i, visible: !i.visible } : i));
    }, [setActiveIndicators]);


    // Calculate Volume Profile (Volume at Price)
    const calculateVolumeProfile = useCallback((candles) => {
        if (!candles || candles.length === 0) return [];
        
        const prices = candles.map(c => c.close);
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        const priceRange = maxPrice - minPrice;
        const numBuckets = 30;
        if (priceRange <= 0) {
            const volume = candles.reduce((total, candle) => total + candle.volume, 0);
            return [{ priceLevel: minPrice, volume, normalized: volume > 0 ? 1 : 0 }];
        }
        const bucketSize = priceRange / numBuckets;
        
        const profile = Array(numBuckets).fill(0).map((_, i) => ({
            priceLevel: minPrice + bucketSize * i + bucketSize / 2,
            volume: 0
        }));
        
        candles.forEach(c => {
            const bucketIdx = Math.min(Math.floor((c.close - minPrice) / bucketSize), numBuckets - 1);
            if (bucketIdx >= 0 && bucketIdx < numBuckets) {
                profile[bucketIdx].volume += c.volume;
            }
        });
        
        const maxVol = Math.max(...profile.map(p => p.volume));
        return profile.map(p => ({ ...p, normalized: maxVol > 0 ? p.volume / maxVol : 0 }));
    }, []);

    const fetchData = useCallback(async (currentTicker, signal) => {
        if (!currentTicker) {
            setData({ candles: [], signals: [], metrics: {}, trades: [], equityCurve: [] });
            setDataLoading(false);
            setDataError(null);
            return;
        }
        setDataLoading(true);
        setDataError(null);
        try {
            const resData = await studioRequest(`/data?ticker=${encodeURIComponent(currentTicker)}&lookback_years=10`, {
                signal,
                validate: isStudioDataResponse,
            });
            if (resData.status === 'success') {
                setData(prev => ({
                    ...prev,
                    candles: resData.candles || [],
                    signals: [],
                    metrics: {},
                    trades: [],
                    equityCurve: [],
                    metadata: resData.metadata || null,
                    volumeProfile: calculateVolumeProfile(resData.candles || [])
                }));
                setPlayIndex(0);
                setAnalysisComplete(false);
            }
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') return;
            console.error("Data fetch failed:", e);
            setDataError(e instanceof Error ? e.message : 'Market data request failed.');
        } finally {
            if (!signal?.aborted) setDataLoading(false);
        }
    }, [calculateVolumeProfile, setAnalysisComplete, setData, setDataError, setDataLoading, setPlayIndex]);

    const retryData = useCallback(() => fetchData(ticker), [fetchData, ticker]);

    // Fetch benchmark data for ghosting
    const fetchBenchmark = useCallback(async (benchmarkTicker, signal) => {
        if (!benchmarkTicker) return;
        try {
            const resData = await studioRequest(`/data?ticker=${encodeURIComponent(benchmarkTicker)}&lookback_years=10`, {
                signal,
                validate: isStudioDataResponse,
            });
            if (resData.status === 'success') {
                setBenchmarkData(resData.candles || []);
            }
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') return;
            console.error("Benchmark fetch failed:", e);
        }
    }, [setBenchmarkData]);

    const fetchGridDataBatch = useCallback(async (tickers, signal) => {
        if (!tickers || tickers.length === 0) return;
        setGridLoading(true);
        setGridError(null);
        try {
            const results = await Promise.all(tickers.map(async (t) => {
                const resData = await studioRequest(`/data?ticker=${encodeURIComponent(t)}&lookback_years=10`, {
                    signal,
                    validate: isStudioDataResponse,
                });
                if (resData.status === 'success') {
                    return {
                        candles: resData.candles || [],
                        signals: [],
                        metrics: {},
                        trades: [],
                        equityCurve: [],
                        volumeProfile: calculateVolumeProfile(resData.candles || [])
                    };
                }
                return null;
            }));
            setGridData(results);
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') return;
            console.error("Grid data fetch failed:", e);
            setGridError(e instanceof Error ? e.message : 'Grid market data request failed.');
        } finally {
            if (!signal?.aborted) setGridLoading(false);
        }
    }, [calculateVolumeProfile, setGridData, setGridError, setGridLoading]);

    const retryGridData = useCallback(
        () => fetchGridDataBatch(gridConfig.tickers),
        [fetchGridDataBatch, gridConfig.tickers],
    );

    useEffect(() => {
        if (gridConfig.layoutId !== '1x1' && gridConfig.tickers.length > 0) {
            const controller = new AbortController();
            const frame = requestAnimationFrame(() => fetchGridDataBatch(gridConfig.tickers, controller.signal));
            return () => {
                cancelAnimationFrame(frame);
                controller.abort();
            };
        }
    }, [gridConfig.tickers, gridConfig.layoutId, fetchGridDataBatch]);

    useEffect(() => {
        if (ticker) {
            const controller = new AbortController();
            const frame = requestAnimationFrame(() => fetchData(ticker, controller.signal));
            return () => {
                cancelAnimationFrame(frame);
                controller.abort();
            };
        }
    }, [ticker, fetchData]);

    useEffect(() => {
        if (benchmark && benchmark !== ticker) {
            const controller = new AbortController();
            const frame = requestAnimationFrame(() => fetchBenchmark(benchmark, controller.signal));
            return () => {
                cancelAnimationFrame(frame);
                controller.abort();
            };
        }
    }, [benchmark, ticker, fetchBenchmark]);

    // Show indicator selection before execute
    const promptExecute = useCallback(() => {
        setShowIndicatorSelect(true);
    }, [setShowIndicatorSelect]);

    // Animated playback after execution - refined for "Slow-Mo" tick-based governance
    const startPlayback = useCallback((totalCandles, speed = 20) => {
        if (playIntervalRef.current) clearInterval(playIntervalRef.current);
        
        setPlayIndex(0);
        setIsPlaying(true);
        setAnalysisComplete(false);
        
        let idx = 0;
        // Speed is usually 5-100. 100 = slowest (large delay), 5 = fastest (small delay)
        // We'll use speed as the interval ms directly, but with a floor
        const intervalMs = speed;
        
        const interval = setInterval(() => {
            idx += 1; // Single tick for high-fidelity slow-mo
            if (idx >= totalCandles - 1) {
                idx = totalCandles - 1;
                setPlayIndex(idx);
                setIsPlaying(false);
                setAnalysisComplete(true);
                clearInterval(interval);
            } else {
                setPlayIndex(idx);
            }
        }, intervalMs);
        
        playIntervalRef.current = interval;
    }, [setAnalysisComplete, setIsPlaying, setPlayIndex]);


    const executeStrategy = useCallback(async () => {
        const primaryCode = codeA;
        if (!primaryCode) return;

        executionControllerRef.current?.abort();
        const executionController = new AbortController();
        executionControllerRef.current = executionController;
        
        setKernelCollapsed(true);
        setShowIndicatorSelect(false);
        setIsExecuting(true);
        setExecutionError(null);
        setIsPlaying(false);
        setPlayIndex(0);
        setAnalysisComplete(false);

        if (data.equityCurve?.length > 0) {
            setPreviousEquityCurve([...data.equityCurve]);
        }
        if (data.signals?.length > 0) {
            setPreviousSignals([...data.signals]);
        }
        
        if (playIntervalRef.current) {
            clearInterval(playIntervalRef.current);
        }
        
        try {
            // Helper for individual execution
            const runExecRequest = async (c, t) => {
                return studioRequest('/execute', {
                    method: 'POST',
                    signal: executionController.signal,
                    validate: isStudioExecutionResponse,
                    body: {
                        code: c,
                        ticker: t,
                        slippage_bps: slippageBps,
                        commission_pct: commissionPct,
                        universe: 'US_TOP50',
                        lookback_years: 10,
                        end_date: new Date().toISOString().split('T')[0]
                    }
                });
            };

            const processData = (res) => ({
                candles: res.candles || [],
                signals: res.signals || [],
                metrics: res.metrics || {},
                trades: res.trades || [],
                equityCurve: res.equity_curve || [],
                metadata: res.metadata || null,
                volumeProfile: calculateVolumeProfile(res.candles || [])
            });

            // If layout is '1', use standard flow
            if (gridConfig.layoutId === '1x1') {
                const resA = await runExecRequest(codeA, ticker || 'SPY');
                let resB = null;
                if (vsModeActive) {
                    resB = await runExecRequest(codeB, ticker || 'SPY');
                }

                if (resA.status === 'success') {
                    const formattedA = processData(resA);
                    setDataA(formattedA);
                    setData(formattedA);
                    
                    if (resB && resB.status === 'success') {
                        setDataB(processData(resB));
                    }

                    if (formattedA.candles.length > 0) {
                        startPlayback(formattedA.candles.length, playSpeed);
                        return;
                    }
                }
            } else {
                // Multi-ticker grid execution
                const resultsA = await Promise.all(gridConfig.tickers.map(t => runExecRequest(codeA, t)));
                const formattedA = resultsA.map(res => res.status === 'success' ? processData(res) : null);

                let formattedB = [];
                if (vsModeActive) {
                    const resultsB = await Promise.all(gridConfig.tickers.map(t => runExecRequest(codeB, t)));
                    formattedB = resultsB.map(res => res.status === 'success' ? processData(res) : null);
                    setGridDataB(formattedB);
                    setGridVsView('A');
                } else {
                    setGridDataB([]);
                }

                setGridDataA(formattedA);
                setGridData(vsModeActive ? formattedA : formattedA);
                
                // Use first chart as the master for playback
                const master = (vsModeActive ? formattedA : formattedA)[0];
                if (master && master.candles.length > 0) {
                    setData(master); 
                    startPlayback(master.candles.length, playSpeed);
                    return;
                }
            }
        } catch (e) {
            if (e?.code === 'STUDIO_CANCELLED') {
                if (executionControllerRef.current === executionController) {
                    setExecutionError('Stopped waiting for this run. The isolated runner may finish before its server timeout.');
                }
            } else {
                console.error("Execution failed:", e);
                setExecutionError(e instanceof Error ? e.message : 'Strategy execution failed.');
            }
        } finally {
            if (executionControllerRef.current === executionController) {
                executionControllerRef.current = null;
                setIsExecuting(false);
            }
        }
    }, [codeA, codeB, vsModeActive, ticker, slippageBps, commissionPct, playSpeed, startPlayback, data.equityCurve, data.signals, calculateVolumeProfile, gridConfig.layoutId, gridConfig.tickers, setAnalysisComplete, setData, setDataA, setDataB, setExecutionError, setGridData, setGridDataA, setGridDataB, setGridVsView, setIsExecuting, setIsPlaying, setKernelCollapsed, setPlayIndex, setPreviousEquityCurve, setPreviousSignals, setShowIndicatorSelect]);

    const cancelExecution = useCallback(() => {
        executionControllerRef.current?.abort();
        setIsExecuting(false);
        setExecutionError('Stopped waiting for this run. The isolated runner may finish before its server timeout.');
    }, [setExecutionError, setIsExecuting]);



    const stopPlayback = useCallback(() => {
        if (playIntervalRef.current) {
            clearInterval(playIntervalRef.current);
        }
        setIsPlaying(false);
    }, [setIsPlaying]);

    const runMonteCarlo = useCallback(async (simulations = 10000) => {
        if (data.equityCurve.length < 20) {
            setMcError('Execute a strategy with at least 20 equity observations before simulation.');
            return;
        }
        setMcLoading(true);
        setMcError(null);
        const rets = data.equityCurve.slice(1).map((v, i) => (v - data.equityCurve[i]) / data.equityCurve[i]);
        try {
            const resData = await studioRequest('/monte-carlo', {
                method: 'POST',
                validate: isStudioMonteCarloResponse,
                body: { returns: rets, simulations, time_horizon: 252 }
            });
            if (resData.status === 'success') setData(prev => ({ ...prev, mcData: resData }));
        } catch (e) {
            console.error("Monte Carlo failed:", e);
            setData(prev => ({ ...prev, mcData: null }));
            setMcError(e instanceof Error ? e.message : 'Monte Carlo simulation failed.');
        } finally {
            setMcLoading(false);
        }
    }, [data.equityCurve, setData, setMcError, setMcLoading]);

    const runWalkForward = useCallback(async (nFolds = 5) => {
        if (data.equityCurve.length < 100) {
            setWfError('Execute a strategy with at least 100 equity observations before validation.');
            return;
        }
        setWfLoading(true);
        setWfError(null);
        const returns = data.equityCurve.slice(1).map(
            (value, index) => (value - data.equityCurve[index]) / data.equityCurve[index]
        );
        try {
            const resData = await studioRequest('/walk-forward', {
                method: 'POST',
                validate: isStudioWalkForwardResponse,
                body: {
                    returns,
                    n_folds: nFolds,
                    oos_days: 20
                }
            });
            setData(prev => ({ ...prev, wfData: resData }));
        } catch (e) {
            console.error("Walk-Forward failed:", e);
            setData(prev => ({ ...prev, wfData: null }));
            setWfError(e instanceof Error ? e.message : 'Walk-forward validation failed.');
        } finally {
            setWfLoading(false);
        }
    }, [data.equityCurve, setData, setWfError, setWfLoading]);

    return (
        <StudioContext.Provider value={{
            activeTab, setActiveTab,
            ticker, setTicker,
            benchmark, setBenchmark,
            benchmarkData,
            dataLoading, dataError, retryData,
            gridLoading, gridError, retryGridData,
            selectedStrategy, setSelectedStrategy,
            codeA, setCodeA,
            codeB, setCodeB,
            vsModeActive, setVsModeActive,
            hoverSnapshot, setHoverSnapshot,
            dataA, dataB,
            gridDataA, setGridDataA,
            gridDataB, setGridDataB,
            gridVsView, setGridVsView,
            isExecuting, executionError, setExecutionError, executeStrategy, cancelExecution, promptExecute,
            isPlaying, setIsPlaying, stopPlayback,
            playIndex, setPlayIndex,
            playSpeed, setPlaySpeed,
            showLayoutManager, setShowLayoutManager,
            kernelCollapsed, setKernelCollapsed,
            slippageBps, setSlippageBps,
            commissionPct, setCommissionPct,
            data, setData,
            mcLoading, mcError, runMonteCarlo,
            wfLoading, wfError, runWalkForward,
            analysisComplete, setAnalysisComplete,
            activeDrawingTool, setActiveDrawingTool,
            drawings, setDrawings, clearDrawings,
            selectedPatterns, setSelectedPatterns,
            layoutPreset, setLayoutPreset,
            syncSettings, setSyncSettings,
            customOverlays, setCustomOverlays,
            activeIndicators, setActiveIndicators,
            addIndicator, removeIndicator, toggleIndicator,
            showIndicatorSelect, setShowIndicatorSelect,
            handleStrategyChange,
            previousEquityCurve, setPreviousEquityCurve,
            previousSignals, setPreviousSignals,
            // Grid Layout System
            gridConfig, setGridConfig,
            layoutInitState,
            gridData, setGridData,
            startLayoutInitialization,
            addTickerToLayout,
            resetLayoutInitialization
        }}>
            {children}
        </StudioContext.Provider>
    );
};

export const useStudio = () => useContext(StudioContext);
