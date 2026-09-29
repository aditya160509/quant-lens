"use client";

import React from 'react';
import { researchTokens } from '@/lib/theme/researchTokens';

/**
 * StatusMeta - Display cache status and computation metadata.
 * Upgraded for Cluster D Premium Terminal.
 */
export default function StatusMeta({
    meta = {},
    loading = false,
    error = null
}) {
    const formatDate = (isoString) => {
        if (!isoString) return 'N/A';
        try {
            const d = new Date(isoString);
            return d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch {
            return isoString;
        }
    };

    const isCached = meta.cache_hit === true;

    return (
        <div className="status-meta">
            <style jsx>{`
                .status-meta {
                    display: flex;
                    align-items: center;
                    gap: ${researchTokens.spacing.md}px;
                    padding: 6px 12px;
                    background: ${researchTokens.colors.surface};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: ${researchTokens.radius.chip}px;
                    font-size: ${researchTokens.typography.mono}px;
                    font-family: var(--font-mono);
                    height: 32px;
                }
                .meta-item {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    color: ${researchTokens.colors.muted};
                }
                .meta-value {
                    color: ${researchTokens.colors.text};
                    font-weight: 500;
                }
                .cache-badge {
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .status-fresh {
                    background: rgba(0, 255, 106, 0.1);
                    color: ${researchTokens.colors.good};
                    border: 1px solid rgba(0, 255, 106, 0.3);
                }
                .status-cached {
                    background: rgba(96, 165, 250, 0.1);
                    color: ${researchTokens.colors.info};
                    border: 1px solid rgba(96, 165, 250, 0.3);
                }
                .loading-indicator {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    color: ${researchTokens.colors.warn};
                }
                .spinner {
                    width: 12px;
                    height: 12px;
                    border: 2px solid ${researchTokens.colors.border2};
                    border-top-color: ${researchTokens.colors.warn};
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                .error-badge {
                    color: ${researchTokens.colors.bad};
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    font-weight: 600;
                }
            `}</style>

            {loading ? (
                <div className="loading-indicator">
                    <div className="spinner"></div>
                    <span>CALCULATING</span>
                </div>
            ) : error ? (
                <div className="error-badge">
                    <span>ERR</span>
                    <span>{error.message || 'Compute Failed'}</span>
                </div>
            ) : (
                <>
                    {meta.cache_hit !== undefined && (
                        <div className={`cache-badge ${isCached ? 'status-cached' : 'status-fresh'}`}>
                            {isCached ? 'CACHED' : 'FRESH'}
                        </div>
                    )}

                    {meta.computed_at && (
                        <div className="meta-item">
                            <span>T:</span>
                            <span className="meta-value">{formatDate(meta.computed_at)}</span>
                        </div>
                    )}

                    {(meta.tickers_computed || meta.data_points) && (
                        <div className="meta-item">
                            <span>N:</span>
                            <span className="meta-value">
                                {meta.tickers_computed || meta.data_points}
                            </span>
                        </div>
                    )}

                    {meta.lookback_days && (
                        <div className="meta-item">
                            <span>L:</span>
                            <span className="meta-value">{meta.lookback_days}d</span>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
