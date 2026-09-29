"use client";

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import dynamic from 'next/dynamic';
import TerminalPanel from '@/components/TerminalPanel';
import TradingViewSearch from '@/components/symbols/TradingViewSearch';

// Dynamic Plotly import
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

import { 
    Target, TrendingUp, Activity, Globe, Droplets, RefreshCw, AlertTriangle, 
    AlertCircle, Building2, BarChart2, Search, DollarSign, PieChart, Users, 
    Ruler, FileText, LayoutGrid, Zap, Layers, GripVertical, Pin, PinOff, PlusSquare,
    Database
} from 'lucide-react';

// DND Kit for Draggable Columns
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    horizontalListSortingStrategy,
    useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { restrictToHorizontalAxis } from '@dnd-kit/modifiers';

import ScreenerXRayPopover from './ScreenerXRayPopover';
import UniverseModal from './UniverseModal';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const TABS = [
    { id: "tradeable", label: "TRADEABLE UNIVERSE", icon: LayoutGrid, endpoint: "tradeable-universe" },
    { id: "trend", label: "TREND QUALITY", icon: TrendingUp, endpoint: "trend-quality" },
    { id: "volatility", label: "VOLATILITY", icon: Activity, endpoint: "volatility" },
    { id: "regime", label: "REGIME", icon: Globe, endpoint: "regime" },
    { id: "liquidity", label: "LIQUIDITY", icon: Droplets, endpoint: "liquidity" },
    { id: "rotation", label: "ROTATION", icon: RefreshCw, endpoint: "rotation" },
    { id: "events", label: "EVENTS", icon: AlertTriangle, endpoint: "events" },
    { id: "stress", label: "STRESS", icon: Zap, endpoint: "stress" },
    { id: "company", label: "COMPANY ANALYSIS", icon: Building2, endpoint: "company" },
];

// Sub-tabs for Company Analysis 
const COMPANY_SUB_TABS = [
    { id: 'overview', label: 'Overview', icon: FileText },
    { id: 'chart', label: 'Chart', icon: TrendingUp },
    { id: 'fundamentalsFilter', label: 'Fund. Filter', icon: Search, isNew: true },
    { id: 'financials', label: 'Financials', icon: DollarSign },
    { id: 'quarters', label: 'Quarterly', icon: BarChart2 },
    { id: 'peers', label: 'Peers', icon: Users },
    { id: 'ratios', label: 'Ratios', icon: Ruler },
    { id: 'shareholding', label: 'Shareholding', icon: PieChart },
];

const COLORS = {
    bg: '#0a0e17',
    card: '#111827',
    border: '#1f2937',
    accent: '#fbbf24',
    up: '#22c55e',
    down: '#ef4444',
    text: '#f3f4f6',
    muted: '#9ca3af',
    dim: '#6b7280',
};

const TAG_COLORS = {
    'Tradable Now': '#22c55e',
    'Tradable with Care': '#eab308',
    'Avoid': '#ef4444',
    'Stable': '#22c55e',
    'Fragile': '#f97316',
    'Thin': '#ef4444',
    'Durable': '#22c55e',
    'Late Stage': '#eab308',
    'Neutral': '#6b7280',
    'Very Low': '#3b82f6',
    'Low': '#22c55e',
    'Normal': '#6b7280',
    'Elevated': '#f97316',
    'High': '#ef4444',
    'Calm': '#22c55e',
    'Stress': '#ef4444',
    'Aligned': '#22c55e',
    'Accumulation': '#22c55e',
    'Distribution': '#ef4444',
};

// =============================================================================
// COMPONENTS
// =============================================================================

const QuickStatTile = ({ label, value, subtext, color }) => (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
        <div className="text-[10px] font-mono uppercase text-gray-500 mb-1">{label}</div>
        <div className="text-xl font-mono font-bold" style={{ color: color || COLORS.text }}>{value ?? '—'}</div>
        {subtext && <div className="text-[10px] font-mono text-gray-500 mt-1">{subtext}</div>}
    </div>
);

const Tag = ({ value, colorMap }) => {
    const color = colorMap?.[value] || TAG_COLORS[value] || COLORS.muted;
    // Auto-format joined words in tag values
    const label = value ? formatLabel(String(value)) : '—';
    
    return (
        <span 
            className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold whitespace-nowrap"
            style={{ 
                background: `${color}11`, 
                color, 
                border: `1px solid ${color}33`,
                boxShadow: `0 0 10px ${color}11`
            }}
        >
            {label}
        </span>
    );
};

