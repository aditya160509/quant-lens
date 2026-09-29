'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLMonitoringPage() {
  const [summary, setSummary] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [driftCheck, setDriftCheck] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSummary();
    fetchAlerts();
  }, []);

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/monitor/summary`);
      const data = await res.json();
      setSummary(data);
    } catch (error) {
      console.error('Failed to fetch summary:', error);
    }
  };

  const fetchAlerts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/monitor/alerts`);
      const data = await res.json();
      setAlerts(data.alerts || []);
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    }
  };

  const initializeMonitor = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/monitor/initialize`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        fetchSummary();
      }
    } catch (error) {
      console.error('Failed to initialize monitor:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'HEALTHY': return 'text-green-400 bg-green-500/20 border-green-500/30';
      case 'MODERATE': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      case 'DECLINING': return 'text-orange-400 bg-orange-500/20 border-orange-500/30';
      case 'POOR': return 'text-red-400 bg-red-500/20 border-red-500/30';
      default: return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
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
            <h1 className="text-2xl font-bold">📈 Monitoring - Drift & Decay</h1>
          </div>
          <p className="text-gray-400">Track model performance and detect when retraining is needed</p>
        </div>

        {/* Status Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className={`rounded-lg p-4 border ${summary?.status ? getStatusColor(summary.status) : 'bg-gray-500/20 border-gray-500/30'}`}>
            <div className="text-sm opacity-80">Status</div>
            <div className="text-2xl font-bold">{summary?.status || 'NOT INITIALIZED'}</div>
          </div>
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400">Recent Accuracy</div>
            <div className="text-2xl font-bold text-blue-400">
              {summary?.recent_accuracy ? `${(summary.recent_accuracy * 100).toFixed(1)}%` : '—'}
            </div>
          </div>
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400">Accuracy Trend</div>
            <div className={`text-2xl font-bold ${summary?.accuracy_trend > 0 ? 'text-green-400' : summary?.accuracy_trend < 0 ? 'text-red-400' : 'text-gray-400'}`}>
              {summary?.accuracy_trend ? `${summary.accuracy_trend > 0 ? '+' : ''}${(summary.accuracy_trend * 100).toFixed(1)}%` : '—'}
            </div>
          </div>
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400">Recent Alerts</div>
            <div className={`text-2xl font-bold ${summary?.recent_alerts > 0 ? 'text-red-400' : 'text-green-400'}`}>
              {summary?.recent_alerts ?? 0}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Initialize Monitor */}
            {(!summary || summary.status === 'NOT_INITIALIZED') && (
              <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-3">Initialize Monitor</h2>
                <p className="text-sm text-gray-400 mb-4">
                  Set up baseline distributions from training data to enable drift detection.
                </p>
                <button
                  onClick={initializeMonitor}
                  disabled={loading}
                  className="w-full bg-purple-500 hover:bg-purple-600 disabled:opacity-50 rounded py-3 font-medium transition-colors"
                >
                  {loading ? 'Initializing...' : 'Initialize from Dataset'}
                </button>
              </div>
            )}

            {/* Monitoring Stats */}
            {summary?.total_predictions && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Monitoring Statistics</h2>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-[#0a0a0f] rounded p-3">
                    <div className="text-gray-400">Total Predictions</div>
                    <div className="text-xl font-bold">{summary.total_predictions}</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded p-3">
                    <div className="text-gray-400">With Outcomes</div>
                    <div className="text-xl font-bold">{summary.predictions_with_outcomes}</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded p-3">
                    <div className="text-gray-400">Features Monitored</div>
                    <div className="text-xl font-bold">{summary.features_monitored}</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded p-3">
                    <div className="text-gray-400">Alert Count</div>
                    <div className="text-xl font-bold text-yellow-400">{summary.recent_alerts}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Accuracy Chart Placeholder */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Rolling Accuracy</h2>
              <div className="h-48 bg-[#0a0a0f] rounded-lg flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <div className="text-4xl mb-2">📉</div>
                  <p className="text-sm">Rolling accuracy chart</p>
                  <p className="text-xs text-gray-600">Updates as predictions are recorded</p>
                </div>
              </div>
            </div>

            {/* Drift Types */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Types of Drift</h2>
              <div className="space-y-3 text-sm">
                <div className="p-3 bg-[#0a0a0f] rounded">
                  <div className="font-medium text-yellow-400 mb-1">Feature Drift</div>
                  <div className="text-gray-400">Input feature distributions change (e.g., volatility regime shift)</div>
                </div>
                <div className="p-3 bg-[#0a0a0f] rounded">
                  <div className="font-medium text-orange-400 mb-1">Concept Drift</div>
                  <div className="text-gray-400">Relationship between features and outcome changes</div>
                </div>
                <div className="p-3 bg-[#0a0a0f] rounded">
                  <div className="font-medium text-red-400 mb-1">Performance Decay</div>
                  <div className="text-gray-400">Model accuracy degrades over time</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Alert History */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Recent Alerts</h2>
                <button
                  onClick={fetchAlerts}
                  className="text-sm text-purple-400 hover:text-purple-300"
                >
                  Refresh
                </button>
              </div>
              
              {alerts.length > 0 ? (
                <div className="space-y-3 max-h-80 overflow-y-auto">
                  {alerts.map((alert, i) => (
                    <div key={i} className={`p-3 rounded border ${
                      alert.severity === 'HIGH' ? 'bg-red-500/10 border-red-500/30' :
                      alert.severity === 'MEDIUM' ? 'bg-yellow-500/10 border-yellow-500/30' :
                      'bg-blue-500/10 border-blue-500/30'
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-sm font-medium ${
                          alert.severity === 'HIGH' ? 'text-red-400' :
                          alert.severity === 'MEDIUM' ? 'text-yellow-400' :
                          'text-blue-400'
                        }`}>
                          {alert.type}
                        </span>
                        <span className="text-xs text-gray-500">{alert.timestamp}</span>
                      </div>
                      <div className="text-sm text-gray-300">{alert.message}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  No alerts recorded yet
                </div>
              )}
            </div>

            {/* Drift Heatmap Placeholder */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Feature Drift Heatmap</h2>
              <div className="h-48 bg-[#0a0a0f] rounded-lg flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <div className="text-4xl mb-2">🔥</div>
                  <p className="text-sm">Drift intensity by feature over time</p>
                  <p className="text-xs text-gray-600">Colors indicate PSI values</p>
                </div>
              </div>
            </div>

            {/* Best Practices */}
            <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">💡 Monitoring Best Practices</h2>
              <div className="space-y-2 text-sm text-gray-300">
                <div className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  <span>Set up alerts for &gt;10% accuracy drop</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  <span>Retrain models when PSI &gt; 0.25</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  <span>Compare performance across market regimes</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
