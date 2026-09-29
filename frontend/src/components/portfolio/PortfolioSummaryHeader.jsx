import React from 'react';
import StatCard from '../StatCard';

export default function PortfolioSummaryHeader({ data }) {
    if (!data) return null;

    const {
        total_equity = 0,
        cash = 0,
        unrealized_pl = 0,
        daily_pl = 0,
        positions_count = 0,
        beta = 0,
        volatility = 0
    } = data;

    return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-4 mb-6">
            <StatCard
                label="TOTAL EQUITY"
                value={total_equity}
                prefix="$"
                color="terminal-text"
            />
            <StatCard
                label="CASH"
                value={cash}
                prefix="$"
                color="terminal-dim"
            />
            <StatCard
                label="UNREALIZED P&L"
                value={unrealized_pl}
                prefix="$"
                color={unrealized_pl >= 0 ? "terminal-green" : "terminal-red"}
                trend={unrealized_pl > 0 ? "up" : unrealized_pl < 0 ? "down" : "neutral"}
            />
            <StatCard
                label="DAILY P&L"
                value={daily_pl}
                prefix="$"
                color={daily_pl >= 0 ? "terminal-green" : "terminal-red"}
            />
            <StatCard
                label="POSITIONS"
                value={positions_count}
            />
            <StatCard
                label="BETA"
                value={beta === 0 ? "—" : beta.toFixed(2)}
                color="terminal-yellow"
            />
            <StatCard
                label="VOLATILITY"
                value={volatility === 0 ? "—" : (volatility * 100).toFixed(1)}
                suffix={volatility === 0 ? "" : "%"}
            />
        </div>
    );
}
