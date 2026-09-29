'use client';

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { getSymbolInfo, validateForMode, getExchangeColor } from '@/lib/universe/symbolMapper';
import { getUniverse } from '@/lib/universe/loadUniverse';
import { TICKERS } from '@/constants/tickers';

// Create a map for quick name lookup from the small list we have
const TICKER_NAME_MAP = new Map(TICKERS.map(t => [t.symbol, t.name]));

/**
 * TradingViewSearch Component
 * A premium, TradingView-style symbol search with tabs and detailed list view.
 */
export default function TradingViewSearch({
    mode = 'any',
    allowFxCrypto = false,
    onSelect,
    placeholder = 'Search symbol...',
    value = '',
    disabled = false,
    autoFocus = false,
    dropdownZIndex = 99999,
}) {
    const [query, setQuery] = useState(value || '');
    const [prevValue, setPrevValue] = useState(value);

    if (value !== prevValue) {
        setPrevValue(value);
        setQuery(value || '');
    }

    const [results, setResults] = useState([]);
    const [isOpen, setIsOpen] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [activeTab, setActiveTab] = useState('All');
    const [error, setError] = useState(null);
    const [allTickers, setAllTickers] = useState([]);
    const [isLoading, setIsLoading] = useState(false);

    const inputRef = useRef(null);
    const dropdownRef = useRef(null);

    // Fetch universal tickers on mount
    useEffect(() => {
        const fetchTickers = async () => {
            try {
                const res = await fetch('/api/sovereign/available-tickers');
                const json = await res.json();
                if (json.status === 'ok' && json.tickers) {
                    setAllTickers(json.tickers);
                }
            } catch (err) {
                console.error("Failed to fetch universal tickers:", err);
            }
        };
        fetchTickers();
    }, []);

    const searchUniverse = useMemo(() => {
        if (allTickers.length > 0) return allTickers;
        return getUniverse();
    }, [allTickers]);


    // Available tabs based on content
    const tabs = useMemo(() => {
        const baseTabs = ['All', 'Stocks', 'Funds', 'Indices', 'Commodities'];
        if (mode === 'any' || mode === 'market') {
            if (allowFxCrypto || mode === 'any') {
                baseTabs.push('Crypto', 'Forex');
            }
        }
        return baseTabs;
    }, [mode, allowFxCrypto]);

    // Filter results by tab
    const filterByTab = useCallback((items, tab) => {
        if (tab === 'All') return items;
        return items.filter(item => {
            const type = item.info.group; // 'india_nse', 'us_equities', 'crypto', etc.
            if (tab === 'Stocks') return ['india_nse', 'india_bse', 'us_equities'].includes(type);
            if (tab === 'Funds') return ['etfs'].includes(type);
            if (tab === 'Indices') return ['indices'].includes(type);
            if (tab === 'Commodities') return ['commodities'].includes(type);
            if (tab === 'Crypto') return ['crypto'].includes(type);
            if (tab === 'Forex') return ['fx'].includes(type);
            return true;
        });
    }, []);

    // Search function
    const handleSearch = useCallback((searchQuery) => {
        if (!searchQuery?.trim()) {
            setResults([]);
            setIsOpen(false);
            return;
        }

        const q = searchQuery.toUpperCase();

        // Score items
        let scored = searchUniverse.map(symbol => {
            const info = getSymbolInfo(symbol);
            if (!info) return null;
            
            const base = info.base;
            const name = TICKER_NAME_MAP.get(symbol) || '';
            const nameUpper = name.toUpperCase();

            let score = 0;
            if (base === q) score = 100;
            else if (base.startsWith(q)) score = 80;
            else if (base.includes(q)) score = 60;
            else if (nameUpper.includes(q)) score = 40;
            else if (symbol.includes(q)) score = 20;

            if (score === 0) return null;

            return { symbol, info, name, score };
        }).filter(Boolean);

        scored.sort((a, b) => b.score - a.score);
        setResults(scored);
        setIsOpen(true);
        setSelectedIndex(0);
    }, [searchUniverse]);


    // Apply tab filter to current results for display
    const displayResults = useMemo(() => {
        return filterByTab(results, activeTab).slice(0, 50);
    }, [results, activeTab, filterByTab]);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => handleSearch(query), 150);
        return () => clearTimeout(timer);
    }, [query, handleSearch]);

    const handleSelect = (item) => {
        const validation = validateForMode(item.symbol, mode, { allowFxCrypto });
        if (!validation.valid) {
            setError(validation.error);
            setTimeout(() => setError(null), 3000);
            return;
        }

        onSelect?.(item.symbol);
        setIsOpen(false);
        setQuery('');
        setResults([]);
    };

    // Keyboard navigation
    const handleKeyDown = (e) => {
        if (!isOpen) {
            if (e.key === 'ArrowDown' || e.key === 'Enter') handleSearch(query);
            return;
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex(i => Math.min(i + 1, displayResults.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex(i => Math.max(i - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (displayResults[selectedIndex]) {
                handleSelect(displayResults[selectedIndex]);
            }
        } else if (e.key === 'Escape') {
            setIsOpen(false);
            inputRef.current?.blur();
        } else if (e.key === 'Tab') {
            e.preventDefault();
            // Cycle tabs
            const currIdx = tabs.indexOf(activeTab);
            const nextIdx = (currIdx + 1) % tabs.length;
            setActiveTab(tabs[nextIdx]);
        }
    };

    // Click outside
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target) && !inputRef.current.contains(e.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    useEffect(() => {
        if (autoFocus && inputRef.current) {
            inputRef.current.focus();
        }
    }, [autoFocus]);

    return (
        <div className="relative w-full font-sans">
            <div className="relative flex items-center group z-10">
                <span className="absolute left-2.5 text-terminal-dim group-focus-within:text-terminal-yellow transition-colors">
                    <svg width="12" height="12" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 6.5C10 8.433 8.433 10 6.5 10C4.567 10 3 8.433 3 6.5C3 4.567 4.567 3 6.5 3C8.433 3 10 4.567 10 6.5ZM9.30884 10.0159C8.53901 10.6318 7.56251 11 6.5 11C4.01472 11 2 8.98528 2 6.5C2 4.01472 4.01472 2 6.5 2C8.98528 2 11 4.01472 11 6.5C11 7.56251 10.6318 8.53901 10.0159 9.30884L12.8536 12.1464C13.0488 12.3417 13.0488 12.6583 12.8536 12.8536C12.6583 13.0488 12.3417 13.0488 12.1464 12.8536L9.30884 10.0159Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path></svg>
                </span>
                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => {
                        setQuery(e.target.value);
                        if (!e.target.value) {
                            setResults([]);
                            setIsOpen(false);
                        }
                    }}
                    onKeyDown={handleKeyDown}
                    onFocus={() => query && handleSearch(query)}
                    className="w-full h-8 pl-8 pr-3 bg-white/5 border border-white/10 rounded-lg text-[11px] text-white outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/20 transition-all placeholder:text-[#444] font-mono"
                    placeholder={placeholder}
                    disabled={disabled}
                    autoFocus={autoFocus}
                />
            </div>

            {/* Dropdown */}
            {isOpen && (
                <div
                    ref={dropdownRef}
                    className="absolute top-full left-0 right-0 mt-2 bg-terminal-dark border border-terminal-gray rounded-lg shadow-2xl overflow-hidden min-w-[500px]"
                    style={{ zIndex: dropdownZIndex }}
                >
                    {/* Tabs */}
                    <div className="flex items-center gap-1 p-2 border-b border-terminal-gray overflow-x-auto no-scrollbar bg-terminal-dark">
                        {tabs.map(tab => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${activeTab === tab
                                    ? 'bg-terminal-yellow/10 text-terminal-yellow'
                                    : 'text-terminal-dim hover:text-terminal-text hover:bg-terminal-gray'
                                    }`}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>

                    {/* Header */}
                    <div className="grid grid-cols-[1.5fr_2fr_1fr] px-4 py-2 text-[10px] font-semibold text-terminal-dim uppercase tracking-wider bg-terminal-black border-b border-terminal-gray">
                        <span>Symbol</span>
                        <span>Description</span>
                        <span className="text-right">Exchange</span>
                    </div>

                    {/* Results List */}
                    <div className="max-h-[350px] overflow-y-auto custom-scrollbar bg-terminal-dark">
                        {displayResults.length > 0 ? (
                            displayResults.map((item, idx) => (
                                <div
                                    key={`${item.symbol}-${idx}`}
                                    onMouseEnter={() => setSelectedIndex(idx)}
                                    onClick={() => handleSelect(item)}
                                    className={`
                                        grid grid-cols-[1.5fr_2fr_1fr] items-center px-4 py-2.5 cursor-pointer border-b border-terminal-gray/30 last:border-0 transition-colors
                                        ${selectedIndex === idx ? 'bg-terminal-gray' : 'hover:bg-terminal-gray/50'}
                                    `}
                                >
                                    {/* Left: Symbol + Badge */}
                                    <div className="flex items-center gap-2 min-w-0">
                                        <div className="w-8 h-8 rounded-full flex items-center justify-center bg-terminal-black border border-terminal-gray shrink-0 text-xs font-bold text-terminal-dim">
                                            {item.info.base[0]}
                                        </div>
                                        <div className="flex flex-col truncate">
                                            <span className="font-bold text-sm text-terminal-text truncate">{item.info.base}</span>
                                            <span className="text-[10px] text-terminal-dim truncate">{item.info.group.toUpperCase().replace('_', ' ')}</span>
                                        </div>
                                    </div>

                                    {/* Middle: Description */}
                                    <div className="text-sm text-terminal-dim/80 truncate pr-2 font-light">
                                        {item.name || item.info.display}
                                    </div>

                                    {/* Right: Exchange Flag/Tag */}
                                    <div className="flex justify-end">
                                        <span
                                            className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border"
                                            style={{
                                                borderColor: `${getExchangeColor(item.info.exchange)}40`,
                                                backgroundColor: `${getExchangeColor(item.info.exchange)}10`,
                                                color: getExchangeColor(item.info.exchange)
                                            }}
                                        >
                                            {item.info.exchange}
                                        </span>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="py-12 text-center text-terminal-dim text-sm">
                                No symbols found
                            </div>
                        )}
                    </div>

                    {error && (
                        <div className="absolute bottom-0 left-0 right-0 bg-red-500/10 border-t border-red-500/20 p-2 text-xs text-red-500 flex items-center justify-center backdrop-blur-sm">
                            {error}
                        </div>
                    )}
                </div>
            )}

            {/* Global Styles for Scrollbar */}
            <style jsx global>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: #26282c;
                    border-radius: 3px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: #374151;
                }
            `}</style>
        </div>
    );
}
