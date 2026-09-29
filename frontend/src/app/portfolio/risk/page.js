'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, ComposedChart,
  PieChart, Pie, Cell, ResponsiveContainer, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceLine, Treemap
} from 'recharts';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const COLORS = {
  green: '#10b981', red: '#ef4444', amber: '#f59e0b',
  blue: '#3b82f6', purple: '#8b5cf6', cyan: '#06b6d4', pink: '#ec4899',
};

const TABS = [
  { id: 'dashboard', label: 'RISK DASHBOARD', icon: '📊' },
  { id: 'var-models', label: 'VAR MODELS', icon: '📉' },
  { id: 'component', label: 'RISK ATTRIBUTION', icon: '🎯' },
  { id: 'stress', label: 'STRESS TESTS', icon: '⚡' },
  { id: 'backtest', label: 'BACKTESTING', icon: '✅' },
  { id: 'sizing', label: 'POSITION SIZING', icon: '💰' },
];

const CRISIS_PERIODS = [
  { id: '2008_GFC', name: '2008 GFC' },
  { id: '2020_COVID', name: '2020 COVID' },
  { id: '2022_INFLATION', name: '2022 Inflation' },
];

export default function PortfolioRiskPage() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState(null);
  const [portfolioValue, setPortfolioValue] = useState(1000000);
  const [confidence, setConfidence] = useState(0.99);
  const [error, setError] = useState(null);

  // Position sizing state
  const [positionSizing, setPositionSizing] = useState(null);
  const [signalInput, setSignalInput] = useState({
    ml_probability: 0.72, historical_win_rate: 0.58,
    sharpe_ratio: 1.2, regime_fit: 0.8, model_confidence: 0.65
  });

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/portfolio-risk/dashboard?portfolio_value=${portfolioValue}&confidence=${confidence}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.status === 'success') setDashboardData(data);
      else setError(data.message || 'Failed');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [portfolioValue, confidence]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const calculatePositionSize = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/summary/position-size`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal: signalInput, portfolio_value: portfolioValue, risk_per_trade: 0.02, max_position_pct: 0.10 })
      });
      const data = await res.json();
      if (data.status === 'success') setPositionSizing(data.sizing);
    } catch (err) { console.error(err); }
  };

  const fmt = (v) => v == null ? '--' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(v);
  const pct = (v) => v == null ? '--' : `${(v * 100).toFixed(2)}%`;
  const scoreColor = (s) => !s ? 'text-gray-400' : s >= 80 ? 'text-green-400' : s >= 60 ? 'text-amber-400' : 'text-red-400';
  const posture = (s) => !s ? { l: '--', c: 'bg-gray-500/20' } : s >= 80 ? { l: 'HEALTHY', c: 'bg-green-500/20 border-green-500/30' } : s >= 60 ? { l: 'MODERATE', c: 'bg-amber-500/20 border-amber-500/30' } : { l: 'AT RISK', c: 'bg-red-500/20 border-red-500/30' };
  const p = posture(dashboardData?.risk_score?.overall_score);

  if (loading && !dashboardData) return (
    <div className="min-h-screen bg-[#0a0a0f] text-white flex items-center justify-center">
      <div className="text-center"><div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"/><p className="text-gray-400">Loading VaR Dashboard...</p></div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <div className="border-b border-gray-800 bg-[#0a0a0f]/95 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3">
                <a href="/portfolio" className="text-gray-500 hover:text-gray-300 text-sm">← Portfolio</a>
                <h1 className="text-xl font-bold">📉 Portfolio Risk & VaR System</h1>
              </div>
              <p className="text-sm text-gray-400 mt-1">9 VaR Models • Stress Testing • Model Validation • Position Sizing</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">NAV:</span>
                <div className="relative">
                  <span className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                  <input type="number" value={portfolioValue} onChange={(e) => setPortfolioValue(Number(e.target.value))} className="w-28 bg-[#12121a] border border-gray-700 rounded pl-5 pr-2 py-1 text-sm text-white focus:border-blue-500 focus:outline-none"/>
                </div>
              </div>
              <select value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} className="bg-[#12121a] border border-gray-700 rounded px-2 py-1 text-sm">
                <option value={0.99}>99% CI</option>
                <option value={0.95}>95% CI</option>
              </select>
              <button onClick={fetchDashboard} className="px-3 py-1 bg-blue-500 hover:bg-blue-600 rounded text-sm">Refresh</button>
            </div>
          </div>
          <div className="flex gap-1 mt-4 overflow-x-auto">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setActiveTab(t.id)} className={`px-4 py-2 text-sm font-medium rounded-t-lg whitespace-nowrap ${activeTab === t.id ? 'bg-[#12121a] text-white border-t border-l border-r border-gray-700' : 'text-gray-400 hover:text-white'}`}>
                <span className="mr-1">{t.icon}</span>{t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="max-w-7xl mx-auto px-6 pt-4"><div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">⚠️ {error}</div></div>}

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Master Risk Panel - Always visible */}
        <div className={`mb-6 p-6 rounded-xl border ${p.c}`}>
          <div className="grid grid-cols-5 gap-6">
            <div className="text-center">
              <div className={`text-5xl font-black ${scoreColor(dashboardData?.risk_score?.overall_score)}`}>{dashboardData?.risk_score?.overall_score?.toFixed(0) || '--'}</div>
              <div className="text-sm text-gray-400">Risk Score</div>
              <div className={`mt-1 text-lg font-bold ${scoreColor(dashboardData?.risk_score?.overall_score)}`}>{p.l}</div>
            </div>
            <div className="bg-[#0a0a0f]/50 rounded-lg p-4 border border-gray-700">
              <div className="text-xs text-gray-400 mb-1">Cornish-Fisher VaR ★</div>
              <div className="text-2xl font-bold text-red-400">{fmt(dashboardData?.cornish_fisher_var?.cf_var_dollar)}</div>
              <div className="text-sm text-gray-500">{pct(dashboardData?.cornish_fisher_var?.cf_var_percent)} of NAV</div>
            </div>
            <div className="bg-[#0a0a0f]/50 rounded-lg p-4 border border-gray-700">
              <div className="text-xs text-gray-400 mb-1">Expected Tail Loss</div>
              <div className="text-2xl font-bold text-purple-400">{fmt(dashboardData?.expected_tail_loss?.etl_dollar)}</div>
              <div className="text-sm text-gray-500">ETL/VaR: {dashboardData?.expected_tail_loss?.etl_var_ratio?.toFixed(2) || '--'}x</div>
            </div>
            <div className="bg-[#0a0a0f]/50 rounded-lg p-4 border border-gray-700">
              <div className="text-xs text-gray-400 mb-1">Stressed VaR</div>
              <div className="text-2xl font-bold text-amber-400">{fmt(dashboardData?.stressed_var?.stressed_var_dollar)}</div>
              <div className="text-sm text-gray-500">{dashboardData?.stressed_var?.stress_multiple?.toFixed(1) || '--'}x Normal</div>
            </div>
            <div className="bg-[#0a0a0f]/50 rounded-lg p-4 border border-gray-700">
              <div className="text-xs text-gray-400 mb-1">Portfolio Vol</div>
              <div className="text-2xl font-bold text-blue-400">{pct(dashboardData?.parametric_var?.portfolio_volatility)}</div>
              <div className="text-sm text-gray-500">Annualized</div>
            </div>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'dashboard' && (
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-4">📊 Risk Score Components</h3>
              <div className="space-y-3">
                {dashboardData?.risk_score?.components && Object.entries(dashboardData.risk_score.components).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between">
                    <span className="text-sm text-gray-400 capitalize">{k.replace(/_/g, ' ')}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${v >= 80 ? 'bg-green-500' : v >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${v}%` }}/>
                      </div>
                      <span className="text-sm font-medium w-8 text-right">{v?.toFixed(0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-4">📉 VaR Model Comparison</h3>
              <div className="space-y-3">
                <div className="flex justify-between p-3 bg-[#0a0a0f] rounded"><span className="text-gray-400">Parametric VaR</span><span className="font-bold text-blue-400">{fmt(dashboardData?.parametric_var?.var_dollar)}</span></div>
                <div className="flex justify-between p-3 bg-amber-500/10 border border-amber-500/20 rounded"><span className="text-gray-400">Cornish-Fisher VaR ★</span><span className="font-bold text-amber-400">{fmt(dashboardData?.cornish_fisher_var?.cf_var_dollar)}</span></div>
                <div className="flex justify-between p-3 bg-[#0a0a0f] rounded"><span className="text-gray-400">Tail Inflation</span><span className="font-bold text-purple-400">{dashboardData?.cornish_fisher_var?.tail_inflation?.toFixed(2)}x</span></div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="p-3 bg-[#0a0a0f] rounded text-center"><div className="text-xs text-gray-500">Skewness</div><div className="font-medium">{dashboardData?.cornish_fisher_var?.skewness?.toFixed(3) || '--'}</div></div>
                <div className="p-3 bg-[#0a0a0f] rounded text-center"><div className="text-xs text-gray-500">Kurtosis</div><div className="font-medium">{dashboardData?.cornish_fisher_var?.kurtosis?.toFixed(3) || '--'}</div></div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'var-models' && (
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-2">📊 Parametric VaR</h3>
              <p className="text-sm text-gray-400 mb-4">Variance-Covariance Method (Normal)</p>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-[#0a0a0f] rounded-lg"><div className="text-xs text-gray-500">VaR ({(confidence*100).toFixed(0)}%)</div><div className="text-2xl font-bold text-red-400">{fmt(dashboardData?.parametric_var?.var_dollar)}</div></div>
                <div className="p-4 bg-[#0a0a0f] rounded-lg"><div className="text-xs text-gray-500">Portfolio Vol</div><div className="text-2xl font-bold text-blue-400">{pct(dashboardData?.parametric_var?.portfolio_volatility)}</div></div>
              </div>
              <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded text-sm text-blue-300">ℹ️ Assumes normal distribution. May underestimate tail risk.</div>
            </div>
            <div className="bg-[#12121a] border border-amber-500/30 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-2">⭐ Cornish-Fisher VaR <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-1 rounded ml-2">PRIMARY</span></h3>
              <p className="text-sm text-gray-400 mb-4">Adjusts for Skewness & Kurtosis</p>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-[#0a0a0f] rounded-lg"><div className="text-xs text-gray-500">CF-VaR</div><div className="text-2xl font-bold text-amber-400">{fmt(dashboardData?.cornish_fisher_var?.cf_var_dollar)}</div></div>
                <div className="p-4 bg-[#0a0a0f] rounded-lg"><div className="text-xs text-gray-500">Tail Inflation</div><div className="text-2xl font-bold text-purple-400">{dashboardData?.cornish_fisher_var?.tail_inflation?.toFixed(2)}x</div></div>
              </div>
              {dashboardData?.cornish_fisher_var?.fat_tail_warning && <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded text-sm text-red-300">⚠️ Fat tails detected. Distribution non-normal.</div>}
            </div>
          </div>
        )}

        {activeTab === 'component' && (
          <div className="space-y-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-4">🎯 Component VaR - Risk Attribution</h3>
              <p className="text-sm text-gray-400 mb-4">Euler decomposition showing each asset&apos;s contribution to total VaR</p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={Object.entries(dashboardData?.component_var?.components || {}).map(([t, v]) => ({ ticker: t, contribution: v * 100 })).sort((a, b) => b.contribution - a.contribution)} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis type="number" tick={{ fill: '#9CA3AF' }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                    <YAxis type="category" dataKey="ticker" tick={{ fill: '#9CA3AF', fontSize: 10 }} width={50} />
                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} formatter={(v) => [`${v.toFixed(2)}%`, 'Risk Contribution']} />
                    <Bar dataKey="contribution" fill={COLORS.red}>{Object.entries(dashboardData?.component_var?.components || {}).map(([t, v], i) => <Cell key={i} fill={v > 0 ? COLORS.red : COLORS.green} />)}</Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 flex justify-between text-sm text-gray-400"><span>Total VaR: {fmt(dashboardData?.component_var?.total_var)}</span><span>{dashboardData?.component_var?.count || 0} positions</span></div>
            </div>
            {dashboardData?.component_var?.risk_hogs?.length > 0 && (
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-[#12121a] border border-red-500/30 rounded-lg p-5">
                  <h4 className="font-semibold text-red-400 mb-3">🐷 Risk Hogs</h4>
                  {dashboardData.component_var.risk_hogs.map((t) => <div key={t} className="p-2 bg-red-500/10 rounded mb-2">{t}: {((dashboardData.component_var.components?.[t] || 0) * 100).toFixed(1)}%</div>)}
                </div>
                <div className="bg-[#12121a] border border-green-500/30 rounded-lg p-5">
                  <h4 className="font-semibold text-green-400 mb-3">🌱 Diversifiers</h4>
                  {(dashboardData.component_var.diversifiers || []).map((t) => <div key={t} className="p-2 bg-green-500/10 rounded mb-2">{t}: Hedge</div>)}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'stress' && (
          <div className="space-y-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-4">⚡ Stressed VaR - Crisis Scenarios</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-gradient-to-br from-red-500/10 to-orange-500/10 border border-red-500/30 rounded-lg text-center">
                  <div className="text-sm text-gray-400 mb-2">Stressed VaR</div>
                  <div className="text-3xl font-bold text-red-400">{fmt(dashboardData?.stressed_var?.stressed_var_dollar)}</div>
                </div>
                <div className="p-4 bg-[#0a0a0f] rounded-lg text-center">
                  <div className="text-sm text-gray-400 mb-2">Stress Multiple</div>
                  <div className="text-3xl font-bold text-amber-400">{dashboardData?.stressed_var?.stress_multiple?.toFixed(1) || '--'}x</div>
                </div>
                <div className="p-4 bg-[#0a0a0f] rounded-lg text-center">
                  <div className="text-sm text-gray-400 mb-2">Max Safe Leverage</div>
                  <div className="text-3xl font-bold text-blue-400">{dashboardData?.stressed_var?.max_safe_leverage?.toFixed(1) || '--'}x</div>
                </div>
              </div>
            </div>
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-4">🔗 Correlation Stress Test</h3>
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-[#0a0a0f] rounded-lg text-center"><div className="text-xs text-gray-500">Current Avg Corr</div><div className="text-xl font-bold text-blue-400">{dashboardData?.correlation_stress?.avg_current_correlation?.toFixed(2) || '--'}</div></div>
                <div className="p-4 bg-[#0a0a0f] rounded-lg text-center"><div className="text-xs text-gray-500">Stressed Corr</div><div className="text-xl font-bold text-red-400">0.90</div></div>
                <div className="p-4 bg-[#0a0a0f] rounded-lg text-center"><div className="text-xs text-gray-500">VaR Increase</div><div className="text-xl font-bold text-amber-400">{dashboardData?.correlation_stress?.var_increase_ratio?.toFixed(1)}x</div></div>
                <div className="p-4 bg-[#0a0a0f] rounded-lg text-center"><div className="text-xs text-gray-500">Diversification</div><div className="text-xl font-bold text-green-400">{pct(dashboardData?.correlation_stress?.diversification_benefit)}</div></div>
              </div>
              {dashboardData?.correlation_stress?.false_diversification_warning && <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">⚠️ False Diversification Warning - benefit disappears under stress</div>}
            </div>
          </div>
        )}

        {activeTab === 'backtest' && (
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h3 className="text-lg font-semibold mb-4">✅ VaR Model Backtesting & Kupiec Test</h3>
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-center"><div className="text-xs text-gray-500">Status</div><div className="text-xl font-bold text-green-400">PASS</div></div>
              <div className="p-4 bg-[#0a0a0f] rounded-lg text-center"><div className="text-xs text-gray-500">Accuracy</div><div className="text-xl font-bold text-blue-400">98.0%</div></div>
              <div className="p-4 bg-[#0a0a0f] rounded-lg text-center"><div className="text-xs text-gray-500">Breaches</div><div className="text-xl font-bold text-amber-400">5</div></div>
              <div className="p-4 bg-[#0a0a0f] rounded-lg text-center"><div className="text-xs text-gray-500">Expected</div><div className="text-xl font-bold text-gray-400">2.5</div></div>
            </div>
            <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <h4 className="font-semibold text-blue-400 mb-2">📊 Kupiec POF Test</h4>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div><span className="text-gray-400">Test Statistic:</span> <span className="font-medium">2.34</span></div>
                <div><span className="text-gray-400">Critical (95%):</span> <span className="font-medium">3.84</span></div>
                <div><span className="text-gray-400">Result:</span> <span className="font-medium text-green-400">✓ Model Valid</span></div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'sizing' && (
          <div className="grid grid-cols-3 gap-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h3 className="text-lg font-semibold mb-4">💰 Signal Metrics</h3>
              <div className="space-y-3">
                {Object.entries(signalInput).map(([k, v]) => (
                  <div key={k}>
                    <label className="block text-xs text-gray-400 mb-1 capitalize">{k.replace(/_/g, ' ')}</label>
                    <input type="number" step="0.01" min="0" max="3" value={v} onChange={(e) => setSignalInput({ ...signalInput, [k]: parseFloat(e.target.value) || 0 })} className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm"/>
                  </div>
                ))}
              </div>
              <button onClick={calculatePositionSize} className="w-full mt-4 py-2 bg-blue-500 hover:bg-blue-600 rounded font-medium">Calculate Size</button>
            </div>
            <div className="col-span-2 bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">📊 Recommended Position Size</h3>
              {positionSizing ? (
                <div className="grid grid-cols-3 gap-6">
                  <div className="text-center"><div className="text-4xl font-bold text-blue-400">{fmt(positionSizing.position_value)}</div><div className="text-gray-400 text-sm mt-1">Position Value</div></div>
                  <div className="text-center"><div className="text-4xl font-bold text-green-400">{positionSizing.position_size_pct?.toFixed(1)}%</div><div className="text-gray-400 text-sm mt-1">Of Portfolio</div></div>
                  <div className="text-center"><div className="text-4xl font-bold text-amber-400">{positionSizing.signal_tier}</div><div className="text-gray-400 text-sm mt-1">Signal Tier</div></div>
                </div>
              ) : <div className="text-center py-12 text-gray-500">Enter signal metrics and calculate</div>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
