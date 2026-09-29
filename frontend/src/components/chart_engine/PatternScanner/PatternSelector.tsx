/**
 * Pattern Selector Modal
 * TradingView-inspired pattern picker with categories and search
 */

'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { CANDLESTICK_PATTERNS, CandlestickPattern } from './candlestickPatterns';
import { CHART_THEME } from '../types';
import { LayoutGrid, TrendingUp, TrendingDown, Square, Minus, Search, X, ChevronUp, ChevronDown } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface PatternSelectorProps {
    isOpen: boolean;
    onClose: () => void;
    selectedPatterns: string[];
    onPatternToggle: (patternId: string) => void;
    onSelectAll?: () => void;
    onClearAll?: () => void;
}

type Tab = 'all' | 'bullish' | 'bearish' | 'single' | 'multi';

// =============================================================================
// PATTERN CATEGORIES
// =============================================================================

const PATTERN_CATEGORIES = [
    { id: 'all', label: 'All Patterns', icon: <LayoutGrid size={14} /> },
    { id: 'bullish', label: 'Bullish', icon: <TrendingUp size={14} className="text-emerald-500" /> },
    { id: 'bearish', label: 'Bearish', icon: <TrendingDown size={14} className="text-red-500" /> },
    { id: 'single', label: 'Single', icon: <Square size={14} /> },
    { id: 'multi', label: 'Multi', icon: <Minus size={14} /> },
] as const;

// =============================================================================
// COMPONENT
// =============================================================================

