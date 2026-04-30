import { expect, test, type Page } from '@playwright/test';

async function mockApi(page: Page) {
  await page.route('http://127.0.0.1:8000/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    const json = (body: unknown) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(body),
      });

    if (path === '/api/health') {
      return json({ status: 'ok', local_only: true });
    }
    if (path === '/api/dashboard') {
      return json({
        ledger_events: 3,
        decisions: 1,
        codex_analyses: 1,
        fiscal_review_rows_current_year: 1,
        current_year: 2026,
        fiscal_error: null,
      });
    }
    if (path === '/api/markets/movers') {
      return json({
        market: url.searchParams.get('market') ?? 'pt',
        generated_at: '2026-04-30T00:00:00Z',
        source: 'yfinance',
        quotes: [
          {
            symbol: 'EDP.LS',
            name: 'EDP',
            market: 'pt',
            currency: 'EUR',
            price: 4,
            previous_close: 3.5,
            change: 0.5,
            change_percent: 14.28,
            volume: 1000,
            as_of: '2026-04-29T00:00:00Z',
            source: 'yfinance',
            status: 'ok',
          },
          {
            symbol: 'GALP.LS',
            name: 'Galp',
            market: 'pt',
            currency: 'EUR',
            price: 19,
            previous_close: 20,
            change: -1,
            change_percent: -5,
            volume: 2000,
            as_of: '2026-04-29T00:00:00Z',
            source: 'yfinance',
            status: 'ok',
          },
        ],
        top_gainers: [
          {
            symbol: 'EDP.LS',
            market: 'pt',
            currency: 'EUR',
            price: 4,
            change: 0.5,
            change_percent: 14.28,
            source: 'yfinance',
            status: 'ok',
          },
        ],
        top_losers: [
          {
            symbol: 'GALP.LS',
            market: 'pt',
            currency: 'EUR',
            price: 19,
            change: -1,
            change_percent: -5,
            source: 'yfinance',
            status: 'ok',
          },
        ],
      });
    }
    if (path === '/api/markets/tickers/EDP.LS') {
      return json({
        symbol: 'EDP.LS',
        quote: {
          symbol: 'EDP.LS',
          name: 'EDP',
          market: 'pt',
          currency: 'EUR',
          price: 4,
          previous_close: 3.5,
          change: 0.5,
          change_percent: 14.28,
          volume: 1000,
          as_of: '2026-04-29T00:00:00Z',
          source: 'yfinance',
          status: 'ok',
        },
        history: [{ date: '2026-04-29T00:00:00Z', close: 4, volume: 1000 }],
        ledger: {
          event_count: 2,
          net_quantity: '8',
          buy_quantity: '10',
          sell_quantity: '2',
          latest_event_at: '2026-04-15T00:00:00Z',
        },
        decisions: [{ id: 1, ticker: 'EDP.LS', trade_date: '2026-04-30', rating: 'Hold' }],
      });
    }
    if (path === '/api/ledger/events') {
      return json([
        {
          timestamp: '2026-04-30T09:00:00+00:00',
          event_type: 'trade',
          asset_type: 'equity',
          symbol: 'NVDA',
          quantity: '1',
          side: 'buy',
          price: '860',
          currency: 'USD',
          broker: 'DemoBroker',
          account: 'MAIN',
          source_hash: 'abcdef123456',
          requires_review: false,
          review_reason: null,
        },
      ]);
    }
    if (path === '/api/ledger/imports/preview' && method === 'POST') {
      return json({
        events: [
          {
            timestamp: '2026-04-30T09:00:00+00:00',
            event_type: 'trade',
            asset_type: 'equity',
            symbol: 'NVDA',
            quantity: '1',
            side: 'buy',
            currency: 'USD',
            broker: 'DemoBroker',
            source_hash: 'previewhash',
            requires_review: false,
          },
        ],
        errors: [],
      });
    }
    if (path === '/api/ledger/imports' && method === 'POST') {
      return json({
        batch_id: 1,
        row_count: 1,
        inserted_count: 1,
        skipped_count: 0,
        source_hash: 'batchhash',
      });
    }
    if (path === '/api/codex/analyses') {
      return json([
        {
          analysis_id: 'analysis-1',
          ticker: 'NVDA',
          trade_date: '2026-04-30',
          rating: 'HOLD',
          model_hint: 'GPT-5.5 extra reasoning',
          report_path: 'local/codex/NVDA.md',
        },
      ]);
    }
    if (path === '/api/codex/bundles' && method === 'POST') {
      const payload = request.postDataJSON() as { ticker?: string; date?: string };
      const ticker = payload.ticker ?? 'NVDA';
      const tradeDate = payload.date ?? '2026-04-30';
      return json({
        bundle_id: `bundle-${ticker.toLowerCase().replace(/[^a-z0-9]/g, '-')}`,
        bundle_dir: `local/codex/${ticker}/${tradeDate}/bundle`,
        bundle_json_path: `local/codex/${ticker}/${tradeDate}/bundle/bundle.json`,
        prompt_path: `local/codex/${ticker}/${tradeDate}/bundle/prompt.md`,
        prompt_hash: 'prompthash',
        prompt: `# Codex analysis bundle\nTicker: ${ticker}\nDate: ${tradeDate}`,
      });
    }
    if (path === '/api/codex/import' && method === 'POST') {
      return json({
        analysis_id: 'analysis-2',
        analysis_dir: 'local/codex/NVDA/2026-04-30/analysis-2',
        response_path: 'local/codex/NVDA/2026-04-30/analysis-2/response.md',
        report_path: 'local/codex/NVDA/2026-04-30/analysis-2/report.md',
        bundle_hash: 'bundlehash',
        response_hash: 'responsehash',
        decision_link_id: 7,
        rating: 'HOLD',
      });
    }
    if (path === '/api/fiscal/pt/2026') {
      return json({
        jurisdiction: 'PT',
        year: 2026,
        rows: [
          {
            tax_year: 2026,
            appendix: 'Anexo J',
            category: 'G',
            asset_type: 'crypto',
            symbol: 'BTC',
            acquisition_date: '2026-01-01',
            realization_date: '2026-04-30',
            quantity: '0.1',
            proceeds_eur: '6200',
            cost_basis_eur: '5000',
            expenses_eur: '5',
            gain_eur: '1195',
            holding_days: 119,
            tax_treatment: 'pt_crypto_taxable',
            broker: 'DemoExchange',
            account: 'MAIN',
            requires_review: true,
            review_reason: 'Short-term crypto disposal; accountant review required.',
          },
        ],
        totals_by_treatment: {
          pt_crypto_taxable: {
            proceeds_eur: '6200',
            cost_basis_eur: '5000',
            gain_eur: '1195',
          },
        },
        inventory: [],
        review_notes: ['Short-term crypto disposal; accountant review required.'],
      });
    }
    if (path === '/api/analyses') {
      return json([]);
    }
    if (path === '/api/reports') {
      return json([]);
    }
    if (path === '/api/config/defaults') {
      return json({
        paths: { ledger_db_path: 'data/ledger.sqlite' },
        env: { FINNHUB_API_KEY: false, OPENAI_API_KEY: false },
        providers: ['codex-assisted'],
        message: 'Local-only configuration.',
      });
    }

    return route.fulfill({ status: 404, body: `Unhandled ${method} ${path}` });
  });
}

