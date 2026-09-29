/**
 * Intelligent Replay Engine
 * 
 * Per tradefeature.md §14:
 * - Event detectors (crossovers, structure breaks, volume spikes)
 * - Auto-pause on events
 * - Learning mode prompts
 */

import type { OHLCVBar, IndicatorOutput } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export type ReplayEventType = 
    | 'indicator_crossover'
    | 'structure_break'
    | 'vwap_interaction'
    | 'volume_spike'
    | 'session_high_low'
    | 'swing_point';

export interface ReplayEvent {
    id: string;
    type: ReplayEventType;
    timestamp: number;
    barIndex: number;
    description: string;
    price: number;
    severity: 'high' | 'medium' | 'low';
    details: Record<string, unknown>;
}

export interface EventDetectorConfig {
    indicatorCrossover: {
        enabled: boolean;
        pairs: Array<{ fast: string; slow: string }>;
    };
    structureBreak: {
        enabled: boolean;
        lookbackPeriod: number;
    };
    vwapInteraction: {
        enabled: boolean;
        touchThreshold: number; // percentage
    };
    volumeSpike: {
        enabled: boolean;
        multiplier: number;
    };
    sessionHighLow: {
        enabled: boolean;
    };
}

export interface LearningPrompt {
    eventId: string;
    question: string;
    options: Array<{ id: string; label: string }>;
    correctAnswer?: string; // Not revealed until after selection
}

// =============================================================================
// DEFAULT CONFIG
// =============================================================================

export const DEFAULT_EVENT_CONFIG: EventDetectorConfig = {
    indicatorCrossover: {
        enabled: true,
        pairs: [
            { fast: 'ema_9', slow: 'ema_21' },
            { fast: 'macd_line', slow: 'macd_signal' },
        ],
    },
    structureBreak: {
        enabled: true,
        lookbackPeriod: 20,
    },
    vwapInteraction: {
        enabled: true,
        touchThreshold: 0.1, // 0.1%
    },
    volumeSpike: {
        enabled: true,
        multiplier: 2.0,
    },
    sessionHighLow: {
        enabled: true,
    },
};

// =============================================================================
// INTELLIGENT REPLAY ENGINE
// =============================================================================

export class IntelligentReplayEngine {
    private config: EventDetectorConfig;
    private events: ReplayEvent[] = [];
    private currentBarIndex: number = 0;
    private sessionHigh: number = 0;
    private sessionLow: number = Infinity;
    private lastSwingHigh: number | null = null;
    private lastSwingLow: number | null = null;

    constructor(config: Partial<EventDetectorConfig> = {}) {
        this.config = { ...DEFAULT_EVENT_CONFIG, ...config };
    }

    /**
     * Process a single bar and detect events
     */
    processBar(
        bar: OHLCVBar,
        barIndex: number,
        allBars: OHLCVBar[],
        indicatorOutputs: Map<string, IndicatorOutput>
    ): ReplayEvent[] {
        this.currentBarIndex = barIndex;
        const newEvents: ReplayEvent[] = [];

        // Session high/low tracking
        if (bar.high > this.sessionHigh) {
            this.sessionHigh = bar.high;
            if (this.config.sessionHighLow.enabled) {
                newEvents.push(this.createEvent(
                    'session_high_low',
                    bar.timestamp,
                    barIndex,
                    'New Session High',
                    bar.high,
                    'high',
                    { type: 'high' }
                ));
            }
        }
        if (bar.low < this.sessionLow) {
            this.sessionLow = bar.low;
            if (this.config.sessionHighLow.enabled) {
                newEvents.push(this.createEvent(
                    'session_high_low',
                    bar.timestamp,
                    barIndex,
                    'New Session Low',
                    bar.low,
                    'high',
                    { type: 'low' }
                ));
            }
        }

        // Indicator crossovers
        if (this.config.indicatorCrossover.enabled && barIndex > 0) {
            for (const pair of this.config.indicatorCrossover.pairs) {
                const crossEvent = this.detectCrossover(
                    pair.fast,
                    pair.slow,
                    bar,
                    barIndex,
                    indicatorOutputs
                );
                if (crossEvent) newEvents.push(crossEvent);
            }
        }

        // Volume spike
        if (this.config.volumeSpike.enabled && barIndex >= 20) {
            const spikeEvent = this.detectVolumeSpike(bar, barIndex, allBars);
            if (spikeEvent) newEvents.push(spikeEvent);
        }

        // VWAP interaction
        if (this.config.vwapInteraction.enabled) {
            const vwapEvent = this.detectVwapInteraction(bar, barIndex, indicatorOutputs);
            if (vwapEvent) newEvents.push(vwapEvent);
        }

        // Structure break
        if (this.config.structureBreak.enabled && barIndex >= this.config.structureBreak.lookbackPeriod) {
            const breakEvent = this.detectStructureBreak(bar, barIndex, allBars);
            if (breakEvent) newEvents.push(breakEvent);
        }

        this.events.push(...newEvents);
        return newEvents;
    }

