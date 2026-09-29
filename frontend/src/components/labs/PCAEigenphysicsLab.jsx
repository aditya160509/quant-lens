"use client";

import React, { useState, useCallback } from 'react';
import { runPCAEigenphysics, runPCAShock } from '@/lib/api';
import TerminalPanel from '@/components/TerminalPanel';
import { PlotlyChart } from '@/components/ui/plotly-chart';

// Universe options
const UNIVERSES = [
    { id: "MACRO", label: "Macro Assets" },
    { id: "ETF", label: "ETF Universe" },
    { id: "INDIA", label: "India (NSE)" },
    { id: "US", label: "US Equity" },
];

// Feature tabs - all 12 features organized
const FEATURE_TABS = [
    { id: "overview", label: "OVERVIEW" },
    { id: "collapse", label: "COLLAPSE" },
    { id: "structure", label: "STRUCTURE" },
    { id: "shock", label: "SHOCK SIM" },
    { id: "risk", label: "RISK" },
];

const STATE_COLORS = {
    stable: "#22c55e", normal: "#22c55e", watching: "#eab308", 
    warning: "#f97316", critical: "#ef4444", collapse: "#ef4444",
};

// ============================================================================
// HELPER COMPONENTS
// ============================================================================
function MetricCard({ label, value, color, bar, barColor, small }) {
    return (
        <div className={`bg-terminal-black ${small ? 'p-2' : 'p-3'} rounded`}>
            <div className={`${small ? 'text-[10px]' : 'text-xs'} text-terminal-dim`}>{label}</div>
            <div className={`${small ? 'text-base' : 'text-lg'} font-mono`} style={{ color }}>{value ?? '-'}</div>
            {bar !== undefined && bar !== null && (
                <div className="h-1 bg-terminal-gray rounded overflow-hidden mt-1">
                    <div className="h-full transition-all" style={{ width: `${Math.min(bar * 100, 100)}%`, background: barColor }} />
                </div>
            )}
        </div>
    );
}

function GovernorBadge({ score, state, color }) {
    return (
        <div className="flex items-center gap-3 bg-terminal-dark border border-terminal-gray px-4 py-2 rounded">
            <div className="w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold"
                style={{ 
                    background: `linear-gradient(135deg, ${color}33, ${color}11)`,
                    border: `2px solid ${color}`, color, boxShadow: `0 0 20px ${color}44`
                }}>
                {Math.round(score || 0)}
            </div>
            <div>
                <div className="text-xs text-terminal-dim uppercase tracking-wider">Governor</div>
                <div className="text-sm font-mono" style={{ color }}>{state?.toUpperCase() || 'LOADING'}</div>
            </div>
        </div>
    );
}

function StatsRow({ pcaState }) {
    if (!pcaState) return null;
    const stats = [
        { label: "Tickers", value: pcaState.N },
        { label: "Days", value: pcaState.T },
        { label: "Window", value: `${pcaState.window_days}d` },
        { label: "Entropy", value: pcaState.entropy?.toFixed(2) },
        { label: "K", value: pcaState.K },
        { label: "Gini", value: pcaState.eigen_gini?.toFixed(2) },
    ];
    return (
        <div className="grid grid-cols-6 gap-2 bg-terminal-dark border border-terminal-gray p-2 rounded">
            {stats.map((s, i) => (
                <div key={i} className="text-center">
                    <div className="text-xs text-terminal-dim">{s.label}</div>
                    <div className="text-sm font-mono text-terminal-text">{s.value ?? '-'}</div>
                </div>
            ))}
        </div>
    );
}

