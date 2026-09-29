"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runFactorContribution } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart, Line, ReferenceLine } from 'recharts';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', up: '#22c55e', down: '#ef4444' };
const FACTOR_COLORS = { 'Mkt-RF': '#3b82f6', 'SMB': '#06b6d4', 'HML': '#8b5cf6', 'RMW': '#ec4899', 'CMA': '#fbbf24', 'Mom': '#22c55e' };

export default function ContributionPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(3);
    const [factorSetId, setFactorSetId] = useState('ff5');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runFactorContribution(ticker, factorSetId, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, factorSetId, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.contributions) return [];
        const factors = Object.keys(data.contributions);
        if (!factors.length) return [];
        const dates = data.contributions[factors[0]]?.map(d => d.t) || [];
        return dates.map((t, i) => {
            const row = { date: t };
            factors.forEach(f => { row[f] = (data.contributions[f]?.[i]?.v || 0) * 100; });
            row.actual = (data.actual?.[i]?.v || 0) * 100;
            row.residual = (data.residual?.[i]?.v || 0) * 100;
            return row;
        });
    }, [data]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🎯 Factor Contribution to Returns</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}><TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search..." /></div>
                <div className="px-3 py-1 border text-sm font-mono font-bold" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>{getSymbolInfo(ticker)?.base || ticker}</div>
                <select value={factorSetId} onChange={(e) => setFactorSetId(e.target.value)} className="px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value="ff3">Fama-French 3</option><option value="ff5">Fama-French 5</option><option value="ff5_mom">FF5 + Momentum</option>
                </select>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={2}>2 Years</option><option value={3}>3 Years</option><option value={5}>5 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'COMPUTING...' : 'APPLY'}
                </button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker to decompose returns by factor</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing contribution decomposition...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-3 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Residual Dominance</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: (data.stats?.residualDominance || 0) > 0.5 ? THEME.down : THEME.up }}>
                                    {((data.stats?.residualDominance || 0) * 100).toFixed(0)}%
                                </div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Mean Explained</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.text }}>{((data.stats?.meanExplained || 0) * 100).toFixed(3)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Mean Residual</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.textMuted }}>{((data.stats?.meanResidual || 0) * 100).toFixed(3)}%</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Factor Contributions (Stacked Daily %)</div>
                            <div style={{ height: 400 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <ComposedChart data={chartData.slice(-120)}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fontSize: 9, fill: THEME.textDim }} tickFormatter={v => v?.slice(5)} />
                                        <YAxis tick={{ fontSize: 9, fill: THEME.textDim }} tickFormatter={v => `${v.toFixed(1)}%`} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={v => `${v?.toFixed(3)}%`} />
                                        <Legend wrapperStyle={{ fontSize: 10 }} />
                                        <ReferenceLine y={0} stroke={THEME.textDim} />
                                        {Object.keys(data.contributions || {}).map(f => (
                                            <Area key={f} type="monotone" dataKey={f} stackId="1" fill={FACTOR_COLORS[f] || THEME.text} stroke={FACTOR_COLORS[f] || THEME.text} fillOpacity={0.6} />
                                        ))}
                                        <Line type="monotone" dataKey="actual" stroke={THEME.text} strokeWidth={2} dot={false} name="Actual" />
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Interpretation</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Daily contribution = beta(t) × factor_return(t)</div>
                                <div>{"• Residual dominance > 50% = factors don't explain much"}</div>
                                <div>• White line = actual excess returns</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
