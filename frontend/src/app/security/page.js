"use client";

import React, { useState, useEffect, useRef, Suspense, useCallback, useMemo } from 'react';
import { fetchSecurityDetail, fetchIntradayMarketData, fetchOptionsChain, fetchSecurityIndicators, fetchFundamentals, fetchMarketIntraday } from '@/lib/api';
import { getNseOptionsChain, getNseEquity, getNseIntraday, getNseTradeInfo, getNseCorporateInfo, getNseHistorical, getNseEarnings, getEarningsWithFallback, getOptionsWithFallback, isNseApiHealthy } from '@/lib/api/nse_india';
import TerminalPanel from '@/components/TerminalPanel';
import PageGrid from '@/components/PageGrid';
import StatCard from '@/components/StatCard';
import { PlotlyChart } from '@/components/ui/plotly-chart';
import OrderBookPanel from '@/components/OrderBookPanel';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import DrawdownPanel from '@/components/security/DrawdownPanel';
import EtfLookThrough from '@/components/security/EtfLookThrough';
import VolSurfacePanel from '@/components/security/VolSurfacePanel';
import { MarketControlBar, RealizedVolatilityStrip, SessionRangeContext, NewsEventsFeed, calculateVWAP } from '@/components/security/IntradayComponents';
import dynamic from 'next/dynamic';

import { useSearchParams } from 'next/navigation';

// Dynamic import for Q360ChartCore (avoid SSR issues)
const IntradayChartWrapper = dynamic(
    () => import('@/components/chart_engine/IntradayChartWrapper'),
    { ssr: false, loading: () => <div className="h-full flex items-center justify-center text-terminal-dim font-mono">Loading Chart Engine...</div> }
);

