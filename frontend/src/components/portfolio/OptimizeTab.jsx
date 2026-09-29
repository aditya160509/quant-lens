import React, { useState } from 'react';
import { optimizePortfolio } from '@/lib/api';
import { Loader2 } from 'lucide-react';

export default function OptimizeTab({ holdings, onApply }) {
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [mode, setMode] = useState("max_sharpe");
    const [customTickers, setCustomTickers] = useState("");

    const handleOptimize = async () => {
        setLoading(true);
        try {
            // Use current holdings tickers by default
            let tickers = holdings.map(h => h.symbol);

            // If custom tickers provided, use those
            if (customTickers.trim()) {
                tickers = customTickers.split(',').map(t => t.trim().toUpperCase());
            }

            if (tickers.length === 0) tickers = ["SPY", "QQQ", "TLT", "GLD"]; // Fallback universe

            const res = await optimizePortfolio({ tickers, mode });
            setResult(res);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full overflow-hidden p-1">
            <div className="flex gap-4 mb-4 items-center">
                <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-xs p-2 rounded outline-none"
                >
                    <option value="max_sharpe">Maximize Sharpe Ratio</option>
                    <option value="min_vol">Minimize Volatility</option>
                </select>

                <input
                    type="text"
                    placeholder="Custom Universe (optional, comma separated)"
                    value={customTickers}
                    onChange={(e) => setCustomTickers(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-xs p-2 rounded outline-none flex-1 font-mono"
                />

                <button
                    onClick={handleOptimize}
                    disabled={loading}
                    className="bg-terminal-dark border border-terminal-yellow text-terminal-yellow px-4 py-2 text-xs font-bold rounded hover:bg-terminal-yellow hover:text-black transition-colors"
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "RUN OPTIMIZER"}
                </button>
            </div>

            {result && (
                <div className="flex-1 flex gap-4 overflow-hidden">
                    {/* Metrics */}
                    <div className="w-1/3 bg-terminal-darker p-4 rounded border border-terminal-gray/30">
                        <h4 className="text-xs font-bold text-terminal-dim uppercase mb-4">optimized Metrics</h4>
                        <div className="space-y-3">
                            <div>
                                <div className="text-xs text-terminal-dim">Expected Return</div>
                                <div className="text-lg font-mono text-terminal-green">{(result.metrics.expected_return * 100).toFixed(2)}%</div>
                            </div>
                            <div>
                                <div className="text-xs text-terminal-dim">Expected Volatility</div>
                                <div className="text-lg font-mono text-terminal-text">{(result.metrics.expected_volatility * 100).toFixed(2)}%</div>
                            </div>
                            <div>
                                <div className="text-xs text-terminal-dim">Sharpe Ratio</div>
                                <div className="text-lg font-mono text-terminal-yellow">{result.metrics.sharpe_ratio.toFixed(2)}</div>
                            </div>
                        </div>
                    </div>

                    {/* Weights Table */}
                    <div className="flex-1 bg-terminal-darker p-4 rounded border border-terminal-gray/30 overflow-auto">
                        <h4 className="text-xs font-bold text-terminal-dim uppercase mb-4">Target Weights</h4>
                        <table className="w-full text-left text-xs">
                            <thead>
                                <tr className="text-terminal-dim border-b border-terminal-gray/30">
                                    <th className="p-2">TICKER</th>
                                    <th className="p-2 text-right">WEIGHT</th>
                                    <th className="p-2 text-center">%</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.entries(result.weights).map(([ticker, weight]) => (
                                    <tr key={ticker} className="border-b border-terminal-gray/10">
                                        <td className="p-2 font-bold text-terminal-text">{ticker}</td>
                                        <td className="p-2 text-right font-mono text-terminal-dim">{weight.toFixed(4)}</td>
                                        <td className="p-2 text-center text-terminal-yellow font-bold">{(weight * 100).toFixed(1)}%</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {!result && !loading && (
                <div className="flex-1 flex items-center justify-center text-terminal-dim italic">
                    Select mode and run optimization to see proposed weights.
                </div>
            )}
        </div>
    );
}
