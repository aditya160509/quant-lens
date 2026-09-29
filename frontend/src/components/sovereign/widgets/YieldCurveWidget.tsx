'use client';

/**
 * YIELD CURVE WIDGET
 * Global bond yields display
 */

import React, { useEffect, useState, useRef } from 'react';
import { createChart, IChartApi, ColorType, LineStyle } from 'lightweight-charts';
import { WidgetConfig } from '@/lib/sovereignStore';
import { RefreshCw, Globe } from 'lucide-react';

interface YieldData {
  country: string;
  y5: number | null;
  y10: number | null;
  spread: number | null;
}

interface YieldCurveWidgetProps {
  config: WidgetConfig;
}

export default function YieldCurveWidget({ config }: YieldCurveWidgetProps) {
  const [yields, setYields] = useState<YieldData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table');

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch('/api/sovereign/global-yields');
        const json = await res.json();
        
        if (json.status === 'ok' && json.data) {
          setYields(json.data);
        }
      } catch (error) {
        console.error('Error fetching yield data:', error);
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

  // Sort by 10Y yield descending
  const sortedYields = [...yields].sort((a, b) => (b.y10 || 0) - (a.y10 || 0));

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-3 py-1.5 border-b border-terminal-gray/30">
        <div className="flex items-center gap-1.5">
          <Globe size={12} className="text-terminal-dim" />
          <span className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider">
            Global Sovereign Yields
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-[10px] font-mono">
          <thead className="sticky top-0 bg-terminal-dark/90">
            <tr className="text-terminal-dim border-b border-terminal-gray/30">
              <th className="text-left py-1.5 px-2 font-normal">Country</th>
              <th className="text-right py-1.5 px-2 font-normal">5Y</th>
              <th className="text-right py-1.5 px-2 font-normal">10Y</th>
              <th className="text-right py-1.5 px-2 font-normal">Spread</th>
            </tr>
          </thead>
          <tbody>
            {sortedYields.map(y => {
              const spreadPositive = (y.spread || 0) >= 0;
              return (
                <tr key={y.country} className="border-b border-terminal-gray/20 hover:bg-terminal-gray/10">
                  <td className="py-1.5 px-2 text-terminal-text">{y.country}</td>
                  <td className="py-1.5 px-2 text-right text-terminal-cyan">
                    {y.y5?.toFixed(2) || '-'}%
                  </td>
                  <td className="py-1.5 px-2 text-right text-terminal-yellow">
                    {y.y10?.toFixed(2) || '-'}%
                  </td>
                  <td className={`py-1.5 px-2 text-right ${spreadPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                    {y.spread !== null ? (spreadPositive ? '+' : '') + y.spread.toFixed(0) + 'bp' : '-'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="shrink-0 px-3 py-1.5 border-t border-terminal-gray/30">
        <div className="flex items-center justify-between text-[9px] font-mono text-terminal-dim">
          <span>5Y-10Y Spread</span>
          <span>Updated: {new Date().toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
}
