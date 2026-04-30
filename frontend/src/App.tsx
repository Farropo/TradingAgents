import { Navigate, Route, Routes } from 'react-router-dom';
import Shell from './components/Shell';
import AnalysisRunsPage from './pages/AnalysisRunsPage';
import CodexPage from './pages/CodexPage';
import DashboardPage from './pages/DashboardPage';
import FiscalPage from './pages/FiscalPage';
import LedgerPage from './pages/LedgerPage';
import MarketsPage from './pages/MarketsPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<DashboardPage />} />
        <Route path="markets" element={<MarketsPage />} />
        <Route path="codex" element={<CodexPage />} />
        <Route path="ledger" element={<LedgerPage />} />
        <Route path="fiscal" element={<FiscalPage />} />
        <Route path="analysis" element={<AnalysisRunsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
