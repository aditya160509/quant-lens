'use client';

import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useTradingContext, type Exchange, type Timeframe } from '@/context/TradingContext';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';
import { getSymbolInfo } from '@/lib/universe/symbolMapper';
import { Globe, Clock, TrendingUp, TrendingDown, ChevronUp, ChevronDown } from 'lucide-react';

// =============================================================================
// TIMEFRAMES
// =============================================================================

const TIMEFRAMES: { value: Timeframe; label: string }[] = [
    { value: '1m', label: '1M' },
    { value: '5m', label: '5M' },
    { value: '15m', label: '15M' },
    { value: '30m', label: '30M' },
    { value: '1h', label: '1H' },
    { value: '1d', label: '1D' },
    { value: '3mo', label: '3MO' },
    { value: '6mo', label: '6MO' },
    { value: '1y', label: '1Y' },
];

// =============================================================================
// SESSION HELPERS
// =============================================================================

interface MarketSession {
    name: string;
    openHour: number;
    openMinute: number;
    closeHour: number;
    closeMinute: number;
    timezone: string;
    utcOffset: number;
}

const MARKET_SESSIONS: MarketSession[] = [
    { name: 'ASIA', openHour: 9, openMinute: 0, closeHour: 15, closeMinute: 30, timezone: 'IST', utcOffset: 5.5 },
    { name: 'EUROPE', openHour: 8, openMinute: 0, closeHour: 16, closeMinute: 30, timezone: 'GMT', utcOffset: 0 },
    { name: 'US', openHour: 9, openMinute: 30, closeHour: 16, closeMinute: 0, timezone: 'EST', utcOffset: -5 },
];

function getSessionStatus(session: MarketSession): 'open' | 'closed' | 'pre' {
    const now = new Date();
    const utcHours = now.getUTCHours();
    const utcMinutes = now.getUTCMinutes();
    const totalMinutesUTC = utcHours * 60 + utcMinutes;
    
    const localOffset = session.utcOffset * 60;
    const totalMinutesLocal = totalMinutesUTC + localOffset;
    
    const openMinutes = session.openHour * 60 + session.openMinute;
    const closeMinutes = session.closeHour * 60 + session.closeMinute;
    
    const day = now.getDay();
    if (day === 0 || day === 6) return 'closed'; // Weekend
    
    if (totalMinutesLocal >= openMinutes && totalMinutesLocal < closeMinutes) {
        return 'open';
    } else if (totalMinutesLocal >= openMinutes - 60 && totalMinutesLocal < openMinutes) {
        return 'pre';
    }
    return 'closed';
}

function getNextSessionOpen(): { hours: number; minutes: number } | null {
    const now = new Date();
    const day = now.getDay();
    
    // If weekend, calculate time to Monday 9:30 AM EST
    if (day === 0 || day === 6) {
        const daysUntilMonday = day === 0 ? 1 : 2;
        const targetDate = new Date(now);
        targetDate.setDate(targetDate.getDate() + daysUntilMonday);
        targetDate.setUTCHours(14, 30, 0, 0); // 9:30 AM EST = 14:30 UTC
        
        const diff = targetDate.getTime() - now.getTime();
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        return { hours, minutes };
    }
    
    // Weekday - check if US market opens later today
    const usOpenUTC = 14 * 60 + 30; // 9:30 AM EST = 14:30 UTC
    const currentUTC = now.getUTCHours() * 60 + now.getUTCMinutes();
    
    if (currentUTC < usOpenUTC) {
        const diffMinutes = usOpenUTC - currentUTC;
        return { hours: Math.floor(diffMinutes / 60), minutes: diffMinutes % 60 };
    }
    
    // Market already closed today, calculate for tomorrow
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (tomorrow.getDay() === 6) tomorrow.setDate(tomorrow.getDate() + 2); // Skip to Monday
    if (tomorrow.getDay() === 0) tomorrow.setDate(tomorrow.getDate() + 1);
    
    tomorrow.setUTCHours(14, 30, 0, 0);
    const diff = tomorrow.getTime() - now.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    return { hours, minutes };
}

// =============================================================================
// MARKET CONTEXT BAR - CATEGORY A
// =============================================================================

interface MarketContextBarProps {
    activeTab?: string;
    onTabChange?: (tabId: any) => void;
}

