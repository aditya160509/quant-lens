import React, { useState, useEffect, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Maximize2, Minimize2 } from 'lucide-react';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const THEME = {
    yellow: "#ffcc00",
    blue: "#00d4ff",
    green: "#00ff88",
    red: "#ff3333",
    purple: "#bf5af2",
    gray: "rgba(255, 255, 255, 0.1)",
};

/**
 * DimensionalLoadingMap v3.0 (Supports 2D/3D toggle)
 */
export default function Sequential3DLoadingMap({ mode = 'structural', data, loading }) {
    const [viewMode, setViewMode] = useState('2D'); // '2D' or '3D'
    const [animation, setAnimation] = useState({ key: '', visibleCount: 0, complete: false });

    const getItemsByMode = useCallback(() => {
        if (!data) return [];
        if (mode === 'structural') return data.matrix_data || [];
        if (mode === 'regime_helix') return data.historical_dispersion || [];
        if (mode === 'signal_terrain') return data.alpha_oracle || [];
        return [];
    }, [data, mode]);

    const items = getItemsByMode();
    const animationKey = useMemo(() => JSON.stringify([
        mode,
        items.length,
        items[0] ?? null,
        items.at(-1) ?? null,
    ]), [items, mode]);
    const visibleCount = !loading && animation.key === animationKey ? animation.visibleCount : 0;
    const animationComplete = !loading && animation.key === animationKey && animation.complete;

    useEffect(() => {
        if (loading || items.length === 0) return undefined;

        let nextVisibleCount = 0;
        const step = Math.max(1, Math.floor(items.length / 40));
        const interval = window.setInterval(() => {
            nextVisibleCount = Math.min(items.length, nextVisibleCount + step);
            const complete = nextVisibleCount >= items.length;
            setAnimation({ key: animationKey, visibleCount: nextVisibleCount, complete });
            if (complete) window.clearInterval(interval);
        }, 30);

        return () => window.clearInterval(interval);
    }, [animationKey, items.length, loading]);

    const plotData = useMemo(() => {
        const visibleItems = items.slice(0, visibleCount);
        
        if (mode === 'structural') {
            if (viewMode === '3D') {
                return [
                    {
                        type: 'scatter3d',
                        mode: 'markers',
                        x: visibleItems.map(p => p.pc1),
                        y: visibleItems.map(p => p.pc2),
                        z: visibleItems.map(p => p.pc3 || 0),
                        text: visibleItems.map(p => p.ticker),
                        marker: {
                            size: 4 + (viewMode === '3D' ? 2 : 5),
                            color: visibleItems.map(p => p.loading_strength),
                            colorscale: 'Viridis',
                            opacity: 0.8,
                            line: { color: 'rgba(255,255,255,0.2)', width: 0.5 }
                        }
                    },
                    visibleCount > 10 ? {
                        type: 'mesh3d',
                        x: visibleItems.map(p => p.pc1),
                        y: visibleItems.map(p => p.pc2),
                        z: visibleItems.map(p => (p.pc3 || 0) * 0.5),
                        opacity: 0.1,
                        color: THEME.blue,
                    } : null
                ].filter(Boolean);
            } else {
                return [{
                    type: 'scatter',
                    mode: 'markers',
                    x: visibleItems.map(p => p.pc1),
                    y: visibleItems.map(p => p.pc2),
                    text: visibleItems.map(p => p.ticker),
                    marker: {
                        size: visibleItems.map(p => 10 + (p.loading_strength * 12)),
                        color: visibleItems.map(p => p.loading_strength),
                        colorscale: 'Viridis',
                        opacity: 0.8,
                        line: { color: 'rgba(255,255,255,0.2)', width: 1 }
                    }
                }];
            }
        }

        if (mode === 'regime_helix') {
            const x = data.historical_entropy || [];
            const y = data.historical_dispersion || [];
            const vX = x.slice(0, visibleCount);
            const vY = y.slice(0, visibleCount);

            if (viewMode === '3D') {
                const z = vX.map((_, i) => i);
                return [
                    {
                        type: 'scatter3d',
                        mode: 'lines+markers',
                        x: vX,
                        y: vY,
                        z: z,
                        line: { color: THEME.blue, width: 4 },
                        marker: { size: 2, color: vX.map(v => v > 0.5 ? THEME.red : THEME.green) }
                    }
                ];
            } else {
                return [
                    {
                        type: 'scatter',
                        mode: 'lines+markers',
                        x: vX,
                        y: vY,
                        line: { color: 'rgba(0, 212, 255, 0.4)', width: 2, shape: 'spline' },
                        marker: { size: 6, color: vX.map(v => v > 0.5 ? THEME.red : THEME.green) }
                    }
                ];
            }
        }

        if (mode === 'signal_terrain') {
            if (viewMode === '3D') {
                const x = visibleItems.map(p => p.ai_score);
                const y = visibleItems.map(p => p.confidence);
                const z = visibleItems.map((_, i) => i);
                return [
                    {
                        type: 'mesh3d',
                        x, y, z,
                        opacity: 0.4,
                        intensity: y,
                        colorscale: 'RdYlGn'
                    },
                    {
                        type: 'scatter3d',
                        mode: 'markers',
                        x, y, z,
                        marker: { size: 4, color: x, colorscale: 'RdYlGn' }
                    }
                ];
            } else {
                return [{
                    type: 'scatter',
                    mode: 'markers',
                    x: visibleItems.map(p => p.ai_score),
                    y: visibleItems.map(p => p.confidence),
                    text: visibleItems.map(p => p.ticker),
                    marker: {
                        size: 14,
                        color: visibleItems.map(p => p.ai_score),
                        colorscale: 'RdYlGn',
                        line: { color: '#fff', width: 1 }
                    }
                }];
            }
        }

        return [];
    }, [visibleCount, data, items, mode, viewMode]);

    const getLayout = () => {
        if (viewMode === '3D') {
            return {
                margin: { t: 0, r: 0, b: 0, l: 0 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                autosize: true,
                showlegend: false,
                scene: {
                    xaxis: { title: { text: mode === 'structural' ? 'PC1' : 'SCORE', font: { color: '#444' } }, gridcolor: THEME.gray },
                    yaxis: { title: { text: mode === 'structural' ? 'PC2' : 'CONFIDENCE', font: { color: '#444' } }, gridcolor: THEME.gray },
                    zaxis: { title: { text: mode === 'structural' ? 'PC3' : 'INDEX', font: { color: '#444' } }, gridcolor: THEME.gray },
                    camera: { eye: { x: 1.5, y: 1.5, z: 1.2 } }
                }
            };
        }

        const layout = {
            margin: { t: 40, r: 40, b: 60, l: 60 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'rgba(0,0,0,0.1)',
            autosize: true,
            showlegend: false,
            xaxis: { gridcolor: 'rgba(255,255,255,0.05)', tickfont: { color: '#666' } },
            yaxis: { gridcolor: 'rgba(255,255,255,0.05)', tickfont: { color: '#666' } }
        };

        if (mode === 'structural') {
            layout.xaxis.title = { text: 'EIGEN_PC1', font: { size: 9, color: '#444' } };
            layout.yaxis.title = { text: 'EIGEN_PC2', font: { size: 9, color: '#444' } };
        } else if (mode === 'signal_terrain') {
            layout.xaxis.title = { text: 'AI_SCORE', font: { size: 9, color: '#444' } };
            layout.yaxis.title = { text: 'CONFIDENCE', font: { size: 9, color: '#444' } };
        }

        return layout;
    };

    return (
        <div className="w-full h-full relative group">
            <Plot
                data={plotData}
                layout={getLayout()}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
            />
            
            {/* HUD Status */}
            <div className="absolute top-4 left-6 flex flex-col gap-1 pointer-events-none">
                <div className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${animationComplete ? 'bg-terminal-green shadow-[0_0_8px_#00ff88]' : 'bg-terminal-yellow animate-pulse'}`} />
                    <span className="text-[10px] font-black text-terminal-white uppercase tracking-[0.2em] font-mono">
                        {mode.replace('_', ' ')}: {animationComplete ? 'CONVERGED' : `STREAMING_${visibleCount}`}
                    </span>
                </div>
            </div>

            {/* Dimensional Toggle */}
            <div className="absolute top-4 right-6 flex gap-2">
                <button 
                  onClick={() => setViewMode(prev => prev === '2D' ? '3D' : '2D')}
                  className="px-3 py-1.5 bg-black/60 border border-white/10 rounded-md text-[10px] font-bold text-terminal-blue uppercase tracking-widest hover:border-terminal-blue/50 transition-all flex items-center gap-2"
                >
                    {viewMode === '2D' ? <Maximize2 size={12} /> : <Minimize2 size={12} />}
                    {viewMode} PROJECT
                </button>
            </div>
        </div>
    );
}
