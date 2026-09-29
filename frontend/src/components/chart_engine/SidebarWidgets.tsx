/**
 * Sidebar Widgets Component
 * TradingView-style sidebar widgets for Key Stats, Earnings, Analyst Estimates
 * Data sourced from Yahoo Finance via existing fetchFundamentals API
 */

'use client';

import React, { useMemo } from 'react';
import { CHART_THEME } from './types';

// =============================================================================
// TYPES
// =============================================================================

interface FundamentalsData {
    name?: string;
    exchange?: string;
    currency?: string;
    pe?: number;
    pb?: number;
    pe_forward?: number;
    eps_trailing?: number;
    eps_forward?: number;
    roe?: number;
    roic?: number;
    dividend_yield?: number;
    payout_ratio?: number;
    debt_to_equity?: number;
    current_ratio?: number;
    quick_ratio?: number;
    revenue_growth?: number;
    earnings_growth?: number;
    recommendation?: string;
    num_analysts?: number;
    target_mean?: number;
    target_high?: number;
    target_low?: number;
    target_median?: number;
    market_cap?: number;
    enterprise_value?: number;
    float_shares?: number;
    shares_outstanding?: number;
    short_ratio?: number;
    short_percent?: number;
    beta?: number;
    fifty_two_week_high?: number;
    fifty_two_week_low?: number;
    fifty_day_ma?: number;
    two_hundred_day_ma?: number;
    avg_volume?: number;
    earnings_date?: string;
    ex_dividend_date?: string;
    sector?: string;
    industry?: string;
    error?: string;
}

interface SidebarWidgetsProps {
    fundamentals: FundamentalsData | null;
    symbol: string;
    currentPrice?: number;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function formatNumber(value: number | undefined, decimals: number = 2): string {
    if (value === undefined || value === null || isNaN(value)) return 'N/A';
    return value.toFixed(decimals);
}

function formatPercent(value: number | undefined): string {
    if (value === undefined || value === null || isNaN(value)) return 'N/A';
    return `${(value * 100).toFixed(2)}%`;
}

function formatLargeNumber(value: number | undefined): string {
    if (value === undefined || value === null || isNaN(value)) return 'N/A';
    if (value >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
    return value.toFixed(0);
}

function formatDate(dateStr: string | undefined): string {
    if (!dateStr) return 'N/A';
    try {
        return new Date(dateStr).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    } catch {
        return 'N/A';
    }
}

// =============================================================================
// STAT ROW COMPONENT
// =============================================================================

function StatRow({ 
    label, 
    value, 
    valueColor, 
    subValue 
}: { 
    label: string; 
    value: string; 
    valueColor?: string;
    subValue?: string;
}) {
    return (
        <div className="flex justify-between items-center py-1.5 border-b border-white/5">
            <span 
                className="text-[11px] font-mono uppercase tracking-wide"
                style={{ color: CHART_THEME.textSecondary }}
            >
                {label}
            </span>
            <div className="text-right">
                <span 
                    className="text-xs font-mono font-bold"
                    style={{ color: valueColor || CHART_THEME.textPrimary }}
                >
                    {value}
                </span>
                {subValue && (
                    <span 
                        className="text-[10px] font-mono ml-1"
                        style={{ color: CHART_THEME.textMuted }}
                    >
                        {subValue}
                    </span>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// KEY STATS WIDGET
// =============================================================================

function KeyStatsWidget({ fundamentals, currentPrice }: { fundamentals: FundamentalsData; currentPrice?: number }) {
    const distToHigh = useMemo(() => {
        if (!fundamentals.fifty_two_week_high || !currentPrice) return null;
        return ((fundamentals.fifty_two_week_high - currentPrice) / currentPrice) * 100;
    }, [fundamentals.fifty_two_week_high, currentPrice]);

    const distToLow = useMemo(() => {
        if (!fundamentals.fifty_two_week_low || !currentPrice) return null;
        return ((currentPrice - fundamentals.fifty_two_week_low) / fundamentals.fifty_two_week_low) * 100;
    }, [fundamentals.fifty_two_week_low, currentPrice]);

    return (
        <div 
            className="rounded-lg p-3"
            style={{ 
                background: CHART_THEME.bgSecondary,
                border: `1px solid ${CHART_THEME.border}`,
            }}
        >
            <div 
                className="text-xs font-mono font-bold mb-3 uppercase tracking-wider flex items-center gap-2"
                style={{ color: CHART_THEME.accent }}
            >
                <span>📊</span>
                KEY STATISTICS
            </div>

            <div className="space-y-0">
                <StatRow 
                    label="Market Cap" 
                    value={formatLargeNumber(fundamentals.market_cap)}
                />
                <StatRow 
                    label="Enterprise Value" 
                    value={formatLargeNumber(fundamentals.enterprise_value)}
                />
                <StatRow 
                    label="P/E (TTM)" 
                    value={formatNumber(fundamentals.pe, 1)}
                />
                <StatRow 
                    label="P/E (Forward)" 
                    value={formatNumber(fundamentals.pe_forward, 1)}
                />
                <StatRow 
                    label="P/B Ratio" 
                    value={formatNumber(fundamentals.pb, 2)}
                />
                <StatRow 
                    label="EPS (TTM)" 
                    value={`$${formatNumber(fundamentals.eps_trailing)}`}
                />
                <StatRow 
                    label="Beta" 
                    value={formatNumber(fundamentals.beta, 2)}
                    valueColor={
                        (fundamentals.beta || 0) > 1.5 ? CHART_THEME.downColor : 
                        (fundamentals.beta || 0) < 0.8 ? CHART_THEME.upColor : 
                        CHART_THEME.textPrimary
                    }
                />
            </div>

            {/* 52-Week Range Visual */}
            <div className="mt-3 pt-3 border-t border-white/10">
                <div 
                    className="text-[10px] font-mono mb-2"
                    style={{ color: CHART_THEME.textSecondary }}
                >
                    52-WEEK RANGE
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono">
                    <span style={{ color: CHART_THEME.textMuted }}>
                        ${formatNumber(fundamentals.fifty_two_week_low, 2)}
                    </span>
                    <div 
                        className="flex-1 h-1.5 rounded-full relative"
                        style={{ background: CHART_THEME.bgPanel }}
                    >
                        {currentPrice && fundamentals.fifty_two_week_high && fundamentals.fifty_two_week_low && (
                            <div
                                className="absolute top-0 h-full w-1.5 rounded-full"
                                style={{ 
                                    left: `${((currentPrice - fundamentals.fifty_two_week_low) / 
                                        (fundamentals.fifty_two_week_high - fundamentals.fifty_two_week_low)) * 100}%`,
                                    background: CHART_THEME.accent,
                                    transform: 'translateX(-50%)',
                                }}
                            />
                        )}
                    </div>
                    <span style={{ color: CHART_THEME.textMuted }}>
                        ${formatNumber(fundamentals.fifty_two_week_high, 2)}
                    </span>
                </div>
                <div className="flex justify-between mt-1 text-[9px] font-mono">
                    <span style={{ color: CHART_THEME.upColor }}>
                        {distToLow !== null ? `+${distToLow.toFixed(1)}% from low` : ''}
                    </span>
                    <span style={{ color: CHART_THEME.downColor }}>
                        {distToHigh !== null ? `${distToHigh.toFixed(1)}% to high` : ''}
                    </span>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// ANALYST ESTIMATES WIDGET
// =============================================================================

function AnalystEstimatesWidget({ fundamentals, currentPrice }: { fundamentals: FundamentalsData; currentPrice?: number }) {
    const recommendation = fundamentals.recommendation?.toLowerCase() || '';
    
    const recColor = useMemo(() => {
        if (recommendation.includes('strong_buy') || recommendation.includes('buy')) return CHART_THEME.upColor;
        if (recommendation.includes('sell')) return CHART_THEME.downColor;
        return CHART_THEME.accent;
    }, [recommendation]);

    const recLabel = useMemo(() => {
        if (recommendation.includes('strong_buy')) return 'STRONG BUY';
        if (recommendation.includes('buy')) return 'BUY';
        if (recommendation.includes('hold')) return 'HOLD';
        if (recommendation.includes('sell')) return 'SELL';
        if (recommendation.includes('strong_sell')) return 'STRONG SELL';
        return recommendation.toUpperCase() || 'N/A';
    }, [recommendation]);

    const upside = useMemo(() => {
        if (!fundamentals.target_mean || !currentPrice) return null;
        return ((fundamentals.target_mean - currentPrice) / currentPrice) * 100;
    }, [fundamentals.target_mean, currentPrice]);

    return (
        <div 
            className="rounded-lg p-3"
            style={{ 
                background: CHART_THEME.bgSecondary,
                border: `1px solid ${CHART_THEME.border}`,
            }}
        >
            <div 
                className="text-xs font-mono font-bold mb-3 uppercase tracking-wider flex items-center gap-2"
                style={{ color: CHART_THEME.accent }}
            >
                <span>💼</span>
                ANALYST ESTIMATES
            </div>

            {/* Main Recommendation */}
            <div className="flex items-center justify-between mb-3 pb-3 border-b border-white/10">
                <div>
                    <div 
                        className="text-lg font-mono font-bold"
                        style={{ color: recColor }}
                    >
                        {recLabel}
                    </div>
                    <div 
                        className="text-[10px] font-mono"
                        style={{ color: CHART_THEME.textSecondary }}
                    >
                        Based on {fundamentals.num_analysts || 0} analysts
                    </div>
                </div>
                {upside !== null && (
                    <div className="text-right">
                        <div 
                            className="text-sm font-mono font-bold"
                            style={{ color: upside >= 0 ? CHART_THEME.upColor : CHART_THEME.downColor }}
                        >
                            {upside >= 0 ? '+' : ''}{upside.toFixed(1)}%
                        </div>
                        <div 
                            className="text-[10px] font-mono"
                            style={{ color: CHART_THEME.textSecondary }}
                        >
                            Potential
                        </div>
                    </div>
                )}
            </div>

            {/* Price Targets */}
            <div className="space-y-0">
                <StatRow 
                    label="Price Target (Mean)" 
                    value={`$${formatNumber(fundamentals.target_mean)}`}
                    valueColor={CHART_THEME.accent}
                />
                <StatRow 
                    label="Price Target (High)" 
                    value={`$${formatNumber(fundamentals.target_high)}`}
                    valueColor={CHART_THEME.upColor}
                />
                <StatRow 
                    label="Price Target (Low)" 
                    value={`$${formatNumber(fundamentals.target_low)}`}
                    valueColor={CHART_THEME.downColor}
                />
            </div>

            {/* Target Range Visual */}
            {fundamentals.target_high && fundamentals.target_low && currentPrice && (
                <div className="mt-3">
                    <div 
                        className="h-2 rounded-full relative"
                        style={{ background: CHART_THEME.bgPanel }}
                    >
                        <div
                            className="absolute top-0 h-full rounded-full opacity-30"
                            style={{ 
                                left: `${Math.max(0, ((fundamentals.target_low - currentPrice * 0.8) / (currentPrice * 0.4)) * 100)}%`,
                                right: `${Math.max(0, 100 - ((fundamentals.target_high - currentPrice * 0.8) / (currentPrice * 0.4)) * 100)}%`,
                                background: `linear-gradient(to right, ${CHART_THEME.downColor}, ${CHART_THEME.upColor})`,
                            }}
                        />
                        {/* Current Price Marker */}
                        <div
                            className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full"
                            style={{ 
                                left: '50%',
                                transform: 'translate(-50%, -50%)',
                                background: CHART_THEME.textPrimary,
                                border: `2px solid ${CHART_THEME.bgPrimary}`,
                            }}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// EARNINGS & DIVIDENDS WIDGET
// =============================================================================

function EarningsWidget({ fundamentals }: { fundamentals: FundamentalsData }) {
    const hasEarningsDate = fundamentals.earnings_date && fundamentals.earnings_date !== 'N/A';
    const hasDividend = (fundamentals.dividend_yield || 0) > 0;

    return (
        <div 
            className="rounded-lg p-3"
            style={{ 
                background: CHART_THEME.bgSecondary,
                border: `1px solid ${CHART_THEME.border}`,
            }}
        >
            <div 
                className="text-xs font-mono font-bold mb-3 uppercase tracking-wider flex items-center gap-2"
                style={{ color: CHART_THEME.accent }}
            >
                <span>📅</span>
                EARNINGS & DIVIDENDS
            </div>

            <div className="space-y-0">
                <StatRow 
                    label="Next Earnings" 
                    value={hasEarningsDate ? formatDate(fundamentals.earnings_date) : 'TBD'}
                />
                <StatRow 
                    label="Revenue Growth" 
                    value={formatPercent(fundamentals.revenue_growth)}
                    valueColor={(fundamentals.revenue_growth || 0) >= 0 ? CHART_THEME.upColor : CHART_THEME.downColor}
                />
                <StatRow 
                    label="Earnings Growth" 
                    value={formatPercent(fundamentals.earnings_growth)}
                    valueColor={(fundamentals.earnings_growth || 0) >= 0 ? CHART_THEME.upColor : CHART_THEME.downColor}
                />
            </div>

            {/* Dividend Section */}
            {hasDividend && (
                <div className="mt-3 pt-3 border-t border-white/10">
                    <div 
                        className="text-[10px] font-mono mb-2 uppercase"
                        style={{ color: CHART_THEME.textSecondary }}
                    >
                        Dividend Info
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div 
                            className="p-2 rounded"
                            style={{ background: CHART_THEME.bgPanel }}
                        >
                            <div 
                                className="text-[10px] font-mono"
                                style={{ color: CHART_THEME.textSecondary }}
                            >
                                YIELD
                            </div>
                            <div 
                                className="text-sm font-mono font-bold"
                                style={{ color: CHART_THEME.upColor }}
                            >
                                {formatPercent(fundamentals.dividend_yield)}
                            </div>
                        </div>
                        <div 
                            className="p-2 rounded"
                            style={{ background: CHART_THEME.bgPanel }}
                        >
                            <div 
                                className="text-[10px] font-mono"
                                style={{ color: CHART_THEME.textSecondary }}
                            >
                                PAYOUT RATIO
                            </div>
                            <div 
                                className="text-sm font-mono font-bold"
                                style={{ color: CHART_THEME.textPrimary }}
                            >
                                {formatPercent(fundamentals.payout_ratio)}
                            </div>
                        </div>
                    </div>
                    {fundamentals.ex_dividend_date && (
                        <div className="mt-2">
                            <StatRow 
                                label="Ex-Dividend Date" 
                                value={formatDate(fundamentals.ex_dividend_date)}
                            />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// FINANCIALS WIDGET
// =============================================================================

function FinancialsWidget({ fundamentals }: { fundamentals: FundamentalsData }) {
    return (
        <div 
            className="rounded-lg p-3"
            style={{ 
                background: CHART_THEME.bgSecondary,
                border: `1px solid ${CHART_THEME.border}`,
            }}
        >
            <div 
                className="text-xs font-mono font-bold mb-3 uppercase tracking-wider flex items-center gap-2"
                style={{ color: CHART_THEME.accent }}
            >
                <span>📈</span>
                FINANCIALS
            </div>

            <div className="space-y-0">
                <StatRow 
                    label="ROE" 
                    value={formatPercent(fundamentals.roe)}
                    valueColor={(fundamentals.roe || 0) >= 0.15 ? CHART_THEME.upColor : CHART_THEME.textPrimary}
                />
                <StatRow 
                    label="ROIC" 
                    value={formatPercent(fundamentals.roic)}
                />
                <StatRow 
                    label="Debt/Equity" 
                    value={formatNumber(fundamentals.debt_to_equity, 2)}
                    valueColor={(fundamentals.debt_to_equity || 0) > 2 ? CHART_THEME.downColor : CHART_THEME.textPrimary}
                />
                <StatRow 
                    label="Current Ratio" 
                    value={formatNumber(fundamentals.current_ratio, 2)}
                    valueColor={(fundamentals.current_ratio || 0) < 1 ? CHART_THEME.downColor : CHART_THEME.upColor}
                />
                <StatRow 
                    label="Quick Ratio" 
                    value={formatNumber(fundamentals.quick_ratio, 2)}
                />
            </div>

            {/* Sector/Industry */}
            {(fundamentals.sector || fundamentals.industry) && (
                <div className="mt-3 pt-3 border-t border-white/10">
                    {fundamentals.sector && (
                        <div className="flex justify-between py-1">
                            <span 
                                className="text-[10px] font-mono uppercase"
                                style={{ color: CHART_THEME.textSecondary }}
                            >
                                Sector
                            </span>
                            <span 
                                className="text-[11px] font-mono"
                                style={{ color: CHART_THEME.textPrimary }}
                            >
                                {fundamentals.sector}
                            </span>
                        </div>
                    )}
                    {fundamentals.industry && (
                        <div className="flex justify-between py-1">
                            <span 
                                className="text-[10px] font-mono uppercase"
                                style={{ color: CHART_THEME.textSecondary }}
                            >
                                Industry
                            </span>
                            <span 
                                className="text-[11px] font-mono text-right max-w-[60%]"
                                style={{ color: CHART_THEME.textPrimary }}
                            >
                                {fundamentals.industry}
                            </span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// MAIN SIDEBAR WIDGETS COMPONENT
// =============================================================================

export default function SidebarWidgets({ fundamentals, symbol, currentPrice }: SidebarWidgetsProps) {
    if (!fundamentals || fundamentals.error) {
        return (
            <div 
                className="rounded-lg p-4 text-center"
                style={{ 
                    background: CHART_THEME.bgSecondary,
                    border: `1px solid ${CHART_THEME.border}`,
                }}
            >
                <div 
                    className="text-sm font-mono"
                    style={{ color: CHART_THEME.textSecondary }}
                >
                    {fundamentals?.error || `No data available for ${symbol}`}
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-3">
            <KeyStatsWidget fundamentals={fundamentals} currentPrice={currentPrice} />
            <AnalystEstimatesWidget fundamentals={fundamentals} currentPrice={currentPrice} />
            <EarningsWidget fundamentals={fundamentals} />
            <FinancialsWidget fundamentals={fundamentals} />
        </div>
    );
}

// =============================================================================
// EXPORTS
// =============================================================================

export { KeyStatsWidget, AnalystEstimatesWidget, EarningsWidget, FinancialsWidget };
