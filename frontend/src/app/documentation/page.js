'use client';

import React, { useState, useRef } from 'react';
import { 
    Globe, Zap, Activity, Book, Search, ChevronRight, 
    Copy, Check, Layout, LineChart, Shield, Terminal,
    FileText, Code, Cpu, Layers, MousePointer2, Settings2,
    ArrowUpRight, BarChart3, Binary, List, Info
} from 'lucide-react';

// =============================================================================
// TECHNICAL KNOWLEDGE BASE (Source of Truth)
// =============================================================================

const DOCS = {
    introduction: {
        title: "Introduction",
        icon: Globe,
        description: "The structural lens for modern quantitative execution.",
        sections: [
            {
                id: 'philosophy',
                title: "Our Philosophy",
                content: "Quant360 is not just a dashboard; it is a surgical environment built for the modern quantitative analyst. We prioritize deterministic clarity over black-box heuristics. Every pixel, every tick, and every eigen-weight is exposed to you with zero marketing fluff. We serve as a structural lens, decomposing price action into its constituent frequencies and information flows. Our goal is to provide institutional-grade tools to the decentralized world.",
                highlights: [
                    "Zero lookahead bias",
                    "Deterministic execution",
                    "Open-source methodology",
                    "Vector-first rendering"
                ]
            },
            {
                id: 'connectivity',
                title: "High-Fidelity Connectivity",
                content: "Data integrity is our cornerstone. Our backend synchronizes with professional-grade data lakes, providing 5 years of historical integrity (January 2020 – Current) across global equities and derivatives. We utilize a hybrid ingestion engine that blends REST polling for stability with high-throughput WebSocket streams for real-time tick capture. Every incoming bar is audited for gaps and corrected against secondary providers during the synchronization pulse.",
                stats: [
                    { label: "History", value: "5 Years" },
                    { label: "Stability", value: "99.99%" },
                    { label: "Latency", value: "<15ms" }
                ]
            },
            {
                id: 'architecture',
                title: "System Architecture",
                content: "The system is divided into three primary Layers: The Ingestion Layer (Websockets/FIX), the Computation Kernel (WASM-based math engines), and the Presentation Layer (Canvas API). This separation ensures that even under heavy analytical load (e.g., 50+ concurrent Indicators), the UI remains responsive at 120Hz frames.",
                list: [
                    { item: "Ingestion Layer", desc: "Handles raw binary streams and tick-to-bar aggregation." },
                    { item: "Computation Kernel", desc: "Executes GARCH, PCA, and HMM regressions in high-priority workers." },
                    { item: "Presentation Layer", desc: "Utilizes hardware acceleration for zero-lag vector chart rendering." }
                ]
            }
        ]
    },
    trade: {
        title: "Trade Terminal",
        icon: Zap,
        description: "High-performance execution with real-time risk parity and neural diagnostics.",
        sections: [
            {
                id: 'drawing-engine',
                title: "Institutional Drawing Engine",
                content: "Our drawing engine is built on a vector-first, coordinate-independent architecture. Unlike standard platforms that use pixel coordinates (X, Y), we anchor levels to precise time-price tuples (Epoch, Price). This ensures that levels recalculated on high-frequency timeframe shifts do not suffer from 'geometric drift'.",
                list: [
                    { item: "Trend & Channels (12 Tools)", desc: "Trend Lines, Rays, Info Lines, Extended Lines, Parallel Channels, Disjoint Channels, and Flat Tops/Bottoms for structural mapping." },
                    { item: "Fibonacci & Gann (14 Tools)", desc: "Retracements, Extensions, Fans, Time Zones, Gann Boxes, and Fibonacci Speed Resistance Fans for cyclical/ratio analysis." },
                    { item: "Shapes & Annotation (8 Tools)", desc: "Rectangles, Ellipses, Polygons, Path tools, and Callouts for qualitative desk notes." },
                    { item: "Price Projections (4 Tools)", desc: "Long/Short position tools calculate real-time Reward/Risk ratios, projected account PnL, and Stop-Loss anchoring." }
                ],
                code: `// Vector-First Level Mapping Logic
const calculateDriftFreeLevel = (anchor, currentBar) => {
    // slope = deltaPrice / deltaTime
    const slope = (anchor.price2 - anchor.price1) / (anchor.time2 - anchor.time1);
    // Y = m(X - X0) + Y0
    return anchor.price1 + slope * (currentBar.time - anchor.time1);
};`
            },
            {
                id: 'indicator-math',
                title: "Quantitative Indicator Math",
                content: "The Quant360 core provides 65+ technical indicators computed locally via the high-speed Math Kernel. These are not 'black boxes'—they are recursive filters and adaptive systems designed for signal clarity.",
                list: [
                    { item: "Recursive Averages", desc: "SMA, EMA, WMA, HMA (Hull), LSMA (Least Squares), DEMA, TEMA, and VWMA (Volume Weighted)." },
                    { item: "Volatility Envelopes", desc: "Bollinger Bands (Standard Dev), Keltner Channels (ATR-based), Donchian Channels, and Supertrend (Directional Volatility)." },
                    { item: "Momentum Oscillators", desc: "RSI (Relative Strength), MACD (Convergence/Divergence), Stochastic Momentum, Fisher Transform, and SMI Ergodic." },
                    { item: "Liquidity Benchmarks", desc: "VWAP (Session/Anchored), Volume Profile (VPVR), On-Balance Volume (OBV), and Money Flow Index (MFI)." }
                ],
                formula: "VWAP = Σ (Price * Volume) / Σ Volume",
                code: `// Recursive EMA Implementation
const ema = (price, prevEMA, period) => {
    const alpha = 2 / (period + 1);
    return price * alpha + prevEMA * (1 - alpha);
};`
            },
            {
                id: 'signal-intelligence',
                title: "Signal Intelligence",
                content: "The Command Grid decomposes market action into specific tactical drivers. We don't just give you a 'Buy' or 'Sell'—we give you a dependency tree.",
                list: [
                    { item: "Neural Dependency Map", desc: "Visualizes hierarchical influence. If the index drops 2%, how does that weight into the local AAPL signal?" },
                    { item: "Cause Engine", desc: "Attributing price thrusts. Was the move driven by a Volume Spike, a Gamma Squeeze, or a Structural Break?" },
                    { item: "Impact Matrix", desc: "Predicts signal magnitude. Uses a library of thousands of historical analogs to estimate move duration." }
                ],
                content_extra: "Dependency mapping is critical for systemic risk. A signal with 80% dependency on a volatile index is treated differently than a high-conviction idiosyncratic move."
            },
            {
                id: 'multi-chart-sync',
                title: "Multi-Chart Synchronization",
                content: "Institutional trading requires multi-timeframe correlation. Our sync engine handles cross-chart communication with sub-5ms overhead.",
                list: [
                    { item: "Link Groups", desc: "Group charts by color to sync Symbol, Timeframe, or both simultaneously across quadrants." },
                    { item: "Crosshair Persistence", desc: "Project your crosshair across all visible panes to align signals across timeframes (e.g., 1m vs 1h)." },
                    { item: "Layout Presets", desc: "Save complex grid configurations, including specific drawing sets for each quadrant." }
                ]
            },
            {
                id: 'order-gateway',
                title: "Execution Gateway",
                content: "A professional-level gateway supporting institutional order types and pre-trade risk validation.",
                list: [
                    { item: "Smart Triggers", desc: "Stop-Limit and OCO (One-Cancels-Other) logic handled at the client level for sub-ms reaction." },
                    { item: "Slicing Algos", desc: "TWAP (Time-Weighted) and VWAP (Volume-Weighted) slicing to minimize market impact on large sizes." },
                    { item: "Risk HUD", desc: "Real-time VaR (Value at Risk) and Beta-weighting against the Portfolio context." },
                    { item: "Forensic Journaling", desc: "Automatic recording of the 'Reasoning State'—what indicators and signals were active at the moment of entry." }
                ],
                code: `// Pre-Trade Risk Check (Simplified)
const checkRisk = (order, portfolio) => {
    const totalExposure = portfolio.exposure + order.notionalValue;
    const maxLeverage = 4.0; 
    if (totalExposure > portfolio.equity * maxLeverage) {
        throw new Error("Leverage Limit Exceeded: Regulatory parity breach.");
    }
    return true;
};`
            },
            {
                id: 'replay-logic',
                title: "Intelligent Replay Engine",
                content: "The Replay Engine is a high-fidelity 'Forensic Playback' system. It doesn't just play bars—it simulates the state of every indicator and signal detector as they appeared in the past.",
                list: [
                    { item: "Event Detection", desc: "Identify key moments like RSI Crossovers, Volume Pulses, and Major Structure Breaks." },
                    { item: "Decision Pulse", desc: "The engine auto-pauses at high-probability setups to capture the user's 'Alpha Intent'." },
                    { item: "State Persistence", desc: "Maintains a full local buffer of OHLCV and technical states for instant back/forward jumping." }
                ]
            }
        ]
    },
    labs: {
        title: "Forensic Labs",
        icon: Activity,
        description: "Deep-structure market analysis across volatility, causality, and information manifolds.",
        sections: [
            {
                id: 'research-lab',
                title: "Research Lab (Alpha Workbench)",
                content: "The Research Lab is where raw data is converted into actionable hypotheses. We focus on identifying relationships that exist beneath the surface of price action.",
                list: [
                    { item: "Johansen Cointegration", desc: "Identifies stationary baskets of assets. Crucial for pairs trading and mean-reversion strategies." },
                    { item: "Granger Causality", desc: "Determining whether one time series is useful in forecasting another. Identifies 'Lead-Lag' relationships." },
                    { item: "VAR (Vector Autoregression)", desc: "Captures linear interdependencies among multiple assets, allowing for impulse response analysis." },
                    { item: "Entropy Pulse", desc: "Measures Shannon Entropy in the price stream to detect informational exhaustion." }
                ],
                formula: "Y_t = c + Σ A_i Y_{t-i} + ε_t",
                code: `// Spread Cointegration Check
const isStationary = (series) => {
    const { adf_stat, p_value } = runADFTest(series);
    return p_value < 0.05;
};`
            },
            {
                id: 'factors-dna',
                title: "Factors DNA Hub",
                content: "Returns are decomposed into systematic premiums. We use the Fama-French 5-Factor model as the baseline for assessing equity performance.",
                list: [
                    { item: "Mkt-RF (Market)", desc: "Excess return of the market over the risk-free rate." },
                    { item: "SMB (Small Minus Big)", desc: "Performance of small-cap stocks vs large-cap stocks." },
                    { item: "HML (High Minus Low)", desc: "Performance of value stocks vs growth stocks." },
                    { item: "RMW / CMA", desc: "Profitability (Robust minus Weak) and Investment (Conservative minus Aggressive) premiums." }
                ],
                stats: [
                    { label: "Stability", value: "R² > 0.85" },
                    { label: "Confidence", value: "95% T-Stat" },
                    { label: "Sample", value: "1260 bars" }
                ],
                content_extra: "High Alpha in the presence of low Factor Beta indicates true managerial skill (edge)."
            },
            {
                id: 'vol-intel',
                title: "Volatility Intelligence",
                content: "Volatility is not just standard deviation. We use high-fidelity models like GARCH and Yang-Zhang to capture the true risk distribution.",
                list: [
                    { item: "Yang-Zhang Fitting", desc: "The only estimator that captures overnight gaps AND intraday range drift. The institutional gold standard." },
                    { item: "GARCH(1,1)", desc: "Captures 'Volatility Clustering'—the tendency for high-vol days to follow high-vol days." },
                    { item: "EWMA (RiskMetrics)", desc: "Exponentially Weighted Moving Average, placing more weight on recent price shocks." },
                    { item: "Fracture Map", desc: "Visualizes structural breaks in the variance regime using Change-Point Detection (CPD)." }
                ],
                formula: "σ²_t = ω + αε²_{t-1} + βσ²_{t-1}",
                code: `// Yang-Zhang Weighting constant (k)
const calculateYZVol = (bars, N) => {
    const k = 0.34 / (1.34 + (N + 1) / (N - 1));
    return Math.sqrt(volOpen**2 + k*volClose**2 + (1-k)*volRS**2);
};`
            },
            {
                id: 'regime-dna',
                title: "Regime DNA Lab",
                content: "Market environments are not stationary. We use Hidden Markov Models (HMM) to detect when the 'Ground State' of the market has shifted.",
                list: [
                    { item: "Bayesian States", desc: "Classifying the market into states like 'Calm Upside', 'Stressed Mean Reversion', or 'Crash'." },
                    { item: "Transition Probabilities", desc: "Calculating the % chance that the market stays in its current state." },
                    { item: "Viterbi Path", desc: "Identifying the most likely sequence of hidden states given the observed price series." }
                ],
                code: `// Markov State Transition Pulse
const getNextState = (current, matrix) => {
    const probs = matrix[current];
    return sampleDiscrete(probs); // Returns 0, 1, or 2 based on probability
};`
            },
            {
                id: 'pca-eigen',
                title: "PCA Eigenphysics",
                content: "Systemic risk is often hidden in correlation. PCA decomposes the asset universe into independent components to find the 'Market Factor'.",
                list: [
                    { item: "PC1 Variance Share", desc: "If PC1 explains > 45%, assets are moving in lockstep, signifying high fragility." },
                    { item: "ENB (Effective Number of Bets)", desc: "Entropy-based measure. Low ENB = hidden concentration risk." },
                    { item: "Loading Map", desc: "Determining which assets are the primary drivers of the current systemic move." }
                ],
                formula: "ENB = exp( -Σ p_i log(p_i) )",
                stats: [
                    { label: "Fragility", value: "PC1 > 40%" },
                    { label: "Stability", value: "ENB Rank" },
                    { label: "Diversity", value: "L2 Norm" }
                ]
            },
            {
                id: 'ml-bench',
                title: "ML Bench: Structural DNA",
                content: "Automated neural scoring of market environments. We use clustering and feature importance to detect anomalies in the information flow.",
                list: [
                    { item: "Fragility Score", desc: "A 0-100 metric aggregating regime stress, PCA loading, and entropy spikes." },
                    { item: "Structural DNA Map", desc: "A multidimensional scatter plot visualizing how the current market 'looks' compared to historical analogs." },
                    { item: "Anomalous Load", desc: "Detecting information flows that deviate from the 60-day moving average distribution." }
                ]
            },
            {
                id: 'screener-lab',
                title: "Factor Screener Lab",
                content: "The Factor Screener allows for multi-dimensional filtering across technical, fundamental, and quantitative risk metrics.",
                list: [
                    { item: "Z-Score Ranking", desc: "Ranking symbols based on their statistical distance from the mean for any given metric." },
                    { item: "Percentile Filtering", desc: "Isolating the top 5% of assets by Alpha, Momentum, or Low-Volatility." },
                    { item: "Composite Scoring", desc: "Building custom rankers that blend Volatility, RSI, and Factor Loadings into a single list." }
                ]
            }
        ]
    },
    advanced: {
        title: "Advanced Engineering",
        icon: Terminal,
        description: "Programmatic access, kernel hooks, and low-latency data pipelines.",
        sections: [
            {
                id: 'api-reference',
                title: "Internal API Reference",
                content: "Documentation for the Quant360 data engine. All endpoints are optimized for high-performance consumption and state-hydration.",
                list: [
                    { item: "fetchRegistryStatus()", desc: "Health check for the distributed compute nodes handling Lab calculations." },
                    { item: "runFactors(ticker, window, model)", desc: "Triggers a factor regression task on the backend worker cluster." },
                    { item: "runPCA(tickers)", desc: "Executes a principal component decomposition on a ticker universe." },
                    { item: "getFactorScreen(filterSet)", desc: "Retrieve a ranked list of symbols meeting specific factor criteria." }
                ],
                code: `// Triggering Factor Screening
const screener = await q360.getFactorScreen({
    momentum: { min: 0.8 },
    volatility: { max: 'median' },
    limit: 10
});`
            },
            {
                id: 'kernel-hooks',
                title: "Kernel Hooks & Logic Injection",
                content: "The Quant360 engine allows developers to inject custom logic directly into the execution loop via 'Hooks'.",
                list: [
                    { item: "useDataHook", desc: "Intercept OHLCV bars before they reach the drawing and rendering engine." },
                    { item: "useSignalHook", desc: "Override or augment built-in signals with external intelligence feeds." },
                    { item: "useRiskHook", desc: "A client-side circuit breaker. If unauthorized exposure is detected, it flags the gateway." }
                ],
                code: `// Custom Risk Circuit Breaker Hook
export const useRiskHook = (order, portfolio) => {
    const sectorExposure = portfolio.getSectorExposure(order.symbol);
    if (sectorExposure > 0.30) {
        return { authorized: false, reason: "Sector Cap Reached" };
    }
    return { authorized: true };
};`
            },
            {
                id: 'data-lifecycle',
                title: "Data Lifecycle & Pipe",
                content: "Understanding the path of a single tick through our system.",
                list: [
                    { item: "T-0: Ingestion", desc: "RAW L1/L2 data captured from provider network via WebSocket." },
                    { item: "T+2ms: Normalization", desc: "Ticks quantized and structured into OHLCV bars." },
                    { item: "T+5ms: Computation", desc: "Indicators, signal detectors, and lab regressions are executed." },
                    { item: "T+10ms: Rendering", desc: "Pushed to client context for 120Hz canvas rendering." }
                ]
            }
        ]
    }
};

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