export function PatternSelector({
    isOpen,
    onClose,
    selectedPatterns,
    onPatternToggle,
    onSelectAll,
    onClearAll,
}: PatternSelectorProps) {
    const [searchQuery, setSearchQuery] = useState('');
    const [activeTab, setActiveTab] = useState<Tab>('all');

    // Filter patterns based on search and tab
    const filteredPatterns = useMemo(() => {
        let patterns = [...CANDLESTICK_PATTERNS];

        // Filter by tab
        switch (activeTab) {
            case 'bullish':
                patterns = patterns.filter(p => p.type === 'bullish');
                break;
            case 'bearish':
                patterns = patterns.filter(p => p.type === 'bearish');
                break;
            case 'single':
                patterns = patterns.filter(p => p.category === 'single');
                break;
            case 'multi':
                patterns = patterns.filter(p => ['double', 'triple', 'complex'].includes(p.category));
                break;
        }

        // Filter by search
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            patterns = patterns.filter(p =>
                p.name.toLowerCase().includes(query) ||
                p.displayName.toLowerCase().includes(query) ||
                p.description.toLowerCase().includes(query)
            );
        }

        return patterns;
    }, [activeTab, searchQuery]);

    // Group patterns by category for display
    const groupedPatterns = useMemo(() => {
        const groups: Record<string, CandlestickPattern[]> = {
            single: [],
            double: [],
            triple: [],
            complex: [],
        };

        filteredPatterns.forEach(p => {
            groups[p.category]?.push(p);
        });

        return groups;
    }, [filteredPatterns]);

    const handlePatternClick = useCallback((patternId: string) => {
        onPatternToggle(patternId);
    }, [onPatternToggle]);

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center"
            style={{ background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)' }}
            onClick={(e) => e.target === e.currentTarget && onClose()}
        >
            <div
                className="relative w-full max-w-2xl mx-4 rounded-2xl overflow-hidden shadow-2xl"
                style={{
                    background: CHART_THEME.bgSecondary,
                    border: `1px solid ${CHART_THEME.border}`,
                    maxHeight: '85vh',
                }}
            >
                {/* Header */}
                <div
                    className="flex items-center justify-between px-6 py-4"
                    style={{ borderBottom: `1px solid ${CHART_THEME.border}` }}
                >
                    <h2 className="text-lg font-bold text-white flex items-center gap-3">
                        <LayoutGrid size={20} className="text-purple-500" />
                        Candlestick Patterns
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Search Bar */}
                <div className="px-6 py-3" style={{ background: CHART_THEME.bgPrimary }}>
                    <div className="relative">
                        <Search
                            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                            size={18}
                        />
                        <input
                            type="text"
                            placeholder="Search patterns..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 focus:bg-white/10 transition-all"
                        />
                    </div>
                </div>

                {/* Tabs */}
                <div
                    className="flex gap-1 px-6 py-3 overflow-x-auto no-scrollbar"
                    style={{ background: CHART_THEME.bgPrimary, borderBottom: `1px solid ${CHART_THEME.border}` }}
                >
                    {PATTERN_CATEGORIES.map(cat => (
                        <button
                            key={cat.id}
                            onClick={() => setActiveTab(cat.id as Tab)}
                            className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-all flex items-center gap-2 ${
                                activeTab === cat.id
                                    ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20'
                                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            <span>{cat.icon}</span>
                            {cat.label}
                        </button>
                    ))}
                </div>

                {/* Quick Actions */}
                <div className="flex items-center justify-between px-6 py-2" style={{ background: CHART_THEME.bgPrimary }}>
                    <span className="text-xs text-gray-500">
                        {selectedPatterns.length} of {CANDLESTICK_PATTERNS.length} selected
                    </span>
                    <div className="flex gap-2">
                        <button
                            onClick={onSelectAll}
                            className="px-3 py-1 text-xs text-purple-400 hover:text-purple-300 hover:bg-purple-500/10 rounded transition-colors"
                        >
                            Select All
                        </button>
                        <button
                            onClick={onClearAll}
                            className="px-3 py-1 text-xs text-gray-400 hover:text-gray-300 hover:bg-white/5 rounded transition-colors"
                        >
                            Clear All
                        </button>
                    </div>
                </div>

                {/* Pattern List */}
                <div
                    className="overflow-y-auto px-4 py-4"
                    style={{ maxHeight: 'calc(85vh - 240px)' }}
                >
                    {/* Single Candle Patterns */}
                    {groupedPatterns.single.length > 0 && (
                        <PatternGroup
                            title="Single Candle"
                            patterns={groupedPatterns.single}
                            selectedPatterns={selectedPatterns}
                            onPatternClick={handlePatternClick}
                        />
                    )}

                    {/* Double Candle Patterns */}
                    {groupedPatterns.double.length > 0 && (
                        <PatternGroup
                            title="Double Candle"
                            patterns={groupedPatterns.double}
                            selectedPatterns={selectedPatterns}
                            onPatternClick={handlePatternClick}
                        />
                    )}

                    {/* Triple Candle Patterns */}
                    {groupedPatterns.triple.length > 0 && (
                        <PatternGroup
                            title="Triple Candle"
                            patterns={groupedPatterns.triple}
                            selectedPatterns={selectedPatterns}
                            onPatternClick={handlePatternClick}
                        />
                    )}

                    {/* Empty State */}
                    {filteredPatterns.length === 0 && (
                        <div className="text-center py-12 text-gray-500">
                            <Search size={40} className="mx-auto mb-3 opacity-20" />
                            <p>No patterns found</p>
                            <p className="text-sm mt-1">Try a different search term</p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div
                    className="flex items-center justify-end gap-3 px-6 py-4"
                    style={{ borderTop: `1px solid ${CHART_THEME.border}`, background: CHART_THEME.bgPrimary }}
                >
                    <button
                        onClick={onClose}
                        className="px-6 py-2 text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onClose}
                        className="px-6 py-2 text-sm font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-colors shadow-lg shadow-purple-500/20"
                    >
                        Apply Scanner
                    </button>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

interface PatternGroupProps {
    title: string;
    patterns: CandlestickPattern[];
    selectedPatterns: string[];
    onPatternClick: (id: string) => void;
}

function PatternGroup({ title, patterns, selectedPatterns, onPatternClick }: PatternGroupProps) {
    return (
        <div className="mb-6">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 mb-3 px-2">
                {title}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {patterns.map(pattern => (
                    <PatternCard
                        key={pattern.id}
                        pattern={pattern}
                        isSelected={selectedPatterns.includes(pattern.id)}
                        onClick={() => onPatternClick(pattern.id)}
                    />
                ))}
            </div>
        </div>
    );
}

interface PatternCardProps {
    pattern: CandlestickPattern;
    isSelected: boolean;
    onClick: () => void;
}

function PatternCard({ pattern, isSelected, onClick }: PatternCardProps) {
    const typeColors = {
        bullish: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', icon: <ChevronUp size={12} /> },
        bearish: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', icon: <ChevronDown size={12} /> },
        neutral: { bg: 'bg-gray-500/10', border: 'border-gray-500/30', text: 'text-gray-400', icon: <Minus size={12} /> },
    };

    const colors = typeColors[pattern.type];

    return (
        <button
            onClick={onClick}
            className={`relative flex items-start gap-3 p-3 rounded-xl text-left transition-all group ${
                isSelected
                    ? `${colors.bg} ${colors.border} border-2`
                    : 'bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/10'
            }`}
        >
            {/* Checkbox */}
            <div
                className={`flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 transition-all ${
                    isSelected
                        ? 'bg-purple-600 border-purple-600'
                        : 'border-gray-500 group-hover:border-gray-400'
                }`}
            >
                {isSelected && (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                        <polyline points="20 6 9 17 4 12" />
                    </svg>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                    <span className={`flex items-center justify-center ${colors.text}`}>{colors.icon}</span>
                    <span className="text-sm font-semibold text-white truncate">
                        {pattern.displayName}
                    </span>
                </div>
                <p className="text-[11px] text-gray-500 line-clamp-2 leading-relaxed">
                    {pattern.description}
                </p>

                {/* Complexity Stars */}
                <div className="flex items-center gap-1 mt-2">
                    {[...Array(3)].map((_, i) => (
                        <span
                            key={i}
                            className={`text-[10px] ${i < pattern.complexity ? 'text-yellow-400' : 'text-gray-600'}`}
                        >
                            ★
                        </span>
                    ))}
                    <span className="text-[9px] text-gray-600 ml-1 uppercase">
                        {pattern.category}
                    </span>
                </div>
            </div>
        </button>
    );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default PatternSelector;
