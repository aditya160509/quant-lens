'use client';

import { useState, Suspense, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { REGIME_UNIVERSES, THEME, API_BASE } from '../regimeConfig';

const ResponsiveContainer = dynamic(() => import('recharts').then(m => m.ResponsiveContainer), { ssr: false });
const ScatterChart = dynamic(() => import('recharts').then(m => m.ScatterChart), { ssr: false });
const Scatter = dynamic(() => import('recharts').then(m => m.Scatter), { ssr: false });
const LineChart = dynamic(() => import('recharts').then(m => m.LineChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(m => m.Line), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(m => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(m => m.YAxis), { ssr: false });
const ZAxis = dynamic(() => import('recharts').then(m => m.ZAxis), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(m => m.Tooltip), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(m => m.CartesianGrid), { ssr: false });
const ReferenceLine = dynamic(() => import('recharts').then(m => m.ReferenceLine), { ssr: false });
const Cell = dynamic(() => import('recharts').then(m => m.Cell), { ssr: false });

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

export default function FragilityPage() {
    return (
        <Suspense fallback={<div style={{ background: '#0a0a0f', color: '#888', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>}>
            <FragilityContent />
        </Suspense>
    );
}

function FragilityContent() {
    const searchParams = useSearchParams();
    const modeFromUrl = searchParams.get('mode') || 'US';
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [windowYears, setWindowYears] = useState(2);
    const [regimeMode, setRegimeMode] = useState(modeFromUrl);
    
    const currentUniverse = REGIME_UNIVERSES[regimeMode];

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/labs/regimes/fragility`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    benchmark: currentUniverse.benchmark,
                    nodes: currentUniverse.nodes,
                    window_years: windowYears
                })
            });
            if (!res.ok) throw new Error('Failed to compute fragility');
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
            fragility: v.fragility,
            liquidityAxis: v.liquidityAxis,
            leverageAxis: v.leverageAxis,
            corrStress: v.corrStress
        }));
    }, [data]);

    const scatterData = useMemo(() => {
        if (!data?.stateSpace) return [];
        return data.stateSpace.slice(-252).map(s => ({
            x: s.x,
            y: s.y,
            z: s.fragility,
            date: s.t
        }));
    }, [data]);

    const currentStats = useMemo(() => {
        if (!data?.values?.length) return null;
        const latest = data.values[data.values.length - 1];
        
        let quadrant = 'Normal';
        if (latest.liquidityAxis > 1 && latest.leverageAxis > 1) quadrant = 'Both Crisis';
        else if (latest.liquidityAxis > 1) quadrant = 'Liquidity Crisis';
        else if (latest.leverageAxis > 1) quadrant = 'Leverage Stress';
        
        return {
            fragility: latest.fragility.toFixed(1),
            liquidityAxis: latest.liquidityAxis.toFixed(2),
            leverageAxis: latest.leverageAxis.toFixed(2),
            corrStress: latest.corrStress.toFixed(2),
            quadrant
        };
    }, [data]);

    const getFragilityColor = (val) => {
        if (val >= 65) return THEME.danger;
        if (val >= 40) return THEME.warning;
        return THEME.safe;
    };

    const getQuadrantColor = (q) => {
        if (q === 'Both Crisis') return THEME.danger;
        if (q === 'Liquidity Crisis' || q === 'Leverage Stress') return THEME.warning;
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
                    <span>💎</span> Liquidity & Leverage Fragility
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
                        Click ANALYZE to compute Fragility Surface
                    </div>
                )}

                {loading && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
                        <div style={{ color: currentUniverse.color, fontSize: '13px', fontFamily: 'monospace' }}>Computing fragility surface...</div>
                    </div>
                )}

                {data && !loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Stats Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
                            <StatBox label="Fragility" value={currentStats?.fragility} color={getFragilityColor(parseFloat(currentStats?.fragility))} />
                            <StatBox label="Liquidity Axis" value={currentStats?.liquidityAxis} unit="z" />
                            <StatBox label="Leverage Axis" value={currentStats?.leverageAxis} unit="z" />
                            <StatBox label="Corr Stress" value={currentStats?.corrStress} unit="z" />
                            <StatBox label="Quadrant" value={currentStats?.quadrant} color={getQuadrantColor(currentStats?.quadrant)} />
                        </div>

                        {/* Main Charts Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                            {/* State Space Scatter */}
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                                <div style={{ color: currentUniverse.color, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                    State Space (Liquidity × Leverage) • {currentUniverse.label}
                                </div>
                                <div style={{ height: 320 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis type="number" dataKey="x" name="Liquidity" domain={[-3, 3]} tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border}
                                                label={{ value: 'Liquidity Stress →', position: 'bottom', fill: THEME.textMuted, fontSize: 10 }} />
                                            <YAxis type="number" dataKey="y" name="Leverage" domain={[-3, 3]} tick={{ fill: THEME.textMuted, fontSize: 10 }} stroke={THEME.border}
                                                label={{ value: 'Leverage Sensitivity →', angle: -90, position: 'left', fill: THEME.textMuted, fontSize: 10 }} />
                                            <ZAxis type="number" dataKey="z" range={[20, 200]} />
                                            <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }}
                                                formatter={(val, name) => [val.toFixed(2), name]} />
                                            <ReferenceLine x={0} stroke={THEME.border} />
                                            <ReferenceLine y={0} stroke={THEME.border} />
                                            <ReferenceLine x={1} stroke={THEME.warning} strokeDasharray="3 3" strokeOpacity={0.5} />
                                            <ReferenceLine y={1} stroke={THEME.warning} strokeDasharray="3 3" strokeOpacity={0.5} />
                                            <Scatter name="State Space" data={scatterData}>
                                                {scatterData.map((entry, i) => (
                                                    <Cell key={`cell-${i}`}
                                                        fill={entry.z >= 65 ? THEME.danger : entry.z >= 40 ? THEME.warning : THEME.safe}
                                                        fillOpacity={0.7} />
                                                ))}
                                            </Scatter>
                                        </ScatterChart>
                                    </ResponsiveContainer>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '8px' }}>
                                    <span style={{ color: THEME.textMuted, fontSize: '9px' }}>🟢 Fragility &lt;40</span>
                                    <span style={{ color: THEME.textMuted, fontSize: '9px' }}>🟡 40-65</span>
                                    <span style={{ color: THEME.textMuted, fontSize: '9px' }}>🔴 ≥65</span>
                                </div>
                            </div>

                            {/* Fragility Timeline */}
                            <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '20px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '11px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '16px' }}>
                                    Fragility Timeline
                                </div>
                                <div style={{ height: 320 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={timelineData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 9 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                            <YAxis domain={[0, 100]} tick={{ fill: THEME.textMuted, fontSize: 9 }} stroke={THEME.border} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                            <ReferenceLine y={65} stroke={THEME.danger} strokeDasharray="3 3" strokeOpacity={0.5} />
                                            <ReferenceLine y={40} stroke={THEME.warning} strokeDasharray="3 3" strokeOpacity={0.5} />
                                            <Line type="monotone" dataKey="fragility" stroke={THEME.danger} dot={false} strokeWidth={2} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        {/* Component Lines */}
                        <div style={{ background: THEME.card, border: `1px solid ${THEME.border}`, borderRadius: '8px', padding: '16px' }}>
                            <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '12px' }}>
                                Axis Components
                            </div>
                            <div style={{ height: 180 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={timelineData.slice(-150)}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                        <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 9 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                        <YAxis tick={{ fill: THEME.textMuted, fontSize: 9 }} stroke={THEME.border} />
                                        <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                        <Line type="monotone" dataKey="liquidityAxis" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="Liquidity" />
                                        <Line type="monotone" dataKey="leverageAxis" stroke="#8b5cf6" dot={false} strokeWidth={1.5} name="Leverage" />
                                        <Line type="monotone" dataKey="corrStress" stroke={THEME.warning} dot={false} strokeWidth={1.5} name="CorrStress" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Methodology */}
                        <div style={{ background: `${currentUniverse.color}08`, border: `1px solid ${currentUniverse.color}30`, borderRadius: '8px', padding: '16px' }}>
                            <div style={{ color: currentUniverse.color, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '8px' }}>
                                Methodology
                            </div>
                            <div style={{ color: THEME.textMuted, fontSize: '11px', lineHeight: '1.6' }}>
                                Fragility = σ(f₁×LiquidityAxis + f₂×LeverageAxis + f₃×CorrStress). Liquidity = z(ILLIQ₂₀).
                                Leverage = z(RV₂₀ × VoV₂₀). State space maps mechanical failure risk with quadrants.
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
