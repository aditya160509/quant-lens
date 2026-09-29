"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { fetchEtfFactorDna } from '@/lib/api_fg';
import TerminalPanel from '@/components/TerminalPanel';

/**
 * FG7: ETF Factor DNA View
 * Factor personality of an ETF compared to peers.
 */
export default function EtfFactorDna() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedEtf, setSelectedEtf] = useState('QQQ');
    const [peerEtfs, setPeerEtfs] = useState(['SPY', 'VUG', 'VTV']);

    const etfOptions = ['QQQ', 'SPY', 'VTI', 'VUG', 'VTV', 'IWM', 'DIA', 'GLD', 'TLT'];

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetchEtfFactorDna({
                etf: selectedEtf,
                peer_etfs: peerEtfs.filter(p => p !== selectedEtf)
            });
            setData(result);
        } catch (err) {
            console.error("EtfFactorDna error:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [selectedEtf, peerEtfs]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Get factor color
    const getFactorColor = (value) => {
        if (value >= 0.4) return 'var(--color-terminal-green)';
        if (value >= 0.1) return 'var(--color-terminal-cyan)';
        if (value >= -0.1) return 'var(--color-terminal-dim)';
        if (value >= -0.4) return 'var(--color-terminal-orange)';
        return 'var(--color-terminal-red)';
    };

    // SVG Radar chart
    const RadarChart = ({ factors, size = 200 }) => {
        const centerX = size / 2;
        const centerY = size / 2;
        const radius = size / 2 - 30;
        const angleStep = (2 * Math.PI) / factors.length;

        // Generate polygon points
        const getPoint = (value, index) => {
            const angle = index * angleStep - Math.PI / 2;
            const r = ((value + 1) / 2) * radius; // Normalize -1 to 1 -> 0 to radius
            return {
                x: centerX + r * Math.cos(angle),
                y: centerY + r * Math.sin(angle)
            };
        };

        const points = factors.map((f, i) => getPoint(f.exposure, i));
        const polygonPoints = points.map(p => `${p.x},${p.y}`).join(' ');

        // Label positions
        const labelPoints = factors.map((f, i) => {
            const angle = i * angleStep - Math.PI / 2;
            return {
                x: centerX + (radius + 20) * Math.cos(angle),
                y: centerY + (radius + 20) * Math.sin(angle)
            };
        });

        return (
            <svg width={size} height={size} className="mx-auto">
                {/* Background circles */}
                {[0.25, 0.5, 0.75, 1].map((r, i) => (
                    <circle
                        key={i}
                        cx={centerX}
                        cy={centerY}
                        r={radius * r}
                        fill="none"
                        stroke="var(--color-terminal-gray)"
                        strokeWidth="1"
                        opacity={0.3}
                    />
                ))}

                {/* Axis lines */}
                {factors.map((f, i) => {
                    const angle = i * angleStep - Math.PI / 2;
                    return (
                        <line
                            key={i}
                            x1={centerX}
                            y1={centerY}
                            x2={centerX + radius * Math.cos(angle)}
                            y2={centerY + radius * Math.sin(angle)}
                            stroke="var(--color-terminal-gray)"
                            strokeWidth="1"
                            opacity={0.3}
                        />
                    );
                })}

                {/* Center line (neutral) */}
                <circle
                    cx={centerX}
                    cy={centerY}
                    r={radius * 0.5}
                    fill="none"
                    stroke="var(--color-terminal-dim)"
                    strokeWidth="1"
                    strokeDasharray="4 4"
                />

                {/* Data polygon */}
                <polygon
                    points={polygonPoints}
                    fill="rgba(255, 214, 10, 0.2)"
                    stroke="var(--color-terminal-yellow)"
                    strokeWidth="2"
                    style={{ filter: 'drop-shadow(0 0 8px rgba(255, 214, 10, 0.4))' }}
                />

                {/* Data points */}
                {points.map((p, i) => (
                    <circle
                        key={i}
                        cx={p.x}
                        cy={p.y}
                        r={5}
                        fill={getFactorColor(factors[i].exposure)}
                        stroke="#fff"
                        strokeWidth="1"
                    />
                ))}

                {/* Labels */}
                {labelPoints.map((p, i) => (
                    <text
                        key={i}
                        x={p.x}
                        y={p.y}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fill="var(--color-terminal-text)"
                        fontSize="10"
                        fontFamily="var(--font-mono)"
                        className="uppercase"
                    >
                        {factors[i].name}
                    </text>
                ))}
            </svg>
        );
    };

    if (loading && !data) {
        return (
            <TerminalPanel title="ETF FACTOR DNA" subtitle="Loading...">
                <div className="p-4 text-terminal-dim font-mono text-sm">
                    ANALYZING FACTOR COMPOSITION...
                </div>
            </TerminalPanel>
        );
    }

    if (error) {
        return (
            <TerminalPanel title="ETF FACTOR DNA" subtitle="Error">
                <div className="p-4 text-terminal-red font-mono text-sm">
                    {error}
                </div>
            </TerminalPanel>
        );
    }

    if (!data) return null;

    return (
        <TerminalPanel title="ETF FACTOR DNA" subtitle={`${data.etf} • ${data.as_of}`}>
            <div className="p-4">
                {/* ETF Selector */}
                <div className="flex items-center gap-4 mb-4">
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-terminal-dim">ETF:</span>
                        <select
                            value={selectedEtf}
                            onChange={(e) => setSelectedEtf(e.target.value)}
                            className="bg-terminal-darker border border-terminal-gray/50 rounded px-2 py-1 text-xs font-mono text-terminal-yellow"
                        >
                            {etfOptions.map(etf => (
                                <option key={etf} value={etf}>{etf}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="grid grid-cols-12 gap-4">
                    {/* Radar Chart */}
                    <div className="col-span-12 lg:col-span-5">
                        <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2 text-center">
                            Factor Profile
                        </div>
                        <RadarChart factors={data.factors} size={220} />
                    </div>

                    {/* Factor Details */}
                    <div className="col-span-12 lg:col-span-4">
                        <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2">
                            Factor Breakdown
                        </div>
                        <div className="space-y-3">
                            {data.factors.map((f) => (
                                <div key={f.name} className="p-2 rounded bg-terminal-darker/50 border border-terminal-gray/20">
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-xs font-mono uppercase text-terminal-text">{f.name}</span>
                                        <span
                                            className="text-sm font-mono font-bold"
                                            style={{ color: getFactorColor(f.exposure) }}
                                        >
                                            {f.exposure >= 0 ? '+' : ''}{f.exposure.toFixed(2)}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 text-xs font-mono text-terminal-dim">
                                        <span>Purity: {(f.purity * 100).toFixed(0)}%</span>
                                        <span>•</span>
                                        <span style={{ color: f.drift_1y >= 0 ? 'var(--color-terminal-green)' : 'var(--color-terminal-red)' }}>
                                            Drift: {f.drift_1y >= 0 ? '+' : ''}{(f.drift_1y * 100).toFixed(1)}%
                                        </span>
                                    </div>
                                    {/* Exposure bar */}
                                    <div className="mt-1 h-1.5 bg-terminal-gray/30 rounded overflow-hidden relative">
                                        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-terminal-dim" />
                                        <div
                                            className="absolute top-0 bottom-0 rounded"
                                            style={{
                                                left: f.exposure >= 0 ? '50%' : `${50 + f.exposure * 50}%`,
                                                width: `${Math.abs(f.exposure) * 50}%`,
                                                background: getFactorColor(f.exposure)
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Peer Comparison */}
                    <div className="col-span-12 lg:col-span-3">
                        <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2">
                            Peer Comparison
                        </div>
                        <div className="space-y-2">
                            {data.peers.map((peer) => (
                                <div key={peer.ticker} className="p-2 rounded bg-terminal-darker/50 border border-terminal-gray/20">
                                    <div className="text-xs font-mono text-terminal-yellow mb-1">{peer.ticker}</div>
                                    <div className="flex flex-wrap gap-1">
                                        {Object.entries(peer.factors).map(([name, value]) => (
                                            <span
                                                key={name}
                                                className="text-xs font-mono px-1 rounded"
                                                style={{
                                                    background: `${getFactorColor(value)}20`,
                                                    color: getFactorColor(value)
                                                }}
                                            >
                                                {name.charAt(0).toUpperCase()}: {value >= 0 ? '+' : ''}{value.toFixed(1)}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </TerminalPanel>
    );
}
