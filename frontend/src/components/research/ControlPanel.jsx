"use client";

import React from 'react';
import { researchTokens } from '@/lib/theme/researchTokens';

/**
 * ControlPanel - Wrapper component for research control panels.
 * Fixed width 240px, premium style.
 */
export default function ControlPanel({
    children,
    title = '',
    onApply,
    applyLabel = 'Apply',
    loading = false,
    collapsed = false,
    onToggleCollapse
}) {
    return (
        <div className={`control-panel ${collapsed ? 'collapsed' : ''}`}>
            <style jsx>{`
                .control-panel {
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    padding: 16px;
                    width: 240px;
                    min-width: 240px; 
                    max-width: 240px;
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    border-radius: ${researchTokens.radius.panel}px;
                }
                .control-panel.collapsed {
                    width: 48px;
                    min-width: 48px;
                    padding: 12px 8px;
                }
                .panel-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: ${collapsed ? '0' : '20px'};
                }
                .panel-title {
                    font-size: 13px;
                    font-weight: 700;
                    color: ${researchTokens.colors.warn};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    display: ${collapsed ? 'none' : 'block'};
                }
                .collapse-btn {
                    background: none;
                    border: none;
                    color: ${researchTokens.colors.muted};
                    cursor: pointer;
                    font-size: 14px;
                    padding: 0;
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 4px;
                    transition: all 0.2s;
                }
                .collapse-btn:hover {
                    background: ${researchTokens.colors.surface2};
                    color: ${researchTokens.colors.text};
                }
                .panel-content {
                    display: ${collapsed ? 'none' : 'flex'};
                    flex-direction: column;
                    gap: 20px;
                    flex-grow: 1;
                    overflow-y: auto;
                    padding-right: 2px; /* For scrollbar space */
                }
                /* Scrollbar */
                .panel-content::-webkit-scrollbar { width: 4px; }
                .panel-content::-webkit-scrollbar-track { background: transparent; }
                .panel-content::-webkit-scrollbar-thumb { background: ${researchTokens.colors.border2}; border-radius: 2px; }

                .panel-footer {
                    margin-top: 16px;
                    padding-top: 16px;
                    border-top: 1px solid ${researchTokens.colors.border2};
                    display: ${collapsed ? 'none' : 'block'};
                }
                .apply-btn {
                    width: 100%;
                    background: ${researchTokens.colors.warn};
                    color: ${researchTokens.colors.bg};
                    border: none;
                    padding: 10px 16px;
                    font-size: 13px;
                    font-weight: 700;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    text-transform: uppercase;
                    border-radius: 4px;
                    box-shadow: 0 4px 12px rgba(251, 191, 36, 0.2);
                }
                .apply-btn:hover:not(:disabled) {
                    background: #e5b830;
                    transform: translateY(-1px);
                    box-shadow: 0 6px 16px rgba(251, 191, 36, 0.3);
                }
                .apply-btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                    box-shadow: none;
                    transform: none;
                    filter: saturate(0);
                }
                .spinner {
                    width: 14px;
                    height: 14px;
                    border: 2px solid rgba(0, 0, 0, 0.2);
                    border-top-color: black;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>

            <div className="panel-header">
                <span className="panel-title">{title}</span>
                {onToggleCollapse && (
                    <button className="collapse-btn" onClick={onToggleCollapse}>
                        {collapsed ? '▶' : '◀'}
                    </button>
                )}
            </div>

            <div className="panel-content">
                {children}
            </div>

            {onApply && (
                <div className="panel-footer">
                    <button
                        className="apply-btn"
                        onClick={onApply}
                        disabled={loading}
                    >
                        {loading ? <div className="spinner" /> : null}
                        {applyLabel}
                    </button>
                </div>
            )}
        </div>
    );
}

/**
 * ControlGroup - Group of controls with label.
 */
export function ControlGroup({ label, children }) {
    return (
        <div className="control-group">
            <style jsx>{`
                .control-group {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .group-label {
                    font-size: 10px;
                    color: ${researchTokens.colors.muted};
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    font-weight: 600;
                    font-family: var(--font-mono);
                }
            `}</style>
            <div className="group-label">{label}</div>
            {children}
        </div>
    );
}

/**
 * ControlSelect - Styled select dropdown.
 */
export function ControlSelect({ value, onChange, options = [], multiple = false, size = 1 }) {
    return (
        <>
            <style jsx>{`
            .control-select {
                background: ${researchTokens.colors.surface2};
                border: 1px solid ${researchTokens.colors.border};
                padding: 8px 10px;
                color: ${researchTokens.colors.text};
                font-size: 12px;
                font-family: var(--font-mono);
                width: 100%;
                cursor: pointer;
                outline: none;
                border-radius: 4px;
                transition: border-color 0.2s;
            }
            .control-select:focus {
                border-color: ${researchTokens.colors.warn};
            }
            /* Custom styling for options is limited in native select */
        `}</style>
            <select
                className="control-select"
                value={value}
                onChange={(e) => {
                    if (multiple) {
                        const selected = Array.from(e.target.selectedOptions, opt => opt.value);
                        onChange(selected);
                    } else {
                        onChange(e.target.value);
                    }
                }}
                multiple={multiple}
                size={multiple ? Math.min(size, options.length) : 1}
            >
                {options.map(opt => (
                    <option key={opt.value ?? opt} value={opt.value ?? opt}>
                        {opt.label ?? opt}
                    </option>
                ))}
            </select>
        </>
    );
}

/**
 * ControlSlider - Styled range slider.
 */
export function ControlSlider({ value, onChange, min = 0, max = 1, step = 0.1, label }) {
    return (
        <div className="control-slider">
            <style jsx>{`
                .control-slider {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .slider-header {
                    display: flex;
                    justify-content: space-between;
                    font-size: 10px;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                }
                .slider-value {
                    font-weight: 600;
                    color: ${researchTokens.colors.warn};
                }
                input[type="range"] {
                    width: 100%;
                    height: 2px;
                    background: ${researchTokens.colors.border2};
                    appearance: none;
                    outline: none;
                    border-radius: 2px;
                }
                input[type="range"]::-webkit-slider-thumb {
                    appearance: none;
                    width: 12px;
                    height: 12px;
                    background: ${researchTokens.colors.warn};
                    border-radius: 50%;
                    cursor: pointer;
                    transition: transform 0.1s;
                }
                input[type="range"]::-webkit-slider-thumb:hover {
                    transform: scale(1.2);
                }
            `}</style>
            <div className="slider-header">
                <span>{label}</span>
                <span className="slider-value">{value.toFixed(2)}</span>
            </div>
            <input
                type="range"
                value={value}
                onChange={(e) => onChange(parseFloat(e.target.value))}
                min={min}
                max={max}
                step={step}
            />
        </div>
    );
}

