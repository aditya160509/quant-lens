"use client";

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
    getPCAGodModeUniverses,
    runPCAGodMode,
    getPCAGodModeStructure,
    getPCAGodModeFactors,
    getPCAGodModeLoadings,
    getPCAGodModeStability,
    getPCAGodModeRedundancy,
    simulatePCAGodModeShock,
    getPCAGodModeBreaks,
    getPCAGodModeGovernance,
    exportPCAGodModeData
} from '@/lib/api';
import { 
    LayoutGrid, RefreshCw, Database, 
    Zap, Globe, Calendar, Clock,
    ChevronDown, X, TrendingUp,
    Shield, Briefcase
} from 'lucide-react';
import TerminalPanel from '@/components/TerminalPanel';
import { PlotlyChart } from '@/components/ui/plotly-chart';

import SovereignCommandBar from './SovereignCommandBar';

// =============================================================================
// CONSTANTS
// =============================================================================

const TABS = [
    { id: "structure", label: "Structure", icon: "◉" },
    { id: "factors", label: "Factors", icon: "⊕" },
    { id: "stability", label: "Stability", icon: "◎" },
    { id: "redundancy", label: "Redundancy", icon: "⊛" },
    { id: "governance", label: "Governance", icon: "✓" },
];

const COLORS = {
    green: "#22c55e", yellow: "#fbbf24", orange: "#f97316",
    red: "#ef4444", blue: "#3b82f6", cyan: "#06b6d4",
    purple: "#a855f7", dim: "#6b7280"
};

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function MetricCard({ label, value, color = COLORS.cyan, bar, barColor, subtext, large }) {
    return (
        <div className={`bg-terminal-black ${large ? 'p-4' : 'p-3'} rounded border border-terminal-gray/30`}>
            <div className="text-xs text-terminal-dim uppercase tracking-wide">{label}</div>
            <div className={`${large ? 'text-2xl' : 'text-lg'} font-mono font-bold mt-1`} style={{ color }}>
                {value ?? '—'}
            </div>
            {bar !== undefined && bar !== null && (
                <div className="h-1.5 bg-terminal-gray/30 rounded overflow-hidden mt-2">
                    <div className="h-full transition-all duration-500" 
                        style={{ width: `${Math.min(Math.abs(bar) * 100, 100)}%`, background: barColor || color }} />
                </div>
            )}
            {subtext && <div className="text-xs text-terminal-dim mt-1">{subtext}</div>}
        </div>
    );
}

function ClassificationBadge({ label, color }) {
    return (
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-sm font-bold"
            style={{ background: `${color}20`, border: `1px solid ${color}50`, color }}>
            <span className="w-2 h-2 rounded-full" style={{ background: color }} />
            {label}
        </div>
    );
}

