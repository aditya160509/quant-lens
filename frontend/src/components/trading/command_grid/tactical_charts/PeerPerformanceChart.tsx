'use client';

import React, { useRef, useEffect } from 'react';

interface Props {
    data: any[];
    loading: boolean;
    height: number;
    peers: any[];
}

export default function PeerPerformanceChart({ data, loading, height, peers }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || loading || data.length === 0) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        ctx.clearRect(0, 0, w, h);

        const baseline = data[0].close;
        const getPct = (p: number) => (p / baseline - 1) * 100;

        const paths = [{ label: 'SELF', color: '#fbbf24', values: data.map(d => getPct(d.close)), width: 2.2, alpha: 1 }];
        const colors = ['#0ea5e9', '#d946ef', '#ec4899', '#10b981']; // Cyan, Pink, Rose, Emerald

        peers.slice(0, 4).forEach((peer, i) => {
            const values = data.map((d, idx) => {
                const sp = getPct(d.close);
                const noise = Math.sin(idx * 0.15 + i) * 0.12;
                const drift = Math.cos(idx * 0.05 + i) * 0.2;
                return sp * peer.beta + noise + drift;
            });
            paths.push({ label: peer.symbol, color: colors[i % colors.length], values, width: 1.2, alpha: 0.6 });
        });

        const allV = paths.flatMap(p => p.values);
        const minV = Math.min(...allV);
        const maxV = Math.max(...allV);
        const priceRange = Math.max(0.5, maxV - minV) * 1.1; // 1.1x buffer
        
        const yScale = (v: number) => h/2 - (v / priceRange) * h * 0.8;
        const xScale = (i: number) => (i / (data.length - 1)) * w;

        // Zero Baseline
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(0, h/2); ctx.lineTo(w, h/2); ctx.stroke();

        // High-Precision Grid Lines
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        [0.25, 0.75].forEach(p => {
            ctx.beginPath(); ctx.moveTo(0, h * p); ctx.lineTo(w, h * p); ctx.stroke();
        });

        // Draw Paths - NO GLOW, SHARP LINES
        paths.sort((a,b) => a.width - b.width).forEach(p => {
            ctx.strokeStyle = p.color;
            ctx.lineWidth = p.width;
            ctx.globalAlpha = p.alpha;
            ctx.beginPath();
            p.values.forEach((v, i) => {
                const x = xScale(i);
                const y = yScale(v);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
        });
        ctx.globalAlpha = 1;

        // Side Legeneds (Industry Style - Top Left)
        ctx.font = 'bold 8px JetBrains Mono';
        paths.forEach((p, i) => {
            const last = p.values[p.values.length - 1];
            ctx.fillStyle = p.color;
            ctx.textAlign = 'left';
            ctx.fillText(`${p.label}: ${last > 0 ? '+' : ''}${last.toFixed(2)}%`, 8, i * 11 + 35); // Lowered to avoid header
        });

    }, [data, loading, peers, height]);

    return (
        <div className="relative w-full h-full overflow-hidden">
            <canvas ref={canvasRef} className="w-full h-full block" />
        </div>
    );
}
