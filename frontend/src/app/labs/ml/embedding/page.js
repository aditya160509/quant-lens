'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLEmbeddingPage() {
  const [embedding, setEmbedding] = useState(null);
  const [separation, setSeparation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [method, setMethod] = useState('umap');
  const [nComponents, setNComponents] = useState(2);

  const computeEmbedding = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/embedding/compute?method=${method}&n_components=${nComponents}`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        setEmbedding(data.embedding);
        fetchSeparation();
      }
    } catch (error) {
      console.error('Failed to compute embedding:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSeparation = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/embedding/separation`);
      const data = await res.json();
      if (!data.error) {
        setSeparation(data);
      }
    } catch (error) {
      console.error('Failed to fetch separation:', error);
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
            <h1 className="text-2xl font-bold">🎨 Embedding - Feature Space Visualization</h1>
          </div>
          <p className="text-gray-400">Project high-dimensional features into 2D/3D for visualization</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Controls */}
          <div className="space-y-6">
            {/* Embedding Controls */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Compute Embedding</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Method</label>
                  <div className="grid grid-cols-3 gap-2">
                    {['umap', 'tsne', 'pca'].map(m => (
                      <button
                        key={m}
                        onClick={() => setMethod(m)}
                        className={`py-2 px-4 rounded text-sm font-medium transition-colors ${
                          method === m
                            ? 'bg-purple-500 text-white'
                            : 'bg-[#1a1a24] text-gray-400 hover:text-white'
                        }`}
                      >
                        {m.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Dimensions</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[2, 3].map(n => (
                      <button
                        key={n}
                        onClick={() => setNComponents(n)}
                        className={`py-2 px-4 rounded text-sm font-medium transition-colors ${
                          nComponents === n
                            ? 'bg-blue-500 text-white'
                            : 'bg-[#1a1a24] text-gray-400 hover:text-white'
                        }`}
                      >
                        {n}D
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  onClick={computeEmbedding}
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 rounded py-3 font-medium transition-all"
                >
                  {loading ? 'Computing Embedding...' : 'Compute Embedding'}
                </button>
              </div>
            </div>

            {/* Method Info */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">Method Information</h2>
              <div className="space-y-3 text-sm">
                <div className={`p-3 rounded ${method === 'umap' ? 'bg-purple-500/20 border border-purple-500/30' : 'bg-[#0a0a0f]'}`}>
                  <div className="font-medium text-purple-400">UMAP</div>
                  <div className="text-gray-400">Best for preserving global structure. Fast and scalable.</div>
                </div>
                <div className={`p-3 rounded ${method === 'tsne' ? 'bg-blue-500/20 border border-blue-500/30' : 'bg-[#0a0a0f]'}`}>
                  <div className="font-medium text-blue-400">t-SNE</div>
                  <div className="text-gray-400">Best for local structure. Good for cluster visualization.</div>
                </div>
                <div className={`p-3 rounded ${method === 'pca' ? 'bg-green-500/20 border border-green-500/30' : 'bg-[#0a0a0f]'}`}>
                  <div className="font-medium text-green-400">PCA</div>
                  <div className="text-gray-400">Linear, interpretable. Shows variance explained.</div>
                </div>
              </div>
            </div>

            {/* Separation Metrics */}
            {separation && !separation.error && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Separation Metrics</h2>
                <div className="space-y-4">
                  <div className="text-center p-4 bg-[#0a0a0f] rounded-lg">
                    <div className="text-3xl font-bold text-blue-400">
                      {separation.silhouette_score?.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-400">Silhouette Score</div>
                    <div className={`mt-2 text-sm ${
                      separation.overall_separation === 'GOOD' ? 'text-green-400' :
                      separation.overall_separation === 'MODERATE' ? 'text-yellow-400' :
                      'text-red-400'
                    }`}>
                      {separation.overall_separation} Separation
                    </div>
                  </div>
                  <div className="text-sm text-gray-500">
                    Higher silhouette score = better cluster separation in embedding space
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Visualization */}
          <div className="space-y-6">
            {/* Embedding Plot */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Embedding Visualization</h2>
              {embedding ? (
                <div className="bg-[#0a0a0f] rounded-lg p-4">
                  <div className="mb-3 text-sm text-gray-400">
                    {embedding.n_samples} points • {embedding.method?.toUpperCase()} • {embedding.n_components}D
                  </div>
                  <div className="h-80 relative">
                    {/* SVG Scatter Plot */}
                    <svg className="w-full h-full" viewBox="-50 -50 100 100">
                      {embedding.x?.map((x, i) => {
                        const y = embedding.y?.[i] || 0;
                        const scaledX = (x / (Math.max(...embedding.x.map(Math.abs)) || 1)) * 45;
                        const scaledY = (y / (Math.max(...embedding.y.map(Math.abs)) || 1)) * 45;
                        return (
                          <circle
                            key={i}
                            cx={scaledX}
                            cy={-scaledY}
                            r="1.5"
                            fill="rgba(147, 51, 234, 0.6)"
                            className="hover:fill-purple-400"
                          />
                        );
                      })}
                    </svg>
                    {/* Axes Labels */}
                    <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 text-xs text-gray-500">
                      Dimension 1
                    </div>
                    <div className="absolute left-0 top-1/2 transform -translate-y-1/2 -rotate-90 text-xs text-gray-500">
                      Dimension 2
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-80 bg-[#0a0a0f] rounded-lg flex items-center justify-center">
                  <div className="text-center text-gray-500">
                    <div className="text-4xl mb-2">📊</div>
                    <p className="text-sm">Compute embedding to visualize</p>
                    <p className="text-xs text-gray-600">Feature space projected to {nComponents}D</p>
                  </div>
                </div>
              )}
            </div>

            {/* PCA Variance (if applicable) */}
            {embedding?.explained_variance && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Explained Variance (PCA)</h2>
                <div className="space-y-2">
                  {embedding.explained_variance.map((v, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-sm text-gray-400 w-16">PC{i + 1}</span>
                      <div className="flex-1 h-4 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-green-500 to-emerald-500"
                          style={{ width: `${v * 100}%` }}
                        />
                      </div>
                      <span className="text-sm font-mono text-green-400 w-16 text-right">
                        {(v * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                  <div className="mt-2 p-3 bg-[#0a0a0f] rounded text-sm">
                    <span className="text-gray-400">Total:</span>
                    <span className="ml-2 text-green-400 font-mono">
                      {(embedding.explained_variance.reduce((a, b) => a + b, 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Use Cases */}
            <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">💡 Embedding Use Cases</h2>
              <div className="space-y-2 text-sm text-gray-300">
                <div className="flex items-start gap-2">
                  <span className="text-purple-400">•</span>
                  <span>Validate regime labels form distinct clusters</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-purple-400">•</span>
                  <span>Identify outlier signals in feature space</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-purple-400">•</span>
                  <span>Visualize decision boundaries of classifiers</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
