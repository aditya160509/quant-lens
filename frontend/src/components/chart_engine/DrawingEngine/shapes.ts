/**
 * Drawing Engine - Shape Tools
 * Rectangle, Ellipse, Triangle, Arrow, Text
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
// RECTANGLE
// =============================================================================

export const RectangleTool: DrawingToolDefinition = {
    type: 'rectangle',
    name: 'Rectangle',
    icon: '□',
    category: 'shapes',
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
        const top = Math.min(y1, y2);
        const width = Math.abs(x2 - x1);
        const height = Math.abs(y2 - y1);

        // Fill
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.fillRect(left, top, width, height);
        }

        // Stroke
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.strokeRect(left, top, width, height);
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            drawAnchor(c, x1, y2, false);
            drawAnchor(c, x2, y1, false);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        const top = Math.min(y1, y2);
        const bottom = Math.max(y1, y2);

        // Check corners
        const corners = [[x1, y1], [x2, y2], [x1, y2], [x2, y1]];
        for (let i = 0; i < corners.length; i++) {
            if (distanceToPoint(x, y, corners[i][0], corners[i][1]) < 10) {
                return { hit: true, anchorIndex: i < 2 ? i : undefined, distance: 0 };
            }
        }

        // Check edges
        if (x >= left && x <= right && y >= top && y <= bottom) {
            const distToEdge = Math.min(
                x - left,
                right - x,
                y - top,
                bottom - y
            );
            if (distToEdge < 5) {
                return { hit: true, distance: distToEdge };
            }
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'rectangle',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ELLIPSE
// =============================================================================

export const EllipseTool: DrawingToolDefinition = {
    type: 'ellipse',
    name: 'Ellipse',
    icon: '○',
    category: 'shapes',
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

        const cx = (x1 + x2) / 2;
        const cy = (y1 + y2) / 2;
        const rx = Math.abs(x2 - x1) / 2;
        const ry = Math.abs(y2 - y1) / 2;

        c.beginPath();
        c.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);

        // Fill
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.fill();
        }

        // Stroke
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        // Check anchors
        for (let i = 0; i < 2; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            const ay = priceToPixel(drawing.anchors[i].price);
            if (distanceToPoint(x, y, ax, ay) < 10) {
                return { hit: true, anchorIndex: i, distance: 0 };
            }
        }

        const cx = (x1 + x2) / 2;
        const cy = (y1 + y2) / 2;
        const rx = Math.abs(x2 - x1) / 2;
        const ry = Math.abs(y2 - y1) / 2;

        // Point on ellipse check
        const normalizedX = (x - cx) / rx;
        const normalizedY = (y - cy) / ry;
        const dist = Math.sqrt(normalizedX ** 2 + normalizedY ** 2);

        if (Math.abs(dist - 1) < 0.1) {
            return { hit: true, distance: Math.abs(dist - 1) * Math.min(rx, ry) };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'ellipse',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// TRIANGLE
// =============================================================================

export const TriangleTool: DrawingToolDefinition = {
    type: 'triangle',
    name: 'Triangle',
    icon: '△',
    category: 'shapes',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        c.lineTo(points[1].x, points[1].y);
        c.lineTo(points[2].x, points[2].y);
        c.closePath();

        // Fill
        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.fill();
        }

        // Stroke
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            points.forEach((p, i) => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 3) return { hit: false, distance: Infinity };

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
        type: 'triangle',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ARROW
// =============================================================================

export const ArrowTool: DrawingToolDefinition = {
    type: 'arrow',
    name: 'Arrow',
    icon: '→',
    category: 'shapes',
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

        const headLength = 15;
        const angle = Math.atan2(y2 - y1, x2 - x1);

        // Line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();
        c.setLineDash([]);

        // Arrow head
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.moveTo(x2, y2);
        c.lineTo(
            x2 - headLength * Math.cos(angle - Math.PI / 6),
            y2 - headLength * Math.sin(angle - Math.PI / 6)
        );
        c.lineTo(
            x2 - headLength * Math.cos(angle + Math.PI / 6),
            y2 - headLength * Math.sin(angle + Math.PI / 6)
        );
        c.closePath();
        c.fill();

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const [a1, a2] = drawing.anchors;
        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        for (let i = 0; i < 2; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            const ay = priceToPixel(drawing.anchors[i].price);
            if (distanceToPoint(x, y, ax, ay) < 10) {
                return { hit: true, anchorIndex: i, distance: 0 };
            }
        }

        const distance = distanceToLine(x, y, x1, y1, x2, y2);
        return { hit: distance < 5, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'arrow',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// TEXT
// =============================================================================

export const TextTool: DrawingToolDefinition = {
    type: 'text',
    name: 'Text',
    icon: 'A',
    category: 'text',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const x = timestampToPixel(drawing.anchors[0].timestamp);
        const y = priceToPixel(drawing.anchors[0].price);
        const text = drawing.label || 'Text';

        c.font = `${drawing.style.fontSize || 12}px ${CHART_THEME.fontMono}`;
        c.fillStyle = drawing.style.fontColor || drawing.style.color;
        c.textAlign = 'left';
        c.textBaseline = 'top';

        // Background
        const metrics = c.measureText(text);
        const padding = 4;

        if (isSelected || isHovered) {
            c.fillStyle = 'rgba(255, 214, 10, 0.1)';
            c.fillRect(
                x - padding,
                y - padding,
                metrics.width + padding * 2,
                (drawing.style.fontSize || 12) + padding * 2
            );
        }

        c.fillStyle = drawing.style.fontColor || drawing.style.color;
        c.fillText(text, x, y);

        if (isSelected) {
            drawAnchor(c, x, y, true);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const ax = timestampToPixel(drawing.anchors[0].timestamp);
        const ay = priceToPixel(drawing.anchors[0].price);

        // Simple bounding box
        const text = drawing.label || 'Text';
        const width = text.length * 8;
        const height = (drawing.style.fontSize || 12);

        if (x >= ax && x <= ax + width && y >= ay && y <= ay + height) {
            return { hit: true, anchorIndex: 0, distance: 0 };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'text',
        symbol: '',
        category: 'text',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        label: 'Text',
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ROTATED RECTANGLE
// =============================================================================

export const RotatedRectangleTool: DrawingToolDefinition = {
    type: 'rotatedRectangle',
    name: 'Rotated Rectangle',
    icon: '◇',
    category: 'shapes',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [a1, a2, a3] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);
        const x3 = timestampToPixel(a3.timestamp);
        const y3 = priceToPixel(a3.price);

        // Calculate 4th corner of rotated rectangle
        const dx = x2 - x1;
        const dy = y2 - y1;
        const perpX = -(y3 - y1);
        const perpY = x3 - x1;
        const projLen = (perpX * (x3 - x1) + perpY * (y3 - y1)) / (perpX * perpX + perpY * perpY + 0.0001);
        const x4 = x2 + projLen * perpX;
        const y4 = y2 + projLen * perpY;

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.lineTo(x4, y4);
        c.lineTo(x3, y3);
        c.closePath();

        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.fill();
        }

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.stroke();
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
        type: 'rotatedRectangle',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// CIRCLE
// =============================================================================

export const CircleTool: DrawingToolDefinition = {
    type: 'circle',
    name: 'Circle',
    icon: '◯',
    category: 'shapes',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [center, edge] = drawing.anchors;

        const cx = timestampToPixel(center.timestamp);
        const cy = priceToPixel(center.price);
        const ex = timestampToPixel(edge.timestamp);
        const ey = priceToPixel(edge.price);

        const radius = Math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2);

        c.beginPath();
        c.arc(cx, cy, radius, 0, Math.PI * 2);

        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.fill();
        }

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, cx, cy, isSelected);
            drawAnchor(c, ex, ey, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const [center, edge] = drawing.anchors;

        const cx = timestampToPixel(center.timestamp);
        const cy = priceToPixel(center.price);
        const ex = timestampToPixel(edge.timestamp);
        const ey = priceToPixel(edge.price);

        const radius = Math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2);
        const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);

        if (Math.abs(dist - radius) < 8) {
            return { hit: true, distance: Math.abs(dist - radius) };
        }

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
        type: 'circle',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// PATH (Polyline/Free polygon)
// =============================================================================

export const PathTool: DrawingToolDefinition = {
    type: 'path',
    name: 'Path',
    icon: '⟋',
    category: 'shapes',
    minAnchors: 2,
    maxAnchors: 50,

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

        if (isSelected || isHovered) {
            drawing.anchors.forEach((a, i) => {
                drawAnchor(c, timestampToPixel(a.timestamp), priceToPixel(a.price), isSelected);
            });
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
        for (let i = 0; i < drawing.anchors.length - 1; i++) {
            const x1 = timestampToPixel(drawing.anchors[i].timestamp);
            const y1 = priceToPixel(drawing.anchors[i].price);
            const x2 = timestampToPixel(drawing.anchors[i + 1].timestamp);
            const y2 = priceToPixel(drawing.anchors[i + 1].price);
            const distance = distanceToLine(x, y, x1, y1, x2, y2);
            if (distance < 8) return { hit: true, distance };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'path',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// POLYLINE (closed polygon)
// =============================================================================

export const PolylineTool: DrawingToolDefinition = {
    type: 'polyline',
    name: 'Polyline',
    icon: '⬡',
    category: 'shapes',
    minAnchors: 3,
    maxAnchors: 20,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.closePath();

        if (drawing.style.fillOpacity && drawing.style.fillOpacity > 0) {
            c.fillStyle = `${drawing.style.fillColor}${Math.round(drawing.style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
            c.fill();
        }

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: PathTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'polyline',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ARC
// =============================================================================

export const ArcTool: DrawingToolDefinition = {
    type: 'arc',
    name: 'Arc',
    icon: '⌒',
    category: 'shapes',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [start, control, end] = drawing.anchors;

        const x1 = timestampToPixel(start.timestamp);
        const y1 = priceToPixel(start.price);
        const cx = timestampToPixel(control.timestamp);
        const cy = priceToPixel(control.price);
        const x2 = timestampToPixel(end.timestamp);
        const y2 = priceToPixel(end.price);

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.quadraticCurveTo(cx, cy, x2, y2);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, cx, cy, isSelected);
            drawAnchor(c, x2, y2, isSelected);
            // Draw control lines
            c.strokeStyle = CHART_THEME.textMuted;
            c.lineWidth = 1;
            c.setLineDash([3, 3]);
            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(cx, cy);
            c.lineTo(x2, y2);
            c.stroke();
            c.setLineDash([]);
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
        type: 'arc',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// CURVE (Bezier)
// =============================================================================

export const CurveTool: DrawingToolDefinition = {
    type: 'curve',
    name: 'Curve',
    icon: '∿',
    category: 'shapes',
    minAnchors: 4,
    maxAnchors: 4,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 4) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [start, cp1, cp2, end] = drawing.anchors;

        const x1 = timestampToPixel(start.timestamp);
        const y1 = priceToPixel(start.price);
        const cx1 = timestampToPixel(cp1.timestamp);
        const cy1 = priceToPixel(cp1.price);
        const cx2 = timestampToPixel(cp2.timestamp);
        const cy2 = priceToPixel(cp2.price);
        const x2 = timestampToPixel(end.timestamp);
        const y2 = priceToPixel(end.price);

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.bezierCurveTo(cx1, cy1, cx2, cy2, x2, y2);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, cx1, cy1, false);
            drawAnchor(c, cx2, cy2, false);
            drawAnchor(c, x2, y2, isSelected);
            // Control lines
            c.strokeStyle = CHART_THEME.textMuted;
            c.lineWidth = 1;
            c.setLineDash([3, 3]);
            c.beginPath();
            c.moveTo(x1, y1);
            c.lineTo(cx1, cy1);
            c.moveTo(x2, y2);
            c.lineTo(cx2, cy2);
            c.stroke();
            c.setLineDash([]);
        }
    },

    hitTest: ArcTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'curve',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// DOUBLE CURVE
// =============================================================================

export const DoubleCurveTool: DrawingToolDefinition = {
    type: 'doubleCurve',
    name: 'Double Curve',
    icon: '∞',
    category: 'shapes',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [start, mid, end] = drawing.anchors;

        const x1 = timestampToPixel(start.timestamp);
        const y1 = priceToPixel(start.price);
        const mx = timestampToPixel(mid.timestamp);
        const my = priceToPixel(mid.price);
        const x2 = timestampToPixel(end.timestamp);
        const y2 = priceToPixel(end.price);

        // Two quadratic curves meeting at midpoint
        const cp1x = (x1 + mx) / 2;
        const cp1y = my + (y1 - my) * 0.5;
        const cp2x = (mx + x2) / 2;
        const cp2y = my + (y2 - my) * 0.5;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.quadraticCurveTo(cp1x, cp1y, mx, my);
        c.quadraticCurveTo(cp2x, cp2y, x2, y2);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, mx, my, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: ArcTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'doubleCurve',
        symbol: '',
        category: 'shapes',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ARROW MARKER (single point)
// =============================================================================

export const ArrowMarkerTool: DrawingToolDefinition = {
    type: 'arrowMarker',
    name: 'Arrow Marker',
    icon: '▲',
    category: 'arrows',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const x = timestampToPixel(drawing.anchors[0].timestamp);
        const y = priceToPixel(drawing.anchors[0].price);

        const size = 12;
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.moveTo(x, y - size);
        c.lineTo(x - size * 0.6, y + size * 0.4);
        c.lineTo(x + size * 0.6, y + size * 0.4);
        c.closePath();
        c.fill();

        if (isSelected || isHovered) {
            c.strokeStyle = CHART_THEME.accent;
            c.lineWidth = 2;
            c.stroke();
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };
        const { priceToPixel, timestampToPixel } = ctx;
        const ax = timestampToPixel(drawing.anchors[0].timestamp);
        const ay = priceToPixel(drawing.anchors[0].price);
        const distance = distanceToPoint(x, y, ax, ay);
        return { hit: distance < 15, anchorIndex: 0, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'arrowMarker',
        symbol: '',
        category: 'arrows',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ARROW MARK UP
// =============================================================================

export const ArrowMarkUpTool: DrawingToolDefinition = {
    type: 'arrowMarkUp',
    name: 'Arrow Mark Up',
    icon: '▲',
    category: 'arrows',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const x = timestampToPixel(drawing.anchors[0].timestamp);
        const y = priceToPixel(drawing.anchors[0].price);

        const size = 14;
        c.fillStyle = CHART_THEME.upColor;
        c.beginPath();
        c.moveTo(x, y - size);
        c.lineTo(x - size * 0.7, y + size * 0.3);
        c.lineTo(x + size * 0.7, y + size * 0.3);
        c.closePath();
        c.fill();

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
        }
    },

    hitTest: ArrowMarkerTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'arrowMarkUp',
        symbol: '',
        category: 'arrows',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ARROW MARK DOWN
// =============================================================================

export const ArrowMarkDownTool: DrawingToolDefinition = {
    type: 'arrowMarkDown',
    name: 'Arrow Mark Down',
    icon: '▼',
    category: 'arrows',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const x = timestampToPixel(drawing.anchors[0].timestamp);
        const y = priceToPixel(drawing.anchors[0].price);

        const size = 14;
        c.fillStyle = CHART_THEME.downColor;
        c.beginPath();
        c.moveTo(x, y + size);
        c.lineTo(x - size * 0.7, y - size * 0.3);
        c.lineTo(x + size * 0.7, y - size * 0.3);
        c.closePath();
        c.fill();

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
        }
    },

    hitTest: ArrowMarkerTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'arrowMarkDown',
        symbol: '',
        category: 'arrows',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const shapeTools = [
    RectangleTool,
    RotatedRectangleTool,
    CircleTool,
    EllipseTool,
    TriangleTool,
    PathTool,
    PolylineTool,
    ArcTool,
    CurveTool,
    DoubleCurveTool,
    ArrowTool,
    ArrowMarkerTool,
    ArrowMarkUpTool,
    ArrowMarkDownTool,
    TextTool,
];
