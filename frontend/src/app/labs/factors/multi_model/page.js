"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { runFactorMultiModel } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const THEME = {
    bg: '#010409',
    card: '#0d1117',
    border: '#21262d',
    accent: '#fbbf24',
    text: '#e5e7eb',
    textMuted: '#9ca3af',
    textDim: '#6b7280',
    up: '#22c55e',
    down: '#ef4444',
    blue: '#3b82f6',
};

const FACTOR_SETS = [
    { id: 'capm', label: 'CAPM' },
    { id: 'ff3', label: 'Fama-French 3' },
    { id: 'ff5', label: 'Fama-French 5' },
    { id: 'carhart', label: 'Carhart 4-Factor' },
    { id: 'ff5_mom', label: 'FF5 + Momentum' },
];

export default function MultiModelPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(3);
    const [factorSetId, setFactorSetId] = useState('ff5');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await runFactorMultiModel(ticker, factorSetId, windowYears);
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [ticker, factorSetId, windowYears]);

    // Get the best model (first in sorted array) or selected model
    const bestModel = useMemo(() => {
        if (!data?.models?.length) return null;
        // Find selected model or use first (best ranked)
        return data.models.find(m => m.modelId === factorSetId) || data.models[0];
    }, [data, factorSetId]);

    const betaChartData = useMemo(() => {
        if (!bestModel?.betas) return [];
        return Object.entries(bestModel.betas).map(([factor, value]) => ({
            factor,
            beta: value,
            color: value >= 0 ? THEME.up : THEME.down
        }));
    }, [bestModel]);

    const dominantModel = data?.models?.find(m => m.modelId === data?.arbitration?.dominantModelId);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🔬 Multi-Model Factor Engine</h1>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}>
                    <TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search equities..." />
                </div>
                <div className="flex items-center gap-2 px-3 py-1 border text-sm font-mono" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span>
                </div>
                <select value={factorSetId} onChange={(e) => setFactorSetId(e.target.value)} className="px-3 py-1 text-sm font-mono border focus:outline-none" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    {FACTOR_SETS.map(fs => <option key={fs.id} value={fs.id}>{fs.label}</option>)}
                </select>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border focus:outline-none" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={1}>1 Year</option>
                    <option value={2}>2 Years</option>
                    <option value={3}>3 Years</option>
                    <option value={5}>5 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'COMPUTING...' : 'APPLY'}
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                
                {!data && !loading && !error && (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-center font-mono" style={{ color: THEME.textDim }}>
                            Select a ticker and click APPLY to run factor regression
                        </div>
                    </div>
                )}

                {loading && (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing factor regressions...</div>
                    </div>
                )}

                {data && !loading && (
                    <div className="space-y-6">
                        {/* Summary Stats */}
                        <div className="grid grid-cols-4 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>R-Squared</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.accent }}>{((bestModel?.r2 || 0) * 100).toFixed(1)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Alpha (Ann.)</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: (bestModel?.alpha || 0) >= 0 ? THEME.up : THEME.down }}>
                                    {((bestModel?.alpha || 0) * 252 * 100).toFixed(2)}%
                                </div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Market Beta</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.text }}>{(bestModel?.betas?.['Mkt-RF'] || 0).toFixed(2)}</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Observations</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.text }}>{bestModel?.nObs || 0}</div>
                            </div>
                        </div>

                        {/* Factor Betas Chart */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Factor Betas</div>
                            <div style={{ height: 300 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={betaChartData} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis type="number" tick={{ fontSize: 10, fill: THEME.textDim }} />
                                        <YAxis type="category" dataKey="factor" tick={{ fontSize: 10, fill: THEME.textDim }} width={60} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={v => v.toFixed(3)} />
                                        <Bar dataKey="beta">
                                            {betaChartData.map((entry, idx) => <Cell key={idx} fill={entry.color} />)}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Factor Table */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Regression Details</div>
                            <table className="w-full text-sm font-mono">
                                <thead>
                                    <tr style={{ borderBottom: `1px solid ${THEME.border}` }}>
                                        <th className="text-left py-2" style={{ color: THEME.textDim }}>Factor</th>
                                        <th className="text-right py-2" style={{ color: THEME.textDim }}>Beta</th>
                                        <th className="text-right py-2" style={{ color: THEME.textDim }}>T-Stat</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr style={{ borderBottom: `1px solid ${THEME.border}40` }}>
                                        <td className="py-2" style={{ color: THEME.text }}>Alpha</td>
                                        <td className="text-right py-2" style={{ color: (bestModel?.alpha || 0) >= 0 ? THEME.up : THEME.down }}>{(bestModel?.alpha || 0).toFixed(6)}</td>
                                        <td className="text-right py-2" style={{ color: THEME.textMuted }}>{(bestModel?.tStats?.alpha || 0).toFixed(2)}</td>
                                    </tr>
                                    {Object.entries(bestModel?.betas || {}).map(([factor, beta]) => (
                                        <tr key={factor} style={{ borderBottom: `1px solid ${THEME.border}40` }}>
                                            <td className="py-2" style={{ color: THEME.text }}>{factor}</td>
                                            <td className="text-right py-2" style={{ color: beta >= 0 ? THEME.up : THEME.down }}>{beta.toFixed(3)}</td>
                                            <td className="text-right py-2" style={{ color: THEME.textMuted }}>{(bestModel?.tStats?.[factor] || 0).toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {/* Methodology */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• OLS regression of excess returns on factor returns</div>
                                <div>• Factor data from Ken French library (1963-present)</div>
                                <div>• RF subtracted from asset returns for excess calculation</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
