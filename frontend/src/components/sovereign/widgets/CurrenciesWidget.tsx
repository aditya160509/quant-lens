'use client';

/**
 * CURRENCIES WIDGET
 * FX rates and major currency pairs
 */

import React, { useEffect, useState } from 'react';
import { WidgetConfig } from '@/lib/sovereignStore';
import { RefreshCw, DollarSign } from 'lucide-react';

interface CurrencyData {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
}

// Currency flag emojis
const CURRENCY_FLAGS: Record<string, string> = {
  'EUR=X': '🇪🇺',   // Euro
  'JPY=X': '🇯🇵',   // Japanese Yen
  'GBP=X': '🇬🇧',   // British Pound
  'CHF=X': '🇨🇭',   // Swiss Franc
  'CNY=X': '🇨🇳',   // Chinese Yuan
  'INR=X': '🇮🇳',   // Indian Rupee
  'BTC-USD': '₿',   // Bitcoin
  'ETH-USD': 'Ξ',   // Ethereum
  'DX-Y.NYB': '💵', // Dollar Index
};

interface CurrenciesWidgetProps {
  config: WidgetConfig;
}

export default function CurrenciesWidget({ config }: CurrenciesWidgetProps) {
  const [currencies, setCurrencies] = useState<CurrencyData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await fetch('/api/sovereign/tickers?category=currencies');
        const json = await res.json();
        
        if (json.status === 'ok' && json.data?.currencies) {
          setCurrencies(json.data.currencies.tickers);
        }
      } catch (error) {
        console.error('Error fetching currency data:', error);
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
        <DollarSign size={12} className="text-terminal-dim" />
        <span className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider">
          Currencies & Crypto
        </span>
      </div>

      {/* Currency list */}
      <div className="flex-1 overflow-auto">
        <div className="divide-y divide-terminal-gray/20">
          {currencies.map(currency => {
            const isPositive = (currency.change_pct || 0) >= 0;
            const flag = CURRENCY_FLAGS[currency.symbol] || '💰';
            
            return (
              <div
                key={currency.symbol}
                className="flex items-center justify-between px-3 py-2 hover:bg-terminal-gray/10 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <span className="text-base">{flag}</span>
                  <div>
                    <div className="text-xs font-mono text-terminal-text">{currency.name}</div>
                    <div className="text-[9px] font-mono text-terminal-dim">{currency.symbol}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-terminal-text">
                    {currency.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 }) || '-'}
                  </div>
                  <div className={`text-[10px] font-mono ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                    {currency.change_pct !== null ? (isPositive ? '+' : '') + currency.change_pct.toFixed(2) + '%' : '-'}
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
