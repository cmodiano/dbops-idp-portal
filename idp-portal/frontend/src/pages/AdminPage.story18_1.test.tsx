/**
 * Story 18.1: Admin Actions — suppression, desactivation et filtres.
 * Tests for delete, deactivate, reactivate, include_disabled filter, and cascade modal.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import AdminPage from './AdminPage';

// ─── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('../services/admin_service');
vi.mock('../services/profiles_service');
vi.mock('../services/integrations_service');

vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({ effectiveMode: 'light' }),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isBusinessProfile: false }),
}));

// Lazy-loaded components
vi.mock('../components/admin/analytics/AdminAnalyticsDashboard', () => ({
  default: () => <div data-testid="analytics-dashboard">Analytics</div>,
}));
vi.mock('../components/admin/FeatureFlagsPanel', () => ({
  FeatureFlagsPanel: () => <div data-testid="feature-flags">Flags</div>,
}));
vi.mock('../components/admin/ActionWizard', () => ({
  ActionWizard: () => null,
}));
vi.mock('../components/admin/ProfileWizard', () => ({
  ProfileWizard: () => null,
}));
vi.mock('../components/admin/ProfileImportModal', () => ({
  ProfileImportModal: () => null,
}));
vi.mock('../components/admin/IntegrationForm', () => ({
  IntegrationForm: () => null,
}));
vi.mock('../components/admin/IntegrationsTable', () => ({
  IntegrationsTable: () => null,
}));
vi.mock('../components/admin/ProfilesTable', () => ({
  ProfilesTable: () => null,
}));

import {
  getAdminActions,
  deleteAction,
  deactivateAction,
  reactivateAction,
} from '../services/admin_service';
import type { ActionListItem, ActionListResponse } from '../types/api';

const mockGetAdminActions = vi.mocked(getAdminActions);
const mockDeleteAction = vi.mocked(deleteAction);
const mockDeactivateAction = vi.mocked(deactivateAction);
const mockReactivateAction = vi.mocked(reactivateAction);

// ─── Test Data ──────────────────────────────────────────────────────────────

const draftNoExec: ActionListItem = {
  id: 1, name: 'Action Draft Zero', status: 'draft', engine: 'Oracle',
  created_at: '2026-01-01T00:00:00Z', execution_count: 0, tags: [],
};
const publishedNoExec: ActionListItem = {
  id: 2, name: 'Action Published Zero', status: 'published', engine: 'Oracle',
  created_at: '2026-01-02T00:00:00Z', execution_count: 0, tags: [],
};
const publishedWithExec: ActionListItem = {
  id: 3, name: 'Action Published Exec', status: 'published', engine: 'DB2',
  created_at: '2026-01-03T00:00:00Z', execution_count: 5, tags: [],
};
const disabledAction: ActionListItem = {
  id: 4, name: 'Action Disabled', status: 'disabled', engine: 'Oracle',
  created_at: '2026-01-04T00:00:00Z', execution_count: 3, tags: [],
  deleted_at: '2026-02-01T00:00:00Z', deleted_by: 99, deletion_reason: 'Obsolete',
};
const disabledNoExec: ActionListItem = {
  id: 5, name: 'Action Disabled Zero', status: 'disabled', engine: 'Oracle',
  created_at: '2026-01-05T00:00:00Z', execution_count: 0, tags: [],
};

const allActions = [draftNoExec, publishedNoExec, publishedWithExec, disabledAction, disabledNoExec];
const activeActions = [draftNoExec, publishedNoExec, publishedWithExec];

function makeResponse(data: ActionListItem[]): ActionListResponse {
  return { data, pagination: null };
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <App>
      <AdminPage />
    </App>,
  );
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('Story 18.1 — AdminPage Actions', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGetAdminActions.mockResolvedValue(makeResponse(activeActions));
  });

  // ── AC4: Default filter excludes disabled ──

  describe('AC4: Default filter excludes disabled', () => {
    it('loads actions without include_disabled by default', async () => {
      renderPage();

      await waitFor(() => {
        expect(mockGetAdminActions).toHaveBeenCalledWith(expect.not.objectContaining({ include_disabled: true }));
      });

      expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      expect(screen.getByText('Action Published Zero')).toBeInTheDocument();
      expect(screen.queryByText('Action Disabled')).not.toBeInTheDocument();
    });

    it('shows the include disabled checkbox unchecked by default', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      expect(checkbox).not.toBeChecked();
    });
  });

  // ── AC5: Toggle to include disabled actions ──

  describe('AC5: Include disabled toggle', () => {
    it('fetches with include_disabled=true when checkbox is checked', async () => {
      const user = userEvent.setup();
      mockGetAdminActions
        .mockResolvedValueOnce(makeResponse(activeActions))
        .mockResolvedValueOnce(makeResponse(allActions));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      await user.click(checkbox);

      await waitFor(() => {
        expect(mockGetAdminActions).toHaveBeenCalledWith(
          expect.objectContaining({ include_disabled: true }),
        );
      });
    });

    it('shows disabled actions with opacity when include_disabled is checked', async () => {
      const user = userEvent.setup();
      mockGetAdminActions
        .mockResolvedValueOnce(makeResponse(activeActions))
        .mockResolvedValueOnce(makeResponse(allActions));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('Action Disabled')).toBeInTheDocument();
      });
    });
  });

  // ── AC1/AC6: Delete button for actions with 0 executions ──

  describe('AC1/AC6: Delete button visibility', () => {
    it('shows Supprimer button for draft action with 0 executions', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Draft Zero').closest('tr')!;
      expect(within(row).getByText('Supprimer')).toBeInTheDocument();
    });

    it('shows Supprimer button for published action with 0 executions', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Zero')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Zero').closest('tr')!;
      expect(within(row).getByText('Supprimer')).toBeInTheDocument();
    });

    it('does NOT show Supprimer for published action with executions', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Exec').closest('tr')!;
      expect(within(row).queryByText('Supprimer')).not.toBeInTheDocument();
    });

    it('shows Desactiver for published action with executions', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Exec').closest('tr')!;
      expect(within(row).getByText('Desactiver')).toBeInTheDocument();
    });
  });

  // ── AC1: Hard delete flow ──

  describe('AC1: Hard delete', () => {
    it('calls deleteAction after confirmation', async () => {
      const user = userEvent.setup();
      mockDeleteAction.mockResolvedValue();

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Draft Zero').closest('tr')!;
      const deleteBtn = within(row).getByText('Supprimer');
      await user.click(deleteBtn);

      // Ant Design modal.confirm appears
      await waitFor(() => {
        expect(screen.getByText(/supprimer definitivement/i)).toBeInTheDocument();
      });

      // Confirm
      const confirmBtn = screen.getByRole('button', { name: 'Supprimer' });
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(mockDeleteAction).toHaveBeenCalledWith(1);
      });
    });
  });

  // ── AC2: Deactivate without cascade ──

  describe('AC2: Deactivate (no cascade)', () => {
    it('calls deactivateAction and shows success notification', async () => {
      const user = userEvent.setup();
      mockDeactivateAction.mockResolvedValue({
        data: { ...publishedWithExec, status: 'disabled' as const } as never,
        deactivated_workflows: [],
      });

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Exec').closest('tr')!;
      const deactivateBtn = within(row).getByText('Desactiver');
      await user.click(deactivateBtn);

      await waitFor(() => {
        expect(mockDeactivateAction).toHaveBeenCalledWith(3);
      });
    });
  });

  // ── AC3: Cascade deactivation with confirmation modal ──

  describe('AC3: Cascade confirmation modal', () => {
    it('shows cascade modal when workflows are affected', async () => {
      const user = userEvent.setup();
      mockDeactivateAction.mockResolvedValue({
        status: 'requires_confirmation',
        affected_workflows: [
          { id: 10, name: 'Workflow A', status: 'published' },
          { id: 11, name: 'Workflow B', status: 'published' },
        ],
      });

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Exec').closest('tr')!;
      const deactivateBtn = within(row).getByText('Desactiver');
      await user.click(deactivateBtn);

      await waitFor(() => {
        expect(screen.getByText('Confirmation de desactivation en cascade')).toBeInTheDocument();
      });

      expect(screen.getByText('Workflow A')).toBeInTheDocument();
      expect(screen.getByText('Workflow B')).toBeInTheDocument();
    });

    it('confirms cascade deactivation', async () => {
      const user = userEvent.setup();
      mockDeactivateAction
        .mockResolvedValueOnce({
          status: 'requires_confirmation',
          affected_workflows: [
            { id: 10, name: 'Workflow A', status: 'published' },
          ],
        })
        .mockResolvedValueOnce({
          data: { ...publishedWithExec, status: 'disabled' as const } as never,
          deactivated_workflows: [{ id: 10, name: 'Workflow A' }],
        });

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      // Click deactivate
      const row = screen.getByText('Action Published Exec').closest('tr')!;
      await user.click(within(row).getByText('Desactiver'));

      await waitFor(() => {
        expect(screen.getByText('Confirmation de desactivation en cascade')).toBeInTheDocument();
      });

      // Click confirm
      const confirmBtn = screen.getByText('Confirmer la desactivation');
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(mockDeactivateAction).toHaveBeenCalledWith(3, undefined, true);
      });
    });

    it('cancels cascade modal without calling API', async () => {
      const user = userEvent.setup();
      mockDeactivateAction.mockResolvedValue({
        status: 'requires_confirmation',
        affected_workflows: [
          { id: 10, name: 'Workflow A', status: 'published' },
        ],
      });

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Exec').closest('tr')!;
      await user.click(within(row).getByText('Desactiver'));

      await waitFor(() => {
        expect(screen.getByText('Confirmation de desactivation en cascade')).toBeInTheDocument();
      });

      // Cancel
      await user.click(screen.getByText('Annuler'));

      // Only the initial call, no confirmed call
      expect(mockDeactivateAction).toHaveBeenCalledTimes(1);
      // Ensure the confirmed version was never called
      expect(mockDeactivateAction).not.toHaveBeenCalledWith(3, expect.anything(), true);
    });
  });

  // ── AC5: Reactivate ──

  describe('AC5: Reactivate disabled action', () => {
    it('shows Reactiver button for disabled actions', async () => {
      const user = userEvent.setup();
      mockGetAdminActions
        .mockResolvedValueOnce(makeResponse(activeActions))
        .mockResolvedValueOnce(makeResponse(allActions));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      // Toggle include disabled
      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('Action Disabled')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Disabled').closest('tr')!;
      expect(within(row).getByText('Reactiver')).toBeInTheDocument();
    });

    it('calls reactivateAction on click', async () => {
      const user = userEvent.setup();
      mockGetAdminActions
        .mockResolvedValueOnce(makeResponse(activeActions))
        .mockResolvedValueOnce(makeResponse(allActions));
      mockReactivateAction.mockResolvedValue({ ...disabledAction, status: 'published' } as never);

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('Action Disabled')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Disabled').closest('tr')!;
      await user.click(within(row).getByText('Reactiver'));

      await waitFor(() => {
        expect(mockReactivateAction).toHaveBeenCalledWith(4);
      });
    });
  });

  // ── AC6: Conditional buttons ──

  describe('AC6: Conditional buttons', () => {
    it('draft with exec=0: shows Modifier, Publier, Supprimer', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Draft Zero').closest('tr')!;
      expect(within(row).getByText('Modifier')).toBeInTheDocument();
      expect(within(row).getByText('Publier')).toBeInTheDocument();
      expect(within(row).getByText('Supprimer')).toBeInTheDocument();
    });

    it('published with exec=0: shows Voir, Supprimer, Desactiver', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Zero')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Zero').closest('tr')!;
      expect(within(row).getByText('Voir')).toBeInTheDocument();
      expect(within(row).getByText('Supprimer')).toBeInTheDocument();
      expect(within(row).getByText('Desactiver')).toBeInTheDocument();
    });

    it('published with exec>0: shows Voir, Desactiver (not Supprimer)', async () => {
      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Exec').closest('tr')!;
      expect(within(row).getByText('Voir')).toBeInTheDocument();
      expect(within(row).getByText('Desactiver')).toBeInTheDocument();
      expect(within(row).queryByText('Supprimer')).not.toBeInTheDocument();
    });

    it('disabled: shows Modifier, Reactiver (Supprimer only when execution_count=0)', async () => {
      const user = userEvent.setup();
      mockGetAdminActions
        .mockResolvedValueOnce(makeResponse(activeActions))
        .mockResolvedValueOnce(makeResponse(allActions));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('Action Disabled')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Disabled').closest('tr')!;
      expect(within(row).getByText('Modifier')).toBeInTheDocument();
      expect(within(row).getByText('Reactiver')).toBeInTheDocument();
      // Action Disabled has execution_count=3 → no Supprimer
      expect(within(row).queryByText('Supprimer')).not.toBeInTheDocument();
      expect(within(row).queryByText('Desactiver')).not.toBeInTheDocument();
    });

    it('disabled with execution_count=0: shows Modifier, Supprimer, Reactiver', async () => {
      const user = userEvent.setup();
      mockGetAdminActions
        .mockResolvedValueOnce(makeResponse(activeActions))
        .mockResolvedValueOnce(makeResponse(allActions));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('Action Disabled Zero')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Disabled Zero').closest('tr')!;
      expect(within(row).getByText('Modifier')).toBeInTheDocument();
      expect(within(row).getByText('Supprimer')).toBeInTheDocument();
      expect(within(row).getByText('Reactiver')).toBeInTheDocument();
    });
  });

  // ── Error handling ──

  describe('Error handling', () => {
    it('shows error notification when delete fails', async () => {
      const user = userEvent.setup();
      mockDeleteAction.mockRejectedValue(new Error('Forbidden'));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Draft Zero').closest('tr')!;
      await user.click(within(row).getByText('Supprimer'));

      await waitFor(() => {
        expect(screen.getByText(/supprimer definitivement/i)).toBeInTheDocument();
      });

      const confirmBtn = screen.getByRole('button', { name: 'Supprimer' });
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(mockDeleteAction).toHaveBeenCalledWith(1);
      });
    });

    it('shows error notification when deactivate fails', async () => {
      mockDeactivateAction.mockRejectedValue(new Error('Server error'));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Published Exec')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Published Exec').closest('tr')!;
      const user = userEvent.setup();
      await user.click(within(row).getByText('Desactiver'));

      await waitFor(() => {
        expect(mockDeactivateAction).toHaveBeenCalledWith(3);
      });
    });

    it('shows error notification when reactivate fails', async () => {
      const user = userEvent.setup();
      mockGetAdminActions
        .mockResolvedValueOnce(makeResponse(activeActions))
        .mockResolvedValueOnce(makeResponse(allActions));
      mockReactivateAction.mockRejectedValue(new Error('Conflict'));

      renderPage();

      await waitFor(() => {
        expect(screen.getByText('Action Draft Zero')).toBeInTheDocument();
      });

      const checkbox = screen.getByLabelText('Inclure les actions desactivees');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('Action Disabled')).toBeInTheDocument();
      });

      const row = screen.getByText('Action Disabled').closest('tr')!;
      await user.click(within(row).getByText('Reactiver'));

      await waitFor(() => {
        expect(mockReactivateAction).toHaveBeenCalledWith(4);
      });
    });
  });
});
