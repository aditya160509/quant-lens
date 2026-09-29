/**
 * Chart State Management
 * Zustand-style state with reducer pattern
 */

import type {
    ChartState,
    ChartAction,
    ChartConfig,
    ReplayState,
    PaneConfig,
    Timeframe,
    ChartType,
    ScaleMode
} from '../types';

// =============================================================================
// INITIAL STATE
// =============================================================================

const defaultConfig: ChartConfig = {
    chartType: 'candlestick',
    scaleMode: 'auto',
    showVolume: true,
    showGrid: true,
    sessionShading: true,
};

const defaultReplay: ReplayState = {
    active: false,
    startIndex: 0,
    cursorIndex: 0,
    speed: 1,
    isPlaying: false,
};

const defaultPanes: PaneConfig[] = [
    { id: 'price', type: 'price', height: 70 },
    { id: 'volume', type: 'volume', height: 15 },
];

export const initialChartState: ChartState = {
    symbol: 'SPY',
    timeframe: '5m',
    data: null,
    config: defaultConfig,
    panes: defaultPanes,
    indicators: [],
    indicatorOutputs: new Map(),
    drawings: [],
    selectedDrawingId: null,
    activeToolType: null,
    activeDrawing: null,
    replay: defaultReplay,
    viewportStart: 0,
    viewportEnd: 0,
    zoomLevel: 1,
    panOffset: 0,
    crosshairPosition: null,
    hoveredBarIndex: null,
    drawingsLocked: false,
    drawingsVisible: true,
};

// =============================================================================
// REDUCER
// =============================================================================

