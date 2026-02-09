/**
 * Tests for cancel execution feature (Story 17.14).
 *
 * AC1: Cancel button visible for initiator (SUBMITTED/RUNNING).
 * AC2: Cancel button visible for admin DBOPS on all executions.
 * AC6: Error handling and user feedback.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { App } from 'antd';
import ExecutionsPage from './ExecutionsPage';
import { AuthProvider } from '../contexts/AuthContext';
import { ThemeProvider } from '../contexts/ThemeContext';
import * as executionService from '../services/execution_service';
import * as integrationsService from '../services/integrations_service';
import * as referenceService from '../services/reference_service';
import logger from '../services/logger';
import type { ExecutionResponse } from '../types/api';

vi.mock('../services/execution_service');
vi.mock('../services/integrations_service');
vi.mock('../services/reference_service');
vi.mock('../services/logger');
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ steps: [], execution: null, loading: false, error: null }),
}));

/** Mock auth session with given profile and user ID */
function mockAuthSession(profile: string, userId = 1) {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: { access_token: 'token', token_type: 'bearer' } }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          id: userId,
          username: 'test.user',
          display_name: 'Test User',
          profile,
          navigation_tabs: ['dashboard', 'catalog', 'executions'],
        },
      }),
    });
}

/** Render component with auth and all providers */
function renderWithAuth() {
  const router = createMemoryRouter(
    [{ path: '/', element: <ExecutionsPage /> }],
    { initialEntries: ['/'] },
  );
  return render(
    <ThemeProvider>
      <App>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </App>
    </ThemeProvider>,
  );
}

/** Render without auth (user=undefined, acts like non-admin) */
function renderWithTheme() {
  const router = createMemoryRouter(
    [{ path: '/', element: <ExecutionsPage /> }],
    { initialEntries: ['/'] },
  );
  return render(
    <ThemeProvider>
      <App>
        <RouterProvider router={router} />
      </App>
    </ThemeProvider>,
  );
}

/** Execution owned by user 1 in SUBMITTED status */
const submittedExecution: ExecutionResponse = {
  id: 10, action_id: 1, action_name: 'Test Action', user_id: 1,
  environment: 'dev', parameters: null, status: 'SUBMITTED',
  servicenow_change_id: null, started_at: null, completed_at: null,
  created_at: '2026-02-07T10:00:00Z',
};

/** Execution owned by user 1 in RUNNING status */
const runningExecution: ExecutionResponse = {
  id: 11, action_id: 2, action_name: 'Running Action', user_id: 1,
  environment: 'prod', parameters: null, status: 'RUNNING',
  servicenow_change_id: null, started_at: '2026-02-07T10:01:00Z',
  completed_at: null, created_at: '2026-02-07T10:00:00Z',
};

/** Execution owned by user 1 in COMPLETED status */
const completedExecution: ExecutionResponse = {
  id: 12, action_id: 3, action_name: 'Done Action', user_id: 1,
  environment: 'dev', parameters: null, status: 'COMPLETED',
  servicenow_change_id: null, started_at: '2026-02-07T10:00:00Z',
  completed_at: '2026-02-07T10:05:00Z', created_at: '2026-02-07T09:59:00Z',
};

/** Execution owned by user 999 in RUNNING status (another user) */
const otherUserRunningExecution: ExecutionResponse = {
  id: 13, action_id: 4, action_name: 'Other User Action', user_id: 999,
  user_display_name: 'Other User', environment: 'prod', parameters: null,
  status: 'RUNNING', servicenow_change_id: null,
  started_at: '2026-02-07T10:01:00Z', completed_at: null,
  created_at: '2026-02-07T10:00:00Z',
};

const defaultStats = {
  executions_jour: 5, taux_succes_pct: 80,
  executions_en_cours: 2, executions_en_erreur: 1,
};

function setupDefaultMocks(executions: ExecutionResponse[]) {
  vi.mocked(integrationsService.getIntegrations).mockResolvedValue([]);
  vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['dev', 'prod']);
  vi.mocked(referenceService.fetchEngines).mockResolvedValue([]);
  vi.mocked(executionService.listExecutions).mockResolvedValue({
    data: executions,
    pagination: { page: 1, page_size: 25, total: executions.length, total_pages: 1 },
  });
  vi.mocked(executionService.getExecution).mockResolvedValue(executions[0]);
  vi.mocked(executionService.getExecutionSteps).mockResolvedValue([]);
  vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
    data: [],
    pagination: { page: 1, page_size: 50, total: 0, total_pages: 0 },
  });
  vi.mocked(executionService.fetchExecutionStats).mockResolvedValue(defaultStats);
  vi.mocked(executionService.fetchExecutionTimeSeries).mockResolvedValue([]);
  vi.mocked(executionService.fetchExecutionTags).mockResolvedValue([]);
  vi.mocked(executionService.cancelExecution).mockResolvedValue({
    ...executions[0], status: 'CANCELLED', completed_at: '2026-02-07T10:06:00Z',
  });
}

