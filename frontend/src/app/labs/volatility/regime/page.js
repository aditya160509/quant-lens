"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { runVolRegime } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// 3D Plot for regime visualization
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280' };
const REGIME_COLORS = { 0: '#22c55e', 1: '#6b7280', 2: '#fbbf24', 3: '#ef4444' };
const REGIME_LABELS = ['Low', 'Normal', 'Elevated', 'Crisis'];

export default function RegimePage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [view3D, setView3D] = useState(false);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolRegime(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({
            date,
            crisis: (data.probabilities?.crisis?.[i] || 0) * 100,
            elevated: (data.probabilities?.elevated?.[i] || 0) * 100,
            normal: (data.probabilities?.normal?.[i] || 0) * 100,
            low: (data.probabilities?.low?.[i] || 0) * 100,
        }));
    }, [data]);

    // 3D Surface data for regime probability visualization
    const surface3DData = useMemo(() => {
        if (!data?.dates || !data?.probabilities) return null;
        
        const numDates = data.dates.length;
        const sampleRate = Math.max(1, Math.floor(numDates / 80));
        const sampledIndices = [];
        for (let i = 0; i < numDates; i += sampleRate) {
            sampledIndices.push(i);
        }
        
        // Z is probability for each regime at each time point
        const regimeTypes = ['low', 'normal', 'elevated', 'crisis'];
        const zData = regimeTypes.map(regime => {
            return sampledIndices.map(idx => (data.probabilities?.[regime]?.[idx] || 0) * 100);
        });
        
        return {
            z: zData,
            x: sampledIndices.map(i => data.dates[i]),
            y: REGIME_LABELS,
            type: 'surface',
            colorscale: [
                [0, 'rgb(20, 40, 60)'],
                [0.25, 'rgb(34, 197, 94)'],   // Low - green
                [0.5, 'rgb(107, 114, 128)'],  // Normal - gray
                [0.75, 'rgb(251, 191, 36)'],  // Elevated - yellow
                [1, 'rgb(239, 68, 68)']       // Crisis - red
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

    const currentRegime = data?.current?.regime ?? 1;

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>◈ Regime Classifier</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}><TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search equities..." /></div>
                <div className="flex items-center gap-2 px-3 py-1 border text-sm font-mono" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}><span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span></div>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border focus:outline-none" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={1}>1 Year</option><option value={2}>2 Years</option><option value={3}>3 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>{loading ? 'COMPUTING...' : 'APPLY'}</button>
                
                {/* 3D Toggle */}
                <div className="ml-auto flex items-center gap-2">
                    <span className="text-[10px] font-mono" style={{ color: THEME.textDim }}>VIEW:</span>
                    <button 
                        onClick={() => setView3D(false)} 
                        className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ 
                            background: !view3D ? '#8b5cf6' : 'transparent', 
                            color: !view3D ? '#fff' : THEME.textMuted,
                            border: `1px solid ${!view3D ? '#8b5cf6' : THEME.border}`
                        }}
                    >
                        2D
                    </button>
                    <button 
                        onClick={() => setView3D(true)} 
                        className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ 
                            background: view3D ? '#06b6d4' : 'transparent', 
                            color: view3D ? '#000' : THEME.textMuted,
                            border: `1px solid ${view3D ? '#06b6d4' : THEME.border}`
                        }}
                    >
                        3D SURFACE
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Classifying regimes...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="flex items-center gap-6">
                            <div className="px-6 py-4 rounded-lg font-mono font-bold text-2xl" style={{ background: `${REGIME_COLORS[currentRegime]}22`, color: REGIME_COLORS[currentRegime], border: `2px solid ${REGIME_COLORS[currentRegime]}` }}>
                                {REGIME_LABELS[currentRegime].toUpperCase()}
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Confidence</div>
                                <div className="text-2xl font-mono font-bold" style={{ color: THEME.text }}>{((data.current?.confidence || 0) * 100).toFixed(0)}%</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-xs font-mono uppercase" style={{ color: THEME.accent }}>
                                    {view3D ? '3D Regime Probability Surface' : 'Regime Probability Over Time'}
                                </div>
                                {view3D && (
                                    <div className="text-[10px] font-mono" style={{ color: THEME.textDim }}>
                                        Drag to rotate • Scroll to zoom
                                    </div>
                                )}
                            </div>
                            
                            {!view3D ? (
                                // 2D Stacked Area
                                <>
                                    <div style={{ height: 300 }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <AreaChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                                <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                                <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                                                <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                                                <Area type="monotone" dataKey="crisis" stackId="1" stroke={REGIME_COLORS[3]} fill={REGIME_COLORS[3]} fillOpacity={0.6} />
                                                <Area type="monotone" dataKey="elevated" stackId="1" stroke={REGIME_COLORS[2]} fill={REGIME_COLORS[2]} fillOpacity={0.6} />
                                                <Area type="monotone" dataKey="normal" stackId="1" stroke={REGIME_COLORS[1]} fill={REGIME_COLORS[1]} fillOpacity={0.6} />
                                                <Area type="monotone" dataKey="low" stackId="1" stroke={REGIME_COLORS[0]} fill={REGIME_COLORS[0]} fillOpacity={0.6} />
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <div className="flex items-center gap-4 mt-4 justify-center">
                                        {REGIME_LABELS.map((label, i) => (
                                            <div key={label} className="flex items-center gap-1">
                                                <div style={{ width: 10, height: 10, background: REGIME_COLORS[i], borderRadius: 2 }} />
                                                <span className="text-[9px] font-mono" style={{ color: THEME.textDim }}>{label}</span>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                // 3D Surface
                                <div style={{ height: 400, width: '100%' }}>
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
                                                        title: { text: 'Date', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
                                                        nticks: 10,
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    yaxis: { 
                                                        title: { text: 'Regime', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    zaxis: { 
                                                        title: { text: 'Probability %', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
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

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Classification Rules</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Low: RV20 percentile &lt; 15%</div>
                                <div>• Normal: 15% - 60%</div>
                                <div>• Elevated: 60% - 85%</div>
                                <div>• Crisis: &gt; 85%</div>
                                <div>• Smoothed with 5-day trailing mode</div>
                                {view3D && <div>• 3D Surface: Shows probability flow across all regimes over time</div>}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
