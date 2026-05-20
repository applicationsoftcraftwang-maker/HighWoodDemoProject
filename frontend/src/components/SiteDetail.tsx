import type { Site, SiteMetrics } from '../types';
import { MetricCard } from './MetricCard';
import { IngestForm } from './IngestForm';

interface Props {
  site: Site;
  metrics: SiteMetrics | null;
  onRefresh: () => void;
}

const safeNumber = (value?: number | null) =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0;

const formatNumber = (value?: number | null, suffix = '') =>
  `${safeNumber(value).toLocaleString()}${suffix}`;

const formatPercent = (value?: number | null) =>
  typeof value === 'number' && Number.isFinite(value)
    ? `${value.toFixed(1)}%`
    : '—';

const formatDate = (value?: string | null) => {
  if (!value) return '—';

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString();
};

const formatTime = (value?: string | null) => {
  if (!value) return 'No readings yet';

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'No readings yet' : date.toLocaleTimeString();
};

export function SiteDetail({ site, metrics, onRefresh }: Props) {
  const total = safeNumber(
    metrics?.total_emissions_to_date ??
      site.methane_accumulated_emissions_to_date
  );

  const limit = safeNumber(
    metrics?.emission_limit ??
      site.methane_emission_limit
  );

  const utilization =
    limit > 0
      ? (total / limit) * 100
      : safeNumber(metrics?.utilization_percent);

  const exceeded = limit > 0 && total > limit;
  const pct = Math.min(Math.max(utilization, 0), 100);
  const warn = !exceeded && utilization >= 80;

  return (
    <section className="detail">
      <div className="hero card">
        <div className="hero-top">
          <div>
            <h1>{site.site_name}</h1>
            <div className="hero-meta">
              <span>{site.site_location}</span>
              <span>·</span>
              <span>{site.site_id}</span>
            </div>
          </div>

          <div className="hero-actions">
            <span className={`badge ${exceeded ? 'danger' : warn ? 'warn' : 'ok'}`}>
              {exceeded ? 'Limit exceeded' : warn ? 'Watch' : 'Within limit'}
            </span>

            <button className="secondary-btn" onClick={onRefresh} type="button">
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="metrics-grid">
        <MetricCard
          label="Total Emissions"
          value={formatNumber(total, ' kg')}
          sub={`Limit: ${formatNumber(limit, ' kg')}`}
          danger={exceeded}
        />

        <MetricCard
          label="Utilization"
          value={formatPercent(utilization)}
          sub={exceeded ? 'Over compliance limit' : warn ? 'Approaching limit' : 'Within compliance limit'}
          danger={exceeded}
          warn={warn}
        />

        <MetricCard
          label="Readings"
          value={formatNumber(metrics?.measurement_count)}
          sub="Total methane readings processed"
        />

        <MetricCard
          label="Last Reading"
          value={metrics?.last_measurement_at ? new Date(metrics.last_measurement_at).toLocaleDateString() : '—'}
          sub={metrics?.last_measurement_at ? new Date(metrics.last_measurement_at).toLocaleTimeString() : 'No readings yet'}
        />
      </div>

      <div className="gauge-card card">
        <div className="gauge-header">
          <div>
            <div className="gauge-title">Emission Utilization</div>
            <p className="card-subtitle">
              Current emissions compared with configured methane operating limit.
            </p>
          </div>

          <div className="gauge-value">{formatPercent(utilization)}</div>
        </div>

        <div className="progress" style={{ height: 12 }}>
          <div
            className={`progress-fill ${exceeded ? 'danger' : warn ? 'warn' : ''}`}
            style={{ width: `${pct}%` }}
          />
        </div>

        <div className="gauge-scale">
          <span>0 kg</span>
          <span>80% watch threshold</span>
          <span>{formatNumber(limit, ' kg')}</span>
        </div>
      </div>

      <IngestForm siteId={site.site_id} onSuccess={onRefresh} />

      <div className="info-strip">
        <strong>Notification pattern active:</strong> batch events are written atomically
        with each ingest transaction, improving downstream alert reliability under
        process failure.
      </div>
    </section>
  );
}