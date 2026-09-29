import React, { useState } from 'react';
import { runPortfolioComparison } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function CompareTab({ holdings }) {
    const [benchmarkId, setBenchmarkId] = useState("SPY");
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);

    const handleRun = async () => {
        setLoading(true);
        try {
            // Logic handled in backend to compare current vs selected benchmark
            const res = await runPortfolioComparison({ benchmarkId });
            if (res && res.dates) {
                const chartData = res.dates.map((d, i) => ({
                    date: d,
                    portfolio: (res.strategy_a.equity[i] - 1) * 100,
                    benchmark: (res.strategy_b.equity[i] - 1) * 100
                }));
                setData({ ...res, chartData });
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full p-1 gap-4">
            <div className="flex gap-4 items-center bg-terminal-darker p-3 rounded border border-terminal-gray/30">
                <span className="text-xs text-terminal-dim font-bold uppercase">Compare Against:</span>
                <select
                    value={benchmarkId}
                    onChange={(e) => setBenchmarkId(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-xs p-2 rounded outline-none w-48"
                >
                    <option value="SPY">S&P 500 (SPY)</option>
                    <option value="QQQ">Nasdaq 100 (QQQ)</option>
                    <option value="IWM">Russell 2000 (IWM)</option>
                    <option value="equal_weight">Equal Weight Portfolio</option>
                </select>

                <button
                    onClick={handleRun}
                    disabled={loading || holdings.length === 0}
                    className="ml-auto bg-terminal-dark border border-terminal-yellow text-terminal-yellow px-6 py-2 text-xs font-bold rounded hover:bg-terminal-yellow hover:text-black transition-colors disabled:opacity-50"
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "COMPARE PERFORMANCE"}
                </button>
            </div>

            {data ? (
                <div className="flex-1 flex flex-col gap-4 min-h-0">
                    <div className="flex-1 min-h-0 bg-terminal-darker p-4 rounded border border-terminal-gray/30 flex flex-col">
                        <div className="flex-1 w-full min-h-0 h-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={data.chartData}>
                                    <defs>
                                        <linearGradient id="gradPort" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="gradBench" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <XAxis dataKey="date" hide />
                                    <YAxis domain={['auto', 'auto']} tickFormatter={v => `${v.toFixed(0)}%`} stroke="#666" fontSize={10} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#000', border: '1px solid #333' }}
                                        formatter={(val) => [`${val.toFixed(2)}%`]}
                                    />
                                    <Legend />
                                    <Area type="monotone" dataKey="portfolio" stroke="#22c55e" fill="url(#gradPort)" name="Current Portfolio" strokeWidth={2} />
                                    <Area type="monotone" dataKey="benchmark" stroke="#3b82f6" fill="url(#gradBench)" name={data.strategy_b.name} strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 flex-none">
                        <StatBlock title="Portfolio Sharpe" val={data.strategy_a.metrics.sharpe} color="green" />
                        <StatBlock title={`${data.strategy_b.name} Sharpe`} val={data.strategy_b.metrics.sharpe} color="blue" />
                        <StatBlock title="Portfolio Vol" val={data.strategy_a.metrics.volatility} format="pct" />
                        <StatBlock title="Benchmark Vol" val={data.strategy_b.metrics.volatility} format="pct" />
                    </div>
                </div>
            ) : null}

            {!data && !loading && (
                <div className="flex-1 flex items-center justify-center text-terminal-dim italic">
                    Select a benchmark to comparing your portfolio against.
                </div>
            )}
        </div>
    );
}

function StatBlock({ title, val, format, color }) {
    const fmt = format === "pct" ? `${(val * 100).toFixed(2)}%` : val?.toFixed(2);
    const c = color === "green" ? "text-terminal-green" : color === "blue" ? "text-blue-500" : "text-terminal-text";
    return (
        <div className="bg-terminal-darker p-3 rounded border border-terminal-gray/30 flex justify-between items-center">
            <span className="text-xs text-terminal-dim uppercase">{title}</span>
            <span className={`font-mono font-bold ${c}`}>{fmt}</span>
        </div>
    );
}
