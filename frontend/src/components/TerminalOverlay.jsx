"use client";

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';

// ATOMIC AGENT DEFINITIONS
const AGENTS = {
    ATLAS: { id: 'ATLAS', name: 'atlas', color: '#ffffff', glyph: '●', bg: '#27272a' },
    EXPLORER: { id: 'EXPLORER', name: 'explorer', color: '#38bdf8', glyph: '●', bg: '#083344' },
    ENGINE: { id: 'ENGINE', name: 'engine', color: '#fbbf24', glyph: '●', bg: '#451a03' },
    QUANTS: { id: 'QUANTS', name: 'quants', color: '#34d399', glyph: '●', bg: '#064e3b' },
};

const BIG_ATLAS = `
      █████╗ ████████╗██╗      █████╗ ███████╗
     ██╔══██╗╚══██╔══╝██║     ██╔══██╗██╔════╝
     ███████║   ██║   ██║     ███████║███████╗
     ██╔══██║   ██║   ██║     ██╔══██║╚════██║
     ██║  ██║   ██║   ███████╗██║  ██║███████║
     ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝
`;

// ASCII TABLE GENERATOR
const renderTable = (headers, rows, type = 'standard') => {
    const chars = type === 'heavy'
        ? { tl: '╔', tr: '╗', bl: '╚', br: '╝', h: '═', v: '║', tm: '╦', bm: '╩', ml: '╠', mr: '╣', mm: '╬' }
        : { tl: '+', tr: '+', bl: '+', br: '+', h: '-', v: '|', tm: '+', bm: '+', ml: '+', mr: '+', mm: '+' };

    const padding = 4;
    const colWidths = headers.map((h, i) => Math.max(h.length, ...rows.map(r => String(r[i]).length)) + padding);

    const drawLine = (left, mid, right) =>
        left + colWidths.map(w => chars.h.repeat(w)).join(mid) + right;

    const drawRow = (row) =>
        chars.v + row.map((cell, i) => {
            const content = String(cell);
            const padTotal = colWidths[i];
            return ` ${content}${' '.repeat(padTotal - content.length - 1)}`;
        }).join(chars.v) + chars.v;

    return [
        drawLine(chars.tl, chars.tm, chars.tr),
        drawRow(headers),
        drawLine(chars.ml, chars.mm, chars.mr),
        ...rows.map(drawRow),
        drawLine(chars.bl, chars.bm, chars.br)
    ].join('\n');
};

const COMMANDS = [
    { name: '/help', desc: 'Display global command matrix', example: '/help', flags: [] },
    { name: '/ls', desc: 'List strategies in active workspace', example: '/ls studio', flags: ['[path]'] },
    { name: '/cat', desc: 'Stream source code to console', example: '/cat bollinger.py', flags: ['<filename>'] },
    { name: '/sub-agent', desc: 'Initialize autonomous sub-pane', example: '/sub-agent ALFA', flags: ['<name>'] },
    { name: '/backtest', desc: 'Execute simulation routine', example: '/backtest SPY boll.py', flags: ['<ticker>', '<strategy>', '--lookback [N]'] },
    { name: '/pca', desc: 'Resolve factor eigenphysics', example: '/pca US_TOP50', flags: ['<universe>', '--lookback [D]'] },
    { name: '/clear', desc: 'Flush terminal history', example: '/clear', flags: [] },
];

