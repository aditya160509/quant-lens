/**
 * Multi-Chart Workspace V2
 * Built with:
 * - lightweight-charts (TradingView's official library)
 * - Zustand store (unified state management)
 * 
 * Per CHART_ENGINE_SPEC.md and CHART_WORKSPACE_TECHNICAL_AUDIT_REPORT.md
 * 
 * Features:
 * - Synchronized crosshairs across all panels
 * - CSS Grid layouts (per Section 2)
 * - Shared data cache to prevent redundant API calls
 * - Link groups for symbol/timeframe sync
 */

'use client';

import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { CHART_THEME, type Timeframe } from './types';
import {
    useChartWorkspaceStore,
    selectLayout,
    selectPanels,
    selectActiveChartId,
    selectSyncSettings,
    selectCrosshairTimestamp,
    selectFullscreenPanel,
    LAYOUT_PRESETS,
    LINK_GROUP_COLORS,
    type ChartPanelState,
} from './store/chartWorkspaceStore';
import { useStableDimensions } from './StableChartContainer';
import { ChartProvider } from './state/ChartContext';

// Dynamically import the new lightweight-charts canvas
const LightweightChartCanvas = dynamic(
    () => import('./LightweightChartCanvas'),
    { ssr: false, loading: () => <ChartLoadingState /> }
);

// =============================================================================
// LOADING STATE
// =============================================================================

function ChartLoadingState() {
    return (
        <div
            style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: CHART_THEME.bgPrimary,
                color: CHART_THEME.textSecondary,
                fontSize: '13px',
                fontFamily: CHART_THEME.fontMono,
            }}
        >
            Loading chart...
        </div>
    );
}

// =============================================================================
// CHART PANEL COMPONENT (uses lightweight-charts)
// =============================================================================

interface ChartPanelProps {
    panel: ChartPanelState;
    isActive: boolean;
    syncedCrosshairTimestamp: number | null;
    onCrosshairMove: (timestamp: number | null) => void;
}

function ChartPanel({ panel, isActive, syncedCrosshairTimestamp, onCrosshairMove }: ChartPanelProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const dimensions = useStableDimensions(containerRef);
    
    const {
        updatePanelSymbol,
        updatePanelTimeframe,
        setActiveChart,
        toggleFullscreen,
        linkGroups,
    } = useChartWorkspaceStore();

    // Get link group color if linked
    const linkGroupColor = useMemo(() => {
        if (!panel.linkGroupId) return null;
        const group = linkGroups.find(g => g.id === panel.linkGroupId);
        return group?.color || null;
    }, [panel.linkGroupId, linkGroups]);

    return (
        <ChartProvider initialSymbol={panel.symbol} initialTimeframe={panel.timeframe}>
            <div
                ref={containerRef}
                onClick={() => setActiveChart(panel.id)}
                style={{
                    position: 'relative',
                    width: '100%',
                    height: '100%',
                    background: CHART_THEME.bgPrimary,
                    border: `1px solid ${isActive ? CHART_THEME.accent : CHART_THEME.border}`,
                    borderRadius: '4px',
                    overflow: 'hidden',
                    cursor: 'pointer',
                }}
            >
                {/* Link indicator */}
                {linkGroupColor && (
                    <div
                        style={{
                            position: 'absolute',
                            top: '4px',
                            left: '4px',
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            background: linkGroupColor,
                            zIndex: 10,
                            boxShadow: `0 0 6px ${linkGroupColor}`,
                        }}
                        title={`Linked: ${panel.linkGroupId}`}
                    />
                )}

                {/* Panel Header */}
                <div
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '28px',
                        background: 'linear-gradient(180deg, rgba(0,0,0,0.6) 0%, transparent 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0 8px',
                        zIndex: 5,
                    }}
                >
                    <span style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        color: CHART_THEME.textPrimary,
                        fontFamily: CHART_THEME.fontMono,
                    }}>
                        {panel.symbol} · {panel.timeframe.toUpperCase()}
                    </span>

                    <div style={{ display: 'flex', gap: '4px' }}>
                        {/* Fullscreen button */}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                toggleFullscreen(panel.id);
                            }}
                            style={{
                                width: '20px',
                                height: '20px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                color: CHART_THEME.textSecondary,
                                borderRadius: '3px',
                            }}
                            title="Fullscreen"
                        >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3" />
                            </svg>
                        </button>
                    </div>
                </div>

                {/* Chart Canvas (using lightweight-charts) */}
                {dimensions.width > 0 && dimensions.height > 0 && (
                    <LightweightChartCanvas
                        width={dimensions.width}
                        height={dimensions.height - 28} // Subtract header height
                        syncedCrosshairTimestamp={syncedCrosshairTimestamp}
                        onCrosshairMove={onCrosshairMove}
                    />
                )}
            </div>
        </ChartProvider>
    );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

interface MultiChartWorkspaceV2Props {
    height?: number | string;
}

