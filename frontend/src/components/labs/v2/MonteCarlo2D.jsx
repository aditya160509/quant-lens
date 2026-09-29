import React, { useEffect, useState } from "react";
import dynamic from 'next/dynamic';
import { fetchML2MonteCarlo } from "@/lib/api";

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function MonteCarlo2D({ universe, ticker, timeframe }) {
  const [mcData, setMcData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2MonteCarlo(universe, ticker, timeframe);
            if (!isMounted) return;
            setMcData(data);
            setLoading(false);
        } catch (err) {
            if (isMounted) setLoading(false);
        }
    };
    loadData();
    return () => { isMounted = false; };
  }, [universe, ticker, timeframe]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[600px] bg-black/40 border border-terminal-gray/20 rounded-xl">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-terminal-yellow border-t-transparent rounded-full animate-spin"></div>
          <div className="text-terminal-yellow font-mono animate-pulse uppercase">Simulating_Future_Paths...</div>
        </div>
      </div>
    );
  }

  if (!mcData) return null;

  const horizon = mcData.horizon || 30;
  const days = Array.from({ length: horizon + 1 }, (_, i) => i);
  const samplePaths = mcData.simulated_paths?.slice(0, 50) || [];
  
  const traces = [
    // Percentile Cloud 95%
    {
        x: [...days, ...days.slice().reverse()],
        y: [...(mcData.cone_upper || []), ...(mcData.cone_lower || []).slice().reverse()],
        fill: 'toself',
        fillcolor: 'rgba(0, 255, 170, 0.05)',
        line: { color: 'transparent' },
        name: '95% Confidence',
        hoverinfo: 'none'
    },
    // Median Path
    {
        x: days,
        y: mcData.median_path || [],
        mode: 'lines',
        line: { color: '#00ffaa', width: 3 },
        name: 'Median Projection'
    }
  ];

  // Add sample paths
  samplePaths.forEach((path, i) => {
      traces.push({
          x: days,
          y: path,
          mode: 'lines',
          line: { color: 'rgba(0, 255, 170, 0.1)', width: 0.5 },
          hoverinfo: 'none',
          showlegend: false
      });
  });

  return (
    <div className="relative border border-terminal-gray/20 rounded-xl overflow-hidden bg-black/40 p-6 flex flex-col gap-6">
      
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 min-h-[500px] bg-black/60 border border-white/5 rounded-lg p-2">
            <Plot
                data={traces}
                layout={{
                    autosize: true,
                    margin: { t: 30, b: 40, l: 50, r: 20 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    showlegend: true,
                    legend: { font: { color: '#fff', size: 10 }, x: 0, y: 1 },
                    xaxis: {
                        gridcolor: 'rgba(255,255,255,0.05)',
                        tickfont: { size: 10, color: '#666' },
                        title: { text: 'DAYS INTO FUTURE', font: { size: 9, color: '#444' } }
                    },
                    yaxis: {
                        gridcolor: 'rgba(255,255,255,0.05)',
                        tickfont: { size: 10, color: '#666' },
                        title: { text: 'PRICE PROJECTION ($)', font: { size: 9, color: '#444' } }
                    }
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
            />
          </div>

          <div className="lg:col-span-1 space-y-4">
              <div className="bg-black/80 border border-terminal-green/30 p-6 rounded-lg shadow-xl h-full flex flex-col justify-between">
                <div>
                  <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Statistical Projection</div>
                  <h3 className="text-2xl font-black text-white uppercase mb-6 tracking-tight">Monte Carlo</h3>
                  
                  <div className="space-y-6">
                      <div className="flex justify-between items-end border-b border-white/5 pb-2">
                          <span className="text-[10px] uppercase font-bold text-gray-400">ITM Probability</span>
                          <span className={`text-3xl font-black font-mono ${(mcData.prob_profit || 0) > 50 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                            {(mcData.prob_profit || 0).toFixed(1)}%
                          </span>
                      </div>

                      <div className="grid grid-cols-1 gap-4">
                          <div className="bg-white/5 p-4 rounded border border-white/5">
                              <div className="text-[9px] text-terminal-blue font-bold uppercase mb-1">Bull Target (P95)</div>
                              <div className="text-xl font-mono font-bold text-terminal-green">${(mcData.percentiles?.p95 || 0).toFixed(2)}</div>
                          </div>
                          <div className="bg-white/5 p-4 rounded border border-white/5">
                              <div className="text-[9px] text-terminal-blue font-bold uppercase mb-1">Median (P50)</div>
                              <div className="text-xl font-mono font-bold text-terminal-white">${(mcData.percentiles?.p50 || 0).toFixed(2)}</div>
                          </div>
                          <div className="bg-white/5 p-4 rounded border border-white/5">
                              <div className="text-[9px] text-terminal-blue font-bold uppercase mb-1">Bear Floor (P05)</div>
                              <div className="text-xl font-mono font-bold text-terminal-red">${(mcData.percentiles?.p05 || 0).toFixed(2)}</div>
                          </div>
                      </div>
                  </div>
                </div>

                <div className="bg-terminal-green/5 border border-terminal-green/10 p-3 rounded mt-4">
                    <div className="text-[8px] text-terminal-green font-bold uppercase mb-1">System Engine</div>
                    <p className="text-[9px] text-terminal-green/70 font-mono leading-tight">
                        Simulation based on recursive historical drift and GARCH vol. 50,000 nodes generated.
                    </p>
                </div>
              </div>
          </div>
      </div>
    </div>
  );
}
