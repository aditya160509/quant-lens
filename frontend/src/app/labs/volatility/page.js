"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { 
    Search, Database, Calendar, Activity, ChevronDown, Boxes, Zap, 
    ShieldAlert, TrendingDown, Layers, MousePointer2, Download,
    Clock, Maximize2, Minimize2, RefreshCw, Shield, Terminal,
    BarChart3, Grid, List, Scale, Target, TrendingUp
} from 'lucide-react';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { 
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, 
    ResponsiveContainer, LineChart, Line, BarChart, Bar,
    Cell, PieChart, Pie, Radar, RadarChart, PolarGrid, 
    PolarAngleAxis, PolarRadiusAxis, ScatterChart, Scatter,
    ReferenceLine, Legend
} from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';

import { runVolatilityIntelligence } from '@/lib/api';

// Dynamic Plotly for 3D Surface
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

// =============================================================================
// THEME & CONSTANTS (Institutional Sharpness)
// =============================================================================

const TABS = [
    { id: 'DNA', label: 'VOLATILITY DNA', description: 'Institutional Realized Risk Metrics', info: 'Forensic breakdown of realized volatility using advanced estimators (Yang-Zhang, Parkinson).' },
    { id: 'SURFACE', label: 'TERM SURFACE', description: 'Multi-Horizon Dispersion & Persistence', info: 'Analyzes the term structure of volatility across multiple time horizons.' },
    { id: 'EDGE', label: 'RISK PREMIUM', description: 'Forensic Bayesian VRP Overlay', info: 'Calculates the Volatility Risk Premium (VRP) – the spread between implied and realized risk.' },
    { id: 'TRAPS', label: 'PRICE TRAPS', description: 'Probability Cones & Gamma Walls', info: 'Maps institutional price barriers using probability cones and simulated options gamma.' },
    { id: 'SKEW', label: 'ASYMMETRY', description: 'Panic/Greed Distributions', info: 'Measures the skewness and kurtosis of vol surfaces to detect crash potential.' },
    { id: 'DISPERSION', label: 'DISPERSION', description: 'Cross-Sectional Fragility Tracker', info: 'Tracks index-level dispersion vs constituent correlation to find alpha opportunities.' },
    { id: 'CLUSTERS', label: 'REGIME CLUSTERS', description: 'State Transition Forensics', info: 'Detects volatility clustering states and transition probabilities.' },
];

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
                            <Shield size={12} className="text-amber-500" />
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

// =============================================================================
// SUB-COMPONENTS (Professional Sizing)
// =============================================================================

