import { create } from 'zustand';
import type { Site, SiteMetrics, IngestStats } from '../types';

interface AppStore {
  sites: Site[];
  selectedId: string | null;
  metrics: SiteMetrics | null;
  stats: IngestStats | null;
  showCreateModal: boolean;

  setSites: (sites: Site[]) => void;
  setSelectedId: (siteId: string | null) => void;
  setMetrics: (metrics: SiteMetrics | null) => void;
  setStats: (stats: IngestStats | null) => void;
  setShowCreateModal: (visible: boolean) => void;
  resetDashboard: () => void;
}

export const useStore = create<AppStore>((set) => ({
  sites: [],
  selectedId: null,
  metrics: null,
  stats: null,
  showCreateModal: false,

  setSites: (sites) => set({ sites }),

  setSelectedId: (selectedId) => set({ selectedId }),

  setMetrics: (metrics) => set({ metrics }),

  setStats: (stats) => set({ stats }),

  setShowCreateModal: (showCreateModal) => set({ showCreateModal }),

  resetDashboard: () =>
    set({
      sites: [],
      selectedId: null,
      metrics: null,
      stats: null,
      showCreateModal: false,
    }),
}));