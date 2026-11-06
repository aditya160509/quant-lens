'use client';

import React, { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react';

// Helper to format duration
function formatDuration(start: number, end: number): string {
    const diffMs = end - start;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `${diffMins}m`;
    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    if (hours < 24) return `${hours}h ${mins}m`;
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
}

// =============================================================================
// TYPES
// =============================================================================

export type Exchange = 'NSE' | 'BSE' | 'US' | 'MCX' | 'FX' | 'CRYPTO' | 'INDEX' | 'COMMODITIES';
export type OrderSide = 'BUY' | 'SELL';
export type OrderType = 'MARKET' | 'LIMIT' | 'STOP' | 'STOP_LIMIT';
export type TimeInForce = 'DAY' | 'GTC' | 'IOC';
export type TradeState = 'IDLE' | 'INTENT' | 'EXECUTING' | 'ACTIVE_POSITION' | 'EXITING';
export type Timeframe = '1m' | '5m' | '15m' | '30m' | '1h' | '1d' | '3mo' | '6mo' | '1y' | '2y' | '5y';

export interface BidAsk {
    bid: number;
    ask: number;
    bidSize: number;
    askSize: number;
}

export interface SessionStatus {
    market: 'pre' | 'regular' | 'post' | 'closed';
    label: string;
    nextOpen?: string;
}

export interface OrderIntent {
    side: OrderSide;
    orderType: OrderType;
    quantity: number;
    price?: number;
    stopLoss?: number;
    takeProfit?: number;
    timeInForce: TimeInForce;
    reduceOnly: boolean;
    postOnly: boolean;
}

export interface Position {
    id: string;
    symbol: string;
    exchange: Exchange;
    side: OrderSide;
    quantity: number;
    avgEntry: number;
    currentPrice: number;
    unrealizedPnl: number;
    unrealizedPnlPercent: number;
    stopLoss?: number;
    takeProfit?: number;
    entryTimestamp: number;
    breakEvenPrice: number;
}

export interface TradingState {
    // Market Context
    symbol: string;
    exchange: Exchange;
    timeframe: Timeframe;
    lastPrice: number;
    change: number;
    changePercent: number;
    bidAsk: BidAsk | null;
    sessionStatus: SessionStatus;
    
    // Trade State Machine
    tradeState: TradeState;
    
    // Order Intent (pre-execution)
    orderIntent: OrderIntent;
    
    // Active Position (post-execution)
    position: Position | null;
    
    // UI State
    isLoading: boolean;
    error: string | null;
    
    // Recent Symbols
    recentSymbols: string[];
}

// =============================================================================
// INITIAL STATE
// =============================================================================

const DEFAULT_ORDER_INTENT: OrderIntent = {
    side: 'BUY',
    orderType: 'MARKET',
    quantity: 1,
    price: undefined,
    stopLoss: undefined,
    takeProfit: undefined,
    timeInForce: 'DAY',
    reduceOnly: false,
    postOnly: false,
};

const initialState: TradingState = {
    symbol: 'SPY',
    exchange: 'US',
    timeframe: '5m',
    lastPrice: 0,
    change: 0,
    changePercent: 0,
    bidAsk: null,
    sessionStatus: { market: 'closed', label: 'MARKET CLOSED' },
    tradeState: 'IDLE',
    orderIntent: { ...DEFAULT_ORDER_INTENT },
    position: null,
    isLoading: false,
    error: null,
    recentSymbols: ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA'],
};

// =============================================================================
// ACTIONS
// =============================================================================

type TradingAction =
    | { type: 'SET_SYMBOL'; payload: { symbol: string; exchange: Exchange } }
    | { type: 'SET_TIMEFRAME'; payload: Timeframe }
    | { type: 'SET_PRICE'; payload: { price: number; change: number; changePercent: number } }
    | { type: 'SET_BID_ASK'; payload: BidAsk }
    | { type: 'SET_SESSION_STATUS'; payload: SessionStatus }
    | { type: 'UPDATE_ORDER_INTENT'; payload: Partial<OrderIntent> }
    | { type: 'RESET_ORDER_INTENT' }
    | { type: 'SET_TRADE_STATE'; payload: TradeState }
    | { type: 'SET_POSITION'; payload: Position | null }
    | { type: 'UPDATE_POSITION_PRICE'; payload: number }
    | { type: 'SET_LOADING'; payload: boolean }
    | { type: 'SET_ERROR'; payload: string | null }
    | { type: 'ADD_RECENT_SYMBOL'; payload: string };

// =============================================================================
// REDUCER
// =============================================================================

function tradingReducer(state: TradingState, action: TradingAction): TradingState {
    switch (action.type) {
        case 'SET_SYMBOL': {
            const newRecent = [action.payload.symbol, ...state.recentSymbols.filter(s => s !== action.payload.symbol)].slice(0, 10);
            return {
                ...state,
                symbol: action.payload.symbol,
                exchange: action.payload.exchange,
                recentSymbols: newRecent,
                // Reset position when switching symbols
                position: null,
                tradeState: 'IDLE',
            };
        }
        case 'SET_TIMEFRAME':
            return { ...state, timeframe: action.payload };
        case 'SET_PRICE':
            return {
                ...state,
                lastPrice: action.payload.price,
                change: action.payload.change,
                changePercent: action.payload.changePercent,
            };
        case 'SET_BID_ASK':
            return { ...state, bidAsk: action.payload };
        case 'SET_SESSION_STATUS':
            return { ...state, sessionStatus: action.payload };
        case 'UPDATE_ORDER_INTENT':
            return {
                ...state,
                orderIntent: { ...state.orderIntent, ...action.payload },
                tradeState: 'INTENT',
            };
        case 'RESET_ORDER_INTENT':
            return {
                ...state,
                orderIntent: { ...DEFAULT_ORDER_INTENT },
                tradeState: 'IDLE',
            };
        case 'SET_TRADE_STATE':
            return { ...state, tradeState: action.payload };
        case 'SET_POSITION':
            return {
                ...state,
                position: action.payload,
                tradeState: action.payload ? 'ACTIVE_POSITION' : 'IDLE',
            };
        case 'UPDATE_POSITION_PRICE':
            if (!state.position) return state;
            const currentPrice = action.payload;
            const pnl = state.position.side === 'BUY'
                ? (currentPrice - state.position.avgEntry) * state.position.quantity
                : (state.position.avgEntry - currentPrice) * state.position.quantity;
            const pnlPercent = (pnl / (state.position.avgEntry * state.position.quantity)) * 100;
            return {
                ...state,
                position: {
                    ...state.position,
                    currentPrice,
                    unrealizedPnl: pnl,
                    unrealizedPnlPercent: pnlPercent,
                },
            };
        case 'SET_LOADING':
            return { ...state, isLoading: action.payload };
        case 'SET_ERROR':
            return { ...state, error: action.payload };
        case 'ADD_RECENT_SYMBOL': {
            const updated = [action.payload, ...state.recentSymbols.filter(s => s !== action.payload)].slice(0, 10);
            return { ...state, recentSymbols: updated };
        }
        default:
            return state;
    }
}

// =============================================================================
// CONTEXT
// =============================================================================

interface TradingContextValue {
    state: TradingState;
    dispatch: React.Dispatch<TradingAction>;
    
    // Convenience actions
    setSymbol: (symbol: string, exchange?: Exchange) => void;
    setTimeframe: (tf: Timeframe) => void;
    updateOrderIntent: (intent: Partial<OrderIntent>) => void;
    resetOrder: () => void;
}

const TradingContext = createContext<TradingContextValue | null>(null);

// =============================================================================
// PROVIDER
// =============================================================================

interface TradingProviderProps {
    children: React.ReactNode;
    initialSymbol?: string;
}

// Helper to detect exchange from symbol (used in initial state)
function getExchangeForSymbol(symbol: string): Exchange {
    const upper = symbol.toUpperCase();
    if (upper.endsWith('.NS') || upper.endsWith('.NSE')) return 'NSE';
    if (upper.endsWith('.BO') || upper.endsWith('.BSE')) return 'BSE';
    const indianStocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'WIPRO', 'TATAMOTORS', 'SBIN', 'ITC'];
    if (indianStocks.includes(upper.replace(/\.(NS|BO|NSE|BSE)$/i, ''))) return 'NSE';
    return 'US';
}

