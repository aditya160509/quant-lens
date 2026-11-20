/**
 * Drawing Engine - Measurement Tools
 * Price Range, Date Range, Date+Price Range, Ruler, Trend Angle Measurement, Percentage Calculator
 */

import { DrawingToolDefinition, defaultDrawingStyle, generateDrawingId, setLineStyle, drawAnchor, distanceToLine, distanceToPoint, getLineAngle } from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// QUANT STATISTICS RULER
// =============================================================================

export const QuantRulerTool: DrawingToolDefinition = {
    type: 'quantRuler',
    name: 'Quant Stats Ruler',
    icon: '📊',
    category: 'quant',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel, bars, height } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const y1 = priceToPixel(a1.price);
        const x2 = timestampToPixel(a2.timestamp);
        const y2 = priceToPixel(a2.price);

        const leftX = Math.min(x1, x2);
        const rightX = Math.max(x1, x2);

        // Find bars in range for calculations
        const rangeBars = (bars || []).filter(b => 
            b.timestamp >= Math.min(a1.timestamp, a2.timestamp) && 
            b.timestamp <= Math.max(a1.timestamp, a2.timestamp)
        );

        // Calculations
        const priceDiff = a2.price - a1.price;
        const pctChange = ((a2.price - a1.price) / a1.price) * 100;
        const totalVolume = rangeBars.reduce((sum, b) => sum + b.volume, 0);
        
        // Volatility (Average True Range in this region)
        const avgRange = rangeBars.length > 0 
            ? rangeBars.reduce((sum, b) => sum + (b.high - b.low), 0) / rangeBars.length 
            : 0;
            
        // Relative Strength / Beta Mockup using actual range volatility
        const rangeVol = Math.sqrt(rangeBars.reduce((sum, b) => sum + Math.pow((b.high - b.low) / b.close, 2), 0) / (rangeBars.length || 1)) * 100;

        // Visual Box for the range
        c.fillStyle = 'rgba(255, 214, 10, 0.05)';
        c.strokeStyle = 'rgba(255, 214, 10, 0.3)';
        c.lineWidth = 1;
        c.setLineDash([5, 5]);
        c.fillRect(leftX, 0, rightX - leftX, height);
        c.strokeRect(leftX, 0, rightX - leftX, height);
        c.setLineDash([]);

        // Horizontal connecting lines
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y1);
        c.stroke();
        c.beginPath();
        c.moveTo(x1, y2);
        c.lineTo(x2, y2);
        c.stroke();

        // Info box
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        
        const lines = [
            `MOVE: ${priceDiff >= 0 ? '+' : ''}${priceDiff.toFixed(2)} (${pctChange.toFixed(2)}%)`,
            `VOL TOTAL: ${(totalVolume / 1000000).toFixed(2)}M`,
            `AVG RANGE: $${avgRange.toFixed(2)} (${rangeVol.toFixed(2)}%)`,
            `BARS: ${rangeBars.length} | REL VOL: ${rangeVol.toFixed(2)}%`
        ];

        c.font = 'bold 10px monospace';
        const maxWidth = Math.max(...lines.map(l => c.measureText(l).width));
        const boxWidth = maxWidth + 16;
        const boxHeight = lines.length * 15 + 10;

        // Glassmorphism Box
        c.fillStyle = 'rgba(3, 5, 10, 0.95)';
        c.strokeStyle = CHART_THEME.accent;
        c.lineWidth = 1.5;
        c.beginPath();
        // @ts-ignore
        if (c.roundRect) {
            // @ts-ignore
            c.roundRect(midX - boxWidth / 2, midY - boxHeight / 2, boxWidth, boxHeight, 4);
        } else {
            c.rect(midX - boxWidth / 2, midY - boxHeight / 2, boxWidth, boxHeight);
        }
        c.fill();
        c.stroke();

        c.textAlign = 'center';
        c.textBaseline = 'middle';
        lines.forEach((line, i) => {
            c.fillStyle = i === 0 
                ? (pctChange >= 0 ? CHART_THEME.upColor : CHART_THEME.downColor)
                : (i === 1 ? CHART_THEME.accent : CHART_THEME.textPrimary);
            c.fillText(line, midX, midY - boxHeight / 2 + 16 + i * 15);
        });

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };
        const { timestampToPixel } = ctx;
        const x1 = timestampToPixel(drawing.anchors[0].timestamp);
        const x2 = timestampToPixel(drawing.anchors[1].timestamp);
        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        
        if (x >= left && x <= right) return { hit: true, distance: 0 };
        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'quantRuler',
        symbol: '',
        category: 'quant',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// LIQUIDITY PROFILE TOOL
