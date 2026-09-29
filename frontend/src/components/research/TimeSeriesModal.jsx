"use client";

import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts';
import { researchTokens } from '@/lib/theme/researchTokens';

/**
 * TimeSeriesModal - Modal for displaying drilldown time series charts.
 * Upgraded for Cluster D Premium Terminal.
 */
export default function TimeSeriesModal({
    isOpen,
    onClose,
    title = '',
    subtitle = '',
    data = [],         // [{ date, value, ... }]
    valueKey = 'value',
    dateKey = 'date',
    yLabel = 'Value',
    color = researchTokens.accent.beta,
    showZeroLine = true,
    stats = {},        // { r2, n, ... }
    onExport
}) {
    if (!isOpen) return null;

    const handleExport = () => {
        if (onExport) {
            onExport(data);
        } else {
            // Default JSON export
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${title.replace(/\s+/g, '_')}.json`;
            a.click();
            URL.revokeObjectURL(url);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <style jsx>{`
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.75);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                    backdrop-filter: blur(4px);
                }
                .modal-content {
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: ${researchTokens.radius.card}px;
                    padding: 24px;
                    width: 70vw;
                    height: 80vh;
                    max-width: 1000px;
                    display: flex;
                    flex-direction: column;
                    box-shadow: ${researchTokens.shadow.card};
                }
                .modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 20px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid ${researchTokens.colors.border};
                }
                .modal-title {
                    font-size: ${researchTokens.typography.h2}px;
                    font-weight: 700;
                    color: ${researchTokens.colors.text};
                    font-family: var(--font-mono);
                }
                .modal-subtitle {
                    font-size: ${researchTokens.typography.body}px;
                    color: ${researchTokens.colors.muted};
                    margin-top: 4px;
                }
                .modal-close {
                    background: none;
                    border: none;
                    color: ${researchTokens.colors.muted};
                    font-size: 24px;
                    cursor: pointer;
                    padding: 0;
                    line-height: 1;
                    transition: color 0.1s;
                }
                .modal-close:hover {
                    color: ${researchTokens.colors.warn};
                }
                .modal-chart {
                    flex-grow: 1;
                    min-height: 300px;
                    margin-bottom: 20px;
                }
                .modal-stats {
                    display: flex;
                    gap: ${researchTokens.spacing.xl}px;
                    padding: 16px;
                    background: ${researchTokens.colors.surface2};
                    border-radius: ${researchTokens.radius.panel}px;
                    border: 1px solid ${researchTokens.colors.border};
                }
                .stat-item {
                    display: flex;
                    flex-direction: column;
                }
                .stat-label {
                    font-size: 10px;
                    color: ${researchTokens.colors.muted};
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    font-weight: 600;
                    font-family: var(--font-mono);
                }
                .stat-value {
                    font-size: 18px;
                    font-weight: 600;
                    color: ${researchTokens.colors.text};
                    margin-top: 4px;
                    font-family: var(--font-mono);
                }
                .modal-footer {
                    display: flex;
                    justify-content: flex-end;
                    gap: 12px;
                    margin-top: 20px;
                }
                .modal-btn {
                    background: transparent;
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: 4px;
                    padding: 8px 16px;
                    color: ${researchTokens.colors.text};
                    font-size: 12px;
                    cursor: pointer;
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    transition: all 0.2s;
                }
                .modal-btn:hover {
                    border-color: ${researchTokens.colors.warn};
                    color: ${researchTokens.colors.warn};
                }
            `}</style>

            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <div>
                        <div className="modal-title">{title}</div>
                        {subtitle && <div className="modal-subtitle">{subtitle}</div>}
                    </div>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>

                <div className="modal-chart">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke={researchTokens.colors.border2} vertical={false} />
                            <XAxis
                                dataKey={dateKey}
                                tick={{ fill: researchTokens.colors.muted, fontSize: 10, fontFamily: 'monospace' }}
                                tickLine={{ stroke: researchTokens.colors.border }}
                                axisLine={{ stroke: researchTokens.colors.border }}
                                minTickGap={30}
                                tickFormatter={(value) => {
                                    if (!value) return '';
                                    const d = new Date(value);
                                    return `${d.getMonth() + 1}/${d.getDate()}`;
                                }}
                            />
                            <YAxis
                                tick={{ fill: researchTokens.colors.muted, fontSize: 10, fontFamily: 'monospace' }}
                                tickLine={{ stroke: researchTokens.colors.border }}
                                axisLine={{ stroke: researchTokens.colors.border }}
                                domain={['auto', 'auto']}
                                label={{
                                    value: yLabel,
                                    angle: -90,
                                    position: 'insideLeft',
                                    style: { fill: researchTokens.colors.muted, fontSize: 11 }
                                }}
                            />
                            <Tooltip
                                contentStyle={{
                                    background: researchTokens.colors.surface2,
                                    border: `1px solid ${researchTokens.colors.border}`,
                                    borderRadius: 8,
                                    fontSize: 12,
                                    color: researchTokens.colors.text
                                }}
                                labelStyle={{ color: researchTokens.colors.muted, marginBottom: 8 }}
                                itemStyle={{ color: color }}
                                formatter={(value) => [typeof value === 'number' ? value.toFixed(4) : value, yLabel]}
                            />
                            {showZeroLine && (
                                <ReferenceLine y={0} stroke={researchTokens.colors.muted2} strokeDasharray="3 3" />
                            )}
                            <Line
                                type="monotone"
                                dataKey={valueKey}
                                stroke={color}
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 5, fill: color, stroke: researchTokens.colors.surface, strokeWidth: 2 }}
                                animationDuration={500}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {Object.keys(stats).length > 0 && (
                    <div className="modal-stats">
                        {stats.r2 !== undefined && (
                            <div className="stat-item">
                                <span className="stat-label">Model Fit (R²)</span>
                                <span className="stat-value">{stats.r2?.toFixed(3) ?? 'N/A'}</span>
                            </div>
                        )}
                        {stats.n !== undefined && (
                            <div className="stat-item">
                                <span className="stat-label">Observations</span>
                                <span className="stat-value">{stats.n}</span>
                            </div>
                        )}
                        {stats.window !== undefined && (
                            <div className="stat-item">
                                <span className="stat-label">Window</span>
                                <span className="stat-value">{stats.window}D</span>
                            </div>
                        )}
                    </div>
                )}

                <div className="modal-footer">
                    <button className="modal-btn" onClick={handleExport}>
                        Export JSON
                    </button>
                    <button className="modal-btn" onClick={onClose}>
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
}
