/**
 * Quant360 Alpha Intelligence Console
 * Handles relative strength, correlation, and ghost management.
 */

'use client';

import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Zap, 
  Target, 
  Activity, 
  Layers, 
  TrendingUp, 
  X, 
  Eye, 
  EyeOff,
  ArrowUpRight,
  ArrowDownRight,
  Maximize2,
  ChevronRight,
  Lock,
  LockOpen
} from 'lucide-react';
import { CHART_THEME } from '../chart_engine/types';
import TradingViewSearch from '../symbols/TradingViewSearch';
import { calculateCorrelation, calculateBeta, calculateAlphaVelocity } from '../chart_engine/AlphaEngine/math';

interface GhostMetric {
    symbol: string;
    correlation: number;
    alpha: number;
    beta: number;
    isVisible: boolean;
    color: string;
    ratioHistory: number[];
}

interface AlphaPanelProps {
    primarySymbol: string;
    compareSymbols: string[];
    compareData: Record<string, any[]>;
    primaryData: any[];
    onRemove: (symbol: string) => void;
    onToggleVisibility: (symbol: string) => void;
    onAdd: (symbol: string) => void;
    onClose: () => void;
    anchorIndex: number;
    alphaMode: 'percent' | 'zscore' | 'ratio';
    onModeChange: (mode: 'percent' | 'zscore' | 'ratio') => void;
    visibleGhosts: string[];
}

