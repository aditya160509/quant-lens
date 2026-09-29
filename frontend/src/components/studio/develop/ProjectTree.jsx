"use client";
import React, { useMemo, useState } from 'react';
import { FileCode, FileJson, Plus, Trash2, Copy, Edit3, Save, FolderInput } from 'lucide-react';
import { useStudioProjectStore, folderOf, normalizeFolder } from '@/stores/studio/projectStore';

const iconFor = (name) => (name.endsWith('.json') ? FileJson : FileCode);

export default function ProjectTree() {
    const files = useStudioProjectStore((s) => s.files);
    const activeId = useStudioProjectStore((s) => s.activeId);
    const setActive = useStudioProjectStore((s) => s.setActive);
    const createFile = useStudioProjectStore((s) => s.createFile);
    const rename = useStudioProjectStore((s) => s.rename);
    const deleteFile = useStudioProjectStore((s) => s.deleteFile);
    const duplicate = useStudioProjectStore((s) => s.duplicate);
    const saveAll = useStudioProjectStore((s) => s.saveAll);
    const moveFile = useStudioProjectStore((s) => s.moveFile);
    const [editing, setEditing] = useState(null);
    const [editVal, setEditVal] = useState('');
    const [moving, setMoving] = useState(null);
    const [moveVal, setMoveVal] = useState('');

    const folders = useMemo(() => {
        const set = new Set(['/']);
        files.forEach((f) => set.add(folderOf(f.path)));
        return [...set].sort();
    }, [files]);

    const grouped = useMemo(() => {
        const map = new Map();
        [...files].sort((a, b) => a.path.localeCompare(b.path)).forEach((f) => {
            const folder = folderOf(f.path);
            if (!map.has(folder)) map.set(folder, []);
            map.get(folder).push(f);
        });
        return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
    }, [files]);

    const commitMove = (id) => {
        const dest = normalizeFolder(moveVal);
        moveFile(id, dest);
        setMoving(null);
    };

    const renderFile = (f) => {
        const Icon = iconFor(f.name);
        const isActive = f.id === activeId;
        return (
            <div key={f.id} role="treeitem" aria-selected={isActive} tabIndex={0}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') setActive(f.id);
                    if (e.key === 'Delete') { e.preventDefault(); if (confirm(`Delete ${f.name}?`)) deleteFile(f.id); }
                    if (e.key === 'F2') { setEditing(f.id); setEditVal(f.name); }
                    if (e.key.toLowerCase() === 'm') { setMoving(f.id); setMoveVal(folderOf(f.path)); }
                }}
                onClick={() => setActive(f.id)}
                className={`group flex items-center justify-between px-2 py-1.5 rounded text-xs font-mono cursor-pointer ${isActive ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'text-[#8b95a7] hover:bg-white/5 hover:text-white'}`}>
                <div className="flex items-center gap-2 truncate">
                    <Icon size={12} />
                    {editing === f.id ? (
                        <input autoFocus value={editVal} onChange={(e) => setEditVal(e.target.value)} onBlur={() => { if (editVal && editVal !== f.name) rename(f.id, editVal); setEditing(null); }} onKeyDown={(e) => { if (e.key === 'Enter') { rename(f.id, editVal); setEditing(null); } if (e.key === 'Escape') setEditing(null); }} className="bg-black/50 border border-amber-500/30 rounded px-1 py-0 text-xs w-24" />
                    ) : (
                        <span className="truncate" title={f.path}>{f.name}{f.dirty ? ' •' : ''}</span>
                    )}
                </div>
                <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 hover:opacity-100">
                    <button aria-label={`Move ${f.name} to folder`} onClick={(e) => { e.stopPropagation(); setMoving(f.id); setMoveVal(folderOf(f.path)); }} className="p-1 hover:bg-white/10 rounded"><FolderInput size={10} /></button>
                    <button aria-label={`Rename ${f.name}`} onClick={(e) => { e.stopPropagation(); setEditing(f.id); setEditVal(f.name); }} className="p-1 hover:bg-white/10 rounded"><Edit3 size={10} /></button>
                    <button aria-label={`Duplicate ${f.name}`} onClick={(e) => { e.stopPropagation(); duplicate(f.id); }} className="p-1 hover:bg-white/10 rounded"><Copy size={10} /></button>
                    <button aria-label={`Delete ${f.name}`} onClick={(e) => { e.stopPropagation(); if (confirm(`Delete ${f.name}? Guarded delete — this cannot be undone.`)) deleteFile(f.id); }} className="p-1 hover:bg-white/10 rounded text-red-400"><Trash2 size={10} /></button>
                </div>
            </div>
        );
    };

    return (
        <div className="w-[200px] border-r border-white/5 bg-[#08080a] flex flex-col">
            <div className="h-9 px-3 border-b border-white/5 flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold tracking-widest text-white">PROJECT</span>
                <div className="flex gap-1">
                    <button aria-label="New file" onClick={() => createFile(`strategy_${Date.now() % 1000}.py`)} className="p-1 hover:bg-white/10 rounded text-[#64748b] hover:text-white"><Plus size={12} /></button>
                    <button aria-label="Save all" onClick={saveAll} className="p-1 hover:bg-white/10 rounded text-[#64748b] hover:text-white"><Save size={12} /></button>
                </div>
            </div>
            <div role="tree" aria-label="Project files" className="flex-1 overflow-auto p-2 space-y-2">
                {grouped.map(([folder, folderFiles]) => (
                    <div key={folder}>
                        <div className="px-2 pb-1 text-[9px] font-mono tracking-widest text-[#64748b] truncate" title={folder}>
                            {folder === '/' ? 'ROOT' : folder}
                        </div>
                        <div className="space-y-1">
                            {folderFiles.map(renderFile)}
                        </div>
                    </div>
                ))}
                {moving && (
                    <div className="rounded border border-amber-500/30 bg-black/60 p-2 space-y-2">
                        <div className="text-[9px] font-mono font-bold tracking-widest text-amber-400">MOVE TO FOLDER</div>
                        <input autoFocus aria-label="Destination folder" value={moveVal} onChange={(e) => setMoveVal(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') commitMove(moving); if (e.key === 'Escape') setMoving(null); }} placeholder="/research" list="studio-folders" className="w-full bg-black/50 border border-amber-500/30 rounded px-2 py-1 text-xs font-mono text-white" />
                        <datalist id="studio-folders">
                            {folders.map((f) => <option key={f} value={f} />)}
                        </datalist>
                        <div className="flex gap-2">
                            <button onClick={() => commitMove(moving)} className="flex-1 rounded bg-amber-500 text-black text-[10px] font-mono font-bold py-1">Move</button>
                            <button onClick={() => setMoving(null)} className="flex-1 rounded bg-white/5 text-white text-[10px] font-mono py-1">Cancel</button>
                        </div>
                    </div>
                )}
            </div>
            <div className="p-2 border-t border-white/5 text-[9px] font-mono text-[#64748b]">Enter: open • F2: rename • M: move • Del: delete (guarded)</div>
        </div>
    );
}
