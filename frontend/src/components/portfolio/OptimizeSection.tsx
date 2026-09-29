'use client';

import React, { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { PlotParams } from 'react-plotly.js';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false }) as React.ComponentType<PlotParams>;
const API_BASE = 'http://127.0.0.1:8000/api';


// =============================================================================
// OPTIMIZE TAB - Features 26-29: Markowitz, Risk Parity, Black-Litterman, Factor Tilt
// =============================================================================

// --- Helper Components ---
const KPICard = ({ label, value, subtitle = '', color = 'default' }: { label: string; value: any; subtitle?: string; color?: string }) => {
  const colorClasses: Record<string, string> = {
    emerald: 'text-[var(--terminal-green)]',
    red: 'text-[var(--terminal-red)]',
    amber: 'text-[var(--terminal-orange)]',
    default: 'text-[var(--terminal-cyan)]'
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

// --- Markowitz Optimizer Component ---
export const MarkowitzOptimizer = () => {
  const [tickers, setTickers] = useState('AAPL,MSFT,GOOGL,AMZN,NVDA');
  const [mode, setMode] = useState('max_sharpe');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runOptimization = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const tickerList = tickers.split(',').map(t => t.trim().toUpperCase());
      const res = await fetch(`${API_BASE}/portfolio/optimize/markowitz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: tickerList, mode })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [tickers, mode]);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Markowitz Portfolio Optimizer</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Tickers (comma-separated)</label>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Optimization Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none"
            >
              <option value="max_sharpe">Max Sharpe Ratio</option>
              <option value="min_volatility">Min Volatility</option>
              <option value="target_return">Target Return</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={runOptimization}
              disabled={loading}
              className="w-full bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono"
            >
              {loading ? 'OPTIMIZING...' : 'RUN OPTIMIZATION'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}

      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Expected Return" value={`${(result.metrics?.expected_return * 100).toFixed(1)}%`} color="emerald" />
            <KPICard label="Expected Volatility" value={`${(result.metrics?.expected_volatility * 100).toFixed(1)}%`} color="amber" />
            <KPICard label="Sharpe Ratio" value={result.metrics?.sharpe_ratio?.toFixed(2)} color="default" />
            <KPICard label="Max DD Est." value={`${(result.metrics?.max_drawdown_estimate * 100).toFixed(1)}%`} color="red" />
          </div>

          {/* Optimal Weights Table */}
          <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
            <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Optimal Weights</h4>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {Object.entries(result.optimal_weights || {}).map(([ticker, weight]: [string, any]) => (
                <div key={ticker} className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded p-2 text-center">
                  <div className="text-[var(--foreground)] font-bold font-mono">{ticker}</div>
                  <div className="text-[var(--terminal-cyan)] text-lg font-mono">{((weight as number) * 100).toFixed(1)}%</div>
                </div>
              ))}

            </div>
          </div>

          {/* Risk Contribution Chart */}
          {result.risk_contribution && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Risk Contribution</h4>
              <Plot
                data={[{
                  type: 'pie',
                  values: Object.values(result.risk_contribution),
                  labels: Object.keys(result.risk_contribution),
                  marker: { colors: ['var(--terminal-cyan)', 'var(--terminal-green)', 'var(--terminal-orange)', 'var(--terminal-red)', 'var(--terminal-blue)', '#ff00ff'] },
                  textinfo: 'label+percent',
                  hole: 0.4
                }]}
                layout={{
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' },
                  showlegend: false,
                  margin: { t: 20, b: 20, l: 20, r: 20 },
                  height: 250
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            </div>
          )}

          {/* Efficient Frontier Chart */}
          {result.efficient_frontier?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Efficient Frontier</h4>
              <Plot
                data={[{
                  type: 'scatter',
                  mode: 'markers+lines',
                  x: result.efficient_frontier.map(p => p.volatility * 100),
                  y: result.efficient_frontier.map(p => p.return * 100),
                  marker: {
                    color: result.efficient_frontier.map(p => p.sharpe),
                    colorscale: 'Viridis',
                    size: 8,
                    colorbar: { title: 'Sharpe', tickfont: { color: 'var(--terminal-dim)' } }
                  },
                  line: { color: 'var(--terminal-cyan)', width: 1 },
                  hovertemplate: 'Vol: %{x:.1f}%<br>Ret: %{y:.1f}%<br><extra></extra>'
                }, {
                  type: 'scatter',
                  mode: 'markers',
                  x: [result.metrics?.expected_volatility * 100],
                  y: [result.metrics?.expected_return * 100],
                  marker: { color: 'var(--terminal-orange)', size: 15, symbol: 'star' },
                  name: 'Optimal'
                }]}
                layout={{
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' },
                  xaxis: { title: 'Volatility (%)', gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  yaxis: { title: 'Return (%)', gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  showlegend: false,
                  margin: { t: 20, b: 50, l: 60, r: 40 },
                  height: 300
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

// --- Risk Parity Component ---
export const RiskParityAllocator = () => {
  const [tickers, setTickers] = useState('SPY,TLT,GLD,VNQ');
  const [targetVol, setTargetVol] = useState(12);
  const [crisisMode, setCrisisMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runOptimization = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const tickerList = tickers.split(',').map(t => t.trim().toUpperCase());
      const res = await fetch(`${API_BASE}/portfolio/optimize/risk-parity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: tickerList,
          target_volatility: targetVol / 100,
          crisis_mode: crisisMode
        })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [tickers, targetVol, crisisMode]);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Risk Parity Allocator</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div className="md:col-span-2">
            <label className="text-xs text-[var(--terminal-dim)]">Tickers (comma-separated)</label>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Target Volatility: {targetVol}%</label>
            <input
              type="range"
              min="5"
              max="25"
              value={targetVol}
              onChange={(e) => setTargetVol(Number(e.target.value))}
              className="w-full accent-[var(--terminal-cyan)]"
            />
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-[var(--terminal-dim)] cursor-pointer">
              <input
                type="checkbox"
                checked={crisisMode}
                onChange={(e) => setCrisisMode(e.target.checked)}
                className="rounded border-[var(--border)] bg-[var(--terminal-darker)] text-[var(--terminal-red)]"
              />
              Crisis Mode
            </label>
            <button
              onClick={runOptimization}
              disabled={loading}
              className="bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono"
            >
              {loading ? '...' : 'RUN'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Portfolio Vol" value={`${(result.metrics?.portfolio_volatility * 100).toFixed(1)}%`} />
            <KPICard label="Leverage Factor" value={result.metrics?.leverage_factor?.toFixed(2)}  color="amber" />
            <KPICard label="Diversification Score" value={`${result.metrics?.diversification_score?.toFixed(0)}/100`} color="emerald" />
            <KPICard label="Crisis Mode" value={result.crisis_mode ? 'ON' : 'OFF'} color={result.crisis_mode ? 'red' : 'default'} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Weights */}
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Risk Parity Weights</h4>
              {Object.entries(result.risk_parity_weights || {}).map(([ticker, weight]: [string, any]) => (
                <div key={ticker} className="flex justify-between items-center py-1 border-b border-[var(--border)]/50">
                  <span className="text-[var(--foreground)] font-mono">{ticker}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 h-2 bg-[var(--terminal-darker)] rounded">
                      <div className="h-full bg-[var(--terminal-cyan)] rounded" style={{ width: `${(weight as number) * 100}%` }}></div>
                    </div>
                    <span className="text-[var(--terminal-cyan)] w-16 text-right font-mono">{((weight as number) * 100).toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Risk Contributions */}
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Risk Contributions</h4>
              {Object.entries(result.risk_contributions || {}).map(([ticker, contrib]: [string, any]) => (
                <div key={ticker} className="flex justify-between items-center py-1 border-b border-[var(--border)]/50">
                  <span className="text-[var(--foreground)] font-mono">{ticker}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 h-2 bg-[var(--terminal-darker)] rounded">
                      <div className="h-full bg-[var(--terminal-green)] rounded" style={{ width: `${contrib}%` }}></div>
                    </div>
                    <span className="text-[var(--terminal-green)] w-16 text-right font-mono">{(contrib as number).toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// --- Factor Tilt Component ---
export const FactorTiltOptimizer = () => {
  const [tickers, setTickers] = useState('AAPL,MSFT,JPM,JNJ,XOM,PG,HD');
  const [factors, setFactors] = useState({ momentum: 30, value: -20, quality: 50, size: 0, low_vol: 20 });
  const [strength, setStrength] = useState(50);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runOptimization = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const tickerList = tickers.split(',').map(t => t.trim().toUpperCase());
      const res = await fetch(`${API_BASE}/portfolio/optimize/factor-tilt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: tickerList,
          target_factors: factors,
          factor_strength: strength
        })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [tickers, factors, strength]);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Factor Tilt Optimizer</h3>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Tickers</label>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none"
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {Object.entries(factors).map(([factor, value]) => (
              <div key={factor}>
                <label className="text-xs text-[var(--terminal-dim)] capitalize">{factor.replace('_', ' ')}: {value}</label>
                <input
                  type="range"
                  min="-100"
                  max="100"
                  value={value}
                  onChange={(e) => setFactors({ ...factors, [factor]: Number(e.target.value) })}
                  className="w-full accent-[var(--terminal-cyan)]"
                />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="text-xs text-[var(--terminal-dim)]">Overall Strength: {strength}%</label>
              <input
                type="range"
                min="0"
                max="100"
                value={strength}
                onChange={(e) => setStrength(Number(e.target.value))}
                className="w-full accent-[var(--terminal-cyan)]"
              />
            </div>
            <button
              onClick={runOptimization}
              disabled={loading}
              className="bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-6 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono"
            >
              {loading ? 'OPTIMIZING...' : 'OPTIMIZE'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Weights */}
          <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
            <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Factor-Tilted Weights</h4>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(result.factor_weights || {}).map(([ticker, weight]: [string, any]) => (
                <div key={ticker} className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded p-2 flex justify-between font-mono">
                  <span className="text-[var(--foreground)]">{ticker}</span>
                  <span className="text-[var(--terminal-cyan)] font-bold">{((weight as number) * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Factor Exposure Radar */}
          <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
            <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Factor Exposure</h4>
            <Plot
              data={[{
                type: 'scatterpolar',
                r: Object.values(result.achieved_exposure || {}).map((v: any) => Math.abs(v as number) * 100),
                theta: Object.keys(result.achieved_exposure || {}).map(k => k.replace('_', ' ')),
                fill: 'toself',
                fillcolor: 'rgba(6, 182, 212, 0.3)',
                line: { color: 'var(--terminal-cyan)' },
                name: 'Achieved'
              }, {
                type: 'scatterpolar',
                r: Object.values(result.target_exposure || {}).map((v: any) => Math.abs(v as number) * 100),
                theta: Object.keys(result.target_exposure || {}).map(k => k.replace('_', ' ')),
                fill: 'toself',
                fillcolor: 'rgba(245, 158, 11, 0.2)',
                line: { color: 'var(--terminal-orange)', dash: 'dash' },
                name: 'Target'
              }]}
              layout={{
                paper_bgcolor: 'transparent',
                polar: {
                  bgcolor: 'transparent',
                  radialaxis: { visible: true, range: [0, 60], gridcolor: 'var(--border)', tickfont: { color: 'var(--terminal-dim)' } },
                  angularaxis: { gridcolor: 'var(--border)', tickfont: { color: 'var(--terminal-dim)' } }
                },
                font: { color: 'var(--terminal-dim)', family: 'monospace' },
                showlegend: true,
                legend: { x: 0, y: 1.1, orientation: 'h' },
                margin: { t: 40, b: 20, l: 40, r: 40 },
                height: 280
              }}
              config={{ displayModeBar: false }}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

const optimizers = { MarkowitzOptimizer, RiskParityAllocator, FactorTiltOptimizer };

export default optimizers;
