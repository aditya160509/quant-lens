/**
 * Watchlist Types
 * Data structures for enhanced watchlist functionality
 */

// =============================================================================
// TYPES
// =============================================================================

export interface WatchlistSymbol {
    symbol: string;
    addedAt: number;
    notes: string;
    colorFlag: ColorFlag | null;
    order: number;
}

export type ColorFlag = 'red' | 'orange' | 'yellow' | 'green' | 'blue' | 'purple';

export interface Watchlist {
    id: string;
    name: string;
    symbols: WatchlistSymbol[];
    createdAt: number;
    updatedAt: number;
}

export interface WatchlistState {
    lists: Watchlist[];
    activeListId: string | null;
    isLeaderboardMode: boolean;
    sortMode: 'volatility' | 'confluence' | 'change' | 'none';
}

export interface TickerSignal {
    trend: boolean;      // Dot 1: Price > EMA 200
    momentum: boolean;   // Dot 2: RSI > 60 or < 40
    liquidity: boolean;  // Dot 3: Volume > 2x Avg
}

export interface TickerIntelligence {
    symbol: string;
    signals: TickerSignal;
    rangeProgress: number; // 0 to 1 (Daily Low to Daily High)
    isVolPulse: boolean;   // Large volume spike detected
    sparkline: number[];
}

// =============================================================================
// CONSTANTS
// =============================================================================

export const COLOR_FLAG_MAP: Record<ColorFlag, string> = {
    red: '#ff5252',
    orange: '#ff9800',
    yellow: '#ffeb3b',
    green: '#4caf50',
    blue: '#2196f3',
    purple: '#9c27b0',
};

// =============================================================================
// ACTIONS
// =============================================================================

export type WatchlistAction =
    | { type: 'CREATE_LIST'; payload: { name: string } }
    | { type: 'DELETE_LIST'; payload: string }
    | { type: 'RENAME_LIST'; payload: { listId: string; name: string } }
    | { type: 'SET_ACTIVE_LIST'; payload: string }
    | { type: 'ADD_SYMBOL'; payload: { listId: string; symbol: string } }
    | { type: 'REMOVE_SYMBOL'; payload: { listId: string; symbol: string } }
    | { type: 'UPDATE_SYMBOL'; payload: { listId: string; symbol: string; updates: Partial<WatchlistSymbol> } }
    | { type: 'REORDER_SYMBOLS'; payload: { listId: string; symbols: WatchlistSymbol[] } }
    | { type: 'LOAD_STATE'; payload: WatchlistState }
    | { type: 'IMPORT_SYMBOLS'; payload: { listId: string; symbols: string[] } }
    | { type: 'SET_LEADERBOARD_MODE'; payload: { enabled: boolean; mode?: 'volatility' | 'confluence' | 'change' } };

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

export function generateListId(): string {
    return `list_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function createDefaultWatchlist(name: string = 'My Watchlist'): Watchlist {
    return {
        id: generateListId(),
        name,
        symbols: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
    };
}

export function createWatchlistSymbol(symbol: string, order: number): WatchlistSymbol {
    return {
        symbol: symbol.toUpperCase(),
        addedAt: Date.now(),
        notes: '',
        colorFlag: null,
        order,
    };
}

export function parseCSV(content: string): string[] {
    const lines = content.split(/[\n\r]+/).filter(l => l.trim());
    const symbols: string[] = [];
    
    for (const line of lines) {
        // Handle both comma-separated and single column
        const parts = line.split(',').map(p => p.trim().toUpperCase());
        for (const part of parts) {
            // Basic validation: alphanumeric with optional dot/hyphen
            if (/^[A-Z0-9.\-]{1,10}$/.test(part)) {
                symbols.push(part);
            }
        }
    }
    
    return [...new Set(symbols)]; // Remove duplicates
}

export function exportToCSV(symbols: WatchlistSymbol[]): string {
    const headers = 'Symbol,Notes,Flag\n';
    const rows = symbols.map(s => 
        `${s.symbol},"${s.notes.replace(/"/g, '""')}",${s.colorFlag || ''}`
    ).join('\n');
    return headers + rows;
}
