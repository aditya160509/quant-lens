/**
 * Drawing Engine - Channel Tools
 * Parallel Channel, Regression Channel, Flat Channel
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
    distanceToLine,
    distanceToPoint,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// PARALLEL CHANNEL
// =============================================================================

export const ParallelChannelTool: DrawingToolDefinition = {
    type: 'parallelChannel',
    name: 'Parallel Channel',
    icon: '⌂',
    category: 'channels',
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

        // Calculate parallel line offset
        const dx = x2 - x1;
        const dy = y2 - y1;
        const offsetY = y3 - y1;

        // Extend lines to chart edges
        const extend = width * 2;
        const len = Math.sqrt(dx * dx + dy * dy);
        const ux = dx / len;
        const uy = dy / len;

        // Main line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1 - ux * extend, y1 - uy * extend);
        c.lineTo(x2 + ux * extend, y2 + uy * extend);
        c.stroke();

        // Parallel line
        c.beginPath();
        c.moveTo(x1 - ux * extend, y1 + offsetY - uy * extend);
        c.lineTo(x2 + ux * extend, y2 + offsetY + uy * extend);
        c.stroke();

        // Fill
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(x2, y2);
            c.lineTo(x2, y2 + offsetY);
            c.lineTo(x1, y1 + offsetY);
            c.closePath();
            c.fill();
        }

        c.setLineDash([]);

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
        type: 'parallelChannel',
        symbol: '',
        category: 'channels',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// REGRESSION CHANNEL
// =============================================================================

export const RegressionChannelTool: DrawingToolDefinition = {
    type: 'regressionChannel',
    name: 'Regression Channel',
    icon: '≈',
    category: 'channels',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        // Simple linear regression (two-point)
        const midY = (y1 + y2) / 2;
        const channelHeight = Math.abs(y2 - y1) * 0.5;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        // Center line
        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();

        // Upper channel
        c.setLineDash([4, 4]);
        c.beginPath();
        c.moveTo(x1, y1 - channelHeight);
        c.lineTo(x2, y2 - channelHeight);
        c.stroke();

        // Lower channel
        c.beginPath();
        c.moveTo(x1, y1 + channelHeight);
        c.lineTo(x2, y2 + channelHeight);
        c.stroke();

        c.setLineDash([]);

        // Fill
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.beginPath();
            c.moveTo(x1, y1 - channelHeight);
            c.lineTo(x2, y2 - channelHeight);
            c.lineTo(x2, y2 + channelHeight);
            c.lineTo(x1, y1 + channelHeight);
            c.closePath();
            c.fill();
        }

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;

        for (let i = 0; i < 2; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            const ay = priceToPixel(drawing.anchors[i].price);
            if (distanceToPoint(x, y, ax, ay) < 10) {
                return { hit: true, anchorIndex: i, distance: 0 };
            }
        }

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);
        const distance = distanceToLine(x, y, x1, y1, x2, y2);
        return { hit: distance < 10, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'regressionChannel',
        symbol: '',
        category: 'channels',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.05, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FLAT CHANNEL (Price Range)
// =============================================================================

export const FlatChannelTool: DrawingToolDefinition = {
    type: 'flatChannel',
    name: 'Price Range',
    icon: '═',
    category: 'channels',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const y1 = priceToPixel(a1.price);
        const y2 = priceToPixel(a2.price);

        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        const top = Math.min(y1, y2);
        const bottom = Math.max(y1, y2);

        // Fill
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.fillRect(left, top, right - left, bottom - top);
        }

        // Top and bottom lines
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(0, y1);
        c.lineTo(width, y1);
        c.stroke();

        c.beginPath();
        c.moveTo(0, y2);
        c.lineTo(width, y2);
        c.stroke();

        c.setLineDash([]);

        // Price labels
        c.fillStyle = drawing.style.color;
        c.font = '9px monospace';
        c.fillText(a1.price.toFixed(2), width - 50, y1 - 3);
        c.fillText(a2.price.toFixed(2), width - 50, y2 - 3);

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

        const y1 = priceToPixel(drawing.anchors[0].price);
        const y2 = priceToPixel(drawing.anchors[1].price);
        const distToTop = Math.abs(y - y1);
        const distToBottom = Math.abs(y - y2);
        const dist = Math.min(distToTop, distToBottom);

        return { hit: dist < 5, distance: dist };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'flatChannel',
        symbol: '',
        category: 'channels',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const channelTools = [
    ParallelChannelTool,
    RegressionChannelTool,
    FlatChannelTool,
];
