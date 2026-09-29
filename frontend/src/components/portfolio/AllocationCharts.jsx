import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const COLORS = ['#22c55e', '#eab308', '#ef4444', '#3b82f6', '#a855f7', '#ec4899', '#64748b'];

export default function AllocationCharts({ allocations }) {
    if (!allocations) return null;

    // Fallback if data is missing
    const sectors = allocations.sector || [];
    const assets = allocations.asset_class || [];

    const CustomTooltip = ({ active, payload }) => {
        if (active && payload && payload.length) {
            const data = payload[0].payload;
            return (
                <div className="bg-terminal-black border border-terminal-gray p-2 text-xs z-50">
                    <div className="font-bold text-white">{data.name}</div>
                    <div className="text-terminal-dim">{(data.weight * 100).toFixed(1)}%</div>
                </div>
            );
        }
        return null;
    };

    return (
        <div className="bg-terminal-darker border border-terminal-gray/30 rounded p-4 flex flex-col gap-4">
            <h3 className="text-xs font-bold text-terminal-dim uppercase">Allocation</h3>

            <div className="grid grid-cols-2 gap-2 h-32">
                <div className="relative">
                    <div className="absolute top-0 left-0 text-[10px] text-terminal-dark-gray w-full text-center">SECTOR</div>
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={sectors}
                                cx="50%"
                                cy="50%"
                                innerRadius={25}
                                outerRadius={40}
                                paddingAngle={2}
                                dataKey="value"
                                stroke="none"
                            >
                                {sectors.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip content={<CustomTooltip />} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>

                <div className="relative">
                    <div className="absolute top-0 left-0 text-[10px] text-terminal-dark-gray w-full text-center">ASSET CLASS</div>
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={assets}
                                cx="50%"
                                cy="50%"
                                innerRadius={25}
                                outerRadius={40}
                                paddingAngle={2}
                                dataKey="value"
                                stroke="none"
                            >
                                {assets.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip content={<CustomTooltip />} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Legend / List */}
            <div className="flex-1 min-h-0 overflow-y-auto text-[10px] text-terminal-dim space-y-1">
                {sectors.slice(0, 3).map((s, i) => (
                    <div key={s.name} className="flex justify-between">
                        <span className="truncate w-24 flex items-center gap-1">
                            <div className="w-1.5 h-1.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }}></div>
                            {s.name}
                        </span>
                        <span>{(s.weight * 100).toFixed(1)}%</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
