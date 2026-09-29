"use client";

import React, { useState, useEffect } from 'react';
import { fetchMacroDashboard } from '@/lib/api';
import TerminalPanel from '@/components/TerminalPanel';
import PageGrid from '@/components/PageGrid';
import StatCard from '@/components/StatCard';
import { PlotlyChart } from '@/components/ui/plotly-chart';

export default function MacroPage() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const res = await fetchMacroDashboard();
            setData(res);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !data) {
        return <div className="p-4 text-terminal-dim font-mono">LOADING MACRO DATA...</div>;
    }

    if (!data) return null;

    const { summary, yield_curve, commentary } = data;

    // Helper to safely get value
    const getVal = (key) => summary[key]?.value || 0;
    const getHist = (key) => summary[key]?.history || [];

    // Yield Curve Chart
    const yieldTraces = [
        {
            x: yield_curve.dates,
            y: yield_curve['10y'],
            type: 'scattergl',
            mode: 'lines',
            name: '10Y Yield',
            line: { color: '#00ff6a', width: 1.5 }
        },
        {
            x: yield_curve.dates,
            y: yield_curve['2y'],
            type: 'scattergl',
            mode: 'lines',
            name: '2Y Yield',
            line: { color: '#ff3b3b', width: 1.5 }
        }
    ];

    return (
        <PageGrid>
            {/* Top Strip: Macro Summary */}
            <div className="col-span-12 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
                <StatCard
                    label="US INFLATION"
                    value={`${(getVal('inflation') * 100).toFixed(2)}%`}
                    subValue="YoY"
                    trend={getVal('inflation') > 0.02 ? "down" : "neutral"}
                    chartData={getHist('inflation')}
                />
                <StatCard
                    label="UNEMPLOYMENT"
                    value={`${getVal('unemployment')}%`}
                    trend={getVal('unemployment') > 4 ? "down" : "neutral"}
                    chartData={getHist('unemployment')}
                />
                <StatCard
                    label="FED FUNDS"
                    value={`${getVal('fed_funds')}%`}
                    chartData={getHist('fed_funds')}
                />
                <StatCard
                    label="REAL GDP"
                    value={`${(getVal('gdp') * 100).toFixed(2)}%`}
                    subValue="QoQ"
                    trend={getVal('gdp') > 0 ? "up" : "down"}
                    chartData={getHist('gdp')}
                />
                <StatCard
                    label="10Y YIELD"
                    value={`${getVal('yield_10y')}%`}
                    chartData={getHist('yield_10y')}
                />
                <StatCard
                    label="2Y YIELD"
                    value={`${getVal('yield_2y')}%`}
                    subValue={`Spread: ${getVal('yield_spread').toFixed(2)}`}
                    trend={getVal('yield_spread') < 0 ? "down" : "neutral"}
                    chartData={getHist('yield_spread')}
                />
            </div>

            {/* Yield Curve Dynamics */}
            <div className="col-span-12 md:col-span-8 h-96">
                <TerminalPanel title="YIELD CURVE DYNAMICS" subtitle="10Y vs 2Y (5 Years)">
                    <PlotlyChart
                        data={yieldTraces}
                        layout={{
                            hovermode: 'x unified',
                            showlegend: true,
                            legend: { x: 0, y: 1, bgcolor: 'rgba(0,0,0,0.5)' },
                            xaxis: { showgrid: true, gridcolor: '#222' },
                            yaxis: { showgrid: true, gridcolor: '#222', title: 'Yield %' }
                        }}
                    />
                </TerminalPanel>
            </div>

            {/* Economic Commentary */}
            <div className="col-span-12 md:col-span-4 h-96">
                <TerminalPanel title="ECONOMIC COMMENTARY" subtitle="Automated Analysis">
                    <div className="p-4 font-mono text-sm text-terminal-text leading-relaxed whitespace-pre-wrap">
                        {commentary}
                    </div>
                </TerminalPanel>
            </div>
        </PageGrid>
    );
}
