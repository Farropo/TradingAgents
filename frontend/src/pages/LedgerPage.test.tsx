import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/render';
import LedgerPage from './LedgerPage';

const previewLedgerCsv = vi.fn(async (_file: File) => ({
  events: [{ timestamp: '2026-01-01T00:00:00Z', event_type: 'TRADE', asset_type: 'EQUITY', symbol: 'AAPL', quantity: '1', side: 'BUY', currency: 'EUR', broker: 'DEGIRO', requires_review: false, source_hash: 'abc' }],
  errors: [],
}));

vi.mock('../lib/api', () => ({
  previewLedgerCsv: (file: File) => previewLedgerCsv(file),
  importLedgerCsv: async () => ({ batch_id: 1, row_count: 1, inserted_count: 1, skipped_count: 0, source_hash: 'h' }),
  listLedgerEvents: async () => [],
}));

describe('LedgerPage', () => {
  it('previews a CSV upload', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LedgerPage />);

    const file = new File(['csv'], 'trades.csv', { type: 'text/csv' });
    await user.upload(screen.getByLabelText(/csv file/i), file);
    await user.click(screen.getByRole('button', { name: /preview/i }));

    expect(await screen.findByText(/Preview: 1 events, 0 errors/)).toBeInTheDocument();
    expect(previewLedgerCsv).toHaveBeenCalledWith(file);
  });
});
