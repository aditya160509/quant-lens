import React, { useState } from 'react';
import { runBacktest } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function BacktestTab({ holdings }) {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [strategy, setStrategy] = useState("current_weights");

    // Default 2y
    const [startDate, setStartDate] = useState(() => {
        const d = new Date();
        d.setFullYear(d.getFullYear() - 2);
        return d.toISOString().split('T')[0];
    });
    const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0]);

    const handleRun = async () => {
        setLoading(true);
        try {
            const res = await runBacktest({ strategy, startDate, endDate });
            if (res && res.dates) {
                // Reformat for chart
                const chartData = res.dates.map((d, i) => ({
                    date: d,
                    strategy: ((res.strategy_equity[i] - 1) * 100),
                    benchmark: ((res.benchmark_equity[i] - 1) * 100)
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
        <div className="flex flex-col h-full gap-4 p-1">
            <div className="flex gap-4 items-center bg-terminal-darker p-3 rounded border border-terminal-gray/30">
                <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-xs p-2 rounded outline-none"
                >
                    <option value="current_weights">Current Portfolio Weights</option>
                    <option value="equal_weight">Equal Weight (Current Holdings)</option>
                </select>

                <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-xs p-2 rounded outline-none text-terminal-text"
                />
                <span className="text-terminal-dim">-</span>
                <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="bg-terminal-black border border-terminal-gray text-xs p-2 rounded outline-none text-terminal-text"
                />

                <button
                    onClick={handleRun}
                    disabled={loading || holdings.length === 0}
                    className="ml-auto bg-terminal-dark border border-terminal-green text-terminal-green px-6 py-2 text-xs font-bold rounded hover:bg-terminal-green hover:text-black transition-colors disabled:opacity-50"
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "RUN BACKTEST"}
                </button>
            </div>

            {data ? (
                <div className="flex-1 flex flex-col gap-4 min-h-0">
                    {/* Chart Container */}
                    <div className="flex-1 min-h-0 bg-terminal-darker p-4 rounded border border-terminal-gray/30 flex flex-col">
                        <div className="flex-1 w-full min-h-0 h-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={data.chartData}>
                                    <defs>
                                        <linearGradient id="gradStrat" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <XAxis dataKey="date" hide />
                                    <YAxis domain={['auto', 'auto']} tickFormatter={v => `${v.toFixed(0)}%`} stroke="#666" fontSize={10} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#000', border: '1px solid #333' }}
                                        formatter={(val) => [`${val.toFixed(2)}%`]}
                                    />
                                    <Legend />
                                    <Area type="monotone" dataKey="strategy" stroke="#22c55e" fill="url(#gradStrat)" name="Portfolio" strokeWidth={2} />
                                    <Area type="monotone" dataKey="benchmark" stroke="#64748b" fill="none" name="SPY Benchmark" strokeWidth={2} strokeDasharray="3 3" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* Metrics Grid */}
                    <div className="grid grid-cols-4 gap-4 flex-none">
                        <MetricCard label="CAGR" val={data.metrics.cagr} bmVal={data.benchmark_metrics.cagr} format="pct" />
                        <MetricCard label="Volatility" val={data.metrics.volatility} bmVal={data.benchmark_metrics.volatility} format="pct" />
                        <MetricCard label="Max Drawdown" val={data.metrics.max_drawdown} bmVal={data.benchmark_metrics.max_drawdown} format="pct" color="red" />
                        <MetricCard label="Sharpe Ratio" val={data.metrics.sharpe_ratio} bmVal={data.benchmark_metrics.sharpe_ratio} format="num" />
                    </div>
                </div>
            ) : null}

            {!data && !loading && (
                <div className="flex-1 flex items-center justify-center text-terminal-dim italic">
                    Configure parameters and run backtest to see performance history.
                </div>
            )}
        </div>
    );
}

function MetricCard({ label, val, bmVal, format, color = "green" }) {
    const fmt = (v) => format === "pct" ? `${(v * 100).toFixed(2)}%` : v.toFixed(2);
    const diff = val - bmVal;

    return (
        <div className="bg-terminal-darker p-3 rounded border border-terminal-gray/30">
            <div className="text-[10px] text-terminal-dim uppercase mb-1">{label}</div>
            <div className={`text-lg font-mono font-bold ${color === "red" ? "text-terminal-red" : "text-terminal-text"}`}>
                {fmt(val)}
            </div>
            <div className="text-[10px] flex justify-between mt-1">
                <span className="text-terminal-dim">BM: {fmt(bmVal)}</span>
                <span className={diff > 0 ? "text-terminal-green" : "text-terminal-red"}>
                    {diff > 0 ? '+' : ''}{fmt(diff)}
                </span>
            </div>
        </div>
    );
}
