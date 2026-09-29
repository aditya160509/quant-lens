"use client";

import React from 'react';
import { researchTokens } from '@/lib/theme/researchTokens';

/**
 * ExportButtons - Export data to JSON or CSV.
 */
export default function ExportButtons({
    data,
    meta = {},
    filename = 'export',
    disabled = false
}) {
    const handleExportJSON = () => {
        const exportData = {
            meta: {
                ...meta,
                exported_at: new Date().toISOString()
            },
            data
        };

        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${filename}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleExportCSV = () => {
        if (!Array.isArray(data) || data.length === 0) {
            console.warn('No data to export');
            return;
        }

        // Get headers from first row
        const headers = Object.keys(data[0]);

        // Build CSV content
        const csvRows = [
            // Meta as comments
            ...Object.entries(meta).map(([k, v]) => `# ${k}: ${JSON.stringify(v)}`),
            '',
            // Header row
            headers.join(','),
            // Data rows
            ...data.map(row =>
                headers.map(h => {
                    const val = row[h];
                    if (val === null || val === undefined) return '';
                    if (typeof val === 'string' && val.includes(',')) return `"${val}"`;
                    return String(val);
                }).join(',')
            )
        ];

        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${filename}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="export-buttons">
            <style jsx>{`
                .export-buttons {
                    display: flex;
                    gap: 8px;
                }
                .export-btn {
                    background: ${researchTokens.colors.surface2};
                    border: 1px solid ${researchTokens.colors.border};
                    border-radius: 4px;
                    padding: 4px 10px;
                    color: ${researchTokens.colors.muted};
                    font-size: 11px;
                    font-family: var(--font-mono);
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    text-transform: uppercase;
                }
                .export-btn:hover:not(:disabled) {
                    background: ${researchTokens.colors.primary};
                    border-color: ${researchTokens.colors.primary};
                    color: ${researchTokens.colors.bg};
                    font-weight: 600;
                }
                .export-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
            `}</style>

            <button
                className="export-btn"
                onClick={handleExportJSON}
                disabled={disabled || !data}
                title="Download JSON"
            >
                JSON
            </button>

            <button
                className="export-btn"
                onClick={handleExportCSV}
                disabled={disabled || !Array.isArray(data) || data.length === 0}
                title="Download CSV"
            >
                CSV
            </button>
        </div>
    );
}
