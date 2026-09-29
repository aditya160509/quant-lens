/**
 * Drawing Engine - Harmonic Pattern Tools
 * XABCD, ABCD, Crab, Butterfly, Bat, Shark, Cypher
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
// BASE HARMONIC RENDERING
// =============================================================================

function drawHarmonicPattern(
    c: CanvasRenderingContext2D,
    points: { x: number; y: number }[],
    labels: string[],
    style: DrawingStyle,
    isSelected: boolean
) {
    if (points.length < 2) return;

    c.strokeStyle = style.color;
    c.lineWidth = isSelected ? style.lineWidth + 1 : style.lineWidth;
    setLineStyle(c, style.lineStyle);

    // Draw connecting lines
    c.beginPath();
    c.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        c.lineTo(points[i].x, points[i].y);
    }
    c.stroke();

    // Fill the pattern area
    if (style.fillOpacity && style.fillOpacity > 0 && points.length >= 4) {
        c.fillStyle = `${style.fillColor}${Math.round(style.fillOpacity * 255).toString(16).padStart(2, '0')}`;
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.closePath();
        c.fill();
    }

    c.setLineDash([]);

    // Draw labels
    c.font = 'bold 11px monospace';
    c.textAlign = 'center';

    points.forEach((p, i) => {
        if (!labels[i]) return;

        // Determine if label should be above or below
        const prevY = i > 0 ? points[i - 1].y : p.y;
        const nextY = i < points.length - 1 ? points[i + 1].y : p.y;
        const isLocalMin = p.y >= prevY && p.y >= nextY;
        const offsetY = isLocalMin ? 15 : -10;

        c.fillStyle = style.color;
        c.fillText(labels[i], p.x, p.y + offsetY);
    });
}

function harmonicHitTest(
    drawing: Drawing,
    x: number,
    y: number,
    ctx: RenderContext
): HitTestResult {
    const { priceToPixel, timestampToPixel } = ctx;

    // Check anchors
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
}

// =============================================================================
// XABCD PATTERN
// =============================================================================

export const XABCDPatternTool: DrawingToolDefinition = {
    type: 'xabcdPattern',
    name: 'XABCD Pattern',
    icon: 'XABCD',
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
        drawHarmonicPattern(c, points, labels, drawing.style, isSelected);

        // Draw XB and BD connecting lines (dashed)
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
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'xabcdPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, color: CHART_THEME.accentCyan, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ABCD PATTERN
// =============================================================================

export const ABCDPatternTool: DrawingToolDefinition = {
    type: 'abcdPattern',
    name: 'ABCD Pattern',
    icon: 'ABCD',
    category: 'patterns',
    minAnchors: 4,
    maxAnchors: 4,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        const labels = ['A', 'B', 'C', 'D'];
        drawHarmonicPattern(c, points, labels, drawing.style, isSelected);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'abcdPattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, fillOpacity: 0.1, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// HEAD AND SHOULDERS
// =============================================================================

export const HeadShouldersTool: DrawingToolDefinition = {
    type: 'headShoulders',
    name: 'Head & Shoulders',
    icon: 'H&S',
    category: 'patterns',
    minAnchors: 7,
    maxAnchors: 7,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        // Labels: LS, N1, H, N2, RS, NL1, NL2
        const labels = ['LS', '', 'H', '', 'RS', '', ''];

        // Draw pattern
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        // Pattern outline (first 5 points)
        if (points.length >= 5) {
            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < 5; i++) {
                c.lineTo(points[i].x, points[i].y);
            }
            c.stroke();
        }

        // Neckline (points 5-6 or computed from neckline points 1,3)
        if (points.length >= 7) {
            c.setLineDash([6, 4]);
            c.strokeStyle = CHART_THEME.downColor;
            c.beginPath();
            c.moveTo(points[5].x, points[5].y);
            c.lineTo(points[6].x, points[6].y);

            // Extend neckline
            const dx = points[6].x - points[5].x;
            const dy = points[6].y - points[5].y;
            const len = Math.sqrt(dx * dx + dy * dy);
            if (len > 0) {
                c.lineTo(points[6].x + (dx / len) * width, points[6].y + (dy / len) * width);
            }
            c.stroke();
            c.setLineDash([]);
        }

        // Labels
        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;

        if (points.length >= 5) {
            c.fillText('LS', points[0].x, points[0].y - 12);
            c.fillText('H', points[2].x, points[2].y - 12);
            c.fillText('RS', points[4].x, points[4].y - 12);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'headShoulders',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// TRIANGLE PATTERN
// =============================================================================

export const TrianglePatternTool: DrawingToolDefinition = {
    type: 'trianglePattern',
    name: 'Triangle Pattern',
    icon: '△',
    category: 'patterns',
    minAnchors: 4,
    maxAnchors: 6,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 4) return;

        // Draw zigzag pattern
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Draw converging trend lines
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.textSecondary;

        // Upper trendline (through highs: points 0, 2, 4...)
        const highPoints = points.filter((_, i) => i % 2 === 0);
        if (highPoints.length >= 2) {
            const slope = (highPoints[1].y - highPoints[0].y) / (highPoints[1].x - highPoints[0].x);
            const endX = width;
            const endY = highPoints[0].y + slope * (endX - highPoints[0].x);

            c.beginPath();
            c.moveTo(highPoints[0].x, highPoints[0].y);
            c.lineTo(endX, endY);
            c.stroke();
        }

        // Lower trendline (through lows: points 1, 3, 5...)
        const lowPoints = points.filter((_, i) => i % 2 === 1);
        if (lowPoints.length >= 2) {
            const slope = (lowPoints[1].y - lowPoints[0].y) / (lowPoints[1].x - lowPoints[0].x);
            const endX = width;
            const endY = lowPoints[0].y + slope * (endX - lowPoints[0].x);

            c.beginPath();
            c.moveTo(lowPoints[0].x, lowPoints[0].y);
            c.lineTo(endX, endY);
            c.stroke();
        }

        c.setLineDash([]);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'trianglePattern',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// INVERSE HEAD & SHOULDERS
// =============================================================================

export const InverseHeadShouldersTool: DrawingToolDefinition = {
    type: 'inverseHeadShoulders',
    name: 'Inverse H&S Pattern',
    icon: 'IH&S',
    category: 'patterns',
    minAnchors: 7,
    maxAnchors: 7,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        if (points.length >= 5) {
            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < 5; i++) {
                c.lineTo(points[i].x, points[i].y);
            }
            c.stroke();
        }

        // Neckline
        if (points.length >= 7) {
            c.setLineDash([6, 4]);
            c.strokeStyle = CHART_THEME.upColor;
            c.beginPath();
            c.moveTo(points[5].x, points[5].y);
            c.lineTo(points[6].x, points[6].y);
            const dx = points[6].x - points[5].x;
            const dy = points[6].y - points[5].y;
            const len = Math.sqrt(dx * dx + dy * dy);
            if (len > 0) {
                c.lineTo(points[6].x + (dx / len) * width, points[6].y + (dy / len) * width);
            }
            c.stroke();
            c.setLineDash([]);
        }

        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;

        if (points.length >= 5) {
            c.fillText('LS', points[0].x, points[0].y + 15);
            c.fillText('H', points[2].x, points[2].y + 15);
            c.fillText('RS', points[4].x, points[4].y + 15);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'inverseHeadShoulders',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// DOUBLE TOP (M Top Formation)
// =============================================================================

export const DoubleTopTool: DrawingToolDefinition = {
    type: 'doubleTop',
    name: 'M Top Formation',
    icon: 'M',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 5) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        // Draw M shape
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Neckline (through the middle low)
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.downColor;
        c.beginPath();
        c.moveTo(0, points[2].y);
        c.lineTo(width, points[2].y);
        c.stroke();
        c.setLineDash([]);

        // Labels
        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;
        c.fillText('1', points[1].x, points[1].y - 12);
        c.fillText('2', points[3].x, points[3].y - 12);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'doubleTop',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// DOUBLE BOTTOM (W Bottom Formation)
// =============================================================================

export const DoubleBottomTool: DrawingToolDefinition = {
    type: 'doubleBottom',
    name: 'W Bottom Formation',
    icon: 'W',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 5,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 5) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        // Draw W shape
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Neckline (through middle high)
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.upColor;
        c.beginPath();
        c.moveTo(0, points[2].y);
        c.lineTo(width, points[2].y);
        c.stroke();
        c.setLineDash([]);

        // Labels
        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;
        c.fillText('1', points[1].x, points[1].y + 15);
        c.fillText('2', points[3].x, points[3].y + 15);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'doubleBottom',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// TRIPLE TOP (Triple M Formation)
// =============================================================================

export const TripleTopTool: DrawingToolDefinition = {
    type: 'tripleTop',
    name: 'Triple M Formation',
    icon: 'MMM',
    category: 'patterns',
    minAnchors: 7,
    maxAnchors: 7,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 7) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Resistance line through tops
        const avgTop = (points[1].y + points[3].y + points[5].y) / 3;
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.downColor;
        c.beginPath();
        c.moveTo(0, avgTop);
        c.lineTo(width, avgTop);
        c.stroke();
        c.setLineDash([]);

        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;
        c.fillText('1', points[1].x, points[1].y - 12);
        c.fillText('2', points[3].x, points[3].y - 12);
        c.fillText('3', points[5].x, points[5].y - 12);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'tripleTop',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// TRIPLE BOTTOM (Triple W Formation)
// =============================================================================

export const TripleBottomTool: DrawingToolDefinition = {
    type: 'tripleBottom',
    name: 'Triple W Formation',
    icon: 'WWW',
    category: 'patterns',
    minAnchors: 7,
    maxAnchors: 7,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 7) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Support line through bottoms
        const avgBottom = (points[1].y + points[3].y + points[5].y) / 3;
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.upColor;
        c.beginPath();
        c.moveTo(0, avgBottom);
        c.lineTo(width, avgBottom);
        c.stroke();
        c.setLineDash([]);

        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;
        c.fillText('1', points[1].x, points[1].y + 15);
        c.fillText('2', points[3].x, points[3].y + 15);
        c.fillText('3', points[5].x, points[5].y + 15);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'tripleBottom',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// CUP AND HANDLE
// =============================================================================

export const CupHandleTool: DrawingToolDefinition = {
    type: 'cupHandle',
    name: 'Cup Handle Formation',
    icon: '∪',
    category: 'patterns',
    minAnchors: 6,
    maxAnchors: 8,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 6) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        // Draw cup as smooth curve
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        
        // Cup portion (first 4-5 points) - draw as quadratic curves for smoothness
        if (points.length >= 5) {
            const cupPoints = points.slice(0, 5);
            for (let i = 0; i < cupPoints.length - 1; i++) {
                const xc = (cupPoints[i].x + cupPoints[i + 1].x) / 2;
                const yc = (cupPoints[i].y + cupPoints[i + 1].y) / 2;
                c.quadraticCurveTo(cupPoints[i].x, cupPoints[i].y, xc, yc);
            }
            c.lineTo(cupPoints[cupPoints.length - 1].x, cupPoints[cupPoints.length - 1].y);
        }
        
        // Handle portion (remaining points)
        for (let i = 5; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Resistance line at cup rim
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.upColor;
        c.beginPath();
        c.moveTo(0, points[0].y);
        c.lineTo(width, points[0].y);
        c.stroke();
        c.setLineDash([]);

        // Labels
        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;
        c.fillText('CUP', points[2].x, points[2].y + 15);
        if (points.length >= 7) {
            c.fillText('HANDLE', points[6].x, points[6].y + 15);
        }

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'cupHandle',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// INVERSE CUP AND HANDLE
// =============================================================================

export const InverseCupHandleTool: DrawingToolDefinition = {
    type: 'inverseCupHandle',
    name: 'Inverse Cup Formation',
    icon: '∩',
    category: 'patterns',
    minAnchors: 6,
    maxAnchors: 8,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 6) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        
        if (points.length >= 5) {
            const cupPoints = points.slice(0, 5);
            for (let i = 0; i < cupPoints.length - 1; i++) {
                const xc = (cupPoints[i].x + cupPoints[i + 1].x) / 2;
                const yc = (cupPoints[i].y + cupPoints[i + 1].y) / 2;
                c.quadraticCurveTo(cupPoints[i].x, cupPoints[i].y, xc, yc);
            }
            c.lineTo(cupPoints[cupPoints.length - 1].x, cupPoints[cupPoints.length - 1].y);
        }
        
        for (let i = 5; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Support line at cup base
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.downColor;
        c.beginPath();
        c.moveTo(0, points[0].y);
        c.lineTo(width, points[0].y);
        c.stroke();
        c.setLineDash([]);

        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;
        c.fillText('CUP', points[2].x, points[2].y - 12);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'inverseCupHandle',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// BULL FLAG FORMATION
// =============================================================================

export const BullFlagTool: DrawingToolDefinition = {
    type: 'bullFlag',
    name: 'Bull Flag Formation',
    icon: '▲⚑',
    category: 'patterns',
    minAnchors: 4,
    maxAnchors: 6,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 4) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        
        // Pole (first two points)
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        c.lineTo(points[1].x, points[1].y);
        c.stroke();

        // Flag channel (rest of points)
        c.setLineDash([4, 4]);
        for (let i = 2; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Fill flag area
        if (drawing.style.fillOpacity && points.length >= 4) {
            c.fillStyle = `${CHART_THEME.upColor}20`;
            c.beginPath();
            c.moveTo(points[1].x, points[1].y);
            for (let i = 2; i < points.length; i++) {
                c.lineTo(points[i].x, points[i].y);
            }
            c.closePath();
            c.fill();
        }
        c.setLineDash([]);

        c.font = 'bold 10px monospace';
        c.fillStyle = drawing.style.color;
        c.fillText('POLE', (points[0].x + points[1].x) / 2 - 20, (points[0].y + points[1].y) / 2);
        c.fillText('FLAG', points[points.length - 1].x + 10, points[points.length - 1].y);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'bullFlag',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// BEAR FLAG FORMATION
// =============================================================================

export const BearFlagTool: DrawingToolDefinition = {
    type: 'bearFlag',
    name: 'Bear Flag Formation',
    icon: '▼⚑',
    category: 'patterns',
    minAnchors: 4,
    maxAnchors: 6,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 4) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        c.lineTo(points[1].x, points[1].y);
        c.stroke();

        c.setLineDash([4, 4]);
        for (let i = 2; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        if (drawing.style.fillOpacity && points.length >= 4) {
            c.fillStyle = `${CHART_THEME.downColor}20`;
            c.beginPath();
            c.moveTo(points[1].x, points[1].y);
            for (let i = 2; i < points.length; i++) {
                c.lineTo(points[i].x, points[i].y);
            }
            c.closePath();
            c.fill();
        }
        c.setLineDash([]);

        c.font = 'bold 10px monospace';
        c.fillStyle = drawing.style.color;
        c.fillText('POLE', (points[0].x + points[1].x) / 2 - 20, (points[0].y + points[1].y) / 2);
        c.fillText('FLAG', points[points.length - 1].x + 10, points[points.length - 1].y);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'bearFlag',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, fillOpacity: 0.1, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// BULL PENNANT
// =============================================================================

export const BullPennantTool: DrawingToolDefinition = {
    type: 'bullPennant',
    name: 'Bull Pennant',
    icon: '▲▷',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 7,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 5) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        
        // Pole
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        c.lineTo(points[1].x, points[1].y);
        c.stroke();

        // Pennant triangle (converging lines)
        c.beginPath();
        c.moveTo(points[1].x, points[1].y);
        for (let i = 2; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Fill pennant
        if (points.length >= 5) {
            c.fillStyle = `${CHART_THEME.upColor}15`;
            c.beginPath();
            c.moveTo(points[1].x, points[1].y);
            for (let i = 2; i < points.length; i++) {
                c.lineTo(points[i].x, points[i].y);
            }
            c.closePath();
            c.fill();
        }

        c.font = 'bold 9px monospace';
        c.fillStyle = drawing.style.color;
        c.fillText('PENNANT', points[Math.floor(points.length / 2)].x, points[Math.floor(points.length / 2)].y - 5);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'bullPennant',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// BEAR PENNANT
// =============================================================================

export const BearPennantTool: DrawingToolDefinition = {
    type: 'bearPennant',
    name: 'Bear Pennant',
    icon: '▼▷',
    category: 'patterns',
    minAnchors: 5,
    maxAnchors: 7,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 5) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        c.lineTo(points[1].x, points[1].y);
        c.stroke();

        c.beginPath();
        c.moveTo(points[1].x, points[1].y);
        for (let i = 2; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        if (points.length >= 5) {
            c.fillStyle = `${CHART_THEME.downColor}15`;
            c.beginPath();
            c.moveTo(points[1].x, points[1].y);
            for (let i = 2; i < points.length; i++) {
                c.lineTo(points[i].x, points[i].y);
            }
            c.closePath();
            c.fill();
        }

        c.font = 'bold 9px monospace';
        c.fillStyle = drawing.style.color;
        c.fillText('PENNANT', points[Math.floor(points.length / 2)].x, points[Math.floor(points.length / 2)].y + 15);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'bearPennant',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ASCENDING WEDGE (Rising Wedge)
// =============================================================================

export const AscendingWedgeTool: DrawingToolDefinition = {
    type: 'ascendingWedge',
    name: 'Ascending Wedge',
    icon: '⟋',
    category: 'patterns',
    minAnchors: 4,
    maxAnchors: 6,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 4) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;

        // Draw zigzag
        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        // Converging trend lines
        c.setLineDash([4, 4]);
        
        const highPoints = points.filter((_, i) => i % 2 === 0);
        const lowPoints = points.filter((_, i) => i % 2 === 1);

        if (highPoints.length >= 2) {
            const slope = (highPoints[1].y - highPoints[0].y) / (highPoints[1].x - highPoints[0].x);
            c.beginPath();
            c.moveTo(highPoints[0].x, highPoints[0].y);
            c.lineTo(width, highPoints[0].y + slope * (width - highPoints[0].x));
            c.stroke();
        }

        if (lowPoints.length >= 2) {
            const slope = (lowPoints[1].y - lowPoints[0].y) / (lowPoints[1].x - lowPoints[0].x);
            c.beginPath();
            c.moveTo(lowPoints[0].x, lowPoints[0].y);
            c.lineTo(width, lowPoints[0].y + slope * (width - lowPoints[0].x));
            c.stroke();
        }

        c.setLineDash([]);

        c.font = 'bold 9px monospace';
        c.fillStyle = drawing.style.color;
        c.fillText('RISING WEDGE', points[Math.floor(points.length / 2)].x, points[0].y - 15);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'ascendingWedge',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.downColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// DESCENDING WEDGE (Falling Wedge)
// =============================================================================

export const DescendingWedgeTool: DrawingToolDefinition = {
    type: 'descendingWedge',
    name: 'Descending Wedge',
    icon: '⟍',
    category: 'patterns',
    minAnchors: 4,
    maxAnchors: 6,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        if (points.length < 4) return;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            c.lineTo(points[i].x, points[i].y);
        }
        c.stroke();

        c.setLineDash([4, 4]);
        
        const highPoints = points.filter((_, i) => i % 2 === 0);
        const lowPoints = points.filter((_, i) => i % 2 === 1);

        if (highPoints.length >= 2) {
            const slope = (highPoints[1].y - highPoints[0].y) / (highPoints[1].x - highPoints[0].x);
            c.beginPath();
            c.moveTo(highPoints[0].x, highPoints[0].y);
            c.lineTo(width, highPoints[0].y + slope * (width - highPoints[0].x));
            c.stroke();
        }

        if (lowPoints.length >= 2) {
            const slope = (lowPoints[1].y - lowPoints[0].y) / (lowPoints[1].x - lowPoints[0].x);
            c.beginPath();
            c.moveTo(lowPoints[0].x, lowPoints[0].y);
            c.lineTo(width, lowPoints[0].y + slope * (width - lowPoints[0].x));
            c.stroke();
        }

        c.setLineDash([]);

        c.font = 'bold 9px monospace';
        c.fillStyle = drawing.style.color;
        c.fillText('FALLING WEDGE', points[Math.floor(points.length / 2)].x, points[points.length - 1].y + 20);

        if (isSelected || isHovered) {
            points.forEach(p => drawAnchor(c, p.x, p.y, isSelected));
        }
    },

    hitTest: harmonicHitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'descendingWedge',
        symbol: '',
        category: 'patterns',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// RECTANGLE (Range Consolidation)
// =============================================================================

export const RectanglePatternTool: DrawingToolDefinition = {
    type: 'rectanglePattern',
    name: 'Range Consolidation',
    icon: '▭',
    category: 'patterns',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        if (drawing.anchors.length < 2) return;

        const x1 = timestampToPixel(drawing.anchors[0].timestamp);
        const y1 = priceToPixel(drawing.anchors[0].price);
        const x2 = timestampToPixel(drawing.anchors[1].timestamp);
        const y2 = priceToPixel(drawing.anchors[1].price);

        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        const top = Math.min(y1, y2);
        const bottom = Math.max(y1, y2);

        // Fill
        c.fillStyle = `${drawing.style.fillColor || drawing.style.color}15`;
        c.fillRect(left, top, right - left, bottom - top);

        // Border
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);
        c.strokeRect(left, top, right - left, bottom - top);

        // Support/Resistance lines extended
        c.setLineDash([8, 4]);
        c.strokeStyle = CHART_THEME.textSecondary;
        c.lineWidth = 1;
        
        c.beginPath();
        c.moveTo(0, top);
        c.lineTo(ctx.width, top);
        c.moveTo(0, bottom);
        c.lineTo(ctx.width, bottom);
        c.stroke();
        c.setLineDash([]);

        // Label
        c.font = 'bold 10px monospace';
        c.textAlign = 'center';
        c.fillStyle = drawing.style.color;
        c.fillText('RANGE', (left + right) / 2, (top + bottom) / 2);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
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

        if (drawing.anchors.length >= 2) {
            const x1 = timestampToPixel(drawing.anchors[0].timestamp);
            const y1 = priceToPixel(drawing.anchors[0].price);
            const x2 = timestampToPixel(drawing.anchors[1].timestamp);
            const y2 = priceToPixel(drawing.anchors[1].price);

            const left = Math.min(x1, x2);
            const right = Math.max(x1, x2);
            const top = Math.min(y1, y2);
            const bottom = Math.max(y1, y2);

            if (x >= left && x <= right && y >= top && y <= bottom) {
                return { hit: true, distance: 0 };
            }
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'rectanglePattern',
        symbol: '',
        category: 'patterns',
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

export const patternTools = [
    // Harmonic Patterns
    XABCDPatternTool,
    ABCDPatternTool,
    // Reversal Patterns
    HeadShouldersTool,
    InverseHeadShouldersTool,
    DoubleTopTool,
    DoubleBottomTool,
    TripleTopTool,
    TripleBottomTool,
    // Cup Patterns
    CupHandleTool,
    InverseCupHandleTool,
    // Flag Patterns
    BullFlagTool,
    BearFlagTool,
    BullPennantTool,
    BearPennantTool,
    // Wedge Patterns
    AscendingWedgeTool,
    DescendingWedgeTool,
    // Consolidation
    TrianglePatternTool,
    RectanglePatternTool,
];
