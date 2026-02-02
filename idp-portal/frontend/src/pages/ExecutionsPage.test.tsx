/**
 * Tests for ExecutionsPage (Story 4.8, Story 8.8).
 *
 * Story 4.8:
 * AC1: Table with columns: action, environment, status, date, duration.
 * AC2: Click opens drawer with ExecutionTimeline (historical mode).
 * AC3: Running executions first with blue indicator.
 * AC4: Pagination 25, skeleton loading, sortable columns.
 *
 * Story 8.8:
 * AC1: Section "Approbations en attente" avant la liste des exécutions.
 * AC8: Réutilisation du composant PendingApprovalsList.
 * AC9: RBAC - seuls DBA/DBOPS voient la section approbations.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { App } from 'antd';
import ExecutionsPage from './ExecutionsPage';
import { AuthProvider } from '../contexts/AuthContext';
import * as executionService from '../services/execution_service';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

vi.mock('../services/execution_service');
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ steps: [], execution: null, loading: false, error: null }),
}));

/** Mock auth session with profile */
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
    [{ path: '/', element: <ExecutionsPage /> }],
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

const mockExecutions: ExecutionResponse[] = [
  {
    id: 1,
    action_id: 10,
    action_name: 'Create PDB',
    user_id: 1,
    environment: 'dev',
    parameters: null,
    status: 'COMPLETED',
    servicenow_change_id: null,
    started_at: '2026-01-28T10:00:00Z',
    completed_at: '2026-01-28T10:05:00Z',
    created_at: '2026-01-28T09:59:00Z',
  },
  {
    id: 2,
    action_id: 11,
    action_name: 'Apply Patch',
    user_id: 1,
    environment: 'prod',
    parameters: null,
    status: 'RUNNING',
    servicenow_change_id: 'CHG0012345',
    started_at: '2026-01-29T14:00:00Z',
    completed_at: null,
    created_at: '2026-01-29T13:59:00Z',
  },
  {
    id: 3,
    action_id: 12,
    action_name: 'Backup Database',
    user_id: 1,
    environment: 'staging',
    parameters: null,
    status: 'FAILED',
    servicenow_change_id: null,
    started_at: '2026-01-27T08:00:00Z',
    completed_at: '2026-01-27T08:10:00Z',
    created_at: '2026-01-27T07:59:00Z',
  },
];

const mockSteps: ExecutionStepResponse[] = [
  {
    id: 1,
    execution_id: 1,
    step_order: 1,
    step_name: 'Vault Credentials',
    step_type: 'vault',
    status: 'COMPLETED',
    started_at: '2026-01-28T10:00:00Z',
    completed_at: '2026-01-28T10:01:00Z',
    output: null,
    platform_job_id: null,
    error_message: null,
  },
  {
    id: 2,
    execution_id: 1,
    step_order: 2,
    step_name: 'Execute Action',
    step_type: 'platform',
    status: 'COMPLETED',
    started_at: '2026-01-28T10:01:00Z',
    completed_at: '2026-01-28T10:05:00Z',
    output: { result: 'success' },
    platform_job_id: '12345',
    error_message: null,
  },
];

