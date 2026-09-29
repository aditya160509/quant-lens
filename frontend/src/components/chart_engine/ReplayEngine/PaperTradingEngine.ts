/**
 * Paper Trading Engine
 * Simulated order execution for replay mode with position tracking and P&L
 */

import type { OHLCVBar } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stopLimit';
export type OrderStatus = 'pending' | 'filled' | 'canceled' | 'rejected';
export type PositionSide = 'long' | 'short' | 'flat';

export interface PaperOrder {
    id: string;
    symbol: string;
    side: OrderSide;
    type: OrderType;
    quantity: number;
    price?: number;        // For limit orders
    stopPrice?: number;    // For stop orders
    status: OrderStatus;
    filledPrice?: number;
    filledAt?: number;
    createdAt: number;
    fee: number;
}

export interface PaperPosition {
    symbol: string;
    side: PositionSide;
    quantity: number;
    entryPrice: number;
    entryTime: number;
    currentPrice: number;
    unrealizedPnL: number;
    unrealizedPnLPercent: number;
}

export interface PaperTrade {
    id: string;
    symbol: string;
    side: OrderSide;
    entryPrice: number;
    entryTime: number;
    exitPrice: number;
    exitTime: number;
    quantity: number;
    pnl: number;
    pnlPercent: number;
    fees: number;
    holdingPeriod: number;  // in ms
    maxDrawdown: number;
    maxProfit: number;
}

export interface PaperTradingState {
    cash: number;
    initialCash: number;
    position: PaperPosition | null;
    openOrders: PaperOrder[];
    trades: PaperTrade[];
    equity: number;
    maxEquity: number;
    maxDrawdown: number;
    currentBar: OHLCVBar | null;
}

export interface PaperTradingStats {
    totalTrades: number;
    winningTrades: number;
    losingTrades: number;
    winRate: number;
    totalPnL: number;
    totalPnLPercent: number;
    avgWin: number;
    avgLoss: number;
    profitFactor: number;
    sharpeRatio: number;
    maxDrawdown: number;
    maxDrawdownPercent: number;
    avgHoldingPeriod: number;
    largestWin: number;
    largestLoss: number;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const DEFAULT_FEE_RATE = 0.001; // 0.1% per trade
const DEFAULT_SLIPPAGE = 0.0005; // 0.05% slippage

// =============================================================================
// PAPER TRADING ENGINE CLASS
// =============================================================================

export class PaperTradingEngine {
    private state: PaperTradingState;
    private feeRate: number;
    private slippage: number;
    private equityHistory: { timestamp: number; equity: number }[];
    private positionPnLHistory: { timestamp: number; unrealizedPnL: number }[];

    constructor(initialCash: number = 100000, feeRate: number = DEFAULT_FEE_RATE) {
        this.feeRate = feeRate;
        this.slippage = DEFAULT_SLIPPAGE;
        this.equityHistory = [];
        this.positionPnLHistory = [];
        
        this.state = {
            cash: initialCash,
            initialCash: initialCash,
            position: null,
            openOrders: [],
            trades: [],
            equity: initialCash,
            maxEquity: initialCash,
            maxDrawdown: 0,
            currentBar: null,
        };
    }

    // ==========================================================================
    // PUBLIC API
    // ==========================================================================

    /**
     * Update with new bar data (called on each replay tick)
     */
    tick(bar: OHLCVBar): void {
        this.state.currentBar = bar;
        this.updatePosition(bar);
        this.processOpenOrders(bar);
        this.updateEquity();
        this.recordEquityHistory(bar.timestamp);
    }

    /**
     * Place a market order
     */
    marketOrder(side: OrderSide, quantity: number): PaperOrder | null {
        if (!this.state.currentBar) return null;
        
        const order = this.createOrder(side, 'market', quantity);
        return this.executeMarketOrder(order);
    }

    /**
     * Place a buy order
     */
    buy(quantity?: number): PaperOrder | null {
        const qty = quantity || this.calculateMaxQuantity('buy');
        if (qty <= 0) return null;
        return this.marketOrder('buy', qty);
    }

    /**
     * Place a sell order
     */
    sell(quantity?: number): PaperOrder | null {
        const qty = quantity || this.state.position?.quantity || 0;
        if (qty <= 0) return null;
        return this.marketOrder('sell', qty);
    }

