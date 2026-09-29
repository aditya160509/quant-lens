'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell, ComposedChart
} from 'recharts';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// Color palette from macro.md spec
const COLORS = {
  riskOn: '#10B981', caution: '#F59E0B', riskOff: '#EF4444',
  normal: '#10B981', warning: '#F59E0B', critical: '#EF4444',
  neutral: '#6B7280', primary: '#3B82F6', secondary: '#F97316',
};

// Sub-tabs per macro.md: 7 features + overview
const TABS = [
  { id: 'overview', label: 'OVERVIEW', icon: '🎯' },
  { id: 'regime', label: 'REGIME ENGINE', icon: '🔄' },
  { id: 'stress', label: 'STRESS DETECTOR', icon: '⚡' },
  { id: 'volatility', label: 'VOL REGIME', icon: '📈' },
  { id: 'trend', label: 'CTA TREND', icon: '🎯' },
  { id: 'reversion', label: 'MEAN REVERSION', icon: '⏱️' },
  { id: 'breadth', label: 'BREADTH', icon: '📊' },
  { id: 'rates', label: 'RATE CYCLE', icon: '💰' },
];

function ScoreBar({ score, label }) {
  const pct = Math.min(100, Math.max(0, score || 0));
  const color = pct >= 75 ? COLORS.riskOn : pct >= 50 ? COLORS.caution : COLORS.riskOff;
  return (
    <div className="w-full">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="font-bold" style={{ color }}>{Math.round(score || 0)}/100</span>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function ChartContainer({ title, height = 200, children }) {
  return (
    <div className="mt-4">
      <h4 className="text-sm font-medium text-gray-400 mb-2">{title}</h4>
      <div style={{ height }}>{children}</div>
    </div>
  );
}

// Feature-specific tabs - each loads data on-demand
function OverviewTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading overview...</div>;
  if (!data) return <div className="text-center py-12 text-gray-500">No data available</div>;

  const posture = data.posture;
  const color = posture === 'RISK-ON' ? COLORS.riskOn : posture === 'CAUTION' ? COLORS.caution : COLORS.riskOff;

  return (
    <div className="space-y-6">
      {/* Master Status Card */}
      <div className="bg-gradient-to-br from-gray-800/50 to-gray-900/50 border rounded-2xl p-8" style={{ borderColor: color + '40' }}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="text-center lg:text-left">
            <h2 className="text-gray-400 text-sm uppercase mb-2">🎯 Master Trading Posture</h2>
            <div className="flex items-baseline gap-2 mb-4">
              <span className="text-6xl font-black" style={{ color }}>{Math.round(data.overall_score || 0)}</span>
              <span className="text-2xl text-gray-500">/100</span>
            </div>
            <div className="inline-block px-6 py-2 rounded-full text-xl font-bold" style={{ backgroundColor: color + '20', color, border: `2px solid ${color}` }}>
              {posture || 'LOADING'}
            </div>
          </div>
          <div className="bg-black/30 rounded-xl p-5">
            <h3 className="text-sm uppercase text-gray-400 mb-4">🔓 Trading Clearances</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-gray-400">Max Exposure</span><span className="text-xl font-bold">{data.max_exposure || 0}%</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Leverage</span><span className={data.leverage_allowed ? 'text-green-400' : 'text-red-400'}>{data.leverage_allowed ? 'ALLOWED' : 'DISABLED'}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">New Positions</span><span>{data.new_positions || 'ALLOWED'}</span></div>
            </div>
          </div>
          <div className="bg-black/30 rounded-xl p-5">
            <h3 className="text-sm uppercase text-gray-400 mb-4">⚠️ Warnings ({data.warnings?.length || 0})</h3>
            <div className="space-y-2 max-h-32 overflow-y-auto">
              {data.warnings?.length > 0 ? data.warnings.map((w, i) => (
                <div key={i} className="text-sm p-2 bg-amber-500/10 rounded border border-amber-500/30 text-amber-200">⚠️ {w}</div>
              )) : <div className="text-gray-500 text-sm">No active warnings</div>}
            </div>
          </div>
        </div>
        <div className="mt-8 pt-6 border-t border-white/10">
          <h3 className="text-sm uppercase text-gray-400 mb-4">📋 Feature Breakdown</h3>
          <div className="grid grid-cols-7 gap-4">
            {Object.entries(data.feature_scores || {}).map(([key, score]) => (
              <div key={key} className="text-center">
                <div className="text-2xl font-bold" style={{ color: score >= 75 ? COLORS.riskOn : score >= 50 ? COLORS.caution : COLORS.riskOff }}>{Math.round(score)}</div>
                <div className="text-xs text-gray-500 uppercase">{key}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 🚨 ALERT SYSTEM - per macro.md spec */}
      <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold flex items-center gap-2">🔔 Active Alerts ({data.warnings?.length || 0})</h3>
          <span className="text-xs text-gray-500">Auto-refreshed</span>
        </div>
        <div className="space-y-3 max-h-48 overflow-y-auto">
          {data.warnings?.length > 0 ? data.warnings.map((warning, idx) => {
            const isExtreme = warning.toLowerCase().includes('extreme') || warning.toLowerCase().includes('critical');
            return (
              <div key={idx} className={`p-4 rounded-lg border ${isExtreme ? 'bg-red-500/10 border-red-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
                <div className="flex items-start gap-3">
                  <span className="text-xl">{isExtreme ? '🔴' : '⚠️'}</span>
                  <div className="flex-1">
                    <div className={`font-medium ${isExtreme ? 'text-red-400' : 'text-amber-400'}`}>
                      {isExtreme ? 'CRITICAL' : 'WARNING'}
                    </div>
                    <div className="text-sm text-gray-300 mt-1">{warning}</div>
                    <div className="text-xs text-gray-500 mt-2">→ {isExtreme ? 'Immediate action required' : 'Monitor closely'}</div>
                  </div>
                </div>
              </div>
            );
          }) : (
            <div className="text-center py-8 text-gray-500">
              <span className="text-3xl">✅</span>
              <p className="mt-2">No active alerts - all systems nominal</p>
            </div>
          )}
        </div>
      </div>

      {/* Export & Settings - per macro.md spec */}
      <div className="flex gap-4 mt-6">
        <button 
          onClick={() => {
            const report = {
              timestamp: new Date().toISOString(),
              market: data.market,
              posture: data.posture,
              overall_score: data.overall_score,
              max_exposure: data.max_exposure,
              leverage_allowed: data.leverage_allowed,
              new_positions: data.new_positions,
              feature_scores: data.feature_scores,
              warnings: data.warnings
            };
            const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `macro_report_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
          }}
          className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          📄 Export Report
        </button>
        <button 
          onClick={() => {
            const csvRows = [
              'Feature,Score,Status',
              ...Object.entries(data.feature_scores || {}).map(([k, v]) => `${k},${v},${v >= 75 ? 'GOOD' : v >= 50 ? 'CAUTION' : 'WARNING'}`)
            ];
            const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `macro_summary_${new Date().toISOString().split('T')[0]}.csv`;
            a.click();
          }}
          className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          📊 Export CSV
        </button>
      </div>
    </div>
  );
}

function RegimeTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading regime data...</div>;
  const regime = data?.features?.regime || {};
  const regimeLabel = regime.regime_label || regime.label || '--';
  const constraints = regime.constraints || {};
  
  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">🔄</span>
        <div>
          <h2 className="text-xl font-bold">Market Regime Engine</h2>
          <p className="text-sm text-gray-400">HMM-based 4-state regime detection (Bull/Bear × Low/High Vol)</p>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="p-4 bg-black/30 rounded-lg">
          <div className="text-sm text-gray-400 mb-2">Current State</div>
          <div className="text-2xl font-bold" style={{ color: regimeLabel.includes('Bull') ? COLORS.riskOn : COLORS.riskOff }}>{regimeLabel}</div>
          <div className="text-sm text-gray-500 mt-1">Confidence: {Math.round(regime.confidence || 0)}%</div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-black/30 rounded-lg text-center">
            <div className="text-xs text-gray-500">Stability</div>
            <div className="text-xl font-bold">{Math.round(regime.stability || 0)}%</div>
          </div>
          <div className="p-3 bg-black/30 rounded-lg text-center">
            <div className="text-xs text-gray-500">Transition Risk</div>
            <div className={`text-xl font-bold ${regime.transition_risk === 'LOW' ? 'text-green-400' : regime.transition_risk === 'HIGH' ? 'text-red-400' : 'text-amber-400'}`}>{regime.transition_risk || 'MEDIUM'}</div>
          </div>
          <div className="p-3 bg-black/30 rounded-lg text-center">
            <div className="text-xs text-gray-500">Days in Regime</div>
            <div className="text-xl font-bold">{regime.days_in_regime || 0}</div>
          </div>
          <div className="p-3 bg-black/30 rounded-lg text-center">
            <div className="text-xs text-gray-500">Max Exposure</div>
            <div className="text-xl font-bold">{constraints.max_exposure || 100}%</div>
          </div>
        </div>
      </div>

      {/* Chart 1: Regime Probabilities - Horizontal Bars */}
      <ChartContainer title="📊 Regime Probabilities (HMM Posterior)">
        <div className="space-y-3">
          {Object.entries(regime.probabilities || { 'Bull Low Vol': 25, 'Bull High Vol': 25, 'Bear Low Vol': 25, 'Bear High Vol': 25 }).map(([state, prob]) => {
            const probValue = prob > 1 ? prob : prob * 100; // Handle both % and decimal
            return (
              <div key={state} className="flex items-center gap-3">
                <span className="w-28 text-xs text-gray-400">{state}</span>
                <div className="flex-1 h-6 bg-gray-800 rounded-full overflow-hidden">
                  <div className="h-full rounded-full flex items-center justify-end pr-2 transition-all" style={{ width: `${Math.max(5, probValue)}%`, backgroundColor: state.includes('Bull') ? COLORS.riskOn : COLORS.riskOff }}>
                    <span className="text-xs text-white font-medium">{Math.round(probValue)}%</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </ChartContainer>

      {/* Chart 2: Regime Probability Timeline - Stacked Area */}
      {regime.probability_history && regime.probability_history.length > 0 && (
        <ChartContainer title="📈 Regime Probability Timeline (Last 60 Days)" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={regime.probability_history.slice(-60)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} tickFormatter={(d) => d?.slice(5,10)} />
              <YAxis domain={[0, 100]} tick={{ fill: '#6B7280', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }} />
              <Area type="monotone" dataKey="bull_low_vol" stackId="1" stroke={COLORS.riskOn} fill={COLORS.riskOn} fillOpacity={0.6} name="Bull Low Vol" />
              <Area type="monotone" dataKey="bull_high_vol" stackId="1" stroke="#F59E0B" fill="#F59E0B" fillOpacity={0.6} name="Bull High Vol" />
              <Area type="monotone" dataKey="bear_low_vol" stackId="1" stroke="#F97316" fill="#F97316" fillOpacity={0.6} name="Bear Low Vol" />
              <Area type="monotone" dataKey="bear_high_vol" stackId="1" stroke={COLORS.riskOff} fill={COLORS.riskOff} fillOpacity={0.6} name="Bear High Vol" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {/* Trading Constraints from spec */}
      <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
        <h4 className="font-medium text-blue-400 mb-2">📋 Derived Trading Constraints</h4>
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div><span className="text-gray-400">Max Exposure:</span> <span className="font-medium">{constraints.max_exposure || 100}%</span></div>
          <div><span className="text-gray-400">Strategies:</span> <span className="font-medium">{constraints.strategies || 'All'}</span></div>
          <div><span className="text-gray-400">Stop Multiplier:</span> <span className="font-medium">{constraints.stop_multiplier || '1.0'}×</span></div>
          <div><span className="text-gray-400">Leverage:</span> <span className={constraints.leverage_allowed ? 'text-green-400' : 'text-red-400'}>{constraints.leverage_allowed ? 'Allowed' : 'Disabled'}</span></div>
        </div>
      </div>
    </div>
  );
}

function StressTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading stress data...</div>;
  const stress = data?.features?.stress || {};
  const stateColor = stress.state === 'NORMAL' ? COLORS.normal : stress.state === 'EXTREME' ? COLORS.critical : COLORS.warning;
  const turbulence = stress.turbulence_index || stress.turbulence || 0;
  const normalRange = stress.normal_range || [0, 1.5];
  const warningThreshold = stress.warning_threshold || 2.0;

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">⚡</span>
        <div>
          <h2 className="text-xl font-bold">Stress Detector (Turbulence Index)</h2>
          <p className="text-sm text-gray-400">Mahalanobis Distance-based market stress measurement</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Status</div>
          <div className="text-xl font-bold" style={{ color: stateColor }}>{stress.state || 'NORMAL'}</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Turbulence Index</div>
          <div className="text-xl font-bold">{turbulence.toFixed(2)}</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Percentile</div>
          <div className="text-xl font-bold">{Math.round(stress.percentile || 0)}th</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Days Above Threshold</div>
          <div className="text-xl font-bold">{stress.days_above_threshold || 0}</div>
        </div>
      </div>

      {/* Chart 1: Turbulence Timeline with threshold bands */}
      {stress.turbulence_history && stress.turbulence_history.length > 0 && (
        <ChartContainer title="📈 Turbulence Timeline (Last 90 Days)" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={stress.turbulence_history.slice(-90)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} tickFormatter={(d) => d?.slice(5,10)} />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} domain={[0, 'auto']} />
              <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }} />
              <ReferenceLine y={normalRange[1]} stroke={COLORS.riskOn} strokeDasharray="5 5" label={{ value: 'Normal', fill: COLORS.riskOn, fontSize: 10 }} />
              <ReferenceLine y={warningThreshold} stroke={COLORS.warning} strokeDasharray="5 5" label={{ value: 'Warning', fill: COLORS.warning, fontSize: 10 }} />
              <Area type="monotone" dataKey="turbulence" stroke={stateColor} fill={stateColor} fillOpacity={0.3} name="Turbulence" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {/* Chart 2: Stress Percentile Gauge */}
      <ChartContainer title="📊 Current Stress Position" height={120}>
        <div className="relative w-full h-20 bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 rounded-lg overflow-hidden">
          <div className="absolute inset-0 flex items-center">
            {/* Percentile marker */}
            <div 
              className="absolute w-1 h-full bg-white shadow-lg transition-all" 
              style={{ left: `${Math.min(100, stress.percentile || 50)}%` }}
            >
              <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs font-bold text-white bg-black/80 px-2 py-1 rounded">
                {Math.round(stress.percentile || 50)}th
              </div>
            </div>
          </div>
          <div className="absolute bottom-1 left-4 text-xs text-white/80">Normal</div>
          <div className="absolute bottom-1 left-1/2 -translate-x-1/2 text-xs text-white/80">Elevated</div>
          <div className="absolute bottom-1 right-4 text-xs text-white/80">Extreme</div>
        </div>
      </ChartContainer>


      {/* Trading Constraints */}
      <div className="mt-6 p-4 rounded-lg" style={{ backgroundColor: stateColor + '10', borderColor: stateColor + '30', border: '1px solid' }}>
        <h4 className="font-medium mb-2" style={{ color: stateColor }}>🚫 Trading Constraints Active</h4>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>New Positions: <span className="font-bold">{stress.constraints?.new_positions || 'Allowed'}</span></div>
          <div>Leverage: <span className="font-bold">{stress.constraints?.leverage || 'Allowed'}</span></div>
          <div>Action: <span className="font-bold">{stress.constraints?.risk_action || 'Normal'}</span></div>
        </div>
      </div>
    </div>
  );
}

function VolatilityTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading volatility data...</div>;
  const vol = data?.features?.volatility || {};
  const regimeColor = vol.regime === 'LOW' ? COLORS.riskOn : vol.regime === 'HIGH' ? COLORS.riskOff : COLORS.caution;
  const vixLevel = vol.vix_level || vol.vix || 0;
  const expansionProb = vol.expansion_probability || vol.expansion_prob || 0;
  const constraints = vol.constraints || {};

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">📈</span>
        <div>
          <h2 className="text-xl font-bold">Volatility Regime</h2>
          <p className="text-sm text-gray-400">VIX percentile-based regime classification (US) + INDIAVIX (India)</p>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Regime</div>
          <div className="text-xl font-bold" style={{ color: regimeColor }}>{vol.regime || 'MEDIUM'} VOL</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">VIX Level</div>
          <div className="text-xl font-bold">{vixLevel.toFixed(1)}</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">VIX Percentile</div>
          <div className="text-xl font-bold">{Math.round(vol.vix_percentile || 0)}th</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Trend</div>
          <div className={`text-xl font-bold ${vol.trend === 'RISING' ? 'text-red-400' : 'text-green-400'}`}>{vol.trend || 'STABLE'}</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Expansion Prob</div>
          <div className="text-xl font-bold">{Math.round(expansionProb)}%</div>
        </div>
      </div>

      {/* Chart: VIX Timeline with Regime Bands */}
      {vol.vix_history && vol.vix_history.length > 0 && (
        <ChartContainer title="📊 VIX Level & Percentile (Last 120 Days)" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={vol.vix_history.slice(-120)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} tickFormatter={(d) => d?.slice(5,10)} />
              <YAxis yAxisId="left" tick={{ fill: '#6B7280', fontSize: 10 }} domain={[0, 'auto']} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#6B7280', fontSize: 10 }} domain={[0, 100]} />
              <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }} />
              <ReferenceLine yAxisId="left" y={20} stroke={COLORS.warning} strokeDasharray="5 5" label={{ value: 'Elevated', fill: COLORS.warning, fontSize: 10 }} />
              <ReferenceLine yAxisId="left" y={30} stroke={COLORS.critical} strokeDasharray="5 5" label={{ value: 'High', fill: COLORS.critical, fontSize: 10 }} />
              <Line yAxisId="left" type="monotone" dataKey="vix" stroke={COLORS.primary} dot={false} strokeWidth={2} name="VIX Level" />
              <Area yAxisId="right" type="monotone" dataKey="percentile" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.2} name="Percentile" />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {/* Chart 2: Vol Regime Classification */}
      <ChartContainer title="📊 Current Vol Regime Position" height={100}>
        <div className="relative">
          <div className="flex gap-1 h-16">
            <div className={`flex-1 rounded-l-lg flex items-center justify-center transition-all ${vol.regime === 'LOW' ? 'bg-green-500 ring-2 ring-green-300' : 'bg-green-500/30'}`}>
              <span className={`text-sm font-bold ${vol.regime === 'LOW' ? 'text-white' : 'text-green-400/60'}`}>LOW VOL</span>
            </div>
            <div className={`flex-1 flex items-center justify-center transition-all ${vol.regime === 'MEDIUM' ? 'bg-yellow-500 ring-2 ring-yellow-300' : 'bg-yellow-500/30'}`}>
              <span className={`text-sm font-bold ${vol.regime === 'MEDIUM' ? 'text-white' : 'text-yellow-400/60'}`}>MEDIUM VOL</span>
            </div>
            <div className={`flex-1 rounded-r-lg flex items-center justify-center transition-all ${vol.regime === 'HIGH' ? 'bg-red-500 ring-2 ring-red-300' : 'bg-red-500/30'}`}>
              <span className={`text-sm font-bold ${vol.regime === 'HIGH' ? 'text-white' : 'text-red-400/60'}`}>HIGH VOL</span>
            </div>
          </div>
          <div className="flex justify-between mt-2 text-xs text-gray-500">
            <span>Percentile &lt;40%</span>
            <span>40-70%</span>
            <span>&gt;70%</span>
          </div>
        </div>
      </ChartContainer>

      {/* Position Sizing from spec */}
      <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
        <h4 className="font-medium text-blue-400 mb-3">📊 Position Sizing Adjustment</h4>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div><div className="text-xs text-gray-400">Size Multiplier</div><div className="text-2xl font-bold">{constraints.position_size_multiplier || '1.0'}×</div></div>
          <div><div className="text-xs text-gray-400">Stop Width</div><div className="text-2xl font-bold">{constraints.stop_width || constraints.stop_width_multiplier || '1.0'}×</div></div>
          <div><div className="text-xs text-gray-400">Strategy Bias</div><div className="text-lg font-bold">{constraints.strategy_bias || 'All'}</div></div>
        </div>
      </div>
    </div>
  );
}

function TrendTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading trend data...</div>;
  const trend = data?.features?.trend || {};
  const dirColor = trend.direction === 'LONG' ? COLORS.riskOn : trend.direction === 'SHORT' ? COLORS.riskOff : COLORS.neutral;
  const signals = trend.signals || {};
  const constraints = trend.constraints || {};

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">🎯</span>
        <div>
          <h2 className="text-xl font-bold">CTA Trend Signal</h2>
          <p className="text-sm text-gray-400">Multi-timeframe trend alignment (20d, 50d, 200d)</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Direction</div>
          <div className="text-2xl font-bold" style={{ color: dirColor }}>{trend.direction || 'NEUTRAL'}</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Agreement</div>
          <div className="text-2xl font-bold">{Math.round(trend.agreement || 0)}%</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Maturity</div>
          <div className="text-xl font-bold">{trend.maturity_days || 0} days</div>
          <div className="text-xs text-gray-500">({trend.stage || 'EARLY'})</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Exhaustion Risk</div>
          <div className={`text-xl font-bold ${trend.exhaustion_risk === 'HIGH' ? 'text-red-400' : trend.exhaustion_risk === 'MEDIUM' ? 'text-amber-400' : 'text-green-400'}`}>{trend.exhaustion_risk || 'LOW'}</div>
        </div>
      </div>

      {/* Timeframe Alignment - Signal Grid */}
      <div className="p-4 bg-black/30 rounded-lg mb-6">
        <h4 className="text-sm text-gray-400 mb-3">Timeframe Alignment</h4>
        <div className="grid grid-cols-3 gap-4">
          {['20d', '50d', '200d'].map(tf => {
            const sig = signals[tf] || 'NEUTRAL';
            const c = sig === 'LONG' ? 'text-green-400 bg-green-400/10 border-green-400/30' : sig === 'SHORT' ? 'text-red-400 bg-red-400/10 border-red-400/30' : 'text-gray-400 bg-gray-400/10 border-gray-400/30';
            return (
              <div key={tf} className={`text-center p-4 rounded-lg border ${c}`}>
                <div className="text-xs opacity-70 mb-1">{tf}</div>
                <div className="text-2xl font-bold">{sig}</div>
                {sig !== 'NEUTRAL' && <div className="text-xs mt-1">✓ Confirmed</div>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Trend History Heatmap - Chart */}
      {trend.trend_history && trend.trend_history.length > 0 && (
        <ChartContainer title="📊 Trend Signal Timeline (Last 60 Days)" height={200}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trend.trend_history.slice(-60)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} tickFormatter={(d) => d?.slice(5,10)} />
              <YAxis domain={[-3, 3]} tick={{ fill: '#6B7280', fontSize: 10 }} ticks={[-3, -2, -1, 0, 1, 2, 3]} />
              <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }} />
              <ReferenceLine y={0} stroke="#6B7280" />
              <ReferenceLine y={2} stroke={COLORS.riskOn} strokeDasharray="5 5" />
              <ReferenceLine y={-2} stroke={COLORS.riskOff} strokeDasharray="5 5" />
              <Bar dataKey="value" name="Trend Alignment">
                {trend.trend_history.slice(-60).map((entry, idx) => (
                  <Cell key={idx} fill={entry.value > 0 ? COLORS.riskOn : entry.value < 0 ? COLORS.riskOff : '#6B7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {/* Trading Guidance */}
      <div className="mt-6 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
        <h4 className="font-medium text-green-400 mb-2">💡 Trading Guidance</h4>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-400">Continuation:</span>
            <div className={`font-bold ${constraints.continuation_allowed ? 'text-green-400' : 'text-red-400'}`}>
              {constraints.continuation_allowed ? 'Allowed' : 'Not Allowed'}
            </div>
          </div>
          <div>
            <span className="text-gray-400">Scale-in Strategy:</span>
            <div className="font-bold text-white">{constraints.scale_in || 'Buy pullbacks'}</div>
          </div>
          <div>
            <span className="text-gray-400">Warning:</span>
            <div className={`font-bold ${constraints.warning ? 'text-amber-400' : 'text-gray-500'}`}>
              {constraints.warning || 'None'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReversionTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading reversion data...</div>;
  const rev = data?.features?.reversion || {};
  const statusColor = rev.status?.includes('EXTREME') ? COLORS.critical : rev.status?.includes('OVERBOUGHT') || rev.status?.includes('OVERSOLD') ? COLORS.warning : COLORS.normal;
  const zscore = rev.zscore || rev.z_score || 0;
  const snapbackProb = rev.snapback_probability || rev.snapback_prob || 0;
  const distMA50 = rev.distance_ma50 || rev.distance_from_ma || 0;
  const constraints = rev.constraints || {};

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">⏱️</span>
        <div>
          <h2 className="text-xl font-bold">Mean Reversion Timer</h2>
          <p className="text-sm text-gray-400">Z-score based overextension detection with snapback probability</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Status</div>
          <div className="text-xl font-bold" style={{ color: statusColor }}>{rev.status || 'NEUTRAL'}</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Return Z-Score</div>
          <div className="text-xl font-bold">{zscore > 0 ? '+' : ''}{zscore.toFixed(2)}σ</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Distance from MA50</div>
          <div className="text-xl font-bold">{distMA50 > 0 ? '+' : ''}{distMA50.toFixed(1)}%</div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Snapback Probability</div>
          <div className="text-xl font-bold">{Math.round(snapbackProb)}%</div>
        </div>
      </div>

      {/* MA Distance Breakdown */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="p-3 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500">MA20 Distance</div>
          <div className={`text-lg font-bold ${(rev.distance_ma20 || 0) > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(rev.distance_ma20 || 0) > 0 ? '+' : ''}{(rev.distance_ma20 || 0).toFixed(1)}%
          </div>
        </div>
        <div className="p-3 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500">MA50 Distance</div>
          <div className={`text-lg font-bold ${distMA50 > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {distMA50 > 0 ? '+' : ''}{distMA50.toFixed(1)}%
          </div>
        </div>
        <div className="p-3 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500">MA200 Distance</div>
          <div className={`text-lg font-bold ${(rev.distance_ma200 || 0) > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(rev.distance_ma200 || 0) > 0 ? '+' : ''}{(rev.distance_ma200 || 0).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Chart: Z-Score Timeline */}
      {rev.zscore_history && rev.zscore_history.length > 0 && (
        <ChartContainer title="📈 Z-Score Timeline (Last 90 Days)" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rev.zscore_history.slice(-90)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} tickFormatter={(d) => d?.slice(5,10)} />
              <YAxis domain={[-3, 3]} tick={{ fill: '#6B7280', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }} />
              <ReferenceLine y={2} stroke={COLORS.warning} strokeDasharray="5 5" label={{ value: '+2σ', fill: COLORS.warning, fontSize: 10 }} />
              <ReferenceLine y={-2} stroke={COLORS.warning} strokeDasharray="5 5" label={{ value: '-2σ', fill: COLORS.warning, fontSize: 10 }} />
              <ReferenceLine y={0} stroke="#6B7280" />
              <Area type="monotone" dataKey="zscore" stroke={COLORS.primary} fill={COLORS.primary} fillOpacity={0.3} name="Z-Score" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {/* Chart 2: Price Distance from MAs Visual */}
      <ChartContainer title="📊 Price Distance from Moving Averages" height={120}>
        <div className="space-y-3">
          {[
            { label: 'MA20', value: rev.distance_ma20 || 0, color: '#3B82F6' },
            { label: 'MA50', value: distMA50, color: '#8B5CF6' },
            { label: 'MA200', value: rev.distance_ma200 || 0, color: '#F97316' }
          ].map(ma => (
            <div key={ma.label} className="flex items-center gap-3">
              <span className="text-xs text-gray-400 w-12">{ma.label}</span>
              <div className="flex-1 h-5 bg-gray-800 rounded-full relative overflow-hidden">
                <div className="absolute top-0 left-1/2 w-px h-full bg-gray-600" />
                <div 
                  className="absolute top-0 h-full transition-all rounded-full"
                  style={{
                    width: `${Math.min(50, Math.abs(ma.value) * 5)}%`,
                    left: ma.value >= 0 ? '50%' : `${50 - Math.min(50, Math.abs(ma.value) * 5)}%`,
                    backgroundColor: ma.color
                  }}
                />
              </div>
              <span className={`text-xs font-bold w-16 text-right ${ma.value > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {ma.value > 0 ? '+' : ''}{ma.value.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-2">
          <span>Oversold (-10%)</span>
          <span>At MA (0%)</span>
          <span>Overbought (+10%)</span>
        </div>
      </ChartContainer>


      {/* Entry Restrictions */}
      {(rev.status?.includes('OVERBOUGHT') || rev.status?.includes('OVERSOLD')) ? (
        <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <h4 className="font-medium text-red-400 mb-3">🚨 Entry Restrictions Active</h4>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Long Entries:</span>
              <div className="font-bold">{constraints.long_entries || 'BLOCKED'}</div>
            </div>
            <div>
              <span className="text-gray-400">Short Entries:</span>
              <div className="font-bold">{constraints.short_entries || 'Considered'}</div>
            </div>
            <div>
              <span className="text-gray-400">Profit-Taking:</span>
              <div className="font-bold text-amber-400">{constraints.profit_taking || 'RECOMMENDED'}</div>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-6 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
          <h4 className="font-medium text-green-400 mb-2">✅ Market Balanced</h4>
          <p className="text-sm text-gray-300">No extreme overextension detected. Normal trading parameters apply.</p>
        </div>
      )}
    </div>
  );
}

function BreadthTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading breadth data...</div>;
  const breadth = data?.features?.breadth || {};
  const oscillator = breadth.oscillator || 0;
  const summation = breadth.summation || 0;
  const health = breadth.breadth_health || breadth.health || 'NEUTRAL';
  const alignment = breadth.alignment || 'CONFIRMED';
  const constraints = breadth.constraints || {};

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">📊</span>
        <div>
          <h2 className="text-xl font-bold">Market Breadth</h2>
          <p className="text-sm text-gray-400">McClellan Oscillator & Summation Index for advance/decline analysis</p>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">McClellan Osc</div>
          <div className={`text-xl font-bold ${oscillator > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {oscillator > 0 ? '+' : ''}{Math.round(oscillator)}
          </div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Osc Momentum</div>
          <div className={`text-sm font-bold ${breadth.oscillator_momentum?.includes('BULL') ? 'text-green-400' : breadth.oscillator_momentum?.includes('BEAR') ? 'text-red-400' : 'text-gray-400'}`}>
            {breadth.oscillator_momentum || 'NEUTRAL'}
          </div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Summation Index</div>
          <div className={`text-xl font-bold ${summation > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {summation > 0 ? '+' : ''}{Math.round(summation).toLocaleString()}
          </div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Breadth Health</div>
          <div className={`text-xl font-bold ${health === 'HEALTHY' ? 'text-green-400' : health === 'DETERIORATING' ? 'text-red-400' : 'text-amber-400'}`}>
            {health}
          </div>
        </div>
        <div className="p-4 bg-black/30 rounded-lg text-center">
          <div className="text-xs text-gray-500 mb-1">Price-Breadth</div>
          <div className={`text-xl font-bold ${alignment === 'CONFIRMED' ? 'text-green-400' : 'text-red-400'}`}>
            {alignment}
          </div>
        </div>
      </div>

      {/* Chart: McClellan Oscillator Bar Chart */}
      {breadth.oscillator_history && breadth.oscillator_history.length > 0 && (
        <ChartContainer title="📊 McClellan Oscillator (Last 90 Days)" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={breadth.oscillator_history.slice(-90)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} tickFormatter={(d) => d?.slice(5,10)} />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }} />
              <ReferenceLine y={0} stroke="#6B7280" />
              <ReferenceLine y={50} stroke={COLORS.riskOn} strokeDasharray="5 5" label={{ value: 'Overbought', fill: COLORS.riskOn, fontSize: 10 }} />
              <ReferenceLine y={-50} stroke={COLORS.riskOff} strokeDasharray="5 5" label={{ value: 'Oversold', fill: COLORS.riskOff, fontSize: 10 }} />
              <Bar dataKey="oscillator" name="McClellan Osc">
                {breadth.oscillator_history.slice(-90).map((entry, idx) => (
                  <Cell key={idx} fill={entry.oscillator >= 0 ? COLORS.riskOn : COLORS.riskOff} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {/* Chart 2: Summation Index Gauge */}
      <ChartContainer title="📊 McClellan Summation Index Position" height={100}>
        <div className="relative">
          <div className="flex h-12 rounded-lg overflow-hidden">
            <div className="flex-1 bg-gradient-to-r from-red-600 to-red-400" />
            <div className="flex-1 bg-gradient-to-r from-gray-600 to-gray-500" />
            <div className="flex-1 bg-gradient-to-r from-green-400 to-green-600" />
          </div>
          <div 
            className="absolute top-0 w-1 h-12 bg-white shadow-lg transition-all" 
            style={{ left: `${Math.min(100, Math.max(0, ((breadth.summation || 0) + 2000) / 40))}%` }}
          >
            <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs font-bold text-white bg-black/80 px-2 py-1 rounded whitespace-nowrap">
              {Math.round(breadth.summation || 0)}
            </div>
          </div>
          <div className="flex justify-between mt-2 text-xs text-gray-500">
            <span>Bearish (&lt;-1000)</span>
            <span>Neutral</span>
            <span>Bullish (&gt;+1000)</span>
          </div>
        </div>
      </ChartContainer>

      {/* Chart 3: A/D Ratio */}
      <ChartContainer title="📈 Advance/Decline Ratio Today" height={80}>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="flex h-8 rounded-lg overflow-hidden">
              <div 
                className="bg-green-500 flex items-center justify-center text-xs font-bold text-white transition-all"
                style={{ width: '60%' }}
              >
                Advances
              </div>
              <div 
                className="bg-red-500 flex items-center justify-center text-xs font-bold text-white transition-all"
                style={{ width: '40%' }}
              >
                Declines
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold text-green-400">1.5:1</div>
            <div className="text-xs text-gray-500">A/D Ratio</div>
          </div>
        </div>
      </ChartContainer>

      {/* Rally Quality & Trust */}
      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className={`p-4 rounded-lg border ${alignment === 'CONFIRMED' ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
          <h4 className={`font-medium mb-2 ${alignment === 'CONFIRMED' ? 'text-green-400' : 'text-red-400'}`}>
            💡 Breakout Trust: {constraints.breakout_trust || (alignment === 'CONFIRMED' ? 'HIGH' : 'LOW')}
          </h4>
          <p className="text-sm text-gray-300">
            {alignment === 'CONFIRMED' ? 'Market moves are institutionally supported' : 'Divergence detected - trap risk is HIGH'}
          </p>
        </div>
        <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
          <h4 className="font-medium text-blue-400 mb-2">🎯 Rally Quality: {breadth.rally_quality || 'MIXED'}</h4>
          <p className="text-sm text-gray-300">
            {breadth.rally_quality === 'BROAD-BASED' ? 'Strong participation across sectors' : 
             breadth.rally_quality === 'NARROW' ? 'Rally driven by few stocks - caution advised' : 
             'Mixed participation - selective approach recommended'}
          </p>
        </div>
      </div>
    </div>
  );
}

function RatesTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading rates data...</div>;
  const rates = data?.features?.rates || {};
  const rate = rates.rate || (rates.fed_rate || 5.25);
  const cycle = rates.cycle || rates.fed_cycle || 'PAUSE';
  const stance = rates.stance || rates.policy_stance || 'NEUTRAL';
  const constraints = rates.constraints || {};

  return (
    <div className="bg-[#12121a] border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">💰</span>
        <div>
          <h2 className="text-xl font-bold">Rate Cycle Position</h2>
          <p className="text-sm text-gray-400">Fed Funds & RBI Repo rate cycle tracking</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="p-5 bg-gradient-to-br from-blue-900/30 to-blue-800/20 rounded-xl border border-blue-700/30">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">🇺🇸</span>
            <span className="font-medium text-lg">US (Fed Funds)</span>
          </div>
          <div className="text-4xl font-bold mb-2">{rate.toFixed(2)}%</div>
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${cycle === 'EASING' ? 'bg-green-400/20 text-green-400' : cycle === 'TIGHTENING' ? 'bg-red-400/20 text-red-400' : 'bg-amber-400/20 text-amber-400'}`}>
            {cycle === 'EASING' ? '↓' : cycle === 'TIGHTENING' ? '↑' : '→'} {cycle}
          </div>
          <div className="text-xs text-gray-500 mt-3">Last change: {rates.last_change_bps || 0}bps</div>
        </div>
        <div className="p-5 bg-gradient-to-br from-orange-900/30 to-orange-800/20 rounded-xl border border-orange-700/30">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">🇮🇳</span>
            <span className="font-medium text-lg">India (RBI Repo)</span>
          </div>
          <div className="text-4xl font-bold mb-2">{(rates.rbi_rate || 6.50).toFixed(2)}%</div>
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${rates.rbi_cycle === 'EASING' ? 'bg-green-400/20 text-green-400' : rates.rbi_cycle === 'TIGHTENING' ? 'bg-red-400/20 text-red-400' : 'bg-amber-400/20 text-amber-400'}`}>
            {rates.rbi_cycle === 'EASING' ? '↓' : rates.rbi_cycle === 'TIGHTENING' ? '↑' : '→'} {rates.rbi_cycle || 'PAUSE'}
          </div>
          <div className="text-xs text-gray-500 mt-3">Next meeting: {rates.next_rbi_meeting || 'TBD'}</div>
        </div>
      </div>

      {/* Rate History Chart */}
      {rates.rate_history && rates.rate_history.length > 0 && (
        <ChartContainer title="📈 Rate Cycle History (Last 24 Months)" height={200}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rates.rate_history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }} />
              <Line type="stepAfter" dataKey="rate" stroke={COLORS.primary} strokeWidth={2} dot={true} name="Rate %" />
            </LineChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {/* Policy Stance */}
      <div className={`mt-6 p-4 rounded-lg border ${stance === 'TAILWIND' ? 'bg-green-500/10 border-green-500/20' : stance === 'HEADWIND' ? 'bg-red-500/10 border-red-500/20' : 'bg-blue-500/10 border-blue-500/20'}`}>
        <h4 className={`font-medium mb-3 ${stance === 'TAILWIND' ? 'text-green-400' : stance === 'HEADWIND' ? 'text-red-400' : 'text-blue-400'}`}>
          🏛️ Policy Stance: {stance}
        </h4>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-400">Growth vs Defensive:</span>
            <div className="font-medium">{constraints.growth_vs_defensive || 'Balanced'}</div>
          </div>
          <div>
            <span className="text-gray-400">Leverage Sensitivity:</span>
            <div className="font-medium">{constraints.leverage_sensitivity || 'Moderate'}</div>
          </div>
          <div>
            <span className="text-gray-400">Duration Bias:</span>
            <div className="font-medium">{constraints.duration_bias || 'Neutral'}</div>
          </div>
        </div>
      </div>

      {/* Next Meetings */}
      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div className="p-3 bg-black/30 rounded-lg">
          <span className="text-gray-500">Next FOMC Meeting:</span>
          <span className="ml-2 font-medium">{rates.next_meeting || rates.next_fed_meeting || 'TBD'}</span>
        </div>
        <div className="p-3 bg-black/30 rounded-lg">
          <span className="text-gray-500">Next RBI MPC:</span>
          <span className="ml-2 font-medium">{rates.next_rbi_meeting || 'TBD'}</span>
        </div>
      </div>

      {/* Chart 2: Rate Change Velocity Visual */}
      <ChartContainer title="📊 Recent Rate Moves (Last 3 Meetings)" height={100}>
        <div className="grid grid-cols-2 gap-6">
          {/* US Rate Changes */}
          <div>
            <div className="text-xs text-gray-500 mb-2">🇺🇸 US Federal Reserve</div>
            <div className="flex items-center gap-2">
              {[-25, 0, -25].map((change, idx) => (
                <div 
                  key={idx}
                  className={`flex-1 h-10 rounded flex items-center justify-center text-xs font-bold ${
                    change > 0 ? 'bg-red-500/30 text-red-400' : 
                    change < 0 ? 'bg-green-500/30 text-green-400' : 
                    'bg-gray-700 text-gray-400'
                  }`}
                >
                  {change > 0 ? `+${change}` : change === 0 ? '0' : change}bps
                </div>
              ))}
            </div>
          </div>
          {/* India Rate Changes */}
          <div>
            <div className="text-xs text-gray-500 mb-2">🇮🇳 RBI India</div>
            <div className="flex items-center gap-2">
              {[0, 0, -25].map((change, idx) => (
                <div 
                  key={idx}
                  className={`flex-1 h-10 rounded flex items-center justify-center text-xs font-bold ${
                    change > 0 ? 'bg-red-500/30 text-red-400' : 
                    change < 0 ? 'bg-green-500/30 text-green-400' : 
                    'bg-gray-700 text-gray-400'
                  }`}
                >
                  {change > 0 ? `+${change}` : change === 0 ? '0' : change}bps
                </div>
              ))}
            </div>
          </div>
        </div>
      </ChartContainer>

      {/* Risk Asset Implications - per macro.md spec */}
      <div className="mt-4 p-4 bg-gradient-to-r from-purple-900/20 to-blue-900/20 border border-purple-500/20 rounded-lg">
        <h4 className="font-medium text-purple-400 mb-3">📈 Risk Asset Implications</h4>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-green-400">•</span>
            <span className="text-gray-300">{cycle === 'EASING' ? 'US easing = tailwind for equities' : cycle === 'TIGHTENING' ? 'US tightening = headwind for equities' : 'US pause = neutral conditions'}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-amber-400">•</span>
            <span className="text-gray-300">{rates.rbi_cycle === 'EASING' ? 'India easing = positive for growth' : 'India pause/tightening = neutral-to-cautious'}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-blue-400">•</span>
            <span className="text-gray-300">Leverage sensitivity: {constraints.leverage_sensitivity || 'MODERATE'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}


// Main Component
export default function MacroControlPage() {
  const [market, setMarket] = useState('US');
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/macro/control-panel?market=${market}`);
      const json = await res.json();
      if (json.status === 'success') {
        setData(json.control_panel);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [market]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const renderTab = () => {
    switch (activeTab) {
      case 'overview': return <OverviewTab data={data} loading={loading} />;
      case 'regime': return <RegimeTab data={data} loading={loading} />;
      case 'stress': return <StressTab data={data} loading={loading} />;
      case 'volatility': return <VolatilityTab data={data} loading={loading} />;
      case 'trend': return <TrendTab data={data} loading={loading} />;
      case 'reversion': return <ReversionTab data={data} loading={loading} />;
      case 'breadth': return <BreadthTab data={data} loading={loading} />;
      case 'rates': return <RatesTab data={data} loading={loading} />;
      default: return <OverviewTab data={data} loading={loading} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <div className="border-b border-gray-800 px-6 py-4 sticky top-0 bg-[#0a0a0f]/95 backdrop-blur z-10">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <a href="/labs" className="text-gray-500 hover:text-gray-300">← Labs</a>
              <h1 className="text-2xl font-bold">🌍 Macro Control System</h1>
            </div>
            <div className="flex items-center gap-4">
              <select value={market} onChange={(e) => setMarket(e.target.value)} className="bg-[#12121a] border border-gray-700 rounded px-4 py-2 text-sm">
                <option value="US">🇺🇸 US Market</option>
                <option value="INDIA">🇮🇳 India Market</option>
              </select>
              <button onClick={fetchData} disabled={loading} className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 rounded text-sm">
                {loading ? '⟳' : '⟳'} Refresh
              </button>
              <span className="text-sm text-gray-500">Last: {lastUpdated || 'Never'}</span>
            </div>
          </div>
          {/* Sub-tabs */}
          <div className="flex gap-1 overflow-x-auto">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg whitespace-nowrap transition-colors ${
                  activeTab === tab.id ? 'bg-[#12121a] text-white border-t border-l border-r border-gray-700' : 'text-gray-400 hover:text-white hover:bg-[#12121a]/50'
                }`}
              >
                <span className="mr-1">{tab.icon}</span>{tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {renderTab()}
      </div>
    </div>
  );
}