function SecurityPageContent() {
    const searchParams = useSearchParams();
    const initialSymbol = searchParams.get('symbol') || "AAPL";
    const [symbol, setSymbol] = useState(initialSymbol);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [period, setPeriod] = useState("1y");
    const [viewMode, setViewMode] = useState("daily"); // daily, intraday
    const [intradayInterval, setIntradayInterval] = useState("5m");
    const [activeTab, setActiveTab] = useState("chart"); // chart, options, earnings, macro, analysis
    const [optionsData, setOptionsData] = useState(null);
    const [liveQuote, setLiveQuote] = useState(null);
    const [liquidity, setLiquidity] = useState(null);
    const [fundamentals, setFundamentals] = useState(null);

    // === NSE INDIA SPECIFIC STATE ===
    const [nseData, setNseData] = useState(null); // Full NSE equity data
    const [nseTradeInfo, setNseTradeInfo] = useState(null); // Trade statistics
    const [nseCorporateInfo, setNseCorporateInfo] = useState(null); // Corporate info
    const [nseEarnings, setNseEarnings] = useState(null); // Earnings data

    // === DATA SUB-TABS (inside chart view) ===
    const [dataSubTab, setDataSubTab] = useState("fundamentals"); // fundamentals, trade, equity

    // === INTRADAY-SPECIFIC STATE ===
    const [intradayBars, setIntradayBars] = useState([]); // For VWAP and volatility calculations
    const [intradayNews, setIntradayNews] = useState([]);
    const [newsLoading, setNewsLoading] = useState(false);
    const [sessionInfo, setSessionInfo] = useState(null); // { high, low, atr }

    // Helper function to detect if symbol is an Indian stock (NSE/BSE)
    const isIndianStock = useMemo(() => {
        // NSE symbols end with .NS, BSE with .BO, or common Indian stock patterns
        const upperSymbol = symbol.toUpperCase();
        const indianSuffixes = ['.NS', '.BO', '.NSE', '.BSE'];
        const commonIndianStocks = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'HINDUNILVR', 
            'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'BAJFINANCE',
            'AXISBANK', 'ASIANPAINT', 'MARUTI', 'TITAN', 'SUNPHARMA', 
            'ULTRACEMCO', 'WIPRO', 'NESTLEIND', 'HCLTECH', 'TECHM',
            'ONGC', 'NTPC', 'POWERGRID', 'TATAMOTORS', 'TATASTEEL', 
            'ADANIENT', 'ADANIPORTS', 'COALINDIA', 'JSWSTEEL', 'M&M'
        ];
        
        // Check for suffixes
        if (indianSuffixes.some(suffix => upperSymbol.endsWith(suffix))) {
            return true;
        }
        
        // Check for common Indian stocks (without suffix)
        const baseSymbol = upperSymbol.replace(/\.(NS|BO|NSE|BSE)$/i, '');
        return commonIndianStocks.includes(baseSymbol);
    }, [symbol]);

    // Get the clean symbol for NSE API (remove suffix)
    const nseSymbol = useMemo(() => {
        return symbol.toUpperCase().replace(/\.(NS|BO|NSE|BSE)$/i, '');
    }, [symbol]);

    // Indicators State
    const [indicators, setIndicators] = useState({
        rsi: true,
        macd: true,
        stoch: false,
        roc: false,
        cci: false,
        adx: false,
        mfi: false
    });

    // Toast State
    const [toast, setToast] = useState(null);

    useEffect(() => {
        if (toast) {
            const timer = setTimeout(() => setToast(null), 3000);
            return () => clearTimeout(timer);
        }
    }, [toast]);

    const loadData = useCallback(async () => {
        // setLoading(true); // Don't full wipe on param change if possible, but simpler to reload
        if (activeTab === "chart") setLoading(true); // minimal loading state

        try {
            // Unified fetch for both Daily and Intraday
            const interval = viewMode === "intraday" ? intradayInterval : "1d";

            // Fetch Price Data
            const res = await fetchSecurityDetail(symbol, period, interval);

            // If price data fails (e.g. no intraday), res might be empty or error handled in api.js
            // Our api.js throws if not ok.

            if (activeTab === "chart") {
                // Fetch Indicators separately
                const indRes = await fetchSecurityIndicators(symbol, period, interval);

                // Fetch Fundamentals (E7)
                try {
                    const fundRes = await fetchFundamentals(symbol, true);
                    setFundamentals(fundRes);
                } catch (e) {
                    console.log('Fundamentals not available for', symbol);
                    setFundamentals(null);
                }

                // === INTRADAY-SPECIFIC DATA LOADING ===
                let intradayIndicators = null;
                if (viewMode === "intraday") {
                    // Fetch intraday bars for VWAP and volatility calculations
                    try {
                        const intradayRes = await fetchMarketIntraday(symbol, intradayInterval);
                        if (intradayRes?.bars) {
                            setIntradayBars(intradayRes.bars);
                            // Extract session info
                            const highs = intradayRes.bars.map(b => b.high);
                            const lows = intradayRes.bars.map(b => b.low);
                            setSessionInfo({
                                high: Math.max(...highs),
                                low: Math.min(...lows),
                                atr: intradayRes.atr || null // Backend may provide this
                            });
                        }
                        // USE INTRADAY INDICATORS from this response!
                        if (intradayRes?.indicators) {
                            intradayIndicators = intradayRes.indicators;
                        }
                    } catch (e) {
                        console.log('Intraday bars not available:', e);
                        setIntradayBars([]);
                        setSessionInfo(null);
                    }
                }

                // Merge response
                // For INTRADAY: use indicators from fetchMarketIntraday
                // For DAILY: use indicators from fetchSecurityIndicators
                const fullData = {
                    ...res,
                    indicators: viewMode === "intraday" 
                        ? (intradayIndicators || {})
                        : (indRes.insufficient_data ? {} : indRes.indicators),
                    global_insufficient: viewMode === "intraday" ? false : indRes.insufficient_data
                };

                setData(fullData);

                // Set initial live quote
                if (res.price && res.price.close && res.price.close.length > 0) {
                    const last = res.price.close[res.price.close.length - 1];
                    const prev = res.price.close.length > 1 ? res.price.close[res.price.close.length - 2] : last;
                    setLiveQuote({
                        price: last,
                        change: last - prev,
                        pctChange: prev !== 0 ? (last - prev) / prev : 0
                    });
                }
            } else {
                // Just set minimal data for header if needed, or keeping old data
                // If switching tabs, we might want to keep price data.
                // For now, re-fetch detail to keep header alive.
                setData(res);
            }

            // === OPTIONS TAB: Use NSE India API for Indian stocks ===
            if (activeTab === "options") {
                if (isIndianStock) {
                    // Use NSE India API for Indian stocks (FREE, reduces yfinance load)
                    try {
                        console.log(`[NSE] Fetching options chain for ${nseSymbol}`);
                        const nseOpts = await getNseOptionsChain(nseSymbol);
                        
                        // NSE API returns data in a different format, normalize it
                        const normalizedOptions = {
                            expirationDates: nseOpts?.records?.expiryDates || [],
                            underlyingValue: nseOpts?.records?.underlyingValue || 0,
                            options: []
                        };
                        
                        // Parse NSE options data
                        if (nseOpts?.records?.data) {
                            nseOpts.records.data.forEach(row => {
                                // Add call option
                                if (row.CE) {
                                    normalizedOptions.options.push({
                                        type: 'call',
                                        strike: row.strikePrice,
                                        expiry: row.expiryDate,
                                        lastPrice: row.CE.lastPrice,
                                        bid: row.CE.bidPrice,
                                        ask: row.CE.askPrice,
                                        volume: row.CE.totalTradedVolume,
                                        openInterest: row.CE.openInterest,
                                        change: row.CE.change,
                                        pctChange: row.CE.pChange,
                                        iv: row.CE.impliedVolatility,
                                        delta: null, // NSE doesn't provide Greeks
                                        gamma: null,
                                        theta: null,
                                        vega: null
                                    });
                                }
                                // Add put option
                                if (row.PE) {
                                    normalizedOptions.options.push({
                                        type: 'put',
                                        strike: row.strikePrice,
                                        expiry: row.expiryDate,
                                        lastPrice: row.PE.lastPrice,
                                        bid: row.PE.bidPrice,
                                        ask: row.PE.askPrice,
                                        volume: row.PE.totalTradedVolume,
                                        openInterest: row.PE.openInterest,
                                        change: row.PE.change,
                                        pctChange: row.PE.pChange,
                                        iv: row.PE.impliedVolatility,
                                        delta: null,
                                        gamma: null,
                                        theta: null,
                                        vega: null
                                    });
                                }
                            });
                        }
                        
                        setOptionsData(normalizedOptions);

                        // Also fetch trade info and corporate info for Indian stocks
                        try {
                            const [tradeInfo, corpInfo] = await Promise.all([
                                getNseTradeInfo(nseSymbol),
                                getNseCorporateInfo(nseSymbol)
                            ]);
                            setNseTradeInfo(tradeInfo);
                            setNseCorporateInfo(corpInfo);
                        } catch (nseErr) {
                            console.log('[NSE] Trade/Corporate info not available:', nseErr);
                        }
                    } catch (nseErr) {
                        console.error('[NSE] Options chain error, falling back to yfinance:', nseErr);
                        // Fallback to yfinance if NSE API fails
                        const opts = await fetchOptionsChain(symbol);
                        setOptionsData(opts);
                    }
                } else {
                    // Use yfinance for US stocks
                    const opts = await fetchOptionsChain(symbol);
                    setOptionsData(opts);
                }
            } else if (activeTab === "earnings") {
                // Fetch earnings using fallback system (NSE India or yfinance)
                try {
                    console.log(`[Earnings] Fetching for ${symbol}`);
                    const earnings = await getEarningsWithFallback(isIndianStock ? nseSymbol : symbol);
                    setNseEarnings(earnings);
                } catch (err) {
                    console.error('[Earnings] Error:', err);
                    setNseEarnings({ error: err.message });
                }
            }

            // === FETCH NSE SPECIFIC DATA FOR INDIAN STOCKS ===
            if (isIndianStock && (activeTab === "chart" || activeTab === "earnings")) {
                try {
                    const [nseEquity, tradeInfo, corpInfo] = await Promise.all([
                        getNseEquity(nseSymbol),
                        getNseTradeInfo(nseSymbol),
                        getNseCorporateInfo(nseSymbol)
                    ]);
                    setNseData(nseEquity);
                    setNseTradeInfo(tradeInfo);
                    setNseCorporateInfo(corpInfo);
                    console.log('[NSE] Fetched full data for', nseSymbol);
                } catch (nseErr) {
                    console.log('[NSE] Failed to fetch NSE data:', nseErr);
                }
            }

        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [symbol, period, viewMode, intradayInterval, activeTab, isIndianStock, nseSymbol]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const toggleIndicator = (key) => {
        setIndicators(prev => {
            const isActive = prev[key];
            if (!isActive) {
                // Check limit
                const activeCount = Object.values(prev).filter(v => v).length;
                if (activeCount >= 2) {
                    setToast("Maximum 2 indicators allowed. Please deselect one first.");
                    return prev;
                }
            }
            return { ...prev, [key]: !prev[key] };
        });
    };

    // === INTRADAY VWAP AND CONTEXT (must be before conditional returns) ===
    const vwapData = useMemo(() => {
        if (viewMode !== "intraday" || !intradayBars || intradayBars.length === 0) {
            return null;
        }
        const vwapValues = calculateVWAP(intradayBars);
        const closes = intradayBars.map(b => b.close);
        const lastClose = closes[closes.length - 1];
        const lastVwap = vwapValues[vwapValues.length - 1];
        
        return {
            vwapValues,
            closes,
            lastClose,
            lastVwap,
            dates: intradayBars.map(b => b.timestamp || b.ts || b.date)
        };
    }, [viewMode, intradayBars]);

    if (loading && !data) {
        return <div className="p-4 text-terminal-dim font-mono animate-pulse">LOADING SECURITY DATA...</div>;
    }

    if (!data) return null;

    // --- Chart Configs ---
    const priceTraces = [
        {
            x: data.price.dates,
            open: data.price.open,
            high: data.price.high,
            low: data.price.low,
            close: data.price.close,
            type: 'candlestick',
            name: symbol,
            increasing: { line: { color: '#00ff6a', width: 1 }, fillcolor: '#00ff6a' },
            decreasing: { line: { color: '#ff3b3b', width: 1 }, fillcolor: '#ff3b3b' }
        }
    ];

    // Add SMAs for Daily
    if (viewMode === "daily") {
        if (data.price.sma_50) {
            priceTraces.push({
                x: data.price.dates,
                y: data.price.sma_50,
                type: 'scattergl',
                mode: 'lines',
                name: 'SMA 50',
                line: { color: '#f7c843', width: 1 }
            });
        }
        if (data.price.sma_200) {
            priceTraces.push({
                x: data.price.dates,
                y: data.price.sma_200,
                type: 'scattergl',
                mode: 'lines',
                name: 'SMA 200',
                line: { color: '#00bfff', width: 1 }
            });
        }
    }

    // Indicators Logic
    const indicatorPanels = [];

    // keys: rsi, macd, stoch, roc, cci, adx, mfi
    const activeIndicators = Object.keys(indicators).filter(k => indicators[k]);

    activeIndicators.forEach(key => {
        // Check valid data
        // For intraday, backend uses keys like 'rsi_14', 'macd_12_26_9'
        // For daily, backend uses uppercase like 'RSI', 'MACD'
        const intradayKeyMap = {
            'rsi': 'rsi_14',
            'macd': 'macd_12_26_9',
            'stoch': 'stoch',
            'roc': 'roc',
            'cci': 'cci',
            'adx': 'adx',
            'mfi': 'mfi'
        };
        const backendKey = viewMode === 'intraday' ? intradayKeyMap[key] : key.toUpperCase();
        const indData = data.indicators ? data.indicators[backendKey] : null;

        let panelContent = null;
        let title = key.toUpperCase();

        // Check if data is valid - for intraday, indData is an array directly
        const isIntraday = viewMode === 'intraday';
        const seriesList = isIntraday ? (Array.isArray(indData) ? indData : []) : (indData?.series || []);
        const hasInsufficientData = isIntraday 
            ? (seriesList.length < 2) 
            : (indData?.insufficient_data || data.global_insufficient);

        if (!indData || hasInsufficientData) {
            panelContent = {
                title: title,
                isPlaceholder: true,
                message: seriesList.length < 2 ? "Awaiting more data..." : "Not enough history for indicator"
            };
        } else {
            // Shapes for reference lines
            const shapes = (indData.reference_levels || []).map(level => ({
                type: 'line', x0: 0, x1: 1, xref: 'paper', y0: level, y1: level,
                line: { color: '#666', width: 0.5, dash: 'dot' }
            }));

            // For intraday: use indices for continuous display without gaps
            // For daily: use timestamps
            const xValues = isIntraday 
                ? seriesList.map((_, idx) => idx) 
                : seriesList.map(s => s.ts);

            if (key === 'macd') {
                panelContent = {
                    title: "MACD (12, 26, 9)",
                    traces: [
                        { x: xValues, y: seriesList.map(s => s.hist), type: 'bar', name: 'Hist', marker: { color: seriesList.map(s => s.hist >= 0 ? '#00ff6a' : '#ff3b3b') } },
                        { x: xValues, y: seriesList.map(s => s.macd), type: 'scattergl', mode: 'lines', name: 'MACD', line: { color: '#00bfff', width: 1 } },
                        { x: xValues, y: seriesList.map(s => s.signal), type: 'scattergl', mode: 'lines', name: 'Signal', line: { color: '#ff9f1c', width: 1 } }
                    ],
                    shapes: shapes,
                    hideXAxis: isIntraday // Flag to hide x-axis labels for index-based charts
                };
            } else if (key === 'stoch') {
                panelContent = {
                    title: "STOCHASTIC (14, 3, 3)",
                    traces: [
                        { x: xValues, y: seriesList.map(s => s.k), type: 'scattergl', mode: 'lines', name: '%K', line: { color: '#00bfff', width: 1 } },
                        { x: xValues, y: seriesList.map(s => s.d), type: 'scattergl', mode: 'lines', name: '%D', line: { color: '#ff9f1c', width: 1 } }
                    ],
                    shapes: shapes,
                    range: [0, 100],
                    hideXAxis: isIntraday
                };
            } else {
                // Simple line indicator (RSI, ROC, CCI, ADX, MFI)
                panelContent = {
                    title: title,
                    traces: [{
                        x: xValues,
                        y: seriesList.map(s => s.value),
                        type: 'scattergl',
                        mode: 'lines',
                        name: title,
                        line: { color: '#e5e5e5', width: 1 }
                    }],
                    shapes: shapes,
                    hideXAxis: isIntraday
                };
                if (key === 'rsi' || key === 'mfi') panelContent.range = [0, 100];
            }
        }

        if (panelContent) indicatorPanels.push(panelContent);
    });

    return (
        <PageGrid>
            {toast && (
                <div className="fixed top-20 right-4 z-50 bg-terminal-dark border border-terminal-red text-terminal-red px-4 py-2 rounded shadow-lg font-mono text-sm animate-in fade-in slide-in-from-top-2">
                    {toast}
                </div>
            )}
            {/* Minimal Page Header - Only tabs since chart has its own controls */}
            <div className="col-span-12 flex items-center justify-end bg-terminal-dark border border-terminal-gray px-3 py-1.5 mb-2">
                <div className="flex gap-1 text-xs font-mono items-center">
                    <button onClick={() => setActiveTab("chart")} className={`px-2 py-0.5 text-[10px] ${activeTab === "chart" ? "bg-terminal-yellow text-terminal-black" : "text-terminal-dim hover:text-terminal-text"}`}>CHART</button>
                    <button onClick={() => setActiveTab("options")} className={`px-2 py-0.5 text-[10px] ${activeTab === "options" ? "bg-terminal-yellow text-terminal-black" : "text-terminal-dim hover:text-terminal-text"}`}>OPTIONS</button>
                    {isIndianStock && (
                        <button onClick={() => setActiveTab("earnings")} className={`px-2 py-0.5 text-[10px] ${activeTab === "earnings" ? "bg-terminal-cyan text-terminal-black" : "text-terminal-cyan/60 hover:text-terminal-cyan"}`}>EARNINGS</button>
                    )}
                    <button onClick={() => setActiveTab("analysis")} className={`px-2 py-0.5 text-[10px] ${activeTab === "analysis" ? "bg-terminal-yellow text-terminal-black" : "text-terminal-dim hover:text-terminal-text"}`}>ANALYSIS</button>
                </div>
            </div>

            {activeTab === "chart" && (
                <>
                    {/* Main Chart - Full height using unified chart engine for ALL timeframes */}
                    <div className="col-span-12 flex flex-col gap-2">
                        <div className="h-[600px]">
                            <IntradayChartWrapper
                                symbol={symbol}
                                interval={viewMode === "intraday" ? intradayInterval : period}
                                height={580}
                                onSymbolChange={(sym) => setSymbol(sym)}
                                onIntervalChange={(tf) => {
                                    // Determine if this is an intraday or daily timeframe
                                    const intradayTfs = ['1m', '5m', '15m', '30m', '1h'];
                                    if (intradayTfs.includes(tf)) {
                                        setViewMode("intraday");
                                        setIntradayInterval(tf);
                                    } else {
                                        setViewMode("daily");
                                        setPeriod(tf);
                                    }
                                }}
                                onIndicatorsChange={(newIndicators) => {
                                    setIndicators(prev => ({
                                        ...prev,
                                        ...newIndicators
                                    }));
                                }}
                            />
                        </div>

                        {/* Indicators are now handled within the chart engine - no duplicate panels needed */}

                        {/* === BOTTOM PANELS: Sub-tabs for Data Views === */}
                        {viewMode === "daily" ? (
                            /* DAILY: Sub-tabs for Fundamentals / Trade Info / Equity Details */
                            <div className="mt-1">
                                {/* Sub-tab Navigation */}
                                <div className="flex gap-1 mb-2">
                                    <button 
                                        onClick={() => setDataSubTab("fundamentals")}
                                        className={`px-3 py-1 text-[10px] font-mono ${dataSubTab === "fundamentals" ? "bg-terminal-yellow text-black" : "bg-terminal-gray/20 text-terminal-dim hover:text-terminal-text"}`}
                                    >
                                        FUNDAMENTALS
                                    </button>
                                    <button 
                                        onClick={() => setDataSubTab("trade")}
                                        className={`px-3 py-1 text-[10px] font-mono ${dataSubTab === "trade" ? "bg-terminal-yellow text-black" : "bg-terminal-gray/20 text-terminal-dim hover:text-terminal-text"}`}
                                    >
                                        TRADE INFO {isIndianStock && <span className="text-terminal-cyan ml-1">[NSE]</span>}
                                    </button>
                                    <button 
                                        onClick={() => setDataSubTab("equity")}
                                        className={`px-3 py-1 text-[10px] font-mono ${dataSubTab === "equity" ? "bg-terminal-yellow text-black" : "bg-terminal-gray/20 text-terminal-dim hover:text-terminal-text"}`}
                                    >
                                        EQUITY DETAILS {isIndianStock && <span className="text-terminal-cyan ml-1">[NSE]</span>}
                                    </button>
                                </div>

                                {/* Sub-tab Content */}
                                <div className="h-[160px]">
                                    {/* FUNDAMENTALS Sub-tab */}
                                    {dataSubTab === "fundamentals" && (
                                        <div className="grid grid-cols-12 gap-2 h-full">
                                            <div className="col-span-12 h-full overflow-auto">
                                                {fundamentals && !fundamentals.error ? (
                                                    <TerminalPanel title="FUNDAMENTALS" subtitle={fundamentals.name || symbol} className="h-full">
                                                        <div className="flex flex-col gap-1 text-[10px] font-mono h-full overflow-auto">
                                                            <div className="grid grid-cols-6 gap-1">
                                                                <StatCard label="P/E" value={fundamentals.pe?.toFixed(1) || 'N/A'} />
                                                                <StatCard label="P/B" value={fundamentals.pb?.toFixed(1) || 'N/A'} />
                                                                <StatCard label="ROE" value={fundamentals.roe ? `${(fundamentals.roe * 100).toFixed(1)}%` : 'N/A'} />
                                                                <StatCard label="EPS" value={fundamentals.eps_trailing?.toFixed(2) || 'N/A'} />
                                                                <StatCard label="DIV" value={fundamentals.dividend_yield ? `${(fundamentals.dividend_yield * 100).toFixed(1)}%` : 'N/A'} />
                                                                <StatCard label="D/E" value={fundamentals.debt_to_equity?.toFixed(1) || 'N/A'} />
                                                            </div>
                                                            {fundamentals.recommendation && (
                                                                <div className="mt-1 pt-1 border-t border-terminal-gray text-[9px]">
                                                                    <span className="text-terminal-dim">ANALYST: </span>
                                                                    <span className={`font-bold ${fundamentals.recommendation === 'buy' || fundamentals.recommendation === 'strong_buy' ? 'text-terminal-green' : fundamentals.recommendation === 'sell' ? 'text-terminal-red' : 'text-terminal-yellow'}`}>
                                                                        {fundamentals.recommendation?.toUpperCase()}
                                                                    </span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </TerminalPanel>
                                                ) : (
                                                    <div className="h-full flex items-center justify-center text-terminal-dim text-xs">Loading fundamentals...</div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {/* TRADE INFO Sub-tab */}
                                    {dataSubTab === "trade" && (
                                        <div className="grid grid-cols-12 gap-2 h-full">
                                            <div className="col-span-12 h-full">
                                                {isIndianStock && nseTradeInfo ? (
                                                    <TerminalPanel title="TRADE INFO" subtitle={`${nseSymbol} [NSE]`} className="h-full">
                                                        <div className="grid grid-cols-6 gap-2 text-[10px] font-mono">
                                                            <StatCard label="VOLUME" value={(nseTradeInfo.securityWiseDP?.quantityTraded || 0).toLocaleString()} />
                                                            <StatCard label="DELIVERY %" value={`${nseTradeInfo.securityWiseDP?.deliveryToTradedQuantity?.toFixed(1) || 'N/A'}%`} />
                                                            <StatCard label="TRADED VAL" value={`₹${((nseTradeInfo.marketDeptOrderBook?.tradeInfo?.totalTradedValue || 0)).toFixed(1)} Cr`} />
                                                            <StatCard label="MKT CAP" value={`₹${((nseTradeInfo.marketDeptOrderBook?.tradeInfo?.totalMarketCap || 0) / 100).toFixed(0)} Cr`} />
                                                            <StatCard label="DAILY VOL" value={`${nseTradeInfo.marketDeptOrderBook?.tradeInfo?.cmDailyVolatility || 'N/A'}%`} />
                                                            <StatCard label="ANNUAL VOL" value={`${nseTradeInfo.marketDeptOrderBook?.tradeInfo?.cmAnnualVolatility || 'N/A'}%`} />
                                                        </div>
                                                        <div className="grid grid-cols-4 gap-2 mt-2 text-[10px] font-mono">
                                                            <StatCard label="VAR MARGIN" value={`${nseTradeInfo.marketDeptOrderBook?.valueAtRisk?.applicableMargin || 'N/A'}%`} />
                                                            <StatCard label="IMPACT COST" value={nseTradeInfo.marketDeptOrderBook?.tradeInfo?.impactCost?.toFixed(2) || 'N/A'} />
                                                            <StatCard label="BUY QTY" value={(nseTradeInfo.marketDeptOrderBook?.totalBuyQuantity || 0).toLocaleString()} />
                                                            <StatCard label="SELL QTY" value={(nseTradeInfo.marketDeptOrderBook?.totalSellQuantity || 0).toLocaleString()} />
                                                        </div>
                                                    </TerminalPanel>
                                                ) : !isIndianStock && data?.liquidity ? (
                                                    <TerminalPanel title="TRADE INFO" subtitle={`${symbol} [US]`} className="h-full">
                                                        <div className="grid grid-cols-6 gap-2 text-[10px] font-mono">
                                                            <StatCard label="VOLUME" value={data.latest?.volume?.toLocaleString() || 'N/A'} />
                                                            <StatCard label="AVG VOL" value={data.liquidity?.avg_volume?.toLocaleString() || 'N/A'} />
                                                            <StatCard label="SPREAD" value={`${(data.liquidity?.spread * 100)?.toFixed(3) || 'N/A'}%`} />
                                                            <StatCard label="LIQUIDITY" value={data.liquidity?.liquidity_score?.toFixed(2) || 'N/A'} />
                                                            <StatCard label="BETA" value={data.risk_profile?.beta?.toFixed(2) || 'N/A'} />
                                                            <StatCard label="VOL 20D" value={`${(data.risk_profile?.volatility * 100)?.toFixed(1) || 'N/A'}%`} />
                                                        </div>
                                                    </TerminalPanel>
                                                ) : (
                                                    <div className="h-full flex items-center justify-center text-terminal-dim text-xs">
                                                        {isIndianStock ? 'Loading NSE trade info...' : 'Loading trade info...'}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {/* EQUITY DETAILS Sub-tab */}
                                    {dataSubTab === "equity" && (
                                        <div className="grid grid-cols-12 gap-2 h-full">
                                            <div className="col-span-12 h-full">
                                                {isIndianStock && nseData ? (
                                                    <TerminalPanel title="EQUITY DETAILS" subtitle={`${nseData.info?.companyName || nseSymbol} [NSE]`} className="h-full">
                                                        <div className="grid grid-cols-2 gap-4 text-[10px] font-mono">
                                                            <div>
                                                                <div className="text-terminal-dim mb-1">COMPANY INFO</div>
                                                                <div className="space-y-0.5">
                                                                    <div><span className="text-terminal-dim">Industry:</span> <span className="text-terminal-text">{nseData.info?.industry || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">ISIN:</span> <span className="text-terminal-cyan">{nseData.info?.isin || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">Listing Date:</span> <span className="text-terminal-text">{nseData.info?.listingDate || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">Series:</span> <span className="text-terminal-text">{nseData.info?.activeSeries?.join(', ') || 'EQ'}</span></div>
                                                                </div>
                                                            </div>
                                                            <div>
                                                                <div className="text-terminal-dim mb-1">MARKET DATA</div>
                                                                <div className="space-y-0.5">
                                                                    <div><span className="text-terminal-dim">P/E (Sector):</span> <span className="text-terminal-text">{nseData.metadata?.pdSectorPe?.toFixed(2) || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">P/E (Symbol):</span> <span className="text-terminal-text">{nseData.metadata?.pdSymbolPe?.toFixed(2) || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">Sector Index:</span> <span className="text-terminal-cyan">{nseData.metadata?.pdSectorInd || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">FNO:</span> <span className={nseData.info?.isFNOSec ? 'text-terminal-green' : 'text-terminal-red'}>{nseData.info?.isFNOSec ? 'YES' : 'NO'}</span></div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </TerminalPanel>
                                                ) : !isIndianStock && fundamentals ? (
                                                    <TerminalPanel title="EQUITY DETAILS" subtitle={`${fundamentals.name || symbol} [US]`} className="h-full">
                                                        <div className="grid grid-cols-2 gap-4 text-[10px] font-mono">
                                                            <div>
                                                                <div className="text-terminal-dim mb-1">COMPANY INFO</div>
                                                                <div className="space-y-0.5">
                                                                    <div><span className="text-terminal-dim">Name:</span> <span className="text-terminal-text">{fundamentals.name || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">Sector:</span> <span className="text-terminal-text">{fundamentals.sector || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">Industry:</span> <span className="text-terminal-text">{fundamentals.industry || 'N/A'}</span></div>
                                                                </div>
                                                            </div>
                                                            <div>
                                                                <div className="text-terminal-dim mb-1">VALUATION</div>
                                                                <div className="space-y-0.5">
                                                                    <div><span className="text-terminal-dim">Mkt Cap:</span> <span className="text-terminal-text">${((fundamentals.market_cap || 0) / 1e9).toFixed(1)}B</span></div>
                                                                    <div><span className="text-terminal-dim">EV/EBITDA:</span> <span className="text-terminal-text">{fundamentals.ev_ebitda?.toFixed(1) || 'N/A'}</span></div>
                                                                    <div><span className="text-terminal-dim">PEG:</span> <span className="text-terminal-text">{fundamentals.peg?.toFixed(2) || 'N/A'}</span></div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </TerminalPanel>
                                                ) : (
                                                    <div className="h-full flex items-center justify-center text-terminal-dim text-xs">
                                                        {isIndianStock ? 'Loading NSE equity details...' : 'Loading equity details...'}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : null}
                    </div>
                </>
            )}

            {
                activeTab === "options" && (
                    <div className="col-span-12 h-[700px] overflow-auto bg-terminal-dark border border-terminal-gray p-4">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-lg font-bold text-terminal-yellow">
                                OPTION CHAIN {isIndianStock && <span className="text-xs text-terminal-cyan ml-2">[NSE India]</span>}
                            </h2>
                            {optionsData?.underlyingValue && (
                                <div className="text-sm font-mono">
                                    <span className="text-terminal-dim">Underlying: </span>
                                    <span className="text-terminal-text font-bold">₹{optionsData.underlyingValue.toLocaleString()}</span>
                                </div>
                            )}
                            {optionsData?.expirationDates?.length > 0 && (
                                <div className="text-xs font-mono text-terminal-dim">
                                    Expiries: {optionsData.expirationDates.slice(0, 3).join(', ')}
                                    {optionsData.expirationDates.length > 3 && ` +${optionsData.expirationDates.length - 3} more`}
                                </div>
                            )}
                        </div>
                        
                        {/* NSE Trade Info Panel for Indian Stocks */}
                        {isIndianStock && nseTradeInfo && (
                            <div className="grid grid-cols-6 gap-2 mb-4 p-2 bg-terminal-black border border-terminal-gray rounded">
                                <div className="text-center">
                                    <div className="text-[10px] text-terminal-dim">VOLUME</div>
                                    <div className="text-sm font-mono text-terminal-text">{(nseTradeInfo.totalTradedVolume || 0).toLocaleString()}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-[10px] text-terminal-dim">VALUE (Cr)</div>
                                    <div className="text-sm font-mono text-terminal-text">{((nseTradeInfo.totalTradedValue || 0) / 10000000).toFixed(2)}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-[10px] text-terminal-dim">DELIVERY %</div>
                                    <div className="text-sm font-mono text-terminal-cyan">{nseTradeInfo.deliveryToTradedQuantity?.toFixed(1) || 'N/A'}%</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-[10px] text-terminal-dim">52W HIGH</div>
                                    <div className="text-sm font-mono text-terminal-green">{nseTradeInfo.weekHighLow?.max?.toLocaleString() || 'N/A'}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-[10px] text-terminal-dim">52W LOW</div>
                                    <div className="text-sm font-mono text-terminal-red">{nseTradeInfo.weekHighLow?.min?.toLocaleString() || 'N/A'}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-[10px] text-terminal-dim">FACE VALUE</div>
                                    <div className="text-sm font-mono text-terminal-text">₹{nseTradeInfo.faceValue || 'N/A'}</div>
                                </div>
                            </div>
                        )}
                        
                        {optionsData && !optionsData.error ? (
                            <div className="grid grid-cols-2 gap-8">
                                {/* CALLS */}
                                <div>
                                    <h3 className="text-center text-terminal-green font-bold mb-2">CALLS</h3>
                                    <table className="w-full text-xs font-mono">
                                        <thead>
                                            <tr className="text-terminal-dim border-b border-terminal-gray">
                                                <th className="text-left py-1">Strike</th>
                                                <th className="text-right py-1">Last</th>
                                                <th className="text-right py-1">Chg%</th>
                                                {isIndianStock ? (
                                                    <>
                                                        <th className="text-right py-1">IV%</th>
                                                        <th className="text-right py-1">OI</th>
                                                        <th className="text-right py-1">Vol</th>
                                                    </>
                                                ) : (
                                                    <>
                                                        <th className="text-right py-1">Delta</th>
                                                        <th className="text-right py-1">Vega</th>
                                                    </>
                                                )}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {optionsData.options?.filter(o => o.type === 'call').slice(0, 25).map((opt, i) => (
                                                <tr key={i} className="border-b border-terminal-gray/30 hover:bg-terminal-gray/10">
                                                    <td className="py-1 text-terminal-text font-bold">{opt.strike}</td>
                                                    <td className="py-1 text-right text-terminal-green">{opt.lastPrice?.toFixed(2) || '-'}</td>
                                                    <td className={`py-1 text-right ${(opt.pctChange || opt.change) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                                        {opt.pctChange?.toFixed(1) || opt.change?.toFixed(1) || '-'}%
                                                    </td>
                                                    {isIndianStock ? (
                                                        <>
                                                            <td className="py-1 text-right text-terminal-cyan">{opt.iv?.toFixed(1) || '-'}</td>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.openInterest?.toLocaleString() || '-'}</td>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.volume?.toLocaleString() || '-'}</td>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.delta?.toFixed(2) || '-'}</td>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.vega?.toFixed(2) || '-'}</td>
                                                        </>
                                                    )}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                                
                                {/* PUTS */}
                                <div>
                                    <h3 className="text-center text-terminal-red font-bold mb-2">PUTS</h3>
                                    <table className="w-full text-xs font-mono">
                                        <thead>
                                            <tr className="text-terminal-dim border-b border-terminal-gray">
                                                <th className="text-left py-1">Strike</th>
                                                <th className="text-right py-1">Last</th>
                                                <th className="text-right py-1">Chg%</th>
                                                {isIndianStock ? (
                                                    <>
                                                        <th className="text-right py-1">IV%</th>
                                                        <th className="text-right py-1">OI</th>
                                                        <th className="text-right py-1">Vol</th>
                                                    </>
                                                ) : (
                                                    <>
                                                        <th className="text-right py-1">Delta</th>
                                                        <th className="text-right py-1">Vega</th>
                                                    </>
                                                )}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {optionsData.options?.filter(o => o.type === 'put').slice(0, 25).map((opt, i) => (
                                                <tr key={i} className="border-b border-terminal-gray/30 hover:bg-terminal-gray/10">
                                                    <td className="py-1 text-terminal-text font-bold">{opt.strike}</td>
                                                    <td className="py-1 text-right text-terminal-red">{opt.lastPrice?.toFixed(2) || '-'}</td>
                                                    <td className={`py-1 text-right ${(opt.pctChange || opt.change) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                                        {opt.pctChange?.toFixed(1) || opt.change?.toFixed(1) || '-'}%
                                                    </td>
                                                    {isIndianStock ? (
                                                        <>
                                                            <td className="py-1 text-right text-terminal-cyan">{opt.iv?.toFixed(1) || '-'}</td>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.openInterest?.toLocaleString() || '-'}</td>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.volume?.toLocaleString() || '-'}</td>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.delta?.toFixed(2) || '-'}</td>
                                                            <td className="py-1 text-right text-terminal-dim">{opt.vega?.toFixed(2) || '-'}</td>
                                                        </>
                                                    )}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ) : (
                            <div className="text-center text-terminal-dim p-8">
                                {optionsData?.error ? `Error: ${optionsData.error}` : "Loading Options Chain..."}
                                {isIndianStock && (
                                    <div className="mt-2 text-xs">
                                        Make sure the NSE API server is running: <code className="bg-terminal-black px-2 py-1 rounded">npx stock-nse-india serve --port 3001</code>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )
            }

            {/* === EARNINGS TAB (NSE India) === */}
            {
                activeTab === "earnings" && (
                    <div className="col-span-12 bg-terminal-dark border border-terminal-gray p-4 overflow-auto" style={{ minHeight: '600px' }}>
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-lg font-bold text-terminal-cyan">
                                EARNINGS & CORPORATE DATA <span className="text-xs text-terminal-dim ml-2">[NSE India]</span>
                            </h2>
                            {nseData?.info?.companyName && (
                                <span className="text-sm text-terminal-text font-mono">{nseData.info.companyName}</span>
                            )}
                        </div>

                        {nseEarnings && !nseEarnings.error ? (
                            <div className="grid grid-cols-12 gap-4">
                                {/* FINANCIAL RESULTS (Quarterly) */}
                                <div className="col-span-12 lg:col-span-8">
                                    <div className="bg-terminal-black border border-terminal-gray p-4 rounded">
                                        <h3 className="text-sm font-bold text-terminal-yellow mb-3">QUARTERLY FINANCIAL RESULTS</h3>
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-xs font-mono">
                                                <thead>
                                                    <tr className="text-terminal-dim border-b border-terminal-gray">
                                                        <th className="text-left py-2 px-2">Period</th>
                                                        <th className="text-right py-2 px-2">Income (₹L)</th>
                                                        <th className="text-right py-2 px-2">PAT (₹L)</th>
                                                        <th className="text-right py-2 px-2">EPS</th>
                                                        <th className="text-center py-2 px-2">Audited</th>
                                                        <th className="text-left py-2 px-2">Announced</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {nseEarnings.financial_results?.slice(0, 8).map((r, i) => (
                                                        <tr key={i} className="border-b border-terminal-gray/30 hover:bg-terminal-gray/10">
                                                            <td className="py-2 px-2 text-terminal-text">{r.period_end}</td>
                                                            <td className="py-2 px-2 text-right text-terminal-text">{r.income?.toLocaleString() || '-'}</td>
                                                            <td className={`py-2 px-2 text-right ${r.profit_after_tax >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                                                {r.profit_after_tax?.toLocaleString() || '-'}
                                                            </td>
                                                            <td className="py-2 px-2 text-right text-terminal-cyan font-bold">{r.eps_diluted?.toFixed(2) || '-'}</td>
                                                            <td className="py-2 px-2 text-center">
                                                                <span className={`px-1.5 py-0.5 rounded text-[9px] ${r.audited ? 'bg-terminal-green/20 text-terminal-green' : 'bg-terminal-yellow/20 text-terminal-yellow'}`}>
                                                                    {r.audited ? 'YES' : 'NO'}
                                                                </span>
                                                            </td>
                                                            <td className="py-2 px-2 text-terminal-dim text-[10px]">{r.broadcast_date?.split(' ')[0] || '-'}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>

                                {/* UPCOMING BOARD MEETINGS */}
                                <div className="col-span-12 lg:col-span-4">
                                    <div className="bg-terminal-black border border-terminal-gray p-4 rounded mb-4">
                                        <h3 className="text-sm font-bold text-terminal-yellow mb-3">UPCOMING BOARD MEETINGS</h3>
                                        {nseEarnings.upcoming_board_meetings?.length > 0 ? (
                                            <div className="space-y-2">
                                                {nseEarnings.upcoming_board_meetings.map((m, i) => (
                                                    <div key={i} className="p-2 bg-terminal-gray/10 rounded border border-terminal-gray/30">
                                                        <div className="flex justify-between items-center">
                                                            <span className="text-terminal-cyan font-bold text-xs">{m.date}</span>
                                                            {m.is_earnings && (
                                                                <span className="px-1.5 py-0.5 bg-terminal-yellow/20 text-terminal-yellow rounded text-[9px]">EARNINGS</span>
                                                            )}
                                                        </div>
                                                        <div className="text-[10px] text-terminal-dim mt-1 line-clamp-2">{m.purpose}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="text-terminal-dim text-xs italic">No upcoming board meetings</div>
                                        )}
                                    </div>

                                    {/* DIVIDENDS */}
                                    <div className="bg-terminal-black border border-terminal-gray p-4 rounded">
                                        <h3 className="text-sm font-bold text-terminal-yellow mb-3">DIVIDEND HISTORY</h3>
                                        {nseEarnings.dividends?.length > 0 ? (
                                            <div className="space-y-1.5">
                                                {nseEarnings.dividends.slice(0, 5).map((d, i) => (
                                                    <div key={i} className="flex justify-between items-center text-xs font-mono py-1 border-b border-terminal-gray/20">
                                                        <span className="text-terminal-dim">{d.ex_date}</span>
                                                        <span className="text-terminal-green">{d.purpose?.replace('Dividend - ', '') || '-'}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="text-terminal-dim text-xs italic">No dividend history</div>
                                        )}
                                    </div>
                                </div>

                                {/* SHAREHOLDING PATTERN */}
                                {nseEarnings.latest_shareholding && (
                                    <div className="col-span-12 lg:col-span-6">
                                        <div className="bg-terminal-black border border-terminal-gray p-4 rounded">
                                            <h3 className="text-sm font-bold text-terminal-yellow mb-3">
                                                SHAREHOLDING PATTERN <span className="text-terminal-dim text-xs font-normal">({nseEarnings.latest_shareholding.date})</span>
                                            </h3>
                                            <div className="grid grid-cols-2 gap-2">
                                                {nseEarnings.latest_shareholding.pattern?.map((p, i) => {
                                                    const key = Object.keys(p)[0];
                                                    const value = parseFloat(p[key]);
                                                    return (
                                                        <div key={i} className="flex justify-between items-center text-xs font-mono py-1">
                                                            <span className="text-terminal-dim">{key}</span>
                                                            <div className="flex items-center gap-2">
                                                                <div className="w-24 h-2 bg-terminal-gray/30 rounded overflow-hidden">
                                                                    <div 
                                                                        className="h-full bg-terminal-cyan" 
                                                                        style={{ width: `${value}%` }}
                                                                    />
                                                                </div>
                                                                <span className="text-terminal-text w-12 text-right">{value.toFixed(1)}%</span>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* ANNOUNCEMENTS COUNT */}
                                <div className="col-span-12 lg:col-span-6">
                                    <div className="bg-terminal-black border border-terminal-gray p-4 rounded">
                                        <h3 className="text-sm font-bold text-terminal-yellow mb-3">CORPORATE SUMMARY</h3>
                                        <div className="grid grid-cols-3 gap-4">
                                            <StatCard 
                                                label="ANNOUNCEMENTS" 
                                                value={nseEarnings.announcements_count || 0}
                                            />
                                            <StatCard 
                                                label="QUARTERS" 
                                                value={nseEarnings.financial_results?.length || 0}
                                            />
                                            <StatCard 
                                                label="DIVIDENDS" 
                                                value={nseEarnings.dividends?.length || 0}
                                            />
                                        </div>
                                        {nseEarnings.financial_results?.length > 0 && (
                                            <div className="mt-3 pt-3 border-t border-terminal-gray">
                                                <div className="text-xs text-terminal-dim">Latest Quarter EPS Trend:</div>
                                                <div className="flex gap-2 mt-2">
                                                    {nseEarnings.financial_results.slice(0, 4).reverse().map((r, i) => (
                                                        <div key={i} className="flex-1 text-center">
                                                            <div className="text-[9px] text-terminal-dim">{r.period_end?.split(' ')[0]}</div>
                                                            <div className={`text-sm font-bold ${r.eps_diluted >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                                                ₹{r.eps_diluted?.toFixed(1) || '-'}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="text-center text-terminal-dim p-8">
                                {nseEarnings?.error || "Loading Earnings Data..."}
                                <div className="mt-2 text-xs">
                                    {isIndianStock ? (
                                        <>Make sure NSE API server is running: <code className="bg-terminal-black px-2 py-1 rounded">npx stock-nse-india serve --port 3001</code></>
                                    ) : (
                                        "Earnings data is only available for Indian stocks via NSE API"
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )
            }

            {
                activeTab === "analysis" && (
                    <div className="col-span-12 grid grid-cols-12 gap-4">
                        {/* FG4: Drawdown Anatomy */}
                        <div className="col-span-12 md:col-span-6">
                            <DrawdownPanel ticker={symbol} />
                        </div>

                        {/* FG6: Volatility Surface */}
                        <div className="col-span-12 md:col-span-6">
                            <VolSurfacePanel ticker={symbol} />
                        </div>

                        {/* FG5: ETF Look-Through (shown for ETFs) */}
                        <div className="col-span-12">
                            <EtfLookThrough ticker={symbol} />
                        </div>
                    </div>
                )
            }
        </PageGrid >
    );
}

// Default export with Suspense wrapper for Next.js 16
export default function SecurityPage() {
    return (
        <Suspense fallback={<div className="p-4 text-terminal-dim font-mono animate-pulse">LOADING SECURITY DATA...</div>}>
            <SecurityPageContent />
        </Suspense>
    );
}
