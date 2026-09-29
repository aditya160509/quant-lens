/**
 * Alert Engine Types
 * Comprehensive alert system for price and indicator conditions
 */

import type { Timeframe } from '../types';

// =============================================================================
// CONDITION TYPES
// =============================================================================

export type AlertConditionType = 
    | 'price_cross_above'
    | 'price_cross_below'
    | 'price_enter_range'
    | 'price_exit_range'
    | 'price_percent_change'
    | 'indicator_cross_above'
    | 'indicator_cross_below'
    | 'indicator_enter_zone'
    | 'indicator_exit_zone'
    | 'ma_crossover'
    | 'ma_crossunder'
    | 'volume_spike'
    | 'candle_pattern';

export interface PriceCrossCondition {
    type: 'price_cross_above' | 'price_cross_below';
    threshold: number;
}

export interface PriceRangeCondition {
    type: 'price_enter_range' | 'price_exit_range';
    upper: number;
    lower: number;
}

export interface PricePercentChangeCondition {
    type: 'price_percent_change';
    percent: number;
    direction: 'up' | 'down' | 'any';
    period: number; // minutes
}

export interface IndicatorCrossCondition {
    type: 'indicator_cross_above' | 'indicator_cross_below';
    indicatorId: string;
    indicatorType: string;
    threshold: number;
}

export interface IndicatorZoneCondition {
    type: 'indicator_enter_zone' | 'indicator_exit_zone';
    indicatorId: string;
    indicatorType: string;
    zone: 'overbought' | 'oversold' | 'custom';
    upper?: number;
    lower?: number;
}

export interface MACrossoverCondition {
    type: 'ma_crossover' | 'ma_crossunder';
    fastMA: { type: string; period: number };
    slowMA: { type: string; period: number };
}

export interface VolumeSpikeCondition {
    type: 'volume_spike';
    multiplier: number; // e.g., 2.0 = 2x average volume
    period: number; // bars to average
}

export interface CandlePatternCondition {
    type: 'candle_pattern';
    pattern: 'doji' | 'hammer' | 'engulfing' | 'pinbar' | 'inside_bar';
    direction?: 'bullish' | 'bearish';
}

export type AlertCondition = 
    | PriceCrossCondition
    | PriceRangeCondition
    | PricePercentChangeCondition
    | IndicatorCrossCondition
    | IndicatorZoneCondition
    | MACrossoverCondition
    | VolumeSpikeCondition
    | CandlePatternCondition;

// =============================================================================
// NOTIFICATION TYPES
// =============================================================================

export type NotificationMethod = 'browser' | 'sound' | 'both' | 'none';

export interface NotificationSettings {
    method: NotificationMethod;
    soundFile?: string;
    showPopup: boolean;
    autoExpire: boolean;
    expireAfterMs?: number;
}

// =============================================================================
// ALERT TYPES
// =============================================================================

export type AlertStatus = 'active' | 'triggered' | 'expired' | 'paused';

export interface Alert {
    id: string;
    name: string;
    symbol: string;
    timeframe: Timeframe;
    condition: AlertCondition;
    notification: NotificationSettings;
    status: AlertStatus;
    enabled: boolean;
    
    // State
    lastState: boolean | null;  // For edge detection (cross vs stay)
    createdAt: number;
    triggeredAt: number | null;
    triggeredCount: number;
    
    // Options
    oneTime: boolean;  // Disable after first trigger
    expiresAt: number | null;
    cooldownMs: number;  // Minimum time between triggers
    lastTriggerTime: number | null;
    
    // Metadata
    notes?: string;
    color?: string;
}

export interface AlertTriggerEvent {
    alertId: string;
    timestamp: number;
    price: number;
    message: string;
    conditionMet: AlertCondition;
}

// =============================================================================
// ALERT HISTORY
// =============================================================================

export interface AlertHistoryEntry {
    id: string;
    alertId: string;
    alertName: string;
    symbol: string;
    timestamp: number;
    price: number;
    conditionType: AlertConditionType;
    message: string;
    acknowledged: boolean;
}

