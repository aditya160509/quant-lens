"use client";

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { researchTokens } from '@/lib/theme/researchTokens';

/**
 * UniversePicker - Multi-select ticker component with search, paste, and validation.
 * Upgraded for Cluster D Premium Terminal.
 */
export default function UniversePicker({
    selected = [],
    onChange,
    universe = [],
    loading = false,
    maxDisplay = 60,
    placeholder = "Search tickers..."
}) {
    const [search, setSearch] = useState('');
    const [pasteMode, setPasteMode] = useState(false);
    const [pasteText, setPasteText] = useState('');
    const [invalidTickers, setInvalidTickers] = useState([]);

    // Filter universe based on search
    const filtered = useMemo(() => {
        if (!search) return universe.slice(0, maxDisplay);
        const lower = search.toLowerCase();
        return universe
            .filter(t => t.toLowerCase().includes(lower))
            .slice(0, maxDisplay);
    }, [universe, search, maxDisplay]);

    // Handle select all visible
    const handleSelectAll = useCallback(() => {
        const newSelected = new Set(selected);
        filtered.forEach(t => newSelected.add(t));
        onChange(Array.from(newSelected));
    }, [filtered, selected, onChange]);

    // Handle clear all
    const handleClearAll = useCallback(() => {
        onChange([]);
    }, [onChange]);

    // Handle toggle single ticker
    const handleToggle = useCallback((ticker) => {
        const newSelected = new Set(selected);
        if (newSelected.has(ticker)) {
            newSelected.delete(ticker);
        } else {
            newSelected.add(ticker);
        }
        onChange(Array.from(newSelected));
    }, [selected, onChange]);

    // Handle paste submit
    const handlePasteSubmit = useCallback(() => {
        const universeSet = new Set(universe);
        const pasted = pasteText
            .split(/[\s,;\n]+/)
            .map(t => t.trim().toUpperCase())
            .filter(t => t.length > 0);

        const valid = [];
        const invalid = [];

        pasted.forEach(t => {
            if (universeSet.has(t)) {
                valid.push(t);
            } else {
                invalid.push(t);
            }
        });

        setInvalidTickers(invalid);

        if (valid.length > 0) {
            const newSelected = new Set(selected);
            valid.forEach(t => newSelected.add(t));
            onChange(Array.from(newSelected));
        }

        if (invalid.length === 0) {
            setPasteMode(false);
            setPasteText('');
        }
    }, [pasteText, universe, selected, onChange]);

    return (
        <div className="universe-picker">
            <style jsx>{`
                .universe-picker {
                    background: transparent;
                    width: 100%;
                }
                .picker-header {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 8px;
                }
                .picker-search {
                    flex: 1;
                    background: ${researchTokens.colors.black};
                    border: 1px solid ${researchTokens.colors.border};
                    padding: 6px 10px;
                    color: ${researchTokens.colors.text};
                    font-size: 12px;
                    font-family: var(--font-mono);
                    border-radius: 4px;
                }
                .picker-search:focus {
                    outline: none;
                    border-color: ${researchTokens.colors.warn};
                }
                .picker-actions {
                    display: flex;
                    gap: 6px;
                    margin-bottom: 8px;
                    justify-content: flex-end;
                }
                .picker-btn {
                    background: ${researchTokens.colors.surface2};
                    border: 1px solid ${researchTokens.colors.border};
                    padding: 4px 8px;
                    color: ${researchTokens.colors.muted};
                    font-size: 10px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    transition: all 0.2s;
                    text-transform: uppercase;
                    border-radius: 3px;
                }
                .picker-btn:hover {
                    border-color: ${researchTokens.colors.warn};
                    color: ${researchTokens.colors.text};
                }
                .picker-list {
                    max-height: 180px;
                    overflow-y: auto;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4px;
                    padding-right: 4px;
                }
                /* Custom Scrollbar for list */
                .picker-list::-webkit-scrollbar {
                    width: 4px;
                }
                .picker-list::-webkit-scrollbar-track {
                    background: transparent;
                }
                .picker-list::-webkit-scrollbar-thumb {
                    background: ${researchTokens.colors.border2};
                }
                .picker-item {
                    background: ${researchTokens.colors.surface2};
                    border: 1px solid ${researchTokens.colors.border};
                    padding: 3px 8px;
                    font-size: 10px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    transition: all 0.1s;
                    color: ${researchTokens.colors.muted};
                    border-radius: 2px;
                }
                .picker-item:hover {
                    border-color: ${researchTokens.colors.warn};
                    color: ${researchTokens.colors.text};
                }
                .picker-item.selected {
                    background: rgba(251, 191, 36, 0.15);
                    border-color: ${researchTokens.colors.warn};
                    color: ${researchTokens.colors.warn};
                    font-weight: 600;
                }
                .picker-selected {
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid ${researchTokens.colors.border};
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .picker-selected-label {
                    font-size: 10px;
                    color: ${researchTokens.colors.muted};
                    font-family: var(--font-mono);
                    text-transform: uppercase;
                }
                .picker-selected-count {
                    color: ${researchTokens.colors.warn};
                    font-weight: 600;
                }
                .paste-modal {
                    margin-top: 8px;
                    padding: 8px;
                    background: ${researchTokens.colors.surface2};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: 4px;
                }
                .paste-textarea {
                    width: 100%;
                    min-height: 80px;
                    background: ${researchTokens.colors.bg};
                    border: 1px solid ${researchTokens.colors.border};
                    padding: 8px;
                    color: ${researchTokens.colors.text};
                    font-size: 11px;
                    font-family: var(--font-mono);
                    resize: vertical;
                    outline: none;
                }
                .invalid-tickers {
                    margin-top: 6px;
                    font-size: 10px;
                    color: ${researchTokens.colors.bad};
                    font-family: var(--font-mono);
                }
            `}</style>

            <div className="picker-header">
                <input
                    type="text"
                    className="picker-search"
                    placeholder={placeholder}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    disabled={loading}
                />
            </div>

            <div className="picker-actions">
                <button className="picker-btn" onClick={handleSelectAll}>
                    All Visible
                </button>
                <button className="picker-btn" onClick={() => setPasteMode(!pasteMode)}>
                    {pasteMode ? 'Cancel' : 'Paste'}
                </button>
                <button className="picker-btn" onClick={handleClearAll} style={{ color: researchTokens.colors.bad, borderColor: researchTokens.colors.border }}>
                    Clear
                </button>
            </div>

            {pasteMode && (
                <div className="paste-modal">
                    <textarea
                        className="paste-textarea"
                        placeholder="Paste tickers separated by space, comma or newline..."
                        value={pasteText}
                        onChange={(e) => setPasteText(e.target.value)}
                    />
                    <div style={{ marginTop: 6, display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        <button className="picker-btn" onClick={handlePasteSubmit} style={{ borderColor: researchTokens.colors.good, color: researchTokens.colors.good }}>
                            Add Tickers
                        </button>
                    </div>
                    {invalidTickers.length > 0 && (
                        <div className="invalid-tickers">
                            Unknown: {invalidTickers.join(', ')}
                        </div>
                    )}
                </div>
            )}

            {!pasteMode && (
                <div className="picker-list">
                    {loading ? (
                        <span style={{ color: researchTokens.colors.muted, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                            Loading universe...
                        </span>
                    ) : filtered.length === 0 ? (
                        <span style={{ color: researchTokens.colors.muted, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                            No matches found.
                        </span>
                    ) : (
                        filtered.map(ticker => (
                            <div
                                key={ticker}
                                className={`picker-item ${selected.includes(ticker) ? 'selected' : ''}`}
                                onClick={() => handleToggle(ticker)}
                            >
                                {ticker}
                            </div>
                        ))
                    )}
                </div>
            )}

            <div className="picker-selected">
                <span className="picker-selected-label">Selection</span>
                <span className="picker-selected-count">{selected.length}</span>
            </div>
        </div>
    );
}
