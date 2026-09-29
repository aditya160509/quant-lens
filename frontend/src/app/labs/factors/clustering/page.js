"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', up: '#22c55e', down: '#ef4444' };
const CLUSTER_COLORS = ['#3b82f6', '#22c55e', '#fbbf24', '#ec4899', '#8b5cf6', '#06b6d4'];

const DEFAULT_TICKERS = ['SPY', 'QQQ', 'IWM', 'DIA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD'];

async function runClustering(tickers, factorSetId, k, windowYears) {
    const res = await fetch(`http://127.0.0.1:8000/api/labs/factors/clustering`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers, factor_set_id: factorSetId, k, window_years: windowYears })
    });
    if (!res.ok) throw new Error('Failed to compute clustering');
    return res.json();
}

export default function ClusteringPage() {
    const [tickers, setTickers] = useState(DEFAULT_TICKERS.join(', '));
    const [k, setK] = useState(5);
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { 
            const tickerList = tickers.split(',').map(t => t.trim()).filter(Boolean);
            setData(await runClustering(tickerList, 'ff5', k, windowYears)); 
        }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [tickers, k, windowYears]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🧬 Multi-Ticker Factor Clustering</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <input value={tickers} onChange={(e) => setTickers(e.target.value)} className="flex-1 px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }} placeholder="Comma-separated tickers..." />
                <div className="flex items-center gap-2">
                    <span className="text-xs font-mono" style={{ color: THEME.textDim }}>K:</span>
                    <select value={k} onChange={(e) => setK(Number(e.target.value))} className="px-2 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                        <option value={3}>3</option><option value={5}>5</option><option value={7}>7</option><option value={10}>10</option>
                    </select>
                </div>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={1}>1 Year</option><option value={2}>2 Years</option><option value={3}>3 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'CLUSTERING...' : 'RUN CLUSTERING'}
                </button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Enter tickers to cluster by factor exposure similarity</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing K-means clustering on factor exposures...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="flex items-center gap-4">
                            <span className="text-xs font-mono uppercase" style={{ color: THEME.textDim }}>Method: {data.method || 'K-Means'}</span>
                            <span className="text-xs font-mono uppercase" style={{ color: THEME.textDim }}>K: {data.k}</span>
                            <span className="text-xs font-mono uppercase" style={{ color: THEME.textDim }}>Tickers: {data.meta?.tickersAnalyzed || 0}</span>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                            {data.clusters?.map((c, i) => (
                                <div key={c.id} className="rounded-lg p-4" style={{ background: THEME.card, border: `2px solid ${CLUSTER_COLORS[i % CLUSTER_COLORS.length]}` }}>
                                    <div className="flex items-center gap-2 mb-3">
                                        <div className="w-3 h-3 rounded-full" style={{ background: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                                        <span className="text-sm font-mono font-bold" style={{ color: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}>Cluster {c.id + 1}</span>
                                        <span className="text-xs font-mono" style={{ color: THEME.textDim }}>({c.members?.length || 0})</span>
                                    </div>
                                    <div className="flex flex-wrap gap-2 mb-3">
                                        {c.members?.map(m => (
                                            <span key={m} className="px-2 py-0.5 rounded text-xs font-mono" style={{ background: THEME.bg, color: THEME.text }}>{m}</span>
                                        ))}
                                    </div>
                                    <div className="text-[10px] font-mono space-y-1" style={{ color: THEME.textDim }}>
                                        <div className="font-bold mb-1">Centroid:</div>
                                        {Object.entries(c.centroid || {}).slice(0, 3).map(([f, v]) => (
                                            <div key={f} className="flex justify-between">
                                                <span>{f}:</span>
                                                <span style={{ color: v >= 0 ? THEME.up : THEME.down }}>{(v || 0).toFixed(2)}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• K-means clustering on standardized factor beta vectors</div>
                                <div>• Centroid = average factor exposures for cluster</div>
                                <div>• Similar clusters = tickers with similar risk profiles</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
