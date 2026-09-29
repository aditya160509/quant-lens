/**
 * Layout Selector
 * TradingView-style dropdown for selecting chart grid layouts
 * Matches the layout picker shown in the screenshots
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { CHART_THEME } from './types';
import { type LayoutPreset, LAYOUT_PRESETS, type SyncSettings } from './workspaceTypes';

// =============================================================================
// TYPES
// =============================================================================

interface LayoutSelectorProps {
    currentLayout: LayoutPreset;
    onLayoutChange: (layout: LayoutPreset) => void;
    syncSettings: SyncSettings;
    onSyncSettingsChange: (settings: Partial<SyncSettings>) => void;
}

// =============================================================================
// LAYOUT ICON COMPONENT
// =============================================================================

function LayoutIcon({ layout, size = 24, active = false }: { 
    layout: LayoutPreset; 
    size?: number; 
    active?: boolean 
}) {
    const config = LAYOUT_PRESETS[layout];
    const cellSize = (size - 4) / Math.max(config.rows, config.cols);
    const gap = 1;

    return (
        <svg 
            width={size} 
            height={size} 
            viewBox={`0 0 ${size} ${size}`}
            style={{ display: 'block' }}
        >
            {config.cells.map((cell, idx) => (
                <rect
                    key={idx}
                    x={2 + cell.col * (cellSize + gap)}
                    y={2 + cell.row * (cellSize + gap)}
                    width={cellSize * (cell.colSpan || 1) - gap}
                    height={cellSize * (cell.rowSpan || 1) - gap}
                    rx={1}
                    fill={active ? CHART_THEME.accent : CHART_THEME.textSecondary}
                    stroke={active ? CHART_THEME.accent : CHART_THEME.border}
                    strokeWidth={0.5}
                />
            ))}
        </svg>
    );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function LayoutSelector({
    currentLayout,
    onLayoutChange,
    syncSettings,
    onSyncSettingsChange,
}: LayoutSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close on outside click
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [isOpen]);

    // Layout options organized by row count (matching TradingView)
    const layoutRows: { count: number; layouts: LayoutPreset[] }[] = [
        { count: 1, layouts: ['1x1'] },
        { count: 2, layouts: ['1x2', '2x1'] },
        { count: 3, layouts: ['1x3', '3x1', '2x2'] },
        { count: 4, layouts: ['1x4', '2x3', '3x2', '4x1'] },
        { count: 5, layouts: ['2x4', '4x2'] },
        { count: 6, layouts: ['3x3'] },
        { count: 8, layouts: ['4x3', '3x4'] },
        { count: 12, layouts: ['4x4'] },
    ];

    return (
        <div ref={dropdownRef} style={{ position: 'relative' }}>
            {/* Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 10px',
                    background: isOpen ? CHART_THEME.bgTertiary : 'transparent',
                    border: `1px solid ${CHART_THEME.border}`,
                    borderRadius: '4px',
                    cursor: 'pointer',
                    color: CHART_THEME.textPrimary,
                    fontSize: '12px',
                    fontFamily: CHART_THEME.fontSans,
                }}
            >
                <LayoutIcon layout={currentLayout} size={18} />
                <span style={{ opacity: 0.8 }}>{currentLayout}</span>
                <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
                    <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
            </button>

            {/* Dropdown Panel */}
            {isOpen && (
                <div
                    style={{
                        position: 'absolute',
                        top: 'calc(100% + 4px)',
                        right: 0,
                        width: '320px',
                        background: CHART_THEME.bgSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                        borderRadius: '8px',
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
                        zIndex: 1000,
                        padding: '12px',
                    }}
                >
                    {/* Layout Grid Options */}
                    <div style={{ marginBottom: '16px' }}>
                        {layoutRows.map((row, rowIdx) => (
                            <div
                                key={rowIdx}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    marginBottom: '8px',
                                }}
                            >
                                <span style={{
                                    width: '20px',
                                    fontSize: '11px',
                                    color: CHART_THEME.textSecondary,
                                    textAlign: 'right',
                                }}>
                                    {row.count}
                                </span>
                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                    {row.layouts.map((layout) => (
                                        <button
                                            key={layout}
                                            onClick={() => {
                                                onLayoutChange(layout);
                                                setIsOpen(false);
                                            }}
                                            style={{
                                                padding: '6px',
                                                background: currentLayout === layout 
                                                    ? 'rgba(255, 214, 10, 0.15)' 
                                                    : 'transparent',
                                                border: `1px solid ${currentLayout === layout 
                                                    ? CHART_THEME.accent 
                                                    : CHART_THEME.border}`,
                                                borderRadius: '4px',
                                                cursor: 'pointer',
                                            }}
                                            title={layout}
                                        >
                                            <LayoutIcon 
                                                layout={layout} 
                                                size={28}
                                                active={currentLayout === layout}
                                            />
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Divider */}
                    <div style={{
                        height: '1px',
                        background: CHART_THEME.border,
                        margin: '12px 0',
                    }} />

                    {/* Sync Settings */}
                    <div>
                        <div style={{
                            fontSize: '11px',
                            color: CHART_THEME.textSecondary,
                            marginBottom: '10px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px',
                        }}>
                            Sync in Layout
                        </div>

                        {[
                            { key: 'symbol', label: 'Symbol' },
                            { key: 'interval', label: 'Interval' },
                            { key: 'crosshair', label: 'Crosshair' },
                            { key: 'time', label: 'Time' },
                            { key: 'dateRange', label: 'Date range' },
                        ].map(({ key, label }) => (
                            <div
                                key={key}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '8px 0',
                                    borderBottom: `1px solid ${CHART_THEME.border}`,
                                }}
                            >
                                <span style={{
                                    fontSize: '13px',
                                    color: CHART_THEME.textPrimary,
                                }}>
                                    {label}
                                </span>
                                <ToggleSwitch
                                    checked={syncSettings[key as keyof SyncSettings]}
                                    onChange={(checked) => 
                                        onSyncSettingsChange({ [key]: checked })
                                    }
                                />
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// TOGGLE SWITCH COMPONENT
// =============================================================================

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
    return (
        <button
            onClick={() => onChange(!checked)}
            style={{
                width: '36px',
                height: '20px',
                borderRadius: '10px',
                background: checked ? CHART_THEME.accent : CHART_THEME.bgTertiary,
                border: `1px solid ${checked ? CHART_THEME.accent : CHART_THEME.border}`,
                cursor: 'pointer',
                position: 'relative',
                transition: 'background 0.15s, border-color 0.15s',
            }}
        >
            <div
                style={{
                    position: 'absolute',
                    top: '2px',
                    left: checked ? '18px' : '2px',
                    width: '14px',
                    height: '14px',
                    borderRadius: '50%',
                    background: checked ? '#000' : CHART_THEME.textSecondary,
                    transition: 'left 0.15s',
                }}
            />
        </button>
    );
}

export default LayoutSelector;
