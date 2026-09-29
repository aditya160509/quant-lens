'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLFeaturesPage() {
  const [validation, setValidation] = useState(null);
  const [correlation, setCorrelation] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchValidation();
  }, []);

  const fetchValidation = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/features/validate`);
      const data = await res.json();
      if (data.status === 'success') {
        setValidation(data.validation);
      }
    } catch (error) {
      console.error('Failed to fetch validation:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCorrelation = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/features/correlation`);
      const data = await res.json();
      setCorrelation(data);
    } catch (error) {
      console.error('Failed to fetch correlation:', error);
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
            <h1 className="text-2xl font-bold">🔧 Features - Engineering & Validation</h1>
          </div>
          <p className="text-gray-400">Validate, transform, and analyze feature quality</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Validation */}
          <div className="space-y-6">
            {/* Validation Summary */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Feature Validation</h2>
                <button
                  onClick={fetchValidation}
                  className="text-sm text-purple-400 hover:text-purple-300"
                >
                  Refresh
                </button>
              </div>

              {loading ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : validation?.valid !== undefined ? (
                <div className="space-y-4">
                  <div className={`p-4 rounded-lg ${validation.valid ? 'bg-green-500/10 border border-green-500/30' : 'bg-yellow-500/10 border border-yellow-500/30'}`}>
                    <div className="flex items-center gap-2 text-lg font-semibold">
                      {validation.valid ? '✅ Features Valid' : '⚠️ Issues Detected'}
                    </div>
                    <div className="text-sm text-gray-400 mt-1">
                      {validation.n_features} features • Quality score: {(validation.quality_score * 100).toFixed(0)}%
                    </div>
                  </div>

                  {/* Issues */}
                  {validation.issues?.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-400 mb-2">Issues Found</h3>
                      <div className="space-y-2">
                        {validation.issues.map((issue, i) => (
                          <div key={i} className="p-3 bg-red-500/10 border border-red-500/20 rounded text-sm">
                            <span className="text-red-400">{issue}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Warnings */}
                  {validation.warnings?.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-400 mb-2">Warnings</h3>
                      <div className="space-y-2">
                        {validation.warnings.slice(0, 5).map((warning, i) => (
                          <div key={i} className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded text-sm">
                            <span className="text-yellow-400">{warning}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  No dataset available. Build dataset first in Data module.
                </div>
              )}
            </div>

            {/* Feature Stats */}
            {validation?.feature_stats && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Feature Statistics</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-400 border-b border-gray-800">
                        <th className="text-left py-2">Feature</th>
                        <th className="text-right py-2">Mean</th>
                        <th className="text-right py-2">Std</th>
                        <th className="text-right py-2">Missing %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(validation.feature_stats).slice(0, 10).map(([name, stats]) => (
                        <tr key={name} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                          <td className="py-2 text-gray-300">{name}</td>
                          <td className="py-2 text-right font-mono text-blue-400">{stats.mean?.toFixed(3)}</td>
                          <td className="py-2 text-right font-mono text-gray-500">{stats.std?.toFixed(3)}</td>
                          <td className="py-2 text-right">
                            <span className={stats.missing_pct > 10 ? 'text-red-400' : 'text-gray-500'}>
                              {stats.missing_pct?.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Correlation */}
          <div className="space-y-6">
            {/* Correlation Matrix */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Correlation Analysis</h2>
                <button
                  onClick={fetchCorrelation}
                  className="px-3 py-1 bg-purple-500 hover:bg-purple-600 rounded text-sm transition-colors"
                >
                  Load Correlation
                </button>
              </div>

              {correlation?.features ? (
                <div>
                  <div className="mb-4 p-3 bg-[#0a0a0f] rounded-lg">
                    <div className="text-sm text-gray-400">
                      {correlation.features.length} features analyzed
                    </div>
                    {correlation.high_correlation_pairs?.length > 0 && (
                      <div className="mt-2 text-sm text-yellow-400">
                        ⚠️ {correlation.high_correlation_pairs.length} highly correlated pairs detected
                      </div>
                    )}
                  </div>

                  {/* High Correlation Pairs */}
                  {correlation.high_correlation_pairs?.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-400 mb-2">High Correlation Pairs (|r| &gt; 0.8)</h3>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {correlation.high_correlation_pairs.slice(0, 10).map((pair, i) => (
                          <div key={i} className="flex items-center justify-between p-2 bg-[#0a0a0f] rounded text-sm">
                            <span className="text-gray-300">{pair.feature1} ↔ {pair.feature2}</span>
                            <span className={`font-mono ${pair.correlation > 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {pair.correlation?.toFixed(3)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  {'Click "Load Correlation" to analyze feature correlations'}
                </div>
              )}
            </div>

            {/* Feature Engineering Tips */}
            <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">💡 Feature Engineering Tips</h2>
              <div className="space-y-3 text-sm">
                <div className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  <span className="text-gray-300">Remove features with &gt;50% missing data</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  <span className="text-gray-300">Drop one feature from highly correlated pairs</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  <span className="text-gray-300">Normalize features to prevent scale dominance</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  <span className="text-gray-300">Add lag features for temporal patterns</span>
                </div>
              </div>
            </div>

            {/* Next Steps */}
            <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Next Steps</h2>
              <div className="space-y-2 text-sm">
                <a href="/labs/ml/supervised" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-purple-400">→ Supervised</span>
                  <span className="text-gray-400 ml-2">Train prediction models</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
