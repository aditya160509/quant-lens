'use client';

import React, { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { PlotParams } from 'react-plotly.js';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false }) as React.ComponentType<PlotParams>;
const API_BASE = 'http://127.0.0.1:8000/api';


// =============================================================================
// PERFORMANCE TAB - Features 32-33, 44-45: Ratios, Drawdowns, Benchmark, Attribution
// =============================================================================

const KPICard = ({ label, value, subtitle = '', color = 'default' }: { label: string; value: any; subtitle?: string; color?: string }) => {
  const colorClasses = {
    excellent: 'text-[var(--terminal-green)]',
    good: 'text-[var(--terminal-cyan)]',
    fair: 'text-[var(--terminal-orange)]',
    poor: 'text-[var(--terminal-red)]',
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

// --- Sharpe/Sortino/Calmar Ratios Component ---
export const RatiosDashboard = () => {
  const [positions, setPositions] = useState('AAPL:0.3,MSFT:0.25,GOOGL:0.2,AMZN:0.15,NVDA:0.1');
  const [window, setWindow] = useState('1y');
  const [benchmark, setBenchmark] = useState('SPY');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const parsePositions = (str) => {
    return str.split(',').map(p => {
      const [ticker, weight] = p.trim().split(':');
      return { ticker: ticker.trim().toUpperCase(), weight: parseFloat(weight) || 0 };
    });
  };

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const positionList = parsePositions(positions);
      const res = await fetch(`${API_BASE}/portfolio/ratios`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions: positionList, window, benchmark })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [positions, window, benchmark]);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3 uppercase tracking-tight">Risk-Adjusted Returns</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div className="md:col-span-2">
            <label className="text-xs text-[var(--terminal-dim)]">Positions (TICKER:WEIGHT,...)</label>
            <input
              type="text"
              value={positions}
              onChange={(e) => setPositions(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Window</label>
            <select value={window} onChange={(e) => setWindow(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none">
              <option value="6mo">6 Months</option>
              <option value="1y">1 Year</option>
              <option value="2y">2 Years</option>
              <option value="3y">3 Years</option>
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={runAnalysis} disabled={loading}
              className="w-full bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
              {loading ? 'ANALYZING...' : 'ANALYZE'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard 
              label="Sharpe Ratio" 
              value={result.ratios?.sharpe?.value?.toFixed(2)} 
              color={result.ratios?.sharpe?.color} 
              subtitle={`vs ${benchmark}: ${result.benchmark_ratios?.sharpe?.toFixed(2)}`}
            />
            <KPICard 
              label="Sortino Ratio" 
              value={result.ratios?.sortino?.value?.toFixed(2)} 
              color={result.ratios?.sortino?.color}
              subtitle={`vs ${benchmark}: ${result.benchmark_ratios?.sortino?.toFixed(2)}`}
            />
            <KPICard 
              label="Calmar Ratio" 
              value={result.ratios?.calmar?.value?.toFixed(2)} 
              color={result.ratios?.calmar?.color}
              subtitle={`vs ${benchmark}: ${result.benchmark_ratios?.calmar?.toFixed(2)}`}
            />
            <KPICard 
              label="Quality Score" 
              value={`${result.quality_score?.toFixed(0)}/100`}
              color={result.quality_score > 70 ? 'emerald' : result.quality_score > 40 ? 'amber' : 'red'}
            />
          </div>

          {/* Rolling Ratios Chart */}
          {result.rolling?.dates?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Rolling Ratios (90-Day Window)</h4>
              <Plot
                data={[
                  { type: 'scatter', mode: 'lines', x: result.rolling.dates, y: result.rolling.sharpe, name: 'Sharpe', line: { color: 'var(--terminal-cyan)' } },
                  { type: 'scatter', mode: 'lines', x: result.rolling.dates, y: result.rolling.sortino, name: 'Sortino', line: { color: 'var(--terminal-green)' } },
                  { type: 'scatter', mode: 'lines', x: result.rolling.dates, y: result.rolling.calmar, name: 'Calmar', line: { color: 'var(--terminal-orange)' } }
                ]}
                layout={{
                  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' }, showlegend: true,
                  legend: { x: 0, y: 1.1, orientation: 'h' },
                  xaxis: { gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' }, yaxis: { gridcolor: 'var(--border)', zeroline: true, zerolinecolor: 'var(--border)' },
                  margin: { t: 30, b: 40, l: 50, r: 20 }, height: 250
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

// --- Drawdown Analysis Component ---
export const DrawdownAnalysis = () => {
  const [positions, setPositions] = useState('AAPL:0.3,MSFT:0.25,GOOGL:0.2,AMZN:0.15,NVDA:0.1');
  const [period, setPeriod] = useState('3y');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const parsePositions = (str) => {
    return str.split(',').map(p => {
      const [ticker, weight] = p.trim().split(':');
      return { ticker: ticker.trim().toUpperCase(), weight: parseFloat(weight) || 0 };
    });
  };

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const positionList = parsePositions(positions);
      const res = await fetch(`${API_BASE}/portfolio/drawdowns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions: positionList, period, threshold: 0.05 })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [positions, period]);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Drawdown Analysis</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="md:col-span-2">
            <label className="text-xs text-[var(--terminal-dim)]">Positions (TICKER:WEIGHT,...)</label>
            <input type="text" value={positions} onChange={(e) => setPositions(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
          <div className="flex items-end gap-2">
            <select value={period} onChange={(e) => setPeriod(e.target.value)}
              className="flex-1 bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none">
              <option value="1y">1 Year</option>
              <option value="2y">2 Years</option>
              <option value="3y">3 Years</option>
              <option value="5y">5 Years</option>
            </select>
            <button onClick={runAnalysis} disabled={loading}
              className="bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
              {loading ? '...' : 'ANALYZE'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Max Drawdown" value={`${(result.metrics?.max_drawdown * 100).toFixed(1)}%`} color="red" />
            <KPICard label="Current DD" value={`${(result.metrics?.current_drawdown * 100).toFixed(1)}%`} 
              color={result.metrics?.current_drawdown < -0.05 ? 'red' : 'emerald'} />
            <KPICard label="Avg Recovery" value={`${result.metrics?.avg_recovery_days?.toFixed(0) || 'N/A'} days`} color="amber" />
            <KPICard label="DD Events" value={result.metrics?.drawdown_count} />
          </div>

          {/* Underwater Chart */}
          {result.underwater_chart?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Underwater Chart</h4>
              <Plot
                data={[{
                  type: 'scatter', mode: 'lines', fill: 'tozeroy',
                  x: result.underwater_chart.map(p => p.date),
                  y: result.underwater_chart.map(p => p.drawdown * 100),
                  line: { color: 'var(--terminal-red)' },
                  fillcolor: 'rgba(239, 68, 68, 0.2)',
                  hovertemplate: '%{x}<br>Drawdown: %{y:.1f}%<extra></extra>'
                }]}
                layout={{
                  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' },
                  xaxis: { gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  yaxis: { title: 'Drawdown (%)', gridcolor: 'var(--border)', zeroline: true, zerolinecolor: 'var(--border)' },
                  margin: { t: 20, b: 40, l: 50, r: 20 }, height: 200
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            </div>
          )}

          {/* Drawdown Table */}
          {result.drawdown_table?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Top Drawdowns</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm font-mono">
                  <thead>
                    <tr className="text-left text-[var(--terminal-dim)] border-b border-[var(--border)]/50 uppercase text-xs">
                      <th className="py-2 px-2">Start</th>
                      <th className="py-2 px-2">Trough</th>
                      <th className="py-2 px-2">End</th>
                      <th className="py-2 px-2 text-right">Depth</th>
                      <th className="py-2 px-2 text-right">Duration</th>
                      <th className="py-2 px-2 text-right">Recovery</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.drawdown_table.slice(0, 5).map((dd, i) => (
                      <tr key={i} className="border-b border-[var(--border)]/30 hover:bg-[var(--terminal-darker)]">
                        <td className="py-2 px-2 text-[var(--foreground)] font-bold">{dd.start_date}</td>
                        <td className="py-2 px-2 text-[var(--foreground)]">{dd.trough_date}</td>
                        <td className="py-2 px-2 text-[var(--foreground)]">{dd.end_date}</td>
                        <td className="py-2 px-2 text-right text-[var(--terminal-red)]">{(dd.depth * 100).toFixed(1)}%</td>
                        <td className="py-2 px-2 text-right text-[var(--terminal-dim)]">{dd.duration_days}d</td>
                        <td className="py-2 px-2 text-right text-[var(--terminal-dim)]">{dd.recovery_days || '-'}d</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// --- Benchmark Comparison Component ---
export const BenchmarkComparison = () => {
  const [positions, setPositions] = useState('AAPL:0.3,MSFT:0.25,GOOGL:0.2,AMZN:0.15,NVDA:0.1');
  const [benchmark, setBenchmark] = useState('SPY');
  const [window, setWindow] = useState('1y');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const parsePositions = (str) => {
    return str.split(',').map(p => {
      const [ticker, weight] = p.trim().split(':');
      return { ticker: ticker.trim().toUpperCase(), weight: parseFloat(weight) || 0 };
    });
  };

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const positionList = parsePositions(positions);
      const res = await fetch(`${API_BASE}/portfolio/benchmark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions: positionList, window, benchmark })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [positions, window, benchmark]);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Benchmark Comparison</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div className="md:col-span-2">
            <label className="text-xs text-[var(--terminal-dim)]">Positions</label>
            <input type="text" value={positions} onChange={(e) => setPositions(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Benchmark</label>
            <select value={benchmark} onChange={(e) => setBenchmark(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none">
              <option value="SPY">S&P 500 (SPY)</option>
              <option value="QQQ">Nasdaq 100 (QQQ)</option>
              <option value="IWM">Russell 2000 (IWM)</option>
              <option value="VTI">Total Market (VTI)</option>
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={runAnalysis} disabled={loading}
              className="w-full bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
              {loading ? '...' : 'COMPARE'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <KPICard label="Portfolio Return" value={`${(result.returns?.portfolio_total * 100).toFixed(1)}%`}
              color={result.returns?.portfolio_total > 0 ? 'emerald' : 'red'} />
            <KPICard label="Benchmark Return" value={`${(result.returns?.benchmark_total * 100).toFixed(1)}%`} />
            <KPICard label="Excess Return" value={`${(result.returns?.excess_return * 100).toFixed(1)}%`}
              color={result.returns?.excess_return > 0 ? 'emerald' : 'red'} />
            <KPICard label="Tracking Error" value={`${(result.risk_metrics?.tracking_error * 100).toFixed(1)}%`} color="amber" />
            <KPICard label="Info Ratio" value={result.risk_metrics?.information_ratio?.toFixed(2)} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Capture Ratios */}
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Capture Ratios</h4>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="text-xs text-[var(--terminal-dim)] mb-1">Upside Capture</div>
                  <div className="h-4 bg-[var(--terminal-darker)] rounded overflow-hidden border border-[var(--border)]/30">
                    <div className="h-full bg-[var(--terminal-green)]" style={{ width: `${Math.min(100, result.capture_ratios?.upside)}%` }}></div>
                  </div>
                  <div className="text-right text-sm text-[var(--terminal-green)] font-mono font-bold mt-1">{result.capture_ratios?.upside?.toFixed(0)}%</div>
                </div>
                <div className="flex-1">
                  <div className="text-xs text-[var(--terminal-dim)] mb-1">Downside Capture</div>
                  <div className="h-4 bg-[var(--terminal-darker)] rounded overflow-hidden border border-[var(--border)]/30">
                    <div className="h-full bg-[var(--terminal-red)]" style={{ width: `${Math.min(100, result.capture_ratios?.downside)}%` }}></div>
                  </div>
                  <div className="text-right text-sm text-[var(--terminal-red)] font-mono font-bold mt-1">{result.capture_ratios?.downside?.toFixed(0)}%</div>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-[var(--border)]/30 text-center">
                <span className="text-[var(--terminal-dim)] text-xs uppercase tracking-widest mr-2">Capture Efficiency: </span>
                <span className={`text-xl font-bold font-mono ${result.capture_ratios?.efficiency > 0 ? 'text-[var(--terminal-green)]' : 'text-[var(--terminal-red)]'}`}>
                  {result.capture_ratios?.efficiency?.toFixed(0)}%
                </span>
              </div>
            </div>

            {/* Cumulative Performance Chart */}
            {result.cumulative_chart?.length > 0 && (
              <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
                <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Cumulative Performance</h4>
                <Plot
                  data={[
                    { type: 'scatter', mode: 'lines', x: result.cumulative_chart.map(p => p.date),
                      y: result.cumulative_chart.map(p => p.portfolio * 100), name: 'Portfolio', line: { color: 'var(--terminal-cyan)', width: 2 } },
                    { type: 'scatter', mode: 'lines', x: result.cumulative_chart.map(p => p.date),
                      y: result.cumulative_chart.map(p => p.benchmark * 100), name: benchmark, line: { color: 'var(--terminal-orange)', dash: 'dash', width: 1.5 } }
                  ]}
                  layout={{
                    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                    font: { color: 'var(--terminal-dim)', family: 'monospace' }, showlegend: true,
                    legend: { x: 0, y: 1.15, orientation: 'h' },
                    xaxis: { gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                    yaxis: { title: 'Return (%)', gridcolor: 'var(--border)', zeroline: true, zerolinecolor: 'var(--border)' },
                    margin: { t: 30, b: 30, l: 50, r: 20 }, height: 200
                  }}
                  config={{ displayModeBar: false }}
                  style={{ width: '100%' }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const PerformanceSectionExports = { RatiosDashboard, DrawdownAnalysis, BenchmarkComparison };
export default PerformanceSectionExports;
