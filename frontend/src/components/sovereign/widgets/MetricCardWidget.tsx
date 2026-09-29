'use client';

/**
 * METRIC CARD WIDGET
 * Single stat display with large value and change indicator
 */

import React, { useEffect, useState } from 'react';
import { useSovereignStore, WidgetConfig } from '@/lib/sovereignStore';
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';

interface MetricCardWidgetProps {
  config: WidgetConfig;
}

export default function MetricCardWidget({ config }: MetricCardWidgetProps) {
  const { channelTickers } = useSovereignStore();
  const [data, setData] = useState<{
    price: number | null;
    change: number | null;
    change_pct: number | null;
  }>({ price: null, change: null, change_pct: null });
  const [isLoading, setIsLoading] = useState(true);

  // Get ticker from settings or channel
  const ticker = config.settings?.ticker || 
    (config.channel !== 'none' ? channelTickers[config.channel] : null) || 
    'SPY';

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`/api/sovereign/tickers?category=volatility`);
        const json = await res.json();
        
        // Search all categories for the ticker
        for (const category of Object.values(json.data || {})) {
          const found = (category as any).tickers?.find((t: any) => t.symbol === ticker);
          if (found) {
            setData({
              price: found.price,
              change: found.change,
              change_pct: found.change_pct,
            });
            break;
          }
        }
      } catch (error) {
        console.error('Error fetching metric data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [ticker]);

  const isPositive = (data.change_pct || 0) >= 0;

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <RefreshCw size={16} className="text-terminal-dim animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col items-center justify-center p-4">
      {/* Ticker label */}
      <div className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider mb-1">
        {ticker}
      </div>
      
      {/* Main value */}
      <div className={`text-2xl font-mono font-bold ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
        {data.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '-'}
      </div>
      
      {/* Change indicator */}
      <div className={`flex items-center gap-1 mt-1 ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
        {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
        <span className="text-xs font-mono">
          {data.change_pct !== null ? (isPositive ? '+' : '') + data.change_pct.toFixed(2) + '%' : '-'}
        </span>
      </div>
    </div>
  );
}
