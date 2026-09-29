"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Terminal, ChevronRight, Activity, Zap, ArrowRight, Command } from "lucide-react";

const INITIAL_LOGS = [
    "SYSTEM_READY_V4.2",
    "DECRYPTING_MARKET_VECTORS...",
    "NEURAL_PLANE_CONNECTED",
    "TYPE 'HELP' TO START_SESSION"
];

const COMMAND_MAP = {
    'help': 'Available commands: trade [symbol], labs, clear, system_status', // Removed monitor
    'trade': 'Redirecting to Trading Terminal...',
    // 'monitor': 'Redirecting to Market Monitor...', // DISABLED: Monitor page removed
    'labs': 'Redirecting to Research Labs...',
    'system_status': 'Kernel: Healthy | Nodes: 12 Active | Latency: 4ms',
};

export default function HomeTerminalSection() {
    const [input, setInput] = useState("");
    const [logs, setLogs] = useState(INITIAL_LOGS);
    const [isThinking, setIsThinking] = useState(false);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        const frame = requestAnimationFrame(() => {
            setMounted(true);
        });
        return () => cancelAnimationFrame(frame);
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs, isThinking]);

    const handleCommand = (cmd) => {
        const fullCmd = cmd.trim().toLowerCase();
        const [baseCmd, ...args] = fullCmd.split(" ");
        
        setLogs(prev => [...prev, `> ${fullCmd}`]);
        setIsThinking(true);

        setTimeout(() => {
            setIsThinking(false);
            if (baseCmd === 'clear') {
                setLogs(INITIAL_LOGS);
            } else if (baseCmd === 'trade') {
                const ticker = args[0] ? args[0].toUpperCase() : 'SPY';
                setLogs(prev => [...prev, `EXECUTING PORTAL TO ${ticker} TRADING ENGINE...`]);
                setTimeout(() => window.location.href = `/trade?symbol=${ticker}`, 1000);
            // DISABLED: Monitor page removed - redirect to labs instead
            } else if (baseCmd === 'monitor') {
                setLogs(prev => [...prev, `MONITOR DEPRECATED. REDIRECTING TO LABS...`]);
                setTimeout(() => window.location.href = `/labs`, 1000);
            } else if (baseCmd === 'labs') {
                setLogs(prev => [...prev, `UNLOCING QUANTUM RESEARCH MODULES...`]);
                setTimeout(() => window.location.href = `/labs`, 1000);
            } else if (COMMAND_MAP[baseCmd]) {
                setLogs(prev => [...prev, COMMAND_MAP[baseCmd]]);
            } else {
                setLogs(prev => [...prev, `EXEC_ERR: INVALID_SYNTAX '${baseCmd}'. TRY 'HELP'.`]);
            }
        }, 600);
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!input.trim()) return;
        handleCommand(input);
        setInput("");
    };

    const renderLogTime = () => {
        if (!mounted) return "[00:00:00]";
        return `[${new Date().toLocaleTimeString([], { hour12: false, second: '2-digit' })}]`;
    };

    return (
        <section id="TERMINAL_CORE" className="relative min-h-screen flex items-center justify-center overflow-hidden py-32 bg-black">
            {/* Background Video */}
            <div className="absolute inset-0 z-0">
                <video 
                    autoPlay 
                    loop 
                    muted 
                    playsInline 
                    className="w-full h-full object-cover opacity-60 scale-110"
                >
                    <source src="/blackhole.webm" type="video/webm" />
                </video>
                <div className="absolute inset-0 bg-gradient-to-b from-black via-transparent to-black" />
            </div>

            <div className="relative z-10 w-full max-w-6xl px-10 flex flex-col items-center">
                {/* Section Header */}
                <div className="mb-16 text-center">
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        className="inline-flex items-center gap-3 px-4 py-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 backdrop-blur-md mb-6"
                    >
                        <Terminal className="w-3.5 h-3.5 text-violet-400" />
                        <span className="text-[10px] font-mono font-black tracking-[0.3em] text-violet-300 uppercase">Input Node</span>
                    </motion.div>
                    <motion.h2 
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="text-5xl md:text-7xl font-black text-white italic uppercase tracking-tighter leading-none"
                    >
                        Kernel<br/><span className="text-violet-500">Access</span>
                    </motion.h2>
                </div>

                {/* Integrated Terminal Panel */}
                <motion.div 
                    initial={{ opacity: 0, scale: 0.95, filter: "blur(20px)" }}
                    whileInView={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                    transition={{ duration: 0.8 }}
                    className="w-full h-[600px] bg-[#03050c]/40 backdrop-blur-3xl border border-white/10 rounded-[2.5rem] shadow-[0_0_100px_rgba(139,92,246,0.15)] flex flex-col overflow-hidden"
                >
                    {/* Panel Top Bar */}
                    <div className="h-14 border-b border-white/10 flex items-center justify-between px-8 bg-white/[0.02]">
                        <div className="flex items-center gap-6">
                            <div className="flex gap-2">
                                <div className="w-2.5 h-2.5 rounded-full bg-red-500/40" />
                                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/40" />
                                <div className="w-2.5 h-2.5 rounded-full bg-green-500/40" />
                            </div>
                            <div className="h-4 w-px bg-white/10" />
                            <div className="flex items-center gap-3">
                                <Activity className="w-3.5 h-3.5 text-violet-500 animate-pulse" />
                                <span className="text-[10px] font-mono text-gray-500 tracking-[0.2em] uppercase">Status: Connected_Alpha</span>
                            </div>
                        </div>
                        <div className="flex items-center gap-4 text-[10px] font-mono text-gray-600">
                            <span>SESSION_ID: 0x9B42</span>
                            <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,1)]" />
                        </div>
                    </div>

                    {/* Console Area */}
                    <div className="flex-grow flex flex-col min-h-0 bg-transparent">
                        <div 
                            ref={scrollRef}
                            className="flex-1 p-10 font-mono text-[13px] overflow-y-auto space-y-4 custom-scrollbar"
                        >
                            {logs.map((log, i) => (
                                <div key={i} className={`flex gap-4 ${log.startsWith('>') ? "text-violet-400" : log.startsWith('EXEC_ERR') ? "text-red-400" : "text-gray-300"}`}>
                                    <span className="opacity-20 shrink-0">{renderLogTime()}</span>
                                    <span className="leading-relaxed whitespace-pre-wrap">{log}</span>
                                </div>
                            ))}
                            {isThinking && (
                                <div className="text-violet-500 flex items-center gap-2">
                                    <Zap className="w-4 h-4 animate-spin" />
                                    <span className="animate-pulse italic">PROCESSING_X_CORE...</span>
                                </div>
                            )}
                        </div>

                        {/* Input Area */}
                        <form onSubmit={handleSubmit} className="p-8 bg-white/[0.03] border-t border-white/5 flex items-center gap-5 group">
                            <ChevronRight className="w-6 h-6 text-violet-500 shrink-0" />
                            <input
                                ref={inputRef}
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="TYPE_COMMAND_HERE..."
                                className="flex-1 bg-transparent border-none outline-none font-mono text-lg text-white placeholder:text-gray-700 uppercase tracking-widest"
                            />
                            <button 
                                type="submit" 
                                className="px-6 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-xl transition-all flex items-center gap-2 group shadow-[0_0_20px_rgba(139,92,246,0.3)]"
                            >
                                <span className="text-[10px] font-mono font-black text-white uppercase tracking-widest">Execute</span>
                                <ArrowRight className="w-3 h-3 text-white group-hover:translate-x-1 transition-transform" />
                            </button>
                        </form>
                    </div>

                    {/* Bottom Meta */}
                    <div className="h-10 border-t border-white/5 bg-black px-8 flex items-center justify-between">
                        <div className="text-[9px] font-mono text-gray-700 uppercase tracking-[0.2em] flex gap-6">
                            <span>BETA_SYNC: OK</span>
                            <span>latency: 0.00ms</span>
                            <span>NODE: FR_01</span>
                        </div>
                        <div className="flex gap-4">
                            {[1, 2, 3, 4].map(i => (
                                <div key={i} className="w-1 h-3 bg-white/5 rounded-full" />
                            ))}
                        </div>
                    </div>
                </motion.div>
                
                {/* Hints */}
                <div className="mt-10 flex gap-10 opacity-30">
                    {['help', 'trade AAPL', 'labs'].map(h => ( // Removed 'monitor'
                        <div key={h} className="text-[10px] font-mono text-gray-500 uppercase tracking-[0.2em]">
                            <span className="text-violet-500 mr-2">$</span> {h}
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
