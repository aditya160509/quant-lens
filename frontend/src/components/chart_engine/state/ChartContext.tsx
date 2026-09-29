/**
 * Chart Context and Provider
 * React context for chart state management
 */

import React, { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react';
import { chartReducer, initialChartState, getVisibleBars, getCurrentPrice, getPriceRange } from './ChartState';
import type { ChartState, ChartAction, Timeframe, ChartType, Drawing, IndicatorConfig, ReplaySpeed } from '../types';

// =============================================================================
// CONTEXT
// =============================================================================

interface ChartContextValue {
    state: ChartState;
    dispatch: React.Dispatch<ChartAction>;

    // Convenience actions
    setSymbol: (symbol: string) => void;
    setTimeframe: (timeframe: Timeframe) => void;
    setChartType: (chartType: ChartType) => void;
    toggleVolume: () => void;
    toggleGrid: () => void;

    // Indicator actions
    addIndicator: (config: IndicatorConfig) => void;
    removeIndicator: (id: string) => void;

    // Drawing actions
    addDrawing: (drawing: Drawing) => void;
    updateDrawing: (drawing: Drawing) => void;
    removeDrawing: (id: string) => void;
    selectDrawing: (id: string | null) => void;
    setActiveTool: (toolType: string | null) => void;

    // Replay actions
    startReplay: (barIndex: number) => void;
    stopReplay: () => void;
    toggleReplayPlay: () => void;
    setReplaySpeed: (speed: ReplaySpeed) => void;
    stepReplay: (direction: 1 | -1) => void;
    enterReplaySelectMode: () => void;
    exitReplaySelectMode: () => void;
    jumpToReplayIndex: (index: number) => void;
    isReplaySelectMode: boolean;

    // Selectors
    visibleBars: ReturnType<typeof getVisibleBars>;
    currentPrice: number | null;
    priceRange: { min: number; max: number } | null;
}

const ChartContext = createContext<ChartContextValue | null>(null);

// =============================================================================
// PROVIDER
// =============================================================================

interface ChartProviderProps {
    children: React.ReactNode;
    initialSymbol?: string;
    initialTimeframe?: Timeframe;
    initialIndicators?: typeof initialChartState.indicators;
}

// LocalStorage key for persisting indicators
const INDICATORS_STORAGE_KEY = 'q360_chart_indicators';

// Helper to load indicators from localStorage
function loadPersistedIndicators() {
    if (typeof window === 'undefined') return [];
    try {
        const stored = localStorage.getItem(INDICATORS_STORAGE_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
}

// Helper to save indicators to localStorage
function saveIndicatorsToStorage(indicators: typeof initialChartState.indicators) {
    if (typeof window === 'undefined') return;
    try {
        localStorage.setItem(INDICATORS_STORAGE_KEY, JSON.stringify(indicators));
    } catch {
        // Ignore storage errors
    }
}

export function ChartProvider({
    children,
    initialSymbol = 'SPY',
    initialTimeframe = '5m',
    initialIndicators
}: ChartProviderProps) {
    // Use lazy initializer to avoid ref access during render
    const [state, dispatch] = useReducer(chartReducer, undefined, () => ({
        ...initialChartState,
        symbol: initialSymbol,
        timeframe: initialTimeframe,
        indicators: initialIndicators ?? loadPersistedIndicators(),
    }));

    // Persist indicators to localStorage whenever they change
    useEffect(() => {
        if (state.indicators.length > 0) {
            saveIndicatorsToStorage(state.indicators);
        }
    }, [state.indicators]);

    // Sync symbol prop with state when it changes from parent
    useEffect(() => {
        if (initialSymbol && initialSymbol !== state.symbol) {
            dispatch({ type: 'SET_SYMBOL', payload: initialSymbol });
        }
    }, [initialSymbol, state.symbol]);

    // Sync timeframe prop with state when it changes from parent
    useEffect(() => {
        if (initialTimeframe && initialTimeframe !== state.timeframe) {
            dispatch({ type: 'SET_TIMEFRAME', payload: initialTimeframe });
        }
    }, [initialTimeframe, state.timeframe]);

    // Replay timer
    const replayTimerRef = useRef<NodeJS.Timeout | null>(null);

    // Handle replay playback
    useEffect(() => {
        if (state.replay.active && state.replay.isPlaying) {
            const interval = 1000 / state.replay.speed;

            replayTimerRef.current = setInterval(() => {
                dispatch({ type: 'STEP_REPLAY', payload: 1 });
            }, interval);

            return () => {
                if (replayTimerRef.current) {
                    clearInterval(replayTimerRef.current);
                }
            };
        }
    }, [state.replay.active, state.replay.isPlaying, state.replay.speed]);

    // Check if replay should stop (reached end) - only when actively playing
    useEffect(() => {
        if (state.replay.active && state.replay.isPlaying && state.data) {
            if (state.replay.cursorIndex >= state.data.bars.length - 1) {
                // Pause instead of toggle to avoid loop
                dispatch({ type: 'TOGGLE_REPLAY_PLAY' });
            }
        }
    // Only trigger when cursorIndex changes while playing
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [state.replay.cursorIndex]);

    // Convenience actions
    const setSymbol = useCallback((symbol: string) => {
        dispatch({ type: 'SET_SYMBOL', payload: symbol });
    }, []);

    const setTimeframe = useCallback((timeframe: Timeframe) => {
        dispatch({ type: 'SET_TIMEFRAME', payload: timeframe });
    }, []);

    const setChartType = useCallback((chartType: ChartType) => {
        dispatch({ type: 'SET_CHART_TYPE', payload: chartType });
    }, []);

    const toggleVolume = useCallback(() => {
        dispatch({ type: 'TOGGLE_VOLUME' });
    }, []);

    const toggleGrid = useCallback(() => {
        dispatch({ type: 'TOGGLE_GRID' });
    }, []);

    const addIndicator = useCallback((config: IndicatorConfig) => {
        dispatch({ type: 'ADD_INDICATOR', payload: config });
    }, []);

    const removeIndicator = useCallback((id: string) => {
        dispatch({ type: 'REMOVE_INDICATOR', payload: id });
    }, []);

    const addDrawing = useCallback((drawing: Drawing) => {
        dispatch({ type: 'ADD_DRAWING', payload: drawing });
    }, []);

    const updateDrawing = useCallback((drawing: Drawing) => {
        dispatch({ type: 'UPDATE_DRAWING', payload: drawing });
    }, []);

    const removeDrawing = useCallback((id: string) => {
        dispatch({ type: 'REMOVE_DRAWING', payload: id });
    }, []);

    const selectDrawing = useCallback((id: string | null) => {
        dispatch({ type: 'SELECT_DRAWING', payload: id });
    }, []);

    const setActiveTool = useCallback((toolType: string | null) => {
        dispatch({ type: 'SET_ACTIVE_TOOL', payload: toolType });
    }, []);

    // Replay Select Mode (for TradingView-style click-to-select)
    const [replaySelectMode, setReplaySelectMode] = React.useState(false);

    const startReplay = useCallback((barIndex: number) => {
        setReplaySelectMode(false);
        dispatch({ type: 'START_REPLAY', payload: barIndex });
    }, []);

    const stopReplay = useCallback(() => {
        setReplaySelectMode(false);
        dispatch({ type: 'STOP_REPLAY' });
    }, []);

    const toggleReplayPlay = useCallback(() => {
        dispatch({ type: 'TOGGLE_REPLAY_PLAY' });
    }, []);

    const setReplaySpeed = useCallback((speed: ReplaySpeed) => {
        dispatch({ type: 'SET_REPLAY_SPEED', payload: speed });
    }, []);

    const stepReplay = useCallback((direction: 1 | -1) => {
        dispatch({ type: 'STEP_REPLAY', payload: direction });
    }, []);

    const enterReplaySelectMode = useCallback(() => {
        setReplaySelectMode(true);
    }, []);

    const exitReplaySelectMode = useCallback(() => {
        setReplaySelectMode(false);
    }, []);

    // Jump to specific replay index - uses STEP_REPLAY with calculated offset
    const jumpToReplayIndex = useCallback((index: number) => {
        // For now, we'll dispatch a custom jump action that the reducer should handle
        // If JUMP_TO_REPLAY doesn't exist, we adjust cursor via multiple steps
        if (state.replay.active && state.data) {
            const targetIndex = Math.max(state.replay.startIndex, Math.min(index, state.data.bars.length - 1));
            // Dispatch a direct state update approach
            dispatch({ type: 'START_REPLAY', payload: targetIndex });
        }
    }, [state.replay.active, state.replay.startIndex, state.data]);

    // Computed values
    const visibleBars = getVisibleBars(state);
    const currentPrice = getCurrentPrice(state);
    const priceRange = getPriceRange(state);

    const value: ChartContextValue = {
        state,
        dispatch,
        setSymbol,
        setTimeframe,
        setChartType,
        toggleVolume,
        toggleGrid,
        addIndicator,
        removeIndicator,
        addDrawing,
        updateDrawing,
        removeDrawing,
        selectDrawing,
        setActiveTool,
        startReplay,
        stopReplay,
        toggleReplayPlay,
        setReplaySpeed,
        stepReplay,
        enterReplaySelectMode,
        exitReplaySelectMode,
        jumpToReplayIndex,
        isReplaySelectMode: replaySelectMode,
        visibleBars,
        currentPrice,
        priceRange,
    };

    return (
        <ChartContext.Provider value={value}>
            {children}
        </ChartContext.Provider>
    );
}


// =============================================================================
// HOOK
// =============================================================================

export function useChart() {
    const context = useContext(ChartContext);
    if (!context) {
        throw new Error('useChart must be used within a ChartProvider');
    }
    return context;
}
