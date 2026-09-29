
import React, { useState } from 'react';
import { 
    X, Search, Globe, Cpu, Database, 
    Zap, LayoutGrid, List, Trash2, 
    Plus, CheckCircle2, AlertCircle,
    ChevronRight, Hash, TrendingUp,
    Shield, Briefcase
} from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { UNIVERSE_REGISTRY, UNIVERSE_METADATA } from '@/lib/universe-registry';

const CATEGORIES = [
    { id: 'All', icon: LayoutGrid },
    { id: 'Equities', icon: Briefcase },
    { id: 'Crypto', icon: Zap },
    { id: 'Asia', icon: Globe },
    { id: 'Macro', icon: TrendingUp },
    { id: 'Forex', icon: Hash },
    { id: 'Custom', icon: Plus },
];

export default function UniverseModal({ isOpen, onClose, onSelect, currentTickers = [] }) {
    const [activeCategory, setActiveCategory] = useState('All');
    const [searchQuery, setSearchQuery] = useState('');
    const [batchText, setBatchText] = useState('');
    const [localTickers, setLocalTickers] = useState(currentTickers);

    const filteredMetadata = UNIVERSE_METADATA.filter(meta => {
        const matchesCategory = activeCategory === 'All' || meta.category === activeCategory;
        const matchesSearch = meta.label.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesCategory && matchesSearch;
    });

    const handleLoadPreset = (presetId) => {
        const tickers = UNIVERSE_REGISTRY[presetId] || [];
        // Unique merge
        const newSet = new Set([...localTickers, ...tickers]);
        setLocalTickers(Array.from(newSet));
    };

    const handleBatchAdd = () => {
        const parsed = batchText.split(/[,\n]/).map(t => t.trim().toUpperCase()).filter(Boolean);
        const newSet = new Set([...localTickers, ...parsed]);
        setLocalTickers(Array.from(newSet));
        setBatchText('');
    };

    const removeTicker = (ticker) => {
        setLocalTickers(localTickers.filter(t => t !== ticker));
    };

    const handleApply = () => {
        onSelect(localTickers);
        onClose();
    };

    return (
        <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] animate-in fade-in" />
                <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-5xl h-[80vh] bg-[#0a0a0a] border border-terminal-gray/30 rounded-xl overflow-hidden shadow-2xl z-[101] flex flex-col font-mono text-terminal-text animate-in zoom-in-95 duration-200">
                    
                    {/* Header */}
                    <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#0d0d0d]">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-terminal-yellow/10 rounded-lg">
                                <Database size={20} className="text-terminal-yellow" />
                            </div>
                            <div>
                                <Dialog.Title className="text-lg font-black uppercase tracking-widest text-white">
                                    Sovereign Universe Registry
                                </Dialog.Title>
                                <Dialog.Description className="text-[10px] text-terminal-dim font-bold uppercase tracking-tighter">
                                    Select Presets or Inject Custom Vector Batches
                                </Dialog.Description>
                            </div>
                        </div>
                        <button 
                            onClick={onClose}
                            className="p-2 hover:bg-white/5 rounded-full text-terminal-dim hover:text-white transition-all"
                        >
                            <X size={24} />
                        </button>
                    </div>

                    <div className="flex-1 flex overflow-hidden">
                        {/* Sidebar */}
                        <div className="w-56 border-r border-white/5 bg-[#080808] p-2 flex flex-col gap-1 overflow-y-auto">
                            <span className="text-[9px] font-black text-terminal-dim px-3 py-2 uppercase tracking-[0.2em]">Categories</span>
                            {CATEGORIES.map(cat => (
                                <button
                                    key={cat.id}
                                    onClick={() => setActiveCategory(cat.id)}
                                    className={`
                                        flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-xs font-bold uppercase tracking-widest
                                        ${activeCategory === cat.id 
                                            ? 'bg-terminal-yellow text-black' 
                                            : 'text-terminal-dim hover:bg-white/5 hover:text-white'}
                                    `}
                                >
                                    <cat.icon size={16} />
                                    {cat.id}
                                </button>
                            ))}
                        </div>

                        {/* Main Content */}
                        <div className="flex-1 flex flex-col bg-[#020202] overflow-hidden">
                            {activeCategory !== 'Custom' ? (
                                <>
                                    <div className="p-4 border-b border-white/5 flex gap-4">
                                        <div className="flex-1 relative">
                                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-terminal-dim" size={16} />
                                            <input 
                                                type="text"
                                                placeholder="Search presets..."
                                                value={searchQuery}
                                                onChange={e => setSearchQuery(e.target.value)}
                                                className="w-full bg-[#0d0d0d] border border-white/10 rounded-lg py-2 pl-10 pr-4 text-sm outline-none focus:border-terminal-yellow/50 transition-all"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex-1 overflow-y-auto p-4 hide-scrollbar">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                            {filteredMetadata.map(meta => (
                                                <div 
                                                    key={meta.id}
                                                    className="bg-[#0d0d0d] border border-white/5 hover:border-terminal-yellow/30 p-4 rounded-xl flex flex-col gap-3 group transition-all"
                                                >
                                                    <div className="flex justify-between items-start">
                                                        <div className="flex flex-col">
                                                            <span className="text-xs font-black text-white uppercase tracking-wider">{meta.label}</span>
                                                            <span className="text-[9px] text-terminal-dim font-bold">{meta.category} • {meta.count} Assets</span>
                                                        </div>
                                                        <CheckCircle2 size={16} className="text-terminal-green opacity-0 group-hover:opacity-100 transition-opacity" />
                                                    </div>
                                                    <button 
                                                        onClick={() => handleLoadPreset(meta.id)}
                                                        className="mt-2 w-full py-2 bg-terminal-yellow/5 border border-terminal-yellow/20 text-[10px] font-bold uppercase tracking-widest text-terminal-yellow hover:bg-terminal-yellow hover:text-black transition-all rounded-lg"
                                                    >
                                                        Load Vector
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="p-6 flex flex-col gap-6 h-full">
                                    <div className="flex-1 flex flex-col gap-3">
                                        <label className="text-[10px] font-black text-terminal-dim uppercase tracking-[0.2em]">Batch Injector (CSV/NL)</label>
                                        <textarea
                                            value={batchText}
                                            onChange={e => setBatchText(e.target.value)}
                                            placeholder="Paste tickers... e.g. AAPL, MSFT, RELIANCE.NS, BTC-USD"
                                            className="flex-1 bg-[#0d0d0d] border border-white/10 rounded-xl p-4 text-sm outline-none focus:border-terminal-yellow/50 transition-all font-mono resize-none"
                                        />
                                    </div>
                                    <button 
                                        onClick={handleBatchAdd}
                                        className="py-4 bg-terminal-yellow text-black font-black uppercase tracking-widest rounded-xl hover:scale-[1.02] active:scale-95 transition-all shadow-[0_0_20px_rgba(255,204,0,0.3)]"
                                    >
                                        Inject Vectors
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Selected Panel */}
                        <div className="w-80 border-l border-white/5 bg-[#080808] flex flex-col overflow-hidden">
                            <div className="p-4 border-b border-white/5 bg-[#0d0d0d] flex justify-between items-center">
                                <div className="flex flex-col">
                                    <span className="text-xs font-black text-white uppercase tracking-widest">Active Universe</span>
                                    <span className="text-[9px] text-terminal-yellow font-bold uppercase">{localTickers.length} Vectors Engaged</span>
                                </div>
                                <button 
                                    onClick={() => setLocalTickers([])}
                                    className="p-1.5 text-red-500/50 hover:text-red-500 hover:bg-red-500/10 rounded transition-all"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                            <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1 hide-scrollbar">
                                {localTickers.map(ticker => (
                                    <div 
                                        key={ticker}
                                        className="flex items-center justify-between px-3 py-2 bg-white/5 border border-white/5 rounded-lg group"
                                    >
                                        <span className="text-[11px] font-black text-white tracking-widest">{ticker}</span>
                                        <button 
                                            onClick={() => removeTicker(ticker)}
                                            className="text-terminal-dim hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                                        >
                                            <X size={14} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                            <div className="p-4 bg-[#0d0d0d] border-t border-white/5">
                                <button 
                                    onClick={handleApply}
                                    className="w-full py-3 bg-terminal-green text-black font-black uppercase tracking-widest rounded-xl hover:bg-terminal-green/90 transition-all flex items-center justify-center gap-2"
                                >
                                    <Zap size={16} fill="currentColor" />
                                    Apply Universe
                                </button>
                            </div>
                        </div>
                    </div>
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    );
}

