"use client";

/**
 * Alpha Momentum Research Page
 * Cross-sectional momentum scoring with z-score normalization
 */

import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { fetchMomentum } from '@/lib/api';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

// Shared styles
const panelStyle = { padding: '20px' };
const headerStyle = { fontFamily: "var(--font-mono)", fontSize: '18px', fontWeight: 700, color: '#ffd60a', letterSpacing: '0.1em', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' };
const controlBarStyle = { display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap' };
const inputStyle = { background: 'rgba(6, 10, 16, 0.8)', border: '1px solid rgba(30, 39, 56, 0.6)', borderRadius: '4px', padding: '10px 14px', color: '#e8eaed', fontFamily: "var(--font-mono)", fontSize: '12px', width: '300px' };
const buttonStyle = { background: 'linear-gradient(180deg, #10b981 0%, #059669 100%)', border: 'none', borderRadius: '4px', padding: '10px 20px', color: '#03050a', fontFamily: "var(--font-mono)", fontSize: '11px', fontWeight: 700, cursor: 'pointer', letterSpacing: '0.05em' };
const cardStyle = { background: 'rgba(6, 10, 16, 0.6)', border: '1px solid rgba(30, 39, 56, 0.5)', borderRadius: '6px', padding: '16px' };

const PHASE_COLORS = {
    'Early': '#10b981',
    'Established': '#3b82f6',
    'Late': '#f59e0b',
    'Exhausted': '#ef4444',
    'Neutral': '#6b7280'
};

export default function MomentumPage() {
    const [symbols, setSymbols] = useState('SPY,QQQ,AAPL,MSFT,NVDA,TSLA,AMZN,GOOGL,META,AMD');
    const [benchmark, setBenchmark] = useState('SPY');
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    
    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        
        try {
            const result = await fetchMomentum(symbols, benchmark);
            if (result.status === 'error') {
                setError(result.message || 'Failed to fetch momentum data');
            } else {
                setData(result);
            }
        } catch (e) {
            console.error('Momentum analysis error:', e);
            setError('Failed to fetch momentum data. Please try again.');
        }
        setLoading(false);
    }, [symbols, benchmark]);
    
    return (
        <div style={{ height: '100%', background: 'transparent', padding: '24px', overflow: 'auto' }}>
            {/* Breadcrumb */}
            <div style={{ marginBottom: '16px' }}>
                <Link href="/labs/research" style={{ color: '#5a6578', fontFamily: 'var(--font-mono)', fontSize: '11px', textDecoration: 'none' }}>
                    ← RESEARCH HUB
                </Link>
            </div>
            
            {/* Header */}
            <div style={headerStyle}>
                <span style={{ fontSize: '24px' }}>🚀</span>
                ALPHA MOMENTUM SCORING
            </div>
            
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#5a6578', marginBottom: '24px', maxWidth: '800px', lineHeight: '1.6' }}>
                Cross-sectional momentum analysis with z-score normalization. Measures risk-adjusted returns, 
                trend consistency, and relative strength. Classifies each security into trend phases: 
                Early, Established, Late, or Exhausted.
            </p>
            
            {/* Controls */}
            <div style={controlBarStyle}>
                <input 
                    value={symbols} 
                    onChange={(e) => setSymbols(e.target.value.toUpperCase())} 
                    style={inputStyle} 
                    placeholder="SPY,QQQ,AAPL,MSFT..." 
                />
                <input 
                    value={benchmark} 
                    onChange={(e) => setBenchmark(e.target.value.toUpperCase())} 
                    style={{ ...inputStyle, width: '100px' }} 
                    placeholder="Benchmark" 
                />
                <button onClick={runAnalysis} disabled={loading} style={buttonStyle}>
                    {loading ? 'SCORING...' : 'RUN ANALYSIS'}
                </button>
                {error && <span style={{ color: '#ef4444', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>⚠ {error}</span>}
            </div>
            
            {/* Results */}
            {data && data.data && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '20px' }}>
                    {/* Main Table */}
                    <div style={cardStyle}>
                        <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '16px', letterSpacing: '0.1em' }}>
                            MOMENTUM LEADERBOARD ({data.data.length} SECURITIES)
                        </div>
                        
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', fontFamily: "var(--font-mono)", fontSize: '11px', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ color: '#5a6578', borderBottom: '1px solid rgba(30, 39, 56, 0.5)' }}>
                                        <th style={{ textAlign: 'left', padding: '10px 8px' }}>Rank</th>
                                        <th style={{ textAlign: 'left', padding: '10px 8px' }}>Symbol</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>Score</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>3M Ret</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>6M Ret</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>Vol</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>Stability</th>
                                        <th style={{ textAlign: 'center', padding: '10px 8px' }}>Phase</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.data.map((row, idx) => (
                                        <tr key={row.symbol} style={{ borderBottom: '1px solid rgba(30, 39, 56, 0.3)' }}>
                                            <td style={{ padding: '10px 8px', color: '#5a6578' }}>#{idx + 1}</td>
                                            <td style={{ padding: '10px 8px', color: '#ffd60a', fontWeight: 600 }}>{row.symbol}</td>
                                            <td style={{ padding: '10px 8px', textAlign: 'right' }}>
                                                <span style={{ 
                                                    background: row.scores.score_0_100 >= 70 ? 'rgba(16, 185, 129, 0.2)' : 
                                                               row.scores.score_0_100 <= 30 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                                    color: row.scores.score_0_100 >= 70 ? '#10b981' : 
                                                          row.scores.score_0_100 <= 30 ? '#ef4444' : '#f59e0b',
                                                    padding: '4px 8px',
                                                    borderRadius: '4px',
                                                    fontWeight: 700
                                                }}>
                                                    {row.scores.score_0_100.toFixed(0)}
                                                </span>
                                            </td>
                                            <td style={{ 
                                                padding: '10px 8px', 
                                                textAlign: 'right', 
                                                color: row.returns.ret_63 >= 0 ? '#10b981' : '#ef4444' 
                                            }}>
                                                {(row.returns.ret_63 * 100).toFixed(1)}%
                                            </td>
                                            <td style={{ 
                                                padding: '10px 8px', 
                                                textAlign: 'right', 
                                                color: row.returns.ret_126 >= 0 ? '#10b981' : '#ef4444' 
                                            }}>
                                                {(row.returns.ret_126 * 100).toFixed(1)}%
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'right', color: '#e8eaed' }}>
                                                {(row.risk_metrics.vol_63 * 100).toFixed(1)}%
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'right', color: '#e8eaed' }}>
                                                {row.scores.stability_score.toFixed(0)}
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'center' }}>
                                                <span style={{
                                                    background: `${PHASE_COLORS[row.classification.trend_phase]}20`,
                                                    color: PHASE_COLORS[row.classification.trend_phase],
                                                    padding: '4px 8px',
                                                    borderRadius: '4px',
                                                    fontSize: '10px',
                                                    fontWeight: 600
                                                }}>
                                                    {row.classification.trend_phase}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    {/* Right Panel - Score Distribution */}
                    <div>
                        <div style={cardStyle}>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '16px', letterSpacing: '0.1em' }}>
                                SCORE DISTRIBUTION
                            </div>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={data.data.map(d => ({ symbol: d.symbol, score: d.scores.score_0_100 }))}>
                                    <XAxis dataKey="symbol" tick={{ fill: '#5a6578', fontSize: 9 }} />
                                    <YAxis tick={{ fill: '#5a6578', fontSize: 10 }} domain={[0, 100]} />
                                    <Tooltip contentStyle={{ background: '#0a0f18', border: '1px solid #1e2738', fontFamily: "var(--font-mono)", fontSize: '11px' }} />
                                    <Bar dataKey="score">
                                        {data.data.map((entry, index) => (
                                            <Cell 
                                                key={`cell-${index}`} 
                                                fill={entry.scores.score_0_100 >= 70 ? '#10b981' : 
                                                      entry.scores.score_0_100 <= 30 ? '#ef4444' : '#f59e0b'} 
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        
                        <div style={{ ...cardStyle, marginTop: '16px' }}>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '16px', letterSpacing: '0.1em' }}>
                                PHASE BREAKDOWN
                            </div>
                            {Object.entries(
                                data.data.reduce((acc, d) => {
                                    acc[d.classification.trend_phase] = (acc[d.classification.trend_phase] || 0) + 1;
                                    return acc;
                                }, {})
                            ).map(([phase, count]) => (
                                <div key={phase} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(30, 39, 56, 0.3)' }}>
                                    <span style={{ color: PHASE_COLORS[phase], fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{phase}</span>
                                    <span style={{ color: '#e8eaed', fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 600 }}>{count}</span>
                                </div>
                            ))}
                        </div>
                        
                        <div style={{ ...cardStyle, marginTop: '16px' }}>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '12px', letterSpacing: '0.1em' }}>
                                METHODOLOGY
                            </div>
                            <div style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', color: '#5a6578', lineHeight: '1.6' }}>
                                <div style={{ marginBottom: '8px' }}><strong style={{ color: '#e8eaed' }}>Score 0-100:</strong> Z-score normalized composite of 63/126/252-day returns, volatility-adjusted returns, consistency, and relative strength.</div>
                                <div style={{ marginBottom: '8px' }}><strong style={{ color: '#e8eaed' }}>Stability:</strong> Inverse of volatility and max drawdown percentile.</div>
                                <div><strong style={{ color: '#e8eaed' }}>Phase:</strong> Classifies trend maturity based on acceleration and consistency.</div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            
            {/* Empty State */}
            {!data && !loading && (
                <div style={{ textAlign: 'center', padding: '60px 20px', color: '#5a6578' }}>
                    <div style={{ fontSize: '48px', marginBottom: '16px' }}>🚀</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '14px' }}>{'Enter symbols and click "RUN ANALYSIS" to score momentum'}</div>
                </div>
            )}
        </div>
    );
}