// ============================================================================
// OVERVIEW TAB - Governor Score + Quick Metrics
// ============================================================================
function OverviewTab({ pcaState, features, governorScore }) {
    const collapse = features?.collapse_gauge?.values || {};
    const dof = features?.degrees_of_freedom?.values || {};
    const instability = features?.instability_engine?.values || {};
    
    return (
        <div className="grid grid-cols-12 gap-4">
            {/* Governor Summary */}
            <div className="col-span-12 lg:col-span-4 bg-slate-900/50 border border-white/5 p-6 rounded-xl">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-6">Market Structural Fragility</div>
                <div className="flex items-center justify-center mb-6">
                    <div className="w-28 h-28 rounded-full flex items-center justify-center text-4xl font-bold font-mono"
                        style={{ 
                            background: `radial-gradient(circle at center, ${governorScore?.color || '#3b82f6'}22, transparent)`,
                            border: `2px solid ${governorScore?.color || '#3b82f6'}44`,
                            color: governorScore?.color || '#3b82f6',
                            boxShadow: `0 0 40px ${governorScore?.color || '#3b82f6'}11`
                        }}>
                        {Math.round(governorScore?.score || instability.instability_score || 0)}
                    </div>
                </div>
                <div className="text-center">
                    <div className="text-sm font-bold text-white uppercase tracking-wider">
                        {governorScore?.state?.replace('HIGHLY CONCENTRATED SYSTEM', 'Concentrated Risk') || instability.state || collapse.state || 'ANALYZING'}
                    </div>
                    <div className="text-[10px] text-slate-500 font-medium mt-1">Systemic Stability Index</div>
                </div>
            </div>
            
            {/* Quick Metrics Grid */}
            <div className="col-span-12 lg:col-span-8 grid grid-cols-4 gap-3">
                <MetricCard label="PC1 Dominance" 
                    value={collapse.pc1_share ? `${(collapse.pc1_share * 100).toFixed(1)}%` : '-'} 
                    color={collapse.pc1_share > 0.4 ? '#ff4444' : '#00ff6a'}
                    bar={collapse.pc1_share} barColor={collapse.pc1_share > 0.4 ? '#ff4444' : '#00ff6a'} />
                <MetricCard label="Entropy" value={collapse.normalized_entropy?.toFixed(3)} 
                    color="#00bfff" bar={collapse.normalized_entropy} barColor="#00bfff" />
                <MetricCard label="Effective Dims" value={dof.effective_dimensions?.toFixed(1)} color="#ffd60a" />
                <MetricCard label="Collapse Score" value={collapse.collapse_score?.toFixed(0)} 
                    color={STATE_COLORS[collapse.state] || '#888'} />
                <MetricCard label="K (90%)" value={dof.k90} color="#00bfff" />
                <MetricCard label="K (95%)" value={dof.k95} color="#00ff6a" />
                <MetricCard label="K (99%)" value={dof.k99} color="#ffd60a" />
                <MetricCard label="Gini Coef" value={collapse.eigen_gini?.toFixed(3)} color="#a855f7" />
            </div>
            
            {/* Variance Chart */}
            <div className="col-span-12">
                <TerminalPanel title="VARIANCE DISTRIBUTION">
                    {pcaState?.explained_variance ? (
                        <div className="h-56 p-2">
                            <PlotlyChart
                                data={[
                                    {
                                        x: pcaState.explained_variance.slice(0, 10).map((_, i) => `PC${i+1}`),
                                        y: pcaState.explained_variance.slice(0, 10).map(v => v * 100),
                                        type: 'bar', name: 'Explained %', marker: { color: '#00bfff' }
                                    },
                                    {
                                        x: pcaState.cumulative_variance.slice(0, 10).map((_, i) => `PC${i+1}`),
                                        y: pcaState.cumulative_variance.slice(0, 10).map(v => v * 100),
                                        type: 'scatter', mode: 'lines+markers', name: 'Cumulative',
                                        yaxis: 'y2', line: { color: '#ffd60a', width: 2 }
                                    }
                                ]}
                                layout={{
                                    xaxis: { showgrid: false },
                                    yaxis: { showgrid: true, gridcolor: '#333', title: '%' },
                                    yaxis2: { overlaying: 'y', side: 'right', range: [0, 100] },
                                    legend: { orientation: 'h', y: -0.15 },
                                    margin: { l: 50, r: 40, t: 20, b: 50 }
                                }}
                            />
                        </div>
                    ) : <div className="h-56 flex items-center justify-center text-terminal-dim">Loading...</div>}
                </TerminalPanel>
            </div>
        </div>
    );
}

