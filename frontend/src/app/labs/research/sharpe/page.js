"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

/**
 * E6 Sharpe Radar Page
 * Rolling Sharpe ratios across multiple horizons.
 */
export default function SharpePage() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [tickersInput, setTickersInput] = useState('SPY,QQQ,IWM,DIA');
    const [horizons, setHorizons] = useState([21, 63, 126, 252]);

    const fetchSharpe = async () => {
        setLoading(true);
        setError(null);
        try {
            const tickers = tickersInput.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
            const res = await fetch('http://127.0.0.1:8000/api/research/e/sharpe_radar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tickers, horizons })
            });
            if (!res.ok) throw new Error('Failed to fetch Sharpe data');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchSharpe();
    }, []);

    const colors = ['#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899'];

    const radarData = data?.series?.map((s, i) => {
        const values = horizons.map(h => s.values?.[String(h)] || 0);
        return {
            type: 'scatterpolar',
            r: [...values, values[0]],
            theta: [...horizons.map(h => `${h}d`), `${horizons[0]}d`],
            fill: 'toself',
            name: s.ticker,
            line: { color: colors[i % colors.length] },
            fillcolor: colors[i % colors.length] + '20'
        };
    }) || [];

    return (
        <div className="h-full overflow-auto p-6 bg-terminal-black">
            <style jsx>{`
                .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; }
                .control-group { display: flex; flex-direction: column; gap: 4px; }
                .control-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-family: var(--font-mono); }
                .control-input { background: #0a0a0a; border: 1px solid #262626; padding: 8px 12px; color: #e5e5e5; font-size: 13px; border-radius: 4px; }
                .btn { background: #f7c843; color: #050505; padding: 8px 16px; font-size: 12px; font-weight: 600; border: none; border-radius: 4px; cursor: pointer; font-family: var(--font-mono); }
                .chart-container { background: #0a0a0a; border: 1px solid #262626; border-radius: 8px; padding: 16px; margin-bottom: 24px; }
                .data-table { width: 100%; border-collapse: collapse; }
                .data-table th { text-align: left; padding: 12px; font-size: 10px; color: #6b7280; text-transform: uppercase; border-bottom: 1px solid #262626; font-family: var(--font-mono); }
                .data-table td { padding: 12px; font-size: 13px; font-family: var(--font-mono); border-bottom: 1px solid #1a1a1a; }
                .positive { color: #10b981; }
                .negative { color: #ef4444; }
            `}</style>

            <Link href="/labs/research" className="text-terminal-dim hover:text-terminal-yellow text-xs font-mono mb-4 inline-block">
                ← Back to Research
            </Link>

            <h1 className="text-xl font-bold text-terminal-yellow font-mono mb-2">SHARPE RADAR</h1>
            <p className="text-terminal-dim text-sm mb-6">Rolling Sharpe ratios across multiple horizons</p>

            <div className="controls">
                <div className="control-group">
                    <label className="control-label">Tickers (comma separated)</label>
                    <input
                        type="text"
                        value={tickersInput}
                        onChange={(e) => setTickersInput(e.target.value)}
                        className="control-input"
                        style={{ minWidth: 300 }}
                        placeholder="SPY, QQQ, IWM..."
                    />
                </div>
                <button onClick={fetchSharpe} disabled={loading} className="btn" style={{ alignSelf: 'flex-end' }}>
                    {loading ? 'Loading...' : 'Calculate'}
                </button>
            </div>

            {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

            {data && (
                <>
                    {/* Radar Chart */}
                    <div className="chart-container">
                        <Plot
                            data={radarData}
                            layout={{
                                height: 450,
                                margin: { t: 40, r: 60, b: 40, l: 60 },
                                paper_bgcolor: 'transparent',
                                plot_bgcolor: 'transparent',
                                font: { color: '#6b7280', size: 11 },
                                polar: {
                                    bgcolor: 'transparent',
                                    radialaxis: {
                                        visible: true,
                                        range: [-1, 3],
                                        gridcolor: '#262626',
                                        linecolor: '#262626'
                                    },
                                    angularaxis: {
                                        gridcolor: '#262626',
                                        linecolor: '#262626'
                                    }
                                },
                                legend: {
                                    x: 1,
                                    y: 1,
                                    bgcolor: 'transparent'
                                },
                                showlegend: true
                            }}
                            config={{ displayModeBar: false }}
                            style={{ width: '100%' }}
                        />
                    </div>

                    {/* Data Table */}
                    <h3 className="text-sm font-bold text-terminal-text mb-4 font-mono">SHARPE RATIOS</h3>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Ticker</th>
                                {horizons.map(h => (
                                    <th key={h}>{h}d</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {data.series?.map((s, i) => (
                                <tr key={s.ticker}>
                                    <td className="text-terminal-yellow font-bold">{s.ticker}</td>
                                    {horizons.map(h => {
                                        const val = s.values?.[String(h)];
                                        return (
                                            <td key={h} className={val >= 0 ? 'positive' : 'negative'}>
                                                {val !== null && val !== undefined ? val.toFixed(2) : '-'}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </>
            )}
        </div>
    );
}
