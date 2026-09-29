"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', up: '#22c55e', down: '#ef4444' };

const DEFAULT_TICKERS = ['SPY', 'QQQ', 'IWM', 'DIA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA'];

async function runCrowding(tickers, factorSetId, windowYears) {
    const res = await fetch(`http://127.0.0.1:8000/api/labs/factors/crowding`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers, factor_set_id: factorSetId, window_years: windowYears })
    });
    if (!res.ok) throw new Error('Failed to compute crowding');
    return res.json();
}

export default function CrowdingPage() {
    const [tickers, setTickers] = useState(DEFAULT_TICKERS.join(', '));
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { 
            const tickerList = tickers.split(',').map(t => t.trim()).filter(Boolean);
            setData(await runCrowding(tickerList, 'ff5', windowYears)); 
        }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [tickers, windowYears]);

    const chartData = data?.level?.byFactor?.map(f => ({ factor: f.factor, crowding: (f.crowding || 0) * 100 })) || [];

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>👥 Factor Crowding Risk</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <input 
                    value={tickers} 
                    onChange={(e) => setTickers(e.target.value)} 
                    className="flex-1 px-3 py-1 text-sm font-mono border focus:outline-none" 
                    style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}
                    placeholder="Comma-separated tickers..."
                />
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={1}>1 Year</option><option value={2}>2 Years</option><option value={3}>3 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'COMPUTING...' : 'ANALYZE CROWDING'}
                </button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Enter tickers to analyze factor crowding across the universe</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing cross-sectional crowding metrics...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-3 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Overall Crowding</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: (data.level?.overall || 0) > 0.5 ? THEME.down : THEME.up }}>
                                    {((data.level?.overall || 0) * 100).toFixed(0)}%
                                </div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Effective Bets</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: THEME.accent }}>{(data.effectiveBets || 0).toFixed(1)}</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Tickers Analyzed</div>
                                <div className="text-3xl font-mono font-bold" style={{ color: THEME.text }}>{data.meta?.tickersAnalyzed || 0}</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Crowding By Factor</div>
                            <div style={{ height: 250 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="factor" tick={{ fontSize: 10, fill: THEME.textDim }} />
                                        <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={v => `${v.toFixed(0)}%`} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={v => `${v?.toFixed(1)}%`} />
                                        <Bar dataKey="crowding" fill={THEME.accent} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Interpretation</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Crowding = std dev of factor betas across tickers</div>
                                <div>• Low crowding = tickers have similar exposures (risk!)</div>
                                <div>• Effective bets = 1/HHI of crowding distribution</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
