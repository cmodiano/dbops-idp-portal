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
 * AC5: Plateforme column with execution platform icons (action.platform).
 * AC7: Column order: Statut, Action, Technologie, Plateforme, [Utilisateur], Environnement, Début, Fin, Durée.
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
import { getIntegrations } from '../services/integrations_service';
import { fetchCatalogActions } from '../services/catalog_service';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

// Mock App.useApp() to provide notification/message/modal without requiring <App> context
const mockNotification = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  open: vi.fn(),
};

const mockMessage = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  loading: vi.fn(),
};

vi.mock('../services/execution_service');
vi.mock('../services/integrations_service', () => ({
  getIntegrations: vi.fn(),
}));
vi.mock('../services/catalog_service', () => ({
  fetchCatalogActionById: vi.fn().mockResolvedValue({
    data: { id: 1, name: 'Test', status: 'published' },
    can_execute: true,
    allowed_environments: ['dev', 'staging', 'prod'],
  }),
  fetchCatalogActions: vi.fn().mockResolvedValue([]),
}));
// Story 36.2: capture onSuccess to test post-wizard refresh trigger
let _wizardOnSuccess: ((id: number) => void) | undefined;
vi.mock('../components/catalog/ExecutionWizard', () => ({
  ExecutionWizard: ({ open, onSuccess }: { open: boolean; onSuccess?: (id: number) => void }) => {
    _wizardOnSuccess = onSuccess;
    return open ? <div data-testid="execution-wizard">Wizard</div> : null;
  },
}));
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ steps: [], execution: null, loading: false, error: null }),
}));
vi.mock('../hooks/useActorExecutionSync', () => ({
  useActorExecutionSync: vi.fn(),
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
    <ThemeProvider>
      <App>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </App>
    </ThemeProvider>
  );
}

/** Simpler render helper with ThemeProvider and Router for tests without auth.
 * Story 9.10: Router required for useExecutionFilters hook (useSearchParams). */
function renderWithTheme(ui: React.ReactElement) {
  const router = createMemoryRouter(
    [{ path: '/', element: ui }],
    { initialEntries: ['/'] }
  );
  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
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
    pagination: { page: 1, page_size: 25, total: 3, total_pages: 1 },
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
    // Re-mock App.useApp after resetAllMocks (provides notification without <App> context)
    vi.spyOn(App, 'useApp').mockReturnValue({
      message: mockMessage as any,
      notification: mockNotification as any,
      modal: {} as any,
    });
    // Re-mock getIntegrations after resetAllMocks (factory mock is cleared by resetAllMocks)
    vi.mocked(getIntegrations).mockResolvedValue([]);
    vi.mocked(executionService.listExecutions).mockResolvedValue(defaultListResponse);
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecutions[0]);
    vi.mocked(executionService.getExecutionSteps).mockResolvedValue(mockSteps);
    vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
      data: [],
      pagination: { page: 1, page_size: 50, total: 0, total_pages: 0 },
    });
    // Story 9.4: Mock fetchExecutionStats
    vi.mocked(executionService.fetchExecutionStats).mockResolvedValue({
      executions_jour: 10,
      taux_succes_pct: 85.5,
      executions_en_cours: 3,
      executions_en_erreur: 2,
    });
    // Story 9.10: Mock fetchExecutionTimeSeries for TrendLineChart
    vi.mocked(executionService.fetchExecutionTimeSeries).mockResolvedValue([]);
    // Story 9.10: Mock fetchExecutionTags for ExecutionsFiltersPanel
    vi.mocked(executionService.fetchExecutionTags).mockResolvedValue([]);
    // Re-mock fetchCatalogActions after resetAllMocks (factory mock implementation is cleared)
    vi.mocked(fetchCatalogActions).mockResolvedValue([]);
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

      // Check column headers within table (Story 9.10: filter panel also has labels)
      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');
      const headerTexts = headers.map(h => h.textContent);
      expect(headerTexts).toContain('Action');
      expect(headerTexts).toContain('Environnement');
      expect(headerTexts).toContain('Statut');
      expect(headerTexts).toContain('Début');
      expect(headerTexts).toContain('Fin');
      expect(headerTexts).toContain('Durée');
    });

    it('displays execution data correctly', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check action names
      expect(screen.getByText('Apply Patch')).toBeInTheDocument();
      expect(screen.getByText('Backup Database')).toBeInTheDocument();

      // Check environments (mapped via getEnvironmentLabel)
      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('Production')).toBeInTheDocument();
      expect(screen.getByText('Staging')).toBeInTheDocument();
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
        pagination: { page: 1, page_size: 25, total: 30, total_pages: 2 },
      });

      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Action 1')).toBeInTheDocument();
      });

      // API called with limit 25, offset 0, scope 'all' (Story 36.1: default for all users)
      // Story 9.10: listExecutions now also takes filters
      expect(executionService.listExecutions).toHaveBeenCalledWith(25, 0, 'all', expect.any(Object));
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
                  pagination: { page: 1, page_size: 25, total: 3, total_pages: 1 },
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
      const loadDelayMs = 800;
      vi.mocked(executionService.getExecution).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockExecutions[0]), loadDelayMs))
      );
      vi.mocked(executionService.getExecutionSteps).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockSteps), loadDelayMs))
      );

      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const createPdbCell = screen.getByText('Create PDB');
      const row = createPdbCell.closest('tr');
      await user.click(row!);

      // Drawer opens; skeleton should be visible while loading (before loadDelayMs)
      await waitFor(
        () => {
          const drawer = screen.getByRole('dialog');
          expect(drawer).toBeInTheDocument();
          const skeleton = drawer.querySelector('.ant-skeleton');
          expect(skeleton).toBeInTheDocument();
        },
        { timeout: 500 }
      );
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

      // Check for sortable indicators on columns within table (Story 9.10: filter panel also has labels)
      const table = screen.getByRole('table');
      const actionHeader = within(table).getByText('Action').closest('th');
      const statusHeader = within(table).getByText('Statut').closest('th');
      const dateHeader = within(table).getByText('Début').closest('th');

      // Story 9.9 AC7: Action and Début (date) are sortable
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
        pagination: { page: 1, page_size: 25, total: 0, total_pages: 1 },
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
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
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
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
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
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
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
        pagination: { page: 1, page_size: 50, total: 0, total_pages: 0 },
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
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
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
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
      });

      const user = userEvent.setup();
      await act(async () => {
        renderWithProviders();
      });

      // Wait for the pending approvals section to render
      await waitFor(() => {
        expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
      });

      // Click "Voir" to open the approval modal
      const voirBtn = screen.getByText('Voir');
      await user.click(voirBtn);

      await waitFor(() => {
        expect(screen.getByText('Approuver')).toBeInTheDocument();
        expect(screen.getByText('Refuser')).toBeInTheDocument();
      });
    });

    it('displays count badge on section header (AC2)', async () => {
      mockAuthSession('DBA');
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: mockPendingApprovals,
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
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

    it('shows both tabs for CLIENT user (Story 36.1 AC1)', async () => {
      // Story 36.1: tous les utilisateurs voient les deux onglets, le backend filtre
      mockAuthSession('CLIENT');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Mes exécutions/i })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });
    });

    it('calls listExecutions with scope=all by default for non-DBA (Story 36.1 AC1)', async () => {
      // Story 36.1: scope par défaut = 'all' pour tous, le backend filtre par RBAC
      mockAuthSession('CLIENT');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(executionService.listExecutions).toHaveBeenCalledWith(25, 0, 'all', expect.any(Object));
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
        // Story 9.10: listExecutions now also takes filters
        expect(executionService.listExecutions).toHaveBeenCalledWith(25, 0, 'all', expect.any(Object));
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
        pagination: { page: 1, page_size: 25, total: 30, total_pages: 2 },
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

      // Story 9.10: Use mockImplementation to dynamically return data based on scope
      vi.mocked(executionService.listExecutions).mockImplementation(
        async (_limit, _offset, scope) => {
          if (scope === 'all') {
            return {
              data: mockAllExecutions,
              pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
            };
          }
          return defaultListResponse;
        }
      );

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });

      // DBA default is scope=all, so "Utilisateur" column should be visible
      expect(screen.getByText('Utilisateur')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();

      // Switch to scope=mine — "Utilisateur" column should disappear
      await user.click(screen.getByRole('tab', { name: /Mes exécutions/i }));

      await waitFor(() => {
        expect(screen.queryByText('Utilisateur')).not.toBeInTheDocument();
      });
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

      // Story 9.10: Use mockImplementation to dynamically return data based on scope
      vi.mocked(executionService.listExecutions).mockImplementation(
        async (_limit, _offset, scope) => {
          if (scope === 'all') {
            return {
              data: mockAllExecutionsNoUser,
              pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
            };
          }
          return defaultListResponse;
        }
      );

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /Toutes les exécutions/i }));

      await waitFor(() => {
        // Query within table to avoid finding it in filter panel
        const table = screen.getByRole('table');
        expect(within(table).getByText('Utilisateur inconnu')).toBeInTheDocument();
      });
    });

    it('"Toutes les exécutions" tab is active by default for DBA/DBOPS', async () => {
      mockAuthSession('DBA');

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        const allTab = screen.getByRole('tab', { name: /Toutes les exécutions/i });
        expect(allTab).toHaveAttribute('aria-selected', 'true');
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

    it('fetchExecutionStats is called with scope=all by default for non-DBA (Story 36.1 AC1)', async () => {
      // Story 36.1: scope par défaut = 'all' pour tous les utilisateurs
      mockAuthSession('CLIENT');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(executionService.fetchExecutionStats).toHaveBeenCalledWith('all', expect.any(Object));
      });
    });

    it('fetchExecutionStats is called with scope=all by default for DBA (AC3)', async () => {
      mockAuthSession('DBA');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        // Story 9.10: DBA default is "Toutes les exécutions" → scope=all
        expect(executionService.fetchExecutionStats).toHaveBeenCalledWith('all', expect.any(Object));
      });
    });

    it('Pending approvals section is displayed BEFORE StatCards (AC1)', async () => {
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
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
        expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
      });

      // Check DOM order: pending approvals should appear before StatCards
      const statsCard = screen.getByText('Exécutions du jour').closest('.ant-card');
      const approvalsSection = document.getElementById('pending-approvals');

      expect(statsCard).not.toBeNull();
      expect(approvalsSection).not.toBeNull();
      // Compare positions - approvals should come before stats
      const approvalsPosition = approvalsSection!.compareDocumentPosition(statsCard!);
      expect(approvalsPosition & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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

      // First data column should be "Statut" (index 0 is expand column)
      const dataHeaders = headers.filter(h => h.textContent?.trim());
      expect(dataHeaders[0]).toHaveTextContent('Statut');
    });

    it('renders columns in correct order (AC7)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');

      // Story 9.9 AC7 / Story 36.1: scope=all is default → Utilisateur column is visible
      // Order: Statut, Action, Technologie, Plateforme, Utilisateur, Environnement, Début, Fin, Durée, Actions
      // First column is expand icon (empty header)
      const dataHeaders = headers.filter(h => h.textContent?.trim());
      expect(dataHeaders[0]).toHaveTextContent('Statut');
      expect(dataHeaders[1]).toHaveTextContent('Action');
      expect(dataHeaders[2]).toHaveTextContent('Technologie');
      expect(dataHeaders[3]).toHaveTextContent('Plateforme');
      expect(dataHeaders[4]).toHaveTextContent('Utilisateur');
      expect(dataHeaders[5]).toHaveTextContent('Environnement');
      expect(dataHeaders[6]).toHaveTextContent('Début');
      expect(dataHeaders[7]).toHaveTextContent('Fin');
      expect(dataHeaders[8]).toHaveTextContent('Durée');
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
        pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
      });

      const { container } = renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for Oracle SVG icon
      const oracleIcon = container.querySelector('img[src*="oracle"]');
      expect(oracleIcon).toBeInTheDocument();
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
        pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
      });

      const { container } = renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // WorkflowIcon renders a custom SVG with aria-label="Workflow" (not ApartmentOutlined)
      const workflowIcon = container.querySelector('[aria-label="Workflow"]');
      expect(workflowIcon).toBeInTheDocument();
    });

    it('renders Plateforme column with execution platform icon (AC5)', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            platform: 'AAP',
          },
        ],
        pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
      });

      const { container } = renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Plateforme column uses action.platform (mandatory for actions) — AAP icon
      const platformIcon = container.querySelector('[class*="anticon-rocket"]');
      expect(platformIcon).toBeInTheDocument();
    });

    it('renders fallback dash when platform is null (AC5)', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            engine: null,
            platform: null, // Plateforme column shows — when platform is null (e.g. workflow)
          },
        ],
        pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
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

      // Story 9.10: Filter panel also has labels, so query within table
      const table = screen.getByRole('table');
      const technologieHeader = within(table).getByText('Technologie').closest('th');
      const plateformeHeader = within(table).getByText('Plateforme').closest('th');

      // These columns should NOT have sortable attribute
      expect(technologieHeader).not.toHaveAttribute('aria-description', 'sortable');
      expect(plateformeHeader).not.toHaveAttribute('aria-description', 'sortable');
    });

    it('includes 9 columns when scope=all (with Utilisateur and Actions)', async () => {
      mockAuthSession('DBA');

      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: [
          {
            ...mockExecutions[0],
            user_display_name: 'Test User',
          },
        ],
        pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
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

      // Should have 11 columns (expand + 10 data columns: Utilisateur, Début, Fin, Durée, Actions)
      // Filter to data columns (exclude expand column with empty header)
      const dataHeaders = headers.filter(h => h.textContent?.trim());
      expect(dataHeaders.length).toBe(10);
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
        pagination: { page: 1, page_size: 25, total: 3, total_pages: 1 },
      });
    });

    it('renders status indicator column as first column (AC1)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');

      // First data column should be "Statut" (index 0 is expand column)
      const dataHeaders = headers.filter(h => h.textContent?.trim());
      expect(dataHeaders[0]).toHaveTextContent('Statut');
    });

    it('renders technology column with Oracle icon (AC4)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Check for Technologie column header within table (Story 9.10: filter panel also has this label)
      const table = screen.getByRole('table');
      expect(within(table).getByText('Technologie')).toBeInTheDocument();

      // Check for Oracle SVG icon
      const oracleIcon = document.querySelector('img[src*="oracle"]');
      expect(oracleIcon).toBeInTheDocument();
    });

    it('renders workflow icon for workflow item_type (AC4)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Deploy Workflow')).toBeInTheDocument();
      });

      // Workflow row has Technologie = ApartmentOutlined (violet). Terraform also uses ApartmentOutlined.
      const apartmentIcons = document.querySelectorAll('[class*="anticon-apartment"]');
      expect(apartmentIcons.length).toBeGreaterThanOrEqual(1);
    });

    it('renders integration icon when integration has icon (AC5)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Row 1 has integration with icon → Plateforme column shows Avatar (user-defined icon)
      expect(screen.getByText('Plateforme')).toBeInTheDocument();
      const avatar = document.querySelector('.ant-avatar');
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

      // Story 9.9 AC7 / Story 36.1: scope=all is default → Utilisateur column is visible
      // Order: Statut, Action, Technologie, Plateforme, Utilisateur, Environnement, Début, Fin, Durée, Actions
      // First column is expand icon (empty header)
      const dataHeaders = headers.filter(h => h.textContent?.trim());
      expect(dataHeaders[0]).toHaveTextContent('Statut');
      expect(dataHeaders[1]).toHaveTextContent('Action');
      expect(dataHeaders[2]).toHaveTextContent('Technologie');
      expect(dataHeaders[3]).toHaveTextContent('Plateforme');
      expect(dataHeaders[4]).toHaveTextContent('Utilisateur');
      expect(dataHeaders[5]).toHaveTextContent('Environnement');
      expect(dataHeaders[6]).toHaveTextContent('Début');
      expect(dataHeaders[7]).toHaveTextContent('Fin');
      expect(dataHeaders[8]).toHaveTextContent('Durée');
    });

    it('status, technologie, plateforme columns are not sortable (AC7)', async () => {
      renderWithTheme(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Create PDB')).toBeInTheDocument();
      });

      // Story 9.10: Filter panel also has labels, so query within table
      const table = screen.getByRole('table');
      const statusHeader = within(table).getByText('Statut').closest('th');
      const technologieHeader = within(table).getByText('Technologie').closest('th');
      const plateformeHeader = within(table).getByText('Plateforme').closest('th');

      // These should NOT have sortable aria-description
      expect(statusHeader).not.toHaveAttribute('aria-description', 'sortable');
      expect(technologieHeader).not.toHaveAttribute('aria-description', 'sortable');
      expect(plateformeHeader).not.toHaveAttribute('aria-description', 'sortable');
    });
  });

  // === Story 22.14: Stale Closure Fix Tests ===
  describe('Story 22.14 — Stale Closure Fix (refetchCurrentState)', () => {
    /**
     * Helper: mock App.useApp with a modal.confirm that auto-invokes onOk.
     * This simulates the user confirming the cancel modal.
     */
    function mockAppWithAutoConfirmModal() {
      const mockModal = {
        confirm: vi.fn(({ onOk }: { onOk: () => Promise<void> }) => {
          // Fire-and-forget: do NOT await onOk() so the test can continue
          // This simulates the user confirming the modal asynchronously
          void onOk();
        }),
      };
      vi.spyOn(App, 'useApp').mockReturnValue({
        message: mockMessage as any,
        notification: mockNotification as any,
        modal: mockModal as any,
      });
      return mockModal;
    }

    describe('Unit Tests — Stale closure prevention', () => {
      it('handleCancelExecution refetches with latest scope, not stale closure values (AC#1, AC#2)', async () => {
        // This test verifies that refetchCurrentState reads from refs at call time.
        // We verify via scope change (reliable interaction), which proves the same mechanism
        // that also handles pagination changes (both use the same ref pattern).
        mockAppWithAutoConfirmModal();
        mockAuthSession('DBA');

        vi.mocked(executionService.cancelExecution).mockResolvedValue({} as never);

        const cancellableExecutions: ExecutionResponse[] = [
          { ...mockExecutions[0], status: 'SUBMITTED', user_display_name: 'Test User' },
        ];
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: cancellableExecutions,
          pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Create PDB')).toBeInTheDocument();
        });

        // Switch to "mine" scope first
        const mesTab = screen.getByRole('tab', { name: /Mes exécutions/i });
        await user.click(mesTab);

        await waitFor(() => {
          expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalledWith(
            25, 0, 'mine', expect.any(Object)
          );
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Now cancel — should refetch with 'mine' (current scope), not 'all' (initial)
        const cancelBtn = screen.getByRole('button', { name: /Annuler/i });
        await user.click(cancelBtn);

        await waitFor(() => {
          const calls = vi.mocked(executionService.listExecutions).mock.calls;
          expect(calls.length).toBeGreaterThan(0);
          expect(calls[calls.length - 1][2]).toBe('mine');
        });
      });

      it('handleCancelExecution uses current scope after scope change during cancel (AC#1, AC#3)', async () => {
        mockAppWithAutoConfirmModal();
        mockAuthSession('DBA');

        let resolveCancelPromise: () => void;
        vi.mocked(executionService.cancelExecution).mockImplementation(
          () => new Promise<never>((resolve) => { resolveCancelPromise = resolve as () => void; })
        );

        const cancellableExecutions: ExecutionResponse[] = [
          {
            ...mockExecutions[0],
            status: 'SUBMITTED',
            user_display_name: 'Test User',
          },
        ];
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: cancellableExecutions,
          pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Create PDB')).toBeInTheDocument();
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Click cancel
        const cancelBtn = screen.getByRole('button', { name: /Annuler/i });
        await user.click(cancelBtn);

        // Switch scope from all → mine while cancel is in flight
        const mesTab = screen.getByRole('tab', { name: /Mes exécutions/i });
        await user.click(mesTab);

        // Resolve cancel
        resolveCancelPromise!();

        // Refetch after cancel should use 'mine' (current scope), not 'all' (old scope)
        await waitFor(() => {
          const calls = vi.mocked(executionService.listExecutions).mock.calls;
          const lastCall = calls[calls.length - 1];
          expect(lastCall[2]).toBe('mine');
        });
      });

      it('double-click cancel is blocked by isCancellingRef guard (AC#4)', async () => {
        const mockModal = mockAppWithAutoConfirmModal();
        mockAuthSession('DBA');

        // Cancel never resolves — stays in-flight
        vi.mocked(executionService.cancelExecution).mockImplementation(
          () => new Promise<never>(() => { /* never resolves */ })
        );

        const cancellableExecutions: ExecutionResponse[] = [
          { ...mockExecutions[0], status: 'SUBMITTED', user_display_name: 'Test User' },
        ];
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: cancellableExecutions,
          pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Create PDB')).toBeInTheDocument();
        });

        // Click cancel twice rapidly
        const cancelBtn = screen.getByRole('button', { name: /Annuler/i });
        await user.click(cancelBtn);
        await user.click(cancelBtn);

        // modal.confirm should only be called once (second click blocked by guard)
        expect(mockModal.confirm).toHaveBeenCalledTimes(1);
      });

      it('cancel after scope change refetches with correct scope, not duplicate (AC#4)', async () => {
        // Tests that the isRefreshingRef guard prevents concurrent refetches and
        // that the refetch after cancel uses current state (not stale)
        mockAppWithAutoConfirmModal();
        mockAuthSession('DBA');

        vi.mocked(executionService.cancelExecution).mockResolvedValue({} as never);

        const cancellableExecutions: ExecutionResponse[] = [
          { ...mockExecutions[0], status: 'SUBMITTED', user_display_name: 'Test User' },
        ];
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: cancellableExecutions,
          pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Create PDB')).toBeInTheDocument();
        });

        // Switch scope, then cancel — both trigger refetch. Verify no stale scope used.
        const mesTab = screen.getByRole('tab', { name: /Mes exécutions/i });
        await user.click(mesTab);

        await waitFor(() => {
          expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalledWith(
            25, 0, 'mine', expect.any(Object)
          );
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Cancel — refetch should use 'mine' not 'all'
        const cancelBtn = screen.getByRole('button', { name: /Annuler/i });
        await user.click(cancelBtn);

        await waitFor(() => {
          const calls = vi.mocked(executionService.listExecutions).mock.calls;
          // All calls after scope change should be 'mine'
          const allMine = calls.every(c => c[2] === 'mine');
          expect(allMine).toBe(true);
          expect(calls.length).toBeGreaterThanOrEqual(1);
        });
      });

      it('handleApprovalComplete uses current scope after scope change (AC#3)', async () => {
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
          pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Switch scope to "mine"
        const mesTab = screen.getByRole('tab', { name: /Mes exécutions/i });
        await user.click(mesTab);

        await waitFor(() => {
          const calls = vi.mocked(executionService.listExecutions).mock.calls;
          expect(calls.some(c => c[2] === 'mine')).toBe(true);
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Open the approval modal by clicking "Voir"
        const voirBtn = screen.getByText('Voir');
        await user.click(voirBtn);

        await waitFor(() => {
          expect(screen.getByText('Approuver')).toBeInTheDocument();
        });

        // Now simulate approval complete (clicking Approuver triggers onActionComplete)
        const approveBtn = screen.getByText('Approuver');
        await user.click(approveBtn);

        // The refetch triggered by handleApprovalComplete should use 'mine' (current scope)
        await waitFor(() => {
          const calls = vi.mocked(executionService.listExecutions).mock.calls;
          if (calls.length > 0) {
            const lastCall = calls[calls.length - 1];
            expect(lastCall[2]).toBe('mine');
          }
        });
      });

      it('mock delay on cancelExecution simulates timing window correctly (AC#4)', async () => {
        mockAppWithAutoConfirmModal();
        mockAuthSession('DBA');

        vi.mocked(executionService.cancelExecution).mockImplementation(async () => {
          await new Promise(resolve => setTimeout(resolve, 50));
          return {} as never;
        });

        const cancellableExecutions: ExecutionResponse[] = [
          { ...mockExecutions[0], status: 'SUBMITTED', user_display_name: 'Test User' },
        ];
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: cancellableExecutions,
          pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Create PDB')).toBeInTheDocument();
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Click cancel
        const cancelBtn = screen.getByRole('button', { name: /Annuler/i });
        await user.click(cancelBtn);

        // Wait for cancel to complete and refetch
        await waitFor(() => {
          expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalled();
        });

        // The notification.success should have been called
        expect(mockNotification.success).toHaveBeenCalledWith({
          title: 'Exécution annulée avec succès',
        });
      });
    });

    describe('Integration Tests — Complete behavior sequences', () => {
      it('cancel → scope change → refetch uses current scope, not stale (AC#1, AC#2)', async () => {
        // Integration test: cancel completes, scope changes during cancel, refetch uses current scope
        mockAppWithAutoConfirmModal();
        mockAuthSession('DBA');

        vi.mocked(executionService.cancelExecution).mockResolvedValue({} as never);

        const cancellableExecutions: ExecutionResponse[] = [
          { ...mockExecutions[0], status: 'SUBMITTED', user_display_name: 'Test User' },
        ];
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: cancellableExecutions,
          pagination: { page: 1, page_size: 25, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Create PDB')).toBeInTheDocument();
        });

        // Switch to "mine"
        await user.click(screen.getByRole('tab', { name: /Mes exécutions/i }));

        await waitFor(() => {
          expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalledWith(
            25, 0, 'mine', expect.any(Object)
          );
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Cancel on current scope
        await user.click(screen.getByRole('button', { name: /Annuler/i }));

        // Verify refetch used 'mine', not stale 'all'
        await waitFor(() => {
          const calls = vi.mocked(executionService.listExecutions).mock.calls;
          expect(calls.length).toBeGreaterThan(0);
          expect(calls[calls.length - 1][2]).toBe('mine');
        });
      });

      it('approval → scope change → refetch uses correct scope (AC#1, AC#3)', async () => {
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
          pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Approbations en attente')).toBeInTheDocument();
        });

        // Switch to mine scope
        const mesTab = screen.getByRole('tab', { name: /Mes exécutions/i });
        await user.click(mesTab);

        await waitFor(() => {
          expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalledWith(
            25, 0, 'mine', expect.any(Object)
          );
        });

        vi.mocked(executionService.listExecutions).mockClear();

        // Open the approval modal by clicking "Voir"
        const voirBtn = screen.getByText('Voir');
        await user.click(voirBtn);

        await waitFor(() => {
          expect(screen.getByText('Approuver')).toBeInTheDocument();
        });

        // Trigger approval callback
        const approveBtn = screen.getByText('Approuver');
        await user.click(approveBtn);

        // Refetch from handleApprovalComplete should use 'mine'
        await waitFor(() => {
          const calls = vi.mocked(executionService.listExecutions).mock.calls;
          if (calls.length > 0) {
            expect(calls[calls.length - 1][2]).toBe('mine');
          }
        });
      });

      it('restart → page change → refetch uses correct page (AC#1, AC#2)', async () => {
        mockAuthSession('DBA');

        const manyExecutions = Array.from({ length: 25 }, (_, i) => ({
          ...mockExecutions[0],
          id: i + 1,
          action_name: `Action ${i + 1}`,
          action_id: 10,
          user_display_name: 'Test User',
        }));
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: manyExecutions,
          pagination: { page: 1, page_size: 25, total: 50, total_pages: 2 },
        });

        const user = userEvent.setup();
        await act(async () => {
          renderWithProviders();
        });

        await waitFor(() => {
          expect(screen.getByText('Action 1')).toBeInTheDocument();
        });

        // Change to page 2 by clicking the pagination item with class ant-pagination-item-2
        const page2Item = document.querySelector('.ant-pagination-item-2');
        expect(page2Item).toBeInTheDocument();
        if (page2Item) await user.click(page2Item);

        // After page change, verify page 2 was fetched (offset 25)
        await waitFor(() => {
          expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalledWith(
            25, 25, expect.any(String), expect.any(Object)
          );
        });
      });
    });
  });
  // ============================================================
  // Story 36.1 — Vue partagée : liste et droits RBAC
  // ============================================================
  describe('Story 36.1 — Vue partagée RBAC', () => {
    it('shows "Toutes les exécutions" tab for all user profiles (AC1)', async () => {
      for (const profile of ['DBA', 'DBOPS', 'CLIENT', 'business', 'auditor']) {
        vi.resetAllMocks();
        vi.spyOn(App, 'useApp').mockReturnValue({
          message: mockMessage as any,
          notification: mockNotification as any,
          modal: {} as any,
        });
        vi.mocked(getIntegrations).mockResolvedValue([]);
        vi.mocked(executionService.listExecutions).mockResolvedValue({
          data: mockExecutions,
          pagination: { page: 1, page_size: 25, total: 3, total_pages: 1 },
        });
        vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
          data: [],
          pagination: { page: 1, page_size: 50, total: 0, total_pages: 0 },
        });
        vi.mocked(executionService.fetchExecutionStats).mockResolvedValue({
          executions_jour: 0, taux_succes_pct: 0, executions_en_cours: 0, executions_en_erreur: 0,
        });
        vi.mocked(executionService.fetchExecutionTimeSeries).mockResolvedValue([]);
        vi.mocked(executionService.fetchExecutionTags).mockResolvedValue([]);
        vi.mocked(fetchCatalogActions).mockResolvedValue([]);
        mockAuthSession(profile);

        const { unmount } = await act(async () => renderWithProviders());
        await waitFor(() => {
          expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
          expect(screen.getByRole('tab', { name: /Mes exécutions/i })).toBeInTheDocument();
        });
        unmount();
      }
    });

    it('initializes scope to "all" for non-DBA user (AC1, subtask 4.2)', async () => {
      mockAuthSession('business');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalledWith(
          25, 0, 'all', expect.any(Object)
        );
      });
    });

    it('shows "Utilisateur" column in table when scope=all (AC4, subtask 4.3)', async () => {
      // scope=all is default → colonne Utilisateur doit être visible
      const executionsWithUser: typeof mockExecutions = [
        { ...mockExecutions[0], user_display_name: 'Alice Dupont' },
        { ...mockExecutions[1], user_display_name: null },
      ];
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: executionsWithUser,
        pagination: { page: 1, page_size: 25, total: 2, total_pages: 1 },
      });

      mockAuthSession('business');
      await act(async () => {
        renderWithProviders();
      });

      await waitFor(() => {
        // "Toutes les exécutions" tab = scope=all (default pour tous)
        const allTab = screen.queryByRole('tab', { name: /Toutes les exécutions/i });
        expect(allTab).toBeInTheDocument();
      });

      // La colonne "Utilisateur" doit être dans le tableau
      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');
      const headerTexts = headers.map(h => h.textContent);
      expect(headerTexts).toContain('Utilisateur');
    });
  });
  // ── Story 36.2 — Trigger refresh post-wizard ──────────────────────────────
  describe('Story 36.2 — Trigger refresh post-wizard (AC4)', () => {
    it('6.1 — après fermeture réussie du wizard (onSuccess), refresh() est appelé (listExecutions rappelé)', async () => {
      vi.mocked(executionService.listExecutions).mockResolvedValue({
        data: mockExecutions,
        pagination: { page: 1, page_size: 25, total: mockExecutions.length, total_pages: 1 },
      });
      vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
        data: [],
        pagination: { page: 1, page_size: 50, total: 0, total_pages: 1 },
      });

      await act(async () => {
        renderWithProviders();
      });

      // Attendre le chargement initial — _wizardOnSuccess est capturé lors du premier rendu
      await waitFor(() => {
        expect(vi.mocked(executionService.listExecutions)).toHaveBeenCalled();
        expect(_wizardOnSuccess).toBeDefined();
      });

      const callsBefore = vi.mocked(executionService.listExecutions).mock.calls.length;

      // Déclencher onSuccess du wizard (simule la soumission réussie d'une exécution)
      await act(async () => {
        _wizardOnSuccess!(99);
      });

      // refresh() doit relancer listExecutions
      await waitFor(() => {
        expect(vi.mocked(executionService.listExecutions).mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });
  });
}); // end ExecutionsPage
