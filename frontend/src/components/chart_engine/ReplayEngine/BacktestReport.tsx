/**
 * Backtest Report
 * Comprehensive performance visualization for paper trading results
 */

'use client';

import React, { useMemo } from 'react';
import { CHART_THEME } from '../types';
import type { PaperTradingStats, PaperTrade, PaperTradingState } from './PaperTradingEngine';

// =============================================================================
// TYPES
// =============================================================================

interface BacktestReportProps {
    state: PaperTradingState;
    stats: PaperTradingStats;
    equityCurve: { timestamp: number; equity: number }[];
    isOpen: boolean;
    onClose: () => void;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function BacktestReport({
    state,
    stats,
    equityCurve,
    isOpen,
    onClose,
}: BacktestReportProps) {
    if (!isOpen) return null;

    const returnPercent = ((state.equity - state.initialCash) / state.initialCash) * 100;
    const isProfit = returnPercent >= 0;

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0, 0, 0, 0.8)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 10000,
            }}
            onClick={onClose}
        >
            <div
                style={{
                    width: '900px',
                    maxHeight: '90vh',
                    background: CHART_THEME.bgSecondary,
                    borderRadius: '12px',
                    border: `1px solid ${CHART_THEME.border}`,
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                }}
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div
                    style={{
                        padding: '20px 24px',
                        borderBottom: `1px solid ${CHART_THEME.border}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                    }}
                >
                    <div>
                        <h2 style={{
                            margin: 0,
                            fontSize: '20px',
                            fontWeight: 600,
                            color: CHART_THEME.textPrimary,
                        }}>
                            Backtest Report
                        </h2>
                        <div style={{
                            fontSize: '13px',
                            color: CHART_THEME.textSecondary,
                            marginTop: '4px',
                        }}>
                            {stats.totalTrades} trades · {formatDuration(getReportDuration(equityCurve))}
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            width: '32px',
                            height: '32px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: CHART_THEME.bgTertiary,
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            color: CHART_THEME.textSecondary,
                        }}
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
                    {/* Summary Cards */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(4, 1fr)',
                        gap: '16px',
                        marginBottom: '24px',
                    }}>
                        <SummaryCard
                            label="Net Profit"
                            value={`${isProfit ? '+' : ''}${returnPercent.toFixed(2)}%`}
                            subValue={`$${(state.equity - state.initialCash).toFixed(2)}`}
                            color={isProfit ? CHART_THEME.upColor : CHART_THEME.downColor}
                        />
                        <SummaryCard
                            label="Win Rate"
                            value={`${stats.winRate.toFixed(1)}%`}
                            subValue={`${stats.winningTrades}W / ${stats.losingTrades}L`}
                            color={stats.winRate >= 50 ? CHART_THEME.upColor : CHART_THEME.downColor}
                        />
                        <SummaryCard
                            label="Profit Factor"
                            value={stats.profitFactor === Infinity ? '∞' : stats.profitFactor.toFixed(2)}
                            subValue={stats.profitFactor >= 1.5 ? 'Good' : stats.profitFactor >= 1 ? 'Fair' : 'Poor'}
                            color={stats.profitFactor >= 1.5 ? CHART_THEME.upColor : 
                                   stats.profitFactor >= 1 ? CHART_THEME.accent : CHART_THEME.downColor}
                        />
                        <SummaryCard
                            label="Max Drawdown"
                            value={`-${stats.maxDrawdownPercent.toFixed(2)}%`}
                            subValue={`$${stats.maxDrawdown.toFixed(2)}`}
                            color={stats.maxDrawdownPercent > 20 ? CHART_THEME.downColor : CHART_THEME.textPrimary}
                        />
                    </div>

                    {/* Equity Curve */}
                    <div style={{
                        marginBottom: '24px',
                        padding: '16px',
                        background: CHART_THEME.bgTertiary,
                        borderRadius: '8px',
                    }}>
                        <h3 style={{
                            margin: '0 0 16px 0',
                            fontSize: '14px',
                            fontWeight: 600,
                            color: CHART_THEME.textPrimary,
                        }}>
                            Equity Curve
                        </h3>
                        <EquityCurveChart 
                            data={equityCurve} 
                            initialCash={state.initialCash}
                        />
                    </div>

                    {/* Detailed Stats */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(2, 1fr)',
                        gap: '24px',
                        marginBottom: '24px',
                    }}>
                        <div>
                            <h3 style={{
                                margin: '0 0 12px 0',
                                fontSize: '14px',
                                fontWeight: 600,
                                color: CHART_THEME.textPrimary,
                            }}>
                                Performance Metrics
                            </h3>
                            <div style={{
                                background: CHART_THEME.bgTertiary,
                                borderRadius: '8px',
                                padding: '12px',
                            }}>
                                <StatRow label="Total P&L" value={`$${stats.totalPnL.toFixed(2)}`} />
                                <StatRow label="Sharpe Ratio" value={stats.sharpeRatio.toFixed(2)} />
                                <StatRow label="Avg Win" value={`$${stats.avgWin.toFixed(2)}`} color={CHART_THEME.upColor} />
                                <StatRow label="Avg Loss" value={`-$${stats.avgLoss.toFixed(2)}`} color={CHART_THEME.downColor} />
                                <StatRow label="Largest Win" value={`$${stats.largestWin.toFixed(2)}`} color={CHART_THEME.upColor} />
                                <StatRow label="Largest Loss" value={`$${Math.abs(stats.largestLoss).toFixed(2)}`} color={CHART_THEME.downColor} />
                            </div>
                        </div>
                        <div>
                            <h3 style={{
                                margin: '0 0 12px 0',
                                fontSize: '14px',
                                fontWeight: 600,
                                color: CHART_THEME.textPrimary,
                            }}>
                                Trade Statistics
                            </h3>
                            <div style={{
                                background: CHART_THEME.bgTertiary,
                                borderRadius: '8px',
                                padding: '12px',
                            }}>
                                <StatRow label="Total Trades" value={stats.totalTrades.toString()} />
                                <StatRow label="Winning Trades" value={stats.winningTrades.toString()} color={CHART_THEME.upColor} />
                                <StatRow label="Losing Trades" value={stats.losingTrades.toString()} color={CHART_THEME.downColor} />
                                <StatRow label="Avg Holding Time" value={formatDuration(stats.avgHoldingPeriod)} />
                                <StatRow label="Final Equity" value={`$${state.equity.toFixed(2)}`} />
                                <StatRow label="Initial Capital" value={`$${state.initialCash.toFixed(2)}`} />
                            </div>
                        </div>
                    </div>

                    {/* Trade List */}
                    {state.trades.length > 0 && (
                        <div>
                            <h3 style={{
                                margin: '0 0 12px 0',
                                fontSize: '14px',
                                fontWeight: 600,
                                color: CHART_THEME.textPrimary,
                            }}>
                                Trade History
                            </h3>
                            <div style={{
                                background: CHART_THEME.bgTertiary,
                                borderRadius: '8px',
                                overflow: 'hidden',
                            }}>
                                <table style={{
                                    width: '100%',
                                    borderCollapse: 'collapse',
                                    fontSize: '12px',
                                }}>
                                    <thead>
                                        <tr style={{ background: CHART_THEME.bgPrimary }}>
                                            <th style={thStyle}>#</th>
                                            <th style={thStyle}>Side</th>
                                            <th style={thStyle}>Entry</th>
                                            <th style={thStyle}>Exit</th>
                                            <th style={thStyle}>Qty</th>
                                            <th style={thStyle}>P&L</th>
                                            <th style={thStyle}>%</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {state.trades.slice(-20).reverse().map((trade, idx) => (
                                            <TradeRow key={trade.id} trade={trade} index={state.trades.length - idx} />
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

const thStyle: React.CSSProperties = {
    padding: '10px 12px',
    textAlign: 'left',
    color: CHART_THEME.textSecondary,
    fontWeight: 500,
    borderBottom: `1px solid ${CHART_THEME.border}`,
};

const tdStyle: React.CSSProperties = {
    padding: '10px 12px',
    borderBottom: `1px solid ${CHART_THEME.border}`,
    color: CHART_THEME.textPrimary,
};

function SummaryCard({ 
    label, 
    value, 
    subValue, 
    color 
}: { 
    label: string; 
    value: string; 
    subValue: string; 
    color: string;
}) {
    return (
        <div style={{
            padding: '16px',
            background: CHART_THEME.bgTertiary,
            borderRadius: '8px',
        }}>
            <div style={{
                fontSize: '11px',
                color: CHART_THEME.textSecondary,
                marginBottom: '8px',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
            }}>
                {label}
            </div>
            <div style={{
                fontSize: '24px',
                fontWeight: 700,
                color: color,
                fontFamily: CHART_THEME.fontMono,
            }}>
                {value}
            </div>
            <div style={{
                fontSize: '12px',
                color: CHART_THEME.textSecondary,
                marginTop: '4px',
            }}>
                {subValue}
            </div>
        </div>
    );
}

function StatRow({ 
    label, 
    value, 
    color = CHART_THEME.textPrimary 
}: { 
    label: string; 
    value: string; 
    color?: string;
}) {
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            padding: '8px 0',
            borderBottom: `1px solid ${CHART_THEME.border}`,
        }}>
            <span style={{ color: CHART_THEME.textSecondary, fontSize: '12px' }}>{label}</span>
            <span style={{ color, fontSize: '12px', fontFamily: CHART_THEME.fontMono }}>{value}</span>
        </div>
    );
}

function TradeRow({ trade, index }: { trade: PaperTrade; index: number }) {
    const isProfit = trade.pnl >= 0;
    
    return (
        <tr>
            <td style={tdStyle}>{index}</td>
            <td style={tdStyle}>
                <span style={{
                    padding: '2px 6px',
                    borderRadius: '3px',
                    fontSize: '10px',
                    fontWeight: 600,
                    background: trade.side === 'buy' 
                        ? 'rgba(0, 255, 136, 0.15)' 
                        : 'rgba(255, 45, 85, 0.15)',
                    color: trade.side === 'buy' ? CHART_THEME.upColor : CHART_THEME.downColor,
                }}>
                    {trade.side.toUpperCase()}
                </span>
            </td>
            <td style={{ ...tdStyle, fontFamily: CHART_THEME.fontMono }}>
                ${trade.entryPrice.toFixed(2)}
            </td>
            <td style={{ ...tdStyle, fontFamily: CHART_THEME.fontMono }}>
                ${trade.exitPrice.toFixed(2)}
            </td>
            <td style={{ ...tdStyle, fontFamily: CHART_THEME.fontMono }}>
                {trade.quantity}
            </td>
            <td style={{ 
                ...tdStyle, 
                fontFamily: CHART_THEME.fontMono,
                color: isProfit ? CHART_THEME.upColor : CHART_THEME.downColor,
            }}>
                {isProfit ? '+' : ''}{trade.pnl.toFixed(2)}
            </td>
            <td style={{ 
                ...tdStyle, 
                fontFamily: CHART_THEME.fontMono,
                color: isProfit ? CHART_THEME.upColor : CHART_THEME.downColor,
            }}>
                {isProfit ? '+' : ''}{trade.pnlPercent.toFixed(2)}%
            </td>
        </tr>
    );
}

function EquityCurveChart({ 
    data, 
    initialCash 
}: { 
    data: { timestamp: number; equity: number }[];
    initialCash: number;
}) {
    const width = 800;
    const height = 180;
    const padding = { top: 20, right: 60, bottom: 30, left: 10 };

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const pathD = useMemo(() => {
        if (data.length < 2) return '';

        const minEquity = Math.min(...data.map(d => d.equity));
        const maxEquity = Math.max(...data.map(d => d.equity));
        const range = maxEquity - minEquity || 1;

        return data.map((point, i) => {
            const x = (i / (data.length - 1)) * chartWidth + padding.left;
            const y = chartHeight - ((point.equity - minEquity) / range) * chartHeight + padding.top;
            return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
        }).join(' ');
    }, [data, chartWidth, chartHeight]);

    const finalEquity = data.length > 0 ? data[data.length - 1].equity : initialCash;
    const isProfit = finalEquity >= initialCash;

    return (
        <svg width={width} height={height} style={{ display: 'block' }}>
            {/* Grid lines */}
            <line
                x1={padding.left}
                y1={height / 2}
                x2={width - padding.right}
                y2={height / 2}
                stroke={CHART_THEME.border}
                strokeDasharray="4,4"
            />

            {/* Baseline (initial cash) */}
            <line
                x1={padding.left}
                y1={chartHeight * 0.5 + padding.top}
                x2={width - padding.right}
                y2={chartHeight * 0.5 + padding.top}
                stroke={CHART_THEME.textMuted}
                strokeWidth={1}
                strokeDasharray="2,2"
            />

            {/* Equity curve */}
            <path
                d={pathD}
                fill="none"
                stroke={isProfit ? CHART_THEME.upColor : CHART_THEME.downColor}
                strokeWidth={2}
            />

            {/* Final value label */}
            <text
                x={width - padding.right + 8}
                y={padding.top + 10}
                fill={isProfit ? CHART_THEME.upColor : CHART_THEME.downColor}
                fontSize="12"
                fontFamily={CHART_THEME.fontMono}
            >
                ${finalEquity.toFixed(0)}
            </text>
        </svg>
    );
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function formatDuration(ms: number): string {
    if (ms < 60000) return `${Math.round(ms / 1000)}s`;
    if (ms < 3600000) return `${Math.round(ms / 60000)}m`;
    if (ms < 86400000) return `${(ms / 3600000).toFixed(1)}h`;
    return `${(ms / 86400000).toFixed(1)}d`;
}

function getReportDuration(equityCurve: { timestamp: number }[]): number {
    if (equityCurve.length < 2) return 0;
    return equityCurve[equityCurve.length - 1].timestamp - equityCurve[0].timestamp;
}

export default BacktestReport;