test('local workflow smoke test', async ({ page }) => {
  await mockApi(page);

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('Backend online')).toBeVisible();

  await page.getByRole('link', { name: /Markets/ }).click();
  await expect(page.getByRole('heading', { name: 'Markets' })).toBeVisible();
  await expect(page.getByText('Portugal')).toBeVisible();
  await page.getByRole('cell', { name: 'EDP.LS' }).click();
  await expect(page.getByText('EDP.LS detail')).toBeVisible();
  await page.getByRole('link', { name: /Prepare Codex Bundle/ }).click();
  await expect(page).toHaveURL(/\/codex\?ticker=EDP\.LS&date=2026-04-29/);
  await expect(page.getByLabel('Ticker')).toHaveValue('EDP.LS');

  await page.getByRole('link', { name: /Ledger/ }).click();
  await expect(page.getByRole('heading', { name: 'Ledger' })).toBeVisible();
  await page.getByLabel('CSV file').setInputFiles({
    name: 'sample.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('date,type,asset_type,symbol,quantity,side,currency\n2026-04-30,trade,equity,NVDA,1,buy,USD\n'),
  });
  await page.getByRole('button', { name: 'Preview' }).click();
  await expect(page.getByText('Preview: 1 events, 0 errors')).toBeVisible();
  await page.getByRole('button', { name: 'Import' }).click();
  await expect(page.getByText('Imported 1 rows, skipped 0.')).toBeVisible();

  await page.getByRole('link', { name: /Codex Assisted/ }).click();
  await page.getByRole('button', { name: 'Prepare bundle' }).click();
  await expect(page.getByText('Bundle ID: bundle-nvda')).toBeVisible();
  await expect(page.locator('textarea.prompt-box')).toHaveValue(/Ticker: NVDA/);
  await page.getByLabel('Paste Codex response').fill('rating: HOLD\nrisks: accounting review');
  await page.getByRole('button', { name: 'Import response' }).click();
  await expect(page.getByText('Imported rating: HOLD')).toBeVisible();

  await page.getByRole('link', { name: /Fiscal PT/ }).click();
  await expect(page.getByRole('heading', { name: 'Fiscal PT' })).toBeVisible();
  await expect(page.getByText('pt_crypto_taxable')).toBeVisible();
  await expect(page.getByText('Short-term crypto disposal; accountant review required.')).toBeVisible();
});
