"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

/**
 * E2 Risk Thermometer Page
 * Composite risk score with explainable components.
 */
export default function RiskPage() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [lookback, setLookback] = useState(252);

    const fetchRiskScore = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/research/e/risk_score', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lookback_days: lookback })
            });
            if (!res.ok) throw new Error('Failed to fetch risk score');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchRiskScore();
    }, []);

    const getScoreColor = (score) => {
        if (score < 20) return '#10b981';
        if (score < 40) return '#6b7280';
        if (score < 60) return '#f59e0b';
        if (score < 80) return '#ef4444';
        return '#dc2626';
    };

    const getLabelColor = (label) => {
        const colors = {
            calm: '#10b981',
            neutral: '#6b7280',
            cautious: '#f59e0b',
            stressed: '#ef4444',
            extreme: '#dc2626'
        };
        return colors[label] || '#6b7280';
    };

    return (
        <div className="h-full overflow-auto p-6 bg-terminal-black">
            <style jsx>{`
                .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 24px; }
                .control-group { display: flex; flex-direction: column; gap: 4px; }
                .control-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-family: var(--font-mono); }
                .control-input { background: #0a0a0a; border: 1px solid #262626; padding: 8px 12px; color: #e5e5e5; font-size: 13px; border-radius: 4px; width: 100px; }
                .btn { background: #f7c843; color: #050505; padding: 8px 16px; font-size: 12px; font-weight: 600; border: none; border-radius: 4px; cursor: pointer; font-family: var(--font-mono); }
                .score-container { text-align: center; margin-bottom: 32px; }
                .score-value { font-size: 72px; font-weight: 700; font-family: var(--font-mono); }
                .score-label { font-size: 18px; font-weight: 700; text-transform: uppercase; margin-top: 8px; }
                .gauge-container { width: 100%; max-width: 500px; margin: 0 auto 32px; height: 24px; background: #1a1a1a; border-radius: 12px; overflow: hidden; position: relative; }
                .gauge-fill { height: 100%; transition: width 0.5s ease; border-radius: 12px; }
                .gauge-markers { position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; justify-content: space-between; padding: 0 8px; align-items: center; font-size: 10px; color: #6b7280; }
                .components-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
                .component-card { background: #0a0a0a; border: 1px solid #262626; border-radius: 8px; padding: 16px; }
                .component-name { font-size: 12px; font-weight: 700; color: #f7c843; text-transform: uppercase; margin-bottom: 12px; font-family: var(--font-mono); }
                .component-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; }
                .component-label { color: #6b7280; }
                .component-value { color: #e5e5e5; font-family: var(--font-mono); }
                .stress-bar { height: 6px; background: #1a1a1a; border-radius: 3px; margin-top: 8px; overflow: hidden; }
                .stress-fill { height: 100%; border-radius: 3px; }
            `}</style>

            <Link href="/labs/research" className="text-terminal-dim hover:text-terminal-yellow text-xs font-mono mb-4 inline-block">
                ← Back to Research
            </Link>

            <h1 className="text-xl font-bold text-terminal-yellow font-mono mb-2">RISK THERMOMETER</h1>
            <p className="text-terminal-dim text-sm mb-6">Composite 0-100 risk score with explainable components</p>

            <div className="controls">
                <div className="control-group">
                    <label className="control-label">Lookback (days)</label>
                    <input type="number" value={lookback} onChange={(e) => setLookback(Number(e.target.value))} className="control-input" />
                </div>
                <button onClick={fetchRiskScore} disabled={loading} className="btn" style={{ alignSelf: 'flex-end' }}>
                    {loading ? 'Loading...' : 'Calculate'}
                </button>
            </div>

            {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

            {data && (
                <>
                    {/* Main Score */}
                    <div className="score-container">
                        <div className="score-value" style={{ color: getScoreColor(data.risk_score) }}>
                            {data.risk_score?.toFixed(1)}
                        </div>
                        <div className="score-label" style={{ color: getLabelColor(data.label) }}>
                            {data.label}
                        </div>
                    </div>

                    {/* Gauge */}
                    <div className="gauge-container">
                        <div className="gauge-fill" style={{ width: `${data.risk_score}%`, backgroundColor: getScoreColor(data.risk_score) }} />
                        <div className="gauge-markers">
                            <span>0</span>
                            <span>20</span>
                            <span>40</span>
                            <span>60</span>
                            <span>80</span>
                            <span>100</span>
                        </div>
                    </div>

                    {/* Components */}
                    <h3 className="text-sm font-bold text-terminal-text mb-4 font-mono">COMPONENT BREAKDOWN</h3>
                    <div className="components-grid">
                        {Object.entries(data.components || {}).map(([key, comp]) => (
                            <div key={key} className="component-card">
                                <div className="component-name">{key.replace('_', ' ')}</div>
                                <div className="component-row">
                                    <span className="component-label">Value</span>
                                    <span className="component-value">{typeof comp.value === 'number' ? comp.value.toFixed(2) : comp.value}</span>
                                </div>
                                <div className="component-row">
                                    <span className="component-label">Z-Score</span>
                                    <span className="component-value">{comp.z?.toFixed(2)}</span>
                                </div>
                                <div className="component-row">
                                    <span className="component-label">Stress</span>
                                    <span className="component-value">{(comp.stress * 100).toFixed(0)}%</span>
                                </div>
                                <div className="component-row">
                                    <span className="component-label">Weight</span>
                                    <span className="component-value">{(comp.weight * 100).toFixed(0)}%</span>
                                </div>
                                <div className="stress-bar">
                                    <div className="stress-fill" style={{ width: `${comp.stress * 100}%`, backgroundColor: getScoreColor(comp.stress * 100) }} />
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
