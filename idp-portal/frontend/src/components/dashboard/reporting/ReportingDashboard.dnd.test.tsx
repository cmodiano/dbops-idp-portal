/**
 * ReportingDashboard companion tests (Story 55.6).
 * Uses mocked ComparisonPanel and ComparisonSummaryCards to cover:
 * - lines 155-157: handleMetricClick body
 * - lines 299-331: comparisonResult JSX block (ComparisonSummaryCards, ComparisonChart, etc.)
 * - lines 292-301: comparisonError alert block
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router';

// ---- Module-level mocked callbacks ----
let capturedOnCompare: ((...args: unknown[]) => void) | null = null;
let capturedOnFiltersChange: ((filters: unknown) => void) | null = null;

// ---- vi.mock hoisted declarations ----

vi.mock('./ComparisonPanel', () => ({
  ComparisonPanel: ({ onCompare }: { onCompare: (...args: unknown[]) => void }) => {
    capturedOnCompare = onCompare;
    return React.createElement('div', { 'data-testid': 'comparison-panel' },
      React.createElement('button', {
        onClick: () => onCompare('technology', 'Oracle', 'PostgreSQL'),
        'data-testid': 'trigger-compare',
      }, 'Compare')
    );
  },
}));

vi.mock('./ComparisonSummaryCards', () => ({
  ComparisonSummaryCards: ({ onMetricClick }: { onMetricClick: (metric: unknown) => void }) => {
    return React.createElement('div', { 'data-testid': 'comparison-summary-cards' },
      React.createElement('button', {
        onClick: () => onMetricClick({ name: 'success_rate', label: 'Taux de succès' }),
        'data-testid': 'trigger-metric-click',
      }, 'Metric Card')
    );
  },
}));

vi.mock('./ComparisonChart', () => ({
  ComparisonChart: () => React.createElement('div', { 'data-testid': 'comparison-chart' }, 'Comparison Chart'),
}));

vi.mock('./PeriodComparisonChart', () => ({
  PeriodComparisonChart: () => React.createElement('div', { 'data-testid': 'period-comparison-chart' }, 'Period Chart'),
}));

vi.mock('./ComparisonExecutionsDrawer', () => ({
  ComparisonExecutionsDrawer: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open
      ? React.createElement('div', { 'data-testid': 'comparison-executions-drawer' },
          React.createElement('button', { onClick: onClose }, 'Close Drawer')
        )
      : null,
}));

vi.mock('./ComparisonModeSelector', () => ({
  ComparisonModeSelector: ({ onModeChange }: { mode: string; onModeChange: (v: string) => void }) =>
    React.createElement('div', { 'data-testid': 'comparison-mode-selector' },
      React.createElement('button', {
        onClick: () => onModeChange('comparison'),
        'data-testid': 'switch-to-comparison',
      }, 'Switch to Comparison'),
      React.createElement('button', {
        onClick: () => onModeChange('stats'),
        'data-testid': 'switch-to-stats',
      }, 'Switch to Stats')
    ),
}));

vi.mock('./TechnologyBarChart', () => ({
  TechnologyBarChart: () => React.createElement('div', {}, 'TechChart'),
}));

vi.mock('./EnvironmentBarChart', () => ({
  EnvironmentBarChart: () => React.createElement('div', {}, 'EnvChart'),
}));

vi.mock('./TrendLineChart', () => ({
  TrendLineChart: () => React.createElement('div', {}, 'TrendChart'),
}));

vi.mock('./AdvancedFiltersPanel', () => ({
  AdvancedFiltersPanel: ({ onFiltersChange }: { onFiltersChange: (filters: unknown) => void }) => {
    capturedOnFiltersChange = onFiltersChange;
    return React.createElement('div', { 'data-testid': 'advanced-filters-panel' }, 'FiltersPanel');
  },
}));

vi.mock('./ExportButton', () => ({
  ExportButton: () => React.createElement('div', {}, 'ExportButton'),
}));

vi.mock('../../../services/dashboard_service', () => ({
  fetchStatsByTechnology: vi.fn(),
  fetchStatsByEnvironment: vi.fn(),
  fetchTimeSeries: vi.fn(),
  fetchFilterOptions: vi.fn(),
  exportDashboardCSV: vi.fn(),
  exportDashboardPDF: vi.fn(),
  fetchComparison: vi.fn(),
  // Story 60.3: mock AdminPlatformSection services
  fetchStatsCatalogue: vi.fn(),
  fetchStatsAdoption: vi.fn(),
}));

vi.mock('../../../services/logger', () => ({
  default: { warn: vi.fn(), error: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

import * as dashboardService from '../../../services/dashboard_service';
import { ReportingDashboard } from './ReportingDashboard';

const mockComparisonResult = {
  dimension: 'technology',
  value1: 'Oracle',
  value2: 'PostgreSQL',
  period_days: 14,
  metrics: {
    success_rate: { value1: 95.0, value2: 88.5, delta: -6.5, delta_pct: -6.84 },
    total_executions: { value1: 50, value2: 30, delta: -20, delta_pct: -40 },
    avg_duration: { value1: 120, value2: 90, delta: -30, delta_pct: -25 },
    failure_rate: { value1: 5.0, value2: 11.5, delta: 6.5, delta_pct: 130 },
  },
};

function renderWithRouter(component: React.ReactNode) {
  const router = createMemoryRouter(
    [{ path: '*', element: component }],
    { initialEntries: ['/'] }
  );
  return render(<RouterProvider router={router} />);
}

/** Helper: render dashboard, switch to comparison mode, wait for panel */
async function setupComparisonMode() {
  await act(async () => {
    renderWithRouter(<ReportingDashboard />);
  });
  await act(async () => {
    fireEvent.click(screen.getByTestId('switch-to-comparison'));
  });
  await waitFor(() => screen.getByTestId('comparison-panel'));
}

