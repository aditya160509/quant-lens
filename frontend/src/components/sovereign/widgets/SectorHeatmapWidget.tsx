'use client';

/**
 * SECTOR HEATMAP WIDGET
 * Sector rotation visualization with performance colors
 */

import React, { useEffect, useState } from 'react';
import { WidgetConfig } from '@/lib/sovereignStore';
import { RefreshCw } from 'lucide-react';

interface SectorData {
  symbol: string;
  name: string;
  change_pct: number | null;
}

// Sector name mappings for display
const SECTOR_NAMES: Record<string, string> = {
  'XLK': 'Tech',
  'XLF': 'Finance',
  'XLV': 'Health',
  'XLE': 'Energy',
  'XLY': 'Discretionary',
  'XLP': 'Staples',
  'XLI': 'Industrials',
  'XLB': 'Materials',
  'XLU': 'Utilities',
  'XLRE': 'Real Estate',
  'XLC': 'Comms',
};

interface SectorHeatmapWidgetProps {
  config: WidgetConfig;
}

export default function SectorHeatmapWidget({ config }: SectorHeatmapWidgetProps) {
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch('/api/sovereign/tickers?category=us_sectors');
        const json = await res.json();
        
        if (json.status === 'ok' && json.data?.us_sectors) {
          setSectors(json.data.us_sectors.tickers);
        }
      } catch (error) {
        console.error('Error fetching sector data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  // Color scale from red (-5%) to green (+5%)
  const getColor = (pct: number | null): string => {
    if (pct === null) return 'bg-terminal-gray/30';
    
    const normalized = Math.max(-5, Math.min(5, pct)) / 5; // Clamp to [-1, 1]
    
    if (normalized >= 0) {
      const intensity = Math.floor(normalized * 255);
      return `rgb(0, ${100 + intensity * 0.6}, 0)`;
    } else {
      const intensity = Math.floor(-normalized * 255);
      return `rgb(${100 + intensity * 0.6}, 0, 0)`;
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <RefreshCw size={16} className="text-terminal-dim animate-spin" />
      </div>
    );
  }

  // Sort by performance
  const sortedSectors = [...sectors].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0));

  return (
    <div className="h-full p-2 overflow-auto">
      <div className="grid grid-cols-3 gap-1">
        {sortedSectors.map(sector => {
          const pct = sector.change_pct || 0;
          const isPositive = pct >= 0;
          
          return (
            <div
              key={sector.symbol}
              className="relative p-2 rounded border border-terminal-gray/20 hover:border-terminal-gray/40 transition-all cursor-pointer overflow-hidden"
              style={{ 
                background: `linear-gradient(135deg, ${getColor(pct)}40, ${getColor(pct)}20)`
              }}
            >
              <div className="text-[10px] font-mono text-terminal-text font-medium">
                {SECTOR_NAMES[sector.symbol] || sector.name}
              </div>
              <div className={`text-xs font-mono font-bold ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                {isPositive ? '+' : ''}{pct.toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
      
      {/* Legend */}
      <div className="mt-2 flex items-center justify-center gap-2 text-[9px] font-mono text-terminal-dim">
        <span>-5%</span>
        <div className="w-16 h-2 rounded bg-gradient-to-r from-red-600 via-terminal-gray to-green-600" />
        <span>+5%</span>
      </div>
    </div>
  );
}
