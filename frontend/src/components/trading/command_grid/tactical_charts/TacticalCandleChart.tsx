'use client';

import React, { useRef, useEffect } from 'react';

interface Props {
    data: any[];
    intelligence: any;
    loading: boolean;
    height: number;
}

export default function TacticalCandleChart({ data, intelligence, loading, height }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || loading || data.length === 0 || !intelligence) return;

        const ctx = canvas.getContext('2d', { alpha: false }); // Performance boost
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        
        // Initial Background Fill
        ctx.fillStyle = '#02040a';
        ctx.fillRect(0, 0, w, h);

        // Scales - Include indicators in range
        const { bollinger, lrc, ema8, ema21 } = intelligence.overlays;
        const { sessionHigh, sessionLow } = intelligence.levels;

        let allPrices = data.flatMap(d => [d.low, d.high]);
        if (bollinger) {
            bollinger.forEach(bb => { if (bb) allPrices.push(bb.upper, bb.lower); });
        }
        if (lrc) {
            lrc.forEach(l => { if (l) allPrices.push(l.upper, l.lower, l.center); });
        }
        [ema8, ema21].forEach(p => { if (p) allPrices.push(...p); });
        
        const minPriceRaw = Math.min(...allPrices);
        const maxPriceRaw = Math.max(...allPrices);
        const rangeRaw = maxPriceRaw - minPriceRaw;
        const padding = rangeRaw * 0.1;
        
        const minPrice = minPriceRaw - padding;
        const maxPrice = maxPriceRaw + padding;
        const range = maxPrice - minPrice;

        const yScale = (p: number) => h - ((p - minPrice) / (range || 1)) * h;
        const xScale = (i: number) => (i / (data.length - 1)) * w;

        // --- BACKGROUND GRID ---
        ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
        for (let x = 0; x < w; x += 40) {
            for (let y = 0; y < h; y += 40) {
                ctx.beginPath(); ctx.arc(x, y, 0.4, 0, Math.PI * 2); ctx.fill();
            }
        }

        // 1. BOLLINGER BANDS 
        if (bollinger) {
            ctx.beginPath();
            let started = false;
            bollinger.forEach((bb: any, i: number) => {
                if (!bb) return;
                if (!started) { ctx.moveTo(xScale(i), yScale(bb.upper)); started = true; }
                else ctx.lineTo(xScale(i), yScale(bb.upper));
            });
            for (let i = data.length - 1; i >= 0; i--) {
                const bb = bollinger[i];
                if (bb) ctx.lineTo(xScale(i), yScale(bb.lower));
            }
            ctx.fillStyle = 'rgba(0, 150, 255, 0.03)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(0, 180, 255, 0.15)';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        // 2. ADAPTIVE LINEAR REGRESSION CHANNEL (LRC)
        if (lrc) {
            // LRC Bands Wash
            ctx.beginPath();
            let started = false;
            lrc.forEach((l: any, i: number) => {
                if (!l) return;
                const px = xScale(i);
                if (!started) { ctx.moveTo(px, yScale(l.upper)); started = true; }
                else ctx.lineTo(px, yScale(l.upper));
            });
            for (let i = data.length - 1; i >= 0; i--) {
                const l = lrc[i];
                if (l) ctx.lineTo(xScale(i), yScale(l.lower));
            }
            ctx.fillStyle = 'rgba(251, 191, 36, 0.05)';
            ctx.fill();

            // LRC Center Line (The "Gravity" Line)
            ctx.beginPath();
            started = false;
            lrc.forEach((l: any, i: number) => {
                if (!l) return;
                const px = xScale(i);
                const py = yScale(l.center);
                if (!started) { ctx.moveTo(px, py); started = true; }
                else ctx.lineTo(px, py);
            });
            ctx.strokeStyle = 'rgba(251, 191, 36, 0.8)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 2]);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // 3. SESSION LEVELS
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 4]);
        [sessionHigh, sessionLow].forEach(lvl => {
            ctx.beginPath(); ctx.moveTo(0, yScale(lvl)); ctx.lineTo(w, yScale(lvl)); ctx.stroke();
        });
        ctx.setLineDash([]);

        // 4. CANDLES
        const candleWidth = Math.max(3, (w / data.length) * 0.7);
        data.forEach((d, i) => {
            const x = Math.floor(xScale(i)) + 0.5;
            const isUp = d.close >= d.open;
            const color = isUp ? '#10b981' : '#f43f5e';
            const bodyTop = yScale(Math.max(d.open, d.close));
            const bodyBottom = yScale(Math.min(d.open, d.close));

            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.beginPath(); 
            ctx.moveTo(x, yScale(d.high)); 
            ctx.lineTo(x, yScale(d.low)); 
            ctx.stroke();
            
            ctx.fillStyle = color;
            const bodyH = Math.max(1, bodyBottom - bodyTop);
            ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyH);
        });

        // 5. OVERLAYS (EMA)
        const drawLayeredPath = (points: number[], color: string, width: number) => {
            if (!points || points.length === 0) return;
            ctx.beginPath();
            let started = false;
            points.forEach((v: number, i: number) => {
                if (v === undefined || v === null || isNaN(v)) return;
                const px = xScale(i);
                const py = yScale(v);
                if (!started) { ctx.moveTo(px, py); started = true; }
                else ctx.lineTo(px, py);
            });
            if (!started) return;
            ctx.strokeStyle = color;
            ctx.lineWidth = width;
            ctx.stroke();
        };

        drawLayeredPath(ema21, '#a855f7', 1.5);
        drawLayeredPath(ema8, '#06b6d4', 1.5);
        
        // 6. PRICE TRACKER
        const last = data[data.length - 1];
        const lastY = yScale(last.close);
        
        ctx.setLineDash([]);
        ctx.fillStyle = '#111';
        ctx.fillRect(w - 65, lastY - 10, 65, 20);
        ctx.strokeStyle = last.close >= last.open ? '#10b981' : '#f43f5e';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(w - 65, lastY - 10, 65, 20);
        
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 11px Inter';
        ctx.textAlign = 'right';
        ctx.fillText(last.close.toFixed(2), w - 5, lastY + 4);

    }, [data, intelligence, loading, height]);

    return (
        <div className="relative w-full overflow-hidden" style={{ height }}>
            <canvas ref={canvasRef} className="w-full h-full block" />
            
        </div>
    );
}
