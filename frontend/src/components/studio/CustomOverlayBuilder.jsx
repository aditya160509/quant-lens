"use client";
import React, { useState, useCallback, useMemo } from 'react';
import { Code2, Plus, Trash2, Play, Palette, ArrowUp, ArrowDown, PaintBucket, Save, FolderOpen } from 'lucide-react';

/**
 * Custom Overlay Builder (PineScript-Lite)
 * A UI builder for creating custom chart overlays with real condition evaluation.
 * 
 * Production-grade implementation:
 * - Generates real condition evaluator functions
 * - Reads and updates overlays through the workspace source of truth
 * - Provides actual overlay configurations for chart rendering
 */

// ============== CONDITION DEFINITIONS ==============

const CONDITION_TYPES = [
    { 
        id: 'close_above_ema', 
        label: 'Close > EMA(period)', 
        params: [{ key: 'period', type: 'number', default: 20, min: 2, max: 200 }],
        evaluate: (candles, idx, { period }) => {
            if (idx < period) return false;
            const ema = calculateEMA(candles, idx, period);
            return candles[idx].close > ema;
        }
    },
    { 
        id: 'close_below_ema', 
        label: 'Close < EMA(period)', 
        params: [{ key: 'period', type: 'number', default: 20, min: 2, max: 200 }],
        evaluate: (candles, idx, { period }) => {
            if (idx < period) return false;
            const ema = calculateEMA(candles, idx, period);
            return candles[idx].close < ema;
        }
    },
    { 
        id: 'close_above_sma', 
        label: 'Close > SMA(period)', 
        params: [{ key: 'period', type: 'number', default: 20, min: 2, max: 200 }],
        evaluate: (candles, idx, { period }) => {
            if (idx < period) return false;
            const sma = calculateSMA(candles, idx, period);
            return candles[idx].close > sma;
        }
    },
    { 
        id: 'close_below_sma', 
        label: 'Close < SMA(period)', 
        params: [{ key: 'period', type: 'number', default: 20, min: 2, max: 200 }],
        evaluate: (candles, idx, { period }) => {
            if (idx < period) return false;
            const sma = calculateSMA(candles, idx, period);
            return candles[idx].close < sma;
        }
    },
    { 
        id: 'volume_spike', 
        label: 'Volume > multiplier × AvgVol', 
        params: [{ key: 'multiplier', type: 'number', default: 2, min: 1, max: 10, step: 0.1 }],
        evaluate: (candles, idx, { multiplier }) => {
            if (idx < 20) return false;
            const avgVol = calculateAvgVolume(candles, idx, 20);
            return candles[idx].volume > avgVol * multiplier;
        }
    },
    { 
        id: 'rsi_below', 
        label: 'RSI < threshold', 
        params: [{ key: 'threshold', type: 'number', default: 30, min: 0, max: 100 }],
        evaluate: (candles, idx, { threshold }) => {
            if (idx < 14) return false;
            const rsi = calculateRSI(candles, idx, 14);
            return rsi < threshold;
        }
    },
    { 
        id: 'rsi_above', 
        label: 'RSI > threshold', 
        params: [{ key: 'threshold', type: 'number', default: 70, min: 0, max: 100 }],
        evaluate: (candles, idx, { threshold }) => {
            if (idx < 14) return false;
            const rsi = calculateRSI(candles, idx, 14);
            return rsi > threshold;
        }
    },
    { 
        id: 'price_above_high', 
        label: 'Close > Highest(days)', 
        params: [{ key: 'days', type: 'number', default: 20, min: 2, max: 200 }],
        evaluate: (candles, idx, { days }) => {
            if (idx < days) return false;
            let highest = -Infinity;
            for (let i = idx - days; i < idx; i++) {
                highest = Math.max(highest, candles[i].high);
            }
            return candles[idx].close > highest;
        }
    },
    { 
        id: 'price_below_low', 
        label: 'Close < Lowest(days)', 
        params: [{ key: 'days', type: 'number', default: 20, min: 2, max: 200 }],
        evaluate: (candles, idx, { days }) => {
            if (idx < days) return false;
            let lowest = Infinity;
            for (let i = idx - days; i < idx; i++) {
                lowest = Math.min(lowest, candles[i].low);
            }
            return candles[idx].close < lowest;
        }
    },
    { 
        id: 'gap_up', 
        label: 'Gap Up > percent%', 
        params: [{ key: 'percent', type: 'number', default: 1, min: 0.1, max: 20, step: 0.1 }],
        evaluate: (candles, idx, { percent }) => {
            if (idx < 1) return false;
            const gapPct = ((candles[idx].open - candles[idx - 1].close) / candles[idx - 1].close) * 100;
            return gapPct > percent;
        }
    },
    { 
        id: 'gap_down', 
        label: 'Gap Down > percent%', 
        params: [{ key: 'percent', type: 'number', default: 1, min: 0.1, max: 20, step: 0.1 }],
        evaluate: (candles, idx, { percent }) => {
            if (idx < 1) return false;
            const gapPct = ((candles[idx - 1].close - candles[idx].open) / candles[idx - 1].close) * 100;
            return gapPct > percent;
        }
    },
    { 
        id: 'bullish_bar', 
        label: 'Bullish Bar (Close > Open)', 
        params: [],
        evaluate: (candles, idx) => candles[idx].close > candles[idx].open
    },
    { 
        id: 'bearish_bar', 
        label: 'Bearish Bar (Close < Open)', 
        params: [],
        evaluate: (candles, idx) => candles[idx].close < candles[idx].open
    },
];

