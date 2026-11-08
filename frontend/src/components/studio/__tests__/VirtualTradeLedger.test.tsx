import { vi, describe, it, expect } from "vitest";
import { fireEvent, render, screen } from '@testing-library/react';
import VirtualTradeLedger, { tradeReturn } from '../results/VirtualTradeLedger';

vi.mock('@tanstack/react-virtual', () => ({
    useVirtualizer: ({ count }: { count: number }) => ({
        getTotalSize: () => count * 66,
        getVirtualItems: () => count ? [{ index: 0, key: '0', start: 0, size: 66 }] : [],
    }),
}));

describe('VirtualTradeLedger', () => {
    it('preserves a zero return as observed data', () => {
        expect(tradeReturn({ pnl: 0 })).toBe(0);
        expect(tradeReturn({ pnl: null })).toBeNull();
    });

    it('renders a virtual row and navigates through the supplied handler', () => {
        const onSelect = vi.fn();
        const trade = { id: 'T-1', entry_date: '2025-01-01', exit_date: '2025-01-02', entry_price: 100, exit_price: 101, direction: 1, holding_period: 1, pnl: 0.01 };
        render(<VirtualTradeLedger trades={[trade]} onSelect={onSelect} />);

        fireEvent.click(screen.getByRole('row', { name: 'Open trade T-1 on chart' }));
        expect(onSelect).toHaveBeenCalledWith(trade, 0);
        expect(screen.getByText('+1.00%')).toBeInTheDocument();
    });
});
