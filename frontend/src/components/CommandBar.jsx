"use client";

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { ALLOWED_SYMBOLS } from '@/lib/universe/loadUniverse';
import { isValidSymbol } from '@/lib/universe/loadUniverse';

// Known pages for navigation
const KNOWN_PAGES = {
    "MONITOR": "/",
    "HOME": "/",
    "MARKETS": "/markets",
    "MKT": "/markets",
    "SECURITY": "/security",
    "SEC": "/security",
    "MACRO": "/macro",
    "LABS": "/labs",
    "PORTFOLIO": "/portfolio",
    "PORT": "/portfolio"
};

// Action shortcuts
const ACTIONS = {
    "PORT OPT": { route: "/portfolio", params: { tab: "optimize" } },
    "PORT OPTIMIZE": { route: "/portfolio", params: { tab: "optimize" } },
    "PORT BACKTEST": { route: "/portfolio", params: { tab: "backtest" } },
    "LABS EARN": { route: "/labs", params: { tab: "earnings" } },
    "LABS EARNINGS": { route: "/labs", params: { tab: "earnings" } },
    "LABS SCREEN": { route: "/labs", params: { tab: "screener" } },
    "LABS SCREENER": { route: "/labs", params: { tab: "screener" } }
};

// Interval patterns
const INTERVALS = ["1m", "5m", "15m", "1h", "1d"];
const WINDOWS = ["1d", "5d", "1m"];

