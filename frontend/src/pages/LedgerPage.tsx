import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FiscalNotice } from '../components/Notice';
import { importLedgerCsv, listLedgerEvents, previewLedgerCsv, type LedgerPreview } from '../lib/api';

export default function LedgerPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState('');
  const [preview, setPreview] = useState<LedgerPreview | null>(null);

  const events = useQuery({
    queryKey: ['ledger-events', year],
    queryFn: () => listLedgerEvents(year ? Number(year) : undefined),
  });
  const previewMutation = useMutation({
    mutationFn: () => previewLedgerCsv(file!),
    onSuccess: setPreview,
  });
  const importMutation = useMutation({
    mutationFn: () => importLedgerCsv(file!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['ledger-events'] });
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>Ledger</h1>
          <p>Import broker/exchange CSV files into the normalized local ledger.</p>
        </div>
      </div>
      <FiscalNotice />
      <section className="panel">
        <h2>CSV import</h2>
        <div className="form-grid">
          <label>
            CSV file
            <input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button disabled={!file || previewMutation.isPending} onClick={() => previewMutation.mutate()}>
            Preview
          </button>
          <button disabled={!file || importMutation.isPending} onClick={() => importMutation.mutate()}>
            Import
          </button>
        </div>
        {preview ? (
          <div>
            <p className={preview.errors.length ? 'error' : 'success'}>
              Preview: {preview.events.length} events, {preview.errors.length} errors
            </p>
            {preview.errors.map((error) => <p className="error" key={error}>{error}</p>)}
          </div>
        ) : null}
        {importMutation.data ? (
          <p className="success">
            Imported {importMutation.data.inserted_count} rows, skipped {importMutation.data.skipped_count}.
          </p>
        ) : null}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Events</h2>
          <label className="inline-label">
            Year
            <input value={year} onChange={(event) => setYear(event.target.value)} placeholder="2026" />
          </label>
        </div>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Asset</th>
              <th>Qty</th>
              <th>Broker</th>
              <th>Review</th>
              <th>Hash</th>
            </tr>
          </thead>
          <tbody>
            {(events.data ?? []).map((event) => (
              <tr key={`${event.source_hash}-${event.timestamp}`}>
                <td>{event.timestamp.slice(0, 10)}</td>
                <td>{event.side ?? event.event_type}</td>
                <td>{event.asset_type}:{event.symbol}</td>
                <td>{event.quantity}</td>
                <td>{event.broker ?? ''}</td>
                <td>{event.requires_review ? event.review_reason || 'Yes' : 'No'}</td>
                <td className="mono">{event.source_hash?.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
