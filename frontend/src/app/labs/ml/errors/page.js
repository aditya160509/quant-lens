'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLErrorsPage() {
  const [errorAnalysis, setErrorAnalysis] = useState(null);
  const [riskFlags, setRiskFlags] = useState([]);
  const [loading, setLoading] = useState(false);
  const [testFeatures, setTestFeatures] = useState({});

  const analyzeErrors = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/errors/analyze`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        setErrorAnalysis(data);
      }
    } catch (error) {
      console.error('Failed to analyze errors:', error);
    } finally {
      setLoading(false);
    }
  };

  const checkRiskFlags = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/errors/risk-flags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features: testFeatures })
      });
      const data = await res.json();
      setRiskFlags(data.active_flags || []);
    } catch (error) {
      console.error('Failed to check risk flags:', error);
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
            <h1 className="text-2xl font-bold">⚠️ Errors - Failure Analysis</h1>
          </div>
          <p className="text-gray-400">Understand when and why models fail to improve future predictions</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Error Analysis */}
          <div className="space-y-6">
            {/* Analyze Button */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Error Analysis</h2>
              <button
                onClick={analyzeErrors}
                disabled={loading}
                className="w-full bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600 disabled:opacity-50 rounded py-3 font-medium transition-all"
              >
                {loading ? 'Analyzing Errors...' : 'Analyze Model Errors'}
              </button>
              <p className="text-xs text-gray-500 mt-2">
                Clusters misclassifications to find patterns in failures
              </p>
            </div>

            {/* Error Summary */}
            {errorAnalysis?.error_analysis && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Error Summary</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-[#0a0a0f] rounded p-4 text-center">
                    <div className="text-3xl font-bold text-blue-400">
                      {errorAnalysis.error_analysis.total_predictions}
                    </div>
                    <div className="text-sm text-gray-400">Total Predictions</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded p-4 text-center">
                    <div className="text-3xl font-bold text-red-400">
                      {errorAnalysis.error_analysis.total_errors}
                    </div>
                    <div className="text-sm text-gray-400">Total Errors</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded p-4 text-center">
                    <div className="text-3xl font-bold text-yellow-400">
                      {errorAnalysis.error_analysis.false_positives}
                    </div>
                    <div className="text-sm text-gray-400">False Positives</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded p-4 text-center">
                    <div className="text-3xl font-bold text-orange-400">
                      {errorAnalysis.error_analysis.false_negatives}
                    </div>
                    <div className="text-sm text-gray-400">False Negatives</div>
                  </div>
                </div>
                <div className="mt-4">
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-gray-400">Error Rate</span>
                    <span className="text-red-400 font-mono">
                      {(errorAnalysis.error_analysis.error_rate * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-red-500 to-orange-500"
                      style={{ width: `${errorAnalysis.error_analysis.error_rate * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Error Clusters */}
            {errorAnalysis?.clusters?.clusters && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Error Clusters</h2>
                <div className="space-y-3">
                  {Object.entries(errorAnalysis.clusters.clusters).map(([id, cluster]) => (
                    <div key={id} className="p-4 bg-[#0a0a0f] rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">Cluster {id}</span>
                        <span className="text-sm text-gray-400">
                          {cluster.size} errors ({cluster.percentage?.toFixed(1)}%)
                        </span>
                      </div>
                      <p className="text-sm text-gray-400 mb-2">{cluster.description}</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.keys(cluster.distinguishing_features || {}).slice(0, 3).map(feat => (
                          <span key={feat} className="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded">
                            {feat}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Risk Flags */}
          <div className="space-y-6">
            {/* High Risk Conditions */}
            {errorAnalysis?.high_risk_conditions && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">🚨 High-Risk Conditions</h2>
                <div className="space-y-3">
                  {errorAnalysis.high_risk_conditions.map((condition, i) => (
                    <div key={i} className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-red-400">{condition.feature}</span>
                        <span className="text-sm text-gray-400">
                          {(condition.error_concentration * 100).toFixed(1)}% of errors
                        </span>
                      </div>
                      <p className="text-sm text-gray-300">{condition.description}</p>
                      <div className="text-xs text-gray-500 mt-2">
                        Condition: {condition.condition} • Threshold: {condition.threshold?.toFixed(3)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Risk Flag Checker */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Check Risk Flags</h2>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {['return_5d', 'volatility_20d', 'momentum_10d', 'rsi_14d'].map(feat => (
                  <div key={feat}>
                    <label className="block text-xs text-gray-400 mb-1">{feat}</label>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      onChange={(e) => setTestFeatures({ ...testFeatures, [feat]: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-[#1a1a24] border border-gray-700 rounded px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={checkRiskFlags}
                className="w-full bg-yellow-500 hover:bg-yellow-600 text-black rounded py-2 text-sm font-medium transition-colors"
              >
                Check for Risk Flags
              </button>

              {riskFlags.length > 0 && (
                <div className="mt-4 space-y-2">
                  {riskFlags.map((flag, i) => (
                    <div key={i} className={`p-3 rounded ${
                      flag.severity === 'HIGH' ? 'bg-red-500/20 border border-red-500/30' : 'bg-yellow-500/20 border border-yellow-500/30'
                    }`}>
                      <div className="font-medium text-sm">{flag.feature}: {flag.condition}</div>
                      <div className="text-xs text-gray-400 mt-1">{flag.description}</div>
                    </div>
                  ))}
                </div>
              )}

              {riskFlags.length === 0 && testFeatures && Object.keys(testFeatures).length > 0 && (
                <div className="mt-4 p-3 bg-green-500/20 border border-green-500/30 rounded text-sm text-green-400">
                  ✓ No risk flags triggered for current conditions
                </div>
              )}
            </div>

            {/* Error Pattern Insights */}
            <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 border border-orange-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">💡 Error Pattern Insights</h2>
              <div className="space-y-2 text-sm text-gray-300">
                <div className="flex items-start gap-2">
                  <span className="text-orange-400">•</span>
                  <span>High volatility periods often lead to false positives</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-orange-400">•</span>
                  <span>Mean reversion signals fail in trending regimes</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-orange-400">•</span>
                  <span>Avoid trading when multiple risk flags trigger</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
