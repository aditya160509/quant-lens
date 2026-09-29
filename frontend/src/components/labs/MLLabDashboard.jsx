import React, { useState, useEffect, useCallback, useMemo } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { 
    Activity, Layers, RefreshCw, AlertTriangle, 
    ArrowUpRight, ArrowDownRight, Zap, Target,
    Cpu, Shield, Globe, TrendingUp, Info, 
    ChevronRight, Maximize2, Terminal as TerminalIcon,
    BarChart3, PieChart, FlaskConical, Binary, 
    Gauge, Network, Radio, Box
} from 'lucide-react';
import { PlotlyChart } from '@/components/ui/plotly-chart';
import TerminalPanel from '@/components/TerminalPanel';
import { 
    fetchMLStructural, 
    fetchMLAlpha, 
    fetchMLRegime, 
    fetchMLStress,
    fetchMLPeak,
    fetchMLMacro
} from '@/lib/api';
import UniverseModal from './UniverseModal';
import Sequential3DLoadingMap from './Sequential3DLoadingMap';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';

// ML v2 Components
import RegimeWaves2D from './v2/RegimeWaves2D';
import AnomalyGravity2D from './v2/AnomalyGravity2D';
import MonteCarlo2D from './v2/MonteCarlo2D';
import LiquidityCanyons2D from './v2/LiquidityCanyons2D';
import Valuation2D from './v2/Valuation2D';

const UNIVERSES = [
    { id: "india_nse", label: "NIFTY NSE", region: "IN", color: "text-orange-400" },
    { id: "us_equities", label: "US EQUITIES", region: "US", color: "text-blue-400" },
    { id: "etfs", label: "GLOBAL ETFs", region: "GLOBAL", color: "text-purple-400" },
    { id: "indices", label: "WORLD INDICES", region: "GLOBAL", color: "text-emerald-400" }
];

const TIMEFRAMES = [
    { id: "1m", label: "1M" },
    { id: "3m", label: "3M" },
    { id: "6m", label: "6M" },
    { id: "1y", label: "1Y" },
    { id: "2y", label: "2Y" },
    { id: "3y", label: "3Y" },
    { id: "4y", label: "4Y" },
    { id: "max", label: "MAX" }
];

const THEME = {
    yellow: "#ffcc00",
    blue: "#00d4ff",
    green: "#00ff88",
    red: "#ff3333",
    purple: "#bf5af2",
    gray: "rgba(255, 255, 255, 0.1)",
    darker: "#050505",
    cardBg: "rgba(10, 10, 10, 0.8)",
};

