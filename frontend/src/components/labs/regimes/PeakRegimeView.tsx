
'use client';

import React, { useState, useMemo, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { 
  Shield, Waves, Repeat, Zap, Activity, Anchor, 
  ChevronRight, Globe, Info, Search, TrendingUp, TrendingDown,
  AlertTriangle, Filter, Database, BarChart3, LineChart as LineChartIcon,
  Maximize2, RefreshCw, Layers
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, 
  Tooltip, LineChart, Line, BarChart, Bar, Cell, PieChart, Pie, Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from 'recharts';

// Dynamic Plotly for 3D
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false }) as any;

import { motion, AnimatePresence } from 'framer-motion';

// --- Theme ---
const THEME = {
  bg: '#030305',
  card: 'rgba(15, 15, 25, 0.7)',
  border: 'rgba(255, 255, 255, 0.05)',
  text: '#f8fafc',
  textMuted: '#64748b',
  accent: '#a855f7',
  us: '#3b82f6',
  india: '#f97316',
  danger: '#ff2d55',
  warning: '#f59e0b',
  terminal_green: '#00ff41',
  terminal_bg: '#020408'
};

const PILLAR_CONFIG = [
  { id: 'integrity', label: 'Integrity', icon: Shield, color: '#10b981', info: 'Measures the mathematical coherence and eigenvalue distribution of the market universe.' },
  { id: 'massFlow', label: 'Mass Flow', icon: Waves, color: '#3b82f6', info: 'Tracks the probability diffusion between defined volatility regimes.' },
  { id: 'reflexivity', label: 'Reflexivity', icon: Repeat, color: '#f59e0b', info: 'Detects feedback loops where price action distorts underlying value anchors.' },
  { id: 'fragility', label: 'Fragility', icon: Zap, color: THEME.danger, info: 'Identifies systemic tension and liquidity gaps prone to flash-crash events.' },
  { id: 'nonlinearity', label: 'Nonlinearity', icon: Activity, color: '#ec4899', info: 'Analyzes chaotic dynamics and tail-risk potential using Lyapunov exponents.' },
  { id: 'governor', label: 'Governor', icon: Anchor, color: '#fbbf24', info: 'Sovereign risk assessment and high-level system stability mandate.' }
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

// --- Utilities ---
const StatGauge = ({ label, value, subValue, color, icon: Icon }) => (
  <div className="bg-white/[0.02] border border-white/[0.05] p-5 rounded-2xl flex flex-col gap-1 backdrop-blur-xl relative overflow-hidden group hover:bg-white/[0.04] transition-all duration-500">
    <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-white/5 to-transparent" />
    <div className="flex justify-between items-start mb-1">
      <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] leading-none">{label}</span>
      <Icon size={14} style={{ color }} className="opacity-60" />
    </div>
    <div className="flex items-baseline gap-2 mt-1.5">
      <span className="text-2xl font-black text-white tracking-tighter font-mono" style={{ color: value === 'CRITICAL' || value === 'NEGATIVE' ? '#ff2d55' : 'white' }}>{value}</span>
    </div>
    {subValue && <span className="text-[10px] text-gray-600 font-medium uppercase tracking-wide truncate mt-0.5">{subValue}</span>}
  </div>
);

