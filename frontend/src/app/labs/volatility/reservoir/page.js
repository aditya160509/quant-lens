"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { runVolReservoir } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', blue: '#3b82f6', down: '#ef4444', up: '#22c55e', cyan: '#06b6d4' };

export default function ReservoirPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [view3D, setView3D] = useState(false);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolReservoir(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({ 
            date, 
            reservoir: data.reservoir?.[i] || 0,
            fillRate: (data.fill_rate?.[i] || 0) * 100,
            compression: (data.compression?.[i] || 0) * 100,
        }));
    }, [data]);

    // Generate 3D terrain for reservoir levels over time
    const surface3DData = useMemo(() => {
        if (!data?.dates || !data?.reservoir) return null;
        
        const sampleRate = Math.max(1, Math.floor(data.dates.length / 80));
        const sampledIndices = [];
        for (let i = 0; i < data.dates.length; i += sampleRate) {
            sampledIndices.push(i);
        }
        
        // Create a terrain-like surface with reservoir as the central mountain range
        // Y-axis represents "pressure" levels centered around the reservoir value
        const pressureLevels = [];
        for (let p = -2; p <= 2; p += 0.2) {
            pressureLevels.push(p);
        }
        
        const zData = pressureLevels.map(pressure => {
            return sampledIndices.map(idx => {
                const reservoir = data.reservoir?.[idx] || 50;
                // Create a Gaussian-like terrain around reservoir level
                const height = reservoir * Math.exp(-pressure * pressure / 1.5);
                return height;
            });
        });
        
        return {
            z: zData,
            x: sampledIndices.map(i => data.dates[i]),
            y: pressureLevels.map(p => p.toFixed(1)),
            type: 'surface',
            colorscale: [
                [0, 'rgb(20, 60, 100)'],
                [0.3, 'rgb(30, 130, 180)'],
                [0.5, 'rgb(59, 130, 246)'],
                [0.7, 'rgb(251, 191, 36)'],
                [0.85, 'rgb(249, 115, 22)'],
                [1, 'rgb(239, 68, 68)']
            ],
            showscale: true,
            opacity: 0.95,
            lighting: {
                ambient: 0.5,
                diffuse: 0.8,
                specular: 0.5,
                roughness: 0.3,
                fresnel: 0.3
            },
            colorbar: {
                title: { text: 'Energy %', font: { color: THEME.textMuted, size: 11 } },
                tickfont: { color: THEME.textDim, size: 9 }
            },
            contours: {
                z: { show: true, usecolormap: true, highlightcolor: "#fff", project: { z: true } }
            }
        };
    }, [data]);

    const currentLevel = data?.current_level || 0;

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🔋 Energy Reservoir</h1>
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
                    <button onClick={() => setView3D(false)} className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ background: !view3D ? THEME.blue : 'transparent', color: !view3D ? '#fff' : THEME.textMuted, border: `1px solid ${!view3D ? THEME.blue : THEME.border}` }}>
                        2D
                    </button>
                    <button onClick={() => setView3D(true)} className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ background: view3D ? THEME.cyan : 'transparent', color: view3D ? '#000' : THEME.textMuted, border: `1px solid ${view3D ? THEME.cyan : THEME.border}` }}>
                        3D TERRAIN
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing reservoir...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="text-center p-6 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                            <div className="text-[10px] font-mono uppercase mb-1" style={{ color: THEME.textDim }}>Reservoir Level</div>
                            <div className="text-5xl font-mono font-bold" style={{ color: currentLevel > 70 ? THEME.down : currentLevel < 30 ? THEME.up : THEME.text }}>{currentLevel.toFixed(0)}%</div>
                            <div className="text-xs font-mono mt-2" style={{ color: THEME.textMuted }}>
                                {currentLevel > 70 ? '⚠️ High energy - breakout imminent' : currentLevel < 30 ? '✓ Low energy - calm conditions' : '○ Normal energy levels'}
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-xs font-mono uppercase" style={{ color: THEME.accent }}>
                                    {view3D ? '3D Energy Terrain' : 'Energy Reservoir Over Time'}
                                </div>
                                {view3D && <div className="text-[10px] font-mono" style={{ color: THEME.textDim }}>Drag to rotate • Scroll to zoom</div>}
                            </div>
                            
                            {!view3D ? (
                                <div style={{ height: 350 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                            <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} formatter={(v) => `${v.toFixed(1)}%`} />
                                            <ReferenceLine y={80} stroke={THEME.down} strokeDasharray="5 5" label={{ value: 'Danger', fill: THEME.down, fontSize: 9 }} />
                                            <ReferenceLine y={30} stroke={THEME.up} strokeDasharray="5 5" label={{ value: 'Safe', fill: THEME.up, fontSize: 9 }} />
                                            <Area type="monotone" dataKey="reservoir" fill={THEME.blue} stroke={THEME.blue} fillOpacity={0.4} name="Reservoir %" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
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
                                                    aspectratio: { x: 2.5, y: 1, z: 0.8 },
                                                    xaxis: { title: { text: 'Date', font: { size: 11, color: THEME.accent } }, showgrid: true, gridcolor: THEME.border, tickfont: { size: 9, color: THEME.textDim }, nticks: 8, showbackground: true, backgroundcolor: THEME.bg },
                                                    yaxis: { title: { text: 'Pressure', font: { size: 11, color: THEME.accent } }, showgrid: true, gridcolor: THEME.border, tickfont: { size: 9, color: THEME.textDim }, showbackground: true, backgroundcolor: THEME.bg },
                                                    zaxis: { title: { text: 'Energy Level', font: { size: 11, color: THEME.accent } }, showgrid: true, gridcolor: THEME.border, tickfont: { size: 9, color: THEME.textDim }, showbackground: true, backgroundcolor: THEME.bg },
                                                    camera: { eye: { x: 1.8, y: 1.6, z: 1.0 }, center: { x: 0, y: 0, z: -0.1 } },
                                                    bgcolor: 'transparent',
                                                }
                                            }}
                                            style={{ width: '100%', height: '100%' }}
                                            useResizeHandler={true}
                                            config={{ displayModeBar: true, displaylogo: false, modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'], responsive: true }}
                                        />
                                    )}
                                </div>
                            )}
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Interpretation</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Stock-and-flow model of latent volatility risk</div>
                                <div>• Inflow: Vol compression + range tightness build energy</div>
                                <div>• Outflow: Short-term vol spikes release energy</div>
                                <div>• High levels ({'>'}80%) often precede volatility events</div>
                                {view3D && <div>• 3D Terrain: Mountain peaks = high energy buildup zones</div>}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
