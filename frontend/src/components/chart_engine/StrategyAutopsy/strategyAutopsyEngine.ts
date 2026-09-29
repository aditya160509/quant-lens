/**
 * Strategy Autopsy Mode
 * 
 * Per tradefeature.md §15:
 * - Entry timing tags (Early/Late/Timely)
 * - Exit analysis (Plan Followed/Exited Early)
 * - Market condition context
 * - Pattern frequency statistics
 */

// =============================================================================
// TYPES
// =============================================================================

export interface TradeAutopsy {
    tradeId: string;
    symbol: string;
    side: 'long' | 'short';
    
    // Entry analysis
    entry: {
        price: number;
        timestamp: number;
        timing: 'early' | 'timely' | 'late';
        optimalEntryPrice?: number;
        distanceFromOptimal?: number;
        marketCondition: 'trending' | 'ranging' | 'volatile' | 'quiet';
        triggerPattern?: string;
    };
    
    // Exit analysis
    exit: {
        price: number;
        timestamp: number;
        type: 'stop_loss' | 'take_profit' | 'manual' | 'trailing';
        planFollowed: boolean;
        planExit?: number;
        priceAtPlanExit?: number;
        leftOnTable?: number;
    };
    
    // Trade performance
    performance: {
        pnl: number;
        pnlPercent: number;
        maxDrawdown: number;
        maxRunup: number;
        rMultiple: number;
        holdingPeriod: number; // milliseconds
    };
    
    // Tags
    tags: string[];
    notes?: string;
    
    // Lessons learned
    lessons?: string[];
}

export interface PatternStatistics {
    pattern: string;
    count: number;
    winRate: number;
    avgPnlPercent: number;
    avgRMultiple: number;
    bestTrade: number;
    worstTrade: number;
}

export interface AutopsySummary {
    totalTrades: number;
    winRate: number;
    avgPnl: number;
    
    // Entry timing distribution
    earlyEntries: number;
    timelyEntries: number;
    lateEntries: number;
    
    // Exit analysis
    planFollowedRate: number;
    avgLeftOnTable: number;
    
    // Market condition performance
    trendingWinRate: number;
    rangingWinRate: number;
    
    // Pattern stats
    patterns: PatternStatistics[];
    
    // Common tags
    topTags: Array<{ tag: string; count: number }>;
}

// =============================================================================
// STRATEGY AUTOPSY ENGINE
// =============================================================================

export class StrategyAutopsyEngine {
    private autopsies: TradeAutopsy[] = [];
    private patterns: Map<string, PatternStatistics> = new Map();

