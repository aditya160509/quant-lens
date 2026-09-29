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
const XAxis = dynamic(() => import('recharts').then(m => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(m => m.YAxis), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(m => m.Tooltip), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(m => m.CartesianGrid), { ssr: false });
const ReferenceLine = dynamic(() => import('recharts').then(m => m.ReferenceLine), { ssr: false });

function StatBox({ label, value, unit, color = THEME.text, subtext = null }) {
    return (
        <div style={{
            background: THEME.card,
            border: `1px solid ${THEME.border}`,
            borderRadius: '8px',
            padding: '16px',
            textAlign: 'center'
        }}>
            <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '8px' }}>
                {label}
            </div>
            <div style={{ color, fontSize: '24px', fontWeight: 700, fontFamily: 'monospace' }}>
                {value}
                {unit && <span style={{ fontSize: '12px', color: THEME.textMuted, marginLeft: '4px' }}>{unit}</span>}
            </div>
            {subtext && <div style={{ color: THEME.textMuted, fontSize: '9px', marginTop: '4px' }}>{subtext}</div>}
        </div>
    );
}

export default function NonlinearityPage() {
    return (
        <Suspense fallback={<div style={{ background: '#0a0a0f', color: '#888', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>}>
            <NonlinearityContent />
        </Suspense>
    );
}

function NonlinearityContent() {
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
            const res = await fetch(`${API_BASE}/api/labs/regimes/nonlinearity`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    benchmark: currentUniverse.benchmark,
                    nodes: currentUniverse.nodes,
                    window_years: windowYears
                })
            });
            if (!res.ok) throw new Error('Failed to compute nonlinearity');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [windowYears, currentUniverse]);

    const timelineData = useMemo(() => {
        if (!data?.values) return [];
        return data.values.map(v => ({
            date: v.t,
            nonlinearity: v.nonlinearity,
            breakThreshold: v.breakThreshold
        }));
    }, [data]);

    const currentStats = useMemo(() => {
        if (!data?.values?.length) return null;
        const latest = data.values[data.values.length - 1];
        return {
            nonlinearity: latest.nonlinearity.toFixed(1),
            breakThreshold: latest.breakThreshold.toFixed(2),
            damageCrit: (latest.damageCrit * 100).toFixed(1),
            units: latest.units
        };
    }, [data]);

    const pinnedCurve = useMemo(() => {
        if (!data?.curves) return null;
        if (pinnedTime) {
            return data.curves.find(c => c.t === pinnedTime);
        }
        return data.curves[data.curves.length - 1];
    }, [data, pinnedTime]);

    const curveData = useMemo(() => {
        if (!pinnedCurve) return [];
        return pinnedCurve.shockSizes.map((s, i) => ({
            shock: s,
            breakProb: pinnedCurve.breakProb[i] * 100
        }));
    }, [pinnedCurve]);

    const getProximityColor = (val) => {
        if (val >= 70) return THEME.danger;
        if (val >= 40) return THEME.warning;
        return THEME.safe;
    };

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
                    <span>⚡</span> Nonlinearity Proximity
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
                    {loading ? 'SIMULATING...' : 'RUN BOOTSTRAP'}
                </button>

                {data?.simulation && (
                    <span style={{ marginLeft: 'auto', color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace' }}>
                        {data.simulation.paths || 500} paths × {data.simulation.horizonDays || 20} days
                    </span>
                )}
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
                        Click RUN BOOTSTRAP to compute break threshold via simulation
                    </div>
                )}

                {loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px', gap: '16px' }}>
                        <div style={{ color: currentUniverse.color, fontSize: '13px', fontFamily: 'monospace' }}>Running bootstrap simulation for {currentUniverse.label}...</div>
                        <div style={{ color: THEME.textMuted, fontSize: '11px' }}>500 paths with block resampling</div>
                    </div>
                )}

                {data && !loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Stats Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                            <StatBox
                                label="Nonlinearity Proximity"
                                value={currentStats?.nonlinearity}
                                color={getProximityColor(parseFloat(currentStats?.nonlinearity))}
                                subtext="Higher = closer to break"
                            />
                            <StatBox
                                label="Break Threshold"
                                value={currentStats?.breakThreshold}
                                unit="%"
                                color={parseFloat(currentStats?.breakThreshold) < 1 ? THEME.danger : THEME.safe}
                                subtext="Shock size for 50% break prob"
                            />
                            <StatBox label="Damage Critical" value={currentStats?.damageCrit} unit="%" subtext="95th pctl historical" />
                            <div style={{
                                background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '16px',
                                display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}>
                                <div style={{
                                    fontSize: '11px', color: parseFloat(currentStats?.breakThreshold) < 1 ? THEME.danger : THEME.safe, fontFamily: 'monospace', textAlign: 'center'
                                }}>
                                    {parseFloat(currentStats?.breakThreshold) < 1 ? '⚠️ LOW THRESHOLD' : '✓ STABLE'}
                                    <div style={{ fontSize: '9px', color: THEME.textMuted, marginTop: '4px' }}>
                                        {parseFloat(currentStats?.breakThreshold) < 1 ? 'Vulnerable to small shocks' : 'Resilient structure'}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Main Charts */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                            {/* Break Probability Curve */}
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                                <div style={{ color: currentUniverse.color, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                    Break Probability Curve • {currentUniverse.label}
                                </div>
                                <div style={{ height: 280 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={curveData}>
                                            <defs>
                                                <linearGradient id="breakGrad" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#ec4899" stopOpacity={0.4}/>
                                                    <stop offset="95%" stopColor="#ec4899" stopOpacity={0}/>
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="shock" tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border} tickFormatter={(v) => `${v}%`} />
                                            <YAxis domain={[0, 100]} tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border} tickFormatter={(v) => `${v}%`} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} formatter={(val) => [`${val.toFixed(1)}%`, 'Break Prob']} />
                                            <ReferenceLine y={50} stroke={THEME.warning} strokeDasharray="3 3" />
                                            <Area type="monotone" dataKey="breakProb" stroke="#ec4899" fill="url(#breakGrad)" strokeWidth={2} />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                                <div style={{ textAlign: 'center', color: THEME.textMuted, fontSize: '9px', marginTop: '8px' }}>
                                    Horizontal line = 50% break probability threshold
                                </div>
                            </div>

                            {/* Break Threshold Timeline */}
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                    Break Threshold Timeline
                                </div>
                                <div style={{ height: 280 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={timelineData} onClick={(e) => e?.activeLabel && setPinnedTime(e.activeLabel)}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 10 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                            <YAxis tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border} domain={[0, 'auto']} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                            <ReferenceLine y={1} stroke={THEME.danger} strokeDasharray="3 3" />
                                            <Line type="monotone" dataKey="breakThreshold" stroke="#ec4899" dot={false} strokeWidth={2} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                                <div style={{ textAlign: 'center', color: THEME.textMuted, fontSize: '9px', marginTop: '8px' }}>
                                    Click to pin a date and view its break curve
                                </div>
                            </div>
                        </div>

                        {/* Nonlinearity Timeline */}
                        <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '16px' }}>
                            <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '12px' }}>
                                Nonlinearity Proximity (0-100)
                            </div>
                            <div style={{ height: 160 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={timelineData}>
                                        <defs>
                                            <linearGradient id="nlGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={THEME.danger} stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor={THEME.danger} stopOpacity={0}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 9 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                        <YAxis domain={[0, 100]} tick={{ fill: THEME.textMuted, fontSize: 9 }} stroke={THEME.border} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                        <Area type="monotone" dataKey="nonlinearity" stroke={THEME.danger} fill="url(#nlGrad)" strokeWidth={1.5} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Methodology */}
                        <div style={{ background: `${currentUniverse.color}08`, border: `1px solid ${currentUniverse.color}30`, borderRadius: '8px', padding: '16px' }}>
                            <div style={{ color: currentUniverse.color, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '8px' }}>
                                Methodology
                            </div>
                            <div style={{ color: THEME.textMuted, fontSize: '11px', lineHeight: '1.6' }}>
                                Block bootstrap with 5-day blocks from 252-day return pool. 500 paths simulated per shock size.
                                BreakThreshold = smallest shock where P(Damage &gt; DamageCrit) ≥ 50%. Nonlinearity = 100 × (1 - percentileRank(BreakThreshold)).
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
