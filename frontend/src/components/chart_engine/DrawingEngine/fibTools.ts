/**
 * Drawing Engine - Fibonacci Tools
 * Fibonacci Retracement, Extension, TimeZones, Fan, Arcs, Circles
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
    FIBONACCI_LEVELS,
    getFibonacciPrices,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// FIBONACCI RETRACEMENT
// =============================================================================

export const FibRetracementTool: DrawingToolDefinition = {
    type: 'fibRetracement',
    name: 'Fibonacci Retracement',
    icon: 'ψ',
    category: 'fibonacci',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2] = drawing.anchors;
        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const minX = Math.min(x1, x2);
        const maxX = width;

        const levels = getFibonacciPrices(a1.price, a2.price);

        // Draw levels
        levels.forEach(({ level, price }, i) => {
            const y = priceToPixel(price);

            // Background fill between levels
            if (i < levels.length - 1 && drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
                const nextY = priceToPixel(levels[i + 1].price);
                c.fillStyle = `rgba(255, 214, 10, ${drawing.style.fillOpacity * 0.5})`;
                c.fillRect(minX, Math.min(y, nextY), maxX - minX, Math.abs(nextY - y));
            }

            // Level line
            c.strokeStyle = level === 0 || level === 1 ? CHART_THEME.accent : CHART_THEME.textSecondary;
            c.lineWidth = level === 0 || level === 1 || level === 0.5 ? 1.5 : 1;
            setLineStyle(c, level === 0.5 ? 'dashed' : 'solid');

            c.beginPath();
            c.moveTo(minX, y);
            c.lineTo(maxX, y);
            c.stroke();

            // Label
            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '9px monospace';
            c.textAlign = 'left';
            c.fillText(`${(level * 100).toFixed(1)}%  ${price.toFixed(2)}`, maxX - 80, y - 3);
        });

        c.setLineDash([]);

        // Trend line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.beginPath();
        c.moveTo(x1, priceToPixel(a1.price));
        c.lineTo(x2, priceToPixel(a2.price));
        c.stroke();

        if (isSelected || isHovered) {
            drawAnchor(c, x1, priceToPixel(a1.price), isSelected);
            drawAnchor(c, x2, priceToPixel(a2.price), isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;

        // Check anchors
        for (let i = 0; i < 2; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            const ay = priceToPixel(drawing.anchors[i].price);
            if (distanceToPoint(x, y, ax, ay) < 10) {
                return { hit: true, anchorIndex: i, distance: 0 };
            }
        }

        // Check levels
        const levels = getFibonacciPrices(a1.price, a2.price);
        for (const { price } of levels) {
            const ly = priceToPixel(price);
            if (Math.abs(y - ly) < 5) {
                return { hit: true, distance: Math.abs(y - ly) };
            }
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'fibRetracement',
        symbol: '',
        category: 'fibonacci',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.05, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FIBONACCI EXTENSION
// =============================================================================

export const FibExtensionTool: DrawingToolDefinition = {
    type: 'fibExtension',
    name: 'Fibonacci Extension',
    icon: 'ψ+',
    category: 'fibonacci',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2, a3] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const x3 = timestampToPixel(a3.timestamp);

        // Calculate extension levels from point 3
        const swing = a2.price - a1.price;
        const extensionLevels = [0, 0.618, 1, 1.272, 1.618, 2, 2.618];

        extensionLevels.forEach(level => {
            const price = a3.price + swing * level;
            const y = priceToPixel(price);

            c.strokeStyle = level === 1 ? CHART_THEME.accent : CHART_THEME.textSecondary;
            c.lineWidth = 1;
            setLineStyle(c, level === 1 ? 'solid' : 'dashed');

            c.beginPath();
            c.moveTo(x3, y);
            c.lineTo(width, y);
            c.stroke();

            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '9px monospace';
            c.fillText(`${(level * 100).toFixed(1)}%  ${price.toFixed(2)}`, width - 80, y - 3);
        });

        c.setLineDash([]);

        // Draw connecting lines
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.beginPath();
        c.moveTo(x1, priceToPixel(a1.price));
        c.lineTo(x2, priceToPixel(a2.price));
        c.lineTo(x3, priceToPixel(a3.price));
        c.stroke();

        if (isSelected || isHovered) {
            drawAnchor(c, x1, priceToPixel(a1.price), isSelected);
            drawAnchor(c, x2, priceToPixel(a2.price), isSelected);
            drawAnchor(c, x3, priceToPixel(a3.price), isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;

        // Check anchors
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
        type: 'fibExtension',
        symbol: '',
        category: 'fibonacci',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FIBONACCI TIME ZONES
// =============================================================================

export const FibTimeZonesTool: DrawingToolDefinition = {
    type: 'fibTimeZones',
    name: 'Fibonacci Time Zones',
    icon: 'ψ|',
    category: 'fibonacci',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel, height } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const interval = x2 - x1;

        // Fibonacci sequence
        const fibSequence = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89];

        fibSequence.forEach(n => {
            const x = x1 + interval * n;

            c.strokeStyle = drawing.style.color;
            c.lineWidth = 1;
            setLineStyle(c, 'dashed');

            c.beginPath();
            c.moveTo(x, 0);
            c.lineTo(x, height);
            c.stroke();

            c.fillStyle = drawing.style.color;
            c.font = '9px monospace';
            c.fillText(`${n}`, x + 3, 15);
        });

        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, height / 2, isSelected);
            drawAnchor(c, x2, height / 2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        const { timestampToPixel } = ctx;

        for (let i = 0; i < drawing.anchors.length; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            if (Math.abs(x - ax) < 10) {
                return { hit: true, anchorIndex: i, distance: Math.abs(x - ax) };
            }
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'fibTimeZones',
        symbol: '',
        category: 'fibonacci',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FIBONACCI FAN
// =============================================================================

export const FibFanTool: DrawingToolDefinition = {
    type: 'fibFan',
    name: 'Fibonacci Fan',
    icon: 'ψ/',
    category: 'fibonacci',
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

        const fanLevels = [0.236, 0.382, 0.5, 0.618, 0.786];

        fanLevels.forEach(level => {
            const targetY = y1 + (y2 - y1) * level;

            // Extend line to chart edge
            const dx = x2 - x1;
            const dy = targetY - y1;
            const slope = dy / dx;
            const endX = width;
            const endY = y1 + slope * (endX - x1);

            c.strokeStyle = level === 0.5 ? CHART_THEME.accent : CHART_THEME.textSecondary;
            c.lineWidth = 1;
            setLineStyle(c, 'dashed');

            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(endX, endY);
            c.stroke();

            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '9px monospace';
            c.fillText(`${(level * 100).toFixed(1)}%`, endX - 40, endY - 3);
        });

        c.setLineDash([]);

        // Main trend line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1.5;
        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
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
        type: 'fibFan',
        symbol: '',
        category: 'fibonacci',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FIBONACCI ARCS
// =============================================================================

export const FibArcsTool: DrawingToolDefinition = {
    type: 'fibArcs',
    name: 'Fibonacci Arcs',
    icon: 'ψ)',
    category: 'fibonacci',
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

        const baseRadius = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
        const arcLevels = [0.382, 0.5, 0.618, 1];

        arcLevels.forEach(level => {
            const radius = baseRadius * level;

            c.strokeStyle = level === 0.5 ? CHART_THEME.accent : CHART_THEME.textSecondary;
            c.lineWidth = 1;
            setLineStyle(c, 'dashed');

            c.beginPath();
            c.arc(x2, y2, radius, 0, Math.PI * 2);
            c.stroke();
        });

        c.setLineDash([]);

        // Trend line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1.5;
        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
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
        type: 'fibArcs',
        symbol: '',
        category: 'fibonacci',
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

export const fibTools = [
    FibRetracementTool,
    FibExtensionTool,
    FibTimeZonesTool,
    FibFanTool,
    FibArcsTool,
];