const SidebarItem = ({ active, id, doc, onClick }) => (
    <div className="space-y-1">
        <button
            onClick={() => onClick(id)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-sm group ${
                active === id
                ? 'bg-amber-500/10 text-amber-500 font-medium'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
        >
            <doc.icon size={16} className={active === id ? 'text-amber-500' : 'text-gray-500 group-hover:text-gray-400'} />
            <span className="truncate">{doc.title}</span>
            {active === id && <ChevronRight size={14} className="ml-auto" />}
        </button>
        
        {active === id && (
            <div className="ml-4 pl-4 border-l border-white/5 space-y-1 mt-1 mb-3">
                {doc.sections.map((section) => (
                    <a
                        key={section.id}
                        href={`#${section.id}`}
                        className="block py-1.5 text-[11px] text-gray-500 hover:text-amber-500/80 transition-colors truncate"
                    >
                        {section.title}
                    </a>
                ))}
            </div>
        )}
    </div>
);

const CodeTerminal = ({ code, filename = "kernel_execution.js" }) => {
    const [copied, setCopied] = useState(false);
    
    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="my-6 rounded-xl overflow-hidden border border-white/5 bg-[#010204] shadow-2xl">
            <div className="bg-[#0a0e17] px-4 py-2 border-b border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5 mr-3">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/30" />
                        <div className="w-2.5 h-2.5 rounded-full bg-amber-500/20 border border-amber-500/30" />
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/30" />
                    </div>
                    <span className="text-[10px] font-mono text-gray-500 lowercase tracking-wider">{filename}</span>
                </div>
                <button 
                    onClick={handleCopy}
                    className="flex items-center gap-1.5 text-[10px] font-mono text-gray-500 hover:text-white uppercase transition-all"
                >
                    {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
                    {copied ? 'Copied' : 'Copy'}
                </button>
            </div>
            <pre className="p-6 overflow-x-auto font-mono text-[13px] leading-relaxed text-amber-200/90 whitespace-pre">
                <code>{code}</code>
            </pre>
        </div>
    );
};

const SectionHeading = ({ children, id }) => (
    <h2 id={id} className="text-3xl font-bold text-white mb-6 mt-20 first:mt-0 scroll-mt-24 group">
        <a href={`#${id}`} className="flex items-center gap-3">
            {children}
            <span className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-600 text-lg">#</span>
        </a>
    </h2>
);

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function DocumentationPage() {
    const [activeTab, setActiveTab] = useState('introduction');
    const contentRef = useRef(null);

    const activeDoc = DOCS[activeTab];
    const toc = activeDoc?.sections.map(({ id, title }) => ({ id, title })) ?? [];

    return (
        <div className="flex min-h-screen bg-[#050608] font-sans selection:bg-amber-500/30 selection:text-amber-200">
            {/* Left Sidebar - Navigation */}
            <aside className="w-64 border-r border-white/5 flex flex-col sticky top-0 h-screen bg-[#08090b]">
                <div className="p-6 border-b border-white/5">
                    <div className="flex items-center gap-2 mb-1">
                        <div className="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]" />
                        <span className="text-xs font-black uppercase tracking-[0.2em] text-white">Knowledge Hub</span>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
                    <div>
                        <div className="px-3 mb-4 text-[10px] font-bold text-gray-600 uppercase tracking-widest">Navigation</div>
                        <nav className="space-y-2">
                            {Object.entries(DOCS).map(([id, doc]) => (
                                <SidebarItem 
                                    key={id} 
                                    id={id} 
                                    doc={doc} 
                                    active={activeTab} 
                                    onClick={setActiveTab} 
                                />
                            ))}
                        </nav>
                    </div>

                    <div className="divider-gradient opacity-20" />

                    <div className="px-2">
                         <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/10">
                            <div className="text-[10px] font-bold text-amber-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                                 <Zap size={10} />
                                 System Live
                            </div>
                            <p className="text-[10px] text-gray-500 font-mono">Kernel v4.2.0-stable</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 flex overflow-hidden">
                <div className="flex-1 overflow-y-auto scroll-smooth custom-scrollbar" ref={contentRef}>
                    {/* Header Banner */}
                    <div className="max-w-4xl mx-auto px-12 py-16">
                        <div className="flex items-center gap-3 text-[10px] text-gray-600 mb-8 font-mono uppercase tracking-widest">
                            <Book size={12} />
                            <span>Knowledge Base</span>
                            <ChevronRight size={10} />
                            <span className="text-amber-500/80">{activeTab}</span>
                        </div>

                        <header className="mb-20">
                            <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-amber-500/10 text-amber-500 mb-8 shadow-2xl shadow-amber-500/5">
                                <activeDoc.icon size={40} strokeWidth={1.5} />
                            </div>
                            <h1 className="text-6xl font-bold text-white mb-6 tracking-tight leading-tight">
                                {activeDoc.title}
                            </h1>
                            <p className="text-xl text-gray-400 max-w-2xl leading-relaxed">
                                {activeDoc.description}
                            </p>
                        </header>

                        {/* Sections Rendering */}
                        <div className="space-y-40 pb-40">
                            {activeDoc.sections.map((section) => (
                                <section key={section.id} className="scroll-mt-32 group/section">
                                    <SectionHeading id={section.id}>{section.title}</SectionHeading>
                                    
                                    <div className="text-lg text-gray-300/90 font-light leading-relaxed mb-10">
                                        {section.content}
                                    </div>

                                    {section.highlights && (
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 my-10">
                                            {section.highlights.map((h, i) => (
                                                <div key={i} className="p-4 rounded-xl bg-[#0a0c0f] border border-white/5 flex items-center gap-3 hover:border-amber-500/40 transition-all">
                                                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                                                    <span className="text-xs font-semibold text-gray-300">{h}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {section.stats && (
                                        <div className="grid grid-cols-3 gap-8 my-14 p-10 rounded-3xl border border-white/5 bg-[#08090b] shadow-2xl relative overflow-hidden group">
                                            <div className="absolute top-0 right-0 w-64 h-64 bg-amber-500/5 rounded-full blur-[100px] -mr-32 -mt-32" />
                                            {section.stats.map((stat, i) => (
                                                <div key={i} className="space-y-2 relative z-10">
                                                    <div className="text-[10px] font-mono text-gray-500 uppercase tracking-[0.2em]">{stat.label}</div>
                                                    <div className="text-4xl font-bold text-white tracking-tighter">{stat.value}</div>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {section.list && (
                                        <div className="grid grid-cols-1 gap-5 my-10">
                                            {section.list.map((item, i) => (
                                                <div key={i} className="group p-8 rounded-2xl border border-white/5 bg-[#08090b] hover:border-amber-500/20 transition-all duration-300 hover:translate-x-1">
                                                    <div className="text-lg font-bold text-white mb-3 tracking-wide flex items-center gap-4">
                                                        <div className="w-2 h-2 rounded-full bg-amber-500/30 group-hover:bg-amber-500 transition-colors" />
                                                        {item.item}
                                                    </div>
                                                    <div className="text-gray-400 font-light leading-relaxed pl-6">
                                                        {item.desc}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {section.formula && (
                                        <div className="p-16 rounded-3xl bg-[#08090b] border border-white/5 flex flex-col items-center justify-center text-center my-14 relative group overflow-hidden">
                                            <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-amber-500/30 to-transparent" />
                                            <div className="text-[10px] font-bold text-gray-600 uppercase tracking-[0.4em] mb-10">Kernel Computational Core</div>
                                            <div className="text-3xl font-serif text-white italic tracking-[0.15em] leading-relaxed max-w-2xl">
                                                {section.formula}
                                            </div>
                                            <div className="mt-10 px-4 py-1.5 rounded-full border border-white/5 text-[9px] font-mono text-gray-500 uppercase tracking-widest bg-white/5">
                                                Deterministic Logic Engine
                                            </div>
                                        </div>
                                    )}

                                    {section.code && (
                                        <CodeTerminal code={section.code} />
                                    )}

                                    {section.content_extra && (
                                        <div className="mt-12 p-10 rounded-2xl border-l-4 border-amber-500/50 bg-[#0a0c0f] text-gray-300 italic flex gap-8 items-start shadow-xl">
                                            <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0">
                                                <Info size={24} className="text-amber-500" />
                                            </div>
                                            <span className="leading-loose text-lg font-light">{section.content_extra}</span>
                                        </div>
                                    )}
                                </section>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right Sidebar - TOC */}
                <aside className="w-72 sticky top-0 h-screen p-10 border-l border-white/5 bg-[#050608] hidden xl:block overflow-y-auto custom-scrollbar">
                    <div className="mb-12">
                        <div className="text-[10px] font-bold text-gray-600 uppercase tracking-[0.3em] mb-8 px-1">Structural Map</div>
                        <nav className="space-y-2">
                            {toc.map((item) => (
                                <a 
                                    key={item.id}
                                    href={`#${item.id}`}
                                    className="block text-[11px] text-gray-500 hover:text-amber-500 transition-all leading-normal py-2.5 px-4 rounded-xl hover:bg-white/5 border-l-2 border-transparent hover:border-amber-500/50"
                                >
                                    {item.title}
                                </a>
                            ))}
                        </nav>
                    </div>

                    <div className="divider-gradient opacity-10 my-12" />

                    <div className="p-6 rounded-2xl bg-amber-500/[0.03] border border-amber-500/10 group">
                        <div className="text-[10px] font-bold text-amber-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                             <Shield size={12} />
                             Security Protocol
                        </div>
                        <p className="text-[11px] text-gray-400 leading-relaxed font-light group-hover:text-gray-200 transition-colors">
                            All quantitative models are processed in <span className="text-white font-medium">isolated kernels</span>. Local data encryption ensures your Alpha remains sovereign.
                        </p>
                    </div>

                    <div className="mt-20 pt-20 flex flex-col items-center">
                        <div className="w-12 h-[1px] bg-white/10 mb-8" />
                        <div className="text-[10px] font-mono text-gray-600 uppercase tracking-[0.5em] text-center">
                            Quant360
                        </div>
                    </div>
                </aside>
            </main>
        </div>
    );
}