export function AlphaPanel({
    primarySymbol,
    compareSymbols,
    compareData,
    primaryData,
    onRemove,
    onToggleVisibility,
    onAdd,
    onClose,
    anchorIndex,
    alphaMode,
    onModeChange,
    visibleGhosts: parentVisibleGhosts
}: AlphaPanelProps) {
    const [isAnchorLocked, setIsAnchorLocked] = useState(true);

    const suggestions = useMemo(() => {
        const isIndia = primarySymbol.endsWith('.NS') || primarySymbol.endsWith('.BO');
        return isIndia ? ['^NSEI', 'USDINR=X', 'Reliance.NS'] : ['SPY', 'QQQ', 'DXY', 'BTC-USD'];
    }, [primarySymbol]);

    // Calculate Intelligence for each Ghost using REAL Math
    const ghosts = useMemo(() => {
        // Use visible data from anchor forward
        const startIdx = Math.max(0, anchorIndex);
        const pVisible = primaryData.slice(startIdx);
        const pClose = pVisible.map(b => b.close);
        
        return compareSymbols.map((symbol, idx) => {
            const fullGData = compareData[symbol] || [];
            
            // Find ghost bars that match the visible timestamps
            const visibleTimestamps = new Set(primaryData.map(b => b.timestamp));
            const gVisible = fullGData.filter(b => visibleTimestamps.has(b.timestamp));
            
            // Further slice from the anchor
            const gFromAnchor = gVisible.slice(startIdx);
            const gClose = gFromAnchor.map(b => b.close);

            // Fetch intersection for math
            const minLen = Math.min(pClose.length, gClose.length);
            const pSubset = pClose.slice(0, minLen);
            const gSubset = gClose.slice(0, minLen);

            if (pSubset.length < 2) {
                return {
                    symbol,
                    correlation: 0,
                    alpha: 0,
                    beta: 0,
                    isVisible: true,
                    color: idx === 0 ? '#A78BFA' : '#FBBF24',
                    ratioHistory: []
                };
            }

            const correlation = calculateCorrelation(pSubset, gSubset);
            const alpha = calculateAlphaVelocity(pSubset, gSubset);
            const beta = calculateBeta(pSubset, gSubset);

            // Ratio History for visualization
            const ratioHistory = pSubset.map((p, i) => gSubset[i] / p).slice(-50);
            
            return {
                symbol,
                correlation,
                alpha,
                beta,
                isVisible: parentVisibleGhosts.includes(symbol),
                color: idx === 0 ? '#A78BFA' : '#FBBF24', // Purple, Yellow
                ratioHistory
            };
        });
    }, [compareSymbols, compareData, primaryData, anchorIndex, parentVisibleGhosts]);

    return (
        <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            background: CHART_THEME.bgSecondary,
            borderLeft: `1px solid ${CHART_THEME.border}`,
            padding: '12px',
            gap: '12px',
            position: 'relative',
        }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <Target size={16} color={CHART_THEME.accent} />
                        <span style={{ fontSize: '11px', fontWeight: 900, color: CHART_THEME.textPrimary, letterSpacing: '0.1em' }}>ALPHA ENGINE</span>
                    </div>
                    <div style={{ fontSize: '9px', color: CHART_THEME.textMuted, fontWeight: 700 }}>
                        PRIMARY: <span style={{ color: CHART_THEME.accent }}>{primarySymbol}</span>
                        {anchorIndex > 0 && <span style={{ marginLeft: '8px', color: '#6ee7b7' }}>• ANCHORED</span>}
                    </div>
                </div>
                <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: CHART_THEME.textMuted, cursor: 'pointer' }}>
                    <X size={16} />
                </button>
            </div>

            {/* Live Normalization Control (URGENT TOP PLACEMENT) */}
            <div style={{ 
                background: CHART_THEME.bgPrimary + '60',
                borderRadius: '12px',
                padding: '12px',
                border: `1px solid ${CHART_THEME.border}`,
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '10px', fontWeight: 900, color: CHART_THEME.accent }}>INTELLIGENCE MODE</span>
                    <button 
                        onClick={() => setIsAnchorLocked(!isAnchorLocked)}
                        style={{ background: 'transparent', border: 'none', color: isAnchorLocked ? CHART_THEME.accent : CHART_THEME.textMuted, cursor: 'pointer' }}
                    >
                        {isAnchorLocked ? <Lock size={12} /> : <LockOpen size={12} />}
                    </button>
                </div>
                
                <div style={{ display: 'flex', gap: '4px', background: 'rgba(0,0,0,0.3)', padding: '3px', borderRadius: '6px' }}>
                    {(['percent', 'zscore', 'ratio'] as const).map(mode => (
                        <motion.button
                            key={mode}
                            whileTap={{ scale: 0.95 }}
                            onClick={(e) => {
                                e.stopPropagation();
                                onModeChange(mode);
                            }}
                            style={{
                                flex: 1,
                                padding: '6px 0',
                                fontSize: '9px',
                                fontWeight: 800,
                                border: 'none',
                                background: alphaMode === mode ? CHART_THEME.accent : 'transparent',
                                color: alphaMode === mode ? '#000' : CHART_THEME.textMuted,
                                borderRadius: '4px',
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                textTransform: 'uppercase',
                                zIndex: 10,
                                position: 'relative'
                            }}
                        >
                            {mode}
                        </motion.button>
                    ))}
                </div>
            </div>

            {/* Tactical Search / Drop Zone */}
            <div 
                onDragOver={(e) => {
                    e.preventDefault();
                    e.currentTarget.style.borderColor = CHART_THEME.accent;
                }}
                onDragLeave={(e) => {
                    e.currentTarget.style.borderColor = CHART_THEME.border;
                }}
                onDrop={(e) => {
                    e.preventDefault();
                    e.currentTarget.style.borderColor = CHART_THEME.border;
                    const symbol = e.dataTransfer.getData('text/plain');
                    if (symbol) onAdd(symbol);
                }}
                style={{
                    border: `1px dashed ${CHART_THEME.border}`,
                    borderRadius: '12px',
                    padding: '4px',
                    transition: 'border-color 0.2s',
                    background: CHART_THEME.bgPrimary + '20',
                }}
            >
                <TradingViewSearch 
                    onSelect={onAdd}
                    placeholder="DROP FROM WATCHLIST OR SEARCH..."
                />
            </div>

            {/* Ghost Workspace (Scrollable) */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', paddingRight: '4px' }} className="no-scrollbar">
                <AnimatePresence mode="popLayout">
                    {ghosts.map((ghost) => (
                        <GhostCard 
                            key={ghost.symbol}
                            ghost={ghost}
                            onRemove={() => onRemove(ghost.symbol)}
                            onToggleVisibility={() => onToggleVisibility(ghost.symbol)}
                        />
                    ))}
                </AnimatePresence>

                {ghosts.length === 0 && (
                    <div style={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '40px 20px',
                        textAlign: 'center',
                    }}>
                        <div style={{ 
                            width: '48px', 
                            height: '48px', 
                            borderRadius: '50%', 
                            border: `1px solid ${CHART_THEME.border}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginBottom: '16px',
                            color: CHART_THEME.textMuted
                        }}>
                            <Layers size={24} strokeWidth={1.5} />
                        </div>
                        <div style={{ fontSize: '11px', fontWeight: 900, color: CHART_THEME.textPrimary, marginBottom: '4px' }}>SHADOW STACK READY</div>
                        <div style={{ fontSize: '9px', color: CHART_THEME.textMuted, lineHeight: 1.5 }}>
                            DRAG SYMBOLS FROM WATCHLIST<br/>OR SEARCH TO COMPARE
                        </div>
                    </div>
                )}
            </div>

            {/* Suggestions Footer */}
            <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingTop: '8px', borderTop: `1px solid ${CHART_THEME.border}` }} className="no-scrollbar">
                {suggestions.map(s => (
                    <button
                        key={s}
                        onClick={() => onAdd(s)}
                        style={{
                            padding: '4px 8px',
                            background: 'rgba(255,255,255,0.05)',
                            border: `1px solid ${CHART_THEME.border}`,
                            borderRadius: '4px',
                            fontSize: '8px',
                            fontWeight: 700,
                            color: CHART_THEME.textSecondary,
                            cursor: 'pointer',
                            whiteSpace: 'nowrap'
                        }}
                    >
                        {s.replace('.NS', '').replace('^', '')}
                    </button>
                ))}
            </div>
        </div>
    );
}

function GhostCard({ ghost, onRemove, onToggleVisibility }: { ghost: GhostMetric, onRemove: () => void, onToggleVisibility: () => void }) {
    const alphaStatus = ghost.alpha > 0 ? 'LEADING' : (ghost.alpha < 0 ? 'LAGGING' : 'SYNCHRONIZED');
    const alphaColor = ghost.alpha > 0 ? CHART_THEME.upColor : (ghost.alpha < 0 ? CHART_THEME.downColor : CHART_THEME.textMuted);

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, x: 20 }}
            style={{
                background: CHART_THEME.bgPrimary + '40',
                border: `1px solid ${CHART_THEME.border}`,
                borderRadius: '14px',
                padding: '14px',
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '4px', background: ghost.color }} />
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                <div>
                    <div style={{ fontSize: '14px', fontWeight: 900, color: CHART_THEME.textPrimary, letterSpacing: '-0.02em' }}>{ghost.symbol}</div>
                    <div style={{ fontSize: '8px', color: alphaColor, fontWeight: 900, letterSpacing: '0.1em' }}>{alphaStatus}</div>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                    <button 
                        onClick={onToggleVisibility}
                        style={{ background: 'transparent', border: 'none', color: CHART_THEME.textMuted, cursor: 'pointer', padding: '2px' }}
                    >
                        {ghost.isVisible ? <Eye size={14} /> : <EyeOff size={14} />}
                    </button>
                    <button 
                        onClick={onRemove}
                        style={{ background: 'transparent', border: 'none', color: CHART_THEME.textMuted, cursor: 'pointer', padding: '2px' }}
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px' }}>
                <div>
                    <div style={{ fontSize: '8px', fontWeight: 800, color: CHART_THEME.textMuted, marginBottom: '2px' }}>CORRELATION</div>
                    <div style={{ fontSize: '12px', fontWeight: 900, color: CHART_THEME.textPrimary }}>{ghost.correlation.toFixed(2)}</div>
                </div>
                <div>
                    <div style={{ fontSize: '8px', fontWeight: 800, color: CHART_THEME.textMuted, marginBottom: '2px' }}>ALPHA VELOCITY</div>
                    <div style={{ fontSize: '12px', fontWeight: 900, color: alphaColor }}>
                        {ghost.alpha > 0 ? '+' : ''}{ghost.alpha.toFixed(2)}%
                    </div>
                </div>
            </div>

            {/* Live Beta Meter */}
            <div style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '8px', fontWeight: 900, color: CHART_THEME.textMuted, marginBottom: '6px' }}>
                    <span>SENSITIVITY (BETA)</span>
                    <span style={{ color: CHART_THEME.textPrimary }}>{ghost.beta.toFixed(2)}x</span>
                </div>
                <div style={{ height: '4px', background: CHART_THEME.border, borderRadius: '2px', overflow: 'hidden' }}>
                    <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(100, (ghost.beta / 2) * 100)}%` }}
                        style={{ height: '100%', background: ghost.color, boxShadow: `0 0 10px ${ghost.color}` }} 
                    />
                </div>
            </div>

            {/* Ratio History Sparkline */}
            <div style={{ height: '20px', opacity: 0.5 }}>
                <RatioSparkline data={ghost.ratioHistory} color={ghost.color} />
            </div>
        </motion.div>
    );
}

function RatioSparkline({ data, color }: { data: number[], color: string }) {
    if (data.length < 2) return null;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    
    const points = data.map((val, i) => {
        const x = (i / (data.length - 1)) * 100;
        const y = 100 - ((val - min) / range) * 100;
        return { x, y };
    });

    let path = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
        const xc = (points[i].x + points[i + 1].x) / 2;
        const yc = (points[i].y + points[i + 1].y) / 2;
        path += ` Q ${points[i].x} ${points[i].y}, ${xc} ${yc}`;
    }
    const last = points[points.length - 1];
    path += ` L ${last.x} ${last.y}`;

    return (
        <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
            <path
                stroke={color}
                strokeWidth="4"
                fill="none"
                d={path}
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ filter: `drop-shadow(0 0 2px ${color}40)` }}
            />
        </svg>
    );
}
