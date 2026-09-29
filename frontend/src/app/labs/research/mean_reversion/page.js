"use client";

/**
 * Mean Reversion Research Page
 * Quantify stretch vs statistical behavior with confidence gating
 */

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { fetchMeanReversion } from '@/lib/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ScatterChart, Scatter, ZAxis } from 'recharts';

// Shared styles
const panelStyle = { padding: '20px' };
const headerStyle = { fontFamily: "var(--font-mono)", fontSize: '18px', fontWeight: 700, color: '#ffd60a', letterSpacing: '0.1em', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' };
const controlBarStyle = { display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap' };
const inputStyle = { background: 'rgba(6, 10, 16, 0.8)', border: '1px solid rgba(30, 39, 56, 0.6)', borderRadius: '4px', padding: '10px 14px', color: '#e8eaed', fontFamily: "var(--font-mono)", fontSize: '12px', width: '300px' };
const selectStyle = { background: 'rgba(6, 10, 16, 0.8)', border: '1px solid rgba(30, 39, 56, 0.6)', borderRadius: '4px', padding: '10px 14px', color: '#e8eaed', fontFamily: "var(--font-mono)", fontSize: '12px' };
const buttonStyle = { background: 'linear-gradient(180deg, #f59e0b 0%, #d97706 100%)', border: 'none', borderRadius: '4px', padding: '10px 20px', color: '#03050a', fontFamily: "var(--font-mono)", fontSize: '11px', fontWeight: 700, cursor: 'pointer', letterSpacing: '0.05em' };
const cardStyle = { background: 'rgba(6, 10, 16, 0.6)', border: '1px solid rgba(30, 39, 56, 0.5)', borderRadius: '6px', padding: '16px' };

const QUALITY_COLORS = {
    'High Probability': '#10b981',
    'Moderate': '#3b82f6',
    'Tactical': '#f59e0b',
    'Low Odds': '#ef4444'
};

const DIRECTION_COLORS = {
    'oversold': '#10b981',
    'overbought': '#ef4444',
    'neutral': '#6b7280'
};

export default function MeanReversionPage() {
    const [symbols, setSymbols] = useState('SPY,QQQ,AAPL,MSFT,NVDA,TSLA,AMZN,GOOGL,META,AMD');
    const [sensitivity, setSensitivity] = useState('conservative');
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    
    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        
        try {
            const result = await fetchMeanReversion(symbols, sensitivity);
            if (result.status === 'error') {
                setError(result.message || 'Failed to fetch mean reversion data');
            } else {
                setData(result);
            }
        } catch (e) {
            console.error('Mean reversion analysis error:', e);
            setError('Failed to fetch mean reversion data. Please try again.');
        }
        setLoading(false);
    }, [symbols, sensitivity]);
    
    // Heatmap data
    const heatmapData = useMemo(() => {
        if (!data?.data) return [];
        return data.data.map(d => ({
            symbol: d.symbol,
            magnitude: d.scores.magnitude_0_100,
            confidence: d.scores.confidence_0_100,
            direction: d.scores.direction,
            quality: d.scores.quality_label
        }));
    }, [data]);
    
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
                <span style={{ fontSize: '24px' }}>🎯</span>
                MEAN REVERSION SIGNALS
            </div>
            
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: '#5a6578', marginBottom: '24px', maxWidth: '800px', lineHeight: '1.6' }}>
                Quantify price stretch using RSI, Bollinger Z-score, and ATR-normalized distance. 
                Confidence gating reduces false signals by filtering for volatility regime, earnings proximity, 
                and momentum conflicts.
            </p>
            
            {/* Controls */}
            <div style={controlBarStyle}>
                <input 
                    value={symbols} 
                    onChange={(e) => setSymbols(e.target.value.toUpperCase())} 
                    style={inputStyle} 
                    placeholder="SPY,QQQ,AAPL,MSFT..." 
                />
                <select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)} style={selectStyle}>
                    <option value="conservative">Conservative (20/50 MA)</option>
                    <option value="aggressive">Aggressive (10/20 MA)</option>
                </select>
                <button onClick={runAnalysis} disabled={loading} style={buttonStyle}>
                    {loading ? 'ANALYZING...' : 'RUN ANALYSIS'}
                </button>
                {error && <span style={{ color: '#ef4444', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>⚠ {error}</span>}
            </div>
            
            {/* Results */}
            {data && data.data && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '20px' }}>
                    {/* Main Table */}
                    <div style={cardStyle}>
                        <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '16px', letterSpacing: '0.1em' }}>
                            STRETCH SIGNALS ({data.data.length} SECURITIES)
                        </div>
                        
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', fontFamily: "var(--font-mono)", fontSize: '11px', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ color: '#5a6578', borderBottom: '1px solid rgba(30, 39, 56, 0.5)' }}>
                                        <th style={{ textAlign: 'left', padding: '10px 8px' }}>Symbol</th>
                                        <th style={{ textAlign: 'center', padding: '10px 8px' }}>Direction</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>Mag</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>Conf</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>RSI</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>Boll Z</th>
                                        <th style={{ textAlign: 'right', padding: '10px 8px' }}>ATR Str</th>
                                        <th style={{ textAlign: 'center', padding: '10px 8px' }}>Quality</th>
                                        <th style={{ textAlign: 'center', padding: '10px 8px' }}>Flag</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.data.map((row, idx) => (
                                        <tr key={row.symbol} style={{ borderBottom: '1px solid rgba(30, 39, 56, 0.3)' }}>
                                            <td style={{ padding: '10px 8px', color: '#ffd60a', fontWeight: 600 }}>{row.symbol}</td>
                                            <td style={{ padding: '10px 8px', textAlign: 'center' }}>
                                                <span style={{
                                                    background: `${DIRECTION_COLORS[row.scores.direction]}20`,
                                                    color: DIRECTION_COLORS[row.scores.direction],
                                                    padding: '3px 8px',
                                                    borderRadius: '4px',
                                                    fontSize: '10px',
                                                    fontWeight: 600,
                                                    textTransform: 'uppercase'
                                                }}>
                                                    {row.scores.direction === 'oversold' ? '▲ OVERSOLD' : 
                                                     row.scores.direction === 'overbought' ? '▼ OVERBOUGHT' : '— NEUTRAL'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'right' }}>
                                                <span style={{ 
                                                    color: row.scores.magnitude_0_100 > 60 ? '#f59e0b' : '#e8eaed',
                                                    fontWeight: row.scores.magnitude_0_100 > 60 ? 700 : 400
                                                }}>
                                                    {row.scores.magnitude_0_100.toFixed(0)}
                                                </span>
                                            </td>
                                            <td style={{ 
                                                padding: '10px 8px', 
                                                textAlign: 'right', 
                                                color: row.scores.confidence_0_100 > 60 ? '#10b981' : 
                                                       row.scores.confidence_0_100 < 40 ? '#ef4444' : '#f59e0b'
                                            }}>
                                                {row.scores.confidence_0_100.toFixed(0)}%
                                            </td>
                                            <td style={{ 
                                                padding: '10px 8px', 
                                                textAlign: 'right', 
                                                color: row.stretch_indicators.rsi > 70 ? '#ef4444' : 
                                                       row.stretch_indicators.rsi < 30 ? '#10b981' : '#e8eaed' 
                                            }}>
                                                {row.stretch_indicators.rsi.toFixed(1)}
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'right', color: '#e8eaed' }}>
                                                {row.stretch_indicators.boll_z.toFixed(2)}
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'right', color: '#e8eaed' }}>
                                                {row.stretch_indicators.stretch_atr.toFixed(2)}
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'center' }}>
                                                <span style={{
                                                    background: `${QUALITY_COLORS[row.scores.quality_label]}20`,
                                                    color: QUALITY_COLORS[row.scores.quality_label],
                                                    padding: '3px 8px',
                                                    borderRadius: '4px',
                                                    fontSize: '10px',
                                                    fontWeight: 600
                                                }}>
                                                    {row.scores.quality_label}
                                                </span>
                                            </td>
                                            <td style={{ padding: '10px 8px', textAlign: 'center' }}>
                                                {row.flags.dangerous && (
                                                    <span style={{ color: '#ef4444', fontSize: '14px' }} title="Dangerous Zone">⚠️</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    {/* Right Panel */}
                    <div>
                        {/* Magnitude vs Confidence Scatter */}
                        <div style={cardStyle}>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '16px', letterSpacing: '0.1em' }}>
                                MAGNITUDE vs CONFIDENCE
                            </div>
                            <ResponsiveContainer width="100%" height={200}>
                                <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                                    <XAxis dataKey="magnitude" name="Magnitude" tick={{ fill: '#5a6578', fontSize: 10 }} domain={[0, 100]} />
                                    <YAxis dataKey="confidence" name="Confidence" tick={{ fill: '#5a6578', fontSize: 10 }} domain={[0, 100]} />
                                    <Tooltip 
                                        contentStyle={{ background: '#0a0f18', border: '1px solid #1e2738', fontFamily: "var(--font-mono)", fontSize: '11px' }} 
                                        formatter={(value, name) => [value.toFixed(1), name]}
                                        labelFormatter={(value) => `Symbol: ${heatmapData.find(d => d.magnitude === value)?.symbol || ''}`}
                                    />
                                    <Scatter data={heatmapData}>
                                        {heatmapData.map((entry, index) => (
                                            <Cell 
                                                key={`cell-${index}`} 
                                                fill={DIRECTION_COLORS[entry.direction]} 
                                            />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                            </ResponsiveContainer>
                            <div style={{ fontSize: '10px', color: '#5a6578', marginTop: '8px', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                                High magnitude + High confidence = Best opportunities
                            </div>
                        </div>
                        
                        {/* Quality Breakdown */}
                        <div style={{ ...cardStyle, marginTop: '16px' }}>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '16px', letterSpacing: '0.1em' }}>
                                QUALITY BREAKDOWN
                            </div>
                            {Object.entries(
                                data.data.reduce((acc, d) => {
                                    acc[d.scores.quality_label] = (acc[d.scores.quality_label] || 0) + 1;
                                    return acc;
                                }, {})
                            ).map(([quality, count]) => (
                                <div key={quality} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(30, 39, 56, 0.3)' }}>
                                    <span style={{ color: QUALITY_COLORS[quality], fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{quality}</span>
                                    <span style={{ color: '#e8eaed', fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 600 }}>{count}</span>
                                </div>
                            ))}
                        </div>
                        
                        {/* Direction Summary */}
                        <div style={{ ...cardStyle, marginTop: '16px' }}>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '16px', letterSpacing: '0.1em' }}>
                                DIRECTION SUMMARY
                            </div>
                            {Object.entries(
                                data.data.reduce((acc, d) => {
                                    acc[d.scores.direction] = (acc[d.scores.direction] || 0) + 1;
                                    return acc;
                                }, {})
                            ).map(([dir, count]) => (
                                <div key={dir} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(30, 39, 56, 0.3)' }}>
                                    <span style={{ color: DIRECTION_COLORS[dir], fontFamily: 'var(--font-mono)', fontSize: '12px', textTransform: 'capitalize' }}>{dir}</span>
                                    <span style={{ color: '#e8eaed', fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 600 }}>{count}</span>
                                </div>
                            ))}
                        </div>
                        
                        <div style={{ ...cardStyle, marginTop: '16px' }}>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: '10px', color: '#5a6578', marginBottom: '12px', letterSpacing: '0.1em' }}>
                                METHODOLOGY
                            </div>
                            <div style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', color: '#5a6578', lineHeight: '1.6' }}>
                                <div style={{ marginBottom: '8px' }}><strong style={{ color: '#e8eaed' }}>Stretch:</strong> Weighted average of RSI deviation, Bollinger Z-score, ATR-normalized distance.</div>
                                <div style={{ marginBottom: '8px' }}><strong style={{ color: '#e8eaed' }}>Confidence:</strong> Reduces based on volatility regime, earnings proximity, momentum conflicts.</div>
                                <div><strong style={{ color: '#e8eaed' }}>⚠️ Dangerous:</strong> High stretch in elevated volatility regime - proceed with caution.</div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            
            {/* Empty State */}
            {!data && !loading && (
                <div style={{ textAlign: 'center', padding: '60px 20px', color: '#5a6578' }}>
                    <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎯</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '14px' }}>{'Enter symbols and click "RUN ANALYSIS" to detect mean reversion signals'}</div>
                </div>
            )}
        </div>
    );
}
