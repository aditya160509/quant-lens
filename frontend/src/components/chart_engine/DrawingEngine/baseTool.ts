/**
 * Drawing Engine - Base Tool
 * Base class and interfaces for all drawing tools
 */

import type { Drawing, DrawingAnchor, DrawingStyle, DrawingToolCategory, OHLCVBar } from '../types';
import { CHART_THEME } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export interface HitTestResult {
    hit: boolean;
    anchorIndex?: number;  // If hitting an anchor point
    distance: number;
}

export interface RenderContext {
    ctx: CanvasRenderingContext2D;
    priceToPixel: (price: number) => number;
    timestampToPixel: (timestamp: number) => number;
    pixelToPrice: (pixel: number) => number;
    pixelToTimestamp: (pixel: number) => number;
    width: number;
    height: number;
    bars: OHLCVBar[];
}

export interface DrawingToolDefinition {
    type: string;
    name: string;
    icon: string;
    category: DrawingToolCategory;
    minAnchors: number;
    maxAnchors: number;
    render: (drawing: Drawing, ctx: RenderContext, isSelected: boolean, isHovered: boolean) => void;
    hitTest: (drawing: Drawing, x: number, y: number, ctx: RenderContext) => HitTestResult;
    createDrawing: (anchors: DrawingAnchor[], style?: Partial<DrawingStyle>) => Drawing;
}

// =============================================================================
// DEFAULT STYLE
// =============================================================================

export const defaultDrawingStyle: DrawingStyle = {
    color: CHART_THEME.accent,
    lineWidth: 1,
    lineStyle: 'solid',
    fillColor: CHART_THEME.accent,
    fillOpacity: 0.1,
    fontSize: 12,
    fontColor: CHART_THEME.textPrimary,
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

let drawingIdCounter = 0;

export function generateDrawingId(): string {
    return `drawing_${Date.now()}_${++drawingIdCounter}`;
}

export function setLineStyle(ctx: CanvasRenderingContext2D, style: DrawingStyle['lineStyle']) {
    switch (style) {
        case 'dashed':
            ctx.setLineDash([6, 4]);
            break;
        case 'dotted':
            ctx.setLineDash([2, 2]);
            break;
        default:
            ctx.setLineDash([]);
    }
}

export function drawAnchor(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    isSelected: boolean
) {
    const size = isSelected ? 6 : 4;
    ctx.fillStyle = isSelected ? CHART_THEME.accent : CHART_THEME.textPrimary;
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = CHART_THEME.bgPrimary;
    ctx.lineWidth = 1;
    ctx.stroke();
}

export function distanceToLine(
    px: number,
    py: number,
    x1: number,
    y1: number,
    x2: number,
    y2: number
): number {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lenSq = dx * dx + dy * dy;

    if (lenSq === 0) {
        return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
    }

    let t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));

    const closestX = x1 + t * dx;
    const closestY = y1 + t * dy;

    return Math.sqrt((px - closestX) ** 2 + (py - closestY) ** 2);
}

export function distanceToPoint(
    px: number,
    py: number,
    x: number,
    y: number
): number {
    return Math.sqrt((px - x) ** 2 + (py - y) ** 2);
}

export function getLineAngle(x1: number, y1: number, x2: number, y2: number): number {
    return Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI);
}

// =============================================================================
// FIBONACCI LEVELS
// =============================================================================

export const FIBONACCI_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618];

export function getFibonacciPrices(
    startPrice: number,
    endPrice: number,
    levels: number[] = FIBONACCI_LEVELS
): { level: number; price: number }[] {
    const diff = endPrice - startPrice;
    return levels.map(level => ({
        level,
        price: startPrice + diff * level,
    }));
}

// =============================================================================
// GANN ANGLES
// =============================================================================

export const GANN_ANGLES = [
    { ratio: 1 / 8, label: '1x8' },
    { ratio: 1 / 4, label: '1x4' },
    { ratio: 1 / 3, label: '1x3' },
    { ratio: 1 / 2, label: '1x2' },
    { ratio: 1, label: '1x1' },
    { ratio: 2, label: '2x1' },
    { ratio: 3, label: '3x1' },
    { ratio: 4, label: '4x1' },
    { ratio: 8, label: '8x1' },
];

// =============================================================================
// EXPORT
// =============================================================================

export { Drawing, DrawingAnchor, DrawingStyle };
