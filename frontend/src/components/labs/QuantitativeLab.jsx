'use client';

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { 
    Waves, 
    Activity, 
    Grid, 
    Layers, 
    Zap, 
    RefreshCw, 
    Play, 
    Radar,
    Eye,
    GitBranch,
    Skull,
    TrendingUp,
    AlertTriangle
} from 'lucide-react';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';

// Dynamic Plotly import for 3D surfaces
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const API_BASE = '';

const MODULES = [
    { id: 'sde', label: 'SDE Paths', icon: Waves },
    { id: 'kalman', label: 'State-Space', icon: Activity },
    { id: 'cointegration', label: 'Arbitrage', icon: Grid },
    { id: 'spectral', label: 'Spectral', icon: Layers },
];

// ============================================================================
// CANVAS-BASED FAST CHARTS
// ============================================================================
const CanvasLineChart = ({ data, lines, height = 200, showGrid = true, title }) => {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !data || data.length === 0) return;

        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();

        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        // Background
        ctx.fillStyle = '#0a0e14';
        ctx.fillRect(0, 0, rect.width, rect.height);

        const padding = { left: 50, right: 20, top: 30, bottom: 25 };
        const chartWidth = rect.width - padding.left - padding.right;
        const chartHeight = rect.height - padding.top - padding.bottom;

        // Get all values for scaling
        let allValues = [];
        lines.forEach(line => {
            data.forEach(d => {
                if (d[line.key] !== undefined && !isNaN(d[line.key])) {
                    allValues.push(d[line.key]);
                }
            });
        });

        if (allValues.length === 0) return;

        const minV = Math.min(...allValues);
        const maxV = Math.max(...allValues);
        const range = maxV - minV || 1;

        const scaleX = (i) => padding.left + (i / (data.length - 1)) * chartWidth;
        const scaleY = (v) => padding.top + chartHeight - ((v - minV) / range) * chartHeight;

        // Grid
        if (showGrid) {
            ctx.strokeStyle = 'rgba(255,255,255,0.05)';
            ctx.lineWidth = 0.5;
            for (let i = 0; i <= 4; i++) {
                const y = padding.top + (chartHeight / 4) * i;
                ctx.beginPath();
                ctx.moveTo(padding.left, y);
                ctx.lineTo(rect.width - padding.right, y);
                ctx.stroke();

                // Y-axis labels
                const val = maxV - (range / 4) * i;
                ctx.fillStyle = '#5a6578';
                ctx.font = '9px monospace';
                ctx.textAlign = 'right';
                ctx.fillText(val.toFixed(val > 1000 ? 0 : 2), padding.left - 5, y + 3);
            }
        }

        // Title
        if (title) {
            ctx.fillStyle = '#f59e0b';
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'left';
            ctx.fillText(title.toUpperCase(), padding.left, 15);
        }

        // Draw lines
        lines.forEach(line => {
            ctx.beginPath();
            ctx.strokeStyle = line.color || '#00ff88';
            ctx.lineWidth = line.width || 1.5;
            
            let started = false;
            data.forEach((d, i) => {
                const val = d[line.key];
                if (val !== undefined && !isNaN(val)) {
                    const x = scaleX(i);
                    const y = scaleY(val);
                    if (!started) {
                        ctx.moveTo(x, y);
                        started = true;
                    } else {
                        ctx.lineTo(x, y);
                    }
                }
            });
            ctx.stroke();
        });

    }, [data, lines, showGrid, title]);

    return (
        <canvas 
            ref={canvasRef} 
            style={{ width: '100%', height: `${height}px`, display: 'block' }} 
        />
    );
};

