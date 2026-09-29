"use client";

import React, { useState, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import TerminalPanel from '@/components/TerminalPanel';

// Dynamic import for Plotly with no SSR
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

/**
 * Liquidity Intelligence Lab - 7 Systems Dashboard
 * 
 * TABBED interface with:
 * 1. Liquidity State Manifold
 * 2. Cliff & Vacuum Detection  
 * 3. Contagion & Transmission
 * 4. Absorption & Capacity
 * 5. Regime Transition Engine
 * 6. Volatility-Liquidity Feedback
 * 7. Crisis Fingerprint Vault
 */

// =============================================================================
// CONSTANTS
// =============================================================================
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const PHASE_COLORS = {
    tight: "#22c55e",
    normal: "#3b82f6",
    fragile: "#eab308",
    stress: "#f97316",
    crisis: "#ef4444",
};

const SYSTEM_TABS = [
    { id: "manifold", label: "MANIFOLD", icon: "●" },
    { id: "cliff", label: "CLIFF", icon: "△" },
    { id: "contagion", label: "CONTAGION", icon: "◎" },
    { id: "capacity", label: "CAPACITY", icon: "▤" },
    { id: "regimes", label: "REGIMES", icon: "◈" },
    { id: "feedback", label: "FEEDBACK", icon: "↺" },
    { id: "fingerprint", label: "FINGERPRINT", icon: "⚿" },
];

// =============================================================================
// API FUNCTIONS
// =============================================================================
const fetchManifold = async (params) => {
    const url = `${API_BASE}/api/liquidity/state-manifold?universe_key=${params.universe}&window=${params.window}&lookback_days=${params.lookback}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch manifold');
    return res.json();
};

const fetchCliffVacuum = async (params) => {
    const url = `${API_BASE}/api/liquidity/cliff-vacuum?universe_key=${params.universe}&window=${params.window}&lookback_days=${params.lookback}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch cliff data');
    return res.json();
};

const fetchContagion = async (params) => {
    const url = `${API_BASE}/api/liquidity/contagion?universe_key=${params.universe}&window=${params.window}&lookback_days=${params.lookback}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch contagion');
    return res.json();
};

const fetchCapacity = async (params) => {
    const url = `${API_BASE}/api/liquidity/capacity?universe_key=${params.universe}&window=${params.window}&lookback_days=${params.lookback}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch capacity');
    return res.json();
};

const fetchRegimes = async (params) => {
    const url = `${API_BASE}/api/liquidity/regimes?universe_key=${params.universe}&window=${params.window}&lookback_days=${params.lookback}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch regimes');
    return res.json();
};

const fetchFeedback = async (params) => {
    const url = `${API_BASE}/api/liquidity/feedback?universe_key=${params.universe}&window=${params.window}&lookback_days=${params.lookback}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch feedback');
    return res.json();
};

const fetchFingerprint = async (params) => {
    const url = `${API_BASE}/api/liquidity/fingerprint?universe_key=${params.universe}&window=${params.window}&lookback_days=${params.lookback}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch fingerprint');
    return res.json();
};

// =============================================================================
// SHARED COMPONENTS
// =============================================================================
const MetricCard = ({ label, value, color, subtext }) => (
    <div className="bg-terminal-darker/40 rounded border border-terminal-gray/30 p-3">
        <div className="text-[10px] font-mono text-terminal-dim uppercase">{label}</div>
        <div className="text-lg font-mono font-bold" style={{ color: color || '#fff' }}>{value ?? '—'}</div>
        {subtext && <div className="text-[9px] font-mono text-terminal-dim mt-1">{subtext}</div>}
    </div>
);

const DataTable = ({ data, columns, maxRows = 20 }) => {
    if (!data || data.length === 0) return <div className="text-terminal-dim font-mono text-sm">No data</div>;
    
    return (
        <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full text-xs font-mono">
                <thead>
                    <tr className="border-b border-terminal-gray/30">
                        {columns.map((col, i) => (
                            <th key={i} className="px-2 py-1 text-left text-terminal-dim">{col.label}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {data.slice(0, maxRows).map((row, ri) => (
                        <tr key={ri} className="border-b border-terminal-gray/10">
                            {columns.map((col, ci) => (
                                <td key={ci} className="px-2 py-1" style={{ color: col.color?.(row) }}>
                                    {col.render ? col.render(row) : row[col.key]}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

// =============================================================================
// TAB COMPONENTS
// =============================================================================
const ManifoldTab = ({ data, loading }) => {
    if (loading) return <div className="p-4 text-terminal-dim font-mono">Loading...</div>;
    if (!data?.manifold_coordinates) return <div className="p-4 text-terminal-dim font-mono">No data</div>;
    
    const coords = data.manifold_coordinates;
    const summary = data.summary || {};
    const sectorStats = data.sector_stats || {};
    const phaseDistribution = data.phase_distribution || {};
    
    const plotData = [{
        type: 'scatter3d',
        mode: 'markers',
        x: coords.map(c => c.x),
        y: coords.map(c => c.y),
        z: coords.map(c => c.z),
        text: coords.map(c => `${c.ticker} (${c.sector || 'Other'})`),
        marker: { size: 5, color: coords.map(c => PHASE_COLORS[c.phase] || "#888"), opacity: 0.8 },
        hovertemplate: '%{text}<br>X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>'
    }];
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 grid grid-cols-6 gap-3">
                <MetricCard label="Avg Stability" value={summary.avg_stability_score?.toFixed(1)} color="#22c55e" />
                <MetricCard label="Avg Fragility" value={summary.avg_fragility_score?.toFixed(1)} color="#f97316" />
                <MetricCard label="Persistence" value={summary.avg_persistence_score?.toFixed(1)} color="#8b5cf6" />
                <MetricCard label="Loop Gain" value={summary.avg_loop_gain?.toFixed(4)} color="#06b6d4" />
                <MetricCard label="Safe Capacity" value={`$${summary.total_safe_capacity?.toFixed(0)}M`} color="#a855f7" />
                <MetricCard label="Universe" value={coords.length} color="#3b82f6" />
            </div>
            <div className="col-span-12 lg:col-span-6 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-2">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-2">3D LIQUIDITY MANIFOLD</div>
                <Plot
                    data={plotData}
                    layout={{
                        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
                        font: { color: '#888', family: 'monospace', size: 9 },
                        margin: { l: 0, r: 0, t: 0, b: 0 },
                        scene: {
                            xaxis: { title: 'STABILITY', gridcolor: '#333' },
                            yaxis: { title: 'DEPTH', gridcolor: '#333' },
                            zaxis: { title: 'RESP', gridcolor: '#333' },
                            bgcolor: 'rgba(0,0,0,0)',
                        },
                    }}
                    config={{ displayModeBar: false }}
                    style={{ width: '100%', height: '320px' }}
                />
            </div>
            <div className="col-span-12 lg:col-span-6 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-3">SECTOR PROFILES</div>
                <div className="space-y-2 max-h-72 overflow-y-auto">
                    {Object.entries(sectorStats).sort((a, b) => b[1].count - a[1].count).map(([sector, stats]) => (
                        <div key={sector} className="flex justify-between p-2 rounded bg-terminal-gray/10">
                            <span className="text-sm font-mono font-bold text-terminal-text">{sector}</span>
                            <span className="text-xs font-mono text-terminal-dim">
                                S:{stats.avg_stability?.toFixed(0)} F:{stats.avg_fragility?.toFixed(0)} ({stats.count})
                            </span>
                        </div>
                    ))}
                </div>
            </div>
            <div className="col-span-12 lg:col-span-4 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-3">PHASE DISTRIBUTION</div>
                <div className="space-y-2">
                    {Object.entries(phaseDistribution).sort((a, b) => b[1] - a[1]).map(([phase, count]) => (
                        <div key={phase} className="flex items-center gap-3">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PHASE_COLORS[phase] }}></div>
                            <span className="text-sm font-mono uppercase flex-1" style={{ color: PHASE_COLORS[phase] }}>{phase}</span>
                            <span className="text-sm font-mono text-terminal-text">{count}</span>
                            <span className="text-xs font-mono text-terminal-dim">({(count / coords.length * 100).toFixed(0)}%)</span>
                        </div>
                    ))}
                </div>
            </div>
            <div className="col-span-12 lg:col-span-8 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-2">TICKER STATES</div>
                <DataTable 
                    data={data.ticker_states}
                    columns={[
                        { key: 'ticker', label: 'Ticker' },
                        { key: 'stability_score', label: 'Stability', render: r => r.stability_score?.toFixed(1), color: r => r.stability_score > 50 ? '#22c55e' : '#ef4444' },
                        { key: 'fragility_score', label: 'Fragility', render: r => r.fragility_score?.toFixed(1), color: r => r.fragility_score > 50 ? '#ef4444' : '#22c55e' },
                        { key: 'persistence_score', label: 'Persist', render: r => r.persistence_score?.toFixed(1) },
                        { key: 'half_life', label: 'Half-Life', render: r => r.half_life > 0 ? `${r.half_life?.toFixed(1)}d` : '—' },
                    ]}
                />
            </div>
        </div>
    );
};

const CliffTab = ({ data, loading }) => {
    if (loading) return <div className="p-4 text-terminal-dim font-mono">Loading...</div>;
    if (!data?.cliff_metrics) return <div className="p-4 text-terminal-dim font-mono">No data</div>;
    
    const summary = data.summary || {};
    const vacuumCandidates = data.vacuum_candidates || [];
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 grid grid-cols-4 gap-3">
                <MetricCard label="Avg Cliff Distance" value={summary.avg_cliff_distance?.toFixed(4)} color="#f97316" />
                <MetricCard label="Avg Vacuum Prob" value={`${(summary.avg_vacuum_probability * 100).toFixed(1)}%`} color="#ef4444" />
                <MetricCard label="High Risk Count" value={summary.high_risk_count} color="#ef4444" />
                <MetricCard label="Analyzed" value={data.cliff_metrics?.length} color="#3b82f6" />
            </div>
            {vacuumCandidates.length > 0 && (
                <div className="col-span-12 bg-terminal-darker/30 rounded border border-red-500/30 p-3">
                    <div className="text-xs font-mono text-red-400 uppercase mb-3">⚠ VACUUM CANDIDATES</div>
                    <div className="grid grid-cols-5 gap-2">
                        {vacuumCandidates.slice(0, 10).map((c, i) => (
                            <div key={i} className="p-2 rounded bg-red-500/10 text-center">
                                <div className="text-sm font-mono font-bold text-terminal-text">{c.ticker}</div>
                                <div className="text-xs font-mono text-red-400">{(c.vacuum_probability * 100).toFixed(1)}%</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
            <div className="col-span-12 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-2">CLIFF METRICS</div>
                <DataTable 
                    data={data.cliff_metrics}
                    columns={[
                        { key: 'ticker', label: 'Ticker' },
                        { key: 'cliff_distance', label: 'Cliff Dist', render: r => r.cliff_distance?.toFixed(4), color: r => r.cliff_distance > 0 ? '#ef4444' : '#22c55e' },
                        { key: 'vacuum_probability', label: 'Vacuum P', render: r => `${(r.vacuum_probability * 100).toFixed(1)}%`, color: r => r.vacuum_probability > 0.3 ? '#ef4444' : undefined },
                        { key: 'acceleration_zscore', label: 'Accel Z', render: r => r.acceleration_zscore?.toFixed(2) },
                        { key: 'volume_decay_rate', label: 'Vol Decay', render: r => r.volume_decay_rate?.toFixed(4) },
                    ]}
                />
            </div>
        </div>
    );
};

const ContagionTab = ({ data, loading }) => {
    if (loading) return <div className="p-4 text-terminal-dim font-mono">Loading...</div>;
    if (!data) return <div className="p-4 text-terminal-dim font-mono">No data</div>;
    
    const summary = data.summary || {};
    const patientZeros = data.patient_zeros || [];
    const firebreaks = data.firebreaks || [];
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 grid grid-cols-4 gap-3">
                <MetricCard label="Avg R-Number" value={summary.avg_r_number?.toFixed(2)} color="#f97316" />
                <MetricCard label="Total Edges" value={summary.total_edges} color="#8b5cf6" />
                <MetricCard label="Patient Zeros" value={patientZeros.length} color="#ef4444" />
                <MetricCard label="Firebreaks" value={firebreaks.length} color="#22c55e" />
            </div>
            <div className="col-span-6 bg-terminal-darker/30 rounded border border-red-500/30 p-3">
                <div className="text-xs font-mono text-red-400 uppercase mb-3">🦠 PATIENT ZEROS</div>
                <div className="space-y-1">
                    {patientZeros.slice(0, 8).map((p, i) => (
                        <div key={i} className="flex justify-between p-2 rounded bg-red-500/10">
                            <span className="text-sm font-mono">{p.ticker}</span>
                            <span className="text-xs font-mono text-red-400">{(p.patient_zero_prob * 100).toFixed(1)}%</span>
                        </div>
                    ))}
                </div>
            </div>
            <div className="col-span-6 bg-terminal-darker/30 rounded border border-green-500/30 p-3">
                <div className="text-xs font-mono text-green-400 uppercase mb-3">🛡️ FIREBREAKS</div>
                <div className="space-y-1">
                    {firebreaks.slice(0, 8).map((f, i) => (
                        <div key={i} className="flex justify-between p-2 rounded bg-green-500/10">
                            <span className="text-sm font-mono">{f.ticker}</span>
                            <span className="text-xs font-mono text-green-400">{f.firebreak_score?.toFixed(2)}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

const CapacityTab = ({ data, loading }) => {
    if (loading) return <div className="p-4 text-terminal-dim font-mono">Loading...</div>;
    if (!data?.capacity_metrics) return <div className="p-4 text-terminal-dim font-mono">No data</div>;
    
    const summary = data.summary || {};
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 grid grid-cols-4 gap-3">
                <MetricCard label="Median Safe Size" value={`$${(summary.median_safe_size / 1e6).toFixed(1)}M`} color="#22c55e" />
                <MetricCard label="Avg Impact Slope" value={summary.avg_impact_slope?.toFixed(4)} color="#f97316" />
                <MetricCard label="Low Capacity" value={summary.low_capacity_count} color="#ef4444" />
                <MetricCard label="Analyzed" value={data.capacity_metrics?.length} color="#3b82f6" />
            </div>
            <div className="col-span-12 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-2">CAPACITY LIMITS</div>
                <DataTable 
                    data={data.capacity_metrics}
                    columns={[
                        { key: 'ticker', label: 'Ticker' },
                        { key: 'safe_size_dollars', label: 'Safe Size', render: r => `$${(r.safe_size_dollars / 1e6).toFixed(1)}M` },
                        { key: 'stress_size_dollars', label: 'Stress Size', render: r => `$${(r.stress_size_dollars / 1e6).toFixed(1)}M` },
                        { key: 'break_size_dollars', label: 'Break Size', render: r => `$${(r.break_size_dollars / 1e6).toFixed(1)}M` },
                        { key: 'impact_slope', label: 'Impact', render: r => r.impact_slope?.toFixed(4) },
                    ]}
                />
            </div>
        </div>
    );
};

const RegimesTab = ({ data, loading }) => {
    if (loading) return <div className="p-4 text-terminal-dim font-mono">Loading...</div>;
    if (!data?.regime_states) return <div className="p-4 text-terminal-dim font-mono">No data</div>;
    
    const summary = data.summary || {};
    const distribution = data.regime_distribution || {};
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 grid grid-cols-4 gap-3">
                <MetricCard label="Modal Regime" value={summary.modal_regime?.toUpperCase()} color={PHASE_COLORS[summary.modal_regime]} />
                <MetricCard label="Transition Risk" value={`${(summary.avg_transition_risk * 100).toFixed(1)}%`} color="#f97316" />
                <MetricCard label="High Risk" value={data.high_transition_risk?.length || 0} color="#ef4444" />
                <MetricCard label="Analyzed" value={data.regime_states?.length} color="#3b82f6" />
            </div>
            <div className="col-span-12 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-3">REGIME DISTRIBUTION</div>
                <div className="flex gap-6">
                    {Object.entries(distribution).map(([regime, pct]) => (
                        <div key={regime} className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full" style={{ background: PHASE_COLORS[regime] }}></div>
                            <span className="text-sm font-mono" style={{ color: PHASE_COLORS[regime] }}>{regime}</span>
                            <span className="text-sm font-mono text-terminal-dim">{(pct * 100).toFixed(0)}%</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

const FeedbackTab = ({ data, loading }) => {
    if (loading) return <div className="p-4 text-terminal-dim font-mono">Loading...</div>;
    if (!data?.feedback_metrics) return <div className="p-4 text-terminal-dim font-mono">No data</div>;
    
    const summary = data.summary || {};
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 grid grid-cols-4 gap-3">
                <MetricCard label="Avg Loop Gain" value={summary.avg_loop_gain?.toFixed(4)} color={summary.avg_loop_gain > 1 ? '#ef4444' : '#22c55e'} />
                <MetricCard label="Unstable Count" value={summary.unstable_count} color="#ef4444" />
                <MetricCard label="Amplifying" value={summary.amplifying_count} color="#f97316" />
                <MetricCard label="Analyzed" value={data.feedback_metrics?.length} color="#3b82f6" />
            </div>
            <div className="col-span-12 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-2">FEEDBACK METRICS</div>
                <DataTable 
                    data={data.feedback_metrics}
                    columns={[
                        { key: 'ticker', label: 'Ticker' },
                        { key: 'loop_gain', label: 'Loop Gain', render: r => r.loop_gain?.toFixed(4), color: r => r.loop_gain > 1 ? '#ef4444' : '#22c55e' },
                        { key: 'stability_status', label: 'Status', color: r => r.stability_status === 'stable' ? '#22c55e' : '#ef4444' },
                        { key: 'beta_vl', label: 'β_VL', render: r => r.beta_vl?.toFixed(4) },
                        { key: 'beta_lv', label: 'β_LV', render: r => r.beta_lv?.toFixed(4) },
                    ]}
                />
            </div>
        </div>
    );
};

const FingerprintTab = ({ data, loading }) => {
    if (loading) return <div className="p-4 text-terminal-dim font-mono">Loading...</div>;
    if (!data?.current_fingerprint) return <div className="p-4 text-terminal-dim font-mono">No data</div>;
    
    const fingerprint = data.current_fingerprint || [];
    const crises = data.similar_crises || [];
    const labels = data.fingerprint_labels || [];
    
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-12 lg:col-span-6 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-3">CURRENT FINGERPRINT</div>
                <div className="flex items-end justify-around h-40">
                    {fingerprint.map((val, i) => (
                        <div key={i} className="text-center">
                            <div className="w-10 rounded-t" style={{ 
                                height: `${val * 120}px`, 
                                background: val > 0.7 ? '#ef4444' : val > 0.5 ? '#f97316' : '#22c55e' 
                            }}></div>
                            <div className="text-[8px] font-mono text-terminal-dim mt-1">{labels[i]?.slice(0, 5) || `D${i+1}`}</div>
                        </div>
                    ))}
                </div>
            </div>
            <div className="col-span-12 lg:col-span-6 bg-terminal-darker/30 rounded border border-terminal-gray/30 p-3">
                <div className="text-xs font-mono text-terminal-dim uppercase mb-3">SIMILAR CRISES</div>
                <div className="space-y-2">
                    {crises.slice(0, 5).map((crisis, i) => (
                        <div key={i} className="flex justify-between items-center p-2 rounded bg-terminal-gray/10">
                            <span className="text-sm font-mono text-terminal-text">{crisis.name}</span>
                            <span className="text-xs font-mono" style={{ color: crisis.similarity > 0.7 ? '#ef4444' : '#f97316' }}>
                                {(crisis.similarity * 100).toFixed(1)}% match
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================
export default function LiquidityIntelligenceLab() {
    const [activeTab, setActiveTab] = useState("manifold");
    const [universe, setUniverse] = useState("INDIA");
    const [window, setWindow] = useState(60);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [hasRun, setHasRun] = useState(false);
    
    // Cache data per tab
    const [manifoldData, setManifoldData] = useState(null);
    const [cliffData, setCliffData] = useState(null);
    const [contagionData, setContagionData] = useState(null);
    const [capacityData, setCapacityData] = useState(null);
    const [regimesData, setRegimesData] = useState(null);
    const [feedbackData, setFeedbackData] = useState(null);
    const [fingerprintData, setFingerprintData] = useState(null);
    
    const params = useMemo(() => ({ universe, window, lookback: 252 }), [universe, window]);
    
    // Clear cache when params change
    const clearCache = useCallback(() => {
        setManifoldData(null);
        setCliffData(null);
        setContagionData(null);
        setCapacityData(null);
        setRegimesData(null);
        setFeedbackData(null);
        setFingerprintData(null);
        setHasRun(false);
    }, []);
    
    // Fetch current tab data
    const fetchTabData = useCallback(async (tab) => {
        setLoading(true);
        setError(null);
        setHasRun(true);
        
        try {
            switch (tab) {
                case 'manifold':
                    if (!manifoldData) setManifoldData(await fetchManifold(params));
                    break;
                case 'cliff':
                    if (!cliffData) setCliffData(await fetchCliffVacuum(params));
                    break;
                case 'contagion':
                    if (!contagionData) setContagionData(await fetchContagion(params));
                    break;
                case 'capacity':
                    if (!capacityData) setCapacityData(await fetchCapacity(params));
                    break;
                case 'regimes':
                    if (!regimesData) setRegimesData(await fetchRegimes(params));
                    break;
                case 'feedback':
                    if (!feedbackData) setFeedbackData(await fetchFeedback(params));
                    break;
                case 'fingerprint':
                    if (!fingerprintData) setFingerprintData(await fetchFingerprint(params));
                    break;
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [params, manifoldData, cliffData, contagionData, capacityData, regimesData, feedbackData, fingerprintData]);
    
    // Check if current tab has data
    const getCurrentTabData = useCallback(() => {
        switch (activeTab) {
            case 'manifold': return manifoldData;
            case 'cliff': return cliffData;
            case 'contagion': return contagionData;
            case 'capacity': return capacityData;
            case 'regimes': return regimesData;
            case 'feedback': return feedbackData;
            case 'fingerprint': return fingerprintData;
            default: return null;
        }
    }, [activeTab, manifoldData, cliffData, contagionData, capacityData, regimesData, feedbackData, fingerprintData]);
    
    // Render tab content
    const renderTabContent = () => {
        if (!hasRun) {
            return (
                <div className="flex flex-col items-center justify-center h-96 text-center">
                    <div className="text-6xl mb-4">◉</div>
                    <div className="text-lg font-mono text-terminal-text mb-2">LIQUIDITY INTELLIGENCE ENGINE</div>
                    <div className="text-sm font-mono text-terminal-dim mb-6 max-w-md">
                        7 interconnected systems: State Manifold, Cliff Detection, Contagion Networks, 
                        Capacity Limits, Regime Classification, Feedback Loops, and Crisis Fingerprinting.
                    </div>
                    <button
                        onClick={() => fetchTabData(activeTab)}
                        disabled={loading}
                        className="px-6 py-3 bg-terminal-cyan/20 border-2 border-terminal-cyan rounded text-sm font-mono text-terminal-cyan hover:bg-terminal-cyan/30 disabled:opacity-50"
                    >
                        {loading ? "ANALYZING..." : "▶ RUN ANALYSIS"}
                    </button>
                </div>
            );
        }
        
        const tabData = getCurrentTabData();
        if (!tabData && !loading) {
            return (
                <div className="flex flex-col items-center justify-center h-64">
                    <div className="text-sm font-mono text-terminal-dim mb-4">No data for this tab</div>
                    <button
                        onClick={() => fetchTabData(activeTab)}
                        className="px-4 py-2 bg-terminal-cyan/20 border border-terminal-cyan rounded text-xs font-mono text-terminal-cyan"
                    >
                        LOAD {activeTab.toUpperCase()}
                    </button>
                </div>
            );
        }
        
        switch (activeTab) {
            case 'manifold': return <ManifoldTab data={manifoldData} loading={loading} />;
            case 'cliff': return <CliffTab data={cliffData} loading={loading} />;
            case 'contagion': return <ContagionTab data={contagionData} loading={loading} />;
            case 'capacity': return <CapacityTab data={capacityData} loading={loading} />;
            case 'regimes': return <RegimesTab data={regimesData} loading={loading} />;
            case 'feedback': return <FeedbackTab data={feedbackData} loading={loading} />;
            case 'fingerprint': return <FingerprintTab data={fingerprintData} loading={loading} />;
            default: return null;
        }
    };
    
    return (
        <TerminalPanel title="LIQUIDITY INTELLIGENCE ENGINE" subtitle={`${universe} • ${window}D Window`}>
            <div className="p-4">
                {/* Controls */}
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-terminal-dim">UNIVERSE:</span>
                            <select
                                value={universe}
                                onChange={(e) => { setUniverse(e.target.value); clearCache(); }}
                                className="bg-terminal-darker border border-terminal-gray/50 rounded px-2 py-1 text-xs font-mono text-terminal-cyan"
                            >
                                <option value="INDIA">INDIA</option>
                                <option value="US">US</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-terminal-dim">WINDOW:</span>
                            <select
                                value={window}
                                onChange={(e) => { setWindow(parseInt(e.target.value)); clearCache(); }}
                                className="bg-terminal-darker border border-terminal-gray/50 rounded px-2 py-1 text-xs font-mono text-terminal-cyan"
                            >
                                <option value={20}>20D</option>
                                <option value={60}>60D</option>
                                <option value={120}>120D</option>
                                <option value={252}>252D</option>
                            </select>
                        </div>
                    </div>
                    <button 
                        onClick={() => fetchTabData(activeTab)}
                        disabled={loading}
                        className="px-4 py-1.5 bg-terminal-cyan/20 border border-terminal-cyan/50 rounded text-xs font-mono text-terminal-cyan hover:bg-terminal-cyan/30 disabled:opacity-50"
                    >
                        {loading ? "LOADING..." : "▶ RUN"}
                    </button>
                </div>
                
                {/* Tab Navigation */}
                <div className="flex gap-1 mb-4 border-b border-terminal-gray/30 pb-2 overflow-x-auto">
                    {SYSTEM_TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`px-3 py-2 text-xs font-mono uppercase tracking-wide rounded-t transition-all whitespace-nowrap ${
                                activeTab === tab.id
                                    ? 'bg-terminal-cyan/20 text-terminal-cyan border-b-2 border-terminal-cyan'
                                    : 'text-terminal-dim hover:text-terminal-text hover:bg-terminal-gray/20'
                            }`}
                        >
                            <span className="mr-1">{tab.icon}</span>
                            {tab.label}
                        </button>
                    ))}
                </div>
                
                {/* Error */}
                {error && (
                    <div className="mb-4 p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-mono">
                        {error}
                    </div>
                )}
                
                {/* Tab Content */}
                <div className="min-h-[500px]">
                    {renderTabContent()}
                </div>
            </div>
        </TerminalPanel>
    );
}
