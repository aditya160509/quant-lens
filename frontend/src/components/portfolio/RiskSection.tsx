'use client';

import React, { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { PlotParams } from 'react-plotly.js';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false }) as React.ComponentType<PlotParams>;
const API_BASE = 'http://127.0.0.1:8000/api';


// =============================================================================
// RISK SIMULATION TAB - Features 34, 37: Monte Carlo, VaR/CVaR
// =============================================================================

const KPICard = ({ label, value, subtitle = '', color = 'default' }: { label: string; value: any; subtitle?: string; color?: string }) => {
  const colorClasses = {
    emerald: 'text-[var(--terminal-green)]',
    red: 'text-[var(--terminal-red)]',
    amber: 'text-[var(--terminal-orange)]',
    default: 'text-[var(--terminal-cyan)]',
    low: 'text-[var(--terminal-green)]',
    medium: 'text-[var(--terminal-orange)]',
    high: 'text-[var(--terminal-orange)]',
    extreme: 'text-[var(--terminal-red)]'
  };
  return (
    <div className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded-lg p-4">
      <div className="text-xs text-[var(--terminal-dim)] uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-2xl font-bold ${colorClasses[color] || colorClasses.default}`}>{value}</div>
      {subtitle && <div className="text-xs text-[var(--terminal-dim)] mt-1 opacity-70">{subtitle}</div>}
    </div>
  );
};

const LoadingSpinner = () => (
  <div className="flex items-center justify-center p-8">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--terminal-cyan)]"></div>
  </div>
);

