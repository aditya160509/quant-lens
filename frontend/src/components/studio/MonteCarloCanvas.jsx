"use client";
import React, { useRef, useEffect } from 'react';
import { setupHiDPI, createResizeObserver } from './visual-kernel/canvas';
import { createLinearScale } from './visual-kernel/scales';

const S = {
    void: '#04070f',
    amber: '#ffe45e',
    emerald: '#34d399',
    crimson: '#fb7185',
    grid: 'rgba(148, 163, 184, 0.14)',
    text: '#e2e8f0'
};

const MonteCarloCanvas = ({ data, animIdx }) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !data?.samplePaths) return;
        const handleResize = (rect) => {
            const r = rect || container.getBoundingClientRect();
            const { ctx, width, height } = setupHiDPI(canvas, r);
            draw(ctx, width, height);
        };

        const draw = (ctx, width, height) => {
            const bgGradient = ctx.createLinearGradient(0, 0, 0, height);
            bgGradient.addColorStop(0, '#090f1a');
            bgGradient.addColorStop(0.55, '#060b14');
            bgGradient.addColorStop(1, S.void);
            ctx.fillStyle = bgGradient;
            ctx.fillRect(0, 0, width, height);

            const paths = data.samplePaths;
            const horizon = paths[0]?.length || 252;
            const showLen = Math.min(animIdx, horizon);
            
            // Calculate scale
            const allPoints = paths.map(p => p.slice(0, showLen)).flat().filter(Number.isFinite);
            const observedMin = allPoints.length ? Math.min(...allPoints) : 0.95;
            const observedMax = allPoints.length ? Math.max(...allPoints) : 1.05;
            const minV = observedMin * 0.95;
            const maxV = observedMax > observedMin ? observedMax * 1.05 : observedMin + 0.1;

            const xScale = createLinearScale([0, horizon - 1], [0, width]);
            const yScale = createLinearScale([minV, maxV], [height, 0]);
            const scaleX = (i) => xScale(i);
            const scaleY = (v) => yScale(v);

            // Grid
            ctx.strokeStyle = S.grid;
            ctx.lineWidth = 0.8;
            for (let i = 0; i < 10; i++) {
                const x = (i / 10) * width;
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
                const y = (i / 10) * height;
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
            }

            // Draw Paths with Density Heatmapping
            // We draw paths with very low opacity. Where they overlap, they create a "core".
            paths.forEach((path, pi) => {
                const visiblePath = path.slice(0, showLen);
                if (visiblePath.length < 2) return;

                const isProfitable = visiblePath[visiblePath.length - 1] >= 1.0;
                ctx.strokeStyle = isProfitable ? 'rgba(52, 211, 153, 0.11)' : 'rgba(251, 113, 133, 0.11)';
                ctx.lineWidth = 1.15;
                
                ctx.beginPath();
                visiblePath.forEach((v, i) => {
                    const x = scaleX(i);
                    const y = scaleY(v);
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                });
                ctx.stroke();
            });

            // Draw the median of the displayed sample at each horizon step.
            if (showLen > 1) {
                const medianPath = Array.from({ length: showLen }, (_, index) => {
                    const values = paths.map(path => path[index]).filter(Number.isFinite).sort((a, b) => a - b);
                    const middle = Math.floor(values.length / 2);
                    return values.length % 2
                        ? values[middle]
                        : (values[middle - 1] + values[middle]) / 2;
                });
                ctx.strokeStyle = S.amber;
                ctx.lineWidth = 2.5;
                ctx.shadowBlur = 14;
                ctx.shadowColor = 'rgba(255, 228, 94, 0.6)';
                
                ctx.beginPath();
                medianPath.forEach((v, i) => {
                    const x = scaleX(i);
                    const y = scaleY(v);
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                });
                ctx.stroke();
                
                ctx.shadowBlur = 0;
            }

            // Draw percentile markers at the end of the current animation
            if (showLen > 1) {
                const endValues = paths.map(p => p[showLen - 1]).sort((a,b) => a-b);
                const p95 = endValues[Math.floor(endValues.length * 0.95)];
                const p05 = endValues[Math.floor(endValues.length * 0.05)];
                
                ctx.fillStyle = S.text;
                ctx.font = '9px JetBrains Mono';
                ctx.textAlign = 'right';
                ctx.fillText(`95th: ${p95.toFixed(2)}`, width - 10, scaleY(p95) - 5);
                ctx.fillText(`5th: ${p05.toFixed(2)}`, width - 10, scaleY(p05) + 12);
            }
        };

        const cleanup = createResizeObserver(container, handleResize);
        return () => cleanup();
    }, [data, animIdx]);

    return (
        <div ref={containerRef} className="w-full h-full">
            <canvas ref={canvasRef} className="block w-full h-full" />
        </div>
    );
};

export default MonteCarloCanvas;