// ============================================================================
// COLLAPSE TAB - Full Collapse Gauge Details
// ============================================================================
function CollapseTab({ features, pcaState }) {
    const data = features?.collapse_gauge?.values || {};
    const color = STATE_COLORS[data.state] || '#888';
    
    const gaugeData = [{
        type: 'indicator', mode: 'gauge+number', value: data.collapse_score || 0,
        gauge: {
            axis: { range: [0, 100], tickcolor: "#333" },
            bar: { color }, bgcolor: "#1a1a2e", borderwidth: 0,
            steps: [
                { range: [0, 30], color: 'rgba(34, 197, 94, 0.2)' },
                { range: [30, 60], color: 'rgba(234, 179, 8, 0.2)' },
                { range: [60, 80], color: 'rgba(249, 115, 22, 0.2)' },
                { range: [80, 100], color: 'rgba(239, 68, 68, 0.2)' },
            ]
        },
        number: { font: { size: 40, color } },
    }];
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 lg:col-span-6">
                <TerminalPanel title="COLLAPSE GAUGE">
                    <div className="h-64 p-4">
                        <PlotlyChart data={gaugeData} layout={{
                            margin: { t: 40, r: 40, l: 40, b: 40 },
                            paper_bgcolor: 'transparent', font: { color: '#888' }
                        }} />
                    </div>
                </TerminalPanel>
            </div>
            <div className="col-span-12 lg:col-span-6 grid grid-cols-2 gap-3 content-start">
                <MetricCard label="PC1 Dominance" value={data.pc1_share ? `${(data.pc1_share * 100).toFixed(1)}%` : '-'} 
                    color={data.pc1_share > 0.4 ? '#ff4444' : '#00ff6a'}
                    bar={data.pc1_share} barColor={data.pc1_share > 0.4 ? '#ff4444' : '#00ff6a'} />
                <MetricCard label="Entropy (Normalized)" value={data.normalized_entropy?.toFixed(3)} 
                    color="#00bfff" bar={data.normalized_entropy} barColor="#00bfff" />
                <MetricCard label="Participation Ratio" value={data.participation_ratio?.toFixed(2)} color="#ffd60a" />
                <MetricCard label="Effective Dims" value={data.effective_dimensions?.toFixed(1)} color="#f97316" />
                <MetricCard label="Gini Coefficient" value={data.eigen_gini?.toFixed(3)} 
                    color="#a855f7" bar={data.eigen_gini} barColor="#a855f7" />
                <MetricCard label="State" value={data.state?.toUpperCase()} color={color} />
            </div>
            <div className="col-span-12 text-sm text-terminal-dim bg-terminal-black p-3 rounded">
                <strong>Interpretation:</strong> Collapse Score &gt;60 indicates elevated market collapse risk due to PC1 dominance.
                Low entropy means reduced diversification benefit. State: <span style={{color}}>{data.state?.toUpperCase() || '-'}</span>
            </div>
        </div>
    );
}

