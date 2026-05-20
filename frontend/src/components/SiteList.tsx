import type { Site } from '../types';

interface Props {
  sites: Site[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  onNewSite: () => void;
}

const safeNumber = (value?: number | null) =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0;

const formatNumber = (value?: number | null, suffix = '') =>
  `${safeNumber(value).toLocaleString()}${suffix}`;

const formatPercent = (value?: number | null) =>
  `${safeNumber(value).toFixed(1)}%`;

function getUtilization(site: Site) {
  const total = safeNumber(site.methane_accumulated_emissions_to_date);
  const limit = safeNumber(site.methane_emission_limit);

  return limit > 0 ? (total / limit) * 100 : 0;
}

function getStatus(pct: number, exceeded: boolean) {
  if (exceeded) {
    return { label: 'Exceeded', tone: 'danger' };
  }

  if (pct >= 80) {
    return { label: 'Watch', tone: 'warn' };
  }

  return { label: 'OK', tone: 'ok' };
}

export function SiteList({
  sites,
  selectedId,
  onSelect,
  loading,
  onNewSite,
}: Props) {
  return (
    <aside className="site-panel card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Monitoring Sites</h2>
          <p className="card-subtitle">Active facilities and well pads</p>
        </div>

        <span className="site-count">{sites.length}</span>
      </div>

      <div className="site-list">
        {loading ? (
          <SkeletonCards />
        ) : sites.length === 0 ? (
          <EmptyState onNewSite={onNewSite} />
        ) : (
          sites.map((site) => {
            const siteId = site.site_id;
            const siteName = site.site_name;
            const siteLocation = site.site_location;

            const total = safeNumber(
              site.methane_accumulated_emissions_to_date,
            );

            const limit = safeNumber(site.methane_emission_limit);
            const pct = getUtilization(site);
            const exceeded = limit > 0 && total > limit;
            const status = getStatus(pct, exceeded);
            const selected = siteId === selectedId;
            const fillClass = exceeded ? 'danger' : pct >= 80 ? 'warn' : '';
            const progressWidth = Math.min(Math.max(pct, 0), 100);

            return (
              <button
                key={siteId}
                onClick={() => onSelect(siteId)}
                className={`site-card${selected ? ' selected' : ''}`}
                type="button"
              >
                <div className="site-card-top">
                  <div>
                    <div className="site-name">{siteName}</div>
                    <div className="site-location">{siteLocation}</div>
                  </div>

                  <span className={`badge ${status.tone}`}>
                    {status.label}
                  </span>
                </div>

                <div className="progress">
                  <div
                    className={`progress-fill ${fillClass}`}
                    style={{ width: `${progressWidth}%` }}
                  />
                </div>

                <div className="site-meta">
                  <span>{formatNumber(total, ' kg')}</span>
                  <span>{formatPercent(pct)}</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}

function SkeletonCards() {
  return (
    <>
      {[1, 2, 3].map((item) => (
        <div key={item} className="skeleton" />
      ))}
    </>
  );
}

function EmptyState({ onNewSite }: { onNewSite: () => void }) {
  return (
    <div className="empty-state">
      <div>
        <div className="empty-icon">⬡</div>

        <h3 className="card-title">No sites yet</h3>

        <p className="card-subtitle">
          Create your first monitoring site to start tracking methane emissions.
        </p>

        <button
          className="primary-btn"
          style={{ marginTop: 16 }}
          onClick={onNewSite}
          type="button"
        >
          + Create Site
        </button>
      </div>
    </div>
  );
}