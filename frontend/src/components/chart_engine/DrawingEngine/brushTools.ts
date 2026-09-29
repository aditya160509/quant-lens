/**
 * Drawing Engine - Brush & Freehand Tools
 * Freehand Brush, Highlighter, Marker
 */

import type { Drawing, DrawingAnchor, DrawingStyle } from '../types';
import {
    DrawingToolDefinition,
    RenderContext,
    HitTestResult,
    defaultDrawingStyle,
    generateDrawingId,
    setLineStyle,
    distanceToPoint,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// FREEHAND BRUSH
// =============================================================================

export const FreehandBrushTool: DrawingToolDefinition = {
    type: 'freehand',
    name: 'Freehand',
    icon: '✎',
    category: 'brush',
    minAnchors: 2,
    maxAnchors: 1000,  // Unlimited points for freehand

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        c.lineCap = 'round';
        c.lineJoin = 'round';
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        const first = drawing.anchors[0];
        c.moveTo(timestampToPixel(first.timestamp), priceToPixel(first.price));

        for (let i = 1; i < drawing.anchors.length; i++) {
            const a = drawing.anchors[i];
            c.lineTo(timestampToPixel(a.timestamp), priceToPixel(a.price));
        }

        c.stroke();
        c.setLineDash([]);

        if (isSelected) {
            // Show first and last anchor only
            const lastIdx = drawing.anchors.length - 1;
            c.fillStyle = CHART_THEME.accent;
            c.beginPath();
            c.arc(timestampToPixel(first.timestamp), priceToPixel(first.price), 4, 0, Math.PI * 2);
            c.fill();
            c.beginPath();
            c.arc(timestampToPixel(drawing.anchors[lastIdx].timestamp), priceToPixel(drawing.anchors[lastIdx].price), 4, 0, Math.PI * 2);
            c.fill();
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        const { priceToPixel, timestampToPixel } = ctx;

        for (let i = 0; i < drawing.anchors.length; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            const ay = priceToPixel(drawing.anchors[i].price);
            if (distanceToPoint(x, y, ax, ay) < 8) {
                return { hit: true, distance: 0 };
            }
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'freehand',
        symbol: '',
        category: 'brush',
        anchors,
        style: { ...defaultDrawingStyle, lineWidth: 2, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// HIGHLIGHTER
// =============================================================================

export const HighlighterTool: DrawingToolDefinition = {
    type: 'highlighter',
    name: 'Highlighter',
    icon: '🖍',
    category: 'brush',
    minAnchors: 2,
    maxAnchors: 1000,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        // Highlighter: thick, semi-transparent stroke
        c.strokeStyle = `${drawing.style.color}66`;  // 40% opacity
        c.lineWidth = 12;
        c.lineCap = 'round';
        c.lineJoin = 'round';

        c.beginPath();
        const first = drawing.anchors[0];
        c.moveTo(timestampToPixel(first.timestamp), priceToPixel(first.price));

        for (let i = 1; i < drawing.anchors.length; i++) {
            const a = drawing.anchors[i];
            c.lineTo(timestampToPixel(a.timestamp), priceToPixel(a.price));
        }

        c.stroke();
    },

    hitTest: FreehandBrushTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'highlighter',
        symbol: '',
        category: 'brush',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, lineWidth: 12, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// MARKER (Bold Pen)
// =============================================================================

export const MarkerTool: DrawingToolDefinition = {
    type: 'marker',
    name: 'Marker',
    icon: '🖊',
    category: 'brush',
    minAnchors: 2,
    maxAnchors: 1000,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = 4;
        c.lineCap = 'round';
        c.lineJoin = 'round';

        c.beginPath();
        const first = drawing.anchors[0];
        c.moveTo(timestampToPixel(first.timestamp), priceToPixel(first.price));

        for (let i = 1; i < drawing.anchors.length; i++) {
            const a = drawing.anchors[i];
            c.lineTo(timestampToPixel(a.timestamp), priceToPixel(a.price));
        }

        c.stroke();

        if (isSelected) {
            c.fillStyle = CHART_THEME.accent;
            c.beginPath();
            c.arc(timestampToPixel(first.timestamp), priceToPixel(first.price), 4, 0, Math.PI * 2);
            c.fill();
        }
    },

    hitTest: FreehandBrushTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'marker',
        symbol: '',
        category: 'brush',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, lineWidth: 4, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const brushTools = [
    FreehandBrushTool,
    HighlighterTool,
    MarkerTool,
];
