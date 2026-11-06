'use client';

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { TradingProvider } from '@/context/TradingContext';
import dynamic from 'next/dynamic';

// Dynamic imports for tab content components
const MarketContextBar = dynamic(
    () => import('@/components/trading/MarketContextBar'),
    { ssr: false, loading: () => <div className="h-[44px] bg-terminal-dark animate-pulse" /> }
);

// Tab content components - dynamically loaded
const ChartTab = dynamic(
    () => import('@/components/trading/tabs/ChartTab'),
    { ssr: false, loading: () => <TabLoader label="Chart" /> }
);

// Removed: OptionsTab and IVVolTab - heavy yfinance calls with incomplete data

const SignalsTab = dynamic(
    () => import('@/components/trading/tabs/SignalsTab'),
    { ssr: false, loading: () => <TabLoader label="Signals" /> }
);

// Loading placeholder for tabs
function TabLoader({ label }: { label: string }) {
    return (
        <div className="flex-1 flex items-center justify-center bg-terminal-dark">
            <div className="text-terminal-dim font-mono text-sm">Loading {label}...</div>
        </div>
    );
}

// Tab configuration
// Tab configuration - reduced to 3 tabs for performance
const TABS = [
    { id: 'chart', label: 'Chart', shortcut: '1' },
    { id: 'signals', label: 'Signals', shortcut: '2' },
] as const;

type TabId = typeof TABS[number]['id'];

/**
 * QUANT360 ELITE TRADE SYSTEM
 * 
 * Layout:
 * ┌─────────────────────────────────────────────────────────────┐
 * │  TOP BAR: Market Context & Session Info (44px)              │
 * ├─────────────────────────────────────────────────────────────┤
 * │  TAB BAR: Chart | Signals | Trade (40px)                    │
 * ├─────────────────────────────────────────────────────────────┤
 * │                                                             │
 * │  CONTENT AREA: Full-width, changes per tab                  │
 * │  Height: calc(100vh - 84px)                                 │
 * │                                                             │
 * └─────────────────────────────────────────────────────────────┘
 */
function TradingPageContent({ initialSymbol, initialTab }: { initialSymbol?: string; initialTab?: TabId }) {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [activeTab, setActiveTab] = useState<TabId>(initialTab || 'chart');

    // Sync active tab with URL
    useEffect(() => {
        const urlTab = searchParams.get('tab') as TabId | null;
        if (urlTab && TABS.some(t => t.id === urlTab)) {
            if (activeTab !== urlTab) {
                // Defer state update to next microtask to avoid cascading render warning
                Promise.resolve().then(() => setActiveTab(urlTab));
            }
        }
    }, [searchParams, activeTab]);

    // Handle tab change with URL update
    const handleTabChange = useCallback((tabId: TabId) => {
        setActiveTab(tabId);
        const symbol = searchParams.get('symbol') || 'SPY';
        router.push(`/trade?symbol=${symbol}&tab=${tabId}`, { scroll: false });
    }, [router, searchParams]);

    // Keyboard shortcuts for tabs
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Skip if user is typing in an input
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
                return;
            }

            // Number keys 1-3 for tab switching
            if (e.code >= 'Digit1' && e.code <= 'Digit3') {
                const tabIndex = parseInt(e.code.replace('Digit', '')) - 1;
                if (tabIndex >= 0 && tabIndex < TABS.length) {
                    handleTabChange(TABS[tabIndex].id);
                }
            }
        };

        const handleSwitchTabEvent = (e: any) => {
            if (e.detail && TABS.some(t => t.id === e.detail)) {
                handleTabChange(e.detail);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        window.addEventListener('switchTab', handleSwitchTabEvent);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            window.removeEventListener('switchTab', handleSwitchTabEvent);
        };
    }, [handleTabChange]);

    return (
        <TradingProvider initialSymbol={initialSymbol}>
            <div className="h-screen w-screen overflow-hidden bg-terminal-black flex flex-col">
                {/* TOP BAR: Market Context & Navigation - 44px fixed */}
                <div className="h-[44px] w-full shrink-0 border-b border-terminal-gray">
                    <Suspense fallback={<div className="h-full bg-terminal-dark animate-pulse" />}>
                        <MarketContextBar 
                            activeTab={activeTab} 
                            onTabChange={handleTabChange} 
                        />
                    </Suspense>
                </div>

                {/* TAB BAR: Removed (moved to top bar) */}

                {/* CONTENT AREA: Full-width, changes per tab */}
                <div className="flex-1 overflow-hidden">
                    <Suspense fallback={<TabLoader label={TABS.find(t => t.id === activeTab)?.label || 'Content'} />}>
                        {activeTab === 'chart' && <ChartTab />}
                        {activeTab === 'signals' && <SignalsTab />}
                    </Suspense>
                </div>
            </div>
        </TradingProvider>
    );
}

// Inner wrapper that reads URL params - needs Suspense
function TradingPageWrapper() {
    const searchParams = useSearchParams();
    const symbol = searchParams.get('symbol') || undefined;
    const tab = searchParams.get('tab') as TabId | undefined;
    
    return <TradingPageContent initialSymbol={symbol} initialTab={tab} />;
}

// Main export wrapped in Suspense
export default function TradingPage() {
    return (
        <Suspense fallback={
            <div className="h-screen w-screen flex items-center justify-center bg-terminal-black">
                <div className="text-terminal-dim font-mono text-sm">Loading Trading...</div>
            </div>
        }>
            <TradingPageWrapper />
        </Suspense>
    );
}
