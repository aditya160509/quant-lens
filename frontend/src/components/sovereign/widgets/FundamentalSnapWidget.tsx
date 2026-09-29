'use client';

/**
 * FUNDAMENTAL SNAPSHOT WIDGET
 * P/E, P/B, ROE and other fundamentals for selected ticker
 */

import React, { useEffect, useState } from 'react';
import { useSovereignStore, WidgetConfig } from '@/lib/sovereignStore';
import { RefreshCw, FileText } from 'lucide-react';

interface FundamentalData {
  ticker: string;
  pe_ratio: number | null;
  pb_ratio: number | null;
  ps_ratio: number | null;
  roe: number | null;
  roa: number | null;
  dividend_yield: number | null;
  market_cap: number | null;
  revenue_growth: number | null;
  earnings_growth: number | null;
}

interface FundamentalSnapWidgetProps {
  config: WidgetConfig;
}

export default function FundamentalSnapWidget({ config }: FundamentalSnapWidgetProps) {
  const { channelTickers } = useSovereignStore();
  const [data, setData] = useState<FundamentalData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Get ticker from channel or settings
  const ticker = config.channel !== 'none' 
    ? channelTickers[config.channel] 
    : config.settings?.ticker || 'AAPL';

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`/api/sovereign/fundamentals/${ticker}`);
        const json = await res.json();
        
        if (json.status === 'ok' && json.data) {
          setData(json.data);
        }
      } catch (error) {
        console.error('Error fetching fundamental data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [ticker]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <RefreshCw size={16} className="text-terminal-dim animate-spin" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-full flex items-center justify-center text-terminal-dim text-xs">
        No fundamental data available
      </div>
    );
  }

  const formatValue = (value: number | null, suffix: string = '', decimals: number = 2): string => {
    if (value === null || isNaN(value)) return '-';
    return value.toFixed(decimals) + suffix;
  };

  const formatMarketCap = (value: number | null): string => {
    if (value === null) return '-';
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    return `$${value.toFixed(0)}`;
  };

  const metrics = [
    { label: 'P/E', value: formatValue(data.pe_ratio, 'x', 1), color: 'text-terminal-cyan' },
    { label: 'P/B', value: formatValue(data.pb_ratio, 'x', 1), color: 'text-terminal-cyan' },
    { label: 'P/S', value: formatValue(data.ps_ratio, 'x', 1), color: 'text-terminal-cyan' },
    { label: 'ROE', value: formatValue(data.roe, '%', 1), color: data.roe && data.roe > 15 ? 'text-terminal-green' : 'text-terminal-text' },
    { label: 'ROA', value: formatValue(data.roa, '%', 1), color: data.roa && data.roa > 10 ? 'text-terminal-green' : 'text-terminal-text' },
    { label: 'Div Yield', value: formatValue(data.dividend_yield, '%', 2), color: 'text-terminal-yellow' },
    { label: 'Mkt Cap', value: formatMarketCap(data.market_cap), color: 'text-terminal-text' },
    { label: 'Rev Growth', value: formatValue(data.revenue_growth, '%', 1), color: data.revenue_growth && data.revenue_growth > 0 ? 'text-terminal-green' : 'text-terminal-red' },
    { label: 'EPS Growth', value: formatValue(data.earnings_growth, '%', 1), color: data.earnings_growth && data.earnings_growth > 0 ? 'text-terminal-green' : 'text-terminal-red' },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-terminal-gray/30">
        <FileText size={12} className="text-terminal-dim" />
        <span className="text-sm font-mono font-bold text-terminal-yellow">{ticker}</span>
        <span className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider">
          Fundamentals
        </span>
      </div>

      {/* Metrics grid */}
      <div className="flex-1 p-2 overflow-auto">
        <div className="grid grid-cols-3 gap-2">
          {metrics.map(metric => (
            <div
              key={metric.label}
              className="p-2 bg-terminal-gray/10 rounded border border-terminal-gray/20"
            >
              <div className="text-[9px] font-mono text-terminal-dim uppercase tracking-wider mb-0.5">
                {metric.label}
              </div>
              <div className={`text-sm font-mono font-medium ${metric.color}`}>
                {metric.value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
