"use client";

import React, { useState, useEffect, useMemo, useCallback, createContext, useContext } from 'react';
import {
    LineChart, Line, AreaChart, Area, BarChart, Bar, ComposedChart,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    ReferenceLine, ReferenceArea, Cell, Scatter, ScatterChart
} from 'recharts';
import { runVolatilityIntelligence } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';

// =============================================================================
// THEME CONSTANTS
// =============================================================================
const THEME = {
    bg: '#0a0e17',
    card: '#1a1f2e',
    border: '#374151',
    accent: '#fbbf24',
    up: '#22c55e',
    down: '#ef4444',
    text: '#e5e7eb',
    textMuted: '#9ca3af',
    textDim: '#6b7280',
    blue: '#3b82f6',
    cyan: '#06b6d4',
    purple: '#8b5cf6',
    pink: '#ec4899',
};

const REGIME_COLORS = {
    0: '#22c55e', // Low
    1: '#6b7280', // Normal
    2: '#fbbf24', // Elevated
    3: '#ef4444', // Crisis
};

// =============================================================================
// PINNED CURSOR CONTEXT
// =============================================================================
const CursorContext = createContext({
    pinnedDate: null,
    setPinnedDate: () => {},
    compareDate: null,
    setCompareDate: () => {},
});

function CursorProvider({ children }) {
    const [pinnedDate, setPinnedDate] = useState(null);
    const [compareDate, setCompareDate] = useState(null);
    
    return (
        <CursorContext.Provider value={{ pinnedDate, setPinnedDate, compareDate, setCompareDate }}>
            {children}
        </CursorContext.Provider>
    );
}

function useCursor() {
    return useContext(CursorContext);
}

// =============================================================================
// SHARED COMPONENTS
// =============================================================================

function Card({ title, children, status, className = '', collapsed = false, onToggle }) {
    const [isCollapsed, setIsCollapsed] = useState(collapsed);
    
    const handleToggle = () => {
        setIsCollapsed(!isCollapsed);
        onToggle?.(!isCollapsed);
    };
    
    return (
        <div 
            className={`rounded-lg border shadow-xl ${className}`}
            style={{ background: THEME.card, borderColor: THEME.border }}
        >
            <div 
                className="flex items-center justify-between px-4 py-3 border-b cursor-pointer"
                style={{ borderColor: THEME.border }}
                onClick={handleToggle}
            >
                <div className="flex items-center gap-3">
                    <span 
                        className="text-xs font-mono uppercase tracking-wider font-semibold"
                        style={{ color: THEME.accent }}
                    >
                        {title}
                    </span>
                    {status && (
                        <span 
                            className="text-[10px] font-mono px-2 py-0.5 rounded"
                            style={{ 
                                background: status === 'ok' ? 'rgba(34, 197, 94, 0.2)' : 
                                           status === 'warn' ? 'rgba(251, 191, 36, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                color: status === 'ok' ? THEME.up : status === 'warn' ? THEME.accent : THEME.down
                            }}
                        >
                            {status === 'ok' ? '● LIVE' : status === 'warn' ? '● PARTIAL' : '● UNAVAILABLE'}
                        </span>
                    )}
                </div>
                <span style={{ color: THEME.textMuted }}>
                    {isCollapsed ? '▼' : '▲'}
                </span>
            </div>
            {!isCollapsed && (
                <div className="p-4">
                    {children}
                </div>
            )}
        </div>
    );
}

function StatBox({ label, value, subtext, trend }) {
    return (
        <div className="text-center">
            <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>
                {label}
            </div>
            <div 
                className="text-xl font-mono font-bold"
                style={{ 
                    color: trend === 'up' ? THEME.up : trend === 'down' ? THEME.down : THEME.text 
                }}
            >
                {value}
            </div>
            {subtext && (
                <div className="text-[10px] font-mono mt-1" style={{ color: THEME.textDim }}>
                    {subtext}
                </div>
            )}
        </div>
    );
}

function UnavailableState({ reason }) {
    return (
        <div 
            className="flex items-center justify-center h-40 rounded"
            style={{ background: 'rgba(239, 68, 68, 0.1)', border: `1px solid ${THEME.down}` }}
        >
            <div className="text-center">
                <div className="text-sm font-mono font-bold mb-1" style={{ color: THEME.down }}>
                    UNAVAILABLE
                </div>
                <div className="text-xs font-mono" style={{ color: THEME.textMuted }}>
                    {reason}
                </div>
            </div>
        </div>
    );
}

