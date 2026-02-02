/**
 * Tests for ExecutionsPage (Story 4.8, Story 8.8, Story 9.4, Story 9.9).
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
 *
 * Story 9.4:
 * AC1: 4 StatCards déplacées du Dashboard vers Exécutions.
 * AC3: Stats reflètent le scope actif (mine/all).
 * AC4: Responsive layout xs=24 sm=12 md=6.
 * AC5: Loading skeleton pour les cards.
 *
 * Story 9.9:
 * AC1-AC3: Status column with Badge indicators (pulsing for running, fixed for terminal).
 * AC4: Technologie column with engine icons.
 * AC5: Plateforme column with integration icons.
 * AC7: Column order: Statut, Action, Technologie, Plateforme, [Utilisateur], Environnement, Date, Durée.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { App } from 'antd';
import ExecutionsPage from './ExecutionsPage';
import { AuthProvider } from '../contexts/AuthContext';
import { ThemeProvider } from '../contexts/ThemeContext';
import * as executionService from '../services/execution_service';
import type { ExecutionResponse, ExecutionStepResponse, DashboardStats } from '../types/api';

vi.mock('../services/execution_service');
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ steps: [], execution: null, loading: false, error: null }),
}));

/** Helper to wrap component with ThemeProvider (Story 8.9: ExecutionsTabs needs ThemeContext) */
function TestWrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

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
    <ThemeProvider>
      <App>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </App>
    </ThemeProvider>
  );
}

