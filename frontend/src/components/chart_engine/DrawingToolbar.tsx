/**
 * Drawing Toolbar - TradingView-style left sidebar for drawing tools
 * Provides access to all 38 drawing tools organized by category
 */

'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { CHART_THEME } from './types';

// =============================================================================
// ICONS - SVG icons for each tool category
// =============================================================================

const ICONS: Record<string, React.ReactNode> = {
    // Crosshair/Cursor
    cursor: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2v20M2 12h20" />
        </svg>
    ),
    // Lines
    lines: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="20" x2="20" y2="4" />
        </svg>
    ),
    // Fibonacci
    fibonacci: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4h16M4 9h16M4 14h16M4 20h16" />
            <path d="M4 4v16" strokeDasharray="2 2" />
        </svg>
    ),
    // Shapes
    shapes: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="4" y="4" width="16" height="16" rx="2" />
        </svg>
    ),
    // Channels
    channels: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="18" x2="20" y2="6" />
            <line x1="4" y1="22" x2="20" y2="10" />
        </svg>
    ),
    // Gann
    gann: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="4" y="4" width="16" height="16" />
            <line x1="4" y1="4" x2="20" y2="20" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="12" y1="4" x2="12" y2="20" />
        </svg>
    ),
    // Pitchforks
    pitchforks: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L4 20M12 2L20 20M12 2v18" />
        </svg>
    ),
    // Elliott Wave
    elliott: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 18L6 6L10 14L14 8L18 12L22 4" />
        </svg>
    ),
    // Patterns
    patterns: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 16L8 8L12 12L16 6L20 10" />
            <circle cx="8" cy="8" r="2" fill="currentColor" />
            <circle cx="16" cy="6" r="2" fill="currentColor" />
        </svg>
    ),
    // Brush
    brush: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 19l7-7 3 3-7 7-3-3z" />
            <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />
            <circle cx="6" cy="18" r="3" fill="currentColor" />
        </svg>
    ),
    // Text
    text: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 7V4h16v3M9 20h6M12 4v16" />
        </svg>
    ),
    // Eraser
    eraser: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20 20H9L4 15l7-7 9 9v3z" />
            <path d="M11 8l5 5" />
        </svg>
    ),
    // Measure
    measure: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4h16v16H4z" />
            <path d="M4 12h4M12 4v4M16 12h4M12 16v4" />
        </svg>
    ),
    // Zoom
    zoom: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="10" cy="10" r="7" />
            <path d="M21 21l-6-6" />
            <path d="M7 10h6M10 7v6" />
        </svg>
    ),
    // Projections
    projections: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 18L12 6l8 6" />
            <path d="M12 6v12" strokeDasharray="2 2" />
            <circle cx="12" cy="6" r="2" fill="currentColor" />
        </svg>
    ),
    // Volume
    volume: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="4" y="12" width="4" height="8" fill="currentColor" />
            <rect x="10" y="8" width="4" height="12" fill="currentColor" />
            <rect x="16" y="4" width="4" height="16" fill="currentColor" />
        </svg>
    ),
    screenshot: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" />
            <circle cx="12" cy="13" r="4" />
        </svg>
    ),
    export: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
        </svg>
    ),
    quant: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 20V10M18 20V4M6 20v-4" stroke="currentColor" strokeLinecap="round" />
            <path d="M3 20h18" stroke="currentColor" strokeLinecap="round" />
        </svg>
    ),
    liquidity: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 13h4M10 13h4M17 13h4M3 8h10M3 18h18M14 8h7" stroke="currentColor" strokeLinecap="round" />
        </svg>
    ),
    trash: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2M10 11v6M14 11v6" />
        </svg>
    ),
};

// =============================================================================
// TYPES
// =============================================================================

interface DrawingToolbarProps {
    activeTool: string | null;
    onToolSelect: (toolType: string | null) => void;
    onClearAll?: () => void;
    onScreenshot?: () => void;
    onExportData?: () => void;
}

interface ToolMenuState {
    [category: string]: boolean;
}

// =============================================================================
// COMPONENT
// =============================================================================