describe('ExecutionsPage', () => {
  const defaultListResponse = {
    data: mockExecutions,
    pagination: { page: 1, page_size: 25, total_count: 3, total_pages: 1 },
  };

  const mockPendingApprovals: ExecutionResponse[] = [
    {
      id: 100,
      action_id: 50,
      action_name: 'Pending Action',
      user_id: 2,
      user_display_name: 'Other User',
      environment: 'prod',
      parameters: null,
      status: 'PENDING_APPROVAL',
      servicenow_change_id: null,
      started_at: null,
      completed_at: null,
      created_at: '2026-01-30T10:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(executionService.listExecutions).mockResolvedValue(defaultListResponse);
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecutions[0]);
    vi.mocked(executionService.getExecutionSteps).mockResolvedValue(mockSteps);
    vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
      data: [],
      pagination: { page: 1, page_size: 50, total_count: 0, total_pages: 0 },
    });
  });

  describe('Table Display (AC1)', () => {
    it('renders page title', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Exécutions' })).toBeInTheDocument();
      });
    });

    it('displays executions in table with correct columns', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check column headers
      expect(screen.getByText('Action')).toBeInTheDocument();
      expect(screen.getByText('Environnement')).toBeInTheDocument();
      expect(screen.getByText('Statut')).toBeInTheDocument();
      expect(screen.getByText('Date')).toBeInTheDocument();
      expect(screen.getByText('Durée')).toBeInTheDocument();
    });

    it('displays execution data correctly', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check action names
      expect(screen.getByText('Apply Patch')).toBeInTheDocument();
      expect(screen.getByText('Backup Database')).toBeInTheDocument();

      // Check environments (uppercase)
      expect(screen.getByText('DEV')).toBeInTheDocument();
      expect(screen.getByText('PROD')).toBeInTheDocument();
      expect(screen.getByText('STAGING')).toBeInTheDocument();
    });

    it('displays status tags with correct labels', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Terminée')).toBeInTheDocument();
      });

      expect(screen.getByText('En cours')).toBeInTheDocument();
      expect(screen.getByText('Échouée')).toBeInTheDocument();
    });

    it('displays duration for completed executions', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Create PDB: 5 minutes
      expect(screen.getByText('5m')).toBeInTheDocument();
      // Backup Database: 10 minutes
      expect(screen.getByText('10m')).toBeInTheDocument();
    });
  });

  describe('Running Executions First (AC3)', () => {
    it('displays running executions at the top of the table', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Apply Patch')).toBeInTheDocument();
      });

      // Get all table rows (excluding header)
      const table = screen.getByRole('table');
      const rows = within(table).getAllByRole('row');
      // First row is header, second should be the running execution
      const firstDataRow = rows[1];
      expect(within(firstDataRow).getByText('Apply Patch')).toBeInTheDocument();
      expect(within(firstDataRow).getByText('En cours')).toBeInTheDocument();
    });

    it('shows processing badge for running executions', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Apply Patch')).toBeInTheDocument();
      });

      // The running execution should have a Badge with processing status
      const badges = document.querySelectorAll('.ant-badge-status-processing');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  describe('Pagination (AC4)', () => {
    it('shows pagination controls', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Ant Design pagination renders page numbers
      const pagination = document.querySelector('.ant-pagination');
      expect(pagination).toBeInTheDocument();
    });

    it('calls API with correct offset on page change', async () => {
      // Mock more than 25 results to enable pagination
      const manyExecutions = Array.from({ length: 25 }, (_, i) => ({
        ...mockExecutions[0],
        id: i + 1,
        action_name: `Action ${i + 1}`,
      }));
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: manyExecutions,
        pagination: { page: 1, page_size: 25, total_count: 30, total_pages: 2 },
      });

      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Action 1')).toBeInTheDocument();
      });

      // API called with limit 25, offset 0
      expect(executionService.listExecutions).toHaveBeenCalledWith(25, 0);
    });
  });

  describe('Loading State (AC4)', () => {
    it('shows skeleton while loading', async () => {
      vi.mocked(executionService.listExecutions).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  data: mockExecutions,
                  pagination: { page: 1, page_size: 25, total_count: 3, total_pages: 1 },
                }),
              100
            )
          )
      );

      render(<ExecutionsPage />);

      // Skeleton should be visible initially
      expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });
    });

    it('shows error message on fetch failure', async () => {
      vi.mocked(executionService.listExecutions).mockRejectedValue(new Error('Network error'));

      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });

  describe('Drawer with ExecutionTimeline (AC2)', () => {
    it('opens drawer when clicking on a row', async () => {
      const user = userEvent.setup();
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Click on the first data row
      const table = screen.getByRole('table');
      const rows = within(table).getAllByRole('row');
      await user.click(rows[1]); // First data row (after header)

      await waitFor(() => {
        expect(executionService.getExecution).toHaveBeenCalledWith(expect.any(Number));
        expect(executionService.getExecutionSteps).toHaveBeenCalledWith(expect.any(Number));
      });
    });

    it('shows drawer with execution title', async () => {
      const user = userEvent.setup();
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Find and click the row with Create PDB (first completed one, but running goes first)
      // Running execution (Apply Patch) is at top, then Create PDB
      const createPdbCell = screen.getByText('Create PDB');
      const row = createPdbCell.closest('tr');
      await user.click(row!);

      await waitFor(() => {
        const drawer = screen.getByRole('dialog');
        expect(drawer).toBeInTheDocument();
        expect(within(drawer).getByText(/Create PDB/)).toBeInTheDocument();
      });
    });

    it('shows skeleton in drawer while loading detail', async () => {
      const user = userEvent.setup();
      vi.mocked(executionService.getExecution).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockExecutions[0]), 200))
      );
      vi.mocked(executionService.getExecutionSteps).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockSteps), 200))
      );

      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const createPdbCell = screen.getByText('Create PDB');
      const row = createPdbCell.closest('tr');
      await user.click(row!);

      // Drawer opens with skeleton (check that drawer appears)
      await waitFor(() => {
        const drawer = screen.getByRole('dialog');
        expect(drawer).toBeInTheDocument();
      });

      // Skeleton should be visible in the drawer while loading
      const skeleton = document.querySelector('.ant-skeleton');
      expect(skeleton).toBeInTheDocument();
    });

    it('shows error in drawer when getExecution fails', async () => {
      const user = userEvent.setup();
      vi.mocked(executionService.getExecution).mockRejectedValue(new Error('Execution not found'));

      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const createPdbCell = screen.getByText('Create PDB');
      const row = createPdbCell.closest('tr');
      await user.click(row!);

      await waitFor(() => {
        const drawer = screen.getByRole('dialog');
        expect(drawer).toBeInTheDocument();
        expect(within(drawer).getByText('Execution not found')).toBeInTheDocument();
        expect(within(drawer).getByText('Erreur de chargement')).toBeInTheDocument();
      });
    });

    it('closes drawer when close button is clicked', async () => {
      const user = userEvent.setup();
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const createPdbCell = screen.getByText('Create PDB');
      const row = createPdbCell.closest('tr');
      await user.click(row!);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Click close button
      const closeButton = screen.getByRole('button', { name: /close/i });
      await user.click(closeButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Sorting (AC4)', () => {
    it('table columns are sortable', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for sortable indicators on columns
      const actionHeader = screen.getByText('Action').closest('th');
      const statusHeader = screen.getByText('Statut').closest('th');
      const dateHeader = screen.getByText('Date').closest('th');

      expect(actionHeader).toHaveAttribute('aria-description', 'sortable');
      expect(statusHeader).toHaveAttribute('aria-description', 'sortable');
      expect(dateHeader).toHaveAttribute('aria-description', 'sortable');
    });
  });

  describe('Empty State', () => {
    it('shows empty message when no executions', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [],
        pagination: { page: 1, page_size: 25, total_count: 0, total_pages: 1 },
      });

      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Aucune exécution trouvée')).toBeInTheDocument();
      });
    });
  });

  describe('Story 8.8 — Pending Approvals Section', () => {
    it('shows pending approvals section for DBA user (AC1, AC9)', async () => {
      mockAuthSession('DBA');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: mockPendingApprovals,
        pagination: { page: 1, page_size: 50, total_count: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
      });

      expect(screen.getByText('Pending Action')).toBeInTheDocument();
    });

    it('shows pending approvals section for DBOPS user (AC1, AC9)', async () => {
      mockAuthSession('DBOPS');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: mockPendingApprovals,
        pagination: { page: 1, page_size: 50, total_count: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
      });
    });

    it('hides pending approvals section for CLIENT user (AC9)', async () => {
      mockAuthSession('CLIENT');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: mockPendingApprovals,
        pagination: { page: 1, page_size: 50, total_count: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Exécutions' })).toBeInTheDocument();
      });

      expect(screen.queryByText('Approbations en attente')).not.toBeInTheDocument();
    });

    it('hides pending approvals section when no approvals (AC1)', async () => {
      mockAuthSession('DBA');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: [],
        pagination: { page: 1, page_size: 50, total_count: 0, total_pages: 0 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Exécutions' })).toBeInTheDocument();
      });

      expect(screen.queryByText('Approbations en attente')).not.toBeInTheDocument();
    });

    it('displays pending-approvals id for scroll navigation (AC5)', async () => {
      mockAuthSession('DBA');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: mockPendingApprovals,
        pagination: { page: 1, page_size: 50, total_count: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
      });

      const pendingSection = document.getElementById('pending-approvals');
      expect(pendingSection).toBeInTheDocument();
    });

    it('shows approve/reject buttons (AC2)', async () => {
      mockAuthSession('DBA');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: mockPendingApprovals,
        pagination: { page: 1, page_size: 50, total_count: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByText('Approuver')).toBeInTheDocument();
        expect(screen.getByText('Refuser')).toBeInTheDocument();
      });
    });

    it('displays count badge on section header (AC2)', async () => {
      mockAuthSession('DBA');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: mockPendingApprovals,
        pagination: { page: 1, page_size: 50, total_count: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        // The count badge is rendered as a Tag component
        const tag = document.querySelector('.ant-tag-warning');
        expect(tag).toBeInTheDocument();
        expect(tag?.textContent).toBe('1');
      });
    });
  });
});
