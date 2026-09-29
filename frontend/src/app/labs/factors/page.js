"use client";

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
    Activity, Layers, BarChart2, PieChart as PieChartIcon, Shield, 
    RefreshCw, Filter, Search, ChevronRight, Globe,
    TrendingUp, TrendingDown, AlertTriangle, Cpu, Database, Info,
    Clock, Scale, MousePointer2, Target, Zap
} from 'lucide-react';
import {
    ResponsiveContainer, ComposedChart, Line, LineChart, Bar, XAxis, YAxis, 
    CartesianGrid, Tooltip, Legend, Area, ReferenceLine, Scatter, ScatterChart,
    Cell, BarChart, Pie, Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
    AreaChart, PieChart
} from 'recharts';
import {
    fetchFactorsUniverse,
    runFactorMultiModel,
    runFactorRollingExposures,
    runFactorContribution,
    runFactorShockReplay,
    runFactorBacktest,
    runFactorOptimizer,
    runFactorRotation,
    runFactorRegimes
} from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { motion, AnimatePresence } from 'framer-motion';

// =============================================================================
// THEME & CONSTANTS
// =============================================================================

const THEME = {
    bg: '#020408',
    card: '#0a0e17',
    cardLighter: '#0f172a',
    border: '#1e293b',
    accent: '#fbbf24', // Gold
    text: '#f8fafc',
    textDim: '#94a3b8',
    up: '#10b981',
    down: '#f43f5e',
    neutral: '#3b82f6',
};

const FACTOR_COLORS = {
    'Mkt-RF': '#3b82f6', // Blue
    'SMB': '#10b981',    // Green
    'HML': '#f59e0b',    // Orange
    'RMW': '#8b5cf6',    // Purple
    'CMA': '#06b6d4',    // Cyan
    'Mom': '#ec4899',    // Pink
    'Q1': '#ef4444',
    'Q2': '#f59e0b',
    'Q3': '#6b7280',
    'Q4': '#3b82f6',
    'Q5': '#10b981',
};

const TABS = [
    { id: 'DNA', label: 'DNA', description: 'Factor Attribution & Identity', info: 'Decomposes returns into specific factor risk exposures using multi-variate regression.' },
    { id: 'OPTIMIZER', label: 'OPTIMIZER', description: 'Factor Mixer & Tilt Tool', info: 'Calculates optimal factor weighting using Mean-Variance or Black-Litterman frameworks.' },
    { id: 'ROTATION', label: 'ROTATION', description: 'Correlation & Market Map', info: 'Visualizes factor lead-lag relationships and cross-sectional correlations.' },
    { id: 'REGIMES', label: 'REGIMES', description: 'Macro x Factor Interaction', info: 'Maps factor performance across different inflation and growth regimes.' },
];

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