function DataTable({ columns, data, maxHeight = "400px" }) {
    if (!data?.length) return <div className="text-terminal-dim text-center py-8">No data</div>;
    return (
        <div className="overflow-auto" style={{ maxHeight }}>
            <table className="w-full text-sm font-mono">
                <thead className="text-terminal-dim text-xs uppercase sticky top-0 bg-terminal-dark">
                    <tr>
                        {columns.map(col => (
                            <th key={col.key} className="text-left py-2 px-3 border-b border-terminal-gray/30">
                                {col.label}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {data.map((row, i) => (
                        <tr key={i} className="hover:bg-terminal-gray/10 transition-colors">
                            {columns.map(col => (
                                <td key={col.key} className="py-2 px-3 border-b border-terminal-gray/10"
                                    style={{ color: col.getColor?.(row) || '#e5e7eb' }}>
                                    {col.render ? col.render(row) : row[col.key]}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function WarningBanner({ warnings }) {
    if (!warnings?.length) return null;
    return (
        <div className="bg-terminal-orange/10 border border-terminal-orange/30 p-3 rounded space-y-1">
            {warnings.map((w, i) => (
                <div key={i} className="text-xs text-terminal-orange flex items-start gap-2">
                    <span>⚠</span><span>{w}</span>
                </div>
            ))}
        </div>
    );
}

// =============================================================================
// TAB 1: STRUCTURE OVERVIEW
// =============================================================================

function StructureTab({ data, quality }) {
    if (!data) return <div className="text-terminal-dim p-8 text-center">Run analysis to see structure</div>;
    
    const structureColor = data.fragility_score > 70 ? COLORS.red 
        : data.fragility_score > 40 ? COLORS.orange 
        : COLORS.green;
    
    return (
        <div className="space-y-4">
            <WarningBanner warnings={data.warnings} />
            
            {/* Classification Header */}
            <div className="flex items-center justify-between bg-terminal-dark border border-terminal-gray p-4 rounded">
                <div>
                    <div className="text-xs text-terminal-dim mb-1">Market Structure Classification</div>
                    <ClassificationBadge label={data.classification} color={structureColor} />
                </div>
                <div className="text-right">
                    <div className="text-xs text-terminal-dim">Fragility Score</div>
                    <div className="text-4xl font-mono font-bold" style={{ color: structureColor }}>
                        {Math.round(data.fragility_score)}
                    </div>
                </div>
            </div>
            
            {/* Primary Metrics */}
            <div className="grid grid-cols-4 lg:grid-cols-8 gap-3">
                <MetricCard label="PC1 Share" value={`${data.pc1_variance_share}%`}
                    color={data.pc1_variance_share > 40 ? COLORS.red : COLORS.green}
                    bar={data.pc1_variance_share / 100} />
                <MetricCard label="Top 3 PCs" value={`${data.top3_pcs_variance}%`} color={COLORS.blue} />
                <MetricCard label="Top 5 PCs" value={`${data.top5_pcs_variance}%`} color={COLORS.cyan} />
                <MetricCard label="ENB" value={data.enb} 
                    color={data.enb < 5 ? COLORS.red : data.enb > 10 ? COLORS.green : COLORS.yellow}
                    subtext="Effective Bets" />
                <MetricCard label="Concentration" value={data.concentration_index?.toFixed(3)} color={COLORS.purple} />
                <MetricCard label="Noise Floor" value={`${data.noise_floor}%`} 
                    color={data.noise_floor > 5 ? COLORS.orange : COLORS.dim} />
                <MetricCard label="Optimal PCs" value={data.optimal_pc_count} color={COLORS.cyan} />
                <MetricCard label="Quality" value={quality?.quality_badge || "—"} 
                    color={quality?.quality_badge === 'HIGH' ? COLORS.green : COLORS.yellow} />
            </div>
            
            {/* Charts Row */}
            <div className="grid grid-cols-2 gap-4">
                <TerminalPanel title="Explained Variance">
                    <div className="h-64 p-2">
                        <PlotlyChart
                            data={[
                                {
                                    x: data.explained_variance?.map((_, i) => `PC${i+1}`) || [],
                                    y: data.explained_variance || [],
                                    type: 'bar', name: 'Individual',
                                    marker: { color: COLORS.cyan }
                                },
                                {
                                    x: data.cumulative_variance?.map((_, i) => `PC${i+1}`) || [],
                                    y: data.cumulative_variance || [],
                                    type: 'scatter', mode: 'lines+markers', name: 'Cumulative',
                                    yaxis: 'y2', line: { color: COLORS.yellow, width: 2 }
                                }
                            ]}
                            layout={{
                                xaxis: { showgrid: false },
                                yaxis: { showgrid: true, gridcolor: '#333', title: '% Explained' },
                                yaxis2: { overlaying: 'y', side: 'right', range: [0, 100], title: 'Cumulative %' },
                                legend: { orientation: 'h', y: -0.2 },
                                margin: { l: 50, r: 50, t: 20, b: 60 }
                            }}
                        />
                    </div>
                </TerminalPanel>
                
                <TerminalPanel title="Effective Number of Bets Curve">
                    <div className="h-64 p-2">
                        <PlotlyChart
                            data={[{
                                x: data.enb_curve?.map((_, i) => i + 1) || [],
                                y: data.enb_curve || [],
                                type: 'scatter', mode: 'lines+markers',
                                line: { color: COLORS.green, width: 2 },
                                marker: { size: 6 }
                            }]}
                            layout={{
                                xaxis: { title: '# of PCs Included', showgrid: true, gridcolor: '#333' },
                                yaxis: { title: 'ENB', showgrid: true, gridcolor: '#333' },
                                margin: { l: 50, r: 30, t: 20, b: 50 },
                                shapes: [{
                                    type: 'line', y0: data.enb, y1: data.enb, x0: 0, x1: data.optimal_pc_count,
                                    line: { color: COLORS.yellow, dash: 'dot' }
                                }]
                            }}
                        />
                    </div>
                </TerminalPanel>
            </div>
        </div>
    );
}

// =============================================================================
// TAB 2: FACTORS & MEANING
// =============================================================================

function FactorsTab({ factors, onLoadingsRequest }) {
    const [selectedPC, setSelectedPC] = useState(1);
    
    if (!factors?.length) return <div className="text-terminal-dim p-8 text-center">Run analysis to see factors</div>;
    
    const selectedFactor = factors.find(f => f.pc_index === selectedPC) || factors[0];
    
    return (
        <div className="space-y-4">
            {/* Factor Selector */}
            <div className="flex gap-2 overflow-x-auto pb-2">
                {factors.slice(0, 10).map(f => (
                    <button key={f.pc_index}
                        onClick={() => setSelectedPC(f.pc_index)}
                        className={`px-4 py-2 rounded font-mono text-sm whitespace-nowrap transition-all ${
                            selectedPC === f.pc_index 
                            ? 'bg-terminal-cyan text-terminal-black' 
                            : 'bg-terminal-black text-terminal-dim hover:text-terminal-text border border-terminal-gray/30'
                        }`}>
                        PC{f.pc_index}
                        <span className="ml-2 text-xs opacity-70">{f.label}</span>
                    </button>
                ))}
            </div>
            
            {/* Selected Factor Detail */}
            {selectedFactor && (
                <div className="grid grid-cols-12 gap-4">
                    {/* Factor Info */}
                    <div className="col-span-12 lg:col-span-4 space-y-4">
                        <TerminalPanel title={`PC${selectedFactor.pc_index} INTERPRETATION`}>
                            <div className="p-4 space-y-4">
                                <div className="text-lg font-mono text-terminal-cyan">{selectedFactor.interpretation}</div>
                                <div className="grid grid-cols-2 gap-3">
                                    <MetricCard label="Dominant Sector" value={selectedFactor.dominant_sector} color={COLORS.purple} />
                                    <MetricCard label="Sector Share" value={`${selectedFactor.sector_share}%`} 
                                        bar={selectedFactor.sector_share / 100} color={COLORS.blue} />
                                    <MetricCard label="Sign Consistency" value={`${selectedFactor.sign_consistency}%`}
                                        color={selectedFactor.sign_consistency > 80 ? COLORS.green : COLORS.yellow} />
                                    <MetricCard label="Purity Score" value={selectedFactor.purity_score?.toFixed(2)}
                                        color={selectedFactor.purity_score > 0.7 ? COLORS.green : selectedFactor.purity_score > 0.4 ? COLORS.yellow : COLORS.red} />
                                </div>
                                <ClassificationBadge label={selectedFactor.label}
                                    color={selectedFactor.label === 'PURE' ? COLORS.green : selectedFactor.label === 'MIXED' ? COLORS.yellow : COLORS.dim} />
                            </div>
                        </TerminalPanel>
                    </div>
                    
                    {/* Loading Bars */}
                    <div className="col-span-12 lg:col-span-8">
                        <TerminalPanel title={`PC${selectedFactor.pc_index} TOP LOADINGS`}>
                            <div className="h-80 p-2">
                                <PlotlyChart
                                    data={[{
                                        y: selectedFactor.top_loaders?.slice(0, 15).map(l => l.ticker).reverse() || [],
                                        x: selectedFactor.top_loaders?.slice(0, 15).map(l => l.loading).reverse() || [],
                                        type: 'bar', orientation: 'h',
                                        marker: { 
                                            color: selectedFactor.top_loaders?.slice(0, 15).map(l => 
                                                l.loading >= 0 ? COLORS.green : COLORS.red
                                            ).reverse() || []
                                        }
                                    }]}
                                    layout={{
                                        xaxis: { title: 'Loading', showgrid: true, gridcolor: '#333', zeroline: true },
                                        yaxis: { showgrid: false, tickfont: { size: 10 } },
                                        margin: { l: 100, r: 20, t: 20, b: 50 }
                                    }}
                                />
                            </div>
                        </TerminalPanel>
                    </div>
                </div>
            )}
            
            {/* Factor Summary Table */}
            <TerminalPanel title="ALL FACTORS SUMMARY">
                <DataTable
                    columns={[
                        { key: 'pc_index', label: 'PC' },
                        { key: 'interpretation', label: 'Interpretation' },
                        { key: 'dominant_sector', label: 'Dominant Sector' },
                        { key: 'sector_share', label: 'Sector %', render: r => `${r.sector_share}%` },
                        { key: 'purity_score', label: 'Purity', render: r => r.purity_score?.toFixed(2),
                            getColor: r => r.purity_score > 0.7 ? COLORS.green : r.purity_score > 0.4 ? COLORS.yellow : COLORS.red },
                        { key: 'label', label: 'Type',
                            getColor: r => r.label === 'PURE' ? COLORS.green : r.label === 'MIXED' ? COLORS.yellow : COLORS.dim }
                    ]}
                    data={factors}
                    maxHeight="300px"
                />
            </TerminalPanel>
        </div>
    );
}

// =============================================================================
// TAB 3: STABILITY
// =============================================================================

function StabilityTab({ stability, factorReturns, loadingDrift, pcDominance }) {
    const [activePC, setActivePC] = useState(1);
    if (!stability?.length) return <div className="text-terminal-dim p-8 text-center">Run analysis to see stability</div>;
    
    const pcKey = `PC${activePC}`;
    const currentDrift = loadingDrift?.drift_data?.[pcKey];

    return (
        <div className="space-y-4">
            {/* Stability Cards */}
            <div className="grid grid-cols-5 gap-3">
                {stability.slice(0, 5).map(s => (
                    <button 
                        key={s.pc_index} 
                        onClick={() => setActivePC(s.pc_index)}
                        className={`bg-terminal-dark border p-4 rounded text-left transition-all ${
                            activePC === s.pc_index ? 'border-terminal-yellow shadow-[0_0_15px_rgba(255,204,0,0.1)]' : 'border-terminal-gray hover:border-terminal-gray/60'
                        }`}
                    >
                        <div className="flex items-center justify-between mb-3">
                            <span className={`font-mono ${activePC === s.pc_index ? 'text-terminal-yellow' : 'text-terminal-cyan'}`}>PC{s.pc_index}</span>
                            <ClassificationBadge label={s.classification}
                                color={s.classification === 'HIGH' ? COLORS.green : s.classification === 'MEDIUM' ? COLORS.yellow : COLORS.red} />
                        </div>
                        <div className="text-3xl font-mono font-bold mb-3"
                            style={{ color: s.trust_score > 0.7 ? COLORS.green : s.trust_score > 0.4 ? COLORS.yellow : COLORS.red }}>
                            {(s.trust_score * 100).toFixed(0)}%
                        </div>
                        <div className="space-y-1 text-xs">
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Loading Stability</span>
                                <span>{(s.loading_stability * 100).toFixed(0)}%</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Variance Stability</span>
                                <span>{(s.variance_stability * 100).toFixed(0)}%</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Sharpe</span>
                                <span style={{ color: s.sharpe > 0 ? COLORS.green : COLORS.red }}>{s.sharpe}</span>
                            </div>
                        </div>
                    </button>
                ))}
            </div>
            
            {/* Charts - Full Width Stacked Layout */}
            <div className="space-y-4">
                {/* Factor Returns Chart - Full Width */}
                {/* Factor Returns Chart - MISSION CRITICAL */}
                {/* Factor Returns Chart - MISSION CRITICAL */}
                {factorReturns?.cumulative_returns ? (
                    <TerminalPanel title="CUMULATIVE FACTOR RETURNS (PC-PORTFOLIOS)">
                        <div className="h-80 p-2">
                            <PlotlyChart
                                data={Object.entries(factorReturns.cumulative_returns).slice(0, 5).map(([pc, rets], i) => ({
                                    x: factorReturns.dates,
                                    y: rets,
                                    type: 'scatter', 
                                    mode: 'lines', 
                                    name: pc,
                                    line: { 
                                        width: 2, 
                                        color: [COLORS.cyan, COLORS.yellow, COLORS.green, COLORS.orange, COLORS.purple][i],
                                        shape: 'spline'
                                    }
                                }))}
                                layout={{
                                    xaxis: { 
                                        showgrid: false, 
                                        tickfont: { color: COLORS.dim, size: 9 },
                                        rangeslider: { visible: false } 
                                    },
                                    yaxis: { 
                                        title: 'Portfolio Index Value', 
                                        showgrid: true, 
                                        gridcolor: 'rgba(255,255,255,0.05)',
                                        tickfont: { color: COLORS.dim, size: 9 }
                                    },
                                    legend: { 
                                        orientation: 'h', 
                                        y: -0.2, 
                                        x: 0.5, 
                                        xanchor: 'center',
                                        font: { color: COLORS.dim, size: 10 }
                                    },
                                    margin: { l: 60, r: 30, t: 30, b: 60 },
                                    hovermode: 'x unified',
                                    paper_bgcolor: 'transparent',
                                    plot_bgcolor: 'transparent'
                                }}
                            />
                        </div>
                    </TerminalPanel>
                ) : (
                    <div className="bg-terminal-black/50 border border-white/5 p-8 rounded-xl text-center">
                        <div className="text-terminal-dim text-xs font-black uppercase tracking-widest mb-2">Stability Vectors Missing</div>
                        <div className="text-[10px] text-terminal-dim/50 font-bold">Ensure 2020 Depth is selected for full historical return reconstruction.</div>
                    </div>
                )}
                
                {/* PC Dominance History - Full Width */}
                {pcDominance?.dates && (
                    <TerminalPanel title={`${pcKey} VARIANCE SHARE % OVER TIME`}>
                        <div className="h-56 p-2">
                            <PlotlyChart
                                data={[
                                    {
                                        x: pcDominance.dates,
                                        y: activePC === 1 ? pcDominance.pc1_share.map(v => v * 100) : [], // Simple mock if data not available for other PCs
                                        type: 'scatter', mode: 'lines', name: `${pcKey} Share %`,
                                        line: { color: COLORS.yellow, width: 2 }
                                    },
                                    {
                                        x: pcDominance.dates,
                                        y: pcDominance.enb,
                                        type: 'scatter', mode: 'lines', name: 'ENB (System Diversity)',
                                        yaxis: 'y2',
                                        line: { color: COLORS.green, width: 2 }
                                    }
                                ]}
                                layout={{
                                    xaxis: { showgrid: false },
                                    yaxis: { title: 'Variance %', showgrid: true, gridcolor: 'rgba(255,255,255,0.05)' },
                                    yaxis2: { title: 'ENB', overlaying: 'y', side: 'right' },
                                    legend: { orientation: 'h', y: -0.2 },
                                    margin: { l: 50, r: 50, t: 20, b: 60 },
                                    paper_bgcolor: 'transparent'
                                }}
                            />
                        </div>
                    </TerminalPanel>
                )}
            </div>
            
            {/* Loading Drift Heatmap */}
            {currentDrift && (
                <TerminalPanel title={`LOADING DRIFT HEATMAP (${pcKey})`}>
                    <div className="h-80 p-2">
                        <PlotlyChart
                            data={[{
                                z: currentDrift.loadings,
                                x: currentDrift.assets,
                                y: currentDrift.dates,
                                type: 'heatmap',
                                colorscale: [
                                    [0, COLORS.red],
                                    [0.5, '#0a0a0a'],
                                    [1, COLORS.green]
                                ],
                                showscale: true,
                                colorbar: { 
                                    title: 'Weight',
                                    tickfont: { color: COLORS.dim, size: 8 }
                                }
                            }]}
                            layout={{
                                xaxis: { tickangle: -45, tickfont: { color: COLORS.dim, size: 8 } },
                                yaxis: { tickfont: { color: COLORS.dim, size: 8 } },
                                margin: { l: 80, r: 80, t: 20, b: 80 },
                                paper_bgcolor: 'transparent'
                            }}
                        />
                    </div>
                </TerminalPanel>
            )}
            
            {/* Statistics Table */}
            <TerminalPanel title="FACTOR STABILITY & RISK METRICS">
                <DataTable
                    columns={[
                        { key: 'pc_index', label: 'PC' },
                        { key: 'mean_return', label: 'Ann. Return %', render: r => `${r.mean_return > 0 ? '+' : ''}${r.mean_return}%`,
                            getColor: r => r.mean_return > 0 ? COLORS.green : COLORS.red },
                        { key: 'volatility', label: 'Ann. Vol %', render: r => `${r.volatility}%` },
                        { key: 'sharpe', label: 'Sharpe', getColor: r => r.sharpe > 0.5 ? COLORS.green : r.sharpe > 0 ? COLORS.yellow : COLORS.red },
                        { key: 'max_drawdown', label: 'Max DD %', render: r => `${r.max_drawdown}%`, getColor: () => COLORS.red },
                        { key: 'market_correlation', label: 'Mkt Corr', getColor: r => Math.abs(r.market_correlation) > 0.7 ? COLORS.orange : COLORS.dim },
                        { key: 'trust_score', label: 'Trust', render: r => `${(r.trust_score * 100).toFixed(0)}%`,
                            getColor: r => r.trust_score > 0.7 ? COLORS.green : r.trust_score > 0.4 ? COLORS.yellow : COLORS.red }
                    ]}
                    data={stability}
                />
            </TerminalPanel>
        </div>
    );
}

// =============================================================================
// TAB 4: REDUNDANCY
// =============================================================================

function RedundancyTab({ projections, diversifiers, redundantPairs }) {
    const [chartExpanded, setChartExpanded] = useState(true);
    
    if (!projections?.length) return <div className="text-terminal-dim p-8 text-center">Run analysis to see redundancy</div>;
    
    const sectors = [...new Set(projections.map(p => p.sector))];
    const sectorColors = {};
    const palette = [COLORS.cyan, COLORS.green, COLORS.yellow, COLORS.purple, COLORS.orange, COLORS.red, COLORS.blue];
    sectors.forEach((s, i) => sectorColors[s] = palette[i % palette.length]);
    
    return (
        <div className="space-y-4">
            {/* PC Scatter Plot - Collapsible */}
            <div className="grid grid-cols-12 gap-4">
                <div className="col-span-12 lg:col-span-8">
                    <TerminalPanel title="PC1 vs PC2 ASSET PROJECTION" extra={
                        <button 
                            onClick={() => setChartExpanded(!chartExpanded)}
                            className="text-xs text-terminal-dim hover:text-terminal-cyan transition-colors font-mono"
                        >
                            {chartExpanded ? '▼ Collapse' : '▶ Expand'}
                        </button>
                    }>
                        <div className={`transition-all duration-300 ${chartExpanded ? 'h-[450px]' : 'h-48'} p-2`}>
                            <PlotlyChart
                                data={sectors.map(sector => ({
                                    x: projections.filter(p => p.sector === sector).map(p => p.pc1),
                                    y: projections.filter(p => p.sector === sector).map(p => p.pc2),
                                    text: projections.filter(p => p.sector === sector).map(p => p.ticker),
                                    mode: 'markers+text', type: 'scatter', name: sector,
                                    textposition: 'top center', textfont: { size: 9 },
                                    marker: { size: 10, color: sectorColors[sector] }
                                }))}
                                layout={{
                                    xaxis: { title: 'PC1 Loading', showgrid: true, gridcolor: '#333', zeroline: true },
                                    yaxis: { title: 'PC2 Loading', showgrid: true, gridcolor: '#333', zeroline: true },
                                    legend: { orientation: 'h', y: -0.1 },
                                    margin: { l: 60, r: 30, t: 20, b: 70 }
                                }}
                            />
                        </div>
                    </TerminalPanel>
                </div>
                
                <div className="col-span-12 lg:col-span-4 space-y-4">
                    <TerminalPanel title="TOP DIVERSIFIERS">
                        <div className="p-3 space-y-2 max-h-[420px] overflow-y-auto">
                            {diversifiers?.slice(0, 10).map((d, i) => (
                                <div key={i} className="flex items-center justify-between bg-terminal-black p-2 rounded">
                                    <div>
                                        <div className="font-mono text-sm">{d.ticker}</div>
                                        <div className="text-xs text-terminal-dim">{d.sector}</div>
                                    </div>
                                    <div className="text-right">
                                        <div className="font-mono" style={{ 
                                            color: d.classification === 'STRONG' ? COLORS.green 
                                                : d.classification === 'MODERATE' ? COLORS.yellow : COLORS.dim 
                                        }}>
                                            {d.diversifier_score}
                                        </div>
                                        <div className="text-xs text-terminal-dim">{d.classification}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </TerminalPanel>
                </div>
            </div>
            
            {/* Redundant Pairs */}
            <TerminalPanel title="REDUNDANT ASSET PAIRS (>85% Similarity)">
                {redundantPairs?.length > 0 ? (
                    <DataTable
                        columns={[
                            { key: 'asset_a', label: 'Asset A' },
                            { key: 'asset_b', label: 'Asset B' },
                            { key: 'similarity', label: 'Similarity', render: r => `${(r.similarity * 100).toFixed(1)}%`,
                                getColor: r => r.similarity > 0.95 ? COLORS.red : r.similarity > 0.9 ? COLORS.orange : COLORS.yellow },
                            { key: 'sector_match', label: 'Same Sector', render: r => r.sector_match ? '✓' : '✗',
                                getColor: r => r.sector_match ? COLORS.green : COLORS.dim },
                            { key: 'suggestion', label: 'Action' }
                        ]}
                        data={redundantPairs}
                        maxHeight="250px"
                    />
                ) : (
                    <div className="text-terminal-dim p-8 text-center">No highly redundant pairs found</div>
                )}
            </TerminalPanel>
        </div>
    );
}

// =============================================================================
// TAB 5: SHOCKS
// =============================================================================

function ShocksTab({ universeKey, lookbackDays }) {
    const [shockMagnitude, setShockMagnitude] = useState(2.0);
    const [shockedPC, setShockedPC] = useState(1);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [breaks, setBreaks] = useState([]);
    
    const runShock = async () => {
        setLoading(true);
        try {
            const shockConfig = { [shockedPC]: shockMagnitude };
            const res = await simulatePCAGodModeShock(universeKey, lookbackDays, shockConfig);
            setResult(res.simulation);
            
            // Also fetch breaks
            const breaksRes = await getPCAGodModeBreaks(universeKey, 504);
            setBreaks(breaksRes.breaks || []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };
    
    return (
        <div className="space-y-4">
            <div className="grid grid-cols-12 gap-4">
                {/* Shock Controls */}
                <div className="col-span-12 lg:col-span-4 space-y-4">
                    <TerminalPanel title="SHOCK ENGINE">
                        <div className="p-4 space-y-4">
                            <div>
                                <label className="text-xs text-terminal-dim">Target PC</label>
                                <select value={shockedPC} onChange={e => setShockedPC(parseInt(e.target.value))}
                                    className="w-full bg-terminal-black border border-terminal-gray text-terminal-text p-2 mt-1 rounded font-mono">
                                    {[1,2,3,4,5].map(pc => <option key={pc} value={pc}>PC{pc}</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="text-xs text-terminal-dim">Shock Magnitude (σ)</label>
                                <input type="range" min="-3" max="3" step="0.25" value={shockMagnitude}
                                    onChange={e => setShockMagnitude(parseFloat(e.target.value))}
                                    className="w-full mt-1" />
                                <div className="text-center font-mono text-terminal-yellow text-lg">
                                    {shockMagnitude > 0 ? '+' : ''}{shockMagnitude}σ
                                </div>
                            </div>
                            <button onClick={runShock} disabled={loading}
                                className="w-full bg-terminal-red text-white py-3 font-mono font-bold hover:bg-red-600 disabled:opacity-50 rounded">
                                {loading ? "SIMULATING..." : "⚡ RUN SHOCK"}
                            </button>
                        </div>
                    </TerminalPanel>
                    
                    {result && (
                        <div className="grid grid-cols-2 gap-3">
                            <MetricCard label="Market Impact" 
                                value={`${result.total_market_impact >= 0 ? '+' : ''}${(result.total_market_impact * 100).toFixed(2)}%`}
                                color={result.total_market_impact >= 0 ? COLORS.green : COLORS.red} large />
                            <MetricCard label="Dispersion" 
                                value={`${(result.dispersion * 100).toFixed(1)}%`} color={COLORS.dim} large />
                        </div>
                    )}
                </div>
                
                {/* Impact Chart */}
                <div className="col-span-12 lg:col-span-8">
                    <TerminalPanel title="SHOCK IMPACT BY ASSET">
                        {result?.asset_impacts ? (
                            <div className="h-80 p-2">
                                <PlotlyChart
                                    data={[{
                                        y: result.asset_impacts.slice(0, 15).map(a => a.ticker).reverse(),
                                        x: result.asset_impacts.slice(0, 15).map(a => a.impact_pct).reverse(),
                                        type: 'bar', orientation: 'h',
                                        marker: { 
                                            color: result.asset_impacts.slice(0, 15).map(a => 
                                                a.impact_pct >= 0 ? COLORS.green : COLORS.red
                                            ).reverse()
                                        }
                                    }]}
                                    layout={{
                                        xaxis: { title: 'Impact %', showgrid: true, gridcolor: '#333', zeroline: true },
                                        yaxis: { showgrid: false, tickfont: { size: 10 } },
                                        margin: { l: 80, r: 20, t: 20, b: 50 }
                                    }}
                                />
                            </div>
                        ) : (
                            <div className="h-80 flex items-center justify-center text-terminal-dim">
                                Configure shock and click RUN SHOCK
                            </div>
                        )}
                    </TerminalPanel>
                </div>
            </div>
            
            {/* Structural Breaks */}
            <TerminalPanel title="STRUCTURAL BREAK HISTORY">
                {breaks.length > 0 ? (
                    <DataTable
                        columns={[
                            { key: 'date', label: 'Date' },
                            { key: 'break_type', label: 'Type' },
                            { key: 'impact_score', label: 'Impact', render: r => (r.impact_score * 100).toFixed(0) + '%',
                                getColor: r => r.impact_score > 0.7 ? COLORS.red : r.impact_score > 0.4 ? COLORS.orange : COLORS.yellow },
                            { key: 'pc1_delta', label: 'PC1 Δ', render: r => `${r.pc1_delta > 0 ? '+' : ''}${r.pc1_delta}%`,
                                getColor: r => r.pc1_delta < -5 ? COLORS.red : r.pc1_delta > 5 ? COLORS.green : COLORS.dim },
                            { key: 'regime_label', label: 'Regime',
                                getColor: r => r.regime_label === 'Crisis' ? COLORS.red : COLORS.yellow }
                        ]}
                        data={breaks}
                        maxHeight="200px"
                    />
                ) : (
                    <div className="text-terminal-dim p-8 text-center">
                        {loading ? "Loading break data..." : "No structural breaks detected in analysis window"}
                    </div>
                )}
            </TerminalPanel>
        </div>
    );
}

// =============================================================================
// TAB 6: GOVERNANCE
// =============================================================================

function GovernanceTab({ metadata, quality, onExport }) {
    if (!metadata) return <div className="text-terminal-dim p-8 text-center">Run analysis to see governance</div>;
    
    const config = metadata.config || {};
    
    return (
        <div className="space-y-4">
            {/* Quality Panel */}
            <WarningBanner warnings={quality?.warnings} />
            
            <div className="grid grid-cols-2 gap-4">
                <TerminalPanel title="CONFIGURATION">
                    <div className="p-4 space-y-2 text-sm font-mono">
                        <div className="flex justify-between"><span className="text-terminal-dim">Universe</span><span className="text-terminal-yellow font-bold">{config.universe_key}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Lookback</span><span>{config.lookback_days}d</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Returns</span><span>{config.return_type}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Matrix</span><span>{config.matrix_type}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Normalization</span><span>{config.normalization}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Rolling</span><span>{config.rolling_enabled ? '✓' : '✗'}</span></div>
                    </div>
                </TerminalPanel>
                
                <TerminalPanel title="METADATA">
                    <div className="p-4 space-y-2 text-sm font-mono">
                        <div className="flex justify-between"><span className="text-terminal-dim">Run ID</span><span className="text-xs text-terminal-cyan">{metadata.run_id?.slice(0, 20)}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Config Hash</span><span className="text-xs">{metadata.config_hash?.slice(0, 12)}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Universe Hash</span><span className="text-xs">{metadata.universe_hash?.slice(0, 12)}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Assets</span><span>{metadata.data_stats?.n_assets}</span></div>
                        <div className="flex justify-between"><span className="text-terminal-dim">Observations</span><span>{metadata.data_stats?.n_observations}</span></div>
                    </div>
                </TerminalPanel>
            </div>
            
            {/* Export Center */}
            <TerminalPanel title="EXPORT CENTER">
                <div className="p-4">
                    <div className="grid grid-cols-4 gap-3">
                        <button onClick={() => onExport(['eigenvalues'])}
                            className="bg-terminal-black border border-terminal-gray p-3 rounded hover:border-terminal-cyan transition-colors text-left">
                            <div className="font-mono text-terminal-cyan">Eigenvalues</div>
                            <div className="text-xs text-terminal-dim mt-1">Variance explained per PC</div>
                        </button>
                        <button onClick={() => onExport(['loadings'])}
                            className="bg-terminal-black border border-terminal-gray p-3 rounded hover:border-terminal-cyan transition-colors text-left">
                            <div className="font-mono text-terminal-cyan">Loadings</div>
                            <div className="text-xs text-terminal-dim mt-1">Asset weights per PC</div>
                        </button>
                        <button onClick={() => onExport(['factor_returns'])}
                            className="bg-terminal-black border border-terminal-gray p-3 rounded hover:border-terminal-cyan transition-colors text-left">
                            <div className="font-mono text-terminal-cyan">Factor Returns</div>
                            <div className="text-xs text-terminal-dim mt-1">Time series of PC returns</div>
                        </button>
                        <button onClick={() => onExport(['eigenvalues', 'loadings', 'factor_returns', 'stability', 'diversifiers'])}
                            className="bg-terminal-cyan text-terminal-black p-3 rounded font-bold">
                            <div className="font-mono">Full Export</div>
                            <div className="text-xs mt-1">All data as JSON</div>
                        </button>
                    </div>
                </div>
            </TerminalPanel>
            
            {quality?.dropped_assets?.length > 0 && (
                <TerminalPanel title="DROPPED ASSETS">
                    <div className="p-4 text-sm text-terminal-dim font-mono">
                        {quality.dropped_assets.join(', ')}
                    </div>
                </TerminalPanel>
            )}
        </div>
    );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function PCAGodModeLab() {
    const [tickers, setTickers] = useState(["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "RELIANCE.NS", "BTC-USD"]);
    const [timeframe, setTimeframe] = useState("1Y");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState("structure");
    
    // Result States
    const [metadata, setMetadata] = useState(null);
    const [structure, setStructure] = useState(null);
    const [factors, setFactors] = useState([]);
    const [stability, setStability] = useState([]);
    const [factorReturns, setFactorReturns] = useState(null);
    const [loadingDrift, setLoadingDrift] = useState(null);
    const [pcDominance, setPcDominance] = useState(null);
    const [redundancy, setRedundancy] = useState(null);

    const getTimeframeDays = (tf) => {
        const mapping = {
            '1M': 30, '2M': 60, '3M': 90, '4M': 120, '5M': 150, '6M': 180,
            '1Y': 252, '2Y': 504, '3Y': 756, '4Y': 1008, 'MAX': 2000
        };
        return mapping[tf] || 252;
    };
    
    const runAnalysis = useCallback(async (forcedTimeframe) => {
        setLoading(true);
        setError(null);
        try {
            const days = getTimeframeDays(forcedTimeframe || timeframe);
            const res = await runPCAGodMode({
                universeKey: "CUSTOM",
                customTickers: tickers,
                lookbackDays: days,
                rollingEnabled: true
            });
            
            if (res.status === 'success' || res.success) {
                const data = res.data || res;
                setMetadata(data.metadata);
                setStructure(data.structure);
                setFactors(data.factors);
                setStability(data.stability);
                setFactorReturns(data.factor_returns);
                setLoadingDrift(data.loading_drift);
                setPcDominance(data.pc_dominance);
                setRedundancy({
                    projections: data.projections,
                    diversifiers: data.diversifiers,
                    redundantPairs: data.redundant_pairs
                });
            } else {
                setError(res.error || "Execution failed");
            }
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [tickers, timeframe]);

    // Auto-run on mount or change
    useEffect(() => {
        runAnalysis();
    }, [tickers, timeframe]);

    const handleExport = useCallback(async (formats) => {
        try {
            const res = await exportPCAGodModeData("CUSTOM", 252, formats);
            const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `pca_sovereign_export_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
        } catch (e) {
            setError("Export failed: " + e.message);
        }
    }, []);

    return (
        <div className="flex flex-col h-full gap-4 text-terminal-text font-mono bg-[#020202] p-4 overflow-hidden">
            {/* SOVEREIGN COMMANDER */}
            <SovereignCommandBar 
                title="PCA GOD MODE: EIGEN-PHYSICS ENGINE"
                tickers={tickers}
                onTickersChange={setTickers}
                startDate={timeframe}
                onStartDateChange={(tf) => {
                    setTimeframe(tf);
                }}
                onExecute={() => runAnalysis(timeframe)}
                loading={loading}
            />

            {/* TAB SELECTOR */}
            <div className="flex gap-1 p-1 bg-[#0d0d0d] border border-white/5 rounded-xl w-fit self-center">
                {TABS.map(tab => (
                    <button key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-2 px-6 py-2 rounded-lg font-mono text-[11px] font-black tracking-widest transition-all ${
                            activeTab === tab.id 
                            ? 'bg-terminal-yellow text-black shadow-[0_0_15px_rgba(255,204,0,0.3)]' 
                            : 'text-terminal-dim hover:text-white hover:bg-white/5'
                        }`}>
                        <span>{tab.icon}</span>
                        {tab.label.toUpperCase()}
                    </button>
                ))}
            </div>

            {/* MAIN VIEWPORT */}
            <div className="flex-1 overflow-y-auto min-h-0 pr-2 hide-scrollbar">
                {error && (
                    <div className="bg-red-950/20 border border-red-500/50 p-4 rounded-xl flex items-center gap-4 text-red-500 mb-4 animate-in fade-in slide-in-from-top-2">
                        <div className="p-3 bg-red-500/10 rounded-full">
                            <span className="text-xl">!</span>
                        </div>
                        <div>
                            <div className="font-black uppercase text-xs tracking-widest">System Analysis Breach</div>
                            <div className="text-[10px] opacity-80 font-bold">{error}</div>
                        </div>
                    </div>
                )}
                
                {!structure && !loading && (
                    <div className="h-full flex flex-col items-center justify-center text-terminal-dim space-y-4 py-20 animate-in fade-in duration-1000">
                        <div className="w-24 h-24 border border-terminal-gray/20 rounded-full flex items-center justify-center relative">
                            <div className="absolute inset-0 border border-terminal-yellow/20 rounded-full animate-ping-slow" />
                            <LayoutGrid size={32} className="text-terminal-gray/40" />
                        </div>
                        <div className="text-center font-black uppercase tracking-[0.4em] text-xs">
                            Awaiting Vector Injection & Execution
                        </div>
                        <div className="text-[9px] text-terminal-dim/50 font-bold uppercase tracking-[0.2em]">
                            System Prime. Parquet Depth: 2020-01-01
                        </div>
                    </div>
                )}

                {loading && (
                    <div className="h-full flex flex-col items-center justify-center space-y-8 py-20">
                        <div className="relative">
                            <div className="w-32 h-32 border border-terminal-yellow/10 rounded-full animate-ping" />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <RefreshCw className="text-terminal-yellow animate-spin" size={40} />
                            </div>
                        </div>
                        <div className="flex flex-col items-center gap-2">
                            <div className="text-terminal-yellow font-black uppercase tracking-[0.5em] text-sm animate-pulse">
                                Reconstructing Eigen-Field
                            </div>
                            <div className="text-[9px] text-terminal-dim font-bold uppercase tracking-widest">
                                Processing Covariance Tensors • Pure Python Execution
                            </div>
                        </div>
                    </div>
                )}

                {structure && !loading && (
                    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-10">
                        {activeTab === "structure" && <StructureTab data={structure} quality={metadata?.data_stats} />}
                        {activeTab === "factors" && <FactorsTab factors={factors} />}
                        {activeTab === "stability" && (
                            <StabilityTab 
                                stability={stability} 
                                factorReturns={factorReturns} 
                                loadingDrift={loadingDrift} 
                                pcDominance={pcDominance} 
                            />
                        )}
                        {activeTab === "redundancy" && (
                            <RedundancyTab 
                                projections={redundancy?.projections} 
                                diversifiers={redundancy?.diversifiers} 
                                redundantPairs={redundancy?.redundantPairs} 
                            />
                        )}
                        {activeTab === "governance" && (
                            <GovernanceTab 
                                metadata={metadata} 
                                quality={metadata?.data_stats} 
                                onExport={handleExport} 
                            />
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
