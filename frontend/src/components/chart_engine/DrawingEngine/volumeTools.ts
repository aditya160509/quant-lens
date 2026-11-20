/**
 * Drawing Engine - Volume Tools
 * Anchored VWAP, Fixed Range Volume Profile, Visible Range Volume Profile, Volume Delta
 */

import type { OHLCVBar } from '../types';
import { DrawingToolDefinition, defaultDrawingStyle, generateDrawingId, drawAnchor, distanceToPoint } from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// ANCHORED VWAP
// =============================================================================

export const AnchoredVWAPTool: DrawingToolDefinition = {
    type: 'anchoredVWAP',
    name: 'Anchored VWAP',
    icon: 'aVWAP',
    category: 'volume',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1 || !ctx.bars || ctx.bars.length === 0) return;

        const { ctx: c, priceToPixel, timestampToPixel, bars } = ctx;
        const anchor = drawing.anchors[0];
        const anchorTime = anchor.timestamp;
        
        // Find starting index
        let startIndex = bars.findIndex(b => b.timestamp >= anchorTime);
        if (startIndex === -1) return;

        // Calculate VWAP curve
        const vwapPoints: { x: number; y: number }[] = [];
        let cumPv = 0;
        let cumVol = 0;
        let cumSqDiff = 0;
        const vwapValues: number[] = [];

        for (let i = startIndex; i < bars.length; i++) {
            const bar = bars[i];
            const typicalPrice = (bar.high + bar.low + bar.close) / 3;
            cumPv += typicalPrice * bar.volume;
            cumVol += bar.volume;
            const currentVwap = cumPv / cumVol;
            
            vwapValues.push(currentVwap);
            vwapPoints.push({
                x: timestampToPixel(bar.timestamp),
                y: priceToPixel(currentVwap)
            });
        }

        if (vwapPoints.length === 0) return;

        // Draw VWAP line
        c.strokeStyle = CHART_THEME.accentCyan;
        c.lineWidth = isSelected ? 2.5 : 2;
        c.beginPath();
        c.moveTo(vwapPoints[0].x, vwapPoints[0].y);
        for (let i = 1; i < vwapPoints.length; i++) {
            c.lineTo(vwapPoints[i].x, vwapPoints[i].y);
        }
        c.stroke();

        // Standard deviation bands
        // Standard calculation of standard deviation for VWAP
        const bands: { points: {x: number, y: number}[], multiplier: number }[] = [
            { points: [], multiplier: 1 },
            { points: [], multiplier: -1 },
            { points: [], multiplier: 2 },
            { points: [], multiplier: -2 }
        ];

        let sumSqDiff = 0;
        for (let i = 0; i < vwapValues.length; i++) {
            const bar = bars[startIndex + i];
            const typicalPrice = (bar.high + bar.low + bar.close) / 3;
            const diff = typicalPrice - vwapValues[i];
            sumSqDiff += (diff * diff) * bar.volume;
            const stdDev = Math.sqrt(sumSqDiff / cumVol);

            bands.forEach(band => {
                band.points.push({
                    x: vwapPoints[i].x,
                    y: priceToPixel(vwapValues[i] + stdDev * band.multiplier)
                });
            });
        }

        // Draw bands
        c.setLineDash([4, 4]);
        bands.forEach((band, idx) => {
            c.strokeStyle = Math.abs(band.multiplier) === 1 
                ? 'rgba(100, 255, 218, 0.5)' 
                : 'rgba(100, 255, 218, 0.25)';
            c.beginPath();
            c.moveTo(band.points[0].x, band.points[0].y);
            for (let i = 1; i < band.points.length; i++) {
                c.lineTo(band.points[i].x, band.points[i].y);
            }
            c.stroke();
        });
        c.setLineDash([]);

        // Label
        c.font = 'bold 9px monospace';
        c.fillStyle = CHART_THEME.accentCyan;
        const lastPoint = vwapPoints[vwapPoints.length - 1];
        c.textAlign = 'left';
        c.fillText('aVWAP', lastPoint.x + 5, lastPoint.y - 8);

        if (isSelected || isHovered) {
            drawAnchor(c, timestampToPixel(anchorTime), priceToPixel(anchor.price), isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const ax = timestampToPixel(drawing.anchors[0].timestamp);
        const ay = priceToPixel(drawing.anchors[0].price);

        if (distanceToPoint(x, y, ax, ay) < 10) {
            return { hit: true, anchorIndex: 0, distance: 0 };
        }

        // Check if on the line
        if (x >= ax && Math.abs(y - ay) < 5) {
            return { hit: true, distance: Math.abs(y - ay) };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'anchoredVWAP',
        symbol: '',
        category: 'volume',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accentCyan, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// FIXED RANGE VOLUME PROFILE
// =============================================================================

export const FixedRangeVPTool: DrawingToolDefinition = {
    type: 'fixedRangeVP',
    name: 'Fixed Range Volume Profile',
    icon: 'VP',
    category: 'volume',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2 || !ctx.bars) return;

        const { ctx: c, priceToPixel, timestampToPixel, bars } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const y1 = priceToPixel(a1.price);
        const y2 = priceToPixel(a2.price);

        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        const t1 = Math.min(a1.timestamp, a2.timestamp);
        const t2 = Math.max(a1.timestamp, a2.timestamp);

        // Filter bars in range
        const rangeBars = bars.filter(b => b.timestamp >= t1 && b.timestamp <= t2);
        if (rangeBars.length === 0) return;

        const highPrice = Math.max(...rangeBars.map(b => b.high));
        const lowPrice = Math.min(...rangeBars.map(b => b.low));
        const priceRange = highPrice - lowPrice;

        const numBins = 40;
        const binSize = priceRange / numBins;
        const bins = Array(numBins).fill(0);
        const buyBins = Array(numBins).fill(0); // Optional: Delta profile

        rangeBars.forEach(bar => {
            const barMid = (bar.high + bar.low) / 2;
            const binIdx = Math.min(numBins - 1, Math.floor((barMid - lowPrice) / binSize));
            if (binIdx >= 0) {
                bins[binIdx] += bar.volume;
            }
        });

        const maxVol = Math.max(...bins);
        const profileWidth = (right - left) * 0.4;
        
        // Find POC index
        const pocIdx = bins.indexOf(maxVol);
        const pocPrice = lowPrice + (pocIdx + 0.5) * binSize;

        // Draw bars
        for (let i = 0; i < numBins; i++) {
            const barYStart = priceToPixel(lowPrice + i * binSize);
            const barYEnd = priceToPixel(lowPrice + (i + 1) * binSize);
            const h = Math.abs(barYStart - barYEnd);
            const w = (bins[i] / maxVol) * profileWidth;
            
            c.fillStyle = i === pocIdx 
                ? 'rgba(255, 214, 10, 0.7)' 
                : 'rgba(100, 255, 218, 0.35)';
            c.fillRect(right - w, Math.min(barYStart, barYEnd), w, h - 0.5);
        }

        // POC Line
        c.strokeStyle = CHART_THEME.accent;
        c.lineWidth = 1.5;
        const pocY = priceToPixel(pocPrice);
        c.beginPath();
        c.moveTo(left, pocY);
        c.lineTo(right, pocY);
        c.stroke();
        
        c.fillStyle = CHART_THEME.accent;
        c.font = 'bold 9px monospace';
        c.fillText('POC', left + 5, pocY - 2);

        // Box border
        c.strokeStyle = drawing.style.color;
        c.setLineDash([4, 4]);
        c.strokeRect(left, priceToPixel(highPrice), right - left, Math.abs(priceToPixel(highPrice) - priceToPixel(lowPrice)));
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
        type: 'fixedRangeVP',
        symbol: '',
        category: 'volume',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accentCyan, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// SESSION VWAP
// =============================================================================

export const SessionVWAPTool: DrawingToolDefinition = {
    type: 'sessionVWAP',
    name: 'Session VWAP',
    icon: 'sVWAP',
    category: 'volume',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2 || !ctx.bars) return;

        const { ctx: c, priceToPixel, timestampToPixel, bars } = ctx;
        const [a1, a2] = drawing.anchors;

        const t1 = Math.min(a1.timestamp, a2.timestamp);
        const t2 = Math.max(a1.timestamp, a2.timestamp);

        const rangeBars = bars.filter(b => b.timestamp >= t1 && b.timestamp <= t2);
        if (rangeBars.length === 0) return;

        // Group bars by session (day)
        const sessions: OHLCVBar[][] = [];
        let currentSession: OHLCVBar[] = [];
        let lastDay = -1;

        rangeBars.forEach(bar => {
            const day = new Date(bar.timestamp).getDate();
            if (day !== lastDay) {
                if (currentSession.length > 0) sessions.push(currentSession);
                currentSession = [bar];
                lastDay = day;
            } else {
                currentSession.push(bar);
            }
        });
        if (currentSession.length > 0) sessions.push(currentSession);

        // Draw each session's VWAP
        sessions.forEach(session => {
            let cumPv = 0;
            let cumVol = 0;
            const points: { x: number, y: number }[] = [];

            session.forEach(bar => {
                const typicalPrice = (bar.high + bar.low + bar.close) / 3;
                cumPv += typicalPrice * bar.volume;
                cumVol += bar.volume;
                const vwap = cumPv / cumVol;

                points.push({
                    x: timestampToPixel(bar.timestamp),
                    y: priceToPixel(vwap)
                });
            });

            if (points.length < 2) return;

            c.strokeStyle = '#f472b6';
            c.lineWidth = isSelected ? 2.5 : 1.5;
            c.beginPath();
            c.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                c.lineTo(points[i].x, points[i].y);
            }
            c.stroke();
        });

        if (isSelected || isHovered) {
            drawAnchor(c, timestampToPixel(a1.timestamp), priceToPixel(a1.price), isSelected);
            drawAnchor(c, timestampToPixel(a2.timestamp), priceToPixel(a2.price), isSelected);
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
        type: 'sessionVWAP',
        symbol: '',
        category: 'volume',
        anchors,
        style: { ...defaultDrawingStyle, color: '#f472b6', ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// VOLUME DELTA ZONE
// =============================================================================

export const VolumeDeltaTool: DrawingToolDefinition = {
    type: 'volumeDelta',
    name: 'Volume Delta Zone',
    icon: 'Δ',
    category: 'volume',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2 || !ctx.bars) return;

        const { ctx: c, priceToPixel, timestampToPixel, bars } = ctx;
        const [a1, a2] = drawing.anchors;

        const x1 = timestampToPixel(a1.timestamp);
        const x2 = timestampToPixel(a2.timestamp);
        const y1 = priceToPixel(a1.price);
        const y2 = priceToPixel(a2.price);

        const left = Math.min(x1, x2);
        const right = Math.max(x1, x2);
        const t1 = Math.min(a1.timestamp, a2.timestamp);
        const t2 = Math.max(a1.timestamp, a2.timestamp);

        // Calculate real Delta
        const rangeBars = bars.filter(b => b.timestamp >= t1 && b.timestamp <= t2);
        let buyVol = 0;
        let sellVol = 0;

        rangeBars.forEach(b => {
            if (b.close >= b.open) buyVol += b.volume;
            else sellVol += b.volume;
        });

        const netDelta = buyVol - sellVol;
        const isBullish = netDelta >= 0;

        // Zone fill
        const top = Math.min(y1, y2);
        const bottom = Math.max(y1, y2);
        const gradient = c.createLinearGradient(left, top, left, bottom);
        if (isBullish) {
            gradient.addColorStop(0, 'rgba(0, 255, 136, 0.25)');
            gradient.addColorStop(1, 'rgba(0, 255, 136, 0.05)');
        } else {
            gradient.addColorStop(0, 'rgba(255, 45, 85, 0.05)');
            gradient.addColorStop(1, 'rgba(255, 45, 85, 0.25)');
        }

        c.fillStyle = gradient;
        c.fillRect(left, top, right - left, bottom - top);

        // Border
        c.strokeStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
        c.lineWidth = isSelected ? 2 : 1;
        c.setLineDash([4, 4]);
        c.strokeRect(left, top, right - left, bottom - top);
        c.setLineDash([]);

        // Delta label
        const deltaStr = (netDelta / 1000).toFixed(1) + 'K';
        c.font = 'bold 12px monospace';
        c.fillStyle = isBullish ? CHART_THEME.upColor : CHART_THEME.downColor;
        c.textAlign = 'center';
        c.fillText(isBullish ? `+${deltaStr}` : deltaStr, (left + right) / 2, (top + bottom) / 2);
        c.font = '9px monospace';
        c.fillText('VOLUME DELTA', (left + right) / 2, (top + bottom) / 2 + 14);

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
        type: 'volumeDelta',
        symbol: '',
        category: 'volume',
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

export const volumeTools = [
    AnchoredVWAPTool,
    FixedRangeVPTool,
    SessionVWAPTool,
    VolumeDeltaTool,
];