const MetricTooltip = ({ text, children }) => {
    const [isVisible, setIsVisible] = useState(false);
    return (
        <div className="relative inline-block" 
             onMouseEnter={() => setIsVisible(true)} 
             onMouseLeave={() => setIsVisible(false)}>
            {children}
            <AnimatePresence>
                {isVisible && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 5 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 5 }}
                        className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-64 bg-[#0a0e17] border border-amber-500/20 p-4 rounded-xl shadow-2xl z-[100] pointer-events-none backdrop-blur-3xl"
                    >
                        <div className="flex items-center gap-2 mb-2">
                            <Info size={12} className="text-amber-500" />
                            <span className="text-[10px] font-black text-amber-500 uppercase tracking-widest">Intelligence_Note</span>
                        </div>
                        <p className="text-[10px] text-gray-300 font-mono leading-relaxed normal-case">
                            {text}
                        </p>
                        <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-amber-500/20" />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const Panel = ({ title, children, icon: Icon, className = "", headerActions = null, info = "Analytical Metric Details" }) => (
    <div className={`bg-white/[0.02] border border-white/[0.05] rounded-3xl overflow-hidden backdrop-blur-2xl shadow-2xl flex flex-col hover:border-white/[0.1] transition-all duration-700 ${className}`}>
        {title && (
            <div className="px-6 py-5 border-b border-white/[0.05] flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-4">
                    <div className="p-2 rounded-lg bg-white/[0.03] border border-white/5">
                        {Icon && <Icon size={16} className="text-gray-500/80" />}
                    </div>
                    <div>
                        <h3 className="text-[11px] font-black text-white tracking-[0.2em] uppercase">{title}</h3>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {headerActions}
                    <MetricTooltip text={info}>
                        <div className="p-1.5 rounded-full hover:bg-white/5 transition-colors group cursor-help">
                            <Info size={14} className="text-gray-600 group-hover:text-amber-500/60 transition-colors" />
                        </div>
                    </MetricTooltip>
                </div>
            </div>
        )}
        <div className="flex-1 p-6 relative overflow-hidden">
            {children}
        </div>
    </div>
);

const StatCard = ({ label, value, subValue, trend, trendLabel, info }) => (
    <MetricTooltip text={info || "Institutional metric tracking"}>
        <div className="bg-[#0d111a] border border-[#1f2937] p-4 rounded-xl overflow-hidden group hover:border-amber-500/30 transition-all cursor-crosshair">
            <div className="text-[9px] text-gray-600 uppercase tracking-[0.2em] mb-2 font-black truncate">{label}</div>
            <div className="flex items-baseline gap-2">
                <div className="text-xl font-mono font-bold text-white truncate tracking-tighter">{value}</div>
                {trend !== undefined && (
                    <div className={`text-[10px] flex items-center gap-0.5 font-bold ${trend >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {trend >= 0 ? '▲' : '▼'}{Math.abs(trend).toFixed(1)}%
                    </div>
                )}
            </div>
            {subValue && <div className="text-[9px] text-gray-500 font-mono mt-1 uppercase tracking-widest">{subValue}</div>}
        </div>
    </MetricTooltip>
);

const LoadingOverlay = () => (
    <div className="absolute inset-0 bg-[#030508]/80 backdrop-blur-md z-50 flex flex-col items-center justify-center">
        <motion.div 
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="flex flex-col items-center"
        >
            <div className="w-16 h-16 relative mb-6">
                <div className="absolute inset-0 border-2 border-amber-500/10 rounded-full" />
                <div className="absolute inset-0 border-t-2 border-amber-500 rounded-full animate-spin" />
                <div className="absolute inset-4 border-2 border-blue-500/10 rounded-full" />
                <div className="absolute inset-4 border-b-2 border-blue-500 rounded-full animate-spin-reverse" style={{ animationDuration: '1.5s' }} />
            </div>
            <span className="text-[10px] font-black uppercase tracking-[0.4em] text-amber-500 mb-1">
                Optimizing
            </span>
            <span className="text-[8px] font-mono text-gray-600 uppercase tracking-widest">
                Computing Factor Analytics...
            </span>
        </motion.div>
    </div>
);

// =============================================================================
// VIEWS
// =============================================================================

// --- DNA VIEW ---
const DNAView = ({ ticker, factorSet, windowYears, data, loading }) => {
    if (!data.multiModel) {
        return <div className="h-full flex items-center justify-center text-gray-600 text-xs italic">Run Analysis to view Factor DNA</div>;
    }

    const m = data.multiModel.models?.[0] || {};
    const rollingData = data.rolling?.dates?.map((d, i) => {
        const p = { t: d };
        Object.keys(data.rolling?.betas || {}).forEach(f => p[f] = data.rolling.betas[f][i]?.v);
        return p;
    });

    const alphaResidData = data.multiModel.alphaResidual?.map((v, i) => ({
        t: data.multiModel.dates?.[i] || i,
        v: v * 100 // %
    }));

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            {/* Summary Stats */}
            <div className="grid grid-cols-4 gap-4">
                <StatCard 
                    label="Dominant Model BELIEF" 
                    value={data.multiModel.arbitration?.dominantModelId?.toUpperCase() || '--'} 
                    subValue={`Reliability: ${(data.multiModel.arbitration?.dominanceScore * 100 || 0).toFixed(1)}%`}
                />
                <StatCard 
                    label="EXPLAINED VARIANCE (R²)" 
                    value={`${(m.adjR2 * 100 || 0).toFixed(1)}%`} 
                    trend={m.adjR2 * 100 - 65}
                    trendLabel="vs Bench"
                />
                <StatCard 
                    label="ANNUALIZED ALPHA" 
                    value={`${(m.alphaAnnualized * 100 || 0).toFixed(2)}%`} 
                    trend={m.tStats?.alpha}
                    trendLabel="t-stat"
                />
                <StatCard 
                    label="FACTOR STABILITY" 
                    value={data.rolling?.stability ? (Object.values(data.rolling.stability)[0] * 5).toFixed(1) : '--'} 
                    subValue="Persistence Score / 10"
                />
            </div>

            {/* Main Visuals */}
            <div className="grid grid-cols-12 gap-4 h-[450px]">
                <Panel title="ROLLING FACTOR BIAS (AREA STACK)" className="col-span-8 h-full" icon={Activity}>
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={rollingData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#111827" vertical={false} />
                            <XAxis dataKey="t" tick={{fontSize: 9, fill: '#4b5563'}} minTickGap={50} />
                            <YAxis tick={{fontSize: 9, fill: '#4b5563'}} />
                            <Tooltip contentStyle={{ backgroundColor: '#0a101b', border: '1px solid #1f2937', fontSize: '10px' }} />
                            <Legend wrapperStyle={{ fontSize: '9px', paddingTop: '10px' }} iconType="circle" />
                            {Object.keys(data.rolling?.betas || {}).map(f => (
                                <Area key={f} type="monotone" dataKey={f} stackId="1" stroke={FACTOR_COLORS[f] || '#6b7280'} fill={FACTOR_COLORS[f] || '#6b7280'} fillOpacity={0.4} name={f} />
                            ))}
                        </AreaChart>
                    </ResponsiveContainer>
                </Panel>
                
                <div className="col-span-4 flex flex-col gap-4">
                    <Panel title="ALPHA RESIDUAL (PURE SKILL)" icon={TrendingUp} className="flex-1">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={alphaResidData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis dataKey="t" hide />
                                <YAxis tick={{fontSize: 9, fill: '#4b5563'}} />
                                <Tooltip />
                                <Area type="monotone" dataKey="v" stroke="#fbbf24" fill="#fbbf24" fillOpacity={0.1} name="Alpha Skill (%)" />
                                <ReferenceLine y={0} stroke="#4b5563" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </Panel>
                    <Panel title="EXPOSURE RADAR" icon={Target} className="flex-1">
                        <ResponsiveContainer width="100%" height="100%">
                            <RadarChart outerRadius="70%" data={Object.entries(m.betas || {}).map(([name, value]) => ({ name, value: Math.abs(value) }))}>
                                <PolarGrid stroke="#1f2937" />
                                <PolarAngleAxis dataKey="name" tick={{fontSize: 8, fill: '#6b7280'}} />
                                <Radar name="Exposure" dataKey="value" stroke="#fbbf24" fill="#fbbf24" fillOpacity={0.2} />
                            </RadarChart>
                        </ResponsiveContainer>
                    </Panel>
                </div>
            </div>

            {/* Ledger */}
            <Panel title="STATISTICAL LEDGER (DMA FORENSICS)" icon={Database}>
                <div className="overflow-x-auto overflow-hidden">
                    <table className="w-full text-[11px] font-mono">
                        <thead>
                            <tr className="text-gray-500 border-b border-gray-800">
                                <th className="text-left py-2 px-3 font-medium uppercase tracking-wider">Factor Metric</th>
                                {m.factors?.map(f => <th key={f} className="text-right py-2 px-3 font-medium uppercase tracking-wider">{f}</th>)}
                                <th className="text-right py-2 px-3 font-medium uppercase tracking-wider">Alpha</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="border-b border-gray-800/50 hover:bg-white/5">
                                <td className="py-2 px-3 text-gray-300">EXPOSURE (BETA)</td>
                                {m.factors?.map(f => (
                                    <td key={f} className={`text-right py-2 px-3 font-bold ${m.betas[f] >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                        {m.betas[f]?.toFixed(2)}
                                    </td>
                                ))}
                                <td className="text-right py-2 px-3 text-amber-500">{(m.alphaAnnualized * 100 || 0).toFixed(2)}%</td>
                            </tr>
                            <tr className="border-b border-gray-800/50 hover:bg-white/5 opacity-70">
                                <td className="py-2 px-3 text-gray-500">T-STAT (SIG)</td>
                                {m.factors?.map(f => (
                                    <td key={f} className={`text-right py-2 px-3 ${Math.abs(m.tStats[f]) > 2 ? 'text-blue-400 font-bold' : 'text-gray-600'}`}>
                                        {m.tStats[f]?.toFixed(2)}
                                    </td>
                                ))}
                                <td className={`text-right py-2 px-3 ${Math.abs(m.tStats?.alpha) > 2 ? 'text-blue-400 font-bold' : 'text-gray-600'}`}>{m.tStats?.alpha?.toFixed(2)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </Panel>
        </div>
    );
};

// --- OPTIMIZER VIEW ---
const OptimizerView = ({ factorSet, data, loading }) => {
    if (!data.optimizer) {
        return <div className="h-full flex items-center justify-center text-gray-600 text-xs italic">Run Optimizer to view frontier</div>;
    }

    const { weights, riskContribution, metrics, frontier } = data.optimizer;
    const weightData = Object.entries(weights).map(([name, value]) => ({ name, value }));
    const riskData = Object.entries(riskContribution || {}).map(([name, value]) => ({ name, value: value * 100 }));

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <div className="grid grid-cols-4 gap-4">
                <StatCard label="OPTIMAL EXP. RETURN" value={`${(metrics.expectedReturn * 100).toFixed(2)}%`} />
                <StatCard label="PORTFOLIO VOLATILITY" value={`${(metrics.expectedVol * 100).toFixed(2)}%`} subValue={`Target: ${(data.optimizer.meta.targetVol*100).toFixed(1)}%`} />
                <StatCard label="SHARPE RATIO" value={metrics.sharpe.toFixed(2)} />
                <StatCard label="CONCENTRATION" value={(1 / Object.values(weights).reduce((a,b) => a + b**2, 0)).toFixed(1)} subValue="Eff. N Factors" />
            </div>

            <div className="grid grid-cols-12 gap-4 h-[450px]">
                <Panel title="EFFICIENT FRONTIER (FACTOR MIX)" className="col-span-8 h-full" icon={Scale}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                            <XAxis type="number" dataKey="vol" name="Risk (Vol)" unit="%" tick={{fontSize: 9}} label={{ value: 'Volatility %', position: 'bottom', fill: '#6b7280', fontSize: 10 }} />
                            <YAxis type="number" dataKey="ret" name="Return" unit="%" tick={{fontSize: 9}} label={{ value: 'Annual Return %', angle: -90, position: 'left', fill: '#6b7280', fontSize: 10 }} />
                            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                            <Scatter name="Frontier" data={frontier.map(f => ({ vol: f.vol * 100, ret: f.ret * 100 }))} fill="#fbbf24" line shape="circle" />
                            <Scatter name="Current Portfolio" data={[{ vol: metrics.expectedVol * 100, ret: metrics.expectedReturn * 100 }]} fill="#ef4444" />
                        </ScatterChart>
                    </ResponsiveContainer>
                </Panel>
                
                <div className="col-span-4 flex flex-col gap-4">
                    <Panel title="RISK CONTRIBUTION (MCTR %)" icon={Shield} className="flex-1">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={riskData} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                                <XAxis type="number" hide />
                                <YAxis dataKey="name" type="category" tick={{fontSize: 9, fill: '#6b7280'}} width={60} />
                                <Tooltip />
                                <Bar dataKey="value" name="Risk Contrib. (%)">
                                    {riskData.map((entry, index) => (
                                        <Cell key={index} fill={FACTOR_COLORS[entry.name] || '#6b7280'} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </Panel>
                    <Panel title="OPTIMAL ALLOCATION" className="col-span-4 h-full" icon={PieChartIcon}>
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie data={weightData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                                    {weightData.map((entry, index) => (
                                        <Cell key={index} fill={FACTOR_COLORS[entry.name] || THEME.neutral} />
                                    ))}
                                </Pie>
                                <Tooltip />
                                <Legend verticalAlign="bottom" height={36} wrapperStyle={{fontSize: 9}} />
                            </PieChart>
                        </ResponsiveContainer>
                    </Panel>
                </div>
            </div>

            <div className="grid grid-cols-12 gap-4 mt-6">
                <Panel title="HISTORICAL STRESS TEST (SCENARIO SIM)" className="col-span-12" icon={AlertTriangle}>
                    <div className="grid grid-cols-2 gap-6">
                        {data.optimizer.scenarios?.map(s => (
                            <div key={s.scenario} className="bg-[#0d111a] border border-[#1f2937] p-4 rounded-lg flex items-center justify-between">
                                <div>
                                    <div className="text-[10px] text-gray-500 uppercase font-black tracking-widest">{s.scenario} Impact</div>
                                    <div className={`text-xl font-mono font-black ${s.impact < 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                                        {(s.impact * 100).toFixed(2)}% Portfolio Shift
                                    </div>
                                </div>
                                <div className={`px-3 py-1 rounded text-[10px] font-black uppercase tracking-tighter ${s.status === 'CRITICAL' ? 'bg-rose-500/20 text-rose-500' : 'bg-emerald-500/20 text-emerald-500'}`}>
                                    {s.status}
                                </div>
                            </div>
                        ))}
                    </div>
                </Panel>
            </div>
        </div>
    );
};

// --- ROTATION VIEW ---
const RotationView = ({ data, loading }) => {
    if (!data.rotation) {
        return <div className="h-full flex items-center justify-center text-gray-600 text-xs italic">Run Rotation Engine...</div>;
    }

    const dispersionData = data.rotation.dates?.map((d, i) => ({
        t: d,
        v: data.rotation.dispersion[i] * 100
    }));

    return (
        <div className="h-full flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <div className="grid grid-cols-12 gap-4 flex-1">
                <Panel title="STYLE ROTATION MAP (RRG)" className="col-span-8 h-full" icon={RefreshCw}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                            <XAxis type="number" dataKey="rsRatio" name="RS-Ratio" domain={[95, 105]} tick={{fontSize: 9}} />
                            <YAxis type="number" dataKey="rsMomentum" name="RS-Momentum" domain={[95, 105]} tick={{fontSize: 9}} />
                            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                            <ReferenceLine x={100} stroke="#4b5563" strokeDasharray="3 3" label={{ value: 'Lagging | Leading', position: 'top', fill: '#4b5563', fontSize: 10 }} />
                            <ReferenceLine y={100} stroke="#4b5563" strokeDasharray="3 3" label={{ value: 'Improving | Weakening', angle: 90, position: 'right', fill: '#4b5563', fontSize: 10 }} />
                            {data.rotation.rotation.map(node => (
                                <Scatter 
                                    key={node.id} 
                                    name={node.label} 
                                    data={[node]} 
                                    fill={FACTOR_COLORS[node.id] || THEME.neutral}
                                    shape={(props) => {
                                        const { cx, cy, fill } = props;
                                        return (
                                            <g>
                                                <circle cx={cx} cy={cy} r={6} fill={fill} />
                                                <text x={cx + 8} y={cy + 4} fill={fill} fontSize={10} fontWeight="bold">{node.label}</text>
                                                {/* Trail */}
                                                {node.history.map((pt, idx) => (
                                                    <circle key={idx} cx={cx - (10 - idx) * 5} cy={cy - (10 - idx) * 2} r={2} fill={fill} opacity={idx / 20} />
                                                ))}
                                            </g>
                                        );
                                    }}
                                />
                            ))}
                        </ScatterChart>
                    </ResponsiveContainer>
                </Panel>
                <Panel title="CROSS-SECTIONAL DISPERSION" className="col-span-4 h-full" icon={Zap}>
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={dispersionData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#111827" vertical={false} />
                            <XAxis dataKey="t" hide />
                            <YAxis tick={{fontSize: 9, fill: '#4b5563'}} />
                            <Tooltip />
                            <Area type="monotone" dataKey="v" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.1} name="Dispersion (%)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </Panel>
            </div>
            
            <div className="grid grid-cols-4 gap-4 py-2 border-t border-gray-800">
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded flex flex-col">
                    <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider">Leading</span>
                    <span className="text-xs text-gray-400 mt-1">High Trend, High Momentum</span>
                </div>
                <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded flex flex-col">
                    <span className="text-[10px] font-bold text-blue-500 uppercase tracking-wider">Improving</span>
                    <span className="text-xs text-gray-400 mt-1">Low Trend, High Momentum</span>
                </div>
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded flex flex-col">
                    <span className="text-[10px] font-bold text-rose-500 uppercase tracking-wider">Lagging</span>
                    <span className="text-xs text-gray-400 mt-1">Low Trend, Low Momentum</span>
                </div>
                <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded flex flex-col">
                    <span className="text-[10px] font-bold text-amber-500 uppercase tracking-wider">Weakening</span>
                    <span className="text-xs text-gray-400 mt-1">High Trend, Low Momentum</span>
                </div>
            </div>
        </div>
    );
};

// --- REGIMES VIEW ---
const RegimesView = ({ data, loading }) => {
    if (!data.regimes) {
        return <div className="h-full flex items-center justify-center text-gray-600 text-xs italic">Loading Regime Matrix...</div>;
    }

    const { matrix, transitionMatrix } = data.regimes;

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <div className="grid grid-cols-12 gap-4">
                <div className="col-span-8">
                    <Panel title="MACRO-FACTOR INTERACTION MATRIX" icon={Shield}>
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs font-mono">
                                <thead>
                                    <tr className="border-b border-gray-800 text-gray-500">
                                        <th className="text-left py-3 px-4 uppercase tracking-widest text-[10px]">Factor Style</th>
                                        <th className="text-right py-3 px-4 uppercase tracking-widest text-[10px]">Low Vol Regime</th>
                                        <th className="text-right py-3 px-4 uppercase tracking-widest text-[10px]">High Vol Regime</th>
                                        <th className="text-right py-3 px-4 uppercase tracking-widest text-[10px]">Regime Alpha Spread</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {matrix.map((row) => (
                                        <tr key={row.factor} className="border-b border-gray-800/50 hover:bg-white/5 h-12 transition-colors">
                                            <td className="px-4 py-2 font-bold text-gray-300">{row.factor}</td>
                                            <td className={`text-right px-4 py-2 ${row.lowVol >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                                {(row.lowVol * 100).toFixed(2)}%
                                            </td>
                                            <td className={`text-right px-4 py-2 ${row.highVol >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                                {(row.highVol * 100).toFixed(2)}%
                                            </td>
                                            <td className="text-right px-4 py-2">
                                                <div className="inline-flex items-center gap-2">
                                                    <div className="w-20 h-1.5 bg-gray-800 rounded-full overflow-hidden flex">
                                                        <div 
                                                            className={`h-full ${row.spread >= 0 ? 'bg-emerald-500' : 'bg-rose-500'}`} 
                                                            style={{ width: `${Math.min(Math.abs(row.spread) * 1000, 100)}%` }}
                                                        />
                                                    </div>
                                                    <span className="font-bold">{(row.spread * 100).toFixed(2)}%</span>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </Panel>
                </div>
                
                <div className="col-span-4 flex flex-col gap-4">
                    <Panel title="STATE TRANSITION PROBABILITIES" icon={RefreshCw} className="flex-1">
                        <div className="grid grid-cols-2 gap-4 h-full p-4">
                            {transitionMatrix?.map((row, i) => 
                                row.map((prob, j) => (
                                    <div key={`${i}-${j}`} className="bg-[#0d111a] border border-[#1f2937] p-2 rounded flex flex-col items-center justify-center">
                                        <span className="text-[8px] text-gray-500 uppercase font-black mb-1">
                                            {i === 0 ? 'Low' : 'High'} → {j === 0 ? 'Low' : 'High'}
                                        </span>
                                        <span className="text-xl font-black font-mono text-white">{(prob * 100).toFixed(0)}%</span>
                                    </div>
                                ))
                            )}
                        </div>
                    </Panel>
                    <Panel title="REGIME CONTEXT" className="flex-1 bg-amber-500/5 border-amber-500/10">
                         <p className="text-[9px] text-gray-400 p-2 leading-relaxed">
                            Transitions favor <b className="text-white">Regime Persistence</b>. 
                            The prob. of staying in Low-Vol is currently dominant, suggesting 
                            alpha-generating environments remain stable.
                         </p>
                    </Panel>
                </div>
            </div>

            <div className="grid grid-cols-12 gap-4 h-[300px]">
                <Panel title={`MACRO VS ALPHA SCATTER (${data.regimes.distributions?.factorName})`} className="col-span-6 h-full" icon={Target}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                            <XAxis type="number" dataKey="vol" name="Market Vol" tick={{fontSize: 9}} label={{ value: 'Vol %', position: 'bottom', fill: '#6b7280', fontSize: 10 }} />
                            <YAxis type="number" dataKey="alpha" name="Alpha" tick={{fontSize: 9}} label={{ value: 'Alpha %', angle: -90, position: 'left', fill: '#6b7280', fontSize: 10 }} />
                            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                            <Scatter name="Factor Alpha" data={data.regimes.scatter} fill="#fbbf24" />
                        </ScatterChart>
                    </ResponsiveContainer>
                </Panel>
                <Panel title="CONDITIONAL PDF (EXPECTANCY)" className="col-span-6 h-full" icon={BarChart2}>
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={Array.from({length: 20}, (_, i) => ({
                            bin: i - 10,
                            low: data.regimes.distributions.low.filter(v => Math.round(v*100) === (i-10)).length,
                            high: data.regimes.distributions.high.filter(v => Math.round(v*100) === (i-10)).length,
                        }))}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                            <XAxis dataKey="bin" tick={{fontSize: 9}} label={{ value: 'Daily Return %', position: 'bottom', fontSize: 10 }} />
                            <YAxis hide />
                            <Tooltip />
                            <Area type="monotone" dataKey="low" stroke="#10b981" fill="#10b981" fillOpacity={0.2} name="Low Vol Dist." />
                            <Area type="monotone" dataKey="high" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} name="High Vol Dist." />
                        </AreaChart>
                    </ResponsiveContainer>
                </Panel>
            </div>

            <div className="bg-[#0d111a] border border-[#1f2937] p-4 rounded-lg flex gap-4">
                 <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-500">
                    <Info size={20} />
                 </div>
                 <div>
                    <h4 className="text-[11px] font-bold text-white uppercase tracking-wider">Insight Engine</h4>
                    <p className="text-[10px] text-gray-500 leading-relaxed max-w-2xl mt-1">
                        Cross-sectional factor returns are strictly conditioned on market volatility regimes. Note how 
                        <span className="text-emerald-500 font-bold mx-1">Value (HML)</span> typically outperforms in High-Vol recovery regimes 
                        whereas <span className="text-blue-500 font-bold mx-1">Momentum (Mom)</span> tends to lead in Low-Vol trending environments.
                    </p>
                 </div>
            </div>
        </div>
    );
};


// =============================================================================
// MAIN HUB COMPONENT
// =============================================================================

export default function FactorsHubPage() {
    const [ticker, setTicker] = useState("AAPL");
    const [activeTab, setActiveTab] = useState("DNA");
    const [factorSet, setFactorSet] = useState("ff5_mom");
    const [windowYears, setWindowYears] = useState(3);
    const [universe, setUniverse] = useState("us_core");
    const [factorStyle, setFactorStyle] = useState("momentum");
    const [targetVol, setTargetVol] = useState(0.15);
    const [loading, setLoading] = useState(false);

    // Quant Filters
    const [zScore, setZScore] = useState(2.0);
    const [pValue, setPValue] = useState(0.05);
    const [outlierHandling, setOutlierHandling] = useState(true);
    
    // UI Metadata fallbacks (Institutional Presets)
    const [meta, setMeta] = useState({
        factorSets: [
            { id: 'ff3', label: 'Fama-French 3-Factor' },
            { id: 'ff5', label: 'Fama-French 5-Factor' },
            { id: 'ff5_mom', label: 'Institutional (5F + Momentum)' }
        ],
        universes: [
            { id: 'us_core', label: 'US Core (S&P 500)' },
            { id: 'us_large', label: 'US Large Cap (Russell 1000)' },
            { id: 'in_nifty50', label: 'Nifty 50 (India)' }
        ],
        factorStyles: [
            { id: 'momentum', label: 'Momentum (High Trend)' },
            { id: 'value', label: 'Value (HML)' },
            { id: 'quality', label: 'Quality (RMW)' },
            { id: 'size', label: 'Size (SMB)' }
        ]
    });

    // Data Store
    const [data, setData] = useState({
        multiModel: null,
        rolling: null,
        contribution: null,
        backtest: null,
        optimizer: null,
        rotation: null,
        regimes: null
    });

    // Load Universe Meta
    useEffect(() => {
        fetchFactorsUniverse().then(setMeta);
    }, []);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        try {
            if (activeTab === 'DNA') {
                const [multi, roll, contrib] = await Promise.all([
                    runFactorMultiModel(ticker, factorSet, windowYears, zScore, outlierHandling),
                    runFactorRollingExposures(ticker, factorSet, windowYears, zScore, outlierHandling),
                    runFactorContribution(ticker, factorSet, windowYears, zScore, outlierHandling)
                ]);
                setData(prev => ({ ...prev, multiModel: multi, rolling: roll, contribution: contrib }));
            } else if (activeTab === 'OPTIMIZER') {
                const res = await runFactorOptimizer(factorSet, targetVol, zScore, outlierHandling);
                setData(prev => ({ ...prev, optimizer: res }));
            } else if (activeTab === 'ROTATION') {
                const res = await runFactorRotation(factorSet);
                setData(prev => ({ ...prev, rotation: res }));
            } else if (activeTab === 'REGIMES') {
                const res = await runFactorRegimes(factorSet);
                setData(prev => ({ ...prev, regimes: res }));
            }
        } catch (err) {
            console.error("Factor analysis failed:", err);
        } finally {
            setLoading(false);
        }
    }, [ticker, factorSet, windowYears, activeTab, universe, factorStyle, targetVol, zScore, outlierHandling]);

    // Run on mount only
    useEffect(() => {
        runAnalysis();
    }, []);

    // Also run when activeTab changes, but only if we don't have data yet
    useEffect(() => {
        if (!data[activeTab.toLowerCase()]) {
            runAnalysis();
        }
    }, [activeTab]);

    return (
        <div className="flex flex-col h-full bg-[#020408] text-gray-100 overflow-hidden font-sans">
            {/* Header / Sub-Nav */}
            <div className="flex items-center justify-between px-8 py-3 bg-[#0a0e17]/80 backdrop-blur-3xl border-b border-[#1f2937] z-30 sticky top-0">
                <div className="flex items-center gap-1">
                    {TABS.map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 px-6 py-2.5 transition-all duration-300 ease-out font-mono border-b-2 ${
                                activeTab === tab.id 
                                ? 'bg-amber-500/5 text-amber-500 border-amber-500 font-bold' 
                                : 'text-gray-500 hover:text-white border-transparent'
                            }`}
                        >
                            <span className="text-[11px] uppercase tracking-[0.2em]">{tab.label}</span>
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-6">
                    {activeTab === 'DNA' && (
                        <div className="w-48 group">
                            <TradingViewSearch mode="security" onSelect={(t) => { setTicker(t); runAnalysis(); }} placeholder="Asset Search..." />
                        </div>
                    )}
                    <button 
                        onClick={runAnalysis}
                        disabled={loading}
                        className={`flex items-center gap-3 px-5 py-2 bg-white/[0.04] hover:bg-white/[0.08] text-gray-400 hover:text-white rounded-full text-[10px] font-display font-black uppercase tracking-[0.2em] border border-white/[0.05] transition-all active:scale-95 ${loading ? 'opacity-50' : ''}`}
                    >
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                        REFRESH ANALYSIS
                    </button>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Unified Sidebar */}
                <div className="w-72 bg-[#05080c] border-r border-[#1e293b] flex flex-col p-5 overflow-y-auto no-scrollbar z-10 shadow-2xl">
                    {/* Focus Ticker - Only for DNA */}
                    {activeTab === 'DNA' && (
                        <div className="mb-8 space-y-4">
                            <div className="p-4 bg-[#0a0e17] border border-[#1e293b] rounded-xl shadow-inner">
                                <span className="text-[10px] font-black text-gray-600 uppercase tracking-widest block mb-2">Primary Asset</span>
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 rounded bg-blue-600/10 flex items-center justify-center text-blue-500 font-black">
                                        {ticker[0]}
                                    </div>
                                    <div className="flex flex-col">
                                        <div className="text-2xl font-black font-mono tracking-tighter text-white">{ticker}</div>
                                        <div className="text-[10px] text-gray-500 font-mono uppercase">{getSymbolInfo(ticker)?.exchange || 'NYSE'}</div>
                                    </div>
                                </div>
                            </div>
                            <div className="relative group">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 group-focus-within:text-amber-500 transition-colors" size={14} />
                                <TradingViewSearch 
                                    mode="security" 
                                    onSelect={(t) => { setTicker(t); }} 
                                    placeholder="Switch Asset..." 
                                />
                            </div>
                        </div>
                    )}

                    {/* Contextual Controls Mapping */}
                    <div className="space-y-8">
                        {/* Selector 1: Universe / Factor Set */}
                        <div>
                            <h3 className="text-[10px] font-black text-gray-600 uppercase tracking-[0.3em] mb-4 flex items-center gap-2">
                                 <Database size={12} className="text-gray-500" /> 
                                 Data Model
                            </h3>
                            <div className="space-y-1.5 focus-within:grayscale-0">
                                {meta.factorSets.map(u => (
                                    <button
                                        key={u.id}
                                        onClick={() => setFactorSet(u.id)}
                                        className={`w-full text-left px-4 py-2.5 rounded-lg text-[11px] font-bold transition-all border ${
                                            factorSet === u.id
                                            ? 'bg-amber-500/10 text-amber-500 border-amber-500/30 shadow-[0_0_20px_rgba(245,158,11,0.1)]' 
                                            : 'text-gray-600 border-transparent hover:bg-white/5 hover:text-gray-300'
                                        }`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <span>{u.label}</span>
                                            {factorSet === u.id && <div className="w-1 h-1 rounded-full bg-amber-500" />}
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>


                        {activeTab === 'OPTIMIZER' && (
                            <div>
                                <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
                                    <Scale size={12} className="text-amber-500" /> Risk Budget
                                </h3>
                                <div className="space-y-4">
                                    <input 
                                        type="range" min="0.05" max="0.30" step="0.01" value={targetVol} 
                                        onChange={(e) => setTargetVol(parseFloat(e.target.value))}
                                        className="w-full h-1 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                    />
                                    <div className="flex justify-between text-[10px] font-mono text-gray-500">
                                        <span>Target Vol: <b className="text-white">{(targetVol*100).toFixed(1)}%</b></span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Quant Filters Section */}
                        <div className="border-t border-gray-800 pt-6">
                            <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-4 flex items-center gap-2">
                                <Cpu size={12} className="text-rose-500" /> Quant Filters
                            </h3>
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <div className="flex justify-between text-[9px] font-bold text-gray-500 uppercase">
                                        <span>Z-Score Threshold</span>
                                        <span className="text-rose-500">{zScore}</span>
                                    </div>
                                    <input 
                                        type="range" min="1" max="4" step="0.5" value={zScore} 
                                        onChange={(e) => setZScore(parseFloat(e.target.value))}
                                        className="w-full h-1 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <div className="flex justify-between text-[9px] font-bold text-gray-500 uppercase">
                                        <span>Alpha Confidence</span>
                                        <span className="text-blue-500">{(1 - pValue) * 100}%</span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                        {[0.05, 0.01].map(p => (
                                            <button 
                                                key={p} onClick={() => setPValue(p)}
                                                className={`px-2 py-1 rounded text-[9px] font-bold border transition-all ${
                                                    pValue === p ? 'bg-blue-600/10 border-blue-600 text-blue-400' : 'bg-[#0d111a] border-[#1f2937] text-gray-600'
                                                }`}
                                            >
                                                {p === 0.05 ? 'Standard' : 'Hyper-Sig'}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-[9px] font-bold text-gray-500 uppercase">Winsorization</span>
                                    <button 
                                        onClick={() => setOutlierHandling(!outlierHandling)}
                                        className={`w-8 h-4 rounded-full transition-colors relative ${outlierHandling ? 'bg-emerald-500' : 'bg-gray-700'}`}
                                    >
                                        <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all ${outlierHandling ? 'left-4.5' : 'left-0.5'}`} />
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Horizon Selection */}
                        {/* Selector 3: Lookback */}
                        <div>
                            <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
                                <Clock size={12} className="text-amber-500" /> Statistical Lookback
                            </h3>
                            <div className="flex gap-2">
                                {[1, 3, 5].map(y => (
                                    <button
                                        key={y}
                                        onClick={() => setWindowYears(y)}
                                        className={`flex-1 py-2 rounded text-[10px] font-black transition-all ${
                                            windowYears === y 
                                            ? 'bg-amber-500 text-black border border-amber-500' 
                                            : 'bg-gray-800/40 text-gray-500 border border-gray-700 hover:text-gray-300'
                                        }`}
                                    >
                                        {y}Y
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="mt-auto pt-6 space-y-4">
                        <button 
                            onClick={runAnalysis}
                            disabled={loading}
                            className={`w-full py-4 rounded-full bg-amber-500 text-black font-black uppercase tracking-[0.3em] text-[11px] flex items-center justify-center gap-3 shadow-[0_0_30px_rgba(245,158,11,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:grayscale`}
                        >
                            {loading ? 'PROCESSING...' : 'RUN SIMULATION'}
                        </button>

                        <div className="p-4 bg-white/[0.02] border border-white/[0.05] rounded-2xl backdrop-blur-xl">
                            <div className="flex items-center gap-3 mb-2">
                                <Shield size={12} className="text-amber-500" />
                                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Operational Status</span>
                            </div>
                            <div className="text-[10px] text-gray-600 font-mono uppercase tracking-tight leading-relaxed">
                                Region: Global Markets<br/>
                                Fidelity: Institutional<br/>
                                State: {loading ? 'CALCULATING...' : 'READY'}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Main View Area */}
                <div className="flex-1 overflow-y-auto bg-[#020408] p-6 no-scrollbar relative min-w-0">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={activeTab + ticker + factorSet}
                            initial={{ opacity: 0, y: 10, filter: 'blur(5px)' }}
                            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                            exit={{ opacity: 0, y: -10, filter: 'blur(5px)' }}
                            transition={{ duration: 0.3 }}
                            className="h-full flex flex-col relative"
                        >
                            {loading && <LoadingOverlay />}
                            
                            {/* Title Block */}
                            <div className="mb-10">
                                <h1 className="text-4xl font-black text-white tracking-tighter flex items-center gap-4 font-display">
                                    {TABS.find(t => t.id === activeTab)?.label} <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-200 to-amber-500">STUDIO</span>
                                </h1>
                                <p className="text-[12px] text-gray-500 font-medium tracking-widest uppercase opacity-80 mt-2 pl-1 border-l border-amber-500/30">{TABS.find(t => t.id === activeTab)?.description}</p>
                            </div>

                            {/* View Router */}
                            {activeTab === 'DNA' && <DNAView ticker={ticker} factorSet={factorSet} windowYears={windowYears} data={data} loading={loading} />}
                            {activeTab === 'OPTIMIZER' && <OptimizerView factorSet={factorSet} data={data} loading={loading} />}
                            {activeTab === 'ROTATION' && <RotationView data={data} loading={loading} />}
                            {activeTab === 'REGIMES' && <RegimesView data={data} loading={loading} />}
                        </motion.div>
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
}
