"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runVolZscore } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', down: '#ef4444', up: '#22c55e' };

export default function ZscorePage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolZscore(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({ date, zscore: data.zscore?.[i] || 0 }));
    }, [data]);

    const currentZ = data?.current?.zscore || 0;
    const zColor = Math.abs(currentZ) > 2 ? THEME.down : Math.abs(currentZ) > 1 ? THEME.accent : THEME.up;

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>📈 Volatility Z-Score</h1>
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
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing z-scores...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-3 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Current Z-Score</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: zColor }}>{currentZ.toFixed(2)}</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Percentile</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: THEME.text }}>{((data.current?.percentile || 0) * 100).toFixed(0)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>RV (20d)</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: THEME.text }}>{((data.current?.rv_20 || 0) * 100).toFixed(1)}%</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Z-Score Time Series</div>
                            <div style={{ height: 350 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[-4, 4]} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                                        <ReferenceLine y={0} stroke={THEME.textMuted} strokeWidth={2} />
                                        <ReferenceLine y={1} stroke={THEME.textDim} strokeDasharray="3 3" label={{ value: '+1σ', fill: THEME.textDim, fontSize: 9 }} />
                                        <ReferenceLine y={-1} stroke={THEME.textDim} strokeDasharray="3 3" label={{ value: '-1σ', fill: THEME.textDim, fontSize: 9 }} />
                                        <ReferenceLine y={2} stroke={THEME.accent} strokeDasharray="3 3" label={{ value: '+2σ', fill: THEME.accent, fontSize: 9 }} />
                                        <ReferenceLine y={-2} stroke={THEME.accent} strokeDasharray="3 3" label={{ value: '-2σ', fill: THEME.accent, fontSize: 9 }} />
                                        <ReferenceLine y={3} stroke={THEME.down} strokeDasharray="3 3" label={{ value: '+3σ', fill: THEME.down, fontSize: 9 }} />
                                        <Line type="monotone" dataKey="zscore" stroke={zColor} strokeWidth={1.5} dot={false} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Interpretation</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Z = 0: Volatility at historical median</div>
                                <div>• |Z| &gt; 1: Unusual (outside ~68% of observations)</div>
                                <div>• |Z| &gt; 2: Rare (outside ~95% of observations)</div>
                                <div>• |Z| &gt; 3: Extreme event (crisis territory)</div>
                                <div>• Uses robust MAD scaling for resistance to outliers</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
