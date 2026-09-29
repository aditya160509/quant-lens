'use client';

import { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLRegimeQualityPage() {
  const [analysis, setAnalysis] = useState(null);
  const [overlapData, setOverlapData] = useState(null);
  const [vizData, setVizData] = useState(null);
  const [loading, setLoading] = useState(false);
  const canvasRef = useRef(null);

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ml/regime-quality/analyze`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        setAnalysis(data.analysis);
        fetchOverlap();
        fetchVisualization();
      } else if (data.error) {
        alert(data.error);
      }
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchOverlap = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/regime-quality/overlap`);
      const data = await res.json();
      if (!data.error) {
        setOverlapData(data);
      }
    } catch (error) {
      console.error('Overlap fetch failed:', error);
    }
  };

  const fetchVisualization = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/regime-quality/visualization`);
      const data = await res.json();
      if (!data.error) {
        setVizData(data);
      }
    } catch (error) {
      console.error('Visualization fetch failed:', error);
    }
  };

  useEffect(() => {
    if (vizData && canvasRef.current) {
      drawEmbeddingPlot();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vizData]);

  const drawEmbeddingPlot = () => {
    const canvas = canvasRef.current;
    if (!canvas || !vizData?.embeddings) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, width, height);

    const embeddings = vizData.embeddings;
    const labels = vizData.labels;
    const centroids = vizData.centroids || {};
    
    if (embeddings.length === 0) return;

    // Find bounds
    const xs = embeddings.map(e => e[0]);
    const ys = embeddings.map(e => e[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    
    const padding = 40;
    const scaleX = (width - 2 * padding) / (maxX - minX || 1);
    const scaleY = (height - 2 * padding) / (maxY - minY || 1);

    // Regime colors
    const colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
    
    // Draw points
    embeddings.forEach((point, i) => {
      const x = padding + (point[0] - minX) * scaleX;
      const y = padding + (point[1] - minY) * scaleY;
      const label = labels[i];
      const color = colors[label % colors.length];
      
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.fillStyle = color + '80';
      ctx.fill();
    });

    // Draw centroids
    Object.entries(centroids).forEach(([label, centroid]) => {
      const x = padding + (centroid[0] - minX) * scaleX;
      const y = padding + (centroid[1] - minY) * scaleY;
      const color = colors[Number(label) % colors.length];
      
      // Star shape for centroid
      ctx.beginPath();
      for (let i = 0; i < 10; i++) {
        const radius = i % 2 === 0 ? 12 : 6;
        const angle = (i * Math.PI / 5) - Math.PI / 2;
        const px = x + radius * Math.cos(angle);
        const py = y + radius * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  };

  const getGradeColor = (grade) => {
    switch(grade) {
      case 'A': return 'text-green-400 bg-green-500/20';
      case 'B': return 'text-blue-400 bg-blue-500/20';
      case 'C': return 'text-yellow-400 bg-yellow-500/20';
      case 'D': return 'text-orange-400 bg-orange-500/20';
      case 'F': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
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
            <h1 className="text-2xl font-bold">🎯 Regime Separation Quality</h1>
          </div>
          <p className="text-gray-400">Validate that market regimes are truly distinct in feature space</p>
        </div>

        {/* Prerequisites */}
        <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg p-5 mb-6">
          <h3 className="font-medium text-blue-400 mb-2">Prerequisites</h3>
          <p className="text-sm text-gray-400 mb-3">
            This analysis requires computed embeddings and discovered regimes.
          </p>
          <div className="flex gap-3">
            <a href="/labs/ml/embedding" className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded text-sm hover:bg-blue-500/30 transition-colors">
              → Compute Embeddings
            </a>
            <a href="/labs/ml/regimes" className="px-4 py-2 bg-purple-500/20 text-purple-400 rounded text-sm hover:bg-purple-500/30 transition-colors">
              → Discover Regimes
            </a>
            <button
              onClick={runAnalysis}
              disabled={loading}
              className="px-6 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-50 rounded font-medium transition-colors"
            >
              {loading ? 'Analyzing...' : 'Analyze Separation'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Embedding Visualization */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Regime-Colored Embedding</h2>
            <div className="relative">
              <canvas
                ref={canvasRef}
                width={500}
                height={400}
                className="w-full rounded-lg"
              />
              {!vizData && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0a0a0f] rounded-lg">
                  <div className="text-center text-gray-500">
                    <div className="text-4xl mb-2">🎯</div>
                    <p>Run analysis to visualize separation</p>
                  </div>
                </div>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-2 text-center">
              Points colored by regime • Stars mark centroids
            </p>
          </div>

          {/* Separation Score */}
          <div className="space-y-4">
            <div className="bg-gradient-to-br from-green-500/10 to-blue-500/10 border border-green-500/20 rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4">Separation Quality Score</h2>
              
              {analysis?.overall_metrics ? (
                <>
                  <div className="flex items-center justify-center mb-4">
                    <div className="relative">
                      <svg className="w-36 h-36 transform -rotate-90">
                        <circle
                          cx="72" cy="72" r="60"
                          stroke="#1a1a24" strokeWidth="14" fill="none"
                        />
                        <circle
                          cx="72" cy="72" r="60"
                          stroke={analysis.overall_metrics.separation_score >= 60 ? '#22c55e' : analysis.overall_metrics.separation_score >= 45 ? '#eab308' : '#ef4444'}
                          strokeWidth="14" fill="none"
                          strokeDasharray={`${analysis.overall_metrics.separation_score * 3.77} 377`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-4xl font-bold">{analysis.overall_metrics.separation_score?.toFixed(0)}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium mt-1 ${getGradeColor(analysis.overall_metrics.separation_grade)}`}>
                          Grade {analysis.overall_metrics.separation_grade}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="p-3 bg-[#0a0a0f] rounded">
                      <div className="text-gray-400">Silhouette</div>
                      <div className="text-lg font-bold text-blue-400">
                        {analysis.overall_metrics.silhouette_score?.toFixed(3)}
                      </div>
                    </div>
                    <div className="p-3 bg-[#0a0a0f] rounded">
                      <div className="text-gray-400">Davies-Bouldin</div>
                      <div className="text-lg font-bold text-purple-400">
                        {analysis.overall_metrics.davies_bouldin?.toFixed(3)}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  Run analysis to see separation score
                </div>
              )}
            </div>

            {/* Ambiguous Observations */}
            {analysis?.ambiguous_observations && (
              <div className={`border rounded-lg p-5 ${
                analysis.ambiguous_observations.ambiguous_pct > 20
                  ? 'bg-red-500/10 border-red-500/20'
                  : analysis.ambiguous_observations.ambiguous_pct > 10
                  ? 'bg-yellow-500/10 border-yellow-500/20'
                  : 'bg-green-500/10 border-green-500/20'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold">Ambiguous Observations</h3>
                  <span className="text-2xl font-bold">
                    {analysis.ambiguous_observations.ambiguous_pct?.toFixed(1)}%
                  </span>
                </div>
                <p className="text-sm text-gray-400">
                  {analysis.ambiguous_observations.interpretation}
                </p>
              </div>
            )}
          </div>

          {/* Regime Metrics */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Per-Regime Metrics</h2>
            
            {analysis?.regime_metrics && Object.keys(analysis.regime_metrics).length > 0 ? (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {Object.entries(analysis.regime_metrics).map(([regime, metrics]) => (
                  <div key={regime} className="p-3 bg-[#0a0a0f] rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium">{regime}</span>
                      <span className="text-xs text-gray-400">{metrics.n_samples} samples</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <span className="text-gray-400">Tightness</span>
                        <div className="font-mono text-white">{metrics.tightness?.toFixed(3)}</div>
                      </div>
                      <div>
                        <span className="text-gray-400">Radius</span>
                        <div className="font-mono text-white">{metrics.radius?.toFixed(3)}</div>
                      </div>
                      <div>
                        <span className="text-gray-400">Isolation</span>
                        <div className={`font-mono ${metrics.isolation_score > 1 ? 'text-green-400' : 'text-yellow-400'}`}>
                          {metrics.isolation_score?.toFixed(2)}
                        </div>
                      </div>
                    </div>
                    {metrics.nearest_regime && (
                      <div className="mt-2 text-xs text-gray-500">
                        Nearest: {metrics.nearest_regime} (dist: {metrics.distance_to_nearest?.toFixed(3)})
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                Run analysis to see regime metrics
              </div>
            )}
          </div>

          {/* Overlap Matrix */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Regime Overlap Matrix</h2>
            
            {overlapData?.regimes && overlapData.overlap_matrix ? (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr>
                        <th className="p-2 text-left text-gray-400"></th>
                        {overlapData.regimes.map(regime => (
                          <th key={regime} className="p-2 text-center text-gray-400 text-xs">{regime}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {overlapData.regimes.map((regime, i) => (
                        <tr key={regime}>
                          <td className="p-2 text-gray-400 text-xs">{regime}</td>
                          {overlapData.overlap_matrix[i].map((val, j) => (
                            <td key={j} className="p-1">
                              <div className={`p-2 rounded text-center text-xs ${
                                i === j ? 'bg-gray-700' :
                                val > 30 ? 'bg-red-500/50' :
                                val > 15 ? 'bg-yellow-500/50' :
                                'bg-green-500/30'
                              }`}>
                                {val?.toFixed(0)}%
                              </div>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                
                {overlapData.high_overlap_pairs?.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <h4 className="text-sm font-medium text-red-400">High Overlap Pairs</h4>
                    {overlapData.high_overlap_pairs.map((pair, idx) => (
                      <div key={idx} className="p-2 bg-red-500/10 border border-red-500/20 rounded text-sm">
                        <span className="font-medium">{pair.regime_1} ↔ {pair.regime_2}</span>
                        <span className="text-red-400 ml-2">{pair.overlap_pct?.toFixed(0)}% overlap</span>
                        <p className="text-xs text-gray-400 mt-1">{pair.recommendation}</p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12 text-gray-500">
                Run analysis to see overlap matrix
              </div>
            )}
          </div>
        </div>

        {/* Recommendations */}
        {analysis?.recommendations && (
          <div className="mt-6 bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Recommendations</h2>
            <div className="space-y-2">
              {analysis.recommendations.map((rec, idx) => (
                <div key={idx} className="p-3 bg-[#0a0a0f] rounded-lg text-sm">
                  {rec}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
