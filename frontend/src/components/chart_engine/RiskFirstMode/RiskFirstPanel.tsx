'use client';

/**
 * Risk First Chart Mode
 * 
 * Per tradefeature.md §16:
 * - Toggle to prioritize risk visualization
 * - Stop-loss zone display
 * - Position sizing calculator
 * - R:R box overlay
 * - Prominent max loss display
 */

import React, { useState, useCallback, useMemo } from 'react';

// =============================================================================
// TYPES
// =============================================================================

export interface RiskParameters {
    accountSize: number;
    riskPercent: number; // 1 = 1%
    entryPrice: number;
    stopLossPrice: number;
    takeProfitPrices: number[]; // Can have multiple targets
}

export interface PositionSizing {
    shares: number;
    positionValue: number;
    riskAmount: number;
    riskPerShare: number;
    rewardRatio: number[];
}

interface RiskFirstModeProps {
    enabled: boolean;
    onToggle: () => void;
    parameters: RiskParameters;
    onParametersChange: (params: RiskParameters) => void;
    currentPrice?: number;
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

// =============================================================================
// POSITION SIZING CALCULATOR
// =============================================================================

export function calculatePositionSize(params: RiskParameters): PositionSizing {
    const { accountSize, riskPercent, entryPrice, stopLossPrice, takeProfitPrices } = params;
    
    const riskAmount = accountSize * (riskPercent / 100);
    const riskPerShare = Math.abs(entryPrice - stopLossPrice);
    
    if (riskPerShare === 0) {
        return {
            shares: 0,
            positionValue: 0,
            riskAmount,
            riskPerShare: 0,
            rewardRatio: [],
        };
    }
    
    const shares = Math.floor(riskAmount / riskPerShare);
    const positionValue = shares * entryPrice;
    
    const rewardRatio = takeProfitPrices.map(tp => {
        const reward = Math.abs(tp - entryPrice);
        return reward / riskPerShare;
    });
    
    return {
        shares,
        positionValue,
        riskAmount,
        riskPerShare,
        rewardRatio,
    };
}

// =============================================================================
// RISK FIRST PANEL
// =============================================================================

export function RiskFirstPanel({
    enabled,
    onToggle,
    parameters,
    onParametersChange,
    currentPrice = 0,
}: RiskFirstModeProps) {
    const [isExpanded, setIsExpanded] = useState(true);
    
    const sizing = useMemo(() => calculatePositionSize(parameters), [parameters]);
    
    const updateParam = useCallback(<K extends keyof RiskParameters>(
        key: K,
        value: RiskParameters[K]
    ) => {
        onParametersChange({ ...parameters, [key]: value });
    }, [parameters, onParametersChange]);
    
    const addTakeProfit = useCallback(() => {
        const lastTP = parameters.takeProfitPrices[parameters.takeProfitPrices.length - 1];
        const entry = parameters.entryPrice;
        const newTP = lastTP ? lastTP + (lastTP - entry) : entry * 1.02;
        updateParam('takeProfitPrices', [...parameters.takeProfitPrices, newTP]);
    }, [parameters, updateParam]);
    
    const removeTakeProfit = useCallback((index: number) => {
        updateParam('takeProfitPrices', parameters.takeProfitPrices.filter((_, i) => i !== index));
    }, [parameters, updateParam]);
    
    const updateTakeProfit = useCallback((index: number, value: number) => {
        const newTPs = [...parameters.takeProfitPrices];
        newTPs[index] = value;
        updateParam('takeProfitPrices', newTPs);
    }, [parameters, updateParam]);

    return (
        <div
            style={{
                position: 'absolute',
                top: '12px',
                right: '12px',
                width: isExpanded ? '280px' : 'auto',
                background: enabled ? 'rgba(239, 83, 80, 0.1)' : THEME.bgSecondary,
                border: `2px solid ${enabled ? THEME.danger : THEME.border}`,
                borderRadius: '8px',
                padding: isExpanded ? '16px' : '8px',
                zIndex: 100,
                backdropFilter: 'blur(8px)',
            }}
        >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: isExpanded ? '16px' : 0 }}>
                <button
                    onClick={onToggle}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '6px 12px',
                        background: enabled ? THEME.danger : 'transparent',
                        border: `1px solid ${enabled ? THEME.danger : THEME.border}`,
                        borderRadius: '4px',
                        color: enabled ? '#fff' : THEME.textMuted,
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: 600,
                    }}
                >
                    ⚠️ Risk First {enabled ? 'ON' : 'OFF'}
                </button>
                
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: THEME.textMuted,
                        cursor: 'pointer',
                        fontSize: '16px',
                        padding: '4px',
                    }}
                >
                    {isExpanded ? '−' : '+'}
                </button>
            </div>

            {isExpanded && enabled && (
                <>
                    {/* MAX LOSS DISPLAY */}
                    <div
                        style={{
                            background: THEME.danger,
                            borderRadius: '6px',
                            padding: '12px',
                            textAlign: 'center',
                            marginBottom: '16px',
                        }}
                    >
                        <div style={{ color: 'rgba(255,255,255,0.8)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>
                            MAX LOSS
                        </div>
                        <div style={{ color: '#fff', fontSize: '24px', fontWeight: 700 }}>
                            ${sizing.riskAmount.toFixed(2)}
                        </div>
                        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '11px' }}>
                            ({parameters.riskPercent}% of ${parameters.accountSize.toLocaleString()})
                        </div>
                    </div>

                    {/* Account Settings */}
                    <div style={{ marginBottom: '16px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                            <div>
                                <label style={{ color: THEME.textMuted, fontSize: '10px', display: 'block', marginBottom: '4px' }}>
                                    Account Size
                                </label>
                                <input
                                    type="number"
                                    value={parameters.accountSize}
                                    onChange={e => updateParam('accountSize', parseFloat(e.target.value) || 0)}
                                    style={{
                                        width: '100%',
                                        padding: '6px 8px',
                                        background: THEME.bg,
                                        border: `1px solid ${THEME.border}`,
                                        borderRadius: '4px',
                                        color: THEME.text,
                                        fontSize: '12px',
                                    }}
                                />
                            </div>
                            <div>
                                <label style={{ color: THEME.textMuted, fontSize: '10px', display: 'block', marginBottom: '4px' }}>
                                    Risk %
                                </label>
                                <input
                                    type="number"
                                    step="0.1"
                                    value={parameters.riskPercent}
                                    onChange={e => updateParam('riskPercent', parseFloat(e.target.value) || 0)}
                                    style={{
                                        width: '100%',
                                        padding: '6px 8px',
                                        background: THEME.bg,
                                        border: `1px solid ${THEME.border}`,
                                        borderRadius: '4px',
                                        color: THEME.text,
                                        fontSize: '12px',
                                    }}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Trade Levels */}
                    <div style={{ marginBottom: '16px' }}>
                        <div style={{ marginBottom: '8px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '10px', display: 'block', marginBottom: '4px' }}>
                                Entry Price
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                value={parameters.entryPrice}
                                onChange={e => updateParam('entryPrice', parseFloat(e.target.value) || 0)}
                                style={{
                                    width: '100%',
                                    padding: '6px 8px',
                                    background: THEME.bg,
                                    border: `1px solid ${THEME.accent}`,
                                    borderRadius: '4px',
                                    color: THEME.accent,
                                    fontSize: '12px',
                                }}
                            />
                        </div>
                        
                        <div style={{ marginBottom: '8px' }}>
                            <label style={{ color: THEME.textMuted, fontSize: '10px', display: 'block', marginBottom: '4px' }}>
                                Stop Loss
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                value={parameters.stopLossPrice}
                                onChange={e => updateParam('stopLossPrice', parseFloat(e.target.value) || 0)}
                                style={{
                                    width: '100%',
                                    padding: '6px 8px',
                                    background: THEME.bg,
                                    border: `1px solid ${THEME.danger}`,
                                    borderRadius: '4px',
                                    color: THEME.danger,
                                    fontSize: '12px',
                                }}
                            />
                        </div>
                        
                        {/* Take Profit Targets */}
                        <div style={{ marginBottom: '8px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                <label style={{ color: THEME.textMuted, fontSize: '10px' }}>
                                    Take Profit Targets
                                </label>
                                <button
                                    onClick={addTakeProfit}
                                    style={{
                                        background: 'transparent',
                                        border: `1px solid ${THEME.success}`,
                                        borderRadius: '3px',
                                        color: THEME.success,
                                        fontSize: '10px',
                                        padding: '2px 6px',
                                        cursor: 'pointer',
                                    }}
                                >
                                    + Add
                                </button>
                            </div>
                            {parameters.takeProfitPrices.map((tp, i) => (
                                <div key={i} style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={tp}
                                        onChange={e => updateTakeProfit(i, parseFloat(e.target.value) || 0)}
                                        style={{
                                            flex: 1,
                                            padding: '4px 6px',
                                            background: THEME.bg,
                                            border: `1px solid ${THEME.success}`,
                                            borderRadius: '4px',
                                            color: THEME.success,
                                            fontSize: '11px',
                                        }}
                                    />
                                    <span style={{ color: THEME.textMuted, fontSize: '10px', padding: '4px' }}>
                                        {sizing.rewardRatio[i]?.toFixed(1) || 0}R
                                    </span>
                                    <button
                                        onClick={() => removeTakeProfit(i)}
                                        style={{
                                            background: 'transparent',
                                            border: 'none',
                                            color: THEME.danger,
                                            cursor: 'pointer',
                                            fontSize: '12px',
                                        }}
                                    >
                                        ×
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Position Sizing Result */}
                    <div
                        style={{
                            background: THEME.bgTertiary,
                            borderRadius: '6px',
                            padding: '12px',
                        }}
                    >
                        <div style={{ color: THEME.textMuted, fontSize: '10px', textTransform: 'uppercase', marginBottom: '8px' }}>
                            Position Sizing
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                            <div>
                                <div style={{ color: THEME.textMuted, fontSize: '9px' }}>Shares</div>
                                <div style={{ color: THEME.text, fontSize: '14px', fontWeight: 600 }}>{sizing.shares}</div>
                            </div>
                            <div>
                                <div style={{ color: THEME.textMuted, fontSize: '9px' }}>Position Value</div>
                                <div style={{ color: THEME.text, fontSize: '14px', fontWeight: 600 }}>${sizing.positionValue.toLocaleString()}</div>
                            </div>
                            <div>
                                <div style={{ color: THEME.textMuted, fontSize: '9px' }}>Risk per Share</div>
                                <div style={{ color: THEME.danger, fontSize: '14px', fontWeight: 600 }}>${sizing.riskPerShare.toFixed(2)}</div>
                            </div>
                            <div>
                                <div style={{ color: THEME.textMuted, fontSize: '9px' }}>Best R:R</div>
                                <div style={{ color: THEME.success, fontSize: '14px', fontWeight: 600 }}>
                                    {Math.max(...(sizing.rewardRatio.length ? sizing.rewardRatio : [0])).toFixed(1)}:1
                                </div>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

// =============================================================================
// DEFAULT PARAMETERS
// =============================================================================

export const DEFAULT_RISK_PARAMETERS: RiskParameters = {
    accountSize: 100000,
    riskPercent: 1,
    entryPrice: 150,
    stopLossPrice: 147,
    takeProfitPrices: [156, 162],
};

export default RiskFirstPanel;
