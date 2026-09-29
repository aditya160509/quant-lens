import React, { useState } from 'react';
import { executeTrade } from '@/lib/api';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';

export default function TradePanel({ onTradeSuccess }) {
    const [ticker, setTicker] = useState("");
    const [quantity, setQuantity] = useState("");
    const [side, setSide] = useState("buy");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!ticker || !quantity) return;

        setLoading(true);
        setError(null);
        try {
            await executeTrade({
                ticker: ticker.toUpperCase(),
                quantity: parseInt(quantity),
                side: side
            });
            setTicker("");
            setQuantity("");
            if (onTradeSuccess) onTradeSuccess();
        } catch (err) {
            setError(err.message || "Trade failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-terminal-darker border border-terminal-gray/30 rounded p-4 h-full flex flex-col">
            <h3 className="text-xs font-bold text-terminal-dim uppercase mb-4">Trade Execution</h3>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div className="flex gap-2">
                    <button
                        type="button"
                        onClick={() => setSide("buy")}
                        className={`flex-1 py-1.5 text-xs font-bold border ${side === "buy" ? "bg-terminal-green text-black border-terminal-green" : "text-terminal-dim border-terminal-dim hover:border-terminal-green hover:text-terminal-green"}`}
                    >
                        BUY
                    </button>
                    <button
                        type="button"
                        onClick={() => setSide("sell")}
                        className={`flex-1 py-1.5 text-xs font-bold border ${side === "sell" ? "bg-terminal-red text-black border-terminal-red" : "text-terminal-dim border-terminal-dim hover:border-terminal-red hover:text-terminal-red"}`}
                    >
                        SELL
                    </button>
                </div>

                <div>
                    <TradingViewSearch
                        mode="security"
                        onSelect={(s) => setTicker(s)}
                        placeholder="Search ticker..."
                    />
                    {ticker && (
                        <div className="mt-2 flex items-center gap-2 px-2 py-1 bg-terminal-black border border-terminal-yellow text-terminal-yellow font-mono text-sm">
                            <span className="font-bold">{getSymbolInfo(ticker)?.base || ticker}</span>
                            <span className="text-terminal-dim text-xs">{getSymbolInfo(ticker)?.exchange || 'US'}</span>
                            <button
                                type="button"
                                onClick={() => setTicker('')}
                                className="ml-auto text-terminal-dim hover:text-terminal-red text-sm"
                            >
                                ×
                            </button>
                        </div>
                    )}
                </div>

                <div>
                    <input
                        type="number"
                        placeholder="QUANTITY"
                        value={quantity}
                        onChange={(e) => setQuantity(e.target.value)}
                        className="w-full bg-terminal-black border border-terminal-gray p-2 text-sm text-terminal-text font-mono focus:border-terminal-yellow outline-none placeholder:text-terminal-dark-gray"
                    />
                </div>

                {error && (
                    <div className="text-[10px] text-terminal-red bg-terminal-red/10 p-2 border border-terminal-red/20">
                        Error: {error}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={loading || !ticker || !quantity}
                    className="mt-2 bg-terminal-dark border border-terminal-yellow text-terminal-yellow py-2 text-sm font-bold hover:bg-terminal-yellow hover:text-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {loading ? "EXECUTING..." : "SUBMIT ORDER"}
                </button>
            </form>

            <div className="mt-auto pt-4 text-[10px] text-terminal-dim text-center">
                Est. Cost: <span className="text-terminal-text font-mono">${(quantity && ticker) ? "—" : "0.00"}</span>
            </div>
        </div>
    );
}
