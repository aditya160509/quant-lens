"use client";

import React, { useState, useEffect } from 'react';
import { fetchDrawdownAnatomy } from '@/lib/api_fg';
import TerminalPanel from '@/components/TerminalPanel';
import { PlotlyChart } from '@/components/ui/plotly-chart';

/**
 * FG4: Drawdown Anatomy Panel
 * Detailed view of major drawdowns for any ticker.
 */
export default function DrawdownPanel({ ticker = "SPY" }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedEpisode, setSelectedEpisode] = useState(null);

    useEffect(() => {
        if (ticker) {
            loadData();
        }
    }, [ticker]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetchDrawdownAnatomy(ticker);
            setData(result);
        } catch (err) {
            console.error("DrawdownPanel error:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !data) {
        return (
            <TerminalPanel title="DRAWDOWN ANATOMY" subtitle={ticker}>
                <div className="p-4 text-terminal-dim font-mono text-sm">
                    ANALYZING DRAWDOWN HISTORY...
                </div>
            </TerminalPanel>
        );
    }

    if (error) {
        return (
            <TerminalPanel title="DRAWDOWN ANATOMY" subtitle={ticker}>
                <div className="p-4 text-terminal-red font-mono text-sm">
                    {error}
                </div>
            </TerminalPanel>
        );
    }

    if (!data || !data.series || data.series.length === 0) {
        return (
            <TerminalPanel title="DRAWDOWN ANATOMY" subtitle={ticker}>
                <div className="p-4 text-terminal-dim font-mono text-sm">
                    No drawdown data available.
                </div>
            </TerminalPanel>
        );
    }

    // Prepare chart data
    const dates = data.series.map(s => s.date);
    const prices = data.series.map(s => s.price);
    const drawdowns = data.series.map(s => s.drawdown * 100);

    // Summary stats
    const maxDD = data.episodes.length > 0
        ? Math.min(...data.episodes.map(e => e.depth))
        : 0;
    const avgRecovery = data.episodes
        .filter(e => e.length_recovery)
        .reduce((sum, e) => sum + e.length_recovery, 0) /
        (data.episodes.filter(e => e.length_recovery).length || 1);
    const currentDD = data.series.length > 0
        ? data.series[data.series.length - 1].drawdown
        : 0;

    const chartData = [
        {
            x: dates,
            y: drawdowns,
            type: 'scatter',
            mode: 'lines',
            fill: 'tozeroy',
            fillcolor: 'rgba(255, 45, 85, 0.2)',
            line: { color: 'var(--color-terminal-red)', width: 1.5 },
            name: 'Drawdown'
        }
    ];

    const chartLayout = {
        hovermode: 'x unified',
        showlegend: false,
        margin: { l: 50, r: 20, t: 20, b: 40 },
        xaxis: {
            showgrid: true,
            gridcolor: 'rgba(30, 39, 56, 0.5)',
            tickfont: { color: '#5a6578', size: 10 }
        },
        yaxis: {
            showgrid: true,
            gridcolor: 'rgba(30, 39, 56, 0.5)',
            tickfont: { color: '#5a6578', size: 10 },
            title: { text: 'Drawdown %', font: { color: '#5a6578', size: 10 } },
            ticksuffix: '%'
        }
    };

    return (
        <TerminalPanel title="DRAWDOWN ANATOMY" subtitle={`${ticker} • ${data.as_of}`}>
            <div className="p-4">
                {/* Summary Cards */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="p-3 rounded border border-terminal-gray/30 bg-terminal-darker/50">
                        <div className="text-xs font-mono text-terminal-dim uppercase mb-1">Max Drawdown</div>
                        <div className="text-xl font-mono font-bold text-terminal-red">
                            {(maxDD * 100).toFixed(1)}%
                        </div>
                    </div>
                    <div className="p-3 rounded border border-terminal-gray/30 bg-terminal-darker/50">
                        <div className="text-xs font-mono text-terminal-dim uppercase mb-1">Avg Recovery</div>
                        <div className="text-xl font-mono font-bold text-terminal-yellow">
                            {avgRecovery.toFixed(0)} days
                        </div>
                    </div>
                    <div className="p-3 rounded border border-terminal-gray/30 bg-terminal-darker/50">
                        <div className="text-xs font-mono text-terminal-dim uppercase mb-1">Current DD</div>
                        <div
                            className="text-xl font-mono font-bold"
                            style={{ color: currentDD < -0.05 ? 'var(--color-terminal-red)' : 'var(--color-terminal-green)' }}
                        >
                            {(currentDD * 100).toFixed(1)}%
                        </div>
                    </div>
                </div>

                {/* Drawdown Chart */}
                <div className="h-48 mb-4">
                    <PlotlyChart data={chartData} layout={chartLayout} />
                </div>

                {/* Episodes Table */}
                <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2">
                    Major Drawdown Episodes
                </div>
                <div className="overflow-x-auto max-h-48 overflow-y-auto">
                    <table className="w-full text-xs font-mono">
                        <thead className="sticky top-0 bg-terminal-dark">
                            <tr className="text-terminal-dim border-b border-terminal-gray">
                                <th className="text-left py-2 px-2">#</th>
                                <th className="text-left py-2 px-2">PEAK</th>
                                <th className="text-left py-2 px-2">TROUGH</th>
                                <th className="text-right py-2 px-2">DEPTH</th>
                                <th className="text-right py-2 px-2">DAYS</th>
                                <th className="text-right py-2 px-2">RECOVERY</th>
                                <th className="text-center py-2 px-2">TYPE</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.episodes.map((ep, i) => (
                                <tr
                                    key={i}
                                    className={`border-b border-terminal-gray/30 cursor-pointer transition-colors ${selectedEpisode === i ? 'bg-terminal-gray/20' : 'hover:bg-terminal-gray/10'
                                        }`}
                                    onClick={() => setSelectedEpisode(i)}
                                >
                                    <td className="py-2 px-2 text-terminal-yellow">{ep.rank}</td>
                                    <td className="py-2 px-2">{ep.peak_date}</td>
                                    <td className="py-2 px-2">{ep.trough_date}</td>
                                    <td className="py-2 px-2 text-right text-terminal-red font-bold">
                                        {(ep.depth * 100).toFixed(1)}%
                                    </td>
                                    <td className="py-2 px-2 text-right">{ep.length_peak_to_trough}d</td>
                                    <td className="py-2 px-2 text-right">
                                        {ep.length_recovery ? `${ep.length_recovery}d` : '—'}
                                    </td>
                                    <td className="py-2 px-2 text-center">
                                        <span
                                            className="px-2 py-0.5 rounded text-xs"
                                            style={{
                                                background: ep.type === 'shock'
                                                    ? 'rgba(255, 45, 85, 0.2)'
                                                    : 'rgba(255, 149, 0, 0.2)',
                                                color: ep.type === 'shock'
                                                    ? 'var(--color-terminal-red)'
                                                    : 'var(--color-terminal-orange)'
                                            }}
                                        >
                                            {ep.type.toUpperCase()}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </TerminalPanel>
    );
}
