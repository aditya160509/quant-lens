"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', up: '#22c55e', down: '#ef4444' };
const FACTOR_COLORS = { 'Mkt-RF': '#3b82f6', 'SMB': '#06b6d4', 'HML': '#8b5cf6', 'RMW': '#ec4899', 'CMA': '#fbbf24' };

async function runVolImpact(ticker, factorSetId, windowYears) {
    const res = await fetch(`http://127.0.0.1:8000/api/labs/factors/vol_impact`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears })
    });
    if (!res.ok) throw new Error('Failed to compute vol impact');
    return res.json();
}

export default function VolImpactPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(3);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolImpact(ticker, 'ff5', windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.impacts) return [];
        return data.impacts.map(i => ({ factor: i.factor, share: (i.share || 0) * 100, impact: i.impact, beta: i.beta }));
    }, [data]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🌡️ Factor Volatility Impact Map</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}><TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search..." /></div>
                <div className="px-3 py-1 border text-sm font-mono font-bold" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>{getSymbolInfo(ticker)?.base || ticker}</div>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={2}>2 Years</option><option value={3}>3 Years</option><option value={5}>5 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'COMPUTING...' : 'APPLY'}
                </button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker to compute volatility contribution by factor</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing volatility decomposition...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Total Vol Impact</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.accent }}>{((data.totalImpact || 0) * 100).toFixed(1)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Model Used</div>
                                <div className="text-xl font-mono font-bold" style={{ color: THEME.text }}>{data.modelUsed || 'FF5'}</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Factor Contribution to Volatility</div>
                            <div style={{ height: 300 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartData} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis type="number" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={v => `${v.toFixed(0)}%`} />
                                        <YAxis type="category" dataKey="factor" tick={{ fontSize: 10, fill: THEME.textDim }} width={60} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={v => `${v?.toFixed(1)}%`} />
                                        <Bar dataKey="share">
                                            {chartData.map((entry, idx) => <Cell key={idx} fill={FACTOR_COLORS[entry.factor] || THEME.text} />)}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Impact Details</div>
                            <table className="w-full text-sm font-mono">
                                <thead><tr style={{ borderBottom: `1px solid ${THEME.border}` }}>
                                    <th className="text-left py-2" style={{ color: THEME.textDim }}>Factor</th>
                                    <th className="text-right py-2" style={{ color: THEME.textDim }}>Beta</th>
                                    <th className="text-right py-2" style={{ color: THEME.textDim }}>Factor Vol</th>
                                    <th className="text-right py-2" style={{ color: THEME.textDim }}>Share</th>
                                </tr></thead>
                                <tbody>
                                    {data.impacts?.map(i => (
                                        <tr key={i.factor} style={{ borderBottom: `1px solid ${THEME.border}40` }}>
                                            <td className="py-2" style={{ color: FACTOR_COLORS[i.factor] || THEME.text }}>{i.factor}</td>
                                            <td className="text-right py-2" style={{ color: i.beta >= 0 ? THEME.up : THEME.down }}>{(i.beta || 0).toFixed(2)}</td>
                                            <td className="text-right py-2" style={{ color: THEME.textMuted }}>{((i.factorVol || 0) * 100).toFixed(1)}%</td>
                                            <td className="text-right py-2" style={{ color: THEME.text }}>{((i.share || 0) * 100).toFixed(1)}%</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Impact = |beta| × factor_volatility (annualized)</div>
                                <div>• Share = factor_impact / total_impact</div>
                                <div>• Mkt-RF typically dominates for diversified portfolios</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
