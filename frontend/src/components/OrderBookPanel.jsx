"use client";

import React, { useState, useEffect } from 'react';
import TerminalPanel from './TerminalPanel';

const API_BASE_URL = "http://127.0.0.1:8000/api";

export default function OrderBookPanel({ ticker, isSynthetic = false }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        setData(null);
        setLoading(true);
        if (ticker) {
            fetchOrderBook();
            const interval = setInterval(fetchOrderBook, 5000); // Refresh every 5s
            return () => clearInterval(interval);
        }
    }, [ticker]);

    const fetchOrderBook = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/orderbook/${ticker}`);
            if (!res.ok) throw new Error("Failed to fetch order book");
            const d = await res.json();
            setData(d);
            setError(null);
            setLoading(false);
        } catch (e) {
            console.error(e);
            setError(e.message);
            setLoading(false);
        }
    };

    if (loading && !data) return <div className="p-4 text-terminal-dim animate-pulse">Loading L2 Data...</div>;
    if (error) return <div className="p-4 text-terminal-red text-xs">L2 Data Unavailable</div>;
    if (!data) return null;

    const maxTotal = Math.max(
        data.bids[data.bids.length - 1]?.total || 0,
        data.asks[data.asks.length - 1]?.total || 0
    );

    const title = isSynthetic ? "ORDER BOOK L2 (SYNTHETIC)" : "ORDER BOOK (L2)";
    const subtitle = isSynthetic
        ? `Spread computed from liquidity • ${data.spread.toFixed(2)}`
        : `Spread: ${data.spread.toFixed(2)} (${(data.spread_pct * 100).toFixed(3)}%)`;

    return (
        <TerminalPanel title={title} subtitle={subtitle}>
            <div className="flex gap-1 text-xs font-mono h-[300px] overflow-hidden">
                {/* BIDS */}
                <div className="flex-1 flex flex-col">
                    <div className="flex text-terminal-dim border-b border-terminal-gray mb-1 pb-1">
                        <div className="flex-1 text-right">Size</div>
                        <div className="flex-1 text-right pr-2">Bid</div>
                    </div>
                    <div className="flex-1 overflow-auto">
                        {data.bids.map((b, i) => (
                            <div key={i} className="relative flex items-center mb-0.5">
                                <div
                                    className="absolute right-0 top-0 bottom-0 bg-terminal-green/20 z-0"
                                    style={{ width: `${(b.total / maxTotal) * 100}%` }}
                                ></div>
                                <div className="relative z-10 flex-1 flex w-full">
                                    <div className="flex-1 text-right text-terminal-dim">{b.size}</div>
                                    <div className="flex-1 text-right pr-2 text-terminal-green">{b.price.toFixed(2)}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ASKS */}
                <div className="flex-1 flex flex-col">
                    <div className="flex text-terminal-dim border-b border-terminal-gray mb-1 pb-1">
                        <div className="flex-1 pl-2 text-left">Ask</div>
                        <div className="flex-1 text-left">Size</div>
                    </div>
                    <div className="flex-1 overflow-auto">
                        {data.asks.map((a, i) => (
                            <div key={i} className="relative flex items-center mb-0.5">
                                <div
                                    className="absolute left-0 top-0 bottom-0 bg-terminal-red/20 z-0"
                                    style={{ width: `${(a.total / maxTotal) * 100}%` }}
                                ></div>
                                <div className="relative z-10 flex-1 flex w-full">
                                    <div className="flex-1 pl-2 text-left text-terminal-red">{a.price.toFixed(2)}</div>
                                    <div className="flex-1 text-left text-terminal-dim">{a.size}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </TerminalPanel>
    );
}
