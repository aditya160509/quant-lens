import React, { useEffect, useState } from "react";
import dynamic from 'next/dynamic';
import { fetchML2Liquidity } from "@/lib/api";

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function LiquidityCanyons2D({ universe, ticker, timeframe }) {
  const [liquidityData, setLiquidityData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Liquidity(universe, ticker, timeframe);
            if (!isMounted) return;
            setLiquidityData(data);
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
      <div className="flex items-center justify-center h-[600px] bg-black/40 border border-terminal-blue/20 rounded-xl">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-terminal-blue border-t-transparent rounded-full animate-spin"></div>
          <div className="text-terminal-blue font-mono animate-pulse uppercase">Mapping_Volume_Profile...</div>
        </div>
      </div>
    );
  }

  if (!liquidityData) return null;

  const profile = liquidityData.volume_profile || [];
  const prices = profile.map(b => b.price);
  const volumes = profile.map(b => b.volume);

  return (
    <div className="relative border border-terminal-blue/20 rounded-xl overflow-hidden bg-black/40 p-6 flex flex-col gap-6">
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 min-h-[500px] bg-black/60 border border-white/5 rounded-lg">
          <Plot
            data={[
              {
                y: prices,
                x: volumes,
                type: 'bar',
                orientation: 'h',
                marker: {
                  color: prices.map(p => {
                    if (Math.abs(p - liquidityData.poc) < 0.5) return '#ffff00';
                    if (p >= liquidityData.val && p <= liquidityData.vah) return '#00ff88';
                    return '#0088ff';
                  }),
                  opacity: 0.7
                },
                name: 'Volume at Price'
              },
              {
                y: [liquidityData.poc, liquidityData.poc],
                x: [0, Math.max(...volumes)],
                type: 'scatter',
                mode: 'lines',
                line: { color: '#ffff00', width: 2, dash: 'dash' },
                name: 'POC'
              }
            ]}
            layout={{
                autosize: true,
                margin: { t: 40, b: 40, l: 60, r: 20 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                showlegend: false,
                xaxis: {
                    gridcolor: 'rgba(255,255,255,0.05)',
                    tickfont: { size: 10, color: '#666' },
                    title: { text: 'VOLUME DENSITY', font: { size: 9, color: '#444' } }
                },
                yaxis: {
                    gridcolor: 'rgba(255,255,255,0.05)',
                    tickfont: { size: 10, color: '#666' },
                    title: { text: 'PRICE LEVEL ($)', font: { size: 9, color: '#444' } }
                }
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>

        <div className="lg:col-span-1 space-y-4">
           <div className="bg-black/80 border border-terminal-blue/30 p-8 rounded-lg shadow-xl flex flex-col h-full border-l-4 border-l-terminal-blue">
                <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Market Profile Analysis</div>
                <h3 className="text-2xl font-black text-white uppercase mb-6 tracking-tight">Liquidity Canyons</h3>
                
                <p className="text-xs text-terminal-blue/80 font-mono mb-8 leading-relaxed italic">
                    &quot;{liquidityData.resistance_path?.summary || "Analyzing orderflow imbalances..."}&quot;
                </p>

                <div className="space-y-4">
                    <div className="p-4 bg-white/5 rounded border border-white/10">
                        <div className="text-[10px] text-gray-500 uppercase font-bold mb-1">Point of Control (POC)</div>
                        <div className="text-2xl font-mono font-black text-terminal-yellow">${(liquidityData.poc || 0).toFixed(2)}</div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 bg-white/5 rounded border border-white/10">
                            <div className="text-[9px] text-gray-500 uppercase font-bold mb-1">Value Area High</div>
                            <div className="text-sm font-mono font-bold text-terminal-green">${(liquidityData.vah || 0).toFixed(2)}</div>
                        </div>
                        <div className="p-3 bg-white/5 rounded border border-white/10">
                            <div className="text-[9px] text-gray-500 uppercase font-bold mb-1">Value Area Low</div>
                            <div className="text-sm font-mono font-bold text-terminal-red">${(liquidityData.val || 0).toFixed(2)}</div>
                        </div>
                    </div>
                </div>

                <div className="mt-8 pt-6 border-t border-white/5">
                    <div className="text-[9px] text-terminal-blue font-bold uppercase mb-3">Liquidity Voids Detected</div>
                    <div className="flex flex-wrap gap-2">
                        {liquidityData.liquidity_voids?.map((v, i) => (
                            <span key={i} className="px-2 py-1 bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] font-mono rounded">
                                AREA_GAP @ ${v.price.toFixed(2)}
                            </span>
                        ))}
                    </div>
                </div>
           </div>
        </div>
      </div>
    </div>
  );
}