export function chartReducer(state: ChartState, action: ChartAction): ChartState {
    switch (action.type) {
        case 'SET_SYMBOL':
            return { ...state, symbol: action.payload, data: null, panOffset: 0, zoomLevel: 1 };

        case 'SET_TIMEFRAME':
            return { ...state, timeframe: action.payload, data: null, panOffset: 0, zoomLevel: 1 };

        case 'SET_DATA':
            return {
                ...state,
                data: action.payload,
                viewportStart: action.payload.bars[0]?.timestamp ?? 0,
                viewportEnd: action.payload.bars[action.payload.bars.length - 1]?.timestamp ?? 0,
                panOffset: 0, // Reset pan when new data loads
                zoomLevel: 1, // Reset zoom when new data loads
            };

        case 'SET_CHART_TYPE':
            return {
                ...state,
                config: { ...state.config, chartType: action.payload }
            };

        case 'SET_SCALE_MODE':
            return {
                ...state,
                config: { ...state.config, scaleMode: action.payload }
            };

        case 'TOGGLE_VOLUME':
            return {
                ...state,
                config: { ...state.config, showVolume: !state.config.showVolume }
            };

        case 'TOGGLE_GRID':
            return {
                ...state,
                config: { ...state.config, showGrid: !state.config.showGrid }
            };

        case 'TOGGLE_SESSION_SHADING':
            return {
                ...state,
                config: { ...state.config, sessionShading: !state.config.sessionShading }
            };

        case 'ADD_INDICATOR':
            return {
                ...state,
                indicators: [...state.indicators, action.payload]
            };

        case 'REMOVE_INDICATOR': {
            const newOutputs = new Map(state.indicatorOutputs);
            newOutputs.delete(action.payload);
            return {
                ...state,
                indicators: state.indicators.filter(i => i.id !== action.payload),
                indicatorOutputs: newOutputs,
            };
        }

        case 'UPDATE_INDICATOR':
            return {
                ...state,
                indicators: state.indicators.map(i =>
                    i.id === action.payload.id
                        ? { ...i, params: { ...i.params, ...action.payload.params } as Record<string, string | number | boolean> }
                        : i
                )
            };

        case 'SET_INDICATOR_OUTPUT': {
            const newOutputs = new Map(state.indicatorOutputs);
            newOutputs.set(action.payload.id, action.payload.output);
            return { ...state, indicatorOutputs: newOutputs };
        }

        case 'ADD_DRAWING':
            return {
                ...state,
                drawings: [...state.drawings, action.payload],
            };

        case 'UPDATE_DRAWING':
            return {
                ...state,
                drawings: state.drawings.map(d =>
                    d.id === action.payload.id ? action.payload : d
                ),
            };

        case 'REMOVE_DRAWING':
            return {
                ...state,
                drawings: state.drawings.filter(d => d.id !== action.payload),
                selectedDrawingId: state.selectedDrawingId === action.payload ? null : state.selectedDrawingId,
            };

        case 'SELECT_DRAWING':
            return { ...state, selectedDrawingId: action.payload };

        case 'SET_ACTIVE_TOOL':
            return { ...state, activeToolType: action.payload, selectedDrawingId: null };

        case 'START_REPLAY':
            return {
                ...state,
                replay: {
                    active: true,
                    startIndex: action.payload,
                    cursorIndex: action.payload,
                    speed: 1,
                    isPlaying: false,
                }
            };

        case 'STOP_REPLAY':
            return {
                ...state,
                replay: defaultReplay,
            };

        case 'TOGGLE_REPLAY_PLAY':
            return {
                ...state,
                replay: { ...state.replay, isPlaying: !state.replay.isPlaying }
            };

        case 'SET_REPLAY_SPEED':
            return {
                ...state,
                replay: { ...state.replay, speed: action.payload }
            };

        case 'STEP_REPLAY': {
            const newIndex = state.replay.cursorIndex + action.payload;
            const maxIndex = (state.data?.bars.length ?? 1) - 1;
            return {
                ...state,
                replay: {
                    ...state.replay,
                    cursorIndex: Math.max(state.replay.startIndex, Math.min(maxIndex, newIndex)),
                }
            };
        }

        case 'SET_VIEWPORT':
            return {
                ...state,
                viewportStart: action.payload.start,
                viewportEnd: action.payload.end,
            };

        case 'ZOOM':
            return {
                ...state,
                zoomLevel: Math.max(0.1, Math.min(10, state.zoomLevel * action.payload)),
            };

        case 'PAN':
            return {
                ...state,
                panOffset: state.panOffset + action.payload,
            };

        case 'SET_CROSSHAIR':
            return { ...state, crosshairPosition: action.payload };

        case 'SET_HOVERED_BAR':
            return { ...state, hoveredBarIndex: action.payload };

        case 'ADD_PANE':
            return {
                ...state,
                panes: [...state.panes, action.payload],
            };

        case 'REMOVE_PANE':
            return {
                ...state,
                panes: state.panes.filter(p => p.id !== action.payload),
            };

        case 'RESIZE_PANE':
            return {
                ...state,
                panes: state.panes.map(p =>
                    p.id === action.payload.id ? { ...p, height: action.payload.height } : p
                ),
            };
            
        case 'CLEAR_DRAWINGS':
            return {
                ...state,
                drawings: [],
                activeDrawing: null,
                selectedDrawingId: null
            };

        case 'TOGGLE_DRAWINGS_LOCK':
            return {
                ...state,
                drawingsLocked: !state.drawingsLocked
            };

        case 'TOGGLE_DRAWINGS_VISIBILITY':
            return {
                ...state,
                drawingsVisible: !state.drawingsVisible
            };

        default:
            return state;
    }
}

// =============================================================================
// SELECTORS
// =============================================================================

export function getVisibleBars(state: ChartState) {
    if (!state.data?.bars) return [];

    if (state.replay.active) {
        return state.data.bars.slice(0, state.replay.cursorIndex + 1);
    }

    return state.data.bars;
}

export function getCurrentPrice(state: ChartState): number | null {
    const bars = getVisibleBars(state);
    if (bars.length === 0) return null;
    return bars[bars.length - 1].close;
}

export function getPriceRange(state: ChartState): { min: number; max: number } | null {
    const bars = getVisibleBars(state);
    if (bars.length === 0) return null;

    let min = Infinity;
    let max = -Infinity;

    for (const bar of bars) {
        if (bar.low < min) min = bar.low;
        if (bar.high > max) max = bar.high;
    }

    // Add 5% padding
    const padding = (max - min) * 0.05;
    return { min: min - padding, max: max + padding };
}

export function getVolumeRange(state: ChartState): { min: number; max: number } | null {
    const bars = getVisibleBars(state);
    if (bars.length === 0) return null;

    const max = Math.max(...bars.map(b => b.volume));
    return { min: 0, max };
}
