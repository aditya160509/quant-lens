'use client';

/**
 * TICKER TABLE WIDGET
 * Displays ticker prices with change % - similar to Koyfin equity panels
 */

import React, { useEffect, useState } from 'react';
import { useSovereignStore, WidgetConfig, ChannelColor } from '@/lib/sovereignStore';
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';

interface TickerData {
  symbol: string;
  name: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
}

interface CategoryData {
  name: string;
  tickers: TickerData[];
}

const CATEGORIES = ['us_equity', 'us_sectors', 'fixed_income', 'global_markets', 'india_equity'];

interface TickerTableWidgetProps {
  config: WidgetConfig;
}

export default function TickerTableWidget({ config }: TickerTableWidgetProps) {
  const { broadcastToChannel } = useSovereignStore();
  const [data, setData] = useState<Record<string, CategoryData>>({});
  const [activeCategory, setActiveCategory] = useState(config.settings?.category || 'us_equity');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`/api/sovereign/tickers`);
        const json = await res.json();
        if (json.status === 'ok') {
          setData(json.data);
        }
      } catch (error) {
        console.error('Error fetching ticker data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleTickerClick = (symbol: string) => {
    if (config.channel !== 'none') {
      broadcastToChannel(config.channel, symbol);
    }
  };

  const categoryData = data[activeCategory];

  return (
    <div className="h-full flex flex-col">
      {/* Category tabs */}
      <div className="shrink-0 flex items-center gap-1 px-2 py-1.5 border-b border-terminal-gray/30 overflow-x-auto">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-2 py-0.5 rounded text-[9px] font-mono whitespace-nowrap transition-colors ${
              activeCategory === cat
                ? 'bg-terminal-yellow/20 text-terminal-yellow'
                : 'text-terminal-dim hover:text-terminal-text hover:bg-terminal-gray/30'
            }`}
          >
            {cat.replace('_', ' ').toUpperCase()}
          </button>
        ))}
      </div>
      
      {/* Table content */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <RefreshCw size={16} className="text-terminal-dim animate-spin" />
          </div>
        ) : !categoryData ? (
          <div className="flex items-center justify-center h-full text-terminal-dim text-xs">
            No data available
          </div>
        ) : (
          <table className="w-full text-[10px] font-mono">
            <thead className="sticky top-0 bg-terminal-dark/90">
              <tr className="text-terminal-dim border-b border-terminal-gray/30">
                <th className="text-left py-1.5 px-2 font-normal">Symbol</th>
                <th className="text-right py-1.5 px-2 font-normal">Price</th>
                <th className="text-right py-1.5 px-2 font-normal">Chg</th>
                <th className="text-right py-1.5 px-2 font-normal">%</th>
              </tr>
            </thead>
            <tbody>
              {categoryData.tickers.map((ticker, i) => {
                const isPositive = (ticker.change_pct || 0) >= 0;
                return (
                  <tr
                    key={ticker.symbol}
                    onClick={() => handleTickerClick(ticker.symbol)}
                    className="border-b border-terminal-gray/20 hover:bg-terminal-gray/20 cursor-pointer transition-colors"
                  >
                    <td className="py-1.5 px-2">
                      <div className="flex items-center gap-1.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${isPositive ? 'bg-terminal-green' : 'bg-terminal-red'}`} />
                        <span className="text-terminal-text">{ticker.name}</span>
                      </div>
                    </td>
                    <td className="text-right py-1.5 px-2 text-terminal-text">
                      {ticker.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '-'}
                    </td>
                    <td className={`text-right py-1.5 px-2 ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {ticker.change !== null ? (isPositive ? '+' : '') + ticker.change.toFixed(2) : '-'}
                    </td>
                    <td className={`text-right py-1.5 px-2 ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {ticker.change_pct !== null ? (isPositive ? '+' : '') + ticker.change_pct.toFixed(1) + '%' : '-'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
