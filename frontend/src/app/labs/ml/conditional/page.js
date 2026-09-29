'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLConditionalPage() {
  const [analysis, setAnalysis] = useState(null);
  const [heatmapData, setHeatmapData] = useState(null);
  const [fingerprints, setFingerprints] = useState(null);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState('heatmap');

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/conditional/analyze`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        setAnalysis(data.analysis);
        fetchHeatmap();
        fetchFingerprints();
      }
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchHeatmap = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/conditional/heatmap`);
      const data = await res.json();
      if (!data.error) {
        setHeatmapData(data);
      }
    } catch (error) {
      console.error('Heatmap fetch failed:', error);
    }
  };

  const fetchFingerprints = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/conditional/fingerprints`);
      const data = await res.json();
      if (!data.error) {
        setFingerprints(data);
      }
    } catch (error) {
      console.error('Fingerprints fetch failed:', error);
    }
  };

  const getHeatmapColor = (value) => {
    if (value === null || value === undefined) return 'bg-gray-800';
    if (value >= 0.03) return 'bg-green-500';
    if (value >= 0.01) return 'bg-green-400/70';
    if (value >= 0) return 'bg-green-300/50';
    if (value >= -0.01) return 'bg-red-300/50';
    if (value >= -0.03) return 'bg-red-400/70';
    return 'bg-red-500';
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <a href="/labs/ml" className="text-gray-500 hover:text-gray-300">← ML</a>
            <span className="text-gray-600">/</span>
            <h1 className="text-2xl font-bold">📈 Conditional Performance Analyzer</h1>
          </div>
          <p className="text-gray-400">Understand when and why signals work by market conditions</p>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex gap-2">
            {['heatmap', 'fingerprints', 'best-worst'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-4 py-2 rounded text-sm transition-colors ${
                  viewMode === mode
                    ? 'bg-blue-500 text-white'
                    : 'bg-[#12121a] text-gray-400 hover:bg-[#1a1a24]'
                }`}
              >
                {mode === 'heatmap' ? 'Performance Heatmap' : mode === 'fingerprints' ? 'Signal Fingerprints' : 'Best/Worst'}
              </button>
            ))}
          </div>
          <button
            onClick={runAnalysis}
            disabled={loading}
            className="px-6 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 rounded font-medium transition-colors"
          >
            {loading ? 'Analyzing...' : 'Run Analysis'}
          </button>
        </div>

        {viewMode === 'heatmap' && (
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Regime vs Return Heatmap</h2>
            
            {heatmapData?.regimes ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="p-3 text-left text-gray-400">Regime / Volatility</th>
                      {heatmapData.volatilities?.map(vol => (
                        <th key={vol} className="p-3 text-center text-gray-400">{vol}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {heatmapData.regimes.map((regime, ri) => (
                      <tr key={regime}>
                        <td className="p-3 font-medium">{regime}</td>
                        {heatmapData.data[ri]?.map((cell, ci) => (
                          <td key={ci} className="p-2">
                            {cell ? (
                              <div className={`p-3 rounded text-center ${getHeatmapColor(cell.value)}`}>
                                <div className="text-lg font-bold">
                                  {(cell.value * 100).toFixed(1)}%
                                </div>
                                <div className="text-xs opacity-80">
                                  WR: {(cell.win_rate * 100).toFixed(0)}% ({cell.sample_size})
                                </div>
                              </div>
                            ) : (
                              <div className="p-3 bg-gray-800 rounded text-center text-gray-500">
                                N/A
                              </div>
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                Run analysis to generate heatmap
              </div>
            )}
          </div>
        )}

        {viewMode === 'fingerprints' && (
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Signal Performance Fingerprints</h2>
            
            {fingerprints?.fingerprints && Object.keys(fingerprints.fingerprints).length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(fingerprints.fingerprints).map(([signal, data]) => (
                  <div key={signal} className="p-4 bg-[#0a0a0f] rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-medium">{signal}</h3>
                      <span className={`px-2 py-1 rounded text-xs ${
                        data.overall_win_rate >= 0.6 ? 'bg-green-500/20 text-green-400' :
                        data.overall_win_rate >= 0.5 ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-red-500/20 text-red-400'
                      }`}>
                        {(data.overall_win_rate * 100).toFixed(0)}% Win Rate
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-gray-400">Total Signals:</span>
                        <span className="ml-2 text-white">{data.total_signals}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Avg Return:</span>
                        <span className={`ml-2 ${data.overall_avg_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {(data.overall_avg_return * 100).toFixed(2)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-400">Best Regime:</span>
                        <span className="ml-2 text-green-400">{data.best_regime || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Worst Regime:</span>
                        <span className="ml-2 text-red-400">{data.worst_regime || 'N/A'}</span>
                      </div>
                    </div>
                    {data.by_regime && (
                      <div className="mt-3 pt-3 border-t border-gray-800">
                        <div className="text-xs text-gray-400 mb-2">Performance by Regime</div>
                        <div className="flex gap-2 flex-wrap">
                          {Object.entries(data.by_regime).map(([regime, perf]) => (
                            <span
                              key={regime}
                              className={`px-2 py-1 rounded text-xs ${
                                perf.win_rate >= 0.6 ? 'bg-green-500/20 text-green-400' :
                                perf.win_rate >= 0.5 ? 'bg-yellow-500/20 text-yellow-400' :
                                'bg-red-500/20 text-red-400'
                              }`}
                            >
                              {regime}: {(perf.win_rate * 100).toFixed(0)}%
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                Run analysis to see signal fingerprints
              </div>
            )}
          </div>
        )}

        {viewMode === 'best-worst' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-green-400 mb-4">✅ Best Conditions</h2>
              
              {fingerprints?.best_worst?.best_by_win_rate?.length > 0 ? (
                <div className="space-y-3">
                  {fingerprints.best_worst.best_by_win_rate.map((cond, idx) => (
                    <div key={idx} className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-green-400">{cond.condition}</span>
                        <span className="text-2xl font-bold text-green-400">
                          {(cond.win_rate * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex gap-4 text-xs text-gray-400">
                        <span>Avg Return: {(cond.avg_return * 100).toFixed(2)}%</span>
                        <span>Sample: {cond.sample_size}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  Run analysis to identify best conditions
                </div>
              )}
            </div>

            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-red-400 mb-4">⚠️ Worst Conditions</h2>
              
              {fingerprints?.best_worst?.worst_by_win_rate?.length > 0 ? (
                <div className="space-y-3">
                  {fingerprints.best_worst.worst_by_win_rate.map((cond, idx) => (
                    <div key={idx} className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-red-400">{cond.condition}</span>
                        <span className="text-2xl font-bold text-red-400">
                          {(cond.win_rate * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex gap-4 text-xs text-gray-400">
                        <span>Avg Return: {(cond.avg_return * 100).toFixed(2)}%</span>
                        <span>Sample: {cond.sample_size}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  Run analysis to identify worst conditions
                </div>
              )}
            </div>
          </div>
        )}

        {/* Overall Stats */}
        {analysis?.overall_stats && (
          <div className="mt-6 grid grid-cols-5 gap-4">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4 text-center">
              <div className="text-gray-400 text-sm">Total Signals</div>
              <div className="text-2xl font-bold text-white">{analysis.overall_stats.total_signals}</div>
            </div>
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4 text-center">
              <div className="text-gray-400 text-sm">Win Rate</div>
              <div className="text-2xl font-bold text-green-400">
                {(analysis.overall_stats.win_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4 text-center">
              <div className="text-gray-400 text-sm">Avg Return</div>
              <div className={`text-2xl font-bold ${analysis.overall_stats.avg_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(analysis.overall_stats.avg_return * 100).toFixed(2)}%
              </div>
            </div>
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4 text-center">
              <div className="text-gray-400 text-sm">Sharpe</div>
              <div className="text-2xl font-bold text-blue-400">
                {analysis.overall_stats.sharpe_approx?.toFixed(2)}
              </div>
            </div>
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4 text-center">
              <div className="text-gray-400 text-sm">Max Loss</div>
              <div className="text-2xl font-bold text-red-400">
                {(analysis.overall_stats.max_loss * 100).toFixed(2)}%
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
