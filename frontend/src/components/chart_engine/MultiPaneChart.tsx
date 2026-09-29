/**
 * Multi-Pane Chart System
 * Allows multiple stacked chart panes with resizable heights
 * Supports: Price pane, Volume pane, Indicator panes (RSI, MACD, etc.)
 */

'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { CHART_THEME } from './types';
import type { PaneConfig, IndicatorConfig, OHLCVBar } from './types';

// =============================================================================
// TYPES
// =============================================================================

export interface ChartPane {
    id: string;
    type: 'price' | 'volume' | 'indicator';
    title: string;
    height: number; // Percentage of total height (0-100)
    minHeight: number; // Minimum height in pixels
    collapsed: boolean;
    indicators?: string[]; // Indicator IDs for this pane
    scaleMode?: 'auto' | 'log' | 'percent';
}

export interface MultiPaneState {
    panes: ChartPane[];
    totalHeight: number;
    dragState: {
        isDragging: boolean;
        paneId: string | null;
        startY: number;
        startHeight: number;
    };
}

interface ChartPaneProps {
    pane: ChartPane;
    height: number;
    isFirst: boolean;
    isLast: boolean;
    onResize: (id: string, newHeight: number) => void;
    onClose: (id: string) => void;
    onToggleCollapse: (id: string) => void;
    onDragStart: (id: string, startY: number) => void;
    children?: React.ReactNode;
}

interface MultiPaneContainerProps {
    children?: React.ReactNode;
    totalHeight: number;
    onAddPane?: (type: 'volume' | 'indicator', indicatorId?: string) => void;
}

// =============================================================================
// DEFAULT PANES
// =============================================================================

export const DEFAULT_PANES: ChartPane[] = [
    {
        id: 'price',
        type: 'price',
        title: 'Price',
        height: 70,
        minHeight: 150,
        collapsed: false,
        scaleMode: 'auto',
    },
    {
        id: 'volume',
        type: 'volume',
        title: 'Volume',
        height: 30,
        minHeight: 60,
        collapsed: false,
    },
];

// =============================================================================
// PANE HEADER COMPONENT
// =============================================================================

