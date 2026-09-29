/**
 * Drawing Engine - Gann Tools
 * Gann Box, Gann Fan, Gann Square
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
    GANN_ANGLES,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// GANN BOX
// =============================================================================

export const GannBoxTool: DrawingToolDefinition = {
    type: 'gannBox',
    name: 'Gann Box',
    icon: '□',
    category: 'gann',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        const top = Math.min(y1, y2);
        const bottom = Math.max(y1, y2);
        const width = right - left;
        const height = bottom - top;

        // Outer box
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.strokeRect(left, top, width, height);

        // Gann divisions (1/8ths)
        const divisions = [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875];

        c.setLineDash([2, 2]);
        c.strokeStyle = CHART_THEME.textSecondary;
        c.lineWidth = 0.5;

        // Horizontal divisions
        divisions.forEach(d => {
            const y = top + height * d;
            c.beginPath();
            c.moveTo(left, y);
            c.lineTo(right, y);
            c.stroke();
        });

        // Vertical divisions
        divisions.forEach(d => {
            const x = left + width * d;
            c.beginPath();
            c.moveTo(x, top);
            c.lineTo(x, bottom);
            c.stroke();
        });

        // Diagonals
        c.strokeStyle = drawing.style.color;
        c.setLineDash([]);
        c.lineWidth = 1;

        // Main diagonals
        c.beginPath();
        c.moveTo(left, top);
        c.lineTo(right, bottom);
        c.stroke();

        c.beginPath();
        c.moveTo(left, bottom);
        c.lineTo(right, top);
        c.stroke();

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;

        for (let i = 0; i < 2; i++) {
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
        type: 'gannBox',
        symbol: '',
        category: 'gann',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// GANN FAN
// =============================================================================

export const GannFanTool: DrawingToolDefinition = {
    type: 'gannFan',
    name: 'Gann Fan',
    icon: '⊿',
    category: 'gann',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel, width, height } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        const baseAngle = Math.atan2(y2 - y1, x2 - x1);
        const lineLength = Math.max(width, height) * 2;

        c.lineWidth = 1;

        GANN_ANGLES.forEach(({ ratio, label }, index) => {
            const angle = Math.atan(ratio);
            const adjustedAngle = y2 > y1 ? baseAngle - angle : baseAngle + angle;

            const endX = x1 + Math.cos(adjustedAngle) * lineLength;
            const endY = y1 + Math.sin(adjustedAngle) * lineLength;

            c.strokeStyle = ratio === 1 ? drawing.style.color : CHART_THEME.textSecondary;
            c.setLineDash(ratio === 1 ? [] : [2, 2]);

            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(endX, endY);
            c.stroke();

            // Label
            const labelX = x1 + Math.cos(adjustedAngle) * 60;
            const labelY = y1 + Math.sin(adjustedAngle) * 60;
            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '9px monospace';
            c.fillText(label, labelX, labelY);
        });

        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;

        for (let i = 0; i < 2; i++) {
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
        type: 'gannFan',
        symbol: '',
        category: 'gann',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// GANN SQUARE
// =============================================================================

export const GannSquareTool: DrawingToolDefinition = {
    type: 'gannSquare',
    name: 'Gann Square',
    icon: '⊞',
    category: 'gann',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        const size = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
        const left = x1;
        const top = y1 < y2 ? y1 : y1 - size;

        // Outer square
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.strokeRect(left, top, size, size);

        // Inner grid (9x9)
        const gridSize = 9;
        const cellSize = size / gridSize;

        c.setLineDash([1, 2]);
        c.strokeStyle = CHART_THEME.textMuted;
        c.lineWidth = 0.5;

        for (let i = 1; i < gridSize; i++) {
            // Vertical
            c.beginPath();
            c.moveTo(left + i * cellSize, top);
            c.lineTo(left + i * cellSize, top + size);
            c.stroke();

            // Horizontal
            c.beginPath();
            c.moveTo(left, top + i * cellSize);
            c.lineTo(left + size, top + i * cellSize);
            c.stroke();
        }

        // Cardinal cross
        c.strokeStyle = drawing.style.color;
        c.setLineDash([]);
        c.lineWidth = 1;

        const mid = size / 2;
        c.beginPath();
        c.moveTo(left + mid, top);
        c.lineTo(left + mid, top + size);
        c.stroke();

        c.beginPath();
        c.moveTo(left, top + mid);
        c.lineTo(left + size, top + mid);
        c.stroke();

        // Diagonals
        c.beginPath();
        c.moveTo(left, top);
        c.lineTo(left + size, top + size);
        c.stroke();

        c.beginPath();
        c.moveTo(left + size, top);
        c.lineTo(left, top + size);
        c.stroke();

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;

        for (let i = 0; i < 2; i++) {
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
        type: 'gannSquare',
        symbol: '',
        category: 'gann',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const gannTools = [
    GannBoxTool,
    GannFanTool,
    GannSquareTool,
];
