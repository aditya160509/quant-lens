/**
 * Q360 Chart Core
 * TradingView-style professional chart with unified toolbar
 * 
 * FEATURES:
 * - Multi-chart grid layouts
 * - Compare symbol overlay
 * - TradingView-style symbol search
 * - Professional indicator panes
 * - Cache for loaded data
 */

'use client';

import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { ChartProvider, useChart } from './state/ChartContext';
import ChartCanvas from './ChartCanvas';
import DrawingToolbar from './DrawingToolbar';
import IndicatorMenu from './IndicatorMenu';
import IndicatorPaneRenderer from './IndicatorPaneRenderer';
import { getIndicator } from './IndicatorEngine/registry';
import { getSeries, getMockSeries } from './DataAdapter/intraday';
import { CustomIndicatorModal, useCustomIndicators } from '../trading/CustomIndicator';
import TradingViewSearch from '../symbols/TradingViewSearch';
import dynamic from 'next/dynamic';
import { WatchlistPanel } from '../watchlist/WatchlistPanel';
import { AlertManager } from './AlertEngine/AlertManager';
import { AlphaPanel } from '../watchlist/AlphaPanel';
import { PatternSelector, CANDLESTICK_PATTERNS, scanForPatterns } from './PatternScanner';
import { StrategySelector, TRADING_STRATEGIES, runStrategies } from './StrategyEngine';
import { Activity, LayoutGrid, Cpu } from 'lucide-react';

// Dynamically import MiniChart to avoid SSR issues with lightweight-charts
const MiniChart = dynamic(() => import('./MiniChart'), { 
    ssr: false, 
    loading: () => <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666', fontSize: 10 }}>Loading...</div>
});
import {
    type Q360ChartCoreProps,
    type OHLCVBar,
    type Timeframe,
    type ChartType,
    CHART_THEME,
    type IndicatorConfig
} from './types';

// =============================================================================
// TIMEFRAME OPTIONS
// =============================================================================

const TIMEFRAMES: { value: Timeframe; label: string }[] = [
    { value: '1m', label: '1m' },
    { value: '5m', label: '5m' },
    { value: '15m', label: '15m' },
    { value: '30m', label: '30m' },
    { value: '1h', label: '1H' },
    { value: '3mo', label: '3M' },
    { value: '6mo', label: '6M' },
    { value: '1y', label: '1Y' },
    { value: '2y', label: '2Y' },
    { value: '5y', label: '5Y' },
];

const CHART_TYPES: { value: ChartType; label: string }[] = [
    // Standard OHLC Types
    { value: 'candlestick', label: 'Candles' },
    { value: 'hollowCandle', label: 'Hollow Candles' },
    { value: 'volumeCandles', label: 'Volume Candles' },
    { value: 'bars', label: 'Bars' },
    { value: 'heikinAshi', label: 'Heikin Ashi' },
    // Line Types
    { value: 'line', label: 'Line' },
    { value: 'lineWithMarkers', label: 'Line w/ Markers' },
    { value: 'stepLine', label: 'Step Line' },
    // Area Types
    { value: 'area', label: 'Area' },
    { value: 'hlcArea', label: 'HLC Area' },
    { value: 'baseline', label: 'Baseline' },
    // Non-Time Based (Synthetic)
    { value: 'renko', label: 'Renko' },
    { value: 'kagi', label: 'Kagi' },
    { value: 'pointAndFigure', label: 'Point & Figure' },
    { value: 'rangeBars', label: 'Range' },
    { value: 'lineBreak', label: 'Line Break' },
];

// All TradingView layout patterns
const LAYOUT_OPTIONS = [
    { id: '1', label: '1', grid: [[1]] },
    { id: '2h', label: '2H', grid: [[1], [1]] },
    { id: '2v', label: '2V', grid: [[1, 1]] },
    { id: '3h', label: '3H', grid: [[1], [1], [1]] },
    { id: '3v', label: '3V', grid: [[1, 1, 1]] },
    { id: '3l', label: '3L', grid: [[1, 1], [2, 2]] },  // 1 large left, 2 stacked right
    { id: '3r', label: '3R', grid: [[1, 1], [1, 1]] },  // 1 large right, 2 stacked left
    { id: '4', label: '4', grid: [[1, 1], [1, 1]] },
    { id: '5', label: '5', grid: [[1, 1, 1], [1, 1, 1]] },
    { id: '6', label: '6', grid: [[1, 1], [1, 1], [1, 1]] },
    { id: '8', label: '8', grid: [[1, 1, 1, 1], [1, 1, 1, 1]] },
] as const;

// Layout icon component - renders visual grid
function LayoutIcon({ layoutId, size = 14 }: { layoutId: string; size?: number }) {
    // Simple grid patterns based on layout
    const patterns: Record<string, { rows: number; cols: number }> = {
        '1': { rows: 1, cols: 1 },
        '2h': { rows: 2, cols: 1 },
        '2v': { rows: 1, cols: 2 },
        '3h': { rows: 3, cols: 1 },
        '3v': { rows: 1, cols: 3 },
        '3l': { rows: 2, cols: 2 },
        '3r': { rows: 2, cols: 2 },
        '4': { rows: 2, cols: 2 },
        '5': { rows: 2, cols: 3 },
        '6': { rows: 3, cols: 2 },
        '8': { rows: 2, cols: 4 },
    };
    
    const pattern = patterns[layoutId] || { rows: 1, cols: 1 };
    
    return (
        <div 
            style={{ 
                display: 'grid', 
                gridTemplateRows: `repeat(${pattern.rows}, 1fr)`, 
                gridTemplateColumns: `repeat(${pattern.cols}, 1fr)`, 
                gap: 1, 
                width: size, 
                height: size 
            }}
        >
            {Array.from({ length: pattern.rows * pattern.cols }).map((_, i) => (
                <div key={i} style={{ background: CHART_THEME.textSecondary, borderRadius: 1 }} />
            ))}
        </div>
    );
}

// =============================================================================
// INNER CHART COMPONENT
// =============================================================================

