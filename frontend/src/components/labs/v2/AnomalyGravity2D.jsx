import React, { useEffect, useState } from "react";
import dynamic from 'next/dynamic';
import { Maximize2, Minimize2 } from 'lucide-react';
import { fetchML2Anomalies } from "@/lib/api";

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function AnomalyGravity2D({ universe, ticker, timeframe }) {
  const [anomalyData, setAnomalyData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('2D');

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Anomalies(universe, ticker, timeframe);
            if (!isMounted) return;
            setAnomalyData(data);
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
      <div className="flex items-center justify-center h-[600px] bg-black/40 border border-terminal-red/20 rounded-xl">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-terminal-red border-t-transparent rounded-full animate-spin"></div>
          <div className="text-terminal-red font-mono animate-pulse uppercase">Scanning_Phase_Space_Anomalies...</div>
        </div>
      </div>
    );
  }

  if (!anomalyData || !anomalyData.points) return null;

  const points = anomalyData.points;
  const anomalies = points.filter(p => p.is_anomaly);
  const normal = points.filter(p => !p.is_anomaly);

  const getTraceData = () => {
      if (viewMode === '3D') {
          return [
            {
                x: normal.map(p => p.x),
                y: normal.map(p => p.y),
                z: normal.map(p => p.z),
                mode: 'markers',
                type: 'scatter3d',
                name: 'Normal',
                marker: { color: 'rgba(255,255,255,0.05)', size: 2 }
            },
            {
                x: anomalies.map(p => p.x),
                y: anomalies.map(p => p.y),
                z: anomalies.map(p => p.z),
                mode: 'markers',
                type: 'scatter3d',
                name: 'Anomalies',
                marker: { color: '#ff3333', size: 6, symbol: 'diamond' }
            }
          ];
      }
      return [
        {
          x: normal.map(p => p.x),
          y: normal.map(p => p.y),
          mode: 'markers',
          type: 'scatter',
          name: 'Normal Variance',
          marker: { color: 'rgba(255,255,255,0.1)', size: 4 }
        },
        {
          x: anomalies.map(p => p.x),
          y: anomalies.map(p => p.y),
          mode: 'markers',
          type: 'scatter',
          name: 'Anomaly Detected',
          marker: { color: '#ff3333', size: 10, symbol: 'diamond-open' },
          text: anomalies.map(p => `Score: ${p.score.toFixed(2)}`),
          hoverinfo: 'text'
        }
      ];
  };

  return (
    <div className="relative border border-terminal-red/20 rounded-xl overflow-hidden bg-black/40 p-6 flex flex-col gap-6">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 min-h-[500px] bg-black/60 border border-white/5 rounded-lg p-2 relative group">
          <Plot
            data={getTraceData()}
            layout={{
                autosize: true,
                margin: { t: 30, b: 40, l: 50, r: 20 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                showlegend: true,
                legend: { font: { color: '#fff', size: 10 }, x: 0, y: 1 },
                xaxis: { gridcolor: 'rgba(255,255,255,0.05)', tickfont: { size: 10, color: '#666' } },
                yaxis: { gridcolor: 'rgba(255,255,255,0.05)', tickfont: { size: 10, color: '#666' } },
                scene: viewMode === '3D' ? {
                    xaxis: { title: 'PCA_1', gridcolor: 'rgba(255,255,255,0.05)' },
                    yaxis: { title: 'PCA_2', gridcolor: 'rgba(255,255,255,0.05)' },
                    zaxis: { title: 'PCA_3', gridcolor: 'rgba(255,255,255,0.05)' },
                    camera: { eye: { x: 1.2, y: 1.2, z: 1.2 } }
                } : undefined
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />

          <button 
            onClick={() => setViewMode(prev => prev === '2D' ? '3D' : '2D')}
            className="absolute top-4 right-4 px-3 py-1.5 bg-black/80 border border-white/10 rounded text-[10px] font-bold text-red-500 hover:border-red-500/50 transition-all flex items-center gap-2"
          >
            {viewMode === '2D' ? <Maximize2 size={12} /> : <Minimize2 size={12} />}
            {viewMode} SCAN
          </button>
        </div>

        <div className="lg:col-span-1 space-y-4">
            <div className="bg-black/80 border border-red-500/30 p-8 rounded-lg shadow-xl flex flex-col h-full border-t-4 border-t-red-500">
                <div className="text-[10px] text-red-400 font-bold tracking-[0.2em] uppercase mb-1">Outlier Identification</div>
                <h3 className="text-2xl font-black text-white uppercase mb-6 tracking-tight">Anomaly Gravity</h3>
                
                <div className="space-y-6">
                    <div className="p-4 bg-red-500/5 rounded border border-red-500/10">
                        <div className="text-[10px] text-gray-500 uppercase font-bold mb-1">Systemic Anomaly Score</div>
                        <div className="text-4xl font-mono font-black text-red-500">{(anomalyData.suspicion_score || 0).toFixed(1)}</div>
                    </div>

                    <div className="space-y-3">
                        <div className="text-[9px] text-gray-400 font-bold uppercase tracking-widest">Recent Trigger Events</div>
                        {anomalies.slice(0, 3).map((a, i) => (
                            <div key={i} className="flex justify-between items-center p-2 bg-white/5 rounded text-[10px] font-mono border border-white/5">
                                <span className="text-gray-400">PHASE_SHIFT_{i}</span>
                                <span className="text-red-400 font-bold">+{a.score.toFixed(2)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
