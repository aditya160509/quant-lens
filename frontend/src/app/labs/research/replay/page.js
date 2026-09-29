"use client";

import React, { useState, useEffect, Suspense, useCallback } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { PlotlyChart } from '@/components/ui/plotly-chart';
import TerminalPanel from '@/components/TerminalPanel';
import PageGrid from '@/components/PageGrid';

/**
 * E4 Market Replay Page - God Mode UI
 * Wrapped in Suspense for Next.js 16 compatibility
 */

function ReplayPageContent() {
    const searchParams = useSearchParams();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [preset, setPreset] = useState(searchParams.get('preset') || 'covid');
    const [isPlaying, setIsPlaying] = useState(false);
    const [playIndex, setPlayIndex] = useState(0);
    const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1 = 100ms, 2 = 50ms, 0.5 = 200ms

    const presets = [
        { value: 'covid', label: 'COVID-19 Crash (2020)' },
        { value: 'gfc', label: 'Global Financial Crisis (2008-09)' },
        { value: 'dotcom', label: 'Dot-com Bubble (2000-02)' },
        { value: 'inflation2022', label: '2022 Inflation Shock' },
    ];

    const fetchReplay = useCallback(async () => {
        setLoading(true);
        setError(null);
        setIsPlaying(false);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/research/e/replay', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'preset', preset, assets: ['SPY', '^VIX'] })
            });
            if (!res.ok) throw new Error('Failed to fetch replay data');
            const result = await res.json();
            setData(result);
            setPlayIndex(0);
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    }, [preset]);

    useEffect(() => {
        fetchReplay();
    }, [fetchReplay]);

    // Playback timer
    useEffect(() => {
        if (!isPlaying || !data?.timeline) return;

        const intervalMs = 100 / playbackSpeed;
        const timer = setInterval(() => {
            setPlayIndex(prev => {
                if (prev >= data.timeline.length - 1) {
                    setIsPlaying(false);
                    return prev;
                }
                return prev + 1;
            });
        }, intervalMs);

        return () => clearInterval(timer);
    }, [isPlaying, data, playbackSpeed]);

    const visibleData = data?.timeline?.slice(0, playIndex + 1) || [];

    // Helper to format date
    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    // Calculate percentage gain/loss from start
    const getPerformance = () => {
        if (!visibleData.length) return 0;
        const first = visibleData[0].price;
        const current = visibleData[visibleData.length - 1].price;
        return ((current - first) / first) * 100;
    };

    const perf = getPerformance();

    return (
        <div className="h-full flex flex-col bg-terminal-black font-mono overflow-auto">
            {/* Header / Toolbar */}
            <div className="shrink-0 px-6 py-4 border-b border-terminal-gray bg-terminal-darker flex justify-between items-center sticky top-0 z-10">
                <div className="flex items-center gap-4">
                    <Link href="/labs/research" className="text-terminal-dim hover:text-terminal-yellow transition-colors text-xs">
                        ← HUB
                    </Link>
                    <div className="h-4 w-px bg-terminal-gray"></div>
                    <h1 className="text-lg font-bold text-terminal-yellow tracking-wider">MARKET REPLAY</h1>
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 bg-terminal-black border border-terminal-gray rounded px-2 py-1">
                        <span className="text-[10px] text-terminal-dim uppercase">Episode</span>
                        <select
                            value={preset}
                            onChange={(e) => setPreset(e.target.value)}
                            className="bg-transparent text-xs text-terminal-text outline-none border-none min-w-[200px] appearance-none cursor-pointer hover:text-terminal-yellow"
                        >
                            {presets.map(p => (
                                <option key={p.value} value={p.value} className="bg-terminal-black">{p.label}</option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            <div className="flex-1 p-6 max-w-7xl mx-auto w-full flex flex-col gap-6">

                {/* Stats & Current Date Head-Up Display */}
                {data && (
                    <div className="grid grid-cols-12 gap-4 items-end">
                        <div className="col-span-12 md:col-span-8 flex flex-col gap-1">
                            <h2 className="text-3xl font-bold text-white tracking-tight">{data.title}</h2>
                            <div className="flex items-center gap-4 text-xs text-terminal-dim">
                                <span>{data.start} — {data.end}</span>
                                {loading && <span className="text-terminal-yellow animate-pulse">LOADING...</span>}
                            </div>
                        </div>
                        <div className="col-span-12 md:col-span-4 flex justify-end items-end gap-6">
                            <div className="text-right">
                                <div className="text-[10px] text-terminal-dim uppercase mb-1">Current Date</div>
                                <div className="text-2xl text-terminal-text font-bold text-shadow-neon">
                                    {visibleData[visibleData.length - 1]?.date || '---'}
                                </div>
                            </div>
                            <div className="text-right">
                                <div className="text-[10px] text-terminal-dim uppercase mb-1">Return</div>
                                <div className={`text-2xl font-bold ${perf >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                    {perf > 0 ? '+' : ''}{perf.toFixed(2)}%
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Main Visualization Area */}
                {data && (
                    <div className="bg-terminal-dark border border-terminal-gray/50 rounded-lg p-1 shadow-2xl overflow-hidden relative group">

                        {/* Playback Controls Overlay (or Toolbar) */}
                        <div className="absolute top-4 right-4 z-10 flex gap-2">
                            <div className="bg-terminal-black/80 backdrop-blur border border-terminal-gray rounded-lg p-1 flex items-center gap-1 shadow-lg">
                                <button
                                    onClick={() => setPlayIndex(0)}
                                    className="p-2 hover:bg-terminal-dim/20 rounded text-terminal-dim hover:text-terminal-text transition-all"
                                    title="Reset"
                                >
                                    ⏮
                                </button>
                                <button
                                    onClick={() => setIsPlaying(!isPlaying)}
                                    className="p-2 hover:bg-terminal-dim/20 rounded text-terminal-yellow hover:text-white transition-all min-w-[40px]"
                                    title={isPlaying ? "Pause" : "Play"}
                                >
                                    {isPlaying ? '⏸' : '▶'}
                                </button>
                                <button
                                    onClick={() => setPlaybackSpeed(s => s === 1 ? 2 : s === 2 ? 5 : 1)}
                                    className="p-2 hover:bg-terminal-dim/20 rounded text-xs font-bold w-[40px] text-terminal-dim hover:text-terminal-text"
                                    title="Playback Speed"
                                >
                                    {playbackSpeed}x
                                </button>
                            </div>
                        </div>

                        {/* Price Chart */}
                        <div className="h-[450px] w-full">
                            <PlotlyChart
                                data={[
                                    {
                                        x: visibleData.map(d => d.date),
                                        y: visibleData.map(d => d.price),
                                        type: 'scatter',
                                        mode: 'lines',
                                        name: 'SPY',
                                        line: { color: '#00ff9d', width: 2, shape: 'linear' }, // Neon Green
                                        fill: 'tozeroy',
                                        fillcolor: 'rgba(0, 255, 157, 0.05)',
                                        hoverinfo: 'y+x',
                                    }
                                ]}
                                layout={{
                                    margin: { t: 40, r: 40, b: 40, l: 60 },
                                    xaxis: {
                                        gridcolor: '#1a1a1a',
                                        linecolor: '#333',
                                        tickfont: { family: 'monospace', color: '#666' },
                                        zeroline: false,
                                        showgrid: false,
                                        range: [data.timeline[0].date, data.timeline[data.timeline.length - 1].date] // Fix X axis range to full episode
                                    },
                                    yaxis: {
                                        gridcolor: '#1a1a1a',
                                        linecolor: '#333',
                                        tickfont: { family: 'monospace', color: '#666' },
                                        zeroline: false,
                                        showgrid: true,
                                        gridwidth: 1,
                                    },
                                    showlegend: false,
                                    hovermode: 'x unified',
                                    hoverlabel: { bgcolor: '#000', bordercolor: '#333', font: { family: 'monospace' } }
                                }}
                            />
                        </div>

                        {/* VIX Chart (Bottom Strip) */}
                        {visibleData.some(d => d.vix) && (
                            <div className="h-[150px] w-full border-t border-terminal-gray/20 bg-black/20">
                                <PlotlyChart
                                    data={[
                                        {
                                            x: visibleData.map(d => d.date),
                                            y: visibleData.map(d => d.vix),
                                            type: 'scatter',
                                            mode: 'lines',
                                            name: 'VIX',
                                            line: { color: '#ff0055', width: 1.5, shape: 'spline' }, // Neon Red
                                            fill: 'tozeroy',
                                            fillcolor: 'rgba(255, 0, 85, 0.05)',
                                        }
                                    ]}
                                    layout={{
                                        margin: { t: 10, r: 40, b: 30, l: 60 },
                                        xaxis: {
                                            showgrid: false,
                                            showticklabels: true,
                                            tickfont: { color: '#444' },
                                            range: [data.timeline[0].date, data.timeline[data.timeline.length - 1].date]
                                        },
                                        yaxis: {
                                            gridcolor: '#1a1a1a',
                                            showticklabels: true,
                                            tickfont: { color: '#444', size: 10 },
                                            title: { text: "VIX", font: { color: '#444', size: 10 } }
                                        },
                                        showlegend: false,
                                        hovermode: 'x unified'
                                    }}
                                />
                            </div>
                        )}

                        {/* Progress Bar Scrubber */}
                        <div
                            className="h-1.5 w-full bg-terminal-gray/30 cursor-pointer relative group-hover:h-3 transition-all duration-200"
                            onClick={(e) => {
                                const rect = e.currentTarget.getBoundingClientRect();
                                const pct = (e.clientX - rect.left) / rect.width;
                                setPlayIndex(Math.floor(pct * (data.timeline?.length || 1)));
                            }}
                        >
                            <div
                                className="absolute top-0 left-0 h-full bg-terminal-yellow shadow-[0_0_10px_rgba(253,224,71,0.5)] transition-all duration-75"
                                style={{ width: `${(playIndex / (data.timeline?.length - 1 || 1)) * 100}%` }}
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// Default export with Suspense wrapper for Next.js 16
export default function ReplayPage() {
    return (
        <Suspense fallback={<div className="p-4 text-terminal-dim font-mono">Loading...</div>}>
            <ReplayPageContent />
        </Suspense>
    );
}