function ChartInner({
    height = 500,
    width,
    onSymbolChange,
    onTimeframeChange,
    onIndicatorsChange,
    isMemberOfGrid = false,
    syncedCrosshairTimestamp,
    onCrosshairMove,
}: Omit<Q360ChartCoreProps, 'symbol' | 'timeframe' | 'mode' | 'session' | 'onBarClick' | 'onDataLoad' | 'replayActive' | 'replayCursorIndex' | 'replaySelectMode'>) {
    const { 
        state, 
        dispatch, 
        setTimeframe, 
        setChartType, 
        toggleVolume, 
        toggleGrid, 
        startReplay, 
        stopReplay, 
        toggleReplayPlay,
        setReplaySpeed,
        stepReplay,
        enterReplaySelectMode,
        exitReplaySelectMode,
        isReplaySelectMode,
        addIndicator, 
        removeIndicator 
    } = useChart();
    
    const { customIndicators, addIndicator: addCustomIndicator } = useCustomIndicators();
    const [showCustomIndicatorModal, setShowCustomIndicatorModal] = useState(false);
    
    const [measuredWidth, setMeasuredWidth] = useState(typeof width === 'number' ? width : 800);
    const [measuredHeight, setMeasuredHeight] = useState(typeof height === 'number' ? height : 600);
    const effectiveWidth = typeof width === 'number' ? width : measuredWidth;
    const effectiveHeight = typeof height === 'number' ? height : measuredHeight;

    const [hoveredBar, setHoveredBar] = useState<OHLCVBar | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    // Layout state
    const [currentLayout, setCurrentLayout] = useState<string>('1');
    const [showLayoutMenu, setShowLayoutMenu] = useState(false);
    const [blockingMessage, setBlockingMessage] = useState<string | null>(null);
    
    // Multi-chart symbols for grid layout
    const [gridSymbols, setGridSymbols] = useState<string[]>([state.symbol]);
    
    // Compare symbol overlay (max 2 symbols)
    const [compareSymbols, setCompareSymbols] = useState<string[]>([]);
    const [showCompareSearch, setShowCompareSearch] = useState(false);
    
    // Symbol search modal for multi-chart layouts  
    const [showSymbolSearch, setShowSymbolSearch] = useState(false);
    const [pendingLayout, setPendingLayout] = useState<string | null>(null);
    
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [rightPanel, setRightPanel] = useState<'watchlist' | 'alerts' | 'alpha' | null>(null);
    const [anchorIndex, setAnchorIndex] = useState(0);
    const [alphaMode, setAlphaMode] = useState<'percent' | 'zscore' | 'ratio'>('percent');
    const [visibleGhosts, setVisibleGhosts] = useState<string[]>([]);
    
    // Pattern Scanner state
    const [showPatternSelector, setShowPatternSelector] = useState(false);
    const [selectedPatterns, setSelectedPatterns] = useState<string[]>([]);
    const [detectedPatterns, setDetectedPatterns] = useState<ReturnType<typeof scanForPatterns>>([]);
    
    // Strategy Engine state
    const [showStrategySelector, setShowStrategySelector] = useState(false);
    const [selectedStrategies, setSelectedStrategies] = useState<string[]>([]);
    const [strategyParams, setStrategyParams] = useState<Record<string, Record<string, number>>>({});
    const [strategySignals, setStrategySignals] = useState<Map<string, ReturnType<typeof runStrategies> extends Map<string, infer T> ? T : never>>(new Map());
    
    // Data cache for symbols (avoid refetching)
    const dataCacheRef = React.useRef<Map<string, { bars: OHLCVBar[], timeframe: Timeframe }>>(new Map());
    
    // Indicator pane height (resizable)
    const [indicatorPaneHeight, setIndicatorPaneHeight] = useState(150);

    // Synchronize visible range for oscillators
    const visibleRange = useMemo(() => {
        const fullBars = state.data?.bars || [];
        // Support Replay: Use cursor index if replay is active
        const totalBars = state.replay.active 
            ? Math.min(fullBars.length, state.replay.cursorIndex + 1) 
            : fullBars.length;
            
        if (totalBars === 0) return { startIndex: 0, endIndex: 0 };

        // Subtract 44 for toolbar and 60 for the axis width to match ChartCanvas exactly
        const availableWidth = effectiveWidth - 44 - 60;
        const baseBarsVisible = Math.min(totalBars, Math.max(50, Math.floor(availableWidth / 8)));
        const visibleCount = Math.max(20, Math.floor(baseBarsVisible / state.zoomLevel));
        
        const maxPanOffset = Math.max(0, totalBars - visibleCount);
        const clampedOffset = Math.max(0, Math.min(maxPanOffset, Math.floor(state.panOffset)));
        
        const startIdx = Math.max(0, totalBars - visibleCount - clampedOffset);
        const endIdx = Math.min(totalBars, startIdx + visibleCount);
        
        return { startIndex: startIdx, endIndex: Math.max(0, endIdx - 1) };
    }, [state.data?.bars, state.zoomLevel, state.panOffset, effectiveWidth, state.replay]);

    // Pane indicators (oscillators like RSI, MACD)
    const paneIndicators = useMemo(() => {
        return state.indicators.filter(ind => {
            const def = getIndicator(ind.type);
            return def?.placement === 'pane'; 
        });
    }, [state.indicators]);

    const paneOutputs = useMemo(() => {
        const outputs = new Map<string, any>();
        const fullBars = state.data?.bars || [];
        if (fullBars.length === 0) return outputs;

        // Support Replay: Indicators should only compute/show up to the current replay point
        const activeBars = state.replay.active 
            ? fullBars.slice(0, state.replay.cursorIndex + 1)
            : fullBars;

        paneIndicators.forEach(ind => {
            const def = getIndicator(ind.type);
            if (def) {
                outputs.set(ind.id, def.compute(activeBars, ind.params));
            }
        });
        return outputs;
    }, [paneIndicators, state.data?.bars, state.replay.active, state.replay.cursorIndex]);

    const handleAddIndicatorWrap = useCallback((config: IndicatorConfig) => {
        if (config.placement === 'pane' && state.config.showVolume) {
            setBlockingMessage("Please remove the Volume bars before adding an oscillator to maintain layout integrity. We recommend keeping only the essential indicators visible.");
            return;
        }
        addIndicator(config);
    }, [addIndicator, state.config.showVolume]);

    // Grid resizing state
    const [columnPercents, setColumnPercents] = useState<number[]>([]);
    const [rowPercents, setRowPercents] = useState<number[]>([]);

    const handleToggleVolumeWrap = useCallback(() => {
        if (!state.config.showVolume && paneIndicators.length > 0) {
            setBlockingMessage("Please remove all oscillators before enabling the Volume bars to maintain layout integrity.");
            return;
        }
        toggleVolume();
    }, [state.config.showVolume, paneIndicators.length, toggleVolume]);

    const handleMaximizePanel = useCallback((symbol: string) => {
        if (symbol !== state.symbol) {
            onSymbolChange(symbol);
        }
        setCurrentLayout('1');
        // Reset grid percents to default for next time we enter grid mode
        const cols = columnPercents.length;
        const rows = rowPercents.length;
        if (cols > 0) setColumnPercents(new Array(cols).fill(100 / cols));
        if (rows > 0) setRowPercents(new Array(rows).fill(100 / rows));
    }, [state.symbol, onSymbolChange, columnPercents.length, rowPercents.length]);

    const handleScreenshot = useCallback(() => {
        const chartElement = document.getElementById('q360-chart-area');
        if (!chartElement) return;

        // Find the main canvas
        const canvas = chartElement.querySelector('canvas');
        if (!canvas) return;

        try {
            // Create a temporary canvas to add watermark
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height;
            const tempCtx = tempCanvas.getContext('2d');
            if (!tempCtx) return;

            // Draw original chart
            tempCtx.drawImage(canvas, 0, 0);

            // Add Quant360 Watermark
            tempCtx.font = 'bold 20px "IBM Plex Mono", monospace';
            tempCtx.fillStyle = 'rgba(255, 214, 10, 0.4)';
            tempCtx.textAlign = 'right';
            tempCtx.fillText('QUANT360 TERMINAL', tempCanvas.width - 20, tempCanvas.height - 30);
            
            tempCtx.font = '12px "IBM Plex Mono", monospace';
            tempCtx.fillText(`${state.symbol} • ${state.timeframe.toUpperCase()} • ${new Date().toLocaleString()}`, tempCanvas.width - 20, tempCanvas.height - 15);

            const dataUrl = tempCanvas.toDataURL('image/png');
            const link = document.createElement('a');
            link.download = `Q360-${state.symbol}-${state.timeframe}-${new Date().getTime()}.png`;
            link.href = dataUrl;
            link.click();
        } catch (err) {
            console.error('Screenshot failed:', err);
        }
    }, [state.symbol, state.timeframe]);

    const handleExportCSV = useCallback(() => {
        if (!state.data?.bars) {
            alert('No data available to export');
            return;
        }

        const headers = ['Timestamp', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume'];
        const csvRows = [headers.join(',')];

        state.data.bars.forEach(b => {
            const row = [
                b.timestamp,
                new Date(b.timestamp).toISOString(),
                b.open.toFixed(4),
                b.high.toFixed(4),
                b.low.toFixed(4),
                b.close.toFixed(4),
                Math.round(b.volume)
            ];
            csvRows.push(row.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `Q360_Data_${state.symbol}_${state.timeframe}.csv`);
        link.click();
        URL.revokeObjectURL(url);
    }, [state.data, state.symbol, state.timeframe]);

    useEffect(() => {
        const layout = LAYOUT_OPTIONS.find(l => l.id === currentLayout);
        if (!layout) return;

        const rows = layout.grid.length;
        const cols = layout.grid[0]?.length || 1;

        setRowPercents(new Array(rows).fill(100 / rows));
        setColumnPercents(new Array(cols).fill(100 / cols));
    }, [currentLayout]);

// Sync main symbol with grid first slot
useEffect(() => {
    setGridSymbols(prev => {
        if (prev[0] === state.symbol) return prev;
        const next = [...prev];
        next[0] = state.symbol;
        return next;
    });
}, [state.symbol]);

    const prevIndicatorsRef = React.useRef<string>('');

    useEffect(() => {
        if (onIndicatorsChange && state.indicators) {
            const indicatorMap: Record<string, boolean> = {};
            state.indicators.forEach((ind) => {
                const key = ind.type.toLowerCase();
                indicatorMap[key] = ind.visible !== false;
            });
            
            const serialized = JSON.stringify(indicatorMap);
            if (serialized !== prevIndicatorsRef.current) {
                prevIndicatorsRef.current = serialized;
                onIndicatorsChange(indicatorMap);
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [state.indicators]);

    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                setMeasuredWidth(containerRef.current.offsetWidth);
                setMeasuredHeight(containerRef.current.offsetHeight);
            }
        };

        updateDimensions();
        
        // ResizeObserver is more reliable for grid layouts
        const observer = new ResizeObserver(updateDimensions);
        if (containerRef.current) {
            observer.observe(containerRef.current);
        }

        window.addEventListener('resize', updateDimensions);
        return () => {
            window.removeEventListener('resize', updateDimensions);
            observer.disconnect();
        };
    }, []);

    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            setError(null);

            try {
                let data;
                try {
                    data = await getSeries(state.symbol, state.timeframe);
                } catch {
                    console.log('Using mock data for development');
                    data = getMockSeries(state.symbol, state.timeframe);
                }

                dispatch({ type: 'SET_DATA', payload: data });
            } catch (err: any) {
                setError(err.message || 'Failed to load data');
            } finally {
                setIsLoading(false);
            }
        };

        fetchData();
    }, [state.symbol, state.timeframe, dispatch]);
    
    // State for compare symbol data
    const [compareData, setCompareData] = useState<Record<string, OHLCVBar[]>>({});
    
    // Fetch compare symbol data when compareSymbols changes
    useEffect(() => {
        const fetchCompareData = async () => {
            const newData: Record<string, OHLCVBar[]> = {};
            
            for (const symbol of compareSymbols) {
                // Check cache first
                const cacheKey = `${symbol}-${state.timeframe}`;
                const cached = dataCacheRef.current.get(cacheKey);
                if (cached) {
                    newData[symbol] = cached.bars;
                    continue;
                }
                
                try {
                    let data;
                    try {
                        data = await getSeries(symbol, state.timeframe);
                    } catch {
                        data = getMockSeries(symbol, state.timeframe);
                    }
                    newData[symbol] = data.bars;
                    // Store in cache
                    dataCacheRef.current.set(cacheKey, { bars: data.bars, timeframe: state.timeframe });
                } catch (err) {
                    console.error(`Failed to fetch compare data for ${symbol}:`, err);
                }
            }
            
            setCompareData(newData);
        };
        
        if (compareSymbols.length > 0) {
            fetchCompareData();
        } else {
            setCompareData({});
        }
    }, [compareSymbols, state.timeframe]);

    // Calculate visible bars for Alpha Panel synchronization
    const displayBars = useMemo(() => {
        const bars = state.data?.bars || [];
        const totalBars = bars.length;
        if (totalBars === 0) return [];

        const chartWidth = effectiveWidth - 44 - 60; // effectiveWidth - toolbar - price axis
        const baseBarsVisible = Math.min(totalBars, Math.max(50, Math.floor(chartWidth / 8)));
        const visibleCount = Math.max(20, Math.floor(baseBarsVisible / state.zoomLevel));

        const maxPanOffset = Math.max(0, totalBars - visibleCount);
        const clampedOffset = Math.max(0, Math.min(maxPanOffset, Math.floor(state.panOffset)));
        const startIdx = Math.max(0, totalBars - visibleCount - clampedOffset);
        const endIdx = Math.min(totalBars, startIdx + visibleCount);

        return bars.slice(startIdx, endIdx);
    }, [state.data?.bars, state.zoomLevel, state.panOffset, effectiveWidth]);
    
    // Switch to percent scaling mode automatically when comparison symbols are present
    useEffect(() => {
        if (compareSymbols.length > 0 && state.config.scaleMode !== 'percent') {
            dispatch({ type: 'SET_SCALE_MODE', payload: 'percent' });
        } else if (compareSymbols.length === 0 && state.config.scaleMode === 'percent') {
            dispatch({ type: 'SET_SCALE_MODE', payload: 'auto' });
        }
    }, [compareSymbols, state.config.scaleMode, dispatch]);
    
    // State for grid symbol data
    const [gridData, setGridData] = useState<Record<string, OHLCVBar[]>>({});
    
    // Fetch grid symbol data when gridSymbols changes
    useEffect(() => {
        const fetchGridData = async () => {
            const newData: Record<string, OHLCVBar[]> = {};
            
            for (const symbol of gridSymbols) {
                // Skip the main symbol - already fetched
                if (symbol === state.symbol) continue;
                
                // Check cache first
                const cacheKey = `${symbol}-${state.timeframe}`;
                const cached = dataCacheRef.current.get(cacheKey);
                if (cached) {
                    newData[symbol] = cached.bars;
                    continue;
                }
                
                try {
                    let data;
                    try {
                        data = await getSeries(symbol, state.timeframe);
                    } catch {
                        data = getMockSeries(symbol, state.timeframe);
                    }
                    newData[symbol] = data.bars;
                    // Store in cache
                    dataCacheRef.current.set(cacheKey, { bars: data.bars, timeframe: state.timeframe });
                } catch (err) {
                    console.error(`Failed to fetch grid data for ${symbol}:`, err);
                }
            }
            
            setGridData(newData);
        };
        
        if (gridSymbols.length > 1) {
            fetchGridData();
        }
    }, [gridSymbols, state.timeframe, state.symbol]);

    // =============================================================================
    // FIX: AUTO-TRIGGER PERCENT SCALE MODE FOR COMPARE OVERLAYS
    // Per CHART_WORKSPACE_TECHNICAL_AUDIT_REPORT.md Step 3
    // =============================================================================
    React.useEffect(() => {
        if (compareSymbols.length > 0 && state.config.scaleMode !== 'percent') {
            dispatch({ type: 'SET_SCALE_MODE', payload: 'percent' });
        } else if (compareSymbols.length === 0 && state.config.scaleMode === 'percent') {
            // Revert to auto when compare symbols removed
            dispatch({ type: 'SET_SCALE_MODE', payload: 'auto' });
        }
    }, [compareSymbols.length, state.config.scaleMode, dispatch]);

    const handleReplayClick = () => {
        if (state.replay.active) {
            stopReplay();
        } else if (isReplaySelectMode) {
            exitReplaySelectMode();
        } else {
            enterReplaySelectMode();
        }
    };

    // Calculate current bar info - show hovered bar or last bar
    const displayBar = useMemo(() => {
        if (hoveredBar) return hoveredBar;
        if (!state.data?.bars || state.data.bars.length === 0) return null;
        
        const bars = state.replay.active
            ? state.data.bars.slice(0, state.replay.cursorIndex + 1)
            : state.data.bars;
        
        return bars.length > 0 ? bars[bars.length - 1] : null;
    }, [hoveredBar, state.data, state.replay]);

    // Calculate stats for header
    const stats = useMemo(() => {
        if (!state.data?.bars || state.data.bars.length === 0) return null;

        const bars = state.replay.active
            ? state.data.bars.slice(0, state.replay.cursorIndex + 1)
            : state.data.bars;

        if (bars.length === 0) return null;

        const last = bars[bars.length - 1];
        const first = bars[0];
        const prevClose = state.data.previousClose || first.open;
        const change = last.close - prevClose;
        const changePct = (change / prevClose) * 100;

        return {
            last: last.close,
            change,
            changePct,
        };
    }, [state.data, state.replay]);

    const handleBarHover = useCallback((index: number | null, bar: OHLCVBar | null) => {
        setHoveredBar(bar);
        dispatch({ type: 'SET_HOVERED_BAR', payload: index });
    }, [dispatch]);

    const handleTimeframeChange = useCallback((tf: Timeframe) => {
        setTimeframe(tf);
        onTimeframeChange?.(tf);
    }, [setTimeframe, onTimeframeChange]);

    const TOOLBAR_HEIGHT = 42;
    const [measuredPriceHeight, setMeasuredPriceHeight] = useState(0);
    const priceAreaRef = useRef<HTMLDivElement>(null);

    // Measure the price area dynamically to ensure zero gaps and proper axis visibility
    useEffect(() => {
        if (!priceAreaRef.current) return;
        
        const updateHeight = () => {
            if (priceAreaRef.current) {
                setMeasuredPriceHeight(priceAreaRef.current.offsetHeight);
            }
        };

        const observer = new ResizeObserver(updateHeight);
        observer.observe(priceAreaRef.current);
        
        updateHeight();
        return () => observer.disconnect();
    }, []);



    // Chart height calculations
    const chartHeight = effectiveHeight - TOOLBAR_HEIGHT;
    
    // TRADINGVIEW STYLE: Dynamic split with minimum indicator height
    const mainChartHeight = useMemo(() => {
        if (paneIndicators.length === 0) return chartHeight;
        // Reserve at least 35% or 180px per indicator for the panes, whichever is more comfortable
        const totalPaneRequestedHeight = Math.max(chartHeight * 0.35, paneIndicators.length * 180);
        return Math.max(chartHeight * 0.4, chartHeight - totalPaneRequestedHeight);
    }, [chartHeight, paneIndicators.length]);

    const individualPaneHeight = useMemo(() => {
        if (paneIndicators.length === 0) return 0;
        return (chartHeight - mainChartHeight) / paneIndicators.length;
    }, [chartHeight, mainChartHeight, paneIndicators.length]);

    // Scan for candlestick patterns when data or selected patterns change
    useEffect(() => {
        const bars = state.data?.bars || [];
        if (bars.length === 0 || selectedPatterns.length === 0) {
            setDetectedPatterns([]);
            return;
        }
        
        const patternsToScan = CANDLESTICK_PATTERNS.filter(p => selectedPatterns.includes(p.id));
        const matches = scanForPatterns(bars, patternsToScan);
        setDetectedPatterns(matches);
    }, [state.data?.bars, selectedPatterns]);

    // Pattern scanner toggle handlers
    const handlePatternToggle = useCallback((patternId: string) => {
        setSelectedPatterns(prev => 
            prev.includes(patternId) 
                ? prev.filter(id => id !== patternId)
                : [...prev, patternId]
        );
    }, []);

    const handleSelectAllPatterns = useCallback(() => {
        setSelectedPatterns(CANDLESTICK_PATTERNS.map(p => p.id));
    }, []);

    const handleClearAllPatterns = useCallback(() => {
        setSelectedPatterns([]);
    }, []);

    // Run strategies when data or selected strategies change
    useEffect(() => {
        const bars = state.data?.bars || [];
        if (bars.length === 0 || selectedStrategies.length === 0) {
            setStrategySignals(new Map());
            return;
        }
        
        const results = runStrategies(bars, selectedStrategies, strategyParams);
        setStrategySignals(results);
    }, [state.data?.bars, selectedStrategies, strategyParams]);

    // Strategy toggle handlers
    const handleStrategyToggle = useCallback((strategyId: string) => {
        setSelectedStrategies(prev => 
            prev.includes(strategyId) 
                ? prev.filter(id => id !== strategyId)
                : [...prev, strategyId]
        );
    }, []);

    const handleStrategyParamChange = useCallback((strategyId: string, param: string, value: number) => {
        setStrategyParams(prev => ({
            ...prev,
            [strategyId]: {
                ...(prev[strategyId] || {}),
                [param]: value,
            },
        }));
    }, []);

    const handleSelectAllStrategies = useCallback(() => {
        setSelectedStrategies(TRADING_STRATEGIES.map(s => s.id));
    }, []);

    const handleClearAllStrategies = useCallback(() => {
        setSelectedStrategies([]);
    }, []);

    // Get total signal count for display
    const totalSignalCount = useMemo(() => {
        let count = 0;
        strategySignals.forEach(result => {
            count += result.signals.length;
        });
        return count;
    }, [strategySignals]);

    return (
        <div
            ref={containerRef}
            className="flex flex-col h-full overflow-hidden"
            style={{
                background: CHART_THEME.bgPrimary,
                // Border removed - parent container provides outer border
                borderRadius: 4,
                contain: 'layout style paint',
                willChange: 'transform',
                isolation: 'isolate',
            }}
        >
            {/* ============================================================
                UNIFIED TOOLBAR (TradingView Style)
                Single row: Symbol+OHLCV | Timeframes | Chart Type | Tools
            ============================================================ */}
            <div
                className="flex items-center gap-2 px-2 flex-shrink-0"
                style={{ 
                    height: TOOLBAR_HEIGHT,
                    borderBottom: `1px solid ${CHART_THEME.border}`,
                    background: CHART_THEME.bgSecondary,
                }}
            >
                {/* Symbol + Live OHLCV (inline like TradingView) */}
                <div className="flex items-center gap-3 mr-2 min-w-0 max-w-[40%]">
                    <span
                        className="text-sm font-bold truncate"
                        style={{ color: CHART_THEME.textPrimary, fontFamily: CHART_THEME.fontMono }}
                        title={state.symbol}
                    >
                        {state.symbol}
                    </span>
                    {stats && (
                        <span
                            className="text-xs font-mono flex-shrink-0"
                            style={{ color: stats.change >= 0 ? CHART_THEME.upColor : CHART_THEME.downColor }}
                        >
                            {stats.last.toFixed(2)} {stats.change >= 0 ? '+' : ''}{stats.changePct.toFixed(2)}%
                        </span>
                    )}
                    
                    {/* Inline OHLCV - hidden on very small screens, scrollable if needed */}
                    {displayBar && (
                        <div className="hidden md:flex items-center gap-2 text-[11px] font-mono border-l pl-3 ml-1 overflow-x-auto no-scrollbar whitespace-nowrap" style={{ borderColor: CHART_THEME.border }}>
                            <span style={{ color: CHART_THEME.textSecondary }}>O</span>
                            <span style={{ color: CHART_THEME.textPrimary }}>{displayBar.open.toFixed(2)}</span>
                            <span style={{ color: CHART_THEME.textSecondary }}>H</span>
                            <span style={{ color: CHART_THEME.upColor }}>{displayBar.high.toFixed(2)}</span>
                            <span style={{ color: CHART_THEME.textSecondary }}>L</span>
                            <span style={{ color: CHART_THEME.downColor }}>{displayBar.low.toFixed(2)}</span>
                            <span style={{ color: CHART_THEME.textSecondary }}>C</span>
                            <span style={{ color: displayBar.close >= displayBar.open ? CHART_THEME.upColor : CHART_THEME.downColor }}>
                                {displayBar.close.toFixed(2)}
                            </span>
                        </div>
                    )}
                </div>

                {/* Separator */}
                <div className="w-px h-5" style={{ background: CHART_THEME.border }} />

                {/* Timeframe Pills */}
                <div className="flex items-center gap-0.5">
                    {TIMEFRAMES.map(tf => (
                        <button
                            key={tf.value}
                            onClick={() => handleTimeframeChange(tf.value)}
                            className="px-2 py-1 text-[11px] font-mono transition-colors"
                            style={{
                                background: state.timeframe === tf.value ? CHART_THEME.accent : 'transparent',
                                color: state.timeframe === tf.value ? CHART_THEME.bgPrimary : CHART_THEME.textSecondary,
                                borderRadius: 2,
                            }}
                        >
                            {tf.label}
                        </button>
                    ))}
                </div>

                {/* Separator */}
                <div className="w-px h-5" style={{ background: CHART_THEME.border }} />

                {/* Chart Type Dropdown */}
                <select
                    value={state.config.chartType}
                    onChange={(e) => setChartType(e.target.value as ChartType)}
                    className="px-2 py-1 text-[11px] font-mono outline-none cursor-pointer"
                    style={{
                        background: CHART_THEME.bgPrimary,
                        color: CHART_THEME.textPrimary,
                        border: `1px solid ${CHART_THEME.border}`,
                        borderRadius: 2,
                    }}
                >
                    {CHART_TYPES.map(ct => (
                        <option key={ct.value} value={ct.value}>{ct.label}</option>
                    ))}
                </select>

                {/* Separator */}
                <div className="w-px h-5" style={{ background: CHART_THEME.border }} />

                {/* Indicators Menu */}
                <IndicatorMenu
                    onAddIndicator={handleAddIndicatorWrap}
                    activeIndicators={state.indicators}
                    onRemoveIndicator={removeIndicator}
                />

                {/* Pattern Scanner Button */}
                <button
                    onClick={() => setShowPatternSelector(true)}
                    className="px-2 py-1 text-[11px] font-mono flex items-center gap-1.5"
                    style={{
                        background: selectedPatterns.length > 0 ? 'rgba(236, 72, 153, 0.15)' : 'transparent',
                        color: selectedPatterns.length > 0 ? '#ec4899' : CHART_THEME.textSecondary,
                        border: `1px solid ${selectedPatterns.length > 0 ? '#ec4899' : CHART_THEME.border}`,
                        borderRadius: 2,
                    }}
                    title="Candlestick Pattern Scanner"
                >
                    <LayoutGrid size={13} />
                    Patterns
                    {selectedPatterns.length > 0 && (
                        <span className="ml-1 px-1.5 py-0.5 text-[9px] bg-pink-500/20 rounded">
                            {detectedPatterns.length}
                        </span>
                    )}
                </button>

                {/* Strategy Engine Button */}
                <button
                    onClick={() => setShowStrategySelector(true)}
                    className="px-2 py-1 text-[11px] font-mono flex items-center gap-1.5"
                    style={{
                        background: selectedStrategies.length > 0 ? 'rgba(6, 182, 212, 0.15)' : 'transparent',
                        color: selectedStrategies.length > 0 ? '#06b6d4' : CHART_THEME.textSecondary,
                        border: `1px solid ${selectedStrategies.length > 0 ? '#06b6d4' : CHART_THEME.border}`,
                        borderRadius: 2,
                    }}
                    title="Trading Strategies"
                >
                    <Cpu size={13} />
                    Strategies
                    {selectedStrategies.length > 0 && (
                        <span className="ml-1 px-1.5 py-0.5 text-[9px] bg-cyan-500/20 rounded">
                            {totalSignalCount}
                        </span>
                    )}
                </button>

                {/* Replay Button */}
                <button
                    onClick={handleReplayClick}
                    className="px-2 py-1 text-[11px] font-mono"
                    style={{
                        background: state.replay.active || isReplaySelectMode ? CHART_THEME.accent : 'transparent',
                        color: state.replay.active || isReplaySelectMode ? CHART_THEME.bgPrimary : CHART_THEME.textSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                        borderRadius: 2,
                    }}
                >
                    Replay
                </button>

                {/* Spacer */}
                <div className="flex-1" />

                {/* Compare Button - Only for single chart layout */}
                {currentLayout === '1' && (
                    <button
                        onClick={() => {
                            setRightPanel(rightPanel === 'alpha' ? null : 'alpha');
                        }}
                        className="px-2 py-1 text-[11px] font-mono"
                        style={{
                            background: rightPanel === 'alpha' ? 'rgba(139, 92, 246, 0.25)' : (compareSymbols.length > 0 ? 'rgba(139, 92, 246, 0.1)' : 'transparent'),
                            color: rightPanel === 'alpha' || compareSymbols.length > 0 ? '#a78bfa' : CHART_THEME.textSecondary,
                            border: `1px solid ${rightPanel === 'alpha' ? '#a78bfa' : CHART_THEME.border}`,
                            borderRadius: 2,
                        }}
                    >
                        Compare{compareSymbols.length > 0 && ` (${compareSymbols.length})`}
                    </button>
                )}

                {/* Right side tools */}
                <button
                    onClick={handleToggleVolumeWrap}
                    className="px-2 py-1 text-[11px] font-mono"
                    style={{
                        background: state.config.showVolume ? 'rgba(255, 214, 10, 0.15)' : 'transparent',
                        color: state.config.showVolume ? CHART_THEME.accent : CHART_THEME.textSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                        borderRadius: 2,
                    }}
                >
                    Vol
                </button>

                {/* Layout Selector - TradingView style */}
                {/* Hidden when chart is embedded in a grid (isMemberOfGrid = true) per audit report Section 2B */}
                {!isMemberOfGrid && (
                <div className="relative">
                    <button
                        onClick={() => {
                            // Automatically handle blockers instead of showing popups
                            if (paneIndicators.length > 0) {
                                // Close all pane indicators before layout change to avoid grid conflicts
                                paneIndicators.forEach(ind => removeIndicator(ind.id));
                            }
                            if (state.config.showVolume) {
                                toggleVolume();
                            }
                            if (compareSymbols.length > 0) {
                                setCompareSymbols([]);
                                setVisibleGhosts([]);
                            }
                            setShowLayoutMenu(!showLayoutMenu);
                        }}
                        className="px-2 py-1 text-[11px] font-mono flex items-center gap-1"
                        style={{
                            background: 'transparent',
                            color: CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                            borderRadius: 2,
                        }}
                    >
                        <LayoutIcon layoutId={currentLayout} />
                    </button>
                    
                    {showLayoutMenu && paneIndicators.length === 0 && !state.config.showVolume && compareSymbols.length === 0 && (
                        <div
                            className="absolute top-full right-0 mt-1 p-3 z-[100]"
                            style={{
                                background: CHART_THEME.bgPrimary,
                                border: `1px solid ${CHART_THEME.border}`,
                                borderRadius: 6,
                                boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
                                minWidth: 200,
                            }}
                        >
                            <div 
                                className="text-[10px] font-mono uppercase mb-2 pb-2"
                                style={{ color: CHART_THEME.textMuted, borderBottom: `1px solid ${CHART_THEME.border}` }}
                            >
                                Select Layout
                            </div>
                            <div className="grid grid-cols-4 gap-1.5">
                                {LAYOUT_OPTIONS.map(layout => (
                                    <button
                                        key={layout.id}
                                        onClick={() => {
                                            if (layout.id !== '1') {
                                                // Multi-chart layout - show symbol search
                                                setPendingLayout(layout.id);
                                                setGridSymbols([state.symbol]); // Reset with main symbol first
                                                setShowSymbolSearch(true);
                                                setShowLayoutMenu(false);
                                            } else {
                                                setCurrentLayout(layout.id);
                                                setGridSymbols([state.symbol]);
                                                setShowLayoutMenu(false);
                                            }
                                        }}
                                        className="w-10 h-10 flex items-center justify-center transition-all"
                                        style={{
                                            background: currentLayout === layout.id ? CHART_THEME.accent + '25' : 'transparent',
                                            border: currentLayout === layout.id 
                                                ? `2px solid ${CHART_THEME.accent}` 
                                                : `1px solid ${CHART_THEME.border}`,
                                            borderRadius: 4,
                                        }}
                                        title={`${layout.label} charts`}
                                    >
                                        <LayoutIcon layoutId={layout.id} size={18} />
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
                )}
                
                {/* Right Panel Toggles */}
                <div className="flex gap-1 ml-1">
                    <button
                        onClick={() => setRightPanel(rightPanel === 'watchlist' ? null : 'watchlist')}
                        className="px-2 py-1 text-[11px] font-mono transition-colors"
                        style={{
                            background: rightPanel === 'watchlist' ? CHART_THEME.accent : 'transparent',
                            color: rightPanel === 'watchlist' ? '#000' : CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                            borderRadius: 2,
                        }}
                    >
                        WL
                    </button>
                    <button
                        onClick={() => setRightPanel(rightPanel === 'alerts' ? null : 'alerts')}
                        className="px-2 py-1 text-[11px] font-mono transition-colors"
                        style={{
                            background: rightPanel === 'alerts' ? CHART_THEME.accent : 'transparent',
                            color: rightPanel === 'alerts' ? '#000' : CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                            borderRadius: 2,
                        }}
                    >
                        AL
                    </button>
                </div>

                {/* Fullscreen Button */}
                <button
                    onClick={() => {
                        const elem = document.documentElement;
                        if (!isFullscreen) {
                            elem.requestFullscreen?.();
                        } else {
                            document.exitFullscreen?.();
                        }
                        setIsFullscreen(!isFullscreen);
                    }}
                    className="px-2 py-1 text-[11px] font-mono"
                    style={{
                        background: 'transparent',
                        color: CHART_THEME.textSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                        borderRadius: 2,
                    }}
                    title="Toggle Fullscreen"
                >
                    {isFullscreen ? '[-]' : '[+]'}
                </button>
            </div>

            {/* Chart Area with Toolbar AND Indicator Panes */}
            <div 
                className="flex-1 flex relative"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => e.preventDefault()}
            >
                {/* Drawing Toolbar - Left Side */}
                <div className="z-50 h-full flex-shrink-0 relative">
                <DrawingToolbar
                    activeTool={state.activeToolType}
                    onToolSelect={(tool) => dispatch({ type: 'SET_ACTIVE_TOOL', payload: tool })}
                    onClearAll={() => dispatch({ type: 'CLEAR_DRAWINGS' })}
                    onScreenshot={handleScreenshot}
                    onExportData={handleExportCSV}
                />
                </div>

                {/* Charts Stack (Main + Panes) */}
                <div 
                    id="q360-chart-area" 
                    className="flex-1 flex flex-col relative min-w-0 z-0 gap-0"
                    style={{ background: CHART_THEME.bgPrimary }}
                    onDragOver={(e) => {
                        e.preventDefault();
                        e.dataTransfer.dropEffect = 'copy';
                        e.currentTarget.style.boxShadow = `inset 0 0 40px ${CHART_THEME.accent}15`;
                    }}
                    onDragLeave={(e) => {
                        e.currentTarget.style.boxShadow = 'none';
                    }}
                    onDrop={(e) => {
                        e.preventDefault();
                        e.currentTarget.style.boxShadow = 'none';
                        const symbol = e.dataTransfer.getData('text/plain');
                        if (symbol && symbol !== state.symbol) {
                            if (!compareSymbols.includes(symbol)) {
                                setCompareSymbols(prev => [...prev, symbol].slice(-2));
                                setVisibleGhosts(prev => [...prev, symbol]);
                                setRightPanel('alpha'); // Auto-open the panel
                            }
                        }
                    }}
                >
                    
                    {/* Single Chart or Multi-Chart Grid */}
                    {(currentLayout === '1' || isMemberOfGrid) ? (
                        /* Main Price Chart (Single) */
                        <div 
                            ref={priceAreaRef}
                            className="relative w-full border-b border-[#363c4e]" 
                            style={{ 
                                height: mainChartHeight,
                                minHeight: 150,
                                flexShrink: 0
                            }}
                        >
                             {isLoading && (
                                <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: 'rgba(19, 23, 34, 0.9)' }}>
                                    <span className="text-sm font-mono" style={{ color: CHART_THEME.textSecondary }}>Loading...</span>
                                </div>
                            )}
                            {error && (
                                <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: 'rgba(19, 23, 34, 0.9)' }}>
                                    <span className="text-sm font-mono" style={{ color: CHART_THEME.downColor }}>{error}</span>
                                </div>
                            )}

                             <ChartCanvas
                                width={effectiveWidth - 44}
                                height={mainChartHeight} 
                                hideTimeAxis={paneIndicators.length > 0}
                                onBarHover={handleBarHover}
                                onBarClick={(absoluteIndex) => {
                                    setAnchorIndex(absoluteIndex);

                                    // Handle internal replay select mode
                                    if (isReplaySelectMode && absoluteIndex >= 0) {
                                        startReplay(absoluteIndex);
                                    }
                                }}
                                compareData={compareSymbols.length > 0 ? compareData : undefined}
                                syncedCrosshairTimestamp={syncedCrosshairTimestamp}
                                onCrosshairMove={onCrosshairMove}
                                anchorIndex={anchorIndex}
                                visibleGhosts={visibleGhosts}
                                alphaMode={alphaMode}
                                detectedPatterns={detectedPatterns}
                                strategySignals={strategySignals}
                            />
                        </div>
                    ) : (
                        /* Multi-Chart Grid Layout */
                        <div 
                            className="flex-1 relative min-h-0"
                            style={{
                                display: 'grid',
                                gridTemplateColumns: columnPercents.length > 0 
                                    ? columnPercents.map(p => `${p}%`).join(' ') 
                                    : '1fr',
                                gridTemplateRows: rowPercents.length > 0 
                                    ? rowPercents.map(p => `${p}%`).join(' ') 
                                    : '1fr',
                                gap: '2px',
                                background: CHART_THEME.border,
                            }}
                        >
                            {gridSymbols.map((symbol, idx) => {
                                const bars = symbol === state.symbol 
                                    ? state.data?.bars || [] 
                                    : gridData[symbol] || [];
                                
                                return (
                                    <div 
                                        key={`${symbol}-${idx}`}
                                        className="relative overflow-hidden group"
                                        style={{ 
                                            background: CHART_THEME.bgPrimary,
                                            border: `1px solid ${CHART_THEME.border}`,
                                            borderRadius: 2,
                                        }}
                                    >
                                        {/* Chart Header */}
                                        <div 
                                            className="absolute top-0 left-0 right-0 z-10 px-2 py-1 flex items-center gap-2"
                                            style={{ 
                                                background: 'linear-gradient(180deg, rgba(0,0,0,0.8) 0%, transparent 100%)',
                                            }}
                                        >
                                            <span 
                                                className="font-bold text-[10px]"
                                                style={{ color: CHART_THEME.textPrimary }}
                                            >
                                                {symbol}
                                            </span>
                                            <span 
                                                className="text-[9px]"
                                                style={{ color: CHART_THEME.textSecondary }}
                                            >
                                                {state.timeframe.toUpperCase()}
                                            </span>
                                            <div className="flex-1" />
                                            <button 
                                                onClick={() => handleMaximizePanel(symbol)}
                                                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-white/10 rounded"
                                                title="Maximize"
                                            >
                                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                                    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                                                </svg>
                                            </button>
                                        </div>
                                        
                                        {/* Full Chart Canvas inside grid cell */}
                                        <div 
                                            className="absolute inset-0"
                                            style={{ contain: 'strict' }}
                                        >
                                            <ChartCanvas
                                                width={(() => {
                                                    const layout = LAYOUT_OPTIONS.find(l => l.id === currentLayout);
                                                    const cols = layout?.grid[0]?.length || 1;
                                                    const colIdx = idx % cols;
                                                    const pct = columnPercents[colIdx] || (100 / cols);
                                                    return Math.floor((effectiveWidth - 44) * (pct / 100));
                                                })()}
                                                height={(() => {
                                                    const layout = LAYOUT_OPTIONS.find(l => l.id === currentLayout);
                                                    const cols = layout?.grid[0]?.length || 1;
                                                    const rows = layout?.grid.length || 1;
                                                    const rowIdx = Math.floor(idx / cols);
                                                    const pct = rowPercents[rowIdx] || (100 / rows);
                                                    return Math.floor(chartHeight * (pct / 100));
                                                })()}
                                                externalBars={bars}
                                                symbol={symbol}
                                                onBarHover={handleBarHover}
                                                onBarClick={(index) => {
                                                    if (isReplaySelectMode && index >= 0) {
                                                        startReplay(index);
                                                    } else if (rightPanel === 'alpha') {
                                                        setAnchorIndex(index);
                                                    }
                                                }}
                                                replayActive={state.replay.active}
                                                replayCursorIndex={state.replay.cursorIndex}
                                                replaySelectMode={isReplaySelectMode}
                                                syncedCrosshairTimestamp={syncedCrosshairTimestamp}
                                                onCrosshairMove={onCrosshairMove}
                                                onDoubleClick={() => handleMaximizePanel(symbol)}
                                                anchorIndex={anchorIndex}
                                                compareData={compareData}
                                                visibleGhosts={visibleGhosts}
                                                alphaMode={alphaMode}
                                                detectedPatterns={detectedPatterns}
                                                strategySignals={strategySignals}
                                            />
                                        </div>
                                    </div>
                                );
                            })}

                            {/* Column Dividers (Draggable) */}
                            {columnPercents.length > 1 && columnPercents.slice(0, -1).map((_, i) => {
                                let leftPct = 0;
                                for (let j = 0; j <= i; j++) leftPct += columnPercents[j];
                                
                                return (
                                    <div
                                        key={`col-divider-${i}`}
                                        className="absolute top-0 bottom-0 w-1 z-50 cursor-col-resize hover:bg-yellow-500/30 transition-colors"
                                        style={{ left: `calc(${leftPct}% - 0.5px)` }}
                                        onMouseDown={(e) => {
                                            const startX = e.clientX;
                                            const startLeftPct = columnPercents[i];
                                            const startRightPct = columnPercents[i+1];
                                            
                                            const onMouseMove = (moveEvent: MouseEvent) => {
                                                const deltaX = moveEvent.clientX - startX;
                                                const deltaPct = (deltaX / (effectiveWidth - 44)) * 100;
                                                
                                                const newCols = [...columnPercents];
                                                newCols[i] = Math.max(10, startLeftPct + deltaPct);
                                                newCols[i+1] = Math.max(10, startRightPct - deltaPct);
                                                setColumnPercents(newCols);
                                            };
                                            
                                            const onMouseUp = () => {
                                                window.removeEventListener('mousemove', onMouseMove);
                                                window.removeEventListener('mouseup', onMouseUp);
                                            };
                                            
                                            window.addEventListener('mousemove', onMouseMove);
                                            window.addEventListener('mouseup', onMouseUp);
                                        }}
                                    />
                                );
                            })}

                            {/* Row Dividers (Draggable) */}
                            {rowPercents.length > 1 && rowPercents.slice(0, -1).map((_, i) => {
                                let topPct = 0;
                                for (let j = 0; j <= i; j++) topPct += rowPercents[j];
                                
                                return (
                                    <div
                                        key={`row-divider-${i}`}
                                        className="absolute left-0 right-0 h-1 z-50 cursor-row-resize hover:bg-yellow-500/30 transition-colors"
                                        style={{ top: `calc(${topPct}% - 0.5px)` }}
                                        onMouseDown={(e) => {
                                            const startY = e.clientY;
                                            const startTopPct = rowPercents[i];
                                            const startBottomPct = rowPercents[i+1];
                                            
                                            const onMouseMove = (moveEvent: MouseEvent) => {
                                                const deltaY = moveEvent.clientY - startY;
                                                const deltaPct = (deltaY / chartHeight) * 100;
                                                
                                                const newRows = [...rowPercents];
                                                newRows[i] = Math.max(10, startTopPct + deltaPct);
                                                newRows[i+1] = Math.max(10, startBottomPct - deltaPct);
                                                setRowPercents(newRows);
                                            };
                                            
                                            const onMouseUp = () => {
                                                window.removeEventListener('mousemove', onMouseMove);
                                                window.removeEventListener('mouseup', onMouseUp);
                                            };
                                            
                                            window.addEventListener('mousemove', onMouseMove);
                                            window.addEventListener('mouseup', onMouseUp);
                                        }}
                                    />
                                );
                            })}
                        </div>
                    )}

                    {/* Indicator Panes */}
                    {paneOutputs && paneIndicators.map((ind) => {
                        const output = paneOutputs.get(ind.id);
                        return (
                            <div 
                                key={ind.id} 
                                className="flex-shrink-0 relative group border-t border-terminal-border"
                                style={{ 
                                    height: individualPaneHeight,
                                    background: CHART_THEME.bgPrimary 
                                }}
                            >
                                {/* Indicator Pane (No top border, touches previous pane) */}
                                <IndicatorPaneRenderer
                                    indicatorId={ind.type}
                                    indicatorName={getIndicator(ind.type)?.name || ind.type}
                                    output={output}
                                    bars={state.data?.bars || []}
                                    width={effectiveWidth - 44}
                                    height={individualPaneHeight}
                                    visibleRange={visibleRange}
                                    hoveredIndex={state.hoveredBarIndex}
                                    anchorIndex={anchorIndex}
                                    onHover={(idx) => handleBarHover(idx, state.data?.bars[idx] || null)}
                                    showTimeAxis={paneIndicators.indexOf(ind) === paneIndicators.length - 1}
                                />
                                <button
                                    className="absolute top-2 right-2 px-1.5 py-0.5 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity z-10 font-mono"
                                    style={{ color: CHART_THEME.textSecondary, background: CHART_THEME.bgSecondary, borderRadius: 2 }}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        dispatch({ type: 'REMOVE_INDICATOR', payload: ind.id });
                                    }}
                                >
                                    x
                                </button>
                            </div>
                        );
                    })}
                </div>

                {/* Right Side Panels */}
                {rightPanel === 'watchlist' && (
                    <div 
                        className="h-full border-l" 
                        style={{ 
                            width: 320, 
                            borderColor: CHART_THEME.border,
                            background: CHART_THEME.bgSecondary,
                        }}
                    >
                        <WatchlistPanel onSymbolClick={(s) => onSymbolChange(s)} />
                    </div>
                )}

                {rightPanel === 'alpha' && (
                    <div 
                        className="h-full border-l" 
                        style={{ 
                            width: 320, 
                            borderColor: CHART_THEME.border,
                            background: CHART_THEME.bgSecondary,
                        }}
                    >
                        <AlphaPanel 
                            primarySymbol={state.symbol}
                            compareSymbols={compareSymbols}
                            compareData={compareData}
                            primaryData={displayBars}
                            onRemove={(s) => setCompareSymbols(prev => prev.filter(sym => sym !== s))}
                            onToggleVisibility={(s) => {
                                setVisibleGhosts(prev => 
                                    prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
                                );
                            }}
                            onAdd={(s) => {
                                if (!compareSymbols.includes(s) && s !== state.symbol) {
                                    setCompareSymbols(prev => [...prev, s].slice(-2));
                                    setVisibleGhosts(prev => [...prev, s]);
                                }
                            }}
                            onClose={() => setRightPanel(null)}
                            anchorIndex={anchorIndex}
                            alphaMode={alphaMode}
                            onModeChange={setAlphaMode}
                            visibleGhosts={visibleGhosts}
                        />
                    </div>
                )}

                {rightPanel === 'alerts' && (
                    <AlertManager 
                        symbol={state.symbol}
                        timeframe={state.timeframe}
                        currentPrice={state.data?.bars[state.data.bars.length - 1]?.close || 0}
                        isOpen={true}
                        onClose={() => setRightPanel(null)}
                    />
                )}
            </div>

            {/* Replay Controls (Overlay at bottom) */}
            {(state.replay.active || isReplaySelectMode) && (
                 <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-50 shadow-xl rounded overflow-hidden">
                    <ReplayControls />
                 </div>
            )}

            {/* Custom Indicator Modal */}
            <CustomIndicatorModal
                isOpen={showCustomIndicatorModal}
                onClose={() => setShowCustomIndicatorModal(false)}
                onSave={(indicator) => {
                    addCustomIndicator(indicator);
                    console.log('Custom indicator saved:', indicator);
                }}
            />

            {/* Candlestick Pattern Selector */}
            <PatternSelector
                isOpen={showPatternSelector}
                onClose={() => setShowPatternSelector(false)}
                selectedPatterns={selectedPatterns}
                onPatternToggle={handlePatternToggle}
                onSelectAll={handleSelectAllPatterns}
                onClearAll={handleClearAllPatterns}
            />

            {/* Trading Strategy Selector */}
            <StrategySelector
                isOpen={showStrategySelector}
                onClose={() => setShowStrategySelector(false)}
                selectedStrategies={selectedStrategies}
                onStrategyToggle={handleStrategyToggle}
                strategyParams={strategyParams}
                onParamChange={handleStrategyParamChange}
                onSelectAll={handleSelectAllStrategies}
                onClearAll={handleClearAllStrategies}
            />
            
            {/* Blocking Message Modal */}
            {blockingMessage && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(0, 0, 0, 0.8)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 10000,
                    }}
                    onClick={() => setBlockingMessage(null)}
                >
                    <div
                        style={{
                            background: CHART_THEME.bgSecondary,
                            border: `2px solid ${CHART_THEME.accent}`,
                            borderRadius: 8,
                            padding: '24px 32px',
                            maxWidth: 450,
                            textAlign: 'center',
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        <h3 
                            style={{ 
                                color: CHART_THEME.accent, 
                                fontSize: 14, 
                                fontWeight: 600,
                                marginBottom: 12,
                                fontFamily: 'monospace',
                                textTransform: 'uppercase',
                            }}
                        >
                            Action Required
                        </h3>
                        <p 
                            style={{ 
                                color: CHART_THEME.textSecondary, 
                                fontSize: 13,
                                lineHeight: 1.6,
                                marginBottom: 20,
                                fontFamily: 'monospace',
                            }}
                        >
                            {blockingMessage}
                        </p>
                        <button
                            onClick={() => setBlockingMessage(null)}
                            style={{
                                background: CHART_THEME.accent,
                                color: CHART_THEME.bgPrimary,
                                border: 'none',
                                borderRadius: 4,
                                padding: '8px 20px',
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                                fontFamily: 'monospace',
                            }}
                        >
                            OK
                        </button>
                    </div>
                </div>
            )}
            
            {/* Symbol Search Modal for Multi-Chart Layouts */}
            {showSymbolSearch && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(0, 0, 0, 0.9)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 10000,
                    }}
                    onClick={() => {
                        setShowSymbolSearch(false);
                        setPendingLayout(null);
                    }}
                >
                    <div
                        style={{
                            background: CHART_THEME.bgSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                            borderRadius: 12,
                            padding: 24,
                            width: 550,
                            maxHeight: '80vh',
                            overflow: 'visible',
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-4">
                            <h3 
                                style={{ 
                                    color: CHART_THEME.textPrimary, 
                                    fontSize: 16, 
                                    fontWeight: 600,
                                    fontFamily: 'monospace',
                                }}
                            >
                                {pendingLayout ? `Select Ticker for Chart ${gridSymbols.length + 1} of ${(() => {
                                    const l = LAYOUT_OPTIONS.find(opt => opt.id === pendingLayout);
                                    return l ? l.grid.flat().length : 0;
                                })()}` : 'Add Symbol to Layout'}
                            </h3>
                            <button
                                onClick={() => {
                                    setShowSymbolSearch(false);
                                    setPendingLayout(null);
                                }}
                                style={{
                                    background: CHART_THEME.bgPanel,
                                    border: `1px solid ${CHART_THEME.border}`,
                                    color: CHART_THEME.textSecondary,
                                    width: 28,
                                    height: 28,
                                    borderRadius: 4,
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                }}
                            >
                                x
                            </button>
                        </div>
                        
                        <TradingViewSearch
                            mode="any"
                            placeholder="Type a symbol..."
                            onSelect={(symbol) => {
                                const l = LAYOUT_OPTIONS.find(opt => opt.id === pendingLayout);
                                const required = l ? l.grid.flat().length : 1;
                                
                                setGridSymbols(prev => {
                                    const next = [...prev, symbol];
                                    if (next.length >= required) {
                                        // Final symbol added
                                        if (pendingLayout) {
                                            setCurrentLayout(pendingLayout);
                                        }
                                        setShowSymbolSearch(false);
                                        setPendingLayout(null);
                                    }
                                    return next;
                                });
                            }}
                        />
                        
                        <div 
                            className="mt-4 text-[11px] font-mono"
                            style={{ color: CHART_THEME.textMuted }}
                        >
                            Current symbols: {gridSymbols.join(', ')}
                        </div>
                    </div>
                </div>
            )}
            
            {/* Compare Symbol Search Modal */}
            {showCompareSearch && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(0, 0, 0, 0.9)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 10000,
                    }}
                    onClick={() => setShowCompareSearch(false)}
                >
                    <div
                        style={{
                            background: CHART_THEME.bgSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                            borderRadius: 12,
                            padding: 24,
                            width: 550,
                            maxHeight: '80vh',
                            overflow: 'visible',
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-4">
                            <h3 
                                style={{ 
                                    color: CHART_THEME.textPrimary, 
                                    fontSize: 16, 
                                    fontWeight: 600,
                                    fontFamily: 'monospace',
                                }}
                            >
                                Compare Symbol
                            </h3>
                            <button
                                onClick={() => setShowCompareSearch(false)}
                                style={{
                                    background: CHART_THEME.bgPanel,
                                    border: `1px solid ${CHART_THEME.border}`,
                                    color: CHART_THEME.textSecondary,
                                    width: 28,
                                    height: 28,
                                    borderRadius: 4,
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                }}
                            >
                                x
                            </button>
                        </div>
                        
                        <div 
                            className="text-[11px] font-mono mb-3"
                            style={{ color: CHART_THEME.textMuted }}
                        >
                            Overlay another symbol on the current chart (max 2 compare symbols)
                        </div>
                        
                        <TradingViewSearch
                            mode="any"
                            placeholder="Search symbol to compare..."
                            onSelect={(symbol) => {
                                // Add to compare symbols (max 2)
                                if (compareSymbols.length < 2 && !compareSymbols.includes(symbol) && symbol !== state.symbol) {
                                    setCompareSymbols(prev => [...prev, symbol]);
                                }
                                setShowCompareSearch(false);
                            }}
                        />
                        
                        {compareSymbols.length > 0 && (
                            <div className="mt-4">
                                <div 
                                    className="text-[10px] font-mono uppercase mb-2"
                                    style={{ color: CHART_THEME.textMuted }}
                                >
                                    Active Comparisons
                                </div>
                                <div className="flex gap-2">
                                    {compareSymbols.map(sym => (
                                        <div 
                                            key={sym}
                                            className="flex items-center gap-2 px-3 py-1.5 rounded"
                                            style={{ 
                                                background: CHART_THEME.bgPanel,
                                                border: `1px solid ${CHART_THEME.border}`,
                                            }}
                                        >
                                            <span 
                                                className="text-[12px] font-mono font-bold"
                                                style={{ color: CHART_THEME.accent }}
                                            >
                                                {sym}
                                            </span>
                                            <button
                                                onClick={() => setCompareSymbols(prev => prev.filter(s => s !== sym))}
                                                className="text-[10px]"
                                                style={{ color: CHART_THEME.textMuted }}
                                            >
                                                x
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// REPLAY CONTROLS (No emojis)
// =============================================================================

function ReplayControls() {
    const {
        state,
        toggleReplayPlay,
        stopReplay,
        stepReplay,
        setReplaySpeed,
        isReplaySelectMode,
        exitReplaySelectMode,
    } = useChart();

    const totalBars = state.data?.bars.length || 0;
    const progress = totalBars > 0 && state.replay.cursorIndex >= state.replay.startIndex
        ? ((state.replay.cursorIndex - state.replay.startIndex) / (totalBars - state.replay.startIndex)) * 100
        : 0;

    const currentBar = state.data?.bars[state.replay.cursorIndex] || null;

    React.useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement) return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    toggleReplayPlay();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    stepReplay(1);
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    stepReplay(-1);
                    break;
                case 'Escape':
                    e.preventDefault();
                    stopReplay();
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [toggleReplayPlay, stepReplay, stopReplay]);

    if (isReplaySelectMode) {
        return (
            <div
                className="flex items-center justify-center px-4 py-2 gap-4"
                style={{
                    background: CHART_THEME.bgSecondary,
                    borderTop: `2px solid ${CHART_THEME.accent}`,
                }}
            >
                <div className="flex items-center gap-3">
                    <div 
                        className="text-sm font-mono font-bold"
                        style={{ color: CHART_THEME.accent }}
                    >
                        Click on chart to set replay start point
                    </div>
                </div>
                <button
                    onClick={exitReplaySelectMode}
                    className="px-3 py-1 text-xs font-mono font-bold rounded"
                    style={{
                        background: CHART_THEME.downColor,
                        color: '#fff',
                    }}
                >
                    Cancel
                </button>
            </div>
        );
    }

    return (
        <div
            className="flex flex-col gap-2 px-4 py-2"
            style={{
                background: CHART_THEME.bgSecondary,
                borderTop: `1px solid ${CHART_THEME.border}`,
                minWidth: 400,
            }}
        >
            {/* Controls Row */}
            <div className="flex items-center justify-between">
                {/* Playback Controls */}
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => stepReplay(-1)}
                        className="w-7 h-7 flex items-center justify-center text-xs font-mono rounded"
                        style={{
                            background: CHART_THEME.bgPanel,
                            color: CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                        }}
                        title="Step backward"
                    >
                        {'<<'}
                    </button>

                    <button
                        onClick={toggleReplayPlay}
                        className="w-8 h-8 flex items-center justify-center text-sm font-bold rounded"
                        style={{
                            background: state.replay.isPlaying ? CHART_THEME.downColor : CHART_THEME.accent,
                            color: state.replay.isPlaying ? '#fff' : CHART_THEME.bgPrimary,
                        }}
                        title={state.replay.isPlaying ? "Pause" : "Play"}
                    >
                        {state.replay.isPlaying ? '||' : '>'}
                    </button>

                    <button
                        onClick={() => stepReplay(1)}
                        className="w-7 h-7 flex items-center justify-center text-xs font-mono rounded"
                        style={{
                            background: CHART_THEME.bgPanel,
                            color: CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                        }}
                        title="Step forward"
                    >
                        {'>>'}
                    </button>

                    <button
                        onClick={stopReplay}
                        className="px-2 py-1 text-xs font-mono rounded ml-2"
                        style={{
                            background: CHART_THEME.downColor + '20',
                            color: CHART_THEME.downColor,
                            border: `1px solid ${CHART_THEME.downColor}40`,
                        }}
                        title="Exit replay"
                    >
                        Exit
                    </button>
                </div>

                {/* Bar Info */}
                {currentBar && (
                    <div 
                        className="flex items-center gap-2 px-2 py-1 rounded text-[11px] font-mono"
                        style={{ background: CHART_THEME.bgPanel }}
                    >
                        <span style={{ color: CHART_THEME.textSecondary }}>
                            {state.replay.cursorIndex - state.replay.startIndex + 1}/{totalBars - state.replay.startIndex}
                        </span>
                        <span style={{ color: currentBar.close >= currentBar.open ? CHART_THEME.upColor : CHART_THEME.downColor }}>
                            {currentBar.close.toFixed(2)}
                        </span>
                    </div>
                )}

                {/* Speed Controls */}
                <div className="flex items-center gap-1">
                    <span className="text-[10px] font-mono mr-1" style={{ color: CHART_THEME.textSecondary }}>
                        Speed:
                    </span>
                    {([1, 2, 5, 10] as const).map(speed => (
                        <button
                            key={speed}
                            onClick={() => setReplaySpeed(speed)}
                            className="px-1.5 py-0.5 text-[10px] font-mono rounded"
                            style={{
                                background: state.replay.speed === speed ? CHART_THEME.accent : CHART_THEME.bgPanel,
                                color: state.replay.speed === speed ? CHART_THEME.bgPrimary : CHART_THEME.textSecondary,
                            }}
                        >
                            {speed}x
                        </button>
                    ))}
                </div>
            </div>

            {/* Progress Bar */}
            <div
                className="relative h-1.5 rounded-full cursor-pointer"
                style={{ background: CHART_THEME.bgPanel }}
            >
                <div
                    className="absolute top-0 left-0 h-full rounded-full transition-all duration-75"
                    style={{
                        width: `${progress}%`,
                        background: CHART_THEME.accent,
                    }}
                />
            </div>
        </div>
    );
}


// =============================================================================
// MAIN EXPORT
// =============================================================================

export default function Q360ChartCore(props: Q360ChartCoreProps) {
    const { symbol, timeframe, ...rest } = props;

    return (
        <ChartProvider initialSymbol={symbol} initialTimeframe={timeframe}>
            <ChartInner {...rest} />
        </ChartProvider>
    );
}
