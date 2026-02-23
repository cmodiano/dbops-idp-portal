/**
 * Tests for DashboardPage/AnalyticsPage (Story 8.3, Story 8.8, Story 9.10).
 *
 * DashboardPage now uses ReportingDashboard component.
 * Tests verify:
 * - Page title renders (now "Analytics" per Story 9.10)
 * - ReportingDashboard is rendered with charts
 *
 * Story 8.8 AC3: PendingApprovalsList removed from Dashboard (moved to ExecutionsPage)
 * Story 9.4: StatCards moved to ExecutionsPage
 * Story 9.10: Renamed to Analytics, DBOPS only
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { App } from 'antd';
import { createMemoryRouter, RouterProvider } from 'react-router';
import DashboardPage from './DashboardPage';
import { AuthProvider } from '../contexts/AuthContext';
import * as dashboardService from '../services/dashboard_service';
import type {
  DashboardStats,
  TechnologyStats,
  EnvironmentStats,
  DashboardTimeSeriesPoint,
} from '../types/api';

vi.mock('../services/dashboard_service');

// Mock recharts to avoid ResponsiveContainer dimension issues in tests
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
  };
});

const mockStats: DashboardStats = {
  executions_jour: 15,
  taux_succes_pct: 87.5,
  executions_en_cours: 3,
  executions_en_erreur: 2,
};

const mockTechStats: TechnologyStats[] = [
  { engine: 'Oracle', count: 50, success_rate: 95.0 },
  { engine: 'PostgreSQL', count: 30, success_rate: 88.5 },
];

const mockEnvStats: EnvironmentStats[] = [
  { environment: 'dev', count: 40, success_rate: 92.0 },
  { environment: 'prod', count: 20, success_rate: 95.0 },
];

const mockTimeSeries: DashboardTimeSeriesPoint[] = [
  { date: '2026-01-28', success: 2, failed: 0 },
  { date: '2026-01-29', success: 5, failed: 1 },
  { date: '2026-01-30', success: 3, failed: 2 },
];

/** Mock auth session */
function mockAuthSession(profile: string) {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: { access_token: 'token', token_type: 'bearer' } }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          id: 1,
          username: 'test.user',
          display_name: 'Test User',
          profile,
          navigation_tabs: ['dashboard', 'catalog', 'executions'],
        },
      }),
    });
}

/** Helper to render component with router and auth */
function renderWithProviders() {
  const router = createMemoryRouter(
    [{ path: '/', element: <DashboardPage /> }],
    { initialEntries: ['/'] }
  );
  return render(
    <App>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </App>
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthSession('dba');
    vi.mocked(dashboardService.fetchStats).mockResolvedValue(mockStats);
    vi.mocked(dashboardService.fetchStatsByTechnology).mockResolvedValue(mockTechStats);
    vi.mocked(dashboardService.fetchStatsByEnvironment).mockResolvedValue(mockEnvStats);
    vi.mocked(dashboardService.fetchTimeSeries).mockResolvedValue(mockTimeSeries);
    vi.mocked(dashboardService.fetchFilterOptions).mockResolvedValue({
      engines: ['Oracle', 'PostgreSQL'],
      environments: ['dev', 'staging', 'prod'],
      tags: [],
      statuses: [],
    });
  });

  it('renders page title (Story 9.10: renamed to Analytics)', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      // Story 9.10: Dashboard renamed to Analytics
      expect(screen.getByRole('heading', { name: /Statistiques/i })).toBeInTheDocument();
    });
  });

  // Story 9.4: StatCards moved to ExecutionsPage - no longer tested here
  // it('displays StatCards from ReportingDashboard (AC2)') - REMOVED

  it('displays period selector (AC6)', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      expect(screen.getByText('7 jours')).toBeInTheDocument();
      expect(screen.getByText('14 jours')).toBeInTheDocument();
      expect(screen.getByText('30 jours')).toBeInTheDocument();
      expect(screen.getByText('90 jours')).toBeInTheDocument();
    });
  });

  it('displays charts from ReportingDashboard (AC3, AC4, AC5)', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      expect(screen.getByText('Repartition par technologie')).toBeInTheDocument();
      expect(screen.getByText('Repartition par environnement')).toBeInTheDocument();
      expect(screen.getByText('Tendances temporelles')).toBeInTheDocument();
    });
  });

  it('displays link to executions page (AC8)', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      expect(screen.getByText(/Voir toutes les executions/i)).toBeInTheDocument();
    });

    const link = screen.getByRole('link', { name: /Voir toutes les executions/i });
    expect(link).toHaveAttribute('href', '/executions');
  });

  it('does not display Recent Executions table (AC8 - removed)', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      // Story 9.10: Wait for Analytics title
      expect(screen.getByRole('heading', { name: /Statistiques/i })).toBeInTheDocument();
    });

    // Should NOT have "Activite recente" card from old design
    expect(screen.queryByText('Activite recente')).not.toBeInTheDocument();
  });

  it('does not show pending approvals section (Story 8.8 AC3 - moved to ExecutionsPage)', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      // Story 9.10: Wait for Analytics title
      expect(screen.getByRole('heading', { name: /Statistiques/i })).toBeInTheDocument();
    });

    // Story 8.8 AC3: PendingApprovalsList removed from Dashboard
    expect(screen.queryByText('Approbations en attente')).not.toBeInTheDocument();
  });
});
