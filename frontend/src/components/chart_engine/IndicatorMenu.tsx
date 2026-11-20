/**
 * Indicator Menu Component
 * TradingView-style dropdown menu for selecting and adding indicators to the chart
 * Max 2 oscillators allowed, with proper active chips and remove functionality
 * Supports 65+ technical indicators organized by category
 */

'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { getAllIndicators, getIndicatorsByPlacement } from './IndicatorEngine/registry';
import { CHART_THEME, getIndicatorColor, type IndicatorConfig } from './types';
import { Check, X, Search } from 'lucide-react';

interface IndicatorMenuProps {
    onAddIndicator: (config: IndicatorConfig) => void;
    activeIndicators: IndicatorConfig[];
    onRemoveIndicator: (id: string) => void;
    isGridMode?: boolean;
}

// Max oscillators allowed (pane indicators like RSI, MACD)
const MAX_OSCILLATORS = 4;

// Category colors for visual organization
const CATEGORY_COLORS: Record<string, string> = {
    'Trend': '#22c55e',
    'Momentum': '#f59e0b',
    'Volatility': '#ef4444',
    'Volume': '#3b82f6',
    'Oscillator': '#8b5cf6',
    'Support': '#06b6d4',
    'default': '#6b7280',
};

// Indicator categories based on their function
const getCategoryForIndicator = (id: string): string => {
    const trendIndicators = ['sma', 'ema', 'wma', 'hullma', 'dema', 'tema', 'zlema', 'mcginley', 'kama', 'frama', 'supertrend', 'sar', 'psar', 'ichimoku', 'emaRibbon', 'volatilityStop'];
    const momentumIndicators = ['rsi', 'macd', 'stochastic', 'roc', 'momentum', 'cmo', 'ao', 'ppo', 'trix', 'crsi', 'tsi', 'rvi', 'elderRay', 'kst', 'coppock', 'dpo', 'force', 'aroon', 'ultimate', 'stc', 'smiErgodic'];
    const volatilityIndicators = ['atr', 'natr', 'bollinger', 'keltner', 'donchian', 'chop', 'hv', 'ulcer', 'stderror', 'mass'];
    const volumeIndicators = ['obv', 'vwap', 'ad', 'cmf', 'volumeOsc', 'volumeProfile', 'mfi', 'pvo', 'bop'];
    const supportIndicators = ['pivot'];
    
    if (trendIndicators.includes(id)) return 'Trend';
    if (momentumIndicators.includes(id)) return 'Momentum';
    if (volatilityIndicators.includes(id)) return 'Volatility';
    if (volumeIndicators.includes(id)) return 'Volume';
    if (supportIndicators.includes(id)) return 'Support';
    return 'Other';
};