    /**
     * Close current position
     */
    closePosition(): PaperTrade | null {
        if (!this.state.position || this.state.position.side === 'flat') {
            return null;
        }

        const position = this.state.position;
        const closeOrder = this.marketOrder(
            position.side === 'long' ? 'sell' : 'buy',
            position.quantity
        );

        if (closeOrder?.status === 'filled') {
            return this.state.trades[this.state.trades.length - 1];
        }

        return null;
    }

    /**
     * Place a limit order
     */
    limitOrder(side: OrderSide, quantity: number, price: number): PaperOrder {
        const order = this.createOrder(side, 'limit', quantity, price);
        this.state.openOrders.push(order);
        return order;
    }

    /**
     * Place a stop order
     */
    stopOrder(side: OrderSide, quantity: number, stopPrice: number): PaperOrder {
        const order = this.createOrder(side, 'stop', quantity, undefined, stopPrice);
        this.state.openOrders.push(order);
        return order;
    }

    /**
     * Cancel an open order
     */
    cancelOrder(orderId: string): boolean {
        const index = this.state.openOrders.findIndex(o => o.id === orderId);
        if (index === -1) return false;
        
        this.state.openOrders[index].status = 'canceled';
        this.state.openOrders.splice(index, 1);
        return true;
    }

    /**
     * Cancel all open orders
     */
    cancelAllOrders(): void {
        this.state.openOrders.forEach(o => o.status = 'canceled');
        this.state.openOrders = [];
    }

    /**
     * Reset the engine to initial state
     */
    reset(initialCash?: number): void {
        const cash = initialCash || this.state.initialCash;
        this.state = {
            cash,
            initialCash: cash,
            position: null,
            openOrders: [],
            trades: [],
            equity: cash,
            maxEquity: cash,
            maxDrawdown: 0,
            currentBar: null,
        };
        this.equityHistory = [];
        this.positionPnLHistory = [];
    }

    /**
     * Get current state
     */
    getState(): PaperTradingState {
        return { ...this.state };
    }

    /**
     * Get trading statistics
     */
    getStats(): PaperTradingStats {
        const trades = this.state.trades;
        const winningTrades = trades.filter(t => t.pnl > 0);
        const losingTrades = trades.filter(t => t.pnl < 0);

        const totalPnL = trades.reduce((sum, t) => sum + t.pnl, 0);
        const grossProfit = winningTrades.reduce((sum, t) => sum + t.pnl, 0);
        const grossLoss = Math.abs(losingTrades.reduce((sum, t) => sum + t.pnl, 0));

        const avgWin = winningTrades.length > 0
            ? grossProfit / winningTrades.length
            : 0;
        const avgLoss = losingTrades.length > 0
            ? grossLoss / losingTrades.length
            : 0;

        const returns = this.calculateReturns();
        const sharpeRatio = this.calculateSharpeRatio(returns);

        return {
            totalTrades: trades.length,
            winningTrades: winningTrades.length,
            losingTrades: losingTrades.length,
            winRate: trades.length > 0 ? (winningTrades.length / trades.length) * 100 : 0,
            totalPnL,
            totalPnLPercent: (totalPnL / this.state.initialCash) * 100,
            avgWin,
            avgLoss,
            profitFactor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : 0,
            sharpeRatio,
            maxDrawdown: this.state.maxDrawdown,
            maxDrawdownPercent: this.state.maxEquity > 0 
                ? (this.state.maxDrawdown / this.state.maxEquity) * 100 
                : 0,
            avgHoldingPeriod: trades.length > 0
                ? trades.reduce((sum, t) => sum + t.holdingPeriod, 0) / trades.length
                : 0,
            largestWin: winningTrades.length > 0 ? Math.max(...winningTrades.map(t => t.pnl)) : 0,
            largestLoss: losingTrades.length > 0 ? Math.min(...losingTrades.map(t => t.pnl)) : 0,
        };
    }

    /**
     * Get equity curve data
     */
    getEquityCurve(): { timestamp: number; equity: number }[] {
        return [...this.equityHistory];
    }

    // ==========================================================================
    // PRIVATE METHODS
    // ==========================================================================

