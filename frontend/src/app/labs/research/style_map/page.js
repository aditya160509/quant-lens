"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { postStyleMap } from '@/lib/api/research';
import { researchTokens } from '@/lib/theme/researchTokens';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import SelectedPills from '@/components/symbols/SelectedPills';
import ScatterCanvas from '@/components/research/ScatterCanvas';
import ExportButtons from '@/components/research/ExportButtons';
import StatusMeta from '@/components/research/StatusMeta';
import ControlPanel, { ControlGroup, ControlSelect } from '@/components/research/ControlPanel';
import { LIMITS } from '@/lib/universe/loadUniverse';

const FACTORS = ['MKT', 'SMB', 'HML', 'MOMENTUM', 'VOL', 'QUALITY', 'RATES', 'USD'];
const LOOKBACKS = [
    { value: 126, label: '6 Months' },
    { value: 252, label: '1 Year' },
    { value: 504, label: '2 Years' },
];

export default function StyleMapPage() {
    // Controls
    const [selectedTickers, setSelectedTickers] = useState(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'JPM', 'XOM', 'UNH', 'LLY', 'AVGO', 'V', 'HD']);
    const [xFactor, setXFactor] = useState('HML');
    const [yFactor, setYFactor] = useState('MOMENTUM');
    const [colorFactor, setColorFactor] = useState('MKT');
    const [sizeFactor, setSizeFactor] = useState('VOL');
    const [lookback, setLookback] = useState(252);
    const [showLabels, setShowLabels] = useState(true);

    // Results
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Selection
    const [selectedTicker, setSelectedTicker] = useState(null);

    // Symbol handlers
    const handleAddSymbol = useCallback((symbol) => {
        if (selectedTickers.length >= 50) {
            alert('Maximum 50 symbols allowed for Style Map');
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

    // Apply
    const handleApply = useCallback(async () => {
        if (selectedTickers.length === 0) {
            setError({ message: 'Select at least one ticker' });
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const data = await postStyleMap({
                tickers: selectedTickers,
                lookback,
                x: xFactor,
                y: yFactor,
                color: colorFactor,
                size: sizeFactor,
                standardize: 'cross_sectional_z',
                winsor_p: 0.01
            });

            setResults(data);
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
        }
    }, [selectedTickers, lookback, xFactor, yFactor, colorFactor, sizeFactor]);

    // Points for scatter
    const points = useMemo(() => {
        if (!results?.points) return [];
        return results.points.filter(p => p.x !== null && p.y !== null);
    }, [results]);

    // Selected point data
    const selectedData = useMemo(() => {
        if (!selectedTicker || !results?.points) return null;
        return results.points.find(p => p.ticker === selectedTicker);
    }, [selectedTicker, results]);

    // Export data
    const exportData = useMemo(() => {
        if (!results?.points) return [];
        return results.points.map(p => ({
            ticker: p.ticker,
            [`${xFactor}_x`]: p.x,
            [`${yFactor}_y`]: p.y,
            [`${colorFactor}_color`]: p.color,
            [`${sizeFactor}_size`]: p.size
        }));
    }, [results, xFactor, yFactor, colorFactor, sizeFactor]);

    return (
        <div className="style-page">
            <style jsx>{`
                .style-page {
                    height: calc(100vh - 80px); /* Adjust for global nav */
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
                    grid-template-columns: 240px 1fr 280px;
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
                .panel-title {
                    font-size: 13px;
                    font-weight: 700;
                    color: ${researchTokens.colors.text};
                    font-family: var(--font-mono);
                    padding: 12px 16px;
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    text-transform: uppercase;
                    background: ${researchTokens.colors.surface};
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
                .toggle-btn {
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    padding: 4px 12px;
                    color: ${researchTokens.colors.muted};
                    font-size: 11px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    text-transform: uppercase;
                    transition: all 0.2s;
                    border-radius: 4px;
                }
                .toggle-btn.active, .toggle-btn:hover {
                    background: ${researchTokens.colors.surface2};
                    color: ${researchTokens.colors.text};
                    border-color: ${researchTokens.colors.text};
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
                }
                .detail-row {
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid ${researchTokens.colors.border2};
                    font-size: 12px;
                    font-family: var(--font-mono);
                }
                .detail-label {
                    color: ${researchTokens.colors.muted};
                }
                .detail-value {
                    font-weight: 600;
                    color: ${researchTokens.colors.text};
                }
                .list-container {
                     flex-grow: 1;
                     overflow-y: auto;
                     padding: 0;
                }
                .ticker-item {
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 16px;
                    border-bottom: 1px solid ${researchTokens.colors.border2};
                    cursor: pointer;
                    font-size: 12px;
                    font-family: var(--font-mono);
                    color: ${researchTokens.colors.text};
                    transition: background 0.1s;
                }
                .ticker-item:hover {
                    background: ${researchTokens.colors.surface2};
                }
                .ticker-item.selected {
                    background: rgba(251, 191, 36, 0.15);
                    color: ${researchTokens.colors.warn};
                    border-left: 2px solid ${researchTokens.colors.warn};
                }
            `}</style>

            <Link href="/labs/research" className="back-link">
                ← Back
            </Link>

            <div className="page-header">
                <h1 className="page-title"><span style={{ fontSize: 24 }}>🗺️</span> Style Map</h1>
                <p className="page-subtitle">
                    Visualize cross-sectional factor positioning on an interactive scatter plot.
                </p>
            </div>

            <div className="main-layout">
                {/* 1. Control Panel */}
                <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <ControlPanel
                        title="Configuration"
                        onApply={handleApply}
                        loading={loading}
                        description="Configure X, Y, Color, and Size dimensions."
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

                        <ControlGroup label="Dimensions">
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                <ControlSelect label="X-Axis" value={xFactor} onChange={setXFactor} options={FACTORS} />
                                <ControlSelect label="Y-Axis" value={yFactor} onChange={setYFactor} options={FACTORS} />
                                <ControlSelect label="Color" value={colorFactor} onChange={setColorFactor} options={FACTORS} />
                                <ControlSelect label="Size" value={sizeFactor} onChange={setSizeFactor} options={FACTORS} />
                            </div>
                        </ControlGroup>

                        <ControlGroup label="Lookback">
                            <ControlSelect
                                value={lookback}
                                onChange={v => setLookback(Number(v))}
                                options={LOOKBACKS}
                            />
                        </ControlGroup>
                    </ControlPanel>
                </div>

                {/* 2. Scatter Plot (Center) */}
                <div className="panel">
                    <div className="content-header">
                        <div className="panel-title" style={{ border: 'none', padding: 0, background: 'transparent' }}>
                            Visualization
                        </div>
                        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                            <button
                                className={`toggle-btn ${showLabels ? 'active' : ''}`}
                                onClick={() => setShowLabels(!showLabels)}
                            >
                                {showLabels ? 'Hide Labels' : 'Show Labels'}
                            </button>
                            <StatusMeta meta={results?.meta} loading={loading} error={error} />
                            <ExportButtons data={exportData} meta={results?.meta} filename="style_map" disabled={!results} />
                        </div>
                    </div>

                    <div style={{ flexGrow: 1, position: 'relative', overflow: 'hidden' }}>
                        {!results && !loading ? (
                            <div className="empty-state">
                                <span style={{ fontSize: 32, marginBottom: 16 }}>🗺️</span>
                                <div>Click Apply to generate the map</div>
                            </div>
                        ) : (
                            <ScatterCanvas
                                points={points}
                                xLabel={xFactor}
                                yLabel={yFactor}
                                colorLabel={colorFactor}
                                sizeLabel={sizeFactor}
                                // Responsive layout handles width/height via CSS usually, but canvas needs explicit size
                                // We can use a resize observer or just fixed percentage logic if wrapper is absolute
                                width={800}
                                height={600}
                                // Note: ScatterCanvas might need a resizer too, but overflow hidden prevents breaking layout
                                showLabels={showLabels}
                                onPointClick={(p) => setSelectedTicker(p.ticker)}
                                selectedTickers={selectedTicker ? [selectedTicker] : []}
                            />
                        )}
                    </div>
                </div>

                {/* 3. Detail Panel (Right) */}
                <div className="panel">
                    <div className="panel-title">
                        {selectedData ? `${selectedData.ticker} Stats` : 'Ticker List'}
                    </div>

                    {selectedData ? (
                        <div style={{ padding: 16, overflowY: 'auto' }}>
                            <div className="detail-row">
                                <span className="detail-label">{xFactor} (X)</span>
                                <span className="detail-value">{selectedData.x?.toFixed(2) ?? '-'}</span>
                            </div>
                            <div className="detail-row">
                                <span className="detail-label">{yFactor} (Y)</span>
                                <span className="detail-value">{selectedData.y?.toFixed(2) ?? '-'}</span>
                            </div>
                            <div className="detail-row">
                                <span className="detail-label">{colorFactor} (Color)</span>
                                <span className="detail-value">{selectedData.color?.toFixed(2) ?? '-'}</span>
                            </div>
                            <div className="detail-row">
                                <span className="detail-label">{sizeFactor} (Size)</span>
                                <span className="detail-value">{selectedData.size?.toFixed(2) ?? '-'}</span>
                            </div>

                            <button
                                className="toggle-btn"
                                style={{ marginTop: 24, width: '100%', textAlign: 'center' }}
                                onClick={() => setSelectedTicker(null)}
                            >
                                Clear Selection
                            </button>
                        </div>
                    ) : (
                        <div className="list-container">
                            {(results?.points || []).map(p => (
                                <div
                                    key={p.ticker}
                                    className={`ticker-item ${selectedTicker === p.ticker ? 'selected' : ''}`}
                                    onClick={() => setSelectedTicker(p.ticker)}
                                >
                                    <span>{p.ticker}</span>
                                    <span style={{ color: researchTokens.colors.muted }}>
                                        {p.x?.toFixed(1)}, {p.y?.toFixed(1)}
                                    </span>
                                </div>
                            ))}
                            {(!results?.points || results.points.length === 0) && (
                                <div style={{ padding: 16, textAlign: 'center', color: researchTokens.colors.muted, fontSize: 12 }}>
                                    No points to display
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div >
    );
}
