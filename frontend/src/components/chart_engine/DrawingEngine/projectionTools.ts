/**
 * Drawing Engine - Projection Tools
 * Long Position, Short Position, Risk/Reward Box, Bars Pattern, Forecast Curve, Ghost Feed
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
// LONG POSITION
// =============================================================================

export const LongPositionTool: DrawingToolDefinition = {
    type: 'longPosition',
    name: 'Long Position',
    icon: '↑L',
    category: 'projections',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [entry, stopLoss, takeProfit] = drawing.anchors;

        const x1 = timestampToPixel(entry.timestamp);
        const x2 = timestampToPixel(Math.max(stopLoss.timestamp, takeProfit.timestamp));
        const entryY = priceToPixel(entry.price);
        const slY = priceToPixel(stopLoss.price);
        const tpY = priceToPixel(takeProfit.price);

        const boxLeft = x1;
        const boxRight = Math.max(x2, x1 + 100);

        // Risk (stop loss zone) - red
        c.fillStyle = 'rgba(255, 45, 85, 0.15)';
        c.fillRect(boxLeft, Math.min(entryY, slY), boxRight - boxLeft, Math.abs(slY - entryY));
        c.strokeStyle = CHART_THEME.downColor;
        c.lineWidth = 1;
        c.strokeRect(boxLeft, Math.min(entryY, slY), boxRight - boxLeft, Math.abs(slY - entryY));

        // Reward (take profit zone) - green
        c.fillStyle = 'rgba(0, 255, 136, 0.15)';
        c.fillRect(boxLeft, Math.min(entryY, tpY), boxRight - boxLeft, Math.abs(tpY - entryY));
        c.strokeStyle = CHART_THEME.upColor;
        c.lineWidth = 1;
        c.strokeRect(boxLeft, Math.min(entryY, tpY), boxRight - boxLeft, Math.abs(tpY - entryY));

        // Entry line
        c.strokeStyle = CHART_THEME.accent;
        c.lineWidth = 2;
        c.setLineDash([]);
        c.beginPath();
        c.moveTo(boxLeft, entryY);
        c.lineTo(boxRight, entryY);
        c.stroke();

        // Labels
        c.font = 'bold 10px monospace';
        c.textAlign = 'left';

        const riskPips = Math.abs(entry.price - stopLoss.price);
        const rewardPips = Math.abs(takeProfit.price - entry.price);
        const rr = riskPips > 0 ? (rewardPips / riskPips).toFixed(2) : '∞';

        c.fillStyle = CHART_THEME.upColor;
        c.fillText(`TP: $${takeProfit.price.toFixed(2)} (+${((takeProfit.price - entry.price) / entry.price * 100).toFixed(2)}%)`, boxRight + 5, tpY);

        c.fillStyle = CHART_THEME.accent;
        c.fillText(`ENTRY: $${entry.price.toFixed(2)}`, boxRight + 5, entryY);

        c.fillStyle = CHART_THEME.downColor;
        c.fillText(`SL: $${stopLoss.price.toFixed(2)} (${((stopLoss.price - entry.price) / entry.price * 100).toFixed(2)}%)`, boxRight + 5, slY);

        c.fillStyle = CHART_THEME.textPrimary;
        c.fillText(`R:R = 1:${rr}`, boxRight + 5, (entryY + tpY) / 2);

        // Arrow indicating direction
        c.fillStyle = CHART_THEME.upColor;
        c.beginPath();
        c.moveTo(boxLeft + 10, entryY);
        c.lineTo(boxLeft + 5, entryY - 10);
        c.lineTo(boxLeft + 15, entryY - 10);
        c.closePath();
        c.fill();

        if (isSelected || isHovered) {
            drawAnchor(c, x1, entryY, isSelected);
            drawAnchor(c, x1, slY, isSelected);
            drawAnchor(c, x1, tpY, isSelected);
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
        type: 'longPosition',
        symbol: '',
        category: 'projections',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// SHORT POSITION
// =============================================================================

export const ShortPositionTool: DrawingToolDefinition = {
    type: 'shortPosition',
    name: 'Short Position',
    icon: '↓S',
    category: 'projections',
    minAnchors: 3,
    maxAnchors: 3,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const [entry, stopLoss, takeProfit] = drawing.anchors;

        const x1 = timestampToPixel(entry.timestamp);
        const x2 = timestampToPixel(Math.max(stopLoss.timestamp, takeProfit.timestamp));
        const entryY = priceToPixel(entry.price);
        const slY = priceToPixel(stopLoss.price);
        const tpY = priceToPixel(takeProfit.price);

        const boxLeft = x1;
        const boxRight = Math.max(x2, x1 + 100);

        // Risk (stop loss zone) - red (above entry for shorts)
        c.fillStyle = 'rgba(255, 45, 85, 0.15)';
        c.fillRect(boxLeft, Math.min(entryY, slY), boxRight - boxLeft, Math.abs(slY - entryY));
        c.strokeStyle = CHART_THEME.downColor;
        c.lineWidth = 1;
        c.strokeRect(boxLeft, Math.min(entryY, slY), boxRight - boxLeft, Math.abs(slY - entryY));

        // Reward (take profit zone) - green (below entry for shorts)
        c.fillStyle = 'rgba(0, 255, 136, 0.15)';
        c.fillRect(boxLeft, Math.min(entryY, tpY), boxRight - boxLeft, Math.abs(tpY - entryY));
        c.strokeStyle = CHART_THEME.upColor;
        c.lineWidth = 1;
        c.strokeRect(boxLeft, Math.min(entryY, tpY), boxRight - boxLeft, Math.abs(tpY - entryY));

        // Entry line
        c.strokeStyle = CHART_THEME.accent;
        c.lineWidth = 2;
        c.setLineDash([]);
        c.beginPath();
        c.moveTo(boxLeft, entryY);
        c.lineTo(boxRight, entryY);
        c.stroke();

        // Labels
        c.font = 'bold 10px monospace';
        c.textAlign = 'left';

        const riskPips = Math.abs(stopLoss.price - entry.price);
        const rewardPips = Math.abs(entry.price - takeProfit.price);
        const rr = riskPips > 0 ? (rewardPips / riskPips).toFixed(2) : '∞';

        c.fillStyle = CHART_THEME.downColor;
        c.fillText(`SL: $${stopLoss.price.toFixed(2)} (+${((stopLoss.price - entry.price) / entry.price * 100).toFixed(2)}%)`, boxRight + 5, slY);

        c.fillStyle = CHART_THEME.accent;
        c.fillText(`ENTRY: $${entry.price.toFixed(2)}`, boxRight + 5, entryY);

        c.fillStyle = CHART_THEME.upColor;
        c.fillText(`TP: $${takeProfit.price.toFixed(2)} (${((takeProfit.price - entry.price) / entry.price * 100).toFixed(2)}%)`, boxRight + 5, tpY);

        c.fillStyle = CHART_THEME.textPrimary;
        c.fillText(`R:R = 1:${rr}`, boxRight + 5, (entryY + tpY) / 2);

        // Arrow indicating direction
        c.fillStyle = CHART_THEME.downColor;
        c.beginPath();
        c.moveTo(boxLeft + 10, entryY);
        c.lineTo(boxLeft + 5, entryY + 10);
        c.lineTo(boxLeft + 15, entryY + 10);
        c.closePath();
        c.fill();

        if (isSelected || isHovered) {
            drawAnchor(c, x1, entryY, isSelected);
            drawAnchor(c, x1, slY, isSelected);
            drawAnchor(c, x1, tpY, isSelected);
        }
    },

    hitTest: LongPositionTool.hitTest,

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'shortPosition',
        symbol: '',
        category: 'projections',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// RISK REWARD BOX
// =============================================================================

export const RiskRewardTool: DrawingToolDefinition = {
    type: 'riskReward',
    name: 'Risk/Reward Box',
    icon: 'R:R',
    category: 'projections',
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

        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        const top = Math.min(y1, y2);
        const bottom = Math.max(y1, y2);

        // Determine if bullish or bearish move
        const isBullish = a2.price > a1.price;

        // Fill
        c.fillStyle = isBullish 
            ? 'rgba(0, 255, 136, 0.1)' 
            : 'rgba(255, 45, 85, 0.1)';
        c.fillRect(left, top, right - left, bottom - top);

        // Border
        c.strokeStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
        c.lineWidth = isSelected ? 2 : 1;
        c.strokeRect(left, top, right - left, bottom - top);

        // Diagonal line
        c.setLineDash([4, 4]);
        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();
        c.setLineDash([]);

        // Labels
        const priceDiff = Math.abs(a2.price - a1.price);
        const pctChange = ((a2.price - a1.price) / a1.price * 100);

        c.font = 'bold 11px monospace';
        c.textAlign = 'center';
        c.fillStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
        
        const label = `${isBullish ? '+' : ''}${pctChange.toFixed(2)}%`;
        c.fillText(label, (left + right) / 2, (top + bottom) / 2);
        c.fillText(`$${priceDiff.toFixed(2)}`, (left + right) / 2, (top + bottom) / 2 + 14);

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
        type: 'riskReward',
        symbol: '',
        category: 'projections',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FORECAST CURVE (BEZIER)
// =============================================================================

export const ForecastCurveTool: DrawingToolDefinition = {
    type: 'forecastCurve',
    name: 'Forecast Curve',
    icon: '〰',
    category: 'projections',
    minAnchors: 3,
    maxAnchors: 4,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 3) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;

        const points = drawing.anchors.map(a => ({
            x: timestampToPixel(a.timestamp),
            y: priceToPixel(a.price),
        }));

        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        c.setLineDash([6, 4]);

        c.beginPath();
        c.moveTo(points[0].x, points[0].y);

        if (points.length === 3) {
            // Quadratic bezier
            c.quadraticCurveTo(points[1].x, points[1].y, points[2].x, points[2].y);
        } else if (points.length === 4) {
            // Cubic bezier
            c.bezierCurveTo(points[1].x, points[1].y, points[2].x, points[2].y, points[3].x, points[3].y);
        }
        c.stroke();
        c.setLineDash([]);

        // Arrow at end
        const lastPoint = points[points.length - 1];
        const prevPoint = points[points.length - 2];
        const angle = Math.atan2(lastPoint.y - prevPoint.y, lastPoint.x - prevPoint.x);

        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.moveTo(lastPoint.x, lastPoint.y);
        c.lineTo(
            lastPoint.x - 10 * Math.cos(angle - Math.PI / 6),
            lastPoint.y - 10 * Math.sin(angle - Math.PI / 6)
        );
        c.lineTo(
            lastPoint.x - 10 * Math.cos(angle + Math.PI / 6),
            lastPoint.y - 10 * Math.sin(angle + Math.PI / 6)
        );
        c.closePath();
        c.fill();

        // Label "FORECAST"
        c.font = '9px monospace';
        c.fillStyle = drawing.style.color;
        c.textAlign = 'center';
        c.fillText('FORECAST', lastPoint.x, lastPoint.y - 15);

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

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'forecastCurve',
        symbol: '',
        category: 'projections',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accentBlue, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// PROJECTION ARROW
// =============================================================================

export const ProjectionArrowTool: DrawingToolDefinition = {
    type: 'projectionArrow',
    name: 'Projection Arrow',
    icon: '➤',
    category: 'projections',
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

        const isBullish = a2.price > a1.price;

        // Main line
        c.strokeStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
        c.lineWidth = isSelected ? 3 : 2;
        c.setLineDash([]);

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();

        // Arrow head
        const angle = Math.atan2(y2 - y1, x2 - x1);
        const arrowSize = 12;

        c.fillStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
        c.beginPath();
        c.moveTo(x2, y2);
        c.lineTo(
            x2 - arrowSize * Math.cos(angle - Math.PI / 6),
            y2 - arrowSize * Math.sin(angle - Math.PI / 6)
        );
        c.lineTo(
            x2 - arrowSize * Math.cos(angle + Math.PI / 6),
            y2 - arrowSize * Math.sin(angle + Math.PI / 6)
        );
        c.closePath();
        c.fill();

        // Price target label
        c.font = 'bold 10px monospace';
        c.textAlign = x2 > x1 ? 'left' : 'right';
        c.fillStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
        c.fillText(`$${a2.price.toFixed(2)}`, x2 + (x2 > x1 ? 10 : -10), y2);

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
        type: 'projectionArrow',
        symbol: '',
        category: 'projections',
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

export const projectionTools = [
    LongPositionTool,
    ShortPositionTool,
    RiskRewardTool,
    ForecastCurveTool,
    ProjectionArrowTool,
];
