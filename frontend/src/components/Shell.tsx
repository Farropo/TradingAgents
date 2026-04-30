import { NavLink, Outlet } from 'react-router-dom';
import {
  BarChart3,
  Bot,
  ClipboardList,
  FileText,
  FolderOpen,
  Landmark,
  PlayCircle,
  Settings,
  TrendingUp,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { health } from '../lib/api';

const navItems = [
  { to: '/', label: 'Dashboard', icon: BarChart3 },
  { to: '/markets', label: 'Markets', icon: TrendingUp },
  { to: '/codex', label: 'Codex Assisted', icon: Bot },
  { to: '/ledger', label: 'Ledger', icon: ClipboardList },
  { to: '/fiscal', label: 'Fiscal PT', icon: Landmark },
  { to: '/analysis', label: 'Analysis Runs', icon: PlayCircle },
  { to: '/reports', label: 'Reports', icon: FolderOpen },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Shell() {
  const { data } = useQuery({ queryKey: ['health'], queryFn: health, refetchInterval: 10_000 });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <FileText size={22} />
          <div>
            <strong>TradingAgents</strong>
            <span>Local desk</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={item.to} end={item.to === '/'}>
                <Icon size={18} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <strong>Local-only workspace</strong>
            <span>No AT submission. No browser-visible API keys.</span>
          </div>
          <span className={`status-dot ${data?.status === 'ok' ? 'online' : 'offline'}`}>
            {data?.status === 'ok' ? 'Backend online' : 'Backend offline'}
          </span>
        </header>
        <section className="content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
