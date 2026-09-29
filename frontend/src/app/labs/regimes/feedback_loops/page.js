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

const LINK_COLORS = {
    'Return→Vol': '#3b82f6',
    'Vol→Illiq': '#f59e0b',
    'Illiq→Return': '#ef4444'
};

function StatBox({ label, value, unit, color = THEME.text, badge = null }) {
    return (
        <div style={{
            background: THEME.card,
            border: `1px solid ${THEME.border}`,
            borderRadius: '8px',
            padding: '16px',
            textAlign: 'center',
            position: 'relative'
        }}>
            {badge && (
                <div style={{
                    position: 'absolute',
                    top: '8px',
                    right: '8px',
                    background: `${color}20`,
                    color,
                    fontSize: '8px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontFamily: 'monospace'
                }}>
                    {badge}
                </div>
            )}
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

export default function FeedbackLoopsPage() {
    return (
        <Suspense fallback={<div style={{ background: '#0a0a0f', color: '#888', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>}>
            <FeedbackLoopsContent />
        </Suspense>
    );
}

function FeedbackLoopsContent() {
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
            const res = await fetch(`${API_BASE}/api/labs/regimes/feedback_loops`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    benchmark: currentUniverse.benchmark,
                    nodes: currentUniverse.nodes,
                    window_years: windowYears
                })
            });
            if (!res.ok) throw new Error('Failed to compute feedback loops');
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
            loopStrength: v.loopStrength * 100,
            amplification: v.amplification,
            dominantLink: v.dominantLink
        }));
    }, [data]);

    const currentStats = useMemo(() => {
        if (!data?.values?.length) return null;
        const latest = data.values[data.values.length - 1];
        return {
            loopStrength: (latest.loopStrength * 100).toFixed(1),
            amplification: latest.amplification.toFixed(1),
            dominantLink: latest.dominantLink,
            isAmplifying: latest.amplification > 50
        };
    }, [data]);

    const pinnedLinks = useMemo(() => {
        if (!data?.links || !pinnedTime) return null;
        return data.links.find(l => l.t === pinnedTime)?.items || null;
    }, [data, pinnedTime]);

    const latestLinks = useMemo(() => {
        if (!data?.links?.length) return [];
        return data.links[data.links.length - 1]?.items || [];
    }, [data]);

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
                    <span>🔄</span> Feedback Loop Closure
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
                    {loading ? 'COMPUTING...' : 'ANALYZE'}
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
                        Click ANALYZE to detect feedback loop closure
                    </div>
                )}

                {loading && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
                        <div style={{ color: currentUniverse.color, fontSize: '13px', fontFamily: 'monospace' }}>Analyzing feedback loops for {currentUniverse.label}...</div>
                    </div>
                )}

                {data && !loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Stats Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                            <StatBox label="Loop Strength" value={currentStats?.loopStrength} unit="%" color="#8b5cf6" />
                            <StatBox
                                label="Amplification"
                                value={currentStats?.amplification}
                                color={currentStats?.isAmplifying ? THEME.danger : THEME.safe}
                                badge={currentStats?.isAmplifying ? 'AMPLIFY' : 'DAMPEN'}
                            />
                            <StatBox label="Dominant Link" value={currentStats?.dominantLink?.replace('→', '→')} />
                            <div style={{
                                background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '16px',
                                display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}>
                                <div style={{
                                    fontSize: '11px', color: currentStats?.isAmplifying ? THEME.danger : THEME.safe, fontFamily: 'monospace', textAlign: 'center'
                                }}>
                                    {currentStats?.isAmplifying ? '⚠️ Positive Feedback' : '✓ Negative Feedback'}
                                    <div style={{ fontSize: '9px', color: THEME.textMuted, marginTop: '4px' }}>
                                        {currentStats?.isAmplifying ? 'Risk amplifying' : 'Self-correcting'}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Loop Diagram */}
                        <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                            <div style={{ color: currentUniverse.color, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '20px' }}>
                                Feedback Loop Structure • {currentUniverse.label}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '60px', padding: '20px 0' }}>
                                {/* Loop visualization */}
                                <div style={{ position: 'relative', width: '300px', height: '200px' }}>
                                    <div style={{ position: 'absolute', top: '0', left: '50%', transform: 'translateX(-50%)', background: LINK_COLORS['Return→Vol'], color: '#fff', padding: '12px 24px', borderRadius: '8px', fontSize: '12px', fontFamily: 'monospace', fontWeight: 600 }}>RETURNS</div>
                                    <div style={{ position: 'absolute', bottom: '0', left: '0', background: LINK_COLORS['Vol→Illiq'], color: '#000', padding: '12px 24px', borderRadius: '8px', fontSize: '12px', fontFamily: 'monospace', fontWeight: 600 }}>VOLATILITY</div>
                                    <div style={{ position: 'absolute', bottom: '0', right: '0', background: LINK_COLORS['Illiq→Return'], color: '#fff', padding: '12px 24px', borderRadius: '8px', fontSize: '12px', fontFamily: 'monospace', fontWeight: 600 }}>ILLIQUIDITY</div>
                                    <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                                        <defs>
                                            <marker id="arrow1" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill={LINK_COLORS['Return→Vol']} /></marker>
                                            <marker id="arrow2" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill={LINK_COLORS['Vol→Illiq']} /></marker>
                                            <marker id="arrow3" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill={LINK_COLORS['Illiq→Return']} /></marker>
                                        </defs>
                                        <line x1="120" y1="45" x2="60" y2="150" stroke={LINK_COLORS['Return→Vol']} strokeWidth="2" markerEnd="url(#arrow1)" />
                                        <line x1="100" y1="170" x2="190" y2="170" stroke={LINK_COLORS['Vol→Illiq']} strokeWidth="2" markerEnd="url(#arrow2)" />
                                        <line x1="240" y1="150" x2="180" y2="45" stroke={LINK_COLORS['Illiq→Return']} strokeWidth="2" markerEnd="url(#arrow3)" />
                                    </svg>
                                </div>

                                {/* Link correlations table */}
                                <div style={{ minWidth: '250px' }}>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', marginBottom: '12px' }}>
                                        LINK CORRELATIONS {pinnedTime && `@ ${pinnedTime}`}
                                    </div>
                                    {(pinnedLinks || latestLinks).map((link, i) => (
                                        <div key={i} style={{
                                            display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: `1px solid ${THEME.border}`
                                        }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: LINK_COLORS[link.name] || '#8b5cf6' }} />
                                                <span style={{ color: THEME.text, fontSize: '12px', fontFamily: 'monospace' }}>{link.name}</span>
                                            </div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                                <span style={{ color: link.corr > 0 ? THEME.danger : THEME.safe, fontSize: '13px', fontFamily: 'monospace', fontWeight: 600 }}>
                                                    {link.corr > 0 ? '+' : ''}{link.corr.toFixed(3)}
                                                </span>
                                                <span style={{ color: THEME.textMuted, fontSize: '10px' }}>lag {link.lagDays}d</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Amplification Timeline */}
                        <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                            <div style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                Amplification Score Timeline
                            </div>
                            <div style={{ height: 250 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData} onClick={(e) => e?.activeLabel && setPinnedTime(e.activeLabel)}>
                                        <defs>
                                            <linearGradient id="ampGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 10 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                        <YAxis domain={[0, 100]} tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                        <ReferenceLine y={50} stroke={THEME.warning} strokeDasharray="3 3" />
                                        <Area type="monotone" dataKey="amplification" stroke="#8b5cf6" fill="url(#ampGrad)" strokeWidth={2} />
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
                                Loop closure computed via lead-lag correlations over 60-day windows. Return→Vol: corr(r_t, ΔRV_t+1).
                                Vol→Illiq: corr(ΔRV_t, ΔILLIQ_t+1). Illiq→Return: corr(ΔILLIQ_t, r_t+1). Amplification = σ(g₁×LoopStrength + g₂×amplifyFlag).
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
