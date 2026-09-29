/**
 * Replay Engine - Enhanced TradingView-style Controls
 * Full market replay with click-to-select, bar-by-bar ticking, and proper animations
 */

'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { CHART_THEME } from '../types';
import type { ReplaySpeed, OHLCVBar } from '../types';

// =============================================================================
// TYPES
// =============================================================================

interface EnhancedReplayControlsProps {
    isActive: boolean;
    isPlaying: boolean;
    isSelectMode: boolean;
    speed: ReplaySpeed;
    cursorIndex: number;
    startIndex: number;
    totalBars: number;
    currentBar: OHLCVBar | null;
    onPlay: () => void;
    onPause: () => void;
    onStop: () => void;
    onStepForward: () => void;
    onStepBackward: () => void;
    onSetSpeed: (speed: ReplaySpeed) => void;
    onJumpTo: (index: number) => void;
    onEnterSelectMode: () => void;
}

// =============================================================================
// REPLAY CONTROLS COMPONENT
// =============================================================================

export default function EnhancedReplayControls({
    isActive,
    isPlaying,
    isSelectMode,
    speed,
    cursorIndex,
    startIndex,
    totalBars,
    currentBar,
    onPlay,
    onPause,
    onStop,
    onStepForward,
    onStepBackward,
    onSetSpeed,
    onJumpTo,
    onEnterSelectMode,
}: EnhancedReplayControlsProps) {
    const progressRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);

    // Calculate progress
    const progress = totalBars > 0 && cursorIndex >= startIndex
        ? ((cursorIndex - startIndex) / (totalBars - startIndex)) * 100
        : 0;

    // Handle progress bar click/drag
    const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        if (!progressRef.current || !isActive) return;

        const rect = progressRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = Math.max(0, Math.min(1, x / rect.width));
        const targetIndex = Math.floor(startIndex + (totalBars - startIndex) * percentage);
        onJumpTo(targetIndex);
    }, [isActive, startIndex, totalBars, onJumpTo]);

    // Keyboard shortcuts
    useEffect(() => {
        if (!isActive) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement) return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    isPlaying ? onPause() : onPlay();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    onStepForward();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    onStepBackward();
                    break;
                case 'Escape':
                    e.preventDefault();
                    onStop();
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isActive, isPlaying, onPlay, onPause, onStepForward, onStepBackward, onStop]);

    if (!isActive && !isSelectMode) return null;

    // Select mode UI - shows when waiting for user to click on chart
    if (isSelectMode) {
        return (
            <div
                className="flex items-center justify-center px-4 py-3 gap-4"
                style={{
                    background: `linear-gradient(to right, ${CHART_THEME.accent}15, ${CHART_THEME.bgSecondary}, ${CHART_THEME.accent}15)`,
                    borderTop: `1px solid ${CHART_THEME.accent}40`,
                }}
            >
                <div className="flex items-center gap-3">
                    <div 
                        className="w-8 h-8 rounded-full flex items-center justify-center animate-pulse"
                        style={{ background: CHART_THEME.accent }}
                    >
                        <span className="text-lg">✂️</span>
                    </div>
                    <div>
                        <div 
                            className="text-sm font-mono font-bold"
                            style={{ color: CHART_THEME.accent }}
                        >
                            CLICK ON CHART TO SET REPLAY START POINT
                        </div>
                        <div 
                            className="text-xs font-mono"
                            style={{ color: CHART_THEME.textSecondary }}
                        >
                            All bars after your selection will be hidden. Then press Play to replay.
                        </div>
                    </div>
                </div>
                <button
                    onClick={onStop}
                    className="px-3 py-1.5 text-xs font-mono font-bold rounded transition-colors hover:opacity-80"
                    style={{
                        background: CHART_THEME.downColor,
                        color: '#fff',
                    }}
                >
                    CANCEL
                </button>
            </div>
        );
    }

    return (
        <div
            className="flex flex-col gap-2 px-4 py-3"
            style={{
                background: CHART_THEME.bgSecondary,
                borderTop: `1px solid ${CHART_THEME.border}`,
            }}
        >
            {/* Top Row: Controls + Bar Info */}
            <div className="flex items-center justify-between">
                {/* Left: Playback Controls */}
                <div className="flex items-center gap-1">
                    {/* Step Backward */}
                    <button
                        onClick={onStepBackward}
                        className="w-8 h-8 flex items-center justify-center text-sm font-mono rounded transition-all hover:scale-110"
                        style={{
                            background: CHART_THEME.bgPanel,
                            color: CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                        }}
                        title="Step backward (←)"
                    >
                        ◀◀
                    </button>

                    {/* Play/Pause */}
                    <button
                        onClick={isPlaying ? onPause : onPlay}
                        className="w-10 h-10 flex items-center justify-center text-lg font-bold rounded transition-all hover:scale-105"
                        style={{
                            background: isPlaying ? CHART_THEME.downColor : CHART_THEME.accent,
                            color: isPlaying ? '#fff' : CHART_THEME.bgPrimary,
                        }}
                        title={isPlaying ? "Pause (Space)" : "Play (Space)"}
                    >
                        {isPlaying ? '⏸' : '▶'}
                    </button>

                    {/* Step Forward */}
                    <button
                        onClick={onStepForward}
                        className="w-8 h-8 flex items-center justify-center text-sm font-mono rounded transition-all hover:scale-110"
                        style={{
                            background: CHART_THEME.bgPanel,
                            color: CHART_THEME.textSecondary,
                            border: `1px solid ${CHART_THEME.border}`,
                        }}
                        title="Step forward (→)"
                    >
                        ▶▶
                    </button>

                    <div className="w-px h-6 mx-2" style={{ background: CHART_THEME.border }} />

                    {/* Stop/Exit */}
                    <button
                        onClick={onStop}
                        className="px-3 py-1.5 text-xs font-mono font-bold rounded flex items-center gap-1.5 transition-all hover:scale-105"
                        style={{
                            background: CHART_THEME.downColor + '20',
                            color: CHART_THEME.downColor,
                            border: `1px solid ${CHART_THEME.downColor}40`,
                        }}
                        title="Exit replay (Esc)"
                    >
                        <span>■</span>
                        EXIT
                    </button>
                </div>

                {/* Center: Current Bar Info */}
                {currentBar && (
                    <div 
                        className="flex items-center gap-4 px-3 py-1 rounded"
                        style={{ background: CHART_THEME.bgPanel }}
                    >
                        <div className="text-xs font-mono" style={{ color: CHART_THEME.textSecondary }}>
                            Bar {cursorIndex + 1} of {totalBars}
                        </div>
                        <div className="w-px h-4" style={{ background: CHART_THEME.border }} />
                        <div className="flex items-center gap-2 text-xs font-mono">
                            <span style={{ color: CHART_THEME.textSecondary }}>O:</span>
                            <span style={{ color: CHART_THEME.textPrimary }}>{currentBar.open.toFixed(2)}</span>
                            <span style={{ color: CHART_THEME.textSecondary }}>H:</span>
                            <span style={{ color: CHART_THEME.upColor }}>{currentBar.high.toFixed(2)}</span>
                            <span style={{ color: CHART_THEME.textSecondary }}>L:</span>
                            <span style={{ color: CHART_THEME.downColor }}>{currentBar.low.toFixed(2)}</span>
                            <span style={{ color: CHART_THEME.textSecondary }}>C:</span>
                            <span style={{ color: currentBar.close >= currentBar.open ? CHART_THEME.upColor : CHART_THEME.downColor }}>
                                {currentBar.close.toFixed(2)}
                            </span>
                        </div>
                    </div>
                )}

                {/* Right: Speed Controls */}
                <div className="flex items-center gap-1">
                    <span 
                        className="text-[10px] font-mono mr-2 uppercase"
                        style={{ color: CHART_THEME.textSecondary }}
                    >
                        Speed
                    </span>
                    {([1, 2, 5, 10] as ReplaySpeed[]).map(s => (
                        <button
                            key={s}
                            onClick={() => onSetSpeed(s)}
                            className="px-2 py-1 text-xs font-mono font-bold rounded transition-all"
                            style={{
                                background: speed === s ? CHART_THEME.accent : CHART_THEME.bgPanel,
                                color: speed === s ? CHART_THEME.bgPrimary : CHART_THEME.textSecondary,
                                border: `1px solid ${speed === s ? CHART_THEME.accent : CHART_THEME.border}`,
                            }}
                        >
                            {s}x
                        </button>
                    ))}
                </div>
            </div>

            {/* Bottom Row: Progress Bar */}
            <div
                ref={progressRef}
                className="relative h-2 rounded-full cursor-pointer group"
                style={{ background: CHART_THEME.bgPanel }}
                onClick={handleProgressClick}
            >
                {/* Progress Fill */}
                <div
                    className="absolute top-0 left-0 h-full rounded-full transition-all duration-75"
                    style={{
                        width: `${progress}%`,
                        background: `linear-gradient(to right, ${CHART_THEME.accent}, ${CHART_THEME.upColor})`,
                    }}
                />

                {/* Progress Thumb */}
                <div
                    className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full shadow-lg transition-all group-hover:scale-125"
                    style={{
                        left: `calc(${progress}% - 8px)`,
                        background: CHART_THEME.accent,
                        border: `2px solid ${CHART_THEME.bgPrimary}`,
                    }}
                />

                {/* Time markers */}
                <div 
                    className="absolute top-4 left-0 text-[10px] font-mono"
                    style={{ color: CHART_THEME.textMuted }}
                >
                    Start
                </div>
                <div 
                    className="absolute top-4 right-0 text-[10px] font-mono"
                    style={{ color: CHART_THEME.textMuted }}
                >
                    End
                </div>
            </div>

            {/* Keyboard Shortcuts Hint */}
            <div 
                className="flex items-center justify-center gap-4 text-[10px] font-mono"
                style={{ color: CHART_THEME.textMuted }}
            >
                <span>Space: Play/Pause</span>
                <span>←/→: Step</span>
                <span>Esc: Exit</span>
            </div>
        </div>
    );
}

