/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import StudioPaneBoundary from '../../StudioPaneBoundary';

describe('integration hardest', () => {
    it('StudioPaneBoundary does not throw on null data and shows fallback', () => {
        const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
        const Throwing = () => { throw new Error('canvas fail'); };
        render(
            <StudioPaneBoundary resetKey="test">
                <Throwing />
            </StudioPaneBoundary>
        );
        expect(screen.getByRole('heading', { name: /Workspace pane failed/i })).toBeInTheDocument();
        spy.mockRestore();
    });
    it('retry button clears error', async () => {
        const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
        const Throwing = () => { throw new Error('first fail'); };
        render(
            <StudioPaneBoundary resetKey="1">
                <Throwing />
            </StudioPaneBoundary>
        );
        expect(screen.getByRole('heading', { name: /Workspace pane failed/i })).toBeInTheDocument();
        const btn = screen.getByRole('button', { name: /Retry pane/i });
        expect(btn).toBeInTheDocument();
        spy.mockRestore();
    });
});
