/**
 * Multi-Chart Workspace Types
 * TradingView-inspired layout system for multiple synchronized charts
 */

import type { Timeframe, ChartConfig, Drawing, IndicatorConfig } from './types';

// =============================================================================
// LAYOUT TYPES
// =============================================================================

export type LayoutPreset = 
    | '1x1' 
    | '1x2' 
    | '2x1' 
    | '2x2' 
    | '1x3' 
    | '3x1'
    | '2x3' 
    | '3x2' 
    | '1x4'
    | '4x1'
    | '2x4'
    | '4x2'
    | '3x3'
    | '3x4'
    | '4x3'
    | '4x4';

export interface LayoutCell {
    row: number;
    col: number;
    rowSpan?: number;
    colSpan?: number;
}

export interface GridLayout {
    rows: number;
    cols: number;
    cells: LayoutCell[];
}

// Predefined layout configurations (matches TradingView screenshot)
export const LAYOUT_PRESETS: Record<LayoutPreset, GridLayout> = {
    '1x1': { rows: 1, cols: 1, cells: [{ row: 0, col: 0 }] },
    '1x2': { rows: 1, cols: 2, cells: [{ row: 0, col: 0 }, { row: 0, col: 1 }] },
    '2x1': { rows: 2, cols: 1, cells: [{ row: 0, col: 0 }, { row: 1, col: 0 }] },
    '2x2': { rows: 2, cols: 2, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 },
        { row: 1, col: 0 }, { row: 1, col: 1 }
    ]},
    '1x3': { rows: 1, cols: 3, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }
    ]},
    '3x1': { rows: 3, cols: 1, cells: [
        { row: 0, col: 0 }, { row: 1, col: 0 }, { row: 2, col: 0 }
    ]},
    '2x3': { rows: 2, cols: 3, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 },
        { row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }
    ]},
    '3x2': { rows: 3, cols: 2, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 },
        { row: 1, col: 0 }, { row: 1, col: 1 },
        { row: 2, col: 0 }, { row: 2, col: 1 }
    ]},
    '1x4': { rows: 1, cols: 4, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }, { row: 0, col: 3 }
    ]},
    '4x1': { rows: 4, cols: 1, cells: [
        { row: 0, col: 0 }, { row: 1, col: 0 }, { row: 2, col: 0 }, { row: 3, col: 0 }
    ]},
    '2x4': { rows: 2, cols: 4, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }, { row: 0, col: 3 },
        { row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }, { row: 1, col: 3 }
    ]},
    '4x2': { rows: 4, cols: 2, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 },
        { row: 1, col: 0 }, { row: 1, col: 1 },
        { row: 2, col: 0 }, { row: 2, col: 1 },
        { row: 3, col: 0 }, { row: 3, col: 1 }
    ]},
    '3x3': { rows: 3, cols: 3, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 },
        { row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 },
        { row: 2, col: 0 }, { row: 2, col: 1 }, { row: 2, col: 2 }
    ]},
    '3x4': { rows: 3, cols: 4, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }, { row: 0, col: 3 },
        { row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }, { row: 1, col: 3 },
        { row: 2, col: 0 }, { row: 2, col: 1 }, { row: 2, col: 2 }, { row: 2, col: 3 }
    ]},
    '4x3': { rows: 4, cols: 3, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 },
        { row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 },
        { row: 2, col: 0 }, { row: 2, col: 1 }, { row: 2, col: 2 },
        { row: 3, col: 0 }, { row: 3, col: 1 }, { row: 3, col: 2 }
    ]},
    '4x4': { rows: 4, cols: 4, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }, { row: 0, col: 3 },
        { row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }, { row: 1, col: 3 },
        { row: 2, col: 0 }, { row: 2, col: 1 }, { row: 2, col: 2 }, { row: 2, col: 3 },
        { row: 3, col: 0 }, { row: 3, col: 1 }, { row: 3, col: 2 }, { row: 3, col: 3 }
    ]},
};

// =============================================================================
// CHART PANEL TYPES
// =============================================================================

export interface ChartPanelState {
    id: string;
    symbol: string;
    timeframe: Timeframe;
    chartConfig: ChartConfig;
    indicators: IndicatorConfig[];
    drawings: Drawing[];
    linkGroupId: string | null;   // For syncing with other charts
    isFullscreen: boolean;
    zoomLevel: number;
    panOffset: number;
}

// =============================================================================
// LINK GROUP TYPES (for chart synchronization)
// =============================================================================

