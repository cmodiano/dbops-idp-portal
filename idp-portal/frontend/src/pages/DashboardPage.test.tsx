/**
 * Tests for DashboardPage (Story 5.1, Task 5.2).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import DashboardPage from './DashboardPage';
import { DashboardProvider } from '../contexts/DashboardContext';
import * as dashboardService from '../services/dashboard_service';
import * as executionService from '../services/execution_service';
import type {
  DashboardStats,
  DashboardRecentExecution,
  DashboardTimeSeriesPoint,
  ExecutionResponse,
  ExecutionStepResponse,
} from '../types/api';

vi.mock('../services/dashboard_service');
vi.mock('../services/execution_service');
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({
    steps: [],
    execution: null,
    loading: false,
    error: null,
    lastMessage: null,
  })),
}));
vi.mock('../hooks/useDashboardWebSocket', () => ({
  useDashboardWebSocket: vi.fn(() => ({
    connected: true,
    lastMessage: null,
    error: null,
  })),
}));

/** Wrapper with DashboardProvider and App for tests (Story 5.2, 5.5). */
function renderWithProvider(ui: React.ReactElement) {
  return render(<App><DashboardProvider>{ui}</DashboardProvider></App>);
}

const mockStats: DashboardStats = {
  executions_jour: 15,
  taux_succes_pct: 87.5,
  executions_en_cours: 3,
  executions_en_erreur: 2,
};

const mockRecent: DashboardRecentExecution[] = [
  {
    id: 1,
    action_name: 'Create PDB',
    user_display_name: 'Alice DBA',
    environment: 'dev',
    status: 'COMPLETED',
    created_at: '2026-01-30T10:00:00Z',
    platform: 'AAP',
    engine: 'Oracle',
  },
  {
    id: 2,
    action_name: 'Drop PDB',
    user_display_name: 'Bob Ops',
    environment: 'prod',
    status: 'FAILED',
    created_at: '2026-01-30T09:00:00Z',
    platform: 'GitHub Actions',
    engine: 'SQL Server',
  },
];

const mockTimeSeries: DashboardTimeSeriesPoint[] = [
  { date: '2026-01-28', success: 2, failed: 0 },
  { date: '2026-01-29', success: 5, failed: 1 },
  { date: '2026-01-30', success: 3, failed: 2 },
];

const mockExecution: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Create PDB',
  user_id: 1,
  environment: 'dev',
  parameters: {},
  status: 'COMPLETED',
  servicenow_change_id: null,
  started_at: '2026-01-30T10:00:00Z',
  completed_at: '2026-01-30T10:00:30Z',
  created_at: '2026-01-30T10:00:00Z',
};

const mockSteps: ExecutionStepResponse[] = [
  {
    id: 101,
    execution_id: 1,
    step_order: 1,
    step_name: 'Vault',
    step_type: 'vault',
    status: 'COMPLETED',
    started_at: '2026-01-30T10:00:00Z',
    completed_at: '2026-01-30T10:00:05Z',
    output: null,
    platform_job_id: null,
    error_message: null,
  },
];

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardService.fetchStats).mockResolvedValue(mockStats);
    vi.mocked(dashboardService.fetchRecent).mockResolvedValue(mockRecent);
    vi.mocked(dashboardService.fetchTimeSeries).mockResolvedValue(mockTimeSeries);
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
    vi.mocked(executionService.getExecutionSteps).mockResolvedValue(mockSteps);
  });

  it('renders page title', async () => {
    renderWithProvider(<DashboardPage />);

    expect(screen.getByRole('heading', { name: /Dashboard/i })).toBeInTheDocument();
  });

  it('displays statistics in StatCards (AC1)', async () => {
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Exécutions aujourd'hui")).toBeInTheDocument();
    });

    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('87.5%')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('displays recent executions table (AC2)', async () => {
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    expect(screen.getByText('Alice DBA')).toBeInTheDocument();
    expect(screen.getByText('Bob Ops')).toBeInTheDocument();
  });

  it('shows loading skeletons initially (AC6)', () => {
    vi.mocked(dashboardService.fetchStats).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );
    vi.mocked(dashboardService.fetchRecent).mockImplementation(
      () => new Promise(() => {})
    );

    renderWithProvider(<DashboardPage />);

    // Should have skeleton elements
    expect(document.querySelectorAll('.ant-skeleton').length).toBeGreaterThan(0);
  });

  it('shows error alert when stats fetch fails', async () => {
    vi.mocked(dashboardService.fetchStats).mockRejectedValue(new Error('Network error'));

    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Erreur de chargement des statistiques')).toBeInTheDocument();
    });
  });

  it('shows error alert when recent fetch fails', async () => {
    vi.mocked(dashboardService.fetchRecent).mockRejectedValue(new Error('Network error'));

    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Erreur de chargement')).toBeInTheDocument();
    });
  });

  it('opens modal when clicking on execution row (AC3)', async () => {
    const user = userEvent.setup();
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Create PDB'));

    await waitFor(() => {
      expect(screen.getByText('Exécution — Create PDB')).toBeInTheDocument();
    });

    // Verify getExecution and getExecutionSteps were called
    expect(executionService.getExecution).toHaveBeenCalledWith(1);
    expect(executionService.getExecutionSteps).toHaveBeenCalledWith(1);
  });

  it('displays ExecutionTimeline in modal (AC3)', async () => {
    const user = userEvent.setup();
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Create PDB'));

    await waitFor(() => {
      // ExecutionTimeline should render the step
      expect(screen.getByText('Vault')).toBeInTheDocument();
    });
  });

  it('shows modal error when execution fetch fails', async () => {
    const user = userEvent.setup();
    vi.mocked(executionService.getExecution).mockRejectedValue(new Error('Not found'));

    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Create PDB'));

    await waitFor(() => {
      expect(screen.getByText('Not found')).toBeInTheDocument();
    });
  });

  it('shows modal with close control when opening execution', async () => {
    const user = userEvent.setup();
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Create PDB'));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText('Exécution — Create PDB')).toBeInTheDocument();
    // Modal has a close control (Ant Design renders .ant-modal-close)
    const closeControl = document.querySelector('.ant-modal-close');
    expect(closeControl).toBeInTheDocument();
  });

  it('renders 4 StatCards in responsive grid (AC5)', async () => {
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Exécutions aujourd'hui")).toBeInTheDocument();
    });

    // Should have 4 stat cards
    expect(screen.getByText("Exécutions aujourd'hui")).toBeInTheDocument();
    expect(screen.getByText('Taux de succès (24h)')).toBeInTheDocument();
    expect(screen.getByText('En cours')).toBeInTheDocument();
    expect(screen.getByText('En erreur (24h)')).toBeInTheDocument();
  });

  it('shows spinning icon when executions are in progress', async () => {
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    // The SyncOutlined icon should have spin class when value > 0
    const spinIcon = document.querySelector('.anticon-sync');
    expect(spinIcon).toBeInTheDocument();
  });

  it('applies error variant to stat card when errors exist', async () => {
    renderWithProvider(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    // Find the error stat card (has red border)
    const errorCard = screen.getByText('En erreur (24h)').closest('.ant-card');
    expect(errorCard).toHaveStyle({ borderLeft: '4px solid #EF4444' });
  });
});
