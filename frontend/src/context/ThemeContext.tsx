'use client';

/**
 * Theme Provider - Manages dark/light mode with localStorage persistence
 * 
 * Best Practices (from research):
 * - Dark mode: #0a0e17 (Material Design inspired, better than pure black #000000)
 * - Light mode: #f8fafc (softer than pure white #FFFFFF, easier on eyes)
 * - Pure black causes eye strain and makes shadows invisible
 * - #121212 is the Material Design recommendation
 */

import React, { createContext, useContext, useLayoutEffect, useRef, useCallback, useSyncExternalStore } from 'react';

type Theme = 'dark' | 'light' | 'classic';

interface ThemeContextType {
    theme: Theme;
    toggleTheme: () => void;
    setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

// Store for theme to avoid hydration mismatch
let themeStore: Theme = 'dark';
const listeners = new Set<() => void>();

function getThemeSnapshot(): Theme {
    return themeStore;
}

function getServerSnapshot(): Theme {
    return 'dark'; // Server always returns dark to avoid hydration mismatch
}

function subscribeToTheme(callback: () => void) {
    listeners.add(callback);
    return () => listeners.delete(callback);
}

function emitThemeChange(newTheme: Theme) {
    themeStore = newTheme;
    listeners.forEach(listener => listener());
}

// Apply theme to DOM
function applyThemeToDOM(theme: Theme) {
    if (typeof window === 'undefined') return;
    
    const root = document.documentElement;
    // Remove all possible theme classes first
    root.classList.remove('light', 'dark', 'classic');
    
    if (theme === 'light') {
        root.setAttribute('data-theme', 'light');
        root.classList.add('light');
    } else if (theme === 'classic') {
        root.setAttribute('data-theme', 'classic');
        root.classList.add('classic');
    } else {
        root.removeAttribute('data-theme');
        root.classList.add('dark');
    }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    // Use useSyncExternalStore for SSR-safe theme
    const theme = useSyncExternalStore(subscribeToTheme, getThemeSnapshot, getServerSnapshot);
    const skipInitialThemeEffect = useRef(true);

    // Initialize theme from localStorage on client
    useLayoutEffect(() => {
        const stored = localStorage.getItem('quant360-theme');
        let initialTheme: Theme = 'dark';
        
        if (stored === 'dark' || stored === 'light' || stored === 'classic') {
            initialTheme = stored as Theme;
        } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
            initialTheme = 'light';
        }
        
        emitThemeChange(initialTheme);
        applyThemeToDOM(initialTheme);
        localStorage.setItem('quant360-theme', initialTheme);
    }, []);

    // Apply theme changes
    useLayoutEffect(() => {
        if (skipInitialThemeEffect.current) {
            skipInitialThemeEffect.current = false;
            return;
        }
        applyThemeToDOM(theme);
        localStorage.setItem('quant360-theme', theme);
    }, [theme]);

    const toggleTheme = useCallback(() => {
        const themes: Theme[] = ['dark', 'light', 'classic'];
        const currentIndex = themes.indexOf(themeStore);
        const nextIndex = (currentIndex + 1) % themes.length;
        emitThemeChange(themes[nextIndex]);
    }, []);

    const setTheme = useCallback((newTheme: Theme) => {
        emitThemeChange(newTheme);
    }, []);

    // Always provide context, even before mounted (use default values)
    return (
        <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
}
