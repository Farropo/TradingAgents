import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/render';
import FiscalPage from './FiscalPage';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return {
    ...actual,
    fiscalReport: async () => ({
      jurisdiction: 'PT',
      year: 2026,
      rows: [
        { tax_year: 2026, appendix: 'G', category: 'G', asset_type: 'EQUITY', symbol: 'AAPL', acquisition_date: '2026-01-01', realization_date: '2026-02-01', quantity: '1', proceeds_eur: '120', cost_basis_eur: '100', expenses_eur: '1', gain_eur: '19', holding_days: 31, tax_treatment: 'PT_SECURITIES_G_OR_J', requires_review: false },
      ],
      totals_by_treatment: { PT_SECURITIES_G_OR_J: { proceeds_eur: '120', cost_basis_eur: '100', gain_eur: '19' } },
      inventory: [],
      review_notes: [],
    }),
  };
});

describe('FiscalPage', () => {
  it('renders fiscal totals and rows', async () => {
    renderWithProviders(<FiscalPage />);

    expect(await screen.findByText('PT_SECURITIES_G_OR_J')).toBeInTheDocument();
    expect(await screen.findByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText(/Nada é submetido automaticamente/)).toBeInTheDocument();
  });
});
