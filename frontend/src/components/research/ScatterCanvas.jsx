"use client";

import React, { useMemo, useState, useRef, useEffect, useCallback } from 'react';
import { researchTokens } from '@/lib/theme/researchTokens';

/**
 * ScatterCanvas - Canvas-based scatter plot with pan, zoom, and selection.
 */
export default function ScatterCanvas({
    points = [],          // [{ ticker, x, y, color, size }]
    xLabel = 'X',
    yLabel = 'Y',
    colorLabel = 'Color',
    sizeLabel = 'Size',
    width = 600,
    height = 400,
    showLabels = false,
    onPointClick,
    selectedTickers = []
}) {
    const canvasRef = useRef(null);
    const [hoveredPoint, setHoveredPoint] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState(null);

    // Calculate data bounds
    const bounds = useMemo(() => {
        if (points.length === 0) return { minX: -2, maxX: 2, minY: -2, maxY: 2 };

        const xs = points.map(p => p.x).filter(v => v !== null);
        const ys = points.map(p => p.y).filter(v => v !== null);

        if (xs.length === 0 || ys.length === 0) return { minX: -2, maxX: 2, minY: -2, maxY: 2 };

        const padding = 0.2;
        const minX = Math.min(...xs);
        const maxX = Math.max(...xs);
        const minY = Math.min(...ys);
        const maxY = Math.max(...ys);

        const rangeX = maxX - minX || 1;
        const rangeY = maxY - minY || 1;

        return {
            minX: minX - rangeX * padding,
            maxX: maxX + rangeX * padding,
            minY: minY - rangeY * padding,
            maxY: maxY + rangeY * padding
        };
    }, [points]);

    const boundsKey = `${bounds.minX}:${bounds.maxX}:${bounds.minY}:${bounds.maxY}`;
    const boundsViewBox = useMemo(() => ({
        x: bounds.minX,
        y: bounds.minY,
        width: bounds.maxX - bounds.minX,
        height: bounds.maxY - bounds.minY
    }), [bounds]);
    const [storedViewBox, setStoredViewBox] = useState({ key: '', value: null });
    const viewBox = storedViewBox.key === boundsKey ? storedViewBox.value : boundsViewBox;
    const setViewBox = useCallback((next) => {
        setStoredViewBox(previous => {
            const current = previous.key === boundsKey ? previous.value : boundsViewBox;
            return {
                key: boundsKey,
                value: typeof next === 'function' ? next(current) : next
            };
        });
    }, [boundsKey, boundsViewBox]);

    // Reset view to data bounds
    const resetView = useCallback(() => {
        setStoredViewBox({ key: boundsKey, value: boundsViewBox });
    }, [boundsKey, boundsViewBox]);

    // Transform data to canvas coordinates
    const toCanvas = useCallback((x, y) => {
        const cx = ((x - viewBox.x) / viewBox.width) * width;
        const cy = height - ((y - viewBox.y) / viewBox.height) * height;
        return { cx, cy };
    }, [viewBox, width, height]);

    // Transform canvas to data coordinates
    const toData = useCallback((cx, cy) => {
        const x = (cx / width) * viewBox.width + viewBox.x;
        const y = ((height - cy) / height) * viewBox.height + viewBox.y;
        return { x, y };
    }, [viewBox, width, height]);

    // Color scale
    const colorScale = useCallback((value) => {
        if (value === null || value === undefined) return researchTokens.colors.muted;
        // Normalized -2 to 2 typically for Z-scores
        const normalized = Math.max(0, Math.min(1, (value + 2) / 4));

        // Simple Gradient: Blue (Low) -> Purple (Mid) -> Yellow (High)
        if (normalized < 0.5) {
            // Blue to Purple
            const t = normalized * 2;
            const r = Math.round(59 + t * (168 - 59));
            const g = Math.round(130 + t * (85 - 130));
            const b = Math.round(246 + t * (247 - 246));
            return `rgb(${r}, ${g}, ${b})`;
        } else {
            // Purple to Yellow
            const t = (normalized - 0.5) * 2;
            const r = Math.round(168 + t * (250 - 168));
            const g = Math.round(85 + t * (204 - 85));
            const b = Math.round(247 + t * (21 - 247));
            return `rgb(${r}, ${g}, ${b})`;
        }
    }, []);

    // Size scale
    const sizeScale = useCallback((value) => {
        if (value === null || value === undefined) return 6;
        return Math.max(4, Math.min(24, 8 + value * 5));
    }, []);

    // Draw the plot
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, width, height);

        // Background
        ctx.fillStyle = researchTokens.colors.bg;
        ctx.fillRect(0, 0, width, height);

        // Grid lines
        ctx.strokeStyle = researchTokens.colors.border2;
        ctx.lineWidth = 1;

        // Vertical grid & labels
        const xStep = viewBox.width / 5;
        for (let i = 1; i < 5; i++) {
            const x = viewBox.x + i * xStep;
            const { cx } = toCanvas(x, 0);
            ctx.beginPath();
            ctx.moveTo(cx, 0);
            ctx.lineTo(cx, height);
            ctx.stroke();

            // Label
            ctx.fillStyle = researchTokens.colors.muted;
            ctx.font = '10px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(x.toFixed(1), cx, height - 6);
        }

        // Horizontal grid & labels
        const yStep = viewBox.height / 5;
        for (let i = 1; i < 5; i++) {
            const y = viewBox.y + i * yStep;
            const { cy } = toCanvas(0, y);
            ctx.beginPath();
            ctx.moveTo(0, cy);
            ctx.lineTo(width, cy);
            ctx.stroke();

            // Label
            ctx.fillStyle = researchTokens.colors.muted;
            ctx.font = '10px monospace';
            ctx.textAlign = 'left';
            ctx.fillText(y.toFixed(1), 6, cy - 4);
        }

        // Zero lines (Axis)
        ctx.strokeStyle = researchTokens.colors.border;
        ctx.lineWidth = 1;

        if (viewBox.x < 0 && viewBox.x + viewBox.width > 0) {
            const { cx } = toCanvas(0, 0);
            ctx.beginPath();
            ctx.moveTo(cx, 0);
            ctx.lineTo(cx, height);
            ctx.stroke();
        }

        if (viewBox.y < 0 && viewBox.y + viewBox.height > 0) {
            const { cy } = toCanvas(0, 0);
            ctx.beginPath();
            ctx.moveTo(0, cy);
            ctx.lineTo(width, cy);
            ctx.stroke();
        }

        // Draw points
        points.forEach(point => {
            if (point.x === null || point.y === null) return;

            const { cx, cy } = toCanvas(point.x, point.y);
            const radius = sizeScale(point.size);
            const isSelected = selectedTickers.includes(point.ticker);
            const isHovered = hoveredPoint?.ticker === point.ticker;

            ctx.beginPath();
            ctx.arc(cx, cy, radius, 0, Math.PI * 2);
            ctx.fillStyle = colorScale(point.color);
            ctx.fill();

            if (isSelected || isHovered) {
                ctx.strokeStyle = researchTokens.colors.text;
                ctx.lineWidth = 2;
                ctx.stroke();

                // Outer glow for selection
                if (isSelected) {
                    ctx.beginPath();
                    ctx.arc(cx, cy, radius + 4, 0, Math.PI * 2);
                    ctx.strokeStyle = 'rgba(251, 191, 36, 0.5)';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            }

            // Label
            if (showLabels || isHovered || isSelected) {
                ctx.fillStyle = isSelected ? researchTokens.colors.warn : researchTokens.colors.text;
                ctx.font = isSelected ? 'bold 11px monospace' : '10px monospace';
                ctx.textAlign = 'center';
                ctx.fillText(point.ticker, cx, cy - radius - 6);
            }
        });

    }, [points, viewBox, width, height, showLabels, hoveredPoint, selectedTickers, toCanvas, colorScale, sizeScale]);

    // Mouse handlers
    const handleMouseMove = useCallback((e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;

        if (isDragging && dragStart) {
            const dx = (dragStart.cx - cx) / width * viewBox.width;
            const dy = (cy - dragStart.cy) / height * viewBox.height;
            setViewBox(prev => ({
                ...prev,
                x: dragStart.viewBox.x + dx,
                y: dragStart.viewBox.y + dy
            }));
            return;
        }

        // Find hovered point
        const { x, y } = toData(cx, cy);
        let closest = null;
        let minDist = Infinity;

        points.forEach(point => {
            if (point.x === null || point.y === null) return;
            const dist = Math.sqrt((point.x - x) ** 2 + (point.y - y) ** 2);
            const pixelDist = dist / viewBox.width * width;
            if (pixelDist < 20 && dist < minDist) {
                minDist = dist;
                closest = point;
            }
        });

        setHoveredPoint(closest);
    }, [isDragging, dragStart, points, viewBox, width, height, toData, setViewBox]);

    const handleMouseDown = useCallback((e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        setIsDragging(true);
        setDragStart({
            cx: e.clientX - rect.left,
            cy: e.clientY - rect.top,
            viewBox: { ...viewBox }
        });
    }, [viewBox]);

    const handleMouseUp = useCallback(() => {
        setIsDragging(false);
        setDragStart(null);
    }, []);

    const handleClick = useCallback((e) => {
        if (hoveredPoint && onPointClick) {
            onPointClick(hoveredPoint);
        }
    }, [hoveredPoint, onPointClick]);

    const handleWheel = useCallback((e) => {
        e.preventDefault();
        const scale = e.deltaY > 0 ? 1.1 : 0.9;

        const rect = canvasRef.current.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const { x, y } = toData(cx, cy);

        setViewBox(prev => {
            const newWidth = prev.width * scale;
            const newHeight = prev.height * scale;
            return {
                x: x - (x - prev.x) * scale,
                y: y - (y - prev.y) * scale,
                width: newWidth,
                height: newHeight
            };
        });
    }, [toData, setViewBox]);

    return (
        <div className="scatter-container">
            <style jsx>{`
                .scatter-container {
                    position: relative;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                }
                .scatter-canvas {
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: ${researchTokens.radius.panel}px;
                    cursor: ${isDragging ? 'grabbing' : 'crosshair'};
                    background: ${researchTokens.colors.bg};
                    width: 100%;
                    height: 100%;
                }
                .scatter-tooltip {
                    position: absolute;
                    background: ${researchTokens.colors.surface2};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 11px;
                    pointer-events: none;
                    z-index: 100;
                    box-shadow: ${researchTokens.shadow.lg};
                }
                .tooltip-ticker {
                    font-weight: 700;
                    color: ${researchTokens.colors.text};
                    margin-bottom: 4px;
                    font-family: var(--font-mono);
                }
                .tooltip-row {
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                }
                .scatter-controls {
                    position: absolute;
                    bottom: 12px;
                    right: 12px;
                    display: flex;
                    gap: 8px;
                    align-items: center;
                }
                .scatter-btn {
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: ${researchTokens.colors.text};
                    font-size: 10px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    text-transform: uppercase;
                }
                .scatter-btn:hover {
                    background: ${researchTokens.colors.surface2};
                    color: ${researchTokens.colors.warn};
                }
                .axis-label {
                    font-size: 11px;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    pointer-events: none;
                }
                .x-label {
                    position: absolute;
                    bottom: 8px;
                    left: 50%;
                    transform: translateX(-50%);
                }
                .y-label {
                    position: absolute;
                    left: 8px;
                    top: 50%;
                    transform: translateY(-50%) rotate(-90deg);
                    transform-origin: center;
                }
                .legend {
                    position: absolute;
                    top: 12px;
                    right: 12px;
                    background: rgba(0,0,0,0.5);
                    padding: 8px;
                    border-radius: 4px;
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                }
                .legend-item {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 10px;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                }
                .legend-color {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                }
            `}</style>

            <div className="axis-label y-label">{yLabel}</div>

            <canvas
                ref={canvasRef}
                width={width}
                height={height}
                className="scatter-canvas"
                onMouseMove={handleMouseMove}
                onMouseDown={handleMouseDown}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onClick={handleClick}
                onWheel={handleWheel}
            />

            <div className="axis-label x-label">{xLabel}</div>

            {hoveredPoint && (
                <div
                    className="scatter-tooltip"
                    style={{
                        left: toCanvas(hoveredPoint.x, hoveredPoint.y).cx + 15,
                        top: toCanvas(hoveredPoint.x, hoveredPoint.y).cy - 50
                    }}
                >
                    <div className="tooltip-ticker">{hoveredPoint.ticker}</div>
                    <div className="tooltip-row">{xLabel}: {hoveredPoint.x?.toFixed(2)}</div>
                    <div className="tooltip-row">{yLabel}: {hoveredPoint.y?.toFixed(2)}</div>
                    <div className="tooltip-row">{colorLabel}: {hoveredPoint.color?.toFixed(2)}</div>
                </div>
            )}

            <div className="scatter-controls">
                <button className="scatter-btn" onClick={resetView}>Reset Zoom</button>
            </div>
        </div>
    );
}
