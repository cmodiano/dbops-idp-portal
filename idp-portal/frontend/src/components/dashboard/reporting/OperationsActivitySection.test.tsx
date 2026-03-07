/**
 * Tests for OperationsActivitySection component (Story 60.9, AC9, AC10 + Story 60.10).
 *
 * Covers:
 * - Rendering StatCards with valid data
 * - null avg_execution_time_s → displays "N/D"
 * - Loading state (Skeletons)
 * - Network error → Alert displayed
 * - Filters transmitted to service functions
 * - Zero approved_count displayed correctly
 * - Charts displayed when data loaded (Story 60.10)
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { OperationsActivitySection } from './OperationsActivitySection';
import * as dashboardService from '../../../services/dashboard_service';

vi.mock('./TopActionsByExecutionChart', () => ({
  TopActionsByExecutionChart: ({ data, loading }: { data: unknown[]; loading?: boolean }) =>
    loading ? null : <div data-testid="top-execution-chart">{data.length} items</div>,
}));

vi.mock('./TopActionsByFailureChart', () => ({
  TopActionsByFailureChart: ({ data, loading }: { data: unknown[]; loading?: boolean }) =>
    loading ? null : <div data-testid="top-failure-chart">{data.length} items</div>,
}));

vi.mock('./ApprobationsRatioChart', () => ({
  ApprobationsRatioChart: ({ loading }: { approved: number; loading?: boolean }) =>
    loading ? null : <div data-testid="approbations-chart" />,
}));

vi.mock('../../../services/dashboard_service', () => ({
  fetchStatsOperations: vi.fn(),
  fetchStatsApprobations: vi.fn(),
  fetchStatsPlanifiees: vi.fn(),
}));

const mockOperationsData = {
  avg_execution_time_s: 12.5,
  top_actions_by_execution: [{ action_id: 1, action_name: 'Deploy', execution_count: 42 }],
  top_actions_by_failure: [],
  by_platform: [{ platform: 'AAP', count: 30 }],
};

const mockApprobationsData = {
  approved_count: 8,
  rejected_count: 2,
  approval_rate: 80.0,
  avg_approval_delay_s: 300.0,
};

const mockPlanifieesData = {
  scheduled_count: 15,
  manual_count: 27,
  scheduled_rate: 35.7,
  by_recurrence_type: [{ pattern_type: 'daily', count: 10 }],
};

describe('OperationsActivitySection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardService.fetchStatsOperations).mockResolvedValue(mockOperationsData);
    vi.mocked(dashboardService.fetchStatsApprobations).mockResolvedValue(mockApprobationsData);
    vi.mocked(dashboardService.fetchStatsPlanifiees).mockResolvedValue(mockPlanifieesData);
  });

  it('affiche les StatCards avec les données', async () => {
    render(<OperationsActivitySection filters={{ days: 14 }} />);
    await waitFor(() => {
      expect(screen.getByText("Durée moy. d'exéc.")).toBeInTheDocument();
      expect(screen.getByText('Approuvées')).toBeInTheDocument();
      expect(screen.getByText('Planifiées')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();   // approved_count
      expect(screen.getByText('15')).toBeInTheDocument();  // scheduled_count
    });
  });

  it('affiche N/D si avg_execution_time_s est null', async () => {
    vi.mocked(dashboardService.fetchStatsOperations).mockResolvedValue({
      ...mockOperationsData,
      avg_execution_time_s: null,
    });
    render(<OperationsActivitySection filters={{ days: 14 }} />);
    await waitFor(() => {
      expect(screen.getByText('N/D')).toBeInTheDocument();
    });
  });

  it('affiche des Skeletons pendant le chargement (task 5.4)', () => {
    vi.mocked(dashboardService.fetchStatsOperations).mockReturnValue(new Promise(() => {}));
    vi.mocked(dashboardService.fetchStatsApprobations).mockReturnValue(new Promise(() => {}));
    vi.mocked(dashboardService.fetchStatsPlanifiees).mockReturnValue(new Promise(() => {}));

    render(<OperationsActivitySection filters={{ days: 14 }} />);

    // StatCards render with loading={true} while promises are pending → Skeleton elements shown
    const skeletons = document.querySelectorAll('.ant-skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("affiche une Alert en cas d'erreur réseau", async () => {
    vi.mocked(dashboardService.fetchStatsOperations).mockRejectedValue(
      new Error('Network error')
    );
    render(<OperationsActivitySection filters={{ days: 14 }} />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('transmet les filtres aux services', async () => {
    render(<OperationsActivitySection filters={{ days: 30 }} />);
    await waitFor(() => {
      expect(dashboardService.fetchStatsOperations).toHaveBeenCalledWith(expect.objectContaining({ days: 30 }));
      expect(dashboardService.fetchStatsApprobations).toHaveBeenCalledWith(expect.objectContaining({ days: 30 }));
      expect(dashboardService.fetchStatsPlanifiees).toHaveBeenCalledWith(expect.objectContaining({ days: 30 }));
    });
  });

  it('affiche 0 pour approved_count quand aucune approbation', async () => {
    vi.mocked(dashboardService.fetchStatsApprobations).mockResolvedValue({
      approved_count: 0,
      rejected_count: 0,
      approval_rate: null,
      avg_approval_delay_s: null,
    });
    render(<OperationsActivitySection filters={{ days: 14 }} />);
    await waitFor(() => {
      expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('affiche le titre de section', async () => {
    render(<OperationsActivitySection filters={{ days: 14 }} />);
    await waitFor(() => {
      expect(screen.getByText('Activité opérationnelle')).toBeInTheDocument();
    });
  });

  it('les autres sections restent visibles si un seul endpoint échoue', async () => {
    vi.mocked(dashboardService.fetchStatsOperations).mockRejectedValue(
      new Error('Network error')
    );
    render(<OperationsActivitySection filters={{ days: 14 }} />);
    await waitFor(() => {
      // Error alert shown
      expect(screen.getByRole('alert')).toBeInTheDocument();
      // Other cards still rendered
      expect(screen.getByText('8')).toBeInTheDocument();   // approved_count
      expect(screen.getByText('15')).toBeInTheDocument();  // scheduled_count
    });
  });

  it('affiche les graphiques quand les données sont chargées', async () => {
    render(<OperationsActivitySection filters={{ days: 14 }} />);
    await waitFor(() => {
      expect(screen.getByTestId('top-execution-chart')).toBeInTheDocument();
      expect(screen.getByTestId('top-failure-chart')).toBeInTheDocument();
      expect(screen.getByTestId('approbations-chart')).toBeInTheDocument();
    });
  });
});
