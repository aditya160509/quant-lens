/**
 * Alert Manager Panel
 * TradingView-style alert management UI
 */

'use client';

import React, { useState, useCallback } from 'react';
import { CHART_THEME, type Timeframe } from '../types';
import {
    type Alert,
    type AlertCondition,
    type AlertConditionType,
    type NotificationMethod,
    getConditionDescription,
    ALERT_COLORS,
} from './alertTypes';
import { requestNotificationPermission } from './alertNotifier';
import { useAlerts } from './useAlerts';
import { Bell, History, Plus, X, AlertCircle, Trash2, Power, BellOff } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface AlertManagerProps {
    symbol: string;
    timeframe: Timeframe;
    currentPrice: number;
    isOpen: boolean;
    onClose: () => void;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function AlertManager({
    symbol,
    timeframe,
    currentPrice,
    isOpen,
    onClose,
}: AlertManagerProps) {
    const {
        alertsForSymbol,
        history,
        unacknowledgedHistory,
        notificationPermission,
        addPriceAlert,
        removeAlert,
        toggleAlert,
        acknowledgeHistory,
        clearHistory,
    } = useAlerts({ symbol });

    const [activeTab, setActiveTab] = useState<'alerts' | 'history'>('alerts');
    const [isCreating, setIsCreating] = useState(false);

    // New alert form state
    const [newAlertType, setNewAlertType] = useState<'above' | 'below'>('above');
    const [newAlertPrice, setNewAlertPrice] = useState(currentPrice.toString());

    const handleCreateAlert = useCallback(() => {
        const price = parseFloat(newAlertPrice);
        if (isNaN(price)) return;

        addPriceAlert(symbol, timeframe, price, newAlertType);
        setIsCreating(false);
        setNewAlertPrice(currentPrice.toString());
    }, [addPriceAlert, symbol, timeframe, newAlertPrice, newAlertType, currentPrice]);

    const handleRequestPermission = useCallback(async () => {
        await requestNotificationPermission();
    }, []);

    if (!isOpen) return null;

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                right: 0,
                width: '360px',
                height: '100vh',
                background: CHART_THEME.bgSecondary,
                borderLeft: `1px solid ${CHART_THEME.border}`,
                display: 'flex',
                flexDirection: 'column',
                zIndex: 1000,
                boxShadow: '-4px 0 20px rgba(0, 0, 0, 0.3)',
            }}
        >
            {/* Header */}
            <div
                style={{
                    padding: '16px',
                    borderBottom: `1px solid ${CHART_THEME.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}
            >
                <h2 style={{
                    margin: 0,
                    fontSize: '16px',
                    fontWeight: 600,
                    color: CHART_THEME.textPrimary,
                }}>
                    Alerts
                </h2>
                <button
                    onClick={onClose}
                    style={{
                        width: '28px',
                        height: '28px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: CHART_THEME.textSecondary,
                        borderRadius: '4px',
                    }}
                >
                    <X size={16} />
                </button>
            </div>

            {/* Notification Permission Banner */}
            {notificationPermission !== 'granted' && (
                <div
                    style={{
                        padding: '12px 16px',
                        background: 'rgba(255, 165, 0, 0.1)',
                        borderBottom: `1px solid ${CHART_THEME.border}`,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                    }}
                >
                    <Bell size={18} className="text-terminal-yellow" />
                    <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '12px', color: CHART_THEME.textPrimary, fontWeight: 500 }}>
                            Enable Notifications
                        </div>
                        <div style={{ fontSize: '11px', color: CHART_THEME.textSecondary }}>
                            Get browser alerts when conditions trigger
                        </div>
                    </div>
                    <button
                        onClick={handleRequestPermission}
                        style={{
                            padding: '6px 12px',
                            fontSize: '11px',
                            fontWeight: 500,
                            background: CHART_THEME.accent,
                            color: '#000',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                        }}
                    >
                        Enable
                    </button>
                </div>
            )}

            {/* Tabs */}
            <div
                style={{
                    display: 'flex',
                    borderBottom: `1px solid ${CHART_THEME.border}`,
                }}
            >
                {(['alerts', 'history'] as const).map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        style={{
                            flex: 1,
                            padding: '12px',
                            fontSize: '13px',
                            fontWeight: activeTab === tab ? 600 : 400,
                            color: activeTab === tab ? CHART_THEME.accent : CHART_THEME.textSecondary,
                            background: 'transparent',
                            border: 'none',
                            borderBottom: activeTab === tab 
                                ? `2px solid ${CHART_THEME.accent}` 
                                : '2px solid transparent',
                            cursor: 'pointer',
                            textTransform: 'capitalize',
                        }}
                    >
                        {tab}
                        {tab === 'history' && unacknowledgedHistory.length > 0 && (
                            <span style={{
                                marginLeft: '6px',
                                background: CHART_THEME.downColor,
                                color: '#fff',
                                padding: '2px 6px',
                                borderRadius: '10px',
                                fontSize: '10px',
                            }}>
                                {unacknowledgedHistory.length}
                            </span>
                        )}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: '12px' }}>
                {activeTab === 'alerts' && (
                    <>
                        {/* Create Alert Section */}
                        {isCreating ? (
                            <div
                                style={{
                                    padding: '16px',
                                    background: CHART_THEME.bgTertiary,
                                    borderRadius: '8px',
                                    marginBottom: '12px',
                                }}
                            >
                                <div style={{ marginBottom: '12px' }}>
                                    <label style={{
                                        display: 'block',
                                        fontSize: '11px',
                                        color: CHART_THEME.textSecondary,
                                        marginBottom: '6px',
                                    }}>
                                        Condition
                                    </label>
                                    <div style={{ display: 'flex', gap: '8px' }}>
                                        {(['above', 'below'] as const).map(type => (
                                            <button
                                                key={type}
                                                onClick={() => setNewAlertType(type)}
                                                style={{
                                                    flex: 1,
                                                    padding: '8px',
                                                    fontSize: '12px',
                                                    background: newAlertType === type
                                                        ? (type === 'above' ? 'rgba(0, 255, 136, 0.15)' : 'rgba(255, 45, 85, 0.15)')
                                                        : 'transparent',
                                                    border: `1px solid ${newAlertType === type
                                                        ? (type === 'above' ? CHART_THEME.upColor : CHART_THEME.downColor)
                                                        : CHART_THEME.border}`,
                                                    borderRadius: '4px',
                                                    color: newAlertType === type
                                                        ? (type === 'above' ? CHART_THEME.upColor : CHART_THEME.downColor)
                                                        : CHART_THEME.textSecondary,
                                                    cursor: 'pointer',
                                                }}
                                            >
                                                Crosses {type}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div style={{ marginBottom: '16px' }}>
                                    <label style={{
                                        display: 'block',
                                        fontSize: '11px',
                                        color: CHART_THEME.textSecondary,
                                        marginBottom: '6px',
                                    }}>
                                        Price
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={newAlertPrice}
                                        onChange={(e) => setNewAlertPrice(e.target.value)}
                                        style={{
                                            width: '100%',
                                            padding: '10px 12px',
                                            fontSize: '14px',
                                            fontFamily: CHART_THEME.fontMono,
                                            background: CHART_THEME.bgPrimary,
                                            border: `1px solid ${CHART_THEME.border}`,
                                            borderRadius: '4px',
                                            color: CHART_THEME.textPrimary,
                                            outline: 'none',
                                        }}
                                    />
                                </div>

                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <button
                                        onClick={() => setIsCreating(false)}
                                        style={{
                                            flex: 1,
                                            padding: '10px',
                                            fontSize: '12px',
                                            background: 'transparent',
                                            border: `1px solid ${CHART_THEME.border}`,
                                            borderRadius: '4px',
                                            color: CHART_THEME.textSecondary,
                                            cursor: 'pointer',
                                        }}
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        onClick={handleCreateAlert}
                                        style={{
                                            flex: 1,
                                            padding: '10px',
                                            fontSize: '12px',
                                            fontWeight: 600,
                                            background: CHART_THEME.accent,
                                            border: 'none',
                                            borderRadius: '4px',
                                            color: '#000',
                                            cursor: 'pointer',
                                        }}
                                    >
                                        Create Alert
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <button
                                onClick={() => setIsCreating(true)}
                                style={{
                                    width: '100%',
                                    padding: '12px',
                                    marginBottom: '12px',
                                    fontSize: '13px',
                                    fontWeight: 500,
                                    background: 'transparent',
                                    border: `1px dashed ${CHART_THEME.border}`,
                                    borderRadius: '8px',
                                    color: CHART_THEME.accent,
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '8px',
                                }}
                            >
                                <Plus size={14} />
                                Create Alert for {symbol}
                            </button>
                        )}

                        {/* Alert List */}
                        {alertsForSymbol.length === 0 ? (
                            <div style={{
                                textAlign: 'center',
                                padding: '40px 20px',
                                color: CHART_THEME.textSecondary,
                            }}>
                                <Bell size={32} className="mx-auto mb-3 opacity-20" />
                                <div style={{ fontSize: '13px' }}>No alerts for {symbol}</div>
                                <div style={{ fontSize: '11px', opacity: 0.7, marginTop: '4px' }}>
                                    Create an alert to get notified of price movements
                                </div>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {alertsForSymbol.map(alert => (
                                    <AlertCard
                                        key={alert.id}
                                        alert={alert}
                                        onToggle={() => toggleAlert(alert.id)}
                                        onRemove={() => removeAlert(alert.id)}
                                    />
                                ))}
                            </div>
                        )}
                    </>
                )}

                {activeTab === 'history' && (
                    <>
                        {history.length === 0 ? (
                            <div style={{
                                textAlign: 'center',
                                padding: '40px 20px',
                                color: CHART_THEME.textSecondary,
                            }}>
                                <History size={32} className="mx-auto mb-3 opacity-20" />
                                <div style={{ fontSize: '13px' }}>No alert history</div>
                            </div>
                        ) : (
                            <>
                                <button
                                    onClick={clearHistory}
                                    style={{
                                        width: '100%',
                                        padding: '8px',
                                        marginBottom: '12px',
                                        fontSize: '11px',
                                        background: 'transparent',
                                        border: `1px solid ${CHART_THEME.border}`,
                                        borderRadius: '4px',
                                        color: CHART_THEME.textSecondary,
                                        cursor: 'pointer',
                                    }}
                                >
                                    Clear History
                                </button>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {history.map(entry => (
                                        <HistoryCard
                                            key={entry.id}
                                            entry={entry}
                                            onAcknowledge={() => acknowledgeHistory(entry.id)}
                                        />
                                    ))}
                                </div>
                            </>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// ALERT CARD
// =============================================================================

function AlertCard({
    alert,
    onToggle,
    onRemove,
}: {
    alert: Alert;
    onToggle: () => void;
    onRemove: () => void;
}) {
    const description = getConditionDescription(alert.condition);

    return (
        <div
            style={{
                padding: '12px',
                background: CHART_THEME.bgTertiary,
                borderRadius: '6px',
                borderLeft: `3px solid ${alert.enabled ? CHART_THEME.upColor : CHART_THEME.textSecondary}`,
            }}
        >
            <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                marginBottom: '6px',
            }}>
                <div>
                    <div style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: CHART_THEME.textPrimary,
                    }}>
                        {alert.name}
                    </div>
                    <div style={{
                        fontSize: '11px',
                        color: CHART_THEME.textSecondary,
                        marginTop: '2px',
                    }}>
                        {description}
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                        onClick={onToggle}
                        style={{
                            width: '24px',
                            height: '24px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            color: alert.enabled ? CHART_THEME.upColor : CHART_THEME.textSecondary,
                        }}
                        title={alert.enabled ? 'Disable' : 'Enable'}
                    >
                        {alert.enabled ? <Bell size={16} /> : <BellOff size={16} />}
                    </button>
                    <button
                        onClick={onRemove}
                        style={{
                            width: '24px',
                            height: '24px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            color: CHART_THEME.textSecondary,
                        }}
                        title="Delete"
                    >
                        <Trash2 size={14} />
                    </button>
                </div>
            </div>

            {alert.triggeredCount > 0 && (
                <div style={{
                    fontSize: '10px',
                    color: CHART_THEME.textMuted,
                    marginTop: '6px',
                }}>
                    Triggered {alert.triggeredCount} time{alert.triggeredCount > 1 ? 's' : ''}
                    {alert.triggeredAt && ` · Last: ${new Date(alert.triggeredAt).toLocaleTimeString()}`}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// HISTORY CARD
// =============================================================================

import type { AlertHistoryEntry } from './alertTypes';

function HistoryCard({
    entry,
    onAcknowledge,
}: {
    entry: AlertHistoryEntry;
    onAcknowledge: () => void;
}) {
    return (
        <div
            style={{
                padding: '10px 12px',
                background: entry.acknowledged 
                    ? CHART_THEME.bgTertiary 
                    : 'rgba(255, 214, 10, 0.08)',
                borderRadius: '4px',
                borderLeft: `2px solid ${entry.acknowledged ? CHART_THEME.border : CHART_THEME.accent}`,
                cursor: entry.acknowledged ? 'default' : 'pointer',
            }}
            onClick={() => !entry.acknowledged && onAcknowledge()}
        >
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
            }}>
                <span style={{
                    fontSize: '12px',
                    fontWeight: 500,
                    color: CHART_THEME.textPrimary,
                }}>
                    {entry.symbol} @ ${entry.price.toFixed(2)}
                </span>
                <span style={{
                    fontSize: '10px',
                    color: CHART_THEME.textMuted,
                }}>
                    {new Date(entry.timestamp).toLocaleTimeString()}
                </span>
            </div>
            <div style={{
                fontSize: '11px',
                color: CHART_THEME.textSecondary,
                marginTop: '4px',
            }}>
                {entry.message}
            </div>
        </div>
    );
}

export default AlertManager;