// =============================================================================
// REPLAY SELECT MODE OVERLAY
// =============================================================================

interface ReplaySelectOverlayProps {
    isVisible: boolean;
    onCancel: () => void;
}

export function ReplaySelectOverlay({ isVisible, onCancel }: ReplaySelectOverlayProps) {
    if (!isVisible) return null;

    return (
        <div 
            className="absolute inset-0 pointer-events-none z-20"
            style={{
                background: 'linear-gradient(to right, rgba(255, 214, 10, 0.05), transparent, rgba(255, 214, 10, 0.05))',
            }}
        >
            {/* Animated vertical line that follows cursor would be rendered in ChartCanvas */}
        </div>
    );
}

// =============================================================================
// REPLAY CURSOR LINE (rendered on canvas)
// =============================================================================

export function drawReplayCutLine(
    ctx: CanvasRenderingContext2D,
    x: number,
    height: number,
    isSelectMode: boolean
) {
    if (!isSelectMode) return;

    // Draw dashed vertical line
    ctx.strokeStyle = CHART_THEME.accent;
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 4]);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw scissors icon at top
    ctx.fillStyle = CHART_THEME.accent;
    ctx.font = 'bold 16px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('✂️', x, 24);

    // Draw "CUT HERE" label
    ctx.fillStyle = CHART_THEME.bgPrimary;
    ctx.fillRect(x - 35, 30, 70, 18);
    ctx.strokeStyle = CHART_THEME.accent;
    ctx.lineWidth = 1;
    ctx.strokeRect(x - 35, 30, 70, 18);
    ctx.fillStyle = CHART_THEME.accent;
    ctx.font = 'bold 10px monospace';
    ctx.fillText('CUT HERE', x, 43);
}

// =============================================================================
// REPLAY FUTURE OVERLAY (grayed out area after cursor)
// =============================================================================

export function drawReplayFutureOverlay(
    ctx: CanvasRenderingContext2D,
    cursorX: number,
    width: number,
    height: number
) {
    // Gray out the future area
    ctx.fillStyle = 'rgba(3, 5, 10, 0.7)';
    ctx.fillRect(cursorX, 0, width - cursorX, height);

    // Draw "HIDDEN" text
    const centerX = cursorX + (width - cursorX) / 2;
    const centerY = height / 2;
    ctx.fillStyle = CHART_THEME.textMuted;
    ctx.font = 'bold 14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('FUTURE DATA HIDDEN', centerX, centerY);
    ctx.font = '10px monospace';
    ctx.fillText('Press Play to reveal', centerX, centerY + 20);
}
