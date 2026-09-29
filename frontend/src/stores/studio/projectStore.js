"use client";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

const STORE_KEY = 'quant360-studio-project';
const BACKUP_KEY = 'quant360-studio-project-backup';
// Server synchronization is OPEN: no backend project API exists, so persistence
// is local-only. When a server project API lands, sync should compare
// lastSavedAt/autoSavedAt against the server updated_at and keep the newer
// version, preserving the backup key below. See docs/evidence/studio/P5-polish/execution.md.

const initial = () => ({
    files: [
        { id: '1', name: 'strategy.py', path: '/strategy.py', dirty: false, content: '', draft: '' },
        { id: '2', name: 'config.json', path: '/config.json', dirty: false, content: '{}', draft: '{}' },
    ],
    activeId: '1',
    tabs: ['1'],
    // Conflict-safe version markers (ISO timestamps). lastSavedAt tracks explicit
    // saves, autoSavedAt tracks autosave commits. On load the newer of the
    // primary/backup payloads wins; the loser is retained under BACKUP_KEY.
    lastSavedAt: null,
    autoSavedAt: null,
});

const basenameOf = (path) => (path || '').split('/').filter(Boolean).pop() || 'untitled.py';
export const folderOf = (path) => {
    const parts = (path || '').split('/').filter(Boolean);
    if (parts.length <= 1) return '/';
    return `/${parts.slice(0, -1).join('/')}`;
};
export const normalizeFolder = (folder) => {
    const cleaned = `/${(folder || '').split('/').filter(Boolean).join('/')}`;
    return cleaned === '/' ? '/' : cleaned;
};

const pickNewer = (a, b) => {
    const stampOf = (s) => {
        try {
            const parsed = JSON.parse(s || 'null');
            const state = parsed?.state || parsed;
            return state?.lastSavedAt || state?.autoSavedAt || null;
        } catch {
            return null;
        }
    };
    const ta = stampOf(a);
    const tb = stampOf(b);
    if (ta && tb) return tb > ta ? 'second' : 'first';
    if (tb && !ta) return 'second';
    return 'first';
};

// Local-only storage wrapper: mirrors every write to a backup key and, on
// read, merges primary/backup by newer timestamp (lastSavedAt/autoSavedAt).
const versionedStorage = {
    getItem: (key) => {
        if (typeof localStorage === 'undefined') return null;
        const primary = localStorage.getItem(key);
        const backup = localStorage.getItem(BACKUP_KEY);
        if (!primary) return backup;
        if (!backup || key !== STORE_KEY) return primary;
        return pickNewer(primary, backup) === 'second' ? backup : primary;
    },
    setItem: (key, value) => {
        if (typeof localStorage === 'undefined') return;
        try {
            const previous = localStorage.getItem(key);
            if (previous && key === STORE_KEY) localStorage.setItem(BACKUP_KEY, previous);
        } catch {
            // Backup is best-effort; the primary write below still applies.
        }
        localStorage.setItem(key, value);
    },
    removeItem: (key) => {
        if (typeof localStorage === 'undefined') return;
        localStorage.removeItem(key);
    },
};

const stamp = () => new Date().toISOString();

