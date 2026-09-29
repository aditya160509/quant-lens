/**
 * Drawing Engine - Extended Gann Tools
 * Gann Box Fixed, Gann Square of 9, Gann Grid, Gann Square Range
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
    GANN_ANGLES,
} from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// GANN BOX FIXED
// =============================================================================

export const GannBoxFixedTool: DrawingToolDefinition = {
    type: 'gannBoxFixed',
    name: 'Gann Box Fixed',
    icon: '□F',
    category: 'gann',
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

        // Create a square based on the larger dimension
        const width = Math.abs(x2 - x1);
        const height = Math.abs(y2 - y1);
        const size = Math.max(width, height);
        
        const left = Math.min(x1, x2);
        const top = Math.min(y1, y2);

        // Outer box
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? 2 : 1.5;
        setLineStyle(c, drawing.style.lineStyle);
        c.strokeRect(left, top, size, size);

        // Gann divisions (1/4, 1/2, 3/4)
        const divisions = [0.25, 0.5, 0.75];

        c.setLineDash([3, 3]);
        c.strokeStyle = CHART_THEME.textSecondary;
        c.lineWidth = 0.5;

        // Horizontal divisions
        divisions.forEach(d => {
            const y = top + size * d;
            c.beginPath();
            c.moveTo(left, y);
            c.lineTo(left + size, y);
            c.stroke();

            // Label
            c.fillStyle = CHART_THEME.textMuted;
            c.font = '8px monospace';
            c.textAlign = 'right';
            c.fillText(`${(d * 100).toFixed(0)}%`, left - 5, y + 3);
        });

        // Vertical divisions
        divisions.forEach(d => {
            const x = left + size * d;
            c.beginPath();
            c.moveTo(x, top);
            c.lineTo(x, top + size);
            c.stroke();
        });

        c.setLineDash([]);

        // Diagonals from corners and midpoints
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;

        // Corner diagonals
        c.beginPath();
        c.moveTo(left, top);
        c.lineTo(left + size, top + size);
        c.stroke();

        c.beginPath();
        c.moveTo(left + size, top);
        c.lineTo(left, top + size);
        c.stroke();

        // 1x2 and 2x1 lines
        c.setLineDash([2, 2]);
        c.strokeStyle = CHART_THEME.accent;
        
        // 1x2 from bottom left
        c.beginPath();
        c.moveTo(left, top + size);
        c.lineTo(left + size * 0.5, top);
        c.stroke();

        // 2x1 from bottom left
        c.beginPath();
        c.moveTo(left, top + size);
        c.lineTo(left + size, top + size * 0.5);
        c.stroke();

        c.setLineDash([]);

        // Labels at corners
        c.font = 'bold 9px monospace';
        c.fillStyle = drawing.style.color;
        c.textAlign = 'center';
        c.fillText('0/360°', left, top - 5);
        c.fillText('90°', left + size, top - 5);
        c.fillText('180°', left + size, top + size + 12);
        c.fillText('270°', left, top + size + 12);

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
        type: 'gannBoxFixed',
        symbol: '',
        category: 'gann',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// GANN SQUARE OF 9
// =============================================================================

export const GannSquare9Tool: DrawingToolDefinition = {
    type: 'gannSquare9',
    name: 'Gann Square of 9',
    icon: '⊞9',
    category: 'gann',
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
        const centerY = (y1 + y2) / 2;
        const baseRadius = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 2;

        // Draw concentric circles (representing price levels)
        const levels = 9;
        
        for (let i = 1; i <= levels; i++) {
            const radius = (baseRadius / levels) * i;
            
            c.strokeStyle = i % 3 === 0 ? drawing.style.color : CHART_THEME.textSecondary;
            c.lineWidth = i % 3 === 0 ? 1.5 : 0.5;
            c.setLineDash(i % 3 === 0 ? [] : [2, 2]);

            c.beginPath();
            c.arc(centerX, centerY, radius, 0, Math.PI * 2);
            c.stroke();
        }

        c.setLineDash([]);

        // Draw cardinal and ordinal lines (8 divisions = 45° each)
        const angles = [0, 45, 90, 135, 180, 225, 270, 315];
        const angleLabels = ['0°', '45°', '90°', '135°', '180°', '225°', '270°', '315°'];

        angles.forEach((angleDeg, i) => {
            const angle = (angleDeg * Math.PI) / 180;
            
            c.strokeStyle = angleDeg % 90 === 0 ? drawing.style.color : CHART_THEME.textSecondary;
            c.lineWidth = angleDeg % 90 === 0 ? 1.5 : 0.5;

            c.beginPath();
            c.moveTo(centerX, centerY);
            c.lineTo(
                centerX + baseRadius * Math.cos(angle),
                centerY + baseRadius * Math.sin(angle)
            );
            c.stroke();

            // Labels at outer edge
            c.fillStyle = CHART_THEME.textSecondary;
            c.font = '8px monospace';
            c.textAlign = 'center';
            c.fillText(
                angleLabels[i],
                centerX + (baseRadius + 15) * Math.cos(angle),
                centerY + (baseRadius + 15) * Math.sin(angle)
            );
        });

        // Center point
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.arc(centerX, centerY, 3, 0, Math.PI * 2);
        c.fill();

        // Number spiral (simplified representation)
        c.font = '7px monospace';
        c.fillStyle = CHART_THEME.textMuted;
        c.textAlign = 'center';

        let num = 1;
        const spiralStep = baseRadius / (levels * 2);
        
        for (let ring = 0; ring < 4; ring++) {
            const r = ring * spiralStep * 2;
            const numPoints = ring === 0 ? 1 : ring * 8;
            
            for (let p = 0; p < numPoints; p++) {
                const angle = (p / numPoints) * Math.PI * 2 - Math.PI / 2;
                const px = centerX + r * Math.cos(angle);
                const py = centerY + r * Math.sin(angle);
                
                if (num <= 81) {
                    c.fillText(String(num), px, py);
                    num++;
                }
            }
        }

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
        type: 'gannSquare9',
        symbol: '',
        category: 'gann',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// GANN GRID
// =============================================================================

export const GannGridTool: DrawingToolDefinition = {
    type: 'gannGrid',
    name: 'Gann Grid',
    icon: '⊞G',
    category: 'gann',
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

        const cellWidth = Math.abs(x2 - x1);
        const cellHeight = Math.abs(y2 - y1);
        const startX = Math.min(x1, x2);
        const startY = Math.min(y1, y2);

        // Calculate how many cells fit in the chart
        const numCellsX = Math.ceil(width / cellWidth);
        const numCellsY = Math.ceil(height / cellHeight);

        // Draw grid
        c.strokeStyle = CHART_THEME.textMuted;
        c.lineWidth = 0.5;
        c.setLineDash([]);

        // Vertical lines
        for (let i = 0; i <= numCellsX; i++) {
            const x = startX + i * cellWidth;
            c.beginPath();
            c.moveTo(x, 0);
            c.lineTo(x, height);
            c.stroke();
        }

        // Horizontal lines
        for (let i = 0; i <= numCellsY; i++) {
            const y = startY + i * cellHeight;
            c.beginPath();
            c.moveTo(0, y);
            c.lineTo(width, y);
            c.stroke();
        }

        // Diagonal lines (45° angles)
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.setLineDash([4, 4]);

        // From each intersection point, draw 45° lines
        for (let i = 0; i <= numCellsX; i++) {
            const x = startX + i * cellWidth;
            
            // Upward diagonal
            c.beginPath();
            c.moveTo(x, height);
            c.lineTo(Math.min(x + height, width), 0);
            c.stroke();

            // Downward diagonal
            c.beginPath();
            c.moveTo(x, 0);
            c.lineTo(Math.min(x + height, width), height);
            c.stroke();
        }

        c.setLineDash([]);

        // Highlight the defining cell
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 2;
        c.strokeRect(Math.min(x1, x2), Math.min(y1, y2), cellWidth, cellHeight);

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
        type: 'gannGrid',
        symbol: '',
        category: 'gann',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// GANN SQUARE RANGE
// =============================================================================

export const GannSquareRangeTool: DrawingToolDefinition = {
    type: 'gannSquareRange',
    name: 'Gann Square Range',
    icon: '⊞R',
    category: 'gann',
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

        const priceRange = Math.abs(a2.price - a1.price);
        const left = Math.min(x1, x2);
        const top = Math.min(y1, y2);
        const boxWidth = Math.abs(x2 - x1);
        const boxHeight = Math.abs(y2 - y1);

        // Main box
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? 2 : 1.5;
        c.setLineDash([]);
        c.strokeRect(left, top, boxWidth, boxHeight);

        // Fill with subtle gradient
        const gradient = c.createLinearGradient(left, top, left, top + boxHeight);
        gradient.addColorStop(0, 'rgba(255, 214, 10, 0.1)');
        gradient.addColorStop(0.5, 'rgba(255, 214, 10, 0.05)');
        gradient.addColorStop(1, 'rgba(255, 214, 10, 0.1)');
        c.fillStyle = gradient;
        c.fillRect(left, top, boxWidth, boxHeight);

        // Square levels based on price range
        // Gann believed price = time, so we project time levels from price movement
        const squareRoot = Math.sqrt(a1.price);
        const increment = 1; // Each unit represents one "square"
        
        // Draw projected time levels
        const levels = [1, 2, 3, 4];
        
        levels.forEach(level => {
            const nextSquare = Math.pow(squareRoot + level * increment, 2);
            const projectedY = priceToPixel(nextSquare);
            
            if (projectedY > 0 && projectedY < ctx.height) {
                c.setLineDash([4, 4]);
                c.strokeStyle = CHART_THEME.textSecondary;
                c.lineWidth = 1;
                
                c.beginPath();
                c.moveTo(0, projectedY);
                c.lineTo(width, projectedY);
                c.stroke();

                c.fillStyle = CHART_THEME.textSecondary;
                c.font = '8px monospace';
                c.textAlign = 'right';
                c.fillText(`√+${level} = $${nextSquare.toFixed(2)}`, width - 5, projectedY - 3);
            }
        });

        c.setLineDash([]);

        // Central cross
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        
        const midX = left + boxWidth / 2;
        const midY = top + boxHeight / 2;

        c.beginPath();
        c.moveTo(midX, top);
        c.lineTo(midX, top + boxHeight);
        c.stroke();

        c.beginPath();
        c.moveTo(left, midY);
        c.lineTo(left + boxWidth, midY);
        c.stroke();

        // Price labels
        c.font = 'bold 9px monospace';
        c.fillStyle = drawing.style.color;
        c.textAlign = 'left';
        c.fillText(`High: $${Math.max(a1.price, a2.price).toFixed(2)}`, left + 5, top + 12);
        c.fillText(`Low: $${Math.min(a1.price, a2.price).toFixed(2)}`, left + 5, top + boxHeight - 5);
        c.fillText(`Range: $${priceRange.toFixed(2)}`, left + 5, midY - 3);

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
        type: 'gannSquareRange',
        symbol: '',
        category: 'gann',
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

export const extendedGannTools = [
    GannBoxFixedTool,
    GannSquare9Tool,
    GannGridTool,
    GannSquareRangeTool,
];