function PaneHeader({
    pane,
    onClose,
    onToggleCollapse,
    showClose = true,
}: {
    pane: ChartPane;
    onClose: (id: string) => void;
    onToggleCollapse: (id: string) => void;
    showClose?: boolean;
}) {
    return (
        <div
            className="flex items-center justify-between px-2 py-1"
            style={{
                background: CHART_THEME.bgSecondary,
                borderBottom: `1px solid ${CHART_THEME.border}`,
                height: 24,
            }}
        >
            <div className="flex items-center gap-2">
                <button
                    onClick={() => onToggleCollapse(pane.id)}
                    className="text-xs px-1 opacity-60 hover:opacity-100 transition-opacity"
                    style={{ color: CHART_THEME.textSecondary }}
                >
                    {pane.collapsed ? '▶' : '▼'}
                </button>
                <span
                    className="text-xs font-mono font-semibold uppercase tracking-wide"
                    style={{ color: CHART_THEME.textSecondary }}
                >
                    {pane.title}
                </span>
                {pane.indicators && pane.indicators.length > 0 && (
                    <span
                        className="text-xs font-mono"
                        style={{ color: CHART_THEME.accent }}
                    >
                        ({pane.indicators.join(', ')})
                    </span>
                )}
            </div>
            <div className="flex items-center gap-1">
                {/* Settings button */}
                <button
                    className="w-5 h-5 flex items-center justify-center text-xs opacity-50 hover:opacity-100 transition-opacity"
                    style={{ color: CHART_THEME.textSecondary }}
                    title="Settings"
                >
                    ⚙
                </button>
                {/* Close button (not for price pane) */}
                {showClose && pane.type !== 'price' && (
                    <button
                        onClick={() => onClose(pane.id)}
                        className="w-5 h-5 flex items-center justify-center text-xs opacity-50 hover:opacity-100 transition-opacity hover:text-red-400"
                        style={{ color: CHART_THEME.textSecondary }}
                        title="Remove pane"
                    >
                        ✕
                    </button>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// RESIZE HANDLE COMPONENT
// =============================================================================

function ResizeHandle({
    onDragStart,
}: {
    onDragStart: (e: React.MouseEvent) => void;
}) {
    const [isHovered, setIsHovered] = useState(false);

    return (
        <div
            className="w-full h-[6px] cursor-row-resize flex items-center justify-center group"
            style={{
                background: isHovered ? CHART_THEME.accent + '30' : 'transparent',
            }}
            onMouseDown={onDragStart}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            <div
                className="w-12 h-1 rounded transition-all"
                style={{
                    background: isHovered ? CHART_THEME.accent : CHART_THEME.border,
                }}
            />
        </div>
    );
}

// =============================================================================
// CHART PANE COMPONENT
// =============================================================================

export function ChartPaneContainer({
    pane,
    height,
    isFirst,
    isLast,
    onResize,
    onClose,
    onToggleCollapse,
    onDragStart,
    children,
}: ChartPaneProps) {
    const handleResizeStart = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        onDragStart(pane.id, e.clientY);
    }, [pane.id, onDragStart]);

    const contentHeight = pane.collapsed ? 0 : height - 24 - (isLast ? 0 : 6);

    return (
        <div
            className="flex flex-col"
            style={{
                height: pane.collapsed ? 24 : height,
                minHeight: pane.collapsed ? 24 : pane.minHeight,
                borderBottom: isLast ? 'none' : `1px solid ${CHART_THEME.border}`,
            }}
        >
            <PaneHeader
                pane={pane}
                onClose={onClose}
                onToggleCollapse={onToggleCollapse}
                showClose={!isFirst}
            />

            {!pane.collapsed && (
                <div
                    className="flex-1 relative overflow-hidden"
                    style={{ height: contentHeight }}
                >
                    {children}
                </div>
            )}

            {!isLast && !pane.collapsed && (
                <ResizeHandle onDragStart={handleResizeStart} />
            )}
        </div>
    );
}

// =============================================================================
// MULTI-PANE CONTAINER HOOK
// =============================================================================

export function useMultiPane(initialPanes: ChartPane[] = DEFAULT_PANES) {
    const [panes, setPanes] = useState<ChartPane[]>(initialPanes);
    const [dragState, setDragState] = useState({
        isDragging: false,
        paneId: null as string | null,
        startY: 0,
        initialHeights: {} as Record<string, number>,
    });

    const containerRef = useRef<HTMLDivElement>(null);

    // Add a new pane
    const addPane = useCallback((type: 'volume' | 'indicator', indicatorId?: string) => {
        const newPane: ChartPane = {
            id: `pane_${Date.now()}`,
            type,
            title: type === 'volume' ? 'Volume' : indicatorId?.toUpperCase() || 'Indicator',
            height: 20,
            minHeight: 60,
            collapsed: false,
            indicators: indicatorId ? [indicatorId] : [],
        };

        setPanes(prev => {
            // Reduce other panes' heights proportionally
            const totalReduction = newPane.height;
            const adjustmentFactor = (100 - totalReduction) / 100;

            return [
                ...prev.map(p => ({
                    ...p,
                    height: p.height * adjustmentFactor,
                })),
                newPane,
            ];
        });
    }, []);

    // Remove a pane
    const removePane = useCallback((id: string) => {
        setPanes(prev => {
            const paneToRemove = prev.find(p => p.id === id);
            if (!paneToRemove) return prev;

            const remaining = prev.filter(p => p.id !== id);
            const heightToRedistribute = paneToRemove.height;

            // Redistribute height to remaining panes
            const adjustmentFactor = 100 / (100 - heightToRedistribute);
            return remaining.map(p => ({
                ...p,
                height: p.height * adjustmentFactor,
            }));
        });
    }, []);

    // Toggle pane collapse
    const toggleCollapse = useCallback((id: string) => {
        setPanes(prev => prev.map(p =>
            p.id === id ? { ...p, collapsed: !p.collapsed } : p
        ));
    }, []);

    // Start dragging
    const startDrag = useCallback((paneId: string, startY: number) => {
        const heights: Record<string, number> = {};
        panes.forEach(p => {
            heights[p.id] = p.height;
        });

        setDragState({
            isDragging: true,
            paneId,
            startY,
            initialHeights: heights,
        });
    }, [panes]);

    // Handle drag move
    useEffect(() => {
        if (!dragState.isDragging || !dragState.paneId || !containerRef.current) return;

        const handleMouseMove = (e: MouseEvent) => {
            const containerHeight = containerRef.current?.offsetHeight || 500;
            const deltaY = e.clientY - dragState.startY;
            const deltaPercent = (deltaY / containerHeight) * 100;

            const paneIndex = panes.findIndex(p => p.id === dragState.paneId);
            if (paneIndex === -1 || paneIndex === panes.length - 1) return;

            const currentPane = panes[paneIndex];
            const nextPane = panes[paneIndex + 1];

            const currentInitial = dragState.initialHeights[currentPane.id];
            const nextInitial = dragState.initialHeights[nextPane.id];

            let newCurrentHeight = currentInitial + deltaPercent;
            let newNextHeight = nextInitial - deltaPercent;

            // Enforce minimum heights
            const minPercent = (60 / containerHeight) * 100;
            if (newCurrentHeight < minPercent) {
                newCurrentHeight = minPercent;
                newNextHeight = currentInitial + nextInitial - minPercent;
            }
            if (newNextHeight < minPercent) {
                newNextHeight = minPercent;
                newCurrentHeight = currentInitial + nextInitial - minPercent;
            }

            setPanes(prev => prev.map(p => {
                if (p.id === currentPane.id) return { ...p, height: newCurrentHeight };
                if (p.id === nextPane.id) return { ...p, height: newNextHeight };
                return p;
            }));
        };

        const handleMouseUp = () => {
            setDragState({
                isDragging: false,
                paneId: null,
                startY: 0,
                initialHeights: {},
            });
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [dragState, panes]);

    // Add indicator to a pane
    const addIndicatorToPane = useCallback((paneId: string, indicatorId: string) => {
        setPanes(prev => prev.map(p =>
            p.id === paneId
                ? { ...p, indicators: [...(p.indicators || []), indicatorId] }
                : p
        ));
    }, []);

    // Remove indicator from a pane
    const removeIndicatorFromPane = useCallback((paneId: string, indicatorId: string) => {
        setPanes(prev => prev.map(p =>
            p.id === paneId
                ? { ...p, indicators: (p.indicators || []).filter(i => i !== indicatorId) }
                : p
        ));
    }, []);

    return {
        panes,
        containerRef,
        addPane,
        removePane,
        toggleCollapse,
        startDrag,
        addIndicatorToPane,
        removeIndicatorFromPane,
        isDragging: dragState.isDragging,
    };
}

// =============================================================================
// MULTI-PANE CHART COMPONENT
// =============================================================================

interface MultiPaneChartProps {
    totalHeight: number;
    children: (panes: ChartPane[], paneIndex: number) => React.ReactNode;
    onAddIndicator?: (indicatorId: string) => void;
}

export function MultiPaneChart({
    totalHeight,
    children,
    onAddIndicator,
}: MultiPaneChartProps) {
    const {
        panes,
        containerRef,
        addPane,
        removePane,
        toggleCollapse,
        startDrag,
        isDragging,
    } = useMultiPane();

    const calculatePixelHeight = (pane: ChartPane): number => {
        if (pane.collapsed) return 24;
        const nonCollapsedPanes = panes.filter(p => !p.collapsed);
        const totalPercentage = nonCollapsedPanes.reduce((sum, p) => sum + p.height, 0);
        const availableHeight = totalHeight - (panes.length * 24); // Subtract headers
        return Math.max(pane.minHeight, (pane.height / totalPercentage) * availableHeight + 24);
    };

    return (
        <div
            ref={containerRef}
            className="flex flex-col w-full relative"
            style={{
                height: totalHeight,
                cursor: isDragging ? 'row-resize' : 'default',
                userSelect: isDragging ? 'none' : 'auto',
            }}
        >
            {panes.map((pane, index) => (
                <ChartPaneContainer
                    key={pane.id}
                    pane={pane}
                    height={calculatePixelHeight(pane)}
                    isFirst={index === 0}
                    isLast={index === panes.length - 1}
                    onResize={() => {}}
                    onClose={removePane}
                    onToggleCollapse={toggleCollapse}
                    onDragStart={startDrag}
                >
                    {children(panes, index)}
                </ChartPaneContainer>
            ))}

            {/* Add Pane Button */}
            <div
                className="absolute bottom-2 right-2 flex gap-1"
                style={{ zIndex: 10 }}
            >
                <button
                    onClick={() => addPane('indicator', 'rsi')}
                    className="px-2 py-1 text-xs font-mono rounded transition-all hover:scale-105"
                    style={{
                        background: CHART_THEME.bgSecondary,
                        color: CHART_THEME.textSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                    }}
                    title="Add RSI Pane"
                >
                    + RSI
                </button>
                <button
                    onClick={() => addPane('indicator', 'macd')}
                    className="px-2 py-1 text-xs font-mono rounded transition-all hover:scale-105"
                    style={{
                        background: CHART_THEME.bgSecondary,
                        color: CHART_THEME.textSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                    }}
                    title="Add MACD Pane"
                >
                    + MACD
                </button>
                <button
                    onClick={() => addPane('indicator', 'stochastic')}
                    className="px-2 py-1 text-xs font-mono rounded transition-all hover:scale-105"
                    style={{
                        background: CHART_THEME.bgSecondary,
                        color: CHART_THEME.textSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                    }}
                    title="Add Stochastic Pane"
                >
                    + STOCH
                </button>
            </div>
        </div>
    );
}

// =============================================================================
// PANE LAYOUT PRESETS
// =============================================================================

export const PANE_PRESETS = {
    priceOnly: [
        { id: 'price', type: 'price' as const, title: 'Price', height: 100, minHeight: 200, collapsed: false },
    ],
    priceVolume: [
        { id: 'price', type: 'price' as const, title: 'Price', height: 75, minHeight: 150, collapsed: false },
        { id: 'volume', type: 'volume' as const, title: 'Volume', height: 25, minHeight: 60, collapsed: false },
    ],
    priceVolumeRSI: [
        { id: 'price', type: 'price' as const, title: 'Price', height: 55, minHeight: 150, collapsed: false },
        { id: 'volume', type: 'volume' as const, title: 'Volume', height: 20, minHeight: 50, collapsed: false },
        { id: 'rsi', type: 'indicator' as const, title: 'RSI', height: 25, minHeight: 60, collapsed: false, indicators: ['rsi'] },
    ],
    priceMACD: [
        { id: 'price', type: 'price' as const, title: 'Price', height: 65, minHeight: 150, collapsed: false },
        { id: 'macd', type: 'indicator' as const, title: 'MACD', height: 35, minHeight: 80, collapsed: false, indicators: ['macd'] },
    ],
    full: [
        { id: 'price', type: 'price' as const, title: 'Price', height: 45, minHeight: 150, collapsed: false },
        { id: 'volume', type: 'volume' as const, title: 'Volume', height: 15, minHeight: 50, collapsed: false },
        { id: 'rsi', type: 'indicator' as const, title: 'RSI', height: 20, minHeight: 60, collapsed: false, indicators: ['rsi'] },
        { id: 'macd', type: 'indicator' as const, title: 'MACD', height: 20, minHeight: 60, collapsed: false, indicators: ['macd'] },
    ],
};

export default MultiPaneChart;