/** Simpler render helper with just ThemeProvider for tests without auth */
function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
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
    // Story 9.4: Mock fetchExecutionStats
    vi.mocked(executionService.fetchExecutionStats).mockResolvedValue({
      executions_jour: 10,
      taux_succes_pct: 85.5,
      executions_en_cours: 3,
      executions_en_erreur: 2,
    });
  });

  describe('Table Display (AC1)', () => {
    it('renders page title', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Exécutions' })).toBeInTheDocument();
      });
    });

    it('displays executions in table with correct columns', async () => {
      renderWithTheme(<ExecutionsPage />);

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
      renderWithTheme(<ExecutionsPage />);

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

    it('displays status badges with tooltips (Story 9.9 AC1-AC3)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Story 9.9: Status is now displayed as Badges (processing, success, error) not Tags with text
      // The Badge component renders with specific classes based on status
      const badges = document.querySelectorAll('.ant-badge');
      expect(badges.length).toBeGreaterThan(0);

      // Check for processing badge (RUNNING execution)
      const processingBadges = document.querySelectorAll('.ant-badge-status-processing');
      expect(processingBadges.length).toBeGreaterThan(0);

      // Check for success badge (COMPLETED execution)
      const successBadges = document.querySelectorAll('.ant-badge-status-success');
      expect(successBadges.length).toBeGreaterThan(0);

      // Check for error badge (FAILED execution)
      const errorBadges = document.querySelectorAll('.ant-badge-status-error');
      expect(errorBadges.length).toBeGreaterThan(0);
    });

    it('displays duration for completed executions', async () => {
      renderWithTheme(<ExecutionsPage />);

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
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Apply Patch')).toBeInTheDocument();
      });

      // Get all table rows (excluding header)
      const table = screen.getByRole('table');
      const rows = within(table).getAllByRole('row');
      // First row is header, second should be the running execution
      const firstDataRow = rows[1];
      expect(within(firstDataRow).getByText('Apply Patch')).toBeInTheDocument();
      // Story 9.9: Status is now a Badge, not text. Check for processing badge in the row.
      expect(within(firstDataRow).queryByText('.ant-badge-status-processing')).not.toBeNull;
      const processingBadge = firstDataRow.querySelector('.ant-badge-status-processing');
      expect(processingBadge).toBeInTheDocument();
    });

    it('shows processing badge for running executions', async () => {
      renderWithTheme(<ExecutionsPage />);

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
      renderWithTheme(<ExecutionsPage />);

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

      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Action 1')).toBeInTheDocument();
      });

      // API called with limit 25, offset 0, scope 'mine'
      expect(executionService.listExecutions).toHaveBeenCalledWith(25, 0, 'mine');
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

      renderWithTheme(<ExecutionsPage />);

      // Skeleton should be visible initially
      expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });
    });

    it('shows error message on fetch failure', async () => {
      vi.mocked(executionService.listExecutions).mockRejectedValue(new Error('Network error'));

      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });

  describe('Drawer with ExecutionTimeline (AC2)', () => {
    it('opens drawer when clicking on a row', async () => {
      const user = userEvent.setup();
      renderWithTheme(<ExecutionsPage />);

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
      renderWithTheme(<ExecutionsPage />);

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

      renderWithTheme(<ExecutionsPage />);

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

      renderWithTheme(<ExecutionsPage />);

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
      renderWithTheme(<ExecutionsPage />);

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
    it('table columns are sortable (Story 9.9 AC7: only Action and Date)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for sortable indicators on columns
      const actionHeader = screen.getByText('Action').closest('th');
      const statusHeader = screen.getByText('Statut').closest('th');
      const dateHeader = screen.getByText('Date').closest('th');

      // Story 9.9 AC7: Action and Date are sortable
      expect(actionHeader).toHaveAttribute('aria-description', 'sortable');
      expect(dateHeader).toHaveAttribute('aria-description', 'sortable');

      // Story 9.9 AC7: Statut is NOT sortable (no aria-description='sortable')
      expect(statusHeader).not.toHaveAttribute('aria-description', 'sortable');
    });
  });

  describe('Empty State', () => {
    it('shows empty message when no executions', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [],
        pagination: { page: 1, page_size: 25, total_count: 0, total_pages: 1 },
      });

      renderWithTheme(<ExecutionsPage />);

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

  describe('Story 8.9 — ExecutionsTabs Integration', () => {
    it('shows ExecutionsTabs for DBA user (AC1)', async () => {
      mockAuthSession('DBA');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: /Mes exécutions/i })).toBeInTheDocument();
      });
    });

    it('shows only "Mes exécutions" tab for CLIENT user (AC6)', async () => {
      mockAuthSession('CLIENT');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Mes exécutions/i })).toBeInTheDocument();
      });

      expect(screen.queryByRole('tab', { name: /Toutes les exécutions/i })).not.toBeInTheDocument();
    });

    it('calls listExecutions with scope=mine by default (AC3)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(executionService.listExecutions).toHaveBeenCalledWith(25, 0, 'mine');
      });
    });

    it('calls listExecutions with scope=all when "Toutes les exécutions" tab is clicked (AC2)', async () => {
      mockAuthSession('DBA');
      const user = userEvent.setup();

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /Toutes les exécutions/i }));

      await waitFor(() => {
        expect(executionService.listExecutions).toHaveBeenCalledWith(25, 0, 'all');
      });
    });

    it('resets pagination when changing tabs (AC4)', async () => {
      mockAuthSession('DBA');
      const user = userEvent.setup();

      // Mock 30 results to enable multiple pages
      const manyExecutions = Array.from({ length: 25 }, (_, i) => ({
        ...mockExecutions[0],
        id: i + 1,
        action_name: `Action ${i + 1}`,
      }));
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: manyExecutions,
        pagination: { page: 1, page_size: 25, total_count: 30, total_pages: 2 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });

      // Switch tabs - should call API with offset 0 (page 1)
      await user.click(screen.getByRole('tab', { name: /Toutes les exécutions/i }));

      await waitFor(() => {
        // Last call should be with offset 0 (reset to page 1)
        const lastCall = vi.mocked(executionService.listExecutions).mock.calls.slice(-1)[0];
        expect(lastCall[1]).toBe(0); // offset should be 0
      });
    });

    it('shows "Utilisateur" column only for scope=all (AC9)', async () => {
      const mockAllExecutions: ExecutionResponse[] = [
        {
          id: 1,
          action_id: 10,
          action_name: 'Create PDB',
          user_id: 2,
          user_display_name: 'John Doe',
          environment: 'dev',
          parameters: null,
          status: 'COMPLETED',
          servicenow_change_id: null,
          started_at: '2026-01-28T10:00:00Z',
          completed_at: '2026-01-28T10:05:00Z',
          created_at: '2026-01-28T09:59:00Z',
        },
      ];

      mockAuthSession('DBA');
      const user = userEvent.setup();

      // First call returns user's executions (scope=mine)
      vi.mocked(executionService.listExecutions)
        .mockResolvedValueOnce(defaultListResponse)
        .mockResolvedValueOnce({
          data: mockAllExecutions,
          pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
        });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });

      // Initially scope=mine, should NOT have "Utilisateur" column
      expect(screen.queryByText('Utilisateur')).not.toBeInTheDocument();

      // Switch to scope=all
      await user.click(screen.getByRole('tab', { name: /Toutes les exécutions/i }));

      await waitFor(() => {
        // Now should have "Utilisateur" column header
        expect(screen.getByText('Utilisateur')).toBeInTheDocument();
      });

      // And should display user_display_name value
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    it('displays "Utilisateur inconnu" when user_display_name is null (AC9)', async () => {
      const mockAllExecutionsNoUser: ExecutionResponse[] = [
        {
          id: 1,
          action_id: 10,
          action_name: 'Create PDB',
          user_id: 2,
          user_display_name: null,
          environment: 'dev',
          parameters: null,
          status: 'COMPLETED',
          servicenow_change_id: null,
          started_at: '2026-01-28T10:00:00Z',
          completed_at: '2026-01-28T10:05:00Z',
          created_at: '2026-01-28T09:59:00Z',
        },
      ];

      mockAuthSession('DBA');
      const user = userEvent.setup();

      vi.mocked(executionService.listExecutions)
        .mockResolvedValueOnce(defaultListResponse)
        .mockResolvedValueOnce({
          data: mockAllExecutionsNoUser,
          pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
        });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /Toutes les exécutions/i }));

      await waitFor(() => {
        expect(screen.getByText('Utilisateur inconnu')).toBeInTheDocument();
      });
    });

    it('"Mes exécutions" tab is active by default', async () => {
      mockAuthSession('DBA');

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        const mineTab = screen.getByRole('tab', { name: /Mes exécutions/i });
        expect(mineTab).toHaveAttribute('aria-selected', 'true');
      });
    });
  });

  describe('Story 9.4 — StatCards Section', () => {
    it('displays 4 StatCards with correct labels (AC1)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
        expect(screen.getByText('Taux de succès')).toBeInTheDocument();
        // "En cours" appears in both StatCard label and table status tag
        const enCoursElements = screen.getAllByText('En cours');
        expect(enCoursElements.length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('En erreur')).toBeInTheDocument();
      });
    });

    it('StatCards display values from API (AC3)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('10')).toBeInTheDocument(); // executions_jour
        expect(screen.getByText('85.5%')).toBeInTheDocument(); // taux_succes_pct
        expect(screen.getByText('3')).toBeInTheDocument(); // executions_en_cours
        expect(screen.getByText('2')).toBeInTheDocument(); // executions_en_erreur
      });
    });

    it('fetchExecutionStats is called with scope=mine by default (AC3)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(executionService.fetchExecutionStats).toHaveBeenCalledWith('mine');
      });
    });

    it('fetchExecutionStats is called with scope=all when tab changes (AC3)', async () => {
      mockAuthSession('DBA');
      const user = userEvent.setup();

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /Toutes les exécutions/i }));

      await waitFor(() => {
        expect(executionService.fetchExecutionStats).toHaveBeenCalledWith('all');
      });
    });

    it('StatCards are displayed BEFORE pending approvals section (AC1)', async () => {
      mockAuthSession('DBA');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: [
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
        ],
        pagination: { page: 1, page_size: 50, total_count: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
        expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
      });

      // Check DOM order: StatCards should appear before pending approvals
      const statsCard = screen.getByText('Exécutions du jour').closest('.ant-card');
      const approvalsSection = document.getElementById('pending-approvals');

      if (statsCard && approvalsSection) {
        // Compare positions - stats should come before approvals
        const statsPosition = statsCard.compareDocumentPosition(approvalsSection);
        expect(statsPosition & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      }
    });

    it('shows loading skeleton while stats are loading (AC5)', async () => {
      vi.mocked(executionService.fetchExecutionStats).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  executions_jour: 10,
                  taux_succes_pct: 85.5,
                  executions_en_cours: 3,
                  executions_en_erreur: 2,
                }),
              200
            )
          )
      );

      renderWithTheme(<ExecutionsPage />);

      // Check that skeleton is visible (StatCard uses Skeleton internally when loading=true)
      await waitFor(() => {
        const skeletons = document.querySelectorAll('.ant-skeleton');
        expect(skeletons.length).toBeGreaterThan(0);
      });
    });

    it('handles fetchExecutionStats error gracefully (AC5)', async () => {
      vi.mocked(executionService.fetchExecutionStats).mockRejectedValue(new Error('Network error'));

      renderWithTheme(<ExecutionsPage />);

      // Should display fallback values (0) instead of crashing
      await waitFor(() => {
        expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
      });

      // Table should still be usable
      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });
    });

    it('responsive layout has correct Col spans (AC4)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
      });

      // Check that Col elements have correct responsive classes
      const cols = document.querySelectorAll('.ant-col');
      const statCardCols = Array.from(cols).filter(col =>
        col.classList.contains('ant-col-xs-24') &&
        col.classList.contains('ant-col-sm-12') &&
        col.classList.contains('ant-col-md-6')
      );

      // Should have 4 StatCard columns with responsive breakpoints
      expect(statCardCols.length).toBe(4);
    });

    it('SyncOutlined icon spins when executions_en_cours > 0 (AC1)', async () => {
      vi.mocked(executionService.fetchExecutionStats).mockResolvedValue({
        executions_jour: 10,
        taux_succes_pct: 85.5,
        executions_en_cours: 3, // > 0, should spin
        executions_en_erreur: 2,
      });

      renderWithTheme(<ExecutionsPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
      });

      // Allow time for spin to be applied
      await waitFor(() => {
        // Check for spin class on SyncOutlined icon (Ant Design adds spin class to span)
        const syncIcons = document.querySelectorAll('[class*="anticon-sync"]');
        const hasSpinIcon = Array.from(syncIcons).some(icon => icon.classList.contains('anticon-spin'));
        expect(hasSpinIcon).toBe(true);
      });
    });

    it('SyncOutlined icon does not spin when executions_en_cours = 0', async () => {
      vi.mocked(executionService.fetchExecutionStats).mockResolvedValue({
        executions_jour: 10,
        taux_succes_pct: 100,
        executions_en_cours: 0, // = 0, should NOT spin
        executions_en_erreur: 0,
      });

      renderWithTheme(<ExecutionsPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
      });

      // Check that sync icon exists but does not have spin class
      const syncIcons = document.querySelectorAll('[class*="anticon-sync"]');
      const hasSpinIcon = Array.from(syncIcons).some(icon => icon.classList.contains('anticon-spin'));
      expect(hasSpinIcon).toBe(false);
    });
  });

  // === Story 9.9: Table Column Improvements ===
  describe('Story 9.9 — Table Column Improvements', () => {
    it('renders Statut column as first column (AC1)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Get table headers
      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');

      // First column should be "Statut"
      expect(headers[0]).toHaveTextContent('Statut');
    });

    it('renders columns in correct order (AC7)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');

      // Story 9.9 AC7: Order should be Statut, Action, Technologie, Plateforme, Environnement, Date, Durée
      // (Utilisateur only visible for scope=all)
      expect(headers[0]).toHaveTextContent('Statut');
      expect(headers[1]).toHaveTextContent('Action');
      expect(headers[2]).toHaveTextContent('Technologie');
      expect(headers[3]).toHaveTextContent('Plateforme');
      expect(headers[4]).toHaveTextContent('Environnement');
      expect(headers[5]).toHaveTextContent('Date');
      expect(headers[6]).toHaveTextContent('Durée');
    });

    it('renders Technologie column with engine icons (AC4)', async () => {
      // Mock execution with engine metadata
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            engine: 'Oracle',
            item_type: 'action',
          },
        ],
        pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
      });

      const { container } = renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for DatabaseOutlined icon (Oracle)
      const databaseIcon = container.querySelector('[class*="anticon-database"]');
      expect(databaseIcon).toBeInTheDocument();
    });

    it('renders workflow icon when item_type is workflow (AC4)', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            engine: null,
            item_type: 'workflow',
          },
        ],
        pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
      });

      const { container } = renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for ApartmentOutlined icon (workflow)
      const workflowIcon = container.querySelector('[class*="anticon-apartment"]');
      expect(workflowIcon).toBeInTheDocument();
    });

    it('renders Plateforme column with integration avatar (AC5)', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            integration_id: 1,
            integration_name: 'AAP Production',
            integration_icon: '/icons/aap.png',
          },
        ],
        pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
      });

      const { container } = renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for Avatar component
      const avatar = container.querySelector('.ant-avatar');
      expect(avatar).toBeInTheDocument();
    });

    it('renders fallback for missing integration (AC5)', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            engine: null, // Also null for this test
            integration_id: null,
            integration_name: null,
            integration_icon: null,
          },
        ],
        pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
      });

      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for dash fallback (there should be 2: one for Technologie, one for Plateforme)
      const dashElements = screen.getAllByText('—');
      expect(dashElements.length).toBeGreaterThanOrEqual(2);
    });

    it('Technologie and Plateforme columns are not sortable (AC7)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const technologieHeader = screen.getByText('Technologie').closest('th');
      const plateformeHeader = screen.getByText('Plateforme').closest('th');

      // These columns should NOT have sortable attribute
      expect(technologieHeader).not.toHaveAttribute('aria-description', 'sortable');
      expect(plateformeHeader).not.toHaveAttribute('aria-description', 'sortable');
    });

    it('includes 8 columns when scope=all (with Utilisateur)', async () => {
      mockAuthSession('DBA');

      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            user_display_name: 'Test User',
          },
        ],
        pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
      });

      renderWithProviders();

      // Wait for auth and data
      await waitFor(() => {
        expect(screen.getByText('Toutes les exécutions')).toBeInTheDocument();
      });

      // Click on "Toutes les exécutions" tab to switch to scope=all
      const allTab = screen.getByText('Toutes les exécutions');
      await userEvent.click(allTab);

      await waitFor(() => {
        // When scope=all, Utilisateur column should be visible
        expect(screen.getByText('Utilisateur')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');

      // Should have 8 columns including Utilisateur
      expect(headers.length).toBe(8);
    });
  });

  // Story 9.9 AC1-AC10: Table refactoring tests
  describe('Story 9.9: Table Refactoring', () => {
    const enrichedMockExecutions: ExecutionResponse[] = [
      {
        ...mockExecutions[0],
        engine: 'Oracle',
        platform: 'AAP',
        item_type: 'action',
        integration_id: 10,
        integration_name: 'AAP Production',
        integration_icon: '/icons/aap.png',
      },
      {
        ...mockExecutions[1],
        engine: 'SQL Server',
        platform: 'Terraform',
        item_type: 'action',
        integration_id: null,
        integration_name: null,
        integration_icon: null,
      },
      {
        id: 4,
        action_id: 15,
        action_name: 'Deploy Workflow',
        user_id: 1,
        environment: 'prod',
        parameters: null,
        status: 'COMPLETED',
        servicenow_change_id: null,
        started_at: '2026-01-29T15:00:00Z',
        completed_at: '2026-01-29T15:10:00Z',
        created_at: '2026-01-29T14:59:00Z',
        engine: null,
        platform: null,
        item_type: 'workflow',
        integration_id: 20,
        integration_name: 'GitHub Actions',
        integration_icon: '/icons/github.png',
      },
    ];

    beforeEach(() => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: enrichedMockExecutions,
        pagination: { page: 1, page_size: 25, total_count: 3, total_pages: 1 },
      });
    });

    it('renders status indicator column as first column (AC1)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');

      // First column should be "Statut"
      expect(headers[0]).toHaveTextContent('Statut');
    });

    it('renders technology column with Oracle icon (AC4)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for Technologie column header
      expect(screen.getByText('Technologie')).toBeInTheDocument();

      // Check for Oracle icon (DatabaseOutlined) - query by class name
      const oracleIcon = document.querySelector('[class*="anticon-database"]');
      expect(oracleIcon).toBeInTheDocument();
      expect(oracleIcon).toHaveStyle({ color: '#EF4444' });
    });

    it('renders workflow icon for workflow item_type (AC4)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Deploy Workflow')).toBeInTheDocument();
      });

      // Check for ApartmentOutlined icon (workflow)
      const workflowIcon = document.querySelector('[class*="anticon-apartment"]');
      expect(workflowIcon).toBeInTheDocument();
      expect(workflowIcon).toHaveStyle({ color: '#722ed1' });
    });

    it('renders integration icon when integration metadata present (AC5)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for Plateforme column
      expect(screen.getByText('Plateforme')).toBeInTheDocument();

      // Check for Avatar with integration icon
      const avatar = document.querySelector('.ant-avatar-square');
      expect(avatar).toBeInTheDocument();
    });

    it('renders fallback for missing integration (AC5)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Apply Patch')).toBeInTheDocument();
      });

      // Row 2 has null integration - should show "—" fallback
      const fallbacks = screen.getAllByText('—');
      expect(fallbacks.length).toBeGreaterThan(0);
    });

    it('columns are in correct order (AC7)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');

      // Story 9.9 AC7: Statut, Action, Technologie, Plateforme, Environnement, Date, Durée (no Utilisateur for scope=mine)
      expect(headers[0]).toHaveTextContent('Statut');
      expect(headers[1]).toHaveTextContent('Action');
      expect(headers[2]).toHaveTextContent('Technologie');
      expect(headers[3]).toHaveTextContent('Plateforme');
      expect(headers[4]).toHaveTextContent('Environnement');
      expect(headers[5]).toHaveTextContent('Date');
      expect(headers[6]).toHaveTextContent('Durée');
    });

    it('status, technologie, plateforme columns are not sortable (AC7)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const statusHeader = screen.getByText('Statut').closest('th');
      const technologieHeader = screen.getByText('Technologie').closest('th');
      const plateformeHeader = screen.getByText('Plateforme').closest('th');

      // These should NOT have sortable aria-description
      expect(statusHeader).not.toHaveAttribute('aria-description', 'sortable');
      expect(technologieHeader).not.toHaveAttribute('aria-description', 'sortable');
      expect(plateformeHeader).not.toHaveAttribute('aria-description', 'sortable');
    });
  });
});