export default function IndicatorMenu({
    onAddIndicator,
    activeIndicators,
    onRemoveIndicator,
    isGridMode = false
}: IndicatorMenuProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<'overlay' | 'pane'>('pane'); // Default to oscillators tab
    const [toast, setToast] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [categoryFilter, setCategoryFilter] = useState<string>('All');

    const allIndicators = useMemo(() => getAllIndicators(), []);
    const overlayIndicators = getIndicatorsByPlacement('overlay');
    const paneIndicators = getIndicatorsByPlacement('pane');
    
    // Total indicator count for display
    const totalIndicatorCount = allIndicators.length;
    
    // Filter indicators by search and category
    const filteredIndicators = useMemo(() => {
        const baseList = activeTab === 'overlay' ? overlayIndicators : paneIndicators;
        return baseList.filter(ind => {
            const matchesSearch = searchQuery === '' || 
                ind.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                ind.shortName.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesCategory = categoryFilter === 'All' || 
                getCategoryForIndicator(ind.id) === categoryFilter;
            return matchesSearch && matchesCategory;
        });
    }, [activeTab, overlayIndicators, paneIndicators, searchQuery, categoryFilter]);

    // Count active oscillators (pane placement)
    const activeOscillators = useMemo(() => 
        activeIndicators.filter(i => i.placement === 'pane'),
        [activeIndicators]
    );

    const activeOverlays = useMemo(() => 
        activeIndicators.filter(i => i.placement === 'overlay'),
        [activeIndicators]
    );

    // Show toast notification
    const showToast = useCallback((message: string) => {
        setToast(message);
        setTimeout(() => setToast(null), 2500);
    }, []);

    const handleAddIndicator = useCallback((id: string) => {
        const indicator = getAllIndicators().find(i => i.id === id);
        if (!indicator) return;

        // Check if already active
        if (activeIndicators.some(i => i.type === id)) {
            showToast(`${indicator.shortName} is already active`);
            return;
        }

        // Check oscillator limit or grid constraint
        if (indicator.placement === 'pane') {
            if (isGridMode) {
                showToast(`Oscillators not supported in grid mode`);
                return;
            }
            if (activeOscillators.length >= MAX_OSCILLATORS) {
                showToast(`Max ${MAX_OSCILLATORS} oscillators. Remove one first.`);
                return;
            }
        }

        const indicatorColor = getIndicatorColor(id);

        const config: IndicatorConfig = {
            id: `${id}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
            type: id,
            params: { ...indicator.defaultParams },
            placement: indicator.placement,
            visible: true,
            color: indicatorColor,
            lineWidth: indicator.placement === 'overlay' ? 1.5 : 1,
        };

        onAddIndicator(config);
        setIsOpen(false);
    }, [activeIndicators, activeOscillators.length, onAddIndicator, showToast, isGridMode]);

    const isIndicatorActive = useCallback((type: string) => {
        return activeIndicators.some(i => i.type === type);
    }, [activeIndicators]);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            const target = e.target as HTMLElement;
            if (!target.closest('.indicator-menu-container')) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener('click', handleClickOutside);
            return () => document.removeEventListener('click', handleClickOutside);
        }
    }, [isOpen]);

    return (
        <div className="relative indicator-menu-container">
            {/* Toast Notification */}
            {toast && (
                <div
                    className="absolute -top-10 right-0 px-3 py-1.5 text-xs font-mono rounded shadow-lg z-50 animate-in fade-in slide-in-from-top-2"
                    style={{
                        background: CHART_THEME.downColor,
                        color: '#fff',
                    }}
                >
                    {toast}
                </div>
            )}

            {/* Main Button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setIsOpen(!isOpen);
                }}
                className="px-2 py-1 text-xs font-mono flex items-center gap-1.5"
                style={{
                    background: isOpen ? 'rgba(255, 214, 10, 0.2)' : 'transparent',
                    color: isOpen ? CHART_THEME.accent : CHART_THEME.textSecondary,
                    border: `1px solid ${CHART_THEME.border}`,
                    borderRadius: 2,
                }}
            >
                <span style={{ fontSize: 10, fontWeight: 'bold' }}>ƒx</span>
                INDICATORS
                {activeIndicators.length > 0 && (
                    <span
                        className="px-1.5 rounded text-[10px] font-bold"
                        style={{ background: CHART_THEME.accent, color: CHART_THEME.bgPrimary }}
                    >
                        {activeIndicators.length}
                    </span>
                )}
            </button>

            {isOpen && (
                <div
                    className="absolute right-0 top-full mt-1 z-50 rounded shadow-xl overflow-hidden"
                    style={{
                        background: CHART_THEME.bgSecondary,
                        border: `1px solid ${CHART_THEME.border}`,
                        minWidth: 380,
                        maxWidth: 450,
                    }}
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header with indicator count */}
                    <div 
                        className="px-3 py-2 flex items-center justify-between border-b"
                        style={{ borderColor: CHART_THEME.border, background: CHART_THEME.bgPanel }}
                    >
                        <span className="text-xs font-mono font-bold" style={{ color: CHART_THEME.accent }}>
                            {totalIndicatorCount} INDICATORS
                        </span>
                        <div className="flex gap-1">
                            {['All', 'Trend', 'Momentum', 'Volatility', 'Volume'].map(cat => (
                                <button
                                    key={cat}
                                    onClick={() => setCategoryFilter(cat)}
                                    className="px-2 py-0.5 text-[9px] font-mono rounded transition-all"
                                    style={{
                                        background: categoryFilter === cat ? CATEGORY_COLORS[cat] || CATEGORY_COLORS.default : 'transparent',
                                        color: categoryFilter === cat ? '#000' : CHART_THEME.textSecondary,
                                        border: `1px solid ${categoryFilter === cat ? 'transparent' : CHART_THEME.border}`,
                                    }}
                                >
                                    {cat}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Search Bar */}
                    <div className="px-3 py-2 border-b" style={{ borderColor: CHART_THEME.border }}>
                            <div className="relative">
                                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                                <input
                                    type="text"
                                    placeholder="Search indicators..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="w-full pl-9 pr-3 py-2 text-xs font-mono rounded"
                                    style={{
                                        background: CHART_THEME.bgPrimary,
                                        color: CHART_THEME.textPrimary,
                                        border: `1px solid ${CHART_THEME.border}`,
                                        outline: 'none',
                                    }}
                                    autoFocus
                                />
                            </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex border-b" style={{ borderColor: CHART_THEME.border }}>
                        <button
                            onClick={() => setActiveTab('overlay')}
                            className="flex-1 px-3 py-2.5 text-xs font-mono font-bold transition-colors"
                            style={{
                                background: activeTab === 'overlay' ? CHART_THEME.bgPanel : 'transparent',
                                color: activeTab === 'overlay' ? CHART_THEME.accent : CHART_THEME.textSecondary,
                                borderBottom: activeTab === 'overlay' ? `2px solid ${CHART_THEME.accent}` : '2px solid transparent',
                            }}
                        >
                            OVERLAYS
                            <span className="ml-1 opacity-70">({overlayIndicators.length})</span>
                            {activeOverlays.length > 0 && (
                                <span className="ml-1 px-1 rounded text-[9px]" style={{ background: CHART_THEME.accent, color: '#000' }}>
                                    {activeOverlays.length}
                                </span>
                            )}
                        </button>
                        <button
                            onClick={() => setActiveTab('pane')}
                            className="flex-1 px-3 py-2.5 text-xs font-mono font-bold transition-colors"
                            style={{
                                background: activeTab === 'pane' ? CHART_THEME.bgPanel : 'transparent',
                                color: activeTab === 'pane' ? CHART_THEME.accent : CHART_THEME.textSecondary,
                                borderBottom: activeTab === 'pane' ? `2px solid ${CHART_THEME.accent}` : '2px solid transparent',
                            }}
                        >
                            OSCILLATORS
                            <span className="ml-1 opacity-70">({paneIndicators.length})</span>
                            {activeOscillators.length > 0 && (
                                <span className="ml-1 px-1 rounded text-[9px]" style={{ background: CHART_THEME.accent, color: '#000' }}>
                                    {activeOscillators.length}/{MAX_OSCILLATORS}
                                </span>
                            )}
                        </button>
                    </div>

                    {/* Indicator List */}
                    <div className="max-h-72 overflow-y-auto">
                        {filteredIndicators.length === 0 ? (
                            <div className="px-4 py-6 text-center text-xs font-mono" style={{ color: CHART_THEME.textSecondary }}>
                                No indicators found for &quot;{searchQuery}&quot;
                            </div>
                        ) : (
                            filteredIndicators.map(indicator => {
                                const isActive = isIndicatorActive(indicator.id);
                                const indicatorColor = getIndicatorColor(indicator.id);
                                const isDisabled = (activeTab === 'pane' && isGridMode) || 
                                    (activeTab === 'pane' && !isActive && activeOscillators.length >= MAX_OSCILLATORS);
                                const category = getCategoryForIndicator(indicator.id);
                                const categoryColor = CATEGORY_COLORS[category] || CATEGORY_COLORS.default;

                                return (
                                    <button
                                        key={indicator.id}
                                        onClick={() => !isDisabled && handleAddIndicator(indicator.id)}
                                        disabled={isDisabled}
                                        className={`w-full px-3 py-2 text-left text-xs font-mono flex items-center justify-between transition-all ${
                                            isDisabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-white/5 cursor-pointer'
                                        }`}
                                        style={{
                                            background: isActive ? `${indicatorColor}15` : 'transparent',
                                    }}
                                >
                                    <div className="flex items-center gap-2">
                                        {/* Color indicator dot */}
                                        <span
                                            className="w-2.5 h-2.5 rounded-full shrink-0"
                                            style={{ background: isActive ? indicatorColor : CHART_THEME.textMuted }}
                                        />
                                        <span 
                                            className="font-bold" 
                                            style={{ color: isActive ? indicatorColor : CHART_THEME.textPrimary }}
                                        >
                                            {indicator.shortName}
                                        </span>
                                        <span style={{ color: CHART_THEME.textSecondary }}>
                                            {indicator.name}
                                        </span>
                                    </div>
                                    {isActive && (
                                            <Check size={14} style={{ color: indicatorColor }} />
                                    )}
                                </button>
                                );
                            })
                        )}
                    </div>

                    {/* Active Indicators Section */}
                    {activeIndicators.length > 0 && (
                        <div
                            className="border-t px-3 py-2.5"
                            style={{ borderColor: CHART_THEME.border, background: CHART_THEME.bgPanel }}
                        >
                            <div 
                                className="text-[10px] font-mono font-bold mb-2 uppercase tracking-wider" 
                                style={{ color: CHART_THEME.textSecondary }}
                            >
                                Active ({activeIndicators.length})
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {activeIndicators.map(config => {
                                    const ind = getAllIndicators().find(i => i.id === config.type);
                                    const indicatorColor = config.color || getIndicatorColor(config.type);
                                    return (
                                        <span
                                            key={config.id}
                                            className="px-2 py-1 rounded text-[10px] font-mono font-bold flex items-center gap-1.5 cursor-pointer hover:scale-105 transition-transform"
                                            style={{
                                                background: indicatorColor,
                                                color: '#000',
                                            }}
                                            onClick={() => onRemoveIndicator(config.id)}
                                            title={`Click to remove ${ind?.shortName || config.type}`}
                                        >
                                            {ind?.shortName || config.type}
                                            <X size={10} className="opacity-70" />
                                        </span>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
