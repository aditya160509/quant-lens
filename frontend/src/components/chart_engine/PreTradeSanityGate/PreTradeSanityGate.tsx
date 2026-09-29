'use client';

/**
 * Pre-Trade Sanity Gate
 * 
 * Per tradefeature.md §22:
 * - Mandatory pre-trade checklist before order execution
 * - Direction, invalidation level, risk size, trade reason confirmation
 * - Position sizing calculation
 * - Clear visual feedback
 */

import React, { useState, useCallback, useMemo } from 'react';
import { calculatePositionSize, type RiskParameters } from '../RiskFirstMode/RiskFirstPanel';

// =============================================================================
// TYPES
// =============================================================================

export type TradeDirection = 'long' | 'short';
export type TradeReason = 
    | 'breakout'
    | 'pullback'
    | 'reversal'
    | 'mean_reversion'
    | 'trend_continuation'
    | 'other';

export interface PreTradeChecklist {
    direction: TradeDirection | null;
    entryPrice: number | null;
    stopLossPrice: number | null;
    takeProfitPrice: number | null;
    riskDollar: number | null;
    riskPercent: number;
    tradeReason: TradeReason | null;
    customReason: string;
}

interface PreTradeSanityGateProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (checklist: PreTradeChecklist) => void;
    currentPrice: number;
    accountSize: number;
    symbol: string;
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
    accent: '#2962ff',
};

const TRADE_REASONS: { value: TradeReason; label: string }[] = [
    { value: 'breakout', label: 'Breakout' },
    { value: 'pullback', label: 'Pullback' },
    { value: 'reversal', label: 'Reversal' },
    { value: 'mean_reversion', label: 'Mean Reversion' },
    { value: 'trend_continuation', label: 'Trend Continuation' },
    { value: 'other', label: 'Other' },
];

// =============================================================================
// COMPONENT
// =============================================================================

