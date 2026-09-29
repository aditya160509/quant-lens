"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { postRollingBeta, postRollingBetaDetail } from '@/lib/api/research';
import { researchTokens } from '@/lib/theme/researchTokens';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import SelectedPills from '@/components/symbols/SelectedPills';
import HeatmapMatrix from '@/components/research/HeatmapMatrix';
import TimeSeriesModal from '@/components/research/TimeSeriesModal';
import ExportButtons from '@/components/research/ExportButtons';
import StatusMeta from '@/components/research/StatusMeta';
import ControlPanel, { ControlGroup, ControlSelect } from '@/components/research/ControlPanel';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts';
import { LIMITS } from '@/lib/universe/loadUniverse';

const FACTORS = ['MKT', 'SMB', 'HML', 'MOMENTUM', 'QUAL', 'VOL'];
const WINDOWS = [20, 60, 120, 252];
const LOOKBACK_OPTIONS = [
    { value: 252, label: '1 Year' },
    { value: 504, label: '2 Years' },
    { value: 756, label: '3 Years' },
];

export default function RollingBetaPage() {
    // Controls
    const [selectedTickers, setSelectedTickers] = useState(['AAPL', 'MSFT', 'NVDA', 'AMD', 'GOOGL', 'AMZN']);
    const [selectedFactors, setSelectedFactors] = useState(['MKT', 'SMB', 'HML', 'MOMENTUM']);
    const [selectedWindows, setSelectedWindows] = useState([20, 60]);
    const [lookback, setLookback] = useState(252);
    const [returnsType, setReturnsType] = useState('log');

    // Results
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Detail modal
    const [selectedCell, setSelectedCell] = useState(null);
    const [detailData, setDetailData] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);

    // Active window for display
    const [activeWindow, setActiveWindow] = useState(20);

    // Symbol handlers
    const handleAddSymbol = useCallback((symbol) => {
        if (selectedTickers.length >= LIMITS.beta_max) {
            alert(`Maximum ${LIMITS.beta_max} symbols allowed for Beta analysis`);
            return;
        }
        if (!selectedTickers.includes(symbol)) {
            setSelectedTickers(prev => [...prev, symbol]);
        }
    }, [selectedTickers]);

    const handleRemoveSymbol = useCallback((symbol) => {
        setSelectedTickers(prev => prev.filter(s => s !== symbol));
    }, []);

    const handleClearAll = useCallback(() => {
        setSelectedTickers([]);
    }, []);

    // Fetch Beta Matrix
    const handleApply = useCallback(async () => {
        if (selectedTickers.length === 0) {
            setError({ message: 'Select at least one ticker' });
            return;
        }

        setLoading(true);
        setError(null);
        setResults(null);

        try {
            // Ensure API aligns with these params
            const data = await postRollingBeta({
                tickers: selectedTickers,
                factors: selectedFactors,
                windows: selectedWindows,
                lookback,
                returns_type: returnsType,
                regression: { mode: 'single_factor', winsor_p: 0.01 }, // Backend performs single factor regression iteratively
                include_series: false
            });

            setResults(data);
            if (selectedWindows.length > 0) {
                setActiveWindow(selectedWindows[0]);
            }
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
        }
    }, [selectedTickers, selectedFactors, selectedWindows, lookback, returnsType]);

    // Handle Drilldown
    const handleCellClick = useCallback(async ({ row, col, value }) => {
        if (value === null || value === undefined) return;

        setSelectedCell({ row, col, value });
        setDetailLoading(true);
        setDetailData(null);

        try {
            const data = await postRollingBetaDetail({
                ticker: row,
                factor: col,
                window: activeWindow,
                lookback: lookback
            });
            setDetailData(data);
        } catch (e) {
            console.error('Detail fetch failed:', e);
        } finally {
            setDetailLoading(false);
        }
    }, [activeWindow, lookback]);

    // Prepare Matrix Data
    const matrixData = useMemo(() => {
        if (!results?.matrix) return {};
        const data = {};
        const windowKey = String(activeWindow);

        Object.entries(results.matrix).forEach(([ticker, factors]) => {
            data[ticker] = {};
            Object.entries(factors).forEach(([factor, windows]) => {
                data[ticker][factor] = windows[windowKey] ?? null;
            });
        });
        return data;
    }, [results, activeWindow]);

    // Prepare Overview Data (Average Beta per Factor)
    const overviewData = useMemo(() => {
        if (!results?.matrix) return [];
        const factorSums = {};
        const factorCounts = {};

        Object.values(results.matrix).forEach(factors => {
            Object.entries(factors).forEach(([factor, windows]) => {
                const val = windows[String(activeWindow)];
                if (val !== null && val !== undefined) {
                    factorSums[factor] = (factorSums[factor] || 0) + val;
                    factorCounts[factor] = (factorCounts[factor] || 0) + 1;
                }
            });
        });

        return Object.keys(factorSums).map(f => ({
            factor: f,
            avgBeta: factorSums[f] / factorCounts[f]
        }));
    }, [results, activeWindow]);

    // Export Flattening
    const exportData = useMemo(() => {
        if (!results?.matrix) return [];
        const rows = [];
        Object.entries(results.matrix).forEach(([ticker, factors]) => {
            Object.entries(factors).forEach(([factor, windows]) => {
                Object.entries(windows).forEach(([window, beta]) => {
                    rows.push({
                        ticker,
                        factor,
                        window: parseInt(window),
                        beta
                    });
                });
            });
        });
        return rows;
    }, [results]);

    return (
        <div className="beta-page">
            <style jsx>{`
                .beta-page {
                    height: calc(100vh - 80px);
                    width: 100%;
                    display: flex;
                    overflow: hidden;
                    background: ${researchTokens.colors.bg};
                    padding-bottom: ${researchTokens.spacing.lg}px;
                }
                .main-layout {
                    flex-grow: 1;
                    display: flex;
                    flex-direction: column;
                    padding: ${researchTokens.spacing.lg}px;
                    gap: ${researchTokens.spacing.lg}px;
                    overflow: hidden;
                    min-width: 0;
                }
                .content-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding-bottom: ${researchTokens.spacing.md}px;
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    flex-shrink: 0;
                }
                .header-left {
                    display: flex;
                    align-items: center;
                    gap: ${researchTokens.spacing.lg}px;
                }
                .page-title {
                    font-size: ${researchTokens.typography.h2}px;
                    font-weight: 700;
                    color: ${researchTokens.colors.text};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                .window-tabs {
                    display: flex;
                    gap: 8px;
                    background: ${researchTokens.colors.surface};
                    padding: 4px;
                    border-radius: 6px;
                    border: 1px solid ${researchTokens.colors.border};
                }
                .window-tab {
                    background: transparent;
                    border: none;
                    padding: 4px 12px;
                    color: ${researchTokens.colors.muted};
                    font-size: 11px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    transition: all 0.2s;
                    border-radius: 4px;
                    font-weight: 600;
                }
                .window-tab:hover {
                    color: ${researchTokens.colors.text};
                }
                .window-tab.active {
                    background: ${researchTokens.colors.surface2};
                    color: ${researchTokens.colors.warn};
                    box-shadow: ${researchTokens.shadow.sm};
                }
                .viz-container {
                    flex-grow: 1;
                    display: flex;
                    flex-direction: column;
                    gap: ${researchTokens.spacing.md}px;
                    overflow: hidden;
                    min-height: 0;
                }
                .heatmap-wrapper {
                    flex-grow: 2;
                    min-height: 0;
                    border-radius: ${researchTokens.radius.panel}px;
                    overflow: hidden;
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                }
                .overview-wrapper {
                    flex-grow: 1;
                    min-height: 180px;
                    max-height: 250px;
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: ${researchTokens.radius.panel}px;
                    padding: 16px;
                    display: flex;
                    flex-direction: column;
                    flex-shrink: 0;
                }
                .section-title {
                    font-size: 11px;
                    font-weight: 700;
                    color: ${researchTokens.colors.muted};
                    text-transform: uppercase;
                    margin-bottom: 12px;
                    font-family: var(--font-mono);
                    display: flex;
                    justify-content: space-between;
                }
                .empty-state {
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    opacity: 0.5;
                }
                .empty-icon {
                    font-size: 48px;
                    margin-bottom: 16px;
                    color: ${researchTokens.colors.border2};
                }
            `}</style>

            <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <ControlPanel
                    title="Rolling Beta"
                    onApply={handleApply}
                    loading={loading}
                    description="Multivariate rolling regression of assets against selected factors."
                >
                    <ControlGroup label="Universe">
                        <TradingViewSearch
                            mode="security"
                            onSelect={handleAddSymbol}
                            placeholder="Search equities..."
                        />
                        <div style={{ marginTop: 8 }}>
                            <SelectedPills
                                symbols={selectedTickers}
                                onRemove={handleRemoveSymbol}
                                onClearAll={handleClearAll}
                                maxDisplay={6}
                            />
                        </div>
                        {selectedTickers.length === 0 && (
                            <div style={{ fontSize: 11, color: researchTokens.colors.muted, marginTop: 4 }}>
                                Search and select equities above
                            </div>
                        )}
                    </ControlGroup>

                    <ControlGroup label="Factors">
                        <ControlSelect
                            value={selectedFactors}
                            onChange={setSelectedFactors}
                            options={FACTORS}
                            multiple
                            size={6}
                        />
                    </ControlGroup>

                    <ControlGroup label="Windows">
                        <ControlSelect
                            value={selectedWindows}
                            onChange={v => setSelectedWindows(v.map(Number))}
                            options={WINDOWS.map(w => ({ value: w, label: `${w} Days` }))}
                            multiple
                            size={4}
                        />
                    </ControlGroup>

                    <ControlGroup label="Parameters">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            <ControlSelect
                                value={lookback}
                                onChange={v => setLookback(Number(v))}
                                options={LOOKBACK_OPTIONS}
                                label="Lookback"
                            />
                            <ControlSelect
                                value={returnsType}
                                onChange={setReturnsType}
                                options={[
                                    { value: 'log', label: 'Log Returns' },
                                    { value: 'simple', label: 'Simple Returns' }
                                ]}
                                label="Calc"
                            />
                        </div>
                    </ControlGroup>
                </ControlPanel>
            </div>

            <div className="main-layout">
                <div className="content-header">
                    <div className="header-left">
                        <div className="page-title">
                            <span style={{ fontSize: 20 }}>📊</span> Beta Analysis
                        </div>
                        {selectedWindows.length > 0 && (
                            <div className="window-tabs">
                                {selectedWindows.map(w => (
                                    <button
                                        key={w}
                                        className={`window-tab ${activeWindow === w ? 'active' : ''}`}
                                        onClick={() => setActiveWindow(w)}
                                    >
                                        {w}D
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                        <StatusMeta meta={results?.meta} loading={loading} error={error} />
                        <ExportButtons
                            data={exportData}
                            filename={`rolling_beta_${activeWindow}d`}
                            disabled={!results}
                        />
                    </div>
                </div>

                <div className="viz-container">
                    {!results && !loading ? (
                        <div className="empty-state">
                            <div className="empty-icon">←</div>
                            <div>Configure parameters and apply to generate matrix</div>
                        </div>
                    ) : (
                        <>
                            <div className="heatmap-wrapper">
                                <HeatmapMatrix
                                    data={matrixData}
                                    rows={Object.keys(results?.matrix || {}).sort()}
                                    cols={selectedFactors}
                                    colorScale="diverging"
                                    minValue={-1.5}
                                    maxValue={1.5}
                                    onCellClick={handleCellClick}
                                    selectedCell={selectedCell}
                                    title={`Rolling Request (${activeWindow}D Window)`}
                                />
                            </div>

                            <div className="overview-wrapper">
                                <div className="section-title">
                                    <span>Factor Exposure Overview (Avg)</span>
                                    <span>{activeWindow}D</span>
                                </div>
                                <div style={{ flex: 1, minHeight: 0, width: '100%' }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={overviewData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={researchTokens.colors.border2} horizontal={false} />
                                            <XAxis type="number" hide domain={[-1, 1]} />
                                            <YAxis
                                                dataKey="factor"
                                                type="category"
                                                width={80}
                                                tick={{ fill: researchTokens.colors.muted, fontSize: 10, fontFamily: 'monospace' }}
                                                axisLine={false}
                                                tickLine={false}
                                            />
                                            <Tooltip
                                                cursor={{ fill: 'transparent' }}
                                                contentStyle={{
                                                    background: researchTokens.colors.surface2,
                                                    borderColor: researchTokens.colors.border,
                                                    color: researchTokens.colors.text,
                                                    fontSize: 12
                                                }}
                                            />
                                            <Bar dataKey="avgBeta" barSize={16} radius={[0, 4, 4, 0]}>
                                                {overviewData.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.avgBeta > 0 ? researchTokens.colors.good : researchTokens.colors.bad} fillOpacity={0.7} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>

            <TimeSeriesModal
                isOpen={!!selectedCell}
                onClose={() => setSelectedCell(null)}
                title={`${selectedCell?.row} vs ${selectedCell?.col}`}
                subtitle={`${activeWindow}-day rolling beta`}
                data={detailData?.series || []}
                valueKey="beta"
                dateKey="date"
                yLabel="Beta"
                color={researchTokens.accent.beta}
                stats={{
                    r2: detailData?.series?.[detailData.series.length - 1]?.r2,
                    n: detailData?.meta?.data_points,
                    window: activeWindow
                }}
            />
        </div>
    );
}

