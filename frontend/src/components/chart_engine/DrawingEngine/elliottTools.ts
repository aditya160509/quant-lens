/**
 * Drawing Engine - Elliott Wave Tools
 * Impulse (1-5), ABC Correction, WXY, Manual Labels
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
    distanceToLine,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// HELPERS
// =============================================================================

function drawWaveLabel(
    c: CanvasRenderingContext2D,
    x: number,
    y: number,
    label: string,
    color: string,
    below: boolean = false
) {
    const offsetY = below ? 15 : -10;

    c.fillStyle = color;
    c.font = 'bold 11px monospace';
    c.textAlign = 'center';
    c.fillText(label, x, y + offsetY);
}

function drawWaveLine(
    c: CanvasRenderingContext2D,
    points: { x: number; y: number; label: string }[],
    style: DrawingStyle,
    isSelected: boolean
) {
    if (points.length < 2) return;

    c.strokeStyle = style.color;
    c.lineWidth = isSelected ? style.lineWidth + 1 : style.lineWidth;
    setLineStyle(c, style.lineStyle);

    c.beginPath();
    c.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        c.lineTo(points[i].x, points[i].y);
    }
    c.stroke();
    c.setLineDash([]);

    // Labels
    points.forEach((p, i) => {
        const below = i > 0 && points[i - 1].y < p.y;
        drawWaveLabel(c, p.x, p.y, p.label, style.color, below);
    });
}

// =============================================================================
// IMPULSE WAVE (1-5)
// =============================================================================

export const ElliottImpulseTool: DrawingToolDefinition = {
    type: 'elliottImpulse',
    name: 'Elliott Impulse (1-5)',
    icon: '12345',
    category: 'elliott',
    minAnchors: 6,
    maxAnchors: 6,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map((a, i) => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
            label: i === 0 ? '0' : String(i),
        }));

        drawWaveLine(c, points, drawing.style, isSelected);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        const { priceToPixel, timestampToPixel } = ctx;

        for (let i = 0; i < drawing.anchors.length; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            const ay = priceToPixel(drawing.anchors[i].price);
            if (distanceToPoint(x, y, ax, ay) < 10) {
                return { hit: true, anchorIndex: i, distance: 0 };
            }
        }

        // Check line segments
        for (let i = 1; i < drawing.anchors.length; i++) {
            const x1 = timestampToPixel(drawing.anchors[i - 1].timestamp);
            const y1 = priceToPixel(drawing.anchors[i - 1].price);
            const x2 = timestampToPixel(drawing.anchors[i].timestamp);
            const y2 = priceToPixel(drawing.anchors[i].price);
            const dist = distanceToLine(x, y, x1, y1, x2, y2);
            if (dist < 5) {
                return { hit: true, distance: dist };
            }
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'elliottImpulse',
        symbol: '',
        category: 'elliott',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accentBlue, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ABC CORRECTION
// =============================================================================

export const ElliottCorrectionTool: DrawingToolDefinition = {
    type: 'elliottCorrection',
    name: 'Elliott ABC',
    icon: 'ABC',
    category: 'elliott',
    minAnchors: 4,
    maxAnchors: 4,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const labels = ['', 'A', 'B', 'C'];
        const points = drawing.anchors.map((a, i) => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
            label: labels[i],
        }));

        drawWaveLine(c, points, drawing.style, isSelected);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: ElliottImpulseTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'elliottCorrection',
        symbol: '',
        category: 'elliott',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// WXY DOUBLE CORRECTION
// =============================================================================

export const ElliottWXYTool: DrawingToolDefinition = {
    type: 'elliottWXY',
    name: 'Elliott WXY',
    icon: 'WXY',
    category: 'elliott',
    minAnchors: 4,
    maxAnchors: 4,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const labels = ['', 'W', 'X', 'Y'];
        const points = drawing.anchors.map((a, i) => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
            label: labels[i],
        }));

        drawWaveLine(c, points, drawing.style, isSelected);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: ElliottImpulseTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'elliottWXY',
        symbol: '',
        category: 'elliott',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ABCDE TRIANGLE
// =============================================================================

export const ElliottTriangleTool: DrawingToolDefinition = {
    type: 'elliottTriangle',
    name: 'Elliott ABCDE',
    icon: 'ABCDE',
    category: 'elliott',
    minAnchors: 6,
    maxAnchors: 6,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const labels = ['', 'A', 'B', 'C', 'D', 'E'];
        const points = drawing.anchors.map((a, i) => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
            label: labels[i],
        }));

        drawWaveLine(c, points, drawing.style, isSelected);

        // Draw converging lines through A-C-E and B-D
        if (points.length >= 4) {
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.lineWidth = 1;

            // Upper bound (A-C-E line)
            if (points[1] && (points[3] || points[5])) {
                c.beginPath();
                c.moveTo(points[1].x, points[1].y);
                if (points[5]) {
                    c.lineTo(points[5].x, points[5].y);
                } else if (points[3]) {
                    c.lineTo(points[3].x, points[3].y);
                }
                c.stroke();
            }

            // Lower bound (B-D line)
            if (points[2] && points[4]) {
                c.beginPath();
                c.moveTo(points[2].x, points[2].y);
                c.lineTo(points[4].x, points[4].y);
                c.stroke();
            }

            c.setLineDash([]);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: ElliottImpulseTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'elliottTriangle',
        symbol: '',
        category: 'elliott',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accentCyan, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const elliottTools = [
    ElliottImpulseTool,
    ElliottCorrectionTool,
    ElliottWXYTool,
    ElliottTriangleTool,
];