export function PreTradeSanityGate({
    isOpen,
    onClose,
    onConfirm,
    currentPrice,
    accountSize,
    symbol,
}: PreTradeSanityGateProps) {
    const [checklist, setChecklist] = useState<PreTradeChecklist>({
        direction: null,
        entryPrice: currentPrice,
        stopLossPrice: null,
        takeProfitPrice: null,
        riskDollar: null,
        riskPercent: 1,
        tradeReason: null,
        customReason: '',
    });

    const [step, setStep] = useState(1);
    const [errors, setErrors] = useState<Record<string, string>>({});

    // Calculate position sizing when we have all values
    const positioning = useMemo(() => {
        if (!checklist.entryPrice || !checklist.stopLossPrice) return null;

        const riskAmount = checklist.riskDollar ?? (accountSize * (checklist.riskPercent / 100));
        const riskPerShare = Math.abs(checklist.entryPrice - checklist.stopLossPrice);
        
        if (riskPerShare === 0) return null;

        const shares = Math.floor(riskAmount / riskPerShare);
        const positionValue = shares * checklist.entryPrice;
        
        const rewardRatio = checklist.takeProfitPrice 
            ? Math.abs(checklist.takeProfitPrice - checklist.entryPrice) / riskPerShare
            : 0;

        return {
            shares,
            positionValue,
            riskAmount,
            riskPerShare,
            rewardRatio,
        };
    }, [checklist, accountSize]);

    // Validation
    const validateStep = useCallback((currentStep: number): boolean => {
        const newErrors: Record<string, string> = {};

        switch (currentStep) {
            case 1:
                if (!checklist.direction) {
                    newErrors.direction = 'Select trade direction';
                }
                break;
            case 2:
                if (!checklist.stopLossPrice) {
                    newErrors.stopLossPrice = 'Enter stop-loss price';
                } else if (checklist.direction === 'long' && checklist.stopLossPrice >= (checklist.entryPrice ?? 0)) {
                    newErrors.stopLossPrice = 'Stop-loss must be below entry for long trades';
                } else if (checklist.direction === 'short' && checklist.stopLossPrice <= (checklist.entryPrice ?? 0)) {
                    newErrors.stopLossPrice = 'Stop-loss must be above entry for short trades';
                }
                break;
            case 3:
                if (checklist.riskPercent > 5) {
                    newErrors.riskPercent = 'Warning: Risk exceeds 5% of account';
                }
                break;
            case 4:
                if (!checklist.tradeReason) {
                    newErrors.tradeReason = 'Select a trade reason';
                }
                if (checklist.tradeReason === 'other' && !checklist.customReason.trim()) {
                    newErrors.customReason = 'Enter custom reason';
                }
                break;
        }

        setErrors(newErrors);
        return Object.keys(newErrors).filter(k => k !== 'riskPercent').length === 0;
    }, [checklist]);

    const handleNext = useCallback(() => {
        if (validateStep(step)) {
            if (step < 5) {
                setStep(step + 1);
            }
        }
    }, [step, validateStep]);

    const handleConfirm = useCallback(() => {
        if (validateStep(4)) {
            onConfirm(checklist);
            onClose();
        }
    }, [checklist, validateStep, onConfirm, onClose]);

    const updateChecklist = <K extends keyof PreTradeChecklist>(
        key: K,
        value: PreTradeChecklist[K]
    ) => {
        setChecklist(prev => ({ ...prev, [key]: value }));
        setErrors(prev => ({ ...prev, [key]: '' }));
    };

    if (!isOpen) return null;

    const renderStep = () => {
        switch (step) {
            case 1:
                return (
                    <div>
                        <h3 style={{ color: THEME.text, marginBottom: '16px', fontSize: '14px' }}>
                            Step 1: Trade Direction
                        </h3>
                        <div style={{ display: 'flex', gap: '12px' }}>
                            <button
                                onClick={() => updateChecklist('direction', 'long')}
                                style={{
                                    flex: 1,
                                    padding: '20px',
                                    background: checklist.direction === 'long' ? THEME.success : THEME.bgTertiary,
                                    border: `2px solid ${checklist.direction === 'long' ? THEME.success : THEME.border}`,
                                    borderRadius: '8px',
                                    color: checklist.direction === 'long' ? '#fff' : THEME.text,
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 600,
                                }}
                            >
                                ↑ LONG
                            </button>
                            <button
                                onClick={() => updateChecklist('direction', 'short')}
                                style={{
                                    flex: 1,
                                    padding: '20px',
                                    background: checklist.direction === 'short' ? THEME.danger : THEME.bgTertiary,
                                    border: `2px solid ${checklist.direction === 'short' ? THEME.danger : THEME.border}`,
                                    borderRadius: '8px',
                                    color: checklist.direction === 'short' ? '#fff' : THEME.text,
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 600,
                                }}
                            >
                                ↓ SHORT
                            </button>
                        </div>
                        {errors.direction && (
                            <div style={{ color: THEME.danger, fontSize: '12px', marginTop: '8px' }}>
                                {errors.direction}
                            </div>
                        )}
                    </div>
                );

            case 2:
                return (
                    <div>
                        <h3 style={{ color: THEME.text, marginBottom: '16px', fontSize: '14px' }}>
                            Step 2: Invalidation Level (Stop-Loss)
                        </h3>
                        <p style={{ color: THEME.textMuted, fontSize: '12px', marginBottom: '12px' }}>
                            At what price is this trade wrong?
                        </p>
                        
                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '11px', display: 'block', marginBottom: '4px' }}>
                                Entry Price
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                value={checklist.entryPrice ?? ''}
                                onChange={e => updateChecklist('entryPrice', parseFloat(e.target.value) || null)}
                                style={{
                                    width: '100%',
                                    padding: '10px',
                                    background: THEME.bg,
                                    border: `1px solid ${THEME.accent}`,
                                    borderRadius: '6px',
                                    color: THEME.accent,
                                    fontSize: '14px',
                                }}
                            />
                        </div>

                        <div>
                            <label style={{ color: THEME.textMuted, fontSize: '11px', display: 'block', marginBottom: '4px' }}>
                                Stop-Loss Price
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                value={checklist.stopLossPrice ?? ''}
                                onChange={e => updateChecklist('stopLossPrice', parseFloat(e.target.value) || null)}
                                style={{
                                    width: '100%',
                                    padding: '10px',
                                    background: THEME.bg,
                                    border: `1px solid ${errors.stopLossPrice ? THEME.danger : THEME.danger}`,
                                    borderRadius: '6px',
                                    color: THEME.danger,
                                    fontSize: '14px',
                                }}
                                placeholder={checklist.direction === 'long' ? 'Below entry price' : 'Above entry price'}
                            />
                            {errors.stopLossPrice && (
                                <div style={{ color: THEME.danger, fontSize: '11px', marginTop: '4px' }}>
                                    {errors.stopLossPrice}
                                </div>
                            )}
                        </div>
                    </div>
                );

            case 3:
                return (
                    <div>
                        <h3 style={{ color: THEME.text, marginBottom: '16px', fontSize: '14px' }}>
                            Step 3: Risk Size
                        </h3>
                        <p style={{ color: THEME.textMuted, fontSize: '12px', marginBottom: '12px' }}>
                            How much are you risking?
                        </p>

                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '11px', display: 'block', marginBottom: '4px' }}>
                                Risk Percentage of Account
                            </label>
                            <input
                                type="number"
                                step="0.1"
                                min="0.1"
                                max="10"
                                value={checklist.riskPercent}
                                onChange={e => updateChecklist('riskPercent', parseFloat(e.target.value) || 1)}
                                style={{
                                    width: '100%',
                                    padding: '10px',
                                    background: THEME.bg,
                                    border: `1px solid ${errors.riskPercent ? THEME.warning : THEME.border}`,
                                    borderRadius: '6px',
                                    color: THEME.text,
                                    fontSize: '14px',
                                }}
                            />
                            {errors.riskPercent && (
                                <div style={{ color: THEME.warning, fontSize: '11px', marginTop: '4px' }}>
                                    {errors.riskPercent}
                                </div>
                            )}
                        </div>

                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '11px', display: 'block', marginBottom: '4px' }}>
                                Take Profit (optional)
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                value={checklist.takeProfitPrice ?? ''}
                                onChange={e => updateChecklist('takeProfitPrice', parseFloat(e.target.value) || null)}
                                style={{
                                    width: '100%',
                                    padding: '10px',
                                    background: THEME.bg,
                                    border: `1px solid ${THEME.success}`,
                                    borderRadius: '6px',
                                    color: THEME.success,
                                    fontSize: '14px',
                                }}
                            />
                        </div>

                        {positioning && (
                            <div style={{
                                background: THEME.bgTertiary,
                                borderRadius: '6px',
                                padding: '12px',
                                marginTop: '16px',
                            }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px', marginBottom: '8px', textTransform: 'uppercase' }}>
                                    Calculated Position
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                                    <div>
                                        <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Shares</div>
                                        <div style={{ color: THEME.text, fontSize: '14px', fontWeight: 600 }}>{positioning.shares}</div>
                                    </div>
                                    <div>
                                        <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Risk Amount</div>
                                        <div style={{ color: THEME.danger, fontSize: '14px', fontWeight: 600 }}>
                                            ${positioning.riskAmount.toFixed(2)}
                                        </div>
                                    </div>
                                    {positioning.rewardRatio > 0 && (
                                        <div style={{ gridColumn: 'span 2' }}>
                                            <div style={{ color: THEME.textMuted, fontSize: '10px' }}>R:R Ratio</div>
                                            <div style={{ color: positioning.rewardRatio >= 1.5 ? THEME.success : THEME.warning, fontSize: '14px', fontWeight: 600 }}>
                                                {positioning.rewardRatio.toFixed(2)}:1
                                                {positioning.rewardRatio < 1.5 && ' ⚠️ Low R:R'}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                );

            case 4:
                return (
                    <div>
                        <h3 style={{ color: THEME.text, marginBottom: '16px', fontSize: '14px' }}>
                            Step 4: Trade Reason
                        </h3>
                        <p style={{ color: THEME.textMuted, fontSize: '12px', marginBottom: '12px' }}>
                            Why are you taking this trade?
                        </p>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                            {TRADE_REASONS.map(reason => (
                                <button
                                    key={reason.value}
                                    onClick={() => updateChecklist('tradeReason', reason.value)}
                                    style={{
                                        padding: '12px',
                                        background: checklist.tradeReason === reason.value ? THEME.accent : THEME.bgTertiary,
                                        border: `1px solid ${checklist.tradeReason === reason.value ? THEME.accent : THEME.border}`,
                                        borderRadius: '6px',
                                        color: checklist.tradeReason === reason.value ? '#fff' : THEME.text,
                                        cursor: 'pointer',
                                        fontSize: '12px',
                                    }}
                                >
                                    {reason.label}
                                </button>
                            ))}
                        </div>

                        {checklist.tradeReason === 'other' && (
                            <textarea
                                value={checklist.customReason}
                                onChange={e => updateChecklist('customReason', e.target.value)}
                                placeholder="Enter your trade reason..."
                                style={{
                                    width: '100%',
                                    marginTop: '12px',
                                    padding: '10px',
                                    background: THEME.bg,
                                    border: `1px solid ${THEME.border}`,
                                    borderRadius: '6px',
                                    color: THEME.text,
                                    fontSize: '12px',
                                    minHeight: '60px',
                                    resize: 'vertical',
                                }}
                            />
                        )}

                        {errors.tradeReason && (
                            <div style={{ color: THEME.danger, fontSize: '11px', marginTop: '8px' }}>
                                {errors.tradeReason}
                            </div>
                        )}
                    </div>
                );

            case 5:
                return (
                    <div>
                        <h3 style={{ color: THEME.text, marginBottom: '16px', fontSize: '14px' }}>
                            Confirm Trade
                        </h3>
                        
                        <div style={{
                            background: THEME.bgTertiary,
                            borderRadius: '8px',
                            padding: '16px',
                        }}>
                            <div style={{ marginBottom: '12px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Symbol</div>
                                <div style={{ color: THEME.text, fontSize: '16px', fontWeight: 600 }}>{symbol}</div>
                            </div>
                            
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                                <div>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Direction</div>
                                    <div style={{ 
                                        color: checklist.direction === 'long' ? THEME.success : THEME.danger, 
                                        fontSize: '14px', 
                                        fontWeight: 600 
                                    }}>
                                        {checklist.direction?.toUpperCase()}
                                    </div>
                                </div>
                                <div>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Entry</div>
                                    <div style={{ color: THEME.accent, fontSize: '14px', fontWeight: 600 }}>
                                        ${checklist.entryPrice?.toFixed(2)}
                                    </div>
                                </div>
                                <div>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Stop</div>
                                    <div style={{ color: THEME.danger, fontSize: '14px', fontWeight: 600 }}>
                                        ${checklist.stopLossPrice?.toFixed(2)}
                                    </div>
                                </div>
                                <div>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Target</div>
                                    <div style={{ color: THEME.success, fontSize: '14px', fontWeight: 600 }}>
                                        ${checklist.takeProfitPrice?.toFixed(2) ?? '-'}
                                    </div>
                                </div>
                                <div>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Position</div>
                                    <div style={{ color: THEME.text, fontSize: '14px', fontWeight: 600 }}>
                                        {positioning?.shares ?? 0} shares
                                    </div>
                                </div>
                                <div>
                                    <div style={{ color: THEME.textMuted, fontSize: '10px' }}>R:R</div>
                                    <div style={{ color: THEME.text, fontSize: '14px', fontWeight: 600 }}>
                                        {positioning?.rewardRatio.toFixed(1) ?? '-'}:1
                                    </div>
                                </div>
                            </div>

                            <div style={{ 
                                marginTop: '16px', 
                                padding: '12px', 
                                background: THEME.danger, 
                                borderRadius: '6px',
                                textAlign: 'center'
                            }}>
                                <div style={{ color: 'rgba(255,255,255,0.8)', fontSize: '10px', marginBottom: '2px' }}>
                                    MAX LOSS
                                </div>
                                <div style={{ color: '#fff', fontSize: '20px', fontWeight: 700 }}>
                                    ${positioning?.riskAmount.toFixed(2) ?? '0.00'}
                                </div>
                            </div>

                            <div style={{ marginTop: '12px' }}>
                                <div style={{ color: THEME.textMuted, fontSize: '10px' }}>Reason</div>
                                <div style={{ color: THEME.text, fontSize: '12px' }}>
                                    {checklist.tradeReason === 'other' ? checklist.customReason : 
                                     TRADE_REASONS.find(r => r.value === checklist.tradeReason)?.label}
                                </div>
                            </div>
                        </div>
                    </div>
                );
        }
    };

    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.8)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
            }}
            onClick={onClose}
        >
            <div
                style={{
                    width: '400px',
                    maxHeight: '90vh',
                    overflowY: 'auto',
                    background: THEME.bgSecondary,
                    border: `1px solid ${THEME.border}`,
                    borderRadius: '12px',
                    padding: '24px',
                }}
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <div>
                        <h2 style={{ color: THEME.text, margin: 0, fontSize: '16px', fontWeight: 600 }}>
                            Pre-Trade Checklist
                        </h2>
                        <div style={{ color: THEME.textMuted, fontSize: '12px', marginTop: '4px' }}>
                            {symbol} @ ${currentPrice.toFixed(2)}
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: THEME.textMuted,
                            cursor: 'pointer',
                            fontSize: '20px',
                        }}
                    >
                        ×
                    </button>
                </div>

                {/* Progress Steps */}
                <div style={{ display: 'flex', gap: '4px', marginBottom: '24px' }}>
                    {[1, 2, 3, 4, 5].map(s => (
                        <div
                            key={s}
                            style={{
                                flex: 1,
                                height: '4px',
                                background: s <= step ? THEME.accent : THEME.bgTertiary,
                                borderRadius: '2px',
                            }}
                        />
                    ))}
                </div>

                {/* Step Content */}
                {renderStep()}

                {/* Navigation */}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '24px' }}>
                    {step > 1 ? (
                        <button
                            onClick={() => setStep(step - 1)}
                            style={{
                                padding: '10px 20px',
                                background: THEME.bgTertiary,
                                border: `1px solid ${THEME.border}`,
                                borderRadius: '6px',
                                color: THEME.text,
                                cursor: 'pointer',
                                fontSize: '13px',
                            }}
                        >
                            ← Back
                        </button>
                    ) : (
                        <button
                            onClick={onClose}
                            style={{
                                padding: '10px 20px',
                                background: THEME.bgTertiary,
                                border: `1px solid ${THEME.border}`,
                                borderRadius: '6px',
                                color: THEME.text,
                                cursor: 'pointer',
                                fontSize: '13px',
                            }}
                        >
                            Cancel Trade
                        </button>
                    )}

                    {step < 5 ? (
                        <button
                            onClick={handleNext}
                            style={{
                                padding: '10px 24px',
                                background: THEME.accent,
                                border: 'none',
                                borderRadius: '6px',
                                color: '#fff',
                                cursor: 'pointer',
                                fontSize: '13px',
                                fontWeight: 600,
                            }}
                        >
                            Next →
                        </button>
                    ) : (
                        <button
                            onClick={handleConfirm}
                            style={{
                                padding: '10px 24px',
                                background: THEME.success,
                                border: 'none',
                                borderRadius: '6px',
                                color: '#fff',
                                cursor: 'pointer',
                                fontSize: '13px',
                                fontWeight: 600,
                            }}
                        >
                            ✓ Execute Trade
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

export default PreTradeSanityGate;