// =============================================================================
// ALERT MANAGER STATE
// =============================================================================

export interface AlertManagerState {
    alerts: Alert[];
    history: AlertHistoryEntry[];
    notificationPermission: NotificationPermission | null;
    isEvaluating: boolean;
}

// =============================================================================
// ALERT ACTIONS
// =============================================================================

export type AlertAction =
    | { type: 'ADD_ALERT'; payload: Alert }
    | { type: 'UPDATE_ALERT'; payload: Partial<Alert> & { id: string } }
    | { type: 'REMOVE_ALERT'; payload: string }
    | { type: 'TOGGLE_ALERT'; payload: string }
    | { type: 'TRIGGER_ALERT'; payload: AlertTriggerEvent }
    | { type: 'ACKNOWLEDGE_HISTORY'; payload: string }
    | { type: 'CLEAR_HISTORY' }
    | { type: 'SET_NOTIFICATION_PERMISSION'; payload: NotificationPermission }
    | { type: 'LOAD_ALERTS'; payload: Alert[] }
    | { type: 'SET_EVALUATING'; payload: boolean };

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

export function generateAlertId(): string {
    return `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function generateHistoryId(): string {
    return `history_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function createDefaultAlert(symbol: string, timeframe: Timeframe): Alert {
    return {
        id: generateAlertId(),
        name: `${symbol} Price Alert`,
        symbol,
        timeframe,
        condition: {
            type: 'price_cross_above',
            threshold: 0,
        },
        notification: {
            method: 'browser',
            showPopup: true,
            autoExpire: false,
        },
        status: 'active',
        enabled: true,
        lastState: null,
        createdAt: Date.now(),
        triggeredAt: null,
        triggeredCount: 0,
        oneTime: false,
        expiresAt: null,
        cooldownMs: 60000, // 1 minute default
        lastTriggerTime: null,
    };
}

export function getConditionDescription(condition: AlertCondition): string {
    switch (condition.type) {
        case 'price_cross_above':
            return `Price crosses above $${condition.threshold.toFixed(2)}`;
        case 'price_cross_below':
            return `Price crosses below $${condition.threshold.toFixed(2)}`;
        case 'price_enter_range':
            return `Price enters $${condition.lower.toFixed(2)} - $${condition.upper.toFixed(2)}`;
        case 'price_exit_range':
            return `Price exits $${condition.lower.toFixed(2)} - $${condition.upper.toFixed(2)}`;
        case 'price_percent_change':
            return `Price moves ${condition.percent}% ${condition.direction} in ${condition.period}min`;
        case 'indicator_cross_above':
            return `${condition.indicatorType} crosses above ${condition.threshold}`;
        case 'indicator_cross_below':
            return `${condition.indicatorType} crosses below ${condition.threshold}`;
        case 'indicator_enter_zone':
            return `${condition.indicatorType} enters ${condition.zone} zone`;
        case 'indicator_exit_zone':
            return `${condition.indicatorType} exits ${condition.zone} zone`;
        case 'ma_crossover':
            return `${condition.fastMA.type}(${condition.fastMA.period}) crosses above ${condition.slowMA.type}(${condition.slowMA.period})`;
        case 'ma_crossunder':
            return `${condition.fastMA.type}(${condition.fastMA.period}) crosses below ${condition.slowMA.type}(${condition.slowMA.period})`;
        case 'volume_spike':
            return `Volume exceeds ${condition.multiplier}x average`;
        case 'candle_pattern':
            return `${condition.direction || ''} ${condition.pattern} pattern`;
        default:
            return 'Unknown condition';
    }
}

// Alert color palette
export const ALERT_COLORS = [
    '#ff5252',  // Red
    '#ff9800',  // Orange
    '#ffeb3b',  // Yellow
    '#4caf50',  // Green
    '#2196f3',  // Blue
    '#9c27b0',  // Purple
    '#00bcd4',  // Cyan
    '#e91e63',  // Pink
];