export default function CommandBar() {
    const [query, setQuery] = useState("");
    const [focused, setFocused] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef(null);
    const router = useRouter();
    const pathname = usePathname();

    // Ticker symbols for matching (from universe)
    const tickerSymbols = useMemo(() => Array.from(ALLOWED_SYMBOLS), []);

    // Parse command and generate route
    const parseCommand = (cmd) => {
        const tokens = cmd.trim().toUpperCase().split(/\s+/);
        if (tokens.length === 0 || !tokens[0]) return null;

        const first = tokens[0];

        // Check for action shortcuts first (e.g., "PORT OPT")
        const actionKey = tokens.slice(0, 2).join(" ");
        if (ACTIONS[actionKey]) {
            const action = ACTIONS[actionKey];
            const params = new URLSearchParams(action.params);
            return `${action.route}?${params}`;
        }

        // Check for page navigation
        if (KNOWN_PAGES[first] && tokens.length === 1) {
            return KNOWN_PAGES[first];
        }

        // Check if first token is a ticker (use universe validation)
        const isTicker = isValidSymbol(first) || /^[A-Z]{1,5}$/.test(first);

        if (isTicker) {
            const ticker = first;

            // Pattern: AAPL intraday 5m
            if (tokens.includes("INTRADAY")) {
                const intervalIdx = tokens.findIndex(t => INTERVALS.includes(t.toLowerCase()));
                const interval = intervalIdx > -1 ? tokens[intervalIdx].toLowerCase() : "5m";
                return `/security?ticker=${ticker}&mode=intraday&interval=${interval}`;
            }

            // Pattern: SPY 5m 5d (markets intraday)
            const hasInterval = tokens.some(t => INTERVALS.includes(t.toLowerCase()));
            const hasWindow = tokens.some(t => WINDOWS.includes(t.toLowerCase()));

            if (hasInterval || hasWindow) {
                const interval = tokens.find(t => INTERVALS.includes(t.toLowerCase())) || "5m";
                const window = tokens.find(t => WINDOWS.includes(t.toLowerCase())) || "5d";
                return `/markets?tab=intraday&ticker=${ticker}&interval=${interval}&window=${window}`;
            }

            // Just ticker name -> security page
            return `/security?ticker=${ticker}`;
        }

        // Fallback: if looks like ticker, go to security
        if (/^[A-Z]{2,5}$/.test(first)) {
            return `/security?ticker=${first}`;
        }

        return null;
    };

    // Generate suggestions based on query
    useEffect(() => {
        if (!query.trim()) {
            setSuggestions([]);
            return;
        }

        const q = query.toUpperCase();
        const results = [];

        // Match tickers from universe
        const matchedTickers = tickerSymbols
            .filter(t => t.toUpperCase().startsWith(q))
            .slice(0, 3)
            .map(t => ({ type: 'ticker', label: t, value: t }));
        results.push(...matchedTickers);

        // Match pages
        Object.keys(KNOWN_PAGES).forEach(page => {
            if (page.startsWith(q) && results.length < 6) {
                results.push({ type: 'page', label: page, value: page });
            }
        });

        // Match actions
        Object.keys(ACTIONS).forEach(action => {
            if (action.startsWith(q) && results.length < 6) {
                results.push({ type: 'action', label: action, value: action });
            }
        });

        setSuggestions(results.slice(0, 6));
        setSelectedIndex(0);
    }, [query]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleGlobalKeyDown = (e) => {
            // Ctrl+K or / to focus
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                inputRef.current?.focus();
                return;
            }
            if (e.key === '/') {
                const tag = document.activeElement?.tagName;
                if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
                    e.preventDefault();
                    inputRef.current?.focus();
                }
            }
        };

        window.addEventListener('keydown', handleGlobalKeyDown);
        return () => window.removeEventListener('keydown', handleGlobalKeyDown);
    }, []);

    const handleKeyDown = (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIndex(prev => Math.min(prev + 1, suggestions.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIndex(prev => Math.max(prev - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();

            // If suggestion selected, use it
            if (suggestions.length > 0 && suggestions[selectedIndex]) {
                const selected = suggestions[selectedIndex];
                executeCommand(selected.value);
            } else {
                // Parse raw query
                const route = parseCommand(query);
                if (route) {
                    router.push(route);
                    setQuery("");
                    inputRef.current?.blur();
                }
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            if (query) {
                setQuery("");
            } else {
                inputRef.current?.blur();
            }
        }
    };

    const executeCommand = (value) => {
        const route = parseCommand(value);
        if (route) {
            router.push(route);
            setQuery("");
            inputRef.current?.blur();
        }
    };

    return (
        <div className="w-full relative h-[36px] bg-terminal-black border-b border-terminal-gray z-40 flex items-center px-4 gap-4">
            {/* Input Overlay */}
            <div className={`
                flex-1 relative flex items-center group
                ${focused ? 'ring-1 ring-terminal-yellow/20' : ''}
            `}>
                <span className="absolute left-2 text-terminal-dim group-focus-within:text-terminal-yellow transition-colors">
                    <svg width="14" height="14" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2.5 5.5C2.5 3.84315 3.84315 2.5 5.5 2.5C7.15685 2.5 8.5 3.84315 8.5 5.5C8.5 7.15685 7.15685 8.5 5.5 8.5C3.84315 8.5 2.5 7.15685 2.5 5.5ZM5.5 1.5C3.29086 1.5 1.5 3.29086 1.5 5.5C1.5 7.70914 3.29086 9.5 5.5 9.5C6.38071 9.5 7.19478 9.21532 7.85461 8.73327L11.7071 12.5858C11.8946 12.7733 12.1983 12.7733 12.3858 12.5858C12.5733 12.3983 12.5733 12.0946 12.3858 11.9071L8.53327 8.05461C9.01532 7.39478 9.3 6.58071 9.3 5.7C9.3 3.38023 7.41977 1.5 5.1 1.5H5.5Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path></svg>
                </span>

                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => setFocused(true)}
                    onBlur={() => setTimeout(() => setFocused(false), 200)}
                    placeholder="Command..."
                    className="w-full h-7 pl-8 pr-3 bg-terminal-black border border-terminal-gray group-hover:border-terminal-dim rounded text-xs font-mono text-terminal-text outline-none focus:border-terminal-yellow/50 transition-colors placeholder:text-terminal-dim"
                />

                {/* Keyboard hints */}
                <div className="absolute right-2 hidden lg:flex gap-1 text-[10px] font-mono text-terminal-dim pointer-events-none opacity-50">
                    <kbd className="px-1 rounded bg-terminal-dark border border-terminal-gray">/</kbd>
                </div>

                {/* Suggestions Dropdown */}
                {focused && suggestions.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 py-1 bg-terminal-dark border border-terminal-gray rounded-md shadow-lg z-50 overflow-hidden">
                        {suggestions.map((s, i) => (
                            <div
                                key={i}
                                onClick={() => executeCommand(s.value)}
                                className={`
                                    px-3 py-1.5 cursor-pointer font-mono text-xs flex items-center justify-between
                                    ${i === selectedIndex ? 'bg-terminal-black border-l-2 border-terminal-yellow pl-[10px]' : 'text-terminal-text hover:bg-terminal-black pl-3 border-l-2 border-transparent'}
                                `}
                            >
                                <div className="flex items-center gap-2">
                                    <span className={`text-[10px] opacity-70 ${s.type === 'ticker' ? 'text-blue-400' : 'text-terminal-yellow'}`}>
                                        {s.type === 'ticker' ? 'TICKER' : 'CMD'}
                                    </span>
                                    <span>{s.label}</span>
                                </div>
                                <span className="text-[10px] text-terminal-dim opacity-50">
                                    ↵
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Hint Text */}
            <div className="hidden md:block text-[10px] font-mono text-terminal-dim/50 whitespace-nowrap">
                Try: AAPL, SPY 5m, PORT OPT...
            </div>
        </div>
    );
}
