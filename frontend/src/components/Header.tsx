import { useStore } from '../store';
import type { IngestStats } from '../types';

interface Props {
  stats: IngestStats | null;
  lastRefresh: Date;
}

const formatNumber = (value?: number | null) =>
  value !== undefined && value !== null && !Number.isNaN(value)
    ? value.toLocaleString()
    : '0';

const formatTime = (value: Date) =>
  value.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

export function Header({ stats, lastRefresh }: Props) {
  const setShowCreateModal = useStore((state) => state.setShowCreateModal);

  return (
    <header className="topbar card">
      <div className="brand">
        <div className="logo">H</div>

        <div>
          <div className="brand-kicker">Highwood EMS</div>
          <div className="brand-title">Emissions Management Dashboard</div>
        </div>
      </div>

      <div className="topbar-actions">
        <span className="pill live">
          <span className="live-dot" />
          Live
        </span>

        <span className="pill">
          Last refresh {formatTime(lastRefresh)}
        </span>

        <span className="pill">
          Sites {formatNumber(stats?.active_sites)}
        </span>

        <span className="pill">
          Readings {formatNumber(stats?.total_measurements)}
        </span>

        <button
          className="primary-btn"
          onClick={() => setShowCreateModal(true)}
          type="button"
        >
          + New Site
        </button>
      </div>
    </header>
  );
}