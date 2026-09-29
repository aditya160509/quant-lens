/**
 * Quant360 Chart Engine - Core Types
 * Types for OHLCV data, chart state, drawings, and indicators
 */

// =============================================================================
// DATA TYPES
// =============================================================================

export interface OHLCVBar {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface SessionConfig {
    timezone: string;
    preMarketStart?: string;  // "04:00"
    regularStart: string;     // "09:30"
    regularEnd: string;       // "16:00"
    extendedEnd?: string;     // "20:00"
}

export interface SeriesData {
    symbol: string;
    timeframe: Timeframe;
    bars: OHLCVBar[];
    session: SessionConfig;
    previousClose?: number;
}

// =============================================================================
// CHART CONFIGURATION
// =============================================================================

export type Timeframe = '1m' | '5m' | '15m' | '30m' | '1h' | '1d' | '3mo' | '6mo' | '1y' | '2y' | '5y';

export type ChartType =
    // Standard OHLC Types
    | 'candlestick'
    | 'hollowCandle'
    | 'volumeCandles'
    | 'bars'
    | 'heikinAshi'
    // Line Types
    | 'line'
    | 'lineWithMarkers'
    | 'stepLine'
    // Area Types
    | 'area'
    | 'hlcArea'
    | 'baseline'
    // Non-Time Based (Synthetic)
    | 'renko'
    | 'kagi'
    | 'pointAndFigure'
    | 'rangeBars'
    | 'lineBreak';

export type ScaleMode = 'auto' | 'manual' | 'log' | 'percent';

export interface ChartConfig {
    chartType: ChartType;
    scaleMode: ScaleMode;
    showVolume: boolean;
    showGrid: boolean;
    sessionShading: boolean;
    baselinePrice?: number;  // For baseline chart type
    renkoBoxSize?: number;   // For renko
    kagiReversal?: number;   // For kagi
    rangeBarSize?: number;   // For range bars
}

// =============================================================================
// DRAWING TYPES
// =============================================================================

export type DrawingToolCategory =
    | 'lines'
    | 'channels'
    | 'pitchforks'
    | 'fibonacci'
    | 'gann'
    | 'shapes'
    | 'arrows'
    | 'brush'
    | 'text'
    | 'patterns'
    | 'elliott'
    | 'projections'
    | 'volume'
    | 'quant';

export interface DrawingAnchor {
    timestamp: number;
    price: number;
}

export interface DrawingStyle {
    color: string;
    lineWidth: number;
    lineStyle: 'solid' | 'dashed' | 'dotted';
    fillColor?: string;
    fillOpacity?: number;
    fontSize?: number;
    fontColor?: string;
}

export interface Drawing {
    id: string;
    type: string;
    category: DrawingToolCategory;
    anchors: DrawingAnchor[];
    style: DrawingStyle;
    visible: boolean;
    locked: boolean;
    symbol: string;
    label?: string;
    metadata?: Record<string, unknown>;
    data?: Record<string, unknown>;  // Custom tool data (text content, colors, etc.)
    createdAt: number;
    updatedAt: number;
}

// =============================================================================
// INDICATOR TYPES
// =============================================================================

export type IndicatorPlacement = 'overlay' | 'pane';

export interface IndicatorConfig {
    id: string;
    type: string;
    params: Record<string, number | string | boolean>;
    placement: IndicatorPlacement;
    visible: boolean;
    color?: string;
    lineWidth?: number;
}

export interface IndicatorOutput {
    indicatorId: string;
    series: { timestamp: number; value: number; extra?: Record<string, unknown> }[];
    bands?: { upper: number[]; middle: number[]; lower: number[] };
}

export interface IndicatorDefinition {
    id: string;
    name: string;
    shortName: string;
    placement: IndicatorPlacement;
    defaultParams: Record<string, number | string | boolean>;
    paramLabels: Record<string, string>;
    compute: (bars: OHLCVBar[], params: Record<string, unknown>) => IndicatorOutput;
}

// =============================================================================
// REPLAY TYPES
// =============================================================================

export type ReplaySpeed = 1 | 2 | 5 | 10;

export interface ReplayState {
    active: boolean;
    startIndex: number;
    cursorIndex: number;
    speed: ReplaySpeed;
    isPlaying: boolean;
}

// =============================================================================
// PANE TYPES
// =============================================================================

export interface PaneConfig {
    id: string;
    type: 'price' | 'indicator' | 'volume';
    height: number;  // Percentage of total height
    indicators?: string[];  // Indicator IDs in this pane
}

// =============================================================================
// CHART STATE
// =============================================================================

export interface ChartState {
    // Data
    symbol: string;
    timeframe: Timeframe;
    data: SeriesData | null;

