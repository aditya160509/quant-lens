'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLExplainabilityPage() {
  const [globalExplanation, setGlobalExplanation] = useState(null);
  const [signalExplanation, setSignalExplanation] = useState(null);
  const [testFeatures, setTestFeatures] = useState({});
  const [loading, setLoading] = useState(false);

  const fetchGlobalExplanation = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/explain/global`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        setGlobalExplanation(data);
      }
    } catch (error) {
      console.error('Failed to fetch explanation:', error);
    } finally {
      setLoading(false);
    }
  };

  const explainSignal = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/explain/signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features: testFeatures })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setSignalExplanation(data);
      }
    } catch (error) {
      console.error('Failed to explain signal:', error);
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
            <h1 className="text-2xl font-bold">🔍 Explainability - Feature Attribution</h1>
          </div>
          <p className="text-gray-400">Understand why models make predictions (SHAP-based)</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Global Importance */}
          <div className="space-y-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Global Feature Importance</h2>
                <button
                  onClick={fetchGlobalExplanation}
                  disabled={loading}
                  className="px-4 py-2 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 rounded text-sm transition-colors"
                >
                  {loading ? 'Loading...' : 'Compute'}
                </button>
              </div>

              {globalExplanation?.global_importance ? (
                <div className="space-y-3">
                  {Object.entries(globalExplanation.global_importance)
                    .sort((a, b) => b[1] - a[1])
                    .map(([feature, importance]) => {
                      const maxImp = Math.max(...Object.values(globalExplanation.global_importance));
                      const pct = (importance / maxImp) * 100;
                      return (
                        <div key={feature} className="flex items-center gap-3">
                          <span className="w-36 truncate text-sm text-gray-300">{feature}</span>
                          <div className="flex-1 h-4 bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="w-16 text-right text-sm font-mono text-gray-400">
                            {(importance * 100).toFixed(2)}
                          </span>
                        </div>
                      );
                    })}
                  <div className="mt-4 p-3 bg-[#0a0a0f] rounded text-sm text-gray-500">
                    Total features: {globalExplanation.total_features}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  Click &quot;Compute&quot; to calculate global feature importance
                </div>
              )}
            </div>

            {/* SHAP Info */}
            <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">📊 What is SHAP?</h2>
              <div className="space-y-2 text-sm text-gray-300">
                <p>
                  SHAP (SHapley Additive exPlanations) assigns each feature an importance value
                  for a particular prediction, based on game theory.
                </p>
                <ul className="list-disc list-inside space-y-1 text-gray-400">
                  <li>Positive SHAP = pushes prediction UP</li>
                  <li>Negative SHAP = pushes prediction DOWN</li>
                  <li>Magnitude = importance for that prediction</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Right Column - Signal Explanation */}
          <div className="space-y-6">
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Explain Signal Prediction</h2>
              
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
                onClick={explainSignal}
                className="w-full bg-blue-500 hover:bg-blue-600 rounded py-2 text-sm font-medium transition-colors"
              >
                Explain This Signal
              </button>
            </div>

            {/* Signal Explanation Result */}
            {signalExplanation?.prediction && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <div className="text-center mb-6">
                  <div className="text-3xl font-bold mb-1">
                    <span className={signalExplanation.prediction.probability > 0.5 ? 'text-green-400' : 'text-red-400'}>
                      {(signalExplanation.prediction.probability * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-sm text-gray-400">Predicted Probability</div>
                </div>

                <h3 className="text-sm font-medium text-gray-400 mb-3">Top Contributing Features</h3>
                <div className="space-y-2">
                  {Object.entries(signalExplanation.top_contributors || {}).map(([feature, data]) => (
                    <div key={feature} className="p-3 bg-[#0a0a0f] rounded">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-gray-300">{feature}</span>
                        <span className={`text-sm font-mono ${data.direction === 'positive' ? 'text-green-400' : 'text-red-400'}`}>
                          {data.direction === 'positive' ? '↑' : '↓'} {(data.importance * 100).toFixed(2)}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">
                        Value: {data.feature_value?.toFixed(4)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Waterfall Visualization Placeholder */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Waterfall Plot</h2>
              <div className="bg-[#0a0a0f] rounded-lg p-8 text-center">
                <div className="text-4xl mb-3">📊</div>
                <p className="text-gray-500 text-sm">
                  Waterfall visualization shows how each feature contributes to the final prediction,
                  starting from a base value.
                </p>
                <p className="text-gray-600 text-xs mt-2">
                  Full SHAP waterfall plots available via API
                </p>
              </div>
            </div>

            {/* Next Steps */}
            <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Next Steps</h2>
              <div className="space-y-2 text-sm">
                <a href="/labs/ml/monitoring" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-purple-400">→ Monitoring</span>
                  <span className="text-gray-400 ml-2">Track model performance over time</span>
                </a>
                <a href="/labs/ml/errors" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-red-400">→ Errors</span>
                  <span className="text-gray-400 ml-2">Analyze when models fail</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
