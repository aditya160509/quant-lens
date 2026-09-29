import React from 'react';

export default function PortfolioMetricsPanel({ metrics }) {
    if (!metrics) return null;

    const {
        var_1d_95 = 0,
        volatility_annual = 0,
        leverage = 1.0,
        beta = 0
    } = metrics;

    return (
        <div className="bg-terminal-darker border border-terminal-gray/30 rounded p-4">
            <h3 className="text-xs font-bold text-terminal-dim uppercase mb-4">Risk Profile</h3>

            <div className="space-y-4">
                <MetricRow
                    label="Value at Risk (95%, 1d)"
                    value={`$${var_1d_95.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                    desc="Estimated max loss on 95% of days"
                />
                <MetricRow
                    label="Annual Volatility"
                    value={`${(volatility_annual * 100).toFixed(1)}%`}
                    desc="Standard deviation of returns (annualized)"
                />
                <MetricRow
                    label="Beta"
                    value={beta.toFixed(2)}
                    desc="Sensitivity to market (SPY)"
                />
                <MetricRow
                    label="Leverage (Gross)"
                    value={`${leverage.toFixed(2)}x`}
                    desc="Total exposure / Equity"
                />
            </div>
        </div>
    );
}

function MetricRow({ label, value, desc }) {
    return (
        <div className="flex flex-col">
            <div className="flex justify-between items-baseline mb-1">
                <span className="text-xs text-terminal-dim">{label}</span>
                <span className="text-sm font-bold text-terminal-text font-mono">{value}</span>
            </div>
            {desc && <span className="text-[10px] text-terminal-dark-gray">{desc}</span>}
            <div className="w-full bg-terminal-gray/20 h-0.5 mt-2"></div>
        </div>
    );
}
