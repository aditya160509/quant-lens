"use client";
import React, { useState, useRef, useCallback } from 'react';
import { X, Check, Search, Activity, TrendingUp, BarChart2, Zap } from 'lucide-react';
import { useStudioModalA11y } from './shell/useStudioModalA11y';

// Complete indicator library matching Trade page
const OVERLAYS = [
    { id: 'sma20', name: 'SMA 20', shortName: 'SMA', desc: 'Simple Moving Average', color: '#ffd60a', type: 'sma', period: 20 },
    { id: 'sma50', name: 'SMA 50', shortName: 'SMA', desc: 'Simple Moving Average', color: '#22c55e', type: 'sma', period: 50 },
    { id: 'sma200', name: 'SMA 200', shortName: 'SMA', desc: 'Simple Moving Average', color: '#ef4444', type: 'sma', period: 200 },
    { id: 'ema12', name: 'EMA 12', shortName: 'EMA', desc: 'Exponential Moving Average', color: '#8b5cf6', type: 'ema', period: 12 },
    { id: 'ema26', name: 'EMA 26', shortName: 'EMA', desc: 'Exponential Moving Average', color: '#06b6d4', type: 'ema', period: 26 },
    { id: 'ema50', name: 'EMA 50', shortName: 'EMA', desc: 'Exponential Moving Average', color: '#f97316', type: 'ema', period: 50 },
    { id: 'wma', name: 'WMA 20', shortName: 'WMA', desc: 'Weighted Moving Average', color: '#14b8a6', type: 'wma', period: 20 },
    { id: 'hullma', name: 'Hull MA', shortName: 'HMA', desc: 'Hull Moving Average', color: '#ec4899', type: 'hullma', period: 20 },
    { id: 'dema', name: 'DEMA', shortName: 'DEMA', desc: 'Double EMA', color: '#84cc16', type: 'dema', period: 20 },
    { id: 'tema', name: 'TEMA', shortName: 'TEMA', desc: 'Triple EMA', color: '#a855f7', type: 'tema', period: 20 },
    { id: 'bb', name: 'Bollinger Bands', shortName: 'BB', desc: '20 Period, 2 StdDev', color: '#a855f7', type: 'bollinger', period: 20, stddev: 2 },
    { id: 'keltner', name: 'Keltner Channel', shortName: 'KC', desc: 'ATR-based envelope', color: '#14b8a6', type: 'keltner', period: 20, atrMult: 2 },
    { id: 'donchian', name: 'Donchian Channel', shortName: 'DC', desc: '20-period high/low', color: '#f59e0b', type: 'donchian', period: 20 },
    { id: 'vwap', name: 'VWAP', shortName: 'VWAP', desc: 'Volume Weighted Avg Price', color: '#ec4899', type: 'vwap' },
    { id: 'supertrend', name: 'Supertrend', shortName: 'ST', desc: 'ATR-based trend', color: '#22c55e', type: 'supertrend', period: 10, multiplier: 3 },
    { id: 'sar', name: 'Parabolic SAR', shortName: 'SAR', desc: 'Stop and Reverse', color: '#fbbf24', type: 'sar' },
    { id: 'ichimoku', name: 'Ichimoku Cloud', shortName: 'ICHI', desc: 'Ichimoku Kinko Hyo', color: '#6366f1', type: 'ichimoku' },
    { id: 'emaRibbon', name: 'EMA Ribbon', shortName: 'RIB', desc: 'Multiple EMA lines', color: '#8b5cf6', type: 'emaRibbon' },
    { id: 'pivot', name: 'Pivot Points', shortName: 'PIV', desc: 'Support/Resistance', color: '#94a3b8', type: 'pivot' },
    { id: 'zigzag', name: 'ZigZag', shortName: 'ZZ', desc: 'Trend identification', color: '#f43f5e', type: 'zigzag' },
    { id: 'alligator', name: 'Williams Alligator', shortName: 'ALIG', desc: 'Teeth/Jaws/Lips', color: '#10b981', type: 'alligator' },
    { id: 'env', name: 'Envelopes', shortName: 'ENV', desc: 'Percentage based bands', color: '#6366f1', type: 'envelope', percent: 2.5 },
    { id: 'fibo', name: 'Fibonacci Pivots', shortName: 'FIBP', desc: 'Fibo-based support', color: '#f59e0b', type: 'fiboPivot' },
    { id: 'hma', name: 'Hull Moving Average', shortName: 'HMA', desc: 'Reduced lag MA', color: '#ec4899', type: 'hma', period: 20 },
];