export default function MLLabDashboard() {
    const [universe, setUniverse] = useState("india_nse");
    const [timeframe, setTimeframe] = useState("1D");
    const [universeModalOpen, setUniverseModalOpen] = useState(false);
    const [activeSubTab, setActiveSubTab] = useState("structural");
    const [ticker, setTicker] = useState("AAPL");
    const [loading, setLoading] = useState(false);
    const [macroLoading, setMacroLoading] = useState(false);
    const [data, setData] = useState(null);
    const [macroData, setMacroData] = useState([]);
    const [error, setError] = useState(null);
    const [logs, setLogs] = useState([
        "SYSTEM INITIALIZED: QUANT-360 ML ENGINE",
        "AWAITING MARKET INPUT..."
    ]);

    const addLog = (msg) => {
        setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 10));
    };

    const fetchData = useCallback(async (isInitial = false) => {
        if (!universe) return;
        
        // ML v1 tabs only
        const v1Tabs = ["structural", "alpha", "regime", "stress", "peak"];
        if (!v1Tabs.includes(activeSubTab)) {
            setLoading(false);
            setError(null);
            return;
        }

        if (!isInitial) {
            setData(null);
            setLoading(true);
        } else {
            setLoading(true);
        }
        
        const controller = new AbortController();
        const signal = controller.signal;

        try {
            setError(null);
            const univLabel = Array.isArray(universe) ? `CUSTOM_VECTOR_SET` : universe;
            addLog(`Initializing ${activeSubTab} probe [${univLabel} | ${timeframe}]...`);
            
            let result;
            const options = { timeframe, signal };
            
            if (activeSubTab === "structural") result = await fetchMLStructural(universe, 252, options);
            else if (activeSubTab === "alpha") result = await fetchMLAlpha(universe, 60, options);
            else if (activeSubTab === "regime") result = await fetchMLRegime(universe, options);
            else if (activeSubTab === "stress") result = await fetchMLStress(universe, -0.03, options);
            else if (activeSubTab === "peak") result = await fetchMLPeak(universe, options);

            if (signal.aborted) return;
            
            if (result && !result.error) {
                setData(result);
                addLog(`SVD link established. Rank: ${result.explained_variance?.length || 'N/A'}`);
            } else {
                setError(result?.error || "Fetch failed");
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(err.message);
                addLog(`CRITICAL: ${err.message}`);
            }
        } finally {
            if (!signal.aborted) setLoading(false);
        }

        return () => controller.abort();
    }, [universe, timeframe, activeSubTab]);

    useEffect(() => {
        const fetchMacros = async () => {
            setMacroLoading(true);
            try {
                const res = await fetchMLMacro();
                if (res && res.length) setMacroData(res);
            } catch (err) {
                console.error("Macro Pulse Failure", err);
            } finally {
                setMacroLoading(false);
            }
        };
        fetchMacros();
        
        const v1Tabs = ["structural", "alpha", "regime", "stress", "peak"];
        if (v1Tabs.includes(activeSubTab)) {
            fetchData(false);
        } else {
            setLoading(false);
            setError(null);
        }
    }, [universe, timeframe, activeSubTab, fetchData]);

    const activeUnivLabel = useMemo(() => {
        if (Array.isArray(universe)) return `${universe.length} ASSETS`;
        const found = UNIVERSES.find(u => u.id === universe);
        return found ? found.label : (universe?.toUpperCase() || "SELECT UNIVERSE");
    }, [universe]);

    return (
        <div className="flex flex-col h-full gap-4 text-terminal-text font-mono bg-[#020202] p-2">
            {/* UNIVERSE MODAL */}
            <UniverseModal 
                isOpen={universeModalOpen} 
                onClose={() => setUniverseModalOpen(false)} 
                onSelect={(u) => {
                    // u can be a list of tickers or an object with an id (if we changed modal later)
                    // Currently UniverseModal.jsx:54 calls onSelect(localTickers) where localTickers is string[]
                    setUniverse(u);
                    setUniverseModalOpen(false);
                }}
            />

            {/* AGGRESSIVE TOP NAVIGATION BAR */}
            <div className="flex items-center justify-between bg-terminal-darker border-y border-terminal-gray/30 px-4 py-2 backdrop-blur-md sticky top-0 z-50">
                <div className="flex items-center gap-6">
                    <div className="flex flex-col">
                        <span className="text-[10px] font-black text-terminal-dim uppercase tracking-[0.2em]">Compute Domain</span>
                        <span className="text-sm font-bold text-terminal-blue tracking-wide">ML ANALYTICS ENGINE v4.0</span>
                    </div>
                    <div className="h-8 w-[1px] bg-terminal-gray/20" />
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${loading ? 'bg-terminal-yellow animate-pulse' : 'bg-terminal-green'} shadow-[0_0_8px_currentColor]`} />
                        <span className="text-[11px] font-black text-terminal-white tracking-widest uppercase">
                            {loading ? 'CALCULATING HYPER-SPACE' : 'SYSTEM READY'}
                        </span>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    {/* Timeframe Selector */}
                    <div className="flex bg-black border border-terminal-gray/30 p-1 rounded-lg">
                        {TIMEFRAMES.map(tf => (
                            <button
                                key={tf.id}
                                onClick={() => setTimeframe(tf.id)}
                                className={`px-3 py-1 text-[10px] font-black rounded-md transition-all ${
                                    timeframe === tf.id 
                                    ? 'bg-terminal-blue text-black' 
                                    : 'text-terminal-dim hover:text-terminal-white'
                                }`}
                            >
                                {tf.label}
                            </button>
                        ))}
                    </div>

                    {/* Target Selector (Context Aware) */}
                    <div className="flex flex-col min-w-[200px]">
                        <span className="text-[10px] font-black text-terminal-dim uppercase tracking-[0.2em]">Target Context</span>
                        {!["structural", "alpha", "regime", "stress", "peak"].includes(activeSubTab) ? (
                            <TradingViewSearch 
                                onSelect={(s) => setTicker(s)}
                                value={ticker}
                                placeholder="SEARCH TICKER"
                            />
                        ) : (
                            <div className="bg-black/40 border border-terminal-gray/20 text-terminal-dim px-3 py-1 text-xs rounded font-bold uppercase h-8 flex items-center">
                                {Array.isArray(universe) ? "CUSTOM LIST" : universe?.replace('_', ' ')}
                            </div>
                        )}
                    </div>

                    <div className="h-8 w-[1px] bg-terminal-gray/20" />

                    {/* Universe Selector Button */}
                    <button 
                        onClick={() => setUniverseModalOpen(true)}
                        className="flex items-center gap-3 bg-[#0a0a0a] border border-terminal-gray/40 text-terminal-yellow px-4 py-2 text-sm rounded-lg hover:border-terminal-yellow/50 transition-all outline-none"
                    >
                        <Globe size={14} className="text-terminal-blue" />
                        <span className="font-bold tracking-tight">{activeUnivLabel}</span>
                        <ChevronRight className="rotate-90 text-terminal-dim" size={14} />
                    </button>

                    <button 
                        onClick={() => fetchData()}
                        disabled={loading}
                        className={`group relative flex items-center gap-2 px-6 py-2 bg-transparent border border-terminal-yellow/50 text-terminal-yellow font-bold text-xs rounded-lg transition-all hover:bg-terminal-yellow hover:text-black overflow-hidden ${loading ? 'cursor-not-allowed opacity-50' : ''}`}
                    >
                        <div className="absolute inset-0 bg-terminal-yellow/10 translate-x-[-100%] group-hover:translate-x-0 transition-transform duration-500" />
                        {loading ? <RefreshCw className="animate-spin" size={14} /> : <Zap size={14} />}
                        <span className="relative z-10">{loading ? "COMPUTING..." : "RE-CALCULATE EIGEN"}</span>
                    </button>
                    
                    <button className="p-2 border border-terminal-gray/30 rounded-lg text-terminal-dim hover:text-terminal-white hover:border-terminal-white transition-all">
                        <Maximize2 size={18} />
                    </button>
                </div>
            </div>

            {/* MAIN CONTENT AREA WITH STACKED GRID LAYOUT */}
            <Tabs.Root value={activeSubTab} onValueChange={setActiveSubTab} className="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
                {/* VERTICAL SIDEBAR FOR SUB-TABS */}
                <Tabs.List className="flex lg:flex-col gap-1 p-1 bg-[#050505] border border-terminal-gray/20 rounded-lg lg:w-[140px] shrink-0 overflow-x-auto lg:overflow-y-auto hide-scrollbar">
                    <SideTabTrigger value="structural" icon={Layers} label="Structural" active={activeSubTab === "structural"} />
                    <SideTabTrigger value="alpha" icon={Zap} label="Alpha" active={activeSubTab === "alpha"} />
                    <SideTabTrigger value="regime" icon={RefreshCw} label="Regime" active={activeSubTab === "regime"} />
                    <SideTabTrigger value="stress" icon={AlertTriangle} label="Stress" active={activeSubTab === "stress"} />
                    <SideTabTrigger value="peak" icon={Target} label="Signal" active={activeSubTab === "peak"} />
                    
                    <div className="my-2 border-t border-terminal-gray/20" />
                    <div className="px-2 py-1 text-[8px] text-terminal-dim uppercase font-bold tracking-widest">ML v2.0 Deep Dive</div>
                    
                    <SideTabTrigger value="valuation" icon={Gauge} label="Intrinsic" active={activeSubTab === "valuation"} />
                    <SideTabTrigger value="monte-carlo" icon={Binary} label="Monte Carlo" active={activeSubTab === "monte-carlo"} />
                    <SideTabTrigger value="liquidity" icon={Box} label="Liquidity" active={activeSubTab === "liquidity"} />
                    <SideTabTrigger value="anomalies" icon={Shield} label="Anomalies" active={activeSubTab === "anomalies"} />
                    <SideTabTrigger value="regime2" icon={Radio} label="Regime v2" active={activeSubTab === "regime2"} />
                </Tabs.List>

                {/* DYNAMIC VIEWPORT */}
                <div className="flex-1 flex flex-col gap-4 relative min-h-0 overflow-hidden">
                    <div className="flex-1 overflow-y-auto px-1 hide-scrollbar">
                        {loading && (
                            <div className="absolute inset-0 z-40 bg-black/60 flex items-center justify-center backdrop-blur-md">
                                <div className="flex flex-col items-center gap-6">
                                    <div className="relative">
                                        <div className="w-24 h-24 border-2 border-terminal-yellow/20 rounded-full animate-ping" />
                                        <div className="absolute inset-0 flex items-center justify-center">
                                            <Binary size={48} className="text-terminal-yellow animate-pulse" />
                                        </div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-xl font-bold text-terminal-yellow mb-2 tracking-widest uppercase">CONSTRUCTING EIGEN-SPACE</div>
                                        <div className="text-[10px] text-terminal-dim animate-pulse">OPTIMIZING CROSS-CORRELATIONS...</div>
                                    </div>
                                </div>
                            </div>
                        )}
                        
                        {error && (
                            <div className="p-10 flex flex-col items-center justify-center bg-red-900/10 border border-red-500/30 rounded-lg text-red-500 m-4">
                                <AlertTriangle size={64} className="mb-4" />
                                <h3 className="text-2xl font-bold mb-2 uppercase tracking-tighter">Connection Interrupted</h3>
                                <p className="font-mono text-sm max-w-md text-center text-red-400/80 mb-6">{error}</p>
                                <button onClick={fetchData} className="px-8 py-2 border border-red-500 rounded hover:bg-red-500 hover:text-black transition-all font-bold">RE-ESTABLISH HANDSHAKE</button>
                            </div>
                        )}

                        {!loading && !error && (
                            <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-700 h-full">
                                <Tabs.Content value="structural" className="outline-none h-full">
                                    {data && !data.error && (
                                        <EnhancedStructuralDNAView 
                                            data={data} 
                                            loading={loading} 
                                            macroLoading={macroLoading} 
                                            macroData={macroData} 
                                        />
                                    )}
                                    {data?.error && <InsufficientDensityView label={activeUnivLabel} fetchData={fetchData} />}
                                </Tabs.Content>
                                <Tabs.Content value="alpha" className="outline-none h-full">
                                    {data && !data.error ? <EnhancedAlphaRibbonView data={data} /> : <InsufficientDensityView label={activeUnivLabel} fetchData={fetchData} />}
                                </Tabs.Content>
                                <Tabs.Content value="regime" className="outline-none h-full">
                                    {data && !data.error ? <EnhancedRegimeHubView data={data} loading={loading} /> : <InsufficientDensityView label={activeUnivLabel} fetchData={fetchData} />}
                                </Tabs.Content>
                                <Tabs.Content value="stress" className="outline-none h-full">
                                    {data && !data.error ? <EnhancedStressMatrixView data={data} /> : <InsufficientDensityView label={activeUnivLabel} fetchData={fetchData} />}
                                </Tabs.Content>
                                <Tabs.Content value="peak" className="outline-none h-full">
                                    {data && !data.error ? <EnhancedPeakMLView data={data} loading={loading} /> : <InsufficientDensityView label={activeUnivLabel} fetchData={fetchData} />}
                                </Tabs.Content>
                                
                                {/* ML v2.0 Content - Independent of v1 data state */}
                                <Tabs.Content value="valuation" className="outline-none h-full">
                                    <Valuation2D universe={universe} ticker={ticker} timeframe={timeframe} />
                                </Tabs.Content>
                                <Tabs.Content value="monte-carlo" className="outline-none h-full">
                                    <MonteCarlo2D universe={universe} ticker={ticker} timeframe={timeframe} />
                                </Tabs.Content>
                                <Tabs.Content value="liquidity" className="outline-none h-full">
                                    <LiquidityCanyons2D universe={universe} ticker={ticker} timeframe={timeframe} />
                                </Tabs.Content>
                                <Tabs.Content value="anomalies" className="outline-none h-full">
                                    <AnomalyGravity2D universe={universe} ticker={ticker} timeframe={timeframe} />
                                </Tabs.Content>
                                <Tabs.Content value="regime2" className="outline-none h-full">
                                    <RegimeWaves2D universe={universe} ticker={ticker} timeframe={timeframe} />
                                </Tabs.Content>
                            </div>
                        )}
                    </div>
                </div>
            </Tabs.Root>

            {/* GLOBAL STATUS BAR */}
            <div className="bg-[#050505] border-t border-terminal-gray/20 p-2 flex items-center justify-between text-[10px] uppercase font-bold">
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-terminal-green shadow-[0_0_8px_#00ff88]" />
                        <span className="text-terminal-white">LATENCY: 42ms</span>
                    </div>
                    <div className="text-terminal-dim">NODES: 1,420</div>
                    <div className="text-terminal-dim">EIGEN-RESIDUAL: 0.00041</div>
                </div>
                <div className="flex items-center gap-4 text-terminal-dim">
                    <div className="flex items-center gap-1">
                        <Globe size={10} />
                        <span>QUASAR_X86_64</span>
                    </div>
                    <span>UTC: {new Date().toISOString()}</span>
                </div>
            </div>
        </div>
    );
}

function SideTabTrigger({ value, icon: Icon, label, active }) {
    return (
        <Tabs.Trigger 
            value={value}
            className={`
                group flex items-center gap-3 px-4 py-3 rounded transition-all duration-300
                ${active 
                    ? 'bg-terminal-yellow text-black' 
                    : 'text-terminal-dim hover:bg-terminal-white/5 hover:text-terminal-white'}
            `}
        >
            <Icon size={18} className={active ? 'text-black' : 'group-hover:text-terminal-yellow'} />
            <div className="flex flex-col items-start">
                <span className="text-[11px] font-bold uppercase tracking-widest">{label}</span>
                {!active && <span className="text-[7px] font-mono text-terminal-yellow/40">READY_FOR_DEPLOY</span>}
            </div>
            {active && <ChevronRight size={14} className="ml-auto" />}
        </Tabs.Trigger>
    );
}

// --- ENHANCED SUB-VIEWS ---

function EnhancedStructuralDNAView({ data, loading, macroLoading, macroData }) {
    if (!data) return (
        <div className="h-[600px] bg-black/40 border border-terminal-gray/10 rounded-3xl flex items-center justify-center animate-pulse">
            <span className="text-terminal-dim font-mono uppercase tracking-[0.3em]">Mapping Component Manifold...</span>
        </div>
    );

    return (
        <div className="grid grid-cols-12 gap-6 pb-12">
            {/* LARGE HERO PLOT */}
            <div className="col-span-12 flex flex-col gap-6">
                <TerminalPanel 
                    title="EIGEN-LOADING HYPER-SPACE: 3D STRUCTURAL CLUSTERING" 
                    icon={Binary}
                    extra={(
                        <div className="flex items-center gap-4 text-[10px] text-terminal-dim">
                             <span className="animate-pulse flex items-center gap-1"><div className="w-1 h-1 rounded-full bg-terminal-yellow"/> REAL-TIME_SYNTHESIS_ACTIVE</span>
                        </div>
                    )}
                >
                    <div className="h-[600px] relative bg-[#050505] rounded-b-2xl overflow-hidden shadow-2xl">
                         <Sequential3DLoadingMap mode="structural" data={data} loading={loading} />
                    </div>
                </TerminalPanel>

                <div className="grid grid-cols-3 gap-6">
                    <TerminalPanel title="SECTOR BREADTH RADAR" icon={PieChart}>
                        <div className="h-[300px]">
                            <SectorRadarChart matrixData={data.matrix_data || []} />
                        </div>
                    </TerminalPanel>

                    <TerminalPanel title="FACTOR DECAY (SCREE PLOT)" icon={Layers}>
                        <div className="h-[300px]">
                            <ScreePlot data={data.explained_variance || []} />
                        </div>
                    </TerminalPanel>

                    <TerminalPanel title="TOP DECOUPLERS" icon={Target}>
                        <div className="p-4 space-y-3 h-[300px] overflow-y-auto custom-scrollbar">
                            {(data.idiosyncratic_alpha || []).slice(0, 8).map((d, i) => (
                                <div key={d.ticker} className="group flex items-center gap-4 p-2 bg-terminal-white/5 border border-transparent hover:border-terminal-green/30 rounded-lg transition-all">
                                    <div className="w-6 h-6 flex items-center justify-center bg-terminal-black rounded font-bold text-[10px] text-terminal-dim group-hover:text-terminal-green transition-colors">
                                        {i+1}
                                    </div>
                                    <div className="flex-1 flex flex-col">
                                        <div className="flex justify-between items-center">
                                            <span className="text-xs font-bold text-terminal-white tracking-widest">{d.ticker}</span>
                                            <span className="text-[10px] font-mono text-terminal-green">{(d.residual_var * 100).toFixed(1)}%</span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </TerminalPanel>
                </div>
            </div>


        </div>
    );
}

function EnhancedAlphaRibbonView({ data }) {
    return (
        <div className="flex flex-col gap-4 pb-10">
            {/* TOP SUMMARY BAR */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <DenseMetricCard 
                    label="Aggregate Market Velocity" 
                    value={`${(data.market_velocity * 100).toFixed(3)}%`} 
                    sub="Avg 20D Flux"
                    color="text-terminal-blue"
                    icon={Activity}
                />
                <DenseMetricCard 
                    label="Neural Acceleration" 
                    value={(data.market_acceleration * 1000).toFixed(2)} 
                    sub="Convexity Index"
                    color="text-terminal-yellow"
                    icon={Zap}
                />
                 <DenseMetricCard 
                    label="Signal Confidence" 
                    value={`${(npMean((data.ribbon_data || []).map(r => r.confidence)) * 100).toFixed(1)}%`} 
                    sub="Composite Strength"
                    color="text-terminal-green"
                    icon={Shield}
                />
                 <DenseMetricCard 
                    label="Liquidity Absorption" 
                    value="ACTIVE" 
                    sub="Network Status"
                    color="text-terminal-purple"
                    icon={Radio}
                />
            </div>

            {/* MAIN DENSE TABULAR INTERFACE */}
            <div className="bg-terminal-darker border border-terminal-gray/20 rounded-xl overflow-hidden">
                <div className="p-4 bg-terminal-dark border-b border-terminal-gray/10 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <TerminalIcon size={16} className="text-terminal-yellow" />
                        <span className="text-sm font-bold uppercase tracking-widest text-terminal-white">Alpha Flux Matrix</span>
                    </div>
                    <div className="flex items-center gap-4">
                         <div className="flex items-center gap-2 text-[10px] text-terminal-dim">
                            <span className="px-2 py-0.5 bg-terminal-green/10 text-terminal-green border border-terminal-green/30 rounded">BULLISH</span>
                            <span className="px-2 py-0.5 bg-red-500/10 text-red-500 border border-red-500/30 rounded">BEARISH</span>
                         </div>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] uppercase text-terminal-dim bg-terminal-black/40 border-b border-terminal-gray/10">
                                <th className="p-4 font-bold tracking-wider">Asset Identifier</th>
                                <th className="p-4 font-bold tracking-wider text-right">Information Ratio</th>
                                <th className="p-4 font-bold tracking-wider text-right">Momentum Sc.</th>
                                <th className="p-4 font-bold tracking-wider text-right">Acceleration</th>
                                <th className="p-4 font-bold tracking-wider text-right">Vol Shock</th>
                                <th className="p-4 font-bold tracking-wider text-center">Prediction confidence</th>
                                <th className="p-4 font-bold tracking-wider">Market Profile</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-terminal-gray/5">
                            {(data.ribbon_data || []).map((d) => (
                                <tr key={d.ticker} className="hover:bg-terminal-white/[0.03] transition-colors group border-l-2 border-transparent hover:border-terminal-yellow">
                                    <td className="p-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-2 h-2 rounded-full bg-terminal-yellow/30 animate-pulse" />
                                            <span className="text-sm font-black text-terminal-white tracking-widest">{d.ticker}</span>
                                        </div>
                                    </td>
                                    <td className="p-4 text-right">
                                        <div className="flex flex-col items-end">
                                            <span className={`text-sm font-mono font-bold ${d.information_ratio > 1 ? 'text-terminal-green' : d.information_ratio < -1 ? 'text-red-500' : 'text-terminal-white'}`}>
                                                {d.information_ratio.toFixed(3)}
                                            </span>
                                            <span className="text-[8px] text-terminal-dim uppercase font-bold">ANNUALIZED</span>
                                        </div>
                                    </td>
                                    <td className="p-4 text-right">
                                        <span className="text-sm font-mono text-terminal-blue">+{ (d.momentum_score * 100).toFixed(1) }%</span>
                                    </td>
                                    <td className="p-4 text-right">
                                        <div className="flex items-center justify-end gap-2">
                                            <span className={`text-xs ${d.acceleration > 0 ? 'text-terminal-green' : 'text-red-400'}`}>
                                                {d.acceleration > 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                                            </span>
                                            <span className="text-sm font-mono">{(d.acceleration * 1000).toFixed(2)}</span>
                                        </div>
                                    </td>
                                    <td className="p-4 text-right">
                                        <div className={`text-xs inline-block px-2 py-0.5 rounded font-bold ${d.vol_shock > 0.03 ? 'bg-red-500/20 text-red-500 border border-red-500/30' : 'bg-terminal-gray/20 text-terminal-dim'}`}>
                                            {(d.vol_shock * 100).toFixed(1)}%
                                        </div>
                                    </td>
                                    <td className="p-4">
                                        <div className="flex flex-col items-center gap-1">
                                            <div className="flex items-center gap-1">
                                                {[...Array(5)].map((_, i) => (
                                                    <div 
                                                        key={i} 
                                                        className={`w-4 h-1 rounded-sm ${i < Math.round(d.confidence * 5) ? 'bg-terminal-yellow shadow-[0_0_5px_rgba(255,204,0,0.5)]' : 'bg-terminal-black'}`} 
                                                    />
                                                ))}
                                            </div>
                                            <span className="text-[8px] text-terminal-dim font-bold">{(d.confidence * 100).toFixed(0)}% PROBABILITY</span>
                                        </div>
                                    </td>
                                    <td className="p-4">
                                        <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-[9px] font-bold uppercase tracking-tighter transition-all ${
                                            d.acceleration > 0 
                                            ? 'bg-terminal-green text-black group-hover:shadow-[0_0_15px_rgba(0,255,136,0.3)]' 
                                            : 'bg-terminal-dark border border-terminal-gray/20 text-terminal-dim'
                                        }`}>
                                            {d.acceleration > 0 ? <Zap size={10} fill="currentColor" /> : <Activity size={10} />}
                                            {d.acceleration > 0 ? "Gamma-Accelerating" : "Structural Decay"}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