const DenseTickerTable = ({ tickers, pillarId }) => {
  if (!tickers || tickers.length === 0) return null;
  
  const columns = {
    integrity: ['Ticker', 'Eigen Weight', 'Correlation', 'Coherence Δ'],
    massFlow: ['Ticker', 'Regime Beta', 'Fidelity %', 'Flow Intensity'],
    reflexivity: ['Ticker', 'Warp Score', 'Denial Heat', 'Squeeze Prob'],
    fragility: ['Ticker', 'Liquidity Risk', 'Convexity', 'Crash Prob'],
    nonlinearity: ['Ticker', 'Entropy Pulse', 'Hurst Exp', 'Chaos Coeff'],
    governor: ['Ticker', 'Signal', 'Severity', 'Action']
  }[pillarId] || ['Ticker', 'Val1', 'Val2', 'Val3'];

  const getRowData = (t) => {
    const keys = Object.keys(t).filter(k => k !== 'ticker');
    return keys.map(k => t[k]);
  };

  return (
    <div className="mt-8">
      <div className="flex items-center gap-2 mb-4 px-2 border-l-2 border-emerald-500">
        <h4 className="text-[10px] font-bold text-white uppercase tracking-wider">Constituent Risk Attribution</h4>
      </div>
      <div className="overflow-hidden rounded-sm border border-white/5 bg-[#020408]">
        <table className="w-full text-left border-collapse table-fixed">
          <thead>
            <tr className="border-b border-white/10 bg-[#0a0e17]">
              {columns.map(c => (
                <th key={c} className="p-2.5 text-[9px] font-black text-[#64748b] uppercase tracking-[0.15em] border-r border-white/5">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickers.slice(0, 15).map((t, i) => (
              <tr key={i} className="border-b border-white/5 hover:bg-[#fbbf24]/5 transition-all group">
                <td className="p-2.5 text-[10px] font-black text-white uppercase border-r border-white/5 bg-[#0a0e17]/30">{t.ticker}</td>
                {getRowData(t).map((val, j) => (
                  <td key={j} className="p-2.5 text-[10px] font-mono text-[#fbbf24] border-r border-white/5 group-hover:text-white">
                    {typeof val === 'number' ? (val > 1 || val < -1 ? val.toFixed(2) : val.toFixed(4)) : val}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// --- Pillar Views ---

const IntegrityView = ({ data }) => (
  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <StatGauge label="Alignment Score" value={`${data.alignmentScore.toFixed(1)}%`} subValue="Systemic Cohesion" color="#10b981" icon={Shield} />
      <StatGauge label="Spectral Gap" value={data.history?.[data.history.length-1]?.spectralGap.toFixed(3) || '0.000'} subValue="Dominance Factor" color="#3b82f6" icon={BarChart3} />
      <StatGauge label="Absorption Index" value={data.history?.[data.history.length-1]?.absorption.toFixed(2) || '0.00'} subValue="Fragility Trigger" color="#ff2d55" icon={AlertTriangle} />
      <StatGauge label="Coherence" value={data.history?.[data.history.length-1]?.coherence.toFixed(2) || '0.00'} subValue="Trend Stability" color="#f59e0b" icon={TrendingUp} />
    </div>
    
    <div className="bg-white/[0.02] border border-white/[0.05] p-8 rounded-3xl backdrop-blur-2xl shadow-2xl h-[400px]">
       <div className="flex justify-between items-center mb-8">
          <div>
            <h3 className="text-[11px] font-black text-white uppercase tracking-[0.2em] mb-1.5">Universe Variance Structure</h3>
            <p className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">Cross-constituent concentration analysis</p>
          </div>
          <div className="flex gap-6">
            <div className="flex items-center gap-3">
               <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]" />
               <span className="text-[9px] font-black text-gray-500 uppercase tracking-widest">Absorption</span>
            </div>
            <div className="flex items-center gap-3">
               <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.3)]" />
               <span className="text-[9px] font-black text-gray-500 uppercase tracking-widest">Spectral Gap</span>
            </div>
          </div>
       </div>
        <ResponsiveContainer width="100%" height="80%">
          <AreaChart data={data.history}>
            <defs>
              <linearGradient id="absGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
            <XAxis dataKey="t" hide />
            <YAxis tick={{fill: '#4b5563', fontSize: 9}} axisLine={false} tickLine={false} />
            <Tooltip 
              contentStyle={{background: '#0a0e17', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', fontSize: 10}} 
              itemStyle={{color: '#fff'}}
            />
            <Area type="monotone" dataKey="absorption" stroke="#10b981" fill="url(#absGradient)" strokeWidth={2} />
            <Area type="monotone" dataKey="spectralGap" stroke="#3b82f6" fill="transparent" strokeWidth={1} strokeDasharray="3 3" />
          </AreaChart>
        </ResponsiveContainer>
    </div>
    
    <DenseTickerTable tickers={data.tickerTable} pillarId="integrity" />
  </div>
);

const MassFlowView = ({ data }) => {
    const [viewMode, setViewMode] = useState('3D'); // '2D' or '3D'

    const plotData = useMemo(() => {
        if (!data?.history) return null;
        const z = [0,1,2,3].map(i => data.history.map(h => h.probs[i] * 100));
        const x = data.history.map(h => h.t);
        const y = ['Calm', 'Elevated', 'Stressed', 'Crisis'];
        return [{
            z, x, y,
            type: 'surface',
            colorscale: [['0.0', '#020408'], ['0.5', '#3b82f6'], ['1.0', '#fbbf24']],
            showscale: false,
            opacity: 0.9
        }];
    }, [data]);

    const timelineData = useMemo(() => {
        return data.history?.map(h => ({
            t: h.t,
            p0: h.probs[0] * 100,
            p1: h.probs[1] * 100,
            p2: h.probs[2] * 100,
            p3: h.probs[3] * 100,
        }));
    }, [data]);

    return (
      <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <StatGauge label="Market State" value={['CALM', 'ELEVATED', 'STRESSED', 'CRISIS'][data.currentState] || 'UNKNOWN'} subValue="Probability Center" color="#3b82f6" icon={Waves} />
          <StatGauge label="Mass Velocity" value={data.history?.[data.history.length-1]?.massVel.toFixed(3) || '0.000'} subValue="Rotation Speed" color="#f59e0b" icon={TrendingUp} />
          <StatGauge label="Structural Entropy" value={data.history?.[data.history.length-1]?.entropy.toFixed(2) || '0.00'} subValue="System Chaos" color="#ec4899" icon={Activity} />
          <StatGauge label="State Stability" value="STABLE" subValue="Persistence Score" color="#10b981" icon={Anchor} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
           <div className="lg:col-span-8 bg-white/[0.02] border border-white/[0.05] p-8 rounded-3xl backdrop-blur-2xl shadow-2xl h-[450px] flex flex-col">
              <div className="flex justify-between items-center mb-8">
                <div>
                    <h3 className="text-[11px] font-black text-white uppercase tracking-[0.2em] mb-1.5">Regime Diffusion Manifold</h3>
                    <p className="text-[10px] font-bold text-gray-600 uppercase tracking-widest">Multi-state probability projection</p>
                </div>
                <div className="flex bg-white/[0.05] rounded-full p-1 border border-white/10">
                   <button 
                     onClick={() => setViewMode('2D')}
                     className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-full transition-all ${viewMode === '2D' ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/20' : 'text-gray-500 hover:text-white'}`}
                   >2D_TIMELINE</button>
                   <button 
                     onClick={() => setViewMode('3D')}
                     className={`px-4 py-1.5 text-[9px] font-black uppercase tracking-widest rounded-full transition-all ${viewMode === '3D' ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/20' : 'text-gray-500 hover:text-white'}`}
                   >3D_SURFACE</button>
                </div>
              </div>
              <div className="w-full h-full pb-8">
                 {viewMode === '3D' ? (
                   <Plot
                      data={plotData}
                      layout={{
                          autosize: true,
                          paper_bgcolor: 'transparent',
                          plot_bgcolor: 'transparent',
                          margin: { l: 0, r: 0, b: 0, t: 0 },
                          scene: {
                              xaxis: { showgrid: false, zeroline: false, showticklabels: false },
                              yaxis: { showgrid: false, zeroline: false, showticklabels: false },
                              zaxis: { showgrid: false, zeroline: false, showticklabels: false },
                              camera: { eye: { x: 1.5, y: 1.5, z: 1.2 } },
                              bgcolor: 'transparent'
                          }
                      }}
                      style={{ width: '100%', height: '100%' }}
                      useResizeHandler={true}
                   />
                 ) : (
                   <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={timelineData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                        <XAxis dataKey="t" hide />
                        <YAxis tick={{fontSize: 9, fill: '#4b5563'}} axisLine={false} tickLine={false} />
                        <Tooltip contentStyle={{ background: '#0a0e17', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', fontSize: 10 }} />
                         <Area type="monotone" dataKey="p0" stackId="1" stroke="#10b981" fill="#10b981" fillOpacity={0.2} name="Calm" />
                         <Area type="monotone" dataKey="p1" stackId="1" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} name="Elevated" />
                         <Area type="monotone" dataKey="p2" stackId="1" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.2} name="Stressed" />
                         <Area type="monotone" dataKey="p3" stackId="1" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} name="Crisis" />
                      </AreaChart>
                   </ResponsiveContainer>
                 )}
              </div>
           </div>
           
           <div className="lg:col-span-4 bg-white/[0.02] border border-white/[0.05] p-8 rounded-3xl backdrop-blur-2xl shadow-2xl h-[450px] flex flex-col">
              <h3 className="text-[11px] font-black text-white uppercase tracking-[0.2em] mb-10">Transition Probability Matrix</h3>
              <div className="grid grid-cols-4 grid-rows-4 gap-3 flex-1">
                 {data.transitionMatrix?.map((row, i) => row.map((val: any, j: any) => (
                    <div 
                      key={`${i}-${j}`} 
                      className="flex items-center justify-center text-[10px] font-mono font-black border border-white/5 rounded-xl transition-all hover:scale-105"
                      style={{ 
                        backgroundColor: `rgba(251, 191, 36, ${Math.min(0.8, val)})`,
                        color: val > 0.4 ? 'black' : '#fbbf24'
                      }}
                    >
                      {(val * 100).toFixed(0)}%
                    </div>
                 )))}
              </div>
              <div className="flex justify-between mt-8 px-2">
                 <div className="text-[9px] font-black text-gray-600 uppercase tracking-[0.3em]">Min Vol</div>
                 <div className="text-[9px] font-black text-gray-600 uppercase tracking-[0.3em]">Max Vol</div>
              </div>
           </div>
        </div>
        
        <DenseTickerTable tickers={data.tickerTable} pillarId="massFlow" />
      </div>
    );
};

const ReflexivityView = ({ data }) => (
  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <StatGauge label="Warp Ratio" value={`${data.masterWarp.toFixed(1)}%`} subValue="Reality Distort" color="#f59e0b" icon={Repeat} />
      <StatGauge label="Reflexive Gain" value={data.history?.[data.history.length-1]?.reflexivity.toFixed(1)} subValue="Loop Intensity" color="#10b981" icon={TrendingUp} />
      <StatGauge label="Denial Heat" value={data.tickerTable?.[0]?.denialHeat.toFixed(2) || '0.00'} subValue="Market Tension" color="#ff2d55" icon={AlertTriangle} />
      <StatGauge label="Squeeze Prob" value={`${data.tickerTable?.[0]?.squeezePotential.toFixed(1)}%`} subValue="Percentile" color="#3b82f6" icon={Info} />
    </div>

    <div className="p-8 rounded-xl border border-white/5 bg-[#020408] h-[400px]">
       <h3 className="text-[10px] font-bold text-white uppercase tracking-wider mb-8">Market Reflexivity Map (Price vs Invariant)</h3>
       <ResponsiveContainer width="100%" height="80%">
          <AreaChart data={data.history}>
            <defs>
              <linearGradient id="warpGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2}/>
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" vertical={false} />
            <XAxis dataKey="t" tick={{fill: '#4b5563', fontSize: 9}} tickFormatter={v => v.slice(5)} axisLine={false} />
            <YAxis tick={{fill: '#4b5563', fontSize: 9, fontFamily: 'monospace'}} axisLine={false} />
            <Tooltip 
              contentStyle={{background: '#0a101f', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '4px', fontSize: 10, fontFamily: 'monospace'}}
              formatter={(val) => Number(val).toFixed(2)}
            />
            <Area type="monotone" dataKey="warp" stroke="#f59e0b" fill="url(#warpGradient)" strokeWidth={2} />
            <Line type="monotone" dataKey="reflexivity" stroke="#10b981" strokeWidth={1} dot={false} strokeDasharray="4 4" />
          </AreaChart>
       </ResponsiveContainer>
    </div>
    <DenseTickerTable tickers={data.tickerTable} pillarId="reflexivity" />
  </div>
);

const FragilityView = ({ data }) => (
  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <StatGauge label="Fragility Index" value={data.fragilityScore.toFixed(1)} subValue="Systemic Tension" color={THEME.danger} icon={Zap} />
      <StatGauge label="Liquidity Gap" value={data.history?.[data.history.length-1]?.liquidityGap.toFixed(2) || '0.00'} subValue="Order Book Depth" color={THEME.warning} icon={BarChart3} />
      <StatGauge label="Flash Prob" value={`${(data.tickerTable?.[0]?.flashCrashProb * 10 || 0.1).toFixed(1)}%`} subValue="Mechanical Risk" color={THEME.accent} icon={AlertTriangle} />
      <StatGauge label="Convexity" value={data.tickerTable?.[0]?.convexityStress.toFixed(2) || '1.00'} subValue="Gamma Stress Proxy" color={THEME.danger} icon={TrendingDown} />
    </div>
    <div className="p-8 rounded-xl border border-white/5 bg-[#020408] h-[400px]">
       <h3 className="text-[10px] font-bold text-white uppercase tracking-wider mb-8">Systemic Fragility Index</h3>
        <ResponsiveContainer width="100%" height="80%">
          <BarChart data={data.history}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" vertical={false} />
            <XAxis dataKey="t" tick={{fill: '#4b5563', fontSize: 9}} tickFormatter={v => v.slice(5)} axisLine={false} />
            <YAxis tick={{fill: '#4b5563', fontSize: 9, fontFamily: 'monospace'}} axisLine={false} />
            <Tooltip 
              contentStyle={{background: '#0a101f', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '4px', fontSize: 10, fontFamily: 'monospace'}}
              formatter={(val) => Number(val).toFixed(2)}
            />
            <Bar dataKey="fragility" fill="#ff2d55" radius={[2, 2, 0, 0]} opacity={0.6} />
            <Line type="monotone" dataKey="liquidityGap" stroke="#f59e0b" strokeWidth={2} dot={false} />
          </BarChart>
        </ResponsiveContainer>
    </div>
    <DenseTickerTable tickers={data.tickerTable} pillarId="fragility" />
  </div>
);

const NonlinearityView = ({ data }) => (
  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <StatGauge label="Chaos Coeff" value={data.history?.[data.history.length-1]?.chaos.toFixed(2) || '0.00'} subValue="Lyapunov Proxy" color="#ec4899" icon={Activity} />
      <StatGauge label="Structural Entropy" value={data.history?.[data.history.length-1]?.entropy.toFixed(3) || '0.000'} subValue="Predict Gap" color="#a855f7" icon={Maximize2} />
      <StatGauge label="Bifurcation Dist" value={data.bifurcationDistance.toFixed(1)} subValue="Edge of Cliff" color={THEME.danger} icon={AlertTriangle} />
      <StatGauge label="Avg Kurtosis" value={data.tickerTable?.[0]?.chaosCoefficient.toFixed(2) || '0.00'} subValue="Fat-Tail Profile" color={THEME.warning} icon={TrendingUp} />
    </div>
    <div className="p-8 rounded-xl border border-white/5 bg-[#020408] h-[400px]">
       <h3 className="text-[10px] font-bold text-white uppercase tracking-wider mb-8">Non-Linear Phase Projection</h3>
       <ResponsiveContainer width="100%" height="80%">
          <LineChart data={data.history}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" vertical={false} />
            <XAxis dataKey="t" tick={{fill: '#4b5563', fontSize: 9}} axisLine={false} />
            <YAxis tick={{fill: '#4b5563', fontSize: 9, fontFamily: 'monospace'}} axisLine={false} />
            <Tooltip 
              contentStyle={{background: '#0a101f', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '4px', fontSize: 10, fontFamily: 'monospace'}}
              formatter={(val) => Number(val).toFixed(3)}
            />
            <Line type="monotone" dataKey="chaos" stroke="#ec4899" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="entropy" stroke="#a855f7" strokeWidth={1} dot={false} strokeDasharray="8 8" />
          </LineChart>
       </ResponsiveContainer>
    </div>
    <DenseTickerTable tickers={data.tickerTable} pillarId="nonlinearity" />
  </div>
);

const GovernorView = ({ data }) => (
  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
       <div className="lg:col-span-2 p-10 rounded-sm border border-white/5 bg-[#020408] flex items-center justify-between overflow-hidden relative shadow-2xl">
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-blue-600/5 blur-[100px] rounded-full" />
          <div className="relative z-10">
             <div className="text-[9px] font-black text-[#fbbf24] uppercase tracking-[0.3em] mb-4 flex items-center gap-3">
                SYSTEM GOVERNOR
             </div>
             <h2 className="text-4xl font-black text-white tracking-tighter uppercase mb-3 leading-none">
                {data.state || 'NOMINAL'}
             </h2>
             <p className="text-[10px] text-[#64748b] font-black uppercase tracking-[0.1em] max-w-sm leading-relaxed">
                Global market mandate is currently in a resilient state. All structural primitives are within nominal operating thresholds.
             </p>
          </div>
          <div className="text-right relative z-10">
             <div className="text-7xl font-black text-white leading-none tracking-tighter">
                {data.stabilityIndex?.toFixed(0) || 72}
             </div>
             <div className="text-[9px] font-black text-[#fbbf24] uppercase tracking-[0.2em] mt-2">Stability MSI</div>
          </div>
       </div>
       
       <div className="lg:col-span-2 p-8 rounded-sm border border-white/5 bg-[#020408]">
          <h3 className="text-[9px] font-black text-[#64748b] uppercase tracking-[0.3em] mb-8 flex items-center gap-3">
             <RefreshCw size={12} className="text-[#fbbf24]" /> SYSTEM HEDGING EFFICIENCY
          </h3>
          <div className="space-y-6">
             {data.hedges?.map(h => (
                <div key={h.asset} className="flex flex-col gap-2">
                   <div className="flex justify-between items-end">
                      <span className="text-[10px] font-black tracking-[0.2em] text-white uppercase">{h.asset}</span>
                      <span className="text-[11px] font-mono text-blue-400 font-bold">{h.efficiency.toFixed(1)}%</span>
                   </div>
                   <div className="h-1.5 w-full bg-white/5 rounded-sm overflow-hidden p-[0.5px]">
                      <div className="h-full bg-[#fbbf24] shadow-[0_0_10px_rgba(251,191,36,0.2)]" style={{ width: `${h.efficiency}%` }} />
                   </div>
                </div>
             ))}
          </div>
       </div>
    </div>
    <DenseTickerTable tickers={data.tickerTable} pillarId="governor" />
  </div>
);

// --- Main View ---

export default function PeakRegimeView() {
  const [mode, setMode] = useState('US');
  const [windowYears, setWindowYears] = useState(1);
  const [activeTab, setActiveTab] = useState('integrity');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = React.useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch('http://127.0.0.1:8000/api/labs/regimes/peak/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, window_years: windowYears })
      });
      const json = await resp.json();
      setData(json);
    } catch (e) {
      console.error("Fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, [mode, windowYears]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="flex h-full bg-[#030305] text-slate-200 overflow-hidden font-sans border border-white/5 rounded-xl">
      {/* Sidebar - Control Deck */}
      <div className="w-80 border-r border-white/5 bg-[#020408] p-8 flex flex-col gap-10 shrink-0 z-20">
         <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-white/[0.03] border border-white/5 flex items-center justify-center shadow-2xl">
               <Layers size={22} className="text-gray-500" />
            </div>
            <div>
               <h1 className="text-lg font-black tracking-tighter text-white uppercase font-display leading-tight">Sovereign <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-200 to-amber-500">Regimes</span></h1>
            </div>
         </div>

         <div className="space-y-6">
            <div className="flex items-center gap-2 px-1">
              <Globe size={12} className="text-gray-500" />
              <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Market Domain</label>
            </div>
            <div className="grid grid-cols-1 gap-1.5">
               <button 
                  onClick={() => setMode('US')}
                  className={`p-2.5 px-3.5 rounded-md border text-[10px] font-bold flex items-center justify-between transition-all ${mode === 'US' ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' : 'border-white/5 text-slate-500 hover:border-white/10'}`}
               >
                  <div className="flex items-center gap-3">
                    <div className={`w-0.5 h-3 ${mode === 'US' ? 'bg-amber-500' : 'bg-transparent'}`} />
                    <span>US EQUITIES</span>
                  </div>
                  {mode === 'US' && <div className="w-1 h-1 rounded-full bg-amber-500" />}
               </button>
               <button 
                  onClick={() => setMode('INDIA')}
                  className={`p-2.5 px-3.5 rounded-md border text-[10px] font-bold flex items-center justify-between transition-all ${mode === 'INDIA' ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' : 'border-white/5 text-slate-500 hover:border-white/10'}`}
               >
                  <div className="flex items-center gap-3">
                    <div className={`w-0.5 h-3 ${mode === 'INDIA' ? 'bg-amber-500' : 'bg-transparent'}`} />
                    <span>INDIA NSE</span>
                  </div>
                  {mode === 'INDIA' && <div className="w-1 h-1 rounded-full bg-amber-500" />}
               </button>
            </div>
         </div>

         <div className="space-y-6">
            <div className="flex items-center gap-2 px-1">
              <Maximize2 size={12} className="text-gray-500" />
              <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Analysis Window</label>
            </div>
            <div className="flex flex-col gap-1.5">
               {[1, 2, 5].map(y => (
                  <button 
                    key={y} 
                    onClick={() => setWindowYears(y)}
                    className={`flex justify-between items-center p-2.5 px-3.5 rounded-md border transition-all ${windowYears === y ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' : 'border-white/5 text-slate-500 hover:border-white/10'}`}
                  >
                     <span className="text-[10px] font-bold uppercase">{y} Year Window</span>
                     <div className={`w-0.5 h-3 ${windowYears === y ? 'bg-amber-500' : 'bg-transparent'}`} />
                  </button>
               ))}
            </div>
         </div>

         <div className="mt-auto p-6 rounded-2xl bg-white/[0.02] border border-white/[0.05] backdrop-blur-xl">
            <div className="flex items-center gap-3 mb-3 text-amber-500/60">
               <Info size={14} />
               <span className="text-[10px] font-black uppercase tracking-[0.2em]">System Status</span>
            </div>
            <p className="text-[10px] text-gray-600 font-medium uppercase tracking-tight leading-relaxed">
               Regional calibration active. Cross-referencing multi-horizon return distributions for structural stability.
            </p>
         </div>
      </div>

      {/* Main Field */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#030305]">
        {/* Header Ribbon */}
        <div className="h-20 border-b border-white/5 bg-[#08080c]/80 backdrop-blur-3xl px-12 flex items-center justify-between sticky top-0 z-30">
           <div className="flex bg-white/[0.03] rounded-full p-1.5 border border-white/5 backdrop-blur-xl">
              {PILLAR_CONFIG.map(p => (
                 <button
                    key={p.id}
                    onClick={() => setActiveTab(p.id)}
                    className={`flex items-center gap-4 px-6 py-2.5 rounded-full transition-all duration-300 ease-out font-mono ${
                        activeTab === p.id 
                        ? 'bg-amber-500 text-black shadow-[0_0_30px_rgba(245,158,11,0.3)] font-bold' 
                        : 'text-gray-500 hover:text-white hover:bg-white/5'
                    }`}
                 >
                    <span className="text-[10px] uppercase tracking-[0.3em] font-bold">{p.label}</span>
                 </button>
              ))}
           </div>
           
           <div className="flex items-center gap-6">
              <div className="h-8 w-px bg-white/5" />
              <button 
                onClick={fetchData}
                className="p-3 rounded-full bg-white/5 border border-white/5 text-gray-500 hover:text-white hover:bg-white/10 transition-all active:rotate-180 duration-500"
              >
                <RefreshCw size={14} />
              </button>
           </div>
        </div>

        {/* Content Field */}
        <div className="flex-1 overflow-auto p-12 relative custom-scrollbar">
            {loading && (
              <div className="absolute inset-0 z-50 bg-[#030305]/95 backdrop-blur-xl flex flex-col items-center justify-center gap-8 animate-in fade-in duration-300">
                 <div className="relative">
                    <div className="w-24 h-24 rounded-full border-2 border-white/5 border-t-amber-500 animate-spin duration-1000" />
                    <div className="absolute inset-0 flex items-center justify-center">
                       <Layers size={24} className="text-white animate-pulse" />
                    </div>
                 </div>
                 <div className="flex flex-col items-center gap-3">
                    <div className="text-[11px] font-bold text-white uppercase tracking-[0.6em] animate-pulse font-display">Analyzing Market State</div>
                    <div className="text-[10px] font-medium text-gray-600 uppercase tracking-[0.4em]">Calibrating Primitive Models...</div>
                 </div>
              </div>
           )}

           {!data && !loading ? (
              <div className="h-full flex items-center justify-center text-gray-700 font-mono italic uppercase tracking-[0.5em] animate-pulse">Initializing Terminal...</div>
           ) : (
              <div className="max-w-7xl mx-auto pb-24">
                 {data && activeTab === 'integrity' && <IntegrityView data={data.integrity} />}
                 {data && activeTab === 'massFlow' && <MassFlowView data={data.massFlow} />}
                 {data && activeTab === 'reflexivity' && <ReflexivityView data={data.reflexivity} />}
                 {data && activeTab === 'fragility' && <FragilityView data={data.fragility} />}
                 {data && activeTab === 'nonlinearity' && <NonlinearityView data={data.nonlinearity} />}
                 {data && activeTab === 'governor' && <GovernorView data={data.governor} />}
              </div>
           )}
        </div>
      </div>
      
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.1);
        }
      `}</style>
    </div>
  );
}
