import { fireEvent, render, screen } from '@testing-library/react';
import StudioPaneBoundary from '../StudioPaneBoundary';

const consoleError = console.error;

function BrokenPane(): never {
    throw new Error('render failed');
}

describe('StudioPaneBoundary', () => {
    beforeEach(() => {
        console.error = jest.fn();
    });

    afterEach(() => {
        console.error = consoleError;
    });

    it('isolates a pane render failure and offers retry', () => {
        const { rerender } = render(
            <StudioPaneBoundary resetKey="develop">
                <BrokenPane />
            </StudioPaneBoundary>,
        );

        expect(screen.getByRole('alert')).toHaveTextContent('Workspace pane failed');
        rerender(
            <StudioPaneBoundary resetKey="validate">
                <div>Validation pane</div>
            </StudioPaneBoundary>,
        );
        expect(screen.getByText('Validation pane')).toBeVisible();
    });

    it('can retry the current pane', () => {
        let shouldFail = true;
        const ConditionalPane = () => {
            if (shouldFail) throw new Error('render failed');
            return <div>Recovered pane</div>;
        };
        render(
            <StudioPaneBoundary resetKey="develop">
                <ConditionalPane />
            </StudioPaneBoundary>,
        );
        shouldFail = false;
        fireEvent.click(screen.getByRole('button', { name: 'Retry pane' }));
        expect(screen.getByText('Recovered pane')).toBeVisible();
    });
});
