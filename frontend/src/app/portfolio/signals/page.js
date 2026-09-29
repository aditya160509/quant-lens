'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function PortfolioSignalsPage() {
  const [signals, setSignals] = useState([]);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');
  const [modelPerformance, setModelPerformance] = useState(null);

  const fetchSignals = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/summary/ranked`);
      const data = await res.json();
      if (data.status === 'success') {
        setSignals(data.ranked_signals || []);
      }
    } catch (error) {
      console.error('Failed to fetch signals:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchModelPerformance = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/supervised/performance`);
      const data = await res.json();
      if (!data.error) {
        setModelPerformance(data);
      }
    } catch (error) {
      console.error('Failed to fetch performance:', error);
    }
  };

  useEffect(() => {
    fetchSignals();
    fetchModelPerformance();
  }, []);

  const filteredSignals = signals.filter(s => {
    if (filter === 'all') return true;
    if (filter === 'high') return s.composite_score >= 0.7;
    if (filter === 'medium') return s.composite_score >= 0.5 && s.composite_score < 0.7;
    if (filter === 'low') return s.composite_score < 0.5;
    return true;
  });

  const getTierColor = (tier) => {
    switch(tier) {
      case 'A': return 'text-green-400 bg-green-500/20';
      case 'B': return 'text-blue-400 bg-blue-500/20';
      case 'C': return 'text-yellow-400 bg-yellow-500/20';
      case 'D': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getConfidenceColor = (score) => {
    if (score >= 0.7) return 'text-green-400';
    if (score >= 0.5) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <a href="/portfolio" className="text-gray-500 hover:text-gray-300">← Portfolio</a>
              <span className="text-gray-600">/</span>
              <h1 className="text-2xl font-bold">📊 Signal Intelligence</h1>
            </div>
            <button
              onClick={fetchSignals}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 rounded text-sm transition-colors"
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
          <p className="text-gray-400">ML-powered signal ranking with success probability predictions</p>
        </div>

        {/* Filter + Stats Bar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex gap-2">
            {['all', 'high', 'medium', 'low'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded text-sm transition-colors ${
                  filter === f
                    ? 'bg-blue-500 text-white'
                    : 'bg-[#12121a] text-gray-400 hover:bg-[#1a1a24]'
                }`}
              >
                {f === 'all' ? 'All Signals' : f === 'high' ? 'High Quality' : f === 'medium' ? 'Medium' : 'Low'}
              </button>
            ))}
          </div>
          <div className="flex gap-4 text-sm">
            <div className="px-3 py-1 bg-[#12121a] rounded">
              <span className="text-gray-400">Total: </span>
              <span className="text-white font-medium">{signals.length}</span>
            </div>
            <div className="px-3 py-1 bg-[#12121a] rounded">
              <span className="text-gray-400">High Quality: </span>
              <span className="text-green-400 font-medium">{signals.filter(s => s.tier === 'A').length}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Signal Ranking Table */}
          <div className="lg:col-span-2 bg-[#12121a] border border-gray-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-gray-800">
              <h2 className="font-semibold">Signal Ranking</h2>
              <p className="text-xs text-gray-500 mt-1">Click a signal for detailed analysis</p>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#0a0a0f]">
                  <tr className="text-left text-gray-400">
                    <th className="p-3">Rank</th>
                    <th className="p-3">Signal</th>
                    <th className="p-3">Probability</th>
                    <th className="p-3">Tier</th>
                    <th className="p-3">Confidence</th>
                    <th className="p-3">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSignals.length > 0 ? (
                    filteredSignals.map((signal, idx) => (
                      <tr
                        key={signal.signal_id || idx}
                        onClick={() => setSelectedSignal(signal)}
                        className={`border-t border-gray-800/50 cursor-pointer transition-colors ${
                          selectedSignal?.signal_id === signal.signal_id
                            ? 'bg-blue-500/10'
                            : 'hover:bg-[#1a1a24]'
                        }`}
                      >
                        <td className="p-3 font-mono text-gray-400">#{signal.rank || idx + 1}</td>
                        <td className="p-3">
                          <div className="font-medium text-white">{signal.ticker || 'Unknown'}</div>
                          <div className="text-xs text-gray-500">{signal.signal_name || 'Signal'}</div>
                        </td>
                        <td className="p-3">
                          <span className={`text-lg font-bold ${getConfidenceColor(signal.composite_score)}`}>
                            {(signal.composite_score * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getTierColor(signal.tier)}`}>
                            {signal.tier}
                          </span>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  signal.composite_score >= 0.7 ? 'bg-green-500' :
                                  signal.composite_score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                                }`}
                                style={{ width: `${signal.composite_score * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-400">
                              {signal.composite_score >= 0.7 ? 'High' : signal.composite_score >= 0.5 ? 'Med' : 'Low'}
                            </span>
                          </div>
                        </td>
                        <td className="p-3 font-mono text-gray-300">
                          {(signal.composite_score * 100).toFixed(1)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-gray-500">
                        {loading ? 'Loading signals...' : 'No signals available. Build a dataset first.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Signal Detail Panel */}
          <div className="space-y-4">
            {selectedSignal ? (
              <>
                {/* Probability Gauge */}
                <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                  <div className="text-center mb-4">
                    <div className="relative inline-flex items-center justify-center">
                      <svg className="w-32 h-32 transform -rotate-90">
                        <circle
                          cx="64" cy="64" r="56"
                          stroke="#1a1a24" strokeWidth="12" fill="none"
                        />
                        <circle
                          cx="64" cy="64" r="56"
                          stroke={selectedSignal.composite_score >= 0.7 ? '#22c55e' : selectedSignal.composite_score >= 0.5 ? '#eab308' : '#ef4444'}
                          strokeWidth="12" fill="none"
                          strokeDasharray={`${selectedSignal.composite_score * 352} 352`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="absolute flex flex-col items-center">
                        <span className="text-3xl font-bold">{(selectedSignal.composite_score * 100).toFixed(0)}%</span>
                        <span className="text-xs text-gray-400">Success Prob</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-center">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getTierColor(selectedSignal.tier)}`}>
                      Tier {selectedSignal.tier}
                    </span>
                  </div>
                </div>

                {/* Score Breakdown */}
                <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                  <h3 className="text-sm font-medium text-gray-400 mb-3">Score Breakdown</h3>
                  <div className="space-y-2">
                    {selectedSignal.breakdown && Object.entries(selectedSignal.breakdown).map(([key, val]) => (
                      <div key={key} className="flex items-center justify-between text-sm">
                        <span className="text-gray-400 capitalize">{key.replace(/_/g, ' ')}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full"
                              style={{ width: `${(val.contribution || 0) * 100}%` }}
                            />
                          </div>
                          <span className="text-gray-300 font-mono w-12 text-right">
                            {((val.contribution || 0) * 100).toFixed(1)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                  <h3 className="text-sm font-medium text-gray-400 mb-3">Actions</h3>
                  <div className="space-y-2">
                    <button className="w-full py-2 bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 transition-colors text-sm">
                      Add to Portfolio
                    </button>
                    <button className="w-full py-2 bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30 transition-colors text-sm">
                      Set Alert
                    </button>
                    <a
                      href="/labs/ml/explainability"
                      className="block w-full py-2 bg-purple-500/20 text-purple-400 rounded hover:bg-purple-500/30 transition-colors text-sm text-center"
                    >
                      Explain Prediction
                    </a>
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-8 text-center">
                <div className="text-4xl mb-3">📊</div>
                <p className="text-gray-500">Select a signal to view details</p>
              </div>
            )}

            {/* Model Performance */}
            {modelPerformance && (
              <div className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg p-5">
                <h3 className="text-sm font-medium text-gray-300 mb-3">Model Performance</h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-gray-400">Accuracy</div>
                    <div className="text-xl font-bold text-green-400">
                      {((modelPerformance.accuracy || 0) * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Precision</div>
                    <div className="text-xl font-bold text-blue-400">
                      {((modelPerformance.precision || 0) * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-4 mt-6">
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Tier A Signals</div>
            <div className="text-2xl font-bold text-green-400">
              {signals.filter(s => s.tier === 'A').length}
            </div>
          </div>
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Avg Score</div>
            <div className="text-2xl font-bold text-blue-400">
              {signals.length > 0 
                ? (signals.reduce((a, s) => a + s.composite_score, 0) / signals.length * 100).toFixed(1)
                : '0'}
            </div>
          </div>
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">High Confidence</div>
            <div className="text-2xl font-bold text-purple-400">
              {signals.filter(s => s.composite_score >= 0.7).length}
            </div>
          </div>
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-sm">Actionable</div>
            <div className="text-2xl font-bold text-yellow-400">
              {signals.filter(s => s.tier === 'A' || s.tier === 'B').length}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