const OSCILLATORS = [    { id: 'rsi', name: 'RSI', shortName: 'RSI', desc: 'Relative Strength Index', color: '#a855f7', type: 'rsi', period: 14 },
    { id: 'macd', name: 'MACD', shortName: 'MACD', desc: 'Moving Avg Convergence/Div', color: '#22c55e', type: 'macd', fast: 12, slow: 26, signal: 9 },
    { id: 'stoch', name: 'Stochastic', shortName: 'STOCH', desc: '%K/%D Oscillator', color: '#f59e0b', type: 'stochastic', kPeriod: 14, dPeriod: 3 },
    { id: 'atr', name: 'ATR', shortName: 'ATR', desc: 'Average True Range', color: '#ef4444', type: 'atr', period: 14 },
    { id: 'adx', name: 'ADX', shortName: 'ADX', desc: 'Average Directional Index', color: '#06b6d4', type: 'adx', period: 14 },
    { id: 'cci', name: 'CCI', shortName: 'CCI', desc: 'Commodity Channel Index', color: '#14b8a6', type: 'cci', period: 20 },
    { id: 'williamsR', name: 'Williams %R', shortName: '%R', desc: 'Williams Percent Range', color: '#f97316', type: 'williamsR', period: 14 },
    { id: 'roc', name: 'ROC', shortName: 'ROC', desc: 'Rate of Change', color: '#10b981', type: 'roc', period: 12 },
    { id: 'momentum', name: 'Momentum', shortName: 'MOM', desc: 'Price Momentum', color: '#8b5cf6', type: 'momentum', period: 10 },
    { id: 'obv', name: 'OBV', shortName: 'OBV', desc: 'On Balance Volume', color: '#3b82f6', type: 'obv' },
    { id: 'cmf', name: 'CMF', shortName: 'CMF', desc: 'Chaikin Money Flow', color: '#a855f7', type: 'cmf', period: 20 },
    { id: 'mfi', name: 'MFI', shortName: 'MFI', desc: 'Money Flow Index', color: '#ec4899', type: 'mfi', period: 14 },
    { id: 'trix', name: 'TRIX', shortName: 'TRIX', desc: 'Triple EMA Oscillator', color: '#06b6d4', type: 'trix', period: 15 },
    { id: 'ppo', name: 'PPO', shortName: 'PPO', desc: 'Percentage Price Osc', color: '#22c55e', type: 'ppo' },
    { id: 'ao', name: 'Awesome Osc', shortName: 'AO', desc: 'Awesome Oscillator', color: '#f43f5e', type: 'ao' },
    { id: 'ultimate', name: 'Ultimate Osc', shortName: 'UO', desc: 'Ultimate Oscillator', color: '#fbbf24', type: 'ultimate' },
    { id: 'dpo', name: 'DPO', shortName: 'DPO', desc: 'Detrended Price Osc', color: '#84cc16', type: 'dpo' },
    { id: 'aroon', name: 'Aroon', shortName: 'ARN', desc: 'Aroon Indicator', color: '#6366f1', type: 'aroon', period: 14 },
    { id: 'chop', name: 'Choppiness', shortName: 'CHOP', desc: 'Choppiness Index', color: '#f97316', type: 'chop', period: 14 },
    { id: 'force', name: 'Force Index', shortName: 'FI', desc: 'Force Index', color: '#14b8a6', type: 'force', period: 13 },
    { id: 'mass', name: 'Mass Index', shortName: 'MASS', desc: 'Volatility reversals', color: '#f43f5e', type: 'massIndex' },
    { id: 'coppock', name: 'Coppock Curve', shortName: 'COPP', desc: 'Long-term momentum', color: '#8b5cf6', type: 'coppock' },
    { id: 'stochRsi', name: 'Stoch RSI', shortName: 'SRSI', desc: 'Stochastic applied to RSI', color: '#a855f7', type: 'stochRsi' },
];

// ── P5-W3 preflight validators (pure, exported for tests) ───────────────
// Read backend data_quality fields truthfully. The backend currently reports
// corporate_actions="unknown" and look_ahead_check="not_verified" for every
// dataset, so these validators return explicit unknown/not-verified labels
// (warnings, never blocking) until real validators exist server-side.

// Pure: corporate-action adjustment status of the dataset.
export function validateCorporateActions(dataQuality) {
    const status = dataQuality?.corporate_actions || 'unknown';
    if (status === 'adjusted') return { status, blocking: false, message: 'Corporate actions: adjusted — splits/dividends applied.' };
    if (status === 'unadjusted') return { status, blocking: false, message: 'Corporate actions: unadjusted — prices may jump on splits/dividends; interpret returns with care.' };
    return { status: 'unknown', blocking: false, message: 'Corporate actions: unknown — no adjustment validator reported by the backend; do not assume split/dividend adjustment.' };
}

// Pure: look-ahead hazard check status of the dataset.
export function validateLookAhead(dataQuality) {
    const status = dataQuality?.look_ahead_check || 'not_verified';
    if (status === 'verified') return { status, blocking: false, message: 'Look-ahead: verified — point-in-time alignment checked.' };
    return { status: 'not_verified', blocking: false, message: 'Look-ahead: not verified — no point-in-time validator reported by the backend; signals may peek.' };
}

// Pure: timezone/currency/calendar wiring read from backend metadata.
export function validateMarketConventions(dataQuality) {
    return {
        timezone: dataQuality?.timezone || null,
        currency: dataQuality?.currency || null,
        calendar: dataQuality?.calendar || null,
        complete: Boolean(dataQuality?.timezone && dataQuality?.currency && dataQuality?.calendar),
    };
}

// Pure: full preflight assessment — blocking errors vs warnings.
export function assessPreflight(dataQuality, nowMs = Date.now()) {
    const blocking = [];
    if (dataQuality?.status !== 'observed') blocking.push(`Data status is "${dataQuality?.status || 'unavailable'}" — execution blocked until observed data is available.`);
    if (!Number.isFinite(dataQuality?.observations) || dataQuality.observations < 20) blocking.push(`Insufficient observations (${dataQuality?.observations ?? 0}) — need ≥20 bars.`);
    if (dataQuality?.missing_observations > 0) blocking.push(`Missing observations: ${dataQuality.missing_observations} — inspect gaps for survivorship bias.`);
    const warnings = [];
    if (dataQuality?.as_of) {
        const ageDays = Math.floor((nowMs - new Date(dataQuality.as_of).getTime()) / 86400000);
        if (ageDays > 2) warnings.push(`Staleness: as_of ${dataQuality.as_of} (${ageDays}d old) — verify corporate actions.`);
    }
    const ca = validateCorporateActions(dataQuality);
    if (ca.status !== 'adjusted') warnings.push(ca.message);
    const la = validateLookAhead(dataQuality);
    if (la.status !== 'verified') warnings.push(la.message);
    const conv = validateMarketConventions(dataQuality);
    if (!conv.complete) warnings.push('Market conventions incomplete — timezone, currency, or calendar missing from backend metadata.');
    return { blocking, warnings, corporateActions: ca, lookAhead: la, conventions: conv };
}

const PreExecuteModal = ({ 
    isOpen, 
    onClose, 
    onExecute,
    activeIndicators,
    addIndicator,
    removeIndicator,
    toggleIndicator,
    isGridMode = false,
    ticker,
    dataQuality,
}) => {
    const [activeTab, setActiveTab] = useState('overlays');
    const [search, setSearch] = useState('');
    const idCounter = useRef(0);
    const dialogRef = useRef(null);
    const { onKeyDownTrap } = useStudioModalA11y({ isOpen, onClose, dialogRef });
    
    const currentList = activeTab === 'overlays' ? OVERLAYS : OSCILLATORS;
    const filtered = currentList.filter(i => 
        i.name.toLowerCase().includes(search.toLowerCase()) ||
        i.shortName.toLowerCase().includes(search.toLowerCase()) ||
        i.desc.toLowerCase().includes(search.toLowerCase())
    );
    
    const handleToggle = useCallback((item) => {
        const existing = activeIndicators.find(o => o.indicatorId === item.id);
        if (existing) {
            removeIndicator(existing.id);
        } else {
            idCounter.current += 1;
            const timestamp = Date.now().toString(36);
            addIndicator({
                id: `${item.type}_${idCounter.current}_${timestamp}`,
                indicatorId: item.id,
                type: item.type,
                name: item.name,
                shortName: item.shortName,
                color: item.color,
                params: { ...item },
                visible: true,
                placement: activeTab === 'overlays' ? 'overlay' : 'pane'
            });
        }
    }, [activeIndicators, addIndicator, removeIndicator, activeTab]);
    
    const isActive = (id) => {
        return activeIndicators.some(o => o.indicatorId === id);
    };
    
    if (!isOpen) return null;
    
    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
            <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="pre-execute-title" onKeyDown={onKeyDownTrap} className="w-[600px] max-h-[80vh] bg-card border border-border rounded-xl shadow-lg overflow-hidden flex flex-col">
                {/* Header — shadcn premium density */}
                <div className="h-12 px-6 border-b border-border flex items-center justify-between bg-card flex-shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center">
                            <Activity size={16} className="text-primary-foreground" />
                        </div>
                        <div>
                            <h2 id="pre-execute-title" className="text-sm font-semibold tracking-tight">Configure Backtest</h2>
                            <p className="text-[10px] text-muted-foreground font-mono">SELECT INDICATORS & OVERLAYS</p>
                        </div>
                    </div>
                    <button onClick={onClose} aria-label="Close dialog" className="p-2 hover:bg-accent rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                        <X size={16} className="text-muted-foreground" />
                    </button>
                </div>

                <div className="grid grid-cols-3 border-b border-white/5 bg-black/20 px-6 py-3 text-[9px] font-mono uppercase tracking-wider">
                    <div>
                        <div className="text-[#64748b]">Symbol</div>
                        <div className="mt-1 text-white">{ticker || 'Unavailable'}</div>
                    </div>
                    <div>
                        <div className="text-[#64748b]">Observed rows</div>
                        <div className="mt-1 text-white">
                            {Number.isFinite(dataQuality?.observations) ? dataQuality.observations : 'Unavailable'}
                        </div>
                    </div>
                    <div>
                        <div className="text-[#64748b]">Data quality</div>
                        <div className={`mt-1 ${dataQuality?.status === 'observed' ? 'text-emerald-400' : 'text-red-300'}`}>
                            {dataQuality?.status || 'unavailable'}
                        </div>
                    </div>
                </div>
                {/* P5-W3 institutional preflight: blocking vs warnings + manifest + explicit validators */}
                <div className="border-b border-white/5 bg-[#0f0f14]/50 px-6 py-3 space-y-2">
                    {(() => {
                        const { blocking, warnings, corporateActions, lookAhead } = assessPreflight(dataQuality);
                        return (
                            <>
                                {blocking.length > 0 && (
                                    <div role="alert" className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2">
                                        <div className="text-[9px] font-mono font-bold tracking-widest text-red-300">BLOCKING ERRORS</div>
                                        <ul className="mt-1 list-disc pl-4 text-[10px] font-mono text-red-300/90 space-y-1">
                                            {blocking.map((m, i) => <li key={i}>{m}</li>)}
                                        </ul>
                                    </div>
                                )}
                                {warnings.length > 0 && (
                                    <div className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                                        <div className="text-[9px] font-mono font-bold tracking-widest text-amber-300">WARNINGS — review before relying</div>
                                        <ul className="mt-1 list-disc pl-4 text-[10px] font-mono text-amber-300/90 space-y-1">
                                            {warnings.map((m, i) => <li key={i}>{m}</li>)}
                                        </ul>
                                    </div>
                                )}
                                <div aria-label="Preflight validators" className="grid grid-cols-2 gap-2">
                                    <div className="rounded border border-white/10 bg-black/20 px-3 py-2">
                                        <div className="text-[9px] font-mono font-bold tracking-widest text-[#8b95a7]">CORPORATE-ACTION VALIDATOR</div>
                                        <div className={`mt-1 text-[10px] font-mono ${corporateActions.status === 'adjusted' ? 'text-emerald-400' : 'text-amber-300'}`}>{corporateActions.status}</div>
                                        <div className="mt-0.5 text-[9px] font-mono text-[#64748b]">{corporateActions.message}</div>
                                    </div>
                                    <div className="rounded border border-white/10 bg-black/20 px-3 py-2">
                                        <div className="text-[9px] font-mono font-bold tracking-widest text-[#8b95a7]">LOOK-AHEAD VALIDATOR</div>
                                        <div className={`mt-1 text-[10px] font-mono ${lookAhead.status === 'verified' ? 'text-emerald-400' : 'text-amber-300'}`}>{lookAhead.status.replace('_', ' ')}</div>
                                        <div className="mt-0.5 text-[9px] font-mono text-[#64748b]">{lookAhead.message}</div>
                                    </div>
                                </div>
                                <details className="rounded border border-white/10 bg-black/20 px-3 py-2">
                                    <summary className="text-[9px] font-mono font-bold tracking-widest text-[#8b95a7] cursor-pointer">DATASET MANIFEST — inspect before running</summary>
                                    <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] font-mono">
                                        <div><span className="text-[#64748b]">source:</span> <span className="text-white">{dataQuality?.source || 'Not reported'}</span></div>
                                        <div><span className="text-[#64748b]">as_of:</span> <span className="text-white">{dataQuality?.as_of || '--'}</span></div>
                                        <div><span className="text-[#64748b]">timezone:</span> <span className="text-white">{dataQuality?.timezone || 'Not reported'}</span></div>
                                        <div><span className="text-[#64748b]">currency:</span> <span className="text-white">{dataQuality?.currency || 'Not reported'}</span></div>
                                        <div><span className="text-[#64748b]">calendar:</span> <span className="text-white">{dataQuality?.calendar || 'Not reported'}</span></div>
                                        <div><span className="text-[#64748b]">corporate actions:</span> <span className="text-white">{dataQuality?.corporate_actions || 'unknown'}</span></div>
                                        <div><span className="text-[#64748b]">look-ahead:</span> <span className="text-white">{dataQuality?.look_ahead_check === 'verified' ? 'verified' : 'not verified'}</span></div>
                                    </div>
                                </details>
                            </>
                        );
                    })()}
                </div>
                
                {/* Tabs */}
                <div className="flex border-b border-white/5 flex-shrink-0">
                    <button
                        onClick={() => setActiveTab('overlays')}
                        className={`flex-1 px-4 py-3 text-[11px] font-mono font-bold uppercase tracking-widest transition-all ${
                            activeTab === 'overlays' 
                            ? 'text-amber-500 border-b-2 border-amber-500 bg-amber-500/5' 
                            : 'text-[#64748b] hover:text-white'
                        }`}
                    >
                        <TrendingUp size={14} className="inline mr-2" />
                        Overlays ({OVERLAYS.length})
                    </button>
                    <button
                        onClick={() => {
                            if (isGridMode) return;
                            setActiveTab('oscillators');
                        }}
                        className={`flex-1 px-4 py-3 text-[11px] font-mono font-bold uppercase tracking-widest transition-all relative ${
                            isGridMode ? 'opacity-30 cursor-not-allowed' : ''
                        } ${
                            activeTab === 'oscillators' 
                            ? 'text-amber-500 border-b-2 border-amber-500 bg-amber-500/5' 
                            : 'text-[#64748b] hover:text-white'
                        }`}
                        title={isGridMode ? "Oscillators are not supported in grid mode" : ""}
                    >
                        <BarChart2 size={14} className="inline mr-2" />
                        Oscillators ({OSCILLATORS.length})
                        {isGridMode && (
                            <span className="absolute top-1/2 -translate-y-1/2 right-4 px-1.5 py-0.5 bg-amber-500/10 border border-amber-500/30 rounded text-[7px] text-amber-500">BLOCKED</span>
                        )}
                    </button>
                </div>
                
                {/* Search */}
                <div className="p-4 border-b border-white/5 flex-shrink-0">
                    <div className="relative">
                        <Search size={14} className="absolute left-3 top-3 text-[#64748b]" />
                        <input 
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="Search indicators..."
                            className="w-full h-10 bg-[#020204] border border-white/10 rounded-lg pl-10 pr-4 text-[12px] font-mono text-white outline-none focus:border-amber-500/30 transition-all placeholder:text-[#64748b]/50"
                        />
                    </div>
                </div>
                
                {/* Indicator Grid */}
                <div className="flex-1 overflow-y-auto p-4">
                    <div className="grid grid-cols-2 gap-2">
                        {filtered.map(item => {
                            const active = isActive(item.id);
                            return (
                                <button
                                    key={item.id}
                                    onClick={() => handleToggle(item)}
                                    className={`p-3 rounded-lg flex items-center gap-3 transition-all text-left ${
                                        active 
                                        ? 'bg-amber-500/10 border border-amber-500/30' 
                                        : 'bg-[#0f0f14] border border-white/5 hover:border-white/10'
                                    }`}
                                >
                                    <div 
                                        className="w-3 h-3 rounded-full flex-shrink-0" 
                                        style={{ backgroundColor: item.color }}
                                    />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className={`text-[11px] font-mono font-bold ${active ? 'text-amber-500' : 'text-white'}`}>
                                                {item.shortName}
                                            </span>
                                            <span className="text-[10px] text-[#64748b] truncate">{item.name}</span>
                                        </div>
                                        <span className="text-[9px] text-[#64748b]/70 font-mono">{item.desc}</span>
                                    </div>
                                    {active && (
                                        <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center flex-shrink-0">
                                            <Check size={10} className="text-black" />
                                        </div>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </div>
                
                {/* Active Indicators */}
                {activeIndicators.length > 0 && (
                    <div className="px-4 py-3 border-t border-white/5 bg-[#0f0f14]/50 flex-shrink-0">
                        <div className="text-[9px] font-mono text-[#64748b] uppercase tracking-widest mb-2">
                            Active ({activeIndicators.length})
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                            {activeIndicators.map(o => (
                                <span key={o.id} className="flex items-center gap-1 px-2 py-1 rounded text-[9px] font-mono font-bold" style={{ backgroundColor: `${o.color}20`, color: o.color, border: `1px solid ${o.color}40` }}>
                                    {o.name}
                                    <X size={8} className="cursor-pointer opacity-70 hover:opacity-100" onClick={() => removeIndicator(o.id)} />
                                </span>
                            ))}
                        </div>
                    </div>
                )}
                
                {/* Footer */}
                <div className="p-4 border-t border-white/5 flex gap-3 flex-shrink-0">
                    <button 
                        onClick={onClose}
                        className="flex-1 h-11 bg-white/5 text-white text-[11px] font-bold rounded-lg hover:bg-white/10 transition-all uppercase tracking-widest"
                    >
                        Cancel
                    </button>
                    <button 
                        onClick={onExecute}
                        disabled={dataQuality?.status !== 'observed' || !Number.isFinite(dataQuality?.observations) || dataQuality.observations < 20}
                        className="flex-1 h-11 bg-amber-500 text-black text-[11px] font-bold rounded-lg hover:bg-amber-400 transition-all uppercase tracking-widest flex items-center justify-center gap-2 disabled:bg-white/10 disabled:text-[#64748b]"
                    >
                        <Zap size={14} />
                        Execute Backtest
                    </button>
                </div>
            </div>
        </div>
    );
};

export default PreExecuteModal;
export { OVERLAYS, OSCILLATORS };
