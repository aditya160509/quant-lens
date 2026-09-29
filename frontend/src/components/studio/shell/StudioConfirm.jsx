"use client";

import React, { useEffect, useRef } from 'react';

// P15: standardized destructive confirmation. Wraps window.confirm behind an
// accessible modal so destructive Studio actions (delete version, kill
// deployment, discard draft) share one keyboard-safe pattern. Falls back to
// native confirm() only when `forceNative` is set (tests/headless).
export default function StudioConfirm({
    open,
    title,
    body,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    onConfirm,
    onCancel,
    forceNative = false,
}) {
    const dialogRef = useRef(null);
    const confirmRef = useRef(null);
    const openerRef = useRef(null);

    useEffect(() => {
        if (!open || forceNative || typeof document === 'undefined') return undefined;
        openerRef.current = document.activeElement;
        const timer = setTimeout(() => confirmRef.current?.focus?.({ preventScroll: true }), 0);
        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                event.stopPropagation();
                onCancel?.();
            }
        };
        document.addEventListener('keydown', onKeyDown, true);
        return () => {
            clearTimeout(timer);
            document.removeEventListener('keydown', onKeyDown, true);
            openerRef.current?.focus?.({ preventScroll: true });
            openerRef.current = null;
        };
    }, [open, forceNative, onCancel]);

    useEffect(() => {
        if (open && forceNative) {
            const accepted = window.confirm(`${title}\n\n${body || ''}`);
            if (accepted) onConfirm?.();
            else onCancel?.();
        }
    }, [open, forceNative, title, body, onConfirm, onCancel]);

    if (!open || forceNative) return null;

    return (
        <div className="fixed inset-0 z-[400] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={onCancel} aria-hidden="true" />
            <div
                ref={dialogRef}
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="studio-confirm-title"
                aria-describedby="studio-confirm-body"
                className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#0a0a0f] p-6 shadow-2xl"
            >
                <h3 id="studio-confirm-title" className="text-[12px] font-bold uppercase tracking-widest text-white">
                    {title}
                </h3>
                {body ? (
                    <p id="studio-confirm-body" className="mt-2 text-[11px] leading-relaxed text-slate-400">
                        {body}
                    </p>
                ) : null}
                <div className="mt-5 flex gap-3">
                    <button
                        type="button"
                        onClick={onCancel}
                        aria-label={`${cancelLabel} — keep current state`}
                        className="flex-1 rounded-lg bg-white/5 py-2.5 text-[11px] font-bold uppercase tracking-widest text-white hover:bg-white/10"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        ref={confirmRef}
                        type="button"
                        onClick={onConfirm}
                        aria-label={`${confirmLabel} — this action cannot be undone`}
                        className="flex-1 rounded-lg bg-red-500 py-2.5 text-[11px] font-bold uppercase tracking-widest text-white hover:bg-red-400"
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
