'use client';

/**
 * QUANT360 ELITE TRADE PANEL
 * 
 * Professional-grade trade execution panel for institutional-quality trading.
 * This is an execution surface, not a thinking surface.
 * 
 * Layout: Single-column vertical scroll within the Trade tab.
 * 
 * Sections (Top to Bottom):
 * 1. Instrument Header (Always visible)
 * 2. Market Snapshot (Minimal data grid)
 * 3. Order Entry Form (Core action area)
 * 4. Execution Preview (Mandatory pre-flight check)
 * 5. Intent Confirmation (One-line awareness)
 * 6. Place Order Button (Single action)
 * 7. Order Lifecycle Panel (Post-submission)
 * 8. Inline Journal (Auto-opens after fill)
 * 9. Position Impact Summary (After fill)
 * 10. Active Orders (If any exist)
 * 11. Local Trade History (Context only)
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTradingContext } from '@/context/TradingContext';
import { usePortfolioStore } from '@/lib/portfolioStore';
import { Activity, Clock } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

type OrderSide = 'BUY' | 'SELL';
type OrderType = 'MARKET' | 'LIMIT' | 'STOP' | 'STOP_LIMIT' | 'TWAP' | 'VWAP';
type TimeInForce = 'DAY' | 'GTC' | 'IOC';
type OrderStatus = 'SUBMITTED' | 'ACKNOWLEDGED' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELLED' | 'REJECTED';
type InstrumentType = 'Equity' | 'FX' | 'Crypto';
type MarketStatus = 'open' | 'closed' | 'pre' | 'post';
type ReasonTag = 'Breakout' | 'Rebalance' | 'Hedge' | 'Mean Reversion' | 'Event-Driven' | 'Other';

interface MarketSnapshot {
    lastPrice: number;
    bid: number;
    ask: number;
    spread: number;
    dayVolume: number;
}

interface OrderLifecycle {
    status: OrderStatus;
    submittedAt: number | null;
    acknowledgedAt: number | null;
    filledAt: number | null;
    fillQuantity: number;
    totalQuantity: number;
    avgFillPrice: number | null;
    rejectReason?: string;
}

interface ExecutionPreview {
    estimatedFillPrice: number;
    totalCost: number;
    fees: number;
    estimatedSlippage: number;
    newPositionSize: number;
    positionChange: number;
    remainingCash: number;
    cashChange: number;
}

interface JournalEntry {
    thesis: string;
    setupName: string;
    reasonTag: ReasonTag;
}

interface ActiveOrder {
    id: string;
    orderType: OrderType;
    side: OrderSide;
    remainingQuantity: number;
    limitPrice?: number;
    stopPrice?: number;
    status: OrderStatus;
}

interface TradeHistoryItem {
    id: string;
    timestamp: number;
    side: OrderSide;
    quantity: number;
    fillPrice: number;
    totalValue: number;
}

interface ValidationError {
    field: string;
    message: string;
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function formatCurrency(value: number | undefined | null): string {
    if (value === undefined || value === null || isNaN(Number(value))) return '$0.00';
    return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 });
}

function formatNumber(value: number | undefined | null, decimals: number = 2): string {
    if (value === undefined || value === null || isNaN(Number(value))) return '0' + (decimals > 0 ? '.' + '0'.repeat(decimals) : '');
    return Number(value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatTimestamp(ts: number): string {
    const date = new Date(ts);
    const hours = date.getHours().toString().padStart(2, '0');
    const mins = date.getMinutes().toString().padStart(2, '0');
    const secs = date.getSeconds().toString().padStart(2, '0');
    const ms = date.getMilliseconds().toString().padStart(3, '0');
    return `${hours}:${mins}:${secs}.${ms}`;
}

function getInstrumentType(symbol: string): InstrumentType {
    if (symbol.includes('-USD') || symbol.includes('BTC') || symbol.includes('ETH') || symbol.includes('DOGE')) {
        return 'Crypto';
    }
    if (symbol.includes('/') || ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'].some(fx => symbol.includes(fx))) {
        return 'FX';
    }
    return 'Equity';
}

function getExchangeName(symbol: string, exchange: string): string {
    if (exchange === 'NSE') return 'NSE';
    if (exchange === 'BSE') return 'BSE';
    if (symbol.includes('-USD') || symbol.includes('BTC') || symbol.includes('ETH')) return 'Coinbase';
    return 'NASDAQ';
}

function generateOrderId(): string {
    return `ORD-${Date.now()}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
}

// =============================================================================
// MAIN TRADE TAB COMPONENT
// =============================================================================

export default function TradeTab() {
    const { state } = useTradingContext();
    
    // Order Form State
    const [side, setSide] = useState<OrderSide>('BUY');
    const [orderType, setOrderType] = useState<OrderType>('MARKET');
    const [quantity, setQuantity] = useState('100');
    const [limitPrice, setLimitPrice] = useState('');
    const [stopPrice, setStopPrice] = useState('');
    const [timeInForce, setTimeInForce] = useState<TimeInForce>('DAY');
    const [useNotional, setUseNotional] = useState(false);
    
    // Execution State
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [orderLifecycle, setOrderLifecycle] = useState<OrderLifecycle | null>(null);
    const [showJournal, setShowJournal] = useState(false);
    const [journalSaved, setJournalSaved] = useState(false);
    const [journal, setJournal] = useState<JournalEntry>({ thesis: '', setupName: '', reasonTag: 'Other' });
    
    // Data State from Store
    const { 
        snapshot, 
        risk: portfolioRisk,
        refreshAll, 
        loading: portfolioLoading 
    } = usePortfolioStore();
    
    const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
    const [tradeHistory, setTradeHistory] = useState<TradeHistoryItem[]>([]);
    const [errors, setErrors] = useState<ValidationError[]>([]);
    
    // Duplicate submit prevention
    const orderIdRef = useRef<string | null>(null);
    const isSubmittingRef = useRef(false);

    // Initial load and sync
    useEffect(() => {
        refreshAll();
        
        // Load local trade history for this symbol
        const historyKey = 'quant360_trade_history';
        const history = JSON.parse(localStorage.getItem(historyKey) || '[]');
        const symbolHistory = history.filter((t: any) => t.symbol?.toUpperCase() === state.symbol.toUpperCase()).slice(0, 5);
        setTradeHistory(symbolHistory.map((t: any) => ({
            id: t.id,
            timestamp: t.exitTime || t.entryTime,
            side: t.side,
            quantity: t.quantity,
            fillPrice: t.exitPrice || t.entryPrice,
            totalValue: (t.exitPrice || t.entryPrice) * t.quantity,
        })));
    }, [state.symbol, refreshAll]);

    // Market snapshot calculation
    const marketSnapshot: MarketSnapshot = useMemo(() => {
        const bid = state.bidAsk?.bid || state.lastPrice * 0.9999;
        const ask = state.bidAsk?.ask || state.lastPrice * 1.0001;
        return {
            lastPrice: state.lastPrice,
            bid,
            ask,
            spread: ask - bid,
            dayVolume: 10500000,
        };
    }, [state.lastPrice, state.bidAsk]);

    // Market status detection
    const marketStatus: MarketStatus = useMemo(() => {
        const session = state.sessionStatus?.market;
        if (session === 'regular') return 'open';
        if (session === 'pre') return 'pre';
        if (session === 'post') return 'post';
        return 'closed';
    }, [state.sessionStatus]);

    // Status config
    const statusConfig = {
        open: { color: 'bg-[var(--terminal-green)]', label: 'Open' },
        closed: { color: 'bg-[var(--terminal-red)]', label: 'Closed' },
        pre: { color: 'bg-[var(--terminal-yellow)]', label: 'Pre-Mkt' },
        post: { color: 'bg-[var(--terminal-yellow)]', label: 'After-Hrs' },
    };

    // Calculate max quantity based on REAL store data
    const maxQuantity = useMemo(() => {
        const cash = snapshot?.cash || 10000;
        const currentPosition = snapshot?.positions?.find(
            (p: any) => p.ticker?.toUpperCase() === state.symbol.toUpperCase()
        );
        
        if (side === 'BUY') {
            return Math.floor(cash / state.lastPrice);
        } else {
            return currentPosition?.qty || 0;
        }
    }, [snapshot, side, state.symbol, state.lastPrice]);

    // Current position
    const currentPosition = useMemo(() => {
        return snapshot?.positions?.find(
            (p: any) => p.ticker?.toUpperCase() === state.symbol.toUpperCase()
        );
    }, [snapshot, state.symbol]);

    // Validation using live cash/positions
    useEffect(() => {
        const newErrors: ValidationError[] = [];
        const qty = parseFloat(quantity) || 0;
        const cash = snapshot?.cash || 10000;

        if (qty <= 0) {
            newErrors.push({ field: 'quantity', message: 'Quantity must be > 0' });
        }

        if (side === 'BUY') {
            const cost = qty * state.lastPrice;
            if (cost > cash) {
                newErrors.push({ field: 'quantity', message: `Insufficient cash (${formatCurrency(cash)})` });
            }
        } else {
            const positionQty = currentPosition?.qty || 0;
            if (qty > positionQty) {
                newErrors.push({ field: 'quantity', message: `Max: ${positionQty} shares` });
            }
        }

        if (['LIMIT', 'STOP_LIMIT'].includes(orderType) && limitPrice) {
            const price = parseFloat(limitPrice);
            if (isNaN(price) || price <= 0) {
                newErrors.push({ field: 'limitPrice', message: 'Invalid price' });
            }
        }

        if (['STOP', 'STOP_LIMIT'].includes(orderType) && stopPrice) {
            const price = parseFloat(stopPrice);
            if (isNaN(price) || price <= 0) {
                newErrors.push({ field: 'stopPrice', message: 'Invalid price' });
            }
        }

        setErrors(newErrors);
    }, [quantity, side, orderType, limitPrice, stopPrice, snapshot, state.symbol, state.lastPrice, currentPosition]);

    const getFieldError = (field: string) => errors.find(e => e.field === field)?.message;

    // Execution preview calculation
    const executionPreview: ExecutionPreview | null = useMemo(() => {
        const qty = parseFloat(quantity) || 0;
        if (qty <= 0) return null;

        const isBuy = side === 'BUY';
        const cash = snapshot?.cash || 0;
        const currentPositionSize = currentPosition?.qty || 0;

        let fillPrice = state.lastPrice;
        if (orderType === 'LIMIT' && limitPrice) {
            fillPrice = parseFloat(limitPrice);
        }

        const slippageRate = orderType === 'MARKET' ? 0.05 : 0;
        const slippage = isBuy ? fillPrice * (slippageRate / 100) : -fillPrice * (slippageRate / 100);
        const adjustedFillPrice = fillPrice + slippage;

        const fees = 5.00; // Standard institutional ticket fee
        const totalTradeValue = qty * adjustedFillPrice;
        const cashChange = isBuy ? -(totalTradeValue + fees) : (totalTradeValue - fees);
        const positionChange = isBuy ? qty : -qty;

        return {
            estimatedFillPrice: adjustedFillPrice,
            totalCost: totalTradeValue + fees,
            fees,
            estimatedSlippage: slippageRate,
            newPositionSize: currentPositionSize + positionChange,
            positionChange,
            remainingCash: cash + cashChange,
            cashChange,
        };
    }, [quantity, side, orderType, limitPrice, state.lastPrice, snapshot, currentPosition]);

    // PRE-TRADE IMPACT (BETA / VaR WHAT-IF)
    const preTradeImpact = useMemo(() => {
        if (!executionPreview || !portfolioRisk || !snapshot) return null;
        
        const currentNav = snapshot.nav;
        const currentBeta = portfolioRisk.beta;
        const currentVaR = portfolioRisk.var95;
        
        const tradeNotional = parseFloat(quantity) * state.lastPrice;
        const weightShift = tradeNotional / currentNav;
        
        // Target Ticker Beta (Default to 1.0 if not known, or use position beta)
        const symbolBeta = currentPosition?.beta || 1.15; // Simulated ticker beta
        
        const newBeta = currentBeta + (weightShift * (side === 'BUY' ? 1 : -1) * (symbolBeta - currentBeta));
        const varShift = weightShift * (side === 'BUY' ? 0.05 : -0.05) * currentVaR; // Dummy VaR impact logic
        
        return {
            betaDelta: newBeta - currentBeta,
            newBeta,
            varDeltaPercent: currentVaR > 0 ? (varShift / currentVaR) * 100 : 0
        };
    }, [executionPreview, portfolioRisk, snapshot, quantity, state.lastPrice, side, currentPosition]);

    // Intent confirmation message
    const intentMessage = useMemo(() => {
        const qty = parseFloat(quantity) || 0;
        if (qty <= 0 || !executionPreview) return '';

        const currentPositionSize = currentPosition?.qty || 0;
        const portfolioValue = snapshot?.nav || 0;
        if (portfolioValue === 0) return '';
        const positionValue = executionPreview.newPositionSize * state.lastPrice;
        const exposurePercent = (positionValue / portfolioValue) * 100;

        if (currentPositionSize === 0 && side === 'BUY') {
            return `Opens new ${state.symbol} position`;
        }
        
        if (executionPreview.newPositionSize === 0 && side === 'SELL') {
            return `Closes entire ${state.symbol} position`;
        }

        if (side === 'BUY') {
            return `Increases ${state.symbol} exposure to ${exposurePercent.toFixed(1)}%`;
        } else {
            const reductionPercent = (qty / currentPositionSize) * 100;
            return `Reduces position by ${reductionPercent.toFixed(0)}%`;
        }
    }, [quantity, side, executionPreview, snapshot, state.symbol, state.lastPrice, currentPosition]);

    // Order submission
    const handlePlaceOrder = useCallback(async () => {
        if (isSubmittingRef.current) return;
        if (errors.length > 0) return;

        isSubmittingRef.current = true;
        setIsSubmitting(true);
        
        const orderId = generateOrderId();
        orderIdRef.current = orderId;

        const submittedAt = Date.now();
        setOrderLifecycle({
            status: 'SUBMITTED',
            submittedAt,
            acknowledgedAt: null,
            filledAt: null,
            fillQuantity: 0,
            totalQuantity: parseFloat(quantity),
            avgFillPrice: null,
        });

        try {
            await new Promise(r => setTimeout(r, 150 + Math.random() * 100));
            const acknowledgedAt = Date.now();
            
            setOrderLifecycle(prev => prev ? {
                ...prev,
                status: 'ACKNOWLEDGED',
                acknowledgedAt,
            } : null);

            if (orderType === 'MARKET') {
                await new Promise(r => setTimeout(r, 100 + Math.random() * 150));
                const filledAt = Date.now();
                
                setOrderLifecycle(prev => prev ? {
                    ...prev,
                    status: 'FILLED',
                    filledAt,
                    fillQuantity: parseFloat(quantity),
                    avgFillPrice: executionPreview?.estimatedFillPrice || state.lastPrice,
                } : null);

                setShowJournal(true);
            } else {
                const newActiveOrder: ActiveOrder = {
                    id: orderId,
                    orderType,
                    side,
                    remainingQuantity: parseFloat(quantity),
                    limitPrice: limitPrice ? parseFloat(limitPrice) : undefined,
                    stopPrice: stopPrice ? parseFloat(stopPrice) : undefined,
                    status: 'ACKNOWLEDGED',
                };
                setActiveOrders(prev => [...prev, newActiveOrder]);
            }
        } catch (error) {
            setOrderLifecycle(prev => prev ? {
                ...prev,
                status: 'REJECTED',
                rejectReason: error instanceof Error ? error.message : 'Unknown error',
            } : null);
        } finally {
            setIsSubmitting(false);
            isSubmittingRef.current = false;
        }
    }, [quantity, side, orderType, limitPrice, stopPrice, errors, executionPreview, state.lastPrice]);

    const handleCancelOrder = useCallback((orderId: string) => {
        setActiveOrders(prev => prev.filter(o => o.id !== orderId));
    }, []);

    const handleSaveJournal = useCallback(() => {
        const journalKey = 'quant360_trade_journal';
        const historyKey = 'quant360_trade_history';
        
        const existingJournal = JSON.parse(localStorage.getItem(journalKey) || '[]');
        const existingHistory = JSON.parse(localStorage.getItem(historyKey) || '[]');
        
        // Include Signal Intelligence Snapshot for forensic analysis
        const forensicSnapshot = {
            confidence: 82, // Hardcoded for demo/fallback
            timestamp: Date.now(),
            price: state.lastPrice,
        };

        const entry = {
            id: orderIdRef.current,
            symbol: state.symbol,
            side,
            quantity: parseFloat(quantity),
            price: orderLifecycle?.avgFillPrice || executionPreview?.estimatedFillPrice || state.lastPrice,
            timestamp: Date.now(),
            forensic: forensicSnapshot,
            ...journal,
        };

        const historyEntry = {
            id: entry.id,
            timestamp: entry.timestamp,
            symbol: entry.symbol,
            side: entry.side,
            quantity: entry.quantity,
            fillPrice: entry.price,
            totalValue: entry.price * entry.quantity,
            journal: entry
        };

        localStorage.setItem(journalKey, JSON.stringify([entry, ...existingJournal].slice(0, 100)));
        localStorage.setItem(historyKey, JSON.stringify([historyEntry, ...existingHistory].slice(0, 500)));
        
        // Update local state for immediate feedback
        setTradeHistory(prev => [historyEntry, ...prev].slice(0, 10));
        setJournalSaved(true);
        setShowJournal(false);
    }, [journal, state.symbol, side, quantity, executionPreview, orderLifecycle, state.lastPrice]);

    const handleSkipJournal = useCallback(() => {
        const historyKey = 'quant360_trade_history';
        const existingHistory = JSON.parse(localStorage.getItem(historyKey) || '[]');
        
        const historyEntry = {
            id: orderIdRef.current,
            timestamp: Date.now(),
            symbol: state.symbol,
            side,
            quantity: parseFloat(quantity),
            fillPrice: orderLifecycle?.avgFillPrice || executionPreview?.estimatedFillPrice || state.lastPrice,
            totalValue: (orderLifecycle?.avgFillPrice || executionPreview?.estimatedFillPrice || state.lastPrice) * parseFloat(quantity),
        };

        localStorage.setItem(historyKey, JSON.stringify([historyEntry, ...existingHistory].slice(0, 500)));
        setTradeHistory(prev => [historyEntry, ...prev].slice(0, 10));
        setShowJournal(false);
    }, [state.symbol, side, quantity, orderLifecycle, executionPreview, state.lastPrice]);

    const handleNewOrder = useCallback(() => {
        setOrderLifecycle(null);
        setShowJournal(false);
        setJournalSaved(false);
        setJournal({ thesis: '', setupName: '', reasonTag: 'Other' });
        setQuantity('100');
        setLimitPrice('');
        setStopPrice('');
        orderIdRef.current = null;
    }, []);

    const isFormValid = errors.length === 0 && parseFloat(quantity) > 0;
    const showPositionImpact = orderLifecycle?.status === 'FILLED' && !showJournal;
    const showLimitPrice = ['LIMIT', 'STOP_LIMIT'].includes(orderType);
    const showStopPrice = ['STOP', 'STOP_LIMIT'].includes(orderType);

    const orderTypes = [
        { value: 'MARKET', label: 'Market' },
        { value: 'LIMIT', label: 'Limit' },
        { value: 'STOP', label: 'Stop' },
        { value: 'STOP_LIMIT', label: 'Stop-Limit' },
        { value: 'TWAP', label: 'TWAP' },
        { value: 'VWAP', label: 'VWAP' },
    ];

    const timeInForceOptions = [
        { value: 'DAY', label: 'Day' },
        { value: 'GTC', label: 'GTC' },
        { value: 'IOC', label: 'IOC' },
    ];

    const reasonTags: ReasonTag[] = ['Breakout', 'Rebalance', 'Hedge', 'Mean Reversion', 'Event-Driven', 'Other'];

    const isPositive = state.change >= 0;
    const status = statusConfig[marketStatus];
    const executionLatency = orderLifecycle?.filledAt && orderLifecycle?.submittedAt 
        ? orderLifecycle.filledAt - orderLifecycle.submittedAt 
        : null;

    return (
        <div className="h-full overflow-auto bg-terminal-dark p-3 space-y-4">
            {/* Trade Panels */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-4">
                    {/* ================================================================
                        1. INSTRUMENT HEADER - Compact
                    ================================================================ */}
            <div className="bg-[var(--terminal-darker)] border border-[var(--terminal-gray)] rounded p-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-base font-bold text-[var(--terminal-yellow)] font-mono">{state.symbol}</span>
                        <span className="px-1 py-0.5 text-[8px] font-mono font-bold uppercase tracking-wider bg-[var(--terminal-gray)]/50 text-[var(--terminal-dim)] rounded">
                            {getInstrumentType(state.symbol)}
                        </span>
                        <span className="text-[9px] font-mono text-[var(--terminal-dim)]">{getExchangeName(state.symbol, state.exchange)}</span>
                        <div className="flex items-center gap-1">
                            <div className={`w-1 h-1 rounded-full ${status.color} animate-pulse`} />
                            <span className="text-[8px] font-mono text-[var(--terminal-dim)] uppercase">{status.label}</span>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-lg font-bold font-mono text-[var(--foreground)]">
                            {formatCurrency(state.lastPrice)}
                        </span>
                        <span className={`text-xs font-mono font-bold ${isPositive ? 'text-[var(--terminal-green)]' : 'text-[var(--terminal-red)]'}`}>
                            {isPositive ? '+' : ''}{formatCurrency(state.change)} ({isPositive ? '+' : ''}{state.changePercent.toFixed(2)}%)
                        </span>
                    </div>
                </div>
            </div>

            {/* ================================================================
                2. MARKET SNAPSHOT - Inline compact
            ================================================================ */}
            <div className="grid grid-cols-5 gap-1">
                {[
                    { label: 'Last', value: formatCurrency(marketSnapshot.lastPrice), color: 'text-[var(--foreground)]' },
                    { label: 'Bid', value: formatCurrency(marketSnapshot.bid), color: 'text-[var(--terminal-green)]' },
                    { label: 'Ask', value: formatCurrency(marketSnapshot.ask), color: 'text-[var(--terminal-red)]' },
                    { label: 'Spread', value: formatCurrency(marketSnapshot.spread), color: 'text-[var(--terminal-yellow)]' },
                    { label: 'Volume', value: formatNumber(marketSnapshot.dayVolume / 1000000, 1) + 'M', color: 'text-[var(--terminal-cyan)]' },
                ].map((item) => (
                    <div key={item.label} className="bg-[var(--terminal-darker)] border border-[var(--terminal-gray)]/50 rounded px-1.5 py-1 text-center">
                        <div className="text-[7px] font-mono text-[var(--terminal-dim)] uppercase">{item.label}</div>
                        <div className={`text-xs font-mono font-bold ${item.color}`}>{item.value}</div>
                    </div>
                ))}
            </div>

            {/* ================================================================
                3. ORDER ENTRY FORM - Compact Professional
            ================================================================ */}
            <div className="bg-[var(--terminal-darker)] border border-[var(--terminal-gray)] rounded p-3 space-y-2">
                <h3 className="text-[var(--terminal-yellow)] font-mono text-[10px] font-bold tracking-wide uppercase">Order Entry</h3>

                {/* Side Toggle - Compact */}
                <div className="grid grid-cols-2 gap-1">
                    <button
                        onClick={() => setSide('BUY')}
                        className={`py-2 font-mono font-bold text-sm rounded transition-all ${
                            side === 'BUY'
                                ? 'bg-[var(--terminal-green)] text-[var(--terminal-black)]'
                                : 'bg-[var(--terminal-darker)] border border-[var(--terminal-gray)] text-[var(--terminal-dim)] hover:border-[var(--terminal-green)]/50'
                        }`}
                    >
                        BUY
                    </button>
                    <button
                        onClick={() => setSide('SELL')}
                        className={`py-2 font-mono font-bold text-sm rounded transition-all ${
                            side === 'SELL'
                                ? 'bg-[var(--terminal-red)] text-[var(--terminal-black)]'
                                : 'bg-[var(--terminal-darker)] border border-[var(--terminal-gray)] text-[var(--terminal-dim)] hover:border-[var(--terminal-red)]/50'
                        }`}
                    >
                        SELL
                    </button>
                </div>

                {/* Order Type & Time in Force - Compact */}
                <div className="grid grid-cols-2 gap-2">
                    <div>
                        <label className="text-[8px] font-mono text-[var(--terminal-dim)] uppercase mb-0.5 block">Type</label>
                        <select
                            value={orderType}
                            onChange={(e) => setOrderType(e.target.value as OrderType)}
                            className="w-full bg-[var(--terminal-black)] border border-[var(--terminal-gray)] rounded px-2 py-1.5 text-[var(--foreground)] font-mono text-xs focus:border-[var(--terminal-yellow)] outline-none"
                        >
                            {orderTypes.map((type) => (
                                <option key={type.value} value={type.value}>{type.label}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="text-[8px] font-mono text-[var(--terminal-dim)] uppercase mb-0.5 block">TIF</label>
                        <select
                            value={timeInForce}
                            onChange={(e) => setTimeInForce(e.target.value as TimeInForce)}
                            className="w-full bg-[var(--terminal-black)] border border-[var(--terminal-gray)] rounded px-2 py-1.5 text-[var(--foreground)] font-mono text-xs focus:border-[var(--terminal-yellow)] outline-none"
                        >
                            {timeInForceOptions.map((tif) => (
                                <option key={tif.value} value={tif.value}>{tif.label}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Quantity Input - Compact */}
                <div>
                    <div className="flex items-center justify-between mb-0.5">
                        <label className="text-[8px] font-mono text-[var(--terminal-dim)] uppercase">
                            {useNotional ? 'Notional' : 'Qty'}
                        </label>
                        <button
                            onClick={() => setUseNotional(!useNotional)}
                            className="text-[7px] font-mono text-[var(--terminal-cyan)] hover:text-[var(--terminal-cyan)]/80"
                        >
                            → {useNotional ? 'Units' : '$'}
                        </button>
                    </div>
                    <div className="relative">
                        <input
                            type="text"
                            value={quantity}
                            onChange={(e) => setQuantity(e.target.value)}
                            className={`w-full bg-[var(--terminal-black)] border rounded px-2 py-1.5 text-[var(--foreground)] font-mono text-sm focus:ring-1 outline-none ${
                                getFieldError('quantity')
                                    ? 'border-[var(--terminal-red)] focus:border-[var(--terminal-red)]'
                                    : 'border-[var(--terminal-gray)] focus:border-[var(--terminal-yellow)]'
                            }`}
                        />
                        <button
                            onClick={() => setQuantity(useNotional ? (maxQuantity * state.lastPrice).toFixed(2) : maxQuantity.toString())}
                            className="absolute right-1.5 top-1/2 -translate-y-1/2 px-1 py-0.5 text-[7px] font-mono font-bold text-[var(--terminal-yellow)] bg-[var(--terminal-yellow)]/10 border border-[var(--terminal-yellow)]/25 rounded hover:bg-[var(--terminal-yellow)]/20"
                        >
                            MAX
                        </button>
                    </div>
                    {getFieldError('quantity') && (
                        <p className="text-[9px] font-mono text-[var(--terminal-red)] mt-0.5">{getFieldError('quantity')}</p>
                    )}
                </div>

                {/* Limit/Stop Price - Inline Compact */}
                {(showLimitPrice || showStopPrice) && (
                    <div className="grid grid-cols-2 gap-2">
                        {showLimitPrice && (
                            <div>
                                <label className="text-[8px] font-mono text-terminal-dim uppercase mb-0.5 block">Limit</label>
                                <input
                                    type="text"
                                    value={limitPrice}
                                    onChange={(e) => setLimitPrice(e.target.value)}
                                    placeholder={state.lastPrice.toFixed(2)}
                                    className={`w-full bg-terminal-black border rounded px-2 py-1.5 text-terminal-text font-mono text-sm outline-none ${
                                        getFieldError('limitPrice') ? 'border-terminal-red' : 'border-terminal-gray focus:border-terminal-yellow'
                                    }`}
                                />
                            </div>
                        )}
                        {showStopPrice && (
                            <div>
                                <label className="text-[8px] font-mono text-terminal-dim uppercase mb-0.5 block">Stop</label>
                                <input
                                    type="text"
                                    value={stopPrice}
                                    onChange={(e) => setStopPrice(e.target.value)}
                                    placeholder={state.lastPrice.toFixed(2)}
                                    className={`w-full bg-terminal-black border rounded px-2 py-1.5 text-terminal-text font-mono text-sm outline-none ${
                                        getFieldError('stopPrice') ? 'border-terminal-red' : 'border-terminal-gray focus:border-terminal-yellow'
                                    }`}
                                />
                            </div>
                        )}
                    </div>
                )}
            </div>



            {/* ================================================================
                6. PLACE ORDER BUTTON - More compact
            ================================================================ */}
            {!orderLifecycle ? (
                <button
                    onClick={handlePlaceOrder}
                    disabled={!isFormValid || isSubmitting}
                    className={`w-full py-2.5 font-mono font-bold text-sm rounded transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                        side === 'BUY'
                            ? 'bg-terminal-green hover:bg-terminal-green/90 text-terminal-black'
                            : 'bg-terminal-red hover:bg-terminal-red/90 text-terminal-black'
                    }`}
                >
                    {isSubmitting ? (
                        <span className="flex items-center justify-center gap-2">
                            <span className="w-3 h-3 border-2 border-terminal-black/30 border-t-terminal-black rounded-full animate-spin" />
                            EXECUTING
                        </span>
                    ) : (
                        'PLACE ORDER'
                    )}
                </button>
            ) : (
                <button
                    onClick={handleNewOrder}
                    className="w-full py-2 font-mono font-bold text-sm rounded bg-terminal-darker border border-terminal-gray text-terminal-text hover:border-terminal-yellow hover:text-terminal-yellow transition-all"
                >
                    NEW ORDER
                </button>
            )}

            {/* ================================================================
                7. ORDER LIFECYCLE PANEL
            ================================================================ */}
            {orderLifecycle && (
                <div className="bg-terminal-darker border border-terminal-gray rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="text-[9px] font-mono text-terminal-dim uppercase">Order Status</h4>
                        <span className={`px-2 py-0.5 text-[9px] font-mono font-bold uppercase rounded ${
                            orderLifecycle.status === 'FILLED' ? 'bg-terminal-green/20 text-terminal-green' :
                            orderLifecycle.status === 'REJECTED' ? 'bg-terminal-red/20 text-terminal-red' :
                            orderLifecycle.status === 'ACKNOWLEDGED' ? 'bg-terminal-blue/20 text-terminal-blue' :
                            'bg-terminal-gray/50 text-terminal-dim'
                        }`}>
                            {orderLifecycle.status.replace('_', ' ')}
                        </span>
                    </div>
                    
                    {/* Time Awareness */}
                    <div className="space-y-1 text-[10px] font-mono">
                        {orderLifecycle.submittedAt && (
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Submitted</span>
                                <span className="text-terminal-text">{formatTimestamp(orderLifecycle.submittedAt)}</span>
                            </div>
                        )}
                        {orderLifecycle.acknowledgedAt && (
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Acknowledged</span>
                                <span className="text-terminal-text">{formatTimestamp(orderLifecycle.acknowledgedAt)}</span>
                            </div>
                        )}
                        {orderLifecycle.filledAt && (
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Filled</span>
                                <span className="text-terminal-text">{formatTimestamp(orderLifecycle.filledAt)}</span>
                            </div>
                        )}
                        {executionLatency !== null && (
                            <div className="flex justify-between pt-1 border-t border-terminal-gray/50">
                                <span className="text-terminal-dim">Latency</span>
                                <span className="text-terminal-cyan font-bold">{executionLatency}ms</span>
                            </div>
                        )}
                        {orderLifecycle.avgFillPrice && (
                            <div className="flex justify-between">
                                <span className="text-terminal-dim">Fill Price</span>
                                <span className="text-terminal-green font-bold">{formatCurrency(orderLifecycle.avgFillPrice)}</span>
                            </div>
                        )}
                    </div>

                    {orderLifecycle.status === 'REJECTED' && orderLifecycle.rejectReason && (
                        <div className="mt-2 p-2 bg-terminal-red/10 border border-terminal-red/30 rounded">
                            <p className="text-[10px] font-mono text-terminal-red">{orderLifecycle.rejectReason}</p>
                        </div>
                    )}
                </div>
            )}

            {/* ================================================================
                8. INLINE JOURNAL (Auto-opens after fill)
            ================================================================ */}
            {showJournal && (
                <div className="bg-terminal-green/5 border border-terminal-green/20 rounded-lg p-4 space-y-3">
                    <h4 className="text-[9px] font-mono text-terminal-green uppercase font-bold">Trade Journal</h4>
                    
                    <div>
                        <label className="text-[8px] font-mono text-terminal-dim uppercase mb-1 block">Trade Thesis</label>
                        <textarea
                            value={journal.thesis}
                            onChange={(e) => setJournal({ ...journal, thesis: e.target.value })}
                            placeholder="Why did you make this trade?"
                            rows={2}
                            className="w-full bg-terminal-black border border-terminal-gray rounded px-2 py-1.5 text-xs font-mono text-terminal-text focus:border-terminal-green outline-none resize-none"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-[8px] font-mono text-terminal-dim uppercase mb-1 block">Setup (Optional)</label>
                            <input
                                type="text"
                                value={journal.setupName}
                                onChange={(e) => setJournal({ ...journal, setupName: e.target.value })}
                                placeholder="e.g., Cup & Handle"
                                className="w-full bg-terminal-black border border-terminal-gray rounded px-2 py-1.5 text-xs font-mono text-terminal-text focus:border-terminal-green outline-none"
                            />
                        </div>
                        <div>
                            <label className="text-[8px] font-mono text-terminal-dim uppercase mb-1 block">Reason *</label>
                            <select
                                value={journal.reasonTag}
                                onChange={(e) => setJournal({ ...journal, reasonTag: e.target.value as ReasonTag })}
                                className="w-full bg-terminal-black border border-terminal-gray rounded px-2 py-1.5 text-xs font-mono text-terminal-text focus:border-terminal-green outline-none"
                            >
                                {reasonTags.map((tag) => (
                                    <option key={tag} value={tag}>{tag}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                        <button
                            onClick={handleSaveJournal}
                            className="flex-1 py-2 bg-terminal-green text-terminal-black font-mono font-bold text-xs rounded hover:bg-terminal-green/90 transition-all"
                        >
                            Save Entry
                        </button>
                        <button
                            onClick={handleSkipJournal}
                            className="px-3 py-2 text-terminal-dim font-mono text-xs hover:text-terminal-text"
                        >
                            Skip
                        </button>
                    </div>
                </div>
            )}

                    </div>
                
                {/* RIGHT COLUMN: RECAP & HISTORY (Filling the space) */}
                <div className="space-y-4">
                    {/* Market Context Snapshot */}
                    <div className="bg-[var(--terminal-darker)] border border-[var(--terminal-gray)] rounded p-3">
                        <h4 className="text-[8px] font-mono text-terminal-dim uppercase font-bold tracking-widest mb-2">Market Context</h4>
                        <div className="grid grid-cols-5 gap-1">
                            {[
                                { label: 'Last', value: formatCurrency(marketSnapshot.lastPrice), color: 'text-[var(--foreground)]' },
                                { label: 'Bid', value: formatCurrency(marketSnapshot.bid), color: 'text-[var(--terminal-green)]' },
                                { label: 'Ask', value: formatCurrency(marketSnapshot.ask), color: 'text-[var(--terminal-red)]' },
                                { label: 'Spread', value: formatCurrency(marketSnapshot.spread), color: 'text-[var(--terminal-yellow)]' },
                                { label: 'Vol', value: formatNumber(marketSnapshot.dayVolume / 1000000, 1) + 'M', color: 'text-[var(--terminal-cyan)]' },
                            ].map((item) => (
                                <div key={item.label} className="text-center">
                                    <div className="text-[6px] font-mono text-[var(--terminal-dim)] uppercase">{item.label}</div>
                                    <div className={`text-[10px] font-mono font-bold ${item.color}`}>{item.value}</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Impact Preview + What-If (Moved here to utilize right column space) */}
                    {executionPreview && (
                        <div className="bg-terminal-gray/20 border border-terminal-gray/50 rounded overflow-hidden animate-in fade-in slide-in-from-top-2 duration-300">
                            <div className="bg-[var(--terminal-darker)] px-2 py-1 border-b border-terminal-gray/30 flex justify-between items-center">
                                <h4 className="text-[8px] font-mono text-terminal-dim uppercase font-bold tracking-widest">Impact Preview + What-If</h4>
                                <Activity size={10} className="text-terminal-yellow" />
                            </div>
                            
                            <div className="p-3 space-y-3">
                                <div className="grid grid-cols-4 gap-1 text-[10px] font-mono">
                                    <div className="text-center">
                                        <div className="text-terminal-dim uppercase text-[7px]">Fill</div>
                                        <div className="text-terminal-text font-bold">{formatCurrency(executionPreview.estimatedFillPrice)}</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-terminal-dim uppercase text-[7px]">Total</div>
                                        <div className="text-terminal-text font-bold">{formatCurrency(executionPreview.totalCost)}</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-terminal-dim uppercase text-[7px]">Fees</div>
                                        <div className="text-terminal-yellow">{formatCurrency(executionPreview.fees)}</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-terminal-dim uppercase text-[7px]">Pos</div>
                                        <div className="text-terminal-cyan">
                                            {executionPreview.positionChange >= 0 ? '+' : ''}{executionPreview.positionChange}
                                        </div>
                                    </div>
                                </div>

                                {preTradeImpact && (
                                    <div className="pt-2 border-t border-terminal-gray/30 grid grid-cols-2 gap-4">
                                        <div>
                                            <div className="text-[8px] font-mono text-terminal-dim uppercase mb-0.5">Beta Impact</div>
                                            <div className="flex items-center gap-2">
                                                <div className="text-xs font-mono font-black text-terminal-yellow">
                                                    {preTradeImpact.newBeta.toFixed(2)}
                                                </div>
                                                <div className={`text-[9px] font-mono ${preTradeImpact.betaDelta >= 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                                                    ({preTradeImpact.betaDelta >= 0 ? '+' : ''}{preTradeImpact.betaDelta.toFixed(3)})
                                                </div>
                                            </div>
                                            <div className="w-full h-1 bg-terminal-black mt-1 rounded-full overflow-hidden">
                                                <div className="h-full bg-terminal-yellow" style={{ width: `${Math.min(100, preTradeImpact.newBeta * 40)}%` }} />
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-[8px] font-mono text-terminal-dim uppercase mb-0.5">VaR Sens.</div>
                                            <div className="flex items-center gap-2">
                                                <div className="text-xs font-mono font-black text-terminal-cyan">
                                                    {preTradeImpact.varDeltaPercent >= 0 ? '+' : ''}{preTradeImpact.varDeltaPercent.toFixed(2)}%
                                                </div>
                                                <span className="text-[7px] font-mono text-terminal-dim">∆ risk</span>
                                            </div>
                                            <div className="w-full h-1 bg-terminal-black mt-1 rounded-full overflow-hidden">
                                                <div className="h-full bg-terminal-cyan" style={{ width: `${Math.abs(preTradeImpact.varDeltaPercent) * 10}%` }} />
                                            </div>
                                        </div>
                                    </div>
                                )}
                                
                                {intentMessage && (
                                    <p className="text-[9px] font-mono text-white/40 italic bg-white/5 py-1 px-2 rounded text-center">{intentMessage}</p>
                                )}
                            </div>
                        </div>
                    )}
                    
                    {/* Only show these when NOT in an active order flow for cleaner focused execution */}
                    {!showJournal && !orderLifecycle && (
                        <>
                            {/* Consolidated Trade Log Title badge */}
                            <div className="flex items-center gap-2 mb-1">
                                <Clock size={14} className="text-terminal-yellow" />
                                <span className="text-[10px] font-mono font-bold text-terminal-yellow uppercase tracking-widest">Execution Registry</span>
                            </div>
                        </>
                    )}

            {/* ================================================================
                10. ACTIVE ORDERS (If any exist)
            ================================================================ */}
            {activeOrders.filter(o => o.status !== 'CANCELLED').length > 0 && (
                <div className="bg-terminal-darker border border-terminal-gray rounded-lg p-3">
                    <h4 className="text-[9px] font-mono text-terminal-dim uppercase mb-2">Active Orders</h4>
                    <div className="space-y-1">
                        {activeOrders.filter(o => o.status !== 'CANCELLED').map((order) => (
                            <div key={order.id} className="flex items-center justify-between py-1.5 px-2 bg-terminal-black/50 rounded text-xs font-mono">
                                <div className="flex items-center gap-2">
                                    <span className={order.side === 'BUY' ? 'text-terminal-green font-bold' : 'text-terminal-red font-bold'}>
                                        {order.side}
                                    </span>
                                    <span className="text-terminal-text">{order.remainingQuantity}</span>
                                    <span className="text-terminal-dim">@</span>
                                    <span className="text-terminal-yellow">
                                        {order.limitPrice ? formatCurrency(order.limitPrice) : 'MKT'}
                                    </span>
                                </div>
                                <button
                                    onClick={() => handleCancelOrder(order.id)}
                                    className="px-1.5 py-0.5 text-[8px] font-mono font-bold text-terminal-red bg-terminal-red/10 border border-terminal-red/30 rounded hover:bg-terminal-red/20"
                                >
                                    CANCEL
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ================================================================
                11. LOCAL TRADE HISTORY
            ================================================================ */}
            {tradeHistory.length > 0 && (
                <div className="bg-terminal-darker border border-terminal-gray rounded-lg p-3">
                    <h4 className="text-[9px] font-mono text-terminal-dim uppercase mb-2">Recent Trades • {state.symbol}</h4>
                    <div className="space-y-1">
                        {tradeHistory.slice(0, 5).map((trade) => (
                            <div key={trade.id} className="flex items-center justify-between py-1 text-[10px] font-mono">
                                <span className="text-terminal-dim">{new Date(trade.timestamp).toLocaleDateString()}</span>
                                <span className={trade.side === 'BUY' ? 'text-terminal-green' : 'text-terminal-red'}>{trade.side}</span>
                                <span className="text-terminal-text">{trade.quantity}</span>
                                <span className="text-terminal-text">{formatCurrency(trade.fillPrice)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ================================================================
                CURRENT POSITION (Context)
            ================================================================ */}
            {currentPosition && (
                <div className="bg-terminal-darker border border-terminal-gray rounded-lg p-3">
                    <h4 className="text-[9px] font-mono text-terminal-dim uppercase mb-2">Current Position</h4>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                        <div className="flex justify-between">
                            <span className="text-terminal-dim">Shares</span>
                            <span className="text-terminal-text font-bold">{currentPosition.qty}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-terminal-dim">Avg Cost</span>
                            <span className="text-terminal-text">{formatCurrency(currentPosition.px)}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-terminal-dim">Mkt Value</span>
                            <span className="text-terminal-text">{formatCurrency(state.lastPrice * currentPosition.qty)}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-terminal-dim">P&L</span>
                            {(() => {
                                const pnl = (state.lastPrice - currentPosition.px) * currentPosition.qty;
                                const pnlPct = ((state.lastPrice - currentPosition.px) / currentPosition.px) * 100;
                                return (
                                    <span className={pnl >= 0 ? 'text-terminal-green font-bold' : 'text-terminal-red font-bold'}>
                                        {formatCurrency(pnl)} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%)
                                    </span>
                                );
                            })()}
                        </div>
                    </div>
                </div>
            )}
                </div>
            </div>
        </div>
    );
}