// --- ENHANCED REGIME HUB (Option 1/2/3 Hybrid) ---
function EnhancedRegimeHubView({ data, loading }) {
    if (!data) return (
        <div className="h-[600px] bg-black/40 border border-terminal-gray/10 rounded-3xl flex items-center justify-center animate-pulse">
            <span className="text-terminal-dim font-mono uppercase tracking-[0.3em]">Materializing Helix Phase-Space...</span>
        </div>
    );

    return (
        <div className="flex flex-col gap-6">
            {/* HERO SECTION: THE HELIX PHASE-SPACE */}
            <div className="h-[500px] w-full bg-black/60 border border-terminal-gray/20 rounded-3xl relative overflow-hidden group shadow-2xl">
                <Sequential3DLoadingMap mode="regime_helix" data={data} loading={loading} />
                <div className="absolute top-6 right-6 text-right">
                    <span className="text-[10px] text-terminal-dim uppercase font-bold tracking-widest block mb-1">Current State</span>
                    <div className={`px-4 py-1.5 rounded-md text-xs font-black uppercase tracking-widest border border-white/10 backdrop-blur-md ${
                        data.status === "Stable" ? "bg-terminal-green/20 text-terminal-green" : "bg-red-500/20 text-red-500"
                    }`}>
                        {data.status} REGIME
                    </div>
                </div>
            </div>

            {/* MIDDLE HUD: PRECISION TELEMETRY */}
            <div className="grid grid-cols-4 gap-4">
                <DenseMetricCard 
                    label="FRAGILITY IDX" 
                    value={`${((data.hhi || 0) * 100).toFixed(1)}%`} 
                    sub="Absorption Ratio" 
                    color="text-terminal-blue" 
                    icon={Target} 
                />
                <DenseMetricCard 
                    label="ENTROPY STATE" 
                    value={(data.entropy || 0.5).toFixed(3)} 
                    sub="Systemic Decay" 
                    color="text-terminal-green" 
                    icon={Layers} 
                />
                <DenseMetricCard 
                    label="DISPERSION PULSE" 
                    value={(data.vol_picker_index || 0).toFixed(2)} 
                    sub="Stock Picker Index" 
                    color="text-terminal-yellow" 
                    icon={Activity} 
                />
                <DenseMetricCard 
                    label="NETWORK LINKS" 
                    value={(data.clusters || []).length} 
                    sub="Active Clusters" 
                    color="text-terminal-purple" 
                    icon={Box} 
                />
            </div>

            <div className="grid grid-cols-12 gap-6">
                <div className="col-span-12 flex flex-col gap-6">
                    <TerminalPanel title="CORRELATION CLUSTERING (2D TOPOLOGY)" icon={Network}>
                        <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 h-[400px] overflow-y-auto custom-scrollbar">
                           {(data.clusters || []).length > 0 ? (data.clusters || []).map(c => (
                                <div key={c.anchor} className="bg-white/[0.03] p-4 rounded-xl border border-terminal-gray/10 hover:border-terminal-blue/30 transition-all">
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="text-sm font-bold text-terminal-blue tracking-widest">{c.anchor}</span>
                                        <span className="text-[8px] bg-terminal-blue/20 text-terminal-blue px-2 py-0.5 rounded font-black">ANCHOR_NODE</span>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {c.links.map(link => (
                                            <span key={link} className="px-3 py-1 bg-terminal-black border border-terminal-gray/20 text-[10px] text-terminal-dim font-mono rounded-md hover:text-terminal-white hover:border-terminal-blue/50 transition-colors cursor-default">
                                                {link}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )) : (
                                <div className="col-span-full h-full flex items-center justify-center text-terminal-dim text-xs uppercase tracking-[0.2em]">No significant clusters detected in current timeframe</div>
                            )}
                        </div>
                    </TerminalPanel>
                </div>
            </div>
        </div>
    );
}

function EnhancedStressMatrixView({ data }) {
    if (!data || data.error) return null;

    return (
        <div className="flex flex-col gap-6 pb-12">
            {/* SHOCK HEADER */}
            <div className="bg-gradient-to-r from-red-950/40 via-black to-black border border-red-500/20 rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between shadow-2xl overflow-hidden relative">
                <div className="absolute left-0 top-0 w-1 h-full bg-red-500 animate-pulse" />
                <div className="flex items-center gap-6 relative z-10">
                    <div className="w-20 h-20 rounded-2xl bg-red-500/10 flex items-center justify-center border border-red-500/30">
                        <AlertTriangle size={48} className="text-red-500" />
                    </div>
                    <div>
                        <h2 className="text-4xl font-black text-terminal-white tracking-tighter mb-1 uppercase">SYSTEMIC VaR SIMULATION</h2>
                        <div className="flex items-center gap-4">
                            <span className="text-xs font-bold text-red-500 tracking-[0.3em] uppercase">Status: CRITICAL_PATH_MONITOR</span>
                            <div className="h-4 w-[1px] bg-terminal-gray/30" />
                            <span className="text-xs font-mono text-terminal-dim">SHOCK MAGNITUDE: <span className="text-terminal-yellow">{(data.shock_pct * 100).toFixed(0)}%</span></span>
                        </div>
                    </div>
                </div>

                <div className="mt-8 md:mt-0 flex flex-col items-center md:items-end gap-2 relative z-10">
                    <span className="text-[10px] text-terminal-dim uppercase font-black tracking-widest">Expected Combined Fallout</span>
                    <div className="flex items-baseline gap-2">
                        <span className="text-6xl font-black text-red-500">{(data.systemic_var * 100).toFixed(2)}</span>
                        <span className="text-2xl font-bold text-red-500/50">%</span>
                    </div>
                </div>
                
                {/* DECORATIVE HEX GRID CAN BE SIMULATED WITH CSS */}
                <div className="absolute right-[-40px] top-[-40px] opacity-[0.03] pointer-events-none">
                    <Binary size={300} />
                </div>
            </div>

            {/* STRESS CONTAGION MATRIX */}
            <TerminalPanel title="STRESS REACTION & LIQUIDITY VACUUM ANALYSIS" icon={Shield}>
                <div className="p-0 overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="text-[10px] uppercase text-terminal-dim bg-terminal-black/60 border-b border-terminal-gray/20">
                                    <th className="p-5 font-black">Asset Identifier</th>
                                    <th className="p-5 font-black text-right">Beta Sensitivity</th>
                                    <th className="p-5 font-black text-right">Liquidity Drain Index</th>
                                    <th className="p-5 font-black text-right">Structural Fallout</th>
                                    <th className="p-5 font-black text-center">Contagion Role</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-terminal-gray/10">
                                {(data.simulation_data || []).map((d) => (
                                    <tr key={d.ticker} className="hover:bg-red-500/[0.02] transition-colors group">
                                        <td className="p-5">
                                            <div className="flex flex-col">
                                                <span className="text-sm font-black text-terminal-white tracking-widest uppercase">{d.ticker}</span>
                                                <span className="text-[8px] text-terminal-dim font-bold uppercase">SENSITIVITY HUB: {d.ticker.split('.')[0]}</span>
                                            </div>
                                        </td>
                                        <td className="p-5 text-right font-mono text-sm text-terminal-yellow font-bold">
                                            {d.beta.toFixed(3)}
                                        </td>
                                        <td className="p-5 text-right">
                                            <div className="flex flex-col items-end gap-1">
                                                <div className="flex items-center gap-2">
                                                     <span className={`text-xs font-bold ${d.vacuum_risk > 40 ? 'text-orange-500' : 'text-terminal-dim'}`}>
                                                        {d.vacuum_risk.toFixed(2)}
                                                    </span>
                                                    <div className="w-24 h-2 bg-terminal-black rounded-full overflow-hidden border border-terminal-gray/10">
                                                        <div 
                                                            className={`h-full transition-all duration-1000 ${d.vacuum_risk > 40 ? 'bg-orange-500' : 'bg-terminal-blue'}`} 
                                                            style={{ width: `${Math.min(100, d.vacuum_risk * 1.5)}%` }} 
                                                        />
                                                    </div>
                                                </div>
                                                <span className="text-[8px] text-terminal-dim uppercase font-bold">AMIHUD RATIO CROSS</span>
                                            </div>
                                        </td>
                                        <td className="p-5 text-right">
                                            <div className="flex flex-col items-end">
                                                <span className="text-lg font-black text-red-500 tracking-tighter">
                                                     -{(d.expected_fallout * 100).toFixed(2)}%
                                                </span>
                                                <span className="text-[8px] text-red-500/50 uppercase font-black">SIMULATED MAX DRAWDOWN</span>
                                            </div>
                                        </td>
                                        <td className="p-5">
                                            <div className="flex justify-center">
                                                <div className={`
                                                    px-4 py-1 rounded-sm text-[10px] font-black uppercase tracking-wider border
                                                    ${d.tail_rank === 'First to Fall' ? 'bg-red-500 text-black border-red-500 animate-pulse' : 
                                                      d.tail_rank === 'Buffer' ? 'bg-terminal-green/20 text-terminal-green border-terminal-green/40' :
                                                      'bg-terminal-dark border-terminal-gray/30 text-terminal-dim'}
                                                `}>
                                                    {d.tail_rank}
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </TerminalPanel>
        </div>
    );
}

// --- ENHANCED PEAK ML VIEW (Terrain + Pillars) ---
function EnhancedPeakMLView({ data, loading }) {
    if (!data) return (
        <div className="h-[600px] bg-black/40 border border-terminal-gray/10 rounded-3xl flex items-center justify-center animate-pulse">
            <span className="text-terminal-dim font-mono uppercase tracking-[0.3em]">Synthesizing Alpha Terrain...</span>
        </div>
    );

    return (
        <div className="flex flex-col gap-6">
             {/* HERO SECTION: THE ALPHA TERRAIN */}
             <div className="h-[500px] w-full bg-[#050505] border border-terminal-gray/20 rounded-3xl relative overflow-hidden shadow-2xl">
                <Sequential3DLoadingMap mode="signal_terrain" data={data} loading={loading} />
            </div>

            {/* ALPHA INTELLIGENCE RIBBON */}
            <TerminalPanel title="ALPHA ORACLE: SYSTEMATIC PREDICATED RANKINGS" icon={Target}>
                <div className="p-2 overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="border-b border-terminal-gray/10 text-[10px] text-terminal-dim font-black uppercase tracking-widest">
                                <th className="p-4">Rank</th>
                                <th className="p-4">Ticker</th>
                                <th className="p-4">AI Score</th>
                                <th className="p-4">Confidence</th>
                                <th className="p-4">Lead/Lag Role</th>
                                <th className="p-4">Momentum Vector</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(data.alpha_oracle || []).slice(0, 20).map((item, idx) => (
                                <tr key={item.ticker} className="border-b border-terminal-gray/5 hover:bg-white/[0.02] transition-all group">
                                    <td className="p-4 font-mono text-terminal-dim text-xs">#{idx + 1}</td>
                                    <td className="p-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-1.5 h-1.5 rounded-full bg-terminal-yellow shadow-[0_0_5px_#ffcc00]" />
                                            <span className="text-sm font-black text-terminal-white tracking-wider">{item.ticker}</span>
                                        </div>
                                    </td>
                                    <td className="p-4">
                                        <div className="flex flex-col">
                                            <span className={`text-sm font-bold ${item.ai_score > 5 ? 'text-terminal-green' : 'text-terminal-yellow'}`}>
                                                {item.ai_score.toFixed(2)}
                                            </span>
                                            <div className="w-20 h-1 bg-terminal-gray/10 rounded-full mt-1 overflow-hidden">
                                                <div className="h-full bg-terminal-green" style={{ width: `${Math.min(100, item.ai_score * 10)}%` }} />
                                            </div>
                                        </div>
                                    </td>
                                    <td className="p-4">
                                        <span className="text-xs font-mono text-terminal-blue">{(item.confidence * 100).toFixed(1)}%</span>
                                    </td>
                                    <td className="p-4">
                                        <span className="text-[10px] font-black uppercase tracking-widest text-white/40">{(data.lead_lag_leaders?.find(l => l.ticker === item.ticker)?.role) || "Observer"}</span>
                                    </td>
                                    <td className="p-4">
                                        <div className="flex items-center gap-2">
                                            {item.ai_score > 0 ? <ArrowUpRight size={14} className="text-terminal-green" /> : <ArrowDownRight size={14} className="text-terminal-red" />}
                                            <span className="text-xs font-mono text-terminal-dim">STRUCTURAL_ALPHA</span>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </TerminalPanel>
        </div>
    );
}

// --- UTILITIES ---

function DenseMetricCard({ label, value, sub, color, icon: Icon }) {
    return (
        <div className="bg-[#0c0c0c] border border-terminal-gray/20 rounded-2xl p-5 group hover:border-terminal-white/20 transition-all overflow-hidden relative">
            <div className="absolute top-2 right-2 text-terminal-dim/20 group-hover:text-terminal-white/10 transition-colors">
                <Icon size={24} />
            </div>
            <span className="text-[10px] text-terminal-dim font-black uppercase tracking-[0.2em] block mb-2">{label}</span>
            <div className={`text-3xl font-black tracking-tighter ${color} mb-1`}>{value}</div>
            <div className="text-[10px] font-mono text-terminal-dim uppercase flex items-center gap-1">
                <ChevronRight size={10} className="text-terminal-yellow" /> {sub}
            </div>
        </div>
    );
}

function HighContrastInsight({ title, status, value, desc }) {
    return (
        <div className="bg-white/[0.03] border border-terminal-gray/10 p-5 rounded-2xl group hover:bg-white/[0.05] transition-all">
            <div className="flex justify-between items-start mb-4">
                <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-terminal-dim">{title}</span>
                    <div className="flex items-center gap-2">
                         <div className={`w-2 h-2 rounded-full ${status === 'OPTIMAL' || status === 'HIGH' ? 'bg-terminal-green animate-pulse' : 'bg-red-500 shadow-[0_0_8px_#ff3333]'}`} />
                         <span className={`text-[10px] font-black tracking-widest ${status === 'OPTIMAL' || status === 'HIGH' ? 'text-terminal-green' : 'text-red-500'}`}>{status}</span>
                    </div>
                </div>
                <div className="text-4xl font-black text-terminal-white tracking-tighter">{value}</div>
            </div>
            <p className="text-[11px] text-terminal-dim leading-relaxed font-light">{desc}</p>
        </div>
    );
}

function npMean(arr) {
    if (!arr || arr.length === 0) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
}

const SECTOR_MAP = {
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "BPCL.NS": "Energy", "IOC.NS": "Energy", "NTPC.NS": "Energy", "POWERGRID.NS": "Energy", "GAIL.NS": "Energy", "ADANIPOWER.NS": "Energy", "JSWENERGY.NS": "Energy", "TATAPOWER.NS": "Energy",
    "TCS.NS": "Tech", "INFY.NS": "Tech", "HCLTECH.NS": "Tech", "WIPRO.NS": "Tech", "TECHM.NS": "Tech", "LTIM.NS": "Tech", "COFORGE.NS": "Tech", "MPHASIS.NS": "Tech", "PERSISTENT.NS": "Tech", "KPITTECH.NS": "Tech",
    "HDFCBANK.NS": "Finance", "ICICIBANK.NS": "Finance", "AXISBANK.NS": "Finance", "KOTAKBANK.NS": "Finance", "SBIN.NS": "Finance", "BAJFINANCE.NS": "Finance", "BAJAJFINSV.NS": "Finance", "CHOLAFIN.NS": "Finance", "MUTHOOTFIN.NS": "Finance", "CANBK.NS": "Finance", "BANKBARODA.NS": "Finance",
    "HINDUNILVR.NS": "Consumer", "ITC.NS": "Consumer", "NESTLEIND.NS": "Consumer", "BRITANNIA.NS": "Consumer", "DABUR.NS": "Consumer", "MARICO.NS": "Consumer", "TATACONSUM.NS": "Consumer", "VBL.NS": "Consumer", "COLPAL.NS": "Consumer", "GODREJCP.NS": "Consumer",
    "SUNPHARMA.NS": "Pharma", "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma", "LUPIN.NS": "Pharma", "AUROPHARMA.NS": "Pharma", "ALKEM.NS": "Pharma", "TORNTPHARM.NS": "Pharma", "GLENMARK.NS": "Pharma", "BIOCON.NS": "Pharma",
    "MARUTI.NS": "Auto", "TATAMOTORS.NS": "Auto", "M&M.NS": "Auto", "HEROMOTOCO.NS": "Auto", "EICHERMOT.NS": "Auto", "TVSMOTOR.NS": "Auto", "ASHOKLEY.NS": "Auto", "BHARATFORG.NS": "Auto", "BALKRISIND.NS": "Auto", "MRF.NS": "Auto",
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "META": "Tech", "NVDA": "Tech", "AMD": "Tech", "ORCL": "Tech", "ADBE": "Tech", "CRM": "Tech", "CSCO": "Tech",
    "JPM": "Finance", "BAC": "Finance", "WFC": "Finance", "GS": "Finance", "MS": "Finance", "C": "Finance", "BLK": "Finance", "AXP": "Finance",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "EOG": "Energy", "OXY": "Energy", "MPC": "Energy", "PSX": "Energy",
    "AMZN": "Consumer", "TSLA": "Consumer", "HD": "Consumer", "WMT": "Consumer", "COST": "Consumer", "PG": "Consumer", "KO": "Consumer", "PEP": "Consumer"
};

function SectorRadarChart({ matrixData }) {
    const sectorStats = useMemo(() => {
        const stats = {};
        if (!matrixData || matrixData.length === 0) return [];
        
        matrixData.forEach(d => {
            const sector = SECTOR_MAP[d.ticker] || "Misc";
            if (!stats[sector]) stats[sector] = { totalLoading: 0, count: 0, pc2Alpha: 0 };
            stats[sector].totalLoading += d.loading_strength || 0;
            stats[sector].pc2Alpha += Math.abs(d.pc2 || 0); // Use PC2 as a proxy for alpha/decoupling
            stats[sector].count += 1;
        });

        return Object.entries(stats).map(([name, data]) => ({
            name,
            loading: data.totalLoading / data.count,
            alpha: data.pc2Alpha / data.count
        })).sort((a, b) => b.loading - a.loading);
    }, [matrixData]);

    if (sectorStats.length === 0) {
        return <div className="h-full flex items-center justify-center text-terminal-dim text-[10px]">INSUFFICIENT DATASET</div>;
    }

    const categories = sectorStats.map(s => s.name);
    // Add first category to end to close the radar loop
    const displayCategories = [...categories, categories[0]];
    const loadingValues = [...sectorStats.map(s => s.loading), sectorStats[0].loading];
    const alphaValues = [...sectorStats.map(s => s.alpha), sectorStats[0].alpha];

    return (
        <PlotlyChart 
            data={[
                {
                    type: 'scatterpolar',
                    r: loadingValues,
                    theta: displayCategories,
                    fill: 'toself',
                    name: 'Structural Link',
                    line: { color: THEME.blue, width: 2 },
                    fillcolor: 'rgba(0, 212, 255, 0.15)'
                },
                {
                    type: 'scatterpolar',
                    r: alphaValues.map(v => v * 3), // Magnify for visibility
                    theta: displayCategories,
                    fill: 'toself',
                    name: 'Alpha Intensity',
                    line: { color: THEME.yellow, width: 2 },
                    fillcolor: 'rgba(255, 204, 0, 0.15)'
                }
            ]}
            layout={{
                polar: {
                    bgcolor: 'transparent',
                    radialaxis: {
                        visible: false,
                        range: [0, Math.max(...loadingValues, ...alphaValues.map(v => v * 3)) * 1.1],
                        gridcolor: 'rgba(255,255,255,0.05)',
                    },
                    angularaxis: {
                        gridcolor: 'rgba(255,255,255,0.05)',
                        tickfont: { size: 9, color: '#888', family: 'monospace' },
                        ticklen: 10
                    }
                },
                showlegend: false,
                margin: { t: 30, r: 60, b: 30, l: 60 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                autosize: true
            }}
        />
    );
}

function ScreePlot({ data }) {
    return (
        <PlotlyChart 
            data={[
                {
                    x: (data || []).map((_, i) => `PC${i+1}`),
                    y: (data || []).map(v => v * 100),
                    type: 'bar',
                    name: 'Individual Variance',
                    marker: {
                        color: (data || []).map((_, i) => i < 5 ? THEME.yellow : 'rgba(100, 100, 100, 0.3)'),
                        line: { color: THEME.yellow, width: 1 }
                    }
                },
                {
                    x: (data || []).map((_, i) => `PC${i+1}`),
                    y: (data || []).reduce((acc, v, i) => {
                        const sum = (acc[i-1] || 0) + (v * 100);
                        acc.push(sum);
                        return acc;
                    }, []),
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'Cumulative Variance',
                    line: { color: THEME.blue, width: 2, shape: 'spline' },
                    marker: { color: THEME.blue, size: 6 }
                }
            ]}
            layout={{
                xaxis: { 
                    gridcolor: '#1a1a1a', 
                    tickfont: { size: 9, color: '#666' },
                    fixedrange: true
                },
                yaxis: { 
                    title: '% Explained Variance',
                    titlefont: { size: 9, color: '#666' },
                    gridcolor: '#1a1a1a', 
                    tickfont: { size: 9, color: '#666' },
                    range: [0, 105],
                    fixedrange: true
                },
                showlegend: false,
                margin: { t: 20, r: 20, b: 40, l: 40 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                barmode: 'overlay',
                hovermode: 'x unified'
            }}
        />
    );
}

function MacroPulse({ label, value, change, history = [] }) {
    const isUp = change > 0;
    return (
        <div className="flex items-center justify-between bg-terminal-black/40 border border-terminal-gray/10 p-2 rounded">
            <div className="flex flex-col">
                <span className="text-[8px] text-terminal-dim font-bold uppercase tracking-widest">{label}</span>
                <span className="text-sm font-black text-terminal-white font-mono">{value}</span>
            </div>
            <div className="flex items-center gap-2">
                <div className="w-16 h-4 bg-terminal-black/50 rounded overflow-hidden">
                    <div className="flex items-end h-full gap-0.5 px-1">
                        {history.length > 0 ? history.map((h, i) => (
                            <div 
                                key={i} 
                                className={`flex-1 ${h > 0 ? 'bg-terminal-yellow/30' : 'bg-terminal-blue/30'}`} 
                                style={{ height: `${Math.min(100, 20 + Math.abs(h) * 10)}%` }} 
                            />
                        )) : [...Array(8)].map((_, i) => (
                            <div key={i} className="flex-1 bg-white/5 h-[20%]" />
                        ))}
                    </div>
                </div>
                <span className={`text-[10px] font-bold ${isUp ? 'text-terminal-yellow' : 'text-terminal-blue'}`}>
                    {isUp ? '▲' : '▼'} {Math.abs(change).toFixed(2)}%
                </span>
            </div>
        </div>
    );
}

function EigenMomentum({ matrixData, absorptionRatio }) {
    const pc1Avg = useMemo(() => {
        if (!matrixData.length) return 0;
        return matrixData.reduce((acc, d) => acc + Math.abs(d.pc1), 0) / matrixData.length;
    }, [matrixData]);

    const pc2Avg = useMemo(() => {
        if (!matrixData.length) return 0;
        return matrixData.reduce((acc, d) => acc + Math.abs(d.pc2), 0) / matrixData.length;
    }, [matrixData]);

    const ratio = (pc1Avg / (pc1Avg + pc2Avg)) * 100;

    return (
        <div className="flex flex-col gap-2">
            <div className="flex justify-between text-[9px] font-bold text-terminal-dim uppercase mb-1">
                <span>Beta Dominion</span>
                <span>Alpha Dispersion</span>
            </div>
            <div className="h-4 bg-terminal-black/50 border border-terminal-gray/10 rounded-full relative overflow-hidden">
                <div 
                    className="absolute top-0 left-0 h-full bg-gradient-to-r from-terminal-blue to-terminal-yellow transition-all duration-1000"
                    style={{ width: `${ratio}%` }}
                />
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-[1px] h-full bg-white/20" />
                </div>
            </div>
            <div className="mt-4 flex items-center justify-between">
                <div>
                    <div className="text-[7px] text-terminal-dim uppercase font-bold">Structural Concentration</div>
                    <div className="text-lg font-black text-terminal-white">{(absorptionRatio * 10).toFixed(2)}<span className="text-[10px] ml-1">σ</span></div>
                </div>
                <div className="text-right">
                    <div className="text-[7px] text-terminal-dim uppercase font-bold">Market Phase</div>
                    <div className={`text-[10px] font-bold px-2 py-0.5 rounded ${ratio > 60 ? 'bg-terminal-blue/20 text-terminal-blue' : 'bg-terminal-yellow/20 text-terminal-yellow'}`}>
                        {ratio > 60 ? 'MACRO-DRIVEN' : 'ROTATIONAL_FLUX'}
                    </div>
                </div>
            </div>
        </div>
    );
}

function InsufficientDensityView({ label, fetchData }) {
    return (
        <div className="h-full min-h-[500px] flex flex-col items-center justify-center p-20 text-center">
            <Shield size={80} className="text-terminal-red mb-6 animate-pulse" />
            <h2 className="text-4xl font-bold text-terminal-white mb-4 tracking-tighter">INSUFFICIENT SIGNAL DENSITY</h2>
            <p className="text-terminal-dim max-w-lg mb-8 text-lg font-light leading-relaxed">
                The current universe ({label}) does not meet the minimum convergence threshold for reliable ML inference.
            </p>
            <div className="flex gap-4">
                 <button onClick={() => window.location.reload()} className="px-6 py-3 bg-terminal-yellow text-black font-bold uppercase text-xs rounded hover:scale-105 transition-all">RELOAD SYSTEM</button>
                 <button onClick={() => fetchData()} className="px-6 py-3 border border-terminal-yellow text-terminal-yellow font-bold uppercase text-xs rounded hover:bg-terminal-yellow/10 transition-all">FORCE COMPUTE</button>
            </div>
        </div>
    );
}