function LoadingState() {
    return (
        <div className="flex items-center justify-center h-40">
            <div className="text-sm font-mono" style={{ color: THEME.textMuted }}>
                Loading...
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 1: REALIZED VOLATILITY SUITE
// =============================================================================

function RealizedVolSuite({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            rv20: (data.rv_20?.[i] || 0) * 100,
            rv60: (data.rv_60?.[i] || 0) * 100,
            ewma: (data.ewma?.[i] || 0) * 100,
            parkinson: (data.parkinson?.[i] || 0) * 100,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    return (
        <div>
            <div className="grid grid-cols-3 gap-4 mb-4">
                <StatBox 
                    label="RV (20d)" 
                    value={`${(data.current.rv_20 * 100).toFixed(1)}%`}
                    subtext="Close-to-Close"
                />
                <StatBox 
                    label="RV (60d)" 
                    value={`${(data.current.rv_60 * 100).toFixed(1)}%`}
                    subtext="3-Month Window"
                />
                <StatBox 
                    label="EWMA" 
                    value={`${(data.current.ewma * 100).toFixed(1)}%`}
                    subtext="λ=0.94"
                />
            </div>
            <div style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis 
                            dataKey="date" 
                            tick={{ fontSize: 10, fill: THEME.textDim }} 
                            tickFormatter={(v) => v.slice(5)}
                            interval="preserveStartEnd"
                        />
                        <YAxis 
                            tick={{ fontSize: 10, fill: THEME.textDim }}
                            tickFormatter={(v) => `${v.toFixed(0)}%`}
                            domain={['dataMin - 5', 'dataMax + 5']}
                        />
                        <Tooltip 
                            contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }}
                            labelStyle={{ color: THEME.text }}
                            formatter={(v) => `${v.toFixed(2)}%`}
                        />
                        <Line type="monotone" dataKey="rv20" stroke={THEME.accent} strokeWidth={2} dot={false} name="RV 20d" />
                        <Line type="monotone" dataKey="rv60" stroke={THEME.cyan} strokeWidth={1} dot={false} name="RV 60d" />
                        <Line type="monotone" dataKey="ewma" stroke={THEME.purple} strokeWidth={1} dot={false} name="EWMA" />
                        {data.parkinson && (
                            <Line type="monotone" dataKey="parkinson" stroke={THEME.textDim} strokeWidth={1} dot={false} name="Parkinson" />
                        )}
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
            <div className="text-[9px] font-mono mt-2" style={{ color: THEME.textDim }}>
                RV20: 20d | RV60: 60d | EWMA λ=0.94 | Annualized: √252
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 2: VOLATILITY HEATMAP
// =============================================================================

function VolatilityHeatmap({ data }) {
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    const { windows, heatmap, dates } = data;
    
    // Sample every nth date for display
    const sampleRate = Math.max(1, Math.floor(dates.length / 50));
    const sampledDates = dates.filter((_, i) => i % sampleRate === 0);
    
    const getColor = (val) => {
        const v = val * 100;
        if (v < 10) return '#1e3a5f';
        if (v < 20) return '#2563eb';
        if (v < 30) return '#06b6d4';
        if (v < 50) return '#fbbf24';
        return '#ef4444';
    };
    
    return (
        <div>
            <div className="overflow-x-auto">
                <div style={{ minWidth: 600 }}>
                    {windows.map((w, wi) => (
                        <div key={w} className="flex items-center mb-1">
                            <div 
                                className="w-12 text-[10px] font-mono text-right pr-2" 
                                style={{ color: THEME.textDim }}
                            >
                                {w}d
                            </div>
                            <div className="flex-1 flex">
                                {sampledDates.map((date, di) => {
                                    const idx = dates.indexOf(date);
                                    const val = heatmap[`rv_${w}`][idx];
                                    return (
                                        <div
                                            key={di}
                                            style={{
                                                flex: 1,
                                                height: 16,
                                                background: getColor(val),
                                                marginRight: 1,
                                            }}
                                            title={`${date}: ${(val * 100).toFixed(1)}%`}
                                        />
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
            <div className="flex justify-between mt-2 text-[9px] font-mono" style={{ color: THEME.textDim }}>
                <span>{dates[0]}</span>
                <span>{dates[dates.length - 1]}</span>
            </div>
            <div className="flex items-center gap-4 mt-2 justify-center">
                {[['<10%', '#1e3a5f'], ['10-20%', '#2563eb'], ['20-30%', '#06b6d4'], ['30-50%', '#fbbf24'], ['>50%', '#ef4444']].map(([label, color]) => (
                    <div key={label} className="flex items-center gap-1">
                        <div style={{ width: 12, height: 12, background: color, borderRadius: 2 }} />
                        <span className="text-[9px] font-mono" style={{ color: THEME.textDim }}>{label}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 3: IV-RV SPREAD
// =============================================================================

function IvRvSpread({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || data.unavailable || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            iv: data.iv?.[i] != null ? data.iv[i] * 100 : null,
            rv: data.rv?.[i] != null ? data.rv[i] * 100 : null,
            spread: data.spread?.[i] != null ? data.spread[i] * 100 : null,
            zscore: data.zscore?.[i] || 0,
            vrp: data.vrp?.[i] != null ? data.vrp[i] * 100 : null,
        }));
    }, [data]);
    
    if (!data || data.error) {
        return <UnavailableState reason={data?.error || 'No data'} />;
    }
    
    if (data.unavailable) {
        return <UnavailableState reason={data.reason} />;
    }
    
    // Point-in-time only (no historical)
    if (data.point_in_time) {
        const { current } = data;
        return (
            <div>
                <div className="rounded p-4 mb-4" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                    <div className="text-xs font-mono mb-2" style={{ color: THEME.textDim }}>
                        ⚠️ {data.warning}
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                        <StatBox 
                            label="Current IV" 
                            value={current?.iv != null ? `${(current.iv * 100).toFixed(1)}%` : 'N/A'}
                            subtext="ATM Options"
                        />
                        <StatBox 
                            label="Current RV" 
                            value={current?.rv != null ? `${(current.rv * 100).toFixed(1)}%` : 'N/A'}
                            subtext="20d Realized"
                        />
                        <StatBox 
                            label="Spread" 
                            value={current?.spread != null ? `${(current.spread * 100).toFixed(1)}%` : 'N/A'}
                            trend={current?.spread > 0 ? 'down' : current?.spread < 0 ? 'up' : undefined}
                            subtext={current?.signal || ''}
                        />
                    </div>
                </div>
            </div>
        );
    }
    
    const { current, stats, iv_source } = data;
    
    const signalColor = {
        'warning': THEME.accent,
        'success': THEME.up,
        'neutral': THEME.textMuted,
    }[current?.signal_color] || THEME.textMuted;
    
    return (
        <div>
            {/* Current Status */}
            <div className="grid grid-cols-4 gap-3 mb-4">
                <StatBox 
                    label="IV" 
                    value={current?.iv != null ? `${(current.iv * 100).toFixed(1)}%` : 'N/A'}
                    subtext={`Source: ${iv_source || 'Options'}`}
                />
                <StatBox 
                    label="RV (20d)" 
                    value={current?.rv != null ? `${(current.rv * 100).toFixed(1)}%` : 'N/A'}
                    subtext="Realized"
                />
                <StatBox 
                    label="Spread" 
                    value={current?.spread != null ? `${(current.spread * 100).toFixed(1)}%` : 'N/A'}
                    trend={current?.spread > 0 ? 'down' : current?.spread < 0 ? 'up' : undefined}
                    subtext={current?.spread_pct != null ? `${current.spread_pct.toFixed(0)}% of RV` : ''}
                />
                <div 
                    className="px-3 py-2 rounded font-mono text-xs text-center flex items-center justify-center"
                    style={{ 
                        background: `${signalColor}22`,
                        border: `1px solid ${signalColor}`,
                        color: signalColor
                    }}
                >
                    {current?.signal || 'Unknown'}
                </div>
            </div>
            
            {/* Chart: IV vs RV over time */}
            <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis 
                            dataKey="date" 
                            tick={{ fontSize: 10, fill: THEME.textDim }} 
                            tickFormatter={(v) => v.slice(5)}
                            interval="preserveStartEnd"
                        />
                        <YAxis 
                            yAxisId="left"
                            tick={{ fontSize: 10, fill: THEME.textDim }}
                            tickFormatter={(v) => `${v.toFixed(0)}%`}
                            domain={['dataMin - 2', 'dataMax + 2']}
                        />
                        <YAxis 
                            yAxisId="right"
                            orientation="right"
                            tick={{ fontSize: 10, fill: THEME.textDim }}
                            tickFormatter={(v) => `${v.toFixed(0)}%`}
                            domain={[-20, 20]}
                        />
                        <Tooltip 
                            contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }}
                            labelStyle={{ color: THEME.text }}
                            formatter={(v, name) => {
                                if (v == null) return ['N/A', name];
                                return [`${v.toFixed(2)}%`, name];
                            }}
                        />
                        <ReferenceLine yAxisId="right" y={0} stroke={THEME.textMuted} strokeWidth={1} />
                        <Line 
                            yAxisId="left" 
                            type="monotone" 
                            dataKey="iv" 
                            stroke={THEME.purple} 
                            strokeWidth={2} 
                            dot={false} 
                            name="IV" 
                            connectNulls
                        />
                        <Line 
                            yAxisId="left" 
                            type="monotone" 
                            dataKey="rv" 
                            stroke={THEME.accent} 
                            strokeWidth={2} 
                            dot={false} 
                            name="RV (20d)" 
                        />
                        <Area 
                            yAxisId="right" 
                            type="monotone" 
                            dataKey="spread" 
                            fill={THEME.cyan} 
                            stroke={THEME.cyan} 
                            fillOpacity={0.2}
                            name="Spread" 
                        />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
            
            {/* Stats Summary */}
            <div className="flex items-center justify-between mt-3 pt-2 border-t" style={{ borderColor: THEME.border }}>
                <div className="text-[9px] font-mono" style={{ color: THEME.textDim }}>
                    Mean Spread: {(stats?.mean_spread * 100 || 0).toFixed(2)}% | 
                    VRP: {(stats?.mean_vrp * 100 || 0).toFixed(2)}% | 
                    IV {'>'} RV: {(stats?.pct_iv_premium || 50).toFixed(0)}% of time
                </div>
                <div className="text-[9px] font-mono" style={{ color: THEME.textDim }}>
                    Z-Score: {(current?.zscore || 0).toFixed(2)}
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 4: CLUSTER DETECTOR
// =============================================================================

function ClusterDetector({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            rv: (data.rv_20?.[i] || 0) * 100,
            threshold: (data.threshold || 0) * 100,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    return (
        <div>
            <div className="grid grid-cols-4 gap-4 mb-4">
                <StatBox label="Clusters" value={data.stats.count} />
                <StatBox label="Avg Duration" value={`${data.stats.avg_duration.toFixed(0)}d`} />
                <StatBox label="Max Duration" value={`${data.stats.max_duration}d`} />
                <StatBox 
                    label="Status" 
                    value={data.stats.current_in_cluster ? 'IN CLUSTER' : 'NORMAL'}
                    trend={data.stats.current_in_cluster ? 'down' : 'up'}
                />
            </div>
            <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <ReferenceLine y={data.threshold * 100} stroke={THEME.down} strokeDasharray="5 5" />
                        <Area type="monotone" dataKey="rv" fill="rgba(251, 191, 36, 0.2)" stroke={THEME.accent} />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 5: Z-SCORE
// =============================================================================

function ZScorePanel({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            zscore: data.zscore?.[i] || 0,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    const currentZ = data.current?.zscore || 0;
    const zColor = Math.abs(currentZ) > 2 ? THEME.down : Math.abs(currentZ) > 1 ? THEME.accent : THEME.up;
    
    return (
        <div>
            <div className="flex items-center justify-between mb-4">
                <StatBox 
                    label="Current Z-Score" 
                    value={currentZ.toFixed(2)}
                    trend={currentZ > 2 ? 'down' : currentZ < -1 ? 'up' : undefined}
                />
                <StatBox 
                    label="Percentile" 
                    value={`${(data.current.percentile * 100).toFixed(0)}%`}
                />
            </div>
            <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[-4, 4]} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <ReferenceLine y={0} stroke={THEME.textMuted} strokeWidth={2} />
                        <ReferenceLine y={1} stroke={THEME.textDim} strokeDasharray="3 3" />
                        <ReferenceLine y={-1} stroke={THEME.textDim} strokeDasharray="3 3" />
                        <ReferenceLine y={2} stroke={THEME.accent} strokeDasharray="3 3" />
                        <ReferenceLine y={-2} stroke={THEME.accent} strokeDasharray="3 3" />
                        <ReferenceLine y={3} stroke={THEME.down} strokeDasharray="3 3" />
                        <Line type="monotone" dataKey="zscore" stroke={zColor} strokeWidth={1.5} dot={false} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 6: REGIME CLASSIFIER
// =============================================================================

function RegimeClassifier({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            regime: data.regime?.[i] || 0,
            low: (data.probabilities?.low?.[i] || 0) * 100,
            normal: (data.probabilities?.normal?.[i] || 0) * 100,
            elevated: (data.probabilities?.elevated?.[i] || 0) * 100,
            crisis: (data.probabilities?.crisis?.[i] || 0) * 100,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    return (
        <div>
            <div className="flex items-center justify-between mb-4">
                <div 
                    className="px-4 py-2 rounded font-mono font-bold"
                    style={{ 
                        background: `${REGIME_COLORS[data.current.regime]}22`,
                        color: REGIME_COLORS[data.current.regime],
                        border: `1px solid ${REGIME_COLORS[data.current.regime]}`
                    }}
                >
                    {data.current.regime_label.toUpperCase()}
                </div>
                <StatBox label="Confidence" value={`${(data.current.confidence * 100).toFixed(0)}%`} />
            </div>
            <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <Area type="monotone" dataKey="crisis" stackId="1" stroke={REGIME_COLORS[3]} fill={REGIME_COLORS[3]} fillOpacity={0.6} />
                        <Area type="monotone" dataKey="elevated" stackId="1" stroke={REGIME_COLORS[2]} fill={REGIME_COLORS[2]} fillOpacity={0.6} />
                        <Area type="monotone" dataKey="normal" stackId="1" stroke={REGIME_COLORS[1]} fill={REGIME_COLORS[1]} fillOpacity={0.6} />
                        <Area type="monotone" dataKey="low" stackId="1" stroke={REGIME_COLORS[0]} fill={REGIME_COLORS[0]} fillOpacity={0.6} />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 7: MACRO-LINKED MODEL
// =============================================================================

function MacroLinkedModel({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || data.unavailable || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            observed: (data.observed?.[i] || 0) * 100,
            predicted: (data.predicted?.[i] || 0) * 100,
            residual: (data.residuals?.[i] || 0) * 100,
        }));
    }, [data]);
    
    if (!data || data.error || data.unavailable) {
        return <UnavailableState reason={data?.reason || data?.error || 'No data'} />;
    }
    
    return (
        <div>
            <div className="grid grid-cols-2 gap-4 mb-4">
                <StatBox label="R²" value={`${(data.r_squared * 100).toFixed(1)}%`} />
                <StatBox label="RMSE" value={`${(data.rmse * 100).toFixed(2)}%`} />
            </div>
            <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <Line type="monotone" dataKey="observed" stroke={THEME.accent} strokeWidth={1.5} dot={false} name="Observed" />
                        <Line type="monotone" dataKey="predicted" stroke={THEME.cyan} strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="Predicted" />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
            <div className="mt-3 text-[10px] font-mono" style={{ color: THEME.textDim }}>
                Drivers: {Object.entries(data.coefficients).map(([k, v]) => `${k}: ${v.toFixed(3)}`).join(' | ')}
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 8: FORECAST CONE
// =============================================================================

function ForecastCone({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.forecast_dates) return [];
        return data.forecast_dates.map((date, i) => ({
            date,
            q10: (data.bands?.q_10?.[i] || 0) * 100,
            q25: (data.bands?.q_25?.[i] || 0) * 100,
            q50: (data.bands?.q_50?.[i] || 0) * 100,
            q75: (data.bands?.q_75?.[i] || 0) * 100,
            q90: (data.bands?.q_90?.[i] || 0) * 100,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    return (
        <div>
            <StatBox 
                label="Current Vol" 
                value={`${(data.current_vol * 100).toFixed(1)}%`}
                subtext={`${data.horizon_days}d horizon`}
            />
            <div style={{ height: 200 }} className="mt-4">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <Area type="monotone" dataKey="q90" stroke="transparent" fill={THEME.accent} fillOpacity={0.1} />
                        <Area type="monotone" dataKey="q75" stroke="transparent" fill={THEME.accent} fillOpacity={0.2} />
                        <Area type="monotone" dataKey="q25" stroke="transparent" fill={THEME.bg} />
                        <Area type="monotone" dataKey="q10" stroke="transparent" fill={THEME.bg} />
                        <Line type="monotone" dataKey="q50" stroke={THEME.text} strokeWidth={2} dot={false} name="Median" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 9: GRAVITY WELL (2D)
// =============================================================================

function GravityWell({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            gravity: data.gravity_intensity?.[i] || 0,
            trapping: (data.trapping_probability?.[i] || 0) * 100,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    return (
        <div>
            <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis yAxisId="left" tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                        <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <Area yAxisId="left" type="monotone" dataKey="gravity" fill={THEME.purple} stroke={THEME.purple} fillOpacity={0.3} name="Gravity Intensity" />
                        <Line yAxisId="right" type="monotone" dataKey="trapping" stroke={THEME.cyan} strokeWidth={1.5} dot={false} name="Trapping %" />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 10: FRACTURE MAP
// =============================================================================

function FractureMap({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            alignment: data.alignment?.[i] || 0,
            short: data.short_signal?.[i] || 0,
            mid: data.mid_signal?.[i] || 0,
            long: data.long_signal?.[i] || 0,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    return (
        <div>
            <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <ReferenceLine y={80} stroke={THEME.down} strokeDasharray="5 5" />
                        <Area type="monotone" dataKey="alignment" fill={THEME.pink} stroke={THEME.pink} fillOpacity={0.3} name="Alignment Score" />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 11: ENERGY RESERVOIR
// =============================================================================

function EnergyReservoir({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            reservoir: data.reservoir?.[i] || 0,
            fillRate: (data.fill_rate?.[i] || 0) * 100,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    const currentLevel = data.reservoir?.[data.reservoir?.length - 1] || 0;
    
    return (
        <div>
            <StatBox 
                label="Reservoir Level" 
                value={`${currentLevel.toFixed(0)}%`}
                trend={currentLevel > 70 ? 'down' : currentLevel < 30 ? 'up' : undefined}
            />
            <div style={{ height: 180 }} className="mt-4">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <ReferenceLine y={80} stroke={THEME.down} strokeDasharray="5 5" />
                        <Area type="monotone" dataKey="reservoir" fill={THEME.blue} stroke={THEME.blue} fillOpacity={0.4} name="Reservoir %" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 12: SYMMETRY BREAK
// =============================================================================

function SymmetryBreak({ data }) {
    const chartData = useMemo(() => {
        if (!data || data.error || !data.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            symmetry: data.symmetry_index?.[i] || 0,
            breakpoint: data.breakpoints?.[i] ? 1 : 0,
        }));
    }, [data]);
    
    if (!data || data.error) return <UnavailableState reason={data?.error || 'No data'} />;
    
    return (
        <div>
            <div className="flex items-center justify-between mb-4">
                <StatBox 
                    label="Current Symmetry" 
                    value={data.current.symmetry.toFixed(2)}
                    trend={data.current.symmetry > 0.1 ? 'down' : data.current.symmetry < -0.1 ? 'up' : undefined}
                />
                <div 
                    className="text-xs font-mono px-3 py-1 rounded"
                    style={{ 
                        background: THEME.card,
                        color: data.current.symmetry > 0.1 ? THEME.down : data.current.symmetry < -0.1 ? THEME.up : THEME.textMuted,
                        border: `1px solid ${THEME.border}`
                    }}
                >
                    {data.current.interpretation}
                </div>
            </div>
            <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[-1, 1]} />
                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                        <ReferenceLine y={0} stroke={THEME.textMuted} strokeWidth={2} />
                        <ReferenceLine y={0.1} stroke={THEME.down} strokeDasharray="3 3" />
                        <ReferenceLine y={-0.1} stroke={THEME.up} strokeDasharray="3 3" />
                        <Line type="monotone" dataKey="symmetry" stroke={THEME.accent} strokeWidth={1.5} dot={false} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 13: TRANSMISSION ENGINE
// =============================================================================

function TransmissionEngine({ data }) {
    if (!data || data.error || data.unavailable) {
        return <UnavailableState reason={data?.reason || data?.error || 'No data'} />;
    }
    
    const { nodes, edges } = data;
    
    // Simple node positions (fixed layout)
    const nodePositions = {
        'SPY': { x: 150, y: 100 },
        'TLT': { x: 250, y: 50 },
        'UUP': { x: 250, y: 150 },
        'LQD': { x: 50, y: 50 },
    };
    
    return (
        <div>
            <div 
                className="relative rounded"
                style={{ height: 200, background: THEME.bg, border: `1px solid ${THEME.border}` }}
            >
                <svg width="100%" height="100%" viewBox="0 0 300 200">
                    {/* Edges */}
                    {edges.map((edge, i) => {
                        const from = nodePositions[edge.source];
                        const to = nodePositions[edge.target];
                        if (!from || !to) return null;
                        
                        return (
                            <g key={i}>
                                <line
                                    x1={from.x} y1={from.y}
                                    x2={to.x} y2={to.y}
                                    stroke={THEME.accent}
                                    strokeWidth={Math.max(1, edge.confidence * 3)}
                                    markerEnd="url(#arrowhead)"
                                />
                                <text
                                    x={(from.x + to.x) / 2}
                                    y={(from.y + to.y) / 2 - 5}
                                    fill={THEME.textMuted}
                                    fontSize={9}
                                    textAnchor="middle"
                                >
                                    +{edge.lag_days}d
                                </text>
                            </g>
                        );
                    })}
                    
                    {/* Arrow marker */}
                    <defs>
                        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill={THEME.accent} />
                        </marker>
                    </defs>
                    
                    {/* Nodes */}
                    {nodes.map((node) => {
                        const pos = nodePositions[node];
                        if (!pos) return null;
                        
                        return (
                            <g key={node}>
                                <circle cx={pos.x} cy={pos.y} r={20} fill={THEME.card} stroke={THEME.border} strokeWidth={2} />
                                <text x={pos.x} y={pos.y + 4} fill={THEME.text} fontSize={10} textAnchor="middle" fontFamily="monospace">
                                    {node}
                                </text>
                            </g>
                        );
                    })}
                </svg>
            </div>
            <div className="text-[9px] font-mono mt-2 text-center" style={{ color: THEME.textDim }}>
                {data.warning}
            </div>
        </div>
    );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function VolatilityLabPro() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await runVolatilityIntelligence(ticker, windowYears);
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [ticker, windowYears]);
    
    return (
        <CursorProvider>
            <div className="flex flex-col h-full overflow-auto" style={{ background: THEME.bg }}>
                {/* Control Bar */}
                <div 
                    className="flex items-center gap-4 p-4 border-b shrink-0"
                    style={{ borderColor: THEME.border, background: THEME.card }}
                >
                    <div style={{ width: 200 }}>
                        <TradingViewSearch
                            mode="security"
                            onSelect={setTicker}
                            placeholder="Search equities..."
                        />
                    </div>
                    <div 
                        className="flex items-center gap-2 px-3 py-1 border text-sm font-mono"
                        style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}
                    >
                        <span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span>
                        <span style={{ color: THEME.textDim }} className="text-xs">
                            {getSymbolInfo(ticker)?.exchange || 'US'}
                        </span>
                    </div>
                    <select
                        value={windowYears}
                        onChange={(e) => setWindowYears(Number(e.target.value))}
                        className="px-3 py-1 text-sm font-mono border focus:outline-none"
                        style={{ 
                            borderColor: THEME.border, 
                            background: THEME.bg, 
                            color: THEME.text 
                        }}
                    >
                        <option value={1}>1 Year</option>
                        <option value={2}>2 Years</option>
                        <option value={3}>3 Years</option>
                        <option value={5}>5 Years</option>
                    </select>
                    <button
                        onClick={runAnalysis}
                        disabled={loading}
                        className="px-6 py-1 text-sm font-mono font-bold transition-colors disabled:opacity-50"
                        style={{ 
                            background: THEME.accent, 
                            color: THEME.bg 
                        }}
                    >
                        {loading ? 'ANALYZING...' : 'RUN ANALYSIS'}
                    </button>
                    
                    {data && (
                        <div className="ml-auto text-[10px] font-mono" style={{ color: THEME.textDim }}>
                            {data.data_range?.start} → {data.data_range?.end} ({data.data_range?.trading_days} days)
                        </div>
                    )}
                </div>
                
                {/* Error State */}
                {error && (
                    <div className="m-4 p-4 border rounded" style={{ borderColor: THEME.down, background: 'rgba(239, 68, 68, 0.1)' }}>
                        <div className="text-sm font-mono" style={{ color: THEME.down }}>{error}</div>
                    </div>
                )}
                
                {/* Empty State */}
                {!data && !loading && !error && (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center">
                            <div className="text-lg font-mono mb-2" style={{ color: THEME.textMuted }}>
                                VOLATILITY INTELLIGENCE SYSTEM
                            </div>
                            <div className="text-sm font-mono" style={{ color: THEME.textDim }}>
                                Select a ticker and run analysis to see 13 volatility features
                            </div>
                        </div>
                    </div>
                )}
                
                {/* Loading State */}
                {loading && (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-sm font-mono" style={{ color: THEME.accent }}>
                            Computing volatility features...
                        </div>
                    </div>
                )}
                
                {/* Feature Panels */}
                {data && !loading && (
                    <div className="flex-1 overflow-auto p-4">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            
                            {/* CORE FEATURES (Expanded by default) */}
                            <Card title="1. Realized Volatility Suite" status="ok">
                                <RealizedVolSuite data={data.rv_suite} />
                            </Card>
                            
                            <Card title="2. Volatility Heatmap" status="ok">
                                <VolatilityHeatmap data={data.heatmap} />
                            </Card>
                            
                            <Card title="4. Cluster Detector" status="ok">
                                <ClusterDetector data={data.cluster_detector} />
                            </Card>
                            
                            <Card title="5. Volatility Z-Score" status="ok">
                                <ZScorePanel data={data.zscore} />
                            </Card>
                            
                            <Card title="6. Regime Classifier" status="ok">
                                <RegimeClassifier data={data.regime} />
                            </Card>
                            
                            <Card 
                                title="7. Macro-Linked Model" 
                                status={data.macro_model?.unavailable ? 'warn' : 'ok'}
                            >
                                <MacroLinkedModel data={data.macro_model} />
                            </Card>
                            
                            <Card title="8. Forecast Cone" status="ok">
                                <ForecastCone data={data.forecast_cone} />
                            </Card>
                            
                            <Card 
                                title="3. IV-RV Spread" 
                                status={data.iv_rv_spread?.unavailable || data.iv_rv_spread?.error ? 'warn' : 'ok'}
                            >
                                <IvRvSpread data={data.iv_rv_spread} />
                            </Card>
                            
                            {/* ADVANCED FEATURES (Collapsed by default) */}
                            <Card title="9. Gravity Well" status="ok" collapsed={true}>
                                <GravityWell data={data.gravity_well} />
                            </Card>
                            
                            <Card title="10. Fracture Map" status="ok" collapsed={true}>
                                <FractureMap data={data.fracture_map} />
                            </Card>
                            
                            <Card title="11. Energy Reservoir" status="ok" collapsed={true}>
                                <EnergyReservoir data={data.energy_reservoir} />
                            </Card>
                            
                            <Card title="12. Symmetry Break" status="ok" collapsed={true}>
                                <SymmetryBreak data={data.symmetry_break} />
                            </Card>
                            
                            <Card 
                                title="13. Transmission Engine" 
                                status={data.transmission?.unavailable ? 'warn' : 'ok'}
                                collapsed={true}
                            >
                                <TransmissionEngine data={data.transmission} />
                            </Card>
                        </div>
                    </div>
                )}
            </div>
        </CursorProvider>
    );
}
