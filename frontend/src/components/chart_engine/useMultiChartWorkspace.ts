/**
 * Multi-Chart Workspace Hook
 * Manages workspace state, layout changes, and chart synchronization
 */

'use client';

import { useReducer, useCallback, useEffect, useMemo } from 'react';
import type { Timeframe } from './types';
import {
    type WorkspaceState,
    type WorkspaceAction,
    type ChartPanelState,
    type LinkGroup,
    type LayoutPreset,
    type SyncSettings,
    createDefaultWorkspace,
    createDefaultPanel,
    getLayoutPanelCount,
    generateLinkGroupId,
    LINK_GROUP_COLORS,
} from './workspaceTypes';

// =============================================================================
// CONSTANTS
// =============================================================================

const STORAGE_KEY = 'quant360_workspace';

function loadInitialWorkspace(): WorkspaceState {
    if (typeof window === 'undefined') return createDefaultWorkspace();

    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return createDefaultWorkspace();

    try {
        return JSON.parse(saved) as WorkspaceState;
    } catch {
        return createDefaultWorkspace();
    }
}

// =============================================================================
// REDUCER
// =============================================================================

function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
    switch (action.type) {
        case 'SET_LAYOUT': {
            const newLayout = action.payload;
            const requiredPanels = getLayoutPanelCount(newLayout);
            let panels = [...state.panels];

            // Add panels if needed
            while (panels.length < requiredPanels) {
                panels.push(createDefaultPanel());
            }

            // Remove panels if too many (keep first N)
            if (panels.length > requiredPanels) {
                panels = panels.slice(0, requiredPanels);
            }

            return {
                ...state,
                layout: newLayout,
                panels,
                updatedAt: Date.now(),
            };
        }

        case 'ADD_PANEL': {
            return {
                ...state,
                panels: [...state.panels, action.payload],
                updatedAt: Date.now(),
            };
        }

        case 'REMOVE_PANEL': {
            return {
                ...state,
                panels: state.panels.filter(p => p.id !== action.payload),
                updatedAt: Date.now(),
            };
        }

        case 'UPDATE_PANEL': {
            const { id, ...updates } = action.payload;
            return {
                ...state,
                panels: state.panels.map(p =>
                    p.id === id ? { ...p, ...updates } : p
                ),
                updatedAt: Date.now(),
            };
        }

        case 'SET_PANEL_SYMBOL': {
            const { panelId, symbol } = action.payload;
            let panels = state.panels.map(p =>
                p.id === panelId ? { ...p, symbol } : p
            );

            // If symbol sync is enabled, update all linked charts
            if (state.syncSettings.symbol) {
                const panel = state.panels.find(p => p.id === panelId);
                if (panel?.linkGroupId) {
                    const linkGroup = state.linkGroups.find(g => g.id === panel.linkGroupId);
                    if (linkGroup) {
                        panels = panels.map(p =>
                            linkGroup.chartIds.includes(p.id) ? { ...p, symbol } : p
                        );
                    }
                }
            }

            return {
                ...state,
                panels,
                updatedAt: Date.now(),
            };
        }

        case 'SET_PANEL_TIMEFRAME': {
            const { panelId, timeframe } = action.payload;
            let panels = state.panels.map(p =>
                p.id === panelId ? { ...p, timeframe } : p
            );

            // If interval sync is enabled, update all linked charts
            if (state.syncSettings.interval) {
                const panel = state.panels.find(p => p.id === panelId);
                if (panel?.linkGroupId) {
                    const linkGroup = state.linkGroups.find(g => g.id === panel.linkGroupId);
                    if (linkGroup) {
                        panels = panels.map(p =>
                            linkGroup.chartIds.includes(p.id) ? { ...p, timeframe } : p
                        );
                    }
                }
            }

            return {
                ...state,
                panels,
                updatedAt: Date.now(),
            };
        }

        case 'SET_ACTIVE_CHART': {
            return {
                ...state,
                activeChartId: action.payload,
            };
        }

        case 'TOGGLE_FULLSCREEN': {
            return {
                ...state,
                panels: state.panels.map(p => ({
                    ...p,
                    isFullscreen: p.id === action.payload ? !p.isFullscreen : false,
                })),
            };
        }

        case 'CREATE_LINK_GROUP': {
            return {
                ...state,
                linkGroups: [...state.linkGroups, action.payload],
                updatedAt: Date.now(),
            };
        }

        case 'ADD_TO_LINK_GROUP': {
            const { groupId, chartId } = action.payload;
            return {
                ...state,
                linkGroups: state.linkGroups.map(g =>
                    g.id === groupId
                        ? { ...g, chartIds: [...new Set([...g.chartIds, chartId])] }
                        : g
                ),
                panels: state.panels.map(p =>
                    p.id === chartId ? { ...p, linkGroupId: groupId } : p
                ),
                updatedAt: Date.now(),
            };
        }

        case 'REMOVE_FROM_LINK_GROUP': {
            const { groupId, chartId } = action.payload;
            return {
                ...state,
                linkGroups: state.linkGroups.map(g =>
                    g.id === groupId
                        ? { ...g, chartIds: g.chartIds.filter(id => id !== chartId) }
                        : g
                ),
                panels: state.panels.map(p =>
                    p.id === chartId ? { ...p, linkGroupId: null } : p
                ),
                updatedAt: Date.now(),
            };
        }

        case 'DELETE_LINK_GROUP': {
            return {
                ...state,
                linkGroups: state.linkGroups.filter(g => g.id !== action.payload),
                panels: state.panels.map(p =>
                    p.linkGroupId === action.payload ? { ...p, linkGroupId: null } : p
                ),
                updatedAt: Date.now(),
            };
        }

        case 'SET_SYNC_SETTINGS': {
            return {
                ...state,
                syncSettings: { ...state.syncSettings, ...action.payload },
                updatedAt: Date.now(),
            };
        }

        case 'BROADCAST_CROSSHAIR': {
            return {
                ...state,
                crosshairTimestamp: action.payload,
            };
        }

        case 'LOAD_WORKSPACE': {
            return action.payload;
        }

        case 'RESET_WORKSPACE': {
            return createDefaultWorkspace();
        }

        default:
            return state;
    }
}

