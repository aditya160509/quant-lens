"use client";

import { useCallback, useEffect, useRef } from 'react';

// P15: shared keyboard + focus behavior for Studio shell modals.
// - Restores focus to the element that opened the modal.
// - Closes on Escape.
// - Moves initial focus into the dialog (first focusable or dialog root).
export function useStudioModalA11y({ isOpen, onClose, dialogRef, initialFocusRef }) {
    const openerRef = useRef(null);

    useEffect(() => {
        if (!isOpen) return undefined;
        if (typeof document !== 'undefined') {
            openerRef.current = document.activeElement;
            const target = initialFocusRef?.current || dialogRef?.current;
            const timer = setTimeout(() => {
                if (!target) return;
                const focusable = target.querySelector?.(
                    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
                );
                (focusable || target)?.focus?.({ preventScroll: true });
            }, 0);
            const onKeyDown = (event) => {
                if (event.key === 'Escape') {
                    event.stopPropagation();
                    onClose?.();
                }
            };
            document.addEventListener('keydown', onKeyDown, true);
            return () => {
                clearTimeout(timer);
                document.removeEventListener('keydown', onKeyDown, true);
                openerRef.current?.focus?.({ preventScroll: true });
                openerRef.current = null;
            };
        }
        return undefined;
    }, [isOpen, onClose, dialogRef, initialFocusRef]);

    // Light focus trap: keep Tab cycling inside the dialog.
    const onKeyDownTrap = useCallback((event) => {
        if (event.key !== 'Tab' || !dialogRef?.current) return;
        const nodes = Array.from(dialogRef.current.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )).filter((node) => node.offsetParent !== null);
        if (nodes.length === 0) return;
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }, [dialogRef]);

    return { onKeyDownTrap };
}