// Visual action types
const ACTION_TYPES = [
    { id: 'arrow_up', label: 'Arrow Up', icon: <ArrowUp size={12} /> },
    { id: 'arrow_down', label: 'Arrow Down', icon: <ArrowDown size={12} /> },
    { id: 'paint_bar', label: 'Paint Bar', icon: <PaintBucket size={12} /> },
    { id: 'background', label: 'Highlight BG', icon: <Palette size={12} /> },
];

const COLORS = [
    '#22c55e', '#10b981', '#06b6d4', '#3b82f6', '#8b5cf6',
    '#f43f5e', '#ef4444', '#f97316', '#eab308', '#ffd60a',
];

// ============== INDICATOR CALCULATIONS ==============

const calculateSMA = (candles, idx, period) => {
    let sum = 0;
    for (let i = 0; i < period && idx - i >= 0; i++) {
        sum += candles[idx - i].close;
    }
    return sum / period;
};

const calculateEMA = (candles, idx, period) => {
    const k = 2 / (period + 1);
    let ema = candles[Math.max(0, idx - period)].close;
    const start = Math.max(0, idx - period + 1);
    for (let i = start; i <= idx; i++) {
        ema = candles[i].close * k + ema * (1 - k);
    }
    return ema;
};

const calculateRSI = (candles, idx, period) => {
    let gains = 0, losses = 0;
    for (let i = 1; i <= period && idx - i >= 0; i++) {
        const change = candles[idx - i + 1].close - candles[idx - i].close;
        if (change > 0) gains += change;
        else losses -= change;
    }
    const avgGain = gains / period;
    const avgLoss = losses / period;
    if (avgLoss === 0) return 100;
    return 100 - (100 / (1 + avgGain / avgLoss));
};

const calculateAvgVolume = (candles, idx, period) => {
    let sum = 0;
    for (let i = 1; i <= period && idx - i >= 0; i++) {
        sum += candles[idx - i].volume;
    }
    return sum / period;
};

// ============== MAIN COMPONENT ==============

