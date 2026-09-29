'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLSummaryPage() {
  const [scoreResult, setScoreResult] = useState(null);
  const [rankingResult, setRankingResult] = useState(null);
  const [positionResult, setPositionResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const [signal, setSignal] = useState({
    ml_probability: 0.65,
    historical_win_rate: 0.55,
    sharpe_ratio: 0.8,
    regime_fit: 0.7,
    model_confidence: 0.6,
    momentum_score: 0.3,
    volume_score: 1.2
  });

  const [portfolioValue, setPortfolioValue] = useState(100000);

  const scoreSignal = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/summary/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(signal)
      });
      const data = await res.json();
      if (data.status === 'success') {
        setScoreResult(data.score);
      }
    } catch (error) {
      console.error('Failed to score signal:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPositionSize = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/portfolio/position-size`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          signal: signal,
          portfolio_value: portfolioValue,
          risk_per_trade: 0.02
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setPositionResult(data.recommendation);
      }
    } catch (error) {
      console.error('Failed to get position size:', error);
    }
  };

  const getTierColor = (tier) => {
    switch (tier) {
      case 'A': return 'text-green-400 bg-green-500/20';
      case 'B': return 'text-blue-400 bg-blue-500/20';
      case 'C': return 'text-yellow-400 bg-yellow-500/20';
      case 'D': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <a href="/labs/ml" className="text-gray-500 hover:text-gray-300">← ML</a>
            <span className="text-gray-600">/</span>
            <h1 className="text-2xl font-bold">📋 Summary - Scorecards & Sizing</h1>
          </div>
          <p className="text-gray-400">Aggregate ML insights into actionable scores and position recommendations</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Signal Scoring */}
          <div className="space-y-6">
            {/* Signal Input */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Signal Metrics</h2>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { key: 'ml_probability', label: 'ML Probability', min: 0, max: 1 },
                  { key: 'historical_win_rate', label: 'Win Rate', min: 0, max: 1 },
                  { key: 'sharpe_ratio', label: 'Sharpe Ratio', min: -3, max: 3 },
                  { key: 'regime_fit', label: 'Regime Fit', min: 0, max: 1 },
                  { key: 'model_confidence', label: 'Model Confidence', min: 0, max: 1 },
                  { key: 'momentum_score', label: 'Momentum', min: -1, max: 1 },
                ].map(field => (
                  <div key={field.key}>
                    <label className="block text-xs text-gray-400 mb-1">{field.label}</label>
                    <input
                      type="number"
                      step="0.01"
                      min={field.min}
                      max={field.max}
                      value={signal[field.key]}
                      onChange={(e) => setSignal({ ...signal, [field.key]: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-[#1a1a24] border border-gray-700 rounded px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={scoreSignal}
                disabled={loading}
                className="w-full mt-4 bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 rounded py-3 font-medium transition-all"
              >
                {loading ? 'Scoring...' : 'Score This Signal'}
              </button>
            </div>

            {/* Score Result */}
            {scoreResult && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Signal Scorecard</h2>
                
                {/* Main Score */}
                <div className="text-center mb-6">
                  <div className="text-5xl font-bold text-blue-400 mb-2">
                    {(scoreResult.composite_score * 100).toFixed(0)}
                  </div>
                  <div className={`inline-block px-4 py-2 rounded-lg text-lg font-bold ${getTierColor(scoreResult.tier)}`}>
                    Tier {scoreResult.tier}
                  </div>
                </div>

                {/* Score Breakdown */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-gray-400">Score Breakdown</h3>
                  {Object.entries(scoreResult.breakdown || {}).map(([metric, data]) => (
                    <div key={metric} className="flex items-center gap-3 text-sm">
                      <span className="w-32 text-gray-400">{metric.replace('_', ' ')}</span>
                      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                          style={{ width: `${(data.normalized || 0) * 100}%` }}
                        />
                      </div>
                      <span className="w-12 text-right font-mono text-gray-500">
                        {(data.contribution * 100).toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tier Guide */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Tier Guide</h2>
              <div className="grid grid-cols-4 gap-2 text-center text-sm">
                <div className="p-3 rounded bg-green-500/20">
                  <div className="text-green-400 font-bold text-lg">A</div>
                  <div className="text-gray-400 text-xs">&gt;70</div>
                </div>
                <div className="p-3 rounded bg-blue-500/20">
                  <div className="text-blue-400 font-bold text-lg">B</div>
                  <div className="text-gray-400 text-xs">55-70</div>
                </div>
                <div className="p-3 rounded bg-yellow-500/20">
                  <div className="text-yellow-400 font-bold text-lg">C</div>
                  <div className="text-gray-400 text-xs">40-55</div>
                </div>
                <div className="p-3 rounded bg-red-500/20">
                  <div className="text-red-400 font-bold text-lg">D</div>
                  <div className="text-gray-400 text-xs">&lt;40</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Position Sizing */}
          <div className="space-y-6">
            {/* Position Size Calculator */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Position Sizing</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Portfolio Value ($)</label>
                  <input
                    type="number"
                    value={portfolioValue}
                    onChange={(e) => setPortfolioValue(parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#1a1a24] border border-gray-700 rounded px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <button
                  onClick={getPositionSize}
                  className="w-full bg-blue-500 hover:bg-blue-600 rounded py-3 font-medium transition-colors"
                >
                  Calculate Position Size
                </button>
              </div>
            </div>

            {/* Position Result */}
            {positionResult && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Position Recommendation</h2>
                
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-blue-400">
                      {positionResult.position_size_pct?.toFixed(1)}%
                    </div>
                    <div className="text-sm text-gray-400">Position Size</div>
                  </div>
                  <div className="bg-gradient-to-br from-green-500/20 to-emerald-500/20 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-green-400">
                      ${positionResult.position_value?.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-400">Dollar Value</div>
                  </div>
                </div>

                <div className="space-y-3 text-sm">
                  <div className="flex justify-between p-2 bg-[#0a0a0f] rounded">
                    <span className="text-gray-400">Signal Tier</span>
                    <span className={getTierColor(positionResult.signal_tier) + ' px-2 py-0.5 rounded'}>
                      {positionResult.signal_tier}
                    </span>
                  </div>
                  <div className="flex justify-between p-2 bg-[#0a0a0f] rounded">
                    <span className="text-gray-400">Suggested Stop</span>
                    <span className="text-red-400">{positionResult.suggested_stop_pct?.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between p-2 bg-[#0a0a0f] rounded">
                    <span className="text-gray-400">Max Loss</span>
                    <span className="text-red-400">${positionResult.max_loss?.toFixed(0)}</span>
                  </div>
                </div>

                {/* Adjustment Factors */}
                {positionResult.adjustments && (
                  <div className="mt-4 p-3 bg-[#0a0a0f] rounded">
                    <div className="text-xs text-gray-500 mb-2">Adjustment Factors</div>
                    <div className="flex gap-2 flex-wrap">
                      {Object.entries(positionResult.adjustments).map(([key, val]) => (
                        <span key={key} className="text-xs px-2 py-1 bg-gray-800 rounded">
                          {key.replace('_', ' ')}: {val.toFixed(2)}x
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Kelly Criterion Info */}
            <div className="bg-gradient-to-br from-green-500/10 to-blue-500/10 border border-green-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">📐 Kelly Criterion</h2>
              <div className="space-y-2 text-sm text-gray-300">
                <p>
                  Position sizing uses a fractional Kelly criterion approach, adjusted for:
                </p>
                <ul className="list-disc list-inside space-y-1 text-gray-400">
                  <li>ML model confidence score</li>
                  <li>Regime fit alignment</li>
                  <li>Ensemble model agreement</li>
                </ul>
                <p className="text-gray-500 text-xs mt-2">
                  Using half-Kelly to reduce variance while maintaining edge.
                </p>
              </div>
            </div>

            {/* Next Steps */}
            <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Ready to Trade?</h2>
              <div className="space-y-2 text-sm">
                <a href="/portfolio" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-purple-400">→ Portfolio</span>
                  <span className="text-gray-400 ml-2">Apply sizing to real positions</span>
                </a>
                <a href="/trade" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-blue-400">→ Trade</span>
                  <span className="text-gray-400 ml-2">Execute with ML signals</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