// =============================================================================
// HOOK
// =============================================================================

export function useMultiChartWorkspace() {
    const [state, dispatch] = useReducer(workspaceReducer, null, loadInitialWorkspace);

    // Persist to localStorage on changes
    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }
    }, [state]);

    // Layout actions
    const setLayout = useCallback((layout: LayoutPreset) => {
        dispatch({ type: 'SET_LAYOUT', payload: layout });
    }, []);

    // Panel actions
    const updatePanelSymbol = useCallback((panelId: string, symbol: string) => {
        dispatch({ type: 'SET_PANEL_SYMBOL', payload: { panelId, symbol } });
    }, []);

    const updatePanelTimeframe = useCallback((panelId: string, timeframe: Timeframe) => {
        dispatch({ type: 'SET_PANEL_TIMEFRAME', payload: { panelId, timeframe } });
    }, []);

    const updatePanel = useCallback((panelId: string, updates: Partial<ChartPanelState>) => {
        dispatch({ type: 'UPDATE_PANEL', payload: { id: panelId, ...updates } });
    }, []);

    const setActiveChart = useCallback((chartId: string | null) => {
        dispatch({ type: 'SET_ACTIVE_CHART', payload: chartId });
    }, []);

    const toggleFullscreen = useCallback((chartId: string) => {
        dispatch({ type: 'TOGGLE_FULLSCREEN', payload: chartId });
    }, []);

    // Link group actions
    const createLinkGroup = useCallback((chartIds: string[] = []) => {
        const usedColors = state.linkGroups.map(g => g.color);
        const availableColor = LINK_GROUP_COLORS.find(c => !usedColors.includes(c)) || LINK_GROUP_COLORS[0];
        
        const group: LinkGroup = {
            id: generateLinkGroupId(),
            color: availableColor,
            linkedTypes: ['symbol', 'timeframe', 'crosshair'],
            chartIds,
        };
        
        dispatch({ type: 'CREATE_LINK_GROUP', payload: group });
        return group;
    }, [state.linkGroups]);

    const addToLinkGroup = useCallback((groupId: string, chartId: string) => {
        dispatch({ type: 'ADD_TO_LINK_GROUP', payload: { groupId, chartId } });
    }, []);

    const removeFromLinkGroup = useCallback((groupId: string, chartId: string) => {
        dispatch({ type: 'REMOVE_FROM_LINK_GROUP', payload: { groupId, chartId } });
    }, []);

    const deleteLinkGroup = useCallback((groupId: string) => {
        dispatch({ type: 'DELETE_LINK_GROUP', payload: groupId });
    }, []);

    // Sync settings
    const setSyncSettings = useCallback((settings: Partial<SyncSettings>) => {
        dispatch({ type: 'SET_SYNC_SETTINGS', payload: settings });
    }, []);

    // Crosshair sync
    const broadcastCrosshair = useCallback((timestamp: number | null) => {
        if (state.syncSettings.crosshair) {
            dispatch({ type: 'BROADCAST_CROSSHAIR', payload: timestamp });
        }
    }, [state.syncSettings.crosshair]);

    // Workspace persistence
    const loadWorkspace = useCallback((workspace: WorkspaceState) => {
        dispatch({ type: 'LOAD_WORKSPACE', payload: workspace });
    }, []);

    const resetWorkspace = useCallback(() => {
        dispatch({ type: 'RESET_WORKSPACE' });
    }, []);

    const saveWorkspaceAs = useCallback((name: string) => {
        const savedWorkspaces = JSON.parse(localStorage.getItem('quant360_saved_workspaces') || '{}');
        savedWorkspaces[name] = { ...state, name };
        localStorage.setItem('quant360_saved_workspaces', JSON.stringify(savedWorkspaces));
    }, [state]);

    const loadSavedWorkspace = useCallback((name: string) => {
        const savedWorkspaces = JSON.parse(localStorage.getItem('quant360_saved_workspaces') || '{}');
        if (savedWorkspaces[name]) {
            loadWorkspace(savedWorkspaces[name]);
        }
    }, [loadWorkspace]);

    const getSavedWorkspaceNames = useCallback((): string[] => {
        const savedWorkspaces = JSON.parse(localStorage.getItem('quant360_saved_workspaces') || '{}');
        return Object.keys(savedWorkspaces);
    }, []);

    // Get fullscreen panel if any
    const fullscreenPanel = useMemo(() => 
        state.panels.find(p => p.isFullscreen) || null,
    [state.panels]);

    return {
        // State
        state,
        layout: state.layout,
        panels: state.panels,
        linkGroups: state.linkGroups,
        syncSettings: state.syncSettings,
        activeChartId: state.activeChartId,
        crosshairTimestamp: state.crosshairTimestamp,
        fullscreenPanel,

        // Layout actions
        setLayout,

        // Panel actions
        updatePanelSymbol,
        updatePanelTimeframe,
        updatePanel,
        setActiveChart,
        toggleFullscreen,

        // Link group actions
        createLinkGroup,
        addToLinkGroup,
        removeFromLinkGroup,
        deleteLinkGroup,

        // Sync settings
        setSyncSettings,
        broadcastCrosshair,

        // Workspace persistence
        loadWorkspace,
        resetWorkspace,
        saveWorkspaceAs,
        loadSavedWorkspace,
        getSavedWorkspaceNames,
    };
}

export type UseMultiChartWorkspace = ReturnType<typeof useMultiChartWorkspace>;