describe('Story 17.14: Cancel Execution', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('5.1: Cancel button visible for initiator (SUBMITTED)', () => {
    it('shows cancel button for SUBMITTED execution owned by current user', async () => {
      setupDefaultMocks([submittedExecution]);
      mockAuthSession('DBA', 1);
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByText('Test Action')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /annuler/i })).toBeInTheDocument();
      });
    });
  });

  describe('5.2: Cancel button visible for DBOPS admin on all executions', () => {
    it('shows cancel button for admin on another user\'s RUNNING execution', async () => {
      setupDefaultMocks([otherUserRunningExecution]);
      mockAuthSession('DBOPS', 1);
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByText('Other User Action')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /annuler/i })).toBeInTheDocument();
      });
    });
  });

  describe('5.3: Cancel button NOT visible for unauthorized user', () => {
    it('does not show cancel button when user is not owner and not admin', async () => {
      setupDefaultMocks([otherUserRunningExecution]);
      mockAuthSession('BUSINESS', 1);
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByText('Other User Action')).toBeInTheDocument();
      });

      // Wait for auth to settle, then verify no cancel button
      // User is BUSINESS (not admin) and not the owner (user_id=999)
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /annuler/i })).toBeNull();
      });
    });
  });

  describe('5.4: Cancel button NOT visible for terminal statuses', () => {
    it('does not show cancel button for COMPLETED execution', async () => {
      setupDefaultMocks([completedExecution]);
      mockAuthSession('DBA', 1);
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByText('Done Action')).toBeInTheDocument();
      });

      const cancelButtons = screen.queryAllByRole('button', { name: /annuler/i });
      expect(cancelButtons).toHaveLength(0);
    });
  });

  describe('5.5: Successful cancellation', () => {
    it('calls cancelExecution and refreshes list on confirmation', async () => {
      const user = userEvent.setup();
      setupDefaultMocks([submittedExecution]);
      mockAuthSession('DBA', 1);
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByText('Test Action')).toBeInTheDocument();
      });

      let cancelButton!: HTMLElement;
      await waitFor(() => {
        cancelButton = screen.getByRole('button', { name: /annuler/i });
      });
      await user.click(cancelButton);

      // Modal should appear (Modal.confirm renders title in two DOM nodes)
      await waitFor(() => {
        expect(screen.getAllByText("Confirmer l'annulation").length).toBeGreaterThanOrEqual(1);
      });

      // Click OK (Confirmer) button in the confirm modal
      const confirmBtns = screen.getAllByRole('button', { name: /confirmer/i });
      await user.click(confirmBtns[0]);

      await waitFor(() => {
        expect(vi.mocked(executionService.cancelExecution)).toHaveBeenCalledWith(submittedExecution.id);
      });

      // List should be refreshed (called again after cancel)
      await waitFor(() => {
        expect(vi.mocked(executionService.listExecutions).mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });
  });

  describe('5.6: Failed cancellation - error notification', () => {
    it('shows error notification when cancel fails', async () => {
      const user = userEvent.setup();
      setupDefaultMocks([runningExecution]);
      vi.mocked(executionService.cancelExecution).mockRejectedValue(
        new Error('Accès interdit'),
      );
      mockAuthSession('DBA', 1);
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByText('Running Action')).toBeInTheDocument();
      });

      let cancelButton!: HTMLElement;
      await waitFor(() => {
        cancelButton = screen.getByRole('button', { name: /annuler/i });
      });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.getAllByText("Confirmer l'annulation").length).toBeGreaterThanOrEqual(1);
      });

      const confirmBtns = screen.getAllByRole('button', { name: /confirmer/i });
      await user.click(confirmBtns[0]);

      await waitFor(() => {
        expect(vi.mocked(executionService.cancelExecution)).toHaveBeenCalledWith(runningExecution.id);
      });

      // Error notification should appear
      await waitFor(() => {
        expect(screen.getByText("Erreur d'annulation")).toBeInTheDocument();
      });

      // LOW-2 fix: Verify logger.error was called
      await waitFor(() => {
        expect(vi.mocked(logger.error)).toHaveBeenCalledWith(
          'Cancel execution failed',
          expect.objectContaining({
            executionId: runningExecution.id,
          })
        );
      });
    });
  });
});
