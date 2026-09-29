/**
 * Execution Quality Overlay
 * 
 * Per tradefeature.md §20:
 * - Entry vs candle range analysis
 * - VWAP deviation calculation
 * - Slippage tracking
 * - Chased vs Patient tagging
 */

// =============================================================================
// TYPES
// =============================================================================

export interface ExecutionMetrics {
    tradeId: string;
    symbol: string;
    side: 'buy' | 'sell';
    
    // Candle analysis
    entryPrice: number;
    entryBarHigh: number;
    entryBarLow: number;
    candlePosition: number; // 0-1, where 0 = low, 1 = high
    candlePositionQuality: 'good' | 'average' | 'poor';
    
    // VWAP analysis
    vwapAtEntry: number;
    vwapDeviation: number; // percentage
    vwapQuality: 'premium' | 'neutral' | 'discount';
    
    // Slippage
    intendedPrice: number;
    actualFillPrice: number;
    slippage: number;
    slippagePercent: number;
    spread?: number;
    slippageVsSpread?: number;
    
    // Entry timing
    priceMoveSinceSignal: number; // percentage
    entryTiming: 'patient' | 'timely' | 'chased';
    
    // Overall score
    overallScore: number; // 0-100
    overallQuality: 'excellent' | 'good' | 'average' | 'poor';
    
    // PnL (independent from execution)
    pnl?: number;
    pnlPercent?: number;
}

export interface ExecutionSummary {
    totalTrades: number;
    avgScore: number;
    avgCandlePosition: number;
    avgVwapDeviation: number;
    avgSlippage: number;
    chasedCount: number;
    patientCount: number;
    goodExecutionCount: number;
    poorExecutionCount: number;
    correlationWithPnL: number | null;
}

interface TradeEntry {
    id: string;
    symbol: string;
    side: 'buy' | 'sell';
    entryPrice: number;
    intendedPrice: number;
    signalPrice?: number;
    timestamp: number;
}

interface BarData {
    high: number;
    low: number;
    close: number;
    vwap?: number;
}

// =============================================================================
// EXECUTION ANALYZER
// =============================================================================

export class ExecutionQualityAnalyzer {
    private metrics: ExecutionMetrics[] = [];

    /**
     * Analyze a single trade execution
     */
    analyzeExecution(
        trade: TradeEntry,
        entryBar: BarData,
        spread?: number
    ): ExecutionMetrics {
        const { id, symbol, side, entryPrice, intendedPrice, signalPrice } = trade;
        
        // Candle position analysis
        const barRange = entryBar.high - entryBar.low;
        const candlePosition = barRange > 0 
            ? (entryPrice - entryBar.low) / barRange 
            : 0.5;
        
        let candlePositionQuality: 'good' | 'average' | 'poor';
        if (side === 'buy') {
            // For buys, lower in bar is better
            candlePositionQuality = candlePosition < 0.3 ? 'good' : candlePosition < 0.7 ? 'average' : 'poor';
        } else {
            // For sells, higher in bar is better
            candlePositionQuality = candlePosition > 0.7 ? 'good' : candlePosition > 0.3 ? 'average' : 'poor';
        }

        // VWAP analysis
        const vwapAtEntry = entryBar.vwap || entryPrice;
        const vwapDeviation = vwapAtEntry > 0 
            ? ((entryPrice - vwapAtEntry) / vwapAtEntry) * 100 
            : 0;
        
        let vwapQuality: 'premium' | 'neutral' | 'discount';
        if (side === 'buy') {
            vwapQuality = vwapDeviation < -0.1 ? 'discount' : vwapDeviation > 0.1 ? 'premium' : 'neutral';
        } else {
            vwapQuality = vwapDeviation > 0.1 ? 'discount' : vwapDeviation < -0.1 ? 'premium' : 'neutral';
        }

        // Slippage analysis
        const slippage = Math.abs(entryPrice - intendedPrice);
        const slippagePercent = intendedPrice > 0 ? (slippage / intendedPrice) * 100 : 0;
        const slippageVsSpread = spread && spread > 0 ? slippage / spread : undefined;

        // Entry timing analysis
        const basePrice = signalPrice || intendedPrice;
        const priceMoveSinceSignal = basePrice > 0 
            ? ((entryPrice - basePrice) / basePrice) * 100 
            : 0;
        
        let entryTiming: 'patient' | 'timely' | 'chased';
        const absMove = Math.abs(priceMoveSinceSignal);
        if (absMove < 1) {
            entryTiming = 'patient';
        } else if (absMove < 3) {
            entryTiming = 'timely';
        } else {
            entryTiming = 'chased';
        }

        // Calculate overall score
        let score = 50; // Base score
        
        // Candle position contribution (0-25 points)
        if (candlePositionQuality === 'good') score += 25;
        else if (candlePositionQuality === 'average') score += 12;
        
        // VWAP contribution (0-25 points)
        if (vwapQuality === 'discount') score += 25;
        else if (vwapQuality === 'neutral') score += 12;
        
        // Slippage contribution (-10 to +15 points)
        if (slippagePercent < 0.05) score += 15;
        else if (slippagePercent < 0.1) score += 10;
        else if (slippagePercent > 0.5) score -= 10;
        
        // Entry timing contribution (-15 to +15 points)
        if (entryTiming === 'patient') score += 15;
        else if (entryTiming === 'chased') score -= 15;
        
        score = Math.max(0, Math.min(100, score));
        
        let overallQuality: 'excellent' | 'good' | 'average' | 'poor';
        if (score >= 80) overallQuality = 'excellent';
        else if (score >= 60) overallQuality = 'good';
        else if (score >= 40) overallQuality = 'average';
        else overallQuality = 'poor';

        const metrics: ExecutionMetrics = {
            tradeId: id,
            symbol,
            side,
            entryPrice,
            entryBarHigh: entryBar.high,
            entryBarLow: entryBar.low,
            candlePosition,
            candlePositionQuality,
            vwapAtEntry,
            vwapDeviation,
            vwapQuality,
            intendedPrice,
            actualFillPrice: entryPrice,
            slippage,
            slippagePercent,
            spread,
            slippageVsSpread,
            priceMoveSinceSignal,
            entryTiming,
            overallScore: score,
            overallQuality,
        };

        this.metrics.push(metrics);
        return metrics;
    }

