"use client";

import React, { useState, useEffect, useCallback } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { useRouter } from 'next/navigation';
import { runFactors, runVolatility, runRegimes, runPCA, getFactorScreen, fetchRegistryStatus, fetchScreener } from '@/lib/api';
import TerminalPanel from '@/components/TerminalPanel';
import PageGrid from '@/components/PageGrid';
import { PlotlyChart } from '@/components/ui/plotly-chart';
import { LineChart, Line, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { 
    Search, Globe, Layers, Activity, RefreshCw, Cpu, 
    Filter, Zap, Brain, Landmark, Database, 
    Circle, Clock, LayoutGrid
} from 'lucide-react';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import ScreenerQuant360 from '@/components/labs/ScreenerQuant360';
import VolatilityHubPage from './volatility/page';
import FactorsHubPage from './factors/page';
import PCAEigenphysicsLab from '@/components/labs/PCAEigenphysicsLab';
import PCAGodModeLab from '@/components/labs/PCAGodModeLab';
import MLLabDashboard from '@/components/labs/MLLabDashboard';
import QuantitativeLab from '@/components/labs/QuantitativeLab';

import ResearchPage from './research/page';
import RegimesHubPage from './regimes/page';
// Strategy Lab has been deprecated - use /labs/studio for Sovereign Algo Studio


const TABS = [
    { id: "research", label: "RESEARCH", icon: Globe },
    { id: "factors", label: "FACTORS", icon: Layers },
    { id: "volatility", label: "VOL", icon: Activity },
    { id: "regimes", label: "REGIMES", icon: RefreshCw },
    { id: "pca", label: "PCA", icon: Cpu },
    { id: "screener", label: "SCREENER", icon: Filter },
    { id: "quant", label: "QUANT", icon: Zap },
    { id: "ml", label: "ML", icon: Brain },
];

function ClientTime() {
    const [time, setTime] = useState("");

    useEffect(() => {
        const update = () => setTime(new Date().toLocaleTimeString('en-US', { hour12: false }));
        update();
        const interval = setInterval(update, 1000);
        return () => clearInterval(interval);
    }, []);

    return <span>{time || "--:--:--"}</span>;
}


export default function LabsPage() {
    const [activeTab, setActiveTab] = useState("research");

    return (
        <PageGrid>
            <div className="col-span-12 h-full">
                <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
                    <div style={{
                        background: 'var(--terminal-darker)',
                        borderBottom: '1px solid var(--border)',
                        position: 'relative',
                    }}>
                        <div style={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            height: '1px',
                            background: 'linear-gradient(90deg, transparent 0%, rgba(255, 214, 10, 0.2) 50%, transparent 100%)',
                        }} />

                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            padding: '0 16px',
                            gap: '4px',
                        }}>
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '12px 16px 12px 0',
                                borderRight: '1px solid rgba(30, 39, 56, 0.5)',
                                marginRight: '8px',
                            }}>
                                <div style={{
                                    width: '8px',
                                    height: '8px',
                                    borderRadius: '50%',
                                    background: 'var(--terminal-green)',
                                    boxShadow: '0 0 8px rgba(0, 255, 136, 0.5)',
                                    animation: 'pulse-glow 2s ease-in-out infinite',
                                }} />
                                <span style={{
                                    fontWeight: 700,
                                    letterSpacing: '0.15em',
                                    color: 'var(--terminal-yellow)',
                                    textShadow: '0 0 10px rgba(255, 214, 10, 0.3)',
                                }}>
                                    QUANT LAB
                                </span>
                            </div>

                            <Tabs.List className="flex items-center overflow-x-auto no-scrollbar scroll-smooth" style={{ WebkitOverflowScrolling: 'touch' }}>
                                {TABS.map((tab) => (
                                    <Tabs.Trigger
                                        key={tab.id}
                                        value={tab.id}
                                        style={{
                                            fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                                            fontSize: '11px',
                                            letterSpacing: '0.15em',
                                            textTransform: 'uppercase',
                                            padding: '14px 20px',
                                            color: activeTab === tab.id ? 'var(--terminal-yellow)' : 'var(--terminal-dim)',
                                            background: activeTab === tab.id
                                                ? 'rgba(255, 214, 10, 0.05)'
                                                : 'transparent',
                                            borderBottom: activeTab === tab.id
                                                ? '2px solid var(--terminal-yellow)'
                                                : '2px solid transparent',
                                            transition: 'all 0.3s ease',
                                            cursor: 'pointer',
                                            display: 'flex',
                                            alignItems: 'center',
                                            position: 'relative',
                                            fontWeight: activeTab === tab.id ? '700' : '500',
                                        }}
                                        onMouseEnter={(e) => {
                                            if (activeTab !== tab.id) {
                                                e.currentTarget.style.color = 'var(--foreground)';
                                            }
                                        }}
                                        onMouseLeave={(e) => {
                                            if (activeTab !== tab.id) {
                                                e.currentTarget.style.color = 'var(--terminal-dim)';
                                            }
                                        }}
                                    >
                                        {tab.label}
                                    </Tabs.Trigger>
                                ))}
                            </Tabs.List>

                            <div style={{
                                marginLeft: 'auto',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '12px',
                                padding: '8px 0',
                            }}>
                                <div style={{
                                    fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                                    fontSize: '9px',
                                    color: '#5a6578',
                                    letterSpacing: '0.05em',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px'
                                }}>
                                    <Circle size={8} fill="#00d4ff" stroke="none" /> LIVE
                                </div>
                                <div style={{
                                    fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                                    fontSize: '10px',
                                    color: 'var(--terminal-dim)',
                                    padding: '4px 10px',
                                    background: 'var(--terminal-dark)',
                                    borderRadius: '3px',
                                    border: '1px solid var(--border)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px'
                                }}>
                                    <Clock size={10} />
                                    <ClientTime />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex-1 overflow-auto p-4" style={{
                        background: 'var(--background)',
                    }}>
                        <Tabs.Content value="research" className="h-full outline-none">
                            <div className="h-full" style={{
                                background: 'var(--card)',
                                border: '1px solid var(--border)',
                                borderRadius: '6px',
                                overflow: 'hidden',
                            }}>
                                <ResearchPage />
                            </div>
                        </Tabs.Content>
                        <Tabs.Content value="factors" className="h-full outline-none">
                            <FactorsHubPage />
                        </Tabs.Content>
                        <Tabs.Content value="volatility" className="h-full outline-none">
                            <VolatilityHubPage />
                        </Tabs.Content>
                        <Tabs.Content value="regimes" className="h-full outline-none">
                            <RegimesHubPage />
                        </Tabs.Content>
                        <Tabs.Content value="pca" className="h-full outline-none">
                            <PCAGodModeLab />
                        </Tabs.Content>
                        <Tabs.Content value="screener" className="h-full outline-none">
                            <ScreenerQuant360 />
                        </Tabs.Content>

                        <Tabs.Content value="quant" className="h-full outline-none">
                            <QuantitativeLab />
                        </Tabs.Content>
                        <Tabs.Content value="ml" className="h-full outline-none">
                            <MLLabDashboard />
                        </Tabs.Content>
                        <Tabs.Content value="macro" className="h-full outline-none">
                            <MacroControlEmbed />
                        </Tabs.Content>
                        <Tabs.Content value="registry" className="h-full outline-none">
                            <RegistryLab />
                        </Tabs.Content>

                    </div>
                </Tabs.Root>
            </div>
        </PageGrid>
    );
}

