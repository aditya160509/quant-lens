'use client';

/**
 * 🛢️ COMMODITIES WIDGET
 * Oil, Gold, Silver, Gas, and other commodities
 */

import React, { useEffect, useState } from 'react';
import { WidgetConfig } from '@/lib/sovereignStore';
import { RefreshCw, Droplet } from 'lucide-react';

interface CommodityData {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
}

// No emojis allowed per user request
const COMMODITY_ICONS: Record<string, string> = {
  'CL=F': '',
  'GC=F': '',
  'SI=F': '',
  'NG=F': '',
  'HG=F': '',
  'ZC=F': '',
  'ZW=F': '',
  'ZS=F': '',
};

interface CommoditiesWidgetProps {
  config: WidgetConfig;
}

export default function CommoditiesWidget({ config }: CommoditiesWidgetProps) {
  const [commodities, setCommodities] = useState<CommodityData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch('/api/sovereign/tickers?category=commodities');
        const json = await res.json();
        
        if (json.status === 'ok' && json.data?.commodities) {
          setCommodities(json.data.commodities.tickers);
        }
      } catch (error) {
        console.error('Error fetching commodity data:', error);
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
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 border-b border-terminal-gray/30">
        <Droplet size={12} className="text-terminal-dim" />
        <span className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider">
          Commodities
        </span>
      </div>

      {/* Commodities list */}
      <div className="flex-1 overflow-auto">
        <div className="divide-y divide-terminal-gray/20">
          {commodities.map(commodity => {
            const isPositive = (commodity.change_pct || 0) >= 0;
            
            return (
              <div
                key={commodity.symbol}
                className="flex items-center justify-between px-3 py-2 hover:bg-terminal-gray/10 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <div>
                    <div className="text-xs font-mono text-terminal-text">{commodity.name}</div>
                    <div className="text-[9px] font-mono text-terminal-dim">{commodity.symbol}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-terminal-text">
                    {commodity.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '-'}
                  </div>
                  <div className={`text-[10px] font-mono ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                    {commodity.change_pct !== null ? (isPositive ? '+' : '') + commodity.change_pct.toFixed(1) + '%' : '-'}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
