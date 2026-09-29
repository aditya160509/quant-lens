import React, { useEffect, useState, useMemo } from "react";
import dynamic from 'next/dynamic';
import { Maximize2, Minimize2, Search } from 'lucide-react';
import { fetchML2GalaxyUniverse, fetchML2GalaxySimilar } from "@/lib/api";

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function GalaxyStarMap2D({ universe, timeframe }) {
  const [galaxyData, setGalaxyData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStock, setSelectedStock] = useState(null);
  const [similarStocks, setSimilarStocks] = useState([]);
  const [viewMode, setViewMode] = useState('3D');

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2GalaxyUniverse(universe, timeframe);
            if (!isMounted) return;
            setGalaxyData(data || []);
            setLoading(false);
        } catch (err) {
            if (isMounted) setLoading(false);
        }
    };
    loadData();
    return () => { isMounted = false; };
  }, [universe, timeframe]);

  const handlePointClick = async (event) => {
      const pointIndex = event.points[0].pointIndex;
      // Note: with multiple traces (by sector), pointIndex is relative to the trace.
      // We need to find the actual stock by ticker or name from the host data.
      const ticker = event.points[0].text.split('\n')[0];
      const stock = galaxyData.find(s => s.ticker === ticker);
      
      if (!stock) return;
      
      setSelectedStock(stock);
      setSimilarStocks([]); 
      try {
          const similar = await fetchML2GalaxySimilar(universe, stock.ticker, timeframe);
          setSimilarStocks(similar);
      } catch (e) {
          console.error(e);
      }
  };

  const sectors = useMemo(() => [...new Set(galaxyData.map(s => s.sector))], [galaxyData]);
  const sectorColors = { 
    Technology: '#00ffff', Healthcare: '#ff00ff', Financial: '#ffff00', 
    Energy: '#ff8800', Consumer: '#00ff00', Industrial: '#8888ff' 
  };

  const traces = useMemo(() => {
    return sectors.map(sector => {
        const sectorData = galaxyData.filter(s => s.sector === sector);
        const base = {
            name: sector,
            text: sectorData.map(s => `${s.ticker}\n${s.name}`),
            hoverinfo: 'text',
            marker: {
                size: sectorData.map(s => Math.max(5, Math.log10(s.market_cap || 1e9) * (viewMode === '3D' ? 0.8 : 1.5))),
                color: sectorColors[sector] || '#ffffff',
                opacity: 0.8,
                line: { color: 'rgba(0,0,0,0.5)', width: 0.5 }
            }
        };

        if (viewMode === '3D') {
            return {
                ...base,
                type: 'scatter3d',
                mode: 'markers',
                x: sectorData.map(s => s.x),
                y: sectorData.map(s => s.y),
                z: sectorData.map(s => s.z),
            };
        }
        return {
            ...base,
            type: 'scatter',
            mode: 'markers',
            x: sectorData.map(s => s.x),
            y: sectorData.map(s => s.y),
        };
    });
  }, [galaxyData, sectors, viewMode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[800px] bg-[#000008] border border-terminal-blue/20 rounded-2xl overflow-hidden">
        <div className="flex flex-col items-center gap-6">
          <div className="w-16 h-16 border-4 border-terminal-blue/20 border-t-terminal-blue rounded-full animate-spin"></div>
          <div className="text-terminal-blue font-mono text-lg tracking-[0.2em] animate-pulse uppercase">Mapping_Market_Galaxy</div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-[800px] border border-terminal-blue/20 rounded-2xl overflow-hidden bg-[#000008] p-4 flex flex-col gap-4">
      <div className="flex-1 flex gap-4">
          <div className="flex-1 bg-black/60 rounded-xl overflow-hidden border border-white/5 relative group">
            <Plot
                data={traces}
                onClick={handlePointClick}
                layout={{
                    autosize: true,
                    margin: { t: 0, b: 0, l: 0, r: 0 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    showlegend: true,
                    legend: { font: { color: '#ccc', size: 10 }, bgcolor: 'rgba(0,0,0,0.5)', x: 0, y: 1 },
                    xaxis: { showgrid: false, zeroline: false, showticklabels: false },
                    yaxis: { showgrid: false, zeroline: false, showticklabels: false },
                    hovermode: 'closest',
                    scene: viewMode === '3D' ? {
                        xaxis: { visible: false },
                        yaxis: { visible: false },
                        zaxis: { visible: false },
                        camera: { eye: { x: 1.8, y: 1.8, z: 1.5 } }
                    } : undefined
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
            />
            
            <button 
              onClick={() => setViewMode(prev => prev === '2D' ? '3D' : '2D')}
              className="absolute top-4 right-4 px-3 py-1.5 bg-black/80 border border-white/10 rounded text-[10px] font-bold text-terminal-blue hover:border-terminal-blue/50 transition-all flex items-center gap-2"
            >
              {viewMode === '2D' ? <Maximize2 size={12} /> : <Minimize2 size={12} />}
              {viewMode} GALAXY
            </button>

            <div className="absolute bottom-4 left-4 pointer-events-none">
                <div className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                    Topological Clustering: Structural DNA Similarity (UMAP)
                </div>
            </div>
          </div>

          {selectedStock && (
            <div className="w-80 p-8 bg-black/90 backdrop-blur-2xl border border-terminal-blue/40 rounded-xl shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
              <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Target Identified</div>
              <h3 className="text-3xl font-black text-terminal-white uppercase tracking-tight mb-2">
                {selectedStock.ticker}
              </h3>
              <div className="text-sm font-mono text-terminal-blue mb-8 uppercase tracking-wider">
                  {selectedStock.sector} {'//'} {selectedStock.name}
              </div>
              
              <div className="flex-1 overflow-y-auto space-y-6 hide-scrollbar">
                  <div className="pt-4 border-t border-white/10">
                      <div className="text-[10px] text-gray-500 font-bold uppercase mb-4 tracking-widest">Structural DNA Matches</div>
                      <div className="space-y-3">
                          {similarStocks.map((s) => (
                            <div key={s.ticker} className="flex items-center justify-between p-3 rounded bg-white/5 border border-white/5 hover:border-terminal-blue/20 transition-all cursor-pointer">
                                <div className="flex flex-col">
                                    <span className="text-sm font-bold text-terminal-white">{s.ticker}</span>
                                    <span className="text-[9px] text-gray-500 uppercase">{s.sector}</span>
                                </div>
                                <div className="text-right flex flex-col items-end">
                                    <span className="text-[10px] font-mono font-bold text-terminal-blue">${(s.market_cap / 1e9).toFixed(1)}B</span>
                                </div>
                            </div>
                          ))}
                          {similarStocks.length === 0 && <div className="text-[10px] text-gray-600 font-mono italic animate-pulse">Scanning topological neighbors...</div>}
                      </div>
                  </div>
              </div>

              <button 
                  onClick={() => setSelectedStock(null)}
                  className="mt-8 w-full py-4 bg-terminal-blue/5 border border-terminal-blue/40 hover:bg-terminal-blue hover:text-black text-terminal-blue text-[10px] font-black uppercase transition-all tracking-widest rounded-lg"
              >
                  Reset Galaxy View
              </button>
            </div>
          )}
      </div>
    </div>
  );
}
