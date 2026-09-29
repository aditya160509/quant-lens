"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { postCorrelationMatrix, postCorrelationPair } from '@/lib/api/research';
import { researchTokens } from '@/lib/theme/researchTokens';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import SelectedPills from '@/components/symbols/SelectedPills';
import HeatmapMatrix from '@/components/research/HeatmapMatrix';
import TimeSeriesModal from '@/components/research/TimeSeriesModal';
import ExportButtons from '@/components/research/ExportButtons';
import StatusMeta from '@/components/research/StatusMeta';
import ControlPanel, { ControlGroup, ControlSelect } from '@/components/research/ControlPanel';
import { LIMITS } from '@/lib/universe/loadUniverse';

const WINDOWS = [
    { value: 20, label: '20 days' },
    { value: 30, label: '30 days' },
    { value: 60, label: '60 days' },
    { value: 90, label: '90 days' },
];
const LOOKBACKS = [
    { value: 252, label: '1 Year' },
    { value: 504, label: '2 Years' },
    { value: 756, label: '3 Years' },
];
const METHODS = [
    { value: 'pearson', label: 'Pearson' },
    { value: 'spearman', label: 'Spearman' },
];

export default function CorrelationPage() {
    // Controls
    const [selectedTickers, setSelectedTickers] = useState(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD']);
    const [selectedWindows, setSelectedWindows] = useState([30, 60]);
    const [lookback, setLookback] = useState(504);
    const [method, setMethod] = useState('pearson');
    const [viewMode, setViewMode] = useState('absolute');

    // Results
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Active window for display
    const [activeWindow, setActiveWindow] = useState(30);

    // Pair drilldown
    const [selectedPair, setSelectedPair] = useState(null);
    const [pairData, setPairData] = useState(null);
    const [pairLoading, setPairLoading] = useState(false);

    // Symbol handlers
    const handleAddSymbol = useCallback((symbol) => {
        if (selectedTickers.length >= LIMITS.correlation_max) {
            alert(`Maximum ${LIMITS.correlation_max} symbols allowed for Correlation`);
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

    // Ensure active window is valid
    useEffect(() => {
        if (!selectedWindows.includes(activeWindow) && selectedWindows.length > 0) {
            setActiveWindow(selectedWindows[0]);
        }
    }, [selectedWindows, activeWindow]);

    // Apply
    const handleApply = useCallback(async () => {
        if (selectedTickers.length < 2) {
            setError({ message: 'Select at least 2 tickers' });
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const data = await postCorrelationMatrix({
                tickers: selectedTickers,
                windows: selectedWindows,
                returns_type: 'log',
                method,
                lookback
            });

            setResults(data);
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
        }
    }, [selectedTickers, selectedWindows, lookback, method]);

    // Handle cell click for pair drilldown
    const handleCellClick = useCallback(async ({ row, col }) => {
        if (row === col) return; // Don't drill down on diagonal

        setSelectedPair({ a: row, b: col });
        setPairLoading(true);
        setPairData(null);

        try {
            const data = await postCorrelationPair({
                a: row,
                b: col,
                window: activeWindow,
                lookback
            });
            setPairData(data);
        } catch (e) {
            console.error('Pair fetch failed:', e);
        } finally {
            setPairLoading(false);
        }
    }, [activeWindow, lookback]);

    // Matrix data for current view
    const matrixData = useMemo(() => {
        if (!results) return {};

        if (viewMode === 'delta' && results.delta) {
            return results.delta;
        }

        const windowKey = String(activeWindow);
        return results.matrices?.[windowKey] || {};
    }, [results, activeWindow, viewMode]);

    // Use ordered tickers if available (clustering)
    const orderedTickers = useMemo(() => {
        if (!results) return [];
        return results.order || results.tickers || [];
    }, [results]);

    // Export data
    const exportData = useMemo(() => {
        if (!results?.matrices) return [];

        const rows = [];
        const windowKey = String(activeWindow);
        const matrix = results.matrices[windowKey] || {};

        Object.entries(matrix).forEach(([t1, cols]) => {
            Object.entries(cols).forEach(([t2, corr]) => {
                if (t1 <= t2) { // Avoid duplicates
                    rows.push({
                        ticker_a: t1,
                        ticker_b: t2,
                        correlation: corr,
                        window: activeWindow,
                        method
                    });
                }
            });
        });

        return rows;
    }, [results, activeWindow, method]);

    return (
        <div className="corr-page">
            <style jsx>{`
                .corr-page {
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
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: ${researchTokens.radius.panel}px;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    flex-shrink: 0;
                }
                .content-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 16px;
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    background: ${researchTokens.colors.surface};
                    flex-shrink: 0;
                }
                .tab-group {
                    display: flex;
                    gap: 4px;
                    background: ${researchTokens.colors.surface2};
                    padding: 2px;
                    border-radius: 4px;
                }
                .tab-btn {
                    background: transparent;
                    border: none;
                    padding: 4px 10px;
                    color: ${researchTokens.colors.muted};
                    font-size: 11px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    text-transform: uppercase;
                    border-radius: 3px;
                    transition: all 0.2s;
                    font-weight: 500;
                }
                .tab-btn:hover {
                    color: ${researchTokens.colors.text};
                }
                .tab-btn.active {
                    background: ${researchTokens.colors.surface};
                    color: ${researchTokens.colors.warn};
                    font-weight: 700;
                    box-shadow: ${researchTokens.shadow.sm};
                }
                .empty-state {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 80%;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    opacity: 0.7;
                }
            `}</style>

            <Link href="/labs/research" className="back-link">
                ← Back
            </Link>

            <div className="page-header">
                <h1 className="page-title"><span style={{ fontSize: 24 }}>🔗</span> Cross-Asset Correlation</h1>
                <p className="page-subtitle">
                    Analyze co-movements and hierarchical structures across assets.
                </p>
            </div>

            <div className="main-layout">
                {/* Control Panel */}
                <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <ControlPanel
                        title="Configuration"
                        onApply={handleApply}
                        loading={loading}
                        description="Configure correlation method and analysis windows."
                    >
                        <ControlGroup label="Tickers">
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
                        </ControlGroup>

                        <ControlGroup label="Windows (days)">
                            <ControlSelect
                                value={selectedWindows}
                                onChange={v => setSelectedWindows(v.map(Number))}
                                options={WINDOWS}
                                multiple
                                size={4}
                            />
                        </ControlGroup>

                        <ControlGroup label="Lookback">
                            <ControlSelect
                                value={lookback}
                                onChange={v => setLookback(Number(v))}
                                options={LOOKBACKS}
                            />
                        </ControlGroup>

                        <ControlGroup label="Method">
                            <ControlSelect
                                value={method}
                                onChange={setMethod}
                                options={METHODS}
                            />
                        </ControlGroup>
                    </ControlPanel>
                </div>

                {/* Matrix View */}
                <div className="main-content">
                    <div className="content-header">
                        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                            <div className="tab-group">
                                {selectedWindows.map(w => (
                                    <button
                                        key={w}
                                        className={`tab-btn ${activeWindow === w ? 'active' : ''}`}
                                        onClick={() => setActiveWindow(w)}
                                    >
                                        {w}D
                                    </button>
                                ))}
                            </div>

                            <div className="tab-group">
                                <button
                                    className={`tab-btn ${viewMode === 'absolute' ? 'active' : ''}`}
                                    onClick={() => setViewMode('absolute')}
                                >
                                    ABSOLUTE
                                </button>
                                <button
                                    className={`tab-btn ${viewMode === 'delta' ? 'active' : ''}`}
                                    onClick={() => setViewMode('delta')}
                                    disabled={!results?.delta}
                                    style={{ opacity: !results?.delta ? 0.5 : 1 }}
                                >
                                    DELTA Δ
                                </button>
                            </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <StatusMeta meta={results?.meta} loading={loading} error={error} />
                            <ExportButtons
                                data={exportData}
                                meta={results?.meta}
                                filename={`correlation_${activeWindow}d`}
                                disabled={!results}
                            />
                        </div>
                    </div>

                    {!results && !loading ? (
                        <div className="empty-state">
                            <span style={{ fontSize: 32, marginBottom: 16 }}>🔗</span>
                            <div>Select tickers and apply</div>
                        </div>
                    ) : (
                        <HeatmapMatrix
                            data={matrixData}
                            rows={orderedTickers}
                            cols={orderedTickers}
                            colorScale="diverging"
                            minValue={viewMode === 'delta' ? -0.5 : -1}
                            maxValue={viewMode === 'delta' ? 0.5 : 1}
                            onCellClick={handleCellClick}
                            selectedCell={selectedPair ? { row: selectedPair.a, col: selectedPair.b } : null}
                            cellSize={50}
                        />
                    )}
                </div>
            </div>

            {/* Pair Drilldown Modal */}
            <TimeSeriesModal
                isOpen={!!selectedPair}
                onClose={() => setSelectedPair(null)}
                title={`${selectedPair?.a} × ${selectedPair?.b}`}
                subtitle={`${activeWindow}-day rolling correlation`}
                data={pairData?.series || []}
                valueKey="corr"
                dateKey="date"
                yLabel="Correlation"
                color={researchTokens.colors.warn}
                showZeroLine={true}
                stats={{
                    'Window': `${activeWindow} days`,
                    'Data Points': pairData?.meta?.data_points
                }}
            />
        </div>
    );
}
