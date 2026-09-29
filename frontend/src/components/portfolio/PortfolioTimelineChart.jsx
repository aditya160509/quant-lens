import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { fetchPortfolioHistory } from '@/lib/api';

export default function PortfolioTimelineChart() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const res = await fetchPortfolioHistory();
                // Format: { dates: [], equity: [] } -> [{date, equity}]
                if (res && res.dates) {
                    const formatted = res.dates.map((d, i) => ({
                        date: d,
                        equity: res.equity[i],
                        pnl: res.pnl_daily ? res.pnl_daily[i] : 0
                    }));
                    setData(formatted);
                }
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    if (loading) return <div className="h-32 flex items-center justify-center text-xs text-terminal-dim">Loading History...</div>;

    // Use fallback mock if empty (for dev)
    const chartData = (data && data.length > 0) ? data : [];

    if (chartData.length === 0) {
        return (
            <div className="h-48 flex items-center justify-center bg-terminal-darker border border-terminal-gray/30 rounded text-xs text-terminal-dim italic">
                No history available yet
            </div>
        );
    }

    return (
        <div className="h-64 w-full bg-terminal-darker border border-terminal-gray/30 rounded p-4 flex flex-col">
            <h3 className="text-xs font-bold text-terminal-dim uppercase mb-2">Portfolio Equity Curve</h3>
            <div className="flex-1 min-h-0 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                        <XAxis
                            dataKey="date"
                            stroke="#666"
                            tick={{ fill: '#666', fontSize: 10 }}
                            tickFormatter={(str) => str.substring(5)} // MM-DD
                        />
                        <YAxis
                            stroke="#666"
                            tick={{ fill: '#666', fontSize: 10 }}
                            domain={['auto', 'auto']}
                            tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#000', border: '1px solid #333' }}
                            itemStyle={{ color: '#fff', fontSize: 12 }}
                            labelStyle={{ color: '#888', fontSize: 10 }}
                        />
                        <Area
                            type="monotone"
                            dataKey="equity"
                            stroke="#22c55e"
                            fillOpacity={1}
                            fill="url(#colorEquity)"
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