export type LinkType = 'symbol' | 'timeframe' | 'crosshair' | 'time' | 'dateRange';

export interface LinkGroup {
    id: string;
    color: string;   // Visual indicator color
    linkedTypes: LinkType[];   // What aspects are synced
    chartIds: string[];
}

export interface SyncSettings {
    symbol: boolean;
    interval: boolean;
    crosshair: boolean;
    time: boolean;
    dateRange: boolean;
}

// Default colors for link groups (TradingView style)
export const LINK_GROUP_COLORS = [
    '#ff5252',  // Red
    '#ff9800',  // Orange
    '#ffeb3b',  // Yellow
    '#4caf50',  // Green
    '#2196f3',  // Blue
    '#9c27b0',  // Purple
    '#00bcd4',  // Cyan
    '#e91e63',  // Pink
];

// =============================================================================
// WORKSPACE STATE
// =============================================================================

export interface WorkspaceState {
    id: string;
    name: string;
    layout: LayoutPreset;
    panels: ChartPanelState[];
    linkGroups: LinkGroup[];
    syncSettings: SyncSettings;
    activeChartId: string | null;
    crosshairTimestamp: number | null;  // For synchronized crosshairs
    createdAt: number;
    updatedAt: number;
}

// =============================================================================
// WORKSPACE ACTIONS
// =============================================================================

export type WorkspaceAction =
    | { type: 'SET_LAYOUT'; payload: LayoutPreset }
    | { type: 'ADD_PANEL'; payload: ChartPanelState }
    | { type: 'REMOVE_PANEL'; payload: string }
    | { type: 'UPDATE_PANEL'; payload: Partial<ChartPanelState> & { id: string } }
    | { type: 'SET_PANEL_SYMBOL'; payload: { panelId: string; symbol: string } }
    | { type: 'SET_PANEL_TIMEFRAME'; payload: { panelId: string; timeframe: Timeframe } }
    | { type: 'SET_ACTIVE_CHART'; payload: string | null }
    | { type: 'TOGGLE_FULLSCREEN'; payload: string }
    | { type: 'CREATE_LINK_GROUP'; payload: LinkGroup }
    | { type: 'ADD_TO_LINK_GROUP'; payload: { groupId: string; chartId: string } }
    | { type: 'REMOVE_FROM_LINK_GROUP'; payload: { groupId: string; chartId: string } }
    | { type: 'DELETE_LINK_GROUP'; payload: string }
    | { type: 'SET_SYNC_SETTINGS'; payload: Partial<SyncSettings> }
    | { type: 'BROADCAST_CROSSHAIR'; payload: number | null }
    | { type: 'LOAD_WORKSPACE'; payload: WorkspaceState }
    | { type: 'RESET_WORKSPACE' };

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Generate a unique chart panel ID
 */
export function generatePanelId(): string {
    return `panel_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate a unique link group ID
 */
export function generateLinkGroupId(): string {
    return `link_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Create a default chart panel state
 */
export function createDefaultPanel(symbol: string = 'AAPL', timeframe: Timeframe = '1d'): ChartPanelState {
    return {
        id: generatePanelId(),
        symbol,
        timeframe,
        chartConfig: {
            chartType: 'candlestick',
            scaleMode: 'auto',
            showVolume: true,
            showGrid: true,
            sessionShading: false,
        },
        indicators: [],
        drawings: [],
        linkGroupId: null,
        isFullscreen: false,
        zoomLevel: 1,
        panOffset: 0,
    };
}

/**
 * Create a default workspace
 */
export function createDefaultWorkspace(name: string = 'Default'): WorkspaceState {
    return {
        id: `ws_${Date.now()}`,
        name,
        layout: '1x1',
        panels: [createDefaultPanel()],
        linkGroups: [],
        syncSettings: {
            symbol: false,
            interval: false,
            crosshair: true,
            time: false,
            dateRange: false,
        },
        activeChartId: null,
        crosshairTimestamp: null,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    };
}

/**
 * Get the number of panels for a layout
 */
export function getLayoutPanelCount(layout: LayoutPreset): number {
    return LAYOUT_PRESETS[layout].cells.length;
}

/**
 * Serialize workspace to JSON for localStorage
 */
export function serializeWorkspace(workspace: WorkspaceState): string {
    return JSON.stringify(workspace);
}

/**
 * Deserialize workspace from JSON
 */
export function deserializeWorkspace(json: string): WorkspaceState | null {
    try {
        return JSON.parse(json) as WorkspaceState;
    } catch {
        return null;
    }
}
