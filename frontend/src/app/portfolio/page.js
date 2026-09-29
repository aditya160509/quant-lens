"use client";

import React, { useState, useEffect } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { Loader2 } from 'lucide-react';

import { fetchPortfolioState, fetchPortfolioAllocations, fetchPortfolioSummary } from '@/lib/api';

// Components
import PortfolioSummaryHeader from '@/components/portfolio/PortfolioSummaryHeader';
import HoldingsTable from '@/components/portfolio/HoldingsTable';
import TradePanel from '@/components/portfolio/TradePanel';
import PortfolioMetricsPanel from '@/components/portfolio/PortfolioMetricsPanel';
import AllocationCharts from '@/components/portfolio/AllocationCharts';
import PortfolioTimelineChart from '@/components/portfolio/PortfolioTimelineChart';

// Tabs
import OptimizeTab from '@/components/portfolio/OptimizeTab';
import BacktestTab from '@/components/portfolio/BacktestTab';
import ScenariosTab from '@/components/portfolio/ScenariosTab';
import CompareTab from '@/components/portfolio/CompareTab';

export default function PortfolioPage() {
    const [state, setState] = useState(null);
    const [allocations, setAllocations] = useState(null);
    // summary is implicitly in state for now, but if separate endpoint needed we can use it.
    // fetchPortfolioState returns { cash, total_equity, unrealized_pl, positions, risk }
    // which covers most needs.

    const [loading, setLoading] = useState(true);

    const loadData = async () => {
        try {
            const [s, a] = await Promise.all([
                fetchPortfolioState(),
                fetchPortfolioAllocations()
            ]);
            setState(s);
            setAllocations(a);
        } catch (e) {
            console.error("Portfolio load error:", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    // Pass this to TradePanel to refresh data after trade
    const onTradeSuccess = () => {
        loadData();
    };

    if (loading && !state) {
        return (
            <div className="h-screen flex items-center justify-center bg-terminal-black text-terminal-green">
                <Loader2 className="animate-spin mr-2" /> Initializing Portfolio Protocol...
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-terminal-black text-terminal-text p-6 font-mono">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-terminal-green mb-1">Portfolio Command</h1>
                <div className="h-px bg-terminal-gray/30 w-full mb-4"></div>

                {/* Summary Metrics */}
                <PortfolioSummaryHeader data={state} />
            </div>

            <div className="grid grid-cols-12 gap-6 h-[calc(100vh-250px)] min-h-[600px]">
                {/* Main Content Area (Left 2/3) */}
                <div className="col-span-12 lg:col-span-8 flex flex-col min-h-0">
                    <Tabs.Root defaultValue="build" className="flex-1 flex flex-col min-h-0">
                        <Tabs.List className="flex border-b border-terminal-gray/30 mb-4 bg-terminal-darker rounded-t">
                            <TabTrigger value="build" label="BUILD & MONITOR" />
                            <TabTrigger value="optimize" label="OPTIMIZE" />
                            <TabTrigger value="backtest" label="BACKTEST" />
                            <TabTrigger value="scenarios" label="SCENARIOS" />
                            <TabTrigger value="compare" label="COMPARE" />
                        </Tabs.List>

                        <div className="flex-1 min-h-0 relative bg-terminal-black/50 border border-terminal-gray/10 rounded-b p-1">
                            <Tabs.Content value="build" className="h-full flex flex-col gap-4 overflow-hidden outline-none">
                                <div className="flex-none">
                                    <PortfolioTimelineChart />
                                </div>
                                <div className="flex-1 min-h-0">
                                    <HoldingsTable holdings={state?.positions} />
                                </div>
                            </Tabs.Content>

                            <Tabs.Content value="optimize" className="h-full outline-none">
                                <OptimizeTab holdings={state?.positions} onApply={onTradeSuccess} />
                            </Tabs.Content>

                            <Tabs.Content value="backtest" className="h-full outline-none">
                                <BacktestTab holdings={state?.positions} />
                            </Tabs.Content>

                            <Tabs.Content value="scenarios" className="h-full outline-none">
                                <ScenariosTab holdings={state?.positions} />
                            </Tabs.Content>

                            <Tabs.Content value="compare" className="h-full outline-none">
                                <CompareTab holdings={state?.positions} />
                            </Tabs.Content>
                        </div>
                    </Tabs.Root>
                </div>

                {/* Sidebar (Right 1/3) */}
                <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 overflow-y-auto pr-1">
                    {/* Trade Panel */}
                    <div className="flex-none">
                        <TradePanel onTradeSuccess={onTradeSuccess} />
                    </div>

                    {/* Metrics */}
                    <div className="flex-none">
                        <PortfolioMetricsPanel metrics={state?.risk} />
                    </div>

                    {/* Allocations */}
                    <div className="flex-none">
                        <AllocationCharts allocations={allocations} />
                    </div>
                </div>
            </div>
        </div>
    );
}

function TabTrigger({ value, label }) {
    return (
        <Tabs.Trigger
            value={value}
            className="px-4 py-3 text-xs font-bold text-terminal-dim hover:text-terminal-text data-[state=active]:text-terminal-yellow data-[state=active]:border-b-2 data-[state=active]:border-terminal-yellow transition-all outline-none"
        >
            {label}
        </Tabs.Trigger>
    );
}
