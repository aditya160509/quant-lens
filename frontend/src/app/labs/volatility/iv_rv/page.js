"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runVolIvRvSpread } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from 'recharts';

const THEME = {
    bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24',
    text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', 
    down: '#ef4444', up: '#22c55e', purple: '#8b5cf6', cyan: '#06b6d4',
};

function StatBox({ label, value, subtext, trend }) {
    return (
        <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
            <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>{label}</div>
            <div className="text-xl font-mono font-bold" style={{ color: trend === 'down' ? THEME.down : trend === 'up' ? THEME.up : THEME.text }}>{value}</div>
            {subtext && <div className="text-[9px] font-mono mt-1" style={{ color: THEME.textDim }}>{subtext}</div>}
        </div>
    );
}

export default function IvRvPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolIvRvSpread(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            iv: data.iv?.[i] != null ? data.iv[i] * 100 : null,
            rv: data.rv?.[i] != null ? data.rv[i] * 100 : null,
            spread: data.spread?.[i] != null ? data.spread[i] * 100 : null,
        }));
    }, [data]);

    const signalColor = data?.current?.signal_color === 'warning' ? THEME.accent 
        : data?.current?.signal_color === 'success' ? THEME.up : THEME.textMuted;

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>📉 IV-RV Spread</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}><TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search any ticker..." /></div>
                <div className="flex items-center gap-2 px-3 py-1 border text-sm font-mono" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}><span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span></div>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border focus:outline-none" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={1}>1 Year</option><option value={2}>2 Years</option><option value={3}>3 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>{loading ? 'COMPUTING...' : 'APPLY'}</button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY<br/><span className="text-xs">Works with US, India, Crypto, FX - Any ticker!</span></div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing IV-RV spread...</div></div>}

                {data?.unavailable && (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-center p-6 rounded-lg" style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444' }}>
                            <div className="text-lg font-mono font-bold mb-2" style={{ color: THEME.down }}>UNAVAILABLE</div>
                            <div className="text-sm font-mono" style={{ color: THEME.textMuted }}>{data.reason}</div>
                        </div>
                    </div>
                )}

                {data && !data.unavailable && !loading && (
                    <div className="space-y-6">
                        {/* Stats Row */}
                        <div className="grid grid-cols-5 gap-4">
                            <StatBox label="Implied Vol (IV)" value={data.current?.iv != null ? `${(data.current.iv * 100).toFixed(1)}%` : 'N/A'} subtext={data.iv_source || 'Unknown'} />
                            <StatBox label="Realized Vol (RV)" value={data.current?.rv != null ? `${(data.current.rv * 100).toFixed(1)}%` : 'N/A'} subtext="20-day" />
                            <StatBox label="Spread" value={data.current?.spread != null ? `${(data.current.spread * 100).toFixed(1)}%` : 'N/A'} 
                                trend={data.current?.spread > 0 ? 'down' : data.current?.spread < 0 ? 'up' : undefined} 
                                subtext={data.current?.spread_pct != null ? `${data.current.spread_pct.toFixed(0)}% of RV` : ''} />
                            <StatBox label="Z-Score" value={(data.current?.zscore || 0).toFixed(2)} trend={Math.abs(data.current?.zscore || 0) > 2 ? 'down' : undefined} />
                            <div className="flex items-center justify-center p-4 rounded-lg" style={{ background: `${signalColor}22`, border: `1px solid ${signalColor}` }}>
                                <div className="text-sm font-mono font-bold text-center" style={{ color: signalColor }}>{data.current?.signal || 'Unknown'}</div>
                            </div>
                        </div>

                        {/* Main Chart */}
                        {chartData.length > 0 && (
                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>IV vs RV Over Time</div>
                                <div style={{ height: 350 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                            <YAxis yAxisId="left" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} domain={['dataMin - 2', 'dataMax + 5']} />
                                            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => `${v.toFixed(0)}%`} domain={[-30, 30]} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={(v) => v != null ? `${v.toFixed(2)}%` : 'N/A'} />
                                            <ReferenceLine yAxisId="right" y={0} stroke={THEME.textMuted} strokeWidth={1} />
                                            <Line yAxisId="left" type="monotone" dataKey="iv" stroke={THEME.purple} strokeWidth={2} dot={false} name="IV" connectNulls />
                                            <Line yAxisId="left" type="monotone" dataKey="rv" stroke={THEME.accent} strokeWidth={2} dot={false} name="RV (20d)" />
                                            <Area yAxisId="right" type="monotone" dataKey="spread" fill={THEME.cyan} stroke={THEME.cyan} fillOpacity={0.2} name="Spread" />
                                            <Legend wrapperStyle={{ fontSize: 11 }} />
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        )}

                        {/* Point-in-time warning */}
                        {data.point_in_time && (
                            <div className="p-4 rounded-lg text-sm font-mono" style={{ background: 'rgba(251, 191, 36, 0.1)', color: THEME.accent }}>
                                ⚠️ {data.warning}
                            </div>
                        )}

                        {/* Stats Summary */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Volatility Risk Premium (VRP)</div>
                                <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                    <div>• Mean Spread: <span style={{ color: THEME.text }}>{(data.stats?.mean_spread * 100 || 0).toFixed(2)}%</span></div>
                                    <div>• 60d VRP: <span style={{ color: THEME.text }}>{(data.stats?.mean_vrp * 100 || 0).toFixed(2)}%</span></div>
                                    <div>• IV {'>'} RV: <span style={{ color: THEME.text }}>{(data.stats?.pct_iv_premium || 50).toFixed(0)}%</span> of the time</div>
                                </div>
                            </div>

                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                                <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                    <div>• IV Source: <span style={{ color: THEME.text }}>{data.iv_source || 'Beta-Adjusted VIX'}</span></div>
                                    <div>• RV: 20-day close-to-close realized volatility</div>
                                    <div>• Annualized with √252</div>
                                </div>
                                {data.iv_source?.includes('β=') && (
                                    <div className="mt-2 p-2 rounded text-[10px] font-mono" style={{ background: 'rgba(251, 191, 36, 0.1)', color: THEME.accent }}>
                                        ⚠️ IV is approximated using Beta-Adjusted VIX (IV = VIX × Beta). This is a standard professional proxy when options chain IV is unavailable.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Trading Signals */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Signal Interpretation</div>
                            <div className="grid grid-cols-3 gap-4 text-xs font-mono">
                                <div className="p-3 rounded" style={{ background: 'rgba(251, 191, 36, 0.1)', border: '1px solid rgba(251, 191, 36, 0.3)' }}>
                                    <div style={{ color: THEME.accent }}>IV Premium (Spread {'>'} 5%)</div>
                                    <div style={{ color: THEME.textDim }}>Options expensive. Consider selling volatility.</div>
                                </div>
                                <div className="p-3 rounded" style={{ background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.3)' }}>
                                    <div style={{ color: THEME.up }}>IV Discount (Spread {'<'} -3%)</div>
                                    <div style={{ color: THEME.textDim }}>Options cheap. Consider buying volatility.</div>
                                </div>
                                <div className="p-3 rounded" style={{ background: 'rgba(107, 114, 128, 0.1)', border: '1px solid rgba(107, 114, 128, 0.3)' }}>
                                    <div style={{ color: THEME.textMuted }}>Fair Value (-3% to 5%)</div>
                                    <div style={{ color: THEME.textDim }}>Options fairly priced vs historical vol.</div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
