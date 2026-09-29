"use client";

import React, { useState, useEffect } from 'react';
import { fetchEtfLookthrough } from '@/lib/api_fg';
import TerminalPanel from '@/components/TerminalPanel';

/**
 * FG5: ETF Look-Through Exposure
 * Transparent breakdown of ETF holdings, sectors, and factors.
 */
export default function EtfLookThrough({ ticker = "QQQ" }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (ticker) {
            loadData();
        }
    }, [ticker]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetchEtfLookthrough(ticker);
            setData(result);
        } catch (err) {
            console.error("EtfLookThrough error:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Get factor color
    const getFactorColor = (value) => {
        if (value >= 0.3) return 'var(--color-terminal-green)';
        if (value >= 0) return 'var(--color-terminal-cyan)';
        if (value >= -0.3) return 'var(--color-terminal-orange)';
        return 'var(--color-terminal-red)';
    };

    if (loading && !data) {
        return (
            <TerminalPanel title="ETF LOOK-THROUGH" subtitle={ticker}>
                <div className="p-4 text-terminal-dim font-mono text-sm">
                    ANALYZING ETF COMPOSITION...
                </div>
            </TerminalPanel>
        );
    }

    if (error) {
        return (
            <TerminalPanel title="ETF LOOK-THROUGH" subtitle={ticker}>
                <div className="p-4 text-terminal-red font-mono text-sm">
                    {error}
                </div>
            </TerminalPanel>
        );
    }

    if (!data || data.top_holdings.length === 0) {
        return (
            <TerminalPanel title="ETF LOOK-THROUGH" subtitle={ticker}>
                <div className="p-4 text-terminal-dim font-mono text-sm">
                    No holdings data available for this ETF.
                </div>
            </TerminalPanel>
        );
    }

    const maxSectorWeight = Math.max(...data.sectors.map(s => s.weight));

    return (
        <TerminalPanel title="ETF LOOK-THROUGH" subtitle={`${ticker} • ${data.as_of}`}>
            <div className="p-4">
                <div className="grid grid-cols-12 gap-4">
                    {/* Holdings Table */}
                    <div className="col-span-12 lg:col-span-6">
                        <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2">
                            Top Holdings
                        </div>
                        <div className="overflow-y-auto max-h-64">
                            <table className="w-full text-xs font-mono">
                                <thead className="sticky top-0 bg-terminal-dark">
                                    <tr className="text-terminal-dim border-b border-terminal-gray">
                                        <th className="text-left py-2 px-2">TICKER</th>
                                        <th className="text-left py-2 px-2">NAME</th>
                                        <th className="text-right py-2 px-2">WEIGHT</th>
                                        <th className="text-left py-2 px-2">SECTOR</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.top_holdings.map((h, i) => (
                                        <tr key={i} className="border-b border-terminal-gray/30 hover:bg-terminal-gray/10">
                                            <td className="py-2 px-2 text-terminal-yellow">{h.ticker}</td>
                                            <td className="py-2 px-2 text-terminal-text truncate max-w-[120px]">
                                                {h.name}
                                            </td>
                                            <td className="py-2 px-2 text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    <div
                                                        className="h-1.5 rounded"
                                                        style={{
                                                            width: `${h.weight * 300}px`,
                                                            maxWidth: '60px',
                                                            background: 'var(--color-terminal-yellow)'
                                                        }}
                                                    />
                                                    <span>{(h.weight * 100).toFixed(1)}%</span>
                                                </div>
                                            </td>
                                            <td className="py-2 px-2 text-terminal-dim truncate max-w-[80px]">
                                                {h.sector}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Sector Breakdown */}
                    <div className="col-span-12 lg:col-span-3">
                        <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2">
                            Sector Breakdown
                        </div>
                        <div className="space-y-2">
                            {data.sectors.slice(0, 8).map((s, i) => (
                                <div key={i}>
                                    <div className="flex justify-between text-xs font-mono mb-1">
                                        <span className="text-terminal-text truncate max-w-[100px]">{s.sector}</span>
                                        <span className="text-terminal-yellow">{(s.weight * 100).toFixed(1)}%</span>
                                    </div>
                                    <div className="h-2 bg-terminal-gray/30 rounded overflow-hidden">
                                        <div
                                            className="h-full rounded"
                                            style={{
                                                width: `${(s.weight / maxSectorWeight) * 100}%`,
                                                background: 'linear-gradient(90deg, var(--color-terminal-yellow), var(--color-terminal-orange))'
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Factor Exposure & Liquidity */}
                    <div className="col-span-12 lg:col-span-3">
                        <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2">
                            Factor Exposure
                        </div>
                        <div className="space-y-2 mb-4">
                            {Object.entries(data.factors || {}).map(([name, value]) => (
                                <div key={name}>
                                    <div className="flex justify-between text-xs font-mono mb-1">
                                        <span className="capitalize">{name}</span>
                                        <span style={{ color: getFactorColor(value) }}>
                                            {value >= 0 ? '+' : ''}{value.toFixed(2)}
                                        </span>
                                    </div>
                                    <div className="h-2 bg-terminal-gray/30 rounded overflow-hidden relative">
                                        {/* Center line */}
                                        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-terminal-dim" />
                                        {/* Factor bar */}
                                        <div
                                            className="absolute top-0 bottom-0 rounded"
                                            style={{
                                                left: value >= 0 ? '50%' : `${50 + value * 50}%`,
                                                width: `${Math.abs(value) * 50}%`,
                                                background: getFactorColor(value)
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Liquidity Badge */}
                        <div className="text-xs font-mono text-terminal-dim uppercase tracking-wide mb-2">
                            Liquidity
                        </div>
                        <div
                            className="p-3 rounded border"
                            style={{
                                borderColor: data.liquidity.score >= 0.8
                                    ? 'var(--color-terminal-green)'
                                    : data.liquidity.score >= 0.5
                                        ? 'var(--color-terminal-yellow)'
                                        : 'var(--color-terminal-orange)',
                                background: data.liquidity.score >= 0.8
                                    ? 'rgba(0, 255, 136, 0.1)'
                                    : data.liquidity.score >= 0.5
                                        ? 'rgba(255, 214, 10, 0.1)'
                                        : 'rgba(255, 149, 0, 0.1)'
                            }}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-xs font-mono text-terminal-dim">Score</span>
                                <span
                                    className="text-lg font-mono font-bold"
                                    style={{
                                        color: data.liquidity.score >= 0.8
                                            ? 'var(--color-terminal-green)'
                                            : data.liquidity.score >= 0.5
                                                ? 'var(--color-terminal-yellow)'
                                                : 'var(--color-terminal-orange)'
                                    }}
                                >
                                    {(data.liquidity.score * 100).toFixed(0)}
                                </span>
                            </div>
                            <div className="text-xs font-mono text-terminal-dim">
                                {data.liquidity.comment}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </TerminalPanel>
    );
}
