/**
 * Drawing Engine - Line Tools
 * TrendLine, HorizontalLine, VerticalLine, Ray, InfoLine, Extended Line
 */

import { DrawingToolDefinition, defaultDrawingStyle, generateDrawingId, setLineStyle, drawAnchor, distanceToLine, distanceToPoint, getLineAngle } from './baseTool';

// =============================================================================
// TREND LINE
// =============================================================================

export const TrendLineTool: DrawingToolDefinition = {
    type: 'trendLine',
    name: 'Trend Line',
    icon: '╱',
    category: 'lines',
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

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
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

        // Check anchors first
        for (let i = 0; i < drawing.anchors.length; i++) {
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
        type: 'trendLine',
        symbol: '',
        category: 'lines',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// HORIZONTAL LINE
// =============================================================================

export const HorizontalLineTool: DrawingToolDefinition = {
    type: 'horizontalLine',
    name: 'Horizontal Line',
    icon: '─',
    category: 'lines',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, width } = ctx;
        const y = priceToPixel(drawing.anchors[0].price);

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(0, y);
        c.lineTo(width, y);
        c.stroke();
        c.setLineDash([]);

        // Price label
        c.fillStyle = drawing.style.color;
        c.font = '10px monospace';
        c.fillText(drawing.anchors[0].price.toFixed(2), width - 60, y - 5);

        if (isSelected || isHovered) {
            drawAnchor(c, 50, y, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel } = ctx;
        const lineY = priceToPixel(drawing.anchors[0].price);
        const distance = Math.abs(y - lineY);
        return { hit: distance < 5, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'horizontalLine',
        symbol: '',
        category: 'lines',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// VERTICAL LINE
// =============================================================================

export const VerticalLineTool: DrawingToolDefinition = {
    type: 'verticalLine',
    name: 'Vertical Line',
    icon: '│',
    category: 'lines',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, timestampToPixel, height } = ctx;
        const x = timestampToPixel(drawing.anchors[0].timestamp);

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x, 0);
        c.lineTo(x, height);
        c.stroke();
        c.setLineDash([]);

        // Time label
        const date = new Date(drawing.anchors[0].timestamp);
        const label = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        c.fillStyle = drawing.style.color;
        c.font = '10px monospace';
        c.fillText(label, x + 5, 15);

        if (isSelected || isHovered) {
            drawAnchor(c, x, 50, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { timestampToPixel } = ctx;
        const lineX = timestampToPixel(drawing.anchors[0].timestamp);
        const distance = Math.abs(x - lineX);
        return { hit: distance < 5, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'verticalLine',
        symbol: '',
        category: 'lines',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// HORIZONTAL RAY
// =============================================================================

export const HorizontalRayTool: DrawingToolDefinition = {
    type: 'horizontalRay',
    name: 'Horizontal Ray',
    icon: '→',
    category: 'lines',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const x = timestampToPixel(drawing.anchors[0].timestamp);
        const y = priceToPixel(drawing.anchors[0].price);

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x, y);
        c.lineTo(width, y);
        c.stroke();
        c.setLineDash([]);

        // Price label
        c.fillStyle = drawing.style.color;
        c.font = '10px monospace';
        c.fillText(drawing.anchors[0].price.toFixed(2), width - 60, y - 5);

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const startX = timestampToPixel(drawing.anchors[0].timestamp);
        const lineY = priceToPixel(drawing.anchors[0].price);

        if (x < startX) return { hit: false, distance: Infinity };

        const distance = Math.abs(y - lineY);
        return { hit: distance < 5, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'horizontalRay',
        symbol: '',
        category: 'lines',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// INFO LINE (with price/percent/bars label)
// =============================================================================

export const InfoLineTool: DrawingToolDefinition = {
    type: 'infoLine',
    name: 'Info Line',
    icon: '📏',
    category: 'lines',
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

        // Line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();
        c.setLineDash([]);

        // Info label
        const priceDiff = a2.price - a1.price;
        const pctChange = ((a2.price - a1.price) / a1.price) * 100;
        const angle = getLineAngle(x1, y1, x2, y2);

        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;

        c.fillStyle = drawing.style.color;
        c.font = '10px monospace';
        c.textAlign = 'center';

        const sign = priceDiff >= 0 ? '+' : '';
        const label = `${sign}${priceDiff.toFixed(2)} (${sign}${pctChange.toFixed(2)}%)`;
        c.fillText(label, midX, midY - 10);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: TrendLineTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'infoLine',
        symbol: '',
        category: 'lines',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXTENDED LINE (infinite in both directions)
// =============================================================================

export const ExtendedLineTool: DrawingToolDefinition = {
    type: 'extendedLine',
    name: 'Extended Line',
    icon: '⟷',
    category: 'lines',
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

        // Calculate extended endpoints
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.sqrt(dx * dx + dy * dy);
        const ux = dx / len;
        const uy = dy / len;

        // Extend to chart boundaries
        const extendLength = Math.max(width, height) * 2;
        const ex1 = x1 - ux * extendLength;
        const ey1 = y1 - uy * extendLength;
        const ex2 = x2 + ux * extendLength;
        const ey2 = y2 + uy * extendLength;

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(ex1, ey1);
        c.lineTo(ex2, ey2);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: TrendLineTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'extendedLine',
        symbol: '',
        category: 'lines',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// CROSS LINE (horizontal + vertical at point)
// =============================================================================

export const CrossLineTool: DrawingToolDefinition = {
    type: 'crossLine',
    name: 'Cross Line',
    icon: '┼',
    category: 'lines',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel, width, height } = ctx;
        const x = timestampToPixel(drawing.anchors[0].timestamp);
        const y = priceToPixel(drawing.anchors[0].price);

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        // Horizontal
        c.beginPath();
        c.moveTo(0, y);
        c.lineTo(width, y);
        c.stroke();

        // Vertical
        c.beginPath();
        c.moveTo(x, 0);
        c.lineTo(x, height);
        c.stroke();
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const lineX = timestampToPixel(drawing.anchors[0].timestamp);
        const lineY = priceToPixel(drawing.anchors[0].price);

        const distX = Math.abs(x - lineX);
        const distY = Math.abs(y - lineY);
        const distance = Math.min(distX, distY);

        return { hit: distance < 5, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'crossLine',
        symbol: '',
        category: 'lines',
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

export const lineTools = [
    TrendLineTool,
    HorizontalLineTool,
    VerticalLineTool,
    HorizontalRayTool,
    InfoLineTool,
    ExtendedLineTool,
    CrossLineTool,
];
