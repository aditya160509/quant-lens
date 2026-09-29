import React from 'react';
import Link from 'next/link';

export function Navbar() {
    return (
        <nav className="flex items-center justify-between px-4 py-2 bg-sidebar border-b border-sidebar-border text-sidebar-foreground">
            <div className="flex items-center space-x-4">
                <div className="text-xl font-bold text-primary tracking-tighter">QUANT360</div>
                <div className="hidden md:flex space-x-1">
                    <NavLink href="/">MONITOR</NavLink>
                    <NavLink href="/market">MARKETS</NavLink>
                    <NavLink href="/stock">SECURITY</NavLink>
                    <NavLink href="/macro">MACRO</NavLink>
                    <NavLink href="/labs/factors">FACTORS</NavLink>
                    <NavLink href="/labs/volatility">VOLATILITY</NavLink>
                    <NavLink href="/labs/regimes">REGIMES</NavLink>
                    <NavLink href="/labs/pca">PCA</NavLink>
                    <NavLink href="/labs/scenarios">SCENARIOS</NavLink>
                    <NavLink href="/labs/backtest">BACKTEST</NavLink>
                    <NavLink href="/portfolio">OPTIMIZER</NavLink>
                    <NavLink href="/portfolio/compare">COMPARE</NavLink>
                </div>
            </div>
            <div className="text-xs font-mono text-muted-foreground">
                {new Date().toLocaleTimeString()}
            </div>
        </nav>
    );
}

function NavLink({ href, children }) {
    return (
        <Link
            href={href}
            className="px-3 py-1 text-xs font-bold hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors uppercase"
        >
            {children}
        </Link>
    );
}
