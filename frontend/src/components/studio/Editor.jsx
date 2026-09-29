"use client";
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import dynamic from 'next/dynamic';
import { Terminal, ChevronLeft, Command, GitCompare, Save, Sparkles, ListTree, AlertTriangle } from 'lucide-react';
import { useStudioEditorStore } from '@/stores/studio/editorStore';
import { useStudioPreferenceStore } from '@/stores/studio/preferenceStore';
import { useStudioResultStore } from '@/stores/studio/resultStore';
import { useStudioProjectStore } from '@/stores/studio/projectStore';

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), {
    ssr: false,
    loading: () => <div className="h-full flex items-center justify-center bg-[#0a0a0f]"><div className="animate-spin w-8 h-8 border-2 border-amber-500/30 border-t-amber-500 rounded-full" /></div>
});

// ── LSP-lite (P5-W1 polish) ──────────────────────────────────────────────
// Lightweight client-side diagnostics/completion/symbols only. This is NOT a
// language server: no backend /studio validation endpoint exists for raw
// source, so these checks are best-effort and the bounded backend policy
// (class Strategy required, denied imports) remains authoritative at run time.

const LIKELY_DENIED_IMPORTS = ['os', 'sys', 'subprocess', 'socket', 'pathlib', 'shutil', 'ctypes'];

// Pure: analyze Python strategy source into diagnostics.
// Returns [{ line (1-based), severity: 'error'|'warning', message }].
export function analyzePythonSource(source) {
    const diagnostics = [];
    const text = source || '';
    if (!text.trim()) {
        return [{ line: 1, severity: 'error', message: 'Strategy code is empty.' }];
    }
    const lines = text.split('\n');
    if (!/^\s*class\s+Strategy\b/m.test(text)) {
        diagnostics.push({ line: 1, severity: 'error', message: 'Script must define class Strategy (backend policy rejects otherwise).' });
    }
    const pairs = [['(', ')'], ['[', ']'], ['{', '}']];
    pairs.forEach(([open, close]) => {
        let depth = 0;
        let firstLine = 0;
        lines.forEach((ln, idx) => {
            const stripped = ln.split('#')[0];
            for (const ch of stripped) {
                if (ch === open) { depth += 1; if (depth === 1) firstLine = idx + 1; }
                if (ch === close) depth -= 1;
            }
            if (depth < 0) {
                diagnostics.push({ line: idx + 1, severity: 'error', message: `Unbalanced '${close}' — more closers than openers.` });
                depth = 0;
            }
        });
        if (depth > 0) diagnostics.push({ line: firstLine || 1, severity: 'error', message: `Unbalanced '${open}' — ${depth} unclosed.` });
    });
    const hasTab = lines.some((l) => /^\t/.test(l));
    const hasSpaces = lines.some((l) => /^ +\S/.test(l));
    if (hasTab && hasSpaces) {
        const idx = lines.findIndex((l) => /^\t/.test(l));
        diagnostics.push({ line: idx + 1, severity: 'warning', message: 'Mixed tabs and spaces for indentation.' });
    }
    lines.forEach((ln, idx) => {
        if (ln.length > 120) diagnostics.push({ line: idx + 1, severity: 'warning', message: `Line exceeds 120 chars (${ln.length}).` });
        const m = ln.match(/^\s*(?:import|from)\s+(\w+)/);
        if (m && LIKELY_DENIED_IMPORTS.includes(m[1])) {
            diagnostics.push({ line: idx + 1, severity: 'warning', message: `Import '${m[1]}' may violate the bounded execution policy.` });
        }
    });
    return diagnostics;
}

// Pure: extract document symbols (class/def) with 1-based line numbers.
export function extractSymbols(source) {
    const symbols = [];
    (source || '').split('\n').forEach((ln, idx) => {
        const m = ln.match(/^\s*(class|def)\s+([A-Za-z_]\w*)/);
        if (m) symbols.push({ kind: m[1], name: m[2], line: idx + 1 });
    });
    return symbols;
}

