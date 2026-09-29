'use client';

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLSupervisedPage() {
  const [training, setTraining] = useState(false);
  const [trainingResult, setTrainingResult] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [importance, setImportance] = useState(null);
  const [selectedModels, setSelectedModels] = useState(['logistic', 'random_forest', 'xgboost']);
  const [testFeatures, setTestFeatures] = useState({});

  const availableModels = [
    { id: 'logistic', name: 'Logistic Regression', icon: '📉' },
    { id: 'random_forest', name: 'Random Forest', icon: '🌲' },
    { id: 'gradient_boosting', name: 'Gradient Boosting', icon: '⚡' },
    { id: 'xgboost', name: 'XGBoost', icon: '🚀' },
    { id: 'lightgbm', name: 'LightGBM', icon: '💡' },
  ];

  useEffect(() => {
    fetchImportance();
  }, []);

  const toggleModel = (modelId) => {
    if (selectedModels.includes(modelId)) {
      setSelectedModels(selectedModels.filter(m => m !== modelId));
    } else {
      setSelectedModels([...selectedModels, modelId]);
    }
  };

  const trainModels = async () => {
    setTraining(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/supervised/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selectedModels)
      });
      const data = await res.json();
      setTrainingResult(data);
      fetchImportance();
    } catch (error) {
      console.error('Training failed:', error);
      setTrainingResult({ status: 'error', message: error.message });
    } finally {
      setTraining(false);
    }
  };

  const fetchImportance = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/supervised/importance`);
      const data = await res.json();
      if (data.status === 'success') {
        setImportance(data.importance);
      }
    } catch (error) {
      console.error('Failed to fetch importance:', error);
    }
  };

  const testPrediction = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/supervised/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features: testFeatures })
      });
      const data = await res.json();
      setPrediction(data);
    } catch (error) {
      console.error('Prediction failed:', error);
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
            <h1 className="text-2xl font-bold">🎯 Supervised - Signal Prediction</h1>
          </div>
          <p className="text-gray-400">Train ML models to predict signal success probability</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Training */}
          <div className="space-y-6">
            {/* Model Selection */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Select Models</h2>
              <div className="space-y-2">
                {availableModels.map(model => (
                  <button
                    key={model.id}
                    onClick={() => toggleModel(model.id)}
                    className={`w-full flex items-center justify-between p-3 rounded transition-all ${
                      selectedModels.includes(model.id)
                        ? 'bg-purple-500/20 border border-purple-500/50'
                        : 'bg-[#1a1a24] border border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{model.icon}</span>
                      <span className="font-medium">{model.name}</span>
                    </div>
                    <span className={`text-sm ${selectedModels.includes(model.id) ? 'text-purple-400' : 'text-gray-500'}`}>
                      {selectedModels.includes(model.id) ? '✓ Selected' : 'Click to add'}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Train Button */}
            <button
              onClick={trainModels}
              disabled={training || selectedModels.length === 0}
              className="w-full bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 rounded-lg py-4 font-semibold text-lg transition-all"
            >
              {training ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin">⚙️</span>
                  Training {selectedModels.length} Models...
                </span>
              ) : (
                `Train ${selectedModels.length} Models`
              )}
            </button>

            {/* Training Results */}
            {trainingResult?.training_results?.models && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Training Results</h2>
                <div className="space-y-3">
                  {Object.entries(trainingResult.training_results.models).map(([name, stats]) => (
                    <div key={name} className="bg-[#0a0a0f] rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium capitalize">{name.replace('_', ' ')}</span>
                        <span className={`text-sm ${stats.trained ? 'text-green-400' : 'text-red-400'}`}>
                          {stats.trained ? '✓ Trained' : '✗ Failed'}
                        </span>
                      </div>
                      {stats.trained && (
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>
                            <span className="text-gray-400">CV Mean:</span>
                            <span className="ml-2 font-mono text-blue-400">
                              {(stats.cv_mean * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">CV Std:</span>
                            <span className="ml-2 font-mono text-gray-500">
                              ±{(stats.cv_std * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <div className="mt-4 p-3 bg-gradient-to-r from-green-500/10 to-blue-500/10 rounded-lg border border-green-500/20">
                  <div className="text-sm text-gray-400">
                    Samples: <span className="text-white font-medium">{trainingResult.training_results.n_samples}</span>
                    {' • '}
                    Features: <span className="text-white font-medium">{trainingResult.training_results.n_features}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Results & Prediction */}
          <div className="space-y-6">
            {/* Feature Importance */}
            {importance && Object.keys(importance).length > 0 && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">📊 Feature Importance</h2>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {Object.entries(importance)
                    .sort((a, b) => b[1] - a[1])
                    .map(([feature, score]) => {
                      const maxScore = Math.max(...Object.values(importance));
                      const pct = (score / maxScore) * 100;
                      return (
                        <div key={feature} className="flex items-center gap-3 text-sm">
                          <span className="w-40 truncate text-gray-400">{feature}</span>
                          <div className="flex-1 h-3 bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="w-16 text-right font-mono text-gray-500">
                            {(score * 100).toFixed(1)}
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            {/* Test Prediction */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">🔮 Test Prediction</h2>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
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
                  onClick={testPrediction}
                  className="w-full bg-blue-500 hover:bg-blue-600 rounded py-2 text-sm font-medium transition-colors"
                >
                  Get Prediction
                </button>

                {prediction?.prediction && (
                  <div className="bg-[#0a0a0f] rounded-lg p-4 text-center">
                    <div className="text-4xl font-bold mb-2">
                      <span className={prediction.prediction.probability > 0.5 ? 'text-green-400' : 'text-red-400'}>
                        {(prediction.prediction.probability * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-sm text-gray-400">
                      {prediction.prediction.probability > 0.5 ? 'Likely Success' : 'Likely Failure'}
                    </div>
                    <div className={`mt-2 inline-block px-3 py-1 rounded text-sm ${
                      prediction.prediction.confidence_tier === 'HIGH' ? 'bg-green-500/20 text-green-400' :
                      prediction.prediction.confidence_tier === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {prediction.prediction.confidence_tier} Confidence
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Next Steps */}
            <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Next Steps</h2>
              <div className="space-y-2 text-sm">
                <a href="/labs/ml/ensemble" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-purple-400">→ Ensemble</span>
                  <span className="text-gray-400 ml-2">Get model consensus & disagreement</span>
                </a>
                <a href="/labs/ml/explainability" className="block p-3 bg-[#0a0a0f] rounded hover:bg-[#12121a] transition-colors">
                  <span className="font-medium text-blue-400">→ Explainability</span>
                  <span className="text-gray-400 ml-2">Understand prediction drivers</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