// =============================================================================

export const LiquidityProfileTool: DrawingToolDefinition = {
    type: 'liquidityProfile',
    name: 'Liquidity Profile',
    icon: '📊',
    category: 'quant',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel, bars } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const leftX = Math.min(x1, x2);
        const rightX = Math.max(x1, x2);

        const rangeBars = (bars || []).filter(b => 
            b.timestamp >= Math.min(a1.timestamp, a2.timestamp) && 
            b.timestamp <= Math.max(a1.timestamp, a2.timestamp)
        );

        if (rangeBars.length === 0) return;

        const minPrice = Math.min(...rangeBars.map(b => b.low));
        const maxPrice = Math.max(...rangeBars.map(b => b.high));
        const priceStep = (maxPrice - minPrice) / 20;
        
        const bins = Array(20).fill(0);
        rangeBars.forEach(b => {
            const barMid = (b.high + b.low) / 2;
            const binIdx = Math.min(19, Math.floor((barMid - minPrice) / priceStep));
            if (binIdx >= 0) bins[binIdx] += b.volume;
        });

        const maxVol = Math.max(...bins);
        const profileWidth = 100;

        // Render Histogram
        c.fillStyle = 'rgba(139, 92, 246, 0.3)';
        bins.forEach((vol, i) => {
            const yStart = priceToPixel(minPrice + (i + 1) * priceStep);
            const yEnd = priceToPixel(minPrice + i * priceStep);
            const h = Math.abs(yEnd - yStart);
            const w = (vol / maxVol) * profileWidth;
            c.fillRect(leftX, yStart, w, h);
            
            if (vol === maxVol) {
                // POC (Point of Control) line
                c.strokeStyle = '#ff9500';
                c.lineWidth = 1;
                c.beginPath();
                c.moveTo(leftX, yStart + h/2);
                c.lineTo(rightX + 50, yStart + h/2);
                c.stroke();
                
                c.fillStyle = '#ff9500';
                c.font = 'bold 9px monospace';
                c.fillText('POC', rightX + 55, yStart + h/2 + 3);
            }
        });

        // Box
        c.strokeStyle = CHART_THEME.accent;
        c.lineWidth = 1;
        c.setLineDash([5, 5]);
        c.strokeRect(leftX, priceToPixel(maxPrice), rightX - leftX, Math.abs(priceToPixel(maxPrice) - priceToPixel(minPrice)));
        c.setLineDash([]);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, priceToPixel(a1.price), isSelected);
            drawAnchor(c, x2, priceToPixel(a2.price), isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };
        const { timestampToPixel } = ctx;
        const x1 = timestampToPixel(drawing.anchors[0].timestamp);
        const x2 = timestampToPixel(drawing.anchors[1].timestamp);
        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        if (x >= left && x <= right + 100) return { hit: true, distance: 0 };
        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'liquidityProfile',
        symbol: '',
        category: 'quant',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// PRICE RANGE
// =============================================================================