export function MultiChartWorkspaceV2({ height = '100%' }: MultiChartWorkspaceV2Props) {
    // Use Zustand selectors for optimized re-renders
    const layout = useChartWorkspaceStore(selectLayout);
    const panels = useChartWorkspaceStore(selectPanels);
    const activeChartId = useChartWorkspaceStore(selectActiveChartId);
    const syncSettings = useChartWorkspaceStore(selectSyncSettings);
    const crosshairTimestamp = useChartWorkspaceStore(selectCrosshairTimestamp);
    const fullscreenPanel = useChartWorkspaceStore(selectFullscreenPanel);
    
    const {
        setLayout,
        setSyncSettings,
        broadcastCrosshair,
        toggleFullscreen,
    } = useChartWorkspaceStore();

    const gridConfig = useMemo(() => LAYOUT_PRESETS[layout], [layout]);

    // Handle crosshair sync
    const handleCrosshairMove = useCallback((panelId: string, timestamp: number | null) => {
        if (syncSettings.crosshair) {
            broadcastCrosshair(timestamp);
        }
    }, [syncSettings.crosshair, broadcastCrosshair]);

    // Render fullscreen overlay if a panel is fullscreen
    if (fullscreenPanel) {
        return (
            <div
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    zIndex: 9999,
                    background: CHART_THEME.bgPrimary,
                }}
            >
                <ChartPanel
                    panel={fullscreenPanel}
                    isActive={true}
                    syncedCrosshairTimestamp={null}
                    onCrosshairMove={(ts) => handleCrosshairMove(fullscreenPanel.id, ts)}
                />
            </div>
        );
    }

    return (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                height: typeof height === 'number' ? `${height}px` : height,
                background: CHART_THEME.bgSecondary,
            }}
        >
            {/* Toolbar */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    background: CHART_THEME.bgPrimary,
                    borderBottom: `1px solid ${CHART_THEME.border}`,
                }}
            >
                {/* Layout buttons */}
                <div style={{ display: 'flex', gap: '4px' }}>
                    {(['1', '2h', '2v', '4', '6'] as const).map((l) => (
                        <button
                            key={l}
                            onClick={() => setLayout(l)}
                            style={{
                                padding: '4px 8px',
                                background: layout === l ? CHART_THEME.accent : 'transparent',
                                color: layout === l ? CHART_THEME.bgPrimary : CHART_THEME.textSecondary,
                                border: `1px solid ${layout === l ? CHART_THEME.accent : CHART_THEME.border}`,
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontFamily: CHART_THEME.fontMono,
                                cursor: 'pointer',
                            }}
                        >
                            {l === '1' ? '1×1' : l === '2h' ? '2×1' : l === '2v' ? '1×2' : l === '4' ? '2×2' : '3×2'}
                        </button>
                    ))}
                </div>
                
                {/* Sync toggle */}
                <button
                    onClick={() => setSyncSettings({ crosshair: !syncSettings.crosshair })}
                    style={{
                        padding: '4px 8px',
                        background: syncSettings.crosshair ? 'rgba(0, 255, 136, 0.15)' : 'transparent',
                        color: syncSettings.crosshair ? CHART_THEME.upColor : CHART_THEME.textSecondary,
                        border: `1px solid ${syncSettings.crosshair ? CHART_THEME.upColor : CHART_THEME.border}`,
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontFamily: CHART_THEME.fontMono,
                        cursor: 'pointer',
                    }}
                >
                    {syncSettings.crosshair ? '✓ Sync' : 'Sync'}
                </button>
            </div>

            {/* Grid Container (per CHART_ENGINE_SPEC.md Section 2: CSS Grid) */}
            <div
                style={{
                    flex: 1,
                    display: 'grid',
                    gridTemplateRows: `repeat(${gridConfig.rows}, 1fr)`,
                    gridTemplateColumns: `repeat(${gridConfig.cols}, 1fr)`,
                    gap: '2px',
                    padding: '2px',
                    minHeight: 0,
                }}
            >
                {panels.map((panel, idx) => {
                    const cell = gridConfig.cells[idx];
                    if (!cell) return null;

                    return (
                        <div
                            key={panel.id}
                            style={{
                                gridRow: `${cell.row + 1} / span ${cell.rowSpan || 1}`,
                                gridColumn: `${cell.col + 1} / span ${cell.colSpan || 1}`,
                                minHeight: 0,
                                minWidth: 0,
                            }}
                        >
                            <ChartPanel
                                panel={panel}
                                isActive={activeChartId === panel.id}
                                syncedCrosshairTimestamp={
                                    syncSettings.crosshair && activeChartId !== panel.id
                                        ? crosshairTimestamp
                                        : null
                                }
                                onCrosshairMove={(ts) => handleCrosshairMove(panel.id, ts)}
                            />
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default MultiChartWorkspaceV2;
