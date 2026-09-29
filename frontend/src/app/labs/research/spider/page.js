"use client";

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

/**
 * E10 Spider Chart Page
 * Cross-asset correlation spider chart.
 * FIXED: No auto-load - user must click Calculate
 */
export default function SpiderPage() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [ref, setRef] = useState('SPY');
    const [tickersInput, setTickersInput] = useState('QQQ,IWM,GLD,TLT,BTC-USD');
    const [window, setWindow] = useState(60);

    const fetchSpider = useCallback(async () => {
        setLoading(true);
        setError(null);
        setData(null);
        try {
            const tickers = [ref, ...tickersInput.split(',').map(t => t.trim().toUpperCase()).filter(Boolean)];
            const res = await fetch('http://127.0.0.1:8000/api/research/e/spider', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ref, tickers, window })
            });
            if (!res.ok) throw new Error('Failed to fetch spider data');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    }, [ref, tickersInput, window]);

    // NO useEffect - user must click Calculate

    const getCorrelationColor = (corr) => {
        if (corr === null) return '#6b7280';
        if (corr > 0.7) return '#10b981';
        if (corr > 0.3) return '#84cc16';
        if (corr > -0.3) return '#f59e0b';
        if (corr > -0.7) return '#f97316';
        return '#ef4444';
    };

    // Filter out the reference from axes for the radar
    const filteredAxes = data?.axes?.filter(a => a.ticker !== data.ref) || [];

    const radarData = filteredAxes.length > 0 ? [{
        type: 'scatterpolar',
        r: [...filteredAxes.map(a => (a.corr !== null ? a.corr : 0)), (filteredAxes[0]?.corr || 0)],
        theta: [...filteredAxes.map(a => a.ticker), filteredAxes[0]?.ticker],
        fill: 'toself',
        name: `Corr vs ${data.ref}`,
        line: { color: '#f7c843' },
        fillcolor: '#f7c84330'
    }] : [];

    return (
        <div className="h-full overflow-auto p-6 bg-terminal-black">
            <style jsx>{`
                .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; }
                .control-group { display: flex; flex-direction: column; gap: 4px; }
                .control-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-family: var(--font-mono); }
                .control-input { background: #0a0a0a; border: 1px solid #262626; padding: 8px 12px; color: #e5e5e5; font-size: 13px; border-radius: 4px; }
                .btn { background: #f7c843; color: #050505; padding: 8px 16px; font-size: 12px; font-weight: 600; border: none; border-radius: 4px; cursor: pointer; font-family: var(--font-mono); }
                .btn:disabled { opacity: 0.5; cursor: not-allowed; }
                .chart-container { background: #0a0a0a; border: 1px solid #262626; border-radius: 8px; padding: 16px; margin-bottom: 24px; }
                .corr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
                .corr-card { background: #0a0a0a; border: 1px solid #262626; border-radius: 8px; padding: 16px; text-align: center; }
                .corr-ticker { font-size: 14px; font-weight: 700; color: #e5e5e5; margin-bottom: 8px; font-family: var(--font-mono); }
                .corr-value { font-size: 24px; font-weight: 700; font-family: var(--font-mono); }
                .corr-label { font-size: 10px; color: #6b7280; margin-top: 4px; }
                .empty-state { text-align: center; padding: 48px 24px; color: #6b7280; border: 1px dashed #262626; border-radius: 8px; margin-top: 16px; }
            `}</style>

            <Link href="/labs/research" className="text-terminal-dim hover:text-terminal-yellow text-xs font-mono mb-4 inline-block">
                ← Back to Research
            </Link>

            <h1 className="text-xl font-bold text-terminal-yellow font-mono mb-2">SPIDER CHART</h1>
            <p className="text-terminal-dim text-sm mb-6">Cross-asset correlation relative to reference</p>

            <div className="controls">
                <div className="control-group">
                    <label className="control-label">Reference</label>
                    <input type="text" value={ref} onChange={(e) => setRef(e.target.value.toUpperCase())} className="control-input" style={{ width: 100 }} />
                </div>
                <div className="control-group">
                    <label className="control-label">Compare (comma separated)</label>
                    <input
                        type="text"
                        value={tickersInput}
                        onChange={(e) => setTickersInput(e.target.value)}
                        className="control-input"
                        style={{ minWidth: 300 }}
                    />
                </div>
                <div className="control-group">
                    <label className="control-label">Window</label>
                    <select value={window} onChange={(e) => setWindow(Number(e.target.value))} className="control-input">
                        <option value={21}>21d</option>
                        <option value={60}>60d</option>
                        <option value={126}>126d</option>
                        <option value={252}>252d</option>
                    </select>
                </div>
                <button onClick={fetchSpider} disabled={loading} className="btn" style={{ alignSelf: 'flex-end' }}>
                    {loading ? 'Loading...' : 'Calculate'}
                </button>
            </div>

            {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

            {!data && !loading && !error && (
                <div className="empty-state">
                    <p className="text-lg mb-2">Configure assets and click <strong>Calculate</strong></p>
                    <p className="text-sm text-terminal-dim">This will compute {window}d rolling correlations vs {ref}</p>
                </div>
            )}

            {data && (
                <>
                    {/* Spider Chart */}
                    <div className="chart-container">
                        <Plot
                            data={radarData}
                            layout={{
                                height: 450,
                                margin: { t: 40, r: 80, b: 40, l: 80 },
                                paper_bgcolor: 'transparent',
                                plot_bgcolor: 'transparent',
                                font: { color: '#6b7280', size: 11 },
                                polar: {
                                    bgcolor: 'transparent',
                                    radialaxis: {
                                        visible: true,
                                        range: [-1, 1],
                                        gridcolor: '#262626',
                                        linecolor: '#262626'
                                    },
                                    angularaxis: {
                                        gridcolor: '#262626',
                                        linecolor: '#262626'
                                    }
                                },
                                showlegend: false
                            }}
                            config={{ displayModeBar: false }}
                            style={{ width: '100%' }}
                        />
                    </div>

                    {/* Correlation Cards */}
                    <h3 className="text-sm font-bold text-terminal-text mb-4 font-mono">CORRELATIONS VS {data.ref}</h3>
                    <div className="corr-grid">
                        {filteredAxes.map(a => (
                            <div key={a.ticker} className="corr-card">
                                <div className="corr-ticker">{a.ticker}</div>
                                <div className="corr-value" style={{ color: getCorrelationColor(a.corr) }}>
                                    {a.corr !== null ? a.corr.toFixed(2) : 'N/A'}
                                </div>
                                <div className="corr-label">{window}d correlation</div>
                            </div>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
