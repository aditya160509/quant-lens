'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLEnsemblePage() {
  const [consensus, setConsensus] = useState(null);
  const [agreement, setAgreement] = useState(null);
  const [testFeatures, setTestFeatures] = useState({});
  const [loading, setLoading] = useState(false);

  const getConsensus = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/ensemble/consensus`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features: testFeatures })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setConsensus(data);
      }
    } catch (error) {
      console.error('Failed to get consensus:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgreement = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/ensemble/agreement`);
      const data = await res.json();
      setAgreement(data);
    } catch (error) {
      console.error('Failed to fetch agreement:', error);
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
            <h1 className="text-2xl font-bold">🤝 Ensemble - Model Consensus</h1>
          </div>
          <p className="text-gray-400">Combine multiple models for robust predictions</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Consensus Test */}
          <div className="space-y-6">
            {/* Input Features */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Test Ensemble</h2>
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
                onClick={getConsensus}
                disabled={loading}
                className="w-full bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 rounded py-3 font-medium transition-all"
              >
                {loading ? 'Getting Consensus...' : 'Get Ensemble Consensus'}
              </button>
            </div>

            {/* Consensus Result */}
            {consensus?.consensus && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Consensus Result</h2>
                
                <div className="text-center mb-6">
                  <div className="text-5xl font-bold mb-2">
                    <span className={consensus.consensus.probability > 0.5 ? 'text-green-400' : 'text-red-400'}>
                      {(consensus.consensus.probability * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className={`inline-block px-4 py-2 rounded-lg text-sm font-medium ${
                    consensus.consensus.confidence_tier === 'HIGH' ? 'bg-green-500/20 text-green-400' :
                    consensus.consensus.confidence_tier === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-red-500/20 text-red-400'
                  }`}>
                    {consensus.consensus.confidence_tier} Confidence
                  </div>
                </div>

                {/* Model Disagreement */}
                <div className="mb-4">
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-gray-400">Model Disagreement</span>
                    <span className={consensus.consensus.disagreement > 0.2 ? 'text-yellow-400' : 'text-green-400'}>
                      {(consensus.consensus.disagreement * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${consensus.consensus.disagreement > 0.2 ? 'bg-yellow-500' : 'bg-green-500'}`}
                      style={{ width: `${consensus.consensus.disagreement * 100}%` }}
                    />
                  </div>
                </div>

                {/* Individual Model Predictions */}
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-3">Individual Models</h3>
                  <div className="space-y-2">
                    {Object.entries(consensus.model_predictions || {}).map(([name, prob]) => (
                      <div key={name} className="flex items-center justify-between p-3 bg-[#0a0a0f] rounded">
                        <span className="capitalize text-gray-300">{name.replace('_', ' ')}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-2 bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${prob > 0.5 ? 'bg-green-500' : 'bg-red-500'}`}
                              style={{ width: `${prob * 100}%` }}
                            />
                          </div>
                          <span className={`font-mono text-sm ${prob > 0.5 ? 'text-green-400' : 'text-red-400'}`}>
                            {(prob * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Agreement Matrix */}
          <div className="space-y-6">
            {/* Agreement Analysis */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Model Agreement Analysis</h2>
                <button
                  onClick={fetchAgreement}
                  className="px-3 py-1 bg-purple-500 hover:bg-purple-600 rounded text-sm transition-colors"
                >
                  Analyze
                </button>
              </div>

              {agreement?.agreement_matrix ? (
                <div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-gray-400">
                          <th className="text-left py-2">Model</th>
                          {agreement.models?.map(m => (
                            <th key={m} className="text-center py-2 px-2">{m.slice(0, 4)}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {agreement.models?.map((model, i) => (
                          <tr key={model} className="border-t border-gray-800/50">
                            <td className="py-2 text-gray-300 capitalize">{model}</td>
                            {agreement.agreement_matrix[i]?.map((val, j) => (
                              <td key={j} className="text-center py-2 px-2">
                                <span className={`inline-block w-10 h-6 rounded text-xs leading-6 ${
                                  val > 0.8 ? 'bg-green-500/30 text-green-400' :
                                  val > 0.6 ? 'bg-yellow-500/30 text-yellow-400' :
                                  'bg-red-500/30 text-red-400'
                                }`}>
                                  {(val * 100).toFixed(0)}%
                                </span>
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-4 text-xs text-gray-500">
                    Higher agreement = more robust signal
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  {'Click "Analyze" to compute model agreement on dataset'}
                </div>
              )}
            </div>

            {/* Ensemble Benefits */}
            <div className="bg-gradient-to-br from-green-500/10 to-blue-500/10 border border-green-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">🎯 Why Ensemble?</h2>
              <div className="space-y-3 text-sm">
                <div className="flex items-start gap-2">
                  <span className="text-green-400">✓</span>
                  <span className="text-gray-300">Reduces variance from individual model noise</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-400">✓</span>
                  <span className="text-gray-300">High disagreement = low confidence signals</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-400">✓</span>
                  <span className="text-gray-300">Robustness to regime changes</span>
                </div>
              </div>
            </div>

            {/* Next Steps */}
            <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Next Steps</h2>
              <div className="space-y-2 text-sm">
                <a href="/labs/ml/explainability" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-purple-400">→ Explainability</span>
                  <span className="text-gray-400 ml-2">Understand why models predict</span>
                </a>
                <a href="/labs/ml/summary" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-blue-400">→ Summary</span>
                  <span className="text-gray-400 ml-2">Score signals & size positions</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
