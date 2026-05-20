import { useEffect, useCallback, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './lib/api';
import { useStore } from './store';
import { Header } from './components/Header';
import { SiteList } from './components/SiteList';
import { SiteDetail } from './components/SiteDetail';
import { CreateSiteModal } from './components/CreateSiteModal';
import { ConnectionBanner } from './components/ConnectionBanner';
import { MetricCard } from './components/MetricCard';

const safeNumber = (value?: number | null) =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0;

const formatNumber = (value?: number | null, suffix = '') =>
  `${safeNumber(value).toLocaleString()}${suffix}`;

function EmptyMain({ onNewSite }: { onNewSite: () => void }) {
  return (
    <div className="card empty-state">
      <div>
        <div className="empty-icon">⬡</div>

        <h2 className="card-title">Select a monitoring site</h2>

        <p className="card-subtitle">
          Choose a site from the left panel to review metrics and submit readings.
        </p>

        <button
          className="primary-btn"
          style={{ marginTop: 18 }}
          onClick={onNewSite}
          type="button"
        >
          + Create Site
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const {
    sites,
    setSites,
    selectedId,
    setSelectedId,
    metrics,
    setMetrics,
    stats,
    setStats,
    showCreateModal,
    setShowCreateModal,
  } = useStore();

  const [lastRefresh, setLastRefresh] = useState(new Date());
  const queryClient = useQueryClient();

  const sitesQuery = useQuery({
    queryKey: ['sites'],
    queryFn: api.sites.list,
    refetchInterval: 10000,
  });

  const statsQuery = useQuery({
    queryKey: ['stats'],
    queryFn: api.ingest.stats,
    refetchInterval: 10000,
  });

  const metricsQuery = useQuery({
    queryKey: ['metrics', selectedId],
    queryFn: () => api.sites.metrics(selectedId!),
    enabled: !!selectedId,
    refetchInterval: 10000,
  });

  useEffect(() => {
    if (!sitesQuery.data) {
      return;
    }

    setSites(sitesQuery.data);
    setLastRefresh(new Date());

    const selectedStillExists =
      selectedId !== null &&
      sitesQuery.data.some((site) => site.site_id === selectedId);

    if (!selectedStillExists && sitesQuery.data.length > 0) {
      setSelectedId(sitesQuery.data[0].site_id);
    }

    if (sitesQuery.data.length === 0) {
      setSelectedId(null);
    }
  }, [sitesQuery.data, selectedId, setSelectedId, setSites]);

  useEffect(() => {
    setStats(statsQuery.data ?? null);
  }, [statsQuery.data, setStats]);

  useEffect(() => {
    setMetrics(metricsQuery.data ?? null);
  }, [metricsQuery.data, setMetrics]);

  const selectedSite =
    sites.find((site) => site.site_id === selectedId) ?? null;

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['sites'] });
    queryClient.invalidateQueries({ queryKey: ['stats'] });

    if (selectedId) {
      queryClient.invalidateQueries({ queryKey: ['metrics', selectedId] });
    }

    setLastRefresh(new Date());
  }, [selectedId, queryClient]);

  const openCreateSiteModal = () => {
    setShowCreateModal(true);
  };

  const closeCreateSiteModal = () => {
    setShowCreateModal(false);
  };

  const handleSiteCreated = () => {
    setShowCreateModal(false);
    handleRefresh();
  };

  return (
    <div className="app-shell">
      <div className="app-container">
        <Header stats={stats} lastRefresh={lastRefresh} />

        <ConnectionBanner
          isError={sitesQuery.isError || statsQuery.isError}
          isStale={sitesQuery.isStale && !sitesQuery.isFetching}
        />

        <div className="metrics-grid" style={{ marginBottom: 22 }}>
          <MetricCard
            label="Monitoring Sites"
            value={formatNumber(stats?.active_sites ?? sites.length)}
            sub="Configured methane assets"
          />

          <MetricCard
            label="Total Emissions"
            value={formatNumber(stats?.total_emissions_to_date, ' kg')}
            sub={`Limit: ${formatNumber(stats?.emission_limit, ' kg')}`}
          />

          <MetricCard
            label="Measurements"
            value={formatNumber(stats?.total_measurements)}
            sub="Readings received"
          />

          <MetricCard
            label="System Status"
            value="Online"
            sub="API and database available"
            accent
          />
        </div>

        <div className="app-grid">
          <SiteList
            sites={sites}
            selectedId={selectedId}
            onSelect={setSelectedId}
            loading={sitesQuery.isLoading}
            onNewSite={openCreateSiteModal}
          />

          {selectedSite ? (
            <SiteDetail
              site={selectedSite}
              metrics={metrics}
              onRefresh={handleRefresh}
            />
          ) : (
            <EmptyMain onNewSite={openCreateSiteModal} />
          )}
        </div>
      </div>

      {showCreateModal && (
        <CreateSiteModal
          onClose={closeCreateSiteModal}
          onCreated={handleSiteCreated}
        />
      )}
    </div>
  );
}