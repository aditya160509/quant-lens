"use client";

/**
 * MACRO CONTROL SYSTEM - World-Class Dashboard
 * =============================================
 * 7 interconnected regime detection systems
 * 
 * Features:
 * 1. Market Regime Engine (HMM-based 4-state)
 * 2. Stress Detector (Mahalanobis Turbulence)
 * 3. Volatility Regime Classifier
 * 4. CTA Trend Signal Engine
 * 5. Mean Reversion Timer
 * 6. Market Breadth (McClellan)
 * 7. Rate Cycle Position
 */

import React, { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import Recharts
const AreaChart = dynamic(() => import('recharts').then(mod => mod.AreaChart), { ssr: false });
const Area = dynamic(() => import('recharts').then(mod => mod.Area), { ssr: false });
const BarChart = dynamic(() => import('recharts').then(mod => mod.BarChart), { ssr: false });
const Bar = dynamic(() => import('recharts').then(mod => mod.Bar), { ssr: false });
const LineChart = dynamic(() => import('recharts').then(mod => mod.LineChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(mod => mod.Line), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(mod => mod.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(mod => mod.YAxis), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(mod => mod.Tooltip), { ssr: false });
const ResponsiveContainer = dynamic(() => import('recharts').then(mod => mod.ResponsiveContainer), { ssr: false });
const ReferenceLine = dynamic(() => import('recharts').then(mod => mod.ReferenceLine), { ssr: false });
const Cell = dynamic(() => import('recharts').then(mod => mod.Cell), { ssr: false });

const API_BASE = 'http://127.0.0.1:8000/api/market-labs';

// =============================================================================
// THEME & COLORS
// =============================================================================

const THEME = {
    bg: '#0a0a0f',
    card: '#12121a',
    cardHover: '#1a1a24',
    border: '#1e1e2e',
    text: '#e0e0e0',
    textMuted: '#888',
    green: '#10b981',
    yellow: '#f59e0b',
    red: '#ef4444',
    blue: '#3b82f6',
    purple: '#a855f7',
    cyan: '#00d4ff',
    orange: '#f97316',
};

const POSTURE_COLORS = {
    'RISK-ON': { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', text: '#10b981' },
    'CAUTION': { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', text: '#f59e0b' },
    'RISK-OFF': { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', text: '#ef4444' },
};

// =============================================================================
// SHARED COMPONENTS
// =============================================================================

function LoadingSpinner() {
    return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px' }}>
            <div style={{
                width: '32px',
                height: '32px',
                border: '3px solid #1e1e2e',
                borderTop: '3px solid #a855f7',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
            }} />
        </div>
    );
}

function FeatureCard({ title, icon, badge, children, loading, color = THEME.purple }) {
    return (
        <div style={{
            background: THEME.card,
            border: `1px solid ${THEME.border}`,
            borderRadius: '12px',
            overflow: 'hidden',
            position: 'relative',
        }}>
            {/* Header */}
            <div style={{
                padding: '16px 20px',
                borderBottom: `1px solid ${THEME.border}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '20px' }}>{icon}</span>
                    <span style={{
                        fontSize: '14px',
                        fontWeight: 600,
                        fontFamily: 'monospace',
                        color: THEME.text,
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                    }}>{title}</span>
                </div>
                {badge && (
                    <span style={{
                        background: `${color}20`,
                        color: color,
                        fontSize: '10px',
                        fontWeight: 700,
                        fontFamily: 'monospace',
                        padding: '4px 8px',
                        borderRadius: '4px',
                    }}>{badge}</span>
                )}
            </div>
            
            {/* Content */}
            <div style={{ padding: '20px' }}>
                {loading ? <LoadingSpinner /> : children}
            </div>
            
            {/* Accent bar */}
            <div style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: '2px',
                background: `linear-gradient(90deg, ${color}, transparent)`
            }} />
        </div>
    );
}

function MetricRow({ label, value, subtext, color = THEME.text }) {
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 0',
            borderBottom: `1px solid ${THEME.border}`,
        }}>
            <span style={{ color: THEME.textMuted, fontSize: '12px', fontFamily: 'monospace' }}>{label}</span>
            <div style={{ textAlign: 'right' }}>
                <span style={{ color, fontSize: '14px', fontWeight: 600, fontFamily: 'monospace' }}>{value}</span>
                {subtext && <div style={{ color: THEME.textMuted, fontSize: '10px' }}>{subtext}</div>}
            </div>
        </div>
    );
}

function ProgressBar({ value, max = 100, color = THEME.green }) {
    const pct = Math.min(100, Math.max(0, (value / max) * 100));
    return (
        <div style={{
            width: '100%',
            height: '8px',
            background: THEME.border,
            borderRadius: '4px',
            overflow: 'hidden',
        }}>
            <div style={{
                width: `${pct}%`,
                height: '100%',
                background: color,
                transition: 'width 0.5s ease',
            }} />
        </div>
    );
}

function StatusBadge({ status, size = 'normal' }) {
    const colors = {
        'NORMAL': { bg: '#10b98120', text: '#10b981' },
        'ELEVATED': { bg: '#f59e0b20', text: '#f59e0b' },
        'EXTREME': { bg: '#ef444420', text: '#ef4444' },
        'LOW': { bg: '#10b98120', text: '#10b981' },
        'MEDIUM': { bg: '#f59e0b20', text: '#f59e0b' },
        'HIGH': { bg: '#ef444420', text: '#ef4444' },
        'LONG': { bg: '#10b98120', text: '#10b981' },
        'SHORT': { bg: '#ef444420', text: '#ef4444' },
        'NEUTRAL': { bg: '#88888820', text: '#888' },
        'BULLISH': { bg: '#10b98120', text: '#10b981' },
        'BEARISH': { bg: '#ef444420', text: '#ef4444' },
        'HEALTHY': { bg: '#10b98120', text: '#10b981' },
        'DETERIORATING': { bg: '#ef444420', text: '#ef4444' },
        'CONFIRMED': { bg: '#10b98120', text: '#10b981' },
        'DIVERGENCE': { bg: '#ef444420', text: '#ef4444' },
        'TAILWIND': { bg: '#10b98120', text: '#10b981' },
        'HEADWIND': { bg: '#ef444420', text: '#ef4444' },
        'EASING': { bg: '#10b98120', text: '#10b981' },
        'TIGHTENING': { bg: '#ef444420', text: '#ef4444' },
        'PAUSE': { bg: '#f59e0b20', text: '#f59e0b' },
    };
    
    const c = colors[status] || colors['NEUTRAL'];
    const fontSize = size === 'small' ? '9px' : '11px';
    const padding = size === 'small' ? '2px 6px' : '4px 10px';
    
    return (
        <span style={{
            background: c.bg,
            color: c.text,
            fontSize,
            fontWeight: 600,
            fontFamily: 'monospace',
            padding,
            borderRadius: '4px',
            textTransform: 'uppercase',
        }}>{status}</span>
    );
}

// =============================================================================
// MASTER CONTROL PANEL
// =============================================================================

function MasterControlPanel({ data, loading }) {
    if (loading || !data) {
        return (
            <div style={{
                background: THEME.card,
                border: `1px solid ${THEME.border}`,
                borderRadius: '16px',
                padding: '32px',
                marginBottom: '24px',
            }}>
                <LoadingSpinner />
            </div>
        );
    }
    
    const postureStyle = POSTURE_COLORS[data.posture] || POSTURE_COLORS['CAUTION'];
    
    return (
        <div style={{
            background: postureStyle.bg,
            border: `2px solid ${postureStyle.border}`,
            borderRadius: '16px',
            padding: '24px',
            marginBottom: '24px',
        }}>
            {/* Header Row */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '20px',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <span style={{ fontSize: '32px' }}>🎯</span>
                    <div>
                        <div style={{
                            fontSize: '24px',
                            fontWeight: 700,
                            fontFamily: 'monospace',
                            color: postureStyle.text,
                            textTransform: 'uppercase',
                        }}>
                            {data.posture}
                        </div>
                        <div style={{
                            fontSize: '12px',
                            color: THEME.textMuted,
                            fontFamily: 'monospace',
                        }}>
                            MASTER TRADING POSTURE
                        </div>
                    </div>
                </div>
                
                <div style={{ textAlign: 'right' }}>
                    <div style={{
                        fontSize: '48px',
                        fontWeight: 700,
                        fontFamily: 'monospace',
                        color: postureStyle.text,
                    }}>
                        {data.overall_score?.toFixed(0) || 0}
                    </div>
                    <div style={{ color: THEME.textMuted, fontSize: '11px' }}>/ 100</div>
                </div>
            </div>
            
            {/* Progress Bar */}
            <div style={{ marginBottom: '20px' }}>
                <ProgressBar value={data.overall_score || 0} color={postureStyle.border} />
            </div>
            
            {/* Clearances Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '16px',
                marginBottom: '20px',
            }}>
                <div style={{ background: THEME.card, borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ color: THEME.textMuted, fontSize: '10px', marginBottom: '4px' }}>MAX EXPOSURE</div>
                    <div style={{ color: THEME.text, fontSize: '20px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {data.max_exposure}%
                    </div>
                </div>
                <div style={{ background: THEME.card, borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ color: THEME.textMuted, fontSize: '10px', marginBottom: '4px' }}>LEVERAGE</div>
                    <div style={{ color: data.leverage_allowed ? THEME.green : THEME.red, fontSize: '16px', fontWeight: 700 }}>
                        {data.leverage_allowed ? 'ALLOWED' : 'DISABLED'}
                    </div>
                </div>
                <div style={{ background: THEME.card, borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ color: THEME.textMuted, fontSize: '10px', marginBottom: '4px' }}>NEW POSITIONS</div>
                    <StatusBadge status={data.new_positions || 'ALLOWED'} />
                </div>
                <div style={{ background: THEME.card, borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ color: THEME.textMuted, fontSize: '10px', marginBottom: '4px' }}>STRATEGY BIAS</div>
                    <div style={{ color: THEME.text, fontSize: '11px', fontFamily: 'monospace' }}>
                        {data.preferred_strategies || 'All'}
                    </div>
                </div>
            </div>
            
            {/* Warnings */}
            {data.warnings && data.warnings.length > 0 && (
                <div style={{
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    borderRadius: '8px',
                    padding: '12px',
                }}>
                    <div style={{ color: THEME.red, fontSize: '11px', fontWeight: 600, marginBottom: '8px' }}>
                        ⚠️ ACTIVE WARNINGS ({data.warnings.length})
                    </div>
                    {data.warnings.map((w, i) => (
                        <div key={i} style={{ color: THEME.textMuted, fontSize: '11px', marginLeft: '16px' }}>
                            • {w}
                        </div>
                    ))}
                </div>
            )}
            
            {/* Feature Scores */}
            <div style={{ marginTop: '20px' }}>
                <div style={{ color: THEME.textMuted, fontSize: '10px', marginBottom: '8px' }}>FEATURE BREAKDOWN</div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {data.feature_scores && Object.entries(data.feature_scores).map(([key, score]) => (
                        <div key={key} style={{
                            background: THEME.card,
                            borderRadius: '6px',
                            padding: '6px 10px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                        }}>
                            <span style={{ color: THEME.textMuted, fontSize: '10px', textTransform: 'capitalize' }}>{key}</span>
                            <span style={{
                                color: score >= 70 ? THEME.green : score >= 40 ? THEME.yellow : THEME.red,
                                fontSize: '12px',
                                fontWeight: 600,
                                fontFamily: 'monospace',
                            }}>{score}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// FEATURE 1: REGIME ENGINE CARD
// =============================================================================

function RegimeEngineCard({ data, loading }) {
    if (!data) return null;
    
    const regimeColors = {
        'Bull Low Vol': THEME.green,
        'Bull High Vol': THEME.yellow,
        'Bear Low Vol': THEME.orange,
        'Bear High Vol': THEME.red,
    };
    
    return (
        <FeatureCard title="Market Regime Engine" icon="🔄" badge="R1" loading={loading} color={regimeColors[data.regime_label] || THEME.purple}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div>
                    <div style={{ color: regimeColors[data.regime_label] || THEME.text, fontSize: '18px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {data.regime_label}
                    </div>
                    <div style={{ color: THEME.textMuted, fontSize: '11px' }}>Current State</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <div style={{ color: THEME.text, fontSize: '24px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {data.confidence?.toFixed(0)}%
                    </div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Confidence</div>
                </div>
            </div>
            
            {/* Probability Bars */}
            <div style={{ marginBottom: '16px' }}>
                {data.probabilities && Object.entries(data.probabilities).map(([regime, prob]) => (
                    <div key={regime} style={{ marginBottom: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ color: regime === data.regime_label ? regimeColors[regime] : THEME.textMuted, fontSize: '11px' }}>
                                {regime} {regime === data.regime_label && '← Current'}
                            </span>
                            <span style={{ color: THEME.text, fontSize: '11px', fontFamily: 'monospace' }}>{prob?.toFixed(0)}%</span>
                        </div>
                        <ProgressBar value={prob || 0} color={regimeColors[regime] || THEME.purple} />
                    </div>
                ))}
            </div>
            
            <MetricRow label="Transition Risk" value={data.transition_risk} color={data.transition_risk === 'LOW' ? THEME.green : data.transition_risk === 'HIGH' ? THEME.red : THEME.yellow} />
            <MetricRow label="Stability Score" value={`${data.stability?.toFixed(0)}%`} />
            <MetricRow label="Days in Regime" value={data.days_in_regime} />
            
            {/* Chart */}
            {data.probability_history && data.probability_history.length > 0 && (
                <div style={{ height: 150, marginTop: '16px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data.probability_history}>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fill: THEME.textMuted }} tickFormatter={d => d?.slice(5, 10)} />
                            <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: THEME.textMuted }} />
                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px' }} />
                            <Area type="monotone" dataKey="bull_low_vol" stackId="1" stroke={THEME.green} fill={THEME.green} fillOpacity={0.3} />
                            <Area type="monotone" dataKey="bull_high_vol" stackId="1" stroke={THEME.yellow} fill={THEME.yellow} fillOpacity={0.3} />
                            <Area type="monotone" dataKey="bear_low_vol" stackId="1" stroke={THEME.orange} fill={THEME.orange} fillOpacity={0.3} />
                            <Area type="monotone" dataKey="bear_high_vol" stackId="1" stroke={THEME.red} fill={THEME.red} fillOpacity={0.3} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}
        </FeatureCard>
    );
}

// =============================================================================
// FEATURE 2: STRESS DETECTOR CARD
// =============================================================================

function StressDetectorCard({ data, loading }) {
    if (!data) return null;
    
    const stateColors = {
        'NORMAL': THEME.green,
        'ELEVATED': THEME.yellow,
        'EXTREME': THEME.red,
    };
    
    return (
        <FeatureCard title="Stress Detector" icon="⚡" badge="R2" loading={loading} color={stateColors[data.state] || THEME.purple}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <StatusBadge status={data.state} />
                <div style={{ textAlign: 'right' }}>
                    <div style={{ color: THEME.text, fontSize: '11px' }}>Percentile</div>
                    <div style={{ color: stateColors[data.state], fontSize: '20px', fontWeight: 700 }}>{data.percentile?.toFixed(0)}th</div>
                </div>
            </div>
            
            <MetricRow label="Turbulence Index" value={data.turbulence_index?.toFixed(2)} color={stateColors[data.state]} />
            <MetricRow label="Normal Range" value={`0 - ${data.normal_range?.[1]?.toFixed(1)}`} />
            <MetricRow label="Warning Threshold" value={data.warning_threshold?.toFixed(1)} />
            <MetricRow label="Days Above Threshold" value={data.days_above_threshold} />
            
            {/* Constraints */}
            {data.constraints && (
                <div style={{ marginTop: '12px', background: `${stateColors[data.state]}10`, borderRadius: '8px', padding: '10px' }}>
                    <div style={{ color: stateColors[data.state], fontSize: '10px', fontWeight: 600, marginBottom: '6px' }}>TRADING CONSTRAINTS</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• New Positions: {data.constraints.new_positions}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Leverage: {data.constraints.leverage}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Action: {data.constraints.risk_action}</div>
                </div>
            )}
            
            {/* Chart */}
            {data.turbulence_history && data.turbulence_history.length > 0 && (
                <div style={{ height: 120, marginTop: '16px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data.turbulence_history}>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fill: THEME.textMuted }} tickFormatter={d => d?.slice(5, 10)} />
                            <YAxis tick={{ fontSize: 9, fill: THEME.textMuted }} />
                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                            <ReferenceLine y={data.warning_threshold} stroke={THEME.yellow} strokeDasharray="3 3" />
                            <Line type="monotone" dataKey="turbulence" stroke={stateColors[data.state]} dot={false} strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </FeatureCard>
    );
}

// =============================================================================
// FEATURE 3: VOLATILITY REGIME CARD
// =============================================================================

function VolatilityRegimeCard({ data, loading }) {
    if (!data) return null;
    
    return (
        <FeatureCard title="Volatility Regime" icon="📈" badge="R3" loading={loading} color={THEME.cyan}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div>
                    <StatusBadge status={data.regime} />
                    <div style={{ color: THEME.textMuted, fontSize: '10px', marginTop: '4px' }}>Trend: <StatusBadge status={data.trend} size="small" /></div>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <div style={{ color: THEME.cyan, fontSize: '28px', fontWeight: 700, fontFamily: 'monospace' }}>{data.vix_level?.toFixed(1)}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>VIX Level</div>
                </div>
            </div>
            
            <MetricRow label="VIX Percentile" value={`${data.vix_percentile?.toFixed(0)}th`} />
            <MetricRow label="Expansion Probability" value={`${data.expansion_probability?.toFixed(0)}%`} />
            <MetricRow label="Mean Reversion Timeline" value={data.mean_reversion_timeline} />
            
            {/* Position Sizing */}
            {data.constraints && (
                <div style={{ marginTop: '12px', background: `${THEME.cyan}10`, borderRadius: '8px', padding: '10px' }}>
                    <div style={{ color: THEME.cyan, fontSize: '10px', fontWeight: 600, marginBottom: '6px' }}>POSITION SIZING</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Size Multiplier: {data.constraints.position_size_multiplier}×</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Stop Width: {data.constraints.stop_width}×</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Strategy Bias: {data.constraints.strategy_bias}</div>
                </div>
            )}
            
            {/* Chart */}
            {data.vix_history && data.vix_history.length > 0 && (
                <div style={{ height: 120, marginTop: '16px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data.vix_history.slice(-60)}>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fill: THEME.textMuted }} tickFormatter={d => d?.slice(5, 10)} />
                            <YAxis tick={{ fontSize: 9, fill: THEME.textMuted }} />
                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                            <Line type="monotone" dataKey="vix" stroke={THEME.cyan} dot={false} strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </FeatureCard>
    );
}

// =============================================================================
// FEATURE 4: CTA TREND CARD
// =============================================================================

function CTATrendCard({ data, loading }) {
    if (!data) return null;
    
    const directionColor = data.direction === 'LONG' ? THEME.green : data.direction === 'SHORT' ? THEME.red : THEME.textMuted;
    
    return (
        <FeatureCard title="CTA Trend Signal" icon="🎯" badge="R4" loading={loading} color={directionColor}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div>
                    <StatusBadge status={data.direction} />
                    <div style={{ color: THEME.textMuted, fontSize: '10px', marginTop: '4px' }}>Direction</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <div style={{ color: directionColor, fontSize: '28px', fontWeight: 700, fontFamily: 'monospace' }}>{data.agreement?.toFixed(0)}%</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Agreement</div>
                </div>
            </div>
            
            {/* Timeframe Signals */}
            <div style={{ marginBottom: '16px' }}>
                <div style={{ color: THEME.textMuted, fontSize: '10px', marginBottom: '8px' }}>TIMEFRAME ALIGNMENT</div>
                {data.signals && Object.entries(data.signals).map(([tf, signal]) => (
                    <div key={tf} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <span style={{ color: THEME.text, fontSize: '12px' }}>{tf}</span>
                        <StatusBadge status={signal} size="small" />
                    </div>
                ))}
            </div>
            
            <MetricRow label="Trend Maturity" value={`${data.maturity_days} days`} subtext={data.stage} />
            <MetricRow label="Exhaustion Risk" value={data.exhaustion_risk} color={data.exhaustion_risk === 'HIGH' ? THEME.red : data.exhaustion_risk === 'MEDIUM' ? THEME.yellow : THEME.green} />
            
            {/* Guidance */}
            {data.constraints && (
                <div style={{ marginTop: '12px', background: `${directionColor}10`, borderRadius: '8px', padding: '10px' }}>
                    <div style={{ color: directionColor, fontSize: '10px', fontWeight: 600, marginBottom: '6px' }}>TRADING GUIDANCE</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Continuation: {data.constraints.continuation_allowed ? 'Allowed' : 'Avoid'}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Scale-in: {data.constraints.scale_in}</div>
                    {data.constraints.warning && <div style={{ color: THEME.yellow, fontSize: '10px' }}>• ⚠️ {data.constraints.warning}</div>}
                </div>
            )}
        </FeatureCard>
    );
}

// =============================================================================
// FEATURE 5: MEAN REVERSION CARD
// =============================================================================

function MeanReversionCard({ data, loading }) {
    if (!data) return null;
    
    const statusColors = {
        'EXTREME OVERBOUGHT': THEME.red,
        'OVERBOUGHT': THEME.orange,
        'NEUTRAL': THEME.green,
        'OVERSOLD': THEME.orange,
        'EXTREME OVERSOLD': THEME.red,
    };
    
    return (
        <FeatureCard title="Mean Reversion Timer" icon="⏱️" badge="R5" loading={loading} color={statusColors[data.status] || THEME.purple}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div>
                    <div style={{ color: statusColors[data.status], fontSize: '14px', fontWeight: 700 }}>{data.status}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Extension Status</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <div style={{ color: data.zscore > 0 ? THEME.green : THEME.red, fontSize: '24px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {data.zscore > 0 ? '+' : ''}{data.zscore?.toFixed(1)}σ
                    </div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Z-Score</div>
                </div>
            </div>
            
            <MetricRow label="Distance from MA(20)" value={`${data.distance_ma20?.toFixed(1)}%`} color={data.distance_ma20 > 0 ? THEME.green : THEME.red} />
            <MetricRow label="Distance from MA(50)" value={`${data.distance_ma50?.toFixed(1)}%`} color={data.distance_ma50 > 0 ? THEME.green : THEME.red} />
            <MetricRow label="Snapback Probability" value={`${data.snapback_probability?.toFixed(0)}%`} subtext="within 5 days" />
            
            {/* Entry Restrictions */}
            {data.constraints && (
                <div style={{ marginTop: '12px', background: `${statusColors[data.status]}10`, borderRadius: '8px', padding: '10px' }}>
                    <div style={{ color: statusColors[data.status], fontSize: '10px', fontWeight: 600, marginBottom: '6px' }}>ENTRY RESTRICTIONS</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Long Entries: {data.constraints.long_entries}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Short Entries: {data.constraints.short_entries}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Profit-Taking: {data.constraints.profit_taking}</div>
                </div>
            )}
            
            {/* Chart */}
            {data.zscore_history && data.zscore_history.length > 0 && (
                <div style={{ height: 120, marginTop: '16px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data.zscore_history}>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fill: THEME.textMuted }} tickFormatter={d => d?.slice(5, 10)} />
                            <YAxis domain={[-3, 3]} tick={{ fontSize: 9, fill: THEME.textMuted }} />
                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                            <ReferenceLine y={2} stroke={THEME.red} strokeDasharray="3 3" />
                            <ReferenceLine y={-2} stroke={THEME.red} strokeDasharray="3 3" />
                            <ReferenceLine y={0} stroke={THEME.textMuted} />
                            <Line type="monotone" dataKey="zscore" stroke={THEME.purple} dot={false} strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </FeatureCard>
    );
}

// =============================================================================
// FEATURE 6: MARKET BREADTH CARD
// =============================================================================

function MarketBreadthCard({ data, loading }) {
    if (!data) return null;
    
    return (
        <FeatureCard title="Market Breadth" icon="📊" badge="R6" loading={loading} color={THEME.blue}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div style={{ textAlign: 'center', background: THEME.bg, borderRadius: '8px', padding: '12px' }}>
                    <div style={{ color: THEME.blue, fontSize: '24px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {data.oscillator > 0 ? '+' : ''}{data.oscillator?.toFixed(0)}
                    </div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>McClellan Oscillator</div>
                    <StatusBadge status={data.oscillator_momentum?.split(' ')[0] || 'NEUTRAL'} size="small" />
                </div>
                <div style={{ textAlign: 'center', background: THEME.bg, borderRadius: '8px', padding: '12px' }}>
                    <div style={{ color: THEME.cyan, fontSize: '24px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {data.summation > 0 ? '+' : ''}{data.summation?.toFixed(0)}
                    </div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>McClellan Summation</div>
                    <StatusBadge status={data.summation_trend || 'NEUTRAL'} size="small" />
                </div>
            </div>
            
            <MetricRow label="Breadth Health" value={data.breadth_health} color={data.breadth_health === 'HEALTHY' ? THEME.green : data.breadth_health === 'DETERIORATING' ? THEME.red : THEME.textMuted} />
            <MetricRow label="Price-Breadth Alignment" value={data.alignment} color={data.alignment === 'CONFIRMED' ? THEME.green : THEME.red} />
            <MetricRow label="Rally Quality" value={data.rally_quality} />
            
            {/* Breakout Trust */}
            {data.constraints && (
                <div style={{ marginTop: '12px', background: `${THEME.blue}10`, borderRadius: '8px', padding: '10px' }}>
                    <div style={{ color: THEME.blue, fontSize: '10px', fontWeight: 600, marginBottom: '6px' }}>BREAKOUT TRUST: {data.constraints.breakout_trust}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Chasing Allowed: {data.constraints.chasing_allowed ? 'Yes' : 'No'}</div>
                    {data.constraints.warning && <div style={{ color: THEME.yellow, fontSize: '10px' }}>• ⚠️ {data.constraints.warning}</div>}
                </div>
            )}
            
            {/* Chart */}
            {data.oscillator_history && data.oscillator_history.length > 0 && (
                <div style={{ height: 120, marginTop: '16px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data.oscillator_history.slice(-60)}>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fill: THEME.textMuted }} tickFormatter={d => d?.slice(5, 10)} />
                            <YAxis tick={{ fontSize: 9, fill: THEME.textMuted }} />
                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                            <ReferenceLine y={0} stroke={THEME.textMuted} />
                            <Bar dataKey="oscillator" fill={THEME.blue}>
                                {data.oscillator_history.slice(-60).map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.oscillator >= 0 ? THEME.green : THEME.red} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}
        </FeatureCard>
    );
}

// =============================================================================
// FEATURE 7: RATE CYCLE CARD
// =============================================================================

function RateCycleCard({ data, loading, market }) {
    if (!data) return null;
    
    const cycleColors = {
        'EASING': THEME.green,
        'PAUSE': THEME.yellow,
        'TIGHTENING': THEME.red,
    };
    
    return (
        <FeatureCard title="Rate Cycle Position" icon="💰" badge="R7" loading={loading} color={cycleColors[data.cycle] || THEME.purple}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div>
                    <div style={{ color: THEME.text, fontSize: '28px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {data.rate?.toFixed(2)}%
                    </div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>{market === 'US' ? 'Fed Funds Rate' : 'RBI Repo Rate'}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <StatusBadge status={data.cycle} />
                    <div style={{ color: THEME.textMuted, fontSize: '10px', marginTop: '4px' }}>
                        Last: {data.last_change_bps > 0 ? '+' : ''}{data.last_change_bps} bps
                    </div>
                </div>
            </div>
            
            <MetricRow label="Policy Stance" value={data.stance} color={data.stance === 'TAILWIND' ? THEME.green : data.stance === 'HEADWIND' ? THEME.red : THEME.textMuted} />
            <MetricRow label="Next Meeting" value={data.next_meeting} />
            
            {/* Implications */}
            {data.constraints && (
                <div style={{ marginTop: '12px', background: `${cycleColors[data.cycle]}10`, borderRadius: '8px', padding: '10px' }}>
                    <div style={{ color: cycleColors[data.cycle], fontSize: '10px', fontWeight: 600, marginBottom: '6px' }}>RISK ASSET IMPLICATIONS</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Preference: {data.constraints.growth_vs_defensive}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Leverage Sensitivity: {data.constraints.leverage_sensitivity}</div>
                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>• Duration Bias: {data.constraints.duration_bias}</div>
                </div>
            )}
            
            {/* Chart */}
            {data.rate_history && data.rate_history.length > 0 && (
                <div style={{ height: 100, marginTop: '16px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data.rate_history}>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fill: THEME.textMuted }} />
                            <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9, fill: THEME.textMuted }} />
                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                            <Line type="stepAfter" dataKey="rate" stroke={cycleColors[data.cycle]} dot={false} strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </FeatureCard>
    );
}

// =============================================================================
// MAIN PAGE COMPONENT
// =============================================================================

export default function MacroControlPage() {
    const [market, setMarket] = useState('US');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [error, setError] = useState(null);
    const [retryCount, setRetryCount] = useState(0);
    
    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
            
            const response = await fetch(`${API_BASE}/all-features?market=${market}`, {
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json',
                }
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                const result = await response.json();
                setData(result);
                setLastUpdate(new Date().toLocaleTimeString());
                setRetryCount(0);
                setError(null);
            } else if (response.status === 429) {
                setError('Rate limit exceeded. Please wait a moment before refreshing.');
            } else if (response.status >= 500) {
                setError('Server error. The system may be updating data. Please try again.');
            } else {
                const errorData = await response.json().catch(() => ({}));
                setError(errorData.detail || 'Failed to load data. Please try again.');
            }
        } catch (err) {
            if (err.name === 'AbortError') {
                setError('Request timed out. The server may be busy.');
            } else if (err.message.includes('fetch')) {
                setError('Cannot connect to server. Please check if the backend is running.');
            } else {
                setError('Network error. Please check your connection.');
            }
            console.error('Error fetching macro data:', err);
        } finally {
            setLoading(false);
        }
    }, [market]);
    
    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000); // Refresh every minute
        return () => clearInterval(interval);
    }, [fetchData]);
    
    return (
        <div style={{
            minHeight: '100vh',
            background: THEME.bg,
            padding: '24px',
        }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '24px',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '32px' }}>🌍</span>
                    <div>
                        <h1 style={{
                            fontSize: '24px',
                            fontWeight: 700,
                            fontFamily: 'monospace',
                            color: THEME.text,
                            margin: 0,
                            textTransform: 'uppercase',
                            letterSpacing: '1px',
                        }}>
                            Macro Control System
                        </h1>
                        <p style={{ color: THEME.textMuted, fontSize: '12px', margin: 0 }}>
                            7 Regime Detection Systems • Real-Time Risk Posture
                        </p>
                    </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    {/* Last Update */}
                    {lastUpdate && (
                        <div style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace' }}>
                            Updated: {lastUpdate}
                        </div>
                    )}
                    
                    {/* Market Toggle */}
                    <div style={{
                        display: 'flex',
                        background: THEME.card,
                        border: `1px solid ${THEME.border}`,
                        borderRadius: '8px',
                        padding: '4px',
                    }}>
                        <button
                            onClick={() => setMarket('US')}
                            style={{
                                padding: '8px 20px',
                                borderRadius: '6px',
                                border: 'none',
                                fontFamily: 'monospace',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                background: market === 'US' ? THEME.blue : 'transparent',
                                color: market === 'US' ? '#fff' : THEME.textMuted,
                            }}
                        >
                            🇺🇸 US
                        </button>
                        <button
                            onClick={() => setMarket('INDIA')}
                            style={{
                                padding: '8px 20px',
                                borderRadius: '6px',
                                border: 'none',
                                fontFamily: 'monospace',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                background: market === 'INDIA' ? THEME.orange : 'transparent',
                                color: market === 'INDIA' ? '#fff' : THEME.textMuted,
                            }}
                        >
                            🇮🇳 INDIA
                        </button>
                    </div>
                    
                    {/* Refresh Button */}
                    <button
                        onClick={fetchData}
                        disabled={loading}
                        style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            border: `1px solid ${THEME.border}`,
                            background: THEME.card,
                            color: THEME.text,
                            fontFamily: 'monospace',
                            fontSize: '12px',
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.5 : 1,
                        }}
                    >
                        {loading ? '⏳' : '🔄'} Refresh
                    </button>
                </div>
            </div>
            
            {/* Master Control Panel */}
            <MasterControlPanel data={data} loading={loading} />
            
            {/* Error Display */}
            {error && (
                <div style={{
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid #ef4444',
                    borderRadius: '12px',
                    padding: '16px 20px',
                    marginBottom: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '20px' }}>⚠️</span>
                        <div>
                            <div style={{ color: '#ef4444', fontSize: '14px', fontWeight: 600 }}>Data Error</div>
                            <div style={{ color: THEME.textMuted, fontSize: '12px' }}>{error}</div>
                        </div>
                    </div>
                    <button
                        onClick={() => { setError(null); fetchData(); }}
                        style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            border: '1px solid #ef4444',
                            background: 'transparent',
                            color: '#ef4444',
                            fontFamily: 'monospace',
                            fontSize: '12px',
                            cursor: 'pointer',
                        }}
                    >
                        🔄 Retry
                    </button>
                </div>
            )}
            
            {/* Feature Cards Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
                gap: '20px',
            }}>
                <RegimeEngineCard data={data?.features?.regime} loading={loading} />
                <StressDetectorCard data={data?.features?.stress} loading={loading} />
                <VolatilityRegimeCard data={data?.features?.volatility} loading={loading} />
                <CTATrendCard data={data?.features?.trend} loading={loading} />
                <MeanReversionCard data={data?.features?.reversion} loading={loading} />
                <MarketBreadthCard data={data?.features?.breadth} loading={loading} />
                <RateCycleCard data={data?.features?.rates} loading={loading} market={market} />
            </div>
            
            {/* Spin animation */}
            <style jsx global>{`
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
}