export default function TerminalOverlay() {
    const [isOpen, setIsOpen] = useState(false);
    const [history, setHistory] = useState([]);
    const [input, setInput] = useState('');
    const [isExecuting, setIsExecuting] = useState(false);
    const [execAgent, setExecAgent] = useState(null);
    const [thinkingText, setThinkingText] = useState('');
    const [agentLogs, setAgentLogs] = useState([]);
    const [suggestions, setSuggestions] = useState([]);
    const [selectedIndex, setSelectedIndex] = useState(0);

    // Multi-Agent State
    const [subAgents, setSubAgents] = useState([]);
    const [configuringAgent, setConfiguringAgent] = useState(null);
    const [selectedKits, setSelectedKits] = useState([]);

    // ============================================
    // IMPROVEMENT 5: WebSocket State Management
    // ============================================
    const [ws, setWs] = useState(null);
    const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
    const [currentProgress, setCurrentProgress] = useState({ value: 0, total: 100, message: '' });

    const router = useRouter();
    const inputRef = useRef(null);
    const scrollRef = useRef(null);
    const agentScrollRef = useRef(null);

    // ============================================
    // IMPROVEMENT 6: WebSocket Connection Setup
    // ============================================
    useEffect(() => {
        if (isOpen && !ws) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
            const websocket = new WebSocket(`${protocol}//${host}/api/cli/ws/${sessionId}`);

            websocket.onopen = () => {
                console.log('WebSocket connected');
                setWs(websocket);
            };

            websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'log') {
                    logAgent(data.message, data.log_type);
                } else if (data.type === 'progress') {
                    setCurrentProgress({
                        value: data.progress,
                        total: data.total,
                        message: data.message
                    });
                    setThinkingText(`${data.message} (${data.percentage}%)`);
                }
            };

            websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            websocket.onclose = () => {
                console.log('WebSocket disconnected');
                setWs(null);
                setTimeout(() => {
                    if (isOpen) {
                        setWs(null); 
                    }
                }, 2000);
            };
        }

        return () => {
            if (ws) {
                ws.close();
            }
        };
    }, [isOpen, ws, sessionId]);

    // Toggle logic
    useEffect(() => {
        const handleKeyDown = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setIsOpen(prev => !prev);
            } else if (e.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen]);

    // Focus & Init
    useEffect(() => {
        if (isOpen) {
            setTimeout(() => inputRef.current?.focus(), 50);
            if (history.length === 0) {
                setHistory([{ type: 'big-logo', text: BIG_ATLAS, id: 'init-logo' }]);
                setTimeout(() => {
                    addMessage(AGENTS.ATLAS, 'ACCESS GRANTED: WELCOME [USER]');
                    addMessage(AGENTS.ATLAS, 'READY FOR INSTITUTIONAL ORCHESTRATION.');
                }, 400);
            }
        }
    }, [isOpen, history.length]);

    // Scroll to bottom
    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [history, isExecuting]);

    useEffect(() => {
        if (agentScrollRef.current) agentScrollRef.current.scrollTop = agentScrollRef.current.scrollHeight;
    }, [agentLogs, subAgents]);

    // Autocomplete Logic
    useEffect(() => {
        if (input.startsWith('/') && !input.includes(' ')) {
            const filtered = COMMANDS.filter(c => c.name.startsWith(input));
            setSuggestions(filtered);
            setSelectedIndex(0);
        } else {
            setSuggestions([]);
        }
    }, [input]);

    const handleKeyDown = (e) => {
        if (suggestions.length > 0) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex(prev => (prev + 1) % suggestions.length);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
            } else if (e.key === 'Tab' || (e.key === 'Enter' && suggestions.length > 0)) {
                e.preventDefault();
                setInput(suggestions[selectedIndex].name + ' ');
                setSuggestions([]);
            }
        } else if (e.key === 'Enter') {
            executeCommand(input);
        }
    };

    const addMessage = (agent, text, status = '') => {
        setHistory(prev => [...prev, { type: 'msg', agent, text, status, id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}` }]);
    };

    const addToolUse = (toolName, toolArgs) => {
        setHistory(prev => [...prev, { type: 'tool', toolName, toolArgs, id: `tool-${Date.now()}-${Math.random().toString(36).substr(2, 9)}` }]);
    };

    // ============================================
    // IMPROVEMENT 7: Enhanced Agent Logging
    // ============================================
    const logAgent = (text, log_type = 'info') => {
        setAgentLogs(prev => [...prev, {
            text,
            log_type,
            time: new Date().toLocaleTimeString(),
            id: Date.now() + Math.random()
        }]);
    };

    const sleep = (ms) => new Promise(res => setTimeout(res, ms));

    // ============================================
    // IMPROVEMENT 8: Streaming Command Execution
    // ============================================
    const executeCommand = async (cmdStr) => {
        if (!cmdStr.trim()) return;
        const [cmd, ...args] = cmdStr.trim().split(/\s+/);

        setHistory(prev => [...prev, { type: 'prompt', text: cmdStr, id: `prompt-${Date.now()}-${Math.random().toString(36).substr(2, 9)}` }]);
        setInput('');
        setIsExecuting(true);
        setExecAgent(null);
        setAgentLogs([]);
        setThinkingText('Initializing...');
        setCurrentProgress({ value: 0, total: 100, message: '' });

        try {
            const command = cmd.toLowerCase();

            if (command === '/sub-agent') {
                const agentName = args[0];
                if (!agentName) throw new Error('Specify agent descriptor (e.g. /sub-agent ALFA)');
                if (subAgents.find(a => a.name === agentName)) throw new Error('Agent descriptor already active');
                setConfiguringAgent(agentName);
                setIsExecuting(false);
                return;
            }

            switch (command) {
                case '/help':
                    const helpTable = renderTable(
                        ['ROUTINE', 'PARAMETERS', 'DESCRIPTION', 'EXAMPLE'],
                        COMMANDS.map(c => [c.name, c.flags.join(' ') || 'NONE', c.desc, c.example]),
                        'heavy'
                    );
                    setHistory(prev => [...prev, { type: 'ascii-table', text: helpTable, id: `help-${Date.now()}` }]);
                    break;

                case '/ls':
                    addToolUse('ls_workspace', args[0] || 'studio');
                    const lsRes = await fetch('/api/cli/ls/studio');
                    const lsData = await lsRes.json();

                    const lsTable = renderTable(
                        ['UNIT_NAME', 'SIZE (KB)', 'MOD_DATE'],
                        lsData.files.map(f => [f.name, (f.size/1024).toFixed(1), new Date(f.modified*1000).toLocaleDateString()])
                    );
                    setHistory(prev => [...prev, { type: 'ascii-table', text: lsTable, id: `ls-${Date.now()}` }]);
                    break;

                case '/cat':
                    const filename = args[0];
                    if (!filename) throw new Error('Filename required');
                    addToolUse('cat_file', filename);
                    const catRes = await fetch(`/api/cli/cat/${filename}`);
                    const catData = await catRes.json();
                    if (catRes.status !== 200) throw new Error(catData.detail || 'File not found');
                    setHistory(prev => [...prev, { type: 'code', filename, content: catData.content, id: `code-${Date.now()}` }]);
                    break;

                // ============================================
                // IMPROVEMENT 9: Streaming Backtest
                // ============================================
                case '/backtest':
                    setExecAgent(AGENTS.ENGINE);
                    const ticker = args[0] || 'SPY';
                    const strat = args[1] || 'boll_breakout.py';

                    setThinkingText(`Backtesting ${strat} on ${ticker}...`);
                    addToolUse('engine_execute', `${strat} @ ${ticker}`);

                    const btRes = await fetch('/api/cli/backtest/stream', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            client_id: sessionId,
                            ticker,
                            strategy: strat,
                            lookback_years: 2
                        })
                    });
                    const btData = await btRes.json();

                    if (btRes.status !== 200) throw new Error(btData.detail || 'Backtest failed');

                    addMessage(AGENTS.ENGINE, `Simulation complete. Results flushed to telemetry pane.`, 'success');
                    setHistory(prev => [...prev, { type: 'stats', metrics: btData.metrics, id: `stats-${Date.now()}` }]);
                    break;

                // ============================================
                // IMPROVEMENT 10: Streaming PCA
                // ============================================
                case '/pca':
                    setExecAgent(AGENTS.QUANTS);
                    const universe = args[0] || 'US_TOP50';
                    setThinkingText(`Resolving eigenphysics for ${universe}...`);
                    addToolUse('pca_godmode_run', universe);

                    const pRes = await fetch('/api/cli/pca/stream', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            client_id: sessionId,
                            universe_key: universe,
                            lookback_days: 252
                        })
                    });
                    const pData = await pRes.json();
                    if (pRes.status !== 200) throw new Error(pData.detail || 'PCA Resolution Failed');

                    addMessage(AGENTS.QUANTS, `Factors resolved. Total Variance Explained: ${pData.structure.variance_explained_total?.toFixed(2)}%`, 'success');
                    break;

                case '/clear':
                    setHistory([]);
                    setAgentLogs([]);
                    break;

                default:
                    addMessage(AGENTS.ATLAS, `Unknown routine: ${command}. Type /help for valid matrix.`);
            }
        } catch (e) {
            addMessage(AGENTS.ATLAS, `ALARM: ${e.message}`, 'error');
        } finally {
            setIsExecuting(false);
            setThinkingText('');
            setCurrentProgress({ value: 0, total: 100, message: '' });
        }
    };

    const executeSubAgentCommand = async (agentId, cmdStr) => {
        if (!cmdStr.trim()) return;

        setSubAgents(prev => prev.map(a => {
            if (a.id === agentId) {
                return {
                    ...a,
                    history: [...a.history, {
                        type: 'prompt',
                        text: cmdStr
                    }],
                    isExecuting: true
                };
            }
            return a;
        }));

        setTimeout(() => {
            setSubAgents(prev => prev.map(a => {
                if (a.id === agentId) {
                    return {
                        ...a,
                        history: [...a.history, {
                            type: 'msg',
                            text: `Executed: ${cmdStr}`,
                            agent: AGENTS.ATLAS
                        }],
                        isExecuting: false
                    };
                }
                return a;
            }));
        }, 1000);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[999999] charcoal-surface border-t border-zinc-800 flex flex-col overflow-hidden text-[#d4d4d8]">
            {/* Status Bar */}
            <div className="terminal-status-bar justify-between">
                <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${ws ? 'bg-emerald-500' : 'bg-red-500'} shadow-[0_0_8px_rgba(245,158,11,0.3)]`}></span>
                        <span className="text-zinc-100 font-bold uppercase tracking-widest text-[10px]">ATLAS // TERMINAL</span>
                    </span>
                    <span className="opacity-40 text-zinc-800">|</span>
                    <span className="text-zinc-500 font-mono text-[9px]">INSTITUTIONAL QUANTUM RESEARCH</span>
                </div>
                <div className="flex items-center gap-6">
                    <span className="flex items-center gap-1.5 text-zinc-500 uppercase font-bold tracking-tighter text-[9px]">
                        <span className={`w-1 h-1 rounded-full ${ws ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}></span>
                        {ws ? 'LINKED_AUTH_STABLE' : 'RECONNECTING'}
                    </span>
                    <span className="text-zinc-700 font-mono text-[9px]">{new Date().toLocaleDateString()} {'//'} {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden relative">
                {/* Configuration Modal */}
                <AnimatePresence>
                    {configuringAgent && (
                        <motion.div
                            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                            className="absolute inset-0 z-[100] bg-black/90 backdrop-blur-md flex items-center justify-center p-20"
                        >
                            <div className="max-w-xl w-full border border-zinc-800 bg-[#0c0c0e] p-10 rounded-sm shadow-2xl">
                                <div className="text-[10px] text-amber-500 font-bold uppercase tracking-[0.4em] mb-4">INITIALIZING SUB-AGENT: {configuringAgent}</div>
                                <h2 className="text-2xl font-black text-white mb-8">SELECT COMMAND KIT</h2>

                                <div className="space-y-4 mb-10">
                                    {[
                                        { id: 'workspace', label: 'WORKSPACE KIT', desc: 'File system routines (/ls, /cat)' },
                                        { id: 'simulation', label: 'SIMULATION KIT', desc: 'Backtesting & performance routines' },
                                        { id: 'resolution', label: 'RESOLUTION KIT', desc: 'PCA & Factor eigenphysics routines' },
                                    ].map(kit => (
                                        <div
                                            key={kit.id}
                                            onClick={() => setSelectedKits(prev => prev.includes(kit.id) ? prev.filter(k => k !== kit.id) : [...prev, kit.id])}
                                            className={`p-4 border cursor-pointer transition-all ${selectedKits.includes(kit.id) ? 'border-amber-500 bg-amber-500/5' : 'border-zinc-800 hover:border-zinc-700'}`}
                                        >
                                            <div className="flex justify-between items-center">
                                                <span className={`font-bold ${selectedKits.includes(kit.id) ? 'text-amber-500' : 'text-zinc-400'}`}>{kit.label}</span>
                                                <div className={`w-4 h-4 rounded-full border ${selectedKits.includes(kit.id) ? 'border-amber-500 bg-amber-500' : 'border-zinc-700'}`} />
                                            </div>
                                            <div className="text-[10px] text-zinc-600 mt-1 uppercase tracking-widest">{kit.desc}</div>
                                        </div>
                                    ))}
                                </div>

                                <div className="flex gap-4">
                                    <button
                                        onClick={() => {
                                            setSubAgents(prev => [...prev, {
                                                id: `agent-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                                                name: configuringAgent,
                                                kits: selectedKits,
                                                history: [{ type: 'msg', text: `AGENT ${configuringAgent} ONLINE. KITS: ${selectedKits.join(', ').toUpperCase()}`, agent: AGENTS.ATLAS, id: `msg-init-${Date.now()}` }],
                                                isExecuting: false
                                            }]);
                                            setConfiguringAgent(null);
                                            setSelectedKits([]);
                                        }}
                                        disabled={selectedKits.length === 0}
                                        className="flex-1 bg-amber-500 text-black font-black py-4 uppercase tracking-[0.2em] hover:bg-amber-400 disabled:opacity-20"
                                    >
                                        Deploy Agent
                                    </button>
                                    <button onClick={() => setConfiguringAgent(null)} className="px-8 border border-zinc-800 text-zinc-500 font-bold uppercase tracking-widest hover:text-white">Cancel</button>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Main Terminal */}
                <div className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col p-8 pt-4 custom-scrollbar" ref={scrollRef}>
                    <div className="max-w-5xl mx-auto w-full">
                        {history.map((item, idx) => (
                            <div key={item.id || `hist-${idx}`} className="terminal-msg-block">
                                {item.type === 'big-logo' && (
                                    <div className="flex flex-col items-center justify-center py-20 text-amber-500/90 font-mono">
                                        <pre className="leading-tight text-[11px] text-center">{item.text}</pre>
                                        <div className="mt-4 px-6 py-2 border border-amber-500/20 bg-amber-500/5 text-amber-500/60 font-mono text-[10px] uppercase tracking-[0.3em]">
                                            Institutional Quantum Research Console
                                        </div>
                                    </div>
                                )}
                                {item.type === 'ascii-table' && (
                                    <pre className="text-amber-500/90 leading-[1.3] text-[11px] whitespace-pre font-mono py-10 ml-0 overflow-x-auto custom-scrollbar heavy-table">
                                        {item.text}
                                    </pre>
                                )}
                                {item.type === 'prompt' && (
                                    <div className="flex gap-2.5 text-zinc-600 mt-12 mb-2 items-center">
                                        <span className="text-zinc-800 font-black">❯</span>
                                        <span className="text-zinc-200 font-medium text-[13px] font-mono tracking-tight">{item.text}</span>
                                    </div>
                                )}
                                {item.type === 'msg' && (
                                    <div className="mt-10 mb-6">
                                        <div className="flex items-center gap-4 bg-zinc-900/10 py-1 border-y border-zinc-900/30">
                                            <div className="bg-amber-500 w-2 h-4" />
                                            <span className="font-black text-[11px] uppercase tracking-[0.4em] text-white">
                                                {item.agent.name}
                                            </span>
                                            <span className="text-[9px] text-zinc-800 font-mono ml-auto mr-4 tracking-tighter">
                                                ID_TRANSX_{Math.floor(Math.random()*9000+1000)}
                                            </span>
                                        </div>
                                        <div className="ml-6 mt-6 text-zinc-300 text-[14px] leading-relaxed font-mono max-w-4xl">
                                            {item.text}
                                        </div>
                                    </div>
                                )}
                                {item.type === 'tool' && (
                                    <div className="mt-6 mb-4 ml-7 pl-6 border-l border-zinc-900/40">
                                        <div className="text-[9px] text-zinc-700 font-bold uppercase tracking-[0.3em] mb-2">Tool Instruction</div>
                                        <div className="text-sky-500 font-mono text-[11px] bg-sky-500/5 px-4 py-2 border border-sky-500/10 inline-block rounded-sm">
                                            <span className="opacity-50">CALL:</span> {item.toolName}({JSON.stringify(item.toolArgs)})
                                        </div>
                                    </div>
                                )}
                                {item.type === 'code' && (
                                    <div className="ml-8 my-8 border border-zinc-800/60 rounded bg-black/20 overflow-hidden">
                                        <div className="bg-zinc-900/50 px-4 py-1.5 text-[9px] text-zinc-500 flex justify-between items-center border-b border-zinc-800/40">
                                            <span className="font-mono uppercase tracking-widest">{item.filename}</span>
                                            <span className="opacity-40 uppercase tracking-tighter">Raw Source</span>
                                        </div>
                                        <pre className="p-6 text-[11px] text-zinc-400 overflow-x-auto font-mono leading-6 custom-scrollbar">
                                            {item.content}
                                        </pre>
                                    </div>
                                )}
                                {item.type === 'stats' && (
                                    <div className="ml-8 my-8 grid grid-cols-2 gap-x-12 gap-y-4 max-w-xl p-6 bg-zinc-900/20 rounded border border-zinc-800/30">
                                        {Object.entries(item.metrics).slice(0, 10).map(([k, v]) => (
                                            <div key={k} className="flex justify-between items-center border-b border-zinc-800/20 pb-2">
                                                <span className="text-[9px] text-zinc-500 font-bold tracking-widest uppercase">{k.replace(/_/g, ' ')}</span>
                                                <span className="text-[12px] text-emerald-500 font-mono">{v}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}

                        {/* ============================================ */}
                        {/* IMPROVEMENT 11: Live Execution Logs Panel   */}
                        {/* ============================================ */}
                        {isExecuting && agentLogs.length > 0 && (
                            <div className="mt-8 mb-6 ml-8 border border-zinc-800/40 bg-zinc-900/10 rounded">
                                <div className="bg-zinc-900/50 px-4 py-2 border-b border-zinc-800/40 text-[9px] text-zinc-500 uppercase tracking-widest">
                                    Execution Logs
                                </div>
                                <div className="p-4 space-y-2 max-h-60 overflow-y-auto custom-scrollbar font-mono">
                                    {agentLogs.map(log => (
                                        <div key={log.id} className="flex gap-3 text-[11px]">
                                            <span className="text-zinc-700 text-[9px]">{log.time}</span>
                                            <span className={
                                                log.log_type === 'error' ? 'text-red-500' :
                                                log.log_type === 'success' ? 'text-emerald-500' :
                                                'text-zinc-400'
                                            }>
                                                {log.text}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* ============================================ */}
                        {/* IMPROVEMENT 12: Progress Bar                */}
                        {/* ============================================ */}
                        {isExecuting && currentProgress.total > 0 && (
                            <div className="mt-4 mb-6 ml-8">
                                <div className="text-[9px] text-zinc-600 mb-2 uppercase tracking-widest">
                                    {currentProgress.message}
                                </div>
                                <div className="w-full h-2 bg-zinc-900 rounded-full overflow-hidden">
                                    <motion.div
                                        className="h-full bg-amber-500"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${(currentProgress.value / currentProgress.total) * 100}%` }}
                                        transition={{ duration: 0.3 }}
                                    />
                                </div>
                                <div className="text-[9px] text-zinc-700 mt-1 font-mono">
                                    {currentProgress.value} / {currentProgress.total} ({Math.round((currentProgress.value / currentProgress.total) * 100)}%)
                                </div>
                            </div>
                        )}

                        <div className="h-60" />
                    </div>
                </div>

                {/* Sub-Agents Panel */}
                <div className="flex bg-[#08080a]">
                    <AnimatePresence mode="popLayout">
                        {subAgents.map((agent) => (
                            <motion.div
                                key={agent.id}
                                initial={{ width: 0, opacity: 0 }}
                                animate={{ width: 440, opacity: 1 }}
                                exit={{ width: 0, opacity: 0 }}
                                className="border-l border-zinc-800/50 flex flex-col shadow-2xl relative"
                            >
                                <div className="h-10 bg-[#121214] border-b border-zinc-800/80 flex items-center px-4 shrink-0">
                                    <div className="flex items-center gap-3">
                                        <div className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]" />
                                        <span className="text-amber-500 font-black text-[10px] tracking-[0.3em] uppercase">{agent.name}</span>
                                    </div>
                                    <button
                                        onClick={() => setSubAgents(prev => prev.filter(a => a.id !== agent.id))}
                                        className="ml-auto text-zinc-800 hover:text-red-500 font-bold text-[9px] uppercase tracking-widest transition-colors"
                                    >
                                        [ Kill_Agent ]
                                    </button>
                                </div>

                                <div className="flex-1 overflow-y-auto p-6 font-mono custom-scrollbar space-y-6">
                                    <div className="flex flex-wrap gap-2 mb-4">
                                        {agent.kits.map(k => (
                                            <span key={k} className="text-[8px] px-2 py-0.5 border border-zinc-800 bg-zinc-900/50 text-zinc-600 font-black uppercase tracking-tighter">
                                                {k}_ENABLED
                                            </span>
                                        ))}
                                    </div>
                                    {agent.history.map((item, i) => (
                                        <div key={i} className="text-[11px] leading-relaxed">
                                            {item.type === 'prompt' && (
                                                <div className="flex gap-3 text-amber-500">
                                                    <span className="font-black">❯</span>
                                                    <span>{item.text}</span>
                                                </div>
                                            )}
                                            {item.type === 'msg' && (
                                                <div className="flex gap-3">
                                                    <span className="text-zinc-800 shrink-0 font-black">→</span>
                                                    <span className="text-zinc-400">{item.text}</span>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                    {agent.isExecuting && (
                                        <div className="flex gap-3 text-zinc-600 items-center">
                                            <motion.div
                                                animate={{ rotate: 360 }}
                                                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                                                className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full"
                                            />
                                            <span className="text-[10px]">Executing...</span>
                                        </div>
                                    )}
                                    <div className="h-20" />
                                </div>

                                <div className="h-14 bg-[#0c0c0e] border-t border-zinc-800 flex items-center px-5 shrink-0">
                                    <span className="text-amber-900 font-black mr-4 text-xs select-none">❯</span>
                                    <input
                                        className="bg-transparent border-none outline-none text-zinc-200 text-[13px] font-mono w-full placeholder:text-zinc-900"
                                        placeholder={`Enter ${agent.name} routine...`}
                                        spellCheck={false}
                                        disabled={agent.isExecuting}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !agent.isExecuting) {
                                                executeSubAgentCommand(agent.id, e.target.value);
                                                e.target.value = '';
                                            }
                                        }}
                                    />
                                </div>

                                <div className="h-4 bg-zinc-900/30 flex items-center px-4 justify-between text-[7px] text-zinc-800 uppercase font-black tracking-[0.2em]">
                                    <span>Buff: 0kb</span>
                                    <span className="text-emerald-950">Active_Sync</span>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            </div>

            {/* Command Input */}
            <div className="terminal-command-deck">
                <div className="relative flex-1 flex items-center h-full">
                    <span className="text-zinc-300 font-black mr-4 text-lg select-none">❯</span>
                    <input
                        ref={inputRef}
                        className="flex-1 bg-transparent border-none outline-none text-zinc-100 text-[14px] font-mono placeholder:text-zinc-800 h-full"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.ctrlKey && e.key === 'l') {
                                e.preventDefault();
                                setHistory([]);
                            } else {
                                handleKeyDown(e);
                            }
                        }}
                        spellCheck={false}
                        autoComplete="off"
                        placeholder={isExecuting ? "Executing routine..." : "Enter routine code..."}
                        disabled={isExecuting}
                    />

                    <AnimatePresence>
                        {suggestions.length > 0 && (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 10 }}
                                className="absolute bottom-full left-0 mb-4 w-[400px] bg-[#1a1a1c] border border-zinc-800 rounded-sm shadow-2xl overflow-hidden z-[100]"
                            >
                                <div className="bg-[#222224] px-4 py-2 border-b border-zinc-800 text-[10px] font-bold text-zinc-500 tracking-[0.2em] uppercase">
                                    Available Routines
                                </div>
                                {suggestions.map((s, i) => (
                                    <div
                                        key={s.name}
                                        className={`px-5 py-3 flex flex-col gap-1 cursor-pointer transition-colors ${i === selectedIndex ? 'bg-zinc-800' : 'hover:bg-zinc-800/30'}`}
                                        onClick={() => {
                                            setInput(s.name + ' ');
                                            setSuggestions([]);
                                            inputRef.current?.focus();
                                        }}
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className={`text-[13px] font-bold font-mono ${i === selectedIndex ? 'text-amber-500' : 'text-zinc-300'}`}>{s.name}</span>
                                            <span className="text-[10px] text-zinc-600 font-mono italic opacity-70">{s.desc}</span>
                                        </div>
                                        {s.flags.length > 0 && (
                                            <div className="flex flex-wrap gap-2 text-[10px] text-zinc-500 font-mono mt-0.5">
                                                {s.flags.map(f => (
                                                    <span key={f} className="text-zinc-700 font-bold">{f}</span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                
                {isExecuting && (
                    <div className="flex items-center gap-3 pl-6 border-l border-zinc-800/50 h-6">
                        <motion.div 
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                            className="w-3.5 h-3.5 border-2 border-amber-500 border-t-transparent rounded-full"
                        />
                        <span className="font-mono text-[10px] text-amber-500/80 font-bold uppercase tracking-widest">{thinkingText}</span>
                    </div>
                )}
            </div>
        </div>
    );
}
