"use client";

import React, { useRef, useEffect, useState } from 'react';

/**
 * MarqueeTickerStrip - Continuous horizontal scrolling ticker strip
 * Motion behavior: Constant velocity, infinite loop, pause on hover
 */
export default function MarqueeTickerStrip({ 
    items = [], 
    loading = false,
    direction = 'left', // 'left' or 'right'
    speed = 30, // pixels per second
    height = 'normal' // 'normal' or 'thin'
}) {
    const containerRef = useRef(null);
    const [isPaused, setIsPaused] = useState(false);
    const [offset, setOffset] = useState(0);
    const animationRef = useRef(null);
    const [setsNeeded, setSetsNeeded] = useState(3);
    const lastTimeRef = useRef(null);
    const contentWidthRef = useRef(0);

    // Measure content width and calculate sets needed
    useEffect(() => {
        if (containerRef.current) {
            const firstSet = containerRef.current.querySelector('[data-ticker-set="0"]');
            if (firstSet) {
                const width = firstSet.offsetWidth;
                contentWidthRef.current = width;
                
                // Calculate how many sets are needed to fill the screen width plus buffer
                if (width > 0) {
                    const viewportWidth = window.innerWidth;
                    const needed = Math.ceil(viewportWidth / width) + 2;
                    setSetsNeeded(Math.max(3, needed));
                }
            }
        }
    }, [items]);

    // Animation loop using requestAnimationFrame
    useEffect(() => {
        if (loading || items.length === 0 || contentWidthRef.current === 0) return;

        // Initialize offset for right direction to avoid initial jump
        if (direction === 'right' && offset === 0) {
            setOffset(-contentWidthRef.current);
        }

        const animate = (timestamp) => {
            if (!lastTimeRef.current) lastTimeRef.current = timestamp;
            const deltaTime = timestamp - lastTimeRef.current;
            lastTimeRef.current = timestamp;

            if (!isPaused) {
                const delta = (speed * deltaTime) / 1000;
                setOffset(prev => {
                    let newOffset = direction === 'left' 
                        ? prev - delta 
                        : prev + delta;
                    
                    // Reset when set completely exits viewport
                    const resetThreshold = contentWidthRef.current;
                    
                    if (direction === 'left' && newOffset <= -resetThreshold) {
                        newOffset += resetThreshold;
                    }
                    if (direction === 'right' && newOffset >= 0) {
                        newOffset -= resetThreshold;
                    }
                    return newOffset;
                });
            }

            animationRef.current = requestAnimationFrame(animate);
        };

        animationRef.current = requestAnimationFrame(animate);

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [loading, items.length, isPaused, direction, speed, offset]);

    const getChangeColor = (pct) => {
        if (pct > 0) return 'text-terminal-green';
        if (pct < 0) return 'text-terminal-red';
        return 'text-terminal-dim';
    };

    if (loading) {
        return (
            <div className={`flex items-center overflow-hidden h-full`}>
                <span className="text-terminal-yellow text-[10px] animate-pulse px-4 font-mono uppercase">Streaming Data...</span>
            </div>
        );
    }

    if (!items.length) {
        return (
            <div className={`flex items-center px-4 ${height === 'thin' ? 'h-7' : 'h-9'} text-terminal-dim text-xs font-mono`}>
                No ticker data
            </div>
        );
    }

    const renderTickerSet = (keyPrefix) => (
        <div 
            data-ticker-set={keyPrefix}
            key={`ticker-set-${keyPrefix}`}
            className="flex items-center gap-10 shrink-0 px-5"
        >
            {items.map((item, idx) => (
                <div 
                    key={`${keyPrefix}-${item.symbol}-${idx}`}
                    className="flex items-center gap-2 text-xs font-mono shrink-0"
                    style={{ minWidth: 'max-content' }}
                >
                    <span className="text-terminal-text font-black tracking-tight">
                        {item.symbol
                            .replace('^', '')
                            .replace('.NS', '')
                            .replace('.BO', '')
                            .replace('=X', '')
                            .replace('-USD', '')
                        }
                    </span>
                    <span className="text-terminal-dim">
                        {typeof item.last === 'number' ? item.last.toLocaleString(undefined, { maximumFractionDigits: 2 }) : item.last}
                    </span>
                    <span className={`font-bold ${getChangeColor(item.changePct)}`}>
                        {item.changePct > 0 ? '▲' : item.changePct < 0 ? '▼' : ''} 
                        {Math.abs(typeof item.changePct === 'number' ? item.changePct : 0).toFixed(2)}%
                    </span>
                </div>
            ))}
        </div>
    );


    return (
        <div 
            className={`overflow-hidden ${height === 'thin' ? 'h-7' : 'h-8'} flex items-center border-x border-terminal-gray/20`}
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
        >
            <div 
                ref={containerRef}
                className="flex items-center"
                style={{ 
                    transform: `translateX(${offset}px)`,
                    willChange: 'transform'
                }}
            >
                {/* Dynamically repeat the ticker set to fill screen width + buffer */}
                {Array.from({ length: setsNeeded }).map((_, i) => renderTickerSet(i))}
            </div>
        </div>
    );
}
