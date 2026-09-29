'use client';

/**
 * Replay Decision Capture
 * 
 * Per tradefeature.md §23:
 * - Mark entry, hesitation, exit decisions during replay
 * - Log and analyze decisions vs actual outcomes
 * - Compare decision quality over time
 */

import React, { useState, useCallback } from 'react';

// =============================================================================
// TYPES
// =============================================================================

export type DecisionType = 
    | 'would_enter'
    | 'hesitated'
    | 'would_exit'
    | 'missed_opportunity';

export type EntryReason = 
    | 'breakout'
    | 'pullback'
    | 'indicator_signal'
    | 'support_bounce'
    | 'resistance_break'
    | 'other';

export type HesitationReason = 
    | 'fear'
    | 'uncertainty'
    | 'conflicting_signals'
    | 'waiting_confirmation'
    | 'other';

export type ExitReason =
    | 'fear_reversal'
    | 'profit_target_hit'
    | 'stop_tightened'
    | 'emotional'
    | 'other';

export type MissedReason =
    | 'didnt_see'
    | 'distracted'
    | 'waited_too_long'
    | 'over_analysis'
    | 'other';

export interface ReplayDecision {
    id: string;
    type: DecisionType;
    timestamp: number;
    barIndex: number;
    price: number;
    reason: string;
    confidence?: number; // 1-10
    notes?: string;
    plannedStop?: number;
    plannedTarget?: number;
    actualOutcome?: DecisionOutcome;
}

export interface DecisionOutcome {
    exitPrice: number;
    exitTimestamp: number;
    exitBarIndex: number;
    hypotheticalPnL: number;
    wasSuccessful: boolean;
    analysis: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const THEME = {
    bg: '#131722',
    bgSecondary: '#1e222d',
    bgTertiary: '#252a37',
    border: '#363a45',
    text: '#d1d4dc',
    textMuted: '#787b86',
    danger: '#ef5350',
    success: '#26a69a',
    warning: '#ff9800',
    info: '#2962ff',
};

const DECISION_COLORS: Record<DecisionType, string> = {
    would_enter: THEME.success,
    hesitated: THEME.warning,
    would_exit: '#ff9800',
    missed_opportunity: THEME.textMuted,
};

const DECISION_LABELS: Record<DecisionType, string> = {
    would_enter: '📍 Would Enter',
    hesitated: '🤔 Hesitated',
    would_exit: '🚪 Would Exit',
    missed_opportunity: '👀 Missed',
};

// =============================================================================
// DECISION CAPTURE MANAGER
// =============================================================================

export class ReplayDecisionManager {
    private decisions: ReplayDecision[] = [];
    private sessionId: string;

    constructor() {
        this.sessionId = `session_${Date.now()}`;
    }

    addDecision(decision: Omit<ReplayDecision, 'id'>): ReplayDecision {
        const newDecision: ReplayDecision = {
            ...decision,
            id: `dec_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        };
        this.decisions.push(newDecision);
        return newDecision;
    }

    updateDecisionOutcome(
        decisionId: string,
        outcome: DecisionOutcome
    ): void {
        const decision = this.decisions.find(d => d.id === decisionId);
        if (decision) {
            decision.actualOutcome = outcome;
        }
    }

    getDecisions(): ReplayDecision[] {
        return [...this.decisions];
    }

    getDecisionsByType(type: DecisionType): ReplayDecision[] {
        return this.decisions.filter(d => d.type === type);
    }

    analyzeDecisions(): DecisionAnalysis {
        const analysis: DecisionAnalysis = {
            totalDecisions: this.decisions.length,
            byType: {
                would_enter: 0,
                hesitated: 0,
                would_exit: 0,
                missed_opportunity: 0,
            },
            successfulEntries: 0,
            hesitationsCostProfit: 0,
            hesitationsSavedLoss: 0,
            earlyExitsCostProfit: 0,
            earlyExitsSavedLoss: 0,
        };

        for (const decision of this.decisions) {
            analysis.byType[decision.type]++;

            if (decision.actualOutcome) {
                const outcome = decision.actualOutcome;
                
                if (decision.type === 'would_enter') {
                    if (outcome.wasSuccessful) {
                        analysis.successfulEntries++;
                    }
                } else if (decision.type === 'hesitated') {
                    if (outcome.hypotheticalPnL > 0) {
                        analysis.hesitationsCostProfit++;
                    } else {
                        analysis.hesitationsSavedLoss++;
                    }
                } else if (decision.type === 'would_exit') {
                    if (outcome.hypotheticalPnL > 0) {
                        analysis.earlyExitsCostProfit++;
                    } else {
                        analysis.earlyExitsSavedLoss++;
                    }
                }
            }
        }

        return analysis;
    }

    clearSession(): void {
        this.decisions = [];
        this.sessionId = `session_${Date.now()}`;
    }

    exportToCSV(): string {
        const headers = ['ID', 'Type', 'Timestamp', 'Price', 'Reason', 'Confidence', 'Notes', 'Outcome PnL', 'Successful'];
        const rows = this.decisions.map(d => [
            d.id,
            d.type,
            new Date(d.timestamp).toISOString(),
            d.price.toFixed(2),
            d.reason,
            d.confidence?.toString() ?? '',
            d.notes ?? '',
            d.actualOutcome?.hypotheticalPnL.toFixed(2) ?? '',
            d.actualOutcome?.wasSuccessful ? 'Yes' : 'No',
        ]);
        return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    }
}

export interface DecisionAnalysis {
    totalDecisions: number;
    byType: Record<DecisionType, number>;
    successfulEntries: number;
    hesitationsCostProfit: number;
    hesitationsSavedLoss: number;
    earlyExitsCostProfit: number;
    earlyExitsSavedLoss: number;
}

// =============================================================================
// DECISION CAPTURE PANEL
// =============================================================================

interface DecisionCapturePanelProps {
    currentPrice: number;
    currentTimestamp: number;
    currentBarIndex: number;
    onDecisionMarked: (decision: ReplayDecision) => void;
    decisions: ReplayDecision[];
}

export function DecisionCapturePanel({
    currentPrice,
    currentTimestamp,
    currentBarIndex,
    onDecisionMarked,
    decisions,
}: DecisionCapturePanelProps) {
    const [showModal, setShowModal] = useState<DecisionType | null>(null);
    const [reason, setReason] = useState('');
    const [confidence, setConfidence] = useState(5);
    const [notes, setNotes] = useState('');
    const [plannedStop, setPlannedStop] = useState<number | null>(null);
    const [plannedTarget, setPlannedTarget] = useState<number | null>(null);

    const handleMarkDecision = useCallback((type: DecisionType) => {
        setShowModal(type);
        setReason('');
        setNotes('');
        setConfidence(5);
        setPlannedStop(null);
        setPlannedTarget(null);
    }, []);

    const handleConfirmDecision = useCallback(() => {
        if (!showModal) return;

        const decision: Omit<ReplayDecision, 'id'> = {
            type: showModal,
            timestamp: currentTimestamp,
            barIndex: currentBarIndex,
            price: currentPrice,
            reason,
            confidence,
            notes: notes || undefined,
            plannedStop: plannedStop || undefined,
            plannedTarget: plannedTarget || undefined,
        };

        onDecisionMarked({
            ...decision,
            id: `dec_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        });