    /**
     * Create autopsy for a closed trade
     */
    createAutopsy(
        trade: {
            id: string;
            symbol: string;
            side: 'long' | 'short';
            entryPrice: number;
            entryTimestamp: number;
            exitPrice: number;
            exitTimestamp: number;
            exitType: 'stop_loss' | 'take_profit' | 'manual' | 'trailing';
            plannedStopLoss?: number;
            plannedTakeProfit?: number;
            riskPerShare?: number;
        },
        marketData: {
            priceAtSignal?: number;
            optimalEntry?: number;
            highDuringTrade: number;
            lowDuringTrade: number;
            trend?: 'trending' | 'ranging' | 'volatile' | 'quiet';
            pattern?: string;
        }
    ): TradeAutopsy {
        const {
            id, symbol, side, entryPrice, entryTimestamp,
            exitPrice, exitTimestamp, exitType, plannedStopLoss,
            plannedTakeProfit, riskPerShare
        } = trade;

        const { priceAtSignal, optimalEntry, highDuringTrade, lowDuringTrade, trend, pattern } = marketData;

        // Calculate entry timing
        let entryTiming: 'early' | 'timely' | 'late' = 'timely';
        let distanceFromOptimal: number | undefined;
        if (optimalEntry) {
            const diff = side === 'long' 
                ? (entryPrice - optimalEntry) / optimalEntry 
                : (optimalEntry - entryPrice) / optimalEntry;
            distanceFromOptimal = diff * 100;
            
            if (diff < -0.5) entryTiming = 'early';
            else if (diff > 1) entryTiming = 'late';
        } else if (priceAtSignal) {
            const moveFromSignal = Math.abs(entryPrice - priceAtSignal) / priceAtSignal * 100;
            if (moveFromSignal > 1.5) entryTiming = 'late';
            else if (moveFromSignal < 0.3) entryTiming = 'timely';
        }

        // Calculate performance metrics
        const pnl = side === 'long' 
            ? exitPrice - entryPrice 
            : entryPrice - exitPrice;
        const pnlPercent = (pnl / entryPrice) * 100;
        
        const maxRunup = side === 'long'
            ? highDuringTrade - entryPrice
            : entryPrice - lowDuringTrade;
        const maxDrawdown = side === 'long'
            ? entryPrice - lowDuringTrade
            : highDuringTrade - entryPrice;
        
        const risk = riskPerShare || Math.abs((plannedStopLoss || entryPrice * 0.98) - entryPrice);
        const rMultiple = risk > 0 ? pnl / risk : 0;

        // Exit analysis
        let planFollowed = false;
        let leftOnTable = 0;
        let planExit: number | undefined;
        let priceAtPlanExit: number | undefined;

        if (exitType === 'stop_loss' && plannedStopLoss) {
            planFollowed = Math.abs(exitPrice - plannedStopLoss) < plannedStopLoss * 0.01;
            planExit = plannedStopLoss;
        } else if (exitType === 'take_profit' && plannedTakeProfit) {
            planFollowed = Math.abs(exitPrice - plannedTakeProfit) < plannedTakeProfit * 0.01;
            planExit = plannedTakeProfit;
            
            // Calculate how much was left on table
            const potential = side === 'long' ? highDuringTrade : lowDuringTrade;
            const actualExit = exitPrice;
            leftOnTable = side === 'long' 
                ? potential - actualExit 
                : actualExit - potential;
        }

        // Generate tags
        const tags: string[] = [];
        tags.push(pnl >= 0 ? 'winner' : 'loser');
        tags.push(entryTiming);
        tags.push(exitType);
        if (trend) tags.push(trend);
        if (pattern) tags.push(pattern);
        if (planFollowed) tags.push('plan_followed');
        if (rMultiple >= 2) tags.push('2R+');
        if (rMultiple >= 3) tags.push('3R+');
        if (maxDrawdown > risk) tags.push('underwater');

        const autopsy: TradeAutopsy = {
            tradeId: id,
            symbol,
            side,
            entry: {
                price: entryPrice,
                timestamp: entryTimestamp,
                timing: entryTiming,
                optimalEntryPrice: optimalEntry,
                distanceFromOptimal,
                marketCondition: trend || 'ranging',
                triggerPattern: pattern,
            },
            exit: {
                price: exitPrice,
                timestamp: exitTimestamp,
                type: exitType,
                planFollowed,
                planExit,
                priceAtPlanExit,
                leftOnTable: leftOnTable > 0 ? leftOnTable : undefined,
            },
            performance: {
                pnl,
                pnlPercent,
                maxDrawdown,
                maxRunup,
                rMultiple,
                holdingPeriod: exitTimestamp - entryTimestamp,
            },
            tags,
        };

        this.autopsies.push(autopsy);
        this.updatePatternStats(autopsy);

        return autopsy;
    }

    /**
     * Update pattern statistics
     */
    private updatePatternStats(autopsy: TradeAutopsy): void {
        const pattern = autopsy.entry.triggerPattern;
        if (!pattern) return;

        const existing = this.patterns.get(pattern) || {
            pattern,
            count: 0,
            winRate: 0,
            avgPnlPercent: 0,
            avgRMultiple: 0,
            bestTrade: -Infinity,
            worstTrade: Infinity,
        };

        const patternTrades = this.autopsies.filter(a => a.entry.triggerPattern === pattern);
        const wins = patternTrades.filter(t => t.performance.pnl >= 0).length;
        
        this.patterns.set(pattern, {
            pattern,
            count: patternTrades.length,
            winRate: (wins / patternTrades.length) * 100,
            avgPnlPercent: patternTrades.reduce((s, t) => s + t.performance.pnlPercent, 0) / patternTrades.length,
            avgRMultiple: patternTrades.reduce((s, t) => s + t.performance.rMultiple, 0) / patternTrades.length,
            bestTrade: Math.max(...patternTrades.map(t => t.performance.pnlPercent)),
            worstTrade: Math.min(...patternTrades.map(t => t.performance.pnlPercent)),
        });
    }

