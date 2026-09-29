'use client';

/**
 * FACTOR PULSE WIDGET
 * Value/Growth/Momentum factor matrix by size
 */

import React, { useEffect, useState } from 'react';
import { WidgetConfig } from '@/lib/sovereignStore';
import { RefreshCw, Zap } from 'lucide-react';

interface FactorData {
  factor: string;
  size: string;
  return_1m: number | null;
  return_3m: number | null;
  return_ytd: number | null;
}

interface FactorPulseWidgetProps {
  config: WidgetConfig;
}

export default function FactorPulseWidget({ config }: FactorPulseWidgetProps) {
  const [factors, setFactors] = useState<FactorData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeMetric, setActiveMetric] = useState<'return_1m' | 'return_3m' | 'return_ytd'>('return_1m');

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch('/api/sovereign/factors');
        const json = await res.json();
        
        if (json.status === 'ok' && json.data) {
          setFactors(json.data);
        }
      } catch (error) {
        console.error('Error fetching factor data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const getCellColor = (value: number | null): string => {
    if (value === null) return 'bg-terminal-gray/20';
    const normalized = Math.max(-10, Math.min(10, value)) / 10;
    if (normalized >= 0) {
      return `bg-green-500/${Math.floor(20 + normalized * 30)}`;
    } else {
      return `bg-red-500/${Math.floor(20 + (-normalized) * 30)}`;
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <RefreshCw size={16} className="text-terminal-dim animate-spin" />
      </div>
    );
  }

  // Group by size
  const sizes = ['Large', 'Mid', 'Small'];
  const factorTypes = ['Value', 'Growth', 'Momentum'];

  return (
    <div className="h-full flex flex-col p-2">
      {/* Metric selector */}
      <div className="shrink-0 flex items-center justify-center gap-2 mb-2">
        {(['return_1m', 'return_3m', 'return_ytd'] as const).map(metric => (
          <button
            key={metric}
            onClick={() => setActiveMetric(metric)}
            className={`px-2 py-0.5 rounded text-[9px] font-mono transition-colors ${
              activeMetric === metric
                ? 'bg-terminal-yellow/20 text-terminal-yellow'
                : 'text-terminal-dim hover:text-terminal-text'
            }`}
          >
            {metric === 'return_1m' ? '1M' : metric === 'return_3m' ? '3M' : 'YTD'}
          </button>
        ))}
      </div>

      {/* Factor matrix */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-[10px] font-mono">
          <thead>
            <tr className="text-terminal-dim">
              <th className="p-1.5 text-left font-normal"></th>
              {factorTypes.map(f => (
                <th key={f} className="p-1.5 text-center font-normal">{f}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sizes.map(size => (
              <tr key={size} className="border-t border-terminal-gray/20">
                <td className="p-1.5 text-terminal-dim">{size}</td>
                {factorTypes.map(factor => {
                  const data = factors.find(f => f.factor === factor && f.size === size);
                  const value = data ? data[activeMetric] : null;
                  const isPositive = (value || 0) >= 0;
                  
                  return (
                    <td key={factor} className="p-1.5">
                      <div 
                        className={`p-2 rounded text-center ${
                          value !== null
                            ? isPositive 
                              ? 'bg-terminal-green/20 text-terminal-green' 
                              : 'bg-terminal-red/20 text-terminal-red'
                            : 'bg-terminal-gray/20 text-terminal-dim'
                        }`}
                      >
                        {value !== null ? (isPositive ? '+' : '') + value.toFixed(1) + '%' : '-'}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="shrink-0 flex items-center justify-center gap-2 mt-2 text-[9px] font-mono text-terminal-dim">
        <Zap size={10} />
        <span>Factor performance by market cap</span>
      </div>
    </div>
  );
}
