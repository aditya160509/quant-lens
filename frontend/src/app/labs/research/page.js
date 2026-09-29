"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { 
    Activity, Link as LinkIcon, ArrowRight, Shuffle, Gauge, 
    AlertTriangle, ShieldAlert, FlaskConical, RefreshCw,
    Network, Terminal, ZapOff, Database, TrendingUp, TrendingDown,
    BarChart2, Clock, CheckCircle, XCircle, Plus, X, ChevronDown,
    Radar, GitBranch, PieChart, Zap, Layers, Target, FileText, Brain
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import dynamic from 'next/dynamic';
import { API_BASE_URL } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

// ============== CONSTANTS & CONFIG ==============

// Statistical Analysis Modules (original stats suite - removed Vector Hub)
const STATS_MODULES = [
    { id: 'stationarity', icon: FlaskConical, label: 'Stationarity Suite' },
    { id: 'cointegration', icon: LinkIcon, label: 'Cointegration' },
    { id: 'causality', icon: ArrowRight, label: 'Lead-Lag Hub' },
    { id: 'entropy', icon: Network, label: 'Entropy Hub' },
    { id: 'distribution', icon: Gauge, label: 'Distribution Lab' },
    { id: 'volatility', icon: Activity, label: 'Vol Dynamics' },
];

// Quantitative Research Modules (separate pages, now inline)
const QUANT_MODULES = [
    { id: 'spider', label: 'Spider Chart', icon: Radar, route: '/labs/research/spider' },
    { id: 'sharpe', label: 'Sharpe Radar', icon: Target, route: '/labs/research/sharpe' },
    { id: 'beta', label: 'Beta Analysis', icon: GitBranch, route: '/labs/research/beta' },
    { id: 'correlation', label: 'Correlation', icon: Layers, route: '/labs/research/correlation' },
    { id: 'momentum', label: 'Momentum', icon: TrendingUp, route: '/labs/research/momentum' },
    { id: 'mean_reversion', label: 'Mean Reversion', icon: RefreshCw, route: '/labs/research/mean_reversion' },
    { id: 'risk', label: 'Risk Analytics', icon: AlertTriangle, route: '/labs/research/risk' },
    { id: 'macro_shock', label: 'Macro Shock', icon: Zap, route: '/labs/research/macro_shock' },
    { id: 'style_map', label: 'Style Map', icon: PieChart, route: '/labs/research/style_map' },
    { id: 'regimes', label: 'Regime Detector', icon: Brain, route: '/labs/research/regimes' },
];

// Preset universes
const UNIVERSE_PRESETS = {
    'US Majors': ['SPY', 'QQQ', 'DIA', 'IWM', 'TLT', 'GLD'],
    'US Tech': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA'],
    'US Sectors': ['XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLI', 'XLU'],
    'India Nifty': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS'],
    'Crypto': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD'],
    'Global Indices': ['^GSPC', '^FTSE', '^N225', '^GDAXI', '^NSEI'],
    'Commodities': ['GLD', 'SLV', 'USO', 'UNG', 'DBA'],
};

// ============== STYLES ==============

const glassStyle = {
    background: 'rgba(10, 15, 25, 0.7)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    borderRadius: '12px',
};

const monoLabel = {
    fontFamily: 'var(--font-mono)',
    fontSize: '10px',
    color: '#5a6578',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    fontWeight: 'bold'
};

const statBox = {
    background: 'rgba(0,0,0,0.3)',
    padding: '12px',
    borderRadius: '6px',
    border: '1px solid #1e2738'
};

// ============== SIDEBAR ==============

