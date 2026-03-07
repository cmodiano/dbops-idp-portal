/**
 * Tests for AdminPlatformSection component (Story 60.3, AC: 2, 4, 5, 6, 7, 9 / Story 60.4, AC: 9, 10).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminPlatformSection } from './AdminPlatformSection';
import { ApiError } from '../../../services/api_client';
import * as dashboardService from '../../../services/dashboard_service';

vi.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Cell: () => null,
  Legend: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../../services/dashboard_service', () => ({
  fetchStatsCatalogue: vi.fn(),
  fetchStatsAdoption: vi.fn(),
  // Keep other exports to avoid breaking ReportingDashboard tests
  fetchStatsByTechnology: vi.fn(),
  fetchStatsByEnvironment: vi.fn(),
  fetchTimeSeries: vi.fn(),
  fetchFilterOptions: vi.fn(),
  exportDashboardCSV: vi.fn(),
  exportDashboardPDF: vi.fn(),
  fetchComparison: vi.fn(),
}));

const mockCatalogueData = {
  by_status: [
    { status: 'published', count: 42 },
    { status: 'draft', count: 10 },
  ],
  by_item_type: [
    { item_type: 'action', count: 38 },
    { item_type: 'workflow', count: 14 },
  ],
  by_engine: [],
  by_category: [],
  evolution: [],
};

const mockAdoptionData = {
  executions_by_profile: [{ profile: 'DBA', count: 50 }],
  active_users_by_profile: [
    { profile: 'DBA', user_count: 8 },
    { profile: 'DBOPS', user_count: 2 },
  ],
  adoption_trend: [],
};

describe('AdminPlatformSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardService.fetchStatsCatalogue).mockResolvedValue(mockCatalogueData);
    vi.mocked(dashboardService.fetchStatsAdoption).mockResolvedValue(mockAdoptionData);
  });

  it('affiche les StatCards avec les données correctes (AC2)', async () => {
    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      // "Actions publiées" = 42 (published count)
      expect(screen.getByText('Actions publiées')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();

      // "Workflows" = 14 (workflow item_type count)
      expect(screen.getByText('Workflows')).toBeInTheDocument();
      expect(screen.getByText('14')).toBeInTheDocument();

      // "Utilisateurs actifs" = 10 (8 + 2)
      expect(screen.getByText('Utilisateurs actifs')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });
  });

  it('affiche le titre de section et le Divider (AC7)', async () => {
    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.getByText('Utilisation de la plateforme')).toBeInTheDocument();
    });
  });

  it('affiche les skeletons en état loading (AC5)', () => {
    // Keep promises pending to simulate loading
    vi.mocked(dashboardService.fetchStatsCatalogue).mockReturnValue(new Promise(() => {}));
    vi.mocked(dashboardService.fetchStatsAdoption).mockReturnValue(new Promise(() => {}));

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    // StatCard renders Skeleton when loading=true — check for skeleton elements
    const skeletons = document.querySelectorAll('.ant-skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('masque les stats catalogue si 403, garde Utilisateurs actifs (AC4)', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockRejectedValue(
      new ApiError('Forbidden', 403),
    );

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.queryByText('Actions publiées')).not.toBeInTheDocument();
      expect(screen.queryByText('Workflows')).not.toBeInTheDocument();
      expect(screen.getByText('Utilisateurs actifs')).toBeInTheDocument();
    });
  });

  it('n\'affiche PAS d\'Alert en cas de 403 catalogue (AC4)', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockRejectedValue(
      new ApiError('Forbidden', 403),
    );

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  it('affiche une Alert en cas d\'erreur réseau sur catalogue (AC6)', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockRejectedValue(
      new Error('Network error'),
    );

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('affiche une Alert en cas d\'erreur réseau sur adoption (AC6)', async () => {
    vi.mocked(dashboardService.fetchStatsAdoption).mockRejectedValue(
      new Error('Adoption network error'),
    );

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('transmet les filtres aux deux services (AC3)', async () => {
    render(<AdminPlatformSection filters={{ days: 30 }} />);

    await waitFor(() => {
      expect(dashboardService.fetchStatsCatalogue).toHaveBeenCalled();
      expect(dashboardService.fetchStatsAdoption).toHaveBeenCalled();
    });

    const catalogueCallArg = vi.mocked(dashboardService.fetchStatsCatalogue).mock.calls[0][0];
    expect(catalogueCallArg).toMatchObject({ days: 30 });

    const adoptionCallArg = vi.mocked(dashboardService.fetchStatsAdoption).mock.calls[0][0];
    expect(adoptionCallArg).toMatchObject({ days: 30 });
  });

  it('affiche 0 pour Actions publiées si status published absent (AC2)', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockResolvedValue({
      ...mockCatalogueData,
      by_status: [{ status: 'draft', count: 5 }], // no 'published' entry
    });

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.getByText('Actions publiées')).toBeInTheDocument();
      // Value should be 0
      const cards = screen.getAllByRole('heading');
      const publishedCard = cards.find((el) => el.textContent === '0');
      expect(publishedCard).toBeTruthy();
    });
  });

  it('recharge les données quand les filtres changent (AC3)', async () => {
    const { rerender } = render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(dashboardService.fetchStatsCatalogue).toHaveBeenCalledTimes(1);
    });

    rerender(<AdminPlatformSection filters={{ days: 30 }} />);

    await waitFor(() => {
      expect(dashboardService.fetchStatsCatalogue).toHaveBeenCalledTimes(2);
    });
  });

  it('test_catalogue_charts_rendered : données valides → graphiques catalogue affichés (60.4 AC1)', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockResolvedValue({
      ...mockCatalogueData,
      evolution: [
        { week_start: '2026-01-01', created_count: 5, published_count: 3 },
      ],
    });

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.getByText('Répartition actions / workflows')).toBeInTheDocument();
      expect(screen.getByText('Évolution du catalogue')).toBeInTheDocument();
    });
  });

  it('test_catalogue_charts_hidden_when_403 : 403 → graphiques catalogue absents, adoption toujours présent (60.4 AC2, AC3)', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockRejectedValue(
      new ApiError('Forbidden', 403),
    );

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.queryByText('Répartition actions / workflows')).not.toBeInTheDocument();
      expect(screen.queryByText('Évolution du catalogue')).not.toBeInTheDocument();
      expect(screen.getByText('Adoption par profil')).toBeInTheDocument();
    });
  });

  it('test_adoption_chart_always_visible : graphique adoption visible même si catalogue interdit (60.4 AC3)', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockRejectedValue(
      new ApiError('Forbidden', 403),
    );

    render(<AdminPlatformSection filters={{ days: 14 }} />);

    await waitFor(() => {
      expect(screen.getByText('Adoption par profil')).toBeInTheDocument();
    });
  });
});