const CanvasAreaChart = ({ data, areas, height = 200, title }) => {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !data || data.length === 0) return;

        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();

        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        ctx.fillStyle = '#0a0e14';
        ctx.fillRect(0, 0, rect.width, rect.height);

        const padding = { left: 50, right: 20, top: 30, bottom: 25 };
        const chartWidth = rect.width - padding.left - padding.right;
        const chartHeight = rect.height - padding.top - padding.bottom;

        let allValues = [];
        areas.forEach(area => {
            data.forEach(d => {
                if (d[area.key] !== undefined && !isNaN(d[area.key])) {
                    allValues.push(d[area.key]);
                }
            });
        });

        if (allValues.length === 0) return;

        const minV = Math.min(...allValues);
        const maxV = Math.max(...allValues);
        const range = maxV - minV || 1;

        const scaleX = (i) => padding.left + (i / (data.length - 1)) * chartWidth;
        const scaleY = (v) => padding.top + chartHeight - ((v - minV) / range) * chartHeight;

        // Grid
        ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
            const y = padding.top + (chartHeight / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(rect.width - padding.right, y);
            ctx.stroke();
        }

        // Title
        if (title) {
            ctx.fillStyle = '#f59e0b';
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'left';
            ctx.fillText(title.toUpperCase(), padding.left, 15);
        }

        // Draw areas (in reverse order for proper layering)
        [...areas].reverse().forEach(area => {
            const gradient = ctx.createLinearGradient(0, padding.top, 0, rect.height - padding.bottom);
            gradient.addColorStop(0, area.color + '40');
            gradient.addColorStop(1, area.color + '00');

            ctx.beginPath();
            ctx.moveTo(scaleX(0), rect.height - padding.bottom);
            
            data.forEach((d, i) => {
                const val = d[area.key];
                if (val !== undefined && !isNaN(val)) {
                    ctx.lineTo(scaleX(i), scaleY(val));
                }
            });
            
            ctx.lineTo(scaleX(data.length - 1), rect.height - padding.bottom);
            ctx.closePath();
            ctx.fillStyle = gradient;
            ctx.fill();

            // Stroke line
            ctx.beginPath();
            ctx.strokeStyle = area.color;
            ctx.lineWidth = 1.5;
            let started = false;
            data.forEach((d, i) => {
                const val = d[area.key];
                if (val !== undefined && !isNaN(val)) {
                    if (!started) {
                        ctx.moveTo(scaleX(i), scaleY(val));
                        started = true;
                    } else {
                        ctx.lineTo(scaleX(i), scaleY(val));
                    }
                }
            });
            ctx.stroke();
        });

    }, [data, areas, title]);

    return (
        <canvas 
            ref={canvasRef} 
            style={{ width: '100%', height: `${height}px`, display: 'block' }} 
        />
    );
};

// ============================================================================
// UTILITY COMPONENTS
// ============================================================================
const ParamSlider = ({ label, value, onChange, min, max, step = 1 }) => (
    <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
            <label className="text-[9px] text-terminal-dim uppercase font-bold tracking-tight">{label}</label>
            <span className="text-[10px] font-mono text-terminal-yellow">
                {typeof value === 'number' ? value.toFixed(step < 1 ? 3 : 0) : value}
            </span>
        </div>
        <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-terminal-gray/30 rounded-lg appearance-none cursor-pointer accent-terminal-yellow"
        />
    </div>
);

const StatCard = ({ label, value, unit = '', color = 'terminal-text', subtext }) => (
    <div className="bg-terminal-black/50 border border-terminal-gray/20 p-2 rounded">
        <div className="text-[8px] text-terminal-dim uppercase font-bold tracking-tight">{label}</div>
        <div className={`text-sm font-mono font-bold text-${color}`}>
            {value !== undefined && value !== null ? (
                typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : value
            ) : '--'}{unit}
        </div>
        {subtext && <div className="text-[7px] text-terminal-dim/70 mt-0.5">{subtext}</div>}
    </div>
);

const SignalBadge = ({ signal }) => {
    const colors = {
        'LONG': 'bg-terminal-green/20 text-terminal-green border-terminal-green/40',
        'SHORT': 'bg-terminal-red/20 text-terminal-red border-terminal-red/40',
        'NEUTRAL': 'bg-terminal-yellow/20 text-terminal-yellow border-terminal-yellow/40',
    };
    return (
        <div className={`px-2 py-1 rounded text-[10px] font-mono font-bold border ${colors[signal] || colors.NEUTRAL}`}>
            {signal || 'NEUTRAL'}
        </div>
    );
};

