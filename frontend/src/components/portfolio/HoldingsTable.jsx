import React, { useState } from 'react';

export default function HoldingsTable({ holdings = [] }) {
    const [sortConfig, setSortConfig] = useState({ key: 'market_value', direction: 'desc' });

    const sortedHoldings = [...holdings].sort((a, b) => {
        if (a[sortConfig.key] < b[sortConfig.key]) {
            return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (a[sortConfig.key] > b[sortConfig.key]) {
            return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
    });

    const requestSort = (key) => {
        let direction = 'desc';
        if (sortConfig.key === key && sortConfig.direction === 'desc') {
            direction = 'asc';
        }
        setSortConfig({ key, direction });
    };

    const SortIcon = ({ col }) => {
        if (sortConfig.key !== col) return <span className="text-terminal-dark-gray ml-1">↕</span>;
        return <span className="text-terminal-yellow ml-1">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>;
    };

    return (
        <div className="flex flex-col h-full bg-terminal-darker border border-terminal-gray/30 rounded overflow-hidden">
            <div className="bg-terminal-black/50 p-2 border-b border-terminal-gray/30 text-xs font-bold text-terminal-dim uppercase tracking-wider">
                Holdings
            </div>

            <div className="flex-1 overflow-auto">
                <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-terminal-black sticky top-0 z-10">
                        <tr className="text-terminal-dim border-b border-terminal-gray/30">
                            <th className="p-3 cursor-pointer hover:text-terminal-text" onClick={() => requestSort('symbol')}>
                                TICKER <SortIcon col="symbol" />
                            </th>
                            <th className="p-3 text-right cursor-pointer hover:text-terminal-text" onClick={() => requestSort('quantity')}>
                                QTY <SortIcon col="quantity" />
                            </th>
                            <th className="p-3 text-right cursor-pointer hover:text-terminal-text" onClick={() => requestSort('avg_cost')}>
                                AVG COST <SortIcon col="avg_cost" />
                            </th>
                            <th className="p-3 text-right cursor-pointer hover:text-terminal-text" onClick={() => requestSort('current_price')}>
                                PRICE <SortIcon col="current_price" />
                            </th>
                            <th className="p-3 text-right cursor-pointer hover:text-terminal-text" onClick={() => requestSort('market_value')}>
                                VALUE <SortIcon col="market_value" />
                            </th>
                            <th className="p-3 text-right cursor-pointer hover:text-terminal-text" onClick={() => requestSort('unrealized_pl')}>
                                P&L <SortIcon col="unrealized_pl" />
                            </th>
                            <th className="p-3 text-right cursor-pointer hover:text-terminal-text" onClick={() => requestSort('weight')}>
                                WGT <SortIcon col="weight" />
                            </th>
                            <th className="p-3 text-center">LIQ</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-terminal-gray/10">
                        {sortedHoldings.length > 0 ? (
                            sortedHoldings.map((h, i) => (
                                <tr key={h.symbol} className={`hover:bg-terminal-gray/10 ${i % 2 === 0 ? 'bg-terminal-black' : 'bg-terminal-darker'}`}>
                                    <td className="p-3 font-bold text-terminal-text">{h.symbol}</td>
                                    <td className="p-3 text-right text-terminal-dim">{h.quantity}</td>
                                    <td className="p-3 text-right text-terminal-dim">${h.avg_cost.toFixed(2)}</td>
                                    <td className="p-3 text-right text-white">${h.current_price?.toFixed(2) || '0.00'}</td>
                                    <td className="p-3 text-right text-white font-medium">
                                        ${h.market_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    </td>
                                    <td className={`p-3 text-right ${h.unrealized_pl >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                        ${h.unrealized_pl.toLocaleString()}
                                        <div className="text-[10px] opacity-75">{h.return_pct.toFixed(2)}%</div>
                                    </td>
                                    <td className="p-3 text-right text-terminal-yellow">
                                        {(h.weight * 100).toFixed(1)}%
                                    </td>
                                    <td className="p-3 text-center">
                                        {h.liquidity ? (
                                            <span className={`text-[9px] px-1 py-0.5 rounded ${h.liquidity.liquidity_color}`}>
                                                {h.liquidity.liquidity_label}
                                            </span>
                                        ) : '-'}
                                    </td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan="8" className="p-8 text-center text-terminal-dim italic">
                                    No positions yet • place your first trade to populate this table
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
