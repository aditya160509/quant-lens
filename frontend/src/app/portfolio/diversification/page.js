'use client';

import { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function PortfolioDiversificationPage() {
  const [clusterData, setClusterData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tickers, setTickers] = useState('AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,META,JPM,V,JNJ');
  const [nClusters, setNClusters] = useState(4);
  const canvasRef = useRef(null);

  const runClustering = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/clustering/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: tickers.split(',').map(t => t.trim()),
          n_clusters: nClusters
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setClusterData(data);
      }
    } catch (error) {
      console.error('Clustering failed:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (clusterData && canvasRef.current) {
      drawNetworkGraph();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusterData]);

  const drawNetworkGraph = () => {
    const canvas = canvasRef.current;
    if (!canvas || !clusterData?.correlations) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, width, height);

    const assets = clusterData.assets || [];
    const correlations = clusterData.correlations || [];
    const clusters = clusterData.cluster_labels || {};
    
    const n = assets.length;
    if (n === 0) return;

    // Position nodes in a circle
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;
    
    const positions = assets.map((_, i) => ({
      x: centerX + radius * Math.cos((2 * Math.PI * i) / n - Math.PI / 2),
      y: centerY + radius * Math.sin((2 * Math.PI * i) / n - Math.PI / 2)
    }));

    // Draw edges (correlations)
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const corr = correlations[i]?.[j] || 0;
        if (Math.abs(corr) > 0.5) {
          ctx.beginPath();
          ctx.moveTo(positions[i].x, positions[i].y);
          ctx.lineTo(positions[j].x, positions[j].y);
          ctx.strokeStyle = corr > 0 
            ? `rgba(34, 197, 94, ${Math.abs(corr) * 0.6})`
            : `rgba(239, 68, 68, ${Math.abs(corr) * 0.6})`;
          ctx.lineWidth = Math.abs(corr) * 3;
          ctx.stroke();
        }
      }
    }

    // Draw nodes
    const clusterColors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
    
    assets.forEach((asset, i) => {
      const pos = positions[i];
      const clusterId = clusters[asset] || 0;
      const color = clusterColors[clusterId % clusterColors.length];
      
      // Node circle
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 24, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 10px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(asset, pos.x, pos.y);
    });
  };

  const getClusterColor = (clusterId) => {
    const colors = ['bg-blue-500', 'bg-green-500', 'bg-yellow-500', 'bg-red-500', 'bg-purple-500', 'bg-cyan-500'];
    return colors[clusterId % colors.length];
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <a href="/portfolio" className="text-gray-500 hover:text-gray-300">← Portfolio</a>
            <span className="text-gray-600">/</span>
            <h1 className="text-2xl font-bold">🔗 Diversification Analysis</h1>
          </div>
          <p className="text-gray-400">Asset clustering and redundancy detection for portfolio optimization</p>
        </div>

        {/* Controls */}
        <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm text-gray-400 mb-2">Tickers (comma-separated)</label>
              <input
                type="text"
                value={tickers}
                onChange={(e) => setTickers(e.target.value)}
                placeholder="AAPL,MSFT,GOOGL..."
                className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Number of Clusters</label>
              <div className="flex gap-2">
                <input
                  type="range"
                  min="2"
                  max="8"
                  value={nClusters}
                  onChange={(e) => setNClusters(Number(e.target.value))}
                  className="flex-1"
                />
                <span className="text-white font-mono w-8">{nClusters}</span>
              </div>
            </div>
          </div>
          <button
            onClick={runClustering}
            disabled={loading}
            className="mt-4 px-6 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 rounded font-medium transition-colors"
          >
            {loading ? 'Analyzing...' : 'Analyze Diversification'}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Network Graph */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Correlation Network</h2>
            <div className="relative">
              <canvas
                ref={canvasRef}
                width={500}
                height={400}
                className="w-full rounded-lg"
              />
              {!clusterData && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0a0a0f] rounded-lg">
                  <div className="text-center text-gray-500">
                    <div className="text-4xl mb-2">🔗</div>
                    <p>Run analysis to see network</p>
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-4 mt-4 text-xs text-gray-400">
              <div className="flex items-center gap-1">
                <div className="w-3 h-0.5 bg-green-500"></div>
                <span>Positive correlation</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-0.5 bg-red-500"></div>
                <span>Negative correlation</span>
              </div>
            </div>
          </div>

          {/* Cluster Assignments */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Asset Clusters</h2>
            
            {clusterData?.cluster_labels ? (
              <div className="space-y-3">
                {Object.entries(
                  Object.entries(clusterData.cluster_labels).reduce((acc, [asset, cluster]) => {
                    if (!acc[cluster]) acc[cluster] = [];
                    acc[cluster].push(asset);
                    return acc;
                  }, {})
                ).map(([clusterId, assets]) => (
                  <div key={clusterId} className="p-3 bg-[#0a0a0f] rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-3 h-3 rounded-full ${getClusterColor(Number(clusterId))}`}></div>
                      <span className="font-medium">Cluster {Number(clusterId) + 1}</span>
                      <span className="text-xs text-gray-500">({assets.length} assets)</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {assets.map(asset => (
                        <span key={asset} className="px-2 py-1 bg-gray-800 rounded text-sm">
                          {asset}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                Run analysis to see clusters
              </div>
            )}
          </div>

          {/* Diversification Score */}
          <div className="bg-gradient-to-br from-green-500/10 to-blue-500/10 border border-green-500/20 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Diversification Scorecard</h2>
            
            {clusterData?.diversification_score !== undefined ? (
              <>
                <div className="text-center mb-6">
                  <div className="text-5xl font-bold text-green-400">
                    {(clusterData.diversification_score || 0).toFixed(0)}
                  </div>
                  <div className="text-gray-400">out of 100</div>
                </div>
                
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Portfolio Entropy</span>
                    <span className="text-white">{(clusterData.entropy || 0).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Redundant Pairs</span>
                    <span className={clusterData.redundant_pairs?.length > 0 ? 'text-yellow-400' : 'text-green-400'}>
                      {clusterData.redundant_pairs?.length || 0}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Unique Clusters</span>
                    <span className="text-white">{clusterData.n_clusters || 0}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-8 text-gray-500">
                Run analysis to see score
              </div>
            )}
          </div>

          {/* Redundancy Warnings */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Redundancy Report</h2>
            
            {clusterData?.redundant_pairs?.length > 0 ? (
              <div className="space-y-2">
                {clusterData.redundant_pairs.map((pair, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                    <div className="flex items-center gap-2">
                      <span className="text-red-400">⚠️</span>
                      <span className="font-medium">{pair.asset_1} ↔ {pair.asset_2}</span>
                    </div>
                    <div className="text-right">
                      <div className="text-red-400 font-medium">{(pair.correlation * 100).toFixed(0)}%</div>
                      <div className="text-xs text-gray-500">correlation</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : clusterData ? (
              <div className="text-center py-8">
                <div className="text-4xl mb-2">✅</div>
                <p className="text-green-400">No significant redundancy detected</p>
                <p className="text-xs text-gray-500 mt-1">All asset pairs have correlation below threshold</p>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                Run analysis to check redundancy
              </div>
            )}
          </div>
        </div>

        {/* Recommendations */}
        {clusterData?.recommendations && (
          <div className="mt-6 bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Recommendations</h2>
            <div className="space-y-2">
              {clusterData.recommendations.map((rec, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-[#0a0a0f] rounded">
                  <span className="text-blue-400">💡</span>
                  <span className="text-gray-300">{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
