import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { FiscalNotice } from '../components/Notice';
import { API_BASE, fiscalReport } from '../lib/api';

export default function FiscalPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const report = useQuery({ queryKey: ['fiscal', year], queryFn: () => fiscalReport(year) });

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>Fiscal PT</h1>
          <p>Portugal-focused tax dossier support: appendix hints, review flags, FIFO gains and open inventory.</p>
        </div>
      </div>
      <FiscalNotice />
      <section className="panel">
        <div className="panel-heading">
          <h2>Tax year</h2>
          <label className="inline-label">
            Year
            <input type="number" value={year} onChange={(event) => setYear(Number(event.target.value))} />
          </label>
        </div>
        <div className="button-row">
          <a className="button secondary" href={`${API_BASE}/api/fiscal/pt/${year}/export?format=csv`}>Export CSV</a>
          <a className="button secondary" href={`${API_BASE}/api/fiscal/pt/${year}/export?format=json`}>Export JSON</a>
        </div>
      </section>
      <section className="panel">
        <h2>Totals</h2>
        <table>
          <thead>
            <tr>
              <th>Treatment</th>
              <th>Proceeds</th>
              <th>Cost</th>
              <th>Gain</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(report.data?.totals_by_treatment ?? {}).map(([treatment, totals]) => (
              <tr key={treatment}>
                <td>{treatment}</td>
                <td>{totals.proceeds_eur}</td>
                <td>{totals.cost_basis_eur}</td>
                <td>{totals.gain_eur}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>Rows requiring accountant review are highlighted</h2>
        <table>
          <thead>
            <tr>
              <th>Appendix</th>
              <th>Asset</th>
              <th>Buy date</th>
              <th>Sell date</th>
              <th>Gain EUR</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {(report.data?.rows ?? []).map((row) => (
              <tr key={`${row.symbol}-${row.acquisition_date}-${row.realization_date}`} className={row.requires_review ? 'review-row' : ''}>
                <td>{row.appendix}</td>
                <td>{row.symbol}</td>
                <td>{row.acquisition_date}</td>
                <td>{row.realization_date}</td>
                <td>{row.gain_eur}</td>
                <td>{row.requires_review ? row.review_reason || 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
