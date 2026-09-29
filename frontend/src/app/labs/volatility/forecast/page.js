"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runVolForecast } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { AreaChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280' };

export default function ForecastPage() {
    const [ticker, setTicker] = useState('SPY');
    const [horizon, setHorizon] = useState(20);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolForecast(ticker, horizon)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, horizon]);

    const chartData = useMemo(() => {
        if (!data?.forecast_dates) return [];
        return data.forecast_dates.map((date, i) => ({
            date,
            q10: (data.bands?.q_10?.[i] || 0) * 100,
            q25: (data.bands?.q_25?.[i] || 0) * 100,
            q50: (data.bands?.q_50?.[i] || 0) * 100,
            q75: (data.bands?.q_75?.[i] || 0) * 100,
            q90: (data.bands?.q_90?.[i] || 0) * 100,
        }));
    }, [data]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🔮 Forecast Cone</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}><TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search equities..." /></div>
                <div className="flex items-center gap-2 px-3 py-1 border text-sm font-mono" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}><span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span></div>
                <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border focus:outline-none" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={20}>20 Days</option><option value={40}>40 Days</option><option value={60}>60 Days</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>{loading ? 'SIMULATING...' : 'APPLY'}</button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Running bootstrap simulation...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-3 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Current Vol</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.accent }}>{((data.current_vol || 0) * 100).toFixed(1)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Horizon</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.text }}>{data.horizon_days}d</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Simulations</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.text }}>{data.meta?.n_simulations || 500}</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Volatility Forecast Cone</div>
                            <div style={{ height: 350 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={(v) => `${v.toFixed(2)}%`} />
                                        <Area type="monotone" dataKey="q90" stroke="transparent" fill={THEME.accent} fillOpacity={0.1} name="90th pctl" />
                                        <Area type="monotone" dataKey="q75" stroke="transparent" fill={THEME.accent} fillOpacity={0.15} name="75th pctl" />
                                        <Area type="monotone" dataKey="q25" stroke="transparent" fill={THEME.bg} name="25th pctl" />
                                        <Area type="monotone" dataKey="q10" stroke="transparent" fill={THEME.bg} name="10th pctl" />
                                        <Line type="monotone" dataKey="q50" stroke={THEME.text} strokeWidth={2} dot={false} name="Median" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                            <div className="flex items-center gap-4 mt-4 justify-center text-[9px] font-mono" style={{ color: THEME.textDim }}>
                                <span>Outer band: 10-90th percentile</span>
                                <span>•</span>
                                <span>Inner band: 25-75th percentile</span>
                                <span>•</span>
                                <span>Line: Median</span>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Bootstrap resampling from last 60 days of returns</div>
                                <div>• 500 simulated paths per forecast</div>
                                <div>• 20-day rolling window vol computed for each path</div>
                                <div>• Percentiles at each horizon step</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