const CustomOverlayBuilder = ({ isOpen, onClose, onOverlayCreate, onOverlayDelete, existingOverlays = [] }) => {
    const [overlayName, setOverlayName] = useState('My Overlay');
    const [conditions, setConditions] = useState([]);
    const [logic, setLogic] = useState('AND'); // 'AND' or 'OR'
    const [action, setAction] = useState('arrow_up');
    const [actionColor, setActionColor] = useState('#ffd60a');
    const [placement, setPlacement] = useState('overlay'); // 'overlay' shares price scale, 'pane' separate pane (TradingView best)
    const [lineWidth, setLineWidth] = useState(1.5);
    const [opacity, setOpacity] = useState(100);
    const savedOverlays = existingOverlays;
    const [showSaved, setShowSaved] = useState(false);

    // Add a new condition
    const addCondition = useCallback(() => {
        const condType = CONDITION_TYPES[0];
        const defaultParams = {};
        condType.params.forEach(p => {
            defaultParams[p.key] = p.default;
        });
        
        setConditions(prev => [...prev, {
            id: Date.now(),
            type: condType.id,
            params: defaultParams
        }]);
    }, []);

    // Update condition type
    const updateConditionType = useCallback((id, newType) => {
        const condType = CONDITION_TYPES.find(c => c.id === newType);
        const defaultParams = {};
        condType?.params.forEach(p => {
            defaultParams[p.key] = p.default;
        });
        
        setConditions(prev => prev.map(c => 
            c.id === id ? { ...c, type: newType, params: defaultParams } : c
        ));
    }, []);

    // Update condition parameter
    const updateConditionParam = useCallback((id, paramKey, value) => {
        setConditions(prev => prev.map(c => 
            c.id === id ? { ...c, params: { ...c.params, [paramKey]: Number(value) } } : c
        ));
    }, []);

    // Remove condition
    const removeCondition = useCallback((id) => {
        setConditions(prev => prev.filter(c => c.id !== id));
    }, []);

    // Generate the overlay configuration — TradingView best: overlay vs pane + force_overlay
    const generateOverlay = useCallback(() => {
        if (conditions.length === 0) return;

        const overlay = {
            id: Date.now(),
            name: overlayName,
            conditions: conditions.map(c => ({
                type: c.type,
                params: c.params
            })),
            logic,
            action: { type: action, color: actionColor, lineWidth, opacity },
            placement, // 'overlay' shares price scale, 'pane' separate (TradingView)
            forceOverlay: placement === 'overlay',
            createdAt: new Date().toISOString()
        };

        onOverlayCreate?.(overlay);
        onClose?.();
    }, [overlayName, conditions, logic, action, actionColor, placement, lineWidth, opacity, onOverlayCreate, onClose]);

    // Load a saved overlay
    const loadOverlay = useCallback((overlay) => {
        setOverlayName(overlay.name);
        setConditions(overlay.conditions.map((c, i) => ({ ...c, id: Date.now() + i })));
        setLogic(overlay.logic);
        setAction(overlay.action.type);
        setActionColor(overlay.action.color);
        setPlacement(overlay.placement || 'overlay');
        setLineWidth(overlay.action.lineWidth || 1.5);
        setOpacity(overlay.action.opacity ?? 100);
        setShowSaved(false);
    }, []);

    // Delete a saved overlay
    const deleteOverlay = useCallback((id) => {
        onOverlayDelete?.(id);
    }, [onOverlayDelete]);

    // Generate human-readable rule description
    const ruleDescription = useMemo(() => {
        if (conditions.length === 0) return 'Add conditions to define your overlay';
        
        const parts = conditions.map(c => {
            const condType = CONDITION_TYPES.find(ct => ct.id === c.type);
            if (!condType) return '';
            
            let desc = condType.label;
            Object.entries(c.params).forEach(([key, val]) => {
                desc = desc.replace(new RegExp(key, 'gi'), val.toString());
            });
            return desc;
        });
        
        return parts.join(` ${logic} `);
    }, [conditions, logic]);

    if (!isOpen) return null;

    return (
        <div 
            className="fixed inset-0 z-[100] flex items-center justify-center"
            style={{ background: 'rgba(0, 0, 0, 0.85)', backdropFilter: 'blur(8px)' }}
            onClick={(e) => e.target === e.currentTarget && onClose?.()}
        >
            <div className="w-full max-w-xl mx-4 bg-[#0a0a0f] border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
                {/* Header */}
                <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-amber-500 flex items-center justify-center">
                            <Code2 size={20} className="text-white" />
                        </div>
                        <div>
                            <h2 className="text-sm font-bold text-white">Custom Overlay Builder</h2>
                            <p className="text-[10px] text-[#64748b] font-mono">Create visual signals from conditions</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button 
                            onClick={() => setShowSaved(!showSaved)}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-[9px] font-mono font-bold uppercase transition-all ${
                                showSaved ? 'bg-amber-500/20 text-amber-500' : 'bg-white/5 text-[#64748b] hover:text-white'
                            }`}
                        >
                            <FolderOpen size={12} />
                            Saved ({savedOverlays.length})
                        </button>
                        <button 
                            onClick={onClose}
                            className="text-[#64748b] hover:text-white p-2 rounded-lg hover:bg-white/5 transition-all"
                        >
                            ✕
                        </button>
                    </div>
                </div>

                {showSaved ? (
                    /* Saved Overlays List */
                    <div className="px-6 py-4 max-h-[400px] overflow-y-auto">
                        {savedOverlays.length === 0 ? (
                            <div className="py-8 text-center">
                                <FolderOpen size={24} className="mx-auto text-[#64748b]/30 mb-2" />
                                <p className="text-[10px] font-mono text-[#64748b]">No saved overlays</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {savedOverlays.map(overlay => (
                                    <div 
                                        key={overlay.id}
                                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5 hover:border-white/10 transition-all"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div 
                                                className="w-3 h-3 rounded-full"
                                                style={{ backgroundColor: overlay.action.color }}
                                            />
                                            <div>
                                                <div className="text-[11px] font-mono font-bold text-white">{overlay.name}</div>
                                                <div className="text-[9px] font-mono text-[#64748b]">
                                                    {overlay.conditions.length} condition{overlay.conditions.length !== 1 ? 's' : ''}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-1">
                                            <button
                                                onClick={() => loadOverlay(overlay)}
                                                className="px-2 py-1 text-[9px] font-mono text-amber-500 hover:bg-amber-500/10 rounded transition-all"
                                            >
                                                Load
                                            </button>
                                            <button
                                                onClick={() => deleteOverlay(overlay.id)}
                                                className="p-1 text-[#64748b] hover:text-red-500 rounded transition-all"
                                            >
                                                <Trash2 size={12} />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <>
                        {/* Overlay Name */}
                        <div className="px-6 py-3 border-b border-white/5">
                            <label className="text-[9px] font-mono text-[#64748b] uppercase tracking-wider mb-1 block">Overlay Name</label>
                            <input 
                                type="text"
                                value={overlayName}
                                onChange={(e) => setOverlayName(e.target.value)}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-amber-500/50"
                                placeholder="My Custom Overlay"
                            />
                        </div>

                        {/* Conditions Builder */}
                        <div className="px-6 py-4 border-b border-white/5 max-h-[250px] overflow-y-auto">
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-[9px] font-mono text-[#64748b] uppercase tracking-wider">Conditions</span>
                                <div className="flex items-center gap-2">
                                    <div className="flex items-center bg-white/5 rounded-lg p-0.5">
                                        {['AND', 'OR'].map(l => (
                                            <button
                                                key={l}
                                                onClick={() => setLogic(l)}
                                                className={`px-2 py-1 text-[9px] font-mono font-bold rounded transition-all ${
                                                    logic === l
                                                    ? 'bg-amber-500 text-black'
                                                    : 'text-[#64748b] hover:text-white'
                                                }`}
                                            >
                                                {l}
                                            </button>
                                        ))}
                                    </div>
                                    <button
                                        onClick={addCondition}
                                        className="flex items-center gap-1 px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded-lg text-[9px] font-mono font-bold hover:bg-emerald-500/30 transition-all"
                                    >
                                        <Plus size={11} /> Add
                                    </button>
                                </div>
                            </div>

                            {conditions.length === 0 ? (
                                <div className="py-6 text-center border border-dashed border-white/10 rounded-lg">
                                    <p className="text-[10px] font-mono text-[#64748b]">{'Click "Add" to create conditions'}</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {conditions.map((cond, idx) => {
                                        const condType = CONDITION_TYPES.find(c => c.id === cond.type);
                                        return (
                                            <div key={cond.id} className="flex items-center gap-2 p-2 bg-white/5 rounded-lg">
                                                {idx > 0 && (
                                                    <span className="text-[9px] font-mono font-bold text-amber-500 w-8">{logic}</span>
                                                )}
                                                {idx === 0 && <div className="w-8" />}
                                                
                                                <select
                                                    value={cond.type}
                                                    onChange={(e) => updateConditionType(cond.id, e.target.value)}
                                                    className="flex-1 bg-black/30 border border-white/10 rounded px-2 py-1.5 text-[10px] text-white font-mono focus:outline-none focus:border-amber-500/50"
                                                >
                                                    {CONDITION_TYPES.map(ct => (
                                                        <option key={ct.id} value={ct.id}>{ct.label}</option>
                                                    ))}
                                                </select>

                                                {condType?.params.map(param => (
                                                    <input
                                                        key={param.key}
                                                        type="number"
                                                        value={cond.params[param.key] ?? param.default}
                                                        onChange={(e) => updateConditionParam(cond.id, param.key, e.target.value)}
                                                        min={param.min}
                                                        max={param.max}
                                                        step={param.step || 1}
                                                        className="w-16 bg-black/30 border border-white/10 rounded px-2 py-1.5 text-[10px] text-white font-mono focus:outline-none focus:border-amber-500/50"
                                                    />
                                                ))}

                                                <button
                                                    onClick={() => removeCondition(cond.id)}
                                                    className="p-1.5 text-[#64748b] hover:text-red-500 hover:bg-red-500/10 rounded transition-all"
                                                >
                                                    <Trash2 size={12} />
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                        {/* Placement — TradingView best: overlay vs pane */}
                        <div className="px-6 py-3 border-b border-white/5 bg-amber-500/[0.03]">
                            <div className="flex items-center justify-between">
                                <span className="text-[9px] font-mono text-[#64748b] uppercase tracking-wider">Placement — TradingView best</span>
                                <span className="text-[8px] font-mono text-amber-500/70">{placement === 'overlay' ? 'shares price scale' : 'separate pane • force_overlay'}</span>
                            </div>
                            <div className="mt-2 flex gap-2">
                                {[
                                    { id: 'overlay', label: 'Overlay — price-scaled', desc: 'RVOL-style, on chart' },
                                    { id: 'pane', label: 'Pane — separate', desc: 'RSI-style, below chart' },
                                ].map((p) => (
                                    <button key={p.id} onClick={() => setPlacement(p.id)} className={`flex-1 p-2 rounded-lg border text-left ${placement === p.id ? 'bg-amber-500/10 border-amber-500/30' : 'bg-white/5 border-white/5 hover:border-white/10'}`}>
                                        <div className={`text-[10px] font-mono font-bold ${placement === p.id ? 'text-amber-500' : 'text-white'}`}>{p.label}</div>
                                        <div className="text-[8px] font-mono text-[#64748b]">{p.desc}</div>
                                    </button>
                                ))}
                            </div>
                            <div className="mt-3 grid grid-cols-2 gap-3">
                                <label className="text-[9px] font-mono text-[#64748b]">Line width
                                    <input type="range" min={1} max={4} step={0.5} value={lineWidth} onChange={(e) => setLineWidth(Number(e.target.value))} className="w-full accent-amber-500" />
                                </label>
                                <label className="text-[9px] font-mono text-[#64748b]">Opacity {opacity}%
                                    <input type="range" min={10} max={100} step={10} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} className="w-full accent-amber-500" />
                                </label>
                            </div>
                        </div>
                        {/* Action Selector */}
                        <div className="px-6 py-4 border-b border-white/5">
                            <span className="text-[9px] font-mono text-[#64748b] uppercase tracking-wider mb-3 block">Visual Action</span>
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-0.5 bg-white/5 rounded-lg p-0.5">
                                    {ACTION_TYPES.map(a => (
                                        <button
                                            key={a.id}
                                            onClick={() => setAction(a.id)}
                                            className={`flex items-center gap-1 px-2.5 py-1.5 rounded text-[9px] font-mono font-bold transition-all ${
                                                action === a.id
                                                ? 'bg-amber-500 text-black'
                                                : 'text-[#64748b] hover:text-white hover:bg-white/10'
                                            }`}
                                        >
                                            {a.icon}
                                            {a.label}
                                        </button>
                                    ))}
                                </div>
                                <div className="flex items-center gap-1">
                                    {COLORS.map(c => (
                                        <button
                                            key={c}
                                            onClick={() => setActionColor(c)}
                                            className={`w-5 h-5 rounded-full border-2 transition-all ${
                                                actionColor === c ? 'border-white scale-110' : 'border-transparent'
                                            }`}
                                            style={{ background: c }}
                                        />
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Preview */}
                        <div className="px-6 py-3 bg-white/[0.02]">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-[9px] font-mono text-amber-500 uppercase tracking-wider">Rule Preview</span>
                            </div>
                            <p className="text-[10px] font-mono text-white/80 bg-black/30 rounded-lg px-3 py-2 leading-relaxed">
                                <span className="text-amber-500">WHEN</span> {ruleDescription} <span className="text-amber-500">→</span> {ACTION_TYPES.find(a => a.id === action)?.label} <span style={{ color: actionColor }}>●</span>
                            </p>
                        </div>

                        {/* Footer */}
                        <div className="px-6 py-4 border-t border-white/5 flex items-center justify-end gap-3">
                            <button
                                onClick={onClose}
                                className="px-4 py-2 text-[10px] font-mono text-[#64748b] hover:text-white transition-all"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={generateOverlay}
                                disabled={conditions.length === 0}
                                className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-amber-500 to-orange-500 text-black font-bold text-[10px] font-mono uppercase tracking-wider rounded-lg hover:opacity-90 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                                <Save size={12} />
                                Save Overlay
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

/**
 * Evaluate an overlay configuration against candle data
 * Returns array of indices where conditions are met
 */
export const evaluateOverlay = (overlay, candles) => {
    if (!overlay || !candles || candles.length === 0) return [];
    
    const matches = [];
    
    for (let idx = 0; idx < candles.length; idx++) {
        let result;
        
        if (overlay.logic === 'AND') {
            result = overlay.conditions.every(cond => {
                const condType = CONDITION_TYPES.find(ct => ct.id === cond.type);
                return condType?.evaluate(candles, idx, cond.params) ?? false;
            });
        } else {
            result = overlay.conditions.some(cond => {
                const condType = CONDITION_TYPES.find(ct => ct.id === cond.type);
                return condType?.evaluate(candles, idx, cond.params) ?? false;
            });
        }
        
        if (result) {
            matches.push({
                index: idx,
                time: candles[idx].time,
                price: candles[idx].close,
                action: overlay.action
            });
        }
    }
    
    return matches;
};

export default CustomOverlayBuilder;