    /**
     * Get summary statistics
     */
    getSummary(): AutopsySummary {
        const n = this.autopsies.length;
        if (n === 0) {
            return {
                totalTrades: 0,
                winRate: 0,
                avgPnl: 0,
                earlyEntries: 0,
                timelyEntries: 0,
                lateEntries: 0,
                planFollowedRate: 0,
                avgLeftOnTable: 0,
                trendingWinRate: 0,
                rangingWinRate: 0,
                patterns: [],
                topTags: [],
            };
        }

        const wins = this.autopsies.filter(a => a.performance.pnl >= 0).length;
        const earlyEntries = this.autopsies.filter(a => a.entry.timing === 'early').length;
        const timelyEntries = this.autopsies.filter(a => a.entry.timing === 'timely').length;
        const lateEntries = this.autopsies.filter(a => a.entry.timing === 'late').length;
        
        const planFollowed = this.autopsies.filter(a => a.exit.planFollowed).length;
        const tradesWithLeftOnTable = this.autopsies.filter(a => a.exit.leftOnTable !== undefined);
        const avgLeftOnTable = tradesWithLeftOnTable.length > 0
            ? tradesWithLeftOnTable.reduce((s, a) => s + (a.exit.leftOnTable || 0), 0) / tradesWithLeftOnTable.length
            : 0;

        const trendingTrades = this.autopsies.filter(a => a.entry.marketCondition === 'trending');
        const rangingTrades = this.autopsies.filter(a => a.entry.marketCondition === 'ranging');

        // Count tags
        const tagCounts = new Map<string, number>();
        for (const autopsy of this.autopsies) {
            for (const tag of autopsy.tags) {
                tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
            }
        }
        const topTags = Array.from(tagCounts.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([tag, count]) => ({ tag, count }));

        return {
            totalTrades: n,
            winRate: (wins / n) * 100,
            avgPnl: this.autopsies.reduce((s, a) => s + a.performance.pnl, 0) / n,
            earlyEntries,
            timelyEntries,
            lateEntries,
            planFollowedRate: (planFollowed / n) * 100,
            avgLeftOnTable,
            trendingWinRate: trendingTrades.length > 0
                ? (trendingTrades.filter(t => t.performance.pnl >= 0).length / trendingTrades.length) * 100
                : 0,
            rangingWinRate: rangingTrades.length > 0
                ? (rangingTrades.filter(t => t.performance.pnl >= 0).length / rangingTrades.length) * 100
                : 0,
            patterns: Array.from(this.patterns.values()),
            topTags,
        };
    }

    /**
     * Get all autopsies
     */
    getAutopsies(): TradeAutopsy[] {
        return [...this.autopsies];
    }

    /**
     * Add notes/lessons to an autopsy
     */
    addNotes(tradeId: string, notes: string, lessons?: string[]): void {
        const autopsy = this.autopsies.find(a => a.tradeId === tradeId);
        if (autopsy) {
            autopsy.notes = notes;
            if (lessons) autopsy.lessons = lessons;
        }
    }

    /**
     * Export to CSV
     */
    exportCSV(): string {
        const headers = [
            'Trade ID', 'Symbol', 'Side', 'Entry', 'Exit', 'PnL', 'PnL%', 
            'R-Multiple', 'Entry Timing', 'Exit Type', 'Plan Followed',
            'Market Condition', 'Pattern', 'Tags'
        ];
        
        const rows = this.autopsies.map(a => [
            a.tradeId,
            a.symbol,
            a.side,
            a.entry.price.toFixed(2),
            a.exit.price.toFixed(2),
            a.performance.pnl.toFixed(2),
            a.performance.pnlPercent.toFixed(2) + '%',
            a.performance.rMultiple.toFixed(2),
            a.entry.timing,
            a.exit.type,
            a.exit.planFollowed ? 'Yes' : 'No',
            a.entry.marketCondition,
            a.entry.triggerPattern || '',
            a.tags.join('; ')
        ]);

        return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    }

    /**
     * Clear all data
     */
    clear(): void {
        this.autopsies = [];
        this.patterns.clear();
    }
}

// =============================================================================
// SINGLETON
// =============================================================================

let autopsyInstance: StrategyAutopsyEngine | null = null;

export function getStrategyAutopsyEngine(): StrategyAutopsyEngine {
    if (!autopsyInstance) {
        autopsyInstance = new StrategyAutopsyEngine();
    }
    return autopsyInstance;
}
