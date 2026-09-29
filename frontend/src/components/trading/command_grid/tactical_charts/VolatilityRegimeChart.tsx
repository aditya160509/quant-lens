'use client';

import React, { useRef, useEffect } from 'react';

interface Props {
    data: any[];
    intelligence: any;
    loading: boolean;
    height: number;
}

export default function VolatilityRegimeChart({ data, intelligence, loading, height }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || loading || !intelligence || !intelligence.volatility) return;

        const ctx = canvas.getContext('2d', { alpha: false });
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        
        // Background
        ctx.fillStyle = '#02040a';
        ctx.fillRect(0, 0, w, h);

        const { hv, iv } = intelligence.volatility;
        if (!hv || !iv) return;
        
        // --- ZERO-MASKING SCALING ---
        // Capture only the 'warm' data (values > 0) to determine local range.
        // This prevents the lines from flatlining at the bottom due to early zeros.
        const warmHV = hv.filter((v: number) => !isNaN(v) && v > 0);
        const warmIV = iv.filter((v: number) => !isNaN(v) && v > 0);
        const activePool = [...warmHV, ...warmIV];
        
        if (activePool.length === 0) return;

        const maxV = Math.max(...activePool);
        const minV = Math.min(...activePool);
        const range = maxV - minV;
        
        // Add 20% vertical padding for institutional headspace
        const pad = range * 0.2;
        const upperLimit = maxV + pad;
        const lowerLimit = Math.max(0, minV - pad);
        const dynRange = upperLimit - lowerLimit || 0.01;

        const xScale = (i: number) => (i / (hv.length - 1)) * w;
        const yScale = (v: number) => {
            if (isNaN(v) || v === 0) return h + 10; // Hide zero/null values off-canvas
            return h - ((v - lowerLimit) / dynRange) * h;
        };

        // --- BACKGROUND GRID ---
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 0.5;
        ctx.setLineDash([1, 4]);
        [0.25, 0.5, 0.75].forEach(pct => {
            ctx.beginPath(); ctx.moveTo(0, h * pct); ctx.lineTo(w, h * pct); ctx.stroke();
        });
        ctx.setLineDash([]);

        // 1. HV (Historical Volatility) - High-Opacity Area Wash
        const hvGrad = ctx.createLinearGradient(0, h, 0, 0);
        hvGrad.addColorStop(0, 'rgba(168, 85, 247, 0.05)');
        hvGrad.addColorStop(1, 'rgba(168, 85, 247, 0.35)');
        
        ctx.beginPath();
        let started = false;
        hv.forEach((v: number, i: number) => {
            if (v <= 0) return;
            const px = xScale(i);
            const py = yScale(v);
            if (!started) { 
                ctx.moveTo(px, h); 
                ctx.lineTo(px, py); 
                started = true; 
            } else { 
                ctx.lineTo(px, py); 
            }
        });
        if (started) {
            ctx.lineTo(xScale(hv.length - 1), h);
            ctx.fillStyle = hvGrad;
            ctx.fill();

            // HV Trace - Violet Glow
            ctx.strokeStyle = '#a855f7';
            ctx.lineWidth = 1.5;
            ctx.shadowBlur = 4;
            ctx.shadowColor = 'rgba(168, 85, 247, 0.5)';
            ctx.stroke();
            ctx.shadowBlur = 0;
        }

        // 2. IV Proxy (Implied Volatility) - Bright Burn Line
        ctx.beginPath();
        started = false;
        iv.forEach((v: number, i: number) => {
            if (v <= 0) return;
            const px = xScale(i);
            const py = yScale(v);
            if (!started) { 
                ctx.moveTo(px, py); 
                started = true; 
            } else { 
                ctx.lineTo(px, py); 
            }
        });
        
        if (started) {
            ctx.strokeStyle = '#fbbf24';
            ctx.lineWidth = 2.5;
            ctx.shadowBlur = 12;
            ctx.shadowColor = 'rgba(251, 191, 36, 0.6)';
            ctx.stroke();
            ctx.shadowBlur = 0;
        }

        // 3. INTERACTION HUD
        const lastHV = hv[hv.length - 1] || 0;
        const lastIV = iv[iv.length - 1] || 0;
        
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 8px Inter';
        ctx.textAlign = 'right';
        ctx.fillText(`HV: ${(lastHV * 100).toFixed(2)}%  //  IV-PX: ${(lastIV * 100).toFixed(2)}%`, w - 10, 15);

    }, [data, intelligence, loading, height]);

    return (
        <div className="relative w-full h-full overflow-hidden bg-[#02040a]">
            <canvas ref={canvasRef} className="w-full h-full block" />
        </div>
    );
}