export const PriceRangeTool: DrawingToolDefinition = {
    type: 'priceRange',
    name: 'Price Range',
    icon: '↕',
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

        const centerX = (x1 + x2) / 2;
        const priceDiff = a2.price - a1.price;
        const pctChange = ((a2.price - a1.price) / a1.price) * 100;

        // Horizontal lines
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, 'dashed');

        c.beginPath();
        c.moveTo(x1 - 50, y1);
        c.lineTo(x2 + 50, y1);
        c.stroke();

        c.beginPath();
        c.moveTo(x1 - 50, y2);
        c.lineTo(x2 + 50, y2);
        c.stroke();

        // Vertical connecting line
        c.setLineDash([]);
        c.beginPath();
        c.moveTo(centerX, y1);
        c.lineTo(centerX, y2);
        c.stroke();

        // Arrow heads
        const arrowSize = 6;
        c.fillStyle = drawing.style.color;
        
        // Top arrow
        c.beginPath();
        c.moveTo(centerX, Math.min(y1, y2));
        c.lineTo(centerX - arrowSize, Math.min(y1, y2) + arrowSize);
        c.lineTo(centerX + arrowSize, Math.min(y1, y2) + arrowSize);
        c.fill();
        
        // Bottom arrow
        c.beginPath();
        c.moveTo(centerX, Math.max(y1, y2));
        c.lineTo(centerX - arrowSize, Math.max(y1, y2) - arrowSize);
        c.lineTo(centerX + arrowSize, Math.max(y1, y2) - arrowSize);
        c.fill();

        // Label box
        const midY = (y1 + y2) / 2;
        const sign = priceDiff >= 0 ? '+' : '';
        const label = `${sign}$${priceDiff.toFixed(2)} (${sign}${pctChange.toFixed(2)}%)`;

        c.font = 'bold 11px monospace';
        const textWidth = c.measureText(label).width;
        const boxPadding = 6;
        const boxWidth = textWidth + boxPadding * 2;
        const boxHeight = 20;

        c.fillStyle = priceDiff >= 0 ? 'rgba(0, 255, 136, 0.9)' : 'rgba(255, 45, 85, 0.9)';
        c.fillRect(centerX - boxWidth / 2, midY - boxHeight / 2, boxWidth, boxHeight);

        c.fillStyle = CHART_THEME.bgPrimary;
        c.textAlign = 'center';
        c.textBaseline = 'middle';
        c.fillText(label, centerX, midY);

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
        type: 'priceRange',
        symbol: '',
        category: 'projections',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.upColor, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// DATE RANGE
// =============================================================================

