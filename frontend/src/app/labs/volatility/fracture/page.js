"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { runVolFracture } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend, ResponsiveContainer } from 'recharts';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const THEME = { bg: '#010409', card: '#0d1117', border: '#21262d', accent: '#fbbf24', text: '#e5e7eb', textMuted: '#9ca3af', textDim: '#6b7280', pink: '#ec4899', down: '#ef4444', cyan: '#06b6d4', purple: '#8b5cf6' };

export default function FracturePage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [view3D, setView3D] = useState(false);

    const handleApply = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await runVolFracture(ticker, windowYears)); }
        catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [ticker, windowYears]);

    const chartData = useMemo(() => {
        if (!data?.dates) return [];
        return data.dates.map((date, i) => ({ 
            date, 
            alignment: data.alignment?.[i] || 0,
            short: data.short_signal?.[i] || 0,
            mid: data.mid_signal?.[i] || 0,
            long: data.long_signal?.[i] || 0,
        }));
    }, [data]);

    // Generate 3D surface for multi-scale stress visualization
    const surface3DData = useMemo(() => {
        if (!data?.dates || !data?.short_signal) return null;
        
        const sampleRate = Math.max(1, Math.floor(data.dates.length / 80));
        const sampledIndices = [];
        for (let i = 0; i < data.dates.length; i += sampleRate) {
            sampledIndices.push(i);
        }
        
        // Create a mesh showing stress levels across timescales
        const timescales = ['5d', '20d', '60d', 'Align'];
        const signalKeys = ['short_signal', 'mid_signal', 'long_signal', 'alignment'];
        
        const zData = signalKeys.map(key => {
            return sampledIndices.map(idx => {
                return data[key]?.[idx] || 0;
            });
        });
        
        return {
            z: zData,
            x: sampledIndices.map(i => data.dates[i]),
            y: timescales,
            type: 'surface',
            colorscale: [
                [0, 'rgb(20, 40, 80)'],
                [0.25, 'rgb(30, 80, 160)'],
                [0.5, 'rgb(139, 92, 246)'],
                [0.75, 'rgb(236, 72, 153)'],
                [1, 'rgb(239, 68, 68)']
            ],
            showscale: true,
            opacity: 0.92,
            lighting: {
                ambient: 0.5,
                diffuse: 0.8,
                specular: 0.4,
                roughness: 0.4,
                fresnel: 0.2
            },
            colorbar: {
                title: { text: 'Stress', font: { color: THEME.textMuted, size: 11 } },
                tickfont: { color: THEME.textDim, size: 9 }
            },
            contours: {
                z: { show: true, usecolormap: true, highlightcolor: "#fff", project: { z: true } }
            }
        };
    }, [data]);

    const currentAlignment = data?.alignment?.[data.alignment?.length - 1] || 0;

    return (
        <div style={{ height: '100%', background: THEME.bg, display: 'flex', flexDirection: 'column' }}>
            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <Link href="/labs/volatility" className="text-sm font-mono" style={{ color: THEME.accent }}>← VOL HUB</Link>
                <div className="h-4 w-px" style={{ background: THEME.border }} />
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>⚡ Fracture Map</h1>
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
                        style={{ background: !view3D ? THEME.pink : 'transparent', color: !view3D ? '#fff' : THEME.textMuted, border: `1px solid ${!view3D ? THEME.pink : THEME.border}` }}>
                        2D
                    </button>
                    <button onClick={() => setView3D(true)} className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ background: view3D ? THEME.purple : 'transparent', color: view3D ? '#fff' : THEME.textMuted, border: `1px solid ${view3D ? THEME.purple : THEME.border}` }}>
                        3D STRESS
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto p-4">
                {error && <div className="p-4 mb-4 rounded text-sm font-mono" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{error}</div>}
                {!data && !loading && !error && <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY</div></div>}
                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing fracture map...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        {/* Stats Row */}
                        <div className="grid grid-cols-4 gap-4">
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Current Alignment</div>
                                <div className="text-xl font-mono font-bold" style={{ color: currentAlignment > 80 ? THEME.down : currentAlignment > 50 ? THEME.accent : THEME.text }}>{currentAlignment.toFixed(0)}%</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Short (5d)</div>
                                <div className="text-xl font-mono font-bold" style={{ color: THEME.cyan }}>{(data.short_signal?.[data.short_signal?.length - 1] || 0).toFixed(0)}</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Mid (20d)</div>
                                <div className="text-xl font-mono font-bold" style={{ color: THEME.purple }}>{(data.mid_signal?.[data.mid_signal?.length - 1] || 0).toFixed(0)}</div>
                            </div>
                            <div className="text-center p-4 rounded-lg" style={{ background: THEME.bg, border: `1px solid ${THEME.border}` }}>
                                <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: THEME.textDim }}>Long (60d)</div>
                                <div className="text-xl font-mono font-bold" style={{ color: THEME.pink }}>{(data.long_signal?.[data.long_signal?.length - 1] || 0).toFixed(0)}</div>
                            </div>
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-xs font-mono uppercase" style={{ color: THEME.accent }}>
                                    {view3D ? '3D Multi-Scale Stress Surface' : 'Multi-Scale Alignment Score'}
                                </div>
                                {view3D && <div className="text-[10px] font-mono" style={{ color: THEME.textDim }}>Drag to rotate • Scroll to zoom</div>}
                            </div>
                            
                            {!view3D ? (
                                <div style={{ height: 400 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
                                            <XAxis dataKey="date" tick={{ fontSize: 10, fill: THEME.textDim }} tickFormatter={(v) => v.slice(5)} />
                                            <YAxis tick={{ fontSize: 10, fill: THEME.textDim }} domain={[0, 100]} />
                                            <Tooltip contentStyle={{ background: THEME.card, border: `1px solid ${THEME.border}` }} />
                                            <ReferenceLine y={80} stroke={THEME.down} strokeDasharray="5 5" label={{ value: 'Warning', fill: THEME.down, fontSize: 9 }} />
                                            <Line type="monotone" dataKey="short" stroke={THEME.cyan} strokeWidth={1} dot={false} name="5d Signal" />
                                            <Line type="monotone" dataKey="mid" stroke={THEME.purple} strokeWidth={1} dot={false} name="20d Signal" />
                                            <Line type="monotone" dataKey="long" stroke={THEME.pink} strokeWidth={1} dot={false} name="60d Signal" />
                                            <Area type="monotone" dataKey="alignment" fill={THEME.accent} stroke={THEME.accent} fillOpacity={0.2} strokeWidth={2} name="Alignment" />
                                            <Legend wrapperStyle={{ fontSize: 10 }} />
                                        </ComposedChart>
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
                                                    yaxis: { title: { text: 'Timescale', font: { size: 11, color: THEME.accent } }, showgrid: true, gridcolor: THEME.border, tickfont: { size: 9, color: THEME.textDim }, showbackground: true, backgroundcolor: THEME.bg },
                                                    zaxis: { title: { text: 'Stress Level', font: { size: 11, color: THEME.accent } }, showgrid: true, gridcolor: THEME.border, tickfont: { size: 9, color: THEME.textDim }, showbackground: true, backgroundcolor: THEME.bg },
                                                    camera: { eye: { x: 1.6, y: 1.6, z: 1.0 }, center: { x: 0, y: 0, z: -0.1 } },
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
                                <div>• Measures synchronization across 5d, 20d, 60d volatility signals</div>
                                <div>• High alignment ({'>'}80): All timescales show stress - potential fracture</div>
                                <div>• Low alignment: Timescales diverging - vol regime transition possible</div>
                                {view3D && <div>• 3D Surface: Shows stress levels across all timescales over time</div>}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
