'use client';

import React, { useRef, useEffect, useState } from 'react';
import { useTradingContext } from '@/context/TradingContext';
import { fetchDependencyMap } from '@/lib/api';

interface NodeItem {
    label: string;
    sub?: string;
    color: string;
}

interface MapNode {
    id: string;
    title: string;
    items: NodeItem[];
}

export default function DependencyMap() {
    const { state } = useTradingContext();
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [mapData, setMapData] = useState<MapNode[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadData = async () => {
            if (!state.symbol) return;
            setLoading(true);
            try {
                const data = await fetchDependencyMap(state.symbol);
                setMapData(data.nodes || []);
            } catch (err) {
                console.error('[DependencyMap] API Error:', err);
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, [state.symbol]);

    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container || mapData.length === 0) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let animationFrame: number;
        
        const resize = () => {
            const dpr = window.devicePixelRatio || 1;
            const rect = container.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            canvas.style.width = `${rect.width}px`;
            canvas.style.height = `${rect.height}px`;
            ctx.scale(dpr, dpr);
        };

        resize();
        window.addEventListener('resize', resize);

        const width = container.clientWidth;
        const height = container.clientHeight;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) * 0.35;

        // Position nodes in a circular formation
        const nodes = mapData.map((node, i) => {
            const angle = (i / mapData.length) * Math.PI * 2 - Math.PI / 2;
            return {
                ...node,
                x: centerX + radius * Math.cos(angle) - 70,
                y: centerY + radius * Math.sin(angle) - 40,
                w: 140,
                h: 70
            };
        });

        let frame = 0;
        const render = () => {
            frame++;
            ctx.clearRect(0, 0, width, height);

            // 1. Draw Global Field (Background grid and pulsing rings)
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
            ctx.lineWidth = 1;
            [radius * 0.5, radius, radius * 1.5].forEach(r => {
                ctx.beginPath();
                ctx.arc(centerX, centerY, r, 0, Math.PI * 2);
                ctx.stroke();
            });

            // 2. Connections with Pulsing Energy
            ctx.setLineDash([0]);
            nodes.forEach(node => {
                const bx = node.x + node.w / 2;
                const by = node.y + node.h / 2;
                
                // Gradient for lines
                const grad = ctx.createLinearGradient(centerX, centerY, bx, by);
                const pulse = (Math.sin(frame * 0.05) + 1) / 2;
                grad.addColorStop(0, 'rgba(251, 191, 36, 0.4)');
                grad.addColorStop(0.5, `rgba(251, 191, 36, ${0.1 + pulse * 0.2})`);
                grad.addColorStop(1, 'rgba(64, 64, 64, 0.2)');

                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(bx, by);
                ctx.strokeStyle = grad;
                ctx.lineWidth = 1 + pulse;
                ctx.stroke();
            });

            // 3. Draw Nodes
            nodes.forEach(node => {
                // Background
                ctx.fillStyle = 'rgba(10, 15, 25, 0.9)';
                ctx.shadowColor = 'rgba(0,0,0,0.5)';
                ctx.shadowBlur = 15;
                ctx.fillRect(node.x, node.y, node.w, node.h);
                ctx.shadowBlur = 0;

                // Accent Border
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
                ctx.lineWidth = 1;
                ctx.strokeRect(node.x, node.y, node.w, node.h);

                // Title Section
                ctx.fillStyle = 'rgba(38, 38, 38, 0.8)';
                ctx.fillRect(node.x, node.y, node.w, 18);
                
                ctx.fillStyle = '#a3a3a3';
                ctx.font = 'bold 7px "JetBrains Mono"';
                ctx.textAlign = 'left';
                ctx.fillText(node.title, node.x + 8, node.y + 12);

                // Items
                node.items.forEach((item, i) => {
                    const iy = node.y + 36 + (i * 22);
                    
                    // Leading Status Bar
                    ctx.fillStyle = item.color;
                    ctx.fillRect(node.x + 8, iy - 7, 2, 10);

                    // Label
                    ctx.fillStyle = '#ffffff';
                    ctx.font = 'bold 10px "JetBrains Mono"';
                    ctx.fillText(item.label, node.x + 16, iy);

                    // Sub-label
                    if (item.sub) {
                        ctx.fillStyle = '#737373';
                        ctx.font = '7px "JetBrains Mono"';
                        ctx.fillText(item.sub, node.x + 16, iy + 10);
                    }
                });
            });

            // 4. Central Hub (Active Symbol)
            const cw = 90;
            const ch = 45;
            const cx = centerX - cw / 2;
            const cy = centerY - ch / 2;

            // Hub Outer Ambient Glow
            const hubPulse = (Math.sin(frame * 0.03) + 1) / 2;
            ctx.shadowColor = 'rgba(251, 191, 36, 0.4)';
            ctx.shadowBlur = 20 + hubPulse * 15;
            ctx.fillStyle = '#0a0f19';
            ctx.fillRect(cx, cy, cw, ch);
            ctx.shadowBlur = 0;

            // Hub Border - Golden Institutional
            ctx.strokeStyle = '#fbbf24';
            ctx.lineWidth = 2;
            ctx.strokeRect(cx, cy, cw, ch);

            // Ticker Label
            ctx.fillStyle = '#fbbf24';
            ctx.font = 'bold 16px "JetBrains Mono"';
            ctx.textAlign = 'center';
            ctx.fillText(state.symbol, centerX, centerY + 2);

            ctx.fillStyle = 'rgba(251, 191, 36, 0.6)';
            ctx.font = 'bold 7px "JetBrains Mono"';
            ctx.fillText('NEURAL_CORE_V1', centerX, centerY + 14);

            animationFrame = requestAnimationFrame(render);
        };

        render();

        return () => {
            window.removeEventListener('resize', resize);
            cancelAnimationFrame(animationFrame);
        };
    }, [state.symbol, mapData]);

    if (loading) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-[#02040a]">
                <div className="flex flex-col items-center gap-2">
                    <div className="w-8 h-8 border-2 border-terminal-yellow/30 border-t-terminal-yellow rounded-full animate-spin" />
                    <span className="text-[10px] font-mono text-gray-500 animate-pulse uppercase tracking-[0.2em]">Resolving Dependency Map...</span>
                </div>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="h-full w-full bg-[#02040a] overflow-hidden relative">
            <canvas ref={canvasRef} className="block w-full h-full" />
            
            {/* Field Grid Overlays */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.04] bg-[radial-gradient(#fff_1px,transparent_0)] bg-[length:24px_24px]" />
            <div className="absolute inset-0 pointer-events-none bg-gradient-to-t from-black/40 via-transparent to-black/40" />
        </div>
    );
}
