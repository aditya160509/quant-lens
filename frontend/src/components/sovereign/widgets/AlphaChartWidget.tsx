'use client';

/**
 * ALPHA CHART WIDGET
 * The Hero Widget - Normalized Performance Chart
 * 
 * Features:
 * - Multi-ticker overlay
 * - Ratio/spread support (e.g., BTC-USD/GLD)
 * - Period selectors (1D to 10Y)
 * - Custom indicator overlays
 * - Channel synchronization
 */

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { createChart, IChartApi, ISeriesApi, LineStyle, ColorType } from 'lightweight-charts';
import { useSovereignStore, WidgetConfig, ChannelColor } from '@/lib/sovereignStore';
import { Plus, X, TrendingUp, Settings } from 'lucide-react';

// Predefined colors for chart lines
const LINE_COLORS = [
  '#ffd60a', // Yellow (primary)
  '#00d4ff', // Cyan
  '#00ff88', // Green
  '#ff2d55', // Red
  '#ff9500', // Orange
  '#a78bfa', // Purple
];

// Period options
const PERIODS = ['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', '5Y', '10Y'] as const;

interface AlphaChartWidgetProps {
  config: WidgetConfig;
}

export default function AlphaChartWidget({ config }: AlphaChartWidgetProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  
  const { channelTickers, chartPeriod, setChartPeriod, selectedTickers, addTicker, removeTicker } = useSovereignStore();
  
  const [localTickers, setLocalTickers] = useState<string[]>(config.settings?.tickers || ['SPY', 'QQQ']);
  const [newTickerInput, setNewTickerInput] = useState('');
  const [chartData, setChartData] = useState<Record<string, { time: string; value: number }[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [showAddTicker, setShowAddTicker] = useState(false);

  // Listen to channel broadcasts
  useEffect(() => {
    if (config.channel !== 'none') {
      const channelTicker = channelTickers[config.channel];
      if (channelTicker && !localTickers.includes(channelTicker)) {
        setLocalTickers(prev => [...prev, channelTicker]);
      }
    }
  }, [channelTickers, config.channel, localTickers]);

  // Fetch normalized returns data
  useEffect(() => {
    const fetchData = async () => {
      if (localTickers.length === 0) return;
      
      setIsLoading(true);
      try {
        const tickerParam = localTickers.join(',');
        const res = await fetch(`/api/sovereign/normalized-returns?tickers=${tickerParam}&period=${chartPeriod}`);
        const json = await res.json();
        
        if (json.status === 'ok' && json.data?.series) {
          const formattedData: Record<string, { time: string; value: number }[]> = {};
          
          Object.entries(json.data.series).forEach(([ticker, data]: [string, any]) => {
            if (data.dates && data.values) {
              formattedData[ticker] = data.dates.map((date: string, i: number) => ({
                time: date,
                value: data.values[i],
              }));
            }
          });
          
          setChartData(formattedData);
        }
      } catch (error) {
        console.error('Error fetching alpha chart data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, [localTickers, chartPeriod]);

  // Initialize and update chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart if not exists
    if (!chartRef.current) {
      chartRef.current = createChart(chartContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor: '#6b7280',
          fontSize: 10,
        },
        grid: {
          vertLines: { color: 'rgba(30, 39, 56, 0.5)' },
          horzLines: { color: 'rgba(30, 39, 56, 0.5)' },
        },
        crosshair: {
          mode: 1,
          vertLine: { color: '#ffd60a', style: LineStyle.Dashed, width: 1 },
          horzLine: { color: '#ffd60a', style: LineStyle.Dashed, width: 1 },
        },
        rightPriceScale: {
          borderColor: 'rgba(30, 39, 56, 0.5)',
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
          borderColor: 'rgba(30, 39, 56, 0.5)',
          timeVisible: true,
          secondsVisible: false,
        },
        handleScroll: { mouseWheel: true, pressedMouseMove: true },
        handleScale: { mouseWheel: true, pinch: true },
      });
    }

    // Clear old series
    seriesRefs.current.forEach((series) => {
      chartRef.current?.removeSeries(series);
    });
    seriesRefs.current.clear();

    // Add new series for each ticker
    Object.entries(chartData).forEach(([ticker, data], index) => {
      if (chartRef.current && data.length > 0) {
        // @ts-ignore - Lightweight charts v5 type compatibility
        const series = chartRef.current.addLineSeries({
          color: LINE_COLORS[index % LINE_COLORS.length],
          lineWidth: 2,
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 4,
          priceLineVisible: false,
          lastValueVisible: true,
          title: ticker,
        });
        series.setData(data as any);
        seriesRefs.current.set(ticker, series as any);
      }
    });

    // Fit content
    chartRef.current?.timeScale().fitContent();

    // Resize handler
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [chartData]);

  // Cleanup chart on unmount
  useEffect(() => {
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, []);

  // Add ticker handler
  const handleAddTicker = () => {
    const ticker = newTickerInput.toUpperCase().trim();
    if (ticker && !localTickers.includes(ticker)) {
      setLocalTickers(prev => [...prev, ticker]);
      addTicker(ticker);
    }
    setNewTickerInput('');
    setShowAddTicker(false);
  };

  // Remove ticker handler
  const handleRemoveTicker = (ticker: string) => {
    setLocalTickers(prev => prev.filter(t => t !== ticker));
  };

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="shrink-0 flex items-center justify-between px-3 py-2 border-b border-terminal-gray/30">
        {/* Period selectors */}
        <div className="flex items-center gap-1">
          {PERIODS.map(period => (
            <button
              key={period}
              onClick={() => setChartPeriod(period as any)}
              className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                chartPeriod === period
                  ? 'bg-terminal-yellow/20 text-terminal-yellow'
                  : 'text-terminal-dim hover:text-terminal-text hover:bg-terminal-gray/30'
              }`}
            >
              {period}
            </button>
          ))}
        </div>
        
        {/* Ticker tags */}
        <div className="flex items-center gap-1">
          {localTickers.map((ticker, i) => (
            <div
              key={ticker}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono"
              style={{ backgroundColor: `${LINE_COLORS[i % LINE_COLORS.length]}20`, color: LINE_COLORS[i % LINE_COLORS.length] }}
            >
              <span>{ticker}</span>
              <button
                onClick={() => handleRemoveTicker(ticker)}
                className="hover:opacity-70"
              >
                <X size={10} />
              </button>
            </div>
          ))}
          
          {showAddTicker ? (
            <div className="flex items-center gap-1">
              <input
                type="text"
                value={newTickerInput}
                onChange={(e) => setNewTickerInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddTicker()}
                placeholder="TICKER"
                className="w-16 px-2 py-0.5 bg-terminal-gray/30 border border-terminal-gray/50 rounded text-[10px] font-mono text-terminal-text placeholder:text-terminal-dim focus:outline-none focus:border-terminal-yellow/50"
                autoFocus
              />
              <button
                onClick={handleAddTicker}
                className="p-0.5 bg-terminal-yellow/20 text-terminal-yellow rounded hover:bg-terminal-yellow/30"
              >
                <Plus size={12} />
              </button>
              <button
                onClick={() => { setShowAddTicker(false); setNewTickerInput(''); }}
                className="p-0.5 text-terminal-dim hover:text-terminal-red"
              >
                <X size={12} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowAddTicker(true)}
              className="p-0.5 text-terminal-dim hover:text-terminal-yellow"
              title="Add ticker"
            >
              <Plus size={14} />
            </button>
          )}
        </div>
      </div>
      
      {/* Chart container */}
      <div className="flex-1 relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-terminal-darker/80 z-10">
            <div className="flex items-center gap-2 text-terminal-dim">
              <TrendingUp size={16} className="animate-pulse" />
              <span className="font-mono text-xs">Loading chart...</span>
            </div>
          </div>
        )}
        <div ref={chartContainerRef} className="w-full h-full" />
      </div>
      
      {/* Legend */}
      {Object.keys(chartData).length > 0 && (
        <div className="shrink-0 flex items-center gap-3 px-3 py-1.5 border-t border-terminal-gray/30">
          {Object.entries(chartData).map(([ticker, data], i) => {
            const lastValue = data[data.length - 1]?.value || 100;
            const change = lastValue - 100;
            const isPositive = change >= 0;
            
            return (
              <div key={ticker} className="flex items-center gap-2">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: LINE_COLORS[i % LINE_COLORS.length] }}
                />
                <span className="font-mono text-[10px] text-terminal-dim">{ticker}</span>
                <span className={`font-mono text-[10px] ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                  {isPositive ? '+' : ''}{change.toFixed(2)}%
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
