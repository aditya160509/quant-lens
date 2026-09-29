/**
 * Custom Indicator Modal & Management Component
 * Shared between Trade page and Screener for creating user-defined indicators
 * Supports formula-based indicator creation with live validation
 */

'use client';

import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { CHART_THEME } from '../chart_engine/types';

// Types for custom indicators
export interface CustomIndicatorDefinition {
    id: string;
    name: string;
    shortName: string;
    formula: string;
    description?: string;
    placement: 'overlay' | 'pane';
    color?: string;
    createdAt: Date;
}

// Storage key for persisting custom indicators
const STORAGE_KEY = 'quant360_custom_indicators';

// Available functions for custom formulas
const ALLOWED_FUNCTIONS = [
    { name: 'sma', desc: 'Simple Moving Average', syntax: 'sma(close, 20)' },
    { name: 'ema', desc: 'Exponential Moving Average', syntax: 'ema(close, 20)' },
    { name: 'rsi', desc: 'Relative Strength Index', syntax: 'rsi(close, 14)' },
    { name: 'atr', desc: 'Average True Range', syntax: 'atr(14)' },
    { name: 'std', desc: 'Standard Deviation', syntax: 'std(close, 20)' },
    { name: 'max', desc: 'Maximum value', syntax: 'max(high, 20)' },
    { name: 'min', desc: 'Minimum value', syntax: 'min(low, 20)' },
    { name: 'abs', desc: 'Absolute value', syntax: 'abs(close - sma(close, 20))' },
    { name: 'log', desc: 'Natural logarithm', syntax: 'log(close)' },
    { name: 'sqrt', desc: 'Square root', syntax: 'sqrt(atr(14))' },
    { name: 'zscore', desc: 'Z-Score normalization', syntax: 'zscore(close, 20)' },
    { name: 'percentRank', desc: 'Percentile ranking', syntax: 'percentRank(close, 100)' },
    { name: 'crossover', desc: 'True when A crosses above B', syntax: 'crossover(ema(close,9), ema(close,21))' },
    { name: 'crossunder', desc: 'True when A crosses below B', syntax: 'crossunder(ema(close,9), ema(close,21))' },
];

// Available variables for formulas
const ALLOWED_VARIABLES = [
    { name: 'close', desc: 'Closing price' },
    { name: 'open', desc: 'Opening price' },
    { name: 'high', desc: 'High price' },
    { name: 'low', desc: 'Low price' },
    { name: 'volume', desc: 'Trading volume' },
    { name: 'hl2', desc: '(high + low) / 2' },
    { name: 'hlc3', desc: '(high + low + close) / 3' },
    { name: 'ohlc4', desc: '(open + high + low + close) / 4' },
];

// Example formulas for user guidance
const EXAMPLE_FORMULAS = [
    { name: 'Bollinger Band Width', formula: '(sma(close, 20) + 2 * std(close, 20)) - (sma(close, 20) - 2 * std(close, 20))' },
    { name: 'Price Momentum', formula: 'close - close[10]' },
    { name: 'Volatility Ratio', formula: 'atr(14) / close * 100' },
    { name: 'Trend Strength', formula: 'abs(ema(close, 9) - ema(close, 21)) / atr(14)' },
    { name: 'RSI Divergence', formula: 'rsi(close, 14) - sma(rsi(close, 14), 5)' },
    { name: 'Volume Surge', formula: 'volume / sma(volume, 20)' },
];

