'use client';

import { useState, useCallback, useMemo, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { REGIME_UNIVERSES, THEME, API_BASE } from '../regimeConfig';

const ResponsiveContainer = dynamic(() => import('recharts').then(m => m.ResponsiveContainer), { ssr: false });
const AreaChart = dynamic(() => import('recharts').then(m => m.AreaChart), { ssr: false });
const Area = dynamic(() => import('recharts').then(m => m.Area), { ssr: false });
const LineChart = dynamic(() => import('recharts').then(m => m.LineChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(m => m.Line), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(m => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(m => m.YAxis), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(m => m.Tooltip), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(m => m.CartesianGrid), { ssr: false });
const ReferenceLine = dynamic(() => import('recharts').then(m => m.ReferenceLine), { ssr: false });

function StatBox({ label, value, unit, color = THEME.text }) {
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
        </div>
    );
}

// Wrapper component with Suspense for useSearchParams
export default function IntegrityPage() {
    return (
        <Suspense fallback={<div style={{ background: '#0a0a0f', color: '#888', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>}>
            <IntegrityContent />
        </Suspense>
    );
}

function IntegrityContent() {
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
            const res = await fetch(`${API_BASE}/api/labs/regimes/integrity`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    benchmark: currentUniverse.benchmark,
                    nodes: currentUniverse.nodes,
                    window_years: windowYears
                })
            });
            if (!res.ok) throw new Error('Failed to compute integrity');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [windowYears, currentUniverse]);

    const chartData = useMemo(() => {
        if (!data?.values) return [];
        return data.values.map(v => ({
            date: v.t,
            integrity: v.integrity,
            stressCore: v.stressCore * 100,
            agreement: v.agreement * 100
        }));
    }, [data]);

    const currentStats = useMemo(() => {
        if (!data?.values?.length) return null;
        const latest = data.values[data.values.length - 1];
        return {
            integrity: latest.integrity.toFixed(1),
            stressCore: (latest.stressCore * 100).toFixed(1),
            agreement: (latest.agreement * 100).toFixed(1),
            confidence: (latest.confidence * 100).toFixed(0)
        };
    }, [data]);

    const pinnedContributors = useMemo(() => {
        if (!data?.contributors || !pinnedTime) return null;
        return data.contributors.find(c => c.t === pinnedTime)?.items || null;
    }, [data, pinnedTime]);

    const getIntegrityColor = (val) => {
        if (val >= 65) return THEME.safe;
        if (val >= 40) return THEME.warning;
        return THEME.danger;
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
                <Link href="/labs/regimes" style={{
                    color: currentUniverse.color,
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    textDecoration: 'none'
                }}>
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
                    <span>🏛️</span> Structural Integrity Index
                </h1>
                
                {/* Regime Badge */}
                <div style={{
                    marginLeft: 'auto',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    background: `${currentUniverse.color}20`,
                    border: `1px solid ${currentUniverse.color}40`,
                }}>
                    <span style={{
                        color: currentUniverse.color,
                        fontSize: '11px',
                        fontWeight: 700,
                        fontFamily: 'monospace'
                    }}>
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
                    <button
                        onClick={() => setRegimeMode('US')}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            border: 'none',
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            background: regimeMode === 'US' ? THEME.us : 'transparent',
                            color: regimeMode === 'US' ? '#fff' : THEME.textMuted,
                        }}
                    >
                        🇺🇸 US
                    </button>
                    <button
                        onClick={() => setRegimeMode('INDIA')}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            border: 'none',
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            background: regimeMode === 'INDIA' ? THEME.india : 'transparent',
                            color: regimeMode === 'INDIA' ? '#fff' : THEME.textMuted,
                        }}
                    >
                        🇮🇳 INDIA
                    </button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace' }}>WINDOW:</span>
                    <select
                        value={windowYears}
                        onChange={(e) => setWindowYears(Number(e.target.value))}
                        style={{
                            background: THEME.bg,
                            border: `1px solid ${THEME.border}`,
                            borderRadius: '4px',
                            color: THEME.text,
                            padding: '6px 12px',
                            fontSize: '12px',
                            fontFamily: 'monospace'
                        }}
                    >
                        <option value={1}>1 Year</option>
                        <option value={2}>2 Years</option>
                        <option value={3}>3 Years</option>
                        <option value={5}>5 Years</option>
                    </select>
                </div>

                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    style={{
                        background: currentUniverse.color,
                        border: 'none',
                        borderRadius: '4px',
                        color: '#fff',
                        padding: '8px 20px',
                        fontSize: '11px',
                        fontWeight: 700,
                        fontFamily: 'monospace',
                        cursor: loading ? 'not-allowed' : 'pointer',
                        opacity: loading ? 0.5 : 1,
                        textTransform: 'uppercase',
                        letterSpacing: '1px'
                    }}
                >
                    {loading ? 'COMPUTING...' : 'ANALYZE'}
                </button>

                {data?.quality && (
                    <span style={{
                        marginLeft: 'auto',
                        background: data.quality.missingPct < 5 ? `${THEME.safe}20` : `${THEME.warning}20`,
                        color: data.quality.missingPct < 5 ? THEME.safe : THEME.warning,
                        fontSize: '10px',
                        fontFamily: 'monospace',
                        padding: '4px 8px',
                        borderRadius: '4px'
                    }}>
                        DATA: {(100 - data.quality.missingPct).toFixed(0)}%
                    </span>
                )}
            </div>

            {/* Universe Tickers Display */}
            <div style={{
                padding: '8px 20px',
                background: `${currentUniverse.color}08`,
                borderBottom: `1px solid ${THEME.border}`,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                flexWrap: 'wrap'
            }}>
                <span style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace' }}>
                    UNIVERSE:
                </span>
                {currentUniverse.tickers.map(t => (
                    <span key={t} style={{
                        background: THEME.card,
                        border: `1px solid ${THEME.border}`,
                        padding: '2px 8px',
                        borderRadius: '3px',
                        fontSize: '9px',
                        fontFamily: 'monospace',
                        color: t === currentUniverse.benchmark ? currentUniverse.color : THEME.text,
                        fontWeight: t === currentUniverse.benchmark ? 700 : 400
                    }}>
                        {t}
                    </span>
                ))}
            </div>

            {/* Main Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
                {error && (
                    <div style={{
                        background: `${THEME.danger}20`,
                        border: `1px solid ${THEME.danger}`,
                        borderRadius: '8px',
                        padding: '16px',
                        color: THEME.danger,
                        fontSize: '13px',
                        marginBottom: '20px'
                    }}>
                        {error}
                    </div>
                )}

                {!data && !loading && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '400px',
                        color: THEME.textMuted,
                        fontSize: '13px',
                        fontFamily: 'monospace'
                    }}>
                        Select {regimeMode} regime and click ANALYZE to compute Structural Integrity
                    </div>
                )}

                {loading && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '400px'
                    }}>
                        <div style={{ color: currentUniverse.color, fontSize: '13px', fontFamily: 'monospace' }}>
                            Computing structural integrity for {currentUniverse.label}...
                        </div>
                    </div>
                )}

                {data && !loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Stats Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                            <StatBox
                                label="Integrity"
                                value={currentStats?.integrity}
                                color={getIntegrityColor(parseFloat(currentStats?.integrity))}
                            />
                            <StatBox label="Stress Core" value={currentStats?.stressCore} unit="%" color={THEME.warning} />
                            <StatBox label="Agreement" value={currentStats?.agreement} unit="%" />
                            <StatBox label="Confidence" value={currentStats?.confidence} unit="%" color={THEME.safe} />
                        </div>

                        {/* Main Chart */}
                        <div style={{
                            background: THEME.card,
                            border: `1px solid ${THEME.border}`,
                            borderRadius: '8px',
                            padding: '20px'
                        }}>
                            <div style={{
                                color: currentUniverse.color,
                                fontSize: '11px',
                                fontFamily: 'monospace',
                                textTransform: 'uppercase',
                                marginBottom: '16px',
                                letterSpacing: '1px'
                            }}>
                                Integrity Index Timeline • {currentUniverse.label}
                            </div>
                            <div style={{ height: 350 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData} onClick={(e) => e?.activeLabel && setPinnedTime(e.activeLabel)}>
                                        <defs>
                                            <linearGradient id="integrityGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={THEME.safe} stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor={THEME.safe} stopOpacity={0}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 10 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                        <YAxis domain={[0, 100]} tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '4px', fontSize: '11px' }} />
                                        <ReferenceLine y={65} stroke={THEME.safe} strokeDasharray="3 3" strokeOpacity={0.5} />
                                        <ReferenceLine y={40} stroke={THEME.warning} strokeDasharray="3 3" strokeOpacity={0.5} />
                                        <Area type="monotone" dataKey="integrity" stroke={THEME.safe} fill="url(#integrityGrad)" strokeWidth={2} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'center', gap: '24px', marginTop: '12px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <div style={{ width: '12px', height: '3px', background: THEME.safe }} />
                                    <span style={{ color: THEME.textMuted, fontSize: '10px' }}>Healthy (≥65)</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <div style={{ width: '12px', height: '3px', background: THEME.warning }} />
                                    <span style={{ color: THEME.textMuted, fontSize: '10px' }}>Degrading (40-65)</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <div style={{ width: '12px', height: '3px', background: THEME.danger }} />
                                    <span style={{ color: THEME.textMuted, fontSize: '10px' }}>Broken (&lt;40)</span>
                                </div>
                            </div>
                        </div>

                        {/* Secondary Charts */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '16px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '12px' }}>
                                    Stress Core vs Agreement
                                </div>
                                <div style={{ height: 200 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={chartData.slice(-100)}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 9 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                            <YAxis tick={{ fill: THEME.textMuted, fontSize: 9 }} stroke={THEME.border} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                            <Line type="monotone" dataKey="stressCore" stroke={THEME.danger} dot={false} strokeWidth={1.5} name="Stress Core" />
                                            <Line type="monotone" dataKey="agreement" stroke={THEME.safe} dot={false} strokeWidth={1.5} name="Agreement" />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* Contributors Panel */}
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '16px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '12px' }}>
                                    Stress Contributors {pinnedTime && `@ ${pinnedTime}`}
                                </div>
                                {(pinnedContributors || data.contributors?.[data.contributors.length - 1]?.items)?.map((item, i) => (
                                    <div key={i} style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        padding: '8px 0',
                                        borderBottom: `1px solid ${THEME.border}`
                                    }}>
                                        <span style={{ color: THEME.text, fontSize: '12px', fontFamily: 'monospace' }}>
                                            {item.name}
                                        </span>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                            <span style={{
                                                color: item.z > 1 ? THEME.danger : item.z > 0 ? THEME.warning : THEME.safe,
                                                fontSize: '11px',
                                                fontFamily: 'monospace'
                                            }}>
                                                z={item.z.toFixed(2)}
                                            </span>
                                            <div style={{
                                                width: '60px',
                                                height: '4px',
                                                background: THEME.border,
                                                borderRadius: '2px',
                                                overflow: 'hidden'
                                            }}>
                                                <div style={{
                                                    width: `${Math.min(100, item.contribution * 500)}%`,
                                                    height: '100%',
                                                    background: item.z > 1 ? THEME.danger : THEME.warning
                                                }} />
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Methodology */}
                        <div style={{
                            background: `${currentUniverse.color}08`,
                            border: `1px solid ${currentUniverse.color}30`,
                            borderRadius: '8px',
                            padding: '16px'
                        }}>
                            <div style={{ color: currentUniverse.color, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '8px' }}>
                                Methodology
                            </div>
                            <div style={{ color: THEME.textMuted, fontSize: '11px', lineHeight: '1.6' }}>
                                Integrity = 100 × σ(b₀ - b₁×StressCore + b₂×Agreement). StressCore is the mean of 
                                positive z-scores across RV20, VoV20, CorrAbs, ILLIQ, and Drawdown. Agreement measures 
                                signal coherence. All z-scores use robust scaling with 252-day calibration.
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