const Sidebar = ({ config, setConfig, onRun, loading, calcLog }) => {
    const [showPresets, setShowPresets] = useState(false);
    
    const tickerList = config.tickers.split(',').map(t => t.trim()).filter(Boolean);
    
    const addTicker = (ticker) => {
        const current = tickerList;
        if (!current.includes(ticker.toUpperCase())) {
            setConfig({ ...config, tickers: [...current, ticker.toUpperCase()].join(', ') });
        }
    };
    
    const removeTicker = (ticker) => {
        const current = tickerList.filter(t => t !== ticker);
        setConfig({ ...config, tickers: current.join(', ') });
    };
    
    const applyPreset = (presetName) => {
        setConfig({ ...config, tickers: UNIVERSE_PRESETS[presetName].join(', ') });
        setShowPresets(false);
    };

    return (
        <div style={{ width: '320px', padding: '20px', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <Terminal size={16} className="text-blue-400" />
                <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.08em' }}>ENGINE CONTROLS</span>
            </div>

            {/* Universe Selection with TradingView Search */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label style={monoLabel}>UNIVERSE</label>
                    <div style={{ position: 'relative' }}>
                        <button 
                            onClick={() => setShowPresets(!showPresets)}
                            style={{ 
                                background: 'transparent', border: '1px solid #1e2738', borderRadius: '4px', 
                                padding: '4px 8px', fontSize: '9px', color: '#3b82f6', cursor: 'pointer',
                                display: 'flex', alignItems: 'center', gap: '4px'
                            }}
                        >
                            PRESETS <ChevronDown size={10} />
                        </button>
                        {showPresets && (
                            <div style={{ 
                                position: 'absolute', top: '100%', right: 0, marginTop: '4px',
                                background: '#0a0f18', border: '1px solid #1e2738', borderRadius: '6px',
                                zIndex: 100, minWidth: '150px', boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
                            }}>
                                {Object.keys(UNIVERSE_PRESETS).map(preset => (
                                    <div 
                                        key={preset}
                                        onClick={() => applyPreset(preset)}
                                        style={{ 
                                            padding: '8px 12px', fontSize: '10px', color: '#fff', cursor: 'pointer',
                                            borderBottom: '1px solid #1e2738'
                                        }}
                                        onMouseEnter={e => e.target.style.background = '#1e2738'}
                                        onMouseLeave={e => e.target.style.background = 'transparent'}
                                    >
                                        {preset}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
                
                {/* TradingView Search */}
                <TradingViewSearch 
                    mode="security" 
                    onSelect={addTicker} 
                    placeholder="Search to add symbol..."
                />
                
                {/* Selected Tickers as Chips */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                    {tickerList.map(ticker => (
                        <div 
                            key={ticker}
                            style={{
                                display: 'flex', alignItems: 'center', gap: '4px',
                                background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.3)',
                                borderRadius: '4px', padding: '4px 8px', fontSize: '10px', color: '#3b82f6'
                            }}
                        >
                            <span>{ticker}</span>
                            <X 
                                size={10} 
                                style={{ cursor: 'pointer', opacity: 0.7 }} 
                                onClick={() => removeTicker(ticker)}
                            />
                        </div>
                    ))}
                </div>
                <div style={{ fontSize: '9px', color: '#5a6578' }}>{tickerList.length} symbols selected</div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={monoLabel}>LOOKBACK (TRADING DAYS)</label>
                <select 
                    value={config.lookback} 
                    onChange={(e) => setConfig({ ...config, lookback: e.target.value })}
                    style={{ background: '#0a0f18', border: '1px solid #1e2738', borderRadius: '6px', padding: '8px', color: '#fff', fontSize: '11px' }}
                >
                    <option value="252">252d (1Y)</option>
                    <option value="504">504d (2Y)</option>
                    <option value="756">756d (3Y)</option>
                    <option value="1260">1260d (5Y)</option>
                </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={monoLabel}>HORIZON / MAX LAG</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <input 
                        type="number" min="5" max="60"
                        value={config.horizon}
                        onChange={(e) => setConfig({ ...config, horizon: parseInt(e.target.value) || 10 })}
                        style={{ flex: 1, background: '#0a0f18', border: '1px solid #1e2738', borderRadius: '6px', padding: '8px', color: '#fff', fontSize: '11px' }}
                    />
                    <input 
                        type="number" min="1" max="15"
                        value={config.maxLag}
                        onChange={(e) => setConfig({ ...config, maxLag: parseInt(e.target.value) || 5 })}
                        style={{ flex: 1, background: '#0a0f18', border: '1px solid #1e2738', borderRadius: '6px', padding: '8px', color: '#fff', fontSize: '11px' }}
                    />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#5a6578' }}>
                    <span>H={config.horizon}d</span>
                    <span>Lag={config.maxLag}</span>
                </div>
            </div>

            <button 
                onClick={onRun}
                disabled={loading || tickerList.length < 2}
                style={{ 
                    marginTop: 'auto', background: loading ? '#1e2738' : 'linear-gradient(90deg, #3b82f6 0%, #2563eb 100%)', 
                    color: '#fff', border: 'none', borderRadius: '8px', padding: '12px', 
                    fontWeight: 700, letterSpacing: '0.08em', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '11px',
                    opacity: tickerList.length < 2 ? 0.5 : 1
                }}
            >
                {loading ? 'COMPUTING...' : tickerList.length < 2 ? 'ADD 2+ SYMBOLS' : 'EXECUTE'}
            </button>

            <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px', padding: '10px', background: 'rgba(16, 185, 129, 0.05)', borderRadius: '6px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                <Database size={12} className="text-green-400" />
                <div style={{ fontSize: '9px' }}>
                    <span style={{ color: '#10b981', fontWeight: 'bold' }}>PARQUET ENGINE</span>
                    <span style={{ color: '#5a6578', marginLeft: '4px' }}>v4.5</span>
                </div>
            </div>

            {/* Calculation Log */}
            <div style={{ ...glassStyle, padding: '10px', marginTop: '8px', maxHeight: '100px', overflowY: 'auto' }}>
                <div style={{ ...monoLabel, fontSize: '9px', marginBottom: '6px', color: '#f59e0b' }}>CALC LOG</div>
                <div style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: '#5a6578', lineHeight: '1.6' }}>
                    {calcLog.map((log, i) => (
                        <div key={i} style={{ color: log.type === 'error' ? '#ef4444' : log.type === 'success' ? '#10b981' : '#5a6578' }}>
                            [{log.time}] {log.msg}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// ============== HELPER COMPONENTS ==============

const StatCard = ({ label, value, unit, pass, threshold }) => (
    <div style={statBox}>
        <div style={{ ...monoLabel, marginBottom: '4px' }}>{label}</div>
        <div style={{ fontSize: '18px', fontWeight: 700, color: pass === undefined ? '#fff' : pass ? '#10b981' : '#f59e0b' }}>
            {typeof value === 'number' ? value.toFixed(4) : value}
            {unit && <span style={{ fontSize: '10px', color: '#5a6578', marginLeft: '4px' }}>{unit}</span>}
        </div>
        {threshold && <div style={{ fontSize: '9px', color: '#5a6578' }}>vs {threshold}</div>}
    </div>
);

const TestResult = ({ label, stat, pValue, pass }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
        <div>
            <div style={{ fontSize: '11px', fontWeight: 600, color: '#fff' }}>{label}</div>
            <div style={{ fontSize: '9px', color: '#5a6578' }}>stat: {stat.toFixed(4)} | p: {pValue.toFixed(5)}</div>
        </div>
        {pass !== undefined && (
            pass ? <CheckCircle size={14} className="text-green-400" /> : <XCircle size={14} className="text-yellow-400" />
        )}
    </div>
);

const LoadingState = () => (
    <div style={{ height: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
        <RefreshCw size={32} className="animate-spin text-blue-500" />
        <div style={monoLabel}>COMPUTING...</div>
    </div>
);

const EmptyState = ({ label }) => (
    <div style={{ height: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', opacity: 0.3 }}>
        <ZapOff size={40} />
        <div style={monoLabel}>{label}</div>
    </div>
);

// ============== MODULE PANELS ==============

const StationarityPanel = ({ data, loading }) => {
    if (loading) return <LoadingState />;
    if (!data) return <EmptyState label="RUN STATIONARITY SUITE" />;

    return (
        <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
                <h3 style={{ ...monoLabel, color: '#3b82f6', marginBottom: '12px' }}>UNIT ROOT TESTS ({data.ticker})</h3>
                <div style={{ display: 'grid', gap: '8px' }}>
                    <TestResult label="ADF Test" stat={data.adf.stat} pValue={data.adf.p_value} pass={data.adf.is_stationary} />
                    <TestResult label="KPSS Test" stat={data.kpss.stat} pValue={data.kpss.p_value} pass={data.kpss.is_stationary} />
                    <TestResult label="Phillips-Perron" stat={data.phillips_perron.stat} pValue={data.phillips_perron.p_value} pass={data.phillips_perron.is_stationary} />
                </div>

                <h3 style={{ ...monoLabel, color: '#3b82f6', marginBottom: '12px', marginTop: '20px' }}>PERSISTENCE ANALYSIS</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <StatCard label="Hurst Exponent" value={data.hurst.value} pass={data.hurst.value < 0.5} />
                    <StatCard label="Variance Ratio" value={data.variance_ratio.value} pass={data.variance_ratio.value < 1} />
                </div>

                <div style={{ marginTop: '16px', padding: '12px', borderRadius: '6px', background: data.consensus === 'STATIONARY' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)', border: `1px solid ${data.consensus === 'STATIONARY' ? '#10b981' : '#f59e0b'}` }}>
                    <div style={{ fontSize: '12px', fontWeight: 700, color: data.consensus === 'STATIONARY' ? '#10b981' : '#f59e0b' }}>
                        CONSENSUS: {data.consensus}
                    </div>
                    <div style={{ fontSize: '10px', color: '#5a6578', marginTop: '4px' }}>
                        Hurst: {data.hurst.interpretation} | VR: {data.variance_ratio.interpretation}
                    </div>
                </div>
            </div>

            <div style={{ ...glassStyle, padding: '16px' }}>
                <div style={monoLabel}>HURST PROFILE</div>
                <Plot 
                    data={[{
                        type: 'indicator', mode: 'gauge+number', value: data.hurst.value,
                        gauge: {
                            axis: { range: [0, 1], tickwidth: 1 },
                            bar: { color: data.hurst.value < 0.5 ? '#10b981' : '#f59e0b' },
                            steps: [
                                { range: [0, 0.45], color: 'rgba(16, 185, 129, 0.15)' },
                                { range: [0.45, 0.55], color: 'rgba(245, 158, 11, 0.15)' },
                                { range: [0.55, 1], color: 'rgba(59, 130, 246, 0.15)' }
                            ],
                            threshold: { line: { color: '#fff', width: 2 }, thickness: 0.75, value: 0.5 }
                        }
                    }]}
                    layout={{ width: 350, height: 250, paper_bgcolor: 'transparent', margin: { t: 20, b: 0, l: 30, r: 30 } }}
                />
                <div style={{ marginTop: '12px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', fontSize: '9px', textAlign: 'center' }}>
                    <div><span style={{ color: '#10b981' }}>●</span> Mean-Revert</div>
                    <div><span style={{ color: '#f59e0b' }}>●</span> Random Walk</div>
                    <div><span style={{ color: '#3b82f6' }}>●</span> Trending</div>
                </div>
            </div>
        </div>
    );
};

const CointegrationPanel = ({ data, loading }) => {
    if (loading) return <LoadingState />;
    if (!data) return <EmptyState label="RUN COINTEGRATION TEST" />;

    return (
        <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
                <h3 style={{ ...monoLabel, color: '#3b82f6', marginBottom: '12px' }}>PAIR: {data.tickers.join(' / ')}</h3>
                <div style={{ display: 'grid', gap: '8px' }}>
                    <TestResult label="Engle-Granger" stat={data.engle_granger.stat} pValue={data.engle_granger.p_value} pass={data.engle_granger.is_cointegrated} />
                </div>

                <h3 style={{ ...monoLabel, color: '#3b82f6', marginBottom: '12px', marginTop: '16px' }}>JOHANSEN TRACE (5% CRIT)</h3>
                <div style={{ display: 'grid', gap: '6px' }}>
                    {data.johansen.trace_stats.map((stat, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', padding: '6px', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
                            <span style={{ color: '#5a6578' }}>r ≤ {i}</span>
                            <span style={{ color: stat > data.johansen.crit_trace_5pct[i] ? '#10b981' : '#5a6578' }}>
                                {stat.toFixed(2)} vs {data.johansen.crit_trace_5pct[i].toFixed(2)}
                            </span>
                        </div>
                    ))}
                </div>
                <div style={{ marginTop: '8px', fontSize: '10px', color: '#5a6578' }}>Rank: {data.johansen.rank}</div>

                <h3 style={{ ...monoLabel, color: '#3b82f6', marginBottom: '12px', marginTop: '16px' }}>HEDGE PARAMETERS</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <StatCard label="β (Hedge)" value={data.hedge.ratio} />
                    <StatCard label="R²" value={data.hedge.r_squared} />
                    <StatCard label="Half-Life" value={data.hedge.half_life_days || '∞'} unit="days" />
                    <StatCard label="Z-Score" value={data.hedge.current_zscore} pass={Math.abs(data.hedge.current_zscore) > 2} />
                </div>
            </div>

            <div style={{ ...glassStyle, padding: '16px' }}>
                <div style={monoLabel}>SPREAD TIME SERIES</div>
                <Plot 
                    data={[{
                        y: data.spread_series,
                        type: 'scatter', mode: 'lines', line: { color: '#3b82f6', width: 1 },
                        fill: 'tozeroy', fillcolor: 'rgba(59, 130, 246, 0.1)'
                    }]}
                    layout={{ 
                        height: 300, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                        margin: { t: 20, b: 30, l: 40, r: 20 },
                        xaxis: { showgrid: false }, yaxis: { gridcolor: '#1e2738', title: 'Spread' },
                        shapes: [
                            { type: 'line', x0: 0, x1: data.spread_series.length, y0: data.hedge.spread_mean + 2*data.hedge.spread_std, y1: data.hedge.spread_mean + 2*data.hedge.spread_std, line: { color: '#ef4444', dash: 'dot' } },
                            { type: 'line', x0: 0, x1: data.spread_series.length, y0: data.hedge.spread_mean - 2*data.hedge.spread_std, y1: data.hedge.spread_mean - 2*data.hedge.spread_std, line: { color: '#10b981', dash: 'dot' } }
                        ]
                    }}
                    style={{ width: '100%' }}
                />
            </div>
        </div>
    );
};

const CausalityPanel = ({ data, loading }) => {
    if (loading) return <LoadingState />;
    if (!data) return <EmptyState label="RUN CAUSALITY ANALYSIS" />;

    return (
        <div style={{ padding: '20px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
                <div style={{ ...glassStyle, padding: '16px' }}>
                    <div style={monoLabel}>GRANGER CAUSALITY P-VALUES (COL → ROW)</div>
                    <Plot 
                        data={[{
                            z: data.p_value_matrix, x: data.nodes, y: data.nodes,
                            type: 'heatmap', colorscale: [[0, '#10b981'], [0.05, '#1e2738'], [1, '#0a0f18']],
                            showscale: true, xgap: 2, ygap: 2,
                            text: data.p_value_matrix.map(row => row.map(v => v.toFixed(3))),
                            hoverinfo: 'text+x+y'
                        }]}
                        layout={{ 
                            width: 400, height: 350, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                            font: { color: '#5a6578', size: 10 }, margin: { t: 30, b: 40, l: 60, r: 20 },
                            xaxis: { side: 'top' }, yaxis: { autorange: 'reversed' }
                        }}
                    />
                </div>

                <div>
                    <div style={monoLabel}>OPTIMAL LAGS</div>
                    <Plot 
                        data={[{
                            z: data.optimal_lag_matrix, x: data.nodes, y: data.nodes,
                            type: 'heatmap', colorscale: 'Blues', showscale: false, xgap: 2, ygap: 2,
                            text: data.optimal_lag_matrix.map(row => row.map(v => `${v}d`)),
                            hoverinfo: 'text+x+y'
                        }]}
                        layout={{ 
                            width: 250, height: 250, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                            font: { color: '#5a6578', size: 9 }, margin: { t: 30, b: 40, l: 50, r: 10 },
                            xaxis: { side: 'top' }, yaxis: { autorange: 'reversed' }
                        }}
                    />

                    <div style={{ marginTop: '16px' }}>
                        <div style={monoLabel}>SIGNIFICANT PAIRS (p {'<'} 0.05)</div>
                        <div style={{ maxHeight: '150px', overflowY: 'auto', marginTop: '8px' }}>
                            {data.significant_pairs.length === 0 ? (
                                <div style={{ fontSize: '10px', color: '#5a6578' }}>No significant pairs found</div>
                            ) : data.significant_pairs.slice(0, 8).map((pair, i) => (
                                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', padding: '4px', borderBottom: '1px solid #1e2738' }}>
                                    <span style={{ color: '#fff' }}>{pair.signal} → {pair.target}</span>
                                    <span style={{ color: '#10b981' }}>L{pair.optimal_lag}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

const EntropyPanel = ({ data, loading }) => {
    if (loading) return <LoadingState />;
    if (!data) return <EmptyState label="RUN ENTROPY ANALYSIS" />;

    return (
        <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
                <div style={monoLabel}>SHANNON ENTROPY (BITS)</div>
                <Plot 
                    data={[{
                        x: data.nodes, y: data.nodes.map(n => data.entropy_per_symbol[n]?.entropy_bits || 0),
                        type: 'bar', marker: { color: '#3b82f6' }
                    }]}
                    layout={{ height: 200, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { t: 20, b: 40, l: 40, r: 20 }, font: { color: '#5a6578' }, xaxis: { gridcolor: 'transparent' }, yaxis: { gridcolor: '#1e2738' } }}
                    style={{ width: '100%' }}
                />

                <div style={{ marginTop: '16px' }}>
                    <div style={monoLabel}>MUTUAL INFORMATION</div>
                    <Plot 
                        data={[{
                            z: data.mutual_information_matrix, x: data.nodes, y: data.nodes,
                            type: 'heatmap', colorscale: 'Viridis', xgap: 1, ygap: 1
                        }]}
                        layout={{ width: 300, height: 250, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#5a6578', size: 9 }, margin: { t: 20, b: 20, l: 40, r: 20 }, xaxis: { side: 'top' }, yaxis: { autorange: 'reversed' } }}
                    />
                </div>
            </div>

            <div>
                <div style={monoLabel}>TRANSFER ENTROPY (X → Y)</div>
                <Plot 
                    data={[{
                        z: data.transfer_entropy_matrix, x: data.nodes, y: data.nodes,
                        type: 'heatmap', colorscale: 'Hot', xgap: 1, ygap: 1
                    }]}
                    layout={{ width: 300, height: 250, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#5a6578', size: 9 }, margin: { t: 20, b: 20, l: 40, r: 20 }, xaxis: { side: 'top' }, yaxis: { autorange: 'reversed' } }}
                />

                <div style={{ marginTop: '16px' }}>
                    <div style={monoLabel}>SPECTRAL DENSITY ({data.spectral?.primary_ticker})</div>
                    <Plot 
                        data={[{
                            x: data.spectral?.periods?.slice(0, 30) || [],
                            y: data.spectral?.power?.slice(0, 30) || [],
                            type: 'scatter', fill: 'tozeroy', line: { color: '#f59e0b' }
                        }]}
                        layout={{ height: 180, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { t: 10, b: 40, l: 40, r: 20 }, font: { color: '#5a6578' }, xaxis: { title: 'Period (Days)', gridcolor: '#1e2738' }, yaxis: { gridcolor: '#1e2738' } }}
                        style={{ width: '100%' }}
                    />
                    <div style={{ fontSize: '9px', color: '#5a6578', marginTop: '4px' }}>
                        Dominant Cycles: {data.spectral?.dominant_cycles?.map(c => `${c.period_days.toFixed(0)}d`).join(', ')}
                    </div>
                </div>
            </div>
        </div>
    );
};

const DistributionPanel = ({ data, loading }) => {
    if (loading) return <LoadingState />;
    if (!data) return <EmptyState label="RUN DISTRIBUTION ANALYSIS" />;

    return (
        <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
            <div>
                <div style={monoLabel}>4-MOMENT TABLE ({data.ticker})</div>
                <div style={{ display: 'grid', gap: '8px', marginTop: '12px' }}>
                    <StatCard label="Mean (Daily)" value={data.moments.mean * 100} unit="%" />
                    <StatCard label="Std Dev" value={data.moments.std_dev * 100} unit="%" />
                    <StatCard label="Annualized Vol" value={data.moments.annualized_vol * 100} unit="%" />
                    <StatCard label="Skewness" value={data.moments.skewness} pass={Math.abs(data.moments.skewness) < 0.5} />
                    <StatCard label="Excess Kurtosis" value={data.moments.excess_kurtosis} pass={data.moments.excess_kurtosis < 3} />
                </div>

                <div style={{ marginTop: '16px' }}>
                    <div style={monoLabel}>NORMALITY TESTS</div>
                    <div style={{ display: 'grid', gap: '6px', marginTop: '8px' }}>
                        <TestResult label="Jarque-Bera" stat={data.normality.jarque_bera_stat} pValue={data.normality.jarque_bera_p} pass={data.normality.is_normal} />
                        <TestResult label="Shapiro-Wilk" stat={data.normality.shapiro_wilk_stat} pValue={data.normality.shapiro_wilk_p} />
                        <TestResult label="Kolmogorov-S" stat={data.normality.ks_stat} pValue={data.normality.ks_p} />
                    </div>
                </div>

                <div style={{ marginTop: '16px' }}>
                    <div style={monoLabel}>TAIL RISK</div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                        <StatCard label="VaR 95%" value={data.tail_risk.var_95 * 100} unit="%" />
                        <StatCard label="VaR 99%" value={data.tail_risk.var_99 * 100} unit="%" />
                        <StatCard label="CVaR 95%" value={data.tail_risk.cvar_95 * 100} unit="%" />
                        <StatCard label="CVaR 99%" value={data.tail_risk.cvar_99 * 100} unit="%" />
                    </div>
                </div>
            </div>

            <div style={{ ...glassStyle, padding: '16px' }}>
                <div style={monoLabel}>RETURN DISTRIBUTION</div>
                <Plot 
                    data={[{
                        x: data.histogram.bin_centers.map(v => v * 100),
                        y: data.histogram.counts,
                        type: 'bar', marker: { color: 'rgba(59, 130, 246, 0.6)', line: { color: '#3b82f6', width: 1 } }
                    }]}
                    layout={{ 
                        height: 350, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                        margin: { t: 20, b: 50, l: 50, r: 20 }, font: { color: '#5a6578' },
                        xaxis: { title: 'Return (%)', gridcolor: '#1e2738' },
                        yaxis: { title: 'Frequency', gridcolor: '#1e2738' },
                        shapes: [
                            { type: 'line', x0: data.tail_risk.var_95 * 100, x1: data.tail_risk.var_95 * 100, y0: 0, y1: Math.max(...data.histogram.counts), line: { color: '#ef4444', width: 2, dash: 'dot' } },
                            { type: 'line', x0: data.tail_risk.var_99 * 100, x1: data.tail_risk.var_99 * 100, y0: 0, y1: Math.max(...data.histogram.counts), line: { color: '#dc2626', width: 2, dash: 'dot' } }
                        ]
                    }}
                    style={{ width: '100%' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', marginTop: '8px' }}>
                    <span>Worst: {(data.tail_risk.worst_day_return * 100).toFixed(2)}%</span>
                    <span style={{ color: '#ef4444' }}>---- VaR 95/99</span>
                    <span>Best: {(data.tail_risk.best_day_return * 100).toFixed(2)}%</span>
                </div>
            </div>
        </div>
    );
};

const VARPanel = ({ data, loading }) => {
    if (loading) return <LoadingState />;
    if (!data) return <EmptyState label="RUN VAR ANALYSIS" />;

    return <VARPanelContent data={data} />;
};

const VARPanelContent = ({ data }) => {
    const [selectedTarget, setSelectedTarget] = useState(data.tickers?.[0] || '');

    return (
        <div style={{ padding: '20px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
                <div>
                    <div style={monoLabel}>MODEL FIT</div>
                    <div style={{ display: 'grid', gap: '8px', marginTop: '12px' }}>
                        <StatCard label="AIC" value={data.model_fit.aic} />
                        <StatCard label="BIC" value={data.model_fit.bic} />
                        <StatCard label="Optimal Lag" value={data.model_fit.optimal_lag} unit="days" />
                    </div>

                    <div style={{ marginTop: '16px' }}>
                        <div style={monoLabel}>IRF TARGET</div>
                        <select 
                            value={selectedTarget} 
                            onChange={(e) => setSelectedTarget(e.target.value)}
                            style={{ width: '100%', marginTop: '8px', background: '#0a0f18', border: '1px solid #1e2738', borderRadius: '6px', padding: '8px', color: '#fff' }}
                        >
                            {data.tickers.map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                    </div>

                    <div style={{ marginTop: '16px' }}>
                        <div style={monoLabel}>FEVD @ HORIZON {data.horizon}</div>
                        {data.tickers.map(t => (
                            <div key={t} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', padding: '4px 0', borderBottom: '1px solid #1e2738' }}>
                                <span>{t}</span>
                                <span style={{ color: '#3b82f6' }}>{(data.fevd[selectedTarget || data.tickers[0]]?.[t]?.[data.horizon] || 0).toFixed(1)}%</span>
                            </div>
                        ))}
                    </div>
                </div>

                <div style={{ ...glassStyle, padding: '16px' }}>
                    <div style={monoLabel}>IMPULSE RESPONSE → {selectedTarget || data.tickers[0]}</div>
                    <Plot 
                        data={data.tickers.map((source, i) => ({
                            x: Array.from({ length: data.horizon + 1 }, (_, k) => k),
                            y: data.irf[selectedTarget || data.tickers[0]]?.[source] || [],
                            name: `Shock: ${source}`,
                            type: 'scatter', mode: 'lines+markers',
                            line: { width: 2 }, marker: { size: 4 }
                        }))}
                        layout={{ 
                            height: 350, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                            margin: { t: 20, b: 50, l: 50, r: 100 }, font: { color: '#5a6578' },
                            xaxis: { title: 'Days After Shock', gridcolor: '#1e2738' },
                            yaxis: { title: 'Response', gridcolor: '#1e2738' },
                            legend: { font: { size: 10 }, x: 1.02, y: 1 }
                        }}
                        style={{ width: '100%' }}
                    />
                </div>
            </div>
        </div>
    );
};

const VolPanel = ({ data, loading }) => {
    if (loading) return <LoadingState />;
    if (!data) return <EmptyState label="RUN GARCH ANALYSIS" />;

    return (
        <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
            <div>
                <div style={monoLabel}>GARCH(1,1) PARAMETERS ({data.ticker})</div>
                <div style={{ display: 'grid', gap: '8px', marginTop: '12px' }}>
                    <StatCard label="ω (Omega)" value={data.params.omega} />
                    <StatCard label="α (Alpha)" value={data.params.alpha} />
                    <StatCard label="β (Beta)" value={data.params.beta} />
                    <StatCard label="Persistence (α+β)" value={data.persistence} pass={data.persistence < 0.99} threshold="< 1.0" />
                </div>

                <div style={{ marginTop: '16px' }}>
                    <div style={monoLabel}>VOLATILITY STATE</div>
                    <div style={{ display: 'grid', gap: '8px', marginTop: '8px' }}>
                        <StatCard label="Current Vol" value={data.current_vol_pct} unit="%" />
                        <StatCard label="Percentile" value={data.vol_percentile} unit="%" pass={data.vol_percentile < 80} />
                        <StatCard label="LR Vol" value={data.unconditional_vol_pct} unit="%" />
                    </div>
                </div>

                <div style={{ marginTop: '16px' }}>
                    <div style={monoLabel}>RESIDUAL DIAGNOSTICS</div>
                    <div style={{ display: 'grid', gap: '6px', marginTop: '8px' }}>
                        <TestResult label="Jarque-Bera" stat={data.residual_diagnostics.jarque_bera_stat} pValue={data.residual_diagnostics.jarque_bera_p} pass={data.residual_diagnostics.residuals_normal} />
                    </div>
                    <div style={{ fontSize: '9px', color: '#5a6578', marginTop: '4px' }}>
                        Skew: {data.residual_diagnostics.skewness.toFixed(3)} | Kurt: {data.residual_diagnostics.excess_kurtosis.toFixed(3)}
                    </div>
                </div>
            </div>

            <div>
                <div style={{ ...glassStyle, padding: '16px', marginBottom: '16px' }}>
                    <div style={monoLabel}>{data.forecast.horizon_days}-DAY VOLATILITY FORECAST</div>
                    <Plot 
                        data={[{
                            x: Array.from({ length: data.forecast.volatility_pct.length }, (_, i) => i + 1),
                            y: data.forecast.volatility_pct,
                            type: 'scatter', fill: 'tozeroy', fillcolor: 'rgba(59, 130, 246, 0.1)', line: { color: '#3b82f6', width: 2 }
                        }]}
                        layout={{ height: 200, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { t: 10, b: 40, l: 50, r: 20 }, font: { color: '#5a6578' }, xaxis: { title: 'Days', gridcolor: '#1e2738' }, yaxis: { title: 'σ (%)', gridcolor: '#1e2738' } }}
                        style={{ width: '100%' }}
                    />
                </div>

                <div style={{ ...glassStyle, padding: '16px' }}>
                    <div style={monoLabel}>CONDITIONAL VOLATILITY (HISTORICAL)</div>
                    <Plot 
                        data={[{
                            y: data.conditional_vol_series,
                            type: 'scatter', mode: 'lines', line: { color: '#f59e0b', width: 1 }
                        }]}
                        layout={{ height: 180, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { t: 10, b: 30, l: 50, r: 20 }, font: { color: '#5a6578' }, xaxis: { showgrid: false }, yaxis: { title: 'σ (%)', gridcolor: '#1e2738' } }}
                        style={{ width: '100%' }}
                    />
                </div>
            </div>
        </div>
    );
};

// ============== MAIN PAGE ==============

export default function ResearchPage() {
    const [mode, setMode] = useState('stats'); // 'stats' or 'quant'
    const [activeTab, setActiveTab] = useState('stationarity');
    const [config, setConfig] = useState({
        tickers: 'SPY, QQQ, GLD, TLT',
        lookback: '504',
        horizon: 21,
        maxLag: 5
    });
    const [results, setResults] = useState({});
    const [loading, setLoading] = useState(false);
    const [calcLog, setCalcLog] = useState([]);

    const addLog = (msg, type = 'info') => {
        const time = new Date().toLocaleTimeString('en-US', { hour12: false }).slice(0, 8);
        setCalcLog(prev => [...prev.slice(-20), { time, msg, type }]);
    };

    const runEngine = useCallback(async () => {
        setLoading(true);
        addLog(`Starting ${activeTab.toUpperCase()}...`);
        
        try {
            const tickerList = config.tickers.split(',').map(t => t.trim().toUpperCase());
            const payload = {
                ticker: tickerList[0],
                tickers: tickerList,
                lookback: parseInt(config.lookback),
                horizon: config.horizon,
                max_lag: config.maxLag
            };

            const urls = {
                stationarity: '/research/stats/stationarity',
                cointegration: '/research/stats/cointegration',
                causality: '/research/stats/causality',
                distribution: '/research/stats/distribution',
                entropy: '/research/stats/entropy',
                var: '/research/stats/var_models',
                volatility: '/research/stats/vol_garch'
            };

            addLog(`POST ${urls[activeTab]}`);
            const response = await fetch(`${API_BASE_URL}${urls[activeTab]}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${response.status}`);
            }
            
            const resp = await response.json();
            
            if (resp.error) {
                addLog(`ERROR: ${resp.error.message || resp.error.code || 'Unknown'}`, 'error');
            } else {
                addLog(`OK: ${resp.n_observations || 'N/A'} obs`, 'success');
                setResults(prev => ({ ...prev, [activeTab]: resp }));
            }
        } catch (err) {
            addLog(`FAIL: ${err.message}`, 'error');
            console.error("ENGINE ERROR:", err);
        } finally {
            setLoading(false);
        }
    }, [activeTab, config]);

    useEffect(() => {
        if (!results[activeTab]) {
            runEngine();
        }
    }, [activeTab, results, runEngine]);

    return (
        <div style={{ height: '100%', display: 'flex', overflow: 'hidden', background: '#020617' }}>
            <Sidebar config={config} setConfig={setConfig} onRun={runEngine} loading={loading} calcLog={calcLog} />

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                {/* TOOLBAR with Toggle */}
                <div style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
                    <h1 style={{ fontSize: '16px', fontWeight: 800, color: '#fff', letterSpacing: '0.05em', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <BarChart2 size={18} className="text-blue-500" />
                        OMEGA RESEARCH ENGINE
                    </h1>
                    
                    {/* Mode Toggle - Simplified to Statistical Only */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <div style={{ 
                            display: 'flex', background: 'rgba(0,0,0,0.4)', borderRadius: '8px', padding: '4px',
                            border: '1px solid #1e2738'
                        }}>
                            <button
                                style={{
                                    padding: '8px 16px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                                    background: 'linear-gradient(90deg, #3b82f6 0%, #2563eb 100%)',
                                    color: '#fff',
                                    fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em',
                                    transition: 'all 0.2s'
                                }}
                            >
                                STATISTICAL
                            </button>
                        </div>
                        <div style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: '#5a6578' }}>
                            v4.5
                        </div>
                    </div>
                </div>

                {/* TAB NAV - Statistical Modules Only */}
                <div style={{ padding: '8px', display: 'flex', gap: '4px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
                    {STATS_MODULES.map(mod => (
                        <button 
                            key={mod.id}
                            onClick={() => setActiveTab(mod.id)}
                            style={{ 
                                flex: 1, padding: '10px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                                background: activeTab === mod.id ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                                border: `1px solid ${activeTab === mod.id ? 'rgba(59, 130, 246, 0.3)' : 'transparent'}`
                            }}
                        >
                            <mod.icon size={14} color={activeTab === mod.id ? '#3b82f6' : '#5a6578'} />
                            <span style={{ fontSize: '10px', fontWeight: activeTab === mod.id ? 700 : 500, color: activeTab === mod.id ? '#fff' : '#5a6578' }}>
                                {mod.label.toUpperCase()}
                            </span>
                        </button>
                    ))}
                </div>

                {/* WORKBENCH */}
                <div style={{ flex: 1, overflowY: 'auto', ...glassStyle, margin: '8px', borderRadius: '8px' }}>
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={activeTab}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            transition={{ duration: 0.2 }}
                        >
                            {activeTab === 'stationarity' && <StationarityPanel data={results.stationarity} loading={loading} />}
                            {activeTab === 'cointegration' && <CointegrationPanel data={results.cointegration} loading={loading} />}
                            {activeTab === 'causality' && <CausalityPanel data={results.causality} loading={loading} />}
                            {activeTab === 'entropy' && <EntropyPanel data={results.entropy} loading={loading} />}
                            {activeTab === 'distribution' && <DistributionPanel data={results.distribution} loading={loading} />}
                            {activeTab === 'volatility' && <VolPanel data={results.volatility} loading={loading} />}
                        </motion.div>
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
}
