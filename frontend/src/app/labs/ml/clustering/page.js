'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLClusteringPage() {
  const [clustering, setClustering] = useState(null);
  const [dendrogram, setDendrogram] = useState(null);
  const [network, setNetwork] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tickers, setTickers] = useState('AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, JPM, V, JNJ');
  const [nClusters, setNClusters] = useState(5);
  const [threshold, setThreshold] = useState(0.5);

  const clusterAssets = async () => {
    setLoading(true);
    try {
      const tickerList = tickers.split(',').map(t => t.trim().toUpperCase()).filter(t => t);
      const res = await fetch(`${API_BASE}/api/ml/clustering/assets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: tickerList,
          n_clusters: nClusters
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setClustering(data);
        fetchDendrogram();
        fetchNetwork();
      }
    } catch (error) {
      console.error('Failed to cluster assets:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchDendrogram = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/clustering/dendrogram`);
      const data = await res.json();
      if (!data.error) {
        setDendrogram(data);
      }
    } catch (error) {
      console.error('Failed to fetch dendrogram:', error);
    }
  };

  const fetchNetwork = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/clustering/network?threshold=${threshold}`);
      const data = await res.json();
      if (!data.error) {
        setNetwork(data);
      }
    } catch (error) {
      console.error('Failed to fetch network:', error);
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
            <h1 className="text-2xl font-bold">🔗 Clustering - Asset Similarity</h1>
          </div>
          <p className="text-gray-400">Detect redundancy, crowding, and diversification opportunities</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Clustering */}
          <div className="space-y-6">
            {/* Input */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Cluster Assets</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Tickers (comma-separated)</label>
                  <textarea
                    value={tickers}
                    onChange={(e) => setTickers(e.target.value)}
                    rows={3}
                    className="w-full bg-[#1a1a24] border border-gray-700 rounded px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                    placeholder="AAPL, MSFT, GOOGL..."
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Number of Clusters: {nClusters}</label>
                  <input
                    type="range"
                    min="2"
                    max="10"
                    value={nClusters}
                    onChange={(e) => setNClusters(parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>
                <button
                  onClick={clusterAssets}
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 rounded py-3 font-medium transition-all"
                >
                  {loading ? 'Clustering Assets...' : 'Run Clustering Analysis'}
                </button>
              </div>
            </div>

            {/* Cluster Results */}
            {clustering?.clustering && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Asset Clusters</h2>
                <div className="space-y-3">
                  {Object.entries(clustering.clustering.clusters || {}).map(([id, cluster]) => {
                    if (cluster.type === 'NOISE') return null;
                    const colors = ['bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500', 'bg-cyan-500', 'bg-pink-500'];
                    return (
                      <div key={id} className="p-4 bg-[#0a0a0f] rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`w-3 h-3 rounded-full ${colors[parseInt(id) % colors.length]}`} />
                          <span className="font-medium">Cluster {id}</span>
                          <span className="text-sm text-gray-400">({cluster.size} assets)</span>
                        </div>
                        <div className="flex flex-wrap gap-1 mb-2">
                          {cluster.assets?.map(asset => (
                            <span key={asset} className="px-2 py-1 bg-gray-800 rounded text-sm text-gray-300">
                              {asset}
                            </span>
                          ))}
                        </div>
                        <div className="text-xs text-gray-500">
                          Avg Correlation: {(cluster.avg_correlation * 100)?.toFixed(0)}%
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Diversification Score */}
            {clustering?.diversification && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Diversification Score</h2>
                <div className="text-center mb-4">
                  <div className="text-5xl font-bold text-blue-400">
                    {(clustering.diversification.diversification_ratio)?.toFixed(2)}x
                  </div>
                  <div className="text-sm text-gray-400">Diversification Ratio</div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-[#0a0a0f] rounded p-3">
                    <div className="text-gray-400">Effective N Assets</div>
                    <div className="text-lg font-bold">{clustering.diversification.effective_n_assets?.toFixed(1)}</div>
                  </div>
                  <div className="bg-[#0a0a0f] rounded p-3">
                    <div className="text-gray-400">Div Benefit</div>
                    <div className="text-lg font-bold text-green-400">
                      {(clustering.diversification.diversification_benefit * 100)?.toFixed(0)}%
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Redundancy & Network */}
          <div className="space-y-6">
            {/* Redundancy Analysis */}
            {clustering?.redundancy && (
              <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
                <h2 className="text-lg font-semibold mb-4">Redundancy Analysis</h2>
                <div className="mb-4 p-3 bg-[#0a0a0f] rounded">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Portfolio Redundancy</span>
                    <span className={`font-mono ${clustering.redundancy.portfolio_redundancy_score > 0.3 ? 'text-red-400' : 'text-green-400'}`}>
                      {(clustering.redundancy.portfolio_redundancy_score * 100)?.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full mt-2">
                    <div
                      className={`h-full rounded-full ${clustering.redundancy.portfolio_redundancy_score > 0.3 ? 'bg-red-500' : 'bg-green-500'}`}
                      style={{ width: `${clustering.redundancy.portfolio_redundancy_score * 100}%` }}
                    />
                  </div>
                </div>

                {clustering.redundancy.redundant_pairs?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-400 mb-2">Highly Correlated Pairs</h3>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {clustering.redundancy.redundant_pairs.slice(0, 10).map((pair, i) => (
                        <div key={i} className="flex items-center justify-between p-2 bg-[#0a0a0f] rounded text-sm">
                          <span className="text-gray-300">{pair.asset1} ↔ {pair.asset2}</span>
                          <span className="font-mono text-yellow-400">{(pair.correlation * 100)?.toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Network Graph Placeholder */}
            <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Correlation Network</h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">Threshold:</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={threshold}
                    onChange={(e) => setThreshold(parseFloat(e.target.value))}
                    className="w-16 bg-[#1a1a24] border border-gray-700 rounded px-2 py-1 text-sm"
                  />
                </div>
              </div>
              {network?.nodes ? (
                <div className="bg-[#0a0a0f] rounded-lg p-4">
                  <div className="text-sm text-gray-400 mb-2">
                    {network.nodes.length} nodes • {network.edges.length} edges
                  </div>
                  <div className="h-48 flex items-center justify-center">
                    <div className="text-center text-gray-500">
                      <div className="text-4xl mb-2">🕸️</div>
                      <p className="text-sm">Network visualization</p>
                      <p className="text-xs">Highly correlated assets connected</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-48 bg-[#0a0a0f] rounded-lg flex items-center justify-center text-gray-500">
                  Run clustering to see network
                </div>
              )}
            </div>

            {/* Tips */}
            <div className="bg-gradient-to-br from-cyan-500/10 to-blue-500/10 border border-cyan-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-3">💡 Diversification Tips</h2>
              <div className="space-y-2 text-sm text-gray-300">
                <div className="flex items-start gap-2">
                  <span className="text-cyan-400">•</span>
                  <span>Remove one asset from highly correlated pairs</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-cyan-400">•</span>
                  <span>Add assets from different clusters for true diversification</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-cyan-400">•</span>
                  <span>Diversification ratio &gt; 1.5x = well diversified</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
