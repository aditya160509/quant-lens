/**
 * Chart Engine Exports
 * 
 * This module exports all chart engine components:
 * - Q360ChartCore: Full-featured chart with toolbar (custom canvas)
 * - LightweightChartCanvas: Pure lightweight-charts component
 * - MultiChartWorkspace: Original multi-chart grid
 * - MultiChartWorkspaceV2: New Zustand-powered lightweight-charts grid
 * - Store: Zustand store for workspace state
 */

// Core Components
export { default as Q360ChartCore } from './q360_chart_core';
export { default as ChartCanvas } from './ChartCanvas';
export { default as LightweightChartCanvas } from './LightweightChartCanvas';

// Workspaces
export { MultiChartWorkspace } from './MultiChartWorkspace';
export { MultiChartWorkspaceV2 } from './MultiChartWorkspaceV2';

// Store
export { 
    useChartWorkspaceStore,
    selectLayout,
    selectPanels,
    selectActiveChartId,
    selectSyncSettings,
    selectCrosshairTimestamp,
    LAYOUT_PRESETS,
    LINK_GROUP_COLORS,
} from './store/chartWorkspaceStore';

// Types
export * from './types';
export * from './workspaceTypes';

// State
export { ChartProvider, useChart } from './state/ChartContext';