// --- Monte Carlo Simulation Component ---
export const MonteCarloSimulation = () => {
  const [positions, setPositions] = useState('AAPL:0.3,MSFT:0.25,GOOGL:0.2,AMZN:0.15,NVDA:0.1');
  const [nSims, setNSims] = useState(5000);
  const [horizon, setHorizon] = useState(5);
  const [initialCapital, setInitialCapital] = useState(100000);
  const [contributions, setContributions] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const parsePositions = (str) => {
    return str.split(',').map(p => {
      const [ticker, weight] = p.trim().split(':');
      return { ticker: ticker.trim().toUpperCase(), weight: parseFloat(weight) || 0 };
    });
  };

  const runSimulation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const positionList = parsePositions(positions);
      const res = await fetch(`${API_BASE}/portfolio/monte-carlo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          positions: positionList,
          n_simulations: nSims,
          horizon_years: horizon,
          initial_capital: initialCapital,
          contributions
        })
      });
      const data = await res.json();
      console.log('Monte Carlo result:', data);
      if (data.error) throw new Error(data.error);
      // Handle both cases: direct response or nested in 'data'
      const result = data.data || data;
      setResult(result);
    } catch (e: any) {
      setError(e.message || 'API Error');
    }
    setLoading(false);
  }, [positions, nSims, horizon, initialCapital, contributions]);

  const formatCurrency = (val: number | undefined) => {
    if (val === undefined || isNaN(val)) return '$0';
    return `$${(val / 1000).toFixed(0)}K`;
  };

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3 uppercase tracking-tight">Monte Carlo Simulation</h3>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
          <div className="md:col-span-2">
            <label className="text-xs text-[var(--terminal-dim)]">Positions (TICKER:WEIGHT,...)</label>
            <input type="text" value={positions} onChange={(e) => setPositions(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Initial Capital</label>
            <input type="number" value={initialCapital} onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Horizon (Years): {horizon}</label>
            <input type="range" min="1" max="30" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
              className="w-full accent-[var(--terminal-cyan)]" />
          </div>
          <div className="flex items-end">
            <button onClick={runSimulation} disabled={loading}
              className="w-full bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
              {loading ? 'SIMULATING...' : `RUN ${nSims.toLocaleString()} SIMS`}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <KPICard label="Median Outcome" value={formatCurrency(result.terminal_distribution?.median)} color="default" />
            <KPICard label="Mean Outcome" value={formatCurrency(result.terminal_distribution?.mean)} />
            <KPICard label="5th Percentile" value={formatCurrency(result.probability_metrics?.worst_5_pct)} color="red" />
            <KPICard label="P(Loss)" value={`${(result.probability_metrics?.p_capital_loss ?? 0).toFixed(1)}%`}
              color={(result.probability_metrics?.p_capital_loss ?? 0) > 20 ? 'red' : 'emerald'} />
            <KPICard label="P(2x)" value={`${(result.probability_metrics?.p_doubling ?? 0).toFixed(1)}%`}
              color={(result.probability_metrics?.p_doubling ?? 0) > 50 ? 'emerald' : 'amber'} />
          </div>

          {/* Fan Chart */}
          {result.fan_chart?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Probability Fan Chart</h4>
              <Plot
                data={[
                  // 5th-95th percentile band
                  { type: 'scatter', mode: 'lines', x: result.fan_chart.map(p => p.year),
                    y: result.fan_chart.map(p => p.p95), line: { color: 'transparent' }, showlegend: false },
                  { type: 'scatter', mode: 'lines', x: result.fan_chart.map(p => p.year),
                    y: result.fan_chart.map(p => p.p5), fill: 'tonexty', fillcolor: 'rgba(6, 182, 212, 0.1)',
                    line: { color: 'transparent' }, name: '5-95%' },
                  // 25th-75th percentile band  
                  { type: 'scatter', mode: 'lines', x: result.fan_chart.map(p => p.year),
                    y: result.fan_chart.map(p => p.p75), line: { color: 'transparent' }, showlegend: false },
                  { type: 'scatter', mode: 'lines', x: result.fan_chart.map(p => p.year),
                    y: result.fan_chart.map(p => p.p25), fill: 'tonexty', fillcolor: 'rgba(6, 182, 212, 0.2)',
                    line: { color: 'transparent' }, name: '25-75%' },
                  // Median line
                  { type: 'scatter', mode: 'lines', x: result.fan_chart.map(p => p.year),
                    y: result.fan_chart.map(p => p.p50), line: { color: 'var(--terminal-cyan)', width: 2 }, name: 'Median' },
                  // Best/Worst paths
                  { type: 'scatter', mode: 'lines', x: result.best_path?.map(p => p.year),
                    y: result.best_path?.map(p => p.value), line: { color: 'var(--terminal-green)', dash: 'dot' }, name: 'Best' },
                  { type: 'scatter', mode: 'lines', x: result.worst_path?.map(p => p.year),
                    y: result.worst_path?.map(p => p.value), line: { color: 'var(--terminal-red)', dash: 'dot' }, name: 'Worst' }
                ]}
                layout={{
                  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' }, showlegend: true,
                  legend: { x: 0, y: 1.15, orientation: 'h' },
                  xaxis: { title: 'Years', gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  yaxis: { title: 'Value ($)', gridcolor: 'var(--border)', tickformat: ',.0f', zerolinecolor: 'var(--border)' },
                  margin: { t: 30, b: 50, l: 80, r: 20 }, height: 300
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            </div>
          )}

          {/* Terminal Wealth Histogram */}
          {result.terminal_distribution?.histogram?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Terminal Wealth Distribution</h4>
              <Plot
                data={[{
                  type: 'bar',
                  x: result.terminal_distribution.histogram.map(h => (h.bin_start + h.bin_end) / 2),
                  y: result.terminal_distribution.histogram.map(h => h.count),
                  marker: {
                    color: result.terminal_distribution.histogram.map(h =>
                      (h.bin_start + h.bin_end) / 2 < initialCapital ? 'var(--terminal-red)' : 'var(--terminal-green)')
                  }
                }]}
                layout={{
                  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' }, bargap: 0.1,
                  xaxis: { title: 'Terminal Value ($)', gridcolor: 'var(--border)', tickformat: ',.0f', zerolinecolor: 'var(--border)' },
                  yaxis: { title: 'Frequency', gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  margin: { t: 20, b: 50, l: 60, r: 20 }, height: 200
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// --- VaR & CVaR Calculator Component ---
export const VaRCalculator = () => {
  const [positions, setPositions] = useState('AAPL:0.3,MSFT:0.25,GOOGL:0.2,AMZN:0.15,NVDA:0.1');
  const [confidence, setConfidence] = useState(95);
  const [horizon, setHorizon] = useState(1);
  const [method, setMethod] = useState('historical');
  const [portfolioValue, setPortfolioValue] = useState(100000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const parsePositions = (str) => {
    return str.split(',').map(p => {
      const [ticker, weight] = p.trim().split(':');
      return { ticker: ticker.trim().toUpperCase(), weight: parseFloat(weight) || 0 };
    });
  };

  const runCalculation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const positionList = parsePositions(positions);
      const res = await fetch(`${API_BASE}/portfolio/var`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          positions: positionList,
          confidence_level: confidence / 100,
          horizon_days: horizon,
          method,
          portfolio_value: portfolioValue
        })
      });
      const data = await res.json();
      console.log('VaR result:', data);
      if (data.error) throw new Error(data.error);
      // Handle both cases: direct response or nested in 'data'
      const result = data.data || data;
      setResult(result);
    } catch (e: any) {
      setError(e.message || 'API Error');
    }
    setLoading(false);
  }, [positions, confidence, horizon, method, portfolioValue]);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Value at Risk Calculator</h3>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
          <div className="md:col-span-2">
            <label className="text-xs text-[var(--terminal-dim)]">Positions</label>
            <input type="text" value={positions} onChange={(e) => setPositions(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Confidence: {confidence}%</label>
            <input type="range" min="90" max="99" value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}
              className="w-full accent-[var(--terminal-cyan)]" />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Method</label>
            <select value={method} onChange={(e) => setMethod(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none">
              <option value="historical">Historical</option>
              <option value="parametric">Parametric</option>
              <option value="monte_carlo">Monte Carlo</option>
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={runCalculation} disabled={loading}
              className="w-full bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
              {loading ? '...' : 'CALCULATE'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label={`${confidence}% VaR`} value={`${((result.var?.percentage ?? 0) * 100).toFixed(2)}%`}
              subtitle={`$${(result.var?.dollar ?? 0).toLocaleString()}`} color="amber" />
            <KPICard label="CVaR (ES)" value={`${((result.cvar?.percentage ?? 0) * 100).toFixed(2)}%`}
              subtitle={`$${(result.cvar?.dollar ?? 0).toLocaleString()}`} color="red" />
            <KPICard label="Risk Level" value={(result.risk_thermometer?.level ?? 'N/A').toUpperCase()}
              color={result.risk_thermometer?.level || 'default'} />
            <KPICard label="Horizon" value={`${result.var?.horizon_days ?? horizon} day${(result.var?.horizon_days ?? 1) > 1 ? 's' : ''}`} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Risk Thermometer */}
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Risk Thermometer</h4>
              <div className="relative h-8 bg-gradient-to-r from-[var(--terminal-green)] via-[var(--terminal-orange)] to-[var(--terminal-red)] rounded border border-[var(--border)]/30">
                <div className="absolute top-0 h-full w-1.5 bg-[var(--foreground)] rounded shadow-[0_0_8px_rgba(255,255,255,0.5)]"
                  style={{ left: `${result.risk_thermometer?.value}%`, transform: 'translateX(-50%)' }}></div>
              </div>
              <div className="flex justify-between text-[10px] text-[var(--terminal-dim)] mt-2 font-mono uppercase tracking-tighter">
                <span>Low</span>
                <span>Medium</span>
                <span>High</span>
                <span>Extreme</span>
              </div>
            </div>

            {/* Tail Concentration */}
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Tail Loss Contribution</h4>
              <div className="space-y-2">
                {Object.entries(result.tail_concentration || {}).map(([ticker, contrib]: [string, any]) => (
                  <div key={ticker} className="flex justify-between items-center py-1 border-b border-[var(--border)]/10">
                    <span className="text-[var(--foreground)] font-mono font-bold text-sm">{ticker}</span>
                    <div className="flex items-center gap-3">
                      <div className="w-24 h-2 bg-[var(--terminal-darker)] rounded overflow-hidden border border-[var(--border)]/30">
                        <div className="h-full bg-[var(--terminal-red)]" style={{ width: `${Math.abs(contrib as number)}%` }}></div>
                      </div>
                      <span className="text-[var(--terminal-red)] w-14 text-right text-xs font-mono font-bold">{Math.abs(contrib as number).toFixed(1)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Rolling VaR Chart */}
          {result.rolling_var?.dates?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Rolling {confidence}% VaR</h4>
              <Plot
                data={[{
                  type: 'scatter', mode: 'lines', fill: 'tozeroy',
                  x: result.rolling_var.dates,
                  y: result.rolling_var.values.map(v => v * 100),
                  line: { color: 'var(--terminal-orange)', width: 2 },
                  fillcolor: 'rgba(245, 158, 11, 0.15)'
                }]}
                layout={{
                  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' },
                  xaxis: { gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  yaxis: { title: 'VaR (%)', gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  margin: { t: 20, b: 40, l: 50, r: 20 }, height: 200
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const RiskSectionExports = { MonteCarloSimulation, VaRCalculator };
export default RiskSectionExports;
