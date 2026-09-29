'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';

// Dynamic imports for charts
const LineChart = dynamic(() => import('recharts').then(mod => mod.LineChart), { ssr: false });
const BarChart = dynamic(() => import('recharts').then(mod => mod.BarChart), { ssr: false });
const AreaChart = dynamic(() => import('recharts').then(mod => mod.AreaChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(mod => mod.Line), { ssr: false });
const Bar = dynamic(() => import('recharts').then(mod => mod.Bar), { ssr: false });
const Area = dynamic(() => import('recharts').then(mod => mod.Area), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(mod => mod.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(mod => mod.YAxis), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(mod => mod.CartesianGrid), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(mod => mod.Tooltip), { ssr: false });
const ResponsiveContainer = dynamic(() => import('recharts').then(mod => mod.ResponsiveContainer), { ssr: false });
const ReferenceLine = dynamic(() => import('recharts').then(mod => mod.ReferenceLine), { ssr: false });
const Cell = dynamic(() => import('recharts').then(mod => mod.Cell), { ssr: false });

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// ============================================================================
// THEMES & COLORS
// ============================================================================
const THEME = {
  bg: {
    primary: '#0a0a0f',
    secondary: '#12121a',
    tertiary: '#1a1a24',
    accent: '#1e293b'
  },
  text: {
    primary: '#ffffff',
    secondary: '#94a3b8',
    muted: '#64748b'
  },
  border: {
    default: '#2d2d3d',
    hover: '#3d3d4d'
  },
  status: {
    success: '#22c55e',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#3b82f6'
  },
  gradient: {
    green: 'from-emerald-500/20 to-green-500/10',
    yellow: 'from-amber-500/20 to-yellow-500/10',
    red: 'from-red-500/20 to-rose-500/10',
    blue: 'from-blue-500/20 to-indigo-500/10'
  }
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================
const formatCurrency = (val, decimals = 0) => {
  if (val === null || val === undefined) return '$0';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(val);
};

const formatPercent = (val, decimals = 2) => {
  if (val === null || val === undefined) return '0%';
  return `${val.toFixed(decimals)}%`;
};

const getScoreColor = (score) => {
  if (score >= 80) return THEME.status.success;
  if (score >= 60) return THEME.status.warning;
  return THEME.status.danger;
};

const getStatusBg = (color) => {
  if (color === 'green') return 'bg-emerald-500/20 border-emerald-500/30';
  if (color === 'yellow') return 'bg-amber-500/20 border-amber-500/30';
  if (color === 'red') return 'bg-red-500/20 border-red-500/30';
  return 'bg-slate-500/20 border-slate-500/30';
};

// ============================================================================
// SHARED COMPONENTS
// ============================================================================
const LoadingSpinner = () => (
  <div className="flex items-center justify-center p-8">
    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500" />
  </div>
);

const ErrorAlert = ({ message, onRetry }) => (
  <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center justify-between">
    <span className="text-red-400">{message}</span>
    {onRetry && (
      <button onClick={onRetry} className="px-3 py-1 bg-red-500/20 hover:bg-red-500/30 rounded text-sm">
        Retry
      </button>
    )}
  </div>
);

const FeatureCard = ({ title, icon, children, className = "" }) => (
  <div className={`bg-[#12121a] border border-gray-800 rounded-xl overflow-hidden ${className}`}>
    <div className="px-5 py-4 border-b border-gray-800 flex items-center gap-3">
      <span className="text-2xl">{icon}</span>
      <h3 className="font-semibold text-white">{title}</h3>
    </div>
    <div className="p-5">{children}</div>
  </div>
);

const MetricRow = ({ label, value, subValue, trend, status }) => (
  <div className="flex items-center justify-between py-2 border-b border-gray-800/50 last:border-0">
    <span className="text-gray-400 text-sm">{label}</span>
    <div className="text-right">
      <span className={`font-semibold ${status ? getStatusBg(status) : ''}`}>{value}</span>
      {subValue && <span className="text-gray-500 text-xs ml-2">{subValue}</span>}
    </div>
  </div>
);

const TabNavigation = ({ tabs, active, onChange }) => (
  <div className="flex gap-1 bg-[#0a0a0f] rounded-lg p-1">
    {tabs.map(tab => (
      <button
        key={tab.id}
        onClick={() => onChange(tab.id)}
        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
          active === tab.id
            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
            : 'text-gray-400 hover:text-white hover:bg-gray-800'
        }`}
      >
        {tab.icon} {tab.label}
      </button>
    ))}
  </div>
);

// ============================================================================
// MASTER RISK CARD
// ============================================================================
const MasterRiskCard = ({ data, loading }) => {
  if (loading) return <LoadingSpinner />;
  if (!data) return null;

  const bgGradient = data.posture_color === 'green' ? THEME.gradient.green :
                     data.posture_color === 'yellow' ? THEME.gradient.yellow :
                     THEME.gradient.red;

  return (
    <div className={`bg-gradient-to-br ${bgGradient} border border-gray-800 rounded-xl p-6`}>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        {/* Portfolio Value */}
        <div className="text-center">
          <div className="text-gray-400 text-sm mb-1">Portfolio NAV</div>
          <div className="text-3xl font-bold text-white">{formatCurrency(data.nav)}</div>
        </div>

        {/* Primary VaR */}
        <div className="text-center">
          <div className="text-gray-400 text-sm mb-1">VaR (99%)</div>
          <div className="text-3xl font-bold text-red-400">{formatCurrency(data.primary_var)}</div>
          <div className="text-gray-500 text-xs">{formatPercent(data.primary_var_pct)} of NAV</div>
        </div>

        {/* ETL */}
        <div className="text-center">
          <div className="text-gray-400 text-sm mb-1">Expected Tail Loss</div>
          <div className="text-3xl font-bold text-amber-400">{formatCurrency(data.etl)}</div>
          <div className="text-gray-500 text-xs">{formatPercent(data.etl_pct)} of NAV</div>
        </div>

        {/* Risk Score */}
        <div className="text-center">
          <div className="text-gray-400 text-sm mb-1">Risk Score</div>
          <div className="text-3xl font-bold" style={{ color: getScoreColor(data.overall_score) }}>
            {data.overall_score?.toFixed(0) || 0}
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
            <div
              className="h-2 rounded-full transition-all"
              style={{
                width: `${data.overall_score || 0}%`,
                backgroundColor: getScoreColor(data.overall_score)
              }}
            />
          </div>
        </div>

        {/* Posture */}
        <div className="text-center">
          <div className="text-gray-400 text-sm mb-1">Risk Posture</div>
          <div className={`text-2xl font-bold px-4 py-2 rounded-lg inline-block ${getStatusBg(data.posture_color)}`}>
            {data.posture}
          </div>
          <div className="text-gray-500 text-xs mt-1">{data.warnings_count} warnings</div>
        </div>
      </div>

      {/* Warnings */}
      {data.warnings && data.warnings.length > 0 && (
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-2">
          {data.warnings.slice(0, 4).map((warning, i) => (
            <div key={i} className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-red-300">
              {warning}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// PARAMETRIC VAR CARD
// ============================================================================
const ParametricVarCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="Parametric VaR" icon="📊"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="Parametric VaR" icon="📊">
      <div className="space-y-4">
        {/* Main metrics */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">1-Day VaR</div>
            <div className="text-xl font-bold text-red-400">{formatCurrency(data.var_1d)}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.var_1d_pct)}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">10-Day VaR</div>
            <div className="text-xl font-bold text-amber-400">{formatCurrency(data.var_10d)}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.var_10d_pct)}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Portfolio Vol</div>
            <div className="text-xl font-bold text-blue-400">{formatPercent(data.portfolio_volatility)}</div>
            <div className="text-gray-500 text-xs">Annualized</div>
          </div>
        </div>

        {/* VaR Table */}
        {data.var_table && data.var_table.length > 0 && (
          <div className="bg-[#0a0a0f] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50">
                  <th className="px-3 py-2 text-left text-gray-400">Confidence</th>
                  <th className="px-3 py-2 text-right text-gray-400">1-Day VaR</th>
                  <th className="px-3 py-2 text-right text-gray-400">10-Day VaR</th>
                </tr>
              </thead>
              <tbody>
                {data.var_table.map((row, i) => (
                  <tr key={i} className="border-t border-gray-800">
                    <td className="px-3 py-2 text-white">{row.confidence}%</td>
                    <td className="px-3 py-2 text-right text-red-400">{formatCurrency(row.var_1d)}</td>
                    <td className="px-3 py-2 text-right text-amber-400">{formatCurrency(row.var_10d)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Rolling VaR Chart */}
        {data.var_history && data.var_history.length > 0 && (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.var_history.slice(-90)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d2d3d" />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#12121a', border: '1px solid #2d2d3d' }}
                  formatter={(v) => [formatCurrency(v), 'VaR']}
                />
                <Area type="monotone" dataKey="var" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// CORNISH-FISHER VAR CARD
// ============================================================================
const CornishFisherCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="Cornish-Fisher VaR" icon="📈"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="Cornish-Fisher VaR" icon="📈">
      <div className="space-y-4">
        {/* Primary Metric */}
        <div className="flex items-center justify-between bg-[#0a0a0f] rounded-lg p-4">
          <div>
            <div className="text-gray-400 text-sm">CF-Adjusted VaR</div>
            <div className="text-2xl font-bold text-red-400">{formatCurrency(data.cf_var)}</div>
          </div>
          <div className={`px-4 py-2 rounded-lg ${
            data.regime === 'NORMAL TAILS' ? 'bg-emerald-500/20 text-emerald-400' :
            data.regime === 'MODERATE' ? 'bg-amber-500/20 text-amber-400' :
            'bg-red-500/20 text-red-400'
          }`}>
            {data.regime}
          </div>
        </div>

        {/* Tail Analysis */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4">
            <div className="text-gray-400 text-xs mb-1">Tail Inflation</div>
            <div className={`text-xl font-bold ${data.tail_inflation > 1.1 ? 'text-red-400' : 'text-green-400'}`}>
              {(data.tail_inflation || 1).toFixed(2)}×
            </div>
            <div className="text-gray-500 text-xs">vs Parametric</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4">
            <div className="text-gray-400 text-xs mb-1">Delta VaR</div>
            <div className="text-xl font-bold text-amber-400">+{formatCurrency(data.delta_var)}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.delta_var_pct)} more</div>
          </div>
        </div>

        {/* Distribution Diagnostics */}
        {data.diagnostics && data.diagnostics.length > 0 && (
          <div className="bg-[#0a0a0f] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50">
                  <th className="px-3 py-2 text-left text-gray-400">Metric</th>
                  <th className="px-3 py-2 text-right text-gray-400">Value</th>
                  <th className="px-3 py-2 text-right text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.diagnostics.map((row, i) => (
                  <tr key={i} className="border-t border-gray-800">
                    <td className="px-3 py-2 text-white">{row.metric}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{typeof row.value === 'number' ? row.value.toFixed(2) : row.value}</td>
                    <td className="px-3 py-2 text-right">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Recommendation */}
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg px-4 py-3 text-sm text-blue-300">
          💡 {data.recommendation}
        </div>
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// EXPECTED TAIL LOSS CARD
// ============================================================================
const ETLCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="Expected Tail Loss" icon="💀"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="Expected Tail Loss (CVaR)" icon="💀">
      <div className="space-y-4">
        {/* Main metrics */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">ETL (99%)</div>
            <div className="text-xl font-bold text-red-400">{formatCurrency(data.etl)}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.etl_pct)}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">ETL/VaR Ratio</div>
            <div className={`text-xl font-bold ${data.etl_var_ratio > 1.15 ? 'text-red-400' : 'text-green-400'}`}>
              {(data.etl_var_ratio || 1).toFixed(2)}×
            </div>
            <div className="text-gray-500 text-xs">{data.severity}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Worst Day</div>
            <div className="text-xl font-bold text-orange-400">{formatCurrency(data.worst_single_day)}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.worst_single_day_pct)}</div>
          </div>
        </div>

        {/* Worst Days Table */}
        {data.worst_days && data.worst_days.length > 0 && (
          <div>
            <div className="text-sm font-medium text-gray-400 mb-2">Worst Historical Days</div>
            <div className="bg-[#0a0a0f] rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-800/50">
                    <th className="px-3 py-2 text-left text-gray-400">Date</th>
                    <th className="px-3 py-2 text-right text-gray-400">Loss</th>
                    <th className="px-3 py-2 text-left text-gray-400">Event</th>
                  </tr>
                </thead>
                <tbody>
                  {data.worst_days.slice(0, 5).map((day, i) => (
                    <tr key={i} className="border-t border-gray-800">
                      <td className="px-3 py-2 text-white">{day.date}</td>
                      <td className="px-3 py-2 text-right text-red-400">-{formatCurrency(day.loss)}</td>
                      <td className="px-3 py-2 text-gray-400">{day.event}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tail Frequency */}
        {data.tail_frequency && data.tail_frequency.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {data.tail_frequency.map((freq, i) => (
              <div key={i} className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                <div className="text-gray-400 text-xs">&gt; {freq.threshold_pct}% loss</div>
                <div className="text-lg font-bold text-white">{freq.expected_per_year?.toFixed(1)}</div>
                <div className="text-gray-500 text-xs">days/year</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// COMPONENT VAR CARD
// ============================================================================
const ComponentVarCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="Component VaR" icon="🧩"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="Component VaR (Risk Attribution)" icon="🧩">
      <div className="space-y-4">
        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Total VaR</div>
            <div className="text-xl font-bold text-red-400">{formatCurrency(data.total_var)}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Top Contributor</div>
            <div className="text-lg font-bold text-white">{data.top_contributor}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.top_contributor_pct)} of risk</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Risk HHI</div>
            <div className={`text-xl font-bold ${data.is_concentrated ? 'text-red-400' : 'text-green-400'}`}>
              {(data.hhi || 0).toFixed(3)}
            </div>
            <div className="text-gray-500 text-xs">{data.is_concentrated ? 'Concentrated' : 'Diversified'}</div>
          </div>
        </div>

        {/* Attribution Table */}
        {data.attribution && data.attribution.length > 0 && (
          <div className="bg-[#0a0a0f] rounded-lg overflow-hidden max-h-60 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-800">
                <tr>
                  <th className="px-3 py-2 text-left text-gray-400">Ticker</th>
                  <th className="px-3 py-2 text-right text-gray-400">Weight</th>
                  <th className="px-3 py-2 text-right text-gray-400">Risk %</th>
                  <th className="px-3 py-2 text-right text-gray-400">Conc.</th>
                  <th className="px-3 py-2 text-left text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.attribution.slice(0, 10).map((row, i) => (
                  <tr key={i} className="border-t border-gray-800">
                    <td className="px-3 py-2 font-medium text-white">{row.ticker}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{formatPercent(row.weight)}</td>
                    <td className="px-3 py-2 text-right text-red-400">{formatPercent(row.risk_contribution)}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{row.concentration?.toFixed(2)}×</td>
                    <td className="px-3 py-2">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Risk Hogs Alert */}
        {data.risk_hogs && data.risk_hogs.length > 0 && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <div className="font-medium text-red-400 mb-2">🚨 Risk Hogs Detected</div>
            <div className="text-sm text-red-300">
              {data.risk_hogs.map(h => h.ticker).join(', ')} have concentration &gt; 2.0×
            </div>
          </div>
        )}
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// INCREMENTAL VAR CARD (Trade Simulator)
// ============================================================================
const IncrementalVarCard = ({ onSimulate }) => {
  const [ticker, setTicker] = useState('AAPL');
  const [tradeValue, setTradeValue] = useState(10000);
  const [side, setSide] = useState('buy');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const runSimulation = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/risk-control/incremental-var`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, trade_value: tradeValue, side, confidence: 0.99 })
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      console.error('Incremental VaR failed:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <FeatureCard title="Incremental VaR (Trade Gatekeeper)" icon="🚦">
      <div className="space-y-4">
        {/* Trade Input */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-gray-400 text-xs">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={e => setTicker(e.target.value.toUpperCase())}
              className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-white text-sm mt-1"
              placeholder="AAPL"
            />
          </div>
          <div>
            <label className="text-gray-400 text-xs">Trade Value ($)</label>
            <input
              type="number"
              value={tradeValue}
              onChange={e => setTradeValue(Number(e.target.value))}
              className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-white text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-gray-400 text-xs">Side</label>
            <select
              value={side}
              onChange={e => setSide(e.target.value)}
              className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-white text-sm mt-1"
            >
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </div>
        </div>

        <button
          onClick={runSimulation}
          disabled={loading}
          className="w-full py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 rounded font-medium transition-colors"
        >
          {loading ? 'Simulating...' : 'Simulate Trade Impact'}
        </button>

        {/* Results */}
        {result && (
          <div className="space-y-3">
            <div className={`p-4 rounded-lg text-center ${
              result.assessment === 'APPROVE' ? 'bg-emerald-500/20 border border-emerald-500/30' :
              result.assessment === 'CAUTION' ? 'bg-amber-500/20 border border-amber-500/30' :
              'bg-red-500/20 border border-red-500/30'
            }`}>
              <div className="text-2xl font-bold">{result.assessment}</div>
              <div className="text-sm mt-1">Diversification Benefit: {formatPercent(result.diversification_benefit * 100)}</div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                <div className="text-gray-400 text-xs">VaR Before</div>
                <div className="text-lg font-bold text-white">{formatCurrency(result.var_before)}</div>
              </div>
              <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                <div className="text-gray-400 text-xs">VaR After</div>
                <div className="text-lg font-bold text-white">{formatCurrency(result.var_after)}</div>
              </div>
              <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
                <div className="text-gray-400 text-xs">Incremental</div>
                <div className={`text-lg font-bold ${result.incremental_var > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {result.incremental_var > 0 ? '+' : ''}{formatCurrency(result.incremental_var)}
                </div>
              </div>
            </div>

            {/* Sizing Analysis */}
            {result.sizing_analysis && result.sizing_analysis.length > 0 && (
              <div className="bg-[#0a0a0f] rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-800/50">
                      <th className="px-3 py-2 text-left text-gray-400">Size</th>
                      <th className="px-3 py-2 text-right text-gray-400">Inc. VaR</th>
                      <th className="px-3 py-2 text-left text-gray-400">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.sizing_analysis.map((row, i) => (
                      <tr key={i} className="border-t border-gray-800">
                        <td className="px-3 py-2 text-white">{formatCurrency(row.size)}</td>
                        <td className="px-3 py-2 text-right text-gray-300">{formatCurrency(row.inc_var)}</td>
                        <td className="px-3 py-2">{row.assessment}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// STRESSED VAR CARD
// ============================================================================
const StressedVarCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="Stressed VaR" icon="🌪️"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="Stressed VaR (Crisis Scenarios)" icon="🌪️">
      <div className="space-y-4">
        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Normal VaR</div>
            <div className="text-xl font-bold text-green-400">{formatCurrency(data.normal_var)}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Stressed VaR</div>
            <div className="text-xl font-bold text-red-400">{formatCurrency(data.stressed_var)}</div>
            <div className="text-gray-500 text-xs">{data.crisis_period}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Stress Multiple</div>
            <div className={`text-xl font-bold ${data.stress_multiple > 1.5 ? 'text-red-400' : 'text-amber-400'}`}>
              {(data.stress_multiple || 1).toFixed(2)}×
            </div>
          </div>
        </div>

        {/* Readiness Badge */}
        <div className={`p-4 rounded-lg text-center ${
          data.readiness === 'RESILIENT' ? 'bg-emerald-500/20 border border-emerald-500/30' :
          data.readiness === 'MODERATE RISK' ? 'bg-amber-500/20 border border-amber-500/30' :
          'bg-red-500/20 border border-red-500/30'
        }`}>
          <div className="font-bold text-lg">{data.readiness}</div>
          <div className="text-sm text-gray-400 mt-1">
            Max Safe Leverage: {(data.max_safe_leverage || 1).toFixed(1)}×
          </div>
        </div>

        {/* Scenario Comparison */}
        {data.scenario_comparison && data.scenario_comparison.length > 0 && (
          <div className="bg-[#0a0a0f] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50">
                  <th className="px-3 py-2 text-left text-gray-400">Crisis</th>
                  <th className="px-3 py-2 text-right text-gray-400">Stressed VaR</th>
                  <th className="px-3 py-2 text-right text-gray-400">Multiple</th>
                </tr>
              </thead>
              <tbody>
                {data.scenario_comparison.map((row, i) => (
                  <tr key={i} className="border-t border-gray-800">
                    <td className="px-3 py-2 text-white">{row.scenario}</td>
                    <td className="px-3 py-2 text-right text-red-400">{formatCurrency(row.stressed_var)}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{row.stress_multiple?.toFixed(2)}×</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Impact Decomposition */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
            <div className="text-gray-400 text-xs">Vol Amplification</div>
            <div className="text-lg font-bold text-amber-400">{(data.vol_amplification || 1).toFixed(2)}×</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-3 text-center">
            <div className="text-gray-400 text-xs">Corr Spike</div>
            <div className="text-lg font-bold text-red-400">+{((data.correlation_spike || 0) * 100).toFixed(0)}%</div>
          </div>
        </div>
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// CORRELATION STRESS CARD
// ============================================================================
const CorrelationStressCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="Correlation Stress" icon="🔗"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="Correlation Stress Test" icon="🔗">
      <div className="space-y-4">
        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Avg Correlation</div>
            <div className={`text-xl font-bold ${data.avg_correlation > 0.6 ? 'text-red-400' : 'text-green-400'}`}>
              {((data.avg_correlation || 0) * 100).toFixed(0)}%
            </div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Stressed VaR (ρ=90%)</div>
            <div className="text-xl font-bold text-red-400">{formatCurrency(data.stressed_var)}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">VaR Amplification</div>
            <div className="text-xl font-bold text-amber-400">{(data.amplification || 1).toFixed(2)}×</div>
          </div>
        </div>

        {/* False Diversification Alert */}
        {data.false_diversification > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 text-center">
            <div className="text-amber-400 font-medium">⚠️ False Diversification</div>
            <div className="text-2xl font-bold text-white mt-1">{formatCurrency(data.false_diversification)}</div>
            <div className="text-sm text-gray-400">Hidden risk from correlation underestimation</div>
          </div>
        )}

        {/* Correlation Scenarios */}
        {data.scenarios && data.scenarios.length > 0 && (
          <div className="bg-[#0a0a0f] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50">
                  <th className="px-3 py-2 text-left text-gray-400">Target ρ</th>
                  <th className="px-3 py-2 text-right text-gray-400">Stressed VaR</th>
                  <th className="px-3 py-2 text-right text-gray-400">Risk Added</th>
                </tr>
              </thead>
              <tbody>
                {data.scenarios.map((row, i) => (
                  <tr key={i} className="border-t border-gray-800">
                    <td className="px-3 py-2 text-white">{(row.target_rho * 100).toFixed(0)}%</td>
                    <td className="px-3 py-2 text-right text-red-400">{formatCurrency(row.stressed_var)}</td>
                    <td className="px-3 py-2 text-right text-amber-400">+{formatCurrency(row.risk_added)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* True Diversifiers */}
        {data.diversifiers && data.diversifiers.length > 0 && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
            <div className="font-medium text-emerald-400 mb-2">✅ True Diversifiers</div>
            <div className="flex flex-wrap gap-2">
              {data.diversifiers.map((d, i) => (
                <span key={i} className="px-2 py-1 bg-emerald-500/20 rounded text-sm text-emerald-300">
                  {d.ticker} (ρ={((d.correlation || 0) * 100).toFixed(0)}%)
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// BACKTEST CARD
// ============================================================================
const BacktestCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="VaR Backtesting" icon="📜"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="VaR Backtesting" icon="📜">
      <div className="space-y-4">
        {/* Status */}
        <div className={`p-4 rounded-lg text-center ${getStatusBg(data.status_color)}`}>
          <div className="text-2xl font-bold">{data.status}</div>
          <div className="text-sm mt-1">Accuracy: {formatPercent(data.accuracy)}</div>
        </div>

        {/* Breach Comparison */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Expected Breaches</div>
            <div className="text-xl font-bold text-blue-400">{data.expected_breaches?.toFixed(1)}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.expected_rate)} rate</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Actual Breaches</div>
            <div className={`text-xl font-bold ${Math.abs(data.actual_breaches - data.expected_breaches) > 2 ? 'text-red-400' : 'text-green-400'}`}>
              {data.actual_breaches}
            </div>
            <div className="text-gray-500 text-xs">{formatPercent(data.breach_rate)} rate</div>
          </div>
        </div>

        {/* Rolling Performance */}
        {data.rolling_performance && data.rolling_performance.length > 0 && (
          <div className="bg-[#0a0a0f] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50">
                  <th className="px-3 py-2 text-left text-gray-400">Period</th>
                  <th className="px-3 py-2 text-right text-gray-400">Breaches</th>
                  <th className="px-3 py-2 text-right text-gray-400">Accuracy</th>
                  <th className="px-3 py-2 text-left text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.rolling_performance.map((row, i) => (
                  <tr key={i} className="border-t border-gray-800">
                    <td className="px-3 py-2 text-white">{row.period}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{row.breaches} / {row.expected?.toFixed(1)}</td>
                    <td className="px-3 py-2 text-right">{formatPercent(row.accuracy)}</td>
                    <td className="px-3 py-2">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* PnL vs VaR Chart */}
        {data.overlay_data && data.overlay_data.length > 0 && (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.overlay_data.slice(-60)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d2d3d" />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                <Tooltip contentStyle={{ backgroundColor: '#12121a', border: '1px solid #2d2d3d' }} />
                <Line type="monotone" dataKey="pnl" stroke="#22c55e" dot={false} name="PnL" />
                <Line type="monotone" dataKey="var" stroke="#ef4444" strokeDasharray="5 5" dot={false} name="-VaR" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// KUPIEC TEST CARD
// ============================================================================
const KupiecCard = ({ data, loading }) => {
  if (loading) return <FeatureCard title="Kupiec Test" icon="🔬"><LoadingSpinner /></FeatureCard>;
  if (!data) return null;

  return (
    <FeatureCard title="Kupiec POF Test" icon="🔬">
      <div className="space-y-4">
        {/* Result */}
        <div className={`p-6 rounded-lg text-center ${getStatusBg(data.result_color)}`}>
          <div className="text-3xl font-bold">{data.result}</div>
          <div className="text-sm mt-2 text-gray-300">Model Credibility: {data.credibility}</div>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">LR Statistic</div>
            <div className="text-xl font-bold text-white">{(data.lr_statistic || 0).toFixed(2)}</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">P-Value</div>
            <div className={`text-xl font-bold ${data.p_value > 0.05 ? 'text-green-400' : 'text-red-400'}`}>
              {(data.p_value || 0).toFixed(3)}
            </div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Critical Value</div>
            <div className="text-xl font-bold text-gray-300">{(data.critical_value || 3.84).toFixed(2)}</div>
          </div>
        </div>

        {/* Interpretation */}
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg px-4 py-3 text-sm text-blue-300">
          📊 {data.interpretation}
        </div>

        {/* Breach Comparison */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Observed Breaches</div>
            <div className="text-xl font-bold text-white">{data.breaches_observed}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.observed_rate)} rate</div>
          </div>
          <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
            <div className="text-gray-400 text-xs">Expected Breaches</div>
            <div className="text-xl font-bold text-blue-400">{(data.breaches_expected || 0).toFixed(1)}</div>
            <div className="text-gray-500 text-xs">{formatPercent(data.expected_rate)} rate</div>
          </div>
        </div>
      </div>
    </FeatureCard>
  );
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================
export default function RiskControlPage() {
  const [activeTab, setActiveTab] = useState('loss');
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const tabs = [
    { id: 'loss', label: 'Loss Metrics', icon: '📊' },
    { id: 'attribution', label: 'Risk Attribution', icon: '🧩' },
    { id: 'stress', label: 'Stress Testing', icon: '🌪️' },
    { id: 'validation', label: 'Model Validation', icon: '🔬' }
  ];

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/portfolio/risk-control/dashboard`);
      if (!res.ok) throw new Error('Failed to fetch dashboard');
      const data = await res.json();
      setDashboard(data);
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      console.error('Dashboard fetch failed:', e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 60000);
    return () => clearInterval(interval);
  }, []);

  const features = dashboard?.features || {};

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="max-w-[1600px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <a href="/portfolio" className="text-gray-500 hover:text-gray-300 text-sm">← Portfolio</a>
              <span className="text-gray-600">/</span>
              <h1 className="text-2xl font-bold">🛡️ Risk Control System</h1>
            </div>
            <p className="text-gray-400 text-sm">Institutional-grade VaR analytics with 9 interconnected risk features</p>
          </div>
          <div className="text-right">
            <div className="text-gray-400 text-xs">Last updated</div>
            <div className="text-white text-sm">{lastUpdated?.toLocaleTimeString() || '-'}</div>
          </div>
        </div>

        {/* Error Alert */}
        {error && <ErrorAlert message={error} onRetry={fetchDashboard} />}

        {/* Master Risk Card */}
        <div className="mb-6">
          <MasterRiskCard data={dashboard} loading={loading} />
        </div>

        {/* Tab Navigation */}
        <div className="mb-6">
          <TabNavigation tabs={tabs} active={activeTab} onChange={setActiveTab} />
        </div>

        {/* Tab Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {activeTab === 'loss' && (
            <>
              <ParametricVarCard data={features.parametric_var} loading={loading} />
              <CornishFisherCard data={features.cf_var} loading={loading} />
              <ETLCard data={features.etl} loading={loading} className="lg:col-span-2" />
            </>
          )}

          {activeTab === 'attribution' && (
            <>
              <ComponentVarCard data={features.component_var} loading={loading} />
              <IncrementalVarCard />
            </>
          )}

          {activeTab === 'stress' && (
            <>
              <StressedVarCard data={features.stressed_var} loading={loading} />
              <CorrelationStressCard data={features.correlation_stress} loading={loading} />
            </>
          )}

          {activeTab === 'validation' && (
            <>
              <BacktestCard data={features.backtest} loading={loading} />
              <KupiecCard data={features.kupiec} loading={loading} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
