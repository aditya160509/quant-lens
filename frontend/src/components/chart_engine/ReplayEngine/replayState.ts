/**
 * Replay Engine - State and Controls
 * Market replay functionality for intraday charts
 */

import type { ReplayState, ReplaySpeed, OHLCVBar } from '../types';

// =============================================================================
// REPLAY STATE
// =============================================================================

export interface ReplayConfig {
    multiTimeframe: boolean;
    secondaryTimeframe?: '1m' | '5m';
    hideDrawingsFuture: boolean;
}

export const defaultReplayConfig: ReplayConfig = {
    multiTimeframe: false,
    hideDrawingsFuture: true,
};

// =============================================================================
// REPLAY ACTIONS
// =============================================================================

export type ReplayAction =
    | { type: 'START'; payload: { startIndex: number; config?: Partial<ReplayConfig> } }
    | { type: 'STOP' }
    | { type: 'PLAY' }
    | { type: 'PAUSE' }
    | { type: 'TOGGLE_PLAY' }
    | { type: 'STEP'; payload: 1 | -1 }
    | { type: 'SET_SPEED'; payload: ReplaySpeed }
    | { type: 'JUMP_TO'; payload: number }
    | { type: 'SET_CONFIG'; payload: Partial<ReplayConfig> };

// =============================================================================
// REPLAY REDUCER
// =============================================================================

export interface FullReplayState extends ReplayState {
    config: ReplayConfig;
    maxIndex: number;
}

export const initialReplayState: FullReplayState = {
    active: false,
    startIndex: 0,
    cursorIndex: 0,
    speed: 1,
    isPlaying: false,
    config: defaultReplayConfig,
    maxIndex: 0,
};

export function replayReducer(
    state: FullReplayState,
    action: ReplayAction
): FullReplayState {
    switch (action.type) {
        case 'START':
            return {
                ...state,
                active: true,
                startIndex: action.payload.startIndex,
                cursorIndex: action.payload.startIndex,
                isPlaying: false,
                config: { ...state.config, ...action.payload.config },
            };

        case 'STOP':
            return initialReplayState;

        case 'PLAY':
            return { ...state, isPlaying: true };

        case 'PAUSE':
            return { ...state, isPlaying: false };

        case 'TOGGLE_PLAY':
            return { ...state, isPlaying: !state.isPlaying };

        case 'STEP': {
            const newIndex = state.cursorIndex + action.payload;
            return {
                ...state,
                cursorIndex: Math.max(state.startIndex, Math.min(state.maxIndex, newIndex)),
                isPlaying: false,
            };
        }

        case 'SET_SPEED':
            return { ...state, speed: action.payload };

        case 'JUMP_TO':
            return {
                ...state,
                cursorIndex: Math.max(state.startIndex, Math.min(state.maxIndex, action.payload)),
            };

        case 'SET_CONFIG':
            return { ...state, config: { ...state.config, ...action.payload } };

        default:
            return state;
    }
}

// =============================================================================
// REPLAY UTILITIES
// =============================================================================

/**
 * Get visible bars during replay
 */
export function getReplayBars(
    bars: OHLCVBar[],
    replayState: FullReplayState
): OHLCVBar[] {
    if (!replayState.active) {
        return bars;
    }
    return bars.slice(0, replayState.cursorIndex + 1);
}

/**
 * Check if a drawing should be visible during replay
 */
export function isDrawingVisibleInReplay(
    drawingAnchors: { timestamp: number }[],
    lastVisibleTimestamp: number,
    hideDrawingsFuture: boolean
): boolean {
    if (!hideDrawingsFuture) return true;

    // Hide if any anchor is in the future
    return drawingAnchors.every(a => a.timestamp <= lastVisibleTimestamp);
}

/**
 * Calculate replay progress percentage
 */
export function getReplayProgress(state: FullReplayState): number {
    if (!state.active || state.maxIndex === state.startIndex) {
        return 0;
    }
    return ((state.cursorIndex - state.startIndex) / (state.maxIndex - state.startIndex)) * 100;
}

/**
 * Get time interval between bars for replay speed
 */
export function getReplayInterval(speed: ReplaySpeed): number {
    return 1000 / speed;
}

// =============================================================================
// REPLAY HOOK (for React)
// =============================================================================

export interface UseReplayOptions {
    bars: OHLCVBar[];
    onBarChange?: (index: number, bar: OHLCVBar) => void;
}

// The actual hook implementation would be in a separate .tsx file
// This module provides the pure logic
