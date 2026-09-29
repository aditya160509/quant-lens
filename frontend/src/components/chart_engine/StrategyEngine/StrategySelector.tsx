/**
 * Strategy Selector Modal
 * TradingView-inspired strategy picker with categories and parameters
 */

'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { TRADING_STRATEGIES, TradingStrategy } from './strategies';
import { CHART_THEME } from '../types';
import { Cpu, Zap, TrendingUp, Rocket, Activity, BarChart, Search, X, Star } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface StrategySelectorProps {
    isOpen: boolean;
    onClose: () => void;
    selectedStrategies: string[];
    onStrategyToggle: (strategyId: string) => void;
    strategyParams: Record<string, Record<string, number>>;
    onParamChange: (strategyId: string, param: string, value: number) => void;
    onSelectAll?: () => void;
    onClearAll?: () => void;
}

type Tab = 'all' | 'momentum' | 'trend' | 'breakout' | 'oscillator' | 'volatility';

// =============================================================================
// STRATEGY CATEGORIES
// =============================================================================

const STRATEGY_CATEGORIES = [
    { id: 'all', label: 'All Strategies', icon: <BarChart size={14} /> },
    { id: 'momentum', label: 'Momentum', icon: <Zap size={14} className="text-orange-500" /> },
    { id: 'trend', label: 'Trend', icon: <TrendingUp size={14} className="text-emerald-500" /> },
    { id: 'breakout', label: 'Breakout', icon: <Rocket size={14} className="text-blue-500" /> },
    { id: 'oscillator', label: 'Oscillator', icon: <Activity size={14} className="text-purple-500" /> },
    { id: 'volatility', label: 'Volatility', icon: <Activity size={14} className="text-red-500" /> },
] as const;

// =============================================================================
// COMPONENT
// =============================================================================

