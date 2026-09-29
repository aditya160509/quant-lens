"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runVolRvSuite } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const THEME = {
    bg: '#010409',
    card: '#0d1117',
    border: '#21262d',
    accent: '#fbbf24',
    text: '#e5e7eb',
    textMuted: '#9ca3af',
    textDim: '#6b7280',
    cyan: '#06b6d4',
    purple: '#8b5cf6',
};

function StatBox({ label, value, subtext }) {
    return (
        <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
            <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>
                {label}
            </div>
            <div className="text-xl font-mono font-bold" style={{ color: THEME.text }}>
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

export default function RvSuitePage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await runVolRvSuite(ticker, windowYears);
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            rv20: (data.rv_20?.[i] || 0) * 100,
            rv60: (data.rv_60?.[i] || 0) * 100,
            ewma: (data.ewma?.[i] || 0) * 100,
            parkinson: (data.parkinson?.[i] || 0) * 100,
        }));
    }, [data]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>
                    ← VOL HUB
                </Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>
                    📊 Realized Volatility Suite
                </h1>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
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
                </div>
                <select
                    value={windowYears}
                    onChange={(e) => setWindowYears(Number(e.target.value))}
                    className="px-3 py-1 text-sm font-mono border focus:outline-none"
                    style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}
                >
                    <option value={1}>1 Year</option>
                    <option value={2}>2 Years</option>
                    <option value={3}>3 Years</option>
                    <option value={5}>5 Years</option>
                </select>
                <button
                    onClick={handleApply}
                    disabled={loading}
                    className="px-6 py-1 text-sm font-mono font-bold transition-colors disabled:opacity-50"
                    style={{ background: THEME.accent, color: THEME.bg }}
                >
                    {loading ? 'COMPUTING...' : 'APPLY'}
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto p-4">
                {error && (
                    <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid #ef4444' }}>
                        {error}
                    </div>
                )}

                {!data && !loading && !error && (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-center font-mono" style={{ color: THEME.textDim }}>
                            Select a ticker and click APPLY to compute realized volatility
                        </div>
                    </div>
                )}

                {loading && (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-sm font-mono" style={{ color: THEME.accent }}>
                            Fetching price data and computing volatility...
                        </div>
                    </div>
                )}

                {data && !loading && (
                    <div className="space-y-6">
                        {/* Stats */}
                        <div className="grid grid-cols-3 gap-4">
                            <StatBox 
                                label="RV (20d)" 
                                value={`${((data.current?.rv_20 || 0) * 100).toFixed(1)}%`}
                                subtext="Close-to-Close"
                            />
                            <StatBox 
                                label="RV (60d)" 
                                value={`${((data.current?.rv_60 || 0) * 100).toFixed(1)}%`}
                                subtext="3-Month Window"
                            />
                            <StatBox 
                                label="EWMA" 
                                value={`${((data.current?.ewma || 0) * 100).toFixed(1)}%`}
                                subtext="λ=0.94"
                            />
                        </div>

                        {/* Chart */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.textDim }}>
                                Volatility Time Series (Annualized %)
                            </div>
                            <div style={{ height: 400 }}>
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
                                            contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, color: THEME.text }}
                                            labelStyle={{ color: THEME.text }}
                                            formatter={(v) => `${v.toFixed(2)}%`}
                                        />
                                        <Legend wrapperStyle={{ fontSize: 11 }} />
                                        <Line type="monotone" dataKey="rv20" stroke={THEME.accent} strokeWidth={2} dot={false} name="RV 20d" />
                                        <Line type="monotone" dataKey="rv60" stroke={THEME.cyan} strokeWidth={1} dot={false} name="RV 60d" />
                                        <Line type="monotone" dataKey="ewma" stroke={THEME.purple} strokeWidth={1} dot={false} name="EWMA" />
                                        {data.parkinson && (
                                            <Line type="monotone" dataKey="parkinson" stroke={THEME.textDim} strokeWidth={1} dot={false} name="Parkinson" />
                                        )}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Methodology */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>
                                Methodology
                            </div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• RV20: 20-day rolling standard deviation of log returns × √252</div>
                                <div>• RV60: 60-day window for smoothed comparison</div>
                                <div>• EWMA: Exponential weighting with λ=0.94 (RiskMetrics)</div>
                                <div>• Parkinson: Range-based estimator using High/Low (more efficient)</div>
                                <div>• Data: {data.meta?.data_points} trading days</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
