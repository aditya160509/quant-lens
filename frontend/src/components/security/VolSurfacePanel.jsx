"use client";

import React, { useState, useEffect } from 'react';
import { fetchVolSurface } from '@/lib/api_fg';
import TerminalPanel from '@/components/TerminalPanel';
import dynamic from 'next/dynamic';

// Dynamic import for Plotly (SSR issues)
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

/**
 * FG6: Volatility Surface Viewer
 * 3D/2D visualization of implied volatility surface.
 */
export default function VolSurfacePanel({ ticker = "AAPL" }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('3d'); // '3d' or '2d'
    const [optionType, setOptionType] = useState('all'); // 'all', 'call', 'put'

    useEffect(() => {
        if (ticker) {
            loadData();
        }
    }, [ticker]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetchVolSurface(ticker);
            setData(result);
        } catch (err) {
            console.error("VolSurfacePanel error:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !data) {
        return (
            <TerminalPanel title="VOLATILITY SURFACE" subtitle={ticker}>
                <div className="p-4 text-terminal-dim font-mono text-sm">
                    LOADING OPTIONS DATA...
                </div>
            </TerminalPanel>
        );
    }

    if (error) {
        return (
            <TerminalPanel title="VOLATILITY SURFACE" subtitle={ticker}>
                <div className="p-4 text-terminal-red font-mono text-sm">
                    {error}
                </div>
            </TerminalPanel>
        );
    }

    if (!data || !data.points || data.points.length === 0) {
        return (
            <TerminalPanel title="VOLATILITY SURFACE" subtitle={ticker}>
                <div className="p-4 text-terminal-dim font-mono text-sm">
                    No options data available for this ticker.
                </div>
            </TerminalPanel>
        );
    }

    // Filter points by option type
    const filteredPoints = optionType === 'all'
        ? data.points
        : data.points.filter(p => p.type === optionType);

    // Prepare chart data
    const strikes = filteredPoints.map(p => p.strike);
    const maturities = filteredPoints.map(p => p.days_to_expiry);
    const ivs = filteredPoints.map(p => p.iv * 100);

    // 3D Surface
    const surfaceData = viewMode === '3d' && data.grid_optional ? [{
        type: 'surface',
        x: data.grid_optional.strikes,
        y: data.grid_optional.maturities,
        z: data.grid_optional.iv.map(row => row.map(v => v ? v * 100 : null)),
        colorscale: [
            [0, 'rgba(0, 255, 136, 0.8)'],
            [0.25, 'rgba(0, 212, 255, 0.8)'],
            [0.5, 'rgba(255, 214, 10, 0.8)'],
            [0.75, 'rgba(255, 149, 0, 0.8)'],
            [1, 'rgba(255, 45, 85, 0.8)']
        ],
        contours: {
            z: { show: true, usecolormap: true, highlightcolor: "#fff", project: { z: true } }
        },
        showscale: true,
        colorbar: {
            title: { text: 'IV %', font: { color: '#5a6578', size: 10 } },
            tickfont: { color: '#5a6578', size: 9 }
        }
    }] : [{
        type: 'scatter',
        mode: 'markers',
        x: strikes,
        y: maturities,
        marker: {
            size: 8,
            color: ivs,
            colorscale: [
                [0, '#00ff88'],
                [0.25, '#00d4ff'],
                [0.5, '#ffd60a'],
                [0.75, '#ff9500'],
                [1, '#ff2d55']
            ],
            showscale: true,
            colorbar: {
                title: { text: 'IV %', font: { color: '#5a6578', size: 10 } },
                tickfont: { color: '#5a6578', size: 9 }
            }
        },
        text: filteredPoints.map(p => `Strike: ${p.strike}<br>Days: ${p.days_to_expiry}<br>IV: ${(p.iv * 100).toFixed(1)}%`),
        hovertemplate: '%{text}<extra></extra>'
    }];

    const layout3D = {
        scene: {
            xaxis: {
                title: { text: 'Strike', font: { color: '#5a6578', size: 10 } },
                gridcolor: 'rgba(30, 39, 56, 0.5)',
                tickfont: { color: '#5a6578', size: 9 }
            },
            yaxis: {
                title: { text: 'Days to Expiry', font: { color: '#5a6578', size: 10 } },
                gridcolor: 'rgba(30, 39, 56, 0.5)',
                tickfont: { color: '#5a6578', size: 9 }
            },
            zaxis: {
                title: { text: 'IV %', font: { color: '#5a6578', size: 10 } },
                gridcolor: 'rgba(30, 39, 56, 0.5)',
                tickfont: { color: '#5a6578', size: 9 }
            },
            bgcolor: 'rgba(3, 5, 10, 0.8)',
            camera: { eye: { x: 1.5, y: 1.5, z: 0.8 } }
        },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        margin: { l: 0, r: 0, t: 0, b: 0 }
    };

    const layout2D = {
        xaxis: {
            title: { text: 'Strike', font: { color: '#5a6578', size: 10 } },
            showgrid: true,
            gridcolor: 'rgba(30, 39, 56, 0.5)',
            tickfont: { color: '#5a6578', size: 9 }
        },
        yaxis: {
            title: { text: 'Days to Expiry', font: { color: '#5a6578', size: 10 } },
            showgrid: true,
            gridcolor: 'rgba(30, 39, 56, 0.5)',
            tickfont: { color: '#5a6578', size: 9 }
        },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        margin: { l: 50, r: 50, t: 20, b: 50 },
        hovermode: 'closest'
    };

    return (
        <TerminalPanel title="VOLATILITY SURFACE" subtitle={`${ticker} • Spot: $${data.spot?.toFixed(2) || 'N/A'}`}>
            <div className="p-4">
                {/* Controls */}
                <div className="flex items-center gap-4 mb-4">
                    {/* View Mode Toggle */}
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-terminal-dim">View:</span>
                        <div className="flex rounded overflow-hidden border border-terminal-gray/50">
                            <button
                                onClick={() => setViewMode('3d')}
                                className={`px-3 py-1 text-xs font-mono transition-colors ${viewMode === '3d'
                                    ? 'bg-terminal-yellow text-terminal-black'
                                    : 'bg-terminal-darker text-terminal-dim hover:text-terminal-text'
                                    }`}
                            >
                                3D
                            </button>
                            <button
                                onClick={() => setViewMode('2d')}
                                className={`px-3 py-1 text-xs font-mono transition-colors ${viewMode === '2d'
                                    ? 'bg-terminal-yellow text-terminal-black'
                                    : 'bg-terminal-darker text-terminal-dim hover:text-terminal-text'
                                    }`}
                            >
                                2D
                            </button>
                        </div>
                    </div>

                    {/* Option Type Filter */}
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-terminal-dim">Type:</span>
                        <div className="flex rounded overflow-hidden border border-terminal-gray/50">
                            {['all', 'call', 'put'].map((type) => (
                                <button
                                    key={type}
                                    onClick={() => setOptionType(type)}
                                    className={`px-3 py-1 text-xs font-mono uppercase transition-colors ${optionType === type
                                        ? 'bg-terminal-yellow text-terminal-black'
                                        : 'bg-terminal-darker text-terminal-dim hover:text-terminal-text'
                                        }`}
                                >
                                    {type}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Stats */}
                    <div className="ml-auto flex items-center gap-4 text-xs font-mono">
                        <span className="text-terminal-dim">
                            Points: <span className="text-terminal-text">{filteredPoints.length}</span>
                        </span>
                        <span className="text-terminal-dim">
                            Avg IV: <span className="text-terminal-yellow">
                                {(filteredPoints.reduce((sum, p) => sum + p.iv, 0) / filteredPoints.length * 100).toFixed(1)}%
                            </span>
                        </span>
                    </div>
                </div>

                {/* Chart */}
                <div className="h-80">
                    <Plot
                        data={surfaceData}
                        layout={viewMode === '3d' ? layout3D : layout2D}
                        config={{ displayModeBar: false }}
                        style={{ width: '100%', height: '100%' }}
                    />
                </div>

                {/* Legend */}
                <div className="flex items-center justify-center gap-6 mt-4 text-xs font-mono text-terminal-dim">
                    <span className="flex items-center gap-1">
                        <span className="w-3 h-3 rounded" style={{ background: '#00ff88' }}></span>
                        Low IV
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="w-3 h-3 rounded" style={{ background: '#ffd60a' }}></span>
                        Mid IV
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="w-3 h-3 rounded" style={{ background: '#ff2d55' }}></span>
                        High IV
                    </span>
                </div>
            </div>
        </TerminalPanel>
    );
}