// --- FACTORS LAB ---
function FactorsLab() {
    const [ticker, setTicker] = useState("AAPL");
    const [window, setWindow] = useState(3);
    const [model, setModel] = useState("ff3");
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await runFactors(ticker, window, model);
            setData(res);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-12 gap-4 h-full">
            <div className="col-span-12 flex gap-4 items-center bg-terminal-dark border border-terminal-gray p-4 shrink-0">
                <div style={{ width: 200 }}>
                    <TradingViewSearch
                        mode="security"
                        onSelect={setTicker}
                        placeholder="Search equities..."
                    />
                </div>
                <div className="flex items-center gap-2 px-3 py-1 bg-terminal-black border border-terminal-gray text-terminal-text font-mono text-sm">
                    <span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span>
                    <span className="text-terminal-dim text-xs">{getSymbolInfo(ticker)?.exchange || 'US'}</span>
                </div>
                <select
                    value={window}
                    onChange={e => setWindow(Number(e.target.value))}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1 font-mono text-sm focus:border-terminal-yellow outline-none"
                >
                    <option value={1}>1 Year</option>
                    <option value={3}>3 Years</option>
                    <option value={5}>5 Years</option>
                </select>
                <select
                    value={model}
                    onChange={e => setModel(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1 font-mono text-sm focus:border-terminal-yellow outline-none"
                >
                    <option value="ff3">Fama-French 3</option>
                    <option value="ff5">Fama-French 5</option>
                    <option value="ff5_mom">FF5 + Momentum</option>
                    <option value="momentum">Momentum Only</option>
                </select>
                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="bg-terminal-yellow text-terminal-black px-6 py-1 font-mono text-sm font-bold hover:bg-yellow-400 disabled:opacity-50 transition-colors"
                >
                    {loading ? "RUNNING..." : "RUN REGRESSION"}
                </button>
            </div>

            {error && <div className="col-span-12 text-red-500 font-mono p-4 border border-red-900 bg-red-900/20">{error}</div>}

            {!data && !loading && !error && (
                <div className="col-span-12 text-terminal-dim font-mono p-8 text-center border border-terminal-gray border-dashed">
                    Select parameters and run factor regression to see exposures.
                </div>
            )}

            {data && (
                <>
                    <div className="col-span-12 md:col-span-8 h-96">
                        <TerminalPanel title="CUMULATIVE RETURNS (ASSET VS MODEL)">
                            <PlotlyChart
                                data={[
                                    { x: data.dates, y: data.asset_cum_ret, type: 'scattergl', mode: 'lines', name: 'Asset', line: { color: '#00ff6a', width: 1.5 } },
                                    { x: data.dates, y: data.model_cum_ret, type: 'scattergl', mode: 'lines', name: 'Model', line: { color: '#ff9f1c', width: 1.5, dash: 'dot' } }
                                ]}
                                layout={{
                                    hovermode: 'x unified',
                                    xaxis: { showgrid: true, gridcolor: '#333' },
                                    yaxis: { showgrid: true, gridcolor: '#333', title: 'Cumulative Return' },
                                    legend: { orientation: 'h', y: 1.1 }
                                }}
                            />
                        </TerminalPanel>
                    </div>
                    <div className="col-span-12 md:col-span-4 flex flex-col gap-4">
                        <div className="h-48">
                            <TerminalPanel title="FACTOR BETAS">
                                <PlotlyChart
                                    data={[{
                                        x: Object.keys(data.betas),
                                        y: Object.values(data.betas),
                                        type: 'bar',
                                        marker: { color: Object.values(data.betas).map(v => v >= 0 ? '#00bfff' : '#ff3b3b') }
                                    }]}
                                    layout={{
                                        xaxis: { showgrid: false },
                                        yaxis: { showgrid: true, gridcolor: '#333' },
                                        margin: { t: 10, r: 10, b: 30, l: 40 }
                                    }}
                                />
                            </TerminalPanel>
                        </div>
                        <div className="bg-terminal-dark border border-terminal-gray p-4 flex-1 overflow-auto">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-terminal-dim text-xs uppercase">R-Squared</span>
                                <span className="text-terminal-yellow font-mono">{(data.r_squared * 100).toFixed(1)}%</span>
                            </div>
                            <div className="flex justify-between items-center mb-4">
                                <span className="text-terminal-dim text-xs uppercase">Alpha (Ann.)</span>
                                <span className={`font-mono ${data.alpha_annualized >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                    {(data.alpha_annualized * 100).toFixed(2)}%
                                </span>
                            </div>
                            <table className="w-full text-sm font-mono">
                                <thead>
                                    <tr className="text-terminal-dim border-b border-terminal-gray">
                                        <th className="text-left py-1">Factor</th>
                                        <th className="text-right py-1">Beta</th>
                                        <th className="text-right py-1">T-Stat</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {Object.keys(data.betas).map(f => (
                                        <tr key={f} className="border-b border-terminal-gray/30">
                                            <td className="py-1">{f}</td>
                                            <td className={`text-right py-1 ${data.betas[f] >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>{data.betas[f].toFixed(2)}</td>
                                            <td className="text-right py-1 text-terminal-dim">{data.t_stats[f]?.toFixed(2) || "N/A"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

// --- VOLATILITY LAB ---
function VolatilityLab() {
    const [ticker, setTicker] = useState("SPY");
    const [window, setWindow] = useState(1);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await runVolatility(ticker, window);
            setData(res);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-12 gap-4 h-full">
            <div className="col-span-12 flex gap-4 items-center bg-terminal-dark border border-terminal-gray p-4 shrink-0">
                <div style={{ width: 200 }}>
                    <TradingViewSearch
                        mode="security"
                        onSelect={setTicker}
                        placeholder="Search equities..."
                    />
                </div>
                <div className="flex items-center gap-2 px-3 py-1 bg-terminal-black border border-terminal-gray text-terminal-text font-mono text-sm">
                    <span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span>
                    <span className="text-terminal-dim text-xs">{getSymbolInfo(ticker)?.exchange || 'US'}</span>
                </div>
                <select
                    value={window}
                    onChange={e => setWindow(Number(e.target.value))}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1 font-mono text-sm focus:border-terminal-yellow outline-none"
                >
                    <option value={1}>1 Year</option>
                    <option value={3}>3 Years</option>
                </select>
                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="bg-terminal-yellow text-terminal-black px-6 py-1 font-mono text-sm font-bold hover:bg-yellow-400 disabled:opacity-50 transition-colors"
                >
                    {loading ? "RUNNING..." : "RUN ANALYSIS"}
                </button>
            </div>

            {error && <div className="col-span-12 text-red-500 font-mono p-4 border border-red-900 bg-red-900/20">{error}</div>}

            {!data && !loading && !error && (
                <div className="col-span-12 text-terminal-dim font-mono p-8 text-center border border-terminal-gray border-dashed">
                    No volatility data yet. Run analysis to see results.
                </div>
            )}

            {data && (
                <>
                    <div className="col-span-12 h-96">
                        <TerminalPanel title="VOLATILITY MODELS">
                            <PlotlyChart
                                data={[
                                    { x: data.dates, y: data.realized_vol, type: 'scattergl', mode: 'lines', name: 'Realized (21d)', line: { color: '#00ff6a', width: 1 } },
                                    { x: data.dates, y: data.ewma_vol, type: 'scattergl', mode: 'lines', name: 'EWMA', line: { color: '#00bfff', width: 1 } },
                                    { x: data.dates, y: data.garch_vol, type: 'scattergl', mode: 'lines', name: 'GARCH(1,1)', line: { color: '#ff9f1c', width: 1 } }
                                ]}
                                layout={{
                                    hovermode: 'x unified',
                                    xaxis: { showgrid: true, gridcolor: '#333' },
                                    yaxis: { showgrid: true, gridcolor: '#333', tickformat: '.1%' },
                                    legend: { orientation: 'h', y: 1.1 }
                                }}
                            />
                        </TerminalPanel>
                    </div>
                    <div className="col-span-12 grid grid-cols-3 gap-4">
                        <div className="bg-terminal-dark border border-terminal-gray p-4">
                            <div className="text-terminal-dim text-xs uppercase tracking-wider mb-1">Current Realized</div>
                            <div className="text-2xl font-mono text-terminal-green">
                                {(data.realized_vol[data.realized_vol.length - 1] * 100).toFixed(2)}%
                            </div>
                        </div>
                        <div className="bg-terminal-dark border border-terminal-gray p-4">
                            <div className="text-terminal-dim text-xs uppercase tracking-wider mb-1">Current EWMA</div>
                            <div className="text-2xl font-mono text-terminal-blue">
                                {(data.ewma_vol[data.ewma_vol.length - 1] * 100).toFixed(2)}%
                            </div>
                        </div>
                        <div className="bg-terminal-dark border border-terminal-gray p-4">
                            <div className="text-terminal-dim text-xs uppercase tracking-wider mb-1">GARCH Forecast (21d)</div>
                            <div className="text-2xl font-mono text-terminal-yellow">
                                {(data.garch_forecast_21d * 100).toFixed(2)}%
                            </div>
                            <div className="text-terminal-dim text-[10px] mt-1">
                                &omega;: {data.garch_params.omega.toFixed(6)}, &alpha;: {data.garch_params['alpha[1]'].toFixed(4)}, &beta;: {data.garch_params['beta[1]'].toFixed(4)}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

// --- REGIMES LAB ---
function RegimesLab() {
    const [ticker, setTicker] = useState("SPY");
    const [window, setWindow] = useState(3);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await runRegimes(ticker, window);
            setData(res);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-12 gap-4 h-full">
            <div className="col-span-12 flex gap-4 items-center bg-terminal-dark border border-terminal-gray p-4 shrink-0">
                <div style={{ width: 200 }}>
                    <TradingViewSearch
                        mode="security"
                        onSelect={setTicker}
                        placeholder="Search equities..."
                    />
                </div>
                <div className="flex items-center gap-2 px-3 py-1 bg-terminal-black border border-terminal-gray text-terminal-text font-mono text-sm">
                    <span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span>
                    <span className="text-terminal-dim text-xs">{getSymbolInfo(ticker)?.exchange || 'US'}</span>
                </div>
                <select
                    value={window}
                    onChange={e => setWindow(Number(e.target.value))}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1 font-mono text-sm focus:border-terminal-yellow outline-none"
                >
                    <option value={3}>3 Years</option>
                    <option value={5}>5 Years</option>
                </select>
                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="bg-terminal-yellow text-terminal-black px-6 py-1 font-mono text-sm font-bold hover:bg-yellow-400 disabled:opacity-50 transition-colors"
                >
                    {loading ? "RUNNING..." : "DETECT REGIMES"}
                </button>
            </div>

            {error && <div className="col-span-12 text-red-500 font-mono p-4 border border-red-900 bg-red-900/20">{error}</div>}

            {!data && !loading && !error && (
                <div className="col-span-12 text-terminal-dim font-mono p-8 text-center border border-terminal-gray border-dashed">
                    Run regime detection to see market states.
                </div>
            )}

            {data && (
                <>
                    <div className="col-span-12 md:col-span-8 h-96">
                        <TerminalPanel title="MARKET REGIMES">
                            <PlotlyChart
                                data={[{
                                    x: data.dates,
                                    y: data.prices,
                                    type: 'scattergl',
                                    mode: 'markers',
                                    marker: {
                                        color: data.regime_labels.map(l => l === 0 ? '#00ff6a' : '#ff3b3b'),
                                        size: 3
                                    },
                                    name: 'Price'
                                }]}
                                layout={{
                                    xaxis: { showgrid: true, gridcolor: '#333' },
                                    yaxis: { showgrid: true, gridcolor: '#333' }
                                }}
                            />
                        </TerminalPanel>
                    </div>
                    <div className="col-span-12 md:col-span-4 flex flex-col gap-4">
                        <div className="bg-terminal-dark border border-terminal-gray p-4">
                            <div className="text-terminal-dim text-xs uppercase tracking-wider mb-2">Regime Statistics</div>
                            <table className="w-full text-sm font-mono">
                                <thead>
                                    <tr className="text-terminal-dim border-b border-terminal-gray">
                                        <th className="text-left py-1">Regime</th>
                                        <th className="text-right py-1">Ret</th>
                                        <th className="text-right py-1">Vol</th>
                                        <th className="text-right py-1">Prob</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr className="border-b border-terminal-gray/30">
                                        <td className="py-1 text-terminal-green">0 (Calm)</td>
                                        <td className="text-right py-1">{(data.regime_stats["0"].mean_return * 252 * 100).toFixed(1)}%</td>
                                        <td className="text-right py-1">{(data.regime_stats["0"].volatility * 100).toFixed(1)}%</td>
                                        <td className="text-right py-1">{(data.regime_stats["0"].probability * 100).toFixed(0)}%</td>
                                    </tr>
                                    <tr>
                                        <td className="py-1 text-terminal-red">1 (Stressed)</td>
                                        <td className="text-right py-1">{(data.regime_stats["1"].mean_return * 252 * 100).toFixed(1)}%</td>
                                        <td className="text-right py-1">{(data.regime_stats["1"].volatility * 100).toFixed(1)}%</td>
                                        <td className="text-right py-1">{(data.regime_stats["1"].probability * 100).toFixed(0)}%</td>
                                    </tr>
                                </tbody>
                            </table>
                            <div className="text-terminal-dim text-xs mt-4 italic">
                                Regime 0 is characterized by lower volatility and typically positive returns. Regime 1 indicates high volatility stress.
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

// --- PCA LAB ---
function PCALab() {
    const [universe, setUniverse] = useState("majors");
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const runAnalysis = async () => {
        setLoading(true);
        setError(null);
        try {
            let tickers = [];
            if (universe === "majors") tickers = ["SPY", "QQQ", "DIA", "IWM", "TLT", "GLD"];
            else if (universe === "sectors") tickers = ["XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE"];
            else if (universe === "tech") tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD"];

            const res = await runPCA(tickers);
            setData(res);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-12 gap-4 h-full">
            <div className="col-span-12 flex gap-4 items-center bg-terminal-dark border border-terminal-gray p-4 shrink-0">
                <select
                    value={universe}
                    onChange={e => setUniverse(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1 font-mono text-sm focus:border-terminal-yellow outline-none"
                >
                    <option value="majors">US Majors (Indices + Bonds + Gold)</option>
                    <option value="sectors">US Sectors (SPDRs)</option>
                    <option value="tech">Big Tech</option>
                </select>
                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="bg-terminal-yellow text-terminal-black px-6 py-1 font-mono text-sm font-bold hover:bg-yellow-400 disabled:opacity-50 transition-colors"
                >
                    {loading ? "RUNNING..." : "RUN PCA"}
                </button>
            </div>

            {error && <div className="col-span-12 text-red-500 font-mono p-4 border border-red-900 bg-red-900/20">{error}</div>}

            {!data && !loading && !error && (
                <div className="col-span-12 text-terminal-dim font-mono p-8 text-center border border-terminal-gray border-dashed">
                    Select a universe and run PCA to see principal components.
                </div>
            )}

            {data && (
                <>
                    <div className="col-span-12 md:col-span-6 h-80">
                        <TerminalPanel title="EXPLAINED VARIANCE">
                            <PlotlyChart
                                data={[{
                                    x: data.component_labels,
                                    y: data.explained_variance,
                                    type: 'bar',
                                    marker: { color: '#00bfff' }
                                }]}
                                layout={{
                                    xaxis: { showgrid: false },
                                    yaxis: { showgrid: true, gridcolor: '#333', tickformat: '.1%' }
                                }}
                            />
                        </TerminalPanel>
                    </div>
                    <div className="col-span-12 md:col-span-6 h-80">
                        <TerminalPanel title="PC1 LOADINGS (MARKET FACTOR)">
                            <PlotlyChart
                                data={[{
                                    x: Object.keys(data.loadings),
                                    y: Object.keys(data.loadings).map(k => data.loadings[k].PC1),
                                    type: 'bar',
                                    marker: { color: Object.keys(data.loadings).map(k => data.loadings[k].PC1 >= 0 ? '#00ff6a' : '#ff3b3b') }
                                }]}
                                layout={{
                                    xaxis: { showgrid: false },
                                    yaxis: { showgrid: true, gridcolor: '#333' }
                                }}
                            />
                        </TerminalPanel>
                    </div>
                    <div className="col-span-12 h-80">
                        <TerminalPanel title="PRINCIPAL COMPONENTS OVER TIME">
                            <PlotlyChart
                                data={[
                                    { x: data.dates, y: data.pc1, type: 'scattergl', mode: 'lines', name: 'PC1', line: { color: '#00ff6a', width: 1 } },
                                    { x: data.dates, y: data.pc2, type: 'scattergl', mode: 'lines', name: 'PC2', line: { color: '#ff9f1c', width: 1 } }
                                ]}
                                layout={{
                                    hovermode: 'x unified',
                                    xaxis: { showgrid: true, gridcolor: '#333' },
                                    yaxis: { showgrid: true, gridcolor: '#333' }
                                }}
                            />
                        </TerminalPanel>
                    </div>
                </>
            )}
        </div>
    );
}
// --- SCREENER LAB ---
function ScreenerLab() {
    const router = useRouter();
    const [data, setData] = useState(null);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Filters
    const [sector, setSector] = useState('');
    const [liquidity, setLiquidity] = useState('');
    const [volBucket, setVolBucket] = useState('');

    // Sorting
    const [sortBy, setSortBy] = useState('change_pct');
    const [sortDir, setSortDir] = useState('desc');

    // Pagination
    const [limit] = useState(50);
    const [offset, setOffset] = useState(0);

    const runScreen = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetchScreener({
                sector: sector || undefined,
                liquidity: liquidity || undefined,
                vol_bucket: volBucket || undefined,
                sort_by: sortBy,
                sort_dir: sortDir,
                limit,
                offset
            });
            setData(res.results);
            setTotal(res.total);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [sector, liquidity, volBucket, sortBy, sortDir, limit, offset]);

    useEffect(() => {
        runScreen();
    }, [runScreen]);

    const handleSort = (field) => {
        if (sortBy === field) {
            setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
        } else {
            setSortBy(field);
            setSortDir('desc');
        }
        setOffset(0);
    };

    const handleRowClick = (symbol) => {
        router.push(`/security?symbol=${symbol}`);
    };

    const formatVolume = (v) => {
        if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
        if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
        if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
        return v.toString();
    };

    const SortHeader = ({ field, children }) => (
        <th
            onClick={() => handleSort(field)}
            className="text-right py-2 px-2 cursor-pointer hover:text-terminal-yellow select-none"
        >
            {children}
            {sortBy === field && (
                <span className="ml-1 text-terminal-yellow">{sortDir === 'desc' ? '↓' : '↑'}</span>
            )}
        </th>
    );

    const Sparkline = ({ data: sparkData, positive }) => {
        const chartData = sparkData.map((v, i) => ({ i, v }));
        return (
            <div style={{ width: 60, height: 26 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                        <Line
                            type="monotone"
                            dataKey="v"
                            stroke={positive ? '#00ff6a' : '#ff4260'}
                            strokeWidth={1.4}
                            dot={false}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        );
    };

    const SignalPill = ({ signal, label, bg }) => {
        if (!signal) return null;
        return (
            <span
                className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded mr-1"
                style={{ backgroundColor: bg, color: '#050608' }}
            >
                {label}
            </span>
        );
    };

    return (
        <div className="flex flex-col h-full gap-4">
            {/* Filter Bar */}
            <div className="flex gap-3 items-center bg-terminal-dark border border-terminal-gray p-4 shrink-0 flex-wrap">
                <select
                    value={sector}
                    onChange={e => { setSector(e.target.value); setOffset(0); }}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1.5 font-mono text-xs focus:border-terminal-yellow outline-none w-40"
                >
                    <option value="">All Sectors</option>
                    <option value="Technology">Technology</option>
                    <option value="Financials">Financials</option>
                    <option value="Healthcare">Healthcare</option>
                    <option value="Consumer Discretionary">Consumer Discretionary</option>
                    <option value="Consumer Staples">Consumer Staples</option>
                    <option value="Energy">Energy</option>
                    <option value="Communication Services">Communication Services</option>
                </select>

                <select
                    value={liquidity}
                    onChange={e => { setLiquidity(e.target.value); setOffset(0); }}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1.5 font-mono text-xs focus:border-terminal-yellow outline-none w-32"
                >
                    <option value="">All Liquidity</option>
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="LOW">LOW</option>
                    <option value="ILLIQUID">ILLIQUID</option>
                </select>

                <select
                    value={volBucket}
                    onChange={e => { setVolBucket(e.target.value); setOffset(0); }}
                    className="bg-terminal-black border border-terminal-gray text-terminal-text px-3 py-1.5 font-mono text-xs focus:border-terminal-yellow outline-none w-32"
                >
                    <option value="">All Vol</option>
                    <option value="LOW">LOW (&lt;15%)</option>
                    <option value="MEDIUM">MEDIUM (15-35%)</option>
                    <option value="HIGH">HIGH (&gt;35%)</option>
                </select>

                <div className="ml-auto flex items-center gap-2 text-terminal-dim text-xs">
                    <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
                    <button
                        onClick={() => setOffset(Math.max(0, offset - limit))}
                        disabled={offset === 0}
                        className="px-2 py-1 border border-terminal-gray disabled:opacity-30 hover:border-terminal-yellow"
                    >
                        Prev
                    </button>
                    <button
                        onClick={() => setOffset(offset + limit)}
                        disabled={offset + limit >= total}
                        className="px-2 py-1 border border-terminal-gray disabled:opacity-30 hover:border-terminal-yellow"
                    >
                        Next
                    </button>
                </div>
            </div>

            {error && <div className="text-red-500 font-mono p-4 border border-red-900 bg-red-900/20">{error}</div>}

            {/* Table */}
            <div className="flex-1 overflow-auto bg-terminal-dark border border-terminal-gray">
                <table className="w-full text-[13px] font-mono" style={{ borderCollapse: 'separate', borderSpacing: 0 }}>
                    <thead className="sticky top-0 z-10" style={{ backgroundColor: '#0d0f12', height: 42 }}>
                        <tr className="text-terminal-dim border-b border-terminal-gray">
                            <th className="text-left py-2 px-3">Ticker</th>
                            <th className="text-left py-2 px-2">Name</th>
                            <SortHeader field="price">Price</SortHeader>
                            <SortHeader field="change_pct">Chg%</SortHeader>
                            <SortHeader field="volume">Volume</SortHeader>
                            <th className="text-center py-2 px-2">Liquidity</th>
                            <th className="text-left py-2 px-2">Sector</th>
                            <SortHeader field="vol_20d">Vol 20d</SortHeader>
                            <SortHeader field="momentum_score">Mom</SortHeader>
                            <th className="text-center py-2 px-2">Spark</th>
                            <th className="text-center py-2 px-2">Signals</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading && !data && (
                            <tr><td colSpan={11} className="text-center py-8 text-terminal-dim animate-pulse">Loading...</td></tr>
                        )}
                        {data && data.map((row, i) => (
                            <tr
                                key={row.symbol}
                                onClick={() => handleRowClick(row.symbol)}
                                className="border-b border-terminal-gray/30 cursor-pointer transition-colors"
                                style={{
                                    height: 40,
                                    backgroundColor: i % 2 === 0 ? '#090b0f' : 'transparent'
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#0d0f12'}
                                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = i % 2 === 0 ? '#090b0f' : 'transparent'}
                            >
                                <td className="py-2 px-3 text-terminal-yellow font-bold">{row.symbol}</td>
                                <td className="py-2 px-2 text-terminal-dim truncate max-w-[100px]">{row.name}</td>
                                <td className="py-2 px-2 text-right text-terminal-text">${row.price.toFixed(2)}</td>
                                <td className={`py-2 px-2 text-right font-bold ${row.change_pct >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                    {row.change_pct >= 0 ? '+' : ''}{(row.change_pct * 100).toFixed(2)}%
                                </td>
                                <td className="py-2 px-2 text-right text-terminal-dim">{formatVolume(row.volume)}</td>
                                <td className="py-2 px-2 text-center">
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${row.liquidity === 'HIGH' ? 'bg-terminal-green/20 text-terminal-green' :
                                        row.liquidity === 'MEDIUM' ? 'bg-terminal-yellow/20 text-terminal-yellow' :
                                            row.liquidity === 'LOW' ? 'bg-orange-500/20 text-orange-400' :
                                                'bg-red-500/20 text-red-400'
                                        }`}>
                                        {row.liquidity}
                                    </span>
                                </td>
                                <td className="py-2 px-2 text-terminal-dim text-xs">{row.sector}</td>
                                <td className="py-2 px-2 text-right">{row.volatility.d20.toFixed(1)}%</td>
                                <td className={`py-2 px-2 text-right ${row.factors.momentum >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                    {row.factors.momentum >= 0 ? '+' : ''}{(row.factors.momentum * 100).toFixed(0)}%
                                </td>
                                <td className="py-2 px-2">
                                    <Sparkline data={row.sparkline} positive={row.change_pct >= 0} />
                                </td>
                                <td className="py-2 px-2 text-center whitespace-nowrap">
                                    <SignalPill signal={row.signals.momentum_high} label="MOMO" bg="#00ff6a" />
                                    <SignalPill signal={row.signals.oversold_rsi} label="RSI" bg="#f6c945" />
                                    <SignalPill signal={row.signals.volume_spike} label="VOL" bg="#b37bff" />
                                    <SignalPill signal={row.signals.earnings_soon} label="EPS" bg="#ff8c42" />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// --- REGISTRY LAB ---
function RegistryLab() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadRegistry();
        const interval = setInterval(loadRegistry, 5000);
        return () => clearInterval(interval);
    }, []);

    const loadRegistry = async () => {
        try {
            const res = await fetchRegistryStatus();
            setData(res);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-12 gap-4 h-full">
            <div className="col-span-12 flex justify-between items-center bg-terminal-dark border border-terminal-gray p-4 shrink-0">
                <h2 className="text-lg font-bold text-terminal-text">SERVICE REGISTRY STATUS</h2>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-terminal-dim">SYSTEM STATUS:</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${data?.system_status === 'operational' ? 'bg-terminal-green text-black' : 'bg-terminal-red text-black'
                        }`}>
                        {data?.system_status?.toUpperCase() || "UNKNOWN"}
                    </span>
                </div>
            </div>

            {error && <div className="col-span-12 text-red-500 font-mono p-4 border border-red-900 bg-red-900/20">{error}</div>}

            {loading && !data && (
                <div className="col-span-12 text-terminal-dim font-mono p-8 text-center animate-pulse">
                    Connecting to service registry...
                </div>
            )}

            {data && (
                <div className="col-span-12 bg-terminal-dark border border-terminal-gray p-0 overflow-auto">
                    <table className="w-full text-sm font-mono">
                        <thead className="bg-terminal-darker sticky top-0 z-10">
                            <tr className="text-terminal-dim border-b border-terminal-gray">
                                <th className="text-left py-3 px-4">Service Name</th>
                                <th className="text-left py-3 px-4">Type</th>
                                <th className="text-left py-3 px-4">Status</th>
                                <th className="text-right py-3 px-4">Latency</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.services.map((svc, i) => (
                                <tr key={i} className="border-b border-terminal-gray/30 hover:bg-terminal-gray/10 transition-colors">
                                    <td className="py-3 px-4 text-terminal-text font-bold">{svc.name}</td>
                                    <td className="py-3 px-4 text-terminal-dim">{svc.type}</td>
                                    <td className="py-3 px-4">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-2 h-2 rounded-full ${svc.status === 'operational' ? 'bg-terminal-green' : 'bg-terminal-red animate-pulse'}`}></div>
                                            <span className={svc.status === 'operational' ? 'text-terminal-green' : 'text-terminal-red'}>
                                                {svc.status.toUpperCase()}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="py-3 px-4 text-right text-terminal-text font-mono">{svc.latency}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

// --- ML LAB WITH SUB-TABS ---
function MLLabEmbed() {
    const [activeMLTab, setActiveMLTab] = useState('overview');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [healthData, setHealthData] = useState(null);
    
    const ML_TABS = [
        { id: 'overview', name: 'Overview', icon: '🧠' },
        { id: 'data', name: 'Data', icon: '📊' },
        { id: 'features', name: 'Features', icon: '🔧' },
        { id: 'supervised', name: 'Supervised', icon: '🎯' },
        { id: 'ensemble', name: 'Ensemble', icon: '🤝' },
        { id: 'summary', name: 'Summary', icon: '📋' }
    ];
    
    const ML_MODULES = [
        { id: 'data', name: 'Data', icon: '📊', desc: 'Signal Outcome Dataset Builder', step: 1 },
        { id: 'features', name: 'Features', icon: '🔧', desc: 'Feature Engineering & Validation', step: 2 },
        { id: 'supervised', name: 'Supervised', icon: '🎯', desc: 'Signal Success Probability', step: 3 },
        { id: 'conditional', name: 'Conditional', icon: '📈', desc: 'Conditional Performance', step: 3 },
        { id: 'ensemble', name: 'Ensemble', icon: '🤝', desc: 'Model Consensus', step: 4 },
        { id: 'explainability', name: 'Explainability', icon: '🔍', desc: 'Feature Attribution (SHAP)', step: 5 },
        { id: 'monitoring', name: 'Monitoring', icon: '📡', desc: 'Model Drift & Decay', step: 5 },
        { id: 'errors', name: 'Errors', icon: '⚠️', desc: 'Failure Regime Analyzer', step: 5 },
        { id: 'regimes', name: 'Regimes', icon: '🌊', desc: 'Market Regime Discovery', step: 5 },
        { id: 'clustering', name: 'Clustering', icon: '🔗', desc: 'Asset Similarity', step: 6 },
        { id: 'strategies', name: 'Strategies', icon: '🔀', desc: 'Strategy Overlap', step: 6 },
        { id: 'embedding', name: 'Embedding', icon: '🎨', desc: 'Feature Space Viz', step: 6 },
        { id: 'regime-quality', name: 'Quality', icon: '🎯', desc: 'Regime Separation', step: 6 },
        { id: 'summary', name: 'Summary', icon: '📋', desc: 'Signal Quality Scorecard', step: 7 },
        { id: 'position-sizing', name: 'Sizing', icon: '💰', desc: 'ML-Driven Position Advisor', step: 7 }
    ];
    
    // Fetch health data
    useEffect(() => {
        const fetchHealth = async () => {
            try {
                const res = await fetch('http://127.0.0.1:8000/api/ml/health');
                if (res.ok) {
                    const data = await res.json();
                    setHealthData(data);
                }
            } catch (e) {
                console.error('Failed to fetch ML health:', e);
            }
        };
        fetchHealth();
    }, []);

    return (
        <div className="h-full overflow-auto" style={{ background: 'linear-gradient(180deg, rgba(10, 15, 24, 0.9) 0%, rgba(6, 10, 16, 0.95) 100%)' }}>
            {/* Sub-Tab Header */}
            <div className="border-b border-gray-800 bg-[#0a0a0f]/80 sticky top-0 z-10">
                <div className="flex items-center gap-1 p-2 overflow-x-auto">
                    {ML_TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveMLTab(tab.id)}
                            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all whitespace-nowrap flex items-center gap-2 ${
                                activeMLTab === tab.id 
                                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50' 
                                : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                            }`}
                        >
                            <span>{tab.icon}</span>
                            <span>{tab.name}</span>
                        </button>
                    ))}
                </div>
            </div>
            
            <div className="p-6">
                {/* Overview Tab */}
                {activeMLTab === 'overview' && (
                    <div className="space-y-6">
                        {/* Header */}
                        <div>
                            <h1 className="text-2xl font-bold" style={{ background: 'linear-gradient(to right, #a855f7, #3b82f6, #06b6d4)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                                🧠 ML God Stack
                            </h1>
                            <p className="text-sm text-gray-400 mt-1">15-Module Machine Learning Infrastructure</p>
                        </div>
                        
                        {/* Status Cards */}
                        <div className="grid grid-cols-4 gap-4">
                            <div className="bg-[#12121a] border border-green-500/30 rounded-lg p-4">
                                <div className="text-xs text-gray-400 mb-1">System Status</div>
                                <div className="text-xl font-bold text-green-400">ONLINE</div>
                            </div>
                            <div className="bg-[#12121a] border border-purple-500/30 rounded-lg p-4">
                                <div className="text-xs text-gray-400 mb-1">Modules</div>
                                <div className="text-xl font-bold text-purple-400">15</div>
                            </div>
                            <div className="bg-[#12121a] border border-blue-500/30 rounded-lg p-4">
                                <div className="text-xs text-gray-400 mb-1">Active Models</div>
                                <div className="text-xl font-bold text-blue-400">{healthData?.cached_models || 0}</div>
                            </div>
                            <div className="bg-[#12121a] border border-cyan-500/30 rounded-lg p-4">
                                <div className="text-xs text-gray-400 mb-1">Datasets</div>
                                <div className="text-xl font-bold text-cyan-400">{healthData?.cached_datasets || 0}</div>
                            </div>
                        </div>

                        {/* Module Grid by Workflow Step */}
                        <div className="space-y-4">
                            {[1, 2, 3, 4, 5, 6, 7].map(step => {
                                const stepModules = ML_MODULES.filter(m => m.step === step);
                                if (stepModules.length === 0) return null;
                                const stepLabels = ['', 'Data Prep', 'Feature Eng', 'Training', 'Ensemble', 'Analysis', 'Discovery', 'Output'];
                                return (
                                    <div key={step}>
                                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                                            Step {step}: {stepLabels[step]}
                                        </div>
                                        <div className="grid grid-cols-5 gap-3">
                                            {stepModules.map((mod) => (
                                                <button
                                                    key={mod.id}
                                                    onClick={() => setActiveMLTab(mod.id === 'data' || mod.id === 'features' || mod.id === 'supervised' || mod.id === 'ensemble' || mod.id === 'summary' ? mod.id : 'overview')}
                                                    className="p-3 bg-[#12121a] border border-gray-800 rounded-lg hover:border-purple-500/50 transition-all text-left group"
                                                >
                                                    <span className="text-xl">{mod.icon}</span>
                                                    <div className="text-sm font-medium text-white mt-1 group-hover:text-purple-400 transition-colors">{mod.name}</div>
                                                    <div className="text-xs text-gray-500 mt-0.5 line-clamp-1">{mod.desc}</div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Quick Actions */}
                        <div className="p-4 bg-gradient-to-r from-purple-500/10 via-blue-500/10 to-cyan-500/10 border border-purple-500/20 rounded-lg">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="font-semibold text-white">Recommended Workflow</h3>
                                    <p className="text-sm text-gray-400">Data → Features → Supervised → Ensemble → Summary</p>
                                </div>
                                <button 
                                    onClick={() => setActiveMLTab('data')}
                                    className="px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded text-sm font-medium transition-colors"
                                >
                                    Start Workflow →
                                </button>
                            </div>
                        </div>
                    </div>
                )}
                
                {/* Data Tab */}
                {activeMLTab === 'data' && <MLDataTab />}
                
                {/* Features Tab */}
                {activeMLTab === 'features' && <MLFeaturesTab />}
                
                {/* Supervised Tab */}
                {activeMLTab === 'supervised' && <MLSupervisedTab />}
                
                {/* Ensemble Tab */}
                {activeMLTab === 'ensemble' && <MLEnsembleTab />}
                
                {/* Summary Tab */}
                {activeMLTab === 'summary' && <MLSummaryTab />}
            </div>
        </div>
    );
}

// ML Data Tab Component
function MLDataTab() {
    const [signals, setSignals] = useState([]);
    const [buildResult, setBuildResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [labelingMethod, setLabelingMethod] = useState('binary');
    const [horizon, setHorizon] = useState(5);
    
    const loadDemo = async () => {
        try {
            const res = await fetch('http://127.0.0.1:8000/api/ml/data/demo');
            const data = await res.json();
            setSignals(data.demo_signals || []);
        } catch (e) {
            console.error('Failed to load demo:', e);
        }
    };
    
    const buildDataset = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/ml/data/build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ signals, labeling_method: labelingMethod, horizon })
            });
            const data = await res.json();
            setBuildResult(data);
        } catch (e) {
            console.error('Build failed:', e);
            setBuildResult({ status: 'error', message: e.message });
        } finally {
            setLoading(false);
        }
    };
    
    useEffect(() => { loadDemo(); }, []);
    
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white">📊 Data - Dataset Builder</h2>
                    <p className="text-sm text-gray-400">Build ML-ready datasets from trading signals</p>
                </div>
                <button onClick={loadDemo} className="text-sm text-purple-400 hover:text-purple-300">
                    Load Demo Signals
                </button>
            </div>
            
            <div className="grid grid-cols-2 gap-6">
                {/* Left: Config */}
                <div className="space-y-4">
                    <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
                        <h3 className="text-sm font-semibold mb-3">Configuration</h3>
                        <div className="space-y-3">
                            <div>
                                <label className="text-xs text-gray-400">Labeling Method</label>
                                <select value={labelingMethod} onChange={e => setLabelingMethod(e.target.value)}
                                    className="w-full mt-1 bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm">
                                    <option value="binary">Binary (Up/Down)</option>
                                    <option value="threshold">Threshold (±2%)</option>
                                    <option value="continuous">Continuous Return</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs text-gray-400">Horizon: {horizon} days</label>
                                <input type="range" min="1" max="30" value={horizon} onChange={e => setHorizon(parseInt(e.target.value))}
                                    className="w-full mt-1" />
                            </div>
                        </div>
                    </div>
                    
                    <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
                        <h3 className="text-sm font-semibold mb-3">Signals ({signals.length})</h3>
                        <div className="max-h-32 overflow-y-auto space-y-1 text-xs">
                            {signals.slice(0, 10).map((s, i) => (
                                <div key={i} className="flex justify-between text-gray-400">
                                    <span className="text-blue-400">{s.ticker}</span>
                                    <span>{s.signal_date}</span>
                                </div>
                            ))}
                            {signals.length > 10 && <div className="text-gray-500">+{signals.length - 10} more</div>}
                        </div>
                    </div>
                    
                    <button onClick={buildDataset} disabled={loading || signals.length === 0}
                        className="w-full py-3 bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 rounded-lg font-medium">
                        {loading ? 'Building...' : `Build Dataset (${signals.length} signals)`}
                    </button>
                </div>
                
                {/* Right: Results */}
                <div>
                    {buildResult && (
                        <div className={`border rounded-lg p-4 ${buildResult.status === 'success' ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                            <h3 className="font-semibold mb-3">
                                {buildResult.status === 'success' ? '✅ Dataset Built' : '❌ Build Failed'}
                            </h3>
                            {buildResult.status === 'success' && buildResult.stats && (
                                <div className="grid grid-cols-2 gap-3 text-sm">
                                    <div className="bg-[#0a0a0f] p-3 rounded">
                                        <div className="text-gray-400 text-xs">Total Signals</div>
                                        <div className="text-xl font-bold">{buildResult.stats.total_signals}</div>
                                    </div>
                                    <div className="bg-[#0a0a0f] p-3 rounded">
                                        <div className="text-gray-400 text-xs">Features</div>
                                        <div className="text-xl font-bold">{buildResult.stats.feature_count}</div>
                                    </div>
                                    <div className="bg-[#0a0a0f] p-3 rounded">
                                        <div className="text-gray-400 text-xs">Positive</div>
                                        <div className="text-xl font-bold text-green-400">{buildResult.stats.positive_labels}</div>
                                    </div>
                                    <div className="bg-[#0a0a0f] p-3 rounded">
                                        <div className="text-gray-400 text-xs">Negative</div>
                                        <div className="text-xl font-bold text-red-400">{buildResult.stats.negative_labels}</div>
                                    </div>
                                </div>
                            )}
                            {buildResult.message && <p className="text-sm text-red-400 mt-2">{buildResult.message}</p>}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// ML Features Tab Component
function MLFeaturesTab() {
    const [validation, setValidation] = useState(null);
    const [loading, setLoading] = useState(false);
    
    const fetchValidation = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/ml/features/validate');
            const data = await res.json();
            setValidation(data);
        } catch (e) {
            console.error('Failed:', e);
        } finally {
            setLoading(false);
        }
    };
    
    useEffect(() => { fetchValidation(); }, []);
    
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-bold text-white">🔧 Features - Engineering & Validation</h2>
                <p className="text-sm text-gray-400">Validate and analyze feature quality</p>
            </div>
            
            {validation?.status === 'no_data' ? (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-6 text-center">
                    <div className="text-2xl mb-2">⚠️</div>
                    <div className="text-yellow-400 font-medium">No Dataset Built Yet</div>
                    <div className="text-gray-400 text-sm mt-1">Build a dataset in the Data tab first</div>
                </div>
            ) : validation?.validation ? (
                <div className="grid grid-cols-3 gap-4">
                    <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
                        <div className="text-xs text-gray-400">Feature Count</div>
                        <div className="text-2xl font-bold text-blue-400">{validation.validation.feature_count}</div>
                    </div>
                    <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
                        <div className="text-xs text-gray-400">Sample Count</div>
                        <div className="text-2xl font-bold text-green-400">{validation.validation.sample_count}</div>
                    </div>
                    <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
                        <div className="text-xs text-gray-400">Overall Score</div>
                        <div className="text-2xl font-bold text-purple-400">{validation.validation.overall_score || '--'}</div>
                    </div>
                </div>
            ) : (
                <div className="text-center text-gray-400 py-8">
                    {loading ? 'Loading...' : 'Run validation to see feature analysis'}
                </div>
            )}
        </div>
    );
}

// ML Supervised Tab Component
function MLSupervisedTab() {
    const [models, setModels] = useState([]);
    const [training, setTraining] = useState(false);
    const [result, setResult] = useState(null);
    
    const trainModel = async (modelType) => {
        setTraining(true);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/ml/supervised/train', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_type: modelType, test_size: 0.2 })
            });
            const data = await res.json();
            setResult(data);
        } catch (e) {
            console.error('Training failed:', e);
            setResult({ status: 'error', message: e.message });
        } finally {
            setTraining(false);
        }
    };
    
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-bold text-white">🎯 Supervised - Model Training</h2>
                <p className="text-sm text-gray-400">Train classification models on your dataset</p>
            </div>
            
            <div className="grid grid-cols-3 gap-4">
                {['logistic', 'random_forest', 'gradient_boosting'].map(model => (
                    <button key={model} onClick={() => trainModel(model)} disabled={training}
                        className="bg-[#12121a] border border-gray-800 rounded-lg p-6 hover:border-purple-500/50 transition-all text-left disabled:opacity-50">
                        <div className="text-lg font-medium text-white capitalize">{model.replace('_', ' ')}</div>
                        <div className="text-xs text-gray-500 mt-1">Click to train</div>
                    </button>
                ))}
            </div>
            
            {result && (
                <div className={`border rounded-lg p-4 ${result.status === 'success' ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                    <h3 className="font-semibold mb-3">
                        {result.status === 'success' ? '✅ Model Trained' : '❌ Training Failed'}
                    </h3>
                    {result.metrics && (
                        <div className="grid grid-cols-4 gap-3 text-sm">
                            <div className="bg-[#0a0a0f] p-3 rounded">
                                <div className="text-gray-400 text-xs">Accuracy</div>
                                <div className="text-xl font-bold">{(result.metrics.accuracy * 100).toFixed(1)}%</div>
                            </div>
                            <div className="bg-[#0a0a0f] p-3 rounded">
                                <div className="text-gray-400 text-xs">Precision</div>
                                <div className="text-xl font-bold">{(result.metrics.precision * 100).toFixed(1)}%</div>
                            </div>
                            <div className="bg-[#0a0a0f] p-3 rounded">
                                <div className="text-gray-400 text-xs">Recall</div>
                                <div className="text-xl font-bold">{(result.metrics.recall * 100).toFixed(1)}%</div>
                            </div>
                            <div className="bg-[#0a0a0f] p-3 rounded">
                                <div className="text-gray-400 text-xs">F1 Score</div>
                                <div className="text-xl font-bold">{(result.metrics.f1 * 100).toFixed(1)}%</div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ML Ensemble Tab Component
function MLEnsembleTab() {
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-bold text-white">🤝 Ensemble - Model Consensus</h2>
                <p className="text-sm text-gray-400">Combine multiple models for better predictions</p>
            </div>
            
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-6 text-center">
                <div className="text-2xl mb-2">🔨</div>
                <div className="text-yellow-400 font-medium">Train Models First</div>
                <div className="text-gray-400 text-sm mt-1">Train at least 2 models in the Supervised tab to create an ensemble</div>
            </div>
        </div>
    );
}

// ML Summary Tab Component
function MLSummaryTab() {
    const [summary, setSummary] = useState(null);
    
    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const res = await fetch('http://127.0.0.1:8000/api/ml/summary/scorecard');
                if (res.ok) {
                    const data = await res.json();
                    setSummary(data);
                }
            } catch (e) {
                console.error('Failed:', e);
            }
        };
        fetchSummary();
    }, []);
    
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-bold text-white">📋 Summary - Signal Scorecard</h2>
                <p className="text-sm text-gray-400">Comprehensive signal quality assessment</p>
            </div>
            
            {summary?.scorecard ? (
                <div className="grid grid-cols-5 gap-4">
                    {Object.entries(summary.scorecard).map(([key, value]) => (
                        <div key={key} className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
                            <div className="text-xs text-gray-400 capitalize">{key.replace(/_/g, ' ')}</div>
                            <div className="text-xl font-bold text-blue-400">{typeof value === 'number' ? value.toFixed(2) : value}</div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-6 text-center">
                    <div className="text-2xl mb-2">📊</div>
                    <div className="text-yellow-400 font-medium">No Summary Available</div>
                    <div className="text-gray-400 text-sm mt-1">Complete the ML workflow to generate a summary</div>
                </div>
            )}
        </div>
    );
}

// --- MACRO CONTROL EMBED ---
function MacroControlEmbed() {
    const router = useRouter();
    
    const MACRO_FEATURES = [
        { id: 'regime', name: 'Regime Engine', icon: '🔄', desc: 'HMM-based 4-state detection', score: '--' },
        { id: 'stress', name: 'Stress Detector', icon: '⚡', desc: 'Mahalanobis turbulence index', score: '--' },
        { id: 'volatility', name: 'Vol Regime', icon: '📈', desc: 'VIX percentile tracking', score: '--' },
        { id: 'trend', name: 'CTA Trend', icon: '🎯', desc: 'Multi-timeframe alignment', score: '--' },
        { id: 'reversion', name: 'Mean Reversion', icon: '⏱️', desc: 'Z-score overextension', score: '--' },
        { id: 'breadth', name: 'Breadth', icon: '📊', desc: 'McClellan oscillator', score: '--' },
        { id: 'rates', name: 'Rate Cycle', icon: '💰', desc: 'Fed/RBI policy stance', score: '--' }
    ];

    return (
        <div className="h-full overflow-auto" style={{ background: 'linear-gradient(180deg, rgba(10, 15, 24, 0.9) 0%, rgba(6, 10, 16, 0.95) 100%)' }}>
            <div className="p-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold" style={{ background: 'linear-gradient(to right, #10B981, #3b82f6, #F59E0B)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            🌍 Macro Control System
                        </h1>
                        <p className="text-sm text-gray-400 mt-1">7 Interconnected Regime Detection Systems • 14 Charts</p>
                    </div>
                    <button 
                        onClick={() => router.push('/labs/macro')}
                        className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                        Open Full Dashboard →
                    </button>
                </div>

                {/* Master Posture Preview */}
                <div className="mb-6 p-6 bg-gradient-to-r from-amber-900/30 to-orange-900/30 border border-amber-500/30 rounded-xl">
                    <div className="text-center">
                        <div className="text-sm text-gray-400 mb-1">Master Trading Posture</div>
                        <div className="text-4xl font-black text-amber-400">CAUTION</div>
                        <div className="text-sm text-gray-500 mt-1">Click &quot;Open Full Dashboard&quot; for live data</div>
                    </div>
                </div>

                {/* Feature Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {MACRO_FEATURES.map((feat) => (
                        <div
                            key={feat.id}
                            className="p-4 bg-[#12121a] border border-gray-800 rounded-lg hover:border-green-500/50 transition-all"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xl">{feat.icon}</span>
                                <span className="text-lg font-bold text-gray-500">{feat.score}</span>
                            </div>
                            <div className="text-sm font-medium text-white">{feat.name}</div>
                            <div className="text-xs text-gray-500 mt-0.5">{feat.desc}</div>
                        </div>
                    ))}
                </div>

                {/* Features Included */}
                <div className="mt-6 p-4 bg-gradient-to-r from-green-500/10 via-blue-500/10 to-amber-500/10 border border-green-500/20 rounded-lg">
                    <h3 className="font-semibold text-white mb-2">📊 System Capabilities</h3>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="text-gray-400">• Trading clearances (exposure, leverage)</div>
                        <div className="text-gray-400">• Position sizing adjustments</div>
                        <div className="text-gray-400">• Active warnings & alerts</div>
                        <div className="text-gray-400">• Dual-market (US + India)</div>
                    </div>
                </div>
            </div>
        </div>
    );
}