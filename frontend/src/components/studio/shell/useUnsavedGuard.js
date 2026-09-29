"use client";

import { useEffect } from 'react';

// P15: unsaved-work guard. Registers beforeunload while `dirty` is true so
// navigation away from Composer/Develop prompts before discarding edits.
export function useUnsavedGuard(dirty, message = 'You have unsaved Studio changes. Leave without saving?') {
    useEffect(() => {
        if (!dirty || typeof window === 'undefined') return undefined;
        const onBeforeUnload = (event) => {
            event.preventDefault();
            event.returnValue = message;
            return message;
        };
        window.addEventListener('beforeunload', onBeforeUnload);
        return () => window.removeEventListener('beforeunload', onBeforeUnload);
    }, [dirty, message]);
}
