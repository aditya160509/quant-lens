import { describe, it, expect } from "vitest";
import { folderOf, normalizeFolder } from '@/stores/studio/projectStore';
import { analyzePythonSource, extractSymbols, filterCompletions } from '@/components/studio/Editor';
import { paginateVariable, VARIABLES_PAGE_SIZE } from '@/components/studio/develop/ExecutionDock';
import {
    validateCorporateActions,
    validateLookAhead,
    validateMarketConventions,
    assessPreflight,
} from '@/components/studio/PreExecuteModal';
import { STUDIO_QUOTAS, estimateComputeQuota } from '@/hooks/studio/useStudioExecution';

describe('P5 polish: folder-aware project paths', () => {
    it('derives folder prefixes and normalizes destinations', () => {
        expect(folderOf('/strategy.py')).toBe('/');
        expect(folderOf('/research/momentum.py')).toBe('/research');
        expect(normalizeFolder('research')).toBe('/research');
        expect(normalizeFolder('/research/')).toBe('/research');
        expect(normalizeFolder('')).toBe('/');
    });
});

describe('P5 polish: LSP-lite diagnostics and symbols', () => {
    it('flags empty source and missing Strategy class', () => {
        expect(analyzePythonSource('').some((d) => d.severity === 'error')).toBe(true);
        const missing = analyzePythonSource('x = 1\n');
        expect(missing.some((d) => d.message.includes('class Strategy'))).toBe(true);
    });

    it('passes a minimal valid strategy and detects unbalanced brackets', () => {
        const ok = analyzePythonSource('class Strategy:\n    def generate_signals(self, data):\n        return []\n');
        expect(ok.filter((d) => d.severity === 'error')).toHaveLength(0);
        const bad = analyzePythonSource('class Strategy:\n    def generate_signals(self, data:\n        return []\n');
        expect(bad.some((d) => d.severity === 'error')).toBe(true);
    });

    it('extracts class/def symbols with line numbers', () => {
        const symbols = extractSymbols('class Strategy:\n    def generate_signals(self, data):\n        return []\n');
        expect(symbols).toEqual([
            { kind: 'class', name: 'Strategy', line: 1 },
            { kind: 'def', name: 'generate_signals', line: 2 },
        ]);
    });

    it('filters keyword completions by query', () => {
        expect(filterCompletions('').length).toBeGreaterThan(0);
        const hits = filterCompletions('generate_signals');
        expect(hits.every((c) => c.label.toLowerCase().includes('generate_signals'))).toBe(true);
    });
});

describe('P5 polish: variables pagination', () => {
    it('pages at size 50 with safe bounds', () => {
        expect(VARIABLES_PAGE_SIZE).toBe(50);
        const rows = Array.from({ length: 120 }, (_, i) => i);
        expect(paginateVariable(rows, 0).items).toHaveLength(50);
        expect(paginateVariable(rows, 2).items).toHaveLength(20);
        expect(paginateVariable(rows, 2).totalPages).toBe(3);
        expect(paginateVariable(rows, 99).page).toBe(2);
        expect(paginateVariable(null, 0).total).toBe(0);
    });
});

describe('P5 polish: preflight validators', () => {
    it('reports unknown corporate actions and unverified look-ahead truthfully', () => {
        expect(validateCorporateActions({}).status).toBe('unknown');
        expect(validateCorporateActions({ corporate_actions: 'adjusted' }).status).toBe('adjusted');
        expect(validateLookAhead({}).status).toBe('not_verified');
        expect(validateLookAhead({ look_ahead_check: 'verified' }).status).toBe('verified');
        expect(validateCorporateActions({}).blocking).toBe(false);
        expect(validateLookAhead({}).blocking).toBe(false);
    });

    it('reads timezone/currency/calendar from backend metadata', () => {
        const conv = validateMarketConventions({ timezone: 'UTC', currency: 'USD', calendar: 'XNYS' });
        expect(conv.complete).toBe(true);
        expect(validateMarketConventions({}).complete).toBe(false);
    });

    it('separates blocking errors from warnings including validator output', () => {
        const blocked = assessPreflight({ status: 'unavailable', observations: 0 });
        expect(blocked.blocking.length).toBeGreaterThan(0);
        const warned = assessPreflight(
            { status: 'observed', observations: 100, corporate_actions: 'unknown', look_ahead_check: 'not_verified', timezone: 'UTC', currency: 'USD', calendar: 'XNYS' },
            new Date('2026-01-01T00:00:00Z').getTime(),
        );
        expect(warned.blocking).toHaveLength(0);
        expect(warned.warnings.some((w) => w.includes('Corporate actions: unknown'))).toBe(true);
        expect(warned.warnings.some((w) => w.includes('not verified'))).toBe(true);
    });
});

describe('P5 polish: execution quotas', () => {
    it('mirrors backend convention limits and estimates code budget', () => {
        expect(STUDIO_QUOTAS.maxCodeBytes).toBe(64 * 1024);
        expect(STUDIO_QUOTAS.maxSignals).toBe(100_000);
        expect(STUDIO_QUOTAS.executionMode).toBe('isolated_one_shot');
        expect(estimateComputeQuota('x = 1').withinQuota).toBe(true);
        expect(estimateComputeQuota('x'.repeat(STUDIO_QUOTAS.maxCodeBytes + 1)).withinQuota).toBe(false);
    });
});
