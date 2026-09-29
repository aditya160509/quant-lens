"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280' };

async function runNetwork(factorSetId) {
    const res = await fetch(`http://127.0.0.1:8000/api/labs/factors/network?factor_set_id=${factorSetId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to compute network');
    return res.json();
}

export default function NetworkPage() {
    const [factorSetId, setFactorSetId] = useState('ff5_mom');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runNetwork(factorSetId)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [factorSetId]);

    const plotData = data?.nodes ? [{
        x: data.nodes.map((_, i) => Math.cos(2 * Math.PI * i / data.nodes.length)),
        y: data.nodes.map((_, i) => Math.sin(2 * Math.PI * i / data.nodes.length)),
        text: data.nodes.map(n => n.id),
        mode: 'markers+text',
        type: 'scatter',
        marker: { size: data.nodes.map(n => 20 + n.centrality * 30), color: THEME.accent },
        textposition: 'top center',
        textfont: { size: 12, color: THEME.text }
    }] : [];

    const plotShapes = data?.edges?.map(e => {
        const fromIdx = data.nodes.findIndex(n => n.id === e.from);
        const toIdx = data.nodes.findIndex(n => n.id === e.to);
        if (fromIdx < 0 || toIdx < 0) return null;
        const n = data.nodes.length;
        return {
            type: 'line',
            x0: Math.cos(2 * Math.PI * fromIdx / n), y0: Math.sin(2 * Math.PI * fromIdx / n),
            x1: Math.cos(2 * Math.PI * toIdx / n), y1: Math.sin(2 * Math.PI * toIdx / n),
            line: { color: THEME.border, width: Math.max(1, e.confidence * 3) }
        };
    }).filter(Boolean) || [];

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/factors" className="text-sm font-mono" style={{ color: THEME.accent }}>← FACTORS HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🕸️ Cross-Asset Factor Network</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <select value={factorSetId} onChange={(e) => setFactorSetId(e.target.value)} className="px-3 py-1 text-sm font-mono border" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value="ff3">Fama-French 3</option><option value="ff5">Fama-French 5</option><option value="ff5_mom">FF5 + Momentum</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'COMPUTING...' : 'BUILD NETWORK'}
                </button>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Click BUILD NETWORK to compute lead-lag relationships</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing factor correlations and lead-lag...</div></div>}

                {data && !loading && (
                    <div className="grid grid-cols-3 gap-4">
                        <div className="col-span-2 rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Factor Network Graph</div>
                            <div style={{ height: 400 }}>
                                <Plot
                                    data={plotData}
                                    layout={{
                                        autosize: true,
                                        margin: { l: 40, r: 40, t: 40, b: 40 },
                                        paper_bgcolor: 'transparent',
                                        plot_bgcolor: 'transparent',
                                        xaxis: { visible: false, range: [-1.5, 1.5] },
                                        yaxis: { visible: false, range: [-1.5, 1.5], scaleanchor: 'x' },
                                        shapes: plotShapes
                                    }}
                                    style={{ width: '100%', height: '100%' }}
                                    config={{ displayModeBar: false }}
                                    useResizeHandler={true}
                                />
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-3" style={{ color: THEME.accent }}>Top Edges</div>
                                <div className="space-y-2">
                                    {data.edges?.slice(0, 8).map((e, i) => (
                                        <div key={i} className="text-xs font-mono p-2 rounded" style={{ background: THEME.bg }}>
                                            <div style={{ color: THEME.text }}>{e.from} → {e.to}</div>
                                            <div className="flex justify-between mt-1" style={{ color: THEME.textDim }}>
                                                <span>Lag: {e.lagDays}d</span>
                                                <span>Conf: {(e.confidence * 100).toFixed(0)}%</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                                <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Stats</div>
                                <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                    <div>Nodes: {data.meta?.nodeCount || 0}</div>
                                    <div>Edges: {data.meta?.edgeCount || 0}</div>
                                    <div>Min Confidence: {(data.constraints?.minConfidence || 0) * 100}%</div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
