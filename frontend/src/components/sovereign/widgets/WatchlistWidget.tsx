'use client';

/**
 * WATCHLIST WIDGET
 * Personal ticker watchlist with channel sync
 */

import React, { useState } from 'react';
import { useSovereignStore, WidgetConfig } from '@/lib/sovereignStore';
import { Plus, X, Star, TrendingUp, TrendingDown } from 'lucide-react';

interface WatchlistWidgetProps {
  config: WidgetConfig;
}

export default function WatchlistWidget({ config }: WatchlistWidgetProps) {
  const { selectedTickers, addTicker, removeTicker, broadcastToChannel, channelTickers } = useSovereignStore();
  const [newTicker, setNewTicker] = useState('');
  const [showInput, setShowInput] = useState(false);

  const handleAdd = () => {
    const ticker = newTicker.toUpperCase().trim();
    if (ticker) {
      addTicker(ticker);
      setNewTicker('');
      setShowInput(false);
    }
  };

  const handleTickerClick = (ticker: string) => {
    if (config.channel !== 'none') {
      broadcastToChannel(config.channel, ticker);
    }
  };

  const activeTicker = config.channel !== 'none' ? channelTickers[config.channel] : null;

  return (
    <div className="h-full flex flex-col">
      {/* Header with add button */}
      <div className="shrink-0 flex items-center justify-between px-3 py-2 border-b border-terminal-gray/30">
        <span className="text-[10px] font-mono text-terminal-dim uppercase tracking-wider">
          {selectedTickers.length} items
        </span>
        {showInput ? (
          <div className="flex items-center gap-1">
            <input
              type="text"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              placeholder="TICKER"
              className="w-20 px-2 py-0.5 bg-terminal-gray/30 border border-terminal-gray/50 rounded text-[10px] font-mono text-terminal-text placeholder:text-terminal-dim focus:outline-none focus:border-terminal-yellow/50"
              autoFocus
            />
            <button onClick={handleAdd} className="p-0.5 text-terminal-yellow">
              <Plus size={12} />
            </button>
            <button onClick={() => setShowInput(false)} className="p-0.5 text-terminal-dim">
              <X size={12} />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowInput(true)}
            className="p-1 text-terminal-dim hover:text-terminal-yellow"
          >
            <Plus size={14} />
          </button>
        )}
      </div>

      {/* Watchlist */}
      <div className="flex-1 overflow-auto">
        {selectedTickers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-terminal-dim">
            <Star size={24} className="opacity-30" />
            <span className="text-xs">No tickers in watchlist</span>
          </div>
        ) : (
          <div className="divide-y divide-terminal-gray/20">
            {selectedTickers.map(ticker => {
              const isActive = ticker === activeTicker;
              return (
                <div
                  key={ticker}
                  onClick={() => handleTickerClick(ticker)}
                  className={`flex items-center justify-between px-3 py-2 cursor-pointer transition-colors ${
                    isActive 
                      ? 'bg-terminal-yellow/10 border-l-2 border-terminal-yellow' 
                      : 'hover:bg-terminal-gray/20'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Star size={12} className={isActive ? 'text-terminal-yellow fill-terminal-yellow' : 'text-terminal-dim'} />
                    <span className={`font-mono text-sm ${isActive ? 'text-terminal-yellow' : 'text-terminal-text'}`}>
                      {ticker}
                    </span>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeTicker(ticker); }}
                    className="p-1 opacity-0 group-hover:opacity-100 hover:text-terminal-red"
                  >
                    <X size={12} className="text-terminal-dim hover:text-terminal-red" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
