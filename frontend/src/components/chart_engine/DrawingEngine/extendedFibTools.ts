/**
 * Drawing Engine - Extended Fibonacci Tools
 * Fibonacci Projection, Circles, Spiral, Channel, Wedge, Bars Pattern
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
    FIBONACCI_LEVELS,
    getFibonacciPrices,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// FIBONACCI PROJECTION
// =============================================================================

export const FibProjectionTool: DrawingToolDefinition = {
    type: 'fibProjection',
    name: 'Fibonacci Projection',
    icon: 'ψP',
    category: 'fibonacci',
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

        // Draw ABC points connection
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? 2 : 1.5;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.lineTo(x3, y3);
        c.stroke();
        c.setLineDash([]);

        // Calculate projection levels
        const swing = Math.abs(a2.price - a1.price);
        const direction = a2.price > a1.price ? -1 : 1; // Project opposite of first move
        const projectionLevels = [0.618, 1.0, 1.272, 1.618, 2.0, 2.618];

        projectionLevels.forEach((level, idx) => {
            const price = a3.price + swing * level * direction;
            const y = priceToPixel(price);

            c.strokeStyle = level === 1.0 ? CHART_THEME.accent : CHART_THEME.textSecondary;
            c.lineWidth = level === 1.0 ? 1.5 : 1;
            c.setLineDash(level === 1.0 ? [] : [4, 4]);

            c.beginPath();
            c.moveTo(x3, y);
            c.lineTo(width, y);
            c.stroke();

            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '9px monospace';
            c.textAlign = 'right';
            c.fillText(`${(level * 100).toFixed(1)}%  $${price.toFixed(2)}`, width - 5, y - 3);
        });

        c.setLineDash([]);

        // Labels
        c.font = 'bold 10px monospace';
        c.fillStyle = drawing.style.color;
        c.textAlign = 'center';
        c.fillText('A', x1, y1 + (y1 < y2 ? -10 : 15));
        c.fillText('B', x2, y2 + (y2 < y1 ? -10 : 15));
        c.fillText('C', x3, y3 + (y3 < y2 ? -10 : 15));

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x3, y3, isSelected);
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

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'fibProjection',
        symbol: '',
        category: 'fibonacci',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FIBONACCI CIRCLES
// =============================================================================

export const FibCirclesTool: DrawingToolDefinition = {
    type: 'fibCircles',
    name: 'Fibonacci Circles',
    icon: 'ψ◯',
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

        // Base radius
        const baseRadius = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
        const circleLevels = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618];

        // Draw circles
        circleLevels.forEach((level) => {
            const radius = baseRadius * level;

            c.strokeStyle = level === 1.0 ? CHART_THEME.accent 
                         : level === 0.5 || level === 0.618 ? CHART_THEME.accentBlue 
                         : CHART_THEME.textSecondary;
            c.lineWidth = level === 1.0 ? 1.5 : 1;
            c.setLineDash(level <= 0.5 ? [] : [4, 4]);

            c.beginPath();
            c.arc(x1, y1, radius, 0, Math.PI * 2);
            c.stroke();

            // Label at top of circle
            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '8px monospace';
            c.textAlign = 'center';
            c.fillText(`${(level * 100).toFixed(1)}%`, x1, y1 - radius - 3);
        });

        c.setLineDash([]);

        // Center point marker
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.arc(x1, y1, 3, 0, Math.PI * 2);
        c.fill();

        // Radius line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
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
        type: 'fibCircles',
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
// FIBONACCI SPIRAL
// =============================================================================

export const FibSpiralTool: DrawingToolDefinition = {
    type: 'fibSpiral',
    name: 'Fibonacci Spiral',
    icon: 'ψ@',
    category: 'fibonacci',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;

        const cx = timestampToPixel(a1.timestamp);
        const cy = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        // Calculate initial radius and direction
        const initialRadius = Math.sqrt((x2 - cx) ** 2 + (y2 - cy) ** 2);
        const startAngle = Math.atan2(y2 - cy, x2 - cx);

        // Golden ratio
        const phi = 1.618033988749895;
        const rotations = 4;
        const steps = 100 * rotations;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? 2 : 1.5;
        c.setLineDash([]);

        c.beginPath();
        for (let i = 0; i <= steps; i++) {
            const angle = startAngle + (i / steps) * rotations * Math.PI * 2;
            const radius = initialRadius * Math.pow(phi, (i / steps) * rotations);

            const x = cx + radius * Math.cos(angle);
            const y = cy + radius * Math.sin(angle);

            if (i === 0) {
                c.moveTo(x, y);
            } else {
                c.lineTo(x, y);
            }
        }
        c.stroke();

        // Draw golden rectangles overlay
        c.strokeStyle = CHART_THEME.textSecondary;
        c.setLineDash([2, 2]);
        c.lineWidth = 0.5;

        let rectSize = initialRadius;
        let rectX = cx;
        let rectY = cy;
        const directions = [[1, 0], [0, 1], [-1, 0], [0, -1]];

        for (let i = 0; i < 8; i++) {
            const [dx, dy] = directions[i % 4];
            c.strokeRect(
                rectX - rectSize,
                rectY - rectSize,
                rectSize * 2,
                rectSize * 2
            );
            
            rectX += dx * rectSize * (1 - 1/phi);
            rectY += dy * rectSize * (1 - 1/phi);
            rectSize = rectSize / phi;
        }

        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, cx, cy, isSelected);
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
        type: 'fibSpiral',
        symbol: '',
        category: 'fibonacci',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FIBONACCI CHANNEL
// =============================================================================

export const FibChannelTool: DrawingToolDefinition = {
    type: 'fibChannel',
    name: 'Fibonacci Channel',
    icon: 'ψ⌂',
    category: 'fibonacci',
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

        // Base channel line direction
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.sqrt(dx * dx + dy * dy);
        const ux = dx / len;
        const uy = dy / len;

        // Channel width from third point
        const channelOffset = y3 - y1;

        // Fibonacci levels for channel
        const fibLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.618, 2.618];

        // Extend to chart edge
        const extend = width * 2;

        fibLevels.forEach((level) => {
            const offset = channelOffset * level;
            const startX = x1;
            const startY = y1 + offset;
            const endX = x1 + ux * extend;
            const endY = y1 + uy * extend + offset;

            c.strokeStyle = level === 0 || level === 1 ? drawing.style.color : CHART_THEME.textSecondary;
            c.lineWidth = level === 0 || level === 1 ? 1.5 : 1;
            c.setLineDash(level === 0.5 ? [] : [4, 4]);

            c.beginPath();
            c.moveTo(startX, startY);
            c.lineTo(endX, endY);
            c.stroke();

            // Labels
            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '8px monospace';
            c.textAlign = 'left';
            c.fillText(`${(level * 100).toFixed(1)}%`, endX - 50, endY - 3);
        });

        c.setLineDash([]);

        // Fill between 0 and 1
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `rgba(255, 214, 10, ${drawing.style.fillOpacity})`;
            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(x1 + ux * extend, y1 + uy * extend);
            c.lineTo(x1 + ux * extend, y1 + uy * extend + channelOffset);
            c.lineTo(x1, y1 + channelOffset);
            c.closePath();
            c.fill();
        }

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x3, y3, isSelected);
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

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'fibChannel',
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
// FIBONACCI WEDGE
// =============================================================================

export const FibWedgeTool: DrawingToolDefinition = {
    type: 'fibWedge',
    name: 'Fibonacci Wedge',
    icon: 'ψ◁',
    category: 'fibonacci',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [a1, a2, a3] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp); // Apex
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp); // Upper bound
        const y2 = priceToPixel(a2.price);
        const x3 = timestampToPixel(a3.timestamp); // Lower bound
        const y3 = priceToPixel(a3.price);

        // Calculate angles
        const upperAngle = Math.atan2(y2 - y1, x2 - x1);
        const lowerAngle = Math.atan2(y3 - y1, x3 - x1);
        const angleDiff = lowerAngle - upperAngle;

        // Fibonacci angle divisions
        const fibAngles = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
        const lineLength = width * 2;

        fibAngles.forEach((level) => {
            const angle = upperAngle + angleDiff * level;
            const endX = x1 + Math.cos(angle) * lineLength;
            const endY = y1 + Math.sin(angle) * lineLength;

            c.strokeStyle = level === 0 || level === 1 ? drawing.style.color : CHART_THEME.textSecondary;
            c.lineWidth = level === 0 || level === 1 ? 1.5 : 1;
            c.setLineDash(level === 0.5 ? [] : [4, 4]);

            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(endX, endY);
            c.stroke();

            // Labels
            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '8px monospace';
            c.textAlign = 'left';
            c.fillText(`${(level * 100).toFixed(1)}%`, x1 + 60 * Math.cos(angle), y1 + 60 * Math.sin(angle));
        });

        c.setLineDash([]);

        // Fill wedge
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `rgba(255, 214, 10, ${drawing.style.fillOpacity})`;
            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(x1 + Math.cos(upperAngle) * lineLength, y1 + Math.sin(upperAngle) * lineLength);
            c.lineTo(x1 + Math.cos(lowerAngle) * lineLength, y1 + Math.sin(lowerAngle) * lineLength);
            c.closePath();
            c.fill();
        }

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x3, y3, isSelected);
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

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'fibWedge',
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
// EXPORTS
// =============================================================================

export const extendedFibTools = [
    FibProjectionTool,
    FibCirclesTool,
    FibSpiralTool,
    FibChannelTool,
    FibWedgeTool,
];