export default function MarketContextBar({ activeTab, onTabChange }: MarketContextBarProps) {
    const { state, setSymbol, setTimeframe, dispatch } = useTradingContext();
    const [prevPrice, setPrevPrice] = useState(0);
    const [tickDirection, setTickDirection] = useState<'up' | 'down' | 'neutral'>('neutral');

    // Keyboard shortcut: Cmd+K to focus search
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                // Focus the search input
                const searchInput = document.querySelector('input[placeholder*="Search"]') as HTMLInputElement;
                searchInput?.focus();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    // Fetch live price updates
    useEffect(() => {
        const fetchPrice = async () => {
            try {
                const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
                const res = await fetch(`${API_BASE}/api/markets/intraday?ticker=${state.symbol}&interval=1m`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.bars && data.bars.length > 0) {
                        const lastBar = data.bars[data.bars.length - 1];
                        const firstBar = data.bars[0];
                        const change = lastBar.close - firstBar.open;
                        const changePercent = firstBar.open !== 0 ? (change / firstBar.open) * 100 : 0;
                        
                        // Track tick direction
                        if (prevPrice > 0) {
                            if (lastBar.close > prevPrice) setTickDirection('up');
                            else if (lastBar.close < prevPrice) setTickDirection('down');
                        }
                        setPrevPrice(lastBar.close);
                        
                        dispatch({
                            type: 'SET_PRICE',
                            payload: {
                                price: lastBar.close,
                                change,
                                changePercent,
                            },
                        });
                    }
                }
            } catch (error) {
                console.error('Failed to fetch price:', error);
            }
        };

        fetchPrice();
        const interval = setInterval(fetchPrice, 3000); // Update every 3s
        return () => clearInterval(interval);
    }, [state.symbol, dispatch, prevPrice]);


    // Update countdown timer - initialize with value directly
    const [countdown, setCountdown] = useState(() => getNextSessionOpen());
    
    useEffect(() => {
        const interval = setInterval(() => {
            setCountdown(getNextSessionOpen());
        }, 60000); // Update every minute
        return () => clearInterval(interval);
    }, []);

    // Get session statuses
    const sessionStatuses = useMemo(() => {
        return MARKET_SESSIONS.map(session => ({
            ...session,
            status: getSessionStatus(session)
        }));
    }, []);

    // Determine current session status
    const getMainSessionStatus = useCallback(() => {
        const now = new Date();
        const hour = now.getHours();
        const day = now.getDay();
        
        // Weekend
        if (day === 0 || day === 6) {
            return { market: 'closed' as const, label: 'WEEKEND' };
        }
        
        // US market hours (simplified - 9:30 AM - 4:00 PM EST)
        if (state.exchange === 'US') {
            if (hour >= 9 && hour < 16) {
                return { market: 'regular' as const, label: 'US OPEN' };
            } else if (hour >= 4 && hour < 9) {
                return { market: 'pre' as const, label: 'PRE-MARKET' };
            } else if (hour >= 16 && hour < 20) {
                return { market: 'post' as const, label: 'AFTER-HOURS' };
            }
        }
        
        // NSE hours (9:15 AM - 3:30 PM IST)
        if (state.exchange === 'NSE' || state.exchange === 'BSE') {
            if (hour >= 9 && hour < 16) {
                return { market: 'regular' as const, label: 'INDIA OPEN' };
            }
        }
        
        return { market: 'closed' as const, label: 'MARKET CLOSED' };
    }, [state.exchange]);

    const sessionStatus = getMainSessionStatus();
    const isPositive = state.change >= 0;
    const symbolInfo = getSymbolInfo(state.symbol);

    return (
        <div className="h-full w-full flex items-center justify-between px-3 bg-terminal-dark">
            {/* LEFT SECTION: Symbol Search + Exchange Badge + Price */}
            <div className="flex items-center gap-3">
                {/* Symbol Search - Compact */}
                <div className="w-[120px]">
                    <TradingViewSearch
                        mode="any"
                        allowFxCrypto={true}
                        onSelect={(sym) => setSymbol(sym)}
                        placeholder="⌘K"
                    />
                </div>

                {/* Exchange Badge */}
                <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-terminal-yellow font-mono">
                        {symbolInfo?.base || state.symbol}
                    </span>
                    <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                        state.exchange === 'NSE' ? 'bg-terminal-cyan/20 text-terminal-cyan' :
                        state.exchange === 'BSE' ? 'bg-terminal-green/20 text-terminal-green' :
                        'bg-terminal-dim/20 text-terminal-dim'
                    }`}>
                        {state.exchange}
                    </span>
                </div>

                {/* Divider */}
                <div className="h-6 w-px bg-terminal-gray" />

                {/* Live Price Display - Large and prominent */}
                <div className="flex items-baseline gap-2">
                    <div className="flex items-center gap-1">
                        {/* Currency Symbol */}
                        <span className="text-lg font-mono text-terminal-dim">
                            {state.exchange === 'NSE' || state.exchange === 'BSE' ? '₹' : '$'}
                        </span>
                        <span className={`text-xl font-bold font-mono transition-colors duration-200 ${
                            tickDirection === 'up' ? 'text-terminal-green' :
                            tickDirection === 'down' ? 'text-terminal-red' :
                            'text-terminal-text'
                        }`}>
                            {state.lastPrice > 0 ? state.lastPrice.toFixed(2) : '—'}
                        </span>
                        {/* Tick indicator */}
                        {tickDirection !== 'neutral' && (
                            <span className={`text-sm ${tickDirection === 'up' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                                {tickDirection === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                            </span>
                        )}
                    </div>
                    {state.lastPrice > 0 && (
                        <div className={`flex items-center gap-1 ${isPositive ? 'text-terminal-green' : 'text-terminal-red'}`}>
                            <span className="flex items-center">
                                {isPositive ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </span>
                            <span className="text-xs font-mono font-bold">
                                {isPositive ? '+' : ''}{state.change.toFixed(2)} ({state.changePercent.toFixed(2)}%)
                            </span>
                        </div>
                    )}
                </div>

                {/* Bid/Ask Spread */}
                {state.bidAsk && (
                    <div className="text-[10px] font-mono text-terminal-dim">
                        <span className="text-terminal-green">{state.bidAsk.bid.toFixed(2)}</span>
                        <span className="mx-1">×</span>
                        <span className="text-terminal-red">{state.bidAsk.ask.toFixed(2)}</span>
                    </div>
                )}
            </div>

            {/* CENTER SECTION: Navigation Tabs (New space-saving location) */}
            {activeTab && onTabChange && (
                <div className="flex items-center h-full gap-1 ml-4 border-l border-terminal-gray/30 pl-4">
                    {[
                        { id: 'chart', label: 'Chart', num: '1' },
                        { id: 'signals', label: 'Signals', num: '2' },
                        { id: 'trade', label: 'Trade', num: '3' }
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => onTabChange(tab.id)}
                            className={`px-3 h-full flex items-center gap-1.5 text-[11px] font-mono font-bold transition-all relative ${
                                activeTab === tab.id ? 'text-terminal-yellow' : 'text-terminal-dim hover:text-terminal-text'
                            }`}
                        >
                            <span>{tab.label}</span>
                            <span className="text-[9px] opacity-40 px-1 border border-current rounded-sm leading-none flex items-center h-3">
                                {tab.num}
                            </span>
                            {activeTab === tab.id && (
                                <div className="absolute bottom-[-1px] left-0 right-0 h-[2px] bg-terminal-yellow shadow-[0_0_10px_rgba(255,184,0,0.5)]" />
                            )}
                        </button>
                    ))}
                </div>
            )}

            <div className="flex-1" />

            {/* RIGHT SECTION: Session Status Pills */}
            <div className="flex items-center gap-3">
                {/* Global Session Pills */}
                <div className="flex items-center gap-1">
                    {sessionStatuses.map(session => (
                        <span 
                            key={session.name}
                            className={`px-1.5 py-0.5 text-[8px] font-bold rounded-sm ${
                                session.status === 'open' ? 'bg-terminal-green text-terminal-black' :
                                session.status === 'pre' ? 'bg-terminal-yellow/20 text-terminal-yellow' :
                                'bg-terminal-dim/10 text-terminal-dim'
                            }`}
                        >
                            {session.name}
                        </span>
                    ))}
                </div>
                
                {/* Current Session Indicator */}
                <div className="flex items-center gap-2 border-l border-terminal-gray/30 pl-3">
                    <span className={`px-2 py-0.5 text-[9px] font-bold rounded ${
                        sessionStatus.market === 'regular' ? 'bg-terminal-green text-terminal-black' :
                        sessionStatus.market === 'pre' || sessionStatus.market === 'post' ? 'bg-terminal-yellow/20 text-terminal-yellow' :
                        'bg-terminal-dim/20 text-terminal-dim'
                    }`}>
                        {sessionStatus.label}
                    </span>
                    {sessionStatus.market === 'regular' && (
                        <span className="w-1.5 h-1.5 rounded-full bg-terminal-green animate-pulse" />
                    )}
                </div>
            </div>
        </div>
    );
}