    // Configuration
    config: ChartConfig;

    // Panes
    panes: PaneConfig[];

    // Indicators
    indicators: IndicatorConfig[];
    indicatorOutputs: Map<string, IndicatorOutput>;

    // Drawings
    drawings: Drawing[];
    selectedDrawingId: string | null;
    activeToolType: string | null;
    activeDrawing: Drawing | null;

    // Replay
    replay: ReplayState;

    // Viewport
    viewportStart: number;  // Timestamp
    viewportEnd: number;    // Timestamp
    zoomLevel: number;
    panOffset: number;

    // UI State
    crosshairPosition: { x: number; y: number } | null;
    hoveredBarIndex: number | null;
    drawingsLocked: boolean;
    drawingsVisible: boolean;
}

// =============================================================================
// CHART ACTIONS
// =============================================================================

export type ChartAction =
    | { type: 'SET_SYMBOL'; payload: string }
    | { type: 'SET_TIMEFRAME'; payload: Timeframe }
    | { type: 'SET_DATA'; payload: SeriesData }
    | { type: 'SET_CHART_TYPE'; payload: ChartType }
    | { type: 'SET_SCALE_MODE'; payload: ScaleMode }
    | { type: 'TOGGLE_VOLUME' }
    | { type: 'TOGGLE_GRID' }
    | { type: 'TOGGLE_SESSION_SHADING' }
    | { type: 'ADD_INDICATOR'; payload: IndicatorConfig }
    | { type: 'REMOVE_INDICATOR'; payload: string }
    | { type: 'UPDATE_INDICATOR'; payload: { id: string; params: Record<string, unknown> } }
    | { type: 'SET_INDICATOR_OUTPUT'; payload: { id: string; output: IndicatorOutput } }
    | { type: 'ADD_DRAWING'; payload: Drawing }
    | { type: 'UPDATE_DRAWING'; payload: Drawing }
    | { type: 'REMOVE_DRAWING'; payload: string }
    | { type: 'SELECT_DRAWING'; payload: string | null }
    | { type: 'SET_ACTIVE_TOOL'; payload: string | null }
    | { type: 'START_REPLAY'; payload: number }
    | { type: 'STOP_REPLAY' }
    | { type: 'TOGGLE_REPLAY_PLAY' }
    | { type: 'SET_REPLAY_SPEED'; payload: ReplaySpeed }
    | { type: 'STEP_REPLAY'; payload: 1 | -1 }
    | { type: 'SET_VIEWPORT'; payload: { start: number; end: number } }
    | { type: 'ZOOM'; payload: number }
    | { type: 'PAN'; payload: number }
    | { type: 'SET_CROSSHAIR'; payload: { x: number; y: number } | null }
    | { type: 'SET_HOVERED_BAR'; payload: number | null }
    | { type: 'ADD_PANE'; payload: PaneConfig }
    | { type: 'REMOVE_PANE'; payload: string }
    | { type: 'RESIZE_PANE'; payload: { id: string; height: number } }
    | { type: 'CLEAR_DRAWINGS' }
    | { type: 'SCREENSHOT' }
    | { type: 'EXPORT_DATA' }
    | { type: 'TOGGLE_DRAWINGS_LOCK' }
    | { type: 'TOGGLE_DRAWINGS_VISIBILITY' };

// =============================================================================
// COMPONENT PROPS
// =============================================================================

export interface Q360ChartCoreProps {
    symbol: string;
    timeframe: Timeframe;
    mode: 'intraday';
    session?: SessionConfig;
    height?: number | string;
    width?: number | string;
    syncedCrosshairTimestamp?: number | null;
    onSymbolChange?: (symbol: string) => void;
    onTimeframeChange?: (timeframe: Timeframe) => void;
    onCrosshairMove?: (timestamp: number | null) => void;
    onDrawingChange?: (drawings: Drawing[]) => void;
    onIndicatorsChange?: (indicators: Record<string, boolean>) => void;
    className?: string;
    /** When true, chart is embedded in a grid - hides internal layout controls */
    isMemberOfGrid?: boolean;
    /** 
     * Chart rendering engine: 
     * - 'custom': Uses the custom ChartCanvas with full drawing/indicator support
     * - 'lightweight': Uses TradingView's lightweight-charts library (recommended for compare/sync)
     */
    chartEngine?: 'custom' | 'lightweight';
}

// =============================================================================
// THEME (Fixed to Quant360 existing theme)
// =============================================================================

export const CHART_THEME = {
    // Background
    bgPrimary: '#03050a',
    bgSecondary: '#060a10',
    bgTertiary: '#0a0f18',
    bgPanel: '#151c28',

    // Borders
    border: '#1e2738',
    borderLight: '#26282c',

    // Candles
    upColor: '#00ff88',
    downColor: '#ff2d55',
    wickColor: '#5a6578',

    // Text
    textPrimary: '#e8eaed',
    textSecondary: '#5a6578',
    textMuted: '#3d4654',

    // Accents
    accent: '#ffd60a',
    accentBlue: '#00d4ff',
    accentCyan: '#64ffda',

    // Grid
    gridColor: '#1e2738',
    gridColorLight: '#151c28',

    // Font
    fontMono: "var(--font-mono, 'IBM Plex Mono', 'JetBrains Mono', monospace)",
    fontSans: "var(--font-sans, 'DM Sans', 'Inter', system-ui, sans-serif)",
} as const;

// =============================================================================
// INDICATOR COLOR PALETTE (TradingView-inspired distinct colors)
// =============================================================================

export const INDICATOR_COLORS: Record<string, { primary: string; secondary?: string; fill?: string }> = {
    // Moving Averages - warm tones
    sma: { primary: '#ff9f1c', secondary: '#ff6b35' },      // Orange
    ema: { primary: '#2ec4b6', secondary: '#00a896' },       // Teal/Cyan  
    wma: { primary: '#e9c46a', secondary: '#f4a261' },       // Gold
    hma: { primary: '#9b5de5', secondary: '#7c3aed' },       // Purple
    
    // Bands & Channels - cool tones with fill
    bb: { primary: '#00d4ff', secondary: '#0099cc', fill: 'rgba(0, 212, 255, 0.08)' },  // Cyan for Bollinger
    keltner: { primary: '#8b5cf6', secondary: '#6d28d9', fill: 'rgba(139, 92, 246, 0.08)' },  // Violet
    donchian: { primary: '#06b6d4', secondary: '#0891b2', fill: 'rgba(6, 182, 212, 0.08)' },  // Teal
    
    // Trend - distinct primary colors
    vwap: { primary: '#f472b6', secondary: '#ec4899' },      // Pink/Magenta
    supertrend: { primary: '#10b981', secondary: '#ef4444' }, // Green/Red (dynamic)
    sar: { primary: '#f59e0b' },                              // Amber dots
    ichimoku: { primary: '#3b82f6', secondary: '#10b981', fill: 'rgba(59, 130, 246, 0.12)' },  // Blue cloud front
    
    // Oscillators - muted professional colors
    rsi: { primary: '#22c55e', secondary: '#ef4444' },        // Green/Red zones
    macd: { primary: '#3b82f6', secondary: '#f97316' },       // Blue MACD, Orange signal
    stoch: { primary: '#06b6d4', secondary: '#f43f5e' },      // Cyan %K, Rose %D
    cci: { primary: '#a855f7' },                              // Purple
    adx: { primary: '#14b8a6', secondary: '#f59e0b' },        // Teal DI+, Amber DI-
    atr: { primary: '#64748b' },                              // Slate gray
    roc: { primary: '#0ea5e9' },                              // Sky blue
    mfi: { primary: '#f97316' },                              // Orange
    obv: { primary: '#8b5cf6' },                              // Violet
    
    // Default fallback
    default: { primary: '#e5e5e5' },
};

// Helper to get indicator color
export function getIndicatorColor(indicatorType: string): string {
    const normalizedType = indicatorType.toLowerCase();
    return INDICATOR_COLORS[normalizedType]?.primary || INDICATOR_COLORS.default.primary;
}

// Helper to get secondary color (for two-line indicators)
export function getIndicatorSecondaryColor(indicatorType: string): string {
    const normalizedType = indicatorType.toLowerCase();
    return INDICATOR_COLORS[normalizedType]?.secondary || '#888888';
}

// Helper to get fill color (for bands)
export function getIndicatorFillColor(indicatorType: string): string | undefined {
    const normalizedType = indicatorType.toLowerCase();
    return INDICATOR_COLORS[normalizedType]?.fill;
}