    /**
     * Detect indicator crossover
     */
    private detectCrossover(
        fastId: string,
        slowId: string,
        bar: OHLCVBar,
        barIndex: number,
        indicatorOutputs: Map<string, IndicatorOutput>
    ): ReplayEvent | null {
        const fastOutput = indicatorOutputs.get(fastId);
        const slowOutput = indicatorOutputs.get(slowId);

        if (!fastOutput?.series || !slowOutput?.series) return null;
        if (barIndex < 1 || barIndex >= fastOutput.series.length || barIndex >= slowOutput.series.length) {
            return null;
        }

        const fastCurrent = fastOutput.series[barIndex]?.value;
        const fastPrev = fastOutput.series[barIndex - 1]?.value;
        const slowCurrent = slowOutput.series[barIndex]?.value;
        const slowPrev = slowOutput.series[barIndex - 1]?.value;

        if (fastCurrent === undefined || fastPrev === undefined || 
            slowCurrent === undefined || slowPrev === undefined) {
            return null;
        }

        // Bullish crossover
        if (fastPrev <= slowPrev && fastCurrent > slowCurrent) {
            return this.createEvent(
                'indicator_crossover',
                bar.timestamp,
                barIndex,
                `Bullish Crossover: ${fastId} crossed above ${slowId}`,
                bar.close,
                'high',
                { fast: fastId, slow: slowId, direction: 'bullish' }
            );
        }

        // Bearish crossover
        if (fastPrev >= slowPrev && fastCurrent < slowCurrent) {
            return this.createEvent(
                'indicator_crossover',
                bar.timestamp,
                barIndex,
                `Bearish Crossover: ${fastId} crossed below ${slowId}`,
                bar.close,
                'high',
                { fast: fastId, slow: slowId, direction: 'bearish' }
            );
        }

        return null;
    }

    /**
     * Detect volume spike
     */
    private detectVolumeSpike(
        bar: OHLCVBar,
        barIndex: number,
        allBars: OHLCVBar[]
    ): ReplayEvent | null {
        const lookback = Math.min(20, barIndex);
        const recentVolumes = allBars.slice(barIndex - lookback, barIndex).map(b => b.volume);
        const avgVolume = recentVolumes.reduce((a, b) => a + b, 0) / recentVolumes.length;
        
        const ratio = avgVolume > 0 ? bar.volume / avgVolume : 0;
        
        if (ratio >= this.config.volumeSpike.multiplier) {
            return this.createEvent(
                'volume_spike',
                bar.timestamp,
                barIndex,
                `Volume Spike: ${ratio.toFixed(1)}x average`,
                bar.close,
                'high',
                { ratio, avgVolume, currentVolume: bar.volume }
            );
        }

        return null;
    }

    /**
     * Detect VWAP interaction
     */
    private detectVwapInteraction(
        bar: OHLCVBar,
        barIndex: number,
        indicatorOutputs: Map<string, IndicatorOutput>
    ): ReplayEvent | null {
        const vwapOutput = indicatorOutputs.get('vwap');
        if (!vwapOutput?.series || barIndex < 1 || barIndex >= vwapOutput.series.length) {
            return null;
        }

        const vwapCurrent = vwapOutput.series[barIndex]?.value;
        const vwapPrev = vwapOutput.series[barIndex - 1]?.value;

        if (vwapCurrent === undefined || vwapPrev === undefined) return null;

        // Cross above VWAP
        if (bar.close > vwapCurrent && bar.open <= vwapPrev) {
            return this.createEvent(
                'vwap_interaction',
                bar.timestamp,
                barIndex,
                'Price crossed above VWAP',
                bar.close,
                'medium',
                { vwap: vwapCurrent, direction: 'above' }
            );
        }

        // Cross below VWAP
        if (bar.close < vwapCurrent && bar.open >= vwapPrev) {
            return this.createEvent(
                'vwap_interaction',
                bar.timestamp,
                barIndex,
                'Price crossed below VWAP',
                bar.close,
                'medium',
                { vwap: vwapCurrent, direction: 'below' }
            );
        }

        // Touch VWAP
        const threshold = this.config.vwapInteraction.touchThreshold / 100;
        const deviation = Math.abs(bar.close - vwapCurrent) / vwapCurrent;
        if (deviation < threshold) {
            return this.createEvent(
                'vwap_interaction',
                bar.timestamp,
                barIndex,
                'Price touched VWAP',
                bar.close,
                'low',
                { vwap: vwapCurrent, direction: 'touch', deviation }
            );
        }

        return null;
    }

