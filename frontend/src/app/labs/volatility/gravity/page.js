"use client";

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { runVolGravity } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Dynamic import for Plotly (heavy library - client only)
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const THEME = { 
    bg: '#010409', 
    card: '#0d1117', 
    border: '#21262d', 
    accent: '#fbbf24', 
    text: '#e5e7eb', 
    textMuted: '#9ca3af', 
    textDim: '#6b7280', 
    purple: '#8b5cf6', 
    cyan: '#06b6d4' 
};

export default function GravityPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [view3D, setView3D] = useState(false);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolGravity(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({ 
            date, 
            gravity: data.gravity_intensity?.[i] || 0, 
            trapping: (data.trapping_probability?.[i] || 0) * 100 
        }));
    }, [data]);

    // Generate 3D surface data for gravity well visualization
    const surface3DData = useMemo(() => {
        if (!data?.dates || !data?.gravity_intensity) return null;
        
        const numDates = data.dates.length;
        const sampleRate = Math.max(1, Math.floor(numDates / 80)); // More points for smoother surface
        const sampledIndices = [];
        for (let i = 0; i < numDates; i += sampleRate) {
            sampledIndices.push(i);
        }
        
        // More granular price deviations for smoother surface
        const priceDeviations = [];
        for (let d = -3; d <= 3; d += 0.25) {
            priceDeviations.push(d);
        }
        
        // Z is the "gravitational potential" - higher in center (0σ), lower at edges
        // Creates a classic "gravity well" funnel shape modulated by trapping probability
        const zData = priceDeviations.map(dev => {
            return sampledIndices.map(dateIdx => {
                const trap = data.trapping_probability?.[dateIdx] || 0.5;
                const gravity = data.gravity_intensity?.[dateIdx] || 50;
                // Gaussian potential well shape - deeper well = stronger gravity
                const sigma = 0.8 + (1 - trap) * 1.5; // Wider well when low trapping
                const potential = Math.exp(-dev * dev / (2 * sigma * sigma));
                // Scale by gravity intensity and normalize
                return potential * (gravity / 100) * 100;
            });
        });
        
        return {
            z: zData,
            x: sampledIndices.map(i => data.dates[i]),
            y: priceDeviations,
            type: 'surface',
            colorscale: [
                [0, 'rgb(20, 40, 80)'],
                [0.2, 'rgb(30, 100, 180)'],
                [0.4, 'rgb(100, 80, 200)'],
                [0.6, 'rgb(200, 60, 180)'],
                [0.8, 'rgb(250, 140, 100)'],
                [1, 'rgb(255, 200, 50)']
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
            lightposition: {
                x: 1000,
                y: 1000,
                z: 1000
            },
            colorbar: {
                title: { text: 'Gravity', font: { color: THEME.textMuted, size: 11 } },
                tickfont: { color: THEME.textDim, size: 9 }
            },
            contours: {
                z: { show: true, usecolormap: true, highlightcolor: "#fff", project: { z: true } }
            }
        };
    }, [data]);

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🌀 Gravity Well</h1>
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
                    <span className="text-xs font-mono" style={{ color: THEME.textDim }}>VIEW:</span>
                    <button 
                        onClick={() => setView3D(false)} 
                        className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ 
                            background: !view3D ? THEME.purple : 'transparent', 
                            color: !view3D ? '#fff' : THEME.textMuted,
                            border: `1px solid ${!view3D ? THEME.purple : THEME.border}`
                        }}
                    >
                        2D
                    </button>
                    <button 
                        onClick={() => setView3D(true)} 
                        className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ 
                            background: view3D ? THEME.cyan : 'transparent', 
                            color: view3D ? '#000' : THEME.textMuted,
                            border: `1px solid ${view3D ? THEME.cyan : THEME.border}`
                        }}
                    >
                        3D SURFACE
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing gravity well...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        {/* Stats Row */}
                        <div className="grid grid-cols-4 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Current Gravity</div>
                                <div className="text-xl font-mono font-bold" style={{ color: THEME.purple }}>{(data.gravity_intensity?.[data.gravity_intensity?.length - 1] || 0).toFixed(0)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Trapping Prob</div>
                                <div className="text-xl font-mono font-bold" style={{ color: THEME.cyan }}>{((data.trapping_probability?.[data.trapping_probability?.length - 1] || 0) * 100).toFixed(0)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Avg Gravity</div>
                                <div className="text-xl font-mono font-bold" style={{ color: THEME.text }}>{(data.gravity_intensity?.reduce((a, b) => a + b, 0) / data.gravity_intensity?.length || 0).toFixed(0)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Market State</div>
                                <div className="text-xl font-mono font-bold" style={{ 
                                    color: (data.trapping_probability?.[data.trapping_probability?.length - 1] || 0) > 0.7 ? '#22c55e' : '#ef4444' 
                                }}>
                                    {(data.trapping_probability?.[data.trapping_probability?.length - 1] || 0) > 0.7 ? 'RANGE-BOUND' : 'TRENDING'}
                                </div>
                            </div>
                        </div>

                        {/* Main Visualization */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-xs font-mono uppercase" style={{ color: THEME.accent }}>
                                    {view3D ? '3D Gravity Surface' : 'Gravity Intensity & Trapping Probability'}
                                </div>
                                {view3D && (
                                    <div className="text-[10px] font-mono" style={{ color: THEME.textDim }}>
                                        Drag to rotate • Scroll to zoom
                                    </div>
                                )}
                            </div>
                            
                            {!view3D ? (
                                // 2D Chart
                                <div style={{ height: 400 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                            <YAxis yAxisId="left" tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                                            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                                            <Legend wrapperStyle={{ fontSize: 11 }} />
                                            <Area yAxisId="left" type="monotone" dataKey="gravity" fill={THEME.purple} stroke={THEME.purple} fillOpacity={0.3} name="Gravity Intensity" />
                                            <Line yAxisId="right" type="monotone" dataKey="trapping" stroke={THEME.cyan} strokeWidth={1.5} dot={false} name="Trapping %" />
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                // 3D Surface - Full Width
                                <div style={{ height: 500, width: '100%' }}>
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
                                                    aspectratio: { x: 2, y: 1, z: 0.8 },
                                                    xaxis: { 
                                                        title: { text: 'Date', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
                                                        nticks: 8,
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    yaxis: { 
                                                        title: { text: 'Price Deviation (σ)', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    zaxis: { 
                                                        title: { text: 'Gravity Intensity', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    camera: {
                                                        eye: { x: 1.8, y: 1.8, z: 1.0 },
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

                        {/* Interpretation */}
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Interpretation</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• <span style={{ color: THEME.purple }}>Gravity Well</span>: Tendency for prices to stay within vol-implied bands</div>
                                <div>• <span style={{ color: THEME.cyan }}>Trapping Probability</span>: % of next 20 days within ±2σ band</div>
                                <div>• High trapping {">"} 70% = range-bound market, mean-reversion expected</div>
                                <div>• Low trapping {"<"} 50% = trending or breakout conditions</div>
                                {view3D && <div>• 3D Surface: Shows gravitational pull across price deviations over time</div>}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
