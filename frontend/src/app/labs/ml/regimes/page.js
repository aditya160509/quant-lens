'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLRegimesPage() {
  const [discovery, setDiscovery] = useState(null);
  const [currentRegime, setCurrentRegime] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [nRegimes, setNRegimes] = useState(4);

  useEffect(() => {
    fetchCurrentRegime();
    fetchStatistics();
    fetchTimeline();
  }, []);

  const discoverRegimes = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/regimes/discover?n_regimes=${nRegimes}&method=kmeans`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        setDiscovery(data.discovery);
        fetchCurrentRegime();
        fetchStatistics();
        fetchTimeline();
      }
    } catch (error) {
      console.error('Failed to discover regimes:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCurrentRegime = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/regimes/current`);
      const data = await res.json();
      if (!data.error) {
        setCurrentRegime(data);
      }
    } catch (error) {
      console.error('Failed to fetch current regime:', error);
    }
  };

  const fetchStatistics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/regimes/statistics`);
      const data = await res.json();
      if (!data.error) {
        setStatistics(data);
      }
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  };

  const fetchTimeline = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/regimes/timeline`);
      const data = await res.json();
      if (!data.error) {
        setTimeline(data);
      }
    } catch (error) {
      console.error('Failed to fetch timeline:', error);
    }
  };

  const getRegimeColor = (type) => {
    switch (type) {
      case 'CRISIS': return 'bg-red-500';
      case 'HIGH_VOL': return 'bg-orange-500';
      case 'LOW_VOL': return 'bg-green-500';
      case 'RISK_ON': return 'bg-blue-500';
      case 'RISK_OFF': return 'bg-purple-500';
      default: return 'bg-gray-500';
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
            <h1 className="text-2xl font-bold">🌊 Regimes - Market State Discovery</h1>
          </div>
          <p className="text-gray-400">Discover natural market regimes using unsupervised learning</p>
        </div>

        {/* Current Regime Banner */}
        {currentRegime && !currentRegime.error && (
          <div className={`mb-8 rounded-lg p-6 ${getRegimeColor(currentRegime.regime_type)}/20 border ${getRegimeColor(currentRegime.regime_type)}/30`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm opacity-80">Current Market Regime</div>
                <div className="text-3xl font-bold">{currentRegime.regime_type}</div>
                <div className="text-sm opacity-70 mt-1">As of {currentRegime.as_of}</div>
              </div>
              <div className={`w-16 h-16 rounded-full ${getRegimeColor(currentRegime.regime_type)} flex items-center justify-center text-2xl font-bold`}>
                {currentRegime.current_regime}
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Discovery */}
          <div className="space-y-6">
            {/* Discover Controls */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Discover Regimes</h2>
              <div className="mb-4">
                <label className="block text-sm text-gray-400 mb-2">Number of Regimes: {nRegimes}</label>
                <input
                  type="range"
                  min="2"
                  max="8"
                  value={nRegimes}
                  onChange={(e) => setNRegimes(parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>2</span>
                  <span>8</span>
                </div>
              </div>
              <button
                onClick={discoverRegimes}
                disabled={loading}
                className="w-full bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 rounded py-3 font-medium transition-all"
              >
                {loading ? 'Discovering Regimes...' : 'Run Regime Discovery'}
              </button>
            </div>

            {/* Discovery Results */}
            {discovery && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Discovered Regimes</h2>
                <div className="space-y-3">
                  {Object.entries(discovery.regimes || {}).map(([id, regime]) => (
                    <div key={id} className="p-4 bg-[#0a0a0f] rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`w-3 h-3 rounded-full ${getRegimeColor(regime.type)}`} />
                          <span className="font-medium">{regime.type}</span>
                        </div>
                        <span className="text-sm text-gray-400">
                          {regime.percentage?.toFixed(1)}% of data
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">
                        {regime.count} observations
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded text-sm">
                  <div className="text-gray-400">Quality Score (Silhouette): 
                    <span className="ml-2 text-blue-400 font-mono">
                      {discovery.quality_metrics?.silhouette_score?.toFixed(3)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Transition Matrix */}
            {discovery?.transition_matrix && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Transition Probabilities</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-400">
                        <th className="text-left py-2">From \ To</th>
                        {discovery.transition_matrix.map((_, i) => (
                          <th key={i} className="text-center py-2">R{i}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {discovery.transition_matrix.map((row, i) => (
                        <tr key={i} className="border-t border-gray-800/50">
                          <td className="py-2 font-medium">Regime {i}</td>
                          {row.map((prob, j) => (
                            <td key={j} className="text-center py-2">
                              <span className={`inline-block w-12 h-6 rounded text-xs leading-6 ${
                                prob > 0.5 ? 'bg-green-500/30 text-green-400' :
                                prob > 0.2 ? 'bg-yellow-500/30 text-yellow-400' :
                                'bg-gray-500/30 text-gray-400'
                              }`}>
                                {(prob * 100).toFixed(0)}%
                              </span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Statistics & Timeline */}
          <div className="space-y-6">
            {/* Regime Statistics */}
            {statistics && !statistics.error && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Regime Statistics</h2>
                <div className="space-y-4">
                  {Object.entries(statistics).map(([key, stats]) => (
                    <div key={key} className="p-4 bg-[#0a0a0f] rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`w-3 h-3 rounded-full ${getRegimeColor(stats.type)}`} />
                          <span className="font-medium">{stats.type}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <div className="text-gray-400">Count</div>
                          <div className="font-mono">{stats.count}</div>
                        </div>
                        <div>
                          <div className="text-gray-400">Avg Duration</div>
                          <div className="font-mono">{stats.avg_duration?.toFixed(1)} days</div>
                        </div>
                        <div>
                          <div className="text-gray-400">Persistence</div>
                          <div className="font-mono">{(stats.persistence * 100)?.toFixed(0)}%</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Timeline Visualization */}
            {timeline?.labels && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Regime Timeline</h2>
                <div className="h-12 flex rounded-lg overflow-hidden">
                  {timeline.labels.map((label, i) => (
                    <div
                      key={i}
                      className={`h-full ${getRegimeColor(discovery?.regimes?.[label]?.type || 'NEUTRAL')}`}
                      style={{ width: `${100 / timeline.labels.length}%` }}
                      title={`Regime ${label}`}
                    />
                  ))}
                </div>
                <div className="flex justify-between text-xs text-gray-500 mt-2">
                  <span>{timeline.dates?.[0]}</span>
                  <span>{timeline.dates?.[timeline.dates.length - 1]}</span>
                </div>
              </div>
            )}

            {/* Regime Insights */}
            <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">💡 Regime Insights</h2>
              <div className="space-y-2 text-sm text-gray-300">
                <div className="flex items-start gap-2">
                  <span className="text-purple-400">•</span>
                  <span>Use regime context to filter trading signals</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-purple-400">•</span>
                  <span>High persistence = stable regime, trade confidently</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-purple-400">•</span>
                  <span>Low persistence = volatile transitions, reduce size</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