        setShowModal(null);
    }, [showModal, currentTimestamp, currentBarIndex, currentPrice, reason, confidence, notes, plannedStop, plannedTarget, onDecisionMarked]);

    const getReasonOptions = (type: DecisionType): { value: string; label: string }[] => {
        switch (type) {
            case 'would_enter':
                return [
                    { value: 'breakout', label: 'Breakout' },
                    { value: 'pullback', label: 'Pullback' },
                    { value: 'indicator_signal', label: 'Indicator Signal' },
                    { value: 'support_bounce', label: 'Support Bounce' },
                    { value: 'resistance_break', label: 'Resistance Break' },
                    { value: 'other', label: 'Other' },
                ];
            case 'hesitated':
                return [
                    { value: 'fear', label: 'Fear' },
                    { value: 'uncertainty', label: 'Uncertainty' },
                    { value: 'conflicting_signals', label: 'Conflicting Signals' },
                    { value: 'waiting_confirmation', label: 'Waiting for Confirmation' },
                    { value: 'other', label: 'Other' },
                ];
            case 'would_exit':
                return [
                    { value: 'fear_reversal', label: 'Fear of Reversal' },
                    { value: 'profit_target_hit', label: 'Profit Target Met' },
                    { value: 'stop_tightened', label: 'Tightened Stop' },
                    { value: 'emotional', label: 'Emotional Decision' },
                    { value: 'other', label: 'Other' },
                ];
            case 'missed_opportunity':
                return [
                    { value: 'didnt_see', label: "Didn't See It" },
                    { value: 'distracted', label: 'Distracted' },
                    { value: 'waited_too_long', label: 'Waited Too Long' },
                    { value: 'over_analysis', label: 'Over-Analysis' },
                    { value: 'other', label: 'Other' },
                ];
        }
    };

    return (
        <>
            {/* Quick Action Buttons */}
            <div style={{
                position: 'absolute',
                bottom: '12px',
                left: '12px',
                display: 'flex',
                gap: '8px',
                zIndex: 50,
            }}>
                {(Object.keys(DECISION_LABELS) as DecisionType[]).map(type => (
                    <button
                        key={type}
                        onClick={() => handleMarkDecision(type)}
                        style={{
                            padding: '8px 12px',
                            background: THEME.bgSecondary,
                            border: `1px solid ${DECISION_COLORS[type]}`,
                            borderRadius: '6px',
                            color: DECISION_COLORS[type],
                            cursor: 'pointer',
                            fontSize: '11px',
                            fontWeight: 500,
                        }}
                    >
                        {DECISION_LABELS[type]}
                    </button>
                ))}
            </div>

            {/* Decision Count Badge */}
            {decisions.length > 0 && (
                <div style={{
                    position: 'absolute',
                    bottom: '60px',
                    left: '12px',
                    padding: '4px 8px',
                    background: THEME.bgSecondary,
                    border: `1px solid ${THEME.border}`,
                    borderRadius: '4px',
                    color: THEME.text,
                    fontSize: '10px',
                    zIndex: 50,
                }}>
                    {decisions.length} decisions logged
                </div>
            )}

            {/* Decision Modal */}
            {showModal && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(0, 0, 0, 0.7)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 1000,
                    }}
                    onClick={() => setShowModal(null)}
                >
                    <div
                        style={{
                            width: '360px',
                            background: THEME.bgSecondary,
                            border: `1px solid ${THEME.border}`,
                            borderRadius: '12px',
                            padding: '20px',
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        <h3 style={{
                            color: DECISION_COLORS[showModal],
                            margin: '0 0 16px',
                            fontSize: '14px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                        }}>
                            {DECISION_LABELS[showModal]}
                            <span style={{ color: THEME.textMuted, fontSize: '11px' }}>
                                @ ${currentPrice.toFixed(2)}
                            </span>
                        </h3>

                        {/* Reason Selection */}
                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '11px', display: 'block', marginBottom: '8px' }}>
                                Why?
                            </label>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                                {getReasonOptions(showModal).map(opt => (
                                    <button
                                        key={opt.value}
                                        onClick={() => setReason(opt.value)}
                                        style={{
                                            padding: '8px',
                                            background: reason === opt.value ? DECISION_COLORS[showModal] : THEME.bgTertiary,
                                            border: `1px solid ${reason === opt.value ? DECISION_COLORS[showModal] : THEME.border}`,
                                            borderRadius: '4px',
                                            color: reason === opt.value ? '#fff' : THEME.text,
                                            cursor: 'pointer',
                                            fontSize: '11px',
                                        }}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Confidence Slider */}
                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '11px', display: 'block', marginBottom: '4px' }}>
                                Confidence: {confidence}/10
                            </label>
                            <input
                                type="range"
                                min="1"
                                max="10"
                                value={confidence}
                                onChange={e => setConfidence(parseInt(e.target.value))}
                                style={{ width: '100%' }}
                            />
                        </div>

                        {/* Entry-specific fields */}
                        {showModal === 'would_enter' && (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px' }}>
                                <div>
                                    <label style={{ color: THEME.textMuted, fontSize: '10px', display: 'block', marginBottom: '4px' }}>
                                        Planned Stop
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={plannedStop ?? ''}
                                        onChange={e => setPlannedStop(parseFloat(e.target.value) || null)}
                                        style={{
                                            width: '100%',
                                            padding: '6px 8px',
                                            background: THEME.bg,
                                            border: `1px solid ${THEME.danger}`,
                                            borderRadius: '4px',
                                            color: THEME.danger,
                                            fontSize: '11px',
                                        }}
                                    />
                                </div>
                                <div>
                                    <label style={{ color: THEME.textMuted, fontSize: '10px', display: 'block', marginBottom: '4px' }}>
                                        Planned Target
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={plannedTarget ?? ''}
                                        onChange={e => setPlannedTarget(parseFloat(e.target.value) || null)}
                                        style={{
                                            width: '100%',
                                            padding: '6px 8px',
                                            background: THEME.bg,
                                            border: `1px solid ${THEME.success}`,
                                            borderRadius: '4px',
                                            color: THEME.success,
                                            fontSize: '11px',
                                        }}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Notes */}
                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '10px', display: 'block', marginBottom: '4px' }}>
                                Notes (optional)
                            </label>
                            <textarea
                                value={notes}
                                onChange={e => setNotes(e.target.value)}
                                style={{
                                    width: '100%',
                                    padding: '8px',
                                    background: THEME.bg,
                                    border: `1px solid ${THEME.border}`,
                                    borderRadius: '4px',
                                    color: THEME.text,
                                    fontSize: '11px',
                                    minHeight: '50px',
                                    resize: 'vertical',
                                }}
                                placeholder="Additional thoughts..."
                            />
                        </div>

                        {/* Actions */}
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                                onClick={() => setShowModal(null)}
                                style={{
                                    flex: 1,
                                    padding: '10px',
                                    background: THEME.bgTertiary,
                                    border: `1px solid ${THEME.border}`,
                                    borderRadius: '6px',
                                    color: THEME.text,
                                    cursor: 'pointer',
                                    fontSize: '12px',
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleConfirmDecision}
                                disabled={!reason}
                                style={{
                                    flex: 1,
                                    padding: '10px',
                                    background: reason ? DECISION_COLORS[showModal] : THEME.bgTertiary,
                                    border: 'none',
                                    borderRadius: '6px',
                                    color: reason ? '#fff' : THEME.textMuted,
                                    cursor: reason ? 'pointer' : 'not-allowed',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                }}
                            >
                                Log Decision
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

// Singleton
let decisionManagerInstance: ReplayDecisionManager | null = null;

export function getReplayDecisionManager(): ReplayDecisionManager {
    if (!decisionManagerInstance) {
        decisionManagerInstance = new ReplayDecisionManager();
    }
    return decisionManagerInstance;
}

export default DecisionCapturePanel;
