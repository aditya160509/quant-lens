'use client';

/**
 * GLOBAL MARKETS WIDGET
 * Grid display of global indices with sparklines
 */

import React, { useEffect, useState } from 'react';
import { WidgetConfig } from '@/lib/sovereignStore';
import { Globe, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';

interface MarketData {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
}

interface GlobalMarketsWidgetProps {
  config: WidgetConfig;
}

export default function GlobalMarketsWidget({ config }: GlobalMarketsWidgetProps) {
  const [markets, setMarkets] = useState<MarketData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch('/api/sovereign/tickers?category=global_markets');
        const json = await res.json();
        
        if (json.status === 'ok' && json.data?.global_markets) {
          setMarkets(json.data.global_markets.tickers);
        }
      } catch (error) {
        console.error('Error fetching global markets:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <RefreshCw size={16} className="text-terminal-dim animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full p-2 overflow-auto">
      <div className="grid grid-cols-2 gap-2">
        {markets.map(market => {
          const isPositive = (market.change_pct || 0) >= 0;
          return (
            <div
              key={market.symbol}
              className="p-3 bg-terminal-gray/10 hover:bg-terminal-gray/20 border border-terminal-gray/30 rounded-lg transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono text-terminal-dim uppercase">
                  {market.name}
                </span>
                {isPositive ? (
                  <TrendingUp size={12} className="text-terminal-green" />
                ) : (
                  <TrendingDown size={12} className="text-terminal-red" />
                )}
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-mono text-terminal-text">
                  {market.price?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || '-'}
                </span>
                <span className={`text-xs font-mono ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                  {market.change_pct !== null ? (isPositive ? '+' : '') + market.change_pct.toFixed(1) + '%' : '-'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
