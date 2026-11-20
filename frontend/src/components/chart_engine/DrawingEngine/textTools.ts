/**
 * Drawing Engine - Text and Annotation Tools
 * Text Label, Price Label, Note Box, Callout, Arrow Label, Sticky Note
 */

import { DrawingToolDefinition, defaultDrawingStyle, generateDrawingId, drawAnchor, distanceToPoint } from './baseTool';
import { CHART_THEME } from '../types';

// =============================================================================
// TEXT LABEL
// =============================================================================

export const TextLabelTool: DrawingToolDefinition = {
    type: 'textLabel',
    name: 'Text Label',
    icon: 'T',
    category: 'text',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const anchor = drawing.anchors[0];
        const x = timestampToPixel(anchor.timestamp);
        const y = priceToPixel(anchor.price);

        const text = (drawing.data?.text as string) || 'Label';
        const fontSize = drawing.style.fontSize || 12;

        c.font = `bold ${fontSize}px monospace`;
        const textWidth = c.measureText(text).width;
        const padding = 6;
        const boxWidth = textWidth + padding * 2;
        const boxHeight = fontSize + padding * 2;

        // Background box
        c.fillStyle = isSelected ? 'rgba(255, 214, 10, 0.2)' : 'rgba(3, 5, 10, 0.9)';
        c.strokeStyle = isSelected ? CHART_THEME.accent : drawing.style.color;
        c.lineWidth = isSelected ? 2 : 1;
        c.fillRect(x - boxWidth / 2, y - boxHeight / 2, boxWidth, boxHeight);
        c.strokeRect(x - boxWidth / 2, y - boxHeight / 2, boxWidth, boxHeight);

        // Text
        c.fillStyle = drawing.style.fontColor || CHART_THEME.textPrimary;
        c.textAlign = 'center';
        c.textBaseline = 'middle';
        c.fillText(text, x, y);

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const ax = timestampToPixel(drawing.anchors[0].timestamp);
        const ay = priceToPixel(drawing.anchors[0].price);

        const text = (drawing.data?.text as string) || 'Label';
        const fontSize = drawing.style.fontSize || 12;
        const padding = 6;
        const boxWidth = text.length * fontSize * 0.6 + padding * 2;
        const boxHeight = fontSize + padding * 2;

        if (Math.abs(x - ax) < boxWidth / 2 && Math.abs(y - ay) < boxHeight / 2) {
            return { hit: true, anchorIndex: 0, distance: 0 };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'textLabel',
        symbol: '',
        category: 'text',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        data: { text: 'Label' },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// PRICE LABEL
// =============================================================================

export const PriceLabelTool: DrawingToolDefinition = {
    type: 'priceLabel',
    name: 'Price Label',
    icon: '$',
    category: 'text',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel, width } = ctx;
        const anchor = drawing.anchors[0];
        const x = timestampToPixel(anchor.timestamp);
        const y = priceToPixel(anchor.price);

        // Horizontal line extending to right edge
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.setLineDash([4, 4]);
        c.beginPath();
        c.moveTo(x, y);
        c.lineTo(width, y);
        c.stroke();
        c.setLineDash([]);

        // Price label on right side
        const priceText = `$${anchor.price.toFixed(2)}`;
        c.font = 'bold 10px monospace';
        const textWidth = c.measureText(priceText).width;
        const padding = 4;
        const labelWidth = textWidth + padding * 2;
        const labelHeight = 16;

        // Label background
        c.fillStyle = drawing.style.color;
        c.fillRect(width - labelWidth - 2, y - labelHeight / 2, labelWidth, labelHeight);

        // Label text
        c.fillStyle = CHART_THEME.bgPrimary;
        c.textAlign = 'center';
        c.textBaseline = 'middle';
        c.fillText(priceText, width - labelWidth / 2 - 2, y);

        // Anchor marker
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.arc(x, y, 4, 0, Math.PI * 2);
        c.fill();

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
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
        type: 'priceLabel',
        symbol: '',
        category: 'text',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accent, ...style },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// NOTE BOX
// =============================================================================

export const NoteBoxTool: DrawingToolDefinition = {
    type: 'noteBox',
    name: 'Note Box',
    icon: '📝',
    category: 'text',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const anchor = drawing.anchors[0];
        const x = timestampToPixel(anchor.timestamp);
        const y = priceToPixel(anchor.price);

        const text = (drawing.data?.text as string) || 'Note';
        const lines = text.split('\n');
        const fontSize = 10;
        const lineHeight = 14;
        const padding = 8;

        c.font = `${fontSize}px monospace`;
        const maxWidth = Math.max(...lines.map(line => c.measureText(line).width));
        const boxWidth = maxWidth + padding * 2;
        const boxHeight = lines.length * lineHeight + padding * 2;

        // Shadow
        c.fillStyle = 'rgba(0, 0, 0, 0.3)';
        c.fillRect(x + 3, y + 3, boxWidth, boxHeight);

        // Background (sticky note yellow)
        const bgColor = (drawing.data?.bgColor as string) || '#fff9c4';
        c.fillStyle = bgColor;
        c.fillRect(x, y, boxWidth, boxHeight);

        // Border
        c.strokeStyle = isSelected ? CHART_THEME.accent : '#ddd';
        c.lineWidth = isSelected ? 2 : 1;
        c.strokeRect(x, y, boxWidth, boxHeight);

        // Text
        c.fillStyle = '#333';
        c.textAlign = 'left';
        c.textBaseline = 'top';
        lines.forEach((line, i) => {
            c.fillText(line, x + padding, y + padding + i * lineHeight);
        });

        // Fold corner
        c.fillStyle = '#f0e68c';
        c.beginPath();
        c.moveTo(x + boxWidth - 10, y);
        c.lineTo(x + boxWidth, y + 10);
        c.lineTo(x + boxWidth - 10, y + 10);
        c.closePath();
        c.fill();

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const ax = timestampToPixel(drawing.anchors[0].timestamp);
        const ay = priceToPixel(drawing.anchors[0].price);

        const text = (drawing.data?.text as string) || 'Note';
        const lines = text.split('\n');
        const boxWidth = 150;
        const boxHeight = lines.length * 14 + 16;

        if (x >= ax && x <= ax + boxWidth && y >= ay && y <= ay + boxHeight) {
            return { hit: true, anchorIndex: 0, distance: 0 };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'noteBox',
        symbol: '',
        category: 'text',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        data: { text: 'Add note...', bgColor: '#fff9c4' },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// CALLOUT
// =============================================================================

export const CalloutTool: DrawingToolDefinition = {
    type: 'callout',
    name: 'Callout',
    icon: '💬',
    category: 'text',
    minAnchors: 2,
    maxAnchors: 2,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 2) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const [anchor, textPos] = drawing.anchors;
        const ax = timestampToPixel(anchor.timestamp);
        const ay = priceToPixel(anchor.price);
        const tx = timestampToPixel(textPos.timestamp);
        const ty = priceToPixel(textPos.price);

        const text = (drawing.data?.text as string) || 'Callout';
        const fontSize = 11;
        const padding = 10;

        c.font = `bold ${fontSize}px monospace`;
        const textWidth = c.measureText(text).width;
        const boxWidth = textWidth + padding * 2;
        const boxHeight = fontSize + padding * 2;

        // Leader line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.beginPath();
        c.moveTo(ax, ay);
        c.lineTo(tx, ty);
        c.stroke();

        // Anchor point
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.arc(ax, ay, 4, 0, Math.PI * 2);
        c.fill();

        // Callout box with rounded corners
        const radius = 4;
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.moveTo(tx - boxWidth / 2 + radius, ty - boxHeight / 2);
        c.lineTo(tx + boxWidth / 2 - radius, ty - boxHeight / 2);
        c.arcTo(tx + boxWidth / 2, ty - boxHeight / 2, tx + boxWidth / 2, ty - boxHeight / 2 + radius, radius);
        c.lineTo(tx + boxWidth / 2, ty + boxHeight / 2 - radius);
        c.arcTo(tx + boxWidth / 2, ty + boxHeight / 2, tx + boxWidth / 2 - radius, ty + boxHeight / 2, radius);
        c.lineTo(tx - boxWidth / 2 + radius, ty + boxHeight / 2);
        c.arcTo(tx - boxWidth / 2, ty + boxHeight / 2, tx - boxWidth / 2, ty + boxHeight / 2 - radius, radius);
        c.lineTo(tx - boxWidth / 2, ty - boxHeight / 2 + radius);
        c.arcTo(tx - boxWidth / 2, ty - boxHeight / 2, tx - boxWidth / 2 + radius, ty - boxHeight / 2, radius);
        c.closePath();
        c.fill();

        // Border if selected
        if (isSelected) {
            c.strokeStyle = CHART_THEME.textPrimary;
            c.lineWidth = 2;
            c.stroke();
        }

        // Text
        c.fillStyle = CHART_THEME.bgPrimary;
        c.textAlign = 'center';
        c.textBaseline = 'middle';
        c.fillText(text, tx, ty);

        if (isSelected || isHovered) {
            drawAnchor(c, ax, ay, isSelected);
            drawAnchor(c, tx, ty, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

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
        type: 'callout',
        symbol: '',
        category: 'text',
        anchors,
        style: { ...defaultDrawingStyle, color: CHART_THEME.accentBlue, ...style },
        data: { text: 'Callout' },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// ARROW LABEL
// =============================================================================

export const ArrowLabelTool: DrawingToolDefinition = {
    type: 'arrowLabel',
    name: 'Arrow Label',
    icon: '→T',
    category: 'text',
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

        const text = (drawing.data?.text as string) || 'Label';

        // Arrow line
        c.strokeStyle = drawing.style.color;
        c.lineWidth = isSelected ? 2 : 1.5;
        c.beginPath();
        c.moveTo(x1, y1);
        c.lineTo(x2, y2);
        c.stroke();

        // Arrow head
        const angle = Math.atan2(y2 - y1, x2 - x1);
        const headSize = 8;
        c.fillStyle = drawing.style.color;
        c.beginPath();
        c.moveTo(x2, y2);
        c.lineTo(x2 - headSize * Math.cos(angle - Math.PI / 6), y2 - headSize * Math.sin(angle - Math.PI / 6));
        c.lineTo(x2 - headSize * Math.cos(angle + Math.PI / 6), y2 - headSize * Math.sin(angle + Math.PI / 6));
        c.closePath();
        c.fill();

        // Text label at midpoint
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;

        c.font = 'bold 10px monospace';
        const textWidth = c.measureText(text).width;
        const padding = 4;

        // Label background
        c.fillStyle = 'rgba(3, 5, 10, 0.9)';
        c.fillRect(midX - textWidth / 2 - padding, midY - 8 - padding, textWidth + padding * 2, 16 + padding);
        c.strokeStyle = drawing.style.color;
        c.lineWidth = 1;
        c.strokeRect(midX - textWidth / 2 - padding, midY - 8 - padding, textWidth + padding * 2, 16 + padding);

        // Label text
        c.fillStyle = drawing.style.color;
        c.textAlign = 'center';
        c.textBaseline = 'middle';
        c.fillText(text, midX, midY);

        if (isSelected || isHovered) {
            drawAnchor(c, x1, y1, isSelected);
            drawAnchor(c, x2, y2, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 2) return { hit: false, distance: Infinity };

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
        type: 'arrowLabel',
        symbol: '',
        category: 'text',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        data: { text: 'Label' },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// SIGNPOST (Up/Down Arrow with text)
// =============================================================================

export const SignpostTool: DrawingToolDefinition = {
    type: 'signpost',
    name: 'Signpost',
    icon: '⬆',
    category: 'text',
    minAnchors: 1,
    maxAnchors: 1,

    render: (drawing, ctx, isSelected, isHovered) => {
        if (drawing.anchors.length < 1) return;

        const { ctx: c, priceToPixel, timestampToPixel } = ctx;
        const anchor = drawing.anchors[0];
        const x = timestampToPixel(anchor.timestamp);
        const y = priceToPixel(anchor.price);

        const isUp = (drawing.data?.direction as string) !== 'down';
        const text = (drawing.data?.text as string) || (isUp ? 'BUY' : 'SELL');
        const color = isUp ? CHART_THEME.upColor : CHART_THEME.downColor;

        // Arrow
        const arrowSize = 20;
        c.fillStyle = color;
        c.beginPath();
        if (isUp) {
            c.moveTo(x, y - arrowSize);
            c.lineTo(x - 8, y);
            c.lineTo(x - 3, y);
            c.lineTo(x - 3, y + 10);
            c.lineTo(x + 3, y + 10);
            c.lineTo(x + 3, y);
            c.lineTo(x + 8, y);
        } else {
            c.moveTo(x, y + arrowSize);
            c.lineTo(x - 8, y);
            c.lineTo(x - 3, y);
            c.lineTo(x - 3, y - 10);
            c.lineTo(x + 3, y - 10);
            c.lineTo(x + 3, y);
            c.lineTo(x + 8, y);
        }
        c.closePath();
        c.fill();

        // Text label
        c.font = 'bold 9px monospace';
        c.fillStyle = color;
        c.textAlign = 'center';
        c.fillText(text, x, isUp ? y + 25 : y - 20);

        if (isSelected || isHovered) {
            drawAnchor(c, x, y, isSelected);
        }
    },

    hitTest: (drawing, x, y, ctx) => {
        if (drawing.anchors.length < 1) return { hit: false, distance: Infinity };

        const { priceToPixel, timestampToPixel } = ctx;
        const ax = timestampToPixel(drawing.anchors[0].timestamp);
        const ay = priceToPixel(drawing.anchors[0].price);

        if (distanceToPoint(x, y, ax, ay) < 20) {
            return { hit: true, anchorIndex: 0, distance: 0 };
        }

        return { hit: false, distance: Infinity };
    },

    createDrawing: (anchors, style) => ({
        id: generateDrawingId(),
        type: 'signpost',
        symbol: '',
        category: 'text',
        anchors,
        style: { ...defaultDrawingStyle, ...style },
        data: { direction: 'up', text: 'BUY' },
        visible: true,
        locked: false,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    }),
};

// =============================================================================
// EXPORTS
// =============================================================================

export const textTools = [
    TextLabelTool,
    PriceLabelTool,
    NoteBoxTool,
    CalloutTool,
    ArrowLabelTool,
    SignpostTool,
];
