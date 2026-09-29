'use client';

/**
 * STUDIO CHART WIDGET
 * High-performance OHLCV chart powered by the custom Canvas Engine.
 */

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { ChartProvider, useChart } from '../../chart_engine/state/ChartContext';
import ChartCanvas from '../../chart_engine/ChartCanvas';
import { getAllIndicators } from '../../chart_engine/IndicatorEngine/registry';
import { useSovereignStore, WidgetConfig } from '@/lib/sovereignStore';
import { RefreshCw, Maximize2, Settings, ListPlus, Search, Check } from 'lucide-react';


interface StudioChartWidgetProps {
  config: WidgetConfig;
}

function ChartInner({ config, ticker }: { config: WidgetConfig; ticker: string }) {
  const { state, dispatch, setSymbol, addIndicator, removeIndicator } = useChart();
  const [isLoading, setIsLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 300 });
  const [showIndicators, setShowIndicators] = useState(false);
  const [indicatorSearch, setIndicatorSearch] = useState('');

  const indicators = useMemo(() => getAllIndicators(), []);
  const filteredIndicators = indicators.filter(ind => 
    ind.name.toLowerCase().includes(indicatorSearch.toLowerCase()) ||
    ind.shortName.toLowerCase().includes(indicatorSearch.toLowerCase())
  );


  // Update symbol in chart state when it changes in widget
  useEffect(() => {
    if (ticker) {
      setSymbol(ticker);
    }
  }, [ticker, setSymbol]);

  // Fetch OHLCV data for the canvas
  useEffect(() => {
    const fetchData = async () => {
      if (!ticker) return;
      setIsLoading(true);
      try {
        const res = await fetch(`/api/sovereign/ohlcv/${ticker}?period=1Y`);
        const json = await res.json();
        
        if (json.status === 'ok' && json.data) {
          // Map backend 'time' (string) to 'timestamp' (number) for the engine
          const mappedBars = json.data.map((bar: any) => ({
            ...bar,
            timestamp: new Date(bar.time).getTime()
          }));

          // Dispatch data to chart state
          dispatch({ 
            type: 'SET_DATA', 
            payload: { 
              bars: mappedBars, 
              symbol: ticker, 
              timeframe: '1d',
              session: {
                timezone: 'UTC',
                regularStart: '09:30',
                regularEnd: '16:00'
              }
            } 
          });
        }

      } catch (error) {
        console.error('Error fetching studio chart data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [ticker, dispatch]);

  // Resize handling
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="w-full h-full relative bg-terminal-black overflow-hidden flex flex-col">
      {/* Widget Toolbar (Inside Inner to access ChartContext) */}
      <div className="shrink-0 h-9 flex items-center justify-between px-2 bg-terminal-black/40 border-b border-terminal-gray/20">
        <div className="flex items-center gap-1">
          <button className="px-2 py-1 text-[10px] font-mono text-terminal-dim hover:text-terminal-text hover:bg-terminal-gray/20 rounded">
            1D
          </button>
          <div className="w-px h-3 bg-terminal-gray/30 mx-1" />
          
          <div className="relative">
            <button 
              onClick={() => setShowIndicators(!showIndicators)}
              className={`flex items-center gap-1 px-2 py-1 text-[10px] font-mono rounded transition-colors ${
                showIndicators ? 'bg-terminal-yellow/20 text-terminal-yellow' : 'text-terminal-yellow hover:bg-terminal-yellow/10'
              }`}
            >
              <ListPlus size={10} />
              Indicators
            </button>

            {showIndicators && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-terminal-dark border border-terminal-gray rounded-lg shadow-xl z-[60]">
                <div className="p-2 border-b border-terminal-gray/30">
                  <div className="relative">
                    <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-terminal-dim" />
                    <input
                      type="text"
                      placeholder="Search indicators..."
                      value={indicatorSearch}
                      onChange={(e) => setIndicatorSearch(e.target.value)}
                      className="w-full bg-terminal-black/50 border border-terminal-gray/30 rounded pl-7 pr-2 py-1 text-xs font-mono text-terminal-text focus:outline-none focus:border-terminal-yellow/50"
                      autoFocus
                    />
                  </div>
                </div>
                <div className="max-h-60 overflow-y-auto p-1">
                  {filteredIndicators.map(ind => {
                    const isActive = state.indicators.some(i => i.id === ind.id);
                    return (
                      <button
                        key={ind.id}
                        onClick={() => {
                          if (isActive) removeIndicator(ind.id);
                          else addIndicator({ 
                            id: ind.id, 
                            type: ind.id,
                            params: ind.defaultParams,
                            placement: ind.placement,
                            visible: true
                          });

                          setShowIndicators(false);
                        }}
                        className="w-full flex items-center justify-between px-3 py-2 rounded hover:bg-terminal-gray/10 text-left transition-colors"
                      >
                        <div className="flex flex-col">
                          <span className="text-[10px] font-mono text-terminal-text">{ind.name}</span>
                          <span className="text-[9px] font-mono text-terminal-dim">{ind.placement}</span>
                        </div>
                        {isActive && <Check size={10} className="text-terminal-yellow" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Settings size={12} className="text-terminal-dim cursor-pointer hover:text-terminal-text" />
          <Maximize2 size={12} className="text-terminal-dim cursor-pointer hover:text-terminal-text" />
        </div>
      </div>

      <div className="flex-1 relative">
        {isLoading && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-terminal-black/50 backdrop-blur-sm">
            <RefreshCw size={24} className="text-terminal-yellow animate-spin" />
          </div>
        )}
        
        <ChartCanvas 
          width={dimensions.width} 
          height={dimensions.height - 36} // Subtract toolbar height
        />

        {/* Ticker Overlay */}
        <div className="absolute top-2 left-3 z-10 pointer-events-none">
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-display font-bold text-terminal-text tracking-tighter opacity-80">{ticker}</span>
            <span className="text-[10px] font-mono text-terminal-dim uppercase">D</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function StudioChartWidget({ config }: StudioChartWidgetProps) {
  const { channelTickers } = useSovereignStore();
  
  // Get ticker from channel or settings
  const ticker = config.channel !== 'none' 
    ? channelTickers[config.channel] 
    : config.settings?.ticker || 'AAPL';

  return (
    <div className="h-full flex flex-col">
      {/* Chart Surface */}
      <div className="flex-1 overflow-hidden">
        <ChartProvider initialSymbol={ticker}>
          <ChartInner config={config} ticker={ticker} />
        </ChartProvider>
      </div>
    </div>
  );
}

