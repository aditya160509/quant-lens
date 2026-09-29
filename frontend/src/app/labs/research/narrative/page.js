"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

/**
 * E1 Narrative Analytics Page
 * Generate structured market narrative from computed metrics.
 */
export default function NarrativePage() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [marketProxy, setMarketProxy] = useState('SPY');
    const [lookback, setLookback] = useState(60);

    const fetchNarrative = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/research/e/narrative', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ market_proxy: marketProxy, lookback_days: lookback })
            });
            if (!res.ok) throw new Error('Failed to fetch narrative');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchNarrative();
    }, []);

    const getRiskColor = (level) => {
        const colors = {
            calm: '#10b981',
            neutral: '#6b7280',
            cautious: '#f59e0b',
            stressed: '#ef4444',
            extreme: '#dc2626'
        };
        return colors[level] || '#6b7280';
    };

    return (
        <div className="h-full overflow-auto p-6 bg-terminal-black">
            <style jsx>{`
                .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; }
                .control-group { display: flex; flex-direction: column; gap: 4px; }
                .control-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-family: var(--font-mono); }
                .control-input { background: #0a0a0a; border: 1px solid #262626; padding: 8px 12px; color: #e5e5e5; font-size: 13px; border-radius: 4px; }
                .control-input:focus { outline: none; border-color: #f7c843; }
                .btn { background: #f7c843; color: #050505; padding: 8px 16px; font-size: 12px; font-weight: 600; border: none; border-radius: 4px; cursor: pointer; font-family: var(--font-mono); }
                .btn:hover { background: #fcd34d; }
                .btn:disabled { opacity: 0.5; cursor: not-allowed; }
                .section-card { background: #0a0a0a; border: 1px solid #262626; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
                .section-title { font-size: 12px; font-weight: 700; color: #f7c843; text-transform: uppercase; margin-bottom: 12px; font-family: var(--font-mono); }
                .section-text { font-size: 14px; color: #e5e5e5; line-height: 1.6; }
                .metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; margin-bottom: 24px; }
                .metric-card { background: #0a0a0a; border: 1px solid #262626; border-radius: 6px; padding: 12px; text-align: center; }
                .metric-label { font-size: 10px; color: #6b7280; margin-bottom: 4px; }
                .metric-value { font-size: 18px; font-weight: 700; color: #e5e5e5; font-family: var(--font-mono); }
                .risk-badge { display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 700; text-transform: uppercase; }
            `}</style>

            <Link href="/labs/research" className="text-terminal-dim hover:text-terminal-yellow text-xs font-mono mb-4 inline-block">
                ← Back to Research
            </Link>

            <h1 className="text-xl font-bold text-terminal-yellow font-mono mb-2">NARRATIVE ANALYTICS</h1>
            <p className="text-terminal-dim text-sm mb-6">AI-free market narrative from computed metrics</p>

            <div className="controls">
                <div className="control-group">
                    <label className="control-label">Market Proxy</label>
                    <select value={marketProxy} onChange={(e) => setMarketProxy(e.target.value)} className="control-input">
                        <option value="SPY">SPY</option>
                        <option value="QQQ">QQQ</option>
                        <option value="IWM">IWM</option>
                        <option value="DIA">DIA</option>
                    </select>
                </div>
                <div className="control-group">
                    <label className="control-label">Lookback (days)</label>
                    <input type="number" value={lookback} onChange={(e) => setLookback(Number(e.target.value))} className="control-input" style={{ width: 80 }} />
                </div>
                <button onClick={fetchNarrative} disabled={loading} className="btn" style={{ alignSelf: 'flex-end' }}>
                    {loading ? 'Loading...' : 'Generate'}
                </button>
            </div>

            {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

            {data && (
                <>
                    {/* Key Metrics */}
                    <div className="metrics-grid">
                        <div className="metric-card">
                            <div className="metric-label">1D Return</div>
                            <div className="metric-value" style={{ color: data.inputs?.ret_1d >= 0 ? '#10b981' : '#ef4444' }}>
                                {((data.inputs?.ret_1d || 0) * 100).toFixed(2)}%
                            </div>
                        </div>
                        <div className="metric-card">
                            <div className="metric-label">5D Return</div>
                            <div className="metric-value" style={{ color: data.inputs?.ret_5d >= 0 ? '#10b981' : '#ef4444' }}>
                                {((data.inputs?.ret_5d || 0) * 100).toFixed(2)}%
                            </div>
                        </div>
                        <div className="metric-card">
                            <div className="metric-label">21D Return</div>
                            <div className="metric-value" style={{ color: data.inputs?.ret_21d >= 0 ? '#10b981' : '#ef4444' }}>
                                {((data.inputs?.ret_21d || 0) * 100).toFixed(2)}%
                            </div>
                        </div>
                        <div className="metric-card">
                            <div className="metric-label">Realized Vol</div>
                            <div className="metric-value">
                                {((data.inputs?.rv_21d || 0) * 100).toFixed(1)}%
                            </div>
                        </div>
                        <div className="metric-card">
                            <div className="metric-label">Risk Level</div>
                            <span className="risk-badge" style={{ backgroundColor: getRiskColor(data.signals?.risk_level) + '20', color: getRiskColor(data.signals?.risk_level) }}>
                                {data.signals?.risk_level || 'N/A'}
                            </span>
                        </div>
                    </div>

                    {/* Narrative Sections */}
                    {data.sections?.map((section) => (
                        <div key={section.key} className="section-card">
                            <div className="section-title">{section.title}</div>
                            <div className="section-text">{section.text}</div>
                        </div>
                    ))}
                </>
            )}
        </div>
    );
}
