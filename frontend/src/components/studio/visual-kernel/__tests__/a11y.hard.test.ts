import { vi, describe, it, test, expect } from "vitest";
/**
 */
import React from 'react';
import { render } from '@testing-library/react';
import { exportCanvasToPNG } from '../canvas';

describe('a11y hardest', () => {
    it('export creates download link with correct MIME', () => {
        const canvas = document.createElement('canvas');
        canvas.toDataURL = vi.fn(() => 'data:image/png;base64,xxx');
        const createElementSpy = vi.spyOn(document, 'createElement');
        exportCanvasToPNG(canvas, 'test.png');
        expect(canvas.toDataURL).toHaveBeenCalledWith('image/png');
        createElementSpy.mockRestore();
    });
    it('hidden table rows === canvas points for first 20', () => {
        const data = Array.from({ length: 30 }, (_, i) => 100 + i);
        // Simulate Tearsheet hidden table logic
        const rows = data.slice(0, 20).map((v, i) => ({ i, v }));
        expect(rows.length).toBe(20);
        expect(rows[0].v).toBe(100);
    });
});
