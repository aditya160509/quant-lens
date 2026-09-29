'use client';

/**
 * Theme Toggle Component
 * 
 * A sleek toggle button for switching between dark and light modes.
 * Uses sun/moon icons with smooth transitions.
 */

import React from 'react';
import { useTheme } from '@/context/ThemeContext';
import { Sun, Moon, Monitor } from 'lucide-react';

interface ThemeToggleProps {
    className?: string;
}

export default function ThemeToggle({ className = '' }: ThemeToggleProps) {
    const { theme, toggleTheme } = useTheme();

    return (
        <button
            onClick={toggleTheme}
            className={`
                relative p-2 rounded-lg transition-all duration-200
                hover:bg-[var(--accent)] 
                focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:ring-offset-2 focus:ring-offset-[var(--background)]
                ${className}
            `}
            title={`Switch Theme (Current: ${theme})`}
            aria-label={`Switch Theme (Current: ${theme})`}
        >
            <div className="relative w-5 h-5 flex items-center justify-center">
                {/* Sun icon - Light Mode */}
                <Sun 
                    size={20} 
                    className={`
                        absolute inset-0 transition-all duration-300 
                        ${theme === 'light' 
                            ? 'opacity-100 rotate-0 scale-100 text-[var(--terminal-blue)]' 
                            : 'opacity-0 rotate-90 scale-0'
                        }
                    `}
                />
                {/* Moon icon - Dark Mode */}
                <Moon 
                    size={20} 
                    className={`
                        absolute inset-0 transition-all duration-300
                        ${theme === 'dark' 
                            ? 'opacity-100 rotate-0 scale-100 text-[var(--terminal-yellow)]' 
                            : 'opacity-0 -rotate-90 scale-0'
                        }
                    `}
                />
                {/* Monitor icon - Classic Mode */}
                <Monitor 
                    size={20} 
                    className={`
                        absolute inset-0 transition-all duration-300
                        ${theme === 'classic' 
                            ? 'opacity-100 rotate-0 scale-100 text-[var(--terminal-yellow)]' 
                            : 'opacity-0 -rotate-90 scale-0'
                        }
                    `}
                />
            </div>
        </button>
    );
}
