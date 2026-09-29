"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell, CartesianGrid } from 'recharts';
import { fetchUniverse, postMacroShock } from '@/lib/api/research';
import { researchTokens } from '@/lib/theme/researchTokens';
import UniversePicker from '@/components/research/UniversePicker';
import ExportButtons from '@/components/research/ExportButtons';
import StatusMeta from '@/components/research/StatusMeta';
import ControlPanel, { ControlGroup, ControlSelect, ControlSlider } from '@/components/research/ControlPanel';

const DRIVERS = ['RATES', 'USD', 'VIX', 'YC_SLOPE', 'OIL', 'CPI'];
const LOOKBACKS = [
    { value: 504, label: '2 Years' },
    { value: 756, label: '3 Years' },
    { value: 1008, label: '4 Years' },
];

export default function MacroShockPage() {
    // Universe
    const [universe, setUniverse] = useState([]);
    const [universeLoading, setUniverseLoading] = useState(true);

    // Controls
    const [selectedTickers, setSelectedTickers] = useState(['SPY', 'QQQ', 'TLT', 'GLD', 'XLE', 'EEM', 'HYG', 'LQD']);
    const [selectedDrivers, setSelectedDrivers] = useState(['RATES', 'USD']);
    const [lookback, setLookback] = useState(756);
    const [shockMode, setShockMode] = useState('sigma');
    const [shocks, setShocks] = useState({ RATES: 1.0, USD: 0.5, VIX: 0, YC_SLOPE: 0, OIL: 0, CPI: 0 });

    // Results
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Selected ticker for detail
    const [selectedTicker, setSelectedTicker] = useState(null);

    // Load universe on mount
    useEffect(() => {
        fetchUniverse()
            .then(setUniverse)
            .catch(e => console.error('Failed to load universe:', e))
            .finally(() => setUniverseLoading(false));
    }, []);

    // Update shock when driver selected
    const updateShock = useCallback((driver, value) => {
        setShocks(prev => ({ ...prev, [driver]: value }));
    }, []);

    // Apply
    const handleApply = useCallback(async () => {
        if (selectedTickers.length === 0) {
            setError({ message: 'Select at least one ticker' });
            return;
        }
        if (selectedDrivers.length === 0) {
            setError({ message: 'Select at least one driver' });
            return;
        }

        setLoading(true);
        setError(null);

        try {
            // Only include shocks for selected drivers
            const activeShocks = {};
            selectedDrivers.forEach(d => {
                activeShocks[d] = shocks[d] || 0;
            });

            const data = await postMacroShock({
                tickers: selectedTickers,
                drivers: selectedDrivers,
                lookback,
                returns_type: 'log',
                shock_mode: shockMode,
                shocks: activeShocks,
                model: { type: 'multivariate_ols', winsor_p: 0.01, ridge: 1e-6 }
            });

            setResults(data);

            // Auto-select first ticker in rankings
            if (data.rankings?.top_negative?.[0]) {
                setSelectedTicker(data.rankings.top_negative[0].ticker);
            } else if (data.rankings?.top_positive?.[0]) {
                setSelectedTicker(data.rankings.top_positive[0].ticker);
            }
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
        }
    }, [selectedTickers, selectedDrivers, lookback, shockMode, shocks]);

    // Impact table data
    const impactData = useMemo(() => {
        if (!results?.impacts) return [];

        return Object.entries(results.impacts)
            .map(([ticker, data]) => ({
                ticker,
                total: data.total,
                r2: data.fit?.r2,
                n: data.fit?.n,
                ...data.components
            }))
            .sort((a, b) => (a.total ?? 0) - (b.total ?? 0));
    }, [results]);

    // Contribution chart data for selected ticker
    const contributionData = useMemo(() => {
        if (!selectedTicker || !results?.impacts?.[selectedTicker]) return [];

        const components = results.impacts[selectedTicker].components || {};
        return Object.entries(components)
            .map(([driver, value]) => ({ driver, value: value || 0 }))
            .sort((a, b) => a.value - b.value);
    }, [selectedTicker, results]);

    // Export data
    const exportData = useMemo(() => {
        return impactData.map(row => ({
            ...row,
            shock_mode: shockMode,
            lookback
        }));
    }, [impactData, shockMode, lookback]);

    const formatPct = (val) => {
        if (val === undefined || val === null) return '-';
        return (val * 100).toFixed(2) + '%';
    };

    return (
        <div className="macro-page">
            <style jsx>{`
                .macro-page {
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
                    font-family: var(--font-sans);
                    opacity: 0.8;
                }
                .main-layout {
                    display: grid;
                    grid-template-columns: 240px 1fr 340px;
                    grid-template-rows: minmax(0, 1fr);
                    gap: ${researchTokens.spacing.lg}px;
                    flex-grow: 1;
                    min-height: 0;
                }
                .panel {
                   background: ${researchTokens.colors.surface};
                   border: 1px solid ${researchTokens.colors.border};
                   border-radius: ${researchTokens.radius.panel}px;
                   display: flex;
                   flex-direction: column;
                   overflow: hidden;
                }
                .panel-header {
                    padding: 12px 16px;
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    background: ${researchTokens.colors.surface};
                    flex-shrink: 0;
                }
                .panel-title {
                    font-size: 13px;
                    font-weight: 700;
                    color: ${researchTokens.colors.text};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                }
                .panel-content {
                    flex-grow: 1;
                    padding: 16px;
                    overflow: auto;
                }
                .table-container {
                     flex-grow: 1;
                     overflow: auto;
                }
                .impact-table {
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    font-size: 12px;
                    font-family: var(--font-mono);
                }
                .impact-table th {
                    text-align: right;
                    padding: 8px 12px;
                    color: ${researchTokens.colors.muted};
                    background: ${researchTokens.colors.surface};
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    font-weight: 600;
                    text-transform: uppercase;
                    position: sticky;
                    top: 0;
                    z-index: 10;
                }
                .impact-table th:first-child {
                    text-align: left;
                    padding-left: 16px;
                }
                .impact-table td {
                    padding: 8px 12px;
                    color: ${researchTokens.colors.text};
                    border-bottom: 1px solid ${researchTokens.colors.border2};
                    text-align: right;
                    cursor: pointer;
                    transition: all 0.1s;
                }
                .impact-table td:first-child {
                    text-align: left;
                    font-weight: 600;
                    padding-left: 16px;
                }
                .impact-table tr:hover td {
                    background: ${researchTokens.colors.surface2};
                }
                .impact-table tr.selected td {
                    background: rgba(251, 191, 36, 0.1);
                    border-bottom: 1px solid ${researchTokens.colors.warn};
                }
                .impact-table tr.selected td:first-child {
                    color: ${researchTokens.colors.warn};
                    border-left: 3px solid ${researchTokens.colors.warn};
                }
                .impact-positive { color: ${researchTokens.colors.good}; }
                .impact-negative { color: ${researchTokens.colors.bad}; }
                
                .detail-stat {
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid ${researchTokens.colors.border2};
                    font-size: 12px;
                    font-family: var(--font-mono);
                }
                .detail-stat-label { color: ${researchTokens.colors.muted}; }
                .detail-stat-value { font-weight: 600; color: ${researchTokens.colors.text}; }
                
                .ranking-section {
                    margin-top: 24px;
                }
                .ranking-title {
                    font-size: 11px;
                    font-weight: 700;
                    color: ${researchTokens.colors.muted};
                    margin-bottom: 12px;
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                .ranking-item {
                    display: flex;
                    justify-content: space-between;
                    padding: 6px 8px;
                    margin-bottom: 4px;
                    font-size: 12px;
                    font-family: var(--font-mono);
                    background: ${researchTokens.colors.surface2};
                    border-radius: 4px;
                    cursor: pointer;
                    transition: all 0.1s;
                }
                .ranking-item:hover {
                    background: rgba(255, 255, 255, 0.1);
                }
                
                .empty-state {
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    opacity: 0.6;
                    padding: 40px;
                    text-align: center;
                }
                .empty-icon {
                    font-size: 32px;
                    margin-bottom: 16px;
                    color: ${researchTokens.colors.border2};
                }
            `}</style>

            <Link href="/labs/research" className="back-link">
                ← Back
            </Link>

            <div className="page-header">
                <h1 className="page-title"><span style={{ fontSize: 24 }}>⚡</span> Macro Shock</h1>
                <p className="page-subtitle">
                    Estimate expected return impact from standardized macro driver shocks.
                </p>
            </div>

            <div className="main-layout">
                {/* 1. Control Panel */}
                <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <ControlPanel title="Configuration" onApply={handleApply} loading={loading}>
                        <ControlGroup label="Tickers">
                            <UniversePicker
                                selected={selectedTickers}
                                onChange={setSelectedTickers}
                                universe={universe}
                                loading={universeLoading}
                            />
                        </ControlGroup>

                        <ControlGroup label="Drivers">
                            <ControlSelect
                                value={selectedDrivers}
                                onChange={setSelectedDrivers}
                                options={DRIVERS}
                                multiple
                                size={4}
                            />
                        </ControlGroup>

                        <ControlGroup label="Shock Mode">
                            <ControlSelect
                                value={shockMode}
                                onChange={setShockMode}
                                options={[
                                    { value: 'sigma', label: 'Sigma (Standard Deviation)' },
                                    { value: 'raw', label: 'Raw Units (Basis Points)' }
                                ]}
                            />
                        </ControlGroup>

                        <div style={{ marginTop: 8 }}>
                            {selectedDrivers.map(driver => (
                                <ControlSlider
                                    key={driver}
                                    label={`${driver} Shock`}
                                    value={shocks[driver] || 0}
                                    onChange={(v) => updateShock(driver, v)}
                                    min={-3}
                                    max={3}
                                    step={0.1}
                                />
                            ))}
                        </div>

                        <ControlGroup label="Lookback">
                            <ControlSelect
                                value={lookback}
                                onChange={v => setLookback(Number(v))}
                                options={LOOKBACKS}
                            />
                        </ControlGroup>
                    </ControlPanel>
                </div>

                {/* 2. Impact Table (Center) */}
                <div className="panel">
                    <div className="panel-header">
                        <div className="panel-title">Impact Analysis</div>
                        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                            <StatusMeta meta={results?.meta} loading={loading} error={error} />
                            <ExportButtons data={exportData} meta={results?.meta} filename="macro_shock" disabled={!results} />
                        </div>
                    </div>

                    <div className="table-container">
                        {!results && !loading ? (
                            <div className="empty-state">
                                <div className="empty-icon">⚡</div>
                                <div>Choose drivers and set shock magnitudes to see impacts.</div>
                            </div>
                        ) : (
                            <table className="impact-table">
                                <thead>
                                    <tr>
                                        <th>Ticker</th>
                                        <th>Total Impact</th>
                                        <th>R²</th>
                                        {selectedDrivers.map(d => <th key={d}>{d}</th>)}
                                    </tr>
                                </thead>
                                <tbody>
                                    {impactData.map(row => (
                                        <tr
                                            key={row.ticker}
                                            className={selectedTicker === row.ticker ? 'selected' : ''}
                                            onClick={() => setSelectedTicker(row.ticker)}
                                        >
                                            <td>{row.ticker}</td>
                                            <td className={row.total >= 0 ? 'impact-positive' : 'impact-negative'}>
                                                {formatPct(row.total)}
                                            </td>
                                            <td style={{ color: researchTokens.colors.muted }}>
                                                {row.r2?.toFixed(2) ?? '-'}
                                            </td>
                                            {selectedDrivers.map(d => (
                                                <td key={d} className={row[d] >= 0 ? 'impact-positive' : 'impact-negative'}>
                                                    {formatPct(row[d])}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>

                {/* 3. Breakdown Panel (Right) */}
                <div className="panel">
                    <div className="panel-header">
                        <div className="panel-title">
                            {selectedTicker ? `${selectedTicker} Details` : 'Breakdown'}
                        </div>
                    </div>

                    <div className="panel-content">
                        {selectedTicker && results?.impacts?.[selectedTicker] ? (
                            <>
                                <div className="detail-stat">
                                    <span className="detail-stat-label">Total Impact</span>
                                    <span className="detail-stat-value" style={{
                                        color: results.impacts[selectedTicker].total >= 0 ? researchTokens.colors.good : researchTokens.colors.bad,
                                        fontSize: 14
                                    }}>
                                        {formatPct(results.impacts[selectedTicker].total)}
                                    </span>
                                </div>
                                <div className="detail-stat">
                                    <span className="detail-stat-label">Model Fit (R²)</span>
                                    <span className="detail-stat-value">
                                        {results.impacts[selectedTicker].fit?.r2?.toFixed(4) ?? 'N/A'}
                                    </span>
                                </div>
                                <div className="detail-stat">
                                    <span className="detail-stat-label">Data Points</span>
                                    <span className="detail-stat-value">
                                        {results.impacts[selectedTicker].fit?.n ?? 'N/A'}
                                    </span>
                                </div>

                                <div style={{ height: 220, marginTop: 24, marginBottom: 24 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={contributionData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={researchTokens.colors.border2} horizontal={false} />
                                            <XAxis type="number" tick={{ fill: researchTokens.colors.muted, fontSize: 10 }} tickFormatter={v => (v * 100).toFixed(1)} />
                                            <YAxis type="category" dataKey="driver" tick={{ fill: researchTokens.colors.muted, fontSize: 10, fontFamily: 'monospace' }} width={60} />
                                            <Tooltip
                                                cursor={{ fill: 'transparent' }}
                                                contentStyle={{
                                                    background: researchTokens.colors.surface2,
                                                    border: `1px solid ${researchTokens.colors.border}`,
                                                    borderRadius: 4,
                                                    fontSize: 12
                                                }}
                                                formatter={(v) => [(v * 100).toFixed(3) + '%', 'Impact']}
                                            />
                                            <ReferenceLine x={0} stroke={researchTokens.colors.muted2} />
                                            <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                                                {contributionData.map((entry, index) => (
                                                    <Cell key={index} fill={entry.value >= 0 ? researchTokens.colors.good : researchTokens.colors.bad} fillOpacity={0.8} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </>
                        ) : (
                            <div className="empty-state" style={{ height: '200px', border: 'none' }}>
                                <div>Select a ticker from the table to see breakdown.</div>
                            </div>
                        )}

                        {/* Global Rankings */}
                        {results?.rankings && (
                            <>
                                <div className="ranking-section">
                                    <div className="ranking-title" style={{ color: researchTokens.colors.good }}>Top Beneficiaries</div>
                                    {results.rankings.top_positive?.slice(0, 5).map(({ ticker, impact }) => (
                                        <div key={ticker} className="ranking-item" onClick={() => setSelectedTicker(ticker)}>
                                            <span>{ticker}</span>
                                            <span style={{ color: researchTokens.colors.good }}>{formatPct(impact)}</span>
                                        </div>
                                    ))}
                                </div>
                                <div className="ranking-section">
                                    <div className="ranking-title" style={{ color: researchTokens.colors.bad }}>Top Detractors</div>
                                    {results.rankings.top_negative?.slice(0, 5).map(({ ticker, impact }) => (
                                        <div key={ticker} className="ranking-item" onClick={() => setSelectedTicker(ticker)}>
                                            <span>{ticker}</span>
                                            <span style={{ color: researchTokens.colors.bad }}>{formatPct(impact)}</span>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
