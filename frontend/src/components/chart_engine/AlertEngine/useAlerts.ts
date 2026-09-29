/**
 * useAlerts Hook
 * State management for alerts with evaluation loop and persistence
 */

'use client';

import { useReducer, useCallback, useEffect, useMemo, useRef } from 'react';
import type { OHLCVBar, IndicatorOutput, Timeframe } from '../types';
import {
    type Alert,
    type AlertAction,
    type AlertManagerState,
    type AlertHistoryEntry,
    type AlertCondition,
    type NotificationSettings,
    type AlertTriggerEvent,
    createDefaultAlert,
    generateAlertId,
    generateHistoryId,
} from './alertTypes';
import { evaluateAlert, createTriggerEvent } from './alertEvaluator';
import { triggerAlertNotification, getNotificationPermission } from './alertNotifier';

// =============================================================================
// CONSTANTS
// =============================================================================

const STORAGE_KEY = 'quant360_alerts';
const HISTORY_KEY = 'quant360_alert_history';
const MAX_HISTORY = 100;
const EVALUATION_INTERVAL = 1000; // 1 second

// =============================================================================
// INITIAL STATE
// =============================================================================

function getInitialState(): AlertManagerState {
    if (typeof window === 'undefined') {
        return {
            alerts: [],
            history: [],
            notificationPermission: null,
            isEvaluating: false,
        };
    }

    let alerts: Alert[] = [];
    let history: AlertHistoryEntry[] = [];

    try {
        const savedAlerts = localStorage.getItem(STORAGE_KEY);
        if (savedAlerts) {
            alerts = JSON.parse(savedAlerts);
        }

        const savedHistory = localStorage.getItem(HISTORY_KEY);
        if (savedHistory) {
            history = JSON.parse(savedHistory);
        }
    } catch (error) {
        console.error('Failed to load alerts from storage:', error);
    }

    return {
        alerts,
        history,
        notificationPermission: getNotificationPermission() as NotificationPermission,
        isEvaluating: false,
    };
}

// =============================================================================
// REDUCER
// =============================================================================

function alertReducer(state: AlertManagerState, action: AlertAction): AlertManagerState {
    switch (action.type) {
        case 'ADD_ALERT':
            return {
                ...state,
                alerts: [...state.alerts, action.payload],
            };

        case 'UPDATE_ALERT': {
            const { id, ...updates } = action.payload;
            return {
                ...state,
                alerts: state.alerts.map(a =>
                    a.id === id ? { ...a, ...updates } : a
                ),
            };
        }

        case 'REMOVE_ALERT':
            return {
                ...state,
                alerts: state.alerts.filter(a => a.id !== action.payload),
            };

        case 'TOGGLE_ALERT':
            return {
                ...state,
                alerts: state.alerts.map(a =>
                    a.id === action.payload ? { ...a, enabled: !a.enabled } : a
                ),
            };

        case 'TRIGGER_ALERT': {
            const { alertId, timestamp, price, message } = action.payload;
            const alert = state.alerts.find(a => a.id === alertId);
            if (!alert) return state;

            // Create history entry
            const historyEntry: AlertHistoryEntry = {
                id: generateHistoryId(),
                alertId,
                alertName: alert.name,
                symbol: alert.symbol,
                timestamp,
                price,
                conditionType: alert.condition.type,
                message,
                acknowledged: false,
            };

            // Update alert state
            const updatedAlerts = state.alerts.map(a => {
                if (a.id !== alertId) return a;
                return {
                    ...a,
                    status: alert.oneTime ? 'triggered' as const : a.status,
                    enabled: alert.oneTime ? false : a.enabled,
                    triggeredAt: timestamp,
                    triggeredCount: a.triggeredCount + 1,
                    lastTriggerTime: timestamp,
                    lastState: true,
                };
            });

            return {
                ...state,
                alerts: updatedAlerts,
                history: [historyEntry, ...state.history].slice(0, MAX_HISTORY),
            };
        }

        case 'ACKNOWLEDGE_HISTORY':
            return {
                ...state,
                history: state.history.map(h =>
                    h.id === action.payload ? { ...h, acknowledged: true } : h
                ),
            };

        case 'CLEAR_HISTORY':
            return {
                ...state,
                history: [],
            };

        case 'SET_NOTIFICATION_PERMISSION':
            return {
                ...state,
                notificationPermission: action.payload,
            };

        case 'LOAD_ALERTS':
            return {
                ...state,
                alerts: action.payload,
            };

        case 'SET_EVALUATING':
            return {
                ...state,
                isEvaluating: action.payload,
            };

        default:
            return state;
    }
}

// =============================================================================
// HOOK
// =============================================================================

interface UseAlertsOptions {
    symbol?: string;
    bars?: OHLCVBar[];
    indicatorOutputs?: Map<string, IndicatorOutput>;
    enabled?: boolean;
}

