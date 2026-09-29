"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';

/**
 * E5 Pattern Scanner Page
 * Scan universe for technical patterns.
 * FIXED: Removed auto-load on mount, added universe toggle
 */
export default function ScannerPage() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [pattern, setPattern] = useState('golden_cross');
    const [limit, setLimit] = useState(20);  // Reduced default limit for faster scans
    const [universe, setUniverse] = useState('US');  // US or INDIA

    const patterns = [
        { value: 'golden_cross', label: 'Golden Cross (SMA 50/200)' },
        { value: 'death_cross', label: 'Death Cross' },
        { value: 'rsi_oversold', label: 'RSI Oversold (<30)' },
        { value: 'rsi_overbought', label: 'RSI Overbought (>70)' },
        { value: 'volume_spike', label: 'Volume Spike (>2σ)' },
        { value: 'breakout', label: 'Breakout (55-day high)' },
    ];

    const fetchScan = useCallback(async () => {
        setLoading(true);
        setError(null);
        setData(null);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/research/e/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pattern, tickers: ['ALL'], limit, universe })
            });
            if (!res.ok) throw new Error('Failed to scan');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    }, [pattern, limit, universe]);

    // NO useEffect - user must click Scan button

    return (
        <div className="h-full overflow-auto p-6 bg-terminal-black">
            <style jsx>{`
                .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; }
                .control-group { display: flex; flex-direction: column; gap: 4px; }
                .control-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-family: var(--font-mono); }
                .control-input { background: #0a0a0a; border: 1px solid #262626; padding: 8px 12px; color: #e5e5e5; font-size: 13px; border-radius: 4px; }
                .btn { background: #f7c843; color: #050505; padding: 8px 16px; font-size: 12px; font-weight: 600; border: none; border-radius: 4px; cursor: pointer; font-family: var(--font-mono); }
                .btn:disabled { opacity: 0.5; cursor: not-allowed; }
                .stats-bar { display: flex; gap: 24px; margin-bottom: 16px; padding: 12px 16px; background: #0a0a0a; border: 1px solid #262626; border-radius: 8px; }
                .stat { display: flex; flex-direction: column; gap: 2px; }
                .stat-label { font-size: 10px; color: #6b7280; text-transform: uppercase; }
                .stat-value { font-size: 16px; font-weight: 700; color: #e5e5e5; font-family: var(--font-mono); }
                .results-table { width: 100%; border-collapse: collapse; }
                .results-table th { text-align: left; padding: 12px; font-size: 10px; color: #6b7280; text-transform: uppercase; border-bottom: 1px solid #262626; font-family: var(--font-mono); }
                .results-table td { padding: 12px; font-size: 13px; color: #e5e5e5; border-bottom: 1px solid #1a1a1a; }
                .results-table tr:hover { background: #0a0a0a; }
                .ticker-link { color: #f7c843; text-decoration: none; font-weight: 600; font-family: var(--font-mono); }
                .ticker-link:hover { text-decoration: underline; }
                .universe-toggle { display: flex; gap: 0; }
                .universe-btn { padding: 8px 16px; font-size: 12px; font-weight: 600; font-family: var(--font-mono); border: 1px solid #262626; cursor: pointer; transition: all 0.2s; }
                .universe-btn:first-child { border-radius: 4px 0 0 4px; }
                .universe-btn:last-child { border-radius: 0 4px 4px 0; }
                .universe-btn.active { background: #f7c843; color: #050505; border-color: #f7c843; }
                .universe-btn:not(.active) { background: #0a0a0a; color: #6b7280; }
                .universe-btn:not(.active):hover { color: #e5e5e5; }
                .empty-state { text-align: center; padding: 48px 24px; color: #6b7280; border: 1px dashed #262626; border-radius: 8px; margin-top: 16px; }
            `}</style>

            <Link href="/labs/research" className="text-terminal-dim hover:text-terminal-yellow text-xs font-mono mb-4 inline-block">
                ← Back to Research
            </Link>

            <h1 className="text-xl font-bold text-terminal-yellow font-mono mb-2">PATTERN SCANNER</h1>
            <p className="text-terminal-dim text-sm mb-6">Scan universe for technical patterns</p>

            <div className="controls">
                {/* Universe Toggle */}
                <div className="control-group">
                    <label className="control-label">Universe</label>
                    <div className="universe-toggle">
                        <button 
                            className={`universe-btn ${universe === 'US' ? 'active' : ''}`}
                            onClick={() => setUniverse('US')}
                        >
                            🇺🇸 US
                        </button>
                        <button 
                            className={`universe-btn ${universe === 'INDIA' ? 'active' : ''}`}
                            onClick={() => setUniverse('INDIA')}
                        >
                            🇮🇳 INDIA
                        </button>
                    </div>
                </div>

                <div className="control-group">
                    <label className="control-label">Pattern</label>
                    <select value={pattern} onChange={(e) => setPattern(e.target.value)} className="control-input" style={{ minWidth: 200 }}>
                        {patterns.map(p => (
                            <option key={p.value} value={p.value}>{p.label}</option>
                        ))}
                    </select>
                </div>
                <div className="control-group">
                    <label className="control-label">Limit</label>
                    <input type="number" value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="control-input" style={{ width: 80 }} />
                </div>
                <button onClick={fetchScan} disabled={loading} className="btn" style={{ alignSelf: 'flex-end' }}>
                    {loading ? 'Scanning...' : 'Scan'}
                </button>
            </div>

            {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

            {!data && !loading && !error && (
                <div className="empty-state">
                    <p className="text-lg mb-2">Select a pattern and click <strong>Scan</strong> to find matches</p>
                    <p className="text-sm text-terminal-dim">Scanning {universe === 'US' ? 'S&P 500 + Top ETFs' : 'Nifty 50 + Top Stocks'}</p>
                </div>
            )}

            {data && (
                <>
                    <div className="stats-bar">
                        <div className="stat">
                            <span className="stat-label">Pattern</span>
                            <span className="stat-value">{data.pattern}</span>
                        </div>
                        <div className="stat">
                            <span className="stat-label">Universe</span>
                            <span className="stat-value">{universe}</span>
                        </div>
                        <div className="stat">
                            <span className="stat-label">Scanned</span>
                            <span className="stat-value">{data.stats?.scanned || 0}</span>
                        </div>
                        <div className="stat">
                            <span className="stat-label">Matched</span>
                            <span className="stat-value" style={{ color: '#10b981' }}>{data.stats?.matched || 0}</span>
                        </div>
                        <div className="stat">
                            <span className="stat-label">Runtime</span>
                            <span className="stat-value">{data.stats?.runtime_ms || 0}ms</span>
                        </div>
                    </div>

                    <table className="results-table">
                        <thead>
                            <tr>
                                <th>Ticker</th>
                                <th>Signal Date</th>
                                <th>Confidence</th>
                                <th>Metrics</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.results?.map((r, i) => (
                                <tr key={i}>
                                    <td>
                                        <Link href={`/security?ticker=${r.ticker}`} className="ticker-link">
                                            {r.ticker}
                                        </Link>
                                    </td>
                                    <td>{r.signal_date}</td>
                                    <td>{(r.confidence * 100).toFixed(0)}%</td>
                                    <td className="text-terminal-dim text-xs">
                                        {Object.entries(r.metrics || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '-'}
                                    </td>
                                </tr>
                            ))}
                            {(!data.results || data.results.length === 0) && (
                                <tr>
                                    <td colSpan={4} className="text-center text-terminal-dim">No matches found</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </>
            )}
        </div>
    );
}