// ============================================================================
// STRUCTURE TAB - DOF, Topology, Decoherence, Tail Shift
// ============================================================================
function StructureTab({ features, pcaState }) {
    const dof = features?.degrees_of_freedom?.values || {};
    const topo = features?.eigen_topology?.values || {};
    const decoh = features?.decoherence_index?.values || {};
    const tail = features?.tail_shift?.values || {};
    const recon = features?.reconstruction_failure?.values || {};
    
    const variance = pcaState?.explained_variance || [];
    const cumVar = pcaState?.cumulative_variance || [];
    
    return (
        <div className="grid grid-cols-12 gap-4">
            {/* DOF Metrics */}
            <div className="col-span-12 grid grid-cols-5 gap-3">
                <MetricCard label="K (90%)" value={dof.k90} color="#00bfff" />
                <MetricCard label="K (95%)" value={dof.k95} color="#00ff6a" />
                <MetricCard label="K (99%)" value={dof.k99} color="#ffd60a" />
                <MetricCard label="Effective Dims" value={dof.effective_dimensions?.toFixed(1)} color="#f97316" />
                <MetricCard label="Max Dims (N)" value={dof.N} color="#888" />
            </div>
            
            {/* Variance Chart */}
            <div className="col-span-12 lg:col-span-8">
                <TerminalPanel title="VARIANCE BY COMPONENT">
                    <div className="h-64 p-2">
                        <PlotlyChart
                            data={[
                                { x: variance.slice(0, 15).map((_, i) => `PC${i+1}`),
                                  y: variance.slice(0, 15).map(v => v * 100),
                                  type: 'bar', name: 'Individual', marker: { color: '#00bfff' } },
                                { x: cumVar.slice(0, 15).map((_, i) => `PC${i+1}`),
                                  y: cumVar.slice(0, 15).map(v => v * 100),
                                  type: 'scatter', mode: 'lines+markers', name: 'Cumulative',
                                  yaxis: 'y2', line: { color: '#ffd60a', width: 2 } }
                            ]}
                            layout={{
                                xaxis: { showgrid: false },
                                yaxis: { showgrid: true, gridcolor: '#333', title: 'Var %' },
                                yaxis2: { overlaying: 'y', side: 'right', range: [0, 100] },
                                legend: { orientation: 'h', y: -0.2 },
                                margin: { l: 50, r: 50, t: 20, b: 60 }
                            }}
                        />
                    </div>
                </TerminalPanel>
            </div>
            
            {/* Topology & Decoherence */}
            <div className="col-span-12 lg:col-span-4 space-y-3">
                <TerminalPanel title="TOPOLOGY">
                    <div className="p-3 grid grid-cols-2 gap-2">
                        <MetricCard small label="Nodes" value={topo.n_nodes} color="#00bfff" />
                        <MetricCard small label="Clusters" value={topo.n_clusters} color="#ffd60a" />
                        <MetricCard small label="Density" value={topo.density ? `${(topo.density * 100).toFixed(1)}%` : '-'} color="#00ff6a" />
                        <MetricCard small label="Avg Degree" value={topo.avg_degree?.toFixed(1)} color="#a855f7" />
                    </div>
                </TerminalPanel>
                <TerminalPanel title="DECOHERENCE">
                    <div className="p-3 space-y-2">
                        <MetricCard small label="Decoherence Index" value={decoh.decoherence?.toFixed(4)} 
                            color={decoh.decoherence > 0.2 ? '#ff4444' : '#00ff6a'} />
                        <MetricCard small label="Status" value={decoh.status?.toUpperCase()} 
                            color={decoh.status === 'high' ? '#ff4444' : '#00ff6a'} />
                    </div>
                </TerminalPanel>
            </div>
            
            {/* Tail Shift & Reconstruction */}
            <div className="col-span-12 grid grid-cols-2 gap-4">
                <TerminalPanel title="TAIL SHIFT CORRELATION">
                    <div className="p-3 grid grid-cols-3 gap-2">
                        <MetricCard small label="Left Tail" value={tail.left_tail_corr?.toFixed(3)} color="#ef4444" />
                        <MetricCard small label="Normal" value={tail.normal_corr?.toFixed(3)} color="#888" />
                        <MetricCard small label="Right Tail" value={tail.right_tail_corr?.toFixed(3)} color="#22c55e" />
                        <MetricCard small label="Tail Shift" value={tail.tail_shift ? `${tail.tail_shift > 0 ? '+' : ''}${tail.tail_shift.toFixed(3)}` : '-'} 
                            color={Math.abs(tail.tail_shift || 0) > 0.1 ? '#ff4444' : '#00ff6a'} />
                        <MetricCard small label="Tail Uplift" value={tail.tail_uplift?.toFixed(3)} color="#ffd60a" />
                        <MetricCard small label="Left Days" value={tail.left_days} color="#888" />
                    </div>
                </TerminalPanel>
                <TerminalPanel title="RECONSTRUCTION FAILURE">
                    <div className="p-3 grid grid-cols-2 gap-2">
                        <MetricCard small label="Explained" value={recon.explained_ratio ? `${(recon.explained_ratio * 100).toFixed(1)}%` : '-'} 
                            color="#00bfff" bar={recon.explained_ratio} barColor="#00bfff" />
                        <MetricCard small label="Failure" value={recon.failure_ratio ? `${(recon.failure_ratio * 100).toFixed(1)}%` : '-'} 
                            color={recon.failure_ratio > 0.2 ? '#ff4444' : '#22c55e'} />
                        <div className="col-span-2 text-xs text-terminal-dim">
                            {recon.worst_tickers?.slice(0, 3).map(t => t.ticker).join(', ') || 'No data'}
                        </div>
                    </div>
                </TerminalPanel>
            </div>
        </div>
    );
}