    private createOrder(
        side: OrderSide,
        type: OrderType,
        quantity: number,
        price?: number,
        stopPrice?: number
    ): PaperOrder {
        return {
            id: `order_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            symbol: this.state.currentBar?.timestamp ? 'SYMBOL' : '',
            side,
            type,
            quantity,
            price,
            stopPrice,
            status: 'pending',
            createdAt: Date.now(),
            fee: 0,
        };
    }

    private executeMarketOrder(order: PaperOrder): PaperOrder | null {
        if (!this.state.currentBar) return null;

        const bar = this.state.currentBar;
        
        // Apply slippage
        const slippageMultiplier = order.side === 'buy' 
            ? (1 + this.slippage) 
            : (1 - this.slippage);
        const executionPrice = bar.close * slippageMultiplier;

        // Calculate fee
        const orderValue = executionPrice * order.quantity;
        const fee = orderValue * this.feeRate;

        // Check if we have enough cash for buy
        if (order.side === 'buy' && orderValue + fee > this.state.cash) {
            order.status = 'rejected';
            return order;
        }

        // Execute the order
        order.status = 'filled';
        order.filledPrice = executionPrice;
        order.filledAt = bar.timestamp;
        order.fee = fee;

        // Update position
        this.updatePositionAfterFill(order);

        return order;
    }

    private updatePositionAfterFill(order: PaperOrder): void {
        if (!order.filledPrice) return;

        const position = this.state.position;

        if (order.side === 'buy') {
            this.state.cash -= (order.filledPrice * order.quantity) + order.fee;

            if (!position || position.side === 'flat') {
                // Open new long position
                this.state.position = {
                    symbol: order.symbol,
                    side: 'long',
                    quantity: order.quantity,
                    entryPrice: order.filledPrice,
                    entryTime: order.filledAt!,
                    currentPrice: order.filledPrice,
                    unrealizedPnL: 0,
                    unrealizedPnLPercent: 0,
                };
            } else if (position.side === 'long') {
                // Add to long position
                const totalQty = position.quantity + order.quantity;
                const avgPrice = (position.entryPrice * position.quantity + order.filledPrice * order.quantity) / totalQty;
                position.quantity = totalQty;
                position.entryPrice = avgPrice;
            } else {
                // Covering short position
                this.handlePositionClose(position, order);
            }
        } else {
            // Sell
            this.state.cash += (order.filledPrice * order.quantity) - order.fee;

            if (!position || position.side === 'flat') {
                // Open new short position
                this.state.position = {
                    symbol: order.symbol,
                    side: 'short',
                    quantity: order.quantity,
                    entryPrice: order.filledPrice,
                    entryTime: order.filledAt!,
                    currentPrice: order.filledPrice,
                    unrealizedPnL: 0,
                    unrealizedPnLPercent: 0,
                };
            } else if (position.side === 'long') {
                // Closing long position
                this.handlePositionClose(position, order);
            } else {
                // Add to short position
                const totalQty = position.quantity + order.quantity;
                const avgPrice = (position.entryPrice * position.quantity + order.filledPrice * order.quantity) / totalQty;
                position.quantity = totalQty;
                position.entryPrice = avgPrice;
            }
        }
    }

    private handlePositionClose(position: PaperPosition, order: PaperOrder): void {
        const closeQty = Math.min(position.quantity, order.quantity);
        const exitPrice = order.filledPrice!;
        
        // Calculate P&L
        let pnl: number;
        if (position.side === 'long') {
            pnl = (exitPrice - position.entryPrice) * closeQty;
        } else {
            pnl = (position.entryPrice - exitPrice) * closeQty;
        }
        pnl -= order.fee;

        // Record trade
        const trade: PaperTrade = {
            id: `trade_${Date.now()}`,
            symbol: position.symbol,
            side: position.side === 'long' ? 'buy' : 'sell',
            entryPrice: position.entryPrice,
            entryTime: position.entryTime,
            exitPrice,
            exitTime: order.filledAt!,
            quantity: closeQty,
            pnl,
            pnlPercent: (pnl / (position.entryPrice * closeQty)) * 100,
            fees: order.fee,
            holdingPeriod: order.filledAt! - position.entryTime,
            maxDrawdown: 0, // Would need to track during position
            maxProfit: 0,
        };
        this.state.trades.push(trade);

        // Update or close position
        if (closeQty >= position.quantity) {
            this.state.position = null;
        } else {
            position.quantity -= closeQty;
        }
    }

    private updatePosition(bar: OHLCVBar): void {
        if (!this.state.position || this.state.position.side === 'flat') return;

        const position = this.state.position;
        position.currentPrice = bar.close;

        if (position.side === 'long') {
            position.unrealizedPnL = (bar.close - position.entryPrice) * position.quantity;
        } else {
            position.unrealizedPnL = (position.entryPrice - bar.close) * position.quantity;
        }

        position.unrealizedPnLPercent = (position.unrealizedPnL / (position.entryPrice * position.quantity)) * 100;

        this.positionPnLHistory.push({
            timestamp: bar.timestamp,
            unrealizedPnL: position.unrealizedPnL,
        });
    }

    private processOpenOrders(bar: OHLCVBar): void {
        const ordersToRemove: string[] = [];

        for (const order of this.state.openOrders) {
            if (order.type === 'limit') {
                if (order.side === 'buy' && bar.low <= order.price!) {
                    order.filledPrice = order.price;
                    order.filledAt = bar.timestamp;
                    order.fee = order.price! * order.quantity * this.feeRate;
                    order.status = 'filled';
                    this.updatePositionAfterFill(order);
                    ordersToRemove.push(order.id);
                } else if (order.side === 'sell' && bar.high >= order.price!) {
                    order.filledPrice = order.price;
                    order.filledAt = bar.timestamp;
                    order.fee = order.price! * order.quantity * this.feeRate;
                    order.status = 'filled';
                    this.updatePositionAfterFill(order);
                    ordersToRemove.push(order.id);
                }
            } else if (order.type === 'stop') {
                if (order.side === 'sell' && bar.low <= order.stopPrice!) {
                    order.filledPrice = order.stopPrice! * (1 - this.slippage);
                    order.filledAt = bar.timestamp;
                    order.fee = order.filledPrice * order.quantity * this.feeRate;
                    order.status = 'filled';
                    this.updatePositionAfterFill(order);
                    ordersToRemove.push(order.id);
                } else if (order.side === 'buy' && bar.high >= order.stopPrice!) {
                    order.filledPrice = order.stopPrice! * (1 + this.slippage);
                    order.filledAt = bar.timestamp;
                    order.fee = order.filledPrice * order.quantity * this.feeRate;
                    order.status = 'filled';
                    this.updatePositionAfterFill(order);
                    ordersToRemove.push(order.id);
                }
            }
        }

        this.state.openOrders = this.state.openOrders.filter(o => !ordersToRemove.includes(o.id));
    }

    private updateEquity(): void {
        const positionValue = this.state.position
            ? this.state.position.currentPrice * this.state.position.quantity
            : 0;

        this.state.equity = this.state.cash + positionValue;

        if (this.state.equity > this.state.maxEquity) {
            this.state.maxEquity = this.state.equity;
        }

        const drawdown = this.state.maxEquity - this.state.equity;
        if (drawdown > this.state.maxDrawdown) {
            this.state.maxDrawdown = drawdown;
        }
    }

    private recordEquityHistory(timestamp: number): void {
        this.equityHistory.push({
            timestamp,
            equity: this.state.equity,
        });
    }

    private calculateMaxQuantity(side: OrderSide): number {
        if (!this.state.currentBar) return 0;
        
        if (side === 'buy') {
            const maxValue = this.state.cash * 0.95; // Keep 5% buffer
            return Math.floor(maxValue / this.state.currentBar.close);
        }
        
        return this.state.position?.quantity || 0;
    }

    private calculateReturns(): number[] {
        if (this.equityHistory.length < 2) return [];
        
        const returns: number[] = [];
        for (let i = 1; i < this.equityHistory.length; i++) {
            const ret = (this.equityHistory[i].equity - this.equityHistory[i - 1].equity) / this.equityHistory[i - 1].equity;
            returns.push(ret);
        }
        return returns;
    }

    private calculateSharpeRatio(returns: number[]): number {
        if (returns.length < 2) return 0;
        
        const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length;
        const stdDev = Math.sqrt(variance);
        
        if (stdDev === 0) return 0;
        
        // Annualize (assuming daily returns)
        return (avgReturn * 252) / (stdDev * Math.sqrt(252));
    }
}

// =============================================================================
// SINGLETON FACTORY
// =============================================================================

let engineInstance: PaperTradingEngine | null = null;

export function getPaperTradingEngine(initialCash?: number): PaperTradingEngine {
    if (!engineInstance) {
        engineInstance = new PaperTradingEngine(initialCash);
    }
    return engineInstance;
}

export function resetPaperTradingEngine(initialCash?: number): PaperTradingEngine {
    engineInstance = new PaperTradingEngine(initialCash);
    return engineInstance;
}
