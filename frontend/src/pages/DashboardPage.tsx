import { useQuery } from '@tanstack/react-query';
import { FiscalNotice } from '../components/Notice';
import { StatCard } from '../components/StatCard';
import { dashboard, listCodexAnalyses, listLedgerEvents } from '../lib/api';

export default function DashboardPage() {
  const dashboardQuery = useQuery({ queryKey: ['dashboard'], queryFn: dashboard });
  const ledgerQuery = useQuery({ queryKey: ['ledger-events'], queryFn: () => listLedgerEvents() });
  const codexQuery = useQuery({ queryKey: ['codex-analyses'], queryFn: listCodexAnalyses });

  const events = ledgerQuery.data ?? [];
  const recentCodex = (codexQuery.data ?? []).slice(0, 5);

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>Dashboard</h1>
          <p>Local overview of analysis, ledger and PT fiscal preparation.</p>
        </div>
      </div>
      <FiscalNotice />
      <div className="stats-grid">
        <StatCard label="Ledger events" value={dashboardQuery.data?.ledger_events ?? '...'} />
        <StatCard label="Decision links" value={dashboardQuery.data?.decisions ?? '...'} />
        <StatCard label="Codex analyses" value={dashboardQuery.data?.codex_analyses ?? '...'} />
        <StatCard
          label={`Review rows ${dashboardQuery.data?.current_year ?? ''}`}
          value={dashboardQuery.data?.fiscal_review_rows_current_year ?? '...'}
          detail={dashboardQuery.data?.fiscal_error ?? undefined}
        />
      </div>
      <div className="two-column">
        <section className="panel">
          <h2>Recent ledger events</h2>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Asset</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Review</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, 6).map((event) => (
                <tr key={`${event.source_hash}-${event.timestamp}`}>
                  <td>{event.timestamp.slice(0, 10)}</td>
                  <td>{event.symbol}</td>
                  <td>{event.side ?? event.event_type}</td>
                  <td>{event.quantity}</td>
                  <td>{event.requires_review ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="panel">
          <h2>Recent Codex analyses</h2>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Ticker</th>
                <th>Rating</th>
              </tr>
            </thead>
            <tbody>
              {recentCodex.map((item) => (
                <tr key={item.analysis_id}>
                  <td>{item.trade_date}</td>
                  <td>{item.ticker}</td>
                  <td>{item.rating}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
