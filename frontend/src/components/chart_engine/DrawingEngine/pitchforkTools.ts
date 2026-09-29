/**
 * Drawing Engine - Pitchfork Tools
 * Standard, Schiff, Modified Schiff, Inside Pitchfork
 */

import type { Drawing, DrawingAnchor, DrawingStyle } from '../types';
import {
    DrawingToolDefinition,
    RenderContext,
    HitTestResult,
    defaultDrawingStyle,
    generateDrawingId,
    setLineStyle,
    drawAnchor,
    distanceToPoint,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// HELPERS
// =============================================================================

function drawPitchforkLines(
    c: CanvasRenderingContext2D,
    x1: number, y1: number,
    x2: number, y2: number,
    x3: number, y3: number,
    style: DrawingStyle,
    width: number,
    isSelected: boolean
) {
    // Median line anchor (midpoint of BC)
    const medianX = (x2 + x3) / 2;
    const medianY = (y2 + y3) / 2;

    // Direction vector from point A to median
    const dx = medianX - x1;
    const dy = medianY - y1;
    const len = Math.sqrt(dx * dx + dy * dy);
    const ux = dx / len;
    const uy = dy / len;

    // Extend to edge
    const extendLength = width * 2;
    const endX = x1 + ux * extendLength;
    const endY = y1 + uy * extendLength;

    // Median line
    c.strokeStyle = style.color;
    c.lineWidth = isSelected ? style.lineWidth + 1 : style.lineWidth;
    setLineStyle(c, style.lineStyle);

    c.beginPath();
    c.moveTo(x1, y1);
    c.lineTo(endX, endY);
    c.stroke();

    // Upper prong (from B parallel to median)
    c.beginPath();
    c.moveTo(x2, y2);
    c.lineTo(x2 + ux * extendLength, y2 + uy * extendLength);
    c.stroke();

    // Lower prong (from C parallel to median)
    c.beginPath();
    c.moveTo(x3, y3);
    c.lineTo(x3 + ux * extendLength, y3 + uy * extendLength);
    c.stroke();

    // Fill between prongs
    if (style.fillOpacity && style.fillOpacity > 0) {
        c.fillStyle = `${style.fillColor}${Math.round(style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
        c.beginPath();
        c.moveTo(x2, y2);
        c.lineTo(x2 + ux * extendLength, y2 + uy * extendLength);
        c.lineTo(x3 + ux * extendLength, y3 + uy * extendLength);
        c.lineTo(x3, y3);
        c.closePath();
        c.fill();
    }

    c.setLineDash([]);
}

// =============================================================================
// STANDARD PITCHFORK
// =============================================================================

export const StandardPitchforkTool: DrawingToolDefinition = {
    type: 'pitchforkStandard',
    name: 'Pitchfork',
    icon: '⋔',
    category: 'pitchforks',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2, a3] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);
        const x3 = timestampToPixel(a3.timestamp);
        const y3 = priceToPixel(a3.price);

        drawPitchforkLines(c, x1, y1, x2, y2, x3, y3, drawing.style, width, isSelected);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x3, y3, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 3) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;

        for (let i = 0; i < drawing.anchors.length; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            const ay = priceToPixel(drawing.anchors[i].price);
            if (distanceToPoint(x, y, ax, ay) < 10) {
                return { hit: true, anchorIndex: i, distance: 0 };
            }
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'pitchforkStandard',
        symbol: '',
        category: 'pitchforks',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.05, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// SCHIFF PITCHFORK
// =============================================================================

export const SchiffPitchforkTool: DrawingToolDefinition = {
    type: 'pitchforkSchiff',
    name: 'Schiff Pitchfork',
    icon: '⋔s',
    category: 'pitchforks',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2, a3] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);
        const x3 = timestampToPixel(a3.timestamp);
        const y3 = priceToPixel(a3.price);

        // Schiff: Move point A to midpoint between A and B vertically
        const schiffY1 = (y1 + y2) / 2;

        drawPitchforkLines(c, x1, schiffY1, x2, y2, x3, y3, drawing.style, width, isSelected);

        // Show original A point
        if (isSelected || isHovered) {
            c.setLineDash([2, 2]);
            c.strokeStyle = CHART_THEME.textMuted;
            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(x1, schiffY1);
            c.stroke();
            c.setLineDash([]);

            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x3, y3, isSelected);
        }
    },

    hitTest: StandardPitchforkTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'pitchforkSchiff',
        symbol: '',
        category: 'pitchforks',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.05, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// MODIFIED SCHIFF PITCHFORK
// =============================================================================

export const ModifiedSchiffPitchforkTool: DrawingToolDefinition = {
    type: 'pitchforkModified',
    name: 'Modified Schiff',
    icon: '⋔m',
    category: 'pitchforks',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2, a3] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);
        const x3 = timestampToPixel(a3.timestamp);
        const y3 = priceToPixel(a3.price);

        // Modified Schiff: Move A halfway to BC midpoint
        const midX = (x2 + x3) / 2;
        const midY = (y2 + y3) / 2;
        const modX1 = (x1 + midX) / 2;
        const modY1 = (y1 + midY) / 2;

        drawPitchforkLines(c, modX1, modY1, x2, y2, x3, y3, drawing.style, width, isSelected);

        if (isSelected || isHovered) {
            c.setLineDash([2, 2]);
            c.strokeStyle = CHART_THEME.textMuted;
            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(modX1, modY1);
            c.stroke();
            c.setLineDash([]);

            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x3, y3, isSelected);
        }
    },

    hitTest: StandardPitchforkTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'pitchforkModified',
        symbol: '',
        category: 'pitchforks',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.05, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// INSIDE PITCHFORK
// =============================================================================

export const InsidePitchforkTool: DrawingToolDefinition = {
    type: 'pitchforkInside',
    name: 'Inside Pitchfork',
    icon: '⋔i',
    category: 'pitchforks',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2, a3] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);
        const x3 = timestampToPixel(a3.timestamp);
        const y3 = priceToPixel(a3.price);

        // Inside: Use A as one prong anchor, median from midpoint AB to C
        const midAB_X = (x1 + x2) / 2;
        const midAB_Y = (y1 + y2) / 2;

        drawPitchforkLines(c, midAB_X, midAB_Y, x1, y1, x3, y3, drawing.style, width, isSelected);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x3, y3, isSelected);
        }
    },

    hitTest: StandardPitchforkTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'pitchforkInside',
        symbol: '',
        category: 'pitchforks',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.05, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const pitchforkTools = [
    StandardPitchforkTool,
    SchiffPitchforkTool,
    ModifiedSchiffPitchforkTool,
    InsidePitchforkTool,
];
