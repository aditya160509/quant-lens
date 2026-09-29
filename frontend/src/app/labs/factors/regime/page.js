"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', up: '#22c55e', down: '#ef4444' };
const FACTOR_COLORS = { 'Mkt-RF': '#3b82f6', 'SMB': '#06b6d4', 'HML': '#8b5cf6', 'RMW': '#ec4899', 'CMA': '#fbbf24' };

async function runRegime(ticker, factorSetId, windowYears) {
    const res = await fetch(`http://127.0.0.1:8000/api/labs/factors/regime_sensitivity`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears })
    });
    if (!res.ok) throw new Error('Failed to compute regime sensitivity');
    return res.json();
}

export default function RegimeSensitivityPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(3);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runRegime(ticker, 'ff5', windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const regimeColor = (name) => {
        if (name === 'Stress') return THEME.down;
        if (name === 'High Vol') return THEME.accent;
        if (name === 'Low Vol') return THEME.up;
        return THEME.text;
    };

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🎭 Regime-Linked Factor Sensitivity</h1>
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
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker to analyze regime-conditional factor exposures</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing regime-conditional betas...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="flex items-center gap-4">
                            <span className="text-xs font-mono uppercase" style={{ color: THEME.textDim }}>Current Regime:</span>
                            <span className="px-3 py-1 rounded text-sm font-mono font-bold" style={{ background: regimeColor(data.currentRegime), color: THEME.bg }}>
                                {data.currentRegime || 'Unknown'}
                            </span>
                            <span className="text-xs font-mono" style={{ color: THEME.textDim }}>Method: {data.regimeMethod || 'VIX-based'}</span>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {Object.entries(data.byRegime || {}).map(([regime, stats]) => (
                                <div key={regime} className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                    <div className="flex items-center justify-between mb-3">
                                        <span className="text-xs font-mono font-bold uppercase" style={{ color: regimeColor(regime) }}>{regime}</span>
                                        <span className="text-[10px] font-mono" style={{ color: THEME.textDim }}>{stats.observations} obs</span>
                                    </div>
                                    <div className="space-y-2">
                                        {Object.entries(stats.betas || {}).slice(0, 3).map(([f, v]) => (
                                            <div key={f} className="flex justify-between text-xs font-mono">
                                                <span style={{ color: FACTOR_COLORS[f] || THEME.textMuted }}>{f}</span>
                                                <span style={{ color: v >= 0 ? THEME.up : THEME.down }}>{(v || 0).toFixed(2)}</span>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="text-[10px] font-mono mt-2" style={{ color: THEME.textDim }}>Avg VIX: {(stats.avgVix || 0).toFixed(1)}</div>
                                </div>
                            ))}
                        </div>

                        {data.transitions?.length > 0 && (
                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-3" style={{ color: THEME.accent }}>Recent Transitions</div>
                                <div className="flex flex-wrap gap-2">
                                    {data.transitions.slice(-10).map((t, i) => (
                                        <div key={i} className="px-2 py-1 rounded text-[10px] font-mono" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                            <span style={{ color: THEME.textDim }}>{t.t}: </span>
                                            <span style={{ color: regimeColor(t.from) }}>{t.from}</span>
                                            <span style={{ color: THEME.textDim }}> → </span>
                                            <span style={{ color: regimeColor(t.to) }}>{t.to}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Regimes: Low Vol (VIX {'<'} 0.8×median), Normal, High Vol ({'>'} P75), Stress ({'>'} P90)</div>
                                <div>• Conditional betas = average beta during each regime</div>
                                <div>• Data points: {data.meta?.dataPoints || 0}</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