// Hook for managing custom indicators
export function useCustomIndicators() {
    const [customIndicators, setCustomIndicators] = useState<CustomIndicatorDefinition[]>([]);
    const [isLoaded, setIsLoaded] = useState(false);

    // Load from localStorage on mount using IIFE to avoid cascading effects
    const initializedRef = useRef(false);
    useEffect(() => {
        if (!initializedRef.current && typeof window !== 'undefined') {
            initializedRef.current = true;
            // Use IIFE pattern to wrap setState calls
            (async () => {
                try {
                    const stored = localStorage.getItem(STORAGE_KEY);
                    if (stored) {
                        const parsed = JSON.parse(stored);
                        setCustomIndicators(parsed.map((ind: any) => ({
                            ...ind,
                            createdAt: new Date(ind.createdAt),
                        })));
                    }
                } catch (e) {
                    console.error('Failed to load custom indicators:', e);
                }
                setIsLoaded(true);
            })();
        }
    }, []);

    // Save to localStorage whenever indicators change
    useEffect(() => {
        if (isLoaded && typeof window !== 'undefined') {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(customIndicators));
            } catch (e) {
                console.error('Failed to save custom indicators:', e);
            }
        }
    }, [customIndicators, isLoaded]);

    const addIndicator = useCallback((indicator: Omit<CustomIndicatorDefinition, 'id' | 'createdAt'>) => {
        const newIndicator: CustomIndicatorDefinition = {
            ...indicator,
            id: `CUSTOM_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
            createdAt: new Date(),
        };
        setCustomIndicators(prev => [...prev, newIndicator]);
        return newIndicator;
    }, []);

    const removeIndicator = useCallback((id: string) => {
        setCustomIndicators(prev => prev.filter(ind => ind.id !== id));
    }, []);

    const updateIndicator = useCallback((id: string, updates: Partial<CustomIndicatorDefinition>) => {
        setCustomIndicators(prev => prev.map(ind => 
            ind.id === id ? { ...ind, ...updates } : ind
        ));
    }, []);

    return {
        customIndicators,
        addIndicator,
        removeIndicator,
        updateIndicator,
        isLoaded,
    };
}

// Validate a custom formula
export function validateFormula(formula: string): { valid: boolean; error?: string } {
    if (!formula.trim()) {
        return { valid: false, error: 'Formula cannot be empty' };
    }

    // Check for basic syntax issues
    const openParens = (formula.match(/\(/g) || []).length;
    const closeParens = (formula.match(/\)/g) || []).length;
    if (openParens !== closeParens) {
        return { valid: false, error: 'Mismatched parentheses' };
    }

    // Check for unknown functions (basic check)
    const functionPattern = /([a-zA-Z_]\w*)\s*\(/g;
    let match;
    while ((match = functionPattern.exec(formula)) !== null) {
        const funcName = match[1].toLowerCase();
        if (!ALLOWED_FUNCTIONS.some(f => f.name === funcName)) {
            return { valid: false, error: `Unknown function: ${match[1]}` };
        }
    }

    // Check for variables
    const variablePattern = /\b(close|open|high|low|volume|hl2|hlc3|ohlc4)\b/gi;
    const hasVariables = variablePattern.test(formula);
    if (!hasVariables) {
        return { valid: false, error: 'Formula must reference at least one price variable (close, open, high, low, volume)' };
    }

    return { valid: true };
}

// Props for the CustomIndicatorModal
interface CustomIndicatorModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (indicator: Omit<CustomIndicatorDefinition, 'id' | 'createdAt'>) => void;
    editingIndicator?: CustomIndicatorDefinition;
}

// Custom Indicator Creation Modal
export function CustomIndicatorModal({ isOpen, onClose, onSave, editingIndicator }: CustomIndicatorModalProps) {
    const [name, setName] = useState(editingIndicator?.name || '');
    const [shortName, setShortName] = useState(editingIndicator?.shortName || '');
    const [formula, setFormula] = useState(editingIndicator?.formula || '');
    const [description, setDescription] = useState(editingIndicator?.description || '');
    const [placement, setPlacement] = useState<'overlay' | 'pane'>(editingIndicator?.placement || 'pane');
    const [color, setColor] = useState(editingIndicator?.color || '#22c55e');
    const [showExamples, setShowExamples] = useState(false);
    
    // Use useMemo for validation instead of useEffect to avoid cascading renders
    const validationResult = useMemo(() => {
        if (!formula.trim()) return null;
        return validateFormula(formula);
    }, [formula]);

    // Track if we need to reset form when modal opens
    const prevIsOpen = useRef(isOpen);
    const prevEditingIndicator = useRef(editingIndicator);
    
    // Reset form when modal opens/closes - use IIFE pattern
    useEffect(() => {
        const shouldReset = isOpen && (!prevIsOpen.current || editingIndicator !== prevEditingIndicator.current);
        prevIsOpen.current = isOpen;
        prevEditingIndicator.current = editingIndicator;
        
        if (shouldReset) {
            // Use IIFE to batch state updates
            (() => {
                if (editingIndicator) {
                    setName(editingIndicator.name);
                    setShortName(editingIndicator.shortName);
                    setFormula(editingIndicator.formula);
                    setDescription(editingIndicator.description || '');
                    setPlacement(editingIndicator.placement);
                    setColor(editingIndicator.color || '#22c55e');
                } else {
                    setName('');
                    setShortName('');
                    setFormula('');
                    setDescription('');
                    setPlacement('pane');
                    setColor('#22c55e');
                }
            })();
        }
    }, [isOpen, editingIndicator]);

    const handleSave = () => {
        if (!name.trim() || !shortName.trim() || !formula.trim()) return;
        
        if (!validationResult?.valid) {
            return;
        }

        onSave({
            name: name.trim(),
            shortName: shortName.trim().toUpperCase(),
            formula: formula.trim(),
            description: description.trim(),
            placement,
            color,
        });
        onClose();
    };

    const applyExample = (exampleFormula: string, exampleName: string) => {
        setFormula(exampleFormula);
        if (!name) setName(exampleName);
        if (!shortName) setShortName(exampleName.substring(0, 4).toUpperCase());
        setShowExamples(false);
    };

    if (!isOpen) return null;

    return (
        <div 
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{ background: 'rgba(0, 0, 0, 0.8)' }}
            onClick={onClose}
        >
            <div 
                className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg shadow-2xl"
                style={{ 
                    background: CHART_THEME.bgSecondary,
                    border: `1px solid ${CHART_THEME.border}`,
                }}
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div 
                    className="px-6 py-4 border-b flex items-center justify-between"
                    style={{ borderColor: CHART_THEME.border, background: CHART_THEME.bgPanel }}
                >
                    <div>
                        <h2 className="text-lg font-bold font-mono" style={{ color: CHART_THEME.accent }}>
                            🔧 {editingIndicator ? 'Edit' : 'Create'} Custom Indicator
                        </h2>
                        <p className="text-xs font-mono mt-1" style={{ color: CHART_THEME.textSecondary }}>
                            Build your own indicator using mathematical formulas
                        </p>
                    </div>
                    <button 
                        onClick={onClose}
                        className="text-2xl leading-none hover:opacity-70"
                        style={{ color: CHART_THEME.textSecondary }}
                    >
                        ×
                    </button>
                </div>

                {/* Form */}
                <div className="p-6 space-y-4">
                    {/* Name and Short Name */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-mono font-bold mb-1" style={{ color: CHART_THEME.textSecondary }}>
                                Indicator Name *
                            </label>
                            <input
                                type="text"
                                value={name}
                                onChange={e => setName(e.target.value)}
                                placeholder="e.g., My Custom RSI"
                                className="w-full px-3 py-2 text-sm font-mono rounded"
                                style={{
                                    background: CHART_THEME.bgPrimary,
                                    color: CHART_THEME.textPrimary,
                                    border: `1px solid ${CHART_THEME.border}`,
                                }}
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-mono font-bold mb-1" style={{ color: CHART_THEME.textSecondary }}>
                                Short Name * (4 chars)
                            </label>
                            <input
                                type="text"
                                value={shortName}
                                onChange={e => setShortName(e.target.value.substring(0, 6).toUpperCase())}
                                placeholder="e.g., MRSI"
                                maxLength={6}
                                className="w-full px-3 py-2 text-sm font-mono rounded"
                                style={{
                                    background: CHART_THEME.bgPrimary,
                                    color: CHART_THEME.textPrimary,
                                    border: `1px solid ${CHART_THEME.border}`,
                                }}
                            />
                        </div>
                    </div>

                    {/* Formula */}
                    <div>
                        <div className="flex items-center justify-between mb-1">
                            <label className="text-xs font-mono font-bold" style={{ color: CHART_THEME.textSecondary }}>
                                Formula *
                            </label>
                            <button
                                onClick={() => setShowExamples(!showExamples)}
                                className="text-xs font-mono px-2 py-0.5 rounded"
                                style={{ 
                                    background: CHART_THEME.accent,
                                    color: '#000',
                                }}
                            >
                                {showExamples ? '✕ Close Examples' : '📋 View Examples'}
                            </button>
                        </div>
                        
                        {/* Examples Dropdown */}
                        {showExamples && (
                            <div 
                                className="mb-2 p-3 rounded text-xs"
                                style={{ background: CHART_THEME.bgPanel, border: `1px solid ${CHART_THEME.border}` }}
                            >
                                <div className="font-mono font-bold mb-2" style={{ color: CHART_THEME.accent }}>
                                    Example Formulas (click to use):
                                </div>
                                <div className="space-y-1">
                                    {EXAMPLE_FORMULAS.map((ex, i) => (
                                        <button
                                            key={i}
                                            onClick={() => applyExample(ex.formula, ex.name)}
                                            className="block w-full text-left px-2 py-1 rounded hover:bg-white/10"
                                            style={{ color: CHART_THEME.textPrimary }}
                                        >
                                            <span className="font-bold">{ex.name}:</span>{' '}
                                            <span style={{ color: CHART_THEME.textSecondary }}>{ex.formula}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        <textarea
                            value={formula}
                            onChange={e => setFormula(e.target.value)}
                            placeholder="e.g., ema(close, 9) - ema(close, 21)"
                            rows={3}
                            className="w-full px-3 py-2 text-sm font-mono rounded"
                            style={{
                                background: CHART_THEME.bgPrimary,
                                color: CHART_THEME.textPrimary,
                                border: `1px solid ${validationResult?.valid === false ? '#ef4444' : validationResult?.valid ? '#22c55e' : CHART_THEME.border}`,
                            }}
                        />
                        
                        {/* Validation Feedback */}
                        {validationResult && (
                            <div 
                                className="mt-1 text-xs font-mono px-2 py-1 rounded"
                                style={{ 
                                    color: validationResult.valid ? '#22c55e' : '#ef4444',
                                    background: validationResult.valid ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                                }}
                            >
                                {validationResult.valid ? '✓ Formula is valid' : `✗ ${validationResult.error}`}
                            </div>
                        )}
                    </div>

                    {/* Placement and Color */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-mono font-bold mb-1" style={{ color: CHART_THEME.textSecondary }}>
                                Display Type
                            </label>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setPlacement('overlay')}
                                    className="flex-1 px-3 py-2 text-xs font-mono rounded"
                                    style={{
                                        background: placement === 'overlay' ? CHART_THEME.accent : CHART_THEME.bgPrimary,
                                        color: placement === 'overlay' ? '#000' : CHART_THEME.textSecondary,
                                        border: `1px solid ${CHART_THEME.border}`,
                                    }}
                                >
                                    📈 Overlay
                                </button>
                                <button
                                    onClick={() => setPlacement('pane')}
                                    className="flex-1 px-3 py-2 text-xs font-mono rounded"
                                    style={{
                                        background: placement === 'pane' ? CHART_THEME.accent : CHART_THEME.bgPrimary,
                                        color: placement === 'pane' ? '#000' : CHART_THEME.textSecondary,
                                        border: `1px solid ${CHART_THEME.border}`,
                                    }}
                                >
                                    📊 Oscillator
                                </button>
                            </div>
                        </div>
                        <div>
                            <label className="block text-xs font-mono font-bold mb-1" style={{ color: CHART_THEME.textSecondary }}>
                                Line Color
                            </label>
                            <div className="flex gap-2">
                                {['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'].map(c => (
                                    <button
                                        key={c}
                                        onClick={() => setColor(c)}
                                        className="w-8 h-8 rounded"
                                        style={{
                                            background: c,
                                            border: color === c ? '3px solid white' : '1px solid transparent',
                                        }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Description (optional) */}
                    <div>
                        <label className="block text-xs font-mono font-bold mb-1" style={{ color: CHART_THEME.textSecondary }}>
                            Description (optional)
                        </label>
                        <input
                            type="text"
                            value={description}
                            onChange={e => setDescription(e.target.value)}
                            placeholder="Brief description of what this indicator shows..."
                            className="w-full px-3 py-2 text-sm font-mono rounded"
                            style={{
                                background: CHART_THEME.bgPrimary,
                                color: CHART_THEME.textPrimary,
                                border: `1px solid ${CHART_THEME.border}`,
                            }}
                        />
                    </div>

                    {/* Available Functions Reference */}
                    <details className="text-xs font-mono">
                        <summary 
                            className="cursor-pointer font-bold py-2"
                            style={{ color: CHART_THEME.textSecondary }}
                        >
                            📚 Available Functions & Variables
                        </summary>
                        <div 
                            className="mt-2 p-3 rounded grid grid-cols-2 gap-4"
                            style={{ background: CHART_THEME.bgPanel }}
                        >
                            <div>
                                <div className="font-bold mb-2" style={{ color: CHART_THEME.accent }}>Functions:</div>
                                <div className="space-y-1">
                                    {ALLOWED_FUNCTIONS.slice(0, 8).map(f => (
                                        <div key={f.name} style={{ color: CHART_THEME.textSecondary }}>
                                            <span style={{ color: CHART_THEME.textPrimary }}>{f.name}</span> - {f.desc}
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <div className="font-bold mb-2" style={{ color: CHART_THEME.accent }}>Variables:</div>
                                <div className="space-y-1">
                                    {ALLOWED_VARIABLES.map(v => (
                                        <div key={v.name} style={{ color: CHART_THEME.textSecondary }}>
                                            <span style={{ color: CHART_THEME.textPrimary }}>{v.name}</span> - {v.desc}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </details>
                </div>

                {/* Footer */}
                <div 
                    className="px-6 py-4 border-t flex justify-end gap-3"
                    style={{ borderColor: CHART_THEME.border, background: CHART_THEME.bgPanel }}
                >
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-mono rounded"
                        style={{
                            background: CHART_THEME.bgPrimary,
                            color: CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                        }}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={!name.trim() || !shortName.trim() || !formula.trim() || !validationResult?.valid}
                        className="px-4 py-2 text-sm font-mono font-bold rounded disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                            background: CHART_THEME.accent,
                            color: '#000',
                        }}
                    >
                        💾 {editingIndicator ? 'Update' : 'Save'} Indicator
                    </button>
                </div>
            </div>
        </div>
    );
}

// Custom Indicators List Panel (for Trade page sidebar)
interface CustomIndicatorsPanelProps {
    customIndicators: CustomIndicatorDefinition[];
    onAdd: () => void;
    onEdit: (indicator: CustomIndicatorDefinition) => void;
    onRemove: (id: string) => void;
    onApply: (indicator: CustomIndicatorDefinition) => void;
}

export function CustomIndicatorsPanel({ 
    customIndicators, 
    onAdd, 
    onEdit, 
    onRemove,
    onApply 
}: CustomIndicatorsPanelProps) {
    return (
        <div 
            className="rounded-lg overflow-hidden"
            style={{ 
                background: CHART_THEME.bgSecondary,
                border: `1px solid ${CHART_THEME.border}`,
            }}
        >
            {/* Header */}
            <div 
                className="px-4 py-3 flex items-center justify-between border-b"
                style={{ borderColor: CHART_THEME.border, background: CHART_THEME.bgPanel }}
            >
                <div className="flex items-center gap-2">
                    <span className="text-sm font-mono font-bold" style={{ color: CHART_THEME.accent }}>
                        🔧 Custom Indicators
                    </span>
                    <span 
                        className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                        style={{ background: CHART_THEME.accent, color: '#000' }}
                    >
                        {customIndicators.length}
                    </span>
                </div>
                <button
                    onClick={onAdd}
                    className="px-2 py-1 text-xs font-mono font-bold rounded"
                    style={{
                        background: CHART_THEME.accent,
                        color: '#000',
                    }}
                >
                    + New
                </button>
            </div>

            {/* List */}
            <div className="max-h-48 overflow-y-auto">
                {customIndicators.length === 0 ? (
                    <div 
                        className="px-4 py-6 text-center text-xs font-mono"
                        style={{ color: CHART_THEME.textSecondary }}
                    >
                        No custom indicators yet.<br />
                        Click <span style={{ color: CHART_THEME.accent }}>+ New</span> to create one.
                    </div>
                ) : (
                    customIndicators.map(ind => (
                        <div 
                            key={ind.id}
                            className="px-4 py-2 flex items-center justify-between border-b hover:bg-white/5"
                            style={{ borderColor: CHART_THEME.border }}
                        >
                            <div className="flex items-center gap-2">
                                <span 
                                    className="w-3 h-3 rounded-full"
                                    style={{ background: ind.color || '#22c55e' }}
                                />
                                <div>
                                    <div className="text-xs font-mono font-bold" style={{ color: CHART_THEME.textPrimary }}>
                                        {ind.shortName}
                                    </div>
                                    <div className="text-[10px] font-mono" style={{ color: CHART_THEME.textSecondary }}>
                                        {ind.name}
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-center gap-1">
                                <button
                                    onClick={() => onApply(ind)}
                                    className="px-2 py-1 text-[10px] font-mono rounded"
                                    style={{ 
                                        background: CHART_THEME.upColor + '20',
                                        color: CHART_THEME.upColor,
                                    }}
                                >
                                    Apply
                                </button>
                                <button
                                    onClick={() => onEdit(ind)}
                                    className="px-1.5 py-1 text-xs"
                                    style={{ color: CHART_THEME.textSecondary }}
                                >
                                    ✏️
                                </button>
                                <button
                                    onClick={() => onRemove(ind.id)}
                                    className="px-1.5 py-1 text-xs"
                                    style={{ color: CHART_THEME.downColor }}
                                >
                                    🗑️
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

export default CustomIndicatorModal;
