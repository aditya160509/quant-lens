"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

import ThemeToggle from './ui/ThemeToggle';
import { MODULES } from '@/workspace/modules';

// Register GSAP plugins
if (typeof window !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);
}

export default function GlobalLayout({ children }) {
    const pathname = usePathname();
    const [time, setTime] = useState("");

    useEffect(() => {
        const timer = setInterval(() => {
            setTime(new Date().toLocaleTimeString());
        }, 1000);

        return () => {
            clearInterval(timer);
        };
    }, []);

    const navItems = [
        { name: "Home", path: "/" },
        { name: "Trade", path: "/trade" },
        { name: "Screener", path: "/screener" },
        { name: "Studio", path: "/studio" },
        { name: "ML", path: "/ml" },
        { name: "Research", path: "/research" },
    ];

    // Workspace modules render their own full-screen chrome and command palette
    const isWorkspace = ['/research', '/ml', '/screener', '/studio', '/share'].some((p) => pathname?.startsWith(p));

    return (
        <div className="min-h-screen flex flex-col bg-terminal-black text-terminal-text font-sans selection:bg-terminal-yellow selection:text-terminal-black">
            {/* Top Nav Bar - Hidden on Auth Pages only */}
            {!isWorkspace && (
                <header className={`h-12 border-b border-terminal-gray ${pathname === '/' ? 'bg-transparent absolute top-0 left-0 right-0 z-50' : 'bg-terminal-dark'} flex items-center gap-3 overflow-hidden md:overflow-visible px-3 sm:px-4 shrink-0`}>
                    <div className="flex min-w-0 flex-1 items-center gap-4 lg:gap-8">
                        <Link href="/" className="shrink-0 text-terminal-yellow font-bold tracking-[0.3em] text-lg hover:opacity-80 transition-opacity flex items-center gap-2">
                            ATLAS <span className="hidden lg:inline text-[10px] text-gray-500 font-mono font-medium opacity-70 tracking-normal">Research</span>
                        </Link>

                        <nav aria-label="Primary" className="flex min-w-0 flex-1 items-center gap-4 overflow-x-auto whitespace-nowrap md:overflow-visible lg:gap-6 [scrollbar-width:none]">
                            {navItems.map((item) => {
                                const isActive = pathname === item.path || (item.path !== "/" && pathname.startsWith(item.path));
                                const pages = MODULES.find((m) => m.href === item.path)?.pages;
                                const link = (
                                    <Link
                                        href={item.path}
                                        aria-haspopup={pages ? "menu" : undefined}
                                        className={`text-xs font-mono tracking-wide hover:text-terminal-yellow transition-colors ${isActive ? "text-terminal-yellow border-b-2 border-terminal-yellow py-3.5" : "text-terminal-dim"
                                            }`}
                                    >
                                        {item.name}{pages ? <span aria-hidden className="ml-1 opacity-50">▾</span> : null}
                                    </Link>
                                );
                                if (!pages) return <span key={item.name}>{link}</span>;
                                // Pages open on hover or keyboard focus, so a module is never a blind jump.
                                return (
                                    <div key={item.name} className="group relative">
                                        {link}
                                        <div role="menu" className="invisible absolute left-0 top-full z-50 min-w-[180px] rounded-lg border border-terminal-gray bg-terminal-dark p-1 opacity-0 shadow-xl transition-opacity group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
                                            {pages.map((p) => (
                                                <Link key={p.href} role="menuitem" href={p.href} className="block rounded-md px-3 py-1.5 text-xs text-terminal-dim hover:bg-white/5 hover:text-terminal-text focus:bg-white/5 focus:text-terminal-text focus:outline-none">{p.label}</Link>
                                            ))}
                                        </div>
                                    </div>
                                );
                            })}
                        </nav>
                    </div>

                    {/* Right side - Theme toggle, Terminal hint, time, and user menu */}
                    <div className="flex shrink-0 items-center gap-2 lg:gap-4">
                        <div className="hidden md:block"><ThemeToggle /></div>
                        <div className="hidden xl:block font-mono text-xs text-terminal-green">
                            {time}
                        </div>
                    </div>
                </header>
            )}

            {/* Main Content Area */}
            <main className={`flex-1 relative overflow-hidden ${pathname === '/' ? 'h-screen' : ''}`}>
                {children}
            </main>

            {/* Terminal Overlay - Global, triggered by ⌘K */}
        </div>
    );
}
