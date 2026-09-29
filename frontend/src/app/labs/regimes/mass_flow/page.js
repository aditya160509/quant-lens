'use client';

import { useState, Suspense, useCallback, useMemo, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';

const ResponsiveContainer = dynamic(() => import('recharts').then(m => m.ResponsiveContainer), { ssr: false });
const AreaChart = dynamic(() => import('recharts').then(m => m.AreaChart), { ssr: false });
const Area = dynamic(() => import('recharts').then(m => m.Area), { ssr: false });
const LineChart = dynamic(() => import('recharts').then(m => m.LineChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(m => m.Line), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(m => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(m => m.YAxis), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(m => m.Tooltip), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(m => m.CartesianGrid), { ssr: false });

// 3D Plot for regime visualization
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const THEME = {
    bg: '#0a0a0f',
    card: '#12121a',
    border: '#1e1e2e',
    text: '#e0e0e0',
    textMuted: '#888',
    accent: '#3b82f6',
    danger: '#ef4444',
    warning: '#f59e0b',
    us: '#3b82f6',
    india: '#f97316',
};

const STATE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'];
const STATE_NAMES = ['Calm', 'Elevated', 'Stressed', 'Crisis'];

const API_BASE = 'http://127.0.0.1:8000';

// FIXED REGIME UNIVERSES
const REGIME_UNIVERSES = {
    US: {
        label: 'US Macro Regime',
        color: THEME.us,
        benchmark: 'SPY',
        nodes: ['QQQ', 'IWM', 'TLT', 'IEF', 'SHY', 'LQD', 'HYG', 'GLD', 'USO'],
        tickers: ['SPY', 'QQQ', 'IWM', '^GSPC', '^IXIC', 'TLT', 'IEF', 'SHY', 'LQD', 'HYG', '^VIX', 'GLD', 'USO', 'EURUSD=X', 'JPY=X']
    },
    INDIA: {
        label: 'India Macro Regime',
        color: THEME.india,
        benchmark: '^NSEI',
        nodes: ['INDA', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'PFC.NS', 'RECLTD.NS'],
        tickers: ['^NSEI', 'INDA', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'PFC.NS', 'RECLTD.NS', 'USDINR=X', 'GLD', 'USO', '^VIX']
    }
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
                    color: color,
                    fontSize: '9px',
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

export default function MassFlowPage() {
    return (
        <Suspense fallback={<div style={{ background: '#0a0a0f', color: '#888', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>}>
            <MassFlowContent />
        </Suspense>
    );
}

function MassFlowContent() {
    const searchParams = useSearchParams();
    const modeFromUrl = searchParams.get('mode') || 'US';
    const tickerFromUrl = searchParams.get('ticker') || '';
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [windowYears, setWindowYears] = useState(2);
    const [view3D, setView3D] = useState(false);  // 3D visualization toggle
    
    // Regime mode (US or INDIA)
    const [regimeMode, setRegimeMode] = useState(modeFromUrl === 'CUSTOM' ? 'US' : modeFromUrl);
    
    // Custom ticker option (Mass Flow special feature)
    const [useCustomTicker, setUseCustomTicker] = useState(modeFromUrl === 'CUSTOM');
    const [customTicker, setCustomTicker] = useState(tickerFromUrl);
    
    // Auto-run if custom ticker from URL
    useEffect(() => {
        if (modeFromUrl === 'CUSTOM' && tickerFromUrl) {
            runAnalysis();
        }
    }, []); // Run once on mount
    
    const currentUniverse = REGIME_UNIVERSES[regimeMode];
    
    // Determine what ticker/universe to use
    const analysisTarget = useMemo(() => {
        if (useCustomTicker && customTicker.trim()) {
            return {
                type: 'custom',
                benchmark: customTicker.trim().toUpperCase(),
                nodes: [],
                label: customTicker.trim().toUpperCase()
            };
        }
        return {
            type: 'regime',
            benchmark: currentUniverse.benchmark,
            nodes: currentUniverse.nodes,
            label: `${regimeMode} Regime`
        };
    }, [useCustomTicker, customTicker, regimeMode, currentUniverse]);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/labs/regimes/mass_flow`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    benchmark: analysisTarget.benchmark,
                    nodes: analysisTarget.nodes.length > 0 ? analysisTarget.nodes : null,
                    window_years: windowYears
                })
            });
            if (!res.ok) throw new Error('Failed to compute mass flow');
            const result = await res.json();
            setData(result);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [windowYears, analysisTarget]);

    // Posterior chart data
    const posteriorData = useMemo(() => {
        if (!data?.timeline) return [];
        return data.timeline.map(t => ({
            date: t.t,
            massVel: t.massVel * 100,
            entropy: t.entropy * 100,
            state: t.stateId,
            ...t.probs.reduce((acc, p, i) => ({ ...acc, [`prob${i}`]: p * 100 }), {})
        }));
    }, [data]);

    // Current stats
    const currentStats = useMemo(() => {
        if (!data?.timeline?.length) return null;
        const latest = data.timeline[data.timeline.length - 1];
        const stateLabel = data.stateLabels?.find(s => s.stateId === latest.stateId);
        return {
            state: stateLabel?.name || `State ${latest.stateId}`,
            stateColor: STATE_COLORS[latest.stateId] || THEME.accent,
            massVel: (latest.massVel * 100).toFixed(1),
            entropy: (latest.entropy * 100).toFixed(0),
            age: latest.age,
            exhaustPct: latest.exhaustPct.toFixed(0)
        };
    }, [data]);

    // 3D Surface data for probability mass flow visualization
    const surface3DData = useMemo(() => {
        if (!data?.timeline?.length) return null;
        
        const numDates = data.timeline.length;
        const sampleRate = Math.max(1, Math.floor(numDates / 100));
        const sampledTimeline = [];
        for (let i = 0; i < numDates; i += sampleRate) {
            sampledTimeline.push(data.timeline[i]);
        }
        
        // State axis (0-3 for each regime state)
        const stateAxis = [0, 1, 2, 3];
        
        // Z is the probability for each state at each time point
        const zData = stateAxis.map(stateIdx => {
            return sampledTimeline.map(t => (t.probs[stateIdx] || 0) * 100);
        });
        
        return {
            z: zData,
            x: sampledTimeline.map(t => t.t),
            y: STATE_NAMES,
            type: 'surface',
            colorscale: [
                [0, 'rgb(20, 40, 60)'],
                [0.25, 'rgb(16, 185, 129)'],   // Calm - green
                [0.5, 'rgb(59, 130, 246)'],    // Elevated - blue
                [0.75, 'rgb(245, 158, 11)'],   // Stressed - amber
                [1, 'rgb(239, 68, 68)']        // Crisis - red
            ],
            showscale: true,
            opacity: 0.95,
            lighting: {
                ambient: 0.6,
                diffuse: 0.7,
                specular: 0.3,
                roughness: 0.5,
                fresnel: 0.3
            },
            lightposition: { x: 1000, y: 1000, z: 1000 },
            colorbar: {
                title: { text: 'Probability %', font: { color: THEME.textMuted, size: 11 } },
                tickfont: { color: THEME.textMuted, size: 9 }
            },
            contours: {
                z: { show: true, usecolormap: true, highlightcolor: "#fff", project: { z: true } }
            }
        };
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
                    <span>🌊</span> Probability Mass Flow
                </h1>
                
                {/* Regime Mode Badge */}
                <div style={{
                    marginLeft: 'auto',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                }}>
                    <div style={{
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
                        onClick={() => { setRegimeMode('US'); setUseCustomTicker(false); }}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            border: 'none',
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            background: regimeMode === 'US' && !useCustomTicker ? THEME.us : 'transparent',
                            color: regimeMode === 'US' && !useCustomTicker ? '#fff' : THEME.textMuted,
                        }}
                    >
                        🇺🇸 US
                    </button>
                    <button
                        onClick={() => { setRegimeMode('INDIA'); setUseCustomTicker(false); }}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            border: 'none',
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            background: regimeMode === 'INDIA' && !useCustomTicker ? THEME.india : 'transparent',
                            color: regimeMode === 'INDIA' && !useCustomTicker ? '#fff' : THEME.textMuted,
                        }}
                    >
                        🇮🇳 INDIA
                    </button>
                    <button
                        onClick={() => setUseCustomTicker(true)}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            border: 'none',
                            fontFamily: 'monospace',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            background: useCustomTicker ? '#10b981' : 'transparent',
                            color: useCustomTicker ? '#fff' : THEME.textMuted,
                        }}
                    >
                        ✏️ CUSTOM
                    </button>
                </div>

                {/* Custom Ticker Input */}
                {useCustomTicker && (
                    <input
                        type="text"
                        value={customTicker}
                        onChange={(e) => setCustomTicker(e.target.value)}
                        placeholder="e.g. AAPL, RELIANCE.NS, BTC-USD"
                        style={{
                            background: THEME.bg,
                            border: `1px solid #10b98140`,
                            borderRadius: '4px',
                            color: THEME.text,
                            padding: '6px 12px',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            width: '220px'
                        }}
                    />
                )}

                {/* Window selector */}
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
                    disabled={loading || (useCustomTicker && !customTicker.trim())}
                    style={{
                        background: useCustomTicker ? '#10b981' : currentUniverse.color,
                        border: 'none',
                        borderRadius: '4px',
                        color: '#fff',
                        padding: '8px 20px',
                        fontSize: '11px',
                        fontWeight: 700,
                        fontFamily: 'monospace',
                        cursor: loading ? 'not-allowed' : 'pointer',
                        opacity: loading || (useCustomTicker && !customTicker.trim()) ? 0.5 : 1,
                        textTransform: 'uppercase'
                    }}
                >
                    {loading ? 'COMPUTING...' : 'ANALYZE'}
                </button>

                {/* 3D View Toggle */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '12px' }}>
                    <span style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace' }}>VIEW:</span>
                    <button
                        onClick={() => setView3D(false)}
                        style={{
                            padding: '4px 10px',
                            borderRadius: '4px',
                            border: `1px solid ${!view3D ? '#8b5cf6' : THEME.border}`,
                            background: !view3D ? '#8b5cf6' : 'transparent',
                            color: !view3D ? '#fff' : THEME.textMuted,
                            fontFamily: 'monospace',
                            fontSize: '10px',
                            fontWeight: 600,
                            cursor: 'pointer'
                        }}
                    >
                        2D
                    </button>
                    <button
                        onClick={() => setView3D(true)}
                        style={{
                            padding: '4px 10px',
                            borderRadius: '4px',
                            border: `1px solid ${view3D ? '#06b6d4' : THEME.border}`,
                            background: view3D ? '#06b6d4' : 'transparent',
                            color: view3D ? '#000' : THEME.textMuted,
                            fontFamily: 'monospace',
                            fontSize: '10px',
                            fontWeight: 600,
                            cursor: 'pointer'
                        }}
                    >
                        3D SURFACE
                    </button>
                </div>

                {/* Analysis target display */}
                <span style={{
                    marginLeft: 'auto',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                }}>
                    <span style={{ color: THEME.textMuted }}>ANALYZING: </span>
                    <span style={{ 
                        color: useCustomTicker ? '#10b981' : currentUniverse.color, 
                        fontWeight: 600 
                    }}>
                        {analysisTarget.label}
                    </span>
                </span>

                {data?.model && (
                    <span style={{
                        color: THEME.textMuted,
                        fontSize: '10px',
                        fontFamily: 'monospace'
                    }}>
                        {data.model.method} • {data.model.states} States
                    </span>
                )}
            </div>

            {/* Universe Tickers Display (when not custom) */}
            {!useCustomTicker && (
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
            )}

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
                        Select {useCustomTicker ? 'a custom ticker' : `${regimeMode} regime`} and click ANALYZE to run HMM detection
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
                            Fitting Hidden Markov Model on {analysisTarget.label}...
                        </div>
                    </div>
                )}

                {data && !loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Stats Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
                            <StatBox
                                label="Current Regime"
                                value={currentStats?.state}
                                color={currentStats?.stateColor}
                            />
                            <StatBox label="Mass Velocity" value={currentStats?.massVel} unit="%" color={THEME.warning} />
                            <StatBox label="Entropy" value={currentStats?.entropy} unit="%" />
                            <StatBox label="Regime Age" value={currentStats?.age} unit="days" />
                            <StatBox label="Exhaustion" value={currentStats?.exhaustPct} unit="%" badge="pctl" />
                        </div>

                        {/* Posterior Stacked Area / 3D Surface */}
                        <div style={{
                            background: THEME.card,
                            border: `1px solid ${THEME.border}`,
                            borderRadius: '8px',
                            padding: '20px'
                        }}>
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: '16px'
                            }}>
                                <div style={{
                                    color: useCustomTicker ? '#10b981' : currentUniverse.color,
                                    fontSize: '11px',
                                    fontFamily: 'monospace',
                                    textTransform: 'uppercase'
                                }}>
                                    {view3D ? '3D Probability Mass Surface' : 'Regime Posterior Probabilities'} • {analysisTarget.label}
                                </div>
                                {view3D && (
                                    <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace' }}>
                                        Drag to rotate • Scroll to zoom
                                    </div>
                                )}
                            </div>
                            
                            {!view3D ? (
                                // 2D Stacked Area Chart
                                <>
                                    <div style={{ height: 300 }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <AreaChart data={posteriorData}>
                                                <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                                <XAxis
                                                    dataKey="date"
                                                    tick={{ fill: THEME.textMuted, fontSize: 10 }}
                                                    tickFormatter={(v) => v.slice(5, 10)}
                                                    stroke={THEME.border}
                                                />
                                                <YAxis
                                                    domain={[0, 100]}
                                                    tick={{ fill: THEME.textMuted, fontSize: 10 }}
                                                    stroke={THEME.border}
                                                    tickFormatter={(v) => `${v}%`}
                                                />
                                                <Tooltip
                                                    contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }}
                                                />
                                                {STATE_NAMES.map((name, i) => (
                                                    <Area
                                                        key={i}
                                                        type="monotone"
                                                        dataKey={`prob${i}`}
                                                        stackId="1"
                                                        stroke={STATE_COLORS[i]}
                                                        fill={STATE_COLORS[i]}
                                                        fillOpacity={0.7}
                                                        name={name}
                                                    />
                                                ))}
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'center', gap: '24px', marginTop: '12px' }}>
                                        {STATE_NAMES.map((name, i) => (
                                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                <div style={{ width: '12px', height: '12px', borderRadius: '2px', background: STATE_COLORS[i] }} />
                                                <span style={{ color: THEME.textMuted, fontSize: '10px' }}>{name}</span>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                // 3D Surface Visualization
                                <div style={{ height: 450, width: '100%' }}>
                                    {surface3DData && (
                                        <Plot
                                            data={[surface3DData]}
                                            layout={{
                                                autosize: true,
                                                paper_bgcolor: 'transparent',
                                                plot_bgcolor: 'transparent',
                                                font: { color: THEME.textMuted, family: 'monospace', size: 10 },
                                                margin: { l: 0, r: 0, t: 0, b: 0 },
                                                scene: {
                                                    aspectmode: 'manual',
                                                    aspectratio: { x: 2.5, y: 1, z: 0.8 },
                                                    xaxis: { 
                                                        title: { text: 'Date', font: { size: 11, color: '#06b6d4' } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textMuted },
                                                        nticks: 10,
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    yaxis: { 
                                                        title: { text: 'Regime State', font: { size: 11, color: '#06b6d4' } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textMuted },
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    zaxis: { 
                                                        title: { text: 'Probability %', font: { size: 11, color: '#06b6d4' } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textMuted },
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    camera: {
                                                        eye: { x: 1.8, y: 1.5, z: 1.2 },
                                                        center: { x: 0, y: 0, z: -0.1 }
                                                    },
                                                    bgcolor: 'transparent',
                                                }
                                            }}
                                            style={{ width: '100%', height: '100%' }}
                                            useResizeHandler={true}
                                            config={{ 
                                                displayModeBar: true, 
                                                displaylogo: false,
                                                modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
                                                responsive: true
                                            }}
                                        />
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Mass Velocity & Entropy */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                            <div style={{
                                background: THEME.card,
                                border: `1px solid ${THEME.border}`,
                                borderRadius: '8px',
                                padding: '16px'
                            }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '12px' }}>
                                    Mass Velocity (Belief Migration)
                                </div>
                                <div style={{ height: 180 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={posteriorData.slice(-100)}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 9 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                            <YAxis tick={{ fill: THEME.textMuted, fontSize: 9 }} stroke={THEME.border} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                            <Line type="monotone" dataKey="massVel" stroke={THEME.warning} dot={false} strokeWidth={1.5} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div style={{
                                background: THEME.card,
                                border: `1px solid ${THEME.border}`,
                                borderRadius: '8px',
                                padding: '16px'
                            }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '12px' }}>
                                    Regime Entropy (Uncertainty)
                                </div>
                                <div style={{ height: 180 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={posteriorData.slice(-100)}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fill: THEME.textMuted, fontSize: 9 }} tickFormatter={(v) => v.slice(5, 10)} stroke={THEME.border} />
                                            <YAxis tick={{ fill: THEME.textMuted, fontSize: 9 }} stroke={THEME.border} domain={[0, 100]} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}`, fontSize: '10px' }} />
                                            <Line type="monotone" dataKey="entropy" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        {/* State Labels Table */}
                        {data.stateLabels && (
                            <div style={{
                                background: THEME.card,
                                border: `1px solid ${THEME.border}`,
                                borderRadius: '8px',
                                padding: '16px'
                            }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '12px' }}>
                                    Regime Characteristics
                                </div>
                                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                    <thead>
                                        <tr>
                                            <th style={{ textAlign: 'left', padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: THEME.textMuted, fontSize: '10px' }}>REGIME</th>
                                            <th style={{ textAlign: 'right', padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: THEME.textMuted, fontSize: '10px' }}>MEDIAN RV</th>
                                            <th style={{ textAlign: 'right', padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: THEME.textMuted, fontSize: '10px' }}>MEDIAN ILLIQ</th>
                                            <th style={{ textAlign: 'right', padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: THEME.textMuted, fontSize: '10px' }}>CORR ABS</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.stateLabels.map((label, i) => (
                                            <tr key={i}>
                                                <td style={{ padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: STATE_COLORS[label.stateId] || THEME.text, fontSize: '12px', fontFamily: 'monospace' }}>
                                                    {label.name}
                                                </td>
                                                <td style={{ padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: THEME.text, fontSize: '12px', textAlign: 'right', fontFamily: 'monospace' }}>
                                                    {(label.medianRV * 100).toFixed(1)}%
                                                </td>
                                                <td style={{ padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: THEME.text, fontSize: '12px', textAlign: 'right', fontFamily: 'monospace' }}>
                                                    {label.medianILLIQ.toFixed(2)}
                                                </td>
                                                <td style={{ padding: '8px', borderBottom: `1px solid ${THEME.border}`, color: THEME.text, fontSize: '12px', textAlign: 'right', fontFamily: 'monospace' }}>
                                                    {label.medianCorrAbs.toFixed(2)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* Methodology */}
                        <div style={{
                            background: `${useCustomTicker ? '#10b981' : currentUniverse.color}08`,
                            border: `1px solid ${useCustomTicker ? '#10b981' : currentUniverse.color}30`,
                            borderRadius: '8px',
                            padding: '16px'
                        }}>
                            <div style={{ color: useCustomTicker ? '#10b981' : currentUniverse.color, fontSize: '10px', fontFamily: 'monospace', textTransform: 'uppercase', marginBottom: '8px' }}>
                                Methodology
                            </div>
                            <div style={{ color: THEME.textMuted, fontSize: '11px', lineHeight: '1.6' }}>
                                Hidden Markov Model with 4 Gaussian states fitted on [ln(RV20), Δln(RV20), corrAbsAvg60, z(ILLIQ)].
                                Mass velocity = 0.5×Σ|p_k(t) - p_k(t-1)|. Entropy normalized by ln(K).
                                Exhaustion percentile ranks current regime age against historical ages for that state.
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