export default function DrawingToolbar({
    activeTool,
    onToolSelect,
    onClearAll,
    onScreenshot,
    onExportData,
}: DrawingToolbarProps) {
    const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const deleteTimerRef = useRef<NodeJS.Timeout | null>(null);

    const toggleCategory = useCallback((category: string) => {
        setExpandedCategory(prev => prev === category ? null : category);
    }, []);

    const handleToolClick = useCallback((toolType: string) => {
        onToolSelect(toolType);
        setExpandedCategory(null);
    }, [onToolSelect]);

    const handleClearClick = useCallback(() => {
        if (!confirmDelete) {
            setConfirmDelete(true);
            if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
            deleteTimerRef.current = setTimeout(() => setConfirmDelete(false), 3000);
        } else {
            onClearAll?.();
            setConfirmDelete(false);
            if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
        }
    }, [confirmDelete, onClearAll]);

    useEffect(() => {
        return () => {
            if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
        };
    }, []);

    return (
        <div
            className="flex flex-col items-center py-2 gap-1 h-full"
            style={{
                width: 44,
                background: CHART_THEME.bgSecondary,
                borderRight: `1px solid ${CHART_THEME.border}`,
                position: 'relative',
                zIndex: 50,
            }}
        >
            <div className="flex flex-col items-center gap-1 w-full pb-10">
                {/* Cursor/Selection Tool */}
                <ToolButton
                    icon={ICONS.cursor}
                    tooltip="Cursor"
                    active={activeTool === null}
                    onClick={() => onToolSelect(null)}
                />

                <Separator />

                {/* Lines */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.lines}
                        tooltip="Lines"
                        active={['trendLine', 'horizontalLine', 'verticalLine', 'horizontalRay', 'infoLine', 'extendedLine', 'crossLine'].includes(activeTool || '')}
                        expanded={expandedCategory === 'lines'}
                        onClick={() => toggleCategory('lines')}
                    />
                    {expandedCategory === 'lines' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'trendLine', name: 'Trend Line' },
                                { id: 'horizontalLine', name: 'Horizontal Line' },
                                { id: 'verticalLine', name: 'Vertical Line' },
                                { id: 'horizontalRay', name: 'Horizontal Ray' },
                                { id: 'infoLine', name: 'Info Line' },
                                { id: 'extendedLine', name: 'Extended Line' },
                                { id: 'crossLine', name: 'Cross Line' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Fibonacci */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.fibonacci}
                        tooltip="Fibonacci"
                        active={['fibRetracement', 'fibExtension', 'fibProjection', 'fibTimeZones', 'fibFan', 'fibArcs', 'fibCircles', 'fibSpiral', 'fibChannel', 'fibWedge'].includes(activeTool || '')}
                        expanded={expandedCategory === 'fibonacci'}
                        onClick={() => toggleCategory('fibonacci')}
                    />
                    {expandedCategory === 'fibonacci' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'fibRetracement', name: 'Fib Retracement' },
                                { id: 'fibExtension', name: 'Fib Extension' },
                                { id: 'fibProjection', name: 'Fib Projection' },
                                { id: 'fibTimeZones', name: 'Fib Time Zones' },
                                { id: 'fibFan', name: 'Fib Fan' },
                                { id: 'fibArcs', name: 'Fib Arcs' },
                                { id: 'fibCircles', name: 'Fib Circles' },
                                { id: 'fibSpiral', name: 'Fib Spiral' },
                                { id: 'fibChannel', name: 'Fib Channel' },
                                { id: 'fibWedge', name: 'Fib Wedge' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Shapes */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.shapes}
                        tooltip="Shapes"
                        active={['rectangle', 'rotatedRectangle', 'circle', 'ellipse', 'triangle', 'path', 'polyline', 'arc', 'curve', 'doubleCurve'].includes(activeTool || '')}
                        expanded={expandedCategory === 'shapes'}
                        onClick={() => toggleCategory('shapes')}
                    />
                    {expandedCategory === 'shapes' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'rectangle', name: 'Rectangle' },
                                { id: 'rotatedRectangle', name: 'Rotated Rectangle' },
                                { id: 'circle', name: 'Circle' },
                                { id: 'ellipse', name: 'Ellipse' },
                                { id: 'triangle', name: 'Triangle' },
                                { id: 'path', name: 'Path' },
                                { id: 'polyline', name: 'Polyline' },
                                { id: 'arc', name: 'Arc' },
                                { id: 'curve', name: 'Curve' },
                                { id: 'doubleCurve', name: 'Double Curve' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Arrows */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7" /></svg>}
                        tooltip="Arrows"
                        active={['arrow', 'arrowMarker', 'arrowMarkUp', 'arrowMarkDown'].includes(activeTool || '')}
                        expanded={expandedCategory === 'arrows'}
                        onClick={() => toggleCategory('arrows')}
                    />
                    {expandedCategory === 'arrows' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'arrow', name: 'Arrow' },
                                { id: 'arrowMarker', name: 'Arrow Marker' },
                                { id: 'arrowMarkUp', name: 'Arrow Mark Up' },
                                { id: 'arrowMarkDown', name: 'Arrow Mark Down' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Channels */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.channels}
                        tooltip="Channels"
                        active={['parallelChannel', 'regressionChannel', 'flatChannel'].includes(activeTool || '')}
                        expanded={expandedCategory === 'channels'}
                        onClick={() => toggleCategory('channels')}
                    />
                    {expandedCategory === 'channels' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'parallelChannel', name: 'Parallel Channel' },
                                { id: 'regressionChannel', name: 'Regression Channel' },
                                { id: 'flatChannel', name: 'Flat Channel' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Gann */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.gann}
                        tooltip="Gann"
                        active={['gannBox', 'gannBoxFixed', 'gannFan', 'gannSquare', 'gannSquare9', 'gannGrid', 'gannSquareRange'].includes(activeTool || '')}
                        expanded={expandedCategory === 'gann'}
                        onClick={() => toggleCategory('gann')}
                    />
                    {expandedCategory === 'gann' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'gannBox', name: 'Gann Box' },
                                { id: 'gannBoxFixed', name: 'Gann Box Fixed' },
                                { id: 'gannFan', name: 'Gann Fan' },
                                { id: 'gannSquare', name: 'Gann Square' },
                                { id: 'gannSquare9', name: 'Square of 9' },
                                { id: 'gannGrid', name: 'Gann Grid' },
                                { id: 'gannSquareRange', name: 'Square Range' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Pitchforks */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.pitchforks}
                        tooltip="Pitchforks"
                        active={['pitchforkStandard', 'pitchforkSchiff', 'pitchforkModified', 'pitchforkInside'].includes(activeTool || '')}
                        expanded={expandedCategory === 'pitchforks'}
                        onClick={() => toggleCategory('pitchforks')}
                    />
                    {expandedCategory === 'pitchforks' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'pitchforkStandard', name: 'Pitchfork' },
                                { id: 'pitchforkSchiff', name: 'Schiff Pitchfork' },
                                { id: 'pitchforkModified', name: 'Mod. Schiff' },
                                { id: 'pitchforkInside', name: 'Inside Pitchfork' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Elliott Wave */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.elliott}
                        tooltip="Elliott Wave"
                        active={['elliottImpulse', 'elliottCorrection', 'elliottWXY', 'elliottTriangle'].includes(activeTool || '')}
                        expanded={expandedCategory === 'elliott'}
                        onClick={() => toggleCategory('elliott')}
                    />
                    {expandedCategory === 'elliott' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'elliottImpulse', name: 'Impulse (1-5)' },
                                { id: 'elliottCorrection', name: 'ABC Correction' },
                                { id: 'elliottWXY', name: 'WXY Double' },
                                { id: 'elliottTriangle', name: 'ABCDE Triangle' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Patterns */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.patterns}
                        tooltip="Patterns"
                        active={[
                            'xabcdPattern', 'abcdPattern', 'headShoulders', 'inverseHeadShoulders',
                            'trianglePattern', 'doubleTop', 'doubleBottom', 'tripleTop', 'tripleBottom',
                            'cupHandle', 'inverseCupHandle', 'bullFlag', 'bearFlag',
                            'bullPennant', 'bearPennant', 'ascendingWedge', 'descendingWedge',
                            'rectanglePattern'
                        ].includes(activeTool || '')}
                        expanded={expandedCategory === 'patterns'}
                        onClick={() => toggleCategory('patterns')}
                    />
                    {expandedCategory === 'patterns' && (
                        <ToolSubmenu
                            tools={[
                                // Harmonic Patterns
                                { id: 'xabcdPattern', name: 'XABCD Pattern' },
                                { id: 'abcdPattern', name: 'ABCD Pattern' },
                                // Reversal Patterns
                                { id: 'headShoulders', name: 'H&S Reversal' },
                                { id: 'inverseHeadShoulders', name: 'Inverse H&S' },
                                { id: 'doubleTop', name: 'M Top (Double)' },
                                { id: 'doubleBottom', name: 'W Bottom (Double)' },
                                { id: 'tripleTop', name: 'Triple M Top' },
                                { id: 'tripleBottom', name: 'Triple W Bottom' },
                                // Cup Patterns
                                { id: 'cupHandle', name: 'Cup & Handle' },
                                { id: 'inverseCupHandle', name: 'Inverse Cup' },
                                // Flag & Pennant Patterns
                                { id: 'bullFlag', name: 'Bull Flag' },
                                { id: 'bearFlag', name: 'Bear Flag' },
                                { id: 'bullPennant', name: 'Bull Pennant' },
                                { id: 'bearPennant', name: 'Bear Pennant' },
                                // Wedge Patterns
                                { id: 'ascendingWedge', name: 'Rising Wedge' },
                                { id: 'descendingWedge', name: 'Falling Wedge' },
                                // Consolidation Patterns
                                { id: 'trianglePattern', name: 'Triangle' },
                                { id: 'rectanglePattern', name: 'Range Box' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Brush */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.brush}
                        tooltip="Brush"
                        active={['freehand', 'highlighter', 'marker'].includes(activeTool || '')}
                        expanded={expandedCategory === 'brush'}
                        onClick={() => toggleCategory('brush')}
                    />
                    {expandedCategory === 'brush' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'freehand', name: 'Freehand' },
                                { id: 'highlighter', name: 'Highlighter' },
                                { id: 'marker', name: 'Marker' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Projections */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.projections}
                        tooltip="Projections"
                        active={['longPosition', 'shortPosition', 'riskReward', 'forecastCurve', 'projectionArrow', 'priceRange', 'dateRange', 'ruler'].includes(activeTool || '')}
                        expanded={expandedCategory === 'projections'}
                        onClick={() => toggleCategory('projections')}
                    />
                    {expandedCategory === 'projections' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'longPosition', name: 'Long Position' },
                                { id: 'shortPosition', name: 'Short Position' },
                                { id: 'riskReward', name: 'Risk/Reward Box' },
                                { id: 'forecastCurve', name: 'Forecast Curve' },
                                { id: 'projectionArrow', name: 'Projection Arrow' },
                                { id: 'priceRange', name: 'Price Range' },
                                { id: 'dateRange', name: 'Date Range' },
                                { id: 'ruler', name: 'Ruler Tool' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Quant Tools */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.quant}
                        tooltip="Quant Metrics"
                        active={['quantRuler', 'liquidityProfile'].includes(activeTool || '')}
                        expanded={expandedCategory === 'quant'}
                        onClick={() => toggleCategory('quant')}
                    />
                    {expandedCategory === 'quant' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'quantRuler', name: 'Quant Statistics' },
                                { id: 'liquidityProfile', name: 'Liquidity Profile' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Volume Tools */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.volume}
                        tooltip="Volume Tools"
                        active={['anchoredVWAP', 'sessionVWAP', 'fixedRangeVP', 'volumeDelta'].includes(activeTool || '')}
                        expanded={expandedCategory === 'volume'}
                        onClick={() => toggleCategory('volume')}
                    />
                    {expandedCategory === 'volume' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'anchoredVWAP', name: 'Anchored VWAP' },
                                { id: 'sessionVWAP', name: 'Session VWAP' },
                                { id: 'fixedRangeVP', name: 'Fixed Volume Profile' },
                                { id: 'volumeDelta', name: 'Volume Delta Zone' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                <Separator />

                {/* Text Tools */}
                <div className="relative group/category w-full flex justify-center">
                    <ToolCategoryButton
                        icon={ICONS.text}
                        tooltip="Text & Annotations"
                        active={['textLabel', 'priceLabel', 'noteBox', 'callout', 'arrowLabel', 'signpost', 'text'].includes(activeTool || '')}
                        expanded={expandedCategory === 'text'}
                        onClick={() => toggleCategory('text')}
                    />
                    {expandedCategory === 'text' && (
                        <ToolSubmenu
                            tools={[
                                { id: 'textLabel', name: 'Text Label' },
                                { id: 'priceLabel', name: 'Price Label' },
                                { id: 'noteBox', name: 'Note Box' },
                                { id: 'callout', name: 'Callout' },
                                { id: 'arrowLabel', name: 'Arrow Label' },
                                { id: 'signpost', name: 'Signpost' },
                            ]}
                            activeTool={activeTool}
                            onSelect={handleToolClick}
                        />
                    )}
                </div>

                {/* Measure */}
                <ToolButton
                    icon={ICONS.measure}
                    tooltip="Measure (Rule)"
                    active={activeTool === 'ruler'}
                    onClick={() => handleToolClick('ruler')}
                />

                <Separator />

                {/* Researcher & Quant Set */}
                <div className="flex flex-col items-center gap-1 pb-16 w-full mt-auto">
                    <Separator />
                    <ToolButton
                        icon={confirmDelete ? <span className="text-[10px] font-bold">YES?</span> : ICONS.trash}
                        tooltip={confirmDelete ? "Click again to confirm delete all" : "Clear All Drawings"}
                        active={confirmDelete}
                        onClick={handleClearClick}
                    />
                    <ToolButton
                        icon={ICONS.screenshot}
                        tooltip="Capture Screenshot"
                        active={false}
                        onClick={onScreenshot}
                    />
                    <ToolButton
                        icon={ICONS.export}
                        tooltip="Export CSV Data"
                        active={false}
                        onClick={onExportData}
                    />
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

interface ToolButtonProps {
    icon: React.ReactNode;
    tooltip: string;
    active: boolean;
    onClick?: () => void;
}

function ToolButton({ icon, tooltip, active, onClick }: ToolButtonProps) {
    return (
        <button
            onClick={onClick}
            title={tooltip}
            className="group relative flex items-center justify-center transition-all duration-200"
            style={{
                width: 32,
                height: 32,
                borderRadius: 6,
                background: active ? CHART_THEME.accent : 'transparent',
                color: active ? '#000' : CHART_THEME.textSecondary,
                border: active ? `1px solid ${CHART_THEME.accent}` : '1px solid transparent',
            }}
        >
            <div className="scale-90 group-hover:scale-105 transition-transform duration-200">
                {icon}
            </div>
            
            {/* Subtle glow when active */}
            {active && (
                <div 
                    className="absolute inset-0 rounded-md animate-pulse"
                    style={{
                        boxShadow: `0 0 12px ${CHART_THEME.accent}40`,
                        border: `1px solid ${CHART_THEME.accent}`,
                    }}
                />
            )}
        </button>
    );
}

interface ToolCategoryButtonProps extends ToolButtonProps {
    expanded: boolean;
}

function ToolCategoryButton({ icon, tooltip, active, expanded, onClick }: ToolCategoryButtonProps) {
    return (
        <button
            onClick={onClick}
            title={tooltip}
            className="group relative flex items-center justify-center transition-all duration-200"
            style={{
                width: 32,
                height: 32,
                borderRadius: 6,
                background: active || expanded ? CHART_THEME.accent : 'transparent',
                color: active || expanded ? '#000' : CHART_THEME.textSecondary,
                border: active || expanded ? `1px solid ${CHART_THEME.accent}` : '1px solid transparent',
            }}
        >
            <div className="scale-90 group-hover:scale-105 transition-transform duration-200">
                {icon}
            </div>
            {/* Expand indicator */}
            <span
                className="absolute bottom-1 right-1"
                style={{
                    width: 0,
                    height: 0,
                    borderLeft: '2.5px solid transparent',
                    borderRight: '2.5px solid transparent',
                    borderTop: `3px solid ${active || expanded ? '#000' : CHART_THEME.textSecondary}`,
                    transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.15s',
                }}
            />
        </button>
    );
}

interface ToolSubmenuProps {
    tools: Array<{ id: string; name: string }>;
    activeTool: string | null;
    onSelect: (toolId: string) => void;
}

// Small inline icon for submenu items (Keeping the existing mapping)
const TOOL_MINI_ICONS: Record<string, string> = {
    trendLine: '╱',
    horizontalLine: '─',
    verticalLine: '│',
    horizontalRay: '─→',
    infoLine: 'ℹ',
    extendedLine: '↔',
    crossLine: '┼',
    fibRetracement: '⊟',
    fibExtension: '⊞',
    fibProjection: '⊡',
    fibTimeZones: '⊢',
    fibFan: '⌔',
    fibArcs: '◜',
    fibCircles: '○',
    fibSpiral: '◌',
    fibChannel: '⊏',
    fibWedge: '◣',
    rectangle: '▢',
    rotatedRectangle: '◇',
    circle: '◯',
    ellipse: '⬭',
    triangle: '△',
    path: '⟋',
    polyline: '⬡',
    arc: '⌒',
    curve: '∿',
    doubleCurve: '∞',
    arrow: '→',
    arrowMarker: '▲',
    arrowMarkUp: '▲',
    arrowMarkDown: '▼',
    text: 'T',
    parallelChannel: '═',
    regressionChannel: '≈',
    flatChannel: '⊐',
    gannBox: '⊞',
    gannBoxFixed: '⊟',
    gannFan: '⌔',
    gannSquare: '▣',
    gannSquare9: '⊡',
    gannGrid: '▦',
    gannSquareRange: '⊠',
    pitchforkStandard: '⋔',
    pitchforkSchiff: '⋓',
    pitchforkModified: '⋒',
    pitchforkInside: '⋑',
    elliottImpulse: '⌇',
    elliottCorrection: '∿',
    elliottWXY: '∾',
    elliottTriangle: '△',
    xabcdPattern: '⋈',
    abcdPattern: '⋉',
    cypherPattern: '⊛',
    gartleyPattern: '⊗',
    batPattern: '⊘',
    butterflyPattern: '⊙',
    crabPattern: '⊚',
    sharkPattern: '⊜',
    threeDrivePattern: '⋮',
    headShoulders: '⋀',
    inverseHeadShoulders: '⋁',
    trianglePattern: '△',
    doubleTop: 'M',
    doubleBottom: 'W',
    tripleTop: 'MMM',
    tripleBottom: 'WWW',
    cupHandle: '∪',
    inverseCupHandle: '∩',
    bullFlag: '▲⚑',
    bearFlag: '▼⚑',
    bullPennant: '▲▷',
    bearPennant: '▼▷',
    ascendingWedge: '⟋',
    descendingWedge: '⟍',
    rectanglePattern: '▭',
    freehand: '✎',
    highlighter: '■',
    marker: '●',
    longPosition: '⬆',
    shortPosition: '⬇',
    riskReward: '⊟',
    forecastCurve: '⌒',
    projectionArrow: '➡',
    priceRange: '↕',
    dateRange: '↔',
    ruler: '📏',
    quantRuler: '📊',
    liquidityProfile: '📊',
    orderFlow: '⚡',
    anchoredVWAP: '◈',
    sessionVWAP: '◇',
    fixedRangeVP: '▥',
    volumeDelta: '▤',
    textLabel: 'A',
    priceLabel: '$',
    noteBox: '▭',
    callout: '💬',
    arrowLabel: '➤',
    signpost: '⚑',
};

function ToolSubmenu({ tools, activeTool, onSelect }: ToolSubmenuProps) {
    const menuRef = useRef<HTMLDivElement>(null);
    const [offset, setOffset] = useState(0);

    // Smart positioning logic
    useEffect(() => {
        if (menuRef.current) {
            const rect = menuRef.current.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            
            // If the bottom of the menu would go off-screen
            if (rect.bottom > viewportHeight - 20) {
                // Calculate how much to shift up
                const overflow = rect.bottom - (viewportHeight - 20);
                setOffset(-overflow);
            }
        }
    }, [tools]);

    return (
        <div
            ref={menuRef}
            className="rounded-md shadow-2xl border"
            style={{
                position: 'absolute',
                left: '100%',
                marginLeft: '8px',
                top: 0,
                transform: `translateY(${offset}px)`,
                background: '#1c2030', // Solid dark background for reliability
                borderColor: 'rgba(255,255,255,0.1)',
                minWidth: 160,
                maxHeight: 'calc(100vh - 40px)',
                overflowY: 'auto',
                zIndex: 9999, // Extremely high z-index
                boxShadow: '0 8px 32px rgba(0,0,0,0.8)',
                transition: 'transform 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                padding: '4px 0',
            }}
        >
            <div className="px-2 py-1 mb-1 border-b border-white/5 opacity-50 text-[10px] font-bold uppercase tracking-wider text-white">
                Tools
            </div>
            {tools.map(tool => (
                <button
                    key={tool.id}
                    onClick={() => onSelect(tool.id)}
                    className="w-full px-3 py-1.5 text-left text-[11px] font-medium transition-all flex items-center gap-3 hover:translate-x-1"
                    style={{
                        background: activeTool === tool.id ? CHART_THEME.accent + '20' : 'transparent',
                        color: activeTool === tool.id ? CHART_THEME.accent : CHART_THEME.textPrimary,
                    }}
                >
                    <span style={{ 
                        width: '18px', 
                        height: '18px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: activeTool === tool.id ? CHART_THEME.accent : 'rgba(255,255,255,0.05)',
                        borderRadius: '3px',
                        color: activeTool === tool.id ? '#000' : CHART_THEME.textSecondary,
                        fontSize: '10px',
                    }}>
                        {TOOL_MINI_ICONS[tool.id] || '•'}
                    </span>
                    {tool.name}
                </button>
            ))}
        </div>
    );
}

function Separator() {
    return (
        <div
            style={{
                width: 20,
                height: 1,
                background: CHART_THEME.border,
                margin: '4px 0',
                opacity: 0.5,
            }}
        />
    );
}
