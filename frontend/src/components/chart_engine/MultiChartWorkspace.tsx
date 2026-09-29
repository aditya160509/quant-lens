/**
 * Multi-Chart Workspace
 * TradingView-style grid layout container for multiple synchronized charts
 */

'use client';

import React, { useMemo, useCallback, createContext, useContext } from 'react';
import dynamic from 'next/dynamic';
import { CHART_THEME, type Timeframe } from './types';
import { 
    type LayoutPreset, 
    type ChartPanelState, 
    type SyncSettings,
    LAYOUT_PRESETS,
    LINK_GROUP_COLORS,
} from './workspaceTypes';
import { useMultiChartWorkspace, type UseMultiChartWorkspace } from './useMultiChartWorkspace';
import { LayoutSelector } from './LayoutSelector';

// Dynamically import the chart core to avoid SSR issues
const Q360ChartCore = dynamic(
    () => import('./q360_chart_core'),
    { ssr: false, loading: () => <ChartLoadingState /> }
);

// =============================================================================
// CONTEXT
// =============================================================================

const WorkspaceContext = createContext<UseMultiChartWorkspace | null>(null);

export function useWorkspace() {
    const context = useContext(WorkspaceContext);
    if (!context) {
        throw new Error('useWorkspace must be used within MultiChartWorkspace');
    }
    return context;
}

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
// CHART PANEL COMPONENT
// =============================================================================

interface ChartPanelProps {
    panel: ChartPanelState;
    isActive: boolean;
    syncedCrosshairTimestamp: number | null;
    onSymbolChange: (symbol: string) => void;
    onTimeframeChange: (timeframe: Timeframe) => void;
    onCrosshairMove: (timestamp: number | null) => void;
    onActivate: () => void;
    onToggleFullscreen: () => void;
}

function ChartPanel({
    panel,
    isActive,
    syncedCrosshairTimestamp,
    onSymbolChange,
    onTimeframeChange,
    onCrosshairMove,
    onActivate,
    onToggleFullscreen,
}: ChartPanelProps) {
    const workspace = useWorkspace();
    
    // Get link group color if linked
    const linkGroupColor = useMemo(() => {
        if (!panel.linkGroupId) return null;
        const group = workspace.linkGroups.find(g => g.id === panel.linkGroupId);
        return group?.color || null;
    }, [panel.linkGroupId, workspace.linkGroups]);

    return (
        <div
            onClick={onActivate}
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
                            onToggleFullscreen();
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

            {/* Chart */}
            <Q360ChartCore
                symbol={panel.symbol}
                timeframe={panel.timeframe}
                mode="intraday"
                height="100%"
                width="100%"
                onSymbolChange={onSymbolChange}
                onTimeframeChange={onTimeframeChange}
                onIndicatorsChange={() => {}}
                isMemberOfGrid={true}
                syncedCrosshairTimestamp={syncedCrosshairTimestamp}
                onCrosshairMove={onCrosshairMove}
            />
        </div>
    );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

interface MultiChartWorkspaceProps {
    height?: number | string;
}

export function MultiChartWorkspace({ height = '100%' }: MultiChartWorkspaceProps) {
    const workspace = useMultiChartWorkspace();
    const {
        layout,
        panels,
        syncSettings,
        activeChartId,
        crosshairTimestamp,
        fullscreenPanel,
        setLayout,
        updatePanelSymbol,
        updatePanelTimeframe,
        setActiveChart,
        toggleFullscreen,
        setSyncSettings,
        broadcastCrosshair,
    } = workspace;

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
            <WorkspaceContext.Provider value={workspace}>
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
                        onSymbolChange={(symbol) => updatePanelSymbol(fullscreenPanel.id, symbol)}
                        onTimeframeChange={(tf) => updatePanelTimeframe(fullscreenPanel.id, tf)}
                        onCrosshairMove={(ts) => handleCrosshairMove(fullscreenPanel.id, ts)}
                        onActivate={() => {}}
                        onToggleFullscreen={() => toggleFullscreen(fullscreenPanel.id)}
                    />
                </div>
            </WorkspaceContext.Provider>
        );
    }

    return (
        <WorkspaceContext.Provider value={workspace}>
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
                        justifyContent: 'flex-end',
                        padding: '8px 12px',
                        background: CHART_THEME.bgPrimary,
                        borderBottom: `1px solid ${CHART_THEME.border}`,
                    }}
                >
                    <LayoutSelector
                        currentLayout={layout}
                        onLayoutChange={setLayout}
                        syncSettings={syncSettings}
                        onSyncSettingsChange={setSyncSettings}
                    />
                </div>

                {/* Grid Container */}
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
                                    onSymbolChange={(symbol) => updatePanelSymbol(panel.id, symbol)}
                                    onTimeframeChange={(tf) => updatePanelTimeframe(panel.id, tf)}
                                    onCrosshairMove={(ts) => handleCrosshairMove(panel.id, ts)}
                                    onActivate={() => setActiveChart(panel.id)}
                                    onToggleFullscreen={() => toggleFullscreen(panel.id)}
                                />
                            </div>
                        );
                    })}
                </div>
            </div>
        </WorkspaceContext.Provider>
    );
}

export default MultiChartWorkspace;