const LineSparkline = ({ data, width = 80, height = 24, color = COLORS.up }) => {
    if (!data || data.length === 0) return null;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const points = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * height}`).join(' ');
    
    return (
        <div style={{ width, height }} className="flex items-center">
            <svg width={width} height={height} className="overflow-visible">
                <path d={`M ${points}`} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        </div>
    );
};

const SignalBadges = ({ badges }) => {
    if (!badges || badges.length === 0) return null;
    return (
        <div className="flex gap-1 flex-wrap">
            {badges.map((b, i) => (
                <span key={i} className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded text-[9px] font-mono">
                    {b}
                </span>
            ))}
        </div>
    );
};

// =============================================================================
// PERFORMANCE DNA - HEATMAP MATRIX (Phase 2)
// =============================================================================
const PerformanceDNA = ({ row }) => {
    const metrics = [
        { key: 'change_1d', label: '1D' },
        { key: 'change_5d', label: '5D' },
        { key: 'change_20d', label: '20D' }
    ];

    const getColor = (val) => {
        if (!val) return 'bg-gray-800';
        if (val > 5) return 'bg-green-500';
        if (val > 2) return 'bg-green-600';
        if (val > 0) return 'bg-green-900';
        if (val < -5) return 'bg-red-500';
        if (val < -2) return 'bg-red-600';
        if (val < 0) return 'bg-red-900';
        return 'bg-gray-800';
    };

    return (
        <div className="flex gap-0.5" title={`1D: ${row.change_1d?.toFixed(1)}% | 5D: ${row.change_5d?.toFixed(1)}% | 20D: ${row.change_20d?.toFixed(1)}%`}>
            {metrics.map(m => (
                <div key={m.key} className={`w-3 h-5 rounded-sm ${getColor(row[m.key])} transition-colors duration-500`} />
            ))}
        </div>
    );
};

const RegimePulse = ({ status }) => {
    const colors = {
        'Aligned': '#22c55e',
        'Bullish': '#22c55e',
        'Bearish': '#ef4444',
        'Neutral': '#6b7280',
        'Fractal Extreme': '#fbbf24',
        'Chaos': '#ef4444'
    };
    const color = colors[status] || '#6b7280';
    return (
        <div className="flex items-center gap-1.5" title={status}>
            <div className={`w-2 h-2 rounded-full animate-pulse shadow-[0_0_8px]`} style={{ backgroundColor: color, shadowColor: color }} />
            <span className="text-[10px] text-gray-400">{status}</span>
        </div>
    );
};

// =============================================================================
// DRAGGABLE TABLE COMPONENTS (Sprint 1)
// =============================================================================

const SortableHeader = ({ col, id, sortConfig, onSort }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id });

    const style = {
        transform: CSS.Translate.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        zIndex: isDragging ? 100 : 1,
    };

    const isSorted = sortConfig?.key === col.key;

    return (
        <th 
            ref={setNodeRef} 
            style={style}
            onClick={() => onSort(col.key)}
            className={`px-4 py-3 text-left text-gray-400 font-semibold uppercase tracking-wider border-b border-white/10 group cursor-pointer hover:bg-white/[0.02] ${isSorted ? 'bg-white/[0.05] text-yellow-500' : ''}`}
        >
            <div className="flex items-center gap-2">
                <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity" onClick={e => e.stopPropagation()}>
                    <GripVertical size={12} className="text-gray-600" />
                </div>
                {col.label}
                {isSorted && (
                    <span className="text-[10px] ml-1">{sortConfig.direction === 'asc' ? '▲' : '▼'}</span>
                )}
            </div>
        </th>
    );
};

const DataTable = ({ rows, columns, maxRows = 25, onPin, pinnedRows = [], onAddToWatchlist, allScanRows = [] }) => {
    const [page, setPage] = React.useState(0);
    const [columnOrder, setColumnOrder] = React.useState(columns.map(c => c.key));
    const [xray, setXray] = React.useState({ visible: false, symbol: '', x: 0, y: 0 });
    const [sortConfig, setSortConfig] = React.useState({ key: 'dollar_volume', direction: 'desc' });
    const [expandedRow, setExpandedRow] = React.useState(null); // Ticker of expanded row
    
    // Pulse effect storage
    const [pulsingRows, setPulsingRows] = React.useState({});

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const handleDragEnd = (event) => {
        const { active, over } = event;
        if (active.id !== over.id) {
            setColumnOrder((items) => {
                const oldIndex = items.indexOf(active.id);
                const newIndex = items.indexOf(over.id);
                return arrayMove(items, oldIndex, newIndex);
            });
        }
    };

    const handleSort = (key) => {
        let direction = 'desc';
        if (sortConfig.key === key && sortConfig.direction === 'desc') {
            direction = 'asc';
        }
        setSortConfig({ key, direction });
    };

    const sortedRows = useMemo(() => {
        if (!rows) return [];
        const sorted = [...rows].sort((a, b) => {
            const valA = a[sortConfig.key];
            const valB = b[sortConfig.key];
            
            // Handle undefined/null
            if (valA === undefined) return 1;
            if (valB === undefined) return -1;
            
            if (valA < valB) return sortConfig.direction === 'asc' ? -1 : 1;
            if (valA > valB) return sortConfig.direction === 'asc' ? 1 : -1;
            return 0;
        });
        return sorted;
    }, [rows, sortConfig]);

    const orderedColumns = useMemo(() => {
        return columnOrder.map(key => columns.find(c => c.key === key)).filter(Boolean);
    }, [columnOrder, columns]);

    const pageSize = maxRows;
    const totalPages = Math.ceil((sortedRows?.length || 0) / pageSize);
    
    // We don't set page to 0 in effect to avoid cascading renders if it can be handled during render
    const displayPage = React.useMemo(() => {
        // If the number of rows changes and we are out of bounds, we effectively reset to 0
        // But for consistency we'll just use the state. 
        // If we really want to reset on sortedRows change, we should do it cautiously.
        return page;
    }, [page]);
    
    if (!rows || rows.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12 bg-gray-900/20 rounded-lg border border-dashed border-gray-700">
                <Search size={24} className="text-gray-600 mb-2 opacity-20" />
                <div className="text-gray-500 font-mono text-xs uppercase tracking-widest">No matching results</div>
            </div>
        );
    }
    
    const startIdx = page * pageSize;
    const endIdx = Math.min(startIdx + pageSize, sortedRows.length);
    const displayRows = sortedRows.slice(startIdx, endIdx);

    // Filter out rows that are already pinned from the main list
    const filteredMainRows = displayRows.filter(r => !pinnedRows.find(p => p.ticker === r.ticker));
    
    return (
        <div className="overflow-x-auto rounded-lg border border-white/5 shadow-2xl relative">
            <ScreenerXRayPopover {...xray} />
            
            <div className="max-h-[600px] overflow-y-auto no-scrollbar">
                <DndContext 
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                    modifiers={[restrictToHorizontalAxis]}
                >
                    <table className="w-full text-[11px] font-mono border-collapse relative">
                        <thead className="sticky top-0 z-40">
                            <tr className="bg-[#0f172a] shadow-[0_2px_10px_rgba(0,0,0,0.5)]">
                                <th className="sticky left-0 z-50 bg-[#0f172a] px-4 py-3 border-b border-white/10 w-10"></th>
                                <SortableContext items={columnOrder} strategy={horizontalListSortingStrategy}>
                                    {orderedColumns.map((col) => (
                                        <SortableHeader key={col.key} id={col.key} col={col} sortConfig={sortConfig} onSort={handleSort} />
                                    ))}
                                </SortableContext>
                                <th className="px-4 py-3 border-b border-white/10 w-12"></th>
                            </tr>
                        </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                        {/* PINNED ROWS SECTION */}
                        {pinnedRows.length > 0 && (
                            <>
                                <tr className="bg-blue-500/10"><td colSpan={orderedColumns.length + 2} className="px-4 py-1 text-[9px] text-blue-400 font-bold uppercase tracking-wider">Pinned Radar</td></tr>
                                {pinnedRows.map((row, ri) => (
                                    <tr key={`pinned-${ri}`} className="bg-blue-500/[0.05] border-l-2 border-blue-500">
                                        <td className="px-2 py-2 text-center">
                                            <button onClick={() => onPin(row)} className="text-blue-400 hover:text-white"><PinOff size={14} /></button>
                                        </td>
                                        {orderedColumns.map((col, ci) => (
                                            <td key={ci} className="px-4 py-2.5" style={{ color: col.color?.(row) }}>
                                                {col.render ? col.render(row) : (typeof row[col.key] === 'string' ? formatLabel(row[col.key]) : row[col.key])}
                                            </td>
                                        ))}
                                        <td className="px-2 py-2"></td>
                                    </tr>
                                ))}
                                <tr className="bg-gray-800/30"><td colSpan={orderedColumns.length + 2} className="px-4 py-1 text-[9px] text-gray-500 font-bold uppercase tracking-wider">Universe Stream</td></tr>
                            </>
                        )}

                        {filteredMainRows.map((row, ri) => (
                            <React.Fragment key={row.ticker}>
                                <motion.tr 
                                    initial={false}
                                    animate={pulsingRows[row.ticker] ? { 
                                        boxShadow: ['0 0 0px #22c55e00', '0 0 20px #22c55e33', '0 0 0px #22c55e00'],
                                        backgroundColor: ['rgba(34,197,94,0)', 'rgba(34,197,94,0.1)', 'rgba(34,197,94,0)']
                                    } : {}}
                                    transition={{ duration: 2, repeat: Infinity }}
                                    className={`${ri % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.01]'} hover:bg-blue-500/[0.06] transition-all duration-150 group cursor-pointer`}
                                    onClick={() => setExpandedRow(expandedRow === row.ticker ? null : row.ticker)}
                                >
                                    <td className="px-2 py-2 text-center sticky left-0 bg-[#0a0e17] z-20">
                                        <button onClick={(e) => { e.stopPropagation(); onPin(row); }} className="text-gray-500 hover:text-blue-400">
                                            <Pin size={12} />
                                        </button>
                                    </td>
                                    {orderedColumns.map((col, ci) => (
                                        <td 
                                            key={ci} 
                                            className={`px-4 py-2.5 transition-colors relative ${ci < 2 ? 'sticky z-10 bg-[#0a0e17] group-hover:bg-blue-900/40' : ''}`}
                                            style={{ 
                                                left: ci === 1 ? '40px' : (ci === 0 ? '0px' : undefined),
                                                color: col.color?.(row) 
                                            }}
                                            onMouseEnter={(e) => {
                                                if (col.key === 'ticker') {
                                                    setXray({ visible: true, symbol: row.ticker, x: e.clientX, y: e.clientY });
                                                }
                                            }}
                                            onMouseLeave={() => setXray(prev => ({ ...prev, visible: false }))}
                                        >
                                            <div className="flex items-center group-hover:text-white transition-all">
                                                {col.render ? col.render(row) : (typeof row[col.key] === 'string' ? formatLabel(row[col.key]) : row[col.key])}
                                            </div>
                                        </td>
                                    ))}
                                    <td className="px-2 py-2 text-center opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button 
                                            onClick={(e) => { e.stopPropagation(); onAddToWatchlist(row.ticker); }}
                                            className="text-gray-500 hover:text-yellow-500"
                                            title="Add to Watchlist"
                                        >
                                            <PlusSquare size={14} />
                                        </button>
                                    </td>
                                </motion.tr>
                                
                                <AnimatePresence>
                                    {expandedRow === row.ticker && (
                                        <motion.tr
                                            initial={{ height: 0, opacity: 0 }}
                                            animate={{ height: 'auto', opacity: 1 }}
                                            exit={{ height: 0, opacity: 0 }}
                                            className="bg-blue-500/5 overflow-hidden"
                                        >
                                            <td colSpan={orderedColumns.length + 2} className="p-0 border-b border-blue-500/20">
                                                <div className="p-6 bg-gradient-to-b from-blue-500/[0.05] to-transparent">
                                                    <div className="flex items-center justify-between mb-4">
                                                        <h4 className="text-xs font-mono font-bold text-blue-400 uppercase flex items-center gap-2">
                                                            <Users size={14} /> Sector Peer Intelligence Matrix: {row.sector}
                                                        </h4>
                                                        <span className="text-[10px] text-gray-500 font-mono">Top live competitors from active scan</span>
                                                    </div>
                                                    <div className="grid grid-cols-5 gap-4">
                                                        {allScanRows
                                                            .filter(r => r.sector === row.sector && r.ticker !== row.ticker)
                                                            .sort((a,b) => (b.dollar_volume || 0) - (a.dollar_volume || 0))
                                                            .slice(0, 5)
                                                            .map((peer, i) => (
                                                            <div key={i} className="bg-gray-900/50 border border-white/5 rounded p-3 hover:border-blue-500/30 transition-all">
                                                                <div className="flex justify-between items-start mb-2">
                                                                    <span className="font-bold text-white text-xs">{peer.ticker}</span>
                                                                    <span className={`text-[10px] ${peer.change_1d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                                        {peer.change_1d >= 0 ? '+' : ''}{peer.change_1d?.toFixed(1)}%
                                                                    </span>
                                                                </div>
                                                                <div className="space-y-1.5">
                                                                    <div className="flex justify-between text-[9px] text-gray-500 uppercase">
                                                                        <span>RSI</span>
                                                                        <span className="text-gray-300">{peer.rsi?.toFixed(0) || '—'}</span>
                                                                    </div>
                                                                    <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                                                                        <div className="h-full bg-blue-500" style={{ width: `${Math.max(peer.rsi || 0, 5)}%` }} />
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        ))}
                                                        {allScanRows.filter(r => r.sector === row.sector && r.ticker !== row.ticker).length === 0 && (
                                                            <div className="col-span-5 py-4 text-center text-gray-600 text-[10px] font-mono border border-dashed border-gray-800 rounded">
                                                                No other {row.sector} peers found in current scan results.
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>
                                        </motion.tr>
                                    )}
                                </AnimatePresence>
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
                </DndContext>
            </div>

            {totalPages > 1 && (
                <div className="bg-[#0a0e17] border-t border-white/5 py-2 px-4 flex items-center justify-between">
                    <span className="text-[10px] text-gray-500 font-mono">
                        Showing {startIdx + 1}-{endIdx} of {rows.length}
                    </span>
                    <div className="flex items-center gap-2">
                        <button 
                            onClick={(e) => { e.stopPropagation(); setPage(p => Math.max(0, p - 1)); }}
                            disabled={page === 0}
                            className="px-2 py-1 text-[10px] font-mono bg-gray-800 text-gray-400 hover:text-white rounded disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                            ← Prev
                        </button>
                        <span className="text-[10px] font-mono text-gray-500">
                            {page + 1} / {totalPages}
                        </span>
                        <button 
                            onClick={(e) => { e.stopPropagation(); setPage(p => Math.min(totalPages - 1, p + 1)); }}
                            disabled={page >= totalPages - 1}
                            className="px-2 py-1 text-[10px] font-mono bg-gray-800 text-gray-400 hover:text-white rounded disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                            Next →
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};


// =============================================================================
// UNIVERSAL QUERY SHELL - institutional-grade filtration (Phase 3)
// =============================================================================
const UniversalQueryShell = ({ onQuery }) => {
    const [query, setQuery] = useState('');
    
    const palette = [
        { id: 'rsi', label: 'RSI', color: 'text-purple-400', formula: 'RSI < 30' },
        { id: 'price', label: 'Price', color: 'text-green-400', formula: 'CLOSE > 100' },
        { id: 'vol', label: 'Volume', color: 'text-blue-400', formula: 'VOLUME > 1000000' },
        { id: 'mom', label: 'Momentum', color: 'text-yellow-400', formula: 'MOMENTUM > 10' },
        { id: 'atr', label: 'Volatility', color: 'text-red-400', formula: 'ATR > 3' },
    ];

    const prescriptions = [
        { label: 'Mean Reversion', query: 'RSI < 25 AND PRICE < 200' },
        { label: 'Momentum Breakout', query: 'RSI > 65 AND VOLUME > 2000000 AND MOMENTUM > 5' },
        { label: 'Volatility Crush', query: 'ATR < 1.5 AND VOLATILITY < 0.2' }
    ];

    const handleDropMetric = (formula) => {
        setQuery(prev => prev + (prev.length > 0 ? ' AND ' : '') + formula);
    };
    
    return (
        <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="bg-[#0f172a] border border-blue-500/20 rounded-xl p-4 mb-4 shadow-2xl relative group overflow-hidden"
        >
            <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
                <div className="flex items-center gap-2">
                    <Zap size={14} className="text-yellow-500" />
                    <h3 className="text-xs font-mono font-bold text-gray-400 uppercase tracking-widest">Universal Query Oracle 2.0</h3>
                </div>
                <div className="flex gap-2">
                    {palette.map(m => (
                        <button 
                            key={m.id}
                            onClick={() => handleDropMetric(m.formula)}
                            className={`px-2 py-1 rounded border border-white/10 bg-white/5 text-[10px] font-mono hover:bg-white/10 hover:border-white/20 transition-all ${m.color}`}
                        >
                            + {m.label}
                        </button>
                    ))}
                </div>
            </div>
            
            <div className="flex gap-2 mb-3">
                <span className="text-[10px] font-mono text-gray-600 uppercase pt-1">Prescriptions:</span>
                {prescriptions.map(p => (
                    <button key={p.label} onClick={() => setQuery(p.query)} className="px-2 py-0.5 rounded-full border border-gray-700 text-[9px] font-mono text-gray-400 hover:text-white hover:border-gray-500">
                        {p.label}
                    </button>
                ))}
            </div>

            <div className="relative">
                <textarea 
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Enter terminal SQL-style query or use prescriptions..."
                    className="w-full h-24 bg-black/40 border border-white/10 rounded-lg p-4 font-mono text-sm text-green-400 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all outline-none resize-none placeholder:text-gray-700"
                />
                <div className="absolute bottom-3 right-3 flex gap-2">
                    <button onClick={() => setQuery('')} className="px-3 py-1.5 bg-gray-800 text-gray-400 text-[10px] font-mono font-bold rounded hover:text-white">CLEAR</button>
                    <button onClick={() => onQuery(query)} className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-mono font-bold rounded shadow-lg">RUN QUERY</button>
                </div>
            </div>
        </motion.div>
    );
};




// =============================================================================
// VISUAL RADAR - QUADRANT PLOT (Sprint 1)
// =============================================================================

const VisualRadarHUD = ({ rows, onFilterByRange }) => {
    // We use ATR% as Volatility for Y and 20D Change for Performance as X
    const plotData = useMemo(() => {
        if (!rows || rows.length === 0) return [];
        return [{
            x: rows.map(r => r.change_20d || 0),
            y: rows.map(r => r.atr_pct || r.realized_vol * 100 || 0),
            mode: 'markers+text',
            text: rows.map(r => r.ticker),
            textposition: 'top center',
            marker: {
                size: rows.map(r => 8),
                color: rows.map(r => (r.change_20d > 0 ? (r.change_20d > 10 ? '#22c55e' : '#4ade80') : (r.change_20d < -10 ? '#ef4444' : '#f87171'))),
                line: { width: 1, color: 'rgba(255,255,255,0.1)' }
            },
            type: 'scatter'
        }];
    }, [rows]);

    if (!rows || rows.length === 0) return null;

    const handleSelected = (event) => {
        if (event && event.points) {
            const selectedSymbols = event.points.map(p => p.text);
            onFilterByRange(selectedSymbols);
        }
    };

    return (
        <div className="bg-slate-900/40 border border-white/5 rounded-xl p-4 mb-4 backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Activity size={16} className="text-blue-500" />
                    <h3 className="text-[10px] font-mono font-bold text-gray-400 uppercase tracking-widest">Visual Radar: Momentum vs Volatility</h3>
                </div>
                <div className="text-[9px] font-mono text-gray-600 bg-white/5 px-2 py-0.5 rounded">
                    Lasso or Select dots to filter table
                </div>
            </div>
            <div className="h-[250px]">
                <Plot
                    data={plotData}
                    onSelected={handleSelected}
                    layout={{
                        paper_bgcolor: 'transparent',
                        plot_bgcolor: 'transparent',
                        margin: { t: 0, r: 0, b: 30, l: 30 },
                        showlegend: false,
                        xaxis: { 
                            title: { text: 'Performance (20D %)', font: { size: 9, color: '#4b5563', family: 'monospace' } },
                            gridcolor: '#1e293b', zerolinecolor: '#334155', tickfont: { size: 8, color: '#4b5563' }
                        },
                        yaxis: { 
                            title: { text: 'Volatility (ATR/RVol)', font: { size: 9, color: '#4b5563', family: 'monospace' } },
                            gridcolor: '#1e293b', zerolinecolor: '#334155', tickfont: { size: 8, color: '#4b5563' }
                        },
                        dragmode: 'lasso',
                        hovermode: 'closest'
                    }}
                    style={{ width: '100%', height: '100%' }}
                    config={{ displayModeBar: false }}
                />
            </div>
            <div className="flex justify-around mt-2 text-[8px] font-mono uppercase text-gray-500">
                <div className="text-red-400">Chaos Leader (High Vol / Low Perf)</div>
                <div className="text-blue-500">Alpha Hunter (Low Vol / Mid Perf)</div>
                <div className="text-green-400">Durable Leader (Low Vol / High Perf)</div>
                <div className="text-yellow-500">Momentum Trap (High Vol / High Perf)</div>
            </div>
        </div>
    );
};

// =============================================================================
// QUANT ENGINE - BACKTESTER & SENSITIVITY (Sprint 3)
// =============================================================================


const Section = ({ title, count, children, color }) => (
    <div className="rounded-xl border backdrop-blur-sm overflow-hidden shadow-lg transition-all hover:shadow-2xl group" 
        style={{ 
            background: `${COLORS.card}cc`, 
            borderColor: color ? `${color}33` : 'rgba(255,255,255,0.05)' 
        }}>
        <div className="flex items-center justify-between px-5 py-4 border-b bg-gradient-to-r from-white/[0.02] to-transparent" 
            style={{ borderColor: color ? `${color}22` : 'rgba(255,255,255,0.05)' }}>
            <div className="flex items-center gap-3">
                <div className="w-1 h-4 rounded-full" style={{ background: color || COLORS.accent }} />
                <h3 className="text-xs font-mono font-bold uppercase tracking-widest" style={{ color: color || COLORS.text }}>
                    {title}
                </h3>
            </div>
            {count !== undefined && (
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-white/5 text-gray-400 group-hover:text-white transition-colors">
                        {count} <span className="opacity-50 font-normal">assets</span>
                    </span>
                </div>
            )}
        </div>
        <div className="p-4">
            {children}
        </div>
    </div>
);

// =============================================================================
// FILTER CONTROLS COMPONENTS (Task 2.1)
// =============================================================================

const FilterChip = ({ condition, onRemove }) => (
    <div className="flex items-center gap-1 px-2 py-1 bg-blue-500/20 border border-blue-500/30 rounded text-xs font-mono">
        <span className="text-blue-400">{condition.label || `${condition.field} ${condition.operator} ${condition.value}`}</span>
        <button onClick={onRemove} className="text-blue-300 hover:text-white ml-1">×</button>
    </div>
);

const ActiveFilters = ({ conditions, onRemove, onClearAll }) => {
    if (!conditions || conditions.length === 0) return null;
    
    return (
        <div className="flex items-center gap-2 flex-wrap p-3 bg-gray-800/50 rounded-lg border border-gray-700/50 mb-4">
            <span className="text-[10px] font-mono text-gray-500 uppercase">Active Filters:</span>
            {conditions.map((c, i) => (
                <FilterChip key={i} condition={c} onRemove={() => onRemove(i)} />
            ))}
            <button 
                onClick={onClearAll}
                className="text-xs font-mono text-gray-400 hover:text-red-400 ml-2"
            >
                Clear All
            </button>
        </div>
    );
};

const HeatmapHubView = ({ rows }) => {
    if (!rows || rows.length === 0) return null;
    
    // Sort rows by volume/cap for sizing
    const sorted = [...rows].sort((a, b) => (b.dollar_volume || 0) - (a.dollar_volume || 0)).slice(0, 100);
    
    return (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 h-[600px] overflow-y-auto pr-2 no-scrollbar">
            {sorted.map((r, i) => {
                const perf = r.change_1d || 0;
                const color = perf > 3 ? 'bg-green-500 shadow-[0_0_15px_rgba(34,197,94,0.4)]' : 
                             perf > 0 ? 'bg-green-900/80 border-green-500/30' : 
                             perf < -3 ? 'bg-red-500 shadow-[0_0_15px_rgba(239,68,68,0.4)]' : 
                             perf < 0 ? 'bg-red-900/80 border-red-500/30' : 'bg-gray-800';
                
                return (
                    <motion.div 
                        key={r.ticker}
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ delay: i * 0.01 }}
                        className={`${color} border border-white/5 rounded-lg p-3 flex flex-col justify-between aspect-square cursor-pointer hover:scale-105 hover:z-10 transition-all group`}
                    >
                        <div className="flex justify-between items-start">
                            <span className="text-[11px] font-bold text-white font-mono">{r.ticker}</span>
                            <div className="w-1.5 h-1.5 rounded-full bg-white/20 group-hover:bg-white animate-pulse" />
                        </div>
                        <div>
                            <div className="text-lg font-mono font-bold text-white tracking-tighter">
                                {perf > 0 ? '+' : ''}{perf.toFixed(1)}%
                            </div>
                            <div className="text-[8px] text-white/40 font-mono uppercase truncate">{r.sector}</div>
                        </div>
                    </motion.div>
                );
            })}
        </div>
    );
};

// =============================================================================
// SAVED SCANS DROPDOWN (Task 8.1, 8.2)
// =============================================================================

const SavedScansDropdown = ({ onLoadScan, currentConditions }) => {
    const [scans, setScans] = useState([]);
    const [showSaveModal, setShowSaveModal] = useState(false);
    const [scanName, setScanName] = useState('');
    const [loading, setLoading] = useState(false);

    const fetchScans = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/screener/scans`);
            if (res.ok) {
                const data = await res.json();
                setScans(data.scans || []);
            }
        } catch (e) { console.error(e); }
    };

    useEffect(() => { 
        const loadScans = async () => {
            await fetchScans();
        };
        loadScans();
    }, []);

    const saveScan = async () => {
        if (!scanName.trim()) return;
        setLoading(true);
        try {
            await fetch(`${API_BASE}/api/screener/scans`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: scanName,
                    tags: [],
                    state: { conditions: currentConditions }
                })
            });
            await fetchScans();
            setShowSaveModal(false);
            setScanName('');
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    const deleteScan = async (id) => {
        try {
            await fetch(`${API_BASE}/api/screener/scans/${id}`, { method: 'DELETE' });
            await fetchScans();
        } catch (e) { console.error(e); }
    };

    return (
        <div className="relative group">
            <button className="px-3 py-1.5 bg-gray-800 text-gray-400 font-mono text-xs rounded hover:text-white hover:bg-gray-700 flex items-center gap-1.5">
                Saved Scans {scans.length > 0 && <span className="text-yellow-500">({scans.length})</span>}
            </button>
            <div className="absolute right-0 top-full mt-1 w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50 hidden group-hover:block">
                <div className="p-2 border-b border-gray-700 flex justify-between items-center">
                    <span className="text-xs font-mono text-gray-400">SAVED SCANS</span>
                    <button 
                        onClick={() => setShowSaveModal(true)}
                        className="text-xs font-mono text-yellow-500 hover:text-yellow-400"
                    >
                        + Save Current
                    </button>
                </div>
                <div className="max-h-48 overflow-y-auto">
                    {scans.length === 0 ? (
                        <div className="p-3 text-center text-gray-500 text-xs">No saved scans</div>
                    ) : scans.map(scan => (
                        <div key={scan.id} className="p-2 hover:bg-gray-800 flex justify-between items-center">
                            <button 
                                onClick={() => onLoadScan(scan)}
                                className="text-sm text-gray-300 hover:text-white font-mono truncate"
                            >
                                {scan.name}
                            </button>
                            <button 
                                onClick={() => deleteScan(scan.id)}
                                className="text-red-400 hover:text-red-300 text-xs"
                            >
                                ×
                            </button>
                        </div>
                    ))}
                </div>
            </div>
            {showSaveModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 w-80">
                        <h3 className="text-sm font-mono font-bold text-white mb-3">Save Scan</h3>
                        <input 
                            type="text"
                            value={scanName}
                            onChange={(e) => setScanName(e.target.value)}
                            placeholder="Scan name..."
                            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm font-mono text-white mb-3"
                        />
                        <div className="flex gap-2">
                            <button 
                                onClick={saveScan}
                                disabled={loading || !scanName.trim()}
                                className="flex-1 px-3 py-1.5 bg-yellow-500 text-black font-mono text-xs font-bold rounded disabled:opacity-50"
                            >
                                {loading ? 'Saving...' : 'Save'}
                            </button>
                            <button 
                                onClick={() => setShowSaveModal(false)}
                                className="px-3 py-1.5 bg-gray-700 text-gray-300 font-mono text-xs rounded"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// =============================================================================
// FILTER PANELS FOR TABS (Task 3.1-3.5)
// =============================================================================

const TrendFilterPanel = ({ onAddCondition }) => (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3 bg-gray-800/30 rounded-lg border border-gray-700/50 mb-4">
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">RSI Oversold</label>
            <button onClick={() => onAddCondition({ field: 'rsi', operator: 'lt', value: 30, source_tab: 'trend', label: 'RSI < 30' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-blue-600 text-xs font-mono text-white rounded">
                RSI &lt; 30
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">RSI Overbought</label>
            <button onClick={() => onAddCondition({ field: 'rsi', operator: 'gt', value: 70, source_tab: 'trend', label: 'RSI > 70' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-red-600 text-xs font-mono text-white rounded">
                RSI &gt; 70
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Above SMA 50</label>
            <button onClick={() => onAddCondition({ field: 'ma50_dist', operator: 'gt', value: 0, source_tab: 'trend', label: 'Price > SMA50' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-green-600 text-xs font-mono text-white rounded">
                Price &gt; SMA50
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Strong Trend</label>
            <button onClick={() => onAddCondition({ field: 'trend_persistence', operator: 'gt', value: 60, source_tab: 'trend', label: 'Trend > 60%' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-green-600 text-xs font-mono text-white rounded">
                Persistence &gt; 60%
            </button>
        </div>
    </div>
);

const VolatilityFilterPanel = ({ onAddCondition }) => (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3 bg-gray-800/30 rounded-lg border border-gray-700/50 mb-4">
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Low Volatility</label>
            <button onClick={() => onAddCondition({ field: 'realized_vol', operator: 'lt', value: 0.2, source_tab: 'volatility', label: 'Vol < 20%' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-blue-600 text-xs font-mono text-white rounded">
                RVol &lt; 20%
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">High Volatility</label>
            <button onClick={() => onAddCondition({ field: 'realized_vol', operator: 'gt', value: 0.4, source_tab: 'volatility', label: 'Vol > 40%' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-red-600 text-xs font-mono text-white rounded">
                RVol &gt; 40%
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Tight Range</label>
            <button onClick={() => onAddCondition({ field: 'atr_pct', operator: 'lt', value: 2, source_tab: 'volatility', label: 'ATR < 2%' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-blue-600 text-xs font-mono text-white rounded">
                ATR &lt; 2%
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Breakout Setup</label>
            <button onClick={() => onAddCondition({ field: 'atr_pct', operator: 'gt', value: 3, source_tab: 'volatility', label: 'ATR > 3%' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-yellow-600 text-xs font-mono text-white rounded">
                ATR &gt; 3%
            </button>
        </div>
    </div>
);

const LiquidityFilterPanel = ({ onAddCondition }) => (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3 bg-gray-800/30 rounded-lg border border-gray-700/50 mb-4">
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">High Liquidity</label>
            <button onClick={() => onAddCondition({ field: 'dollar_volume', operator: 'gt', value: 1e8, source_tab: 'liquidity', label: '$Vol > 100M' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-green-600 text-xs font-mono text-white rounded">
                $Vol &gt; 100M
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Stable Liquidity</label>
            <button onClick={() => onAddCondition({ field: 'liq_persistence', operator: 'gt', value: 0.5, source_tab: 'liquidity', label: 'Persist > 0.5' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-green-600 text-xs font-mono text-white rounded">
                Persist &gt; 0.5
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Few Gaps</label>
            <button onClick={() => onAddCondition({ field: 'gap_freq', operator: 'lt', value: 0.1, source_tab: 'liquidity', label: 'Gaps < 10%' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-blue-600 text-xs font-mono text-white rounded">
                Gap Freq &lt; 10%
            </button>
        </div>
        <div>
            <label className="text-[10px] font-mono text-gray-500 uppercase block mb-1">Accumulation</label>
            <button onClick={() => onAddCondition({ field: 'smart_money', operator: 'eq', value: 'Accumulation', source_tab: 'liquidity', label: 'Smart $ = Accum' })}
                className="w-full px-2 py-1.5 bg-gray-700 hover:bg-green-600 text-xs font-mono text-white rounded">
                Smart $ Accum
            </button>
        </div>
    </div>
);


// =============================================================================
// INDICATOR LIBRARY - 50+ INDICATORS (Task 5.1)
// =============================================================================

// Indicators and Libraries removed as part of the "Purge"

const baseColumns = [
    { key: 'ticker', label: 'Ticker', render: r => <span className="font-bold text-white cursor-help group-hover:underline">{r.ticker}</span> },
    { key: 'sector', label: 'Sector', render: r => <span className="text-gray-400">{r.sector}</span> },
    { key: 'price', label: 'Price', render: r => formatPrice(r.price, r.ticker) },
    { key: 'change_1d', label: '1D %', render: r => <span className={(r.change_1d || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>{(r.change_1d || 0) >= 0 ? '+' : ''}{(r.change_1d || 0).toFixed(2)}%</span> },
    { key: 'change_5d', label: '5D %', render: r => <span className={(r.change_5d || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>{(r.change_5d || 0) >= 0 ? '+' : ''}{(r.change_5d || 0).toFixed(2)}%</span> },
    { key: 'change_20d', label: '20D %', render: r => <span className={(r.change_20d || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>{(r.change_20d || 0) >= 0 ? '+' : ''}{(r.change_20d || 0).toFixed(2)}%</span> },
    { key: 'dollar_volume', label: '$ Vol', render: r => r.dollar_volume > 1e9 ? `${(r.dollar_volume/1e9).toFixed(1)}B` : r.dollar_volume > 1e6 ? `${(r.dollar_volume/1e6).toFixed(1)}M` : `${(r.dollar_volume/1e3).toFixed(0)}K` },
];

// =============================================================================
// TAB CONTENT COMPONENTS
// =============================================================================
const SectorDistributionHeatmap = ({ value, sectorAvg }) => {
    // value is where this stock sits, sectorAvg is the center
    const percent = Math.min(Math.max((value / (sectorAvg * 2)) * 100, 0), 100);
    return (
        <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden relative" title={`Rank relative to sector average`}>
            <div className="absolute inset-y-0 left-0 bg-blue-500/40" style={{ width: '50%', borderRight: '1px solid rgba(255,255,255,0.2)' }} />
            <div className={`absolute inset-y-0 h-full transition-all duration-500 ${percent > 70 ? 'bg-red-500' : percent > 40 ? 'bg-green-500' : 'bg-blue-400'}`} 
                style={{ width: '4px', left: `calc(${percent}% - 2px)` }} />
        </div>
    );
};

const TradeableContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols, allScanRows }) => {
    const columns = [
        ...baseColumns,
        { key: 'liquidity_tag', label: 'Liquidity', render: r => <Tag value={r.liquidity_tag} /> },
        { key: 'exec_feasibility', label: 'Execution', render: r => <Tag value={r.exec_feasibility} /> },
        { key: 'distribution', label: 'Sector Rank', render: r => <SectorDistributionHeatmap value={r.atr_pct || 0} sectorAvg={2.5} /> },
        { key: 'position_size', label: 'Size', render: r => <span className="text-gray-400">{r.position_size}</span> },
        { key: 'liq_persistence', label: 'Persist', render: r => r.liq_persistence?.toFixed(2), color: r => r.liq_persistence > 0.5 ? COLORS.up : COLORS.down },
        { key: 'gap_freq', label: 'Gap Freq', render: r => `${(r.gap_freq * 100)?.toFixed(1)}%` },
        { key: 'sparkline', label: 'Trend', render: r => <LineSparkline data={r.sparkline} color={r.change_20d >= 0 ? COLORS.up : COLORS.down} /> },
        { key: 'badges', label: 'Signals', render: r => <SignalBadges badges={r.badges} /> },
    ];
    
    const allRowsInTab = useMemo(() => {
        return [
            ...(data?.sections?.section_a?.rows || []), 
            ...(data?.sections?.section_b?.rows || []), 
            ...(data?.sections?.section_c?.rows || [])
        ];
    }, [data]);

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRowsInTab} onFilterByRange={onFilterBySymbols} />
            
            <Section title="Safe Trade List" count={data?.sections?.section_a?.count || 0} color={COLORS.up}>
                <DataTable rows={data?.sections?.section_a?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Caution Names" count={data?.sections?.section_b?.count || 0} color="#eab308">
                <DataTable rows={data?.sections?.section_b?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Avoid List" count={data?.sections?.section_c?.count || 0} color={COLORS.down}>
                <DataTable rows={data?.sections?.section_c?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
        </div>
    );
};

const TrendContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols, allScanRows }) => {
    const columns = [
        ...baseColumns,
        { key: 'trend_tag', label: 'Trend', render: r => <Tag value={r.trend_tag} /> },
        { key: 'distribution', label: 'RSI Bench', render: r => <SectorDistributionHeatmap value={r.rsi || 50} sectorAvg={50} /> },
        { key: 'rsi', label: 'RSI', render: r => r.rsi?.toFixed(0), color: r => r.rsi > 70 ? COLORS.down : r.rsi < 30 ? COLORS.up : COLORS.muted },
        { key: 'ma20_dist', label: 'MA20%', render: r => r.ma20_dist?.toFixed(2) + '%', color: r => r.ma20_dist > 0 ? COLORS.up : COLORS.down },
        { key: 'momentum_20d', label: 'Mom 20D', render: r => r.momentum_20d?.toFixed(2) + '%', color: r => r.momentum_20d > 0 ? COLORS.up : COLORS.down },
        { key: 'trend_persistence', label: 'Persist%', render: r => r.trend_persistence?.toFixed(0) + '%' },
        { key: 'failure_prob', label: 'Fail Risk', render: r => <Tag value={r.failure_prob} /> },
        { key: 'sparkline', label: 'Trend', render: r => <LineSparkline data={r.sparkline} color={r.change_20d >= 0 ? COLORS.up : COLORS.down} /> },
    ];
    
    const allRowsInTab = useMemo(() => {
        return [
            ...(data?.sections?.section_a?.rows || []), 
            ...(data?.sections?.section_b?.rows || []), 
            ...(data?.sections?.section_c?.rows || [])
        ];
    }, [data]);

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRowsInTab} onFilterByRange={onFilterBySymbols} />

            <Section title="Durable Trends" count={data?.sections?.section_a?.count || 0} color={COLORS.up}>
                <DataTable rows={data?.sections?.section_a?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Late Stage" count={data?.sections?.section_b?.count || 0} color="#eab308">
                <DataTable rows={data?.sections?.section_b?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Fake Trends" count={data?.sections?.section_c?.count || 0} color={COLORS.down}>
                <DataTable rows={data?.sections?.section_c?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
        </div>
    );
};

const VolatilityContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols, allScanRows }) => {
    const columns = [
        ...baseColumns,
        { key: 'vol_regime', label: 'Vol Regime', render: r => <Tag value={r.vol_regime} /> },
        { key: 'distribution', label: 'Vol Bench', render: r => <SectorDistributionHeatmap value={r.realized_vol * 100 || 0} sectorAvg={20} /> },
        { key: 'realized_vol', label: 'RVol%', render: r => (r.realized_vol * 100)?.toFixed(1) + '%' },
        { key: 'vol_of_vol', label: 'VoV', render: r => r.vol_of_vol?.toFixed(3) },
        { key: 'down_semivol', label: 'Down Vol', render: r => (r.down_semivol * 100)?.toFixed(1) + '%', color: () => COLORS.down },
        { key: 'vol_asymmetry', label: 'Asymmetry', render: r => <Tag value={r.vol_asymmetry} /> },
        { key: 'range_respect', label: 'Range%', render: r => r.range_respect?.toFixed(0) + '%' },
        { key: 'atr_pct', label: 'ATR%', render: r => r.atr_pct?.toFixed(2) + '%' },
    ];
    
    const allRowsInTab = useMemo(() => {
        return [
            ...(data?.sections?.section_a?.rows || []), 
            ...(data?.sections?.section_b?.rows || []), 
            ...(data?.sections?.section_c?.rows || [])
        ];
    }, [data]);

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRowsInTab} onFilterByRange={onFilterBySymbols} />

            <Section title="Controlled Volatility" count={data?.sections?.section_a?.count || 0} color={COLORS.up}>
                <DataTable rows={data?.sections?.section_a?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Expansion Plays" count={data?.sections?.section_b?.count || 0} color="#eab308">
                <DataTable rows={data?.sections?.section_b?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Chaos Zone" count={data?.sections?.section_c?.count || 0} color={COLORS.down}>
                <DataTable rows={data?.sections?.section_c?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
        </div>
    );
};

const RegimeContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols, allScanRows }) => {
    const columns = [
        ...baseColumns,
        { key: 'regime_alignment', label: 'Alignment', render: r => <Tag value={r.regime_alignment} /> },
        { key: 'momentum_20d', label: 'Mom 20D', render: r => r.momentum_20d?.toFixed(2) + '%', color: r => r.momentum_20d > 0 ? COLORS.up : COLORS.down },
        { key: 'vol_regime', label: 'Vol Regime', render: r => <Tag value={r.vol_regime} /> },
        { key: 'sparkline', label: 'Trend', render: r => <LineSparkline data={r.sparkline} color={r.change_20d >= 0 ? COLORS.up : COLORS.down} /> },
    ];
    
    const allRowsInTab = useMemo(() => {
        return [
            ...(data?.sections?.section_a?.rows || []), 
            ...(data?.sections?.section_b?.rows || []), 
            ...(data?.sections?.section_c?.rows || [])
        ];
    }, [data]);

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRowsInTab} onFilterByRange={onFilterBySymbols} />
            
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <div className="text-xs font-mono text-gray-500 uppercase mb-2">Current Market Regime</div>
                <div className="text-2xl font-mono font-bold" style={{ color: TAG_COLORS[data?.meta?.market_regime] || COLORS.muted }}>
                    {data?.meta?.market_regime || '—'}
                </div>
            </div>

            <Section title="Regime Tailwinds" count={data?.sections?.section_a?.count || 0} color={COLORS.up}>
                <DataTable rows={data?.sections?.section_a?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Neutral" count={data?.sections?.section_b?.count || 0} color={COLORS.muted}>
                <DataTable rows={data?.sections?.section_b?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Regime Headwinds" count={data?.sections?.section_c?.count || 0} color={COLORS.down}>
                <DataTable rows={data?.sections?.section_c?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
        </div>
    );
};

const LiquidityContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols, allScanRows }) => {
    const columns = [
        ...baseColumns,
        { key: 'liquidity_tag', label: 'State', render: r => <Tag value={r.liquidity_tag} /> },
        { key: 'distribution', label: 'Liq Bench', render: r => <SectorDistributionHeatmap value={r.liq_persistence || 0} sectorAvg={0.5} /> },
        { key: 'illiquidity', label: 'Illiq', render: r => r.illiquidity?.toExponential(2) },
        { key: 'illiq_accel', label: 'Accel', render: r => r.illiq_accel?.toFixed(3), color: r => r.illiq_accel > 0 ? COLORS.down : COLORS.up },
        { key: 'liq_persistence', label: 'Persist', render: r => r.liq_persistence?.toFixed(2) },
        { key: 'smart_money', label: 'Smart $', render: r => <Tag value={r.smart_money} /> },
        { key: 'cliff_distance', label: 'Cliff Dist', render: r => r.cliff_distance?.toFixed(0) + '%', color: r => r.cliff_distance < 50 ? COLORS.down : COLORS.up },
        { key: 'exhaustion_timer', label: 'Timer', render: r => r.exhaustion_timer > 100 ? '∞' : r.exhaustion_timer?.toFixed(0) + 'd' },
    ];
    
    const allRowsInTab = useMemo(() => {
        return [
            ...(data?.sections?.section_a?.rows || []), 
            ...(data?.sections?.section_b?.rows || []), 
            ...(data?.sections?.section_c?.rows || [])
        ];
    }, [data]);

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRowsInTab} onFilterByRange={onFilterBySymbols} />

            <Section title="Stable Liquidity" count={data?.sections?.section_a?.count || 0} color={COLORS.up}>
                <DataTable rows={data?.sections?.section_a?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Deteriorating" count={data?.sections?.section_b?.count || 0} color="#eab308">
                <DataTable rows={data?.sections?.section_b?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Cliff Candidates" count={data?.sections?.section_c?.count || 0} color={COLORS.down}>
                <DataTable rows={data?.sections?.section_c?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
        </div>
    );
};

const RotationContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols, allScanRows }) => {
    const columns = [
        ...baseColumns,
        { key: 'relative_strength', label: 'RS', render: r => r.relative_strength?.toFixed(2), color: r => r.relative_strength > 0 ? COLORS.up : COLORS.down },
        { key: 'rs_confirmed', label: 'Confirmed', render: r => r.rs_confirmed ? '✓' : '—', color: r => r.rs_confirmed ? COLORS.up : COLORS.muted },
        { key: 'liq_persistence', label: 'Liq Persist', render: r => r.liq_persistence?.toFixed(2) },
        { key: 'momentum_20d', label: 'Mom 20D', render: r => r.momentum_20d?.toFixed(2) + '%', color: r => r.momentum_20d > 0 ? COLORS.up : COLORS.down },
        { key: 'sparkline', label: 'Trend', render: r => <LineSparkline data={r.sparkline} color={r.change_20d >= 0 ? COLORS.up : COLORS.down} /> },
    ];
    
    const allRowsInTab = useMemo(() => {
        return [
            ...(data?.sections?.section_a?.rows || []), 
            ...(data?.sections?.section_b?.rows || []), 
            ...(data?.sections?.section_c?.rows || [])
        ];
    }, [data]);

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRowsInTab} onFilterByRange={onFilterBySymbols} />

            <Section title="True Leaders" count={data?.sections?.section_a?.count || 0} color={COLORS.up}>
                <DataTable rows={data?.sections?.section_a?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Weak Leaders" count={data?.sections?.section_b?.count || 0} color="#eab308">
                <DataTable rows={data?.sections?.section_b?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="Distribution" count={data?.sections?.section_c?.count || 0} color={COLORS.down}>
                <DataTable rows={data?.sections?.section_c?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
        </div>
    );
};

const EventsContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols, allScanRows }) => {
    const columns = [
        ...baseColumns,
        { key: 'event_risk', label: 'Event Risk', render: r => <Tag value={r.event_risk} /> },
        { key: 'avoid_zone', label: 'Avoid?', render: r => r.avoid_zone ? <span className="text-red-500">⚠ YES</span> : '—' },
        { key: 'vol_regime', label: 'Vol Regime', render: r => <Tag value={r.vol_regime} /> },
        { key: 'sparkline', label: 'Trend', render: r => <LineSparkline data={r.sparkline} color={r.change_20d >= 0 ? COLORS.up : COLORS.down} /> },
    ];
    
    const allRowsInTab = useMemo(() => {
        return [
            ...(data?.sections?.section_a?.rows || []), 
            ...(data?.sections?.section_b?.rows || [])
        ];
    }, [data]);

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRowsInTab} onFilterByRange={onFilterBySymbols} />

            <Section title="Safe Around Events" count={data?.sections?.section_a?.count || 0} color={COLORS.up}>
                <DataTable rows={data?.sections?.section_a?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
            <Section title="High Event Risk" count={data?.sections?.section_b?.count || 0} color={COLORS.down}>
                <DataTable rows={data?.sections?.section_b?.rows || []} columns={columns} onPin={onPin} pinnedRows={pinnedRows} onAddToWatchlist={onAddToWatchlist} allScanRows={allScanRows} />
            </Section>
        </div>
    );
};


// =============================================================================
// CUSTOM INDICATOR MODAL (Task 6.1)
// =============================================================================

const CustomIndicatorModal = ({ isOpen, onClose, onSave }) => {
    const [name, setName] = useState('');
    const [formula, setFormula] = useState('');
    const [description, setDescription] = useState('');
    
    const allowedFunctions = ['sma', 'ema', 'rsi', 'atr', 'std', 'max', 'min', 'abs', 'log', 'sqrt', 'zscore', 'percentRank'];
    const allowedVars = ['close', 'open', 'high', 'low', 'volume'];
    
    if (!isOpen) return null;
    
    return (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-[500px] max-h-[80vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-mono font-bold text-yellow-500">Create Custom Indicator</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">×</button>
                </div>
                
                <div className="space-y-4">
                    <div>
                        <label className="text-xs font-mono text-gray-500 uppercase block mb-1">Indicator Name</label>
                        <input 
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="My Custom RSI"
                            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm font-mono text-white"
                        />
                    </div>
                    
                    <div>
                        <label className="text-xs font-mono text-gray-500 uppercase block mb-1">Formula</label>
                        <textarea 
                            value={formula}
                            onChange={(e) => setFormula(e.target.value)}
                            placeholder="(close - sma(close, 20)) / atr(14)"
                            className="w-full h-24 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm font-mono text-green-400"
                        />
                        <div className="mt-2 text-[10px] font-mono text-gray-500">
                            <div className="mb-1">Allowed functions: <span className="text-blue-400">{allowedFunctions.join(', ')}</span></div>
                            <div>Variables: <span className="text-yellow-400">{allowedVars.join(', ')}</span></div>
                        </div>
                    </div>
                    
                    <div>
                        <label className="text-xs font-mono text-gray-500 uppercase block mb-1">Description (optional)</label>
                        <input 
                            type="text"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Z-score based mean reversion indicator"
                            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm font-mono text-white"
                        />
                    </div>
                    
                    <div className="bg-gray-800/50 rounded p-3">
                        <div className="text-xs font-mono text-gray-500 uppercase mb-2">Example Formulas</div>
                        <div className="space-y-1 text-xs font-mono">
                            <div className="text-green-400">zscore(close, 20)</div>
                            <div className="text-green-400">(close - sma(close, 20)) / atr(14)</div>
                            <div className="text-green-400">ema(rsi(close, 14), 10)</div>
                            <div className="text-green-400">percentRank(roc(close, 20), 252)</div>
                        </div>
                    </div>
                </div>
                
                <div className="flex gap-3 mt-6">
                    <button 
                        onClick={() => { onSave({ name, formula, description }); onClose(); }}
                        disabled={!name || !formula}
                        className="flex-1 px-4 py-2 bg-yellow-500 text-black font-mono text-sm font-bold rounded disabled:opacity-50"
                    >
                        Save Indicator
                    </button>
                    <button 
                        onClick={onClose}
                        className="px-4 py-2 bg-gray-700 text-gray-300 font-mono text-sm rounded"
                    >
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    );
};


// =============================================================================
// FUNDAMENTALS FILTER PANEL (Task 4.1)
// =============================================================================

const FundamentalsFilterPanel = ({ onApplyFilters }) => {
    const [filters, setFilters] = useState({
        pe_min: '', pe_max: '30',
        pb_min: '', pb_max: '3',
        div_yield_min: '1', div_yield_max: '',
        roe_min: '10', roe_max: '',
        roa_min: '', roa_max: '',
        debt_equity_max: '100',
        current_ratio_min: '1',
        market_cap: 'all',
        sector: 'all',
    });
    
    const updateFilter = (key, value) => setFilters(prev => ({ ...prev, [key]: value }));
    
    const sectors = ['all', 'Technology', 'Financials', 'Healthcare', 'Consumer', 'Energy', 'Industrials', 'Materials', 'Utilities', 'Real Estate'];
    const marketCaps = ['all', 'Large (>10B)', 'Mid (2-10B)', 'Small (300M-2B)', 'Micro (<300M)'];
    
    return (
        <div className="space-y-4">
            <div className="bg-gradient-to-r from-green-900/30 to-blue-900/30 rounded-lg border border-green-500/30 p-4">
                <h3 className="text-sm font-mono font-bold text-green-400 uppercase mb-4">Fundamentals Filter (Screen Universe)</h3>
                
                {/* Valuation Ratios */}
                <div className="mb-4">
                    <div className="text-xs font-mono text-gray-500 uppercase mb-2">Valuation</div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">P/E Ratio</label>
                            <div className="flex gap-1">
                                <input type="number" placeholder="Min" value={filters.pe_min} onChange={e => updateFilter('pe_min', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                                <input type="number" placeholder="Max" value={filters.pe_max} onChange={e => updateFilter('pe_max', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">P/B Ratio</label>
                            <div className="flex gap-1">
                                <input type="number" placeholder="Min" value={filters.pb_min} onChange={e => updateFilter('pb_min', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                                <input type="number" placeholder="Max" value={filters.pb_max} onChange={e => updateFilter('pb_max', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">Dividend Yield %</label>
                            <div className="flex gap-1">
                                <input type="number" placeholder="Min" value={filters.div_yield_min} onChange={e => updateFilter('div_yield_min', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                                <input type="number" placeholder="Max" value={filters.div_yield_max} onChange={e => updateFilter('div_yield_max', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">Market Cap</label>
                            <select value={filters.market_cap} onChange={e => updateFilter('market_cap', e.target.value)}
                                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white">
                                {marketCaps.map(m => <option key={m} value={m}>{m}</option>)}
                            </select>
                        </div>
                    </div>
                </div>
                
                {/* Profitability */}
                <div className="mb-4">
                    <div className="text-xs font-mono text-gray-500 uppercase mb-2">Profitability & Quality</div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">ROE %</label>
                            <div className="flex gap-1">
                                <input type="number" placeholder="Min" value={filters.roe_min} onChange={e => updateFilter('roe_min', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                                <input type="number" placeholder="Max" value={filters.roe_max} onChange={e => updateFilter('roe_max', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">ROA %</label>
                            <div className="flex gap-1">
                                <input type="number" placeholder="Min" value={filters.roa_min} onChange={e => updateFilter('roa_min', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                                <input type="number" placeholder="Max" value={filters.roa_max} onChange={e => updateFilter('roa_max', e.target.value)}
                                    className="w-1/2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">Debt/Equity %</label>
                            <input type="number" placeholder="Max" value={filters.debt_equity_max} onChange={e => updateFilter('debt_equity_max', e.target.value)}
                                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                        </div>
                        <div>
                            <label className="text-[10px] font-mono text-gray-400 block mb-1">Current Ratio</label>
                            <input type="number" placeholder="Min" value={filters.current_ratio_min} onChange={e => updateFilter('current_ratio_min', e.target.value)}
                                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-white" />
                        </div>
                    </div>
                </div>
                
                {/* Sector */}
                <div className="mb-4">
                    <div className="text-xs font-mono text-gray-500 uppercase mb-2">Sector Filter</div>
                    <select value={filters.sector} onChange={e => updateFilter('sector', e.target.value)}
                        className="w-full max-w-xs bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs font-mono text-white">
                        {sectors.map(s => <option key={s} value={s}>{s === 'all' ? 'All Sectors' : s}</option>)}
                    </select>
                </div>
                
                {/* Preset Buttons */}
                <div className="flex gap-2 mb-4">
                    <button onClick={() => setFilters({ ...filters, pe_max: '15', roe_min: '15', div_yield_min: '2' })}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono rounded">
                        Value Preset
                    </button>
                    <button onClick={() => setFilters({ ...filters, roe_min: '20', roa_min: '10', debt_equity_max: '50' })}
                        className="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs font-mono rounded">
                        Quality Preset
                    </button>
                    <button onClick={() => setFilters({ ...filters, pe_max: '50', roe_min: '25' })}
                        className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono rounded">
                        Growth Preset
                    </button>
                </div>
                
                <button 
                    onClick={() => onApplyFilters(filters)}
                    className="w-full px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black font-mono text-sm font-bold rounded"
                >
                    Apply Fundamentals Filter
                </button>
            </div>
        </div>
    );
};



const StressContent = ({ data, onPin, pinnedRows, onAddToWatchlist, onFilterBySymbols }) => {
    const columns = baseColumns;
    const fingerprint = data?.fingerprint?.current || [];
    const labels = data?.fingerprint?.labels || [];
    const crises = data?.crisis_similarities || [];
    
    // Flatten rows for Radar (Stress might not have rows in the same structure, check data)
    const allRows = useMemo(() => {
        return (data?.sections?.section_a?.rows || []).concat(data?.sections?.section_b?.rows || []);
    }, [data]);

    const [isHeatmapMode, setIsHeatmapMode] = useState(false); // Added state

    if (isHeatmapMode) {
        return <HeatmapHubView rows={allRows} />;
    }

    return (
        <div className="space-y-4">
            <VisualRadarHUD rows={allRows} onFilterByRange={onFilterBySymbols} />
            <div className="rounded-lg p-4 border" style={{ 
                background: COLORS.card, 
                borderColor: data?.meta?.stress_state === 'Crisis-Like' ? COLORS.down : 
                            data?.meta?.stress_state === 'Stress-Like' ? '#eab308' : COLORS.up 
            }}>
                <div className="text-xs font-mono text-gray-500 uppercase mb-2">Current Market Stress State</div>
                <div className="text-3xl font-mono font-bold" style={{ 
                    color: data?.meta?.stress_state === 'Crisis-Like' ? COLORS.down : 
                           data?.meta?.stress_state === 'Stress-Like' ? '#eab308' : COLORS.up 
                }}>
                    {data?.meta?.stress_state || '—'}
                </div>
                <div className="text-sm font-mono text-gray-400 mt-2">
                    Top Match: <strong>{data?.meta?.top_crisis_match}</strong> ({(data?.meta?.similarity_score * 100)?.toFixed(1)}% similar)
                </div>
                <div className="text-sm font-mono text-gray-500 mt-1">
                    What Breaks First: <span className="text-yellow-400">{data?.what_breaks_first}</span>
                </div>
            </div>
            
            {/* Fingerprint Bar Chart */}
            <div className="rounded-lg border p-4" style={{ background: COLORS.card, borderColor: COLORS.border }}>
                <div className="text-xs font-mono text-gray-500 uppercase mb-3">Current Fingerprint Vector</div>
                <div className="flex items-end justify-around h-32 gap-2">
                    {fingerprint.map((val, i) => (
                        <div key={i} className="text-center flex-1">
                            <div 
                                className="mx-auto rounded-t w-8"
                                style={{ 
                                    height: `${Math.max(val * 100, 4)}px`,
                                    background: val > 0.7 ? COLORS.down : val > 0.4 ? '#eab308' : COLORS.up,
                                }}
                            />
                            <div className="text-[8px] font-mono text-gray-500 mt-1 truncate">{labels[i]?.slice(0, 6)}</div>
                        </div>
                    ))}
                </div>
            </div>
            
            {/* Crisis Similarities */}
            <div className="rounded-lg border p-4" style={{ background: COLORS.card, borderColor: COLORS.border }}>
                <div className="text-xs font-mono text-gray-500 uppercase mb-3">Crisis Similarity Scores</div>
                <div className="space-y-2">
                    {crises.map((c, i) => (
                        <div key={i} className="flex items-center justify-between p-2 rounded bg-gray-800/50">
                            <span className="text-sm font-mono text-gray-300">{c.name}</span>
                            <div className="flex items-center gap-2">
                                <div className="w-24 h-2 bg-gray-700 rounded overflow-hidden">
                                    <div 
                                        className="h-full rounded"
                                        style={{ 
                                            width: `${c.similarity * 100}%`,
                                            background: c.similarity > 0.7 ? COLORS.down : c.similarity > 0.5 ? '#eab308' : COLORS.up,
                                        }}
                                    />
                                </div>
                                <span className="text-xs font-mono w-12 text-right" style={{ 
                                    color: c.similarity > 0.7 ? COLORS.down : c.similarity > 0.5 ? '#eab308' : COLORS.muted 
                                }}>
                                    {(c.similarity * 100).toFixed(1)}%
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// =============================================================================
// COMPANY ANALYSIS COMPONENT (SCREENER.IN STYLE)
// =============================================================================

// Helper to format large numbers
const formatNumber = (num, decimals = 2) => {
    if (num === null || num === undefined || isNaN(num)) return '—';
    if (Math.abs(num) >= 1e12) return `${(num / 1e12).toFixed(decimals)}T`;
    if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(decimals)}B`;
    if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(decimals)}M`;
    if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(decimals)}K`;
    return num.toFixed(decimals);
};

const formatPercent = (num) => {
    if (num === null || num === undefined || isNaN(num)) return '—';
    return `${(num * 100).toFixed(2)}%`;
};

const formatPrice = (price, ticker) => {
    if (price === undefined || price === null || isNaN(price)) return '—';
    const isIndia = ticker?.endsWith('.NS') || ticker?.endsWith('.BO');
    if (isIndia) {
        return `₹${price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
    }
    return `$${price.toFixed(2)}`;
};

const formatLabel = (key) => {
    if (!key) return '—';
    if (typeof key !== 'string') return String(key);
    
    // Manual mapping for common abbreviations
    const abbrevMap = {
        'rsi': 'RSI',
        'atr_pct': 'ATR%',
        'ma20_dist': 'MA20%',
        'ma50_dist': 'MA50%',
        'ma200_dist': 'MA200%',
        'momentum_20d': 'Mom 20D',
        'momentum_60d': 'Mom 60D',
        'change_1d': '1D%',
        'change_5d': '5D%',
        'change_20d': '20D%',
        'dollar_volume': '$ Vol',
        'realized_vol': 'RVol',
        'vol_of_vol': 'VoV',
        'liq_persistence': 'Persistence',
    };
    
    if (abbrevMap[key.toLowerCase()]) return abbrevMap[key.toLowerCase()];

    // Financial mappings logic...

    // 1. Common manual mappings for tricky financial terms
    const manualMappings = {
        'normalizedebitda': 'Normalized EBITDA',
        'basiceps': 'Basic EPS',
        'dilutedeps': 'Diluted EPS',
        'ebitda': 'EBITDA',
        'ebit': 'EBIT',
        'eps': 'EPS',
        'ni': 'Net Income',
        'ttm': 'TTM',
        'pb': 'Price/Book',
        'pe': 'Price/Earnings',
        'roe': 'ROE',
        'roa': 'ROA',
        'eps_ttm': 'EPS (TTM)',
        'pe_ratio': 'P/E Ratio',
        'pb_ratio': 'P/B Ratio',
        'debt_equity': 'Debt/Equity',
        'current_ratio': 'Current Ratio',
        'div_yield': 'Div. Yield %',
        'market_cap': 'Market Cap',
    };
    
    const lowerKey = key.toLowerCase();
    if (manualMappings[lowerKey]) return manualMappings[lowerKey];

    // 2. Initial cleaning: replace underscores and dots with spaces
    let result = key.replace(/[._]/g, ' ');

    // 3. Handle camelCase or ProperCase by adding spaces (e.g., NetIncome -> Net Income)
    result = result.replace(/([a-z])([A-Z])/g, '$1 $2')
                   .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2');

    // 4. Special logic for "joinedtogetherwords" (no spaces)
    if (!result.includes(' ') && result.length > 5) {
        const commonFinanceWords = [
            'depreciation', 'amortization', 'stockholders', 'discontinued', 'restructuring',
            'reconciled', 'normalized', 'operating', 'nonoperating', 'controlling',
            'investment', 'liabilities', 'comprehensive', 'retained', 'earnings',
            'accumulated', 'statement', 'operations', 'provision', 'available',
            'interests', 'minority', 'interest', 'expense', 'revenue', 'income',
            'pretax', 'special', 'charges', 'diluted', 'average', 'shares',
            'common', 'preferred', 'dividend', 'reconcile', 'current', 'assets',
            'equity', 'cash', 'flow', 'continued', 'unusual', 'items',
            'merger', 'acquisition', 'avail', 'gross', 'profit', 'ebitda',
            'ebit', 'eps', 'and', 'with', 'under', 'effect', 'value', 'book',
            'price', 'sales', 'ratio', 'margin', 'long', 'short', 'business',
            'summary', 'sector', 'industry', 'regular', 'market', 'change',
            'percent', 'cap', 'avg', 'volume', 'beta', 'return', 'on', 'trailing',
            'forward', 'enterprise', 'holders', 'institutional', 'mutual', 'fund',
            'total', 'net', 'cost', 'tax', 'rate', 'calcs', 'of', 'in', 'to', 'for',
            'basic', 'com', 'inc', 'corp', 'limited', 'ltd', 'capital', 'working',
            'free', 'payable', 'receivable', 'deferred', 'goodwill', 'inventory',
            'tangible', 'intangible', 'growth', 'yield', 'fixed', 'liquid',
            'debt', 'loan', 'credit', 'interest', 'realized', 'unrealized',
            'adjustment', 'benefit', 'loss', 'gain', 'other', 'all', 'any'
        ];

        // Sort by length descending to match longest words first
        let temp = result.toLowerCase();
        commonFinanceWords.sort((a, b) => b.length - a.length).forEach(word => {
            const regex = new RegExp(`(${word})`, 'gi');
            temp = temp.replace(regex, ' $1 ');
        });
        result = temp.trim().replace(/\s+/g, ' ');
    }

    // 5. Final Title Case formatting and abbreviation handling
    return result
        .split(' ')
        .map(word => {
            if (word.length <= 3 && !['on', 'of', 'to', 'in', 'for', 'and'].includes(word)) return word.toUpperCase();
            return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
        })
        .join(' ');
};

// StatCard for Company Overview
const CompanyStatCard = ({ label, value, subtext, color }) => (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
        <div className="text-[10px] font-mono uppercase text-gray-500 mb-1">{label}</div>
        <div className="text-lg font-mono font-bold" style={{ color: color || COLORS.text }}>{value ?? '—'}</div>
        {subtext && <div className="text-[10px] font-mono text-gray-500 mt-1">{subtext}</div>}
    </div>
);

// Financial Table Component
const FinancialTable = ({ title, headers, rows, useLabelFormatting = false }) => (
    <div className="bg-gray-800/40 rounded-lg border border-gray-700/50 overflow-hidden shadow-xl">
        <div className="px-4 py-2 bg-gray-900/40 border-b border-gray-700/50">
            <h3 className="text-xs font-mono font-bold text-yellow-500 uppercase tracking-wider">{title}</h3>
        </div>
        <div className="overflow-x-auto">
            <table className="w-full text-[11px] font-mono border-collapse">
                <thead>
                    <tr className="bg-gray-900/60 text-gray-400">
                        {headers.map((h, i) => (
                            <th key={i} className="px-4 py-3 text-left font-normal uppercase border-b border-gray-700/50 whitespace-nowrap">{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/30">
                    {rows.map((row, ri) => (
                        <tr key={ri} className="hover:bg-blue-500/5 transition-colors group">
                            {row.map((cell, ci) => (
                                <td key={ci} className={`px-4 py-2.5 ${ci === 0 ? 'text-gray-200' : 'text-gray-400'} group-hover:text-white transition-colors`}>
                                    {ci === 0 && useLabelFormatting ? formatLabel(cell) : cell}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    </div>
);

// Company Overview Sub-Tab
const CompanyOverviewSubTab = ({ data, loading }) => {
    if (loading) return <div className="flex items-center justify-center py-10"><div className="text-gray-500 font-mono animate-pulse">Loading...</div></div>;
    if (!data) return <div className="text-gray-500 font-mono text-center py-10">Search for a stock to see company details</div>;

    const info = data.info || {};
    const quote = data.quote || {};

    return (
        <div className="space-y-4">
            {/* Company Header */}
            <div className="bg-gray-800/40 rounded-lg p-4 border border-gray-700/50">
                <div className="flex items-start justify-between">
                    <div>
                        <h2 className="text-xl font-bold text-white">{info.longName || info.shortName || data.symbol}</h2>
                        <div className="flex items-center gap-3 mt-1">
                            <span className="text-sm text-gray-400">{info.sector}</span>
                            <span className="text-gray-600">•</span>
                            <span className="text-sm text-gray-400">{info.industry}</span>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-3xl font-mono font-bold text-white">
                            {info.currency === 'INR' ? '₹' : '$'}{quote.regularMarketPrice?.toFixed(2) || info.currentPrice?.toFixed(2) || '—'}
                        </div>
                        <div className={`text-sm font-mono ${(quote.regularMarketChangePercent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {(quote.regularMarketChange || 0) >= 0 ? '+' : ''}{quote.regularMarketChange?.toFixed(2) || '0.00'} ({quote.regularMarketChangePercent?.toFixed(2) || '0.00'}%)
                        </div>
                    </div>
                </div>
            </div>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                <CompanyStatCard label="Market Cap" value={formatNumber(info.marketCap)} color={COLORS.accent} />
                <CompanyStatCard label="P/E Ratio" value={info.trailingPE?.toFixed(2)} />
                <CompanyStatCard label="P/B Ratio" value={info.priceToBook?.toFixed(2)} />
                <CompanyStatCard label="EPS (TTM)" value={info.trailingEps?.toFixed(2)} />
                <CompanyStatCard label="Dividend Yield" value={formatPercent(info.dividendYield)} color={COLORS.up} />
                <CompanyStatCard label="52W High" value={info.fiftyTwoWeekHigh?.toFixed(2)} />
                <CompanyStatCard label="52W Low" value={info.fiftyTwoWeekLow?.toFixed(2)} />
                <CompanyStatCard label="Avg Volume" value={formatNumber(info.averageVolume, 0)} />
                <CompanyStatCard label="Beta" value={info.beta?.toFixed(2)} />
                <CompanyStatCard label="Book Value" value={info.bookValue?.toFixed(2)} />
                <CompanyStatCard label="ROE" value={formatPercent(info.returnOnEquity)} color={info.returnOnEquity > 0.15 ? COLORS.up : COLORS.muted} />
                <CompanyStatCard label="ROA" value={formatPercent(info.returnOnAssets)} />
            </div>

            {/* Business Summary */}
            {info.longBusinessSummary && (
                <div className="bg-gray-800/40 rounded-lg p-4 border border-gray-700/50">
                    <h3 className="text-sm font-mono font-bold text-yellow-500 uppercase mb-3">About</h3>
                    <p className="text-sm text-gray-300 leading-relaxed">{info.longBusinessSummary}</p>
                </div>
            )}

            {/* Pros & Cons */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-green-500/5 rounded-lg p-4 border border-green-500/20">
                    <h3 className="text-sm font-mono font-bold text-green-400 uppercase mb-3">Pros</h3>
                    <ul className="space-y-2 text-sm text-gray-300">
                        {info.priceToBook < 1.5 && <li className="flex items-start gap-2"><span className="text-green-400">✓</span> Trading at {info.priceToBook?.toFixed(2)}x book value</li>}
                        {info.dividendYield > 0.02 && <li className="flex items-start gap-2"><span className="text-green-400">✓</span> Healthy dividend yield ({formatPercent(info.dividendYield)})</li>}
                        {info.returnOnEquity > 0.15 && <li className="flex items-start gap-2"><span className="text-green-400">✓</span> Strong ROE ({formatPercent(info.returnOnEquity)})</li>}
                        {info.currentRatio > 1.5 && <li className="flex items-start gap-2"><span className="text-green-400">✓</span> Good liquidity (CR: {info.currentRatio?.toFixed(2)})</li>}
                        {info.revenueGrowth > 0.1 && <li className="flex items-start gap-2"><span className="text-green-400">✓</span> Strong revenue growth ({formatPercent(info.revenueGrowth)})</li>}
                    </ul>
                </div>
                <div className="bg-red-500/5 rounded-lg p-4 border border-red-500/20">
                    <h3 className="text-sm font-mono font-bold text-red-400 uppercase mb-3">Cons</h3>
                    <ul className="space-y-2 text-sm text-gray-300">
                        {info.trailingPE > 30 && <li className="flex items-start gap-2"><span className="text-red-400">✗</span> High P/E ratio ({info.trailingPE?.toFixed(2)})</li>}
                        {info.debtToEquity > 100 && <li className="flex items-start gap-2"><span className="text-red-400">✗</span> High debt/equity ({info.debtToEquity?.toFixed(0)}%)</li>}
                        {info.returnOnEquity < 0.08 && <li className="flex items-start gap-2"><span className="text-red-400">✗</span> Low ROE ({formatPercent(info.returnOnEquity)})</li>}
                        {info.grossMargins < 0.2 && <li className="flex items-start gap-2"><span className="text-red-400">✗</span> Low gross margins ({formatPercent(info.grossMargins)})</li>}
                    </ul>
                </div>
            </div>
        </div>
    );
};

// Company Chart Sub-Tab
const CompanyChartSubTab = ({ data, symbol, loading }) => {
    const [period, setPeriod] = useState('1y');
    const [chartData, setChartData] = useState(null);
    const [chartLoading, setChartLoading] = useState(false);

    useEffect(() => {
        if (!symbol) return;
        const fetchChart = async () => {
            setChartLoading(true);
            try {
                const res = await fetch(`${API_BASE}/api/screener/chart?symbol=${symbol}&period=${period}`);
                if (res.ok) setChartData(await res.json());
            } catch (err) { console.error(err); }
            finally { setChartLoading(false); }
        };
        fetchChart();
    }, [symbol, period]);

    if (loading || chartLoading) return <div className="flex items-center justify-center py-10"><div className="text-gray-500 font-mono animate-pulse">Loading chart...</div></div>;
    if (!chartData) return <div className="text-gray-500 font-mono text-center py-10">No chart data available</div>;

    return (
        <div className="space-y-4">
            <div className="flex gap-2">
                {['1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'].map(p => (
                    <button key={p} onClick={() => setPeriod(p)}
                        className={`px-3 py-1.5 rounded text-xs font-mono uppercase ${period === p ? 'bg-yellow-500 text-black font-bold' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
                        {p}
                    </button>
                ))}
            </div>
            <div className="h-[400px] bg-gray-800/40 rounded-lg border border-gray-700/50 p-4">
                <Plot
                    data={[{
                        x: chartData.dates,
                        open: chartData.open,
                        high: chartData.high,
                        low: chartData.low,
                        close: chartData.close,
                        type: 'candlestick',
                        name: symbol,
                        increasing: { line: { color: '#22c55e' } },
                        decreasing: { line: { color: '#ef4444' } },
                    }]}
                    layout={{
                        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                        xaxis: { showgrid: true, gridcolor: '#1f2937', rangeslider: { visible: false } },
                        yaxis: { showgrid: true, gridcolor: '#1f2937', title: 'Price' },
                        margin: { t: 10, r: 10, b: 40, l: 60 }, font: { color: '#9ca3af' }
                    }}
                    style={{ width: '100%', height: '100%' }}
                    config={{ displayModeBar: false }}
                />
            </div>
        </div>
    );
};

// Company Financials Sub-Tab - Shows ALL available financial data like screener.in
const CompanyFinancialsSubTab = ({ data, loading }) => {
    const [view, setView] = useState('annual');
    
    if (loading) return <div className="flex items-center justify-center py-10"><div className="text-gray-500 font-mono animate-pulse">Loading financials...</div></div>;
    if (!data?.financials) return <div className="text-gray-500 font-mono text-center py-10">No financial data available</div>;

    const financials = data.financials;
    
    // Render a full financial table with ALL rows
    const renderFullTable = (title, dataObj) => {
        if (!dataObj || Object.keys(dataObj).length === 0) {
            return (
                <div className="bg-gray-800/40 rounded-lg border border-gray-700/50 p-4 mb-4">
                    <h3 className="text-sm font-mono font-bold text-yellow-500 uppercase mb-2">{title}</h3>
                    <p className="text-gray-500 text-xs">No data available</p>
                </div>
            );
        }
        
        const dateKeys = Object.keys(dataObj).slice(0, 4);
        const allRowKeys = new Set();
        
        // Collect all unique keys from all periods
        dateKeys.forEach(date => {
            Object.keys(dataObj[date] || {}).forEach(key => allRowKeys.add(key));
        });
        
        // Sort keys alphabetically for consistency
        const sortedKeys = Array.from(allRowKeys).sort();
        
        return (
            <div className="bg-[#0f172a]/40 rounded-xl border border-white/5 overflow-hidden mb-12 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-sm">
                <div className="px-6 py-4 border-b border-white/10 bg-gradient-to-r from-blue-900/20 to-transparent flex justify-between items-center">
                    <h3 className="text-xs font-mono font-bold text-blue-400 uppercase tracking-widest">{title}</h3>
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                        <span className="text-[9px] text-gray-500 uppercase font-mono tracking-tighter">Live Financial Engine</span>
                    </div>
                </div>
                <div className="overflow-x-auto no-scrollbar">
                    <table className="w-full text-[11px] font-mono border-collapse">
                        <thead>
                            <tr className="bg-white/[0.02]">
                                <th className="px-6 py-4 text-left text-gray-500 font-semibold uppercase sticky left-0 z-20 bg-[#0a0e17] border-b border-white/10 shadow-[4px_0_12px_rgba(0,0,0,0.3)]" style={{minWidth: '300px'}}>
                                    Financial Metric
                                </th>
                                {dateKeys.map((date, i) => (
                                    <th key={i} className="px-5 py-4 text-right text-gray-400 font-medium border-b border-white/10" style={{minWidth: '130px'}}>
                                        {date}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {sortedKeys.map((key, ri) => (
                                <tr key={ri} className={`${ri % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.01]'} hover:bg-blue-500/[0.08] transition-all duration-200 group`}>
                                    <td className="px-6 py-3 text-gray-300 sticky left-0 z-10 bg-[#0a0e17] group-hover:text-white group-hover:bg-[#1e293b] transition-all font-medium border-r border-white/5 shadow-[4px_0_12px_rgba(0,0,0,0.2)]" style={{minWidth: '300px'}}>
                                        {formatLabel(key)}
                                    </td>
                                    {dateKeys.map((date, ci) => {
                                        const val = dataObj[date]?.[key];
                                        const isNegative = typeof val === 'number' && val < 0;
                                        return (
                                            <td key={ci} className={`px-5 py-3 text-right font-mono transition-colors ${isNegative ? 'text-red-400 font-bold' : 'text-gray-400 group-hover:text-gray-200'}`}>
                                                {formatNumber(val)}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    };
    
    return (
        <div className="space-y-4">
            {/* View Toggle */}
            <div className="flex gap-2 mb-4">
                <button
                    onClick={() => setView('annual')}
                    className={`px-4 py-2 rounded text-xs font-mono uppercase ${view === 'annual' ? 'bg-yellow-500 text-black font-bold' : 'bg-gray-800 text-gray-400 hover:text-white'}`}
                >
                    Annual
                </button>
                <button
                    onClick={() => setView('quarterly')}
                    className={`px-4 py-2 rounded text-xs font-mono uppercase ${view === 'quarterly' ? 'bg-yellow-500 text-black font-bold' : 'bg-gray-800 text-gray-400 hover:text-white'}`}
                >
                    Quarterly
                </button>
            </div>
            
            {/* Profit & Loss */}
            {renderFullTable('Profit & Loss', financials.income)}
            
            {/* Balance Sheet */}
            {renderFullTable('Balance Sheet', financials.balance)}
            
            {/* Cash Flow */}
            {renderFullTable('Cash Flow', financials.cashflow)}
            
            {/* Quarterly Results - if quarterly view selected */}
            {view === 'quarterly' && data.quarterly && renderFullTable('Quarterly Results', data.quarterly)}
        </div>
    );
};

// Company Quarters Sub-Tab - Shows ALL quarterly data like screener.in
const CompanyQuartersSubTab = ({ data, loading }) => {
    if (loading) return <div className="flex items-center justify-center py-10"><div className="text-gray-500 font-mono animate-pulse">Loading quarterly data...</div></div>;
    if (!data?.quarterly || Object.keys(data.quarterly).length === 0) return <div className="text-gray-500 font-mono text-center py-10">No quarterly data available</div>;

    const quarterly = data.quarterly;
    const dateKeys = Object.keys(quarterly).slice(0, 8);
    const allRowKeys = new Set();
    
    // Collect all unique keys from all quarters
    dateKeys.forEach(date => {
        Object.keys(quarterly[date] || {}).forEach(key => allRowKeys.add(key));
    });
    
    const sortedKeys = Array.from(allRowKeys).sort();

    return (
        <div className="bg-[#0f172a]/40 rounded-xl border border-white/5 overflow-hidden shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-sm">
            <div className="px-6 py-4 border-b border-white/10 bg-gradient-to-r from-teal-900/20 to-transparent flex justify-between items-center">
                <div>
                    <h3 className="text-xs font-mono font-bold text-teal-400 uppercase tracking-widest">Quarterly Performance</h3>
                    <p className="text-[9px] text-gray-500 mt-1 uppercase tracking-tighter">Multi-Period Trend Analysis</p>
                </div>
                <div className="px-2 py-1 bg-teal-500/10 border border-teal-500/20 rounded text-[9px] font-mono text-teal-500">
                    LIVE FEED
                </div>
            </div>
            <div className="overflow-x-auto no-scrollbar">
                <table className="w-full text-[11px] font-mono border-collapse">
                    <thead>
                        <tr className="bg-white/[0.02] text-gray-500">
                            <th className="px-6 py-4 text-left font-semibold uppercase sticky left-0 z-20 bg-[#0a0e17] border-b border-white/10 shadow-[4px_0_12px_rgba(0,0,0,0.3)]" style={{minWidth: '280px'}}>
                                Fundamental Metrics
                            </th>
                            {dateKeys.map((date, i) => (
                                <th key={i} className="px-4 py-4 text-right font-medium border-b border-white/10" style={{minWidth: '110px'}}>
                                    {date}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                        {sortedKeys.map((key, ri) => (
                            <tr key={ri} className={`${ri % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.01]'} hover:bg-teal-500/[0.08] transition-all duration-200 group`}>
                                <td className="px-6 py-3 text-gray-300 sticky left-0 z-10 bg-[#0a0e17] group-hover:text-white group-hover:bg-[#1e293b] transition-all font-medium border-r border-white/5 shadow-[4px_0_12px_rgba(0,0,0,0.2)]" style={{minWidth: '280px'}}>
                                    {formatLabel(key)}
                                </td>
                                {dateKeys.map((date, ci) => {
                                    const val = quarterly[date]?.[key];
                                    const isNegative = typeof val === 'number' && val < 0;
                                    return (
                                        <td key={ci} className={`px-4 py-3 text-right transition-colors ${isNegative ? 'text-red-400 font-bold' : 'text-gray-400 group-hover:text-gray-200'}`}>
                                            {formatNumber(val)}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

// Company Peers Sub-Tab
const CompanyPeersSubTab = ({ data, loading }) => {
    if (loading) return <div className="flex items-center justify-center py-10"><div className="text-gray-500 font-mono animate-pulse">Loading peers...</div></div>;
    if (!data?.peers || data.peers.length === 0) {
        return (
            <div className="text-center py-10">
                <div className="text-gray-500 font-mono mb-2">No peer data available</div>
                <div className="text-gray-600 text-xs">Peers are determined based on the company&apos;s sector</div>
            </div>
        );
    }

    return (
        <div className="overflow-x-auto bg-gray-800/40 rounded-lg border border-gray-700/50">
            <table className="w-full text-xs font-mono">
                <thead><tr className="bg-gray-900/50 border-b border-gray-700">
                    <th className="px-4 py-3 text-left text-gray-500">Company</th>
                    <th className="px-4 py-3 text-right text-gray-500">Price</th>
                    <th className="px-4 py-3 text-right text-gray-500">Market Cap</th>
                    <th className="px-4 py-3 text-right text-gray-500">P/E</th>
                    <th className="px-4 py-3 text-right text-gray-500">P/B</th>
                    <th className="px-4 py-3 text-right text-gray-500">Sector</th>
                </tr></thead>
                <tbody>
                    {data.peers.map((peer, i) => (
                        <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                            <td className="px-4 py-3">
                                <div className="font-bold text-white">{peer.symbol}</div>
                                <div className="text-gray-500 text-[10px]">{peer.name}</div>
                            </td>
                            <td className="px-4 py-3 text-right text-gray-300">
                                {peer.price ? `₹${peer.price.toFixed(2)}` : '—'}
                            </td>
                            <td className="px-4 py-3 text-right text-gray-300">{formatNumber(peer.marketCap)}</td>
                            <td className="px-4 py-3 text-right text-gray-300">{peer.trailingPE?.toFixed(2) || '—'}</td>
                            <td className="px-4 py-3 text-right text-gray-300">{peer.priceToBook?.toFixed(2) || '—'}</td>
                            <td className="px-4 py-3 text-right text-gray-400 text-[10px]">{peer.sector || '—'}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

// Company Ratios Sub-Tab
const CompanyRatiosSubTab = ({ data, loading }) => {
    if (loading) return <div className="flex items-center justify-center py-10"><div className="text-gray-500 font-mono animate-pulse">Loading ratios...</div></div>;
    if (!data?.info) return <div className="text-gray-500 font-mono text-center py-10">No ratio data available</div>;

    const info = data.info;
    const ratioGroups = [
        { title: 'Valuation', items: [
            { label: 'P/E (TTM)', value: info.trailingPE?.toFixed(2) },
            { label: 'Forward P/E', value: info.forwardPE?.toFixed(2) },
            { label: 'P/B', value: info.priceToBook?.toFixed(2) },
            { label: 'P/S', value: info.priceToSalesTrailing12Months?.toFixed(2) },
            { label: 'EV/EBITDA', value: info.enterpriseToEbitda?.toFixed(2) },
        ]},
        { title: 'Profitability', items: [
            { label: 'Gross Margin', value: formatPercent(info.grossMargins) },
            { label: 'Operating Margin', value: formatPercent(info.operatingMargins) },
            { label: 'Profit Margin', value: formatPercent(info.profitMargins) },
            { label: 'ROE', value: formatPercent(info.returnOnEquity) },
            { label: 'ROA', value: formatPercent(info.returnOnAssets) },
        ]},
        { title: 'Liquidity', items: [
            { label: 'Current Ratio', value: info.currentRatio?.toFixed(2) },
            { label: 'Quick Ratio', value: info.quickRatio?.toFixed(2) },
            { label: 'Debt/Equity', value: info.debtToEquity?.toFixed(2) },
        ]},
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {ratioGroups.map((g, gi) => (
                <div key={gi} className="bg-gray-800/40 rounded-lg border border-gray-700/50 p-4">
                    <h3 className="text-sm font-mono font-bold text-yellow-500 uppercase mb-3">{g.title}</h3>
                    <div className="space-y-2">
                        {g.items.map((item, ii) => (
                            <div key={ii} className="flex justify-between items-center py-1 border-b border-gray-700/30">
                                <span className="text-xs text-gray-400">{item.label}</span>
                                <span className="text-sm font-mono text-white">{item.value || '—'}</span>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};

// Company Shareholding Sub-Tab
const CompanyShareholdingSubTab = ({ data, loading }) => {
    if (loading) return <div className="flex items-center justify-center py-10"><div className="text-gray-500 font-mono animate-pulse">Loading shareholding...</div></div>;
    if (!data?.holders) return <div className="text-gray-500 font-mono text-center py-10">No shareholding data available</div>;

    const holders = data.holders;
    return (
        <div className="space-y-4">
            {holders.institutional && (
                <FinancialTable title="Top Institutional Holders" headers={['Holder', 'Shares', '% Out', 'Value']} useLabelFormatting={false}
                    rows={holders.institutional.slice(0, 10).map(h => [
                        h.holder, formatNumber(h.shares, 0), h.pctHeld ? formatPercent(h.pctHeld) : '—', formatNumber(h.value)
                    ])} />
            )}
            {holders.mutual && (
                <FinancialTable title="Top Mutual Fund Holders" headers={['Fund', 'Shares', '% Out', 'Value']} useLabelFormatting={false}
                    rows={holders.mutual.slice(0, 10).map(h => [
                        h.holder, formatNumber(h.shares, 0), h.pctHeld ? formatPercent(h.pctHeld) : '—', formatNumber(h.value)
                    ])} />
            )}
        </div>
    );
};

// Main Company Content Component with Sub-Tabs
const CompanyContent = () => {
    const [symbol, setSymbol] = useState('');
    const [activeSubTab, setActiveSubTab] = useState('overview');
    const [companyData, setCompanyData] = useState(null);
    const [companyLoading, setCompanyLoading] = useState(false);
    const [companyError, setCompanyError] = useState(null);

    const fetchCompanyData = useCallback(async () => {
        if (!symbol || symbol.trim() === '') return;
        setCompanyLoading(true);
        setCompanyError(null);
        try {
            const url = `${API_BASE}/api/screener/company?symbol=${encodeURIComponent(symbol)}`;
            const res = await fetch(url);
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}: ${res.statusText}`);
            }
            const data = await res.json();
            if (data.error) {
                throw new Error(data.error);
            }
            setCompanyData(data);
        } catch (err) {
            console.error('Company fetch error:', err);
            setCompanyError(err.message || 'Failed to fetch company data');
        } finally {
            setCompanyLoading(false);
        }
    }, [symbol]);

    useEffect(() => { 
        if (symbol) fetchCompanyData(); 
    }, [symbol, fetchCompanyData]);

    const handleSymbolSelect = (selected) => { setSymbol(selected); setCompanyData(null); };

    const renderSubTabContent = () => {
        switch (activeSubTab) {
            case 'overview': return <CompanyOverviewSubTab data={companyData} loading={companyLoading} />;
            case 'chart': return <CompanyChartSubTab data={companyData} symbol={symbol} loading={companyLoading} />;
            case 'fundamentalsFilter': return <FundamentalsFilterPanel onApplyFilters={(filters) => console.log('Apply filters:', filters)} />;
            case 'financials': return <CompanyFinancialsSubTab data={companyData} loading={companyLoading} />;
            case 'quarters': return <CompanyQuartersSubTab data={companyData} loading={companyLoading} />;
            case 'peers': return <CompanyPeersSubTab data={companyData} loading={companyLoading} />;
            case 'ratios': return <CompanyRatiosSubTab data={companyData} loading={companyLoading} />;
            case 'shareholding': return <CompanyShareholdingSubTab data={companyData} loading={companyLoading} />;
            default: return null;
        }
    };

    return (
        <div className="space-y-4">
            {/* Search Bar */}
            <div className="flex items-center gap-4 p-4 bg-gray-800/40 rounded-lg border border-gray-700/50">
                <div style={{ width: 300 }}>
                    <TradingViewSearch mode="security" onSelect={handleSymbolSelect} placeholder="Search stocks..." />
                </div>
                {symbol && (
                    <div className="flex items-center gap-2 px-4 py-2 bg-gray-900 border border-gray-700 rounded">
                        <span className="font-mono font-bold text-white">{symbol}</span>
                        {companyData?.info?.shortName && <span className="text-xs text-gray-400">{companyData.info.shortName}</span>}
                    </div>
                )}
            </div>

            {/* Sub-Tab Navigation (screener.in style) */}
            <div className="flex gap-1 overflow-x-auto border-b border-gray-800 pb-1 no-scrollbar">
                {COMPANY_SUB_TABS.map((tab) => (
                    <button key={tab.id} onClick={() => setActiveSubTab(tab.id)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-t text-xs font-mono whitespace-nowrap transition-all border-b-2 ${
                            activeSubTab === tab.id
                                ? 'bg-gray-800 text-blue-400 font-bold border-blue-500'
                                : 'bg-transparent text-gray-400 hover:text-white border-transparent'
                        }`}>
                        <tab.icon size={13} strokeWidth={2} />{tab.label}
                        {tab.isNew && (
                            <span className="ml-1 text-[9px] bg-blue-500 text-white px-1 rounded">NEW</span>
                        )}
                    </button>
                ))}
            </div>

            {/* Sub-Tab Content */}
            {companyError && (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded text-red-400 font-mono text-sm mb-4">
                    Error: {companyError}
                </div>
            )}
            {!symbol ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                    <div className="text-6xl mb-4">...</div>
                    <div className="text-lg font-mono text-white mb-2">Company Analysis</div>
                    <div className="text-sm font-mono text-gray-500 max-w-md">
                        Search for any stock to see detailed company analysis including financials, ratios, peer comparison, and shareholding patterns (screener.in style).
                    </div>
                </div>
            ) : renderSubTabContent()}
        </div>
    );
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function ScreenerQuant360() {
    const [activeTab, setActiveTab] = useState("tradeable");
    const [universe, setUniverse] = useState("INDIA");
    const [window, setWindow] = useState(60);
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [hasRun, setHasRun] = useState(false);
    const [oracleQuery, setOracleQuery] = useState('');
    
    // GOD-TIER FEATURES STATE
    const [pinnedRows, setPinnedRows] = useState([]);
    const [symbolFilter, setSymbolFilter] = useState(null);
    const [isHeatmapMode, setIsHeatmapMode] = useState(false);
    const [showOracle, setShowOracle] = useState(false);
    const [showCustomIndicatorModal, setShowCustomIndicatorModal] = useState(false);
    const [showUniverseModal, setShowUniverseModal] = useState(false);
    const [customIndicators, setCustomIndicators] = useState([]);

    const handleUniverseSelect = (tickers) => {
        setUniverse("CUSTOM");
        runAnalysis();
    };

    const handlePinRow = (row) => {
        setPinnedRows(prev => {
            const isPinned = prev.find(p => p.ticker === row.ticker);
            if (isPinned) return prev.filter(p => p.ticker !== row.ticker);
            return [...prev, row];
        });
    };

    const handleAddToWatchlist = (ticker) => {
        console.log(`Adding ${ticker} to watchlist...`);
        // Integration with existing watchlist system would go here
    };

    const handleFilterBySymbols = (symbols) => {
        setSymbolFilter(symbols);
    };

    const currentTabConfig = useMemo(() => TABS.find(t => t.id === activeTab), [activeTab]);
    
    // Handler to save custom indicator
    const handleSaveCustomIndicator = useCallback((indicator) => {
        setCustomIndicators(prev => [...prev, { ...indicator, id: `CUSTOM_${Date.now()}` }]);
    }, []);
    
    
    const runAnalysis = useCallback(async (customQuery) => {
        setLoading(true);
        setError(null);
        setHasRun(true);
        
        try {
            const queryToUse = customQuery !== undefined ? customQuery : oracleQuery;
            let result;

            if (showOracle && queryToUse) {
                const res = await fetch(`${API_BASE}/api/screener/evaluate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        universe,
                        lookback_days: window,
                        filter_formula: queryToUse,
                        formula_mode: true,
                        active_tab: activeTab
                    })
                });
                if (!res.ok) throw new Error(`Oracle Error: ${res.status}`);
                const rawData = await res.json();
                // Map flat oracle results to sectioned structure
                result = {
                    meta: rawData.meta || { names_scanned: 0, names_passed: rawData.rows?.length || 0, compute_time_ms: 0 },
                    sections: {
                        section_a: { label: "Oracle Results", count: rawData.rows?.length || 0, rows: rawData.rows || [] },
                        section_b: { label: "Other", count: 0, rows: [] },
                        section_c: { label: "Excluded", count: 0, rows: [] }
                    }
                };
            } else {
                const endpoint = currentTabConfig?.endpoint || "tradeable-universe";
                const url = `${API_BASE}/api/screener/${endpoint}?universe_key=${universe}&window=${window}`;
                const res = await fetch(url);
                if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
                result = await res.json();
            }
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [universe, window, currentTabConfig, showOracle, oracleQuery, activeTab]);

    // Auto-run on mount or critical parameter change
    useEffect(() => {
        if (hasRun) runAnalysis();
    }, [universe, window, hasRun, runAnalysis]);
    
    const handleTabChange = (tabId) => {
        setActiveTab(tabId);
        setData(null);
        setHasRun(false);
    };
    
    // Filter data if symbols are selected from Radar
    const filteredData = useMemo(() => {
        if (!data || !symbolFilter) return data;
        const newData = JSON.parse(JSON.stringify(data));
        if (newData.sections) {
            Object.keys(newData.sections).forEach(key => {
                newData.sections[key].rows = newData.sections[key].rows.filter(r => symbolFilter.includes(r.ticker));
                newData.sections[key].count = newData.sections[key].rows.length;
            });
        }
        return newData;
    }, [data, symbolFilter]);

    const allScanRows = useMemo(() => {
        if (!filteredData) return [];
        return filteredData.sections ? Object.values(filteredData.sections).flatMap(s => s.rows || []) : (filteredData?.rows || []);
    }, [filteredData]);

    const renderTabContent = () => {
        // Company tab doesn't need hasRun - it has its own search
        if (activeTab === 'company') {
            return <CompanyContent />;
        }
        
        if (!hasRun) {
            return (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                    <div className="text-6xl mb-4">
                        {currentTabConfig?.icon ? <currentTabConfig.icon size={64} className="text-yellow-500/50" /> : '...'}
                    </div>
                    <div className="text-lg font-mono text-white mb-2">
                        {currentTabConfig?.label || 'SCREENER'}
                    </div>
                    <div className="text-sm font-mono text-gray-500 mb-6 max-w-md">
                        Select universe and window, then click RUN to analyze.
                    </div>
                    <button
                        onClick={runAnalysis}
                        disabled={loading}
                        className="px-8 py-3 bg-yellow-500 text-black font-mono text-sm font-bold rounded hover:bg-yellow-400 disabled:opacity-50"
                    >
                        ▶ RUN ANALYSIS
                    </button>
                </div>
            );
        }
        
        if (loading) {
            return (
                <div className="flex items-center justify-center py-20">
                    <div className="text-gray-500 font-mono animate-pulse">Computing...</div>
                </div>
            );
        }
        
        if (error) {
            return (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded text-red-400 font-mono text-sm">
                    {error}
                </div>
            );
        }
        
        const props = { 
            data: filteredData, 
            onPin: handlePinRow, 
            pinnedRows: pinnedRows, 
            onAddToWatchlist: handleAddToWatchlist,
            onFilterBySymbols: handleFilterBySymbols,
            allScanRows: allScanRows
        };

        if (isHeatmapMode && activeTab !== 'company') {
            return <HeatmapHubView rows={allScanRows} />;
        }

        switch (activeTab) {
            case 'tradeable': return <TradeableContent {...props} />;
            case 'trend': return <TrendContent {...props} />;
            case 'volatility': return <VolatilityContent {...props} />;
            case 'regime': return <RegimeContent {...props} />;
            case 'liquidity': return <LiquidityContent {...props} />;
            case 'rotation': return <RotationContent {...props} />;
            case 'events': return <EventsContent {...props} />;
            case 'stress': return <StressContent {...props} />;
            case 'company': return <CompanyContent />;
            default: return null;
        }
    };
    
    return (
        <div className="h-full flex flex-col" style={{ background: COLORS.bg }}>
            {/* Header */}
            <div className="p-4 border-b border-gray-800">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h1 className="text-lg font-mono font-bold text-yellow-500">QUANT360 SCREENER</h1>
                        <p className="text-xs font-mono text-gray-500">8-Tab Market Intelligence Dashboard</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] font-mono text-gray-500 uppercase">Universe:</span>
                            <button
                                onClick={() => setShowUniverseModal(true)}
                                className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-[10px] font-mono text-white hover:bg-gray-700 transition-all flex items-center gap-2"
                            >
                                <Database size={12} className="text-yellow-500" />
                                {universe === "INDIA" ? "India (NSE/BSE)" : universe === "US" ? "US (NYSE/NASDAQ)" : universe}
                            </button>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-mono text-gray-500 mr-1 uppercase">Timeframe:</span>
                            {[20, 60, 120, 252, '1y', '2y', '3y', '5y'].map(d => {
                                const label = typeof d === 'string' ? d.toUpperCase() : `${d}D`;
                                return (
                                    <button
                                        key={d}
                                        onClick={() => setWindow(d)}
                                        className={`px-3 py-1 rounded text-[10px] font-mono transition-all uppercase ${window === d ? 'bg-yellow-500 text-black font-bold shadow-[0_0_8px_rgba(234,179,8,0.4)]' : 'bg-gray-800 text-gray-400 border border-gray-700 hover:text-white'}`}
                                    >
                                        {label}
                                    </button>
                                );
                            })}
                        </div>
                        <button
                            onClick={() => runAnalysis()}
                            disabled={loading}
                            className="px-4 py-1.5 bg-yellow-500 text-black font-mono text-xs font-bold rounded hover:bg-yellow-400 disabled:opacity-50"
                        >
                            {loading ? 'COMPUTING...' : 'RUN'}
                        </button>
                        <button
                            onClick={() => setShowOracle(!showOracle)}
                            className={`px-3 py-1.5 font-mono text-xs rounded border transition-all ${showOracle ? 'bg-yellow-500 text-black border-yellow-400' : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-white'}`}
                        >
                            {showOracle ? 'Oracle Active' : 'Open Oracle'}
                        </button>
                        <button
                            onClick={() => setIsHeatmapMode(!isHeatmapMode)}
                            className={`px-3 py-1.5 font-mono text-xs rounded border ${isHeatmapMode ? 'bg-indigo-600 text-white border-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]' : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-white'}`}
                        >
                            {isHeatmapMode ? 'Treemap Active' : 'Table View'}
                        </button>
                    </div>
                </div>
                
                <AnimatePresence>
                    {showOracle && (
                        <UniversalQueryShell onQuery={(q) => {
                            setOracleQuery(q);
                            runAnalysis(q);
                        }} />
                    )}
                </AnimatePresence>
                <UniverseModal 
                    isOpen={showUniverseModal}
                    onClose={() => setShowUniverseModal(false)}
                    onSelect={handleUniverseSelect}
                />
                <CustomIndicatorModal 
                    isOpen={showCustomIndicatorModal} 
                    onClose={() => setShowCustomIndicatorModal(false)}
                    onSave={handleSaveCustomIndicator}
                />
                
                
                {/* The "Purge": Legacy Quant Panels Removed */}
                
                {/* Quick Stats */}
                {data?.meta && (
                    <div className="grid grid-cols-6 gap-3 mb-4">
                        <QuickStatTile label="Names Scanned" value={data.meta.names_scanned} color={COLORS.text} />
                        <QuickStatTile label="Names Passed" value={data.meta.names_passed} color={COLORS.up} />
                        <QuickStatTile label="Safe" value={data.quick_stats?.total_safe ?? data.sections?.section_a?.count} color={COLORS.up} />
                        <QuickStatTile label="Caution" value={data.quick_stats?.total_caution ?? data.sections?.section_b?.count} color="#eab308" />
                        <QuickStatTile label="Avoid/Risk" value={data.quick_stats?.total_avoid ?? data.sections?.section_c?.count} color={COLORS.down} />
                        <QuickStatTile label="Compute Time" value={`${data.meta.compute_time_ms?.toFixed(0)}ms`} color={COLORS.muted} />
                    </div>
                )}
                
                {/* Tab Navigation */}
                <div className="flex gap-1 overflow-x-auto pb-2 no-scrollbar">
                    {TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => handleTabChange(tab.id)}
                            className={`flex items-center gap-2 px-4 py-3 rounded-lg text-xs font-mono font-bold whitespace-nowrap transition-all border ${
                                activeTab === tab.id
                                    ? 'bg-yellow-500 text-black border-yellow-500 shadow-[0_0_10px_rgba(234,179,8,0.3)]'
                                    : 'bg-gray-900 text-gray-400 border-gray-800 hover:text-white hover:border-gray-700'
                            }`}
                        >
                            <tab.icon size={14} className={activeTab === tab.id ? "text-black" : "text-gray-500 group-hover:text-white"} />
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>
            
            {/* Content */}
            <div className="flex-1 overflow-auto p-4">
                {renderTabContent()}
            </div>
        </div>
    );
}
