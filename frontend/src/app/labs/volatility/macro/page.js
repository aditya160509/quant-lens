"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runVolMacro } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', cyan: '#06b6d4' };

export default function MacroPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolMacro(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            observed: (data.observed?.[i] || 0) * 100,
            predicted: (data.predicted?.[i] || 0) * 100,
        }));
    }, [data]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>⚡ Macro-Linked Model</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}><TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search equities..." /></div>
                <div className="flex items-center gap-2 px-3 py-1 border text-sm font-mono" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}><span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span></div>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border focus:outline-none" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={1}>1 Year</option><option value={2}>2 Years</option><option value={3}>3 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>{loading ? 'COMPUTING...' : 'APPLY'}</button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Building model...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>R² (Explained Variance)</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: THEME.accent }}>{((data.r_squared || 0) * 100).toFixed(1)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>RMSE</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: THEME.text }}>{((data.rmse || 0) * 100).toFixed(2)}%</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Observed vs Predicted Volatility</div>
                            <div style={{ height: 350 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={(v) => `${v.toFixed(2)}%`} />
                                        <Legend wrapperStyle={{ fontSize: 11 }} />
                                        <Line type="monotone" dataKey="observed" stroke={THEME.accent} strokeWidth={1.5} dot={false} name="Observed" />
                                        <Line type="monotone" dataKey="predicted" stroke={THEME.cyan} strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="Predicted" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {data.coefficients && (
                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Model Coefficients</div>
                                <div className="grid grid-cols-2 gap-2">
                                    {Object.entries(data.coefficients).map(([k, v]) => (
                                        <div key={k} className="flex justify-between p-2 rounded text-xs font-mono" style={{ background: THEME.bg }}>
                                            <span style={{ color: THEME.textDim }}>{k}</span>
                                            <span style={{ color: v > 0 ? '#22c55e' : '#ef4444' }}>{v.toFixed(4)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Ridge regression (α=0.1) for regularized estimates</div>
                                <div>• Drivers: Lagged RV, EWMA, Vol-of-Vol, Drawdown</div>
                                <div>• All features lagged by 1 day (no look-ahead)</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