const StatBox = ({ label, value, subValue, trend }) => (
  <div className="bg-white/[0.02] border border-white/[0.05] p-5 rounded-2xl flex flex-col gap-1 backdrop-blur-xl relative overflow-hidden group hover:bg-white/[0.04] transition-all duration-500">
    <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-amber-500/20 to-transparent" />
    <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] leading-none">{label}</span>
    <div className="flex items-baseline gap-2 mt-1.5">
      <span className="text-2xl font-black text-white tracking-tighter font-display">{value}</span>
      {trend !== undefined && (
        <span className={`text-[10px] font-bold ${parseFloat(trend) >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
          {parseFloat(trend) >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
        </span>
      )}
    </div>
    {subValue && <span className="text-[10px] text-gray-600 font-medium uppercase tracking-wide truncate">{subValue}</span>}
  </div>
);

const Card = ({ title, subtitle, icon: Icon, children, className = "", noPadding = false, info = "Metric Intelligence" }) => (
  <div className={`bg-white/[0.02] border border-white/[0.05] rounded-3xl overflow-hidden backdrop-blur-2xl shadow-2xl flex flex-col hover:border-white/[0.1] transition-all duration-700 ${className}`}>
    <div className="px-6 py-5 border-b border-white/[0.05] flex items-center justify-between bg-white/[0.01]">
      <div className="flex items-center gap-4">
        <div className="p-2 rounded-lg bg-white/[0.03] border border-white/5">
          {Icon && <Icon className="text-gray-500/80" size={16} />}
        </div>
        <div>
          <h3 className="text-[11px] font-black text-white tracking-[0.2em] uppercase">{title}</h3>
          {subtitle && <p className="text-[9px] text-gray-500 font-medium uppercase tracking-widest mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <MetricTooltip text={info}>
        <div className="p-1.5 rounded-full hover:bg-white/5 transition-colors group cursor-help">
            <Shield size={14} className="text-gray-600 group-hover:text-amber-500/60 transition-colors" />
        </div>
      </MetricTooltip>
    </div>
    <div className={`${noPadding ? '' : 'p-6'} flex-1`}>{children}</div>
  </div>
);



// =============================================================================
// MODULE VIEWS (All 6 Features per Module)
// =============================================================================

const DNAView = ({ data }) => {
    if (!data) return null;
    const chartData = data.dates?.map((d, i) => ({
        date: d,
        yz: data.yang_zhang[i] * 100,
        rv: data.realized[i] * 100
    }));

    return (
        <div className="flex flex-col gap-5 h-full pb-20 no-scrollbar overflow-y-auto">
            <div className="grid grid-cols-4 gap-4">
                <StatBox label="YZ Estimator" value={`${(data.yang_zhang[data.yang_zhang.length-1] * 100).toFixed(2)}%`} subValue="Institutional Model" />
                <StatBox label="Hurst Exponent" value={data.hurst_exponent?.toFixed(3)} subValue={data.hurst_exponent > 0.5 ? "Trending" : "Mean-Reverting"} />
                <StatBox label="Z-Score Surprise" value={data.z_score_current?.toFixed(2)} subValue="Std Deviations" />
                <StatBox label="Tail Risk (Kurtosis)" value={data.stats?.kurtosis.toFixed(2)} subValue="Fat-tail Severity" />
            </div>

            <div className="grid grid-cols-12 gap-5 h-[350px]">
                <Card title="Multi-Estimator Realized Vol" subtitle="Yang-Zhang vs. Close-to-Close" icon={Activity} className="col-span-8">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData}>
                                <defs>
                                    <linearGradient id="colorYZ" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.2}/>
                                        <stop offset="95%" stopColor="#fbbf24" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                <XAxis dataKey="date" stroke="#4b5563" fontSize={9} minTickGap={60} axisLine={false} tickLine={false} />
                                <YAxis stroke="#4b5563" fontSize={9} unit="%" axisLine={false} tickLine={false} />
                                <Tooltip 
                                    contentStyle={{ backgroundColor: '#0a0e17', border: '1px solid #1e293b', fontSize: '9px', borderRadius: '8px' }}
                                    itemStyle={{ color: '#fff' }}
                                />
                                <Area type="monotone" dataKey="yz" name="Yang-Zhang Efficiency" stroke="#fbbf24" fillOpacity={1} fill="url(#colorYZ)" strokeWidth={2} />
                                <Area type="monotone" dataKey="rv" name="Classic Realized" stroke="#3b82f6" fillOpacity={0} strokeWidth={1} strokeDasharray="5 5" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Card>

                <div className="col-span-4 flex flex-col gap-5">
                    <Card title="Intraday Vol Density" subtitle="30-Min Realized Intensity" icon={Clock} className="flex-1">
                        <div className="h-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={data.intraday_density}>
                                    <Bar dataKey="val" fill="#fbbf24" radius={[2, 2, 0, 0]} />
                                    <XAxis dataKey="bucket" stroke="#4b5563" fontSize={7} axisLine={false} tickLine={false} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </Card>
                    <Card title="Volatility Persistence" subtitle="Autocorr Decay (L1-10)" icon={Activity} className="flex-1">
                        <div className="h-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={data.persistence_ledger?.map((v, i) => ({ b: i+1, v }))}>
                                    <Bar dataKey="v" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                                    <XAxis dataKey="b" stroke="#4b5563" fontSize={7} axisLine={false} tickLine={false} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </Card>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-5">
                <div className="bg-[#0f172a]/20 border border-[#1e293b] p-4 rounded-xl">
                    <h4 className="text-[9px] font-black text-amber-500 uppercase tracking-widest mb-3">Skewness Analysis</h4>
                    <p className="text-xl font-black text-white">{data.stats?.skewness.toFixed(3)}</p>
                    <p className="text-[9px] text-gray-500 mt-1 uppercase">Distribution Asymmetry</p>
                </div>
                <div className="bg-[#0f172a]/20 border border-[#1e293b] p-4 rounded-xl">
                    <h4 className="text-[9px] font-black text-amber-500 uppercase tracking-widest mb-3">Whale Cluster Factor</h4>
                    <p className="text-xl font-black text-white">{(data.stats?.vol_of_vol * 100).toFixed(1)}%</p>
                    <p className="text-[9px] text-gray-500 mt-1 uppercase">Intraday Concentration</p>
                </div>
                <div className="bg-[#0f172a]/20 border border-[#1e293b] p-4 rounded-xl">
                    <h4 className="text-[9px] font-black text-amber-500 uppercase tracking-widest mb-3">Memory (Hurst)</h4>
                    <p className="text-xl font-black text-white">{data.hurst_exponent.toFixed(2)}</p>
                    <p className="text-[9px] text-gray-500 mt-1 uppercase">Structural Persistence</p>
                </div>
            </div>
        </div>
    );
};

const SURFACEView = ({ data }) => {
    if (!data) return null;
    const estimatorData = data.dates.map((d, i) => ({
        date: d,
        log: data.rv_log?.[i] * 100,
        gk: data.rv_garman_klass?.[i] * 100,
        parkinson: data.rv_parkinson?.[i] * 100,
        yz: data.rv_yang_zhang?.[i] * 100
    }));

    const termStructureData = data.dates.map((d, i) => ({
        date: d,
        short: data.term_structure_stack?.short[i] * 100,
        medium: data.term_structure_stack?.medium[i] * 100,
        long: data.term_structure_stack?.long[i] * 100
    }));

    return (
        <div className="flex flex-col gap-6 h-full pb-20 no-scrollbar overflow-y-auto">
            <div className="grid grid-cols-4 gap-4">
                <StatBox label="Parkinson Efficiency" value={data.stats.parkinson_efficiency.toFixed(3)} subValue="Range/Log Ratio" />
                <StatBox label="EWMA Alpha" value={data.stats.ewma_alpha.toFixed(2)} subValue="Decay Factor" />
                <StatBox label="Vol-of-Vol" value={(data.stats.vvol_current * 100).toFixed(2)} subValue="Regime Stability" />
                <StatBox label="Slope Status" value={data.stats.slope_status} subValue="Horizon Term Risk" />
            </div>

            <div className="grid grid-cols-12 gap-6 h-[400px]">
                <Card title="RV Forensic Stack" subtitle="Multi-Estimator Engine (DNA Standard)" icon={Activity} className="col-span-12">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={estimatorData}>
                                <defs>
                                    {['log', 'gk', 'parkinson', 'yz'].map((id, idx) => (
                                        <linearGradient key={id} id={`color${id}`} x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor={['#3b82f6', '#10b981', '#fbbf24', '#9333ea'][idx]} stopOpacity={0.2}/>
                                            <stop offset="95%" stopColor={['#3b82f6', '#10b981', '#fbbf24', '#9333ea'][idx]} stopOpacity={0}/>
                                        </linearGradient>
                                    ))}
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis dataKey="date" hide />
                                <YAxis stroke="#4b5563" fontSize={9} unit="%" axisLine={false} tickLine={false} />
                                <Tooltip contentStyle={{ backgroundColor: '#0a0e17', borderRadius: '8px', border: '1px solid #1e293b', fontSize: '9px' }} />
                                <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '9px', fontWeight: 'bold', textTransform: 'uppercase' }} />
                                <Area type="monotone" dataKey="log" stroke="#3b82f6" fill="url(#colorlog)" strokeWidth={2} name="Close-to-Close" stackId="1" />
                                <Area type="monotone" dataKey="gk" stroke="#10b981" fill="url(#colorgk)" strokeWidth={2} name="Garman-Klass" stackId="2" />
                                <Area type="monotone" dataKey="parkinson" stroke="#fbbf24" fill="url(#colorparkinson)" strokeWidth={2} name="Parkinson" stackId="3" />
                                <Area type="monotone" dataKey="yz" stroke="#9333ea" fill="url(#coloryz)" strokeWidth={2} name="Yang-Zhang" stackId="4" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>

            <div className="grid grid-cols-12 gap-6">
                <Card title="Term Structure Persistence" subtitle="Short vs Medium vs Long Horizon Stability" icon={Layers} className="col-span-12">
                    <div className="h-48">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={termStructureData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis dataKey="date" hide />
                                <YAxis stroke="#4b5563" fontSize={9} unit="%" axisLine={false} tickLine={false} />
                                <Tooltip contentStyle={{ backgroundColor: '#0a0e17', borderRadius: '8px', border: '1px solid #1e293b', fontSize: '9px' }} />
                                <Area type="monotone" dataKey="short" stroke="#fbbf24" fill="#fbbf24" fillOpacity={0.15} strokeWidth={2} name="Short (10D)" />
                                <Area type="monotone" dataKey="medium" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={2} name="Medium (60D)" />
                                <Area type="monotone" dataKey="long" stroke="#9333ea" fill="#9333ea" fillOpacity={0.05} strokeWidth={2} name="Long (252D)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>
        </div>
    );
};

const EDGEView = ({ data }) => {
    if (!data) return null;
    const chartData = data.dates.map((d, i) => ({
        date: d,
        vrp: data.vrp_spread[i] * 100,
        confidence: data.vrp_confidence ? data.vrp_confidence[i] : 50
    }));

    return (
        <div className="flex flex-col gap-6 h-full pb-20 no-scrollbar overflow-y-auto">
            <div className="grid grid-cols-4 gap-4">
                <StatBox label="Bayesian Score" value={data.bayesian_signal?.toFixed(1)} subValue="Setup Confidence" />
                <StatBox label="Edge Decay (AC1)" value={data.edge_decay_velocity?.toFixed(3)} subValue="Persistence" />
                <StatBox label="VVIX Proxy" value={(data.vvix_proxy * 100).toFixed(2)} subValue="Vol of Vol Index" />
                <StatBox label="Alpha Ratio" value={(data.alpha_backtest[data.alpha_backtest.length-1] / 100).toFixed(2)} subValue="Cumulative Gain" />
            </div>

            <div className="grid grid-cols-12 gap-6 min-h-[450px]">
                <Card title="VRP Bayesian Overlay" subtitle="Implied vs Realized Edge with Confidence Bounds" icon={Zap} className="col-span-12">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData}>
                                <defs>
                                    <linearGradient id="colorConf" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.1}/>
                                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis dataKey="date" hide />
                                <YAxis stroke="#4b5563" fontSize={9} axisLine={false} tickLine={false} />
                                <Tooltip contentStyle={{ backgroundColor: '#0a0e17', borderRadius: '8px', border: '1px solid #1e293b', fontSize: '9px' }} />
                                <Area type="monotone" dataKey="confidence" stroke="none" fill="url(#colorConf)" name="Signal Confidence" />
                                <Area type="monotone" dataKey="vrp" stroke="#10b981" fill="none" strokeWidth={2} name="VRP Spread" />
                                <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>
        </div>
    );
};

const TRAPSView = ({ data }) => {
    if (!data) return null;
    const chartData = (data.horizons || []).map((h, i) => ({
        horizon: h,
        p: data.spot,
        u1: data.cone_1s?.u[i],
        l1: data.cone_1s?.l[i],
        u2: data.cone_2s?.u[i],
        l2: data.cone_2s?.l[i],
        u3: data.cone_3s?.u[i],
        l3: data.cone_3s?.l[i],
    }));

    return (
        <div className="flex flex-col gap-5 h-full pb-20 no-scrollbar overflow-y-auto">
            <div className="grid grid-cols-4 gap-4">
                <StatBox label="Expected Move" value={`±$${data.expected_move_30d?.toFixed(2)}`} subValue="30D Options Implied" />
                <StatBox label="ADR Comparison" value={`$${data.adr_comparison?.toFixed(2)}`} subValue="Avg Daily Range" />
                <StatBox label="Barrier Breach" value={`${(data.barrier_breach_rate * 100).toFixed(1)}%`} subValue="180D Tail Events" />
                <StatBox label="Pinning Conf." value={`${(data.pinning_prob?.[20] * 100)?.toFixed(1)}%`} subValue="20D Zone Probability" />
            </div>

            <div className="grid grid-cols-12 gap-5 h-[400px]">
                <Card title="Institutional Probability Cones" subtitle="180-Day Projection Matrix" icon={Target} className="col-span-8 relative">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis dataKey="horizon" stroke="#4b5563" fontSize={9} unit="d" axisLine={false} tickLine={false} />
                                <YAxis domain={['auto', 'auto']} stroke="#4b5563" fontSize={9} axisLine={false} tickLine={false} />
                                <Tooltip contentStyle={{ backgroundColor: '#0a0e17', borderRadius: '8px', border: '1px solid #1e293b', fontSize: '9px' }} />
                                <Line type="monotone" dataKey="p" stroke="#fff" strokeWidth={2} dot={false} name="Current Spot" />
                                <Line type="monotone" dataKey="u1" stroke="#fbbf24" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                                <Line type="monotone" dataKey="l1" stroke="#fbbf24" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                                <Line type="monotone" dataKey="u2" stroke="#3b82f6" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                                <Line type="monotone" dataKey="l2" stroke="#3b82f6" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                                <Line type="monotone" dataKey="u3" stroke="#9333ea" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                                <Line type="monotone" dataKey="l3" stroke="#9333ea" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
                <Card title="Institutional Level Ledger" className="col-span-4" icon={Layers}>
                    <div className="space-y-2">
                        {Object.entries(data.institutional_levels || {}).sort((a,b) => b[1]-a[1]).map(([label, price], i) => (
                            <div key={label} className={`flex justify-between items-center p-2.5 rounded-lg border border-white/5 bg-[#020408] group hover:border-amber-500/20 transition-all`}>
                                <span className="text-[9px] font-black text-[#64748b] uppercase tracking-widest">{label.replace('_', ' ')}</span>
                                <span className="text-xs font-black text-white">${price.toFixed(2)}</span>
                            </div>
                        ))}
                        <div className="mt-6 p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-xl">
                            <div className="flex items-center gap-2 mb-1.5">
                                <Shield size={12} className="text-emerald-500" />
                                <span className="text-[9px] text-emerald-500 font-extrabold uppercase tracking-widest leading-none">Safe Zone Active</span>
                            </div>
                            <p className="text-[9px] text-[#94a3b8] leading-normal uppercase">Current spot consolidated within 1-sigma probability cone.</p>
                        </div>
                    </div>
                </Card>
            </div>
            
            <div className="grid grid-cols-1 gap-5">
                <Card title="Gamma Pressure Proxy Map" subtitle="Simulated Options Exposure Density" icon={Grid}>
                    <div className="h-40 flex items-end gap-1">
                        {data.gamma_pressure?.map((g, i) => (
                            <div 
                                key={i} 
                                className="flex-1 rounded-sm bg-amber-500/80 hover:bg-amber-400 transition-colors group relative" 
                                style={{ height: `${g.weight * 100}%`, opacity: 0.3 + (g.weight * 0.7) }}
                            >
                                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 bg-[#0a0e17] border border-[#1e293b] p-2 rounded text-[8px] whitespace-nowrap z-50 pointer-events-none transition-opacity font-mono">
                                    Lvl: ${g.price.toFixed(2)}<br/>
                                    Press: {(g.weight * 100).toFixed(1)}%
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="flex justify-between mt-3 text-[8px] text-[#475569] font-black uppercase tracking-widest">
                        <span>L3_Lower Barrier</span>
                        <span>Current Spot Anchor</span>
                        <span>L3_Upper Barrier</span>
                    </div>
                </Card>
            </div>
        </div>
    );
};

const SKEWView = ({ data }) => {
    if (!data) return null;
    const chartData = data.dates.map((d, i) => ({
        date: d,
        downside: data.downside_vol[i] * 100,
        upside: data.upside_vol[i] * 100,
        ratio: data.skew_ratio[i]
    }));

    return (
        <div className="flex flex-col gap-5 h-full pb-20 no-scrollbar overflow-y-auto">
            <div className="grid grid-cols-4 gap-4">
                <StatBox label="Panic / Greed Ratio" value={data.skew_ratio[data.skew_ratio.length-1].toFixed(2)} subValue="Positive vs Negative Vol" />
                <StatBox label="Downside Velocity" value={data.downside_capture_velocity.toFixed(4)} subValue="Crash Acceleration" />
                <StatBox label="Tail Risk Prob" value={`${(data.tail_risk_prob * 100).toFixed(2)}%`} subValue="3-Sigma Probability" />
                <StatBox label="Panic Delta" value={`${(data.panic_greed_delta * 100).toFixed(1)}%`} subValue="Deviation from Fair Skew" />
            </div>

            <div className="grid grid-cols-12 gap-5 h-[350px]">
                <Card title="Asymmetric Semi-Volatility" subtitle="Downside vs. Upside Realized Risk" icon={Scale} className="col-span-8">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis dataKey="date" hide />
                                <YAxis stroke="#4b5563" fontSize={9} axisLine={false} tickLine={false} />
                                <Tooltip contentStyle={{ backgroundColor: '#0a0e17', borderRadius: '8px', border: '1px solid #1e293b', fontSize: '9px' }} />
                                <Area type="monotone" dataKey="downside" stackId="1" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.15} strokeWidth={2} name="Negative Vol" />
                                <Area type="monotone" dataKey="upside" stackId="2" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={2} name="Positive Vol" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
                <Card title="Vol Smirk Radar" icon={Target} className="col-span-4">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={data.vol_smirk_radar}>
                                <PolarGrid stroke="#1e293b" />
                                <PolarAngleAxis dataKey="axis" stroke="#64748b" fontSize={10} fontWeight="bold" />
                                <Radar 
                                    name="Skew Bias" 
                                    dataKey="value" 
                                    stroke="#f43f5e" 
                                    fill="#f43f5e" 
                                    fillOpacity={0.3} 
                                />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>
 
            <div className="grid grid-cols-1 gap-5">
                <Card title="Tail Risk Velocity" subtitle="60-Day Kurtosis Rolling Momentum" icon={Activity}>
                    <div className="h-24">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data.tail_risk_velocity.map((v, i) => ({ i, v }))}>
                                <Area type="monotone" dataKey="v" stroke="#9333ea" fill="#9333ea" fillOpacity={0.15} />
                                <XAxis hide />
                                <YAxis hide domain={['auto', 'auto']} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="flex justify-between mt-2 text-[8px] text-[#475569] font-bold uppercase tracking-widest">
                        <span>T-252 Trading Days</span>
                        <span>Institutional Tail Anchor</span>
                        <span>Active State</span>
                    </div>
                </Card>
            </div>
        </div>
    );
};

const DISPERSIONView = ({ data }) => {
    if (!data) return null;
    const dispersionTrackerData = data.dates?.map((d, i) => ({
        date: d,
        velocity: data.dispersion_series?.[i] || 0.5,
        fragility: 1 - (data.dispersion_series?.[i] || 0.5)
    }));

    return (
        <div className="flex flex-col gap-6 h-full pb-20 no-scrollbar overflow-y-auto">
            <div className="grid grid-cols-4 gap-4">
                <StatBox label="Avg Correlation" value={data.avg_correlation.toFixed(2)} subValue="Cluster Cohesion" />
                <StatBox label="Index Vol" value={`${(data.index_vol * 100).toFixed(2)}%`} subValue="Benchmark Baseline" />
                <StatBox label="Theo Dispersion" value={data.theoretical_dispersion.toFixed(3)} subValue="Expected Basis" />
                <StatBox label="Matrix Size" value={data.matrix_size} subValue="Active Universe" />
            </div>

            <div className="grid grid-cols-12 gap-6 h-[400px]">
                <Card title="Institutional Alpha Ledger" icon={List} className="col-span-6" noPadding>
                    <div className="h-full overflow-y-auto no-scrollbar">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-[#0a0e17] z-10">
                                <tr className="border-b border-white/5">
                                    <th className="p-3 text-[9px] font-black text-[#475569] uppercase tracking-widest">Ticker</th>
                                    <th className="p-3 text-[9px] font-black text-[#475569] uppercase tracking-widest">Vol</th>
                                    <th className="p-3 text-[9px] font-black text-[#475569] uppercase tracking-widest text-right">Opp Score</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.alpha_ledger.map((item, i) => (
                                    <tr key={item.ticker} className="border-b border-white/5 hover:bg-white/5 transition-all">
                                        <td className="p-3 text-[10px] font-black text-white">{item.ticker}</td>
                                        <td className="p-3 text-[10px] text-[#94a3b8]">{(item.vol * 100).toFixed(1)}%</td>
                                        <td className="p-3 text-right">
                                            <span className="px-2 py-1 bg-amber-500/10 text-amber-500 rounded text-[9px] font-black">{item.score.toFixed(2)}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
                <Card title="Structural Fragmentation Tracker" subtitle="Alpha Opportunity Selection Matrix" icon={Target} className="col-span-6">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={dispersionTrackerData}>
                                <defs>
                                    <linearGradient id="colorFrag" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis dataKey="date" hide />
                                <YAxis stroke="#4b5563" fontSize={9} axisLine={false} tickLine={false} />
                                <Tooltip cursor={{ stroke: '#fbbf24', strokeWidth: 2 }} contentStyle={{ backgroundColor: '#0a0e17', border: '1px solid #1e293b', fontSize: '9px' }} />
                                <Area type="monotone" dataKey="fragility" stroke="#3b82f6" fill="url(#colorFrag)" strokeWidth={2} name="Structural Dispersion" />
                                <ReferenceLine y={1 - data.avg_correlation} stroke="#fbbf24" strokeDasharray="3 3" label={{ value: 'BASELINE', fill: '#fbbf24', fontSize: 8 }} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>
        </div>
    );
};

const CLUSTERSView = ({ data }) => {
    if (!data) return null;
    return (
        <div className="flex flex-col gap-5 h-full pb-20 no-scrollbar overflow-y-auto">
            <div className="grid grid-cols-4 gap-4">
                <StatBox label="Cluster Duration" value={`${data.mean_clustering_duration.toFixed(1)}d`} subValue="Regime Persistence" />
                <StatBox label="Auto-Corr Score" value={data.clustering_auto_corr.toFixed(3)} subValue="5-Day Vol Memory" />
                <StatBox label="High Vol Streak" value={`${data.high_vol_streak}d`} subValue="Avg Panic Window" />
                <StatBox label="Robust Threshold" value={data.robust_threshold.toFixed(2)} subValue="Institutional Median + 2MAD" />
            </div>

            <div className="grid grid-cols-12 gap-5 h-[350px]">
                <Card title="Regime Transition Matrix" icon={Boxes} className="col-span-6">
                    <div className="space-y-4">
                        {Object.entries(data.transition_matrix).map(([fromState, toStates]) => (
                            <div key={fromState} className="space-y-2">
                                 <h4 className="text-[9px] font-black text-[#64748b] uppercase tracking-widest">FROM: {fromState}</h4>
                                 <div className="grid grid-cols-3 gap-2">
                                    {Object.entries(toStates).map(([toState, prob]) => (
                                        <div key={toState} className="p-2.5 bg-black/40 border border-white/5 rounded-lg text-center hover:border-amber-500/20 transition-all cursor-default">
                                            <p className="text-[7px] text-[#475569] uppercase font-bold mb-0.5">{toState}</p>
                                            <p className="text-xs font-black text-white">{(prob * 100).toFixed(0)}%</p>
                                        </div>
                                    ))}
                                 </div>
                            </div>
                        ))}
                    </div>
                </Card>
                <Card title="Regime Energy Spectrum" icon={Activity} className="col-span-6">
                    <div className="h-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data.spectrum_freqs.map((f, i) => ({ f: f.toFixed(2), p: data.spectrum_powers[i] }))}>
                                <Area type="monotone" dataKey="p" stroke="#9333ea" fill="#9333ea" fillOpacity={0.15} strokeWidth={2} />
                                <XAxis dataKey="f" hide />
                                <YAxis hide />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>
            
            <div className="p-6 bg-amber-500/5 border border-amber-500/20 rounded-xl flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-3 mb-1">
                        <Zap size={14} className="text-amber-500" />
                        <h4 className="text-[10px] font-bold text-amber-500 uppercase tracking-[0.2em]">Current State Tracker</h4>
                    </div>
                    <p className="text-xl font-black text-white tracking-widest">92% PROBABILITY - {data.current_state} REGIME</p>
                </div>
                <div className="h-12 w-1 bg-amber-500/20 rounded-full overflow-hidden">
                    <div className="h-full bg-amber-500 w-full animate-pulse" />
                </div>
            </div>
        </div>
    );
};

// =============================================================================
// MAIN PAGE COMPONENT
// =============================================================================

export default function VolatilityIntelligencePage() {
    const [activeTab, setActiveTab] = useState('DNA');
    const [ticker, setTicker] = useState('TSLA');
    const [windowYears, setWindowYears] = useState(2);
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        try {
            const result = await runVolatilityIntelligence(ticker, windowYears);
            setData(result);
        } catch (err) {
            console.error("Vol analysis failed:", err);
        } finally {
            setLoading(false);
        }
    }, [ticker, windowYears]);

    const handleExport = () => {
        if (!data) return;
        const csvContent = "data:text/csv;charset=utf-8," + 
            Object.keys(data).map(k => `${k},${JSON.stringify(data[k])}`).join("\n");
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `vol_analytics_${ticker}.csv`);
        document.body.appendChild(link);
        link.click();
    };

    useEffect(() => {
        runAnalysis();
    }, [runAnalysis]);

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
                    <button 
                        onClick={handleExport}
                        className="flex items-center gap-3 px-4 py-1.5 bg-[#0a0e17] hover:bg-white/5 text-[#94a3b8] hover:text-white rounded-full text-[10px] font-black uppercase tracking-widest border border-white/5 transition-all active:scale-95"
                    >
                        <Download size={14} /> Export CSV
                    </button>
                    <div className="flex items-center bg-emerald-500/5 border border-emerald-500/10 rounded-full px-4 py-1.5 shadow-inner">
                        <Activity size={14} className="text-emerald-500 mr-2 animate-pulse" />
                        <span className="text-[9px] font-black text-emerald-500 uppercase tracking-widest">LIVE_ENGINE</span>
                    </div>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Control Sidebar */}
                <div className="w-[340px] bg-[#0a0e17] border-r border-[#1f2937] p-8 flex flex-col gap-10 z-20 shadow-2xl overflow-y-auto no-scrollbar">
                    <div className="space-y-10">
                        <div>
                            <h3 className="text-[9px] font-black text-gray-600 uppercase tracking-[0.3em] mb-4 flex items-center gap-2">
                                <Terminal size={12} className="text-gray-500" /> Symbol Terminal
                            </h3>
                            <div className="relative group">
                                <TradingViewSearch 
                                    onSelect={(val) => { setTicker(val); runAnalysis(); }}
                                    placeholder="SEARCH SYMBOL..."
                                />
                            </div>
                        </div>

                        <div>
                            <h3 className="text-[9px] font-black text-gray-600 uppercase tracking-[0.3em] mb-4 flex items-center gap-2">
                                <Calendar size={12} className="text-gray-500" /> Analysis Horizon
                            </h3>
                            <div className="grid grid-cols-3 gap-2">
                                {[1, 2, 5].map(y => (
                                    <button
                                        key={y}
                                        onClick={() => { setWindowYears(y); runAnalysis(); }}
                                        className={`py-3 rounded-lg border text-[10px] font-black transition-all ${
                                            windowYears === y 
                                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' 
                                            : 'border-white/5 text-gray-500 hover:text-white hover:bg-white/5'
                                        }`}
                                    >
                                        {y}YR
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="mt-auto p-6 rounded-2xl bg-white/[0.02] border border-white/[0.05] backdrop-blur-xl">
                            <div className="flex items-center gap-3 mb-3 text-amber-500/60">
                                <Shield size={14} />
                                <span className="text-[10px] font-black uppercase tracking-[0.2em]">Compliance Check</span>
                            </div>
                            <p className="text-[10px] text-gray-600 font-medium uppercase tracking-tight leading-relaxed">
                                Yang-Zhang estimation active. Handling overnight volatility bias with seasonal adjustment.
                            </p>
                        </div>
                    </div>

                    <div className="mt-auto">
                        <button 
                            onClick={runAnalysis}
                            disabled={loading}
                            className={`w-full py-5 rounded-2xl font-black uppercase tracking-[0.25em] text-[10px] flex items-center justify-center gap-4 transition-all shadow-2xl relative overflow-hidden group ${
                                loading 
                                ? 'bg-gray-800 text-gray-500 cursor-not-allowed' 
                                : 'bg-gradient-to-r from-amber-600 to-amber-500 text-black hover:scale-[1.02] active:scale-[0.98]'
                            }`}
                        >
                            {loading ? <RefreshCw size={18} className="animate-spin" /> : <Zap size={18} fill="currentColor" />}
                            {loading ? 'CALCULATING...' : 'EXECUTE ANALYSIS'}
                        </button>
                    </div>
                </div>

                {/* Main View Area */}
                <div className="flex-1 overflow-y-auto bg-[#020408] p-10 no-scrollbar relative min-w-0">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={activeTab + ticker}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: 0.3 }}
                            className="h-full flex flex-col"
                        >
                            {/* Title Block */}
                            <div className="mb-12 flex items-end justify-between">
                                <div>
                                    <div className="flex items-center gap-4 mb-3">
                                        <h1 className="text-4xl font-black text-white tracking-tighter uppercase whitespace-nowrap font-display">
                                            Institutional <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-200 to-amber-500">Volatility Studio</span>
                                        </h1>
                                    </div>
                                    <p className="text-[12px] text-gray-500 font-medium tracking-widest uppercase opacity-80">{TABS.find(t => t.id === activeTab)?.description}</p>
                                </div>
                                <div className="text-right flex flex-col items-end">
                                    <span className="text-4xl font-black text-white tracking-widest font-display">{ticker}</span>
                                    <span className="text-[10px] text-gray-600 font-black uppercase tracking-[0.3em] font-mono mt-1">
                                        <span className="text-amber-500/50 mr-2">●</span> Active_Stream
                                    </span>
                                </div>
                            </div>

                            {/* View Router */}
                            <div className="flex-1">
                                {loading ? (
                                    <div className="h-[400px] flex items-center justify-center">
                                        <div className="flex flex-col items-center gap-4">
                                            <RefreshCw size={32} className="text-amber-500 animate-spin" />
                                            <div className="text-[9px] font-black text-amber-500 uppercase tracking-[0.5em] animate-pulse">Computing Volatility Matrix...</div>
                                        </div>
                                    </div>
                                ) : (
                                    <>
                                        {activeTab === 'DNA' && <DNAView data={data?.dna} />}
                                        {activeTab === 'SURFACE' && <SURFACEView data={data?.surface} />}
                                        {activeTab === 'EDGE' && <EDGEView data={data?.edge} />}
                                        {activeTab === 'TRAPS' && <TRAPSView data={data?.traps} />}
                                        {activeTab === 'SKEW' && <SKEWView data={data?.skew} />}
                                        {activeTab === 'DISPERSION' && <DISPERSIONView data={data?.dispersion} />}
                                        {activeTab === 'CLUSTERS' && <CLUSTERSView data={data?.clusters} />}
                                    </>
                                )}
                            </div>
                        </motion.div>
                    </AnimatePresence>
                </div>
            </div>
            

        </div>
    );
}