// ============================================================================
// SHOCK TAB - Shock Simulator
// ============================================================================
function ShockTab({ universeKey, windowDays }) {
    const [pc1, setPC1] = useState(2);
    const [pc2, setPC2] = useState(0);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    
    const runShock = async () => {
        setLoading(true);
        try {
            const shocks = {};
            if (pc1 !== 0) shocks["1"] = pc1;
            if (pc2 !== 0) shocks["2"] = pc2;
            const res = await runPCAShock(universeKey, windowDays, shocks);
            setResult(res.shock_result);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };
    
    const impacts = result?.values?.ticker_impacts 
        ? Object.entries(result.values.ticker_impacts)
            .map(([t, i]) => ({ ticker: t, impact: i * 100 }))
            .sort((a, b) => b.impact - a.impact)
        : [];
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 lg:col-span-4 space-y-4">
                <TerminalPanel title="SHOCK CONTROLS">
                    <div className="p-4 space-y-4">
                        <div>
                            <label className="text-xs text-terminal-dim">PC1 Shock (Market)</label>
                            <input type="range" min="-3" max="3" step="0.5" value={pc1}
                                onChange={e => setPC1(parseFloat(e.target.value))}
                                className="w-full accent-yellow-500" />
                            <div className="text-center font-mono text-terminal-yellow">{pc1 > 0 ? '+' : ''}{pc1}σ</div>
                        </div>
                        <div>
                            <label className="text-xs text-terminal-dim">PC2 Shock (Rotation)</label>
                            <input type="range" min="-3" max="3" step="0.5" value={pc2}
                                onChange={e => setPC2(parseFloat(e.target.value))}
                                className="w-full accent-cyan-500" />
                            <div className="text-center font-mono text-terminal-cyan">{pc2 > 0 ? '+' : ''}{pc2}σ</div>
                        </div>
                        <button onClick={runShock} disabled={loading || (pc1 === 0 && pc2 === 0)}
                            className="w-full bg-terminal-yellow text-terminal-black py-3 font-mono font-bold hover:bg-yellow-400 disabled:opacity-50">
                            {loading ? "SIMULATING..." : "RUN SHOCK"}
                        </button>
                    </div>
                </TerminalPanel>
                {result && (
                    <div className="grid grid-cols-2 gap-2">
                        <MetricCard label="Market Impact" 
                            value={`${result.values.total_market_impact >= 0 ? '+' : ''}${(result.values.total_market_impact * 100).toFixed(2)}%`}
                            color={result.values.total_market_impact >= 0 ? '#22c55e' : '#ef4444'} />
                        <MetricCard label="Dispersion" value={`${(result.values.dispersion * 100).toFixed(1)}%`} color="#888" />
                    </div>
                )}
            </div>
            <div className="col-span-12 lg:col-span-8">
                <TerminalPanel title="SHOCK IMPACT BY TICKER">
                    {impacts.length > 0 ? (
                        <div className="h-80 p-2">
                            <PlotlyChart
                                data={[{
                                    y: impacts.slice(0, 15).map(d => d.ticker),
                                    x: impacts.slice(0, 15).map(d => d.impact),
                                    type: 'bar', orientation: 'h',
                                    marker: { color: impacts.slice(0, 15).map(d => d.impact >= 0 ? '#22c55e' : '#ef4444') }
                                }]}
                                layout={{
                                    xaxis: { title: 'Impact %', showgrid: true, gridcolor: '#333', zeroline: true, zerolinecolor: '#666' },
                                    yaxis: { showgrid: false, automargin: true, tickfont: { size: 10 } },
                                    margin: { l: 80, r: 20, t: 20, b: 50 }
                                }}
                            />
                        </div>
                    ) : (
                        <div className="h-80 flex items-center justify-center text-terminal-dim">
                            Configure shock parameters and click RUN SHOCK
                        </div>
                    )}
                </TerminalPanel>
            </div>
        </div>
    );
}

