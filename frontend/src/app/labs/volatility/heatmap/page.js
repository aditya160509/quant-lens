"use client";

import React, { useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { runVolHeatmap } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';

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
};

export default function HeatmapPage() {
    const [ticker, setTicker] = useState('SPY');
    const [windowYears, setWindowYears] = useState(2);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [view3D, setView3D] = useState(false);

    const handleApply = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await runVolHeatmap(ticker, windowYears);
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [ticker, windowYears]);

    const getColor = (val) => {
        const v = val * 100;
        if (v < 10) return '#1e3a5f';
        if (v < 20) return '#2563eb';
        if (v < 30) return '#06b6d4';
        if (v < 50) return '#fbbf24';
        return '#ef4444';
    };

    const sampledData = useMemo(() => {
        if (!data?.dates) return { dates: [], heatmap: {} };
        const sampleRate = Math.max(1, Math.floor(data.dates.length / 100));
        const dates = data.dates.filter((_, i) => i % sampleRate === 0);
        return { dates, sampleRate };
    }, [data]);

    // Generate 3D surface data for volatility term structure
    const surface3DData = useMemo(() => {
        if (!data?.dates || !data?.windows || !data?.heatmap) return null;
        
        const sampleRate = Math.max(1, Math.floor(data.dates.length / 80));
        const sampledIndices = [];
        for (let i = 0; i < data.dates.length; i += sampleRate) {
            sampledIndices.push(i);
        }
        
        // Z data: rows are windows, columns are dates
        const zData = data.windows.map(w => {
            const key = `rv_${w}`;
            return sampledIndices.map(idx => {
                const val = data.heatmap?.[key]?.[idx] || 0;
                return val * 100; // Convert to percentage
            });
        });
        
        return {
            z: zData,
            x: sampledIndices.map(i => data.dates[i]),
            y: data.windows.map(w => `${w}d`),
            type: 'surface',
            colorscale: [
                [0, 'rgb(20, 50, 90)'],
                [0.2, 'rgb(30, 100, 180)'],
                [0.4, 'rgb(6, 182, 212)'],
                [0.6, 'rgb(251, 191, 36)'],
                [0.8, 'rgb(249, 115, 22)'],
                [1, 'rgb(239, 68, 68)']
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
            colorbar: {
                title: { text: 'Vol %', font: { color: THEME.textMuted, size: 11 } },
                tickfont: { color: THEME.textDim, size: 9 },
                ticksuffix: '%'
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
                <h1 className="text-sm font-mono font-bold uppercase" style={{ color: THEME.text }}>🔥 Volatility Heatmap</h1>
            </div>

            <div className="flex items-center gap-4 p-4 border-b" style={{ borderColor: THEME.border, background: THEME.card }}>
                <div style={{ width: 200 }}>
                    <TradingViewSearch mode="security" onSelect={setTicker} placeholder="Search equities..." />
                </div>
                <div className="flex items-center gap-2 px-3 py-1 border text-sm font-mono" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span>
                </div>
                <select value={windowYears} onChange={(e) => setWindowYears(Number(e.target.value))} className="px-3 py-1 text-sm font-mono border focus:outline-none" style={{ borderColor: THEME.border, background: THEME.bg, color: THEME.text }}>
                    <option value={1}>1 Year</option>
                    <option value={2}>2 Years</option>
                    <option value={3}>3 Years</option>
                </select>
                <button onClick={handleApply} disabled={loading} className="px-6 py-1 text-sm font-mono font-bold disabled:opacity-50" style={{ background: THEME.accent, color: THEME.bg }}>
                    {loading ? 'COMPUTING...' : 'APPLY'}
                </button>
                
                {/* 3D Toggle */}
                <div className="ml-auto flex items-center gap-2">
                    <span className="text-xs font-mono" style={{ color: THEME.textDim }}>VIEW:</span>
                    <button 
                        onClick={() => setView3D(false)} 
                        className="px-3 py-1 text-xs font-mono font-bold rounded transition-all"
                        style={{ 
                            background: !view3D ? '#ef4444' : 'transparent', 
                            color: !view3D ? '#fff' : THEME.textMuted,
                            border: `1px solid ${!view3D ? '#ef4444' : THEME.border}`
                        }}
                    >
                        2D HEATMAP
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
                
                {!data && !loading && !error && (
                    <div className="flex items-center justify-center h-64"><div className="text-center font-mono" style={{ color: THEME.textDim }}>Select a ticker and click APPLY</div></div>
                )}

                {loading && <div className="flex items-center justify-center h-64"><div className="text-sm font-mono" style={{ color: THEME.accent }}>Computing heatmap...</div></div>}

                {data && !loading && (
                    <div className="space-y-6">
                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-xs font-mono uppercase" style={{ color: THEME.accent }}>
                                    {view3D ? '3D Volatility Term Structure' : 'Multi-Window Volatility Heatmap'}
                                </div>
                                {view3D && (
                                    <div className="text-[10px] font-mono" style={{ color: THEME.textDim }}>
                                        Drag to rotate • Scroll to zoom
                                    </div>
                                )}
                            </div>
                            
                            {!view3D ? (
                                // 2D Heatmap
                                <div className="overflow-x-auto">
                                    <div style={{ minWidth: 800 }}>
                                        {data.windows?.map((w) => (
                                            <div key={w} className="flex items-center mb-1">
                                                <div className="w-16 text-[10px] font-mono text-right pr-3" style={{ color: THEME.textDim }}>{w}d</div>
                                                <div className="flex-1 flex">
                                                    {sampledData.dates.map((date, di) => {
                                                        const idx = data.dates.indexOf(date);
                                                        const val = data.heatmap?.[`rv_${w}`]?.[idx] || 0;
                                                        return (
                                                            <div key={di} style={{ flex: 1, height: 24, background: getColor(val), marginRight: 1, minWidth: 4 }} title={`${date}: ${(val * 100).toFixed(1)}%`} />
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="flex justify-between mt-4 text-[10px] font-mono" style={{ color: THEME.textDim }}>
                                        <span>{data.dates?.[0]}</span>
                                        <span>{data.dates?.[data.dates.length - 1]}</span>
                                    </div>
                                </div>
                            ) : (
                                // 3D Surface
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
                                                    aspectratio: { x: 2.5, y: 1, z: 0.7 },
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
                                                        title: { text: 'Window', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    zaxis: { 
                                                        title: { text: 'Volatility %', font: { size: 11, color: THEME.accent } }, 
                                                        showgrid: true, 
                                                        gridcolor: THEME.border,
                                                        tickfont: { size: 9, color: THEME.textDim },
                                                        showbackground: true,
                                                        backgroundcolor: THEME.bg
                                                    },
                                                    camera: {
                                                        eye: { x: 1.6, y: 1.6, z: 1.0 },
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
                            
                            {!view3D && (
                                <div className="flex items-center gap-4 mt-4 justify-center">
                                    {[['<10%', '#1e3a5f'], ['10-20%', '#2563eb'], ['20-30%', '#06b6d4'], ['30-50%', '#fbbf24'], ['>50%', '#ef4444']].map(([label, color]) => (
                                        <div key={label} className="flex items-center gap-1">
                                            <div style={{ width: 12, height: 12, background: color, borderRadius: 2 }} />
                                            <span className="text-[9px] font-mono" style={{ color: THEME.textDim }}>{label}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="rounded-lg p-4" style={{ background: THEME.card, border: `1px solid ${THEME.border}` }}>
                            <div className="text-xs font-mono uppercase mb-2" style={{ color: THEME.accent }}>Methodology</div>
                            <div className="text-xs font-mono space-y-1" style={{ color: THEME.textDim }}>
                                <div>• Windows: 5, 10, 20, 40, 60, 120 trading days</div>
                                <div>• Short windows (5-20d) react faster to vol spikes</div>
                                <div>• Long windows (60-120d) show persistent regimes</div>
                                <div>• {view3D ? '3D Surface: Height = volatility level over time × window' : 'Color scale: Blue (low) → Yellow (moderate) → Red (crisis)'}</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
