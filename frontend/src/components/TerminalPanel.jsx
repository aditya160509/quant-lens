import React from 'react';

export default function TerminalPanel({ title, subtitle, controls, children, className = "", variant = "default", accentColor = "yellow" }) {
    const accentColors = {
        yellow: { glow: 'var(--shadow-glow-yellow)', solid: 'var(--terminal-yellow)', bg: 'color-mix(in srgb, var(--terminal-yellow), transparent 92%)' },
        green: { glow: 'var(--shadow-glow-green)', solid: 'var(--terminal-green)', bg: 'color-mix(in srgb, var(--terminal-green), transparent 92%)' },
        blue: { glow: 'var(--shadow-glow-blue)', solid: 'var(--terminal-blue)', bg: 'color-mix(in srgb, var(--terminal-blue), transparent 92%)' },
        red: { glow: 'color-mix(in srgb, var(--terminal-red), transparent 60%)', solid: 'var(--terminal-red)', bg: 'color-mix(in srgb, var(--terminal-red), transparent 92%)' },
        orange: { glow: 'color-mix(in srgb, var(--terminal-orange), transparent 60%)', solid: 'var(--terminal-orange)', bg: 'color-mix(in srgb, var(--terminal-orange), transparent 92%)' },
    };

    const accent = accentColors[accentColor] || accentColors.yellow;

    return (
        <div className={`flex flex-col h-full ${className}`} style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            boxShadow: 'var(--shadow-panel)',
            backdropFilter: 'blur(8px)',
            position: 'relative',
            overflow: 'hidden',
        }}>
            <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '1px',
                background: `linear-gradient(90deg, transparent 0%, ${accent.solid}4d 50%, transparent 100%)`,
            }} />
            
            <div className="shrink-0" style={{
                background: 'var(--terminal-darker)',
                borderBottom: '1px solid var(--border)',
                padding: '4px 10px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                position: 'relative',
            }}>
                <div style={{
                    position: 'absolute',
                    left: 0,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: '3px',
                    height: '16px',
                    background: accent.solid,
                    borderRadius: '0 2px 2px 0',
                    boxShadow: `0 0 8px ${accent.glow}`,
                }} />
                
                <div className="flex flex-col">
                    <div style={{
                         color: accent.solid,
                        fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                        fontSize: '11px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.12em',
                        fontWeight: 600,
                        textShadow: `0 0 10px ${accent.glow}`,
                        paddingLeft: '8px',
                    }}>
                        {title}
                    </div>
                    {subtitle && (
                        <div style={{
                            fontSize: '10px',
                            color: 'var(--terminal-dim)',
                            fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
                            marginTop: '2px',
                            paddingLeft: '8px',
                            letterSpacing: '0.02em',
                        }}>
                            {subtitle}
                        </div>
                    )}
                </div>

                {controls && (
                    <div className="flex items-center gap-2">
                        {controls}
                    </div>
                )}
            </div>

            <div className="flex-1 min-h-0 relative overflow-hidden">
                {children}
            </div>
        </div>
    );
}