"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', up: '#22c55e', down: '#ef4444' };
const FACTOR_COLORS = { 'Mkt-RF': '#3b82f6', 'SMB': '#06b6d4', 'HML': '#8b5cf6', 'RMW': '#ec4899', 'CMA': '#fbbf24' };

async function runProjection(ticker, factorSetId, windowYears) {
    const res = await fetch(`http://127.0.0.1:8000/api/labs/factors/projection`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears })
    });
    if (!res.ok) throw new Error('Failed to compute projection');
    return res.json();
}

export default function ProjectionPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(3);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runProjection(ticker, 'ff5', windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🔮 Forward Factor Projection</h1>
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
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker to project forward factor exposures</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing beta mean-reversion projections...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Current Betas</div>
                            <div className="grid grid-cols-5 gap-4">
                                {Object.entries(data.currentBetas || {}).map(([f, v]) => (
                                    <div key={f} className="text-center">
                                        <div className="text-[10px] font-mono" style={{ color: FACTOR_COLORS[f] || THEME.textDim }}>{f}</div>
                                        <div className="text-lg font-mono font-bold" style={{ color: v >= 0 ? THEME.up : THEME.down }}>{(v || 0).toFixed(2)}</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Projected Beta Ranges (P10 / P50 / P90)</div>
                            <table className="w-full text-sm font-mono">
                                <thead>
                                    <tr style={{ borderBottom: `1px solid ${THEME.border}` }}>
                                        <th className="text-left py-2" style={{ color: THEME.textDim }}>Horizon</th>
                                        {Object.keys(data.currentBetas || {}).slice(0, 5).map(f => (
                                            <th key={f} className="text-center py-2" style={{ color: FACTOR_COLORS[f] || THEME.textDim }}>{f}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.horizons?.map(h => (
                                        <tr key={h.days} style={{ borderBottom: `1px solid ${THEME.border}40` }}>
                                            <td className="py-3" style={{ color: THEME.accent }}>{h.days}d</td>
                                            {Object.keys(data.currentBetas || {}).slice(0, 5).map(f => (
                                                <td key={f} className="text-center py-3">
                                                    <div className="text-[10px]" style={{ color: THEME.textDim }}>{h.betas?.[f]?.p10?.toFixed(2)}</div>
                                                    <div className="text-sm font-bold" style={{ color: THEME.text }}>{h.betas?.[f]?.p50?.toFixed(2)}</div>
                                                    <div className="text-[10px]" style={{ color: THEME.textDim }}>{h.betas?.[f]?.p90?.toFixed(2)}</div>
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Beta Inertia</div>
                            <div className="flex gap-4">
                                {Object.entries(data.inertia || {}).map(([f, v]) => (
                                    <div key={f} className="flex-1 text-center p-2 rounded" style={{ background: THEME.bg }}>
                                        <div className="text-[10px] font-mono" style={{ color: FACTOR_COLORS[f] || THEME.textDim }}>{f}</div>
                                        <div className="text-lg font-mono font-bold" style={{ color: THEME.text }}>{(v || 0).toFixed(2)}</div>
                                    </div>
                                ))}
                            </div>
                            <div className="text-[10px] font-mono mt-2" style={{ color: THEME.textDim }}>Higher inertia = betas change slowly</div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Projected median = current + reversion_rate × (historical_median - current)</div>
                                <div>• Reversion rate = 1 - exp(-horizon/126)</div>
                                <div>• Uncertainty bands = σ × √(horizon/21)</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
