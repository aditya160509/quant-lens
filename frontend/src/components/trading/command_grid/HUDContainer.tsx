'use client';

import React from 'react';
import { motion } from 'framer-motion';

interface HUDContainerProps {
    children: React.ReactNode;
    title?: string;
    subTitle?: string;
    className?: string;
    icon?: React.ReactNode;
}

export default function HUDContainer({ children, title, subTitle, className = "", icon }: HUDContainerProps) {
    return (
        <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`relative flex flex-col bg-[#05070a]/90 backdrop-blur-3xl border border-white/[0.08] rounded-md overflow-hidden group hover:border-white/20 transition-all duration-500 shadow-2xl ${className}`}
        >
            {/* Background Texture Overlay */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:20px_20px]" />

            {/* Header */}
            {(title || subTitle) && (
                <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.05] bg-white/[0.02] relative">
                    <div className="flex flex-col">
                        <div className="flex items-center gap-2">
                            {icon && <span className="text-terminal-yellow/30 group-hover:text-terminal-yellow transition-colors duration-500">{icon}</span>}
                            <span className="text-[9px] font-mono text-terminal-yellow font-black tracking-[0.15em] uppercase drop-shadow-[0_0_8px_rgba(251,191,36,0.3)]">{title}</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Content Area */}
            <div className="flex-1 relative z-10">
                {children}
            </div>

            {/* Terminal High-Tech Accents */}
            <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-white/20" />
            <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-white/20" />
            <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-white/20" />
            <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-white/20" />
            
            {/* Subtle Inner Glow */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/5 to-transparent pointer-events-none" />
        </motion.div>
    );
}