export const useStudioProjectStore = create(persist((set) => ({
    ...initial(),
    setActive: (id) => set((s) => ({ activeId: id, tabs: s.tabs.includes(id) ? s.tabs : [...s.tabs, id] })),
    closeTab: (id) => set((s) => {
        const tabs = s.tabs.filter((t) => t !== id);
        const activeId = s.activeId === id ? (tabs[0] || null) : s.activeId;
        return { tabs, activeId };
    }),
    markDirty: (id, dirty = true) => set((s) => ({ files: s.files.map((f) => f.id === id ? { ...f, dirty } : f) })),
    updateDraft: (id, draft) => set((s) => ({
        files: s.files.map((f) => f.id === id ? { ...f, draft, dirty: draft !== f.content } : f),
    })),
    saveFile: (id) => set((s) => ({
        files: s.files.map((f) => f.id === id ? { ...f, content: f.draft ?? f.content, dirty: false } : f),
        lastSavedAt: stamp(),
    })),
    // Autosave commit: same local effect as saveFile but stamped as an
    // automatic save so explicit saves and autosaves can be ordered on load.
    // Conflict-safe in the local sense only (newer timestamp wins on rehydrate).
    autosaveFile: (id) => set((s) => {
        const target = s.files.find((f) => f.id === id);
        if (!target || target.draft === target.content) return s;
        return {
            files: s.files.map((f) => f.id === id ? { ...f, content: f.draft ?? f.content, dirty: false } : f),
            autoSavedAt: stamp(),
        };
    }),
    rename: (id, name) => set((s) => {
        const files = s.files.map((f) => {
            if (f.id !== id) return f;
            const clean = (name || '').trim() || f.name;
            const folder = folderOf(f.path);
            const base = basenameOf(clean);
            const path = folder === '/' ? `/${base}` : `${folder}/${base}`;
            return { ...f, name: base, path };
        });
        return { files };
    }),
    // Folder-aware move: relocate a file under a folder/prefix path while
    // keeping its basename. `folder` accepts "research", "/research", or "/".
    moveFile: (id, folder) => set((s) => {
        const target = s.files.find((f) => f.id === id);
        if (!target) return s;
        const dest = normalizeFolder(folder);
        const base = basenameOf(target.path);
        const nextPath = dest === '/' ? `/${base}` : `${dest}/${base}`;
        if (nextPath === target.path) return s;
        if (s.files.some((f) => f.id !== id && f.path === nextPath)) return s; // no clobber
        return { files: s.files.map((f) => f.id === id ? { ...f, path: nextPath } : f) };
    }),
    createFile: (name, folder = '/') => set((s) => {
        const id = Date.now().toString();
        const content = '# New strategy\nclass Strategy:\n    def generate_signals(self, data):\n        return []\nstrategy = Strategy()\n';
        const dest = normalizeFolder(folder);
        const base = (name || '').trim() || `strategy_${Date.now() % 1000}.py`;
        const path = dest === '/' ? `/${base}` : `${dest}/${base}`;
        const file = { id, name: base, path, dirty: false, content, draft: content };
        return { files: [...s.files, file], tabs: [...s.tabs, id], activeId: id };
    }),
    deleteFile: (id) => set((s) => {
        if (s.files.length <= 1) return s;
        const files = s.files.filter((f) => f.id !== id);
        const tabs = s.tabs.filter((t) => t !== id);
        const activeId = s.activeId === id ? tabs[0] || files[0]?.id : s.activeId;
        return { files, tabs, activeId };
    }),
    duplicate: (id) => set((s) => {
        const orig = s.files.find((f) => f.id === id);
        if (!orig) return s;
        const nid = Date.now().toString();
        const base = basenameOf(orig.path).replace('.', '_copy.');
        const dup = { ...orig, id: nid, name: base, path: `${folderOf(orig.path) === '/' ? '' : folderOf(orig.path)}/${base}`.replace('//', '/'), dirty: false };
        return { files: [...s.files, dup], tabs: [...s.tabs, nid], activeId: nid };
    }),
    saveAll: () => set((s) => ({ files: s.files.map((f) => ({ ...f, content: f.draft ?? f.content, dirty: false })), lastSavedAt: stamp() })),
    reset: () => set(initial()),
}), {
    name: STORE_KEY,
    version: 3,
    storage: createJSONStorage(() => versionedStorage),
    partialize: (state) => ({ files: state.files, activeId: state.activeId, tabs: state.tabs, lastSavedAt: state.lastSavedAt, autoSavedAt: state.autoSavedAt }),
    migrate: (persisted) => ({
        ...persisted,
        files: (persisted?.files || initial().files).map((file) => ({
            ...file,
            draft: file.draft ?? file.content ?? '',
            path: file.path || `/${file.name || 'untitled.py'}`,
            name: file.name || basenameOf(file.path || 'untitled.py'),
        })),
        lastSavedAt: persisted?.lastSavedAt || null,
        autoSavedAt: persisted?.autoSavedAt || null,
    }),
}));