export function TradingProvider({ children, initialSymbol }: TradingProviderProps) {
    const [state, dispatch] = useReducer(tradingReducer, {
        ...initialState,
        symbol: initialSymbol || initialState.symbol,
        exchange: initialSymbol ? getExchangeForSymbol(initialSymbol) : initialState.exchange,
    });
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // WebSocket connection for real-time prices
    useEffect(() => {
        const connectWebSocket = () => {
            // Clean up existing connection
            if (wsRef.current) {
                wsRef.current.close();
            }

            const ws = new WebSocket(`ws://localhost:8000/ws/prices?symbol=${state.symbol}`);
            
            ws.onopen = () => {
                console.log(`[WS] Connected for ${state.symbol}`);
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'price' && data.symbol === state.symbol) {
                        dispatch({
                            type: 'SET_PRICE',
                            payload: {
                                price: data.price,
                                change: data.change || 0,
                                changePercent: data.changePercent || 0,
                            },
                        });
                    }
                    if (data.type === 'bidask') {
                        dispatch({
                            type: 'SET_BID_ASK',
                            payload: {
                                bid: data.bid,
                                ask: data.ask,
                                bidSize: data.bidSize || 100,
                                askSize: data.askSize || 100,
                            },
                        });
                    }
                } catch (e) {
                    console.warn('[WS] Parse error:', e);
                }
            };

            ws.onerror = (error) => {
                console.warn('[WS] Error:', error);
            };

            ws.onclose = () => {
                console.log('[WS] Disconnected');
                // Auto-reconnect after 3 seconds
                reconnectTimeoutRef.current = setTimeout(() => {
                    if (state.symbol) {
                        connectWebSocket();
                    }
                }, 3000);
            };

            wsRef.current = ws;
        };

        // Connect when symbol changes
        if (state.symbol) {
            connectWebSocket();
        }

        return () => {
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [state.symbol]);

    // Detect exchange from symbol
    const detectExchange = useCallback((symbol: string): Exchange => {
        const upper = symbol.toUpperCase();
        if (upper.endsWith('.NS') || upper.endsWith('.NSE')) return 'NSE';
        if (upper.endsWith('.BO') || upper.endsWith('.BSE')) return 'BSE';
        if (upper.endsWith('=X')) return 'FX';
        if (upper.endsWith('=F')) return 'COMMODITIES';
        if (upper.includes('-USD')) return 'CRYPTO';
        if (upper.startsWith('^') || upper === 'DX-Y.NYB') return 'INDEX';
        
        // Common Indian stocks
        const indianStocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'WIPRO', 'TATAMOTORS', 'SBIN', 'ITC'];
        if (indianStocks.includes(upper.replace(/\.(NS|BO|NSE|BSE)$/i, ''))) return 'NSE';
        return 'US';
    }, []);

    // Set symbol
    const setSymbol = useCallback((symbol: string, exchange?: Exchange) => {
        const ex = exchange || detectExchange(symbol);
        dispatch({ type: 'SET_SYMBOL', payload: { symbol, exchange: ex } });
    }, [detectExchange]);

    // Set timeframe
    const setTimeframe = useCallback((tf: Timeframe) => {
        dispatch({ type: 'SET_TIMEFRAME', payload: tf });
    }, []);

    // Update order intent
    const updateOrderIntent = useCallback((intent: Partial<OrderIntent>) => {
        dispatch({ type: 'UPDATE_ORDER_INTENT', payload: intent });
    }, []);

    // Reset order
    const resetOrder = useCallback(() => {
        dispatch({ type: 'RESET_ORDER_INTENT' });
    }, []);

    // Update position PnL when price changes (throttled to avoid infinite loop)
    const lastUpdateRef = useRef<number>(0);
    useEffect(() => {
        if (state.position && state.lastPrice > 0) {
            const now = Date.now();
            // Only update every 500ms to prevent infinite loop
            if (now - lastUpdateRef.current > 500) {
                lastUpdateRef.current = now;
                dispatch({ type: 'UPDATE_POSITION_PRICE', payload: state.lastPrice });
            }
        }
    }, [state.lastPrice, state.position?.id]); // Only depend on position.id, not entire position

    const value: TradingContextValue = {
        state,
        dispatch,
        setSymbol,
        setTimeframe,
        updateOrderIntent,
        resetOrder,
    };

    return (
        <TradingContext.Provider value={value}>
            {children}
        </TradingContext.Provider>
    );
}

// =============================================================================
// HOOK
// =============================================================================

export function useTradingContext() {
    const context = useContext(TradingContext);
    if (!context) {
        throw new Error('useTradingContext must be used within TradingProvider');
    }
    return context;
}

export default TradingContext;
