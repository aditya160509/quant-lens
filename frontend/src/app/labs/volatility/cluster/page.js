"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runVolCluster } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { ComposedChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';

const THEME = {
    bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24',
    text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', down: '#ef4444', up: '#22c55e',
};

function StatBox({ label, value, trend }) {
    return (
        <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
            <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>{label}</div>
            <div className="text-xl font-mono font-bold" style={{ color: trend === 'down' ? THEME.down : trend === 'up' ? THEME.up : THEME.text }}>{value}</div>
        </div>
    );
}

export default function ClusterPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolCluster(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({ date, rv: (data.rv_20?.[i] || 0) * 100, threshold: (data.threshold || 0) * 100 }));
    }, [data]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>⬢ Cluster Detector</h1>
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
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Detecting clusters...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-4 gap-4">
                            <StatBox label="Clusters Found" value={data.stats?.count || 0} />
                            <StatBox label="Avg Duration" value={`${(data.stats?.avg_duration || 0).toFixed(0)}d`} />
                            <StatBox label="Max Duration" value={`${data.stats?.max_duration || 0}d`} />
                            <StatBox label="Current Status" value={data.stats?.current_in_cluster ? 'IN CLUSTER' : 'NORMAL'} trend={data.stats?.current_in_cluster ? 'down' : 'up'} />
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Realized Volatility with Cluster Threshold</div>
                            <div style={{ height: 350 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <ComposedChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={(v) => `${v.toFixed(2)}%`} />
                                        <ReferenceLine y={(data.threshold || 0) * 100} stroke={THEME.down} strokeDasharray="5 5" label={{ value: 'Threshold', fill: THEME.down, fontSize: 10 }} />
                                        <Area type="monotone" dataKey="rv" fill="rgba(251, 191, 36, 0.2)" stroke={THEME.accent} strokeWidth={1.5} />
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {data.clusters?.length > 0 && (
                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Detected Clusters</div>
                                <div className="space-y-2">
                                    {data.clusters.slice(0, 10).map((c, i) => (
                                        <div key={i} className="flex items-center gap-4 text-xs font-mono p-2 rounded" style={{ background: THEME.bg }}>
                                            <span style={{ color: THEME.text }}>{c.start} → {c.end}</span>
                                            <span style={{ color: THEME.accent }}>{c.duration}d</span>
                                            {c.ongoing && <span className="px-2 py-0.5 rounded text-[10px]" style={{ background: 'rgba(239, 68, 68, 0.2)', color: THEME.down }}>ONGOING</span>}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Threshold = Median(RV20) + 2 × MAD × 1.4826</div>
                                <div>• Cluster = 3+ consecutive days above threshold</div>
                                <div>• MAD = Median Absolute Deviation (robust to outliers)</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
