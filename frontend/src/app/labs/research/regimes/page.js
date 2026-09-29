"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell, CartesianGrid } from 'recharts';
import { postRegimes } from '@/lib/api/research';
import { researchTokens } from '@/lib/theme/researchTokens';
import ExportButtons from '@/components/research/ExportButtons';
import StatusMeta from '@/components/research/StatusMeta';
import ControlPanel, { ControlGroup, ControlSelect, ControlSlider } from '@/components/research/ControlPanel';

const INPUTS = ['VIX', 'YC_SLOPE', 'CREDIT', 'RATES', 'INFLATION', 'MOMENTUM'];
const MODELS = [
    { value: 'zscore', label: 'Z-Score Composite' },
    { value: 'kmeans', label: 'K-Means Clustering' },
    { value: 'hmm', label: 'Hidden Markov Model' },
];
const LOOKBACKS = [
    { value: 756, label: '3 Years' },
    { value: 1095, label: '~4.5 Years' },
    { value: 1460, label: '~6 Years' },
];

const REGIME_COLORS = {
    'Risk On': researchTokens.colors.good,
    'Neutral': researchTokens.colors.warn,
    'Risk Off': researchTokens.colors.bad
};

export default function RegimesPage() {
    // Controls
    const [selectedInputs, setSelectedInputs] = useState(['VIX', 'YC_SLOPE']);
    const [modelType, setModelType] = useState('zscore');
    const [lookback, setLookback] = useState(1095);
    const [smoothDays, setSmoothDays] = useState(5);
    const [riskOnThreshold, setRiskOnThreshold] = useState(-0.5);
    const [riskOffThreshold, setRiskOffThreshold] = useState(0.5);
    const [weights, setWeights] = useState({ VIX: 0.5, YC_SLOPE: 0.3, CREDIT: 0.2 });

    // Results
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Update weight
    const updateWeight = useCallback((input, value) => {
        setWeights(prev => ({ ...prev, [input]: value }));
    }, []);

    // Apply
    const handleApply = useCallback(async () => {
        if (selectedInputs.length === 0) {
            setError({ message: 'Select at least one input series' });
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const activeWeights = {};
            selectedInputs.forEach(i => {
                activeWeights[i] = weights[i] || 0.25;
            });

            const data = await postRegimes({
                inputs: selectedInputs,
                lookback,
                model: {
                    type: modelType,
                    weights: activeWeights,
                    smooth_days: smoothDays,
                    thresholds: {
                        risk_on: riskOnThreshold,
                        risk_off: riskOffThreshold
                    },
                    n_clusters: 3,
                    n_states: 3
                }
            });

            setResults(data);
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
        }
    }, [selectedInputs, lookback, modelType, smoothDays, riskOnThreshold, riskOffThreshold, weights]);

    // Chart data
    const chartData = useMemo(() => {
        if (!results?.timeline) return [];
        return results.timeline.map(d => ({
            ...d,
            fillColor: REGIME_COLORS[d.regime] || researchTokens.colors.muted
        }));
    }, [results]);

    // Contribution chart data
    const contributorData = useMemo(() => {
        if (!results?.contributors) return [];
        return Object.entries(results.contributors)
            .map(([name, value]) => ({ name, value }))
            .sort((a, b) => b.value - a.value);
    }, [results]);

    // Export data
    const exportData = useMemo(() => {
        if (!results?.timeline) return [];
        return results.timeline.map(d => ({
            date: d.date,
            regime: d.regime,
            score: d.score,
            confidence: d.confidence
        }));
    }, [results]);

    return (
        <div className="regimes-page">
            <style jsx>{`
                .regimes-page {
                    height: calc(100vh - 80px);
                    display: flex;
                    flex-direction: column;
                    padding-bottom: ${researchTokens.spacing.lg}px;
                }
                .back-link {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    color: ${researchTokens.colors.muted};
                    font-size: 12px;
                    text-decoration: none;
                    margin-bottom: 20px;
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    flex-shrink: 0;
                }
                .back-link:hover {
                    color: ${researchTokens.colors.warn};
                }
                .page-header {
                    margin-bottom: ${researchTokens.spacing.lg}px;
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    padding-bottom: ${researchTokens.spacing.md}px;
                    flex-shrink: 0;
                }
                .page-title {
                    font-size: ${researchTokens.typography.h2}px;
                    font-weight: 700;
                    color: ${researchTokens.colors.warn};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    margin-bottom: ${researchTokens.spacing.xs}px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                .page-subtitle {
                    font-size: ${researchTokens.typography.body}px;
                    color: ${researchTokens.colors.muted};
                    opacity: 0.8;
                }
                .main-layout {
                    display: grid;
                    grid-template-columns: 240px 1fr;
                    grid-template-rows: minmax(0, 1fr);
                    gap: ${researchTokens.spacing.lg}px;
                    flex-grow: 1;
                    min-height: 0;
                }
                .main-content {
                    display: flex;
                    flex-direction: column;
                    gap: ${researchTokens.spacing.lg}px;
                    overflow-y: auto;
                    min-height: 0;
                    padding-right: 4px;
                }
                .panel {
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: ${researchTokens.radius.panel}px;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    flex-shrink: 0;
                }
                .panel-title {
                    font-size: 13px;
                    font-weight: 700;
                    color: ${researchTokens.colors.text};
                    font-family: var(--font-mono);
                    margin-bottom: 16px;
                    text-transform: uppercase;
                }
                .current-regime {
                    display: flex;
                    align-items: center;
                    gap: 20px;
                    padding: 24px;
                    border-radius: ${researchTokens.radius.card}px;
                    margin-bottom: 0;
                    box-shadow: ${researchTokens.shadow.lg};
                    flex-shrink: 0;
                }
                .regime-indicator {
                    width: 70px;
                    height: 70px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 32px;
                    box-shadow: 0 0 20px rgba(0,0,0,0.2);
                }
                .regime-info {
                    flex: 1;
                }
                .regime-label {
                    font-size: 28px;
                    font-weight: 700;
                    margin-bottom: 8px;
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    line-height: 1.1;
                }
                .regime-stats {
                    display: flex;
                    gap: 24px;
                    font-size: 13px;
                    color: ${researchTokens.colors.muted2};
                    font-family: var(--font-mono);
                }
                .stat-item {
                    display: flex;
                    gap: 8px;
                    align-items: center;
                }
                .stat-value {
                    font-weight: 700;
                    color: ${researchTokens.colors.text};
                    font-size: 14px;
                }
                .empty-state {
                    text-align: center;
                    padding: 80px 20px;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    opacity: 0.6;
                }
                .empty-icon {
                    font-size: 40px;
                    margin-bottom: 16px;
                    color: ${researchTokens.colors.border2};
                }
                .legend {
                    display: flex;
                    gap: 24px;
                    margin-top: 16px;
                    font-size: 11px;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    justify-content: center;
                }
                .legend-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .legend-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                }
            `}</style>

            <Link href="/labs/research" className="back-link">
                ← Back
            </Link>

            <div className="page-header">
                <h1 className="page-title"><span style={{ fontSize: 24 }}>🌊</span> Regime Detection</h1>
                <p className="page-subtitle">
                    Identify market states using unsupervised learning or composite indicators on macro data.
                </p>
            </div>

            <div className="main-layout">
                {/* Control Panel */}
                <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <ControlPanel
                        title="Model Config"
                        onApply={handleApply}
                        loading={loading}
                        description="Configure model inputs and parameters."
                    >
                        <ControlGroup label="Input Series">
                            <ControlSelect
                                value={selectedInputs}
                                onChange={setSelectedInputs}
                                options={INPUTS}
                                multiple
                                size={4}
                            />
                        </ControlGroup>

                        <ControlGroup label="Model Type">
                            <ControlSelect
                                value={modelType}
                                onChange={setModelType}
                                options={MODELS}
                            />
                        </ControlGroup>

                        <ControlGroup label="Lookback">
                            <ControlSelect
                                value={lookback}
                                onChange={v => setLookback(Number(v))}
                                options={LOOKBACKS}
                            />
                        </ControlGroup>

                        {modelType === 'zscore' && (
                            <>
                                <ControlSlider
                                    label="Smooth Days"
                                    value={smoothDays}
                                    onChange={v => setSmoothDays(Math.round(v))}
                                    min={1}
                                    max={20}
                                    step={1}
                                />

                                <ControlSlider
                                    label="Risk On Thresh"
                                    value={riskOnThreshold}
                                    onChange={setRiskOnThreshold}
                                    min={-1.5}
                                    max={0}
                                    step={0.1}
                                />

                                <ControlSlider
                                    label="Risk Off Thresh"
                                    value={riskOffThreshold}
                                    onChange={setRiskOffThreshold}
                                    min={0}
                                    max={1.5}
                                    step={0.1}
                                />

                                <ControlGroup label="Weights">
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                        {selectedInputs.map(input => (
                                            <ControlSlider
                                                key={input}
                                                label={input}
                                                value={weights[input] || 0.25}
                                                onChange={v => updateWeight(input, v)}
                                                min={0}
                                                max={1}
                                                step={0.05}
                                            />
                                        ))}
                                    </div>
                                </ControlGroup>
                            </>
                        )}
                    </ControlPanel>
                </div>

                {/* Main Content */}
                <div className="main-content">
                    {/* Status Bar */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <StatusMeta meta={results?.meta} loading={loading} error={error} />
                        <ExportButtons data={exportData} meta={results?.meta} filename="regimes" disabled={!results} />
                    </div>

                    {/* Current Regime Card */}
                    {results?.current ? (
                        <div
                            className="current-regime"
                            style={{
                                background: `linear-gradient(90deg, ${REGIME_COLORS[results.current.regime]}10 0%, transparent 100%)`,
                                border: `1px solid ${REGIME_COLORS[results.current.regime]}30`
                            }}
                        >
                            <div
                                className="regime-indicator"
                                style={{ backgroundColor: `${REGIME_COLORS[results.current.regime]}20`, color: REGIME_COLORS[results.current.regime], border: `1px solid ${REGIME_COLORS[results.current.regime]}` }}
                            >
                                {results.current.regime === 'Risk On' ? '📈' :
                                    results.current.regime === 'Risk Off' ? '📉' : '⚖️'}
                            </div>
                            <div className="regime-info">
                                <div className="regime-label" style={{ color: REGIME_COLORS[results.current.regime] }}>
                                    {results.current.regime}
                                </div>
                                <div className="regime-stats">
                                    <div className="stat-item">
                                        <span>AS OF</span>
                                        <span className="stat-value">{results.current.date}</span>
                                    </div>
                                    <div className="stat-item">
                                        <span>SCORE</span>
                                        <span className="stat-value">{results.current.score?.toFixed(2)}</span>
                                    </div>
                                    <div className="stat-item">
                                        <span>CONFIDENCE</span>
                                        <span className="stat-value">{(results.current.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        !loading && (
                            <div style={{ padding: 20, textAlign: 'center', color: researchTokens.colors.muted, border: `1px dashed ${researchTokens.colors.border}`, borderRadius: 8 }}>
                                No regime data detected.
                            </div>
                        )
                    )}

                    {/* Timeline Chart */}
                    <div className="panel">
                        <div className="panel-title">Regime Score Timeline</div>

                        {!results && !loading ? (
                            <div className="empty-state">
                                <div className="empty-icon">🌊</div>
                                Select input series and model type to detect regimes.
                            </div>
                        ) : (
                            <>
                                <div style={{ height: 300 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={researchTokens.colors.border2} vertical={false} />
                                            <XAxis
                                                dataKey="date"
                                                tick={{ fill: researchTokens.colors.muted, fontSize: 10, fontFamily: 'monospace' }}
                                                tickFormatter={(v) => {
                                                    const d = new Date(v);
                                                    return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(2)}`;
                                                }}
                                                axisLine={false}
                                                tickLine={false}
                                                dy={10}
                                            />
                                            <YAxis
                                                tick={{ fill: researchTokens.colors.muted, fontSize: 10, fontFamily: 'monospace' }}
                                                domain={['auto', 'auto']}
                                                axisLine={false}
                                                tickLine={false}
                                            />
                                            <Tooltip
                                                contentStyle={{
                                                    background: researchTokens.colors.surface2,
                                                    border: `1px solid ${researchTokens.colors.border}`,
                                                    borderRadius: 4,
                                                    fontFamily: 'monospace'
                                                }}
                                                itemStyle={{ color: researchTokens.colors.text }}
                                                labelStyle={{ color: researchTokens.colors.muted }}
                                                formatter={(value, name) => [value?.toFixed(3), 'Score']}
                                                labelFormatter={(label) => `Date: ${label}`}
                                            />
                                            <ReferenceLine y={riskOnThreshold} stroke={researchTokens.colors.good} strokeDasharray="3 3" strokeOpacity={0.5} label={{ value: 'Risk On', position: 'right', fill: researchTokens.colors.good, fontSize: 10 }} />
                                            <ReferenceLine y={riskOffThreshold} stroke={researchTokens.colors.bad} strokeDasharray="3 3" strokeOpacity={0.5} label={{ value: 'Risk Off', position: 'right', fill: researchTokens.colors.bad, fontSize: 10 }} />
                                            <ReferenceLine y={0} stroke={researchTokens.colors.muted} />
                                            <Area
                                                type="monotone"
                                                dataKey="score"
                                                stroke={researchTokens.colors.accent}
                                                fill={`${researchTokens.colors.accent}20`}
                                                strokeWidth={2}
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>

                                <div className="legend">
                                    <div className="legend-item">
                                        <div className="legend-dot" style={{ background: researchTokens.colors.good }}></div>
                                        <span>Risk On</span>
                                    </div>
                                    <div className="legend-item">
                                        <div className="legend-dot" style={{ background: researchTokens.colors.warn }}></div>
                                        <span>Neutral</span>
                                    </div>
                                    <div className="legend-item">
                                        <div className="legend-dot" style={{ background: researchTokens.colors.bad }}></div>
                                        <span>Risk Off</span>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Contributors */}
                    {results?.contributors && Object.keys(results.contributors).length > 0 && (
                        <div className="panel" style={{ height: 250 }}>
                            <div className="panel-title">Current Driver Contributions</div>
                            <div style={{ flex: 1, minHeight: 0 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={contributorData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={researchTokens.colors.border2} horizontal={false} />
                                        <XAxis type="number" tick={{ fill: researchTokens.colors.muted, fontSize: 10 }} axisLine={false} tickLine={false} />
                                        <YAxis type="category" dataKey="name" tick={{ fill: researchTokens.colors.muted, fontSize: 11, fontFamily: 'monospace' }} width={80} axisLine={false} tickLine={false} />
                                        <Tooltip
                                            cursor={{ fill: 'transparent' }}
                                            contentStyle={{
                                                background: researchTokens.colors.surface2,
                                                border: `1px solid ${researchTokens.colors.border}`,
                                                borderRadius: 4
                                            }}
                                            formatter={(v) => [v?.toFixed(3), 'Contribution']}
                                        />
                                        <ReferenceLine x={0} stroke={researchTokens.colors.muted} />
                                        <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                                            {contributorData.map((entry, index) => (
                                                <Cell key={index} fill={entry.value >= 0 ? researchTokens.colors.bad : researchTokens.colors.good} fillOpacity={0.8} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