export const DateRangeTool: DrawingToolDefinition = {
    type: 'dateRange',
    name: 'Date Range',
    icon: '↔',
    category: 'projections',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2 || !ctx.bars) return;

        const { ctx: c, priceToPixel, timestampToPixel, height, bars } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const centerY = height / 2;

        const timeDiff = Math.abs(a2.timestamp - a1.timestamp);
        const hours = Math.floor(timeDiff / (1000 * 60 * 60));
        const minutes = Math.floor((timeDiff % (1000 * 60 * 60)) / (1000 * 60));
        
        // Accurate bar count
        const barCount = bars.filter(b => 
            b.timestamp >= Math.min(a1.timestamp, a2.timestamp) && 
            b.timestamp <= Math.max(a1.timestamp, a2.timestamp)
        ).length;

        // Vertical lines
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, 'dashed');

        c.beginPath();
        c.moveTo(x1, 0);
        c.lineTo(x1, height);
        c.stroke();

        c.beginPath();
        c.moveTo(x2, 0);
        c.lineTo(x2, height);
        c.stroke();

        // Horizontal connecting line
        c.setLineDash([]);
        c.beginPath();
        c.moveTo(x1, centerY);
        c.lineTo(x2, centerY);
        c.stroke();

        // Arrow heads
        const arrowSize = 6;
        c.fillStyle = drawing.style.color;
        
        c.beginPath();
        c.moveTo(Math.min(x1, x2), centerY);
        c.lineTo(Math.min(x1, x2) + arrowSize, centerY - arrowSize);
        c.lineTo(Math.min(x1, x2) + arrowSize, centerY + arrowSize);
        c.fill();
        
        c.beginPath();
        c.moveTo(Math.max(x1, x2), centerY);
        c.lineTo(Math.max(x1, x2) - arrowSize, centerY - arrowSize);
        c.lineTo(Math.max(x1, x2) - arrowSize, centerY + arrowSize);
        c.fill();

        // Label
        const midX = (x1 + x2) / 2;
        const label = `${hours}h ${minutes}m | ${barCount} bars`;

        c.font = 'bold 11px monospace';
        const textWidth = c.measureText(label).width;
        const boxPadding = 6;
        const boxWidth = textWidth + boxPadding * 2;
        const boxHeight = 20;

        c.fillStyle = 'rgba(255, 214, 10, 0.9)';
        c.fillRect(midX - boxWidth / 2, centerY - boxHeight / 2 - 25, boxWidth, boxHeight);

        c.fillStyle = CHART_THEME.bgPrimary;
        c.textAlign = 'center';
        c.textBaseline = 'middle';
        c.fillText(label, midX, centerY - 25);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, centerY, isSelected);
            drawAnchor(c, x2, centerY, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

        const { timestampToPixel, height } = ctx;
        const x1 = timestampToPixel(drawing.anchors[0].timestamp);
        const x2 = timestampToPixel(drawing.anchors[1].timestamp);
        const centerY = height / 2;

        for (let i = 0; i < 2; i++) {
            const ax = timestampToPixel(drawing.anchors[i].timestamp);
            if (distanceToPoint(x, y, ax, centerY) < 10) {
                return { hit: true, anchorIndex: i, distance: 0 };
            }
        }

        // Check vertical lines
        const distToX1 = Math.abs(x - x1);
        const distToX2 = Math.abs(x - x2);
        const minDist = Math.min(distToX1, distToX2);

        if (minDist < 5) return { hit: true, distance: minDist };

        // Check horizontal connecting line at centerY
        if (x >= Math.min(x1, x2) && x <= Math.max(x1, x2) && Math.abs(y - centerY) < 5) {
            return { hit: true, distance: Math.abs(y - centerY) };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'dateRange',
        symbol: '',
        category: 'projections',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// DATE + PRICE RANGE (RULER)
// =============================================================================

export const RulerTool: DrawingToolDefinition = {
    type: 'ruler',
    name: 'Ruler',
    icon: '📐',
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

        const priceDiff = a2.price - a1.price;
        const pctChange = ((a2.price - a1.price) / a1.price) * 100;
        const timeDiff = a2.timestamp - a1.timestamp;
        const hours = Math.floor(Math.abs(timeDiff) / (1000 * 60 * 60));
        const minutes = Math.floor((Math.abs(timeDiff) % (1000 * 60 * 60)) / (1000 * 60));

        // Main line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();
        c.setLineDash([]);

        // Dotted lines to form right triangle
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.textSecondary;
        c.lineWidth = 1;

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y1);
        c.lineTo(x2, y2);
        c.stroke();
        c.setLineDash([]);

        // Info box
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        const sign = priceDiff >= 0 ? '+' : '';
        
        const lines = [
            `${sign}$${priceDiff.toFixed(2)} (${sign}${pctChange.toFixed(2)}%)`,
            `${hours}h ${minutes}m`
        ];

        c.font = '10px monospace';
        const maxWidth = Math.max(...lines.map(l => c.measureText(l).width));
        const boxWidth = maxWidth + 12;
        const boxHeight = lines.length * 14 + 8;

        c.fillStyle = 'rgba(3, 5, 10, 0.9)';
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.fillRect(midX - boxWidth / 2, midY - boxHeight / 2, boxWidth, boxHeight);
        c.strokeRect(midX - boxWidth / 2, midY - boxHeight / 2, boxWidth, boxHeight);

        c.fillStyle = priceDiff >= 0 ? CHART_THEME.upColor : CHART_THEME.downColor;
        c.textAlign = 'center';
        lines.forEach((line, i) => {
            c.fillText(line, midX, midY - boxHeight / 2 + 14 + i * 14);
        });

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
        return { hit: distance < 5, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'ruler',
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
// TREND ANGLE MEASUREMENT
// =============================================================================

export const TrendAngleTool: DrawingToolDefinition = {
    type: 'trendAngle',
    name: 'Trend Angle',
    icon: '∠',
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

        const angle = getLineAngle(x1, y1, x2, y2);
        const angleRad = Math.atan2(y2 - y1, x2 - x1);

        // Main trend line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? drawing.style.lineWidth + 1 : drawing.style.lineWidth;
        setLineStyle(c, drawing.style.lineStyle);

        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();
        c.setLineDash([]);

        // Horizontal reference line
        c.setLineDash([4, 4]);
        c.strokeStyle = CHART_THEME.textSecondary;
        c.lineWidth = 1;
        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y1);
        c.stroke();
        c.setLineDash([]);

        // Arc showing angle
        const arcRadius = Math.min(40, Math.abs(x2 - x1) * 0.3);
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.beginPath();
        c.arc(x1, y1, arcRadius, 0, -angleRad, y2 > y1);
        c.stroke();

        // Angle label
        const labelX = x1 + arcRadius * 1.5 * Math.cos(-angleRad / 2);
        const labelY = y1 + arcRadius * 1.5 * Math.sin(-angleRad / 2);

        c.fillStyle = drawing.style.color;
        c.font = 'bold 12px monospace';
        c.textAlign = 'center';
        c.fillText(`${Math.abs(angle).toFixed(1)}°`, labelX, labelY);

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
        return { hit: distance < 5, distance };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'trendAngle',
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

export const measurementTools = [
    PriceRangeTool,
    DateRangeTool,
    RulerTool,
    TrendAngleTool,
    QuantRulerTool,
    LiquidityProfileTool,
];
