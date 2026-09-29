import React, { useEffect, useState } from "react";
import dynamic from 'next/dynamic';
import { fetchML2Valuation } from "@/lib/api";

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function Valuation2D({ universe, ticker, timeframe }) {
  const [valuationData, setValuationData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Valuation(universe, ticker, timeframe);
            if (!isMounted) return;
            setValuationData(data);
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
      <div className="flex items-center justify-center h-[600px] bg-black/40 border border-terminal-green/20 rounded-xl">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-terminal-green border-t-transparent rounded-full animate-spin"></div>
          <div className="text-terminal-green font-mono animate-pulse uppercase">Simulating_Intrinsic_Warp...</div>
        </div>
      </div>
    );
  }

  if (!valuationData) return null;

  const surface = valuationData.surface_grid || { values: [[]], revenue_growth: [], wacc: [] };

  return (
    <div className="relative border border-terminal-green/20 rounded-xl overflow-hidden bg-black/40 p-6 flex flex-col gap-6">
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 min-h-[500px] bg-black/60 border border-white/5 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-white/5 flex justify-between items-center bg-black/40">
             <span className="text-[10px] font-black text-terminal-dim uppercase tracking-widest leading-relaxed">Sensitivity Horizon: Monte Carlo DCF</span>
             <span className="text-[8px] font-mono text-terminal-green uppercase tracking-widest leading-relaxed">Z-Axis: Price Pivot</span>
          </div>
          <Plot
            data={[
              {
                z: surface.values,
                x: surface.revenue_growth,
                y: surface.wacc,
                type: 'heatmap',
                colorscale: [
                    [0, 'rgba(255, 50, 50, 0.8)'],
                    [0.5, 'rgba(10, 10, 10, 0.5)'],
                    [1, 'rgba(0, 255, 136, 0.8)']
                ],
                showscale: true,
                colorbar: {
                    tickfont: { color: '#666', size: 9 },
                    thickness: 10
                }
              }
            ]}
            layout={{
                autosize: true,
                margin: { t: 30, b: 60, l: 60, r: 20 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: {
                    title: { text: 'REVENUE GROWTH (%)', font: { size: 9, color: '#444' } },
                    gridcolor: 'rgba(255,255,255,0.05)',
                    tickfont: { size: 10, color: '#666' }
                },
                yaxis: {
                    title: { text: 'WACC (%)', font: { size: 9, color: '#444' } },
                    gridcolor: 'rgba(255,255,255,0.05)',
                    tickfont: { size: 10, color: '#666' }
                }
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>

        <div className="lg:col-span-1 space-y-4">
           <div className="bg-black/80 border border-terminal-green/30 p-8 rounded-lg shadow-xl flex flex-col h-full border-r-4 border-r-terminal-green">
                <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Valuation Summary</div>
                <h3 className="text-3xl font-black text-white uppercase mb-4 tracking-tight">DCF Surface</h3>
                
                <div className={`mb-8 inline-block px-4 py-2 rounded font-mono font-bold text-lg ${(valuationData.upside || 0) > 0 ? 'bg-terminal-green/20 text-terminal-green' : 'bg-red-500/20 text-red-500'}`}>
                    {(valuationData.upside || 0) > 0 ? '+' : ''}{(valuationData.upside || 0).toFixed(1)}% UPSIDE
                </div>

                <div className="space-y-4">
                    <div className="p-4 bg-white/5 rounded-xl border border-white/5">
                        <div className="text-[10px] text-gray-500 font-bold uppercase mb-1">Current Price</div>
                        <div className="text-2xl font-mono font-black text-white">${(valuationData.current_price || 0).toFixed(2)}</div>
                    </div>
                    <div className="p-4 bg-terminal-green/5 rounded-xl border border-terminal-green/20">
                        <div className="text-[10px] text-terminal-green font-bold uppercase mb-1">Intrinsic (Median)</div>
                        <div className="text-2xl font-mono font-black text-terminal-green">${(valuationData.median_value || 0).toFixed(2)}</div>
                    </div>
                </div>

                <div className="mt-8 space-y-3">
                    <div className="flex justify-between items-center text-[10px] font-mono border-b border-terminal-gray/20 pb-2">
                        <span className="text-gray-500 uppercase tracking-widest leading-relaxed">CONSERVATIVE (P25)</span>
                        <span className="text-white">${valuationData.p25_value?.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-mono border-b border-terminal-gray/20 pb-2">
                        <span className="text-gray-500 uppercase tracking-widest leading-relaxed">AGGRESSIVE (P75)</span>
                        <span className="text-white">${valuationData.p75_value?.toFixed(2)}</span>
                    </div>
                </div>

                <div className="mt-auto pt-6 text-[9px] text-gray-600 font-mono italic leading-relaxed">
                    * Simulation uses 10,000 recursive iterations across the growth/discount manifold.
                </div>
           </div>
        </div>
      </div>
    </div>
  );
}
