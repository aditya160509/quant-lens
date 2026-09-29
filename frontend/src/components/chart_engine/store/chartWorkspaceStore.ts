/**
 * Chart Workspace Store (Zustand)
 * Per CHART_WORKSPACE_TECHNICAL_AUDIT_REPORT.md Section 4:
 * "We need a unified ChartWorkspaceStore to prevent the 'State War' between 
 * Workspace and individual Panels."
 * 
 * This Zustand store provides:
 * 1. Unified state management for all chart panels
 * 2. Crosshair synchronization broadcasting
 * 3. Shared data cache to prevent redundant API calls (Section 3: "Lifting the Cache")
 * 4. Layout management
 * 5. Link group management for symbol/timeframe sync
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type { Timeframe, OHLCVBar, SeriesData } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export interface ChartPanelState {
    id: string;
    symbol: string;
    timeframe: Timeframe;
    linkGroupId?: string;
}

export interface SyncSettings {
    crosshair: boolean;
    timeframe: boolean;
    symbol: boolean;
    zoom: boolean;
}

export interface LinkGroup {
    id: string;
    color: string;
    panelIds: string[];
}

export type LayoutPreset = 
    | '1' | '2h' | '2v' | '3h' | '3v' | '3l' | '3r' 
    | '4' | '5' | '6' | '8';

export interface LayoutConfig {
    rows: number;
    cols: number;
    cells: Array<{ row: number; col: number; rowSpan?: number; colSpan?: number }>;
}

// =============================================================================
// LAYOUT PRESETS (CSS Grid configurations)
// =============================================================================

export const LAYOUT_PRESETS: Record<LayoutPreset, LayoutConfig> = {
    '1': { rows: 1, cols: 1, cells: [{ row: 0, col: 0 }] },
    '2h': { rows: 2, cols: 1, cells: [{ row: 0, col: 0 }, { row: 1, col: 0 }] },
    '2v': { rows: 1, cols: 2, cells: [{ row: 0, col: 0 }, { row: 0, col: 1 }] },
    '3h': { rows: 3, cols: 1, cells: [{ row: 0, col: 0 }, { row: 1, col: 0 }, { row: 2, col: 0 }] },
    '3v': { rows: 1, cols: 3, cells: [{ row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }] },
    '3l': { rows: 2, cols: 2, cells: [{ row: 0, col: 0, rowSpan: 2 }, { row: 0, col: 1 }, { row: 1, col: 1 }] },
    '3r': { rows: 2, cols: 2, cells: [{ row: 0, col: 0 }, { row: 1, col: 0 }, { row: 0, col: 1, rowSpan: 2 }] },
    '4': { rows: 2, cols: 2, cells: [{ row: 0, col: 0 }, { row: 0, col: 1 }, { row: 1, col: 0 }, { row: 1, col: 1 }] },
    '5': { rows: 2, cols: 3, cells: [
        { row: 0, col: 0, colSpan: 2 },
        { row: 0, col: 2 },
        { row: 1, col: 0 },
        { row: 1, col: 1 },
        { row: 1, col: 2 },
    ]},
    '6': { rows: 3, cols: 2, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 },
        { row: 1, col: 0 }, { row: 1, col: 1 },
        { row: 2, col: 0 }, { row: 2, col: 1 },
    ]},
    '8': { rows: 2, cols: 4, cells: [
        { row: 0, col: 0 }, { row: 0, col: 1 }, { row: 0, col: 2 }, { row: 0, col: 3 },
        { row: 1, col: 0 }, { row: 1, col: 1 }, { row: 1, col: 2 }, { row: 1, col: 3 },
    ]},
};

// =============================================================================
// LINK GROUP COLORS
// =============================================================================

export const LINK_GROUP_COLORS = [
    '#ef4444', // Red
    '#f97316', // Orange
    '#eab308', // Yellow
    '#22c55e', // Green
    '#06b6d4', // Cyan
    '#3b82f6', // Blue
    '#8b5cf6', // Purple
    '#ec4899', // Pink
];

// =============================================================================
// STORE INTERFACE
// =============================================================================

interface ChartWorkspaceState {
    // Layout
    layout: LayoutPreset;
    panels: ChartPanelState[];
    activeChartId: string | null;
    fullscreenPanelId: string | null;

    // Sync settings
    syncSettings: SyncSettings;
    linkGroups: LinkGroup[];

    // Crosshair sync
    crosshairTimestamp: number | null;

    // Shared Data Cache (per audit report Section 3: "Lifting the Cache")
    dataCache: Map<string, { data: SeriesData; fetchedAt: number }>;

    // Actions
    setLayout: (layout: LayoutPreset) => void;
    addPanel: (symbol: string, timeframe: Timeframe) => void;
    removePanel: (panelId: string) => void;
    updatePanelSymbol: (panelId: string, symbol: string) => void;
    updatePanelTimeframe: (panelId: string, timeframe: Timeframe) => void;
    setActiveChart: (panelId: string | null) => void;
    toggleFullscreen: (panelId: string) => void;
    setSyncSettings: (settings: Partial<SyncSettings>) => void;
    broadcastCrosshair: (timestamp: number | null) => void;

    // Link groups
    createLinkGroup: (panelIds: string[]) => void;
    addToLinkGroup: (panelId: string, groupId: string) => void;
    removeFromLinkGroup: (panelId: string) => void;

    // Data cache operations
    getCachedData: (symbol: string, timeframe: Timeframe) => SeriesData | null;
    setCachedData: (symbol: string, timeframe: Timeframe, data: SeriesData) => void;
    clearCache: () => void;
}

// =============================================================================
// HELPER: Generate unique ID
// =============================================================================

function generateId(): string {
    return `panel_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// =============================================================================
// CREATE STORE
// =============================================================================

export const useChartWorkspaceStore = create<ChartWorkspaceState>()(
    subscribeWithSelector((set, get) => ({
        // Initial state
        layout: '1' as LayoutPreset,
        panels: [{ id: 'main', symbol: 'SPY', timeframe: '5m' as Timeframe }],
        activeChartId: 'main',
        fullscreenPanelId: null,
        syncSettings: {
            crosshair: true,
            timeframe: false,
            symbol: false,
            zoom: false,
        },
        linkGroups: [],
        crosshairTimestamp: null,
        dataCache: new Map(),

        // Layout actions
        setLayout: (layout) => {
            const config = LAYOUT_PRESETS[layout];
            const currentPanels = get().panels;
            const requiredPanels = config.cells.length;

            let newPanels = [...currentPanels];

            // Add panels if needed
            while (newPanels.length < requiredPanels) {
                newPanels.push({
                    id: generateId(),
                    symbol: 'SPY',
                    timeframe: '5m' as Timeframe,
                });
            }

            // Remove excess panels if needed
            if (newPanels.length > requiredPanels) {
                newPanels = newPanels.slice(0, requiredPanels);
            }

            set({ layout, panels: newPanels });
        },

        addPanel: (symbol, timeframe) => {
            const newPanel: ChartPanelState = {
                id: generateId(),
                symbol,
                timeframe,
            };
            set(state => ({ panels: [...state.panels, newPanel] }));
        },

        removePanel: (panelId) => {
            set(state => ({
                panels: state.panels.filter(p => p.id !== panelId),
                activeChartId: state.activeChartId === panelId ? null : state.activeChartId,
            }));
        },

        updatePanelSymbol: (panelId, symbol) => {
            const state = get();
            const panel = state.panels.find(p => p.id === panelId);
            
            // Update the panel
            set(state => ({
                panels: state.panels.map(p =>
                    p.id === panelId ? { ...p, symbol } : p
                ),
            }));

            // If symbol sync is enabled and panel is in a link group, update all linked panels
            if (panel?.linkGroupId && state.syncSettings.symbol) {
                const group = state.linkGroups.find(g => g.id === panel.linkGroupId);
                if (group) {
                    set(state => ({
                        panels: state.panels.map(p =>
                            group.panelIds.includes(p.id) ? { ...p, symbol } : p
                        ),
                    }));
                }
            }
        },

        updatePanelTimeframe: (panelId, timeframe) => {
            const state = get();
            const panel = state.panels.find(p => p.id === panelId);

            // Update the panel
            set(state => ({
                panels: state.panels.map(p =>
                    p.id === panelId ? { ...p, timeframe } : p
                ),
            }));

            // If timeframe sync is enabled and panel is in a link group, update all linked panels
            if (panel?.linkGroupId && state.syncSettings.timeframe) {
                const group = state.linkGroups.find(g => g.id === panel.linkGroupId);
                if (group) {
                    set(state => ({
                        panels: state.panels.map(p =>
                            group.panelIds.includes(p.id) ? { ...p, timeframe } : p
                        ),
                    }));
                }
            }
        },

        setActiveChart: (panelId) => {
            set({ activeChartId: panelId });
        },

        toggleFullscreen: (panelId) => {
            set(state => ({
                fullscreenPanelId: state.fullscreenPanelId === panelId ? null : panelId,
            }));
        },

        setSyncSettings: (settings) => {
            set(state => ({
                syncSettings: { ...state.syncSettings, ...settings },
            }));
        },

        broadcastCrosshair: (timestamp) => {
            set({ crosshairTimestamp: timestamp });
        },

        // Link group management
        createLinkGroup: (panelIds) => {
            const usedColors = get().linkGroups.map(g => g.color);
            const availableColor = LINK_GROUP_COLORS.find(c => !usedColors.includes(c)) 
                || LINK_GROUP_COLORS[0];

            const newGroup: LinkGroup = {
                id: `link_${Date.now()}`,
                color: availableColor,
                panelIds,
            };

            set(state => ({
                linkGroups: [...state.linkGroups, newGroup],
                panels: state.panels.map(p =>
                    panelIds.includes(p.id) ? { ...p, linkGroupId: newGroup.id } : p
                ),
            }));
        },

        addToLinkGroup: (panelId, groupId) => {
            set(state => ({
                linkGroups: state.linkGroups.map(g =>
                    g.id === groupId ? { ...g, panelIds: [...g.panelIds, panelId] } : g
                ),
                panels: state.panels.map(p =>
                    p.id === panelId ? { ...p, linkGroupId: groupId } : p
                ),
            }));
        },

        removeFromLinkGroup: (panelId) => {
            set(state => ({
                linkGroups: state.linkGroups.map(g => ({
                    ...g,
                    panelIds: g.panelIds.filter(id => id !== panelId),
                })).filter(g => g.panelIds.length > 0),
                panels: state.panels.map(p =>
                    p.id === panelId ? { ...p, linkGroupId: undefined } : p
                ),
            }));
        },

        // Data cache (per audit report: "Lifting the Cache")
        getCachedData: (symbol, timeframe) => {
            const cacheKey = `${symbol}:${timeframe}`;
            const cached = get().dataCache.get(cacheKey);
            
            if (!cached) return null;
            
            // Cache valid for 5 minutes
            const isExpired = Date.now() - cached.fetchedAt > 5 * 60 * 1000;
            if (isExpired) {
                get().dataCache.delete(cacheKey);
                return null;
            }
            
            return cached.data;
        },

        setCachedData: (symbol, timeframe, data) => {
            const cacheKey = `${symbol}:${timeframe}`;
            set(state => {
                const newCache = new Map(state.dataCache);
                newCache.set(cacheKey, { data, fetchedAt: Date.now() });
                return { dataCache: newCache };
            });
        },

        clearCache: () => {
            set({ dataCache: new Map() });
        },
    }))
);

// =============================================================================
// SELECTORS (for optimized re-renders)
// =============================================================================

export const selectLayout = (state: ChartWorkspaceState) => state.layout;
export const selectPanels = (state: ChartWorkspaceState) => state.panels;
export const selectActiveChartId = (state: ChartWorkspaceState) => state.activeChartId;
export const selectSyncSettings = (state: ChartWorkspaceState) => state.syncSettings;
export const selectCrosshairTimestamp = (state: ChartWorkspaceState) => state.crosshairTimestamp;
export const selectFullscreenPanelId = (state: ChartWorkspaceState) => state.fullscreenPanelId;

export const selectPanelById = (panelId: string) => (state: ChartWorkspaceState) =>
    state.panels.find(p => p.id === panelId);

export const selectFullscreenPanel = (state: ChartWorkspaceState) =>
    state.fullscreenPanelId ? state.panels.find(p => p.id === state.fullscreenPanelId) : null;
