'use client';

import { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function MLStrategiesPage() {
  const [analysis, setAnalysis] = useState(null);
  const [heatmapData, setHeatmapData] = useState(null);
  const [allocation, setAllocation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [returnsInput, setReturnsInput] = useState('');
  const canvasRef = useRef(null);

  // Generate sample strategy returns
  const generateSampleData = () => {
    const strategies = ['Momentum', 'MeanReversion', 'Breakout', 'TrendFollow', 'StatArb'];
    const returns = {};
    
    strategies.forEach(strategy => {
      returns[strategy] = Array.from({ length: 100 }, () => 
        (Math.random() - 0.5) * 0.04 + (strategy === 'Momentum' || strategy === 'TrendFollow' ? 0.001 : 0)
      );
    });
    
    setReturnsInput(JSON.stringify(returns, null, 2));
    return returns;
  };

  const runAnalysis = async (data = null) => {
    setLoading(true);
    try {
      const returns = data || (returnsInput ? JSON.parse(returnsInput) : generateSampleData());
      
      const res = await fetch(`${API_BASE}/api/ml/strategies/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_returns: returns,
          overlap_threshold: 0.7
        })
      });
      const result = await res.json();
      if (result.status === 'success') {
        setAnalysis(result.analysis);
        fetchHeatmap();
        fetchAllocation();
      }
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchHeatmap = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/strategies/heatmap`);
      const data = await res.json();
      if (!data.error) {
        setHeatmapData(data);
      }
    } catch (error) {
      console.error('Heatmap fetch failed:', error);
    }
  };

  const fetchAllocation = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ml/strategies/allocation`);
      const data = await res.json();
      if (!data.error) {
        setAllocation(data);
      }
    } catch (error) {
      console.error('Allocation fetch failed:', error);
    }
  };

  useEffect(() => {
    if (heatmapData && canvasRef.current) {
      drawHeatmap();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heatmapData]);

  const drawHeatmap = () => {
    const canvas = canvasRef.current;
    if (!canvas || !heatmapData?.strategies) return;

    const ctx = canvas.getContext('2d');
    const strategies = heatmapData.strategies;
    const correlations = heatmapData.correlations;
    const n = strategies.length;
    
    const cellSize = 60;
    const padding = 100;
    
    canvas.width = n * cellSize + padding;
    canvas.height = n * cellSize + padding;
    
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw cells
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const corr = correlations[i][j];
        const x = padding + j * cellSize;
        const y = padding + i * cellSize;
        
        // Color based on correlation
        if (i === j) {
          ctx.fillStyle = '#3b82f6';
        } else if (corr >= 0.7) {
          ctx.fillStyle = `rgba(239, 68, 68, ${Math.abs(corr)})`;
        } else if (corr >= 0.5) {
          ctx.fillStyle = `rgba(234, 179, 8, ${Math.abs(corr)})`;
        } else if (corr >= 0) {
          ctx.fillStyle = `rgba(34, 197, 94, ${0.3 + Math.abs(corr) * 0.5})`;
        } else {
          ctx.fillStyle = `rgba(139, 92, 246, ${Math.abs(corr)})`;
        }
        
        ctx.fillRect(x, y, cellSize - 2, cellSize - 2);
        
        // Value text
        ctx.fillStyle = '#fff';
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(corr.toFixed(2), x + cellSize/2, y + cellSize/2);
      }
    }

    // Draw labels
    ctx.fillStyle = '#a0a0a0';
    ctx.font = '10px Inter, sans-serif';
    
    strategies.forEach((strategy, i) => {
      // Row labels
      ctx.textAlign = 'right';
      ctx.fillText(strategy, padding - 5, padding + i * cellSize + cellSize/2);
      
      // Column labels
      ctx.save();
      ctx.translate(padding + i * cellSize + cellSize/2, padding - 5);
      ctx.rotate(-Math.PI/4);
      ctx.textAlign = 'right';
      ctx.fillText(strategy, 0, 0);
      ctx.restore();
    });
  };

  const getGradeColor = (grade) => {
    switch(grade) {
      case 'A': return 'text-green-400 bg-green-500/20';
      case 'B': return 'text-blue-400 bg-blue-500/20';
      case 'C': return 'text-yellow-400 bg-yellow-500/20';
      case 'D': return 'text-red-400 bg-red-500/20';
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
            <h1 className="text-2xl font-bold">🔀 Strategy Overlap Detector</h1>
          </div>
          <p className="text-gray-400">Detect strategy redundancy and crowding for portfolio optimization</p>
        </div>

        {/* Controls */}
        <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex gap-3">
              <button
                onClick={() => runAnalysis(generateSampleData())}
                disabled={loading}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
              >
                Load Sample Data
              </button>
              <button
                onClick={() => runAnalysis()}
                disabled={loading}
                className="px-6 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 rounded font-medium transition-colors"
              >
                {loading ? 'Analyzing...' : 'Analyze Overlap'}
              </button>
            </div>
            <div className="text-sm text-gray-400">
              {analysis?.n_strategies} strategies analyzed
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Correlation Heatmap */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Strategy Correlation Matrix</h2>
            <div className="flex justify-center">
              <canvas ref={canvasRef} className="rounded" />
            </div>
            <div className="flex gap-4 mt-4 text-xs text-gray-400 justify-center">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-red-500 rounded"></div>
                <span>High overlap (&gt;0.7)</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-yellow-500 rounded"></div>
                <span>Moderate</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-green-500 rounded"></div>
                <span>Low overlap</span>
              </div>
            </div>
          </div>

          {/* Diversification Score */}
          <div className="space-y-4">
            <div className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Diversification Score</h2>
              
              {analysis?.diversification_score ? (
                <>
                  <div className="flex items-center justify-center mb-4">
                    <div className="relative">
                      <svg className="w-32 h-32 transform -rotate-90">
                        <circle
                          cx="64" cy="64" r="56"
                          stroke="#1a1a24" strokeWidth="12" fill="none"
                        />
                        <circle
                          cx="64" cy="64" r="56"
                          stroke={analysis.diversification_score.score >= 70 ? '#22c55e' : analysis.diversification_score.score >= 50 ? '#eab308' : '#ef4444'}
                          strokeWidth="12" fill="none"
                          strokeDasharray={`${analysis.diversification_score.score * 3.52} 352`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-3xl font-bold">{analysis.diversification_score.score?.toFixed(0)}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getGradeColor(analysis.diversification_score.grade)}`}>
                          Grade {analysis.diversification_score.grade}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="text-center text-sm text-gray-400">
                    {analysis.diversification_score.interpretation}
                  </div>
                  
                  <div className="mt-4 p-3 bg-[#0a0a0f] rounded text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Avg Correlation</span>
                      <span className="text-white">{analysis.diversification_score.avg_correlation?.toFixed(3)}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  Run analysis to see diversification score
                </div>
              )}
            </div>

            {/* Concentration Risk */}
            {analysis?.concentration_risk && (
              <div className={`border rounded-lg p-5 ${
                analysis.concentration_risk.risk_level === 'HIGH' 
                  ? 'bg-red-500/10 border-red-500/20' 
                  : analysis.concentration_risk.risk_level === 'MODERATE'
                  ? 'bg-yellow-500/10 border-yellow-500/20'
                  : 'bg-green-500/10 border-green-500/20'
              }`}>
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">Concentration Risk</h3>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    analysis.concentration_risk.risk_level === 'HIGH' 
                      ? 'bg-red-500/20 text-red-400' 
                      : analysis.concentration_risk.risk_level === 'MODERATE'
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-green-500/20 text-green-400'
                  }`}>
                    {analysis.concentration_risk.risk_level}
                  </span>
                </div>
                {analysis.concentration_risk.warning && (
                  <p className="mt-2 text-sm text-gray-400">{analysis.concentration_risk.warning}</p>
                )}
              </div>
            )}
          </div>

          {/* Overlap Warnings */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Overlap Warnings</h2>
            
            {analysis?.overlap_pairs?.length > 0 ? (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {analysis.overlap_pairs.map((pair, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-lg ${
                      pair.severity === 'HIGH' 
                        ? 'bg-red-500/10 border border-red-500/20' 
                        : 'bg-yellow-500/10 border border-yellow-500/20'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">
                        {pair.strategy_1} ↔ {pair.strategy_2}
                      </span>
                      <span className={`font-bold ${pair.severity === 'HIGH' ? 'text-red-400' : 'text-yellow-400'}`}>
                        {(pair.correlation * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-400">{pair.recommendation}</p>
                  </div>
                ))}
              </div>
            ) : analysis ? (
              <div className="text-center py-8">
                <div className="text-4xl mb-2">✅</div>
                <p className="text-green-400">No significant overlap detected</p>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                Run analysis to check for overlap
              </div>
            )}
          </div>

          {/* Suggested Allocation */}
          <div className="bg-[#12121a] border border-gray-800 rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Suggested Allocation</h2>
            
            {allocation?.suggested_allocations ? (
              <>
                <div className="space-y-3">
                  {Object.entries(allocation.suggested_allocations)
                    .sort((a, b) => b[1] - a[1])
                    .map(([strategy, weight]) => (
                    <div key={strategy} className="flex items-center gap-3">
                      <span className="w-28 truncate text-sm">{strategy}</span>
                      <div className="flex-1 h-4 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                          style={{ width: `${weight}%` }}
                        />
                      </div>
                      <span className="w-12 text-right text-sm font-mono">{weight.toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-xs text-gray-500">
                  {allocation.methodology} — {allocation.note}
                </p>
              </>
            ) : (
              <div className="text-center py-8 text-gray-500">
                Run analysis to see allocation suggestions
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
