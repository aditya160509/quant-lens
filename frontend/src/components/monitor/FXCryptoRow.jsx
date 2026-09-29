"use client";

import React from 'react';

/**
 * FXCryptoRow - Single horizontal line with FX pairs and crypto
 * USDINR, EURUSD, DXY, BTC, ETH
 */
export default function FXCryptoRow({ data, loading = false }) {
    if (loading) {
        return (
            <div className="flex items-center gap-4">
                {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-4 w-20 bg-terminal-gray animate-pulse rounded" />
                ))}
            </div>
        );
    }

    if (!data?.items?.length) {
        return (
            <div className="text-terminal-dim text-xs font-mono">
                FX/Crypto data unavailable
            </div>
        );
    }

    const getChangeColor = (pct) => {
        if (pct > 0) return 'text-terminal-green';
        if (pct < 0) return 'text-terminal-red';
        return 'text-terminal-dim';
    };

    return (
        <div className="flex items-center gap-4 overflow-x-auto text-xs font-mono">
            {data.items.map((item) => (
                <div key={item.symbol} className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-terminal-dim">{item.symbol}</span>
                    <span className="text-terminal-text">
                        {item.last.toLocaleString(undefined, { 
                            minimumFractionDigits: item.symbol.includes('USD') && !item.symbol.includes('BTC') ? 4 : 2,
                            maximumFractionDigits: item.symbol.includes('USD') && !item.symbol.includes('BTC') ? 4 : 2
                        })}
                    </span>
                    <span className={getChangeColor(item.changePct)}>
                        {item.changePct > 0 ? '+' : ''}{item.changePct.toFixed(2)}%
                    </span>
                </div>
            ))}
        </div>
    );
}