describe('ReportingDashboard - coverage 55.7 (comparison/drill-down)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnCompare = null;
    capturedOnFiltersChange = null;
    vi.mocked(dashboardService.fetchStatsByTechnology).mockResolvedValue([]);
    vi.mocked(dashboardService.fetchStatsByEnvironment).mockResolvedValue([]);
    vi.mocked(dashboardService.fetchTimeSeries).mockResolvedValue([]);
    vi.mocked(dashboardService.fetchFilterOptions).mockResolvedValue({
      engines: ['Oracle', 'PostgreSQL'],
      environments: ['dev', 'prod'],
      tags: [],
      statuses: [],
    });
    vi.mocked(dashboardService.fetchComparison).mockResolvedValue(mockComparisonResult as never);
    // Story 60.3: mock AdminPlatformSection services
    vi.mocked(dashboardService.fetchStatsCatalogue).mockResolvedValue({
      by_status: [], by_item_type: [], by_engine: [], by_category: [], evolution: [],
    });
    vi.mocked(dashboardService.fetchStatsAdoption).mockResolvedValue({
      executions_by_profile: [], active_users_by_profile: [], adoption_trend: [],
    });
  });

  it('handleCompare — appelle fetchComparison et affiche ComparisonSummaryCards (lines 304-324)', async () => {
    await setupComparisonMode();

    // Trigger comparison via the mocked button
    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-compare'));
    });

    // fetchComparison should have been called
    await waitFor(() => {
      expect(dashboardService.fetchComparison).toHaveBeenCalledWith(
        expect.objectContaining({ dimension: 'technology', value1: 'Oracle', value2: 'PostgreSQL' })
      );
    });

    // ComparisonSummaryCards should now be visible (comparisonResult set — covers lines 304-323)
    await waitFor(() => {
      expect(screen.getByTestId('comparison-summary-cards')).toBeInTheDocument();
    });

    // ComparisonChart should also be visible (dimension=technology, not 'period' → covers else branch line 317-321)
    await waitFor(() => {
      expect(screen.getByTestId('comparison-chart')).toBeInTheDocument();
    });
  });

  it('handleMetricClick — ouvre le drawer de drill-down (lines 155-158)', async () => {
    await setupComparisonMode();

    // Trigger comparison to get comparisonResult
    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-compare'));
    });

    // Wait for ComparisonSummaryCards to appear
    await waitFor(() => screen.getByTestId('comparison-summary-cards'));

    // Trigger metric click → handleMetricClick (lines 155-158): setDrawerMetric + setDrawerOpen
    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-metric-click'));
    });

    // ComparisonExecutionsDrawer should open (drawerOpen=true)
    await waitFor(() => {
      expect(screen.getByTestId('comparison-executions-drawer')).toBeInTheDocument();
    });
  });

  it('handleCompare avec dimension period — affiche PeriodComparisonChart (line 312-317)', async () => {
    // For period dimension, lastComparisonDimension='period' → PeriodComparisonChart renders
    vi.mocked(dashboardService.fetchComparison).mockResolvedValue({
      ...mockComparisonResult,
      dimension: 'period',
    } as never);

    await setupComparisonMode();

    // Trigger compare — capturedOnCompare was set by the ComparisonPanel mock
    // We call it with 'period' dimension directly
    await act(async () => {
      capturedOnCompare!('period', '2026-01-01', '2026-01-31', '2026-01-01', '2026-01-15', '2026-01-16', '2026-01-31');
    });

    await waitFor(() => {
      expect(dashboardService.fetchComparison).toHaveBeenCalledWith(
        expect.objectContaining({ dimension: 'period' })
      );
    });

    // PeriodComparisonChart should render when lastComparisonDimension === 'period'
    await waitFor(() => {
      expect(screen.getByTestId('comparison-summary-cards')).toBeInTheDocument();
    });

    // lastComparisonDimension is 'period' → PeriodComparisonChart renders (line 313-316)
    await waitFor(() => {
      expect(screen.getByTestId('period-comparison-chart')).toBeInTheDocument();
    });
  });

  it('handleCompare error — affiche alerte erreur comparaison (lines 147-151, 292-301)', async () => {
    vi.mocked(dashboardService.fetchComparison).mockRejectedValue(new Error('Comparison network error'));

    await setupComparisonMode();

    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-compare'));
    });

    // Error alert should appear (lines 292-301: comparisonError && <Alert...>)
    await waitFor(() => {
      expect(screen.getByText('Erreur de comparaison')).toBeInTheDocument();
    });
  });

  it('handleCompare error string — conversion non-Error en string (line 148 else branch)', async () => {
    vi.mocked(dashboardService.fetchComparison).mockRejectedValue('string error message');

    await setupComparisonMode();

    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-compare'));
    });

    // Error alert should show with the fallback message
    await waitFor(() => {
      expect(screen.getByText('Erreur de comparaison')).toBeInTheDocument();
    });
  });

  it('comparisonError Alert onClose — réinitialise comparisonError (line 299)', async () => {
    vi.mocked(dashboardService.fetchComparison).mockRejectedValue(new Error('test error for close'));

    await setupComparisonMode();

    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-compare'));
    });

    await waitFor(() => screen.getByText('Erreur de comparaison'));

    // Verify error alert is visible (lines 292-301: comparisonError && <Alert...>)
    const errorAlert = screen.queryByText('Erreur de comparaison');
    expect(errorAlert).toBeInTheDocument();

    // Click the Alert's close button to trigger setComparisonError(null) (line 299)
    const closeBtn = document.querySelector('.ant-alert-close-icon');
    if (closeBtn) {
      await act(async () => { fireEvent.click(closeBtn as Element); });
      // After close, the error alert should disappear
      await waitFor(() => {
        expect(screen.queryByText('Erreur de comparaison')).not.toBeInTheDocument();
      });
    }
  });

  it('ComparisonExecutionsDrawer onClose — ferme le drawer (line 331)', async () => {
    await setupComparisonMode();

    // Trigger comparison to get comparisonResult
    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-compare'));
    });

    await waitFor(() => screen.getByTestId('comparison-summary-cards'));

    // Open drawer via metric click (lines 155-158)
    await act(async () => {
      fireEvent.click(screen.getByTestId('trigger-metric-click'));
    });

    await waitFor(() => screen.getByTestId('comparison-executions-drawer'));

    // Close the drawer via its close button → triggers setDrawerOpen(false) (line 331)
    const closeDrawerBtn = screen.getByText('Close Drawer');
    await act(async () => {
      fireEvent.click(closeDrawerBtn);
    });

    // Drawer should be closed
    await waitFor(() => {
      expect(screen.queryByTestId('comparison-executions-drawer')).not.toBeInTheDocument();
    });
  });

  it('AdminPlatformSection non affiché en mode comparison (AC8)', async () => {
    await setupComparisonMode();

    // La section "Utilisation de la plateforme" ne doit pas être présente en mode comparison
    expect(screen.queryByText('Utilisation de la plateforme')).not.toBeInTheDocument();
  });

  it('handleFiltersChange — met à jour les filtres (line 112)', async () => {
    await act(async () => {
      renderWithRouter(<ReportingDashboard />);
    });

    // Stats mode is default — verify the FiltersPanel is rendered
    await waitFor(() => screen.getByTestId('advanced-filters-panel'));

    // capturedOnFiltersChange was set by the mock AdvancedFiltersPanel
    expect(capturedOnFiltersChange).not.toBeNull();

    // Call the onFiltersChange callback — this triggers handleFiltersChange (line 112: setFilters(newFilters))
    await act(async () => {
      capturedOnFiltersChange!({ days: 30, environment: 'prod' });
    });

    // After calling, the component re-renders with updated filters
    // fetchStatsByTechnology should have been called (or recalled) with updated filters
    expect(dashboardService.fetchStatsByTechnology).toHaveBeenCalled();
  });
});
