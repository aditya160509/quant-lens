"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { runVolTransmission } from '@/lib/api';

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280' };

const DEFAULT_TICKERS = ['SPY', 'TLT', 'UUP', 'LQD'];

export default function TransmissionPage() {
    const [tickers, setTickers] = useState(DEFAULT_TICKERS);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolTransmission(tickers)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [tickers]);

    const nodePositions = { 'SPY': { x: 150, y: 100 }, 'TLT': { x: 250, y: 50 }, 'UUP': { x: 250, y: 150 }, 'LQD': { x: 50, y: 50 } };

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🔗 Transmission Engine</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div className="flex items-center gap-2 text-sm font-mono" style={{ color: THEME.text }}>
                    Network: {tickers.join(' → ')}
                </div>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>{loading ? 'COMPUTING...' : 'APPLY'}</button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Click APPLY to compute transmission network</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing lead-lag correlations...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-4" style={{ color: THEME.accent }}>Volatility Lead-Lag Network</div>
                            <div className="flex justify-center">
                                <svg width="300" height="200" viewBox="0 0 300 200" style={{ background: THEME.bg, borderRadius: 8 }}>
                                    <defs>
                                        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                                            <polygon points="0 0, 10 3.5, 0 7" fill={THEME.accent} />
                                        </marker>
                                    </defs>
                                    {/* Edges */}
                                    {data.edges?.map((edge, i) => {
                                        const from = nodePositions[edge.source];
                                        const to = nodePositions[edge.target];
                                        if (!from || !to) return null;
                                        return (
                                            <g key={i}>
                                                <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={THEME.accent} strokeWidth={Math.max(1, edge.confidence * 3)} markerEnd="url(#arrowhead)" />
                                                <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 5} fill={THEME.textMuted} fontSize={9} textAnchor="middle">+{edge.lag_days}d</text>
                                            </g>
                                        );
                                    })}
                                    {/* Nodes */}
                                    {data.nodes?.map((node) => {
                                        const pos = nodePositions[node];
                                        if (!pos) return null;
                                        return (
                                            <g key={node}>
                                                <circle cx={pos.x} cy={pos.y} r={20} fill={THEME.card} stroke={THEME.border} strokeWidth={2} />
                                                <text x={pos.x} y={pos.y + 4} fill={THEME.text} fontSize={10} textAnchor="middle" fontFamily="monospace">{node}</text>
                                            </g>
                                        );
                                    })}
                                </svg>
                            </div>
                            <div className="text-[9px] font-mono text-center mt-4" style={{ color: THEME.textDim }}>{data.warning}</div>
                        </div>

                        {data.edges?.length > 0 && (
                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Top Lead-Lag Relationships</div>
                                <div className="space-y-2">
                                    {data.edges.map((edge, i) => (
                                        <div key={i} className="flex items-center justify-between p-2 rounded text-xs font-mono" style={{ background: THEME.bg }}>
                                            <span style={{ color: THEME.text }}>{edge.source} → {edge.target}</span>
                                            <span style={{ color: THEME.accent }}>+{edge.lag_days}d lag, r={edge.correlation}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Cross-correlation of 20d RV across assets</div>
                                <div>• Tests lags from 1-10 days</div>
                                <div>• Only edges with &gt;50% confidence shown</div>
                                <div>• Direction = source RV tends to lead target RV</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
