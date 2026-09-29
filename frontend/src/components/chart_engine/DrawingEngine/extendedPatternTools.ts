/**
 * Drawing Engine - Extended Pattern Tools
 * Additional harmonic patterns and classical chart patterns
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
// HELPER FUNCTIONS
// =============================================================================

function drawPatternPoints(
    c: CanvasRenderingContext2D,
    points: { x: number; y: number }[],
    labels: string[],
    style: DrawingStyle,
    isSelected: boolean
) {
    if (points.length < 2) return;

    // Draw connecting lines
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

    // Draw labels
    c.font = 'bold 11px monospace';
    c.textAlign = 'center';
    c.fillStyle = style.color;

    points.forEach((p, i) => {
        if (!labels[i]) return;
        const prevY = i > 0 ? points[i - 1].y : p.y;
        const nextY = i < points.length - 1 ? points[i + 1].y : p.y;
        const isLocalMin = p.y >= prevY && p.y >= nextY;
        const offsetY = isLocalMin ? 15 : -10;
        c.fillText(labels[i], p.x, p.y + offsetY);
    });
}

function patternHitTest(drawing: Drawing, x: number, y: number, ctx: RenderContext): HitTestResult {
    const { priceToPixel, timestampToPixel } = ctx;

    for (let i = 0; i < drawing.anchors.length; i++) {
        const ax = timestampToPixel(drawing.anchors[i].timestamp);
        const ay = priceToPixel(drawing.anchors[i].price);
        if (distanceToPoint(x, y, ax, ay) < 10) {
            return { hit: true, anchorIndex: i, distance: 0 };
        }
    }

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
}

// =============================================================================
// CYPHER PATTERN
// =============================================================================

export const CypherPatternTool: DrawingToolDefinition = {
    type: 'cypherPattern',
    name: 'Cypher Pattern',
    icon: 'CYPH',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        const labels = ['X', 'A', 'B', 'C', 'D'];
        drawPatternPoints(c, points, labels, drawing.style, isSelected);

        // Draw XB and BD dashed lines
        if (points.length >= 5) {
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.lineWidth = 1;

            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            c.lineTo(points[2].x, points[2].y);
            c.stroke();

            c.beginPath();
            c.moveTo(points[2].x, points[2].y);
            c.lineTo(points[4].x, points[4].y);
            c.stroke();

            c.setLineDash([]);

            // Cypher ratios labels
            c.font = '8px monospace';
            c.fillStyle = CHART_THEME.textSecondary;
            c.textAlign = 'center';
            c.fillText('B: 0.382-0.618 XA', (points[0].x + points[2].x) / 2, (points[0].y + points[2].y) / 2 - 10);
            c.fillText('C: 1.272-1.414 XA', (points[1].x + points[3].x) / 2, (points[1].y + points[3].y) / 2 - 10);
            c.fillText('D: 0.786 XC', (points[0].x + points[4].x) / 2, (points[0].y + points[4].y) / 2 + 10);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: patternHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'cypherPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: '#9b5de5', fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// GARTLEY PATTERN
// =============================================================================

export const GartleyPatternTool: DrawingToolDefinition = {
    type: 'gartleyPattern',
    name: 'Gartley Pattern',
    icon: 'GART',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        const labels = ['X', 'A', 'B', 'C', 'D'];
        drawPatternPoints(c, points, labels, drawing.style, isSelected);

        if (points.length >= 5) {
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.lineWidth = 1;

            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            c.lineTo(points[2].x, points[2].y);
            c.stroke();

            c.beginPath();
            c.moveTo(points[2].x, points[2].y);
            c.lineTo(points[4].x, points[4].y);
            c.stroke();

            c.setLineDash([]);

            // Gartley ratios
            c.font = '8px monospace';
            c.fillStyle = CHART_THEME.textSecondary;
            c.textAlign = 'center';
            c.fillText('B: 0.618 XA', (points[0].x + points[2].x) / 2, (points[0].y + points[2].y) / 2 - 10);
            c.fillText('D: 0.786 XA', (points[0].x + points[4].x) / 2, (points[0].y + points[4].y) / 2 + 10);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: patternHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'gartleyPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: '#00bfff', fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// BAT PATTERN
// =============================================================================

export const BatPatternTool: DrawingToolDefinition = {
    type: 'batPattern',
    name: 'Bat Pattern',
    icon: 'BAT',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        const labels = ['X', 'A', 'B', 'C', 'D'];
        drawPatternPoints(c, points, labels, drawing.style, isSelected);

        if (points.length >= 5) {
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.lineWidth = 1;

            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            c.lineTo(points[2].x, points[2].y);
            c.stroke();

            c.beginPath();
            c.moveTo(points[2].x, points[2].y);
            c.lineTo(points[4].x, points[4].y);
            c.stroke();

            c.setLineDash([]);

            // Bat ratios
            c.font = '8px monospace';
            c.fillStyle = CHART_THEME.textSecondary;
            c.textAlign = 'center';
            c.fillText('B: 0.382-0.5 XA', (points[0].x + points[2].x) / 2, (points[0].y + points[2].y) / 2 - 10);
            c.fillText('D: 0.886 XA', (points[0].x + points[4].x) / 2, (points[0].y + points[4].y) / 2 + 10);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: patternHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'batPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: '#ff9500', fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// BUTTERFLY PATTERN
// =============================================================================

export const ButterflyPatternTool: DrawingToolDefinition = {
    type: 'butterflyPattern',
    name: 'Butterfly Pattern',
    icon: 'BTFL',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        const labels = ['X', 'A', 'B', 'C', 'D'];
        drawPatternPoints(c, points, labels, drawing.style, isSelected);

        if (points.length >= 5) {
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.lineWidth = 1;

            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            c.lineTo(points[2].x, points[2].y);
            c.stroke();

            c.beginPath();
            c.moveTo(points[2].x, points[2].y);
            c.lineTo(points[4].x, points[4].y);
            c.stroke();

            c.setLineDash([]);

            // Butterfly ratios
            c.font = '8px monospace';
            c.fillStyle = CHART_THEME.textSecondary;
            c.textAlign = 'center';
            c.fillText('B: 0.786 XA', (points[0].x + points[2].x) / 2, (points[0].y + points[2].y) / 2 - 10);
            c.fillText('D: 1.27-1.618 XA', (points[0].x + points[4].x) / 2, (points[0].y + points[4].y) / 2 + 10);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: patternHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'butterflyPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: '#ff2d55', fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// CRAB PATTERN
// =============================================================================

export const CrabPatternTool: DrawingToolDefinition = {
    type: 'crabPattern',
    name: 'Crab Pattern',
    icon: 'CRAB',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        const labels = ['X', 'A', 'B', 'C', 'D'];
        drawPatternPoints(c, points, labels, drawing.style, isSelected);

        if (points.length >= 5) {
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.lineWidth = 1;

            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            c.lineTo(points[2].x, points[2].y);
            c.stroke();

            c.beginPath();
            c.moveTo(points[2].x, points[2].y);
            c.lineTo(points[4].x, points[4].y);
            c.stroke();

            c.setLineDash([]);

            // Crab ratios
            c.font = '8px monospace';
            c.fillStyle = CHART_THEME.textSecondary;
            c.textAlign = 'center';
            c.fillText('B: 0.382-0.618 XA', (points[0].x + points[2].x) / 2, (points[0].y + points[2].y) / 2 - 10);
            c.fillText('D: 1.618 XA', (points[0].x + points[4].x) / 2, (points[0].y + points[4].y) / 2 + 10);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: patternHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'crabPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: '#30d158', fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// SHARK PATTERN
// =============================================================================

export const SharkPatternTool: DrawingToolDefinition = {
    type: 'sharkPattern',
    name: 'Shark Pattern',
    icon: 'SHRK',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        // Shark uses 0, X, A, B, C labels
        const labels = ['O', 'X', 'A', 'B', 'C'];
        drawPatternPoints(c, points, labels, drawing.style, isSelected);

        if (points.length >= 5) {
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.lineWidth = 1;

            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            c.lineTo(points[2].x, points[2].y);
            c.stroke();

            c.beginPath();
            c.moveTo(points[2].x, points[2].y);
            c.lineTo(points[4].x, points[4].y);
            c.stroke();

            c.setLineDash([]);

            // Shark ratios
            c.font = '8px monospace';
            c.fillStyle = CHART_THEME.textSecondary;
            c.textAlign = 'center';
            c.fillText('B: 1.13-1.618 XA', (points[1].x + points[3].x) / 2, (points[1].y + points[3].y) / 2 - 10);
            c.fillText('C: 0.886 OX', (points[0].x + points[4].x) / 2, (points[0].y + points[4].y) / 2 + 10);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: patternHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'sharkPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: '#5856d6', fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// THREE DRIVE PATTERN
// =============================================================================

export const ThreeDrivePatternTool: DrawingToolDefinition = {
    type: 'threeDrivePattern',
    name: 'Three Drive Pattern',
    icon: '3DRV',
    category: 'patterns',
    minAnchors: 7,
    maxAnchors: 7,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        const labels = ['', 'D1', '', 'D2', '', 'D3', 'Completion'];
        drawPatternPoints(c, points, labels, drawing.style, isSelected);

        if (points.length >= 7) {
            // Draw correction levels
            c.setLineDash([4, 4]);
            c.strokeStyle = CHART_THEME.textSecondary;
            c.font = '8px monospace';

            // Mark retracement zones
            c.fillStyle = CHART_THEME.textSecondary;
            c.textAlign = 'center';
            c.fillText('0.618-0.786', (points[1].x + points[2].x) / 2, (points[1].y + points[2].y) / 2);
            c.fillText('0.618-0.786', (points[3].x + points[4].x) / 2, (points[3].y + points[4].y) / 2);
            c.fillText('1.272-1.618', points[5].x, points[5].y - 15);

            c.setLineDash([]);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: patternHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'threeDrivePattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: '#ff9f1c', fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const extendedPatternTools = [
    CypherPatternTool,
    GartleyPatternTool,
    BatPatternTool,
    ButterflyPatternTool,
    CrabPatternTool,
    SharkPatternTool,
    ThreeDrivePatternTool,
];