export const STRATEGY_COMPLETIONS = [
    { label: 'class Strategy', kind: 'snippet', detail: 'Strategy skeleton', insert: 'class Strategy:\n    def generate_signals(self, data):\n        return []\nstrategy = Strategy()' },
    { label: 'def generate_signals', kind: 'snippet', detail: 'Signal method', insert: 'def generate_signals(self, data):\n    return []' },
    { label: 'def __init__', kind: 'snippet', detail: 'Constructor', insert: 'def __init__(self):\n    pass' },
    ...['def', 'class', 'return', 'import', 'from', 'for', 'while', 'if', 'elif', 'else', 'try', 'except', 'with', 'as', 'lambda', 'pass', 'None', 'True', 'False', 'self', 'data', 'strategy'].map((w) => ({ label: w, kind: 'keyword', detail: 'Python keyword', insert: w })),
];

// Pure: filter the keyword completion list by prefix query.
export function filterCompletions(query) {
    const q = (query || '').toLowerCase();
    if (!q) return STRATEGY_COMPLETIONS;
    return STRATEGY_COMPLETIONS.filter((c) => c.label.toLowerCase().includes(q));
}

const Editor = ({ value, onChange, height = '100%', options = {} }) => {
    const isExecuting = useStudioResultStore((state) => state.isExecuting);
    const isPlaying = useStudioResultStore((state) => state.isPlaying);
    const kernelCollapsed = useStudioPreferenceStore((state) => state.kernelCollapsed);
    const setKernelCollapsed = useStudioPreferenceStore((state) => state.setKernelCollapsed);
    const selectedStrategy = useStudioEditorStore((state) => state.selectedStrategy);
    const setSelectedCode = useStudioEditorStore((state) => state.setSelectedCode);
    const runtimeStatus = isExecuting ? 'EXECUTING' : isPlaying ? 'PLAYBACK' : 'IDLE';
    const [paletteOpen, setPaletteOpen] = useState(false);
    const [paletteQuery, setPaletteQuery] = useState('');
    const [showDiff, setShowDiff] = useState(false);
    const saveAll = useStudioProjectStore((s) => s.saveAll);
    const autosaveFile = useStudioProjectStore((s) => s.autosaveFile);
    const files = useStudioProjectStore((s) => s.files);
    const activeId = useStudioProjectStore((s) => s.activeId);
    const storeAutoSavedAt = useStudioProjectStore((s) => s.autoSavedAt);
    const activeFile = files.find((f) => f.id === activeId);
    const isDirty = !!activeFile?.dirty;
    const [autoSavedAt, setAutoSavedAt] = useState(null);
    const editorRef = useRef(null);
    const monacoRef = useRef(null);

    // Conflict-safe autosave: commits the draft locally with an autoSavedAt
    // stamp (newer timestamp wins on rehydrate; previous payload kept as
    // backup). Server sync remains open — no backend project API exists.
    useEffect(() => {
        if (!activeFile || !isDirty) return undefined;
        const t = setTimeout(() => {
            autosaveFile(activeFile.id);
            setAutoSavedAt(new Date().toISOString());
        }, 1200);
        return () => clearTimeout(t);
    }, [value, isDirty, activeFile, autosaveFile]);
    const handleFormat = useCallback(() => {
        // Best-effort formatting via Monaco — trim trailing whitespace
        const formatted = value.split('\n').map((l) => l.replace(/\s+$/, '')).join('\n');
        if (formatted !== value) onChange(formatted);
    }, [value, onChange]);

    const diagnostics = useMemo(() => analyzePythonSource(value), [value]);
    const symbols = useMemo(() => extractSymbols(value), [value]);
    const errorCount = diagnostics.filter((d) => d.severity === 'error').length;
    const warningCount = diagnostics.filter((d) => d.severity === 'warning').length;
    const completions = useMemo(() => filterCompletions(paletteQuery), [paletteQuery]);

    // Push LSP-lite markers into Monaco when available.
    useEffect(() => {
        const editor = editorRef.current;
        const monaco = monacoRef.current;
        if (!editor || !monaco) return undefined;
        const model = editor.getModel?.();
        if (!model) return undefined;
        const markers = diagnostics.map((d) => ({
            severity: d.severity === 'error' ? monaco.MarkerSeverity.Error : monaco.MarkerSeverity.Warning,
            message: d.message,
            startLineNumber: d.line,
            startColumn: 1,
            endLineNumber: d.line,
            endColumn: 1000,
        }));
        monaco.editor.setModelMarkers(model, 'studio-lsp-lite', markers);
        return undefined;
    }, [diagnostics, value]);

    const jumpToSymbol = useCallback((line) => {
        const editor = editorRef.current;
        if (!editor) return;
        editor.revealLineInCenter(line);
        editor.setPosition({ lineNumber: line, column: 1 });
        editor.focus();
        setPaletteOpen(false);
    }, []);

    const insertCompletion = useCallback((insert) => {
        const editor = editorRef.current;
        if (!editor) return;
        const selection = editor.getSelection();
        editor.executeEdits('studio-completion', [{ range: selection, text: insert, forceMoveMarkers: true }]);
        editor.focus();
        setPaletteOpen(false);
    }, []);

    const displayedAutosave = autoSavedAt || storeAutoSavedAt;

    return (
        <div className={`flex flex-col bg-[#050507] border-r border-white/5 h-full overflow-hidden transition-all duration-300 shadow-[10px_0_30px_rgba(0,0,0,0.5)] z-50 ${kernelCollapsed ? 'w-0 opacity-0 pointer-events-none' : 'w-[420px] opacity-100'}`}>
            {/* IDE Header */}
            <div className="h-9 px-3 border-b border-white/5 flex items-center justify-between bg-[#0a0a0f]">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 opacity-60">
                         <div className="w-2 h-2 rounded-full bg-blue-500" />
                         <span className="text-[9px] font-mono text-white tracking-widest uppercase">PYTHON 3.11</span>
                    </div>
                    <div className="w-px h-3 bg-white/10" />
                    <div className="flex items-center gap-1.5">
                        <Terminal size={11} className="text-amber-500" />
                        <span className="text-[10px] font-mono font-bold text-white/90 tracking-widest uppercase truncate max-w-[120px]">
                            {selectedStrategy?.toUpperCase() || 'UNTITLED'}
                        </span>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {isDirty && <span className="text-[8px] font-mono text-amber-500 font-bold">• DIRTY</span>}
                    {displayedAutosave && <span className="text-[7px] font-mono text-[#64748b]">autosaved {new Date(displayedAutosave).toLocaleTimeString()}</span>}
                    <button aria-label="Command palette" onClick={() => setPaletteOpen((o) => !o)} className="p-1 hover:bg-white/10 rounded text-[#64748b] hover:text-white"><Command size={14} /></button>
                    <button aria-label="Show diff" onClick={() => setShowDiff((o) => !o)} className="p-1 hover:bg-white/10 rounded text-[#64748b] hover:text-white"><GitCompare size={14} /></button>
                    <button aria-label="Format code" onClick={handleFormat} className="p-1 hover:bg-white/10 rounded text-[#64748b] hover:text-white"><Sparkles size={14} /></button>
                    <button aria-label="Save all" onClick={saveAll} className="p-1 hover:bg-white/10 rounded text-[#64748b] hover:text-white"><Save size={14} /></button>
                    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${isExecuting ? 'bg-amber-500/10 border-amber-500/20' : 'bg-white/5 border-white/10'}`}>
                        <div className={`w-1 h-1 rounded-full ${isExecuting ? 'bg-amber-500 animate-pulse' : 'bg-[#64748b]'}`} />
                        <span className={`text-[8px] font-mono font-bold uppercase ${isExecuting ? 'text-amber-500' : 'text-[#8b95a7]'}`}>{runtimeStatus}</span>
                    </div>
                    <button
                        onClick={() => setKernelCollapsed(true)}
                        className="p-1 hover:bg-white/5 rounded text-[#64748b] transition-colors"
                    >
                        <ChevronLeft size={14} />
                    </button>
                </div>
            </div>
            {/* LSP-lite bar: symbol jump + diagnostic counts */}
            <div className="h-7 px-3 border-b border-white/5 flex items-center gap-2 bg-black/30">
                <ListTree size={11} className="text-[#64748b] flex-shrink-0" />
                <select
                    aria-label="Jump to symbol"
                    value=""
                    onChange={(e) => { const line = Number(e.target.value); if (Number.isFinite(line) && line > 0) jumpToSymbol(line); }}
                    className="flex-1 min-w-0 bg-transparent text-[10px] font-mono text-[#8b95a7] outline-none cursor-pointer"
                >
                    <option value="">{symbols.length === 0 ? 'No symbols — define class/def' : `Symbols (${symbols.length}) — jump…`}</option>
                    {symbols.map((s, i) => (
                        <option key={`${s.line}-${s.name}-${i}`} value={s.line} className="bg-[#0a0a0f]">{s.kind} {s.name} :{s.line}</option>
                    ))}
                </select>
                <span className={`flex items-center gap-1 text-[9px] font-mono ${errorCount > 0 ? 'text-red-400' : warningCount > 0 ? 'text-amber-400' : 'text-emerald-500'}`}>
                    <AlertTriangle size={10} />
                    {errorCount > 0 || warningCount > 0 ? `${errorCount} err ${warningCount} warn` : 'clean'}
                </span>
            </div>

            <div className="flex-1 min-h-0 bg-[#020204] relative">
                {/* Code Editor */}
                <MonacoEditor
                    height="100%"
                    language="python"
                    theme="vs-dark"
                    value={value}
                    onChange={v => onChange(v || '')}
                    options={{
                        minimap: { enabled: false },
                        fontSize: 12,
                        fontFamily: "'JetBrains Mono', monospace",
                        lineNumbers: 'on',
                        scrollBeyondLastLine: false,
                        padding: { top: 16, bottom: 60 },
                        automaticLayout: true,
                        cursorStyle: 'block',
                        wordWrap: 'on',
                        scrollbar: {
                            verticalScrollbarSize: 4,
                            horizontalScrollbarSize: 4,
                            useShadows: false
                        },
                        renderLineHighlight: 'all',
                        overviewRulerBorder: false,
                        hideCursorInOverviewRuler: true
                    }}
                    onMount={(editor, monaco) => {
                        editorRef.current = editor;
                        monacoRef.current = monaco;
                        // Symbol navigation + diagnostics hook (best quality)
                        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyP, () => setPaletteOpen(true));
                        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => saveAll());
                        editor.onDidChangeCursorSelection(() => {
                            try {
                                const model = editor.getModel?.();
                                const sel = editor.getSelection?.();
                                if (model && sel && !sel.isEmpty()) setSelectedCode(model.getValueInRange(sel));
                                else setSelectedCode('');
                            } catch {
                                // Selection tracking is best-effort; editing never depends on it.
                            }
                        });
                    }}
                />
                {paletteOpen && (
                    <div className="absolute inset-0 z-20 bg-black/60 backdrop-blur-sm p-6 flex items-start justify-center">
                        <div className="w-full max-w-md bg-[#0a0a0f] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
                            <input autoFocus value={paletteQuery} onChange={(e) => setPaletteQuery(e.target.value)} placeholder="Command palette — type to filter (save, format, diff, run)" className="w-full h-10 px-4 bg-transparent border-b border-white/10 text-sm font-mono text-white outline-none" />
                            <div className="p-2 space-y-1 max-h-60 overflow-auto">
                                {[
                                    { id: 'save', label: 'Save All', action: () => { saveAll(); setPaletteOpen(false); } },
                                    { id: 'format', label: 'Format Document', action: () => { handleFormat(); setPaletteOpen(false); } },
                                    { id: 'diff', label: 'Show Diff (saved vs working)', action: () => { setShowDiff(true); setPaletteOpen(false); } },
                                ].filter((c) => c.label.toLowerCase().includes(paletteQuery.toLowerCase())).map((c) => (
                                    <button key={c.id} onClick={c.action} className="w-full text-left px-3 py-2 rounded hover:bg-white/5 text-sm font-mono text-white">{c.label}</button>
                                ))}
                                <div className="px-3 pt-2 text-[9px] font-mono font-bold tracking-widest text-[#64748b]">COMPLETIONS — click to insert</div>
                                {completions.slice(0, 8).map((c) => (
                                    <button key={c.label} onClick={() => insertCompletion(c.insert)} className="w-full text-left px-3 py-1.5 rounded hover:bg-white/5 text-xs font-mono text-[#8b95a7]">
                                        <span className="text-amber-400">{c.label}</span>
                                        <span className="ml-2 text-[#64748b]">{c.kind} · {c.detail}</span>
                                    </button>
                                ))}
                                {symbols.length > 0 && (
                                    <>
                                        <div className="px-3 pt-2 text-[9px] font-mono font-bold tracking-widest text-[#64748b]">SYMBOLS — click to jump</div>
                                        {symbols.filter((s) => s.name.toLowerCase().includes(paletteQuery.toLowerCase())).map((s, i) => (
                                            <button key={`${s.line}-${s.name}-${i}`} onClick={() => jumpToSymbol(s.line)} className="w-full text-left px-3 py-1.5 rounded hover:bg-white/5 text-xs font-mono text-[#8b95a7]">
                                                <span className="text-blue-400">{s.kind}</span> {s.name} <span className="text-[#64748b]">:{s.line}</span>
                                            </button>
                                        ))}
                                    </>
                                )}
                            </div>
                            <button onClick={() => setPaletteOpen(false)} className="w-full h-8 text-xs font-mono text-[#64748b] hover:text-white border-t border-white/5">Close (Esc)</button>
                        </div>
                    </div>
                )}
                {showDiff && (
                    <div className="absolute inset-0 z-20 bg-black/80 backdrop-blur-sm p-4 flex flex-col">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-mono font-bold text-white tracking-widest">DIFF — saved vs working</span>
                            <button onClick={() => setShowDiff(false)} className="text-[#64748b] hover:text-white">✕</button>
                        </div>
                        <div className="flex-1 grid grid-cols-2 gap-2 font-mono text-xs">
                            <div className="bg-[#0a0a0f] border border-white/10 rounded p-3 overflow-auto whitespace-pre text-[#8b95a7]">{activeFile?.content || '-- no saved version --'}</div>
                            <div className="bg-amber-500/5 border border-amber-500/20 rounded p-3 overflow-auto whitespace-pre text-white">{value}</div>
                        </div>
                    </div>
                )}
            </div>
            {/* Diagnostics strip: LSP-lite findings (client-side only, backend policy authoritative) */}
            {diagnostics.length > 0 && (
                <div className="max-h-20 overflow-auto border-t border-white/5 bg-black/40 px-3 py-1.5 space-y-1">
                    {diagnostics.slice(0, 6).map((d, i) => (
                        <div key={i} className={`text-[9px] font-mono ${d.severity === 'error' ? 'text-red-400' : 'text-amber-300/80'}`}>
                            {d.severity === 'error' ? 'error' : 'warn'} · line {d.line}: {d.message}
                        </div>
                    ))}
                    {diagnostics.length > 6 && <div className="text-[9px] font-mono text-[#64748b]">+{diagnostics.length - 6} more</div>}
                </div>
            )}

            <style jsx>{`
                @keyframes shimmer { 100% { transform: translateX(100%); } }
            `}</style>
        </div>
    );
};

export default Editor;
