/**
 * Q360 Quant Panel
 * Empty container placeholder for future quant modules
 * Replaces "Risk profile vs SPY" on Security page
 */

'use client';

import React from 'react';
import { CHART_THEME } from './types';

// =============================================================================
// TYPES
// =============================================================================

interface Q360QuantPanelProps {
    height?: number | string;
    className?: string;
}

// =============================================================================
// PLACEHOLDER MODULES
// =============================================================================

const FUTURE_MODULES = [
    { id: 'orderbook', label: 'Order Book', icon: '📊' },
    { id: 'factors', label: 'Factor Exposure', icon: '📈' },
    { id: 'fundamentals', label: 'Fundamentals', icon: '📋' },
    { id: 'options', label: 'Options Flow', icon: '⚡' },
    { id: 'earnings', label: 'Earnings', icon: '📅' },
];

// =============================================================================
// COMPONENT
// =============================================================================

export default function Q360QuantPanel({ height = '100%', className = '' }: Q360QuantPanelProps) {
    return (
        <div
            className={`flex flex-col ${className}`}
            style={{
                height,
                background: CHART_THEME.bgPrimary,
                border: `1px solid ${CHART_THEME.border}`,
                borderRadius: 4,
            }}
        >
            {/* Header */}
            <div
                className="px-3 py-2 flex items-center justify-between"
                style={{ borderBottom: `1px solid ${CHART_THEME.border}` }}
            >
                <span
                    className="text-xs font-mono font-medium"
                    style={{ color: CHART_THEME.textSecondary }}
                >
                    QUANT PANEL
                </span>
                <span
                    className="text-xs font-mono px-1.5 py-0.5 rounded"
                    style={{
                        background: 'rgba(255, 214, 10, 0.1)',
                        color: CHART_THEME.accent,
                    }}
                >
                    v1.0
                </span>
            </div>

            {/* Content */}
            <div className="flex-1 flex flex-col items-center justify-center p-4">
                <div
                    className="text-center mb-4"
                    style={{ color: CHART_THEME.textMuted }}
                >
                    <div className="text-3xl mb-2">🔧</div>
                    <div className="text-xs font-mono">Coming Soon</div>
                </div>

                {/* Future module hints */}
                <div className="w-full max-w-xs space-y-2">
                    {FUTURE_MODULES.map(mod => (
                        <div
                            key={mod.id}
                            className="flex items-center gap-2 px-3 py-2 rounded"
                            style={{
                                background: CHART_THEME.bgSecondary,
                                border: `1px solid ${CHART_THEME.border}`,
                                opacity: 0.5,
                            }}
                        >
                            <span className="text-sm">{mod.icon}</span>
                            <span
                                className="text-xs font-mono"
                                style={{ color: CHART_THEME.textSecondary }}
                            >
                                {mod.label}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Footer */}
            <div
                className="px-3 py-2 text-center"
                style={{
                    borderTop: `1px solid ${CHART_THEME.border}`,
                    color: CHART_THEME.textMuted,
                }}
            >
                <span className="text-xs font-mono">
                    Drop modules here to customize
                </span>
            </div>
        </div>
    );
}

// =============================================================================
// MINI VERSION (for compact layouts)
// =============================================================================

export function Q360QuantPanelMini({ className = '' }: { className?: string }) {
    return (
        <div
            className={`p-2 rounded ${className}`}
            style={{
                background: CHART_THEME.bgSecondary,
                border: `1px solid ${CHART_THEME.border}`,
            }}
        >
            <div
                className="text-xs font-mono flex items-center gap-1"
                style={{ color: CHART_THEME.textMuted }}
            >
                <span>🔧</span>
                <span>Quant Panel</span>
            </div>
        </div>
    );
}
