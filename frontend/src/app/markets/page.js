"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
    fetchMarketDailyMatrix,
    fetchMarketDailySectorDispersion,
    fetchGraphIndexStructure,
    fetchGraphMoveIntensity,
    fetchGraphGapFollowthrough,
    fetchMarketDailyStockMoveMap,
    fetchMarketDailySectorRelativeStrength,
    fetchMarketDailyNews,
} from '@/lib/api';
import { PlotlyChart } from '@/components/ui/plotly-chart';
import MarketsIntradayView from '@/components/MarketsIntradayView';

/**
 * Markets - Bloomberg Classic Terminal Style
 * 
 * Two Modes:
 * 1. DAILY (Post-Close Cognition Screen)
 * 2. INTRADAY (Live Session Monitor)
 */

// Bloomberg Color Palette
const BLOOMBERG = {
    bg: '#0b0f14',
    grid: '#1a1f26',
    green: '#3d7a5a',
    red: '#7a3d3d',
    gray: '#4a5568',
    amber: '#8b7355',
    text: '#a0aec0',
    textMuted: '#5a6577',
};

export default function MarketsPage() {
    // View mode: 'daily' or 'intraday'
    const [viewMode, setViewMode] = useState('daily');
    // Data states
    const [matrix, setMatrix] = useState(null);
    const [sectorDispersion, setSectorDispersion] = useState(null);
    const [indexStructure, setIndexStructure] = useState(null);
    const [moveIntensity, setMoveIntensity] = useState(null);
    const [gapFollowthrough, setGapFollowthrough] = useState(null);
    const [stockMoveMap, setStockMoveMap] = useState(null);
    const [sectorStrength, setSectorStrength] = useState(null);
    const [news, setNews] = useState(null);
    const [newsCategory, setNewsCategory] = useState("Market");

    // Loading states
    const [loading, setLoading] = useState({
        matrix: true,
        sectorDispersion: true,
        indexStructure: true,
        moveIntensity: true,
        gapFollowthrough: true,
        stockMoveMap: true,
        sectorStrength: true,
        news: true,
    });

    const [lastRefresh, setLastRefresh] = useState(null);

    // Load all data
    const loadAllData = useCallback(async () => {
        const load = async (key, fetcher, setter) => {
            setLoading(prev => ({ ...prev, [key]: true }));
            try {
                const data = await fetcher();
                setter(data);
            } catch (err) {
                console.error(`${key} error:`, err);
                setter({ error: err.message });
            } finally {
                setLoading(prev => ({ ...prev, [key]: false }));
            }
        };

        await Promise.all([
            load('matrix', fetchMarketDailyMatrix, setMatrix),
            load('sectorDispersion', fetchMarketDailySectorDispersion, setSectorDispersion),
            load('indexStructure', fetchGraphIndexStructure, setIndexStructure),
            load('moveIntensity', fetchGraphMoveIntensity, setMoveIntensity),
            load('gapFollowthrough', fetchGraphGapFollowthrough, setGapFollowthrough),
            load('stockMoveMap', () => fetchMarketDailyStockMoveMap(30), setStockMoveMap),
            load('sectorStrength', fetchMarketDailySectorRelativeStrength, setSectorStrength),
            load('news', () => fetchMarketDailyNews(newsCategory, 40), setNews),
        ]);

        setLastRefresh(new Date());
    }, [newsCategory]);

    // Load news when category changes
    const loadNews = useCallback(async (cat) => {
        setLoading(prev => ({ ...prev, news: true }));
        try {
            const data = await fetchMarketDailyNews(cat, 40);
            setNews(data);
        } catch (err) {
            console.error('News error:', err);
        } finally {
            setLoading(prev => ({ ...prev, news: false }));
        }
    }, []);

    // Load data when in daily mode
    useEffect(() => {
        if (viewMode === 'daily') {
            loadAllData();
        }
    }, [viewMode, loadAllData]);

    // Extract top 3 metrics for compact header
    const topMetrics = useMemo(() => {
        if (!matrix?.items) return [];
        const nifty = matrix.items.find(i => i.symbol === "^NSEI");
        const usdinr = matrix.items.find(i => i.symbol === "USDINR=X");
        const vix = matrix.items.find(i => i.symbol === "^VIX");
        return [nifty, usdinr, vix].filter(Boolean);
    }, [matrix]);

    // Loading only applies to daily mode now - intraday has its own loading
    const isFullyLoading = viewMode === 'daily' && Object.values(loading).every(v => v);

    if (isFullyLoading) {
        return (
            <div className="flex items-center justify-center h-full" style={{ background: BLOOMBERG.bg }}>
                <div className="font-mono text-sm animate-pulse" style={{ color: BLOOMBERG.amber }}>
                    LOADING MARKETS DAILY...
                </div>
            </div>
        );
    }

    const getColorClass = (val) => {
        if (val > 0) return "text-[#3d7a5a]";
        if (val < 0) return "text-[#7a3d3d]";
        return "text-[#5a6577]";
    };

    return (
        <div className="flex flex-col h-full overflow-hidden font-mono text-xs" style={{ background: BLOOMBERG.bg, color: BLOOMBERG.text }}>
            {/* Row 1: Header with View Mode Toggle */}
            <div className="shrink-0 px-3 py-1 flex justify-between items-center" style={{ borderBottom: `1px solid ${BLOOMBERG.grid}` }}>
                <div className="flex items-center gap-3">
                    {/* View Mode Toggle */}
                    <div className="flex">
                        <button
                            onClick={() => setViewMode('daily')}
                            className="px-2 py-0.5 text-[10px] transition-colors"
                            style={{
                                borderTop: `1px solid ${viewMode === 'daily' ? BLOOMBERG.amber : BLOOMBERG.grid}`,
                                borderBottom: `1px solid ${viewMode === 'daily' ? BLOOMBERG.amber : BLOOMBERG.grid}`,
                                borderLeft: `1px solid ${viewMode === 'daily' ? BLOOMBERG.amber : BLOOMBERG.grid}`,
                                borderRight: 'none',
                                background: viewMode === 'daily' ? BLOOMBERG.amber + '20' : 'transparent',
                                color: viewMode === 'daily' ? BLOOMBERG.amber : BLOOMBERG.textMuted,
                            }}
                        >
                            DAILY
                        </button>
                        <button
                            onClick={() => setViewMode('intraday')}
                            className="px-2 py-0.5 text-[10px] transition-colors"
                            style={{
                                border: `1px solid ${viewMode === 'intraday' ? BLOOMBERG.amber : BLOOMBERG.grid}`,
                                background: viewMode === 'intraday' ? BLOOMBERG.amber + '20' : 'transparent',
                                color: viewMode === 'intraday' ? BLOOMBERG.amber : BLOOMBERG.textMuted,
                            }}
                        >
                            INTRADAY
                        </button>
                    </div>
                    <span style={{ color: BLOOMBERG.amber }} className="font-bold text-[11px]">
                        {viewMode === 'daily' ? 'MARKETS DAILY' : 'INTRADAY MONITOR'}
                    </span>
                </div>
                {/* Refresh only for daily mode - intraday has its own controls */}
                {viewMode === 'daily' && (
                    <div className="flex items-center gap-3 text-[10px]">
                        <span style={{ color: BLOOMBERG.textMuted }}>{lastRefresh?.toLocaleTimeString() || "—"}</span>
                        <button
                            onClick={loadAllData}
                            className="px-2 py-0.5 transition-colors"
                            style={{ border: `1px solid ${BLOOMBERG.grid}`, color: BLOOMBERG.textMuted }}
                            onMouseOver={e => e.target.style.borderColor = BLOOMBERG.amber}
                            onMouseOut={e => e.target.style.borderColor = BLOOMBERG.grid}
                        >
                            REFRESH
                        </button>
                    </div>
                )}
            </div>

            {/* Conditional content based on view mode */}
            {viewMode === 'daily' ? (
                <>
                    {/* Row 2: Top metrics - Extremely compact */}
                    <div className="shrink-0 px-3 py-1 flex gap-4" style={{ borderBottom: `1px solid ${BLOOMBERG.grid}` }}>
                        {topMetrics.map((m) => (
                            <div key={m.symbol} className="flex items-center gap-2 text-[10px]">
                                <span style={{ color: BLOOMBERG.textMuted }}>{m.name}</span>
                                <span style={{ color: BLOOMBERG.text }}>{m.last?.toLocaleString()}</span>
                                <span className={getColorClass(m.dayPct)}>
                                    {m.dayPct > 0 ? "+" : ""}{m.dayPct?.toFixed(2)}%
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Main Content */}
                    <div className="flex-1 overflow-auto p-2">
                        <div className="space-y-2">
                            
                            {/* Row 3: Three Bloomberg-style graphs - Equal width */}
                            <div className="grid grid-cols-3 gap-1" style={{ height: '180px' }}>
                                {/* Graph 1: Index Structure */}
                                <div className="p-1" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}` }}>
                                    <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>INDEX STRUCTURE</div>
                                    <GraphIndexStructure data={indexStructure} loading={loading.indexStructure} />
                                </div>
                                
                                {/* Graph 2: Move Intensity */}
                                <div className="p-1" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}` }}>
                                    <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>MOVE INTENSITY</div>
                                    <GraphMoveIntensity data={moveIntensity} loading={loading.moveIntensity} />
                                </div>
                                
                                {/* Graph 3: Gap & Follow Through */}
                                <div className="p-1" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}` }}>
                                    <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>GAP & FOLLOW THROUGH</div>
                                    <GraphGapFollowthrough data={gapFollowthrough} loading={loading.gapFollowthrough} />
                                </div>
                            </div>

                            {/* Row 4: Sector Strength (8 cols) + Stock Move Map (4 cols) */}
                            <div className="grid grid-cols-12 gap-1">
                                <div className="col-span-8 p-1" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}`, height: '160px' }}>
                                    <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>SECTOR RELATIVE STRENGTH</div>
                                    <GraphSectorStrength data={sectorStrength} loading={loading.sectorStrength} />
                                </div>
                                <div className="col-span-4 p-1 overflow-hidden" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}`, height: '160px' }}>
                                    <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>STOCK MOVE MAP</div>
                                    <StockMoveMapTable data={stockMoveMap} loading={loading.stockMoveMap} />
                                </div>
                            </div>

                            {/* Row 5: Market Matrix (full width) */}
                            <div className="p-1" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}` }}>
                                <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>MARKET MATRIX</div>
                                <MarketMatrixTable data={matrix} loading={loading.matrix} />
                            </div>

                            {/* Row 6: Sector Dispersion (6 cols) + News (6 cols) */}
                            <div className="grid grid-cols-12 gap-1">
                                <div className="col-span-6 p-1" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}` }}>
                                    <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>SECTOR DISPERSION</div>
                                    <SectorDispersionPanel data={sectorDispersion} loading={loading.sectorDispersion} />
                                </div>
                                <div className="col-span-6 p-1" style={{ background: BLOOMBERG.bg, border: `1px solid ${BLOOMBERG.grid}` }}>
                                    <NewsPanel 
                                        data={news} 
                                        loading={loading.news} 
                                        category={newsCategory}
                                        onCategoryChange={(cat) => {
                                            setNewsCategory(cat);
                                            loadNews(cat);
                                        }}
                                    />
                                </div>
                            </div>

                        </div>
                    </div>
                </>
            ) : (
                /* INTRADAY VIEW - Self-contained component with search, chart engine, and indicators */
                <div className="flex-1 overflow-hidden">
                    <MarketsIntradayView />
                </div>
            )}
        </div>
    );
}

// ============================================================================
// Bloomberg Graph 1: Index Structure (Close vs VWAP vs PrevClose)
// ============================================================================

function GraphIndexStructure({ data, loading }) {
    const traces = useMemo(() => {
        if (!data?.series?.length) return [];
        
        const dates = data.series.map(s => s.t);
        const closes = data.series.map(s => s.close);
        const vwap20 = data.series.map(s => s.vwap20);
        const prevCloses = data.series.map(s => s.prevClose);
        
        // Determine line color based on last point
        const lastClose = closes[closes.length - 1];
        const lastVwap = vwap20[vwap20.length - 1];
        const closeColor = lastClose > lastVwap ? BLOOMBERG.green : BLOOMBERG.red;
        
        return [
            {
                x: dates,
                y: closes,
                type: 'scatter',
                mode: 'lines',
                name: 'Close',
                line: { color: closeColor, width: 1.5 },
                hovertemplate: '%{y:,.0f}<extra></extra>',
            },
            {
                x: dates,
                y: vwap20,
                type: 'scatter',
                mode: 'lines',
                name: 'VWAP20',
                line: { color: BLOOMBERG.gray, width: 1 },
                hovertemplate: 'VWAP: %{y:,.0f}<extra></extra>',
            },
            {
                x: dates,
                y: prevCloses,
                type: 'scatter',
                mode: 'lines',
                name: 'PrevClose',
                line: { color: BLOOMBERG.textMuted, width: 1, dash: 'dot' },
                hoverinfo: 'skip',
            },
        ];
    }, [data]);

    const layout = {
        hovermode: 'x unified',
        showlegend: false,
        margin: { l: 40, r: 5, t: 5, b: 20 },
        xaxis: { showgrid: false, tickfont: { size: 8, color: BLOOMBERG.textMuted, family: 'monospace' }, tickformat: '%b %d' },
        yaxis: { showgrid: true, gridcolor: BLOOMBERG.grid, tickfont: { size: 8, color: BLOOMBERG.textMuted, family: 'monospace' }, side: 'left' },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
    };

    if (loading) return <div className="h-full animate-pulse" style={{ background: BLOOMBERG.grid }} />;
    if (!data?.series?.length) return <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">No data</div>;

    return <div className="h-[calc(100%-14px)]"><PlotlyChart data={traces} layout={layout} /></div>;
}

// ============================================================================
// Bloomberg Graph 2: Move Intensity (Violence Bars)
// ============================================================================

function GraphMoveIntensity({ data, loading }) {
    const traces = useMemo(() => {
        if (!data?.series?.length) return [];
        
        const dates = data.series.map(s => s.t);
        const intensities = data.series.map(s => s.intensity);
        const colors = data.series.map(s => {
            if (s.color === 'green') return BLOOMBERG.green;
            if (s.color === 'red') return BLOOMBERG.red;
            return BLOOMBERG.gray;
        });
        
        return [{
            x: dates,
            y: intensities,
            type: 'bar',
            marker: { color: colors },
            hovertemplate: '%{y:.2f}%<extra></extra>',
        }];
    }, [data]);

    const layout = {
        hovermode: 'closest',
        showlegend: false,
        margin: { l: 30, r: 5, t: 5, b: 20 },
        xaxis: { showgrid: false, tickfont: { size: 8, color: BLOOMBERG.textMuted, family: 'monospace' }, tickformat: '%b %d' },
        yaxis: { showgrid: true, gridcolor: BLOOMBERG.grid, tickfont: { size: 8, color: BLOOMBERG.textMuted, family: 'monospace' }, ticksuffix: '%' },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        bargap: 0.3,
    };

    if (loading) return <div className="h-full animate-pulse" style={{ background: BLOOMBERG.grid }} />;
    if (!data?.series?.length) return <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">No data</div>;

    return <div className="h-[calc(100%-14px)]"><PlotlyChart data={traces} layout={layout} /></div>;
}

// ============================================================================
// Bloomberg Graph 3: Gap & Follow Through (Stacked Bars)
// ============================================================================

function GraphGapFollowthrough({ data, loading }) {
    const traces = useMemo(() => {
        if (!data?.series?.length) return [];
        
        const dates = data.series.map(s => s.t);
        
        return [
            {
                x: dates,
                y: data.series.map(s => s.positiveConviction),
                type: 'bar',
                name: 'Conviction+',
                marker: { color: BLOOMBERG.green },
                hovertemplate: '+Conv: %{y}<extra></extra>',
            },
            {
                x: dates,
                y: data.series.map(s => s.reversal),
                type: 'bar',
                name: 'Reversal',
                marker: { color: BLOOMBERG.amber },
                hovertemplate: 'Rev: %{y}<extra></extra>',
            },
            {
                x: dates,
                y: data.series.map(s => s.fade),
                type: 'bar',
                name: 'Fade',
                marker: { color: BLOOMBERG.gray },
                hovertemplate: 'Fade: %{y}<extra></extra>',
            },
            {
                x: dates,
                y: data.series.map(s => s.negativeConviction),
                type: 'bar',
                name: 'Conviction-',
                marker: { color: BLOOMBERG.red },
                hovertemplate: '-Conv: %{y}<extra></extra>',
            },
        ];
    }, [data]);

    const layout = {
        hovermode: 'x unified',
        showlegend: false,
        barmode: 'stack',
        margin: { l: 25, r: 5, t: 5, b: 20 },
        xaxis: { showgrid: false, tickfont: { size: 8, color: BLOOMBERG.textMuted, family: 'monospace' }, tickformat: '%b %d' },
        yaxis: { showgrid: true, gridcolor: BLOOMBERG.grid, tickfont: { size: 8, color: BLOOMBERG.textMuted, family: 'monospace' } },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        bargap: 0.3,
    };

    if (loading) return <div className="h-full animate-pulse" style={{ background: BLOOMBERG.grid }} />;
    if (!data?.series?.length) return <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">No data</div>;

    return <div className="h-[calc(100%-14px)]"><PlotlyChart data={traces} layout={layout} /></div>;
}

// ============================================================================
// Sector Relative Strength (Horizontal Bars)
// ============================================================================

function GraphSectorStrength({ data, loading }) {
    const traces = useMemo(() => {
        if (!data?.items?.length) return [];
        
        return [{
            x: data.items.map(i => i.rel),
            y: data.items.map(i => i.sector),
            type: 'bar',
            orientation: 'h',
            marker: {
                color: data.items.map(i => i.rel >= 0 ? BLOOMBERG.green : BLOOMBERG.red)
            },
            hovertemplate: '%{y}: %{x:.2f}%<extra></extra>',
        }];
    }, [data]);

    const layout = {
        hovermode: 'closest',
        showlegend: false,
        margin: { l: 55, r: 10, t: 5, b: 20 },
        xaxis: { showgrid: true, gridcolor: BLOOMBERG.grid, tickfont: { size: 8, color: BLOOMBERG.textMuted, family: 'monospace' }, ticksuffix: '%', zeroline: true, zerolinecolor: BLOOMBERG.gray },
        yaxis: { tickfont: { size: 9, color: BLOOMBERG.text, family: 'monospace' }, automargin: true },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
    };

    if (loading) return <div className="h-full animate-pulse" style={{ background: BLOOMBERG.grid }} />;
    if (!data?.items?.length) return <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">No data</div>;

    return <div className="h-[calc(100%-14px)]"><PlotlyChart data={traces} layout={layout} /></div>;
}

// ============================================================================
// Stock Move Map Table (with micro bars)
// ============================================================================

function StockMoveMapTable({ data, loading }) {
    if (loading) return <div className="h-full animate-pulse" style={{ background: BLOOMBERG.grid }} />;
    if (!data?.items?.length) return <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">No data</div>;

    return (
        <div className="overflow-auto h-[calc(100%-14px)]">
            <table className="w-full text-[9px] font-mono">
                <thead>
                    <tr style={{ color: BLOOMBERG.textMuted }}>
                        <th className="text-left py-0.5">SYM</th>
                        <th className="text-right py-0.5">%</th>
                        <th className="text-left py-0.5 pl-1 w-12"></th>
                    </tr>
                </thead>
                <tbody>
                    {data.items.slice(0, 12).map((item) => (
                        <tr key={item.symbol} style={{ borderBottom: `1px solid ${BLOOMBERG.grid}` }}>
                            <td className="py-0.5" style={{ color: BLOOMBERG.text }}>{item.symbol}</td>
                            <td className="py-0.5 text-right" style={{ color: item.dayPct >= 0 ? BLOOMBERG.green : BLOOMBERG.red }}>
                                {item.dayPct > 0 ? '+' : ''}{item.dayPct?.toFixed(1)}
                            </td>
                            <td className="py-0.5 pl-1">
                                <div className="h-1.5" style={{ background: BLOOMBERG.grid }}>
                                    <div 
                                        className="h-full"
                                        style={{ 
                                            width: `${(item.barValue || 0) * 100}%`,
                                            background: item.dayPct >= 0 ? BLOOMBERG.green : BLOOMBERG.red
                                        }}
                                    />
                                </div>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ============================================================================
// Market Matrix Table
// ============================================================================

function MarketMatrixTable({ data, loading }) {
    const [sortBy, setSortBy] = useState("dayPct");
    const [sortDir, setSortDir] = useState("desc");

    if (loading) return <div className="h-48 animate-pulse" style={{ background: BLOOMBERG.grid }} />;
    if (!data?.items?.length) return <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">Matrix unavailable</div>;

    const sortedItems = [...data.items].sort((a, b) => {
        const aVal = a[sortBy] ?? -999;
        const bVal = b[sortBy] ?? -999;
        return sortDir === "desc" ? bVal - aVal : aVal - bVal;
    });

    const handleSort = (col) => {
        if (sortBy === col) {
            setSortDir(sortDir === "desc" ? "asc" : "desc");
        } else {
            setSortBy(col);
            setSortDir("desc");
        }
    };

    return (
        <div className="overflow-auto max-h-52">
            <table className="w-full text-[9px] font-mono">
                <thead style={{ background: BLOOMBERG.bg }}>
                    <tr style={{ borderBottom: `1px solid ${BLOOMBERG.grid}` }}>
                        <th className="text-left py-1 px-1" style={{ color: BLOOMBERG.textMuted }}>Name</th>
                        <th className="text-left py-1 px-1" style={{ color: BLOOMBERG.textMuted }}>Group</th>
                        <th className="text-right py-1 px-1" style={{ color: BLOOMBERG.textMuted }}>Last</th>
                        <th className="text-right py-1 px-1 cursor-pointer" style={{ color: BLOOMBERG.textMuted }} onClick={() => handleSort("dayPct")}>
                            Day% {sortBy === "dayPct" && (sortDir === "desc" ? "↓" : "↑")}
                        </th>
                        <th className="text-right py-1 px-1 cursor-pointer" style={{ color: BLOOMBERG.textMuted }} onClick={() => handleSort("d5Pct")}>
                            5D% {sortBy === "d5Pct" && (sortDir === "desc" ? "↓" : "↑")}
                        </th>
                        <th className="text-right py-1 px-1" style={{ color: BLOOMBERG.textMuted }}>MTD%</th>
                        <th className="text-right py-1 px-1" style={{ color: BLOOMBERG.textMuted }}>Vol%</th>
                        <th className="text-right py-1 px-1" style={{ color: BLOOMBERG.textMuted }}>ATR%</th>
                    </tr>
                </thead>
                <tbody>
                    {sortedItems.map((row) => (
                        <tr key={row.symbol} style={{ borderBottom: `1px solid ${BLOOMBERG.grid}` }}>
                            <td className="py-0.5 px-1" style={{ color: BLOOMBERG.text }}>{row.name}</td>
                            <td className="py-0.5 px-1" style={{ color: BLOOMBERG.textMuted }}>{row.group}</td>
                            <td className="py-0.5 px-1 text-right" style={{ color: BLOOMBERG.text }}>{row.last?.toLocaleString()}</td>
                            <td className="py-0.5 px-1 text-right" style={{ color: row.dayPct > 0 ? BLOOMBERG.green : row.dayPct < 0 ? BLOOMBERG.red : BLOOMBERG.textMuted }}>
                                {row.dayPct != null ? (row.dayPct > 0 ? "+" : "") + row.dayPct.toFixed(2) + "%" : "—"}
                            </td>
                            <td className="py-0.5 px-1 text-right" style={{ color: row.d5Pct > 0 ? BLOOMBERG.green : row.d5Pct < 0 ? BLOOMBERG.red : BLOOMBERG.textMuted }}>
                                {row.d5Pct != null ? (row.d5Pct > 0 ? "+" : "") + row.d5Pct.toFixed(2) + "%" : "—"}
                            </td>
                            <td className="py-0.5 px-1 text-right" style={{ color: row.mtdPct > 0 ? BLOOMBERG.green : row.mtdPct < 0 ? BLOOMBERG.red : BLOOMBERG.textMuted }}>
                                {row.mtdPct != null ? (row.mtdPct > 0 ? "+" : "") + row.mtdPct.toFixed(2) + "%" : "—"}
                            </td>
                            <td className="py-0.5 px-1 text-right" style={{ color: BLOOMBERG.textMuted }}>{row.volPctile ?? "—"}</td>
                            <td className="py-0.5 px-1 text-right" style={{ color: BLOOMBERG.textMuted }}>{row.atrPct?.toFixed(2) ?? "—"}%</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ============================================================================
// Sector Dispersion Panel
// ============================================================================

function SectorDispersionPanel({ data, loading }) {
    if (loading) return <div className="h-28 animate-pulse" style={{ background: BLOOMBERG.grid }} />;
    if (!data?.items?.length) return <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">No data</div>;

    const getArrow = (dir) => dir === "up" ? "↑" : dir === "down" ? "↓" : "→";
    const getDirColor = (dir) => dir === "up" ? BLOOMBERG.green : dir === "down" ? BLOOMBERG.red : BLOOMBERG.gray;

    return (
        <div className="grid grid-cols-2 gap-1">
            {data.items.map((item) => (
                <div key={item.sector} className="flex items-center justify-between px-2 py-1 text-[9px] font-mono" style={{ background: BLOOMBERG.grid + '40' }}>
                    <div className="flex items-center gap-1">
                        <span style={{ color: getDirColor(item.direction) }}>{getArrow(item.direction)}</span>
                        <span style={{ color: BLOOMBERG.text }}>{item.sector}</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <span style={{ color: BLOOMBERG.textMuted }}>{item.dispersion?.toFixed(2)}%</span>
                        <span className="text-[8px] px-1" style={{ 
                            background: item.label === "high" ? BLOOMBERG.red + '30' : item.label === "low" ? BLOOMBERG.green + '30' : BLOOMBERG.gray + '30',
                            color: item.label === "high" ? BLOOMBERG.red : item.label === "low" ? BLOOMBERG.green : BLOOMBERG.gray 
                        }}>{item.label?.toUpperCase()}</span>
                        {item.outlier && <span className="text-[8px] px-1" style={{ background: BLOOMBERG.amber + '30', color: BLOOMBERG.amber }}>OUT</span>}
                    </div>
                </div>
            ))}
        </div>
    );
}

// ============================================================================
// News Panel
// ============================================================================

function NewsPanel({ data, loading, category, onCategoryChange }) {
    const categories = ["Market", "Stocks", "IPO", "Global"];

    return (
        <div className="h-44 flex flex-col">
            <div className="text-[9px] mb-0.5" style={{ color: BLOOMBERG.textMuted }}>NEWS</div>
            {/* Tabs */}
            <div className="flex gap-1 mb-1">
                {categories.map((cat) => (
                    <button
                        key={cat}
                        onClick={() => onCategoryChange(cat)}
                        className="px-2 py-0.5 text-[9px] font-mono transition-colors"
                        style={{
                            border: `1px solid ${category === cat ? BLOOMBERG.amber : BLOOMBERG.grid}`,
                            color: category === cat ? BLOOMBERG.amber : BLOOMBERG.textMuted,
                            background: category === cat ? BLOOMBERG.amber + '10' : 'transparent'
                        }}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* News List */}
            <div className="flex-1 overflow-auto">
                {loading ? (
                    <div className="h-full animate-pulse" style={{ background: BLOOMBERG.grid }} />
                ) : !data?.items?.length ? (
                    <div style={{ color: BLOOMBERG.textMuted }} className="text-[10px]">No news</div>
                ) : (
                    <div className="space-y-0.5">
                        {data.items.slice(0, 12).map((item, idx) => (
                            <a
                                key={idx}
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block text-[9px] font-mono py-0.5 px-1 transition-colors"
                                style={{ color: BLOOMBERG.text }}
                                onMouseOver={e => e.target.style.background = BLOOMBERG.grid + '60'}
                                onMouseOut={e => e.target.style.background = 'transparent'}
                            >
                                <span style={{ color: BLOOMBERG.textMuted }} className="mr-2">{item.timeLabel}</span>
                                {item.title}
                            </a>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
