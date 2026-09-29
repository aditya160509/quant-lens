"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { runFactorShockReplay } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend } from 'recharts';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', down: '#ef4444', up: '#22c55e' };

export default function ShockReplayPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(3);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runFactorShockReplay(ticker, 'ff5', windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const damageData = data?.shocks?.map(s => ({
        label: s.label?.slice(0, 20),
        maxDD: (s.damage?.maxDD || 0) * 100,
        troughDays: s.damage?.timeToTroughDays || 0,
        recoverDays: s.damage?.timeToRecoverDays || -1
    })) || [];

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>⚡ Factor Shock Replay Simulator</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}><TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search..." /></div>
                <div className="px-3 py-1 border text-sm font-mono font-bold" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>{getSymbolInfo(ticker)?.base || ticker}</div>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={2}>2 Years</option><option value={3}>3 Years</option><option value={5}>5 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'SIMULATING...' : 'REPLAY SHOCKS'}
                </button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker to replay historical shocks using current factor exposures</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Replaying COVID, SVB, Inflation shocks...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-4 gap-4">
                            {Object.entries(data.currentBetas || {}).slice(0, 4).map(([f, v]) => (
                                <div key={f} className="text-center p-3 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                    <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>{f} Beta</div>
                                    <div className="text-lg font-mono font-bold" style={{ color: v >= 0 ? THEME.up : THEME.down }}>{(v || 0).toFixed(2)}</div>
                                </div>
                            ))}
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Max Drawdown by Historical Shock</div>
                            <div style={{ height: 250 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={damageData} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis type="number" tick={{ fontSize: 10, fill: THEME.textDim }} domain={['dataMin', 0]} tickFormatter={v => `${v.toFixed(0)}%`} />
                                        <YAxis type="category" dataKey="label" tick={{ fontSize: 9, fill: THEME.textDim }} width={120} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={v => `${v?.toFixed(1)}%`} />
                                        <Bar dataKey="maxDD" fill={THEME.down} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Shock Details</div>
                            <table className="w-full text-sm font-mono">
                                <thead>
                                    <tr style={{ borderBottom: `1px solid ${THEME.border}` }}>
                                        <th className="text-left py-2" style={{ color: THEME.textDim }}>Shock Event</th>
                                        <th className="text-right py-2" style={{ color: THEME.textDim }}>Max DD</th>
                                        <th className="text-right py-2" style={{ color: THEME.textDim }}>Days to Trough</th>
                                        <th className="text-right py-2" style={{ color: THEME.textDim }}>Recovery Days</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.shocks?.map(s => (
                                        <tr key={s.id} style={{ borderBottom: `1px solid ${THEME.border}40` }}>
                                            <td className="py-2" style={{ color: THEME.text }}>{s.label}</td>
                                            <td className="text-right py-2" style={{ color: THEME.down }}>{((s.damage?.maxDD || 0) * 100).toFixed(1)}%</td>
                                            <td className="text-right py-2" style={{ color: THEME.textMuted }}>{s.damage?.timeToTroughDays || 0}d</td>
                                            <td className="text-right py-2" style={{ color: s.damage?.timeToRecoverDays > 0 ? THEME.up : THEME.textDim }}>
                                                {s.damage?.timeToRecoverDays > 0 ? `${s.damage.timeToRecoverDays}d` : 'N/A'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Uses current factor betas to simulate historical shock scenarios</div>
                                <div>• Predicted return = Σ(current_beta[i] × historical_factor_return[i])</div>
                                <div>• Shocks: COVID (Feb-Mar 2020), Inflation (Jan-Jun 2022), SVB (Mar 2023), Aug 2024</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
