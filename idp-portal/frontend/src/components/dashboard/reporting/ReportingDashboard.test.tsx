/**
 * Tests for ReportingDashboard component (Story 8.3, AC1, AC2, AC6, AC8; Story 8.5; Story 8.6).
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { ReportingDashboard } from './ReportingDashboard';
import * as dashboardService from '../../../services/dashboard_service';

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

/** Helper to render component with router */
function renderWithRouter(component: React.ReactNode) {
  const router = createMemoryRouter(
    [{ path: '*', element: component }],
    { initialEntries: ['/'] }
  );
  return render(<RouterProvider router={router} />);
}

// Mock dashboard service
vi.mock('../../../services/dashboard_service', () => ({
  fetchStats: vi.fn(),
  fetchStatsByTechnology: vi.fn(),
  fetchStatsByEnvironment: vi.fn(),
  fetchTimeSeries: vi.fn(),
  fetchFilterOptions: vi.fn(),
  exportDashboardCSV: vi.fn(),
  exportDashboardPDF: vi.fn(),
  fetchComparison: vi.fn(),
}));

const mockStats = {
  executions_jour: 15,
  taux_succes_pct: 87.5,
  executions_en_cours: 3,
  executions_en_erreur: 2,
};

const mockTechStats = [
  { engine: 'Oracle', count: 50, success_rate: 95.0 },
  { engine: 'PostgreSQL', count: 30, success_rate: 88.5 },
];

const mockEnvStats = [
  { environment: 'dev', count: 40, success_rate: 92.0 },
  { environment: 'prod', count: 20, success_rate: 95.0 },
];

const mockTimeSeries = [
  { date: '2026-01-30', success: 10, failed: 2 },
  { date: '2026-01-31', success: 15, failed: 1 },
];

const mockFilterOptions = {
  engines: ['Oracle', 'PostgreSQL'],
  environments: ['dev', 'prod'],
  tags: ['patch', 'backup'],
  statuses: ['COMPLETED', 'FAILED'],
};

describe('ReportingDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardService.fetchStats).mockResolvedValue(mockStats);
    vi.mocked(dashboardService.fetchStatsByTechnology).mockResolvedValue(mockTechStats);
    vi.mocked(dashboardService.fetchStatsByEnvironment).mockResolvedValue(mockEnvStats);
    vi.mocked(dashboardService.fetchTimeSeries).mockResolvedValue(mockTimeSeries);
    vi.mocked(dashboardService.fetchFilterOptions).mockResolvedValue(mockFilterOptions);
    vi.mocked(dashboardService.exportDashboardCSV).mockResolvedValue();
    vi.mocked(dashboardService.exportDashboardPDF).mockResolvedValue();
  });

  it('renders StatCards with correct values (AC2)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument(); // executions_jour
    });

    expect(screen.getByText('87.5%')).toBeInTheDocument(); // taux_succes_pct
    expect(screen.getByText('3')).toBeInTheDocument(); // executions_en_cours
    expect(screen.getByText('2')).toBeInTheDocument(); // executions_en_erreur
  });

  it('renders period selector with options (AC6)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    expect(screen.getByText('7 jours')).toBeInTheDocument();
    expect(screen.getByText('14 jours')).toBeInTheDocument();
    expect(screen.getByText('30 jours')).toBeInTheDocument();
    expect(screen.getByText('90 jours')).toBeInTheDocument();
  });

  it('changes period and refetches data (AC6)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    await waitFor(() => {
      // fetchStats is called with a filters object containing days: 14
      expect(dashboardService.fetchStats).toHaveBeenCalled();
      const firstCall = vi.mocked(dashboardService.fetchStats).mock.calls[0][0];
      expect(firstCall).toMatchObject({ days: 14 });
    });

    // Change to 30 days
    await act(async () => {
      fireEvent.click(screen.getByText('30 jours'));
    });

    await waitFor(() => {
      // fetchStats should be called again with days: 30
      const calls = vi.mocked(dashboardService.fetchStats).mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toMatchObject({ days: 30 });
    });
  });

  it('renders link to executions page (AC8)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText(/Voir toutes les executions/i)).toBeInTheDocument();
    });

    const link = screen.getByRole('link', { name: /Voir toutes les executions/i });
    expect(link).toHaveAttribute('href', '/executions');
  });

  it('renders technology and environment charts (AC3, AC4)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText('Repartition par technologie')).toBeInTheDocument();
      expect(screen.getByText('Repartition par environnement')).toBeInTheDocument();
    });
  });

  it('renders trend line chart (AC5)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText('Tendances temporelles')).toBeInTheDocument();
    });
  });

  it('displays error alert on fetch failure', async () => {
    vi.mocked(dashboardService.fetchStats).mockRejectedValue(new Error('Network error'));

    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText('Erreur de chargement')).toBeInTheDocument();
    });
  });

  // Story 8.5: Export button integration test
  it('renders export button (Story 8.5, Task 10.6)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /exporter/i })).toBeInTheDocument();
    });
  });

  // Story 8.6: Comparison mode tests
  describe('Comparison Mode (Story 8.6)', () => {
    it('renders mode selector with Stats and Comparison options (AC1)', async () => {
      await act(async () => {
        renderWithRouter(<ReportingDashboard />);
      });

      expect(screen.getByText('Statistiques')).toBeInTheDocument();
      expect(screen.getByText('Comparaison')).toBeInTheDocument();
    });

    it('shows stats mode by default (AC1)', async () => {
      await act(async () => {
        renderWithRouter(<ReportingDashboard />);
      });

      // In stats mode, should see the period selector
      await waitFor(() => {
        expect(screen.getByText('7 jours')).toBeInTheDocument();
      });
    });

    it('switches to comparison mode when Comparaison is clicked (AC1)', async () => {
      await act(async () => {
        renderWithRouter(<ReportingDashboard />);
      });

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByText('Statistiques')).toBeInTheDocument();
      });

      // Click on Comparison mode
      await act(async () => {
        fireEvent.click(screen.getByText('Comparaison'));
      });

      // In comparison mode, should show compare button
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /comparer/i })).toBeInTheDocument();
      });
    });
  });
});
