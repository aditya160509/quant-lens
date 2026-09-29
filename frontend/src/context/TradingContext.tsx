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
    executeOrder: () => Promise<void>;
    closePosition: () => Promise<void>;
    modifyStopLoss: (price: number) => Promise<void>;
    modifyTakeProfit: (price: number) => Promise<void>;
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

    // Fetch initial price when symbol changes (fallback if WS not ready)
    useEffect(() => {
        const fetchPrice = async () => {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/trades/prices/${state.symbol}`);
                if (res.ok) {
                    const data = await res.json();
                    dispatch({
                        type: 'SET_PRICE',
                        payload: {
                            price: data.price,
                            change: 0,
                            changePercent: 0,
                        },
                    });
                }
            } catch (e) {
                console.warn('Failed to fetch initial price:', e);
            }
        };

        if (state.symbol && state.lastPrice === 0) {
            fetchPrice();
        }
    }, [state.symbol, state.lastPrice]);

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

    // Execute order (calls backend API)
    const executeOrder = useCallback(async () => {
        dispatch({ type: 'SET_TRADE_STATE', payload: 'EXECUTING' });
        dispatch({ type: 'SET_LOADING', payload: true });
        
        try {
            const response = await fetch('/api/trades/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: state.symbol,
                    exchange: state.exchange,
                    ...state.orderIntent,
                }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Trade execution failed');
            }

            const result = await response.json();
            
            // Create position from result
            const position: Position = {
                id: result.tradeId,
                symbol: state.symbol,
                exchange: state.exchange,
                side: state.orderIntent.side,
                quantity: state.orderIntent.quantity,
                avgEntry: result.fillPrice || state.lastPrice,
                currentPrice: state.lastPrice,
                unrealizedPnl: 0,
                unrealizedPnlPercent: 0,
                stopLoss: state.orderIntent.stopLoss,
                takeProfit: state.orderIntent.takeProfit,
                entryTimestamp: Date.now(),
                breakEvenPrice: result.breakEvenPrice || result.fillPrice || state.lastPrice,
            };

            dispatch({ type: 'SET_POSITION', payload: position });
            dispatch({ type: 'RESET_ORDER_INTENT' });
        } catch (error) {
            dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Unknown error' });
            dispatch({ type: 'SET_TRADE_STATE', payload: 'INTENT' });
        } finally {
            dispatch({ type: 'SET_LOADING', payload: false });
        }
    }, [state.symbol, state.exchange, state.orderIntent, state.lastPrice]);

    // Close position
    const closePosition = useCallback(async () => {
        if (!state.position) return;
        
        const positionToClose = state.position; // Capture before clearing
        
        dispatch({ type: 'SET_TRADE_STATE', payload: 'EXITING' });
        dispatch({ type: 'SET_LOADING', payload: true });

        try {
            const response = await fetch(`/api/trades/${state.position.id}/close`, {
                method: 'POST',
            });

            let exitPrice = state.lastPrice;
            let realizedPnl = positionToClose.unrealizedPnl;

            if (response.ok) {
                const result = await response.json();
                exitPrice = result.exitPrice || state.lastPrice;
                realizedPnl = result.realizedPnl || positionToClose.unrealizedPnl;
            }

            // Save to localStorage history (works without database)
            const historyKey = 'quant360_trade_history';
            const existingHistory = JSON.parse(localStorage.getItem(historyKey) || '[]');
            const tradeRecord = {
                id: positionToClose.id,
                symbol: positionToClose.symbol,
                side: positionToClose.side,
                quantity: positionToClose.quantity,
                entryPrice: positionToClose.avgEntry,
                exitPrice: exitPrice,
                pnl: realizedPnl,
                entryTime: positionToClose.entryTimestamp,
                exitTime: Date.now(),
                duration: formatDuration(positionToClose.entryTimestamp, Date.now()),
            };
            localStorage.setItem(historyKey, JSON.stringify([tradeRecord, ...existingHistory].slice(0, 100)));

            dispatch({ type: 'SET_POSITION', payload: null });
        } catch (error) {
            dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Unknown error' });
            dispatch({ type: 'SET_TRADE_STATE', payload: 'ACTIVE_POSITION' });
        } finally {
            dispatch({ type: 'SET_LOADING', payload: false });
        }
    }, [state.position, state.lastPrice]);

    // Modify stop loss
    const modifyStopLoss = useCallback(async (price: number) => {
        if (!state.position) return;
        
        try {
            const response = await fetch(`/api/trades/${state.position.id}/stop`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stopLoss: price }),
            });

            if (!response.ok) throw new Error('Failed to update stop loss');

            dispatch({
                type: 'SET_POSITION',
                payload: { ...state.position, stopLoss: price },
            });
        } catch (error) {
            dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Unknown error' });
        }
    }, [state.position]);

    // Modify take profit
    const modifyTakeProfit = useCallback(async (price: number) => {
        if (!state.position) return;
        
        try {
            const response = await fetch(`/api/trades/${state.position.id}/target`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ takeProfit: price }),
            });

            if (!response.ok) throw new Error('Failed to update take profit');

            dispatch({
                type: 'SET_POSITION',
                payload: { ...state.position, takeProfit: price },
            });
        } catch (error) {
            dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Unknown error' });
        }
    }, [state.position]);

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
        executeOrder,
        closePosition,
        modifyStopLoss,
        modifyTakeProfit,
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
