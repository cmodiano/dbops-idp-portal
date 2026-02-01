/**
 * Tests for DashboardPage (Story 8.3).
 *
 * DashboardPage now uses ReportingDashboard component.
 * Tests verify:
 * - Page title renders
 * - ReportingDashboard is rendered
 * - PendingApprovalsList is shown for DBA/DBOPS profiles
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { App } from 'antd';
import { createMemoryRouter, RouterProvider } from 'react-router';
import DashboardPage from './DashboardPage';
import { AuthProvider } from '../contexts/AuthContext';
import * as dashboardService from '../services/dashboard_service';
import * as executionService from '../services/execution_service';
import type {
  DashboardStats,
  TechnologyStats,
  EnvironmentStats,
  DashboardTimeSeriesPoint,
} from '../types/api';

vi.mock('../services/dashboard_service');
vi.mock('../services/execution_service');

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
    vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
      data: [],
      pagination: { page: 1, page_size: 50, total: 0, total_pages: 0 },
    });
  });

  it('renders page title', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Dashboard/i })).toBeInTheDocument();
    });
  });

  it('displays StatCards from ReportingDashboard (AC2)', async () => {
    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument(); // executions_jour
    });

    expect(screen.getByText('87.5%')).toBeInTheDocument(); // taux_succes_pct
    expect(screen.getByText('3')).toBeInTheDocument(); // executions_en_cours
    expect(screen.getByText('2')).toBeInTheDocument(); // executions_en_erreur
  });

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
      expect(screen.getByText('15')).toBeInTheDocument();
    });

    // Should NOT have "Activite recente" card from old design
    expect(screen.queryByText('Activite recente')).not.toBeInTheDocument();
  });

  it('shows pending approvals for DBA profile (Story 7.4)', async () => {
    vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
      data: [
        {
          id: 1,
          action_id: 10,
          action_name: 'Test Action',
          user_id: 2,
          user_display_name: 'Test User',
          environment: 'prod',
          parameters: {},
          status: 'PENDING_APPROVAL',
          servicenow_change_id: null,
          started_at: null,
          completed_at: null,
          created_at: '2026-01-30T10:00:00Z',
        },
      ],
      pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
    });

    await act(async () => {
      renderWithProviders();
    });

    await waitFor(() => {
      expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
    });
  });
});