// ============================================================================
// RISK TAB - Instability, Liquidity, Crisis Signature
// ============================================================================
function RiskTab({ features, pcaState }) {
    const collapse = features?.collapse_gauge?.values || {};
    const instability = features?.instability_engine?.values || {};
    const lii = features?.liquidity_illusion?.values || {};
    const unwind = features?.forced_unwind_surface?.values || {};
    const crisis = features?.crisis_signature?.values || {};
    
    const riskColors = { HIGH: '#ef4444', MEDIUM: '#ffd60a', LOW: '#22c55e' };
    const pc1Risk = collapse.pc1_share > 0.5 ? 'HIGH' : collapse.pc1_share > 0.3 ? 'MEDIUM' : 'LOW';
    const entropyRisk = collapse.normalized_entropy < 0.5 ? 'HIGH' : collapse.normalized_entropy < 0.7 ? 'MEDIUM' : 'LOW';
    
    return (
        <div className="grid grid-cols-12 gap-4">
            {/* Instability Engine */}
            <div className="col-span-12 lg:col-span-4">
                <TerminalPanel title="INSTABILITY ENGINE">
                    <div className="p-4 space-y-4">
                        <div className="text-center">
                            <div className="text-4xl font-mono" style={{ color: instability.color || '#888' }}>
                                {instability.instability_score?.toFixed(0) || '-'}
                            </div>
                            <div className="text-xs text-terminal-dim mt-1">Instability Score (0-100)</div>
                            <div className="text-lg font-mono uppercase mt-2" style={{ color: instability.color }}>
                                {instability.state || '-'}
                            </div>
                        </div>
                        <div className="space-y-2 text-xs">
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">PC1 Risk</span>
                                <span style={{ color: riskColors[pc1Risk] }}>{pc1Risk}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Entropy Risk</span>
                                <span style={{ color: riskColors[entropyRisk] }}>{entropyRisk}</span>
                            </div>
                        </div>
                    </div>
                </TerminalPanel>
            </div>
            
            {/* Liquidity & Unwind */}
            <div className="col-span-12 lg:col-span-4 space-y-4">
                <TerminalPanel title="LIQUIDITY ILLUSION">
                    <div className="p-3 grid grid-cols-2 gap-2">
                        <MetricCard small label="LII Score" value={lii.lii?.toFixed(2)} 
                            color={lii.lii > 1.5 ? '#ff4444' : '#00ff6a'} />
                        <MetricCard small label="Max Crowding" value={lii.max_crowding?.toFixed(2)} color="#ffd60a" />
                    </div>
                    <div className="px-3 pb-3 text-xs text-terminal-dim">
                        {lii.crowded_positions?.slice(0, 3).map(p => p.ticker).join(', ') || 'No crowding detected'}
                    </div>
                </TerminalPanel>
                <TerminalPanel title="FORCED UNWIND">
                    <div className="p-3 grid grid-cols-2 gap-2">
                        <MetricCard small label="Door Crowding" value={unwind.door_crowding?.toFixed(3)} color="#f97316" />
                        <MetricCard small label="Tickers" value={unwind.n_tickers} color="#888" />
                    </div>
                </TerminalPanel>
            </div>
            
            {/* Crisis Signature */}
            <div className="col-span-12 lg:col-span-4">
                <TerminalPanel title="CRISIS SIGNATURE MATCH">
                    <div className="p-4 space-y-4">
                        <div className="text-center">
                            <div className="text-xs text-terminal-dim mb-2">Closest Match</div>
                            <div className="text-lg font-mono text-terminal-yellow">
                                {crisis.closest_match?.name || 'None Detected'}
                            </div>
                            {crisis.closest_match && (
                                <div className="text-sm text-terminal-dim mt-1">
                                    Similarity: {(crisis.closest_match.similarity * 100).toFixed(0)}%
                                </div>
                            )}
                        </div>
                        <div className="space-y-1 text-xs">
                            {crisis.matches?.slice(0, 4).map((m, i) => (
                                <div key={i} className="flex justify-between bg-terminal-black px-2 py-1 rounded">
                                    <span className="text-terminal-text">{m.name}</span>
                                    <span className="text-terminal-dim">{(m.similarity * 100).toFixed(0)}%</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </TerminalPanel>
            </div>
            
            {/* Top Drivers */}
            <div className="col-span-12">
                <TerminalPanel title="INSTABILITY DRIVERS">
                    <div className="p-3 grid grid-cols-5 gap-2">
                        {(instability.top_drivers || []).slice(0, 5).map((d, i) => (
                            <div key={i} className="bg-terminal-black p-2 rounded text-center">
                                <div className="text-xs text-terminal-dim">{d.driver}</div>
                                <div className="text-lg font-mono text-terminal-yellow">{d.contribution?.toFixed(1)}</div>
                            </div>
                        ))}
                        {(!instability.top_drivers || instability.top_drivers.length === 0) && (
                            <div className="col-span-5 text-center text-terminal-dim py-4">No active drivers</div>
                        )}
                    </div>
                </TerminalPanel>
            </div>
        </div>
    );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function PCAEigenphysicsLab() {
    const [universe, setUniverse] = useState("INDIA");
    const [windowDays, setWindowDays] = useState(60);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState("overview");
    const [hasRun, setHasRun] = useState(false);  // Track if analysis has been run
    
    const runAnalysis = useCallback(async () => {
        setLoading(true); setError(null); setHasRun(true);
        try {
            const result = await runPCAEigenphysics({ 
                universeKey: universe, 
                lookbackDays: 252, 
                windows: [windowDays],
                includeAllFeatures: true 
            });
            setData(result);
        } catch (err) { setError(err.message); }
        finally { setLoading(false); }
    }, [universe, windowDays]);
    
    // NO AUTO-LOAD: Removed useEffect that auto-ran analysis
    // User must click RUN button to start analysis
    
    // Clear data when universe/window changes
    const handleUniverseChange = (e) => {
        setUniverse(e.target.value);
        setData(null);
        setHasRun(false);
    };
    
    const handleWindowChange = (e) => {
        setWindowDays(parseInt(e.target.value));
        setData(null);
        setHasRun(false);
    };
    
    const windowKey = `window_${windowDays}`;
    const pcaState = data?.results?.[windowKey]?.pca_state;
    const features = data?.results?.[windowKey]?.features;
    const governorScore = data?.governor_score;
    
    return (
        <div className="space-y-3 p-4 h-full overflow-auto">
            {/* Header */}
            <div className="flex flex-wrap gap-3 items-center bg-terminal-dark border border-terminal-gray p-3 rounded">
                <select value={universe} onChange={handleUniverseChange}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-2 font-mono text-sm outline-none rounded">
                    {UNIVERSES.map(u => <option key={u.id} value={u.id}>{u.label}</option>)}
                </select>
                <select value={windowDays} onChange={handleWindowChange}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-2 font-mono text-sm outline-none rounded">
                    <option value={20}>20d</option>
                    <option value={60}>60d</option>
                    <option value={120}>120d</option>
                </select>
                <button onClick={runAnalysis} disabled={loading}
                    className="bg-terminal-yellow text-terminal-black px-5 py-2 font-mono text-sm font-bold hover:bg-yellow-400 disabled:opacity-50 rounded">
                    {loading ? "ANALYZING..." : "RUN"}
                </button>
                
                {/* Tabs - only show when data is loaded */}
                {hasRun && data && (
                    <div className="flex gap-1 ml-4">
                        {FEATURE_TABS.map(tab => (
                            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                                className={`px-3 py-1 font-mono text-xs rounded transition-colors ${
                                    activeTab === tab.id 
                                    ? 'bg-terminal-yellow text-terminal-black' 
                                    : 'bg-terminal-black text-terminal-dim hover:text-terminal-text'
                                }`}>
                                {tab.label}
                            </button>
                        ))}
                    </div>
                )}
                
                {governorScore && <div className="ml-auto"><GovernorBadge {...governorScore} /></div>}
            </div>
            
            {error && <div className="text-red-500 font-mono p-3 border border-red-900 bg-red-900/20 rounded">{error}</div>}
            
            {/* Empty State - before RUN is clicked */}
                <div className="flex flex-col items-center justify-center py-20 text-center border border-slate-800 border-dashed rounded-xl bg-slate-900/10">
                    <div className="w-16 h-16 rounded-full bg-blue-500/10 flex items-center justify-center mb-6">
                        <div className="w-6 h-6 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                    </div>
                    <div className="text-lg font-bold text-white mb-2">Portfolio Structure Engine</div>
                    <div className="text-sm font-medium text-slate-500 mb-8 max-w-md">
                        Advanced principal component analysis for risk decomposition, 
                        regime shift detection, and universe structural analysis.
                    </div>
                    <button onClick={runAnalysis} disabled={loading}
                        className="px-10 py-3 bg-blue-600 text-white font-bold text-xs uppercase tracking-widest rounded-lg hover:bg-blue-500 transition-all shadow-lg shadow-blue-900/20">
                        Initialize Analysis
                    </button>
                </div>
            
            {/* Loading State */}
            {loading && !data && (
                <div className="text-terminal-dim font-mono p-8 text-center border border-terminal-gray border-dashed rounded animate-pulse">
                    Computing PCA with all 12 features...
                </div>
            )}
            
            {/* Results */}
            {data && pcaState && (
                <>
                    <StatsRow pcaState={pcaState} />
                    
                    {activeTab === "overview" && <OverviewTab pcaState={pcaState} features={features} governorScore={governorScore} />}
                    {activeTab === "collapse" && <CollapseTab features={features} pcaState={pcaState} />}
                    {activeTab === "structure" && <StructureTab features={features} pcaState={pcaState} />}
                    {activeTab === "shock" && <ShockTab universeKey={universe} windowDays={windowDays} />}
                    {activeTab === "risk" && <RiskTab features={features} pcaState={pcaState} />}
                </>
            )}
        </div>
    );
}