export function useAlerts(options: UseAlertsOptions = {}) {
    const { symbol, bars, indicatorOutputs = new Map(), enabled = true } = options;
    
    const [state, dispatch] = useReducer(alertReducer, undefined, getInitialState);
    const evaluationRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Persist alerts to localStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state.alerts));
        }
    }, [state.alerts]);

    // Persist history to localStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem(HISTORY_KEY, JSON.stringify(state.history));
        }
    }, [state.history]);

    // ==========================================================================
    // ALERT CRUD
    // ==========================================================================

    const addAlert = useCallback((
        alertSymbol: string,
        timeframe: Timeframe,
        condition: AlertCondition,
        name?: string,
        notification?: Partial<NotificationSettings>
    ) => {
        const alert = createDefaultAlert(alertSymbol, timeframe);
        alert.condition = condition;
        if (name) alert.name = name;
        if (notification) alert.notification = { ...alert.notification, ...notification };
        
        dispatch({ type: 'ADD_ALERT', payload: alert });
        return alert;
    }, []);

    const updateAlert = useCallback((id: string, updates: Partial<Alert>) => {
        dispatch({ type: 'UPDATE_ALERT', payload: { id, ...updates } });
    }, []);

    const removeAlert = useCallback((id: string) => {
        dispatch({ type: 'REMOVE_ALERT', payload: id });
    }, []);

    const toggleAlert = useCallback((id: string) => {
        dispatch({ type: 'TOGGLE_ALERT', payload: id });
    }, []);

    // ==========================================================================
    // QUICK ALERT CREATORS
    // ==========================================================================

    const addPriceAlert = useCallback((
        alertSymbol: string,
        timeframe: Timeframe,
        threshold: number,
        direction: 'above' | 'below'
    ) => {
        const condition: AlertCondition = {
            type: direction === 'above' ? 'price_cross_above' : 'price_cross_below',
            threshold,
        };
        return addAlert(
            alertSymbol,
            timeframe,
            condition,
            `${alertSymbol} ${direction === 'above' ? '>' : '<'} $${threshold}`
        );
    }, [addAlert]);

    const addIndicatorAlert = useCallback((
        alertSymbol: string,
        timeframe: Timeframe,
        indicatorType: string,
        indicatorId: string,
        threshold: number,
        direction: 'above' | 'below'
    ) => {
        const condition: AlertCondition = {
            type: direction === 'above' ? 'indicator_cross_above' : 'indicator_cross_below',
            indicatorType,
            indicatorId,
            threshold,
        };
        return addAlert(
            alertSymbol,
            timeframe,
            condition,
            `${indicatorType} ${direction === 'above' ? '>' : '<'} ${threshold}`
        );
    }, [addAlert]);

    // ==========================================================================
    // HISTORY MANAGEMENT
    // ==========================================================================

    const acknowledgeHistory = useCallback((id: string) => {
        dispatch({ type: 'ACKNOWLEDGE_HISTORY', payload: id });
    }, []);

    const clearHistory = useCallback(() => {
        dispatch({ type: 'CLEAR_HISTORY' });
    }, []);

    // ==========================================================================
    // EVALUATION LOOP
    // ==========================================================================

    const evaluateAlerts = useCallback(async () => {
        if (!bars || bars.length === 0) return;

        dispatch({ type: 'SET_EVALUATING', payload: true });

        const activeAlerts = state.alerts.filter(a => 
            a.enabled && 
            a.status === 'active' &&
            (!symbol || a.symbol === symbol)
        );

        for (const alert of activeAlerts) {
            // Check expiration
            if (alert.expiresAt && Date.now() > alert.expiresAt) {
                updateAlert(alert.id, { status: 'expired', enabled: false });
                continue;
            }

            const result = evaluateAlert(alert, bars, indicatorOutputs);

            // Update lastState
            if (result.currentState !== alert.lastState) {
                updateAlert(alert.id, { lastState: result.currentState });
            }

            if (result.triggered) {
                const event = createTriggerEvent(alert, result);
                dispatch({ type: 'TRIGGER_ALERT', payload: event });
                
                // Send notification
                await triggerAlertNotification(alert, event);
            }
        }

        dispatch({ type: 'SET_EVALUATING', payload: false });
    }, [bars, indicatorOutputs, state.alerts, symbol, updateAlert]);

    // Start evaluation loop when enabled
    useEffect(() => {
        if (!enabled || !bars || bars.length === 0) {
            if (evaluationRef.current) {
                clearInterval(evaluationRef.current);
                evaluationRef.current = null;
            }
            return;
        }

        // Initial evaluation
        evaluateAlerts();

        // Set up interval
        evaluationRef.current = setInterval(evaluateAlerts, EVALUATION_INTERVAL);

        return () => {
            if (evaluationRef.current) {
                clearInterval(evaluationRef.current);
                evaluationRef.current = null;
            }
        };
    }, [enabled, bars, evaluateAlerts]);

    // ==========================================================================
    // COMPUTED VALUES
    // ==========================================================================

    const alertsForSymbol = useMemo(() => 
        symbol ? state.alerts.filter(a => a.symbol === symbol) : state.alerts,
    [state.alerts, symbol]);

    const activeAlerts = useMemo(() =>
        state.alerts.filter(a => a.enabled && a.status === 'active'),
    [state.alerts]);

    const triggeredAlerts = useMemo(() =>
        state.alerts.filter(a => a.status === 'triggered'),
    [state.alerts]);

    const unacknowledgedHistory = useMemo(() =>
        state.history.filter(h => !h.acknowledged),
    [state.history]);

    return {
        // State
        alerts: state.alerts,
        history: state.history,
        alertsForSymbol,
        activeAlerts,
        triggeredAlerts,
        unacknowledgedHistory,
        notificationPermission: state.notificationPermission,
        isEvaluating: state.isEvaluating,

        // CRUD
        addAlert,
        updateAlert,
        removeAlert,
        toggleAlert,

        // Quick creators
        addPriceAlert,
        addIndicatorAlert,

        // History
        acknowledgeHistory,
        clearHistory,

        // Manual evaluation
        evaluateAlerts,
    };
}

export type UseAlerts = ReturnType<typeof useAlerts>;