export function StrategySelector({
    isOpen,
    onClose,
    selectedStrategies,
    onStrategyToggle,
    strategyParams,
    onParamChange,
    onSelectAll,
    onClearAll,
}: StrategySelectorProps) {
    const [searchQuery, setSearchQuery] = useState('');
    const [activeTab, setActiveTab] = useState<Tab>('all');
    const [expandedStrategy, setExpandedStrategy] = useState<string | null>(null);

    // Filter strategies based on search and tab
    const filteredStrategies = useMemo(() => {
        let strategies = [...TRADING_STRATEGIES];

        // Filter by tab
        if (activeTab !== 'all') {
            strategies = strategies.filter(s => s.category === activeTab);
        }

        // Filter by search
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            strategies = strategies.filter(s =>
                s.name.toLowerCase().includes(query) ||
                s.displayName.toLowerCase().includes(query) ||
                s.description.toLowerCase().includes(query)
            );
        }

        return strategies;
    }, [activeTab, searchQuery]);

    // Group strategies by complexity
    const groupedStrategies = useMemo(() => {
        const groups: Record<number, TradingStrategy[]> = { 1: [], 2: [], 3: [] };
        filteredStrategies.forEach(s => {
            groups[s.complexity]?.push(s);
        });
        return groups;
    }, [filteredStrategies]);

    const handleStrategyClick = useCallback((strategyId: string) => {
        onStrategyToggle(strategyId);
    }, [onStrategyToggle]);

    const toggleExpand = useCallback((strategyId: string) => {
        setExpandedStrategy(prev => prev === strategyId ? null : strategyId);
    }, []);

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center"
            style={{ background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)' }}
            onClick={(e) => e.target === e.currentTarget && onClose()}
        >
            <div
                className="relative w-full max-w-3xl mx-4 rounded-2xl overflow-hidden shadow-2xl"
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
                        <Cpu size={20} className="text-cyan-500" />
                        Trading Strategies
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
                            placeholder="Search strategies..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:bg-white/10 transition-all"
                        />
                    </div>
                </div>

                {/* Tabs */}
                <div
                    className="flex gap-1 px-6 py-3 overflow-x-auto no-scrollbar"
                    style={{ background: CHART_THEME.bgPrimary, borderBottom: `1px solid ${CHART_THEME.border}` }}
                >
                    {STRATEGY_CATEGORIES.map(cat => (
                        <button
                            key={cat.id}
                            onClick={() => setActiveTab(cat.id as Tab)}
                            className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-all flex items-center gap-2 ${
                                activeTab === cat.id
                                    ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-500/20'
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
                        {selectedStrategies.length} of {TRADING_STRATEGIES.length} active
                    </span>
                    <div className="flex gap-2">
                        <button
                            onClick={onSelectAll}
                            className="px-3 py-1 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10 rounded transition-colors"
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

                {/* Strategy List */}
                <div
                    className="overflow-y-auto px-4 py-4"
                    style={{ maxHeight: 'calc(85vh - 280px)' }}
                >
                    {/* Easy Strategies */}
                    {groupedStrategies[1].length > 0 && (
                        <StrategyGroup
                            title="Easy"
                            icon={<Star size={10} className="text-yellow-500/50" />}
                            strategies={groupedStrategies[1]}
                            selectedStrategies={selectedStrategies}
                            expandedStrategy={expandedStrategy}
                            strategyParams={strategyParams}
                            onStrategyClick={handleStrategyClick}
                            onToggleExpand={toggleExpand}
                            onParamChange={onParamChange}
                        />
                    )}

                    {/* Medium Strategies */}
                    {groupedStrategies[2].length > 0 && (
                        <StrategyGroup
                            title="Medium"
                            icon={<div className="flex gap-0.5"><Star size={10} className="text-yellow-500/50" /><Star size={10} className="text-yellow-500/50" /></div>}
                            strategies={groupedStrategies[2]}
                            selectedStrategies={selectedStrategies}
                            expandedStrategy={expandedStrategy}
                            strategyParams={strategyParams}
                            onStrategyClick={handleStrategyClick}
                            onToggleExpand={toggleExpand}
                            onParamChange={onParamChange}
                        />
                    )}

                    {/* Hard Strategies */}
                    {groupedStrategies[3].length > 0 && (
                        <StrategyGroup
                            title="Hard"
                            icon={<div className="flex gap-0.5"><Star size={10} className="text-yellow-500/50" /><Star size={10} className="text-yellow-500/50" /><Star size={10} className="text-yellow-500/50" /></div>}
                            strategies={groupedStrategies[3]}
                            selectedStrategies={selectedStrategies}
                            expandedStrategy={expandedStrategy}
                            strategyParams={strategyParams}
                            onStrategyClick={handleStrategyClick}
                            onToggleExpand={toggleExpand}
                            onParamChange={onParamChange}
                        />
                    )}

                    {/* Empty State */}
                    {filteredStrategies.length === 0 && (
                        <div className="text-center py-12 text-gray-500">
                            <Search size={40} className="mx-auto mb-3 opacity-20" />
                            <p>No strategies found</p>
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
                        className="px-6 py-2 text-sm font-bold text-white bg-cyan-600 hover:bg-cyan-500 rounded-lg transition-colors shadow-lg shadow-cyan-500/20"
                    >
                        Apply Strategies
                    </button>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

interface StrategyGroupProps {
    title: string;
    strategies: TradingStrategy[];
    selectedStrategies: string[];
    expandedStrategy: string | null;
    strategyParams: Record<string, Record<string, number>>;
    onStrategyClick: (id: string) => void;
    onToggleExpand: (id: string) => void;
    onParamChange: (strategyId: string, param: string, value: number) => void;
    icon?: React.ReactNode;
}

function StrategyGroup({
    title,
    strategies,
    selectedStrategies,
    expandedStrategy,
    strategyParams,
    onStrategyClick,
    onToggleExpand,
    onParamChange,
    icon,
}: StrategyGroupProps) {
    return (
        <div className="mb-6">
            <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 mb-3 px-2 flex items-center gap-2">
                {icon}
                {title}
            </h3>
            <div className="space-y-2">
                {strategies.map(strategy => (
                    <StrategyCard
                        key={strategy.id}
                        strategy={strategy}
                        isSelected={selectedStrategies.includes(strategy.id)}
                        isExpanded={expandedStrategy === strategy.id}
                        params={strategyParams[strategy.id] || {}}
                        onClick={() => onStrategyClick(strategy.id)}
                        onToggleExpand={() => onToggleExpand(strategy.id)}
                        onParamChange={(param, value) => onParamChange(strategy.id, param, value)}
                    />
                ))}
            </div>
        </div>
    );
}

interface StrategyCardProps {
    strategy: TradingStrategy;
    isSelected: boolean;
    isExpanded: boolean;
    params: Record<string, number>;
    onClick: () => void;
    onToggleExpand: () => void;
    onParamChange: (param: string, value: number) => void;
}

function StrategyCard({
    strategy,
    isSelected,
    isExpanded,
    params,
    onClick,
    onToggleExpand,
    onParamChange,
}: StrategyCardProps) {
    const categoryColors: Record<string, { bg: string; text: string }> = {
        momentum: { bg: 'bg-orange-500/10', text: 'text-orange-400' },
        trend: { bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
        breakout: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
        oscillator: { bg: 'bg-purple-500/10', text: 'text-purple-400' },
        volatility: { bg: 'bg-red-500/10', text: 'text-red-400' },
        reversal: { bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
    };

    const colors = categoryColors[strategy.category] || categoryColors.trend;
    const hasParams = Object.keys(strategy.params).length > 0;

    return (
        <div
            className={`rounded-xl overflow-hidden transition-all ${
                isSelected
                    ? 'bg-cyan-500/10 border-2 border-cyan-500/30'
                    : 'bg-white/5 border border-white/5 hover:bg-white/10'
            }`}
        >
            {/* Main Row */}
            <div className="flex items-start gap-3 p-3">
                {/* Checkbox */}
                <button
                    onClick={onClick}
                    className={`flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 transition-all ${
                        isSelected
                            ? 'bg-cyan-600 border-cyan-600'
                            : 'border-gray-500 hover:border-gray-400'
                    }`}
                >
                    {isSelected && (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                            <polyline points="20 6 9 17 4 12" />
                        </svg>
                    )}
                </button>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-sm font-semibold text-white truncate">
                            {strategy.displayName}
                        </span>
                        <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                            {strategy.category}
                        </span>
                    </div>
                    <p className="text-[11px] text-gray-500 line-clamp-1">
                        {strategy.description}
                    </p>
                </div>

                {/* Expand Button (if has params) */}
                {hasParams && (
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onToggleExpand();
                        }}
                        className={`flex-shrink-0 p-1.5 rounded-lg transition-all ${
                            isExpanded ? 'bg-white/10' : 'hover:bg-white/5'
                        }`}
                    >
                        <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            className={`text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        >
                            <polyline points="6 9 12 15 18 9" />
                        </svg>
                    </button>
                )}
            </div>

            {/* Parameters Panel (expanded) */}
            {isExpanded && hasParams && (
                <div
                    className="px-4 pb-4 pt-2 border-t border-white/5"
                    onClick={(e) => e.stopPropagation()}
                >
                    <div className="text-[9px] uppercase tracking-widest text-gray-600 mb-3">Parameters</div>
                    <div className="grid grid-cols-2 gap-3">
                        {Object.entries(strategy.params).map(([key, config]) => {
                            const value = params[key] ?? config.default;
                            return (
                                <div key={key} className="flex flex-col gap-1">
                                    <label className="text-[10px] text-gray-400 font-medium">
                                        {config.label}
                                    </label>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="range"
                                            min={config.min}
                                            max={config.max}
                                            step={config.step}
                                            value={value}
                                            onChange={(e) => onParamChange(key, parseFloat(e.target.value))}
                                            className="flex-1 h-1.5 rounded-full appearance-none bg-gray-700 cursor-pointer"
                                            style={{
                                                accentColor: '#06b6d4',
                                            }}
                                        />
                                        <span className="text-[11px] text-cyan-400 font-mono w-10 text-right">
                                            {value}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default StrategySelector;
