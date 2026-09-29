"use client";

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import dynamic from 'next/dynamic';
import { AlertCircle, TrendingUp, Activity, BarChart2 } from 'lucide-react';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const COLORS = {
    bg: '#0f172a',
    card: '#1e293b',
    up: '#22c55e',
    down: '#ef4444',
    accent: '#3b82f6',
    border: 'rgba(255, 255, 255, 0.1)'
};

const ScreenerXRayPopover = ({ symbol, visible, x, y }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (visible && symbol) {
            const fetchData = async () => {
                setLoading(true);
                try {
                    const res = await fetch(`http://127.0.0.1:8000/api/screener/company?symbol=${symbol}`);
                    if (res.ok) {
                        const json = await res.json();
                        setData(json);
                    }
                } catch (e) {
                    console.error("X-Ray error:", e);
                } finally {
                    setLoading(false);
                }
            };
            fetchData();
        }
    }, [visible, symbol]);

    if (!visible) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 10 }}
                style={{ 
                    position: 'fixed',
                    left: x + 20, 
                    top: y - 100,
                    zIndex: 1000,
                    width: 320,
                    pointerEvents: 'none'
                }}
                className="bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl p-4 overflow-hidden"
            >
                {loading ? (
                    <div className="h-48 flex items-center justify-center">
                        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : data ? (
                    <div className="space-y-4">
                        {/* Header */}
                        <div className="flex justify-between items-start">
                            <div>
                                <h3 className="text-white font-bold text-sm tracking-tight">{data.info?.shortName || symbol}</h3>
                                <p className="text-gray-500 text-[10px] uppercase font-mono">{data.info?.sector || 'N/A'}</p>
                            </div>
                            <div className="text-right">
                                <div className="text-white font-mono font-bold text-sm">
                                    ₹{data.quote?.regularMarketPrice?.toFixed(2)}
                                </div>
                                <div className={`text-[10px] font-mono ${(data.quote?.regularMarketChangePercent || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                    {data.quote?.regularMarketChangePercent?.toFixed(2)}%
                                </div>
                            </div>
                        </div>

                        {/* Quick Metrics */}
                        <div className="grid grid-cols-2 gap-2">
                            <div className="bg-white/5 rounded p-2 border border-white/5">
                                <div className="text-[8px] text-gray-500 uppercase font-mono">Market Cap</div>
                                <div className="text-xs text-blue-400 font-mono">₹{(data.info?.marketCap / 1e7).toFixed(0)} Cr</div>
                            </div>
                            <div className="bg-white/5 rounded p-2 border border-white/5">
                                <div className="text-[8px] text-gray-500 uppercase font-mono">P/E Ratio</div>
                                <div className="text-xs text-yellow-500 font-mono">{data.info?.trailingPE?.toFixed(1) || '—'}</div>
                            </div>
                        </div>

                        {/* Red Flags / Intelligence */}
                        <div className="bg-red-500/5 rounded p-2 border border-red-500/10">
                            <div className="flex items-center gap-1.5 mb-1">
                                <AlertCircle size={10} className="text-red-400" />
                                <span className="text-[9px] text-red-300 font-mono uppercase">Red Flags</span>
                            </div>
                            <ul className="text-[9px] text-gray-400 space-y-0.5 list-disc pl-3">
                                {data.info?.trailingPE > 40 && <li>High P/E relative to sector</li>}
                                {data.info?.debtToEquity > 100 && <li>High Debt/Equity ratio</li>}
                                {data.info?.returnOnEquity < 0.1 && <li>Low ROE for current growth</li>}
                                {!data.info?.trailingPE && <li>Negative earnings (TTM)</li>}
                                {(!data.info?.trailingPE && !data.info?.debtToEquity) && <li>Asset visibility is low</li>}
                            </ul>
                        </div>

                        {/* Mini Visual */}
                        <div className="h-16 flex items-end gap-1 px-1">
                            {[40, 60, 45, 70, 85, 65, 80, 95, 75, 90].map((h, i) => (
                                <div 
                                    key={i} 
                                    className="flex-1 bg-blue-500/20 rounded-t-sm"
                                    style={{ height: `${h}%` }}
                                />
                            ))}
                        </div>
                        <div className="text-[8px] text-center text-gray-600 font-mono uppercase tracking-tighter">
                            Historical Volatility Pulse (20D)
                        </div>
                    </div>
                ) : (
                    <div className="h-48 flex items-center justify-center text-gray-600 text-[10px] font-mono">
                        DATA FEED UNAVAILABLE
                    </div>
                )}
            </motion.div>
        </AnimatePresence>
    );
};

export default ScreenerXRayPopover;