// ============================================================================
// MODULE 1: SDE PATH LABORATORY (with 3D Surface)
// ============================================================================
const SDEPathLab = () => {
    const [ticker, setTicker] = useState('AAPL');
    const [model, setModel] = useState('heston');
    const [horizon, setHorizon] = useState(63);
    const [nPaths, setNPaths] = useState(500);
    const [lookback, setLookback] = useState(252);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/quantitative/sde/paths`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker, model, horizon, n_paths: nPaths, lookback })
            });
            if (!res.ok) throw new Error(await res.text());
            const result = await res.json();
            setData(result.data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [ticker, model, horizon, nPaths, lookback]);

    // Build 3D surface from sample paths
    const surface3D = useMemo(() => {
        if (!data?.paths_sample) return null;
        const paths = data.paths_sample.slice(0, 30);
        return paths;
    }, [data]);

    // Cone chart data
    const coneData = useMemo(() => {
        if (!data?.time_axis) return [];
        return data.time_axis.map((t, i) => ({
            t: i,
            p5: data.cones?.p5?.[i],
            p50: data.cones?.p50?.[i],
            p95: data.cones?.p95?.[i],
        }));
    }, [data]);

    return (
        <div className="grid grid-cols-12 gap-3 h-full">
            {/* Parameters */}
            <div className="col-span-2 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase tracking-wider flex items-center gap-2">
                    <Waves size={14} /> SDE Simulation
                </div>
                
                <div className="mb-3">
                    <label className="text-[9px] text-terminal-dim block mb-1 uppercase">TICKER</label>
                    <TradingViewSearch mode="security" onSelect={setTicker} placeholder={ticker} />
                </div>

                <div className="mb-3">
                    <label className="text-[9px] text-terminal-dim block mb-1 uppercase">MODEL</label>
                    <select
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        className="w-full bg-terminal-black border border-terminal-gray/50 text-terminal-text text-[10px] p-2 rounded"
                    >
                        <option value="gbm">GBM</option>
                        <option value="heston">Heston</option>
                        <option value="jump">Jump-Diffusion</option>
                    </select>
                </div>

                <ParamSlider label="Horizon (Days)" value={horizon} onChange={setHorizon} min={21} max={252} />
                <ParamSlider label="Paths" value={nPaths} onChange={setNPaths} min={100} max={2000} step={100} />

                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="w-full bg-terminal-yellow text-terminal-black py-2 font-mono text-[10px] font-bold rounded mt-3 hover:bg-yellow-400 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {loading ? <RefreshCw size={12} className="animate-spin" /> : <Zap size={12} />}
                    {loading ? 'SIMULATING...' : 'RUN SIMULATION'}
                </button>

                {data?.likelihood_of_ruin && (
                    <div className="mt-4 pt-3 border-t border-terminal-gray/20">
                        <div className="text-[9px] text-terminal-red font-bold mb-2 uppercase flex items-center gap-1">
                            <Skull size={10} /> Ruin Probabilities
                        </div>
                        <div className="space-y-1 text-[9px]">
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">10% Drop:</span>
                                <span className="text-terminal-red">{data.likelihood_of_ruin.ruin_prob_10pct?.toFixed(1)}%</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">25% Drop:</span>
                                <span className="text-terminal-red">{data.likelihood_of_ruin.ruin_prob_25pct?.toFixed(1)}%</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* 3D Surface */}
            <div className="col-span-7 bg-terminal-darker border border-terminal-gray/30 rounded overflow-hidden">
                <div className="px-3 pt-2 border-b border-terminal-gray/20">
                    <div className="text-xs font-bold text-terminal-yellow uppercase">Monte Carlo Surface</div>
                    <div className="text-[8px] text-terminal-dim">{model.toUpperCase()} • {nPaths} Paths</div>
                </div>
                <div className="h-[380px]">
                    {error && <div className="p-4 text-terminal-red text-xs">{error}</div>}
                    {surface3D ? (
                        <Plot
                            data={[{
                                z: surface3D,
                                type: 'surface',
                                colorscale: 'Viridis',
                                showscale: false,
                                contours: { z: { show: true, usecolormap: true, highlightcolor: "#42f462", project: { z: true } } }
                            }]}
                            layout={{
                                autosize: true,
                                paper_bgcolor: 'transparent',
                                plot_bgcolor: 'transparent',
                                margin: { l: 0, r: 0, b: 0, t: 0 },
                                scene: {
                                    bgcolor: 'transparent',
                                    xaxis: { title: 'Time', gridcolor: '#1e2738', showbackground: false },
                                    yaxis: { title: 'Path', gridcolor: '#1e2738', showbackground: false },
                                    zaxis: { title: 'Price', gridcolor: '#1e2738', showbackground: false },
                                    camera: { eye: { x: 1.8, y: 1.2, z: 0.8 } }
                                }
                            }}
                            style={{ width: '100%', height: '100%' }}
                            useResizeHandler={true}
                            config={{ displayModeBar: false }}
                        />
                    ) : (
                        <div className="h-full flex items-center justify-center text-terminal-dim text-xs">
                            Run simulation for 3D surface
                        </div>
                    )}
                </div>
            </div>

            {/* Stats */}
            <div className="col-span-3 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase">Terminal Distribution</div>
                
                {data?.terminal_stats ? (
                    <div className="grid grid-cols-2 gap-2">
                        <StatCard label="Expected" value={data.terminal_stats.mean} />
                        <StatCard label="Std Dev" value={data.terminal_stats.std} />
                        <StatCard label="Skewness" value={data.terminal_stats.skewness} color={data.terminal_stats.skewness > 0 ? 'terminal-green' : 'terminal-red'} />
                        <StatCard label="Kurtosis" value={data.terminal_stats.kurtosis} />
                        <StatCard label="VaR 95%" value={data.terminal_stats.var_95} color="terminal-red" />
                        <StatCard label="CVaR 95%" value={data.terminal_stats.cvar_95} color="terminal-red" />
                    </div>
                ) : (
                    <div className="text-terminal-dim text-xs">Run simulation for stats</div>
                )}

                {data?.market_regime && (
                    <div className="mt-4 p-2 bg-terminal-black/50 border border-terminal-gray/20 rounded">
                        <div className="text-[9px] text-terminal-dim uppercase mb-1">Market Regime</div>
                        <div className={`text-sm font-mono font-bold ${
                            data.market_regime.current_regime === 'Bullish' ? 'text-terminal-green' :
                            data.market_regime.current_regime === 'Bearish' ? 'text-terminal-red' : 'text-terminal-yellow'
                        }`}>{data.market_regime.current_regime}</div>
                    </div>
                )}

                {coneData.length > 0 && (
                    <div className="mt-4">
                        <div className="text-[9px] text-terminal-dim uppercase mb-2">Probability Cones</div>
                        <CanvasAreaChart 
                            data={coneData} 
                            areas={[
                                { key: 'p95', color: '#ff3b3b' },
                                { key: 'p50', color: '#00ff88' },
                                { key: 'p5', color: '#ff3b3b' },
                            ]}
                            height={120}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

// ============================================================================
// MODULE 2: STATE-SPACE TRACKING (KALMAN)
// ============================================================================
const KalmanLab = () => {
    const [ticker, setTicker] = useState('AAPL');
    const [benchmark, setBenchmark] = useState('SPY');
    const [Q, setQ] = useState(0.01);
    const [R, setR] = useState(1.0);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/quantitative/kalman/filter`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker, benchmark, Q, R, lookback: 252 })
            });
            if (!res.ok) throw new Error(await res.text());
            const result = await res.json();
            setData(result.data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [ticker, benchmark, Q, R]);

    const denoiseData = useMemo(() => {
        if (!data?.denoise?.original_price) return [];
        return data.denoise.original_price.map((v, i) => ({
            t: i,
            original: v,
            filtered: data.denoise.filtered_price?.[i],
        }));
    }, [data]);

    const betaData = useMemo(() => {
        if (!data?.dynamic_beta?.betas) return [];
        return data.dynamic_beta.betas.map((v, i) => ({
            t: i,
            beta: v,
        }));
    }, [data]);

    // Phase portrait 3D data
    const phaseData = useMemo(() => {
        if (!data?.phase_portrait?.portrait) return null;
        const portrait = data.phase_portrait.portrait;
        const x = portrait.map(p => p[0]);
        const y = portrait.map(p => p[1]);
        const z = portrait.map((_, i) => i);
        return { x, y, z };
    }, [data]);

    return (
        <div className="grid grid-cols-12 gap-3 h-full">
            {/* Parameters */}
            <div className="col-span-2 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase tracking-wider flex items-center gap-2">
                    <Radar size={14} /> UKF Filter
                </div>
                
                <div className="mb-3">
                    <label className="text-[9px] text-terminal-dim block mb-1 uppercase">TICKER</label>
                    <TradingViewSearch mode="security" onSelect={setTicker} placeholder={ticker} />
                </div>

                <div className="mb-3">
                    <label className="text-[9px] text-terminal-dim block mb-1 uppercase">BENCHMARK</label>
                    <TradingViewSearch mode="security" onSelect={setBenchmark} placeholder={benchmark} />
                </div>

                <ParamSlider label="Process Noise (Q)" value={Q} onChange={setQ} min={0.001} max={0.5} step={0.001} />
                <ParamSlider label="Measurement Noise (R)" value={R} onChange={setR} min={0.1} max={5} step={0.1} />

                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="w-full bg-terminal-yellow text-terminal-black py-2 font-mono text-[10px] font-bold rounded mt-3 hover:bg-yellow-400 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {loading ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                    {loading ? 'FILTERING...' : 'RUN KALMAN'}
                </button>
            </div>

            {/* Charts */}
            <div className="col-span-7 flex flex-col gap-3">
                {/* Denoised */}
                <div className="bg-terminal-darker border border-terminal-gray/30 rounded p-3">
                    {error && <div className="text-terminal-red text-xs mb-2">{error}</div>}
                    {denoiseData.length > 0 ? (
                        <CanvasLineChart 
                            data={denoiseData}
                            lines={[
                                { key: 'original', color: '#5a6578', width: 1 },
                                { key: 'filtered', color: '#00ff88', width: 2 },
                            ]}
                            height={180}
                            title="UKF Denoised Price"
                        />
                    ) : (
                        <div className="h-[180px] flex items-center justify-center text-terminal-dim text-xs">
                            Run filter for denoised prices
                        </div>
                    )}
                </div>

                {/* Phase Portrait 3D */}
                <div className="flex-1 bg-terminal-darker border border-terminal-gray/30 rounded overflow-hidden">
                    <div className="px-3 pt-2 border-b border-terminal-gray/20">
                        <div className="text-xs font-bold text-terminal-yellow uppercase">Phase Space Orbit</div>
                    </div>
                    <div className="h-[200px]">
                        {phaseData ? (
                            <Plot
                                data={[{
                                    type: 'scatter3d',
                                    mode: 'lines+markers',
                                    x: phaseData.x,
                                    y: phaseData.y,
                                    z: phaseData.z,
                                    marker: { size: 2, color: phaseData.z, colorscale: 'Viridis' },
                                    line: { color: '#00ff88', width: 1 }
                                }]}
                                layout={{
                                    autosize: true,
                                    paper_bgcolor: 'transparent',
                                    plot_bgcolor: 'transparent',
                                    margin: { l: 0, r: 0, b: 0, t: 0 },
                                    scene: {
                                        bgcolor: 'transparent',
                                        camera: { eye: { x: 1.5, y: 1.5, z: 1.2 } }
                                    }
                                }}
                                style={{ width: '100%', height: '100%' }}
                                useResizeHandler={true}
                                config={{ displayModeBar: false }}
                            />
                        ) : (
                            <div className="h-full flex items-center justify-center text-terminal-dim text-xs">
                                Run filter for phase portrait
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Stats */}
            <div className="col-span-3 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase">Filter Stats</div>
                
                {data?.denoise && (
                    <StatCard label="Signal-to-Noise" value={data.denoise.snr_db} unit=" dB" color={data.denoise.snr_db > 0 ? 'terminal-green' : 'terminal-red'} />
                )}

                {data?.dynamic_beta && (
                    <div className="mt-4 space-y-2">
                        <div className="text-[9px] font-bold text-terminal-dim mb-2 uppercase">Dynamic Beta</div>
                        <StatCard label="Current Beta" value={data.dynamic_beta.current_beta} />
                        <StatCard label="Alpha (Ann.)" value={(data.dynamic_beta.current_alpha_ann * 100)} unit="%" color={data.dynamic_beta.current_alpha_ann > 0 ? 'terminal-green' : 'terminal-red'} />
                        <StatCard label="Stability" value={(data.dynamic_beta.beta_stability * 100)} unit="%" />
                    </div>
                )}

                {betaData.length > 0 && (
                    <div className="mt-4">
                        <div className="text-[9px] text-terminal-dim uppercase mb-2">Beta Evolution</div>
                        <CanvasLineChart 
                            data={betaData}
                            lines={[{ key: 'beta', color: '#00bfff', width: 1.5 }]}
                            height={100}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

// ============================================================================
// MODULE 3: ARBITRAGE MATRIX
// ============================================================================
const CointegrationLab = () => {
    const [tickerA, setTickerA] = useState('GLD');
    const [tickerB, setTickerB] = useState('SLV');
    const [lookback, setLookback] = useState(504);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/quantitative/cointegration/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker_a: tickerA, ticker_b: tickerB, lookback })
            });
            if (!res.ok) throw new Error(await res.text());
            const result = await res.json();
            setData(result.data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [tickerA, tickerB, lookback]);

    const spreadData = useMemo(() => {
        if (!data?.engle_granger?.spread) return [];
        return data.engle_granger.spread.map((v, i) => ({ t: i, spread: v }));
    }, [data]);

    const priceData = useMemo(() => {
        if (!data?.prices_a) return [];
        return data.prices_a.map((v, i) => ({
            t: i,
            a: v,
            b: data.prices_b?.[i],
        }));
    }, [data]);

    return (
        <div className="grid grid-cols-12 gap-3 h-full">
            {/* Parameters */}
            <div className="col-span-2 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase tracking-wider flex items-center gap-2">
                    <GitBranch size={14} /> Pair Analysis
                </div>
                
                <div className="mb-3">
                    <label className="text-[9px] text-terminal-dim block mb-1 uppercase">ASSET A</label>
                    <TradingViewSearch mode="security" onSelect={setTickerA} placeholder={tickerA} />
                </div>

                <div className="mb-3">
                    <label className="text-[9px] text-terminal-dim block mb-1 uppercase">ASSET B</label>
                    <TradingViewSearch mode="security" onSelect={setTickerB} placeholder={tickerB} />
                </div>

                <ParamSlider label="Lookback" value={lookback} onChange={setLookback} min={120} max={1260} />

                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="w-full bg-terminal-yellow text-terminal-black py-2 font-mono text-[10px] font-bold rounded mt-3 hover:bg-yellow-400 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {loading ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                    {loading ? 'ANALYZING...' : 'ANALYZE PAIR'}
                </button>

                {data?.engle_granger && (
                    <div className="mt-4 p-2 border border-terminal-gray/30 rounded">
                        <SignalBadge signal={data.engle_granger.current_signal} />
                    </div>
                )}
            </div>

            {/* Charts */}
            <div className="col-span-7 flex flex-col gap-3">
                {/* Prices */}
                <div className="bg-terminal-darker border border-terminal-gray/30 rounded p-3">
                    {error && <div className="text-terminal-red text-xs mb-2">{error}</div>}
                    {priceData.length > 0 ? (
                        <CanvasLineChart 
                            data={priceData}
                            lines={[
                                { key: 'a', color: '#00ff88', width: 1.5 },
                                { key: 'b', color: '#ff9f1c', width: 1.5 },
                            ]}
                            height={150}
                            title={`${tickerA} vs ${tickerB}`}
                        />
                    ) : (
                        <div className="h-[150px] flex items-center justify-center text-terminal-dim text-xs">
                            Run analysis for prices
                        </div>
                    )}
                </div>

                {/* Spread */}
                <div className="flex-1 bg-terminal-darker border border-terminal-gray/30 rounded p-3">
                    {spreadData.length > 0 ? (
                        <CanvasLineChart 
                            data={spreadData}
                            lines={[{ key: 'spread', color: '#00bfff', width: 1.5 }]}
                            height={200}
                            title="Spread (Z-Score)"
                        />
                    ) : (
                        <div className="h-[200px] flex items-center justify-center text-terminal-dim text-xs">
                            Run analysis for spread
                        </div>
                    )}
                </div>
            </div>

            {/* Stats */}
            <div className="col-span-3 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase">Cointegration</div>
                
                {data?.engle_granger && (
                    <div className="space-y-2">
                        <div className={`p-2 rounded text-center ${data.engle_granger.cointegrated ? 'bg-terminal-green/20 border border-terminal-green/30' : 'bg-terminal-red/20 border border-terminal-red/30'}`}>
                            <div className={`font-mono font-bold ${data.engle_granger.cointegrated ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                {data.engle_granger.cointegrated ? 'COINTEGRATED' : 'NOT COINTEGRATED'}
                            </div>
                        </div>
                        <StatCard label="ADF Stat" value={data.engle_granger.adf_stat} />
                        <StatCard label="P-Value" value={data.engle_granger.p_value} color={data.engle_granger.p_value < 0.05 ? 'terminal-green' : 'terminal-red'} />
                        <StatCard label="Hedge Ratio" value={data.engle_granger.hedge_ratio_beta} />
                        <StatCard label="Z-Score" value={data.engle_granger.spread_zscore} />
                    </div>
                )}

                {data?.half_life && (
                    <div className="mt-4">
                        <StatCard 
                            label="Half-Life" 
                            value={data.half_life.half_life_days || 'Inf'} 
                            unit={data.half_life.half_life_days ? ' days' : ''} 
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

// ============================================================================
// MODULE 4: SPECTRAL PHYSICS
// ============================================================================
const SpectralLab = () => {
    const [ticker, setTicker] = useState('SPY');
    const [lookback, setLookback] = useState(504);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/quantitative/spectral/full-analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker, lookback })
            });
            if (!res.ok) throw new Error(await res.text());
            const result = await res.json();
            setData(result.data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [ticker, lookback]);

    const spectrumData = useMemo(() => {
        if (!data?.entropy?.frequencies) return [];
        return data.entropy.frequencies.map((f, i) => ({
            f,
            power: data.entropy.power_spectrum?.[i],
        }));
    }, [data]);

    // CWT scalogram surface
    const scalogramSurface = useMemo(() => {
        if (!data?.scalogram?.heatmap_data) return null;
        return data.scalogram.heatmap_data;
    }, [data]);

    return (
        <div className="grid grid-cols-12 gap-3 h-full">
            {/* Parameters */}
            <div className="col-span-2 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase tracking-wider flex items-center gap-2">
                    <Eye size={14} /> Spectral Analysis
                </div>
                
                <div className="mb-3">
                    <label className="text-[9px] text-terminal-dim block mb-1 uppercase">TICKER</label>
                    <TradingViewSearch mode="security" onSelect={setTicker} placeholder={ticker} />
                </div>

                <ParamSlider label="Lookback" value={lookback} onChange={setLookback} min={120} max={1260} />

                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="w-full bg-terminal-yellow text-terminal-black py-2 font-mono text-[10px] font-bold rounded mt-3 hover:bg-yellow-400 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {loading ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                    {loading ? 'ANALYZING...' : 'RUN SPECTRAL'}
                </button>

                {data?.bifurcation && (
                    <div className="mt-4 p-2 border rounded" style={{
                        borderColor: data.bifurcation.bifurcation_score > 60 ? '#ff3b3b' : '#1e2738'
                    }}>
                        <div className="text-[9px] text-terminal-dim mb-1 uppercase">Bifurcation Risk</div>
                        <div className={`text-xl font-mono font-bold ${
                            data.bifurcation.warning_level === 'CRITICAL' ? 'text-terminal-red' :
                            data.bifurcation.warning_level === 'HIGH' ? 'text-terminal-orange' :
                            'text-terminal-green'
                        }`}>
                            {data.bifurcation.bifurcation_score?.toFixed(0)}%
                        </div>
                    </div>
                )}
            </div>

            {/* Scalogram 3D */}
            <div className="col-span-7 bg-terminal-darker border border-terminal-gray/30 rounded overflow-hidden">
                <div className="px-3 pt-2 border-b border-terminal-gray/20">
                    <div className="text-xs font-bold text-terminal-yellow uppercase">CWT Scalogram</div>
                </div>
                <div className="h-[380px]">
                    {error && <div className="p-4 text-terminal-red text-xs">{error}</div>}
                    {scalogramSurface ? (
                        <Plot
                            data={[{
                                z: scalogramSurface,
                                type: 'surface',
                                colorscale: 'Hot',
                                showscale: false
                            }]}
                            layout={{
                                autosize: true,
                                paper_bgcolor: 'transparent',
                                plot_bgcolor: 'transparent',
                                margin: { l: 0, r: 0, b: 0, t: 0 },
                                scene: {
                                    bgcolor: 'transparent',
                                    xaxis: { title: 'Time', gridcolor: '#1e2738' },
                                    yaxis: { title: 'Scale', gridcolor: '#1e2738' },
                                    zaxis: { title: 'Power', gridcolor: '#1e2738' },
                                    camera: { eye: { x: 1.5, y: 1.5, z: 1.0 } }
                                }
                            }}
                            style={{ width: '100%', height: '100%' }}
                            useResizeHandler={true}
                            config={{ displayModeBar: false }}
                        />
                    ) : (
                        <div className="h-full flex items-center justify-center text-terminal-dim text-xs">
                            Run analysis for scalogram
                        </div>
                    )}
                </div>
            </div>

            {/* Stats */}
            <div className="col-span-3 bg-terminal-darker border border-terminal-gray/30 p-3 rounded overflow-y-auto">
                <div className="text-xs font-bold text-terminal-yellow mb-3 uppercase">Chaos Metrics</div>
                
                {data?.lyapunov && (
                    <div className="space-y-2">
                        <StatCard 
                            label="Lyapunov λ" 
                            value={data.lyapunov.lyapunov_exponent} 
                            color={data.lyapunov.lyapunov_exponent > 0 ? 'terminal-red' : 'terminal-green'}
                            subtext={data.lyapunov.chaos_level}
                        />
                        {data.lyapunov.prediction_horizon_days && (
                            <StatCard label="Prediction Horizon" value={data.lyapunov.prediction_horizon_days} unit=" days" />
                        )}
                    </div>
                )}

                {data?.entropy && (
                    <div className="mt-4 space-y-2">
                        <StatCard label="Spectral Entropy" value={data.entropy.spectral_entropy} />
                        <StatCard label="Dominant Period" value={data.entropy.dominant_period_days} unit=" days" />
                    </div>
                )}

                {spectrumData.length > 0 && (
                    <div className="mt-4">
                        <div className="text-[9px] text-terminal-dim uppercase mb-2">Power Spectrum</div>
                        <CanvasAreaChart 
                            data={spectrumData}
                            areas={[{ key: 'power', color: '#00bfff' }]}
                            height={100}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function QuantitativeLab() {
    const [activeModule, setActiveModule] = useState('sde');

    const renderModule = () => {
        switch (activeModule) {
            case 'sde': return <SDEPathLab />;
            case 'kalman': return <KalmanLab />;
            case 'cointegration': return <CointegrationLab />;
            case 'spectral': return <SpectralLab />;
            default: return <SDEPathLab />;
        }
    };

    return (
        <div className="h-full flex flex-col bg-terminal-black">
            {/* Module Tabs */}
            <div className="flex items-center border-b border-terminal-gray/30 bg-terminal-darker px-4">
                <div className="flex items-center gap-2 py-3 pr-4 border-r border-terminal-gray/30 mr-4">
                    <div className="w-2 h-2 rounded-full bg-terminal-cyan animate-pulse" />
                    <span className="text-xs font-bold text-terminal-yellow tracking-wider">QUANTITATIVE LAB</span>
                </div>
                
                {MODULES.map((mod) => {
                    const Icon = mod.icon;
                    const isActive = activeModule === mod.id;
                    return (
                        <button
                            key={mod.id}
                            onClick={() => setActiveModule(mod.id)}
                            className={`flex items-center gap-2 px-4 py-3 text-xs font-mono transition-all border-b-2 ${
                                isActive 
                                    ? 'text-terminal-yellow border-terminal-yellow bg-terminal-yellow/5' 
                                    : 'text-terminal-dim border-transparent hover:text-terminal-text'
                            }`}
                        >
                            <Icon size={14} />
                            {mod.label}
                        </button>
                    );
                })}

                <div className="ml-auto text-[10px] text-terminal-dim font-mono">
                    v2.0 | 3D Surfaces | Real Math
                </div>
            </div>

            {/* Module Content */}
            <div className="flex-1 p-3 overflow-hidden">
                {renderModule()}
            </div>
        </div>
    );
}
