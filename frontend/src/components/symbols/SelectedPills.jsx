'use client';

import React from 'react';
import { getSymbolInfo, getExchangeColor } from '@/lib/universe/symbolMapper';

/**
 * SelectedPills Component
 * Displays selected symbols as removable pills for multi-select.
 * 
 * Props:
 * - symbols: string[] - Array of selected symbols
 * - onRemove: (symbol) => void - Callback when a pill is removed
 * - onClearAll: () => void - Callback to clear all pills
 * - maxDisplay: number - Max pills to show before "+N more"
 */
export default function SelectedPills({
    symbols = [],
    onRemove,
    onClearAll,
    maxDisplay = 10,
}) {
    if (!symbols || symbols.length === 0) {
        return null;
    }

    const displayed = symbols.slice(0, maxDisplay);
    const remaining = symbols.length - maxDisplay;

    return (
        <div className="selected-pills">
            <style jsx>{`
                .selected-pills {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 6px;
                    align-items: center;
                }
                .pill {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 4px 8px 4px 10px;
                    background: #2d2f33;
                    border: 1px solid #3d3f43;
                    border-radius: 16px;
                    font-size: 11px;
                    font-family: var(--font-mono);
                    color: #ffffff;
                    transition: all 0.15s;
                }
                .pill:hover {
                    border-color: #fbbf24;
                    background: rgba(251, 191, 36, 0.1);
                }
                .pill-symbol {
                    font-weight: 600;
                }
                .pill-exchange {
                    font-size: 9px;
                    padding: 1px 4px;
                    border-radius: 3px;
                    text-transform: uppercase;
                    font-weight: 600;
                }
                .pill-remove {
                    background: none;
                    border: none;
                    color: #6b7280;
                    cursor: pointer;
                    padding: 0;
                    font-size: 14px;
                    line-height: 1;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    width: 16px;
                    height: 16px;
                    border-radius: 50%;
                    transition: all 0.15s;
                }
                .pill-remove:hover {
                    color: #ef4444;
                    background: rgba(239, 68, 68, 0.2);
                }
                .remaining-count {
                    padding: 4px 10px;
                    background: #1d1f23;
                    border: 1px solid #2d2f33;
                    border-radius: 16px;
                    font-size: 11px;
                    color: #9ca3af;
                    font-family: var(--font-mono);
                }
                .clear-all {
                    background: none;
                    border: 1px solid #3d3f43;
                    color: #9ca3af;
                    padding: 4px 10px;
                    border-radius: 16px;
                    font-size: 11px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    transition: all 0.15s;
                    margin-left: 4px;
                }
                .clear-all:hover {
                    border-color: #ef4444;
                    color: #ef4444;
                    background: rgba(239, 68, 68, 0.1);
                }
            `}</style>

            {displayed.map(symbol => {
                const info = getSymbolInfo(symbol);
                return (
                    <span key={symbol} className="pill">
                        <span className="pill-symbol">{info?.base || symbol}</span>
                        <span
                            className="pill-exchange"
                            style={{
                                background: `${getExchangeColor(info?.exchange)}20`,
                                color: getExchangeColor(info?.exchange),
                            }}
                        >
                            {info?.exchange || 'US'}
                        </span>
                        {onRemove && (
                            <button
                                className="pill-remove"
                                onClick={() => onRemove(symbol)}
                                title="Remove"
                            >
                                ×
                            </button>
                        )}
                    </span>
                );
            })}

            {remaining > 0 && (
                <span className="remaining-count">+{remaining} more</span>
            )}

            {symbols.length > 1 && onClearAll && (
                <button className="clear-all" onClick={onClearAll}>
                    Clear all
                </button>
            )}
        </div>
    );
}
