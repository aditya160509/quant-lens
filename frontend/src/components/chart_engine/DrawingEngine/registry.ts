/**
 * Drawing Engine - Registry
 * Central registry for all drawing tools
 */

import type { DrawingToolDefinition } from './baseTool';
import { lineTools } from './lineTools';
import { fibTools } from './fibTools';
import { shapeTools } from './shapes';
import { channelTools } from './channelTools';
import { gannTools } from './gannTools';
import { pitchforkTools } from './pitchforkTools';
import { elliottTools } from './elliottTools';
import { brushTools } from './brushTools';
import { patternTools } from './patternTools';
// Extended tools
import { measurementTools } from './measurementTools';
import { projectionTools } from './projectionTools';
import { volumeTools } from './volumeTools';
import { extendedFibTools } from './extendedFibTools';
import { extendedGannTools } from './extendedGannTools';
import { extendedPatternTools } from './extendedPatternTools';
import { textTools } from './textTools';

// =============================================================================
// REGISTRY
// =============================================================================

const toolRegistry = new Map<string, DrawingToolDefinition>();

// Register all tools
[
    ...lineTools,
    ...fibTools,
    ...extendedFibTools,
    ...shapeTools,
    ...channelTools,
    ...gannTools,
    ...extendedGannTools,
    ...pitchforkTools,
    ...elliottTools,
    ...brushTools,
    ...patternTools,
    ...extendedPatternTools,
    ...measurementTools,
    ...projectionTools,
    ...volumeTools,
    ...textTools,
].forEach(tool => {
    toolRegistry.set(tool.type, tool);
});

// =============================================================================
// API
// =============================================================================

export function registerTool(tool: DrawingToolDefinition) {
    toolRegistry.set(tool.type, tool);
}

export function getTool(type: string): DrawingToolDefinition | undefined {
    return toolRegistry.get(type);
}

export function getAllTools(): DrawingToolDefinition[] {
    return Array.from(toolRegistry.values());
}

export function getToolsByCategory(category: string): DrawingToolDefinition[] {
    return getAllTools().filter(t => t.category === category);
}

export function getToolCategories(): { category: string; tools: DrawingToolDefinition[] }[] {
    const categories = new Map<string, DrawingToolDefinition[]>();

    for (const tool of getAllTools()) {
        const list = categories.get(tool.category) || [];
        list.push(tool);
        categories.set(tool.category, list);
    }

    return Array.from(categories.entries()).map(([category, tools]) => ({
        category,
        tools,
    }));
}

// =============================================================================
// TOOL MENU STRUCTURE
// =============================================================================

export const TOOL_MENU = [
    {
        category: 'lines',
        label: 'Lines',
        icon: '╱',
        tools: ['trendLine', 'horizontalLine', 'verticalLine', 'horizontalRay', 'infoLine', 'extendedLine', 'crossLine', 'trendAngle'],
    },
    {
        category: 'channels',
        label: 'Channels',
        icon: '⌂',
        tools: ['parallelChannel', 'regressionChannel', 'flatChannel'],
    },
    {
        category: 'fibonacci',
        label: 'Fibonacci',
        icon: 'ψ',
        tools: ['fibRetracement', 'fibExtension', 'fibProjection', 'fibTimeZones', 'fibFan', 'fibArcs', 'fibCircles', 'fibSpiral', 'fibChannel', 'fibWedge'],
    },
    {
        category: 'pitchforks',
        label: 'Pitchforks',
        icon: '⋔',
        tools: ['pitchforkStandard', 'pitchforkSchiff', 'pitchforkModified', 'pitchforkInside'],
    },
    {
        category: 'gann',
        label: 'Gann',
        icon: '□',
        tools: ['gannBox', 'gannBoxFixed', 'gannFan', 'gannSquare', 'gannSquare9', 'gannGrid', 'gannSquareRange'],
    },
    {
        category: 'shapes',
        label: 'Shapes',
        icon: '○',
        tools: ['rectangle', 'rotatedRectangle', 'circle', 'ellipse', 'triangle', 'path', 'polyline', 'arc', 'curve', 'doubleCurve'],
    },
    {
        category: 'arrows',
        label: 'Arrows',
        icon: '→',
        tools: ['arrow', 'arrowMarker', 'arrowMarkUp', 'arrowMarkDown'],
    },
    {
        category: 'patterns',
        label: 'Patterns',
        icon: '⟁',
        tools: ['xabcdPattern', 'abcdPattern', 'headShoulders', 'trianglePattern', 'cypherPattern', 'gartleyPattern', 'batPattern', 'butterflyPattern', 'crabPattern', 'sharkPattern', 'threeDrivePattern', 'doubleTop', 'doubleBottom'],
    },
    {
        category: 'elliott',
        label: 'Elliott Wave',
        icon: '∿',
        tools: ['elliottImpulse', 'elliottCorrection', 'elliottWXY', 'elliottTriangle'],
    },
    {
        category: 'projections',
        label: 'Projections',
        icon: '⤴',
        tools: ['longPosition', 'shortPosition', 'riskReward', 'forecastCurve', 'projectionArrow', 'priceRange', 'dateRange', 'ruler'],
    },
    {
        category: 'quant',
        label: 'Quant Tools',
        icon: '📊',
        tools: ['quantRuler', 'liquidityProfile'],
    },
    {
        category: 'volume',
        label: 'Volume',
        icon: '▊',
        tools: ['anchoredVWAP', 'sessionVWAP', 'fixedRangeVP', 'volumeDelta'],
    },
    {
        category: 'brush',
        label: 'Brush & Freehand',
        icon: '✎',
        tools: ['freehand', 'highlighter', 'marker'],
    },
];

// =============================================================================
// EXPORT
// =============================================================================

export { toolRegistry };
export type { DrawingToolDefinition } from './baseTool';
export * from './lineTools';
export * from './fibTools';
export * from './extendedFibTools';
export * from './shapes';
export * from './channelTools';
export * from './gannTools';
export * from './extendedGannTools';
export * from './pitchforkTools';
export * from './elliottTools';
export * from './brushTools';
export * from './patternTools';
export * from './extendedPatternTools';
export * from './measurementTools';
export * from './projectionTools';
export * from './volumeTools';
export * from './textTools';
