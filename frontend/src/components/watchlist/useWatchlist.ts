/**
 * useWatchlist Hook
 * State management for watchlists with localStorage persistence
 */

'use client';

import { useReducer, useCallback, useEffect, useMemo } from 'react';
import {
    type Watchlist,
    type WatchlistState,
    type WatchlistAction,
    type WatchlistSymbol,
    type ColorFlag,
    createDefaultWatchlist,
    createWatchlistSymbol,
    parseCSV,
    exportToCSV,
} from './watchlistTypes';

// =============================================================================
// CONSTANTS
// =============================================================================

const STORAGE_KEY = 'quant360_watchlists';

// =============================================================================
// REDUCER
// =============================================================================

function watchlistReducer(state: WatchlistState, action: WatchlistAction): WatchlistState {
    switch (action.type) {
        case 'CREATE_LIST': {
            const newList = createDefaultWatchlist(action.payload.name);
            return {
                ...state,
                lists: [...state.lists, newList],
                activeListId: newList.id,
            };
        }

        case 'DELETE_LIST': {
            const lists = state.lists.filter(l => l.id !== action.payload);
            return {
                ...state,
                lists,
                activeListId: state.activeListId === action.payload
                    ? (lists[0]?.id || null)
                    : state.activeListId,
            };
        }

        case 'RENAME_LIST': {
            return {
                ...state,
                lists: state.lists.map(l =>
                    l.id === action.payload.listId
                        ? { ...l, name: action.payload.name, updatedAt: Date.now() }
                        : l
                ),
            };
        }

        case 'SET_ACTIVE_LIST': {
            return {
                ...state,
                activeListId: action.payload,
            };
        }

        case 'ADD_SYMBOL': {
            const { listId, symbol } = action.payload;
            return {
                ...state,
                lists: state.lists.map(l => {
                    if (l.id !== listId) return l;
                    // Don't add duplicates
                    if (l.symbols.some(s => s.symbol === symbol.toUpperCase())) return l;
                    return {
                        ...l,
                        symbols: [...l.symbols, createWatchlistSymbol(symbol, l.symbols.length)],
                        updatedAt: Date.now(),
                    };
                }),
            };
        }

        case 'REMOVE_SYMBOL': {
            const { listId, symbol } = action.payload;
            return {
                ...state,
                lists: state.lists.map(l => {
                    if (l.id !== listId) return l;
                    return {
                        ...l,
                        symbols: l.symbols.filter(s => s.symbol !== symbol),
                        updatedAt: Date.now(),
                    };
                }),
            };
        }

        case 'UPDATE_SYMBOL': {
            const { listId, symbol, updates } = action.payload;
            return {
                ...state,
                lists: state.lists.map(l => {
                    if (l.id !== listId) return l;
                    return {
                        ...l,
                        symbols: l.symbols.map(s =>
                            s.symbol === symbol ? { ...s, ...updates } : s
                        ),
                        updatedAt: Date.now(),
                    };
                }),
            };
        }

        case 'REORDER_SYMBOLS': {
            const { listId, symbols } = action.payload;
            return {
                ...state,
                lists: state.lists.map(l =>
                    l.id === listId
                        ? { ...l, symbols, updatedAt: Date.now() }
                        : l
                ),
            };
        }

        case 'IMPORT_SYMBOLS': {
            const { listId, symbols } = action.payload;
            return {
                ...state,
                lists: state.lists.map(l => {
                    if (l.id !== listId) return l;
                    const existingSymbols = new Set(l.symbols.map(s => s.symbol));
                    const newSymbols = symbols
                        .filter(s => !existingSymbols.has(s))
                        .map((s, i) => createWatchlistSymbol(s, l.symbols.length + i));
                    return {
                        ...l,
                        symbols: [...l.symbols, ...newSymbols],
                        updatedAt: Date.now(),
                    };
                }),
            };
        }

        case 'LOAD_STATE': {
            return action.payload;
        }

        case 'SET_LEADERBOARD_MODE': {
            return {
                ...state,
                isLeaderboardMode: action.payload.enabled,
                sortMode: action.payload.mode || 'none',
            };
        }

        default:
            return state;
    }
}

// =============================================================================
// INITIAL STATE
// =============================================================================

