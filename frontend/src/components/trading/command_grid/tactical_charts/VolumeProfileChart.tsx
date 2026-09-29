'use client';

import React, { useRef, useEffect } from 'react';

interface Props {
    data: any[];
    intelligence: any;
    loading: boolean;
    height: number;
}

export default function VolumeProfileChart({ data, intelligence, loading, height }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || loading || !intelligence || !intelligence.volumeProfile) return;

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

        const { buckets, maxVol, minPrice, maxPrice } = intelligence.volumeProfile;
        const bucketCount = buckets.length;
        const barHeight = h / bucketCount;

        // Draw Buckets (Horizontal Bars)
        buckets.forEach((bucket: any, i: number) => {
            const y = h - (i + 1) * barHeight;
            const totalWidth = (bucket.total / maxVol) * w * 0.9;
            const buyWidth = (bucket.buyVol / bucket.total) * totalWidth;
            const sellWidth = totalWidth - buyWidth;

            // Buy Volume (Green/Emerald)
            ctx.fillStyle = 'rgba(16, 185, 129, 0.4)';
            ctx.fillRect(0, y + 1, buyWidth, barHeight - 2);

            // Sell Volume (Red/Rose)
            ctx.fillStyle = 'rgba(244, 63, 94, 0.2)';
            ctx.fillRect(buyWidth, y + 1, sellWidth, barHeight - 2);

            // Peak Volume highlight removed per spec
        });

        // Price Scale Labels
        ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.font = '6px JetBrains Mono';
        ctx.textAlign = 'right';
        for (let i = 0; i < bucketCount; i += 5) {
            const y = h - (i * barHeight);
            const price = minPrice + (i / bucketCount) * (maxPrice - minPrice);
            ctx.fillText(price.toFixed(2), w - 5, y - 2);
        }

        // Current Price Interaction
        const last = data[data.length - 1];
        if (last) {
            const lastY = h - ((last.close - minPrice) / (maxPrice - minPrice)) * h;
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(0, lastY);
            ctx.lineTo(w, lastY);
            ctx.stroke();
        }

    }, [data, intelligence, loading]);

    return (
        <div className="relative w-full" style={{ height }}>
            <canvas ref={canvasRef} className="w-full h-full block" />
            <div className="absolute top-0 left-0 text-[7px] font-mono text-gray-500 bg-black/40 px-1 border-b border-white/5 uppercase tracking-widest">
                Dynamic Volume Cluster (VAP)
            </div>
            {(!intelligence || intelligence.volumeProfile.buckets.every((b:any) => b.total === 0)) && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <span className="text-[8px] font-mono text-gray-700 uppercase">Awaiting Volume Signature...</span>
                </div>
            )}
        </div>
    );
}