    /**
     * Update PnL for a trade
     */
    updatePnL(tradeId: string, pnl: number, pnlPercent: number): void {
        const metric = this.metrics.find(m => m.tradeId === tradeId);
        if (metric) {
            metric.pnl = pnl;
            metric.pnlPercent = pnlPercent;
        }
    }

    /**
     * Get summary statistics
     */
    getSummary(): ExecutionSummary {
        if (this.metrics.length === 0) {
            return {
                totalTrades: 0,
                avgScore: 0,
                avgCandlePosition: 0,
                avgVwapDeviation: 0,
                avgSlippage: 0,
                chasedCount: 0,
                patientCount: 0,
                goodExecutionCount: 0,
                poorExecutionCount: 0,
                correlationWithPnL: null,
            };
        }

        const n = this.metrics.length;
        const avgScore = this.metrics.reduce((s, m) => s + m.overallScore, 0) / n;
        const avgCandlePosition = this.metrics.reduce((s, m) => s + m.candlePosition, 0) / n;
        const avgVwapDeviation = this.metrics.reduce((s, m) => s + Math.abs(m.vwapDeviation), 0) / n;
        const avgSlippage = this.metrics.reduce((s, m) => s + m.slippagePercent, 0) / n;
        const chasedCount = this.metrics.filter(m => m.entryTiming === 'chased').length;
        const patientCount = this.metrics.filter(m => m.entryTiming === 'patient').length;
        const goodExecutionCount = this.metrics.filter(m => m.overallQuality === 'good' || m.overallQuality === 'excellent').length;
        const poorExecutionCount = this.metrics.filter(m => m.overallQuality === 'poor').length;

        // Calculate correlation between execution score and PnL
        const tradesWithPnL = this.metrics.filter(m => m.pnlPercent !== undefined);
        let correlationWithPnL: number | null = null;
        if (tradesWithPnL.length >= 5) {
            correlationWithPnL = this.calculateCorrelation(
                tradesWithPnL.map(m => m.overallScore),
                tradesWithPnL.map(m => m.pnlPercent!)
            );
        }

        return {
            totalTrades: n,
            avgScore,
            avgCandlePosition,
            avgVwapDeviation,
            avgSlippage,
            chasedCount,
            patientCount,
            goodExecutionCount,
            poorExecutionCount,
            correlationWithPnL,
        };
    }

    /**
     * Get all metrics
     */
    getMetrics(): ExecutionMetrics[] {
        return [...this.metrics];
    }

    /**
     * Get metrics filtered by quality
     */
    getMetricsByQuality(quality: 'excellent' | 'good' | 'average' | 'poor'): ExecutionMetrics[] {
        return this.metrics.filter(m => m.overallQuality === quality);
    }

    /**
     * Export to CSV
     */
    exportCSV(): string {
        const headers = [
            'Trade ID', 'Symbol', 'Side', 'Entry Price', 'Candle Position', 
            'VWAP Deviation %', 'Slippage %', 'Entry Timing', 'Score', 'Quality', 'PnL %'
        ];
        
        const rows = this.metrics.map(m => [
            m.tradeId,
            m.symbol,
            m.side,
            m.entryPrice.toFixed(2),
            (m.candlePosition * 100).toFixed(1) + '%',
            m.vwapDeviation.toFixed(2) + '%',
            m.slippagePercent.toFixed(3) + '%',
            m.entryTiming,
            m.overallScore.toFixed(0),
            m.overallQuality,
            m.pnlPercent !== undefined ? m.pnlPercent.toFixed(2) + '%' : ''
        ]);

        return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    }

    /**
     * Clear all metrics
     */
    clear(): void {
        this.metrics = [];
    }

    /**
     * Calculate Pearson correlation
     */
    private calculateCorrelation(x: number[], y: number[]): number {
        const n = x.length;
        if (n === 0) return 0;

        const sumX = x.reduce((a, b) => a + b, 0);
        const sumY = y.reduce((a, b) => a + b, 0);
        const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
        const sumX2 = x.reduce((sum, xi) => sum + xi * xi, 0);
        const sumY2 = y.reduce((sum, yi) => sum + yi * yi, 0);

        const numerator = n * sumXY - sumX * sumY;
        const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));

        return denominator === 0 ? 0 : numerator / denominator;
    }
}

// =============================================================================
// SINGLETON
// =============================================================================

let analyzerInstance: ExecutionQualityAnalyzer | null = null;

export function getExecutionAnalyzer(): ExecutionQualityAnalyzer {
    if (!analyzerInstance) {
        analyzerInstance = new ExecutionQualityAnalyzer();
    }
    return analyzerInstance;
}
