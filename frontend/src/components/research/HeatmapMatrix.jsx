"use client";

import React, { useMemo } from 'react';
import { researchTokens } from '@/lib/theme/researchTokens';

/**
 * HeatmapMatrix - Interactive heatmap for correlation/beta matrices.
 * Upgraded for Cluster D Premium Terminal.
 * Features: Sticky headers, fixed cell size, research tokens.
 */
export default function HeatmapMatrix({
    data = {},           // { row: { col: value } }
    rows = [],           // Row labels
    cols = [],           // Column labels  
    colorScale = 'diverging',  // 'diverging' | 'sequential'
    minValue = -1,
    maxValue = 1,
    onCellClick,
    selectedCell = null,  // { row, col }
    title = ''
}) {
    // Color scale functions
    const getColor = useMemo(() => {
        if (colorScale === 'diverging') {
            // Blue (negative) -> Dark (zero) -> Red (positive)
            return (value) => {
                if (value === null || value === undefined) return researchTokens.colors.surface2;

                // Clamp
                const clamped = Math.max(minValue, Math.min(maxValue, value));
                const range = Math.max(0.0001, maxValue - minValue);
                const mid = (minValue + maxValue) / 2;

                // Normalized -1 to 1 around mid
                const norm = (clamped - mid) / (range / 2); // -1 to 1

                if (norm < 0) {
                    // Blue intensity
                    const intensity = Math.min(1, Math.abs(norm));
                    return `rgba(59, 130, 246, ${0.1 + intensity * 0.9})`;
                } else {
                    // Red intensity
                    const intensity = Math.min(1, norm);
                    return `rgba(239, 68, 68, ${0.1 + intensity * 0.9})`;
                }
            };
        } else {
            // Sequential: Transparent to Full Color (Purple)
            return (value) => {
                if (value === null || value === undefined) return researchTokens.colors.surface2;
                const normalized = (value - minValue) / (maxValue - minValue);
                const intensity = Math.max(0, Math.min(1, normalized));
                return `rgba(168, 85, 247, ${0.1 + intensity * 0.9})`;
            };
        }
    }, [colorScale, minValue, maxValue]);

    const getTextColor = (value) => {
        if (value === null || value === undefined) return researchTokens.colors.muted2;
        // If absolute value is high (dark background), use white. If low (transparent), use text color.
        // Since we use opacity, the bg is blackish.
        // Actually, opacity means background shows through. Our background is dark.
        // So always white text is fine, maybe dimmed for low values.
        return Math.abs(value) < 0.1 ? researchTokens.colors.muted : researchTokens.colors.text;
    };

    const cellSize = researchTokens.matrix.cellPx;
    const headerHeight = researchTokens.matrix.headerPx;
    const rowLabelWidth = researchTokens.matrix.rowLabelPx;

    return (
        <div className="heatmap-container">
            <style jsx>{`
                .heatmap-container {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    background: ${researchTokens.colors.surface};
                    border-radius: ${researchTokens.radius.panel}px;
                    overflow: hidden;
                }
                .heatmap-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 16px;
                    background: ${researchTokens.colors.surface};
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    flex-shrink: 0;
                }
                .heatmap-title {
                    font-size: 14px;
                    font-weight: 700;
                    color: ${researchTokens.colors.warn};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                }
                .heatmap-scroll-area {
                    flex-grow: 1;
                    overflow: auto;
                    position: relative;
                }
                .heatmap-table {
                    border-collapse: separate;
                    border-spacing: 1px;
                }
                th, td {
                    padding: 0;
                    margin: 0;
                }
                
                /* Sticky Column Headers */
                .col-header {
                    position: sticky;
                    top: 0;
                    z-index: 20;
                    height: ${headerHeight}px;
                    min-width: ${cellSize}px;
                    background: ${researchTokens.colors.surface};
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    font-size: 11px;
                    font-weight: 600;
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    text-align: center;
                    cursor: default;
                }
                 /* Corner */
                .corner-header {
                    position: sticky;
                    top: 0;
                    left: 0;
                    z-index: 30;
                    width: ${rowLabelWidth}px;
                    min-width: ${rowLabelWidth}px;
                    height: ${headerHeight}px;
                    background: ${researchTokens.colors.surface};
                    border-bottom: 1px solid ${researchTokens.colors.border};
                    border-right: 1px solid ${researchTokens.colors.border};
                }

                /* Sticky Row Labels */
                .row-header {
                    position: sticky;
                    left: 0;
                    z-index: 10;
                    width: ${rowLabelWidth}px;
                    min-width: ${rowLabelWidth}px;
                    height: ${cellSize}px;
                    background: ${researchTokens.colors.surface};
                    border-right: 1px solid ${researchTokens.colors.border};
                    color: ${researchTokens.colors.text};
                    font-family: var(--font-mono);
                    font-size: 11px;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    justify-content: flex-end;
                    padding-right: 12px;
                }
                .row-header:hover {
                    color: ${researchTokens.colors.warn};
                    background: ${researchTokens.colors.surface2};
                }

                .cell {
                    width: ${cellSize}px;
                    min-width: ${cellSize}px;
                    height: ${cellSize}px;
                    text-align: center;
                    vertical-align: middle;
                    font-family: var(--font-mono);
                    font-size: 11px;
                    font-weight: 700;
                    cursor: pointer;
                    transition: transform 0.1s, box-shadow 0.1s;
                }
                .cell:hover {
                    transform: scale(1.1);
                    z-index: 5;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                    border: 1px solid ${researchTokens.colors.text};
                }
                .cell.selected {
                    border: 2px solid ${researchTokens.colors.warn};
                    z-index: 6;
                }
                .null-cell {
                    background: repeating-linear-gradient(
                        45deg,
                        ${researchTokens.colors.surface2},
                        ${researchTokens.colors.surface2} 4px,
                        ${researchTokens.colors.bg} 4px,
                        ${researchTokens.colors.bg} 8px
                    );
                    color: ${researchTokens.colors.muted2};
                    font-size: 9px;
                }
                
                /* Legend */
                .heatmap-legend {
                    display: flex;
                    align-items: center;
                    justify-content: flex-end;
                    gap: 8px;
                    font-size: 10px;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                }
                .legend-gradient {
                    width: 100px;
                    height: 8px;
                    border-radius: 4px;
                    background: ${colorScale === 'diverging'
                    ? `linear-gradient(to right, ${researchTokens.accent.beta}, ${researchTokens.colors.bg}, ${researchTokens.accent.style})`
                    : `linear-gradient(to right, ${researchTokens.colors.bg}, ${researchTokens.accent.corr})`};
                    border: 1px solid ${researchTokens.colors.border};
                }
            `}</style>

            <div className="heatmap-header">
                <div className="heatmap-title">{title}</div>
                <div className="heatmap-legend">
                    <span>{minValue}</span>
                    <div className="legend-gradient"></div>
                    <span>{maxValue}</span>
                </div>
            </div>

            <div className="heatmap-scroll-area">
                <table className="heatmap-table">
                    <thead>
                        <tr>
                            <th className="corner-header"></th>
                            {cols.map(col => (
                                <th key={col} className="col-header">
                                    {col}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map(row => (
                            <tr key={row}>
                                <th className="row-header">{row}</th>
                                {cols.map(col => {
                                    const value = data[row]?.[col];
                                    const isNull = value === null || value === undefined;
                                    const isSelected = selectedCell?.row === row && selectedCell?.col === col;

                                    return (
                                        <td
                                            key={`${row}-${col}`}
                                            className={`cell ${isSelected ? 'selected' : ''} ${isNull ? 'null-cell' : ''}`}
                                            style={{
                                                backgroundColor: isNull ? undefined : getColor(value),
                                                color: isNull ? undefined : getTextColor(value)
                                            }}
                                            onClick={() => onCellClick?.({ row, col, value })}
                                            title={isNull ? 'Insufficient Data' : `${row} / ${col}: ${value.toFixed(4)}`}
                                        >
                                            {!isNull ? value.toFixed(2) : '-'}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