    /**
     * Detect structure break
     */
    private detectStructureBreak(
        bar: OHLCVBar,
        barIndex: number,
        allBars: OHLCVBar[]
    ): ReplayEvent | null {
        const lookback = this.config.structureBreak.lookbackPeriod;
        const recentBars = allBars.slice(barIndex - lookback, barIndex);
        
        const recentHigh = Math.max(...recentBars.map(b => b.high));
        const recentLow = Math.min(...recentBars.map(b => b.low));

        // Break above recent high
        if (bar.close > recentHigh && (this.lastSwingHigh === null || recentHigh !== this.lastSwingHigh)) {
            this.lastSwingHigh = recentHigh;
            return this.createEvent(
                'structure_break',
                bar.timestamp,
                barIndex,
                `Bullish Structure Break above ${recentHigh.toFixed(2)}`,
                bar.close,
                'high',
                { brokenLevel: recentHigh, direction: 'bullish' }
            );
        }

        // Break below recent low
        if (bar.close < recentLow && (this.lastSwingLow === null || recentLow !== this.lastSwingLow)) {
            this.lastSwingLow = recentLow;
            return this.createEvent(
                'structure_break',
                bar.timestamp,
                barIndex,
                `Bearish Structure Break below ${recentLow.toFixed(2)}`,
                bar.close,
                'high',
                { brokenLevel: recentLow, direction: 'bearish' }
            );
        }

        return null;
    }

    /**
     * Create an event object
     */
    private createEvent(
        type: ReplayEventType,
        timestamp: number,
        barIndex: number,
        description: string,
        price: number,
        severity: 'high' | 'medium' | 'low',
        details: Record<string, unknown>
    ): ReplayEvent {
        return {
            id: `event_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type,
            timestamp,
            barIndex,
            description,
            price,
            severity,
            details,
        };
    }

    /**
     * Generate learning prompt for an event
     */
    generateLearningPrompt(event: ReplayEvent): LearningPrompt {
        return {
            eventId: event.id,
            question: `${event.description}. What action would you take here?`,
            options: [
                { id: 'buy', label: 'Buy / Go Long' },
                { id: 'sell', label: 'Sell / Go Short' },
                { id: 'wait', label: 'Wait / No Action' },
                { id: 'exit', label: 'Exit Position' },
            ],
        };
    }

    /**
     * Get all detected events
     */
    getEvents(): ReplayEvent[] {
        return [...this.events];
    }

    /**
     * Get events at a specific bar index
     */
    getEventsAtBar(barIndex: number): ReplayEvent[] {
        return this.events.filter(e => e.barIndex === barIndex);
    }

    /**
     * Reset session data (call at start of replay)
     */
    resetSession(): void {
        this.events = [];
        this.currentBarIndex = 0;
        this.sessionHigh = 0;
        this.sessionLow = Infinity;
        this.lastSwingHigh = null;
        this.lastSwingLow = null;
    }

    /**
     * Update configuration
     */
    setConfig(config: Partial<EventDetectorConfig>): void {
        this.config = { ...this.config, ...config };
    }

    /**
     * Export event log
     */
    exportEventLog(): string {
        const headers = ['Timestamp', 'Type', 'Description', 'Price', 'Severity'];
        const rows = this.events.map(e => [
            new Date(e.timestamp).toISOString(),
            e.type,
            e.description,
            e.price.toFixed(2),
            e.severity,
        ]);
        return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    }
}

// =============================================================================
// SINGLETON
// =============================================================================

let replayEngineInstance: IntelligentReplayEngine | null = null;

export function getIntelligentReplayEngine(): IntelligentReplayEngine {
    if (!replayEngineInstance) {
        replayEngineInstance = new IntelligentReplayEngine();
    }
    return replayEngineInstance;
}
