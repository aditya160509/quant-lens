/**
 * Quant360 Tactical Intelligence Panel (Watchlist)
 * Master Blueprint Implementation
 */

'use client';

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { motion, AnimatePresence, Reorder, useDragControls } from 'framer-motion';
import { 
  Settings,
  MoreVertical,
  PlusCircle,
  Edit2,
  Check,
  X,
  Zap,
  ChevronDown,
  Maximize2,
  ExternalLink,
  Layout,
  GripVertical,
  Trash2
} from 'lucide-react';
import { CHART_THEME } from '../chart_engine/types';
import TradingViewSearch from '../symbols/TradingViewSearch';
import { 
  type WatchlistSymbol, 
  type ColorFlag, 
  COLOR_FLAG_MAP,
  type TickerIntelligence,
  type TickerSignal
} from './watchlistTypes';
import { useWatchlist } from './useWatchlist';

// =============================================================================
// TYPES
// =============================================================================

interface WatchlistPanelProps {
    onSymbolClick?: (symbol: string) => void;
    priceData?: Map<string, any>;
    sparklineData?: Map<string, number[]>;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function WatchlistPanel({
    onSymbolClick,
    priceData = new Map(),
    sparklineData = new Map(),
}: WatchlistPanelProps) {
    const {
        lists,
        activeList,
        activeSymbols,
        activeListId,
        setActiveList,
        addSymbol,
        removeSymbol,
        reorderSymbols,
        isLeaderboardMode,
        sortMode,
        setLeaderboardMode,
        createList,
        renameList,
    } = useWatchlist();

    const [searchFocused, setSearchFocused] = useState(false);
    const [showListMenu, setShowListMenu] = useState(false);
    const [editingListId, setEditingListId] = useState<string | null>(null);
    const [editName, setEditName] = useState('');
    const scrollRef = useRef<HTMLDivElement>(null);

    // Live Price/Sparkline State
    const [tickerData, setTickerData] = useState<Map<string, any>>(new Map());
    const [localSparklines, setLocalSparklines] = useState<Map<string, number[]>>(new Map());

    const symbolsKey = activeSymbols.map(s => s.symbol).join(',');

    // Fetch Price Data for all active symbols
    useEffect(() => {
        if (activeSymbols.length === 0) return;

        const fetchData = async () => {
            const newData = new Map(tickerData);
            const newSparklines = new Map(localSparklines);

            for (const item of activeSymbols) {
                try {
                    // Try to get 1y daily data for sparkline and current price
                    const symbol = item.symbol.replace('/', '-');
                    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
                    const res = await fetch(`${API_BASE}/api/prices/${encodeURIComponent(symbol)}?interval=1d&period=1y`);
                    if (res.ok) {
                        const json = await res.json();
                        const candles = json.candles || [];
                        if (candles.length > 0) {
                            const last = candles[candles.length - 1];
                            const prev = candles[candles.length - 2] || last;
                            
                            newData.set(item.symbol, {
                                price: last.c,
                                changePercent: ((last.c - prev.c) / prev.c) * 100,
                                high: last.h,
                                low: last.l,
                                volume: last.v,
                                avgVolume: candles.reduce((acc: number, c: any) => acc + (c.v || 0), 0) / candles.length,
                                ema200: last.c * 0.98, // Mock EMA for now
                            });
                            
                            newSparklines.set(item.symbol, candles.slice(-20).map((c: any) => c.c));
                        }
                    }
                } catch (err) {
                    console.error('Failed to fetch price for', item.symbol, err);
                }
            }
            setTickerData(newData);
            setLocalSparklines(newSparklines);
        };

        fetchData();
        const timer = setInterval(fetchData, 10000); // 10s refresh
        return () => clearInterval(timer);
    }, [symbolsKey]); // Refresh when list changes

    // Derived Sorted Symbols (Leaderboard Logic)
    const sortedSymbols = useMemo(() => {
        if (!isLeaderboardMode || sortMode === 'none') {
            return [...activeSymbols].sort((a, b) => (a.order || 0) - (b.order || 0));
        }
        
        return [...activeSymbols].sort((a, b) => {
            const dataA = tickerData.get(a.symbol) || priceData.get(a.symbol);
            const dataB = tickerData.get(b.symbol) || priceData.get(b.symbol);
            if (!dataA || !dataB) return 0;
            
            if (sortMode === 'change') return Math.abs(dataB.changePercent || 0) - Math.abs(dataA.changePercent || 0);
            if (sortMode === 'volatility') return (dataB.volatility || 0) - (dataA.volatility || 0);
            if (sortMode === 'confluence') {
                const scoreA = (dataA.signals?.trend ? 1 : 0) + (dataA.signals?.momentum ? 1 : 0) + (dataA.signals?.liquidity ? 1 : 0);
                const scoreB = (dataB.signals?.trend ? 1 : 0) + (dataB.signals?.momentum ? 1 : 0) + (dataB.signals?.liquidity ? 1 : 0);
                return scoreB - scoreA;
            }
            return 0;
        });
    }, [activeSymbols, isLeaderboardMode, sortMode, priceData, tickerData]);


    return (
        <div
            style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                background: CHART_THEME.bgSecondary,
                backdropFilter: 'blur(30px)',
                WebkitBackdropFilter: 'blur(30px)',
                borderLeft: `1px solid ${CHART_THEME.border}`,
                overflow: 'hidden',
                position: 'relative',
            }}
        >
            {/* Top Bar: Selector & Meta Controls */}
            <div
                style={{
                    padding: '16px 16px 12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div
                        onClick={() => setShowListMenu(!showListMenu)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            background: showListMenu ? CHART_THEME.bgPrimary : CHART_THEME.bgPrimary + '80',
                            border: `1px solid ${showListMenu ? CHART_THEME.accent : CHART_THEME.border}`,
                            padding: '6px 12px',
                            borderRadius: '24px',
                            fontSize: '11px',
                            color: CHART_THEME.textPrimary,
                            fontWeight: 700,
                            cursor: 'pointer',
                            letterSpacing: '0.05em',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                            transition: 'all 0.2s',
                            position: 'relative',
                        }}
                    >
                        {activeList?.name.toUpperCase() || 'MY WATCHLIST'}
                        <ChevronDown size={12} strokeWidth={3} />

                        {/* Dropdown Menu */}
                        <AnimatePresence>
                            {showListMenu && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 10 }}
                                    style={{
                                        position: 'absolute',
                                        top: 'calc(100% + 8px)',
                                        left: 0,
                                        width: '200px',
                                        background: CHART_THEME.bgSecondary,
                                        border: `1px solid ${CHART_THEME.border}`,
                                        borderRadius: '12px',
                                        padding: '8px',
                                        zIndex: 100,
                                        boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
                                        backdropFilter: 'blur(20px)',
                                    }}
                                    onClick={e => e.stopPropagation()}
                                >
                                    {lists.map(list => (
                                        <div 
                                            key={list.id}
                                            style={{
                                                padding: '8px 12px',
                                                borderRadius: '6px',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                                background: activeListId === list.id ? CHART_THEME.accent + '15' : 'transparent',
                                                color: activeListId === list.id ? CHART_THEME.accent : CHART_THEME.textPrimary,
                                                cursor: 'pointer',
                                                fontSize: '11px',
                                                fontWeight: 600,
                                            }}
                                            onClick={() => {
                                                setActiveList(list.id);
                                                setShowListMenu(false);
                                            }}
                                        >
                                            {list.name}
                                            <div style={{ display: 'flex', gap: '4px' }}>
                                                <Edit2 
                                                    size={12} 
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setEditingListId(list.id);
                                                        setEditName(list.name);
                                                    }} 
                                                />
                                            </div>
                                        </div>
                                    ))}
                                    <div style={{ height: '1px', background: CHART_THEME.border, margin: '8px 0' }} />
                                    <div 
                                        style={{
                                            padding: '8px 12px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '8px',
                                            color: CHART_THEME.accent,
                                            cursor: 'pointer',
                                            fontSize: '11px',
                                            fontWeight: 700,
                                        }}
                                        onClick={() => {
                                            createList(`WL ${lists.length + 1}`);
                                            setShowListMenu(false);
                                        }}
                                    >
                                        <PlusCircle size={14} />
                                        NEW WATCHLIST
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Rename Modal (Lightweight) */}
                    {editingListId && (
                        <div style={{
                            position: 'fixed',
                            inset: 0,
                            zIndex: 1000,
                            background: 'rgba(0,0,0,0.8)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '20px',
                        }}>
                            <div style={{
                                background: CHART_THEME.bgSecondary,
                                border: `1px solid ${CHART_THEME.border}`,
                                borderRadius: '12px',
                                padding: '16px',
                                width: '100%',
                                maxWidth: '300px',
                            }}>
                                <div style={{ fontSize: '12px', fontWeight: 800, color: CHART_THEME.textPrimary, marginBottom: '12px' }}>RENAME LIST</div>
                                <input 
                                    autoFocus
                                    value={editName}
                                    onChange={e => setEditName(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && editingListId && (renameList(editingListId, editName), setEditingListId(null))}
                                    placeholder="Enter name..."
                                    style={{
                                        width: '100%',
                                        background: CHART_THEME.bgPrimary,
                                        border: `1px solid ${CHART_THEME.border}`,
                                        padding: '10px',
                                        borderRadius: '8px',
                                        color: CHART_THEME.textPrimary,
                                        fontSize: '12px',
                                        outline: 'none',
                                    }}
                                />
                                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                                    <button 
                                        onClick={() => setEditingListId(null)}
                                        style={{ background: 'transparent', border: 'none', color: CHART_THEME.textMuted, cursor: 'pointer', fontSize: '11px', fontWeight: 700 }}
                                    >CANCEL</button>
                                    <button 
                                        onClick={() => editingListId && (renameList(editingListId, editName), setEditingListId(null))}
                                        style={{ background: CHART_THEME.accent, border: 'none', color: '#000', borderRadius: '4px', padding: '6px 12px', cursor: 'pointer', fontSize: '11px', fontWeight: 800 }}
                                    >SAVE</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <ThunderToggle 
                        active={isLeaderboardMode} 
                        onClick={() => setLeaderboardMode(!isLeaderboardMode, 'change')} 
                    />
                    <div style={{ width: '1px', height: '16px', background: CHART_THEME.border, margin: '0 4px' }} />
                    <HeaderIcon 
                        icon={<ExternalLink size={14} />} 
                        title="Pop-out" 
                        onClick={() => window.open(window.location.href, '_blank', 'width=1200,height=800')} 
                    />
                    <HeaderIcon 
                        icon={<Maximize2 size={14} />} 
                        title="Fullscreen" 
                        onClick={() => {
                            if (!document.fullscreenElement) {
                                document.documentElement.requestFullscreen();
                            } else {
                                if (document.exitFullscreen) document.exitFullscreen();
                            }
                        }}
                    />
                </div>
            </div>

            {/* WL Tabs (Minimalist) */}
            <div
                style={{
                    display: 'flex',
                    padding: '0 16px',
                    gap: '4px',
                }}
            >
                {['WL1', 'WL2', 'WL3', 'WL4', 'WL5'].map((tab, idx) => {
                    const list = lists[idx];
                    const isActive = activeList?.id === list?.id;
                    return (
                        <button
                            key={tab}
                            onClick={() => {
                                if (list) {
                                    setActiveList(list.id);
                                } else {
                                    createList(tab);
                                }
                            }}
                            style={{
                                flex: 1,
                                padding: '8px 0',
                                fontSize: '10px',
                                fontWeight: isActive ? 800 : 500,
                                background: isActive ? CHART_THEME.bgPrimary : 'transparent',
                                border: 'none',
                                borderRadius: '4px 4px 0 0',
                                color: isActive ? CHART_THEME.accent : CHART_THEME.textMuted,
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                borderBottom: isActive ? `2px solid ${CHART_THEME.accent}` : '2px solid transparent',
                            }}
                        >
                            {list ? list.name.substring(0, 4) : tab}
                        </button>
                    );
                })}
            </div>

            {/* TradingView Search Integration */}
            <div style={{ padding: '12px 16px' }}>
                <TradingViewSearch 
                    onSelect={(s) => activeListId && addSymbol(activeListId, s)}
                    placeholder="SEARCH & ADD SYMBOL..."
                />
            </div>

            {/* Symbol List (Framer Motion Reorder) */}
            <div 
                ref={scrollRef}
                style={{ 
                    flex: 1, 
                    overflowY: 'auto', 
                    overflowX: 'hidden',
                    padding: '0 8px 16px 8px',
                }}
                className="custom-scrollbar"
            >
                {activeSymbols.length === 0 ? (
                    <EmptyState />
                ) : (
                    <Reorder.Group 
                        axis="y" 
                        values={sortedSymbols} 
                        onReorder={(newOrder) => {
                            if (!isLeaderboardMode && activeListId) reorderSymbols(activeListId, newOrder);
                        }}
                        style={{ listStyle: 'none', padding: 0, margin: 0 }}
                    >
                        {sortedSymbols.map((item) => (
                            <WatchlistRow
                                key={item.symbol}
                                item={item}
                                intelligence={deriveIntelligence(item.symbol, tickerData.get(item.symbol), localSparklines.get(item.symbol) || [])}
                                onSymbolClick={() => onSymbolClick?.(item.symbol)}
                                onRemove={() => activeListId && removeSymbol(activeListId, item.symbol)}
                                data={tickerData.get(item.symbol)}
                                isLeaderboardMode={isLeaderboardMode}
                            />
                        ))}
                    </Reorder.Group>
                )}
            </div>

            <style jsx global>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: ${CHART_THEME.border};
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: ${CHART_THEME.textMuted};
                }
            `}</style>
        </div>
    );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

/**
 * Derives visual intelligence data from raw price info
 */
function deriveIntelligence(symbol: string, priceInfo: any, sparkline: number[]): TickerIntelligence {
    const change = priceInfo?.changePercent || 0;
    const price = priceInfo?.price || 0;
    const high = priceInfo?.high || price * 1.01;
    const low = priceInfo?.low || price * 0.99;
    
    // Calculate range progress (0 = Low, 1 = High)
    const rangeProgress = Math.max(0, Math.min(1, (price - low) / (high - low || 1)));

    return {
        symbol,
        signals: {
            trend: price > (priceInfo?.ema200 || price * 0.98), // Dot 1: Trend
            momentum: Math.abs(change) > 1.0,                   // Dot 2: Momentum
            liquidity: priceInfo?.volume > (priceInfo?.avgVolume * 1.5), // Dot 3: Liquidity
        },
        rangeProgress,
        isVolPulse: priceInfo?.volume > (priceInfo?.avgVolume * 2.5),
        sparkline: sparkline || []
    };
}

/**
 * Watchlist Row Component
 */
function WatchlistRow({
    item,
    intelligence,
    onSymbolClick,
    onRemove,
    isLeaderboardMode,
    data,
}: {
    item: WatchlistSymbol;
    intelligence: TickerIntelligence;
    onSymbolClick: () => void;
    onRemove: () => void;
    isLeaderboardMode: boolean;
    data: any;
}) {
    const change = data?.changePercent || 0;
    const isPositive = change >= 0;
    const priceStr = data?.price ? (data.price > 1000 ? data.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : data.price.toFixed(2)) : '---';
    const changeStr = `${isPositive ? '+' : ''}${change.toFixed(2)}%`;
    
    const controls = useDragControls();

    return (
        <Reorder.Item
            value={item}
            dragListener={false}
            dragControls={controls}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            style={{ marginBottom: '4px' }}
        >
            <div
                className="watchlist-row"
                style={{
                    padding: '10px 12px',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    position: 'relative',
                    overflow: 'hidden',
                    background: CHART_THEME.bgPrimary + '40',
                    border: `1px solid transparent`,
                    transition: 'background-color 0.2s',
                }}
                onDragStart={(e: React.DragEvent) => {
                    if (e.dataTransfer) {
                        e.dataTransfer.setData('text/plain', item.symbol);
                        e.dataTransfer.effectAllowed = 'copy';
                    }
                }}
                draggable={true}
                onClick={onSymbolClick}
            >
                {/* Ghost Range Bar (Background Layer) */}
                <div 
                    style={{
                        position: 'absolute',
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: `${intelligence.rangeProgress * 100}%`,
                        background: (intelligence.rangeProgress > 0.8) ? `${CHART_THEME.upColor}15` : 
                                   (intelligence.rangeProgress < 0.2) ? `${CHART_THEME.downColor}15` : 
                                   `${CHART_THEME.accent}08`,
                        borderRight: intelligence.rangeProgress > 0.8 || intelligence.rangeProgress < 0.2 
                            ? `1px solid ${intelligence.rangeProgress > 0.8 ? CHART_THEME.upColor : CHART_THEME.downColor}30` 
                            : 'none',
                        zIndex: 0,
                        pointerEvents: 'none',
                    }}
                />

                {/* Left Side: Symbol & Signal Matrix */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', zIndex: 1 }}>
                    {!isLeaderboardMode && (
                        <div 
                            style={{ color: CHART_THEME.textMuted, cursor: 'grab' }}
                            onPointerDown={(e) => controls.start(e)}
                        >
                            <GripVertical size={12} opacity={0.4} />
                        </div>
                    )}
                    
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{
                                fontSize: '13px',
                                fontWeight: 800,
                                color: intelligence.isVolPulse ? CHART_THEME.accent : CHART_THEME.textPrimary,
                                fontFamily: CHART_THEME.fontMono,
                                letterSpacing: '-0.02em',
                            }}>
                                {item.symbol}
                            </span>
                            <SignalMatrix signals={intelligence.signals} />
                        </div>
                        <span style={{
                            fontSize: '9px',
                            color: CHART_THEME.textMuted,
                            fontWeight: 600,
                            marginTop: '1px',
                        }}>
                            {item.symbol.includes('.NS') ? 'NSE' : 'NASDAQ'}
                        </span>
                    </div>
                </div>

                {/* Right Side: Sparkline & Price */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px', zIndex: 1 }}>
                    <MiniSparkline data={intelligence.sparkline} isPositive={isPositive} />
                    
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', minWidth: '65px' }}>
                        <span style={{
                            fontSize: '13px',
                            fontWeight: 700,
                            color: CHART_THEME.textPrimary,
                            fontFamily: CHART_THEME.fontMono,
                        }}>
                            {priceStr}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span style={{
                                fontSize: '10px',
                                fontWeight: 800,
                                color: isPositive ? CHART_THEME.upColor : CHART_THEME.downColor,
                            }}>
                                {changeStr}
                            </span>
                            <Trash2 
                                size={10} 
                                style={{ opacity: 0, transition: 'opacity 0.2s' }}
                                className="row-delete-icon"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onRemove();
                                }}
                            />
                        </div>
                    </div>
                </div>
            </div>
            <style jsx>{`
                .watchlist-row:hover {
                    background-color: ${CHART_THEME.bgPrimary}CC !important;
                }
                div:hover .row-delete-icon {
                    opacity: 0.5 !important;
                }
                .row-delete-icon:hover {
                    opacity: 1 !important;
                    color: ${CHART_THEME.downColor};
                }
            `}</style>
        </Reorder.Item>
    );
}

/**
 * Signal Matrix (3 Dots)
 */
function SignalMatrix({ signals }: { signals: TickerSignal }) {
    return (
        <div style={{ display: 'flex', gap: '3px' }}>
            <Dot active={signals.trend} color={CHART_THEME.accentBlue} title="Trend: Above EMA" />
            <Dot active={signals.momentum} color="#A78BFA" title="Momentum: RSI Power" />
            <Dot active={signals.liquidity} color="#FBBF24" title="Liquidity: High Vol" />
        </div>
    );
}

function Dot({ active, color, title }: { active: boolean; color: string; title: string }) {
    return (
        <div 
            title={title}
            style={{
                width: '4px',
                height: '4px',
                borderRadius: '50%',
                background: active ? color : CHART_THEME.border,
                boxShadow: active ? `0 0 6px ${color}` : 'none',
                transition: 'all 0.4s ease',
            }}
        />
    );
}

/**
 * Premium Canvas-based Mini Sparkline
 */
function MiniSparkline({ data, isPositive }: { data: number[]; isPositive: boolean }) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Simplified mock data if none provided
        const plotData = data?.length > 0 ? data : Array.from({ length: 20 }, (_, i) => Math.sin(i / 3) + Math.random() * 0.5);
        
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const min = Math.min(...plotData);
        const max = Math.max(...plotData);
        const range = max - min || 1;

        ctx.beginPath();
        ctx.strokeStyle = isPositive ? CHART_THEME.upColor : CHART_THEME.downColor;
        ctx.lineWidth = 1.8;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        plotData.forEach((val, i) => {
            const x = (i / (plotData.length - 1)) * w;
            const y = h - ((val - min) / range) * h;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        
        ctx.stroke();

        // Add subtle gradient fill
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, (isPositive ? CHART_THEME.upColor : CHART_THEME.downColor) + '30');
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.fill();

    }, [data, isPositive]);

    return (
        <canvas 
            ref={canvasRef} 
            width={45} 
            height={18} 
            style={{ width: '45px', height: '18px', opacity: 0.8 }} 
        />
    );
}

/**
 * Thunderbolt Leaderboard Toggle
 */
function ThunderToggle({ active, onClick }: { active: boolean; onClick: () => void }) {
    return (
        <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={onClick}
            style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                background: active ? CHART_THEME.accent + '20' : 'transparent',
                border: `1px solid ${active ? CHART_THEME.accent : CHART_THEME.border}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: active ? CHART_THEME.accent : CHART_THEME.textMuted,
                cursor: 'pointer',
                transition: 'all 0.3s',
                boxShadow: active ? `0 0 10px ${CHART_THEME.accent}30` : 'none',
            }}
            title="Live Leaderboard Mode"
        >
            <Zap size={14} fill={active ? CHART_THEME.accent : 'none'} strokeWidth={2.5} />
        </motion.button>
    );
}

function HeaderIcon({ icon, title, onClick }: { icon: React.ReactNode; title: string; onClick?: () => void }) {
    return (
        <button
            title={title}
            onClick={onClick}
            style={{
                width: '28px',
                height: '28px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'transparent',
                border: `1px solid ${CHART_THEME.border}`,
                borderRadius: '6px',
                color: CHART_THEME.textSecondary,
                cursor: 'pointer',
                transition: 'all 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = CHART_THEME.textMuted}
            onMouseLeave={e => e.currentTarget.style.borderColor = CHART_THEME.border}
        >
            {icon}
        </button>
    );
}

function EmptyState() {
    return (
        <div style={{
            padding: '60px 20px',
            textAlign: 'center',
            color: CHART_THEME.textMuted,
        }}>
            <Layout size={32} opacity={0.2} style={{ marginBottom: '16px', marginInline: 'auto' }} />
            <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em' }}>GRID EMPTY</div>
            <div style={{ fontSize: '10px', opacity: 0.5, marginTop: '8px' }}>
                SEARCH TICKER TO INITIATE
            </div>
        </div>
    );
}

export default WatchlistPanel;
