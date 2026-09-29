"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', up: '#22c55e', down: '#ef4444' };

async function runMicrostructure(ticker, factorSetId, windowYears) {
    const res = await fetch(`http://127.0.0.1:8000/api/labs/factors/microstructure`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears })
    });
    if (!res.ok) throw new Error('Failed to compute microstructure');
    return res.json();
}

export default function MicrostructurePage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(3);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runMicrostructure(ticker, 'ff5', windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🔬 Factor Microstructure Decomposition</h1>
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
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker to analyze exposure quality metrics</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing trend/shock/mean-reversion decomposition...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-3 gap-4">
                            <div className="text-center p-6 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-2" style={{ color: THEME.textDim }}>Trend Purity</div>
                                <div className="text-4xl font-mono font-bold" style={{ color: THEME.accent }}>{((data.scores?.trendPurity || 0) * 100).toFixed(0)}%</div>
                                <div className="text-[10px] font-mono mt-2" style={{ color: THEME.textDim }}>Higher = smoother trend</div>
                            </div>
                            <div className="text-center p-6 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-2" style={{ color: THEME.textDim }}>Shock Sensitivity</div>
                                <div className="text-4xl font-mono font-bold" style={{ color: (data.scores?.shockSensitivity || 0) > 0.3 ? THEME.down : THEME.up }}>
                                    {((data.scores?.shockSensitivity || 0) * 100).toFixed(0)}%
                                </div>
                                <div className="text-[10px] font-mono mt-2" style={{ color: THEME.textDim }}>Higher = more jumps</div>
                            </div>
                            <div className="text-center p-6 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-2" style={{ color: THEME.textDim }}>Decay Half-Life</div>
                                <div className="text-4xl font-mono font-bold" style={{ color: THEME.text }}>{(data.scores?.decayHalfLifeDays || 0).toFixed(1)}d</div>
                                <div className="text-[10px] font-mono mt-2" style={{ color: THEME.textDim }}>Shock reversion speed</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Interpretation</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• <span style={{ color: THEME.accent }}>Trend Purity:</span> % of explained variance from smooth trend (higher = more predictable)</div>
                                <div>• <span style={{ color: THEME.accent }}>Shock Sensitivity:</span> Average magnitude of large jumps relative to normal moves</div>
                                <div>• <span style={{ color: THEME.accent }}>Decay Half-Life:</span> Days for shocks to revert 50% toward mean</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Trend: 20-day EMA of explained returns</div>
                                <div>• Shock: Explained returns {'>'} 2.5σ from mean</div>
                                <div>• Mean-reversion: Explained - Trend</div>
                                <div>• Data points: {data.meta?.dataPoints || 0}</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