function getInitialState(): WatchlistState {
    const baseState = {
        lists: [createDefaultWatchlist()],
        activeListId: null,
        isLeaderboardMode: false,
        sortMode: 'none' as const,
    };

    if (typeof window === 'undefined') {
        return baseState;
    }

    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved) as WatchlistState;
            if (parsed.lists.length === 0) {
                const defaultList = createDefaultWatchlist();
                return { 
                    ...parsed, 
                    lists: [defaultList], 
                    activeListId: defaultList.id,
                    isLeaderboardMode: parsed.isLeaderboardMode || false,
                    sortMode: parsed.sortMode || 'none'
                };
            }
            return {
                ...parsed,
                isLeaderboardMode: parsed.isLeaderboardMode || false,
                sortMode: parsed.sortMode || 'none'
            };
        }
    } catch {
        // Ignore parse errors
    }

    const defaultList = createDefaultWatchlist();
    return { ...baseState, lists: [defaultList], activeListId: defaultList.id };
}

// =============================================================================
// HOOK
// =============================================================================

export function useWatchlist() {
    const [state, dispatch] = useReducer(watchlistReducer, undefined, getInitialState);

    // Persist to localStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }
    }, [state]);

    // List actions
    const createList = useCallback((name: string) => {
        dispatch({ type: 'CREATE_LIST', payload: { name } });
    }, []);

    const deleteList = useCallback((listId: string) => {
        dispatch({ type: 'DELETE_LIST', payload: listId });
    }, []);

    const renameList = useCallback((listId: string, name: string) => {
        dispatch({ type: 'RENAME_LIST', payload: { listId, name } });
    }, []);

    const setActiveList = useCallback((listId: string) => {
        dispatch({ type: 'SET_ACTIVE_LIST', payload: listId });
    }, []);

    // Symbol actions
    const addSymbol = useCallback((listId: string, symbol: string) => {
        dispatch({ type: 'ADD_SYMBOL', payload: { listId, symbol } });
    }, []);

    const removeSymbol = useCallback((listId: string, symbol: string) => {
        dispatch({ type: 'REMOVE_SYMBOL', payload: { listId, symbol } });
    }, []);

    const updateSymbol = useCallback((
        listId: string, 
        symbol: string, 
        updates: Partial<WatchlistSymbol>
    ) => {
        dispatch({ type: 'UPDATE_SYMBOL', payload: { listId, symbol, updates } });
    }, []);

    const setSymbolNote = useCallback((listId: string, symbol: string, notes: string) => {
        updateSymbol(listId, symbol, { notes });
    }, [updateSymbol]);

    const setSymbolFlag = useCallback((listId: string, symbol: string, colorFlag: ColorFlag | null) => {
        updateSymbol(listId, symbol, { colorFlag });
    }, [updateSymbol]);

    const reorderSymbols = useCallback((listId: string, symbols: WatchlistSymbol[]) => {
        dispatch({ type: 'REORDER_SYMBOLS', payload: { listId, symbols } });
    }, []);

    const setLeaderboardMode = useCallback((enabled: boolean, mode?: 'volatility' | 'confluence' | 'change') => {
        dispatch({ type: 'SET_LEADERBOARD_MODE', payload: { enabled, mode } });
    }, []);

    // Import/Export
    const importFromCSV = useCallback((listId: string, csvContent: string) => {
        const symbols = parseCSV(csvContent);
        dispatch({ type: 'IMPORT_SYMBOLS', payload: { listId, symbols } });
        return symbols.length;
    }, []);

    const exportCSV = useCallback((listId: string): string => {
        const list = state.lists.find(l => l.id === listId);
        if (!list) return '';
        return exportToCSV(list.symbols);
    }, [state.lists]);

    // Add symbol to active list shortcut
    const addToActiveList = useCallback((symbol: string) => {
        if (state.activeListId) {
            addSymbol(state.activeListId, symbol);
        }
    }, [state.activeListId, addSymbol]);

    // Computed values
    const activeList = useMemo(() =>
        state.lists.find(l => l.id === state.activeListId) || state.lists[0] || null,
    [state.lists, state.activeListId]);

    const activeSymbols = useMemo(() =>
        activeList?.symbols || [],
    [activeList]);

    return {
        // State
        lists: state.lists,
        activeListId: state.activeListId,
        activeList,
        activeSymbols,

        // List actions
        createList,
        deleteList,
        renameList,
        setActiveList,
        setLeaderboardMode,

        // Symbol actions
        addSymbol,
        removeSymbol,
        updateSymbol,
        setSymbolNote,
        setSymbolFlag,
        reorderSymbols,
        addToActiveList,

        // Computed State
        isLeaderboardMode: state.isLeaderboardMode,
        sortMode: state.sortMode,

        // Import/Export
        importFromCSV,
        exportCSV,
    };
}

export type UseWatchlist = ReturnType<typeof useWatchlist>;
