import React from 'react';

export default function StatCard({ label, value, subValue, trend, trendValue, prefix = "", suffix = "", decimals = 2, color = "terminal-green" }) {
    const formatValue = (v) => {
        if (typeof v !== 'number') return v;
        return v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    };

    return (
        <div className="bg-terminal-darker p-4 rounded-sm">
            <div className="text-terminal-dim text-xs uppercase tracking-wider mb-1">{label}</div>
            <div className="flex items-baseline gap-2">
                <div className={`text-2xl font-mono ${color === 'terminal-green' ? 'text-terminal-green' : color === 'terminal-red' ? 'text-terminal-red' : 'text-terminal-text'}`}>
                    {prefix}{formatValue(value)}{suffix}
                </div>
                {subValue && (
                    <div className="text-sm text-terminal-dim font-mono">
                        {subValue}
                    </div>
                )}
            </div>
            {trend && (
                <div className={`text-xs mt-2 font-mono flex items-center gap-1 ${trend === 'up' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                    <span>{trend === 'up' ? '▲' : '▼'}</span>
                    <span>{trendValue}</span>
                </div>
            )}
        </div>
    );
}