// P15: frontend env-flag map mirroring backend/feature_flags.py.
// Renderer/worker/GPU-adjacent paths stay on the safe default unless the
// matching NEXT_PUBLIC_STUDIO_* variable is set to "1".
const FLAGS = {
    STUDIO_RENDERER_WEBGL: 'NEXT_PUBLIC_STUDIO_RENDERER_WEBGL',
    STUDIO_WORKER_EXTERNAL: 'NEXT_PUBLIC_STUDIO_WORKER_EXTERNAL',
    STUDIO_GPU_ENABLED: 'NEXT_PUBLIC_STUDIO_GPU_ENABLED',
    STUDIO_PARQUET_FAST_SCAN: 'NEXT_PUBLIC_STUDIO_PARQUET_FAST_SCAN',
};

function readFlag(envName) {
    const raw = typeof process !== 'undefined' ? process.env?.[envName] : undefined;
    return ['1', 'true', 'yes', 'on'].includes(String(raw || '').trim().toLowerCase());
}

export function studioFlagEnabled(name) {
    const envName = FLAGS[name];
    if (!envName) return false;
    return readFlag(envName);
}

export function studioFlagSnapshot() {
    return Object.fromEntries(Object.keys(FLAGS).map((name) => [name, studioFlagEnabled(name)]));
}

export const STUDIO_FLAGS = Object.freeze({ ...FLAGS });
