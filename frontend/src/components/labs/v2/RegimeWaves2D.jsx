import React, { useEffect, useState } from "react";
import dynamic from 'next/dynamic';
import { fetchML2Regime } from "@/lib/api";

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function RegimeWaves2D({ universe, ticker, timeframe }) {
  const [regimeData, setRegimeData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Regime(universe, ticker, timeframe);
            if (!isMounted) return;
            setRegimeData(data);
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
          <div className="text-terminal-green font-mono animate-pulse uppercase">Decomposing_Spectral_State...</div>
        </div>
      </div>
    );
  }

  if (!regimeData) return null;

  const spectralKeys = Object.keys(regimeData.spectral_summary || {});
  const spectralValues = Object.values(regimeData.spectral_summary || {});

  return (
    <div className="relative grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 border border-terminal-green/20 rounded-xl bg-black/40">
      
      {/* Left Panel: Primary Metrics */}
      <div className="lg:col-span-1 bg-black/60 p-6 border border-white/5 rounded-lg flex flex-col justify-between">
        <div>
          <div className="text-[10px] text-terminal-blue font-bold tracking-[0.2em] uppercase mb-2">Regime Intelligence</div>
          <h3 className="text-4xl font-black text-white uppercase mb-1 tracking-tight">
            {regimeData.regime || "STABLE"}
          </h3>
          <div className="text-xs font-mono text-terminal-green uppercase">TYPE: {regimeData.regime_type || "HMM_GAUSSIAN"}</div>
        </div>

        <div className="mt-12 space-y-8">
          <div>
            <div className="text-[10px] text-gray-500 font-bold uppercase mb-2">Phase Stability</div>
            <div className="flex items-end gap-3">
              <span className="text-5xl font-black font-mono text-white">{(regimeData.stability || 0).toFixed(1)}%</span>
              <span className={`text-xs font-bold uppercase mb-2 ${regimeData.stability > 70 ? 'text-terminal-green' : 'text-terminal-yellow'}`}>
                {regimeData.stability > 70 ? '[LOCKED]' : '[WAVERING]'}
              </span>
            </div>
            <div className="w-full h-1 bg-white/5 mt-3 rounded-full overflow-hidden">
               <div 
                 className="h-full bg-terminal-green transition-all duration-1000" 
                 style={{ width: `${regimeData.stability}%` }}
               ></div>
            </div>
          </div>

          <div className="p-4 bg-terminal-green/5 border border-terminal-green/10 rounded">
            <div className="text-[9px] text-terminal-green font-bold uppercase mb-2">Regime Diagnosis</div>
            <p className="text-[11px] text-terminal-green/70 font-mono leading-relaxed">
               Current spectral density indicates {regimeData.regime === 'Bull' ? 'positive momentum convergence' : regimeData.regime === 'Bear' ? 'structural volatility decay' : 'mean-reverting equilibrium'}. 
               Entropy {regimeData.stability < 50 ? 'is increasing' : 'remains suppressed'}.
            </p>
          </div>
        </div>
      </div>

      {/* Right Panel: Spectral Density Plot */}
      <div className="lg:col-span-2 bg-black/60 border border-white/5 rounded-lg overflow-hidden flex flex-col">
        <div className="p-4 border-b border-white/5 flex justify-between items-center bg-black/40">
           <span className="text-[10px] font-black text-terminal-dim uppercase tracking-widest leading-relaxed">Spectral Energy Distribution</span>
           <span className="text-[8px] font-mono text-terminal-green uppercase">Fast Fourier Transform Source</span>
        </div>
        <div className="flex-1 min-h-[400px]">
          <Plot
            data={[
              {
                x: spectralKeys,
                y: spectralValues,
                type: 'bar',
                marker: {
                  color: spectralValues.map(v => v > 50 ? '#00ff88' : '#00aaff'),
                  line: { width: 0 }
                },
                hoverinfo: 'x+y',
                name: 'Spectral Density'
              },
              {
                x: spectralKeys,
                y: spectralValues,
                type: 'scatter',
                mode: 'lines+markers',
                line: { shape: 'spline', color: '#ffffff', width: 1 },
                marker: { size: 4, color: '#ffffff' },
                hoverinfo: 'none'
              }
            ]}
            layout={{
              autosize: true,
              margin: { t: 40, b: 40, l: 50, r: 20 },
              paper_bgcolor: 'rgba(0,0,0,0)',
              plot_bgcolor: 'rgba(0,0,0,0)',
              showlegend: false,
              xaxis: {
                gridcolor: 'rgba(255,255,255,0.05)',
                tickfont: { size: 10, color: '#666', family: 'JetBrains Mono, monospace' },
                title: { text: 'FREQUENCY COMPONENTS', font: { size: 9, color: '#444' } }
              },
              yaxis: {
                gridcolor: 'rgba(255,255,255,0.05)',
                tickfont: { size: 10, color: '#666', family: 'JetBrains Mono, monospace' },
                title: { text: 'ENERGY INTENSITY', font: { size: 9, color: '#444' } }
              }
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </div>
    </div>
  );
}
