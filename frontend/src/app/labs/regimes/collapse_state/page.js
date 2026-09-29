'use client';

import { useState, Suspense, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { REGIME_UNIVERSES, THEME, API_BASE } from '../regimeConfig';

const ResponsiveContainer = dynamic(() => import('recharts').then(m => m.ResponsiveContainer), { ssr: false });
const LineChart = dynamic(() => import('recharts').then(m => m.LineChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(m => m.Line), { ssr: false });
const AreaChart = dynamic(() => import('recharts').then(m => m.AreaChart), { ssr: false });
const Area = dynamic(() => import('recharts').then(m => m.Area), { ssr: false });
const BarChart = dynamic(() => import('recharts').then(m => m.BarChart), { ssr: false });
const Bar = dynamic(() => import('recharts').then(m => m.Bar), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(m => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(m => m.YAxis), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(m => m.Tooltip), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(m => m.CartesianGrid), { ssr: false });
const ReferenceLine = dynamic(() => import('recharts').then(m => m.ReferenceLine), { ssr: false });
const Cell = dynamic(() => import('recharts').then(m => m.Cell), { ssr: false });

const STATE_CONFIG = {
    'Stable': { color: THEME.safe, icon: '✓', desc: 'System operating normally' },
    'Fragile': { color: THEME.warning, icon: '⚠', desc: 'Elevated risk conditions' },
    'Critical': { color: THEME.danger, icon: '🚨', desc: 'Extreme stress detected' }
};

const DRIVER_COLORS = {
    'Integrity': '#10b981',
    'MassVelocity': '#3b82f6',
    'Entropy': '#8b5cf6',
    'ReflexDenial': '#f59e0b',
    'Fragility': '#ef4444',
    'Amplification': '#ec4899',
    'Nonlinearity': '#fbbf24'
};

export default function CollapseStatePage() {
    return (
        <Suspense fallback={<div style={{ background: '#0a0a0f', color: '#888', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>}>
            <CollapseStateContent />
        </Suspense>
    );
}

function CollapseStateContent() {
    const searchParams = useSearchParams();
    const modeFromUrl = searchParams.get('mode') || 'US';
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [windowYears, setWindowYears] = useState(2);
    const [pinnedTime, setPinnedTime] = useState(null);
    const [regimeMode, setRegimeMode] = useState(modeFromUrl);
    
    const currentUniverse = REGIME_UNIVERSES[regimeMode];

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/labs/regimes/collapse_state`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    benchmark: currentUniverse.benchmark,
                    nodes: currentUniverse.nodes,
                    window_years: windowYears
                })
            });
            if (!res.ok) throw new Error('Failed to compute collapse state');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [windowYears, currentUniverse]);

    const chartData = useMemo(() => {
        if (!data?.collapseState?.values) return [];
        return data.collapseState.values.map(v => ({
            date: v.t,
            pressure: v.pressure * 100,
            pressureSmooth: v.pressureSmooth * 100,
            confidence: v.confidence * 100,
            state: v.state
        }));
    }, [data]);

    const currentStats = useMemo(() => {
        if (!data?.collapseState?.values?.length) return null;
        const latest = data.collapseState.values[data.collapseState.values.length - 1];
        return {
            state: latest.state,
            pressure: (latest.pressure * 100).toFixed(1),
            pressureSmooth: (latest.pressureSmooth * 100).toFixed(1),
            confidence: (latest.confidence * 100).toFixed(0)
        };
    }, [data]);

    const pinnedDrivers = useMemo(() => {
        if (!data?.collapseState?.drivers) return [];
        const drivers = pinnedTime
            ? data.collapseState.drivers.find(d => d.t === pinnedTime)?.items
            : data.collapseState.drivers[data.collapseState.drivers.length - 1]?.items;
        return drivers || [];
    }, [data, pinnedTime]);

    const driverChartData = useMemo(() => {
        return pinnedDrivers.map(d => ({
            name: d.name.replace(/([A-Z])/g, ' $1').trim().split(' ')[0],
            contribution: d.contribution * 100,
            value: d.value * 100,
            fullName: d.name
        }));
    }, [pinnedDrivers]);

    const stateHistory = useMemo(() => {
        if (!chartData.length) return [];
        const states = [];
        let currentState = chartData[0].state;
        let startIdx = 0;
        
        chartData.forEach((d, i) => {
            if (d.state !== currentState || i === chartData.length - 1) {
                states.push({
                    state: currentState,
                    startDate: chartData[startIdx].date,
                    endDate: chartData[i - 1]?.date || chartData[i].date,
                    days: i - startIdx
                });
                currentState = d.state;
                startIdx = i;
            }
        });
        return states.slice(-10);
    }, [chartData]);

    const stateConfig = STATE_CONFIG[currentStats?.state] || STATE_CONFIG['Stable'];

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                padding: '16px 20px',
                borderBottom: `1px solid ${THEME.border}`,
                background: THEME.card
            }}>
                <Link href="/labs/regimes" style={{ color: currentUniverse.color, fontSize: '12px', fontFamily: 'monospace', textDecoration: 'none' }}>
                    ← REGIMES HUB
                </Link>
                <div style={{ width: '1px', height: '16px', background: THEME.border }} />
                <h1 style={{
                    color: THEME.text,
                    fontSize: '14px',
                    fontWeight: 700,
                    fontFamily: 'monospace',
                    textTransform: 'uppercase',
                    margin: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                }}>
                    <span>👑</span> Collapse State Governor
                </h1>
                
                <div style={{
                    marginLeft: 'auto',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    background: `${currentUniverse.color}20`,
                    border: `1px solid ${currentUniverse.color}40`,
                }}>
                    <span style={{ color: currentUniverse.color, fontSize: '11px', fontWeight: 700, fontFamily: 'monospace' }}>
                        {regimeMode === 'US' ? '🇺🇸' : '🇮🇳'} {currentUniverse.label}
                    </span>
                </div>
            </div>

            {/* Controls */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                padding: '12px 20px',
                borderBottom: `1px solid ${THEME.border}`,
                background: THEME.card,
                flexWrap: 'wrap'
            }}>
                {/* Mode Toggle */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    background: THEME.bg,
                    borderRadius: '6px',
                    padding: '2px'
                }}>
                    <button onClick={() => setRegimeMode('US')} style={{
                        padding: '6px 12px', borderRadius: '4px', border: 'none', fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, cursor: 'pointer',
                        background: regimeMode === 'US' ? THEME.us : 'transparent', color: regimeMode === 'US' ? '#fff' : THEME.textMuted,
                    }}>🇺🇸 US</button>
                    <button onClick={() => setRegimeMode('INDIA')} style={{
                        padding: '6px 12px', borderRadius: '4px', border: 'none', fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, cursor: 'pointer',
                        background: regimeMode === 'INDIA' ? THEME.india : 'transparent', color: regimeMode === 'INDIA' ? '#fff' : THEME.textMuted,
                    }}>🇮🇳 INDIA</button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace' }}>WINDOW:</span>
                    <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} style={{
                        background: THEME.bg, border: `1px solid ${THEME.border}`, borderRadius: '4px', color: THEME.text, padding: '6px 12px', fontSize: '12px', fontFamily: 'monospace'
                    }}>
                        <option value={1}>1 Year</option>
                        <option value={2}>2 Years</option>
                        <option value={3}>3 Years</option>
                    </select>
                </div>

                <button onClick={runAnalysis} disabled={loading} style={{
                    background: currentUniverse.color, border: 'none', borderRadius: '4px', color: '#fff', padding: '8px 20px', fontSize: '11px', fontWeight: 700, fontFamily: 'monospace',
                    cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.5 : 1, textTransform: 'uppercase'
                }}>
                    {loading ? 'COMPUTING...' : 'RUN FULL ENGINE'}
                </button>
            </div>

            {/* Universe Display */}
            <div style={{
                padding: '8px 20px', background: `${currentUniverse.color}08`, borderBottom: `1px solid ${THEME.border}`,
                display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap'
            }}>
                <span style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace' }}>UNIVERSE:</span>
                {currentUniverse.tickers.map(t => (
                    <span key={t} style={{
                        background: THEME.card, border: `1px solid ${THEME.border}`, padding: '2px 8px', borderRadius: '3px', fontSize: '9px', fontFamily: 'monospace',
                        color: t === currentUniverse.benchmark ? currentUniverse.color : THEME.text, fontWeight: t === currentUniverse.benchmark ? 700 : 400
                    }}>{t}</span>
                ))}
            </div>

            {/* Main Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
                {error && (
                    <div style={{ background: `${THEME.danger}20`, border: `1px solid ${THEME.danger}`, borderRadius: '8px', padding: '16px', color: THEME.danger, fontSize: '13px', marginBottom: '20px' }}>
                        {error}
                    </div>
                )}

                {!data && !loading && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', color: THEME.textMuted, fontSize: '13px', fontFamily: 'monospace' }}>
                        Click RUN FULL ENGINE to compute Collapse State Governor
                    </div>
                )}

                {loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px', gap: '16px' }}>
                        <div style={{ color: currentUniverse.color, fontSize: '13px', fontFamily: 'monospace' }}>Running all 7 crown primitives for {currentUniverse.label}...</div>
                        <div style={{ color: THEME.textMuted, fontSize: '11px' }}>Synthesizing collapse state</div>
                    </div>
                )}

                {data && !loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* State Banner */}
                        <div style={{
                            background: `${stateConfig.color}15`,
                            border: `2px solid ${stateConfig.color}`,
                            borderRadius: '12px',
                            padding: '24px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '24px'
                        }}>
                            <div style={{
                                width: '80px', height: '80px', borderRadius: '50%', background: `${stateConfig.color}20`, border: `3px solid ${stateConfig.color}`,
                                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '32px'
                            }}>
                                {stateConfig.icon}
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{
                                    color: stateConfig.color, fontSize: '28px', fontWeight: 700, fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '2px'
                                }}>
                                    {currentStats?.state}
                                </div>
                                <div style={{ color: THEME.textMuted, fontSize: '13px', marginTop: '4px' }}>
                                    {stateConfig.desc} • {currentUniverse.label}
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: '32px' }}>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace' }}>PRESSURE</div>
                                    <div style={{ color: THEME.text, fontSize: '24px', fontWeight: 700, fontFamily: 'monospace' }}>
                                        {currentStats?.pressureSmooth}%
                                    </div>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace' }}>CONFIDENCE</div>
                                    <div style={{ color: THEME.text, fontSize: '24px', fontWeight: 700, fontFamily: 'monospace' }}>
                                        {currentStats?.confidence}%
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Main Chart with State Ribbon */}
                        <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                            <div style={{ color: currentUniverse.color, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                Collapse Pressure Timeline • {currentUniverse.label}
                            </div>
                            <div style={{ height: 280 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData} onClick={(e) => e?.activeLabel && setPinnedTime(e.activeLabel)}>
                                        <defs>
                                            <linearGradient id="pressureGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor="#fbbf24" stopOpacity={0}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 10 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                        <YAxis domain={[0, 100]} tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                        <ReferenceLine y={33} stroke={THEME.safe} strokeDasharray="3 3" />
                                        <ReferenceLine y={66} stroke={THEME.danger} strokeDasharray="3 3" />
                                        <Area type="monotone" dataKey="pressureSmooth" stroke="#fbbf24" fill="url(#pressureGrad)" strokeWidth={2} name="Pressure (Smooth)" />
                                        <Line type="monotone" dataKey="confidence" stroke="#8b5cf6" dot={false} strokeWidth={1} strokeOpacity={0.5} name="Confidence" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                            {/* State ribbon */}
                            <div style={{ display: 'flex', height: '24px', marginTop: '8px', borderRadius: '4px', overflow: 'hidden' }}>
                                {chartData.slice(-100).map((d, i) => (
                                    <div key={i} style={{
                                        flex: 1,
                                        background: STATE_CONFIG[d.state]?.color || THEME.safe,
                                        opacity: 0.8
                                    }} title={`${d.date}: ${d.state}`} />
                                ))}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'center', gap: '24px', marginTop: '8px' }}>
                                {Object.entries(STATE_CONFIG).map(([name, cfg]) => (
                                    <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                        <div style={{ width: '12px', height: '12px', borderRadius: '2px', background: cfg.color }} />
                                        <span style={{ color: THEME.textMuted, fontSize: '10px' }}>{name}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Driver Contributions */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                    Driver Contributions {pinnedTime && `@ ${pinnedTime}`}
                                </div>
                                <div style={{ height: 220 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={driverChartData} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis type="number" tick={{ fill: THEME.textMuted, fontSize: 9 }} stroke={THEME.border} />
                                            <YAxis dataKey="name" type="category" tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border} width={80} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                            <Bar dataKey="contribution" radius={[0, 4, 4, 0]}>
                                                {driverChartData.map((entry, i) => (
                                                    <Cell key={i} fill={DRIVER_COLORS[entry.fullName] || '#fbbf24'} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* Recent State Changes */}
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                    Recent State Transitions
                                </div>
                                <div style={{ maxHeight: '220px', overflow: 'auto' }}>
                                    {stateHistory.map((s, i) => (
                                        <div key={i} style={{
                                            display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 0', borderBottom: `1px solid ${THEME.border}`
                                        }}>
                                            <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: STATE_CONFIG[s.state]?.color }} />
                                            <div style={{ flex: 1 }}>
                                                <div style={{ color: STATE_CONFIG[s.state]?.color, fontSize: '12px', fontFamily: 'monospace', fontWeight: 600 }}>
                                                    {s.state}
                                                </div>
                                                <div style={{ color: THEME.textMuted, fontSize: '10px' }}>
                                                    {s.startDate.slice(5)} → {s.endDate.slice(5)}
                                                </div>
                                            </div>
                                            <div style={{ color: THEME.text, fontSize: '11px', fontFamily: 'monospace' }}>
                                                {s.days} days
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Methodology */}
                        <div style={{ background: `${currentUniverse.color}08`, border: `1px solid ${currentUniverse.color}30`, borderRadius: '8px', padding: '16px' }}>
                            <div style={{ color: currentUniverse.color, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '8px' }}>
                                Methodology
                            </div>
                            <div style={{ color: THEME.textMuted, fontSize: '11px', lineHeight: '1.6' }}>
                                Collapse Pressure = weighted sum of 7 normalized primitives: Integrity(1-I), MassVelocity, Entropy,
                                ReflexDenial, Fragility, Amplification, Nonlinearity. State thresholds: Stable &lt;33%, Fragile 33-66%, Critical &gt;66%.
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
