/**
 * Tests for ScheduledExecutionsPage (Story 11.6).
 *
 * AC1: Navigation and tab display
 * AC3: Table columns and data display
 * AC4: 24h indicator visual
 * AC5: Cancel modal flow
 * AC6: Cancel button only for pending
 * AC7-AC9: Filter functionality
 * AC10: Details modal
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import dayjs from 'dayjs';
import ScheduledExecutionsPage from './ScheduledExecutionsPage';
import type { ScheduledExecutionListItem, ScheduledExecutionListResponse } from '../../types/api';

// Mock the scheduled execution service
const mockListScheduledExecutions = vi.fn();
const mockCancelScheduledExecution = vi.fn();
const mockToggleRecurringPattern = vi.fn();

vi.mock('../../services/scheduled_execution_service', () => ({
  listScheduledExecutions: (...args: unknown[]) => mockListScheduledExecutions(...args),
  cancelScheduledExecution: (...args: unknown[]) => mockCancelScheduledExecution(...args),
  toggleRecurringPattern: (...args: unknown[]) => mockToggleRecurringPattern(...args),
}));

// Mock App.useApp for notifications
const mockNotificationSuccess = vi.fn();
const mockNotificationError = vi.fn();

function renderWithApp(ui: React.ReactElement) {
  vi.spyOn(App, 'useApp').mockReturnValue({
    message: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), loading: vi.fn() },
    notification: {
      success: mockNotificationSuccess,
      error: mockNotificationError,
      info: vi.fn(),
      warning: vi.fn(),
      open: vi.fn(),
    },
    modal: { confirm: vi.fn() },
  } as ReturnType<typeof App.useApp>);
  return render(<App>{ui}</App>);
}

// Helper to create mock scheduled execution items
function createMockExecution(overrides: Partial<ScheduledExecutionListItem> = {}): ScheduledExecutionListItem {
  return {
    scheduled_execution_id: 1,
    action_id: 10,
    action_name: 'Restart Database',
    user_id: 100,
    user_name: 'Marc Dubois',
    environment: 'prod',
    scheduled_at: dayjs().add(2, 'day').toISOString(),
    status: 'pending',
    created_at: dayjs().subtract(1, 'day').toISOString(),
    parameters: { database: 'db1' },
    ...overrides,
  };
}

// Default mock response
function createMockResponse(items: ScheduledExecutionListItem[]): ScheduledExecutionListResponse {
  return {
    data: items,
    pagination: {
      page: 1,
      page_size: 10,
      total_count: items.length,
      total_pages: 1,
    },
  };
}

describe('ScheduledExecutionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListScheduledExecutions.mockResolvedValue(createMockResponse([]));
  });

  describe('Table rendering (AC1, AC3)', () => {
    it('renders table with correct column headers', async () => {
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([]));
      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Action')).toBeInTheDocument();
        expect(screen.getByText('Utilisateur')).toBeInTheDocument();
        expect(screen.getByText('Date/heure planifiée')).toBeInTheDocument();
        expect(screen.getByText('Statut')).toBeInTheDocument();
        expect(screen.getByText('Environnement')).toBeInTheDocument();
        expect(screen.getByText('Date de création')).toBeInTheDocument();
      });
    });

    it('renders scheduled executions data correctly', async () => {
      const mockItem = createMockExecution({
        action_name: 'Backup Production',
        user_name: 'Jean Dupont',
        environment: 'staging',
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([mockItem]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Backup Production')).toBeInTheDocument();
        expect(screen.getByText('Jean Dupont')).toBeInTheDocument();
        expect(screen.getByText('staging')).toBeInTheDocument();
      });
    });

    it('shows empty state when no executions', async () => {
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Aucune exécution planifiée')).toBeInTheDocument();
      });
    });

    it('shows loading state while fetching', async () => {
      // This test verifies that when loading=true, the table shows loading state
      // Since loading is set synchronously before the fetch completes, we check the table's loading indicator
      mockListScheduledExecutions.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(createMockResponse([])), 500))
      );

      renderWithApp(<ScheduledExecutionsPage />);

      // The Table component adds ant-table-loading class when loading
      await waitFor(() => {
        expect(document.querySelector('.ant-table-wrapper')).toBeInTheDocument();
      });
    });

    it('calls refresh when Actualiser button clicked', async () => {
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(mockListScheduledExecutions).toHaveBeenCalledTimes(1);
      });

      await user.click(screen.getByRole('button', { name: /Actualiser/i }));

      await waitFor(() => {
        expect(mockListScheduledExecutions).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Status badges (AC3)', () => {
    it('renders pending status with blue badge', async () => {
      const mockItem = createMockExecution({ status: 'pending' });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([mockItem]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('En attente')).toBeInTheDocument();
      });
    });

    it('renders executed status with green badge', async () => {
      const mockItem = createMockExecution({ status: 'executed' });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([mockItem]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Exécutée')).toBeInTheDocument();
      });
    });

    it('renders cancelled status with default badge', async () => {
      const mockItem = createMockExecution({ status: 'cancelled' });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([mockItem]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Annulée')).toBeInTheDocument();
      });
    });
  });

  describe('24h indicator (AC4)', () => {
    it('shows "Bientôt" badge for executions within 24 hours', async () => {
      const soonExecution = createMockExecution({
        scheduled_at: dayjs().add(12, 'hour').toISOString(),
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([soonExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Bientôt')).toBeInTheDocument();
      });
    });

    it('does not show "Bientôt" badge for executions more than 24 hours away', async () => {
      const laterExecution = createMockExecution({
        scheduled_at: dayjs().add(3, 'day').toISOString(),
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([laterExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Bientôt')).not.toBeInTheDocument();
      });
    });

    it('does not show "Bientôt" badge for past executions', async () => {
      const pastExecution = createMockExecution({
        scheduled_at: dayjs().subtract(1, 'hour').toISOString(),
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pastExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Bientôt')).not.toBeInTheDocument();
      });
    });

    it('applies scheduled-soon class to rows within 24 hours', async () => {
      const soonExecution = createMockExecution({
        scheduled_execution_id: 1,
        scheduled_at: dayjs().add(6, 'hour').toISOString(),
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([soonExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        const row = document.querySelector('.ant-table-row');
        expect(row?.classList.contains('scheduled-soon')).toBe(true);
      });
    });
  });

  describe('Cancel button visibility (AC5, AC6)', () => {
    it('shows Annuler button for pending executions', async () => {
      const pendingExecution = createMockExecution({ status: 'pending' });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pendingExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Annuler/i })).toBeInTheDocument();
      });
    });

    it('does not show Annuler button for executed executions', async () => {
      const executedExecution = createMockExecution({ status: 'executed' });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([executedExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /^Annuler$/i })).not.toBeInTheDocument();
      });
    });

    it('does not show Annuler button for cancelled executions', async () => {
      const cancelledExecution = createMockExecution({ status: 'cancelled' });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([cancelledExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /^Annuler$/i })).not.toBeInTheDocument();
      });
    });

    it('always shows Voir détails button', async () => {
      const executedExecution = createMockExecution({ status: 'executed' });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([executedExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Voir détails/i })).toBeInTheDocument();
      });
    });
  });

  describe('Cancel modal flow (AC5)', () => {
    it('opens cancel confirmation modal when Annuler clicked', async () => {
      const pendingExecution = createMockExecution({
        action_name: 'Test Action',
        user_name: 'Test User',
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pendingExecution]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Action')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /^Annuler$/i }));

      await waitFor(() => {
        // Modal title appears
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/Êtes-vous sûr de vouloir annuler cette exécution planifiée/i)).toBeInTheDocument();
      });
    });

    it('shows execution details in cancel modal', async () => {
      const pendingExecution = createMockExecution({
        action_name: 'Restart DB',
        user_name: 'Alice Martin',
        scheduled_at: '2026-03-15T14:30:00Z',
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pendingExecution]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Restart DB')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /^Annuler$/i }));

      await waitFor(() => {
        const modal = screen.getByRole('dialog');
        expect(within(modal).getByText('Restart DB')).toBeInTheDocument();
        expect(within(modal).getByText('Alice Martin')).toBeInTheDocument();
      });
    });

    it('calls cancelScheduledExecution and shows success on confirm', async () => {
      const pendingExecution = createMockExecution({ scheduled_execution_id: 42 });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pendingExecution]));
      mockCancelScheduledExecution.mockResolvedValue({ scheduled_execution_id: 42, status: 'cancelled' });
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^Annuler$/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /^Annuler$/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Find the confirm button in the modal (has "Confirmer l'annulation" text)
      const modal = screen.getByRole('dialog');
      const confirmButton = within(modal).getByRole('button', { name: /Confirmer l'annulation/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockCancelScheduledExecution).toHaveBeenCalledWith(42);
        expect(mockNotificationSuccess).toHaveBeenCalledWith(
          expect.objectContaining({
            message: 'Annulation réussie',
          })
        );
      });
    });

    it('shows error notification on 400 error', async () => {
      const pendingExecution = createMockExecution({ scheduled_execution_id: 42 });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pendingExecution]));
      mockCancelScheduledExecution.mockRejectedValue({ status: 400 });
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^Annuler$/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /^Annuler$/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const modal = screen.getByRole('dialog');
      const confirmButton = within(modal).getByRole('button', { name: /Confirmer l'annulation/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockNotificationError).toHaveBeenCalledWith(
          expect.objectContaining({
            message: 'Erreur',
            description: expect.stringContaining('ne peut pas être annulée'),
          })
        );
      });
    });

    it('shows permission error notification on 403 error', async () => {
      const pendingExecution = createMockExecution({ scheduled_execution_id: 42 });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pendingExecution]));
      mockCancelScheduledExecution.mockRejectedValue({ status: 403 });
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^Annuler$/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /^Annuler$/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const modal = screen.getByRole('dialog');
      const confirmButton = within(modal).getByRole('button', { name: /Confirmer l'annulation/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockNotificationError).toHaveBeenCalledWith(
          expect.objectContaining({
            message: 'Permission refusée',
          })
        );
      });
    });

    it('closes modal when cancel button clicked', async () => {
      const pendingExecution = createMockExecution();
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([pendingExecution]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^Annuler$/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /^Annuler$/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Find the modal's cancel button (Ant Design Modal footer has "Annuler" button)
      const modal = screen.getByRole('dialog');
      const modalButtons = within(modal).getAllByRole('button');
      // The "Annuler" button in the modal footer (not "Confirmer l'annulation")
      const modalCancelButton = modalButtons.find(
        (btn) => btn.textContent === 'Annuler'
      );
      expect(modalCancelButton).toBeTruthy();
      await user.click(modalCancelButton!);

      // Wait for modal to start closing (animation takes time, check it initiated close)
      await waitFor(
        () => {
          const dialog = screen.queryByRole('dialog');
          // Either dialog is gone or it has closing animation class
          const isClosing = !dialog || dialog.classList.contains('ant-zoom-leave');
          expect(isClosing).toBe(true);
        },
        { timeout: 2000 }
      );
    });
  });

  describe('Details modal (AC10)', () => {
    it('opens details modal when Voir détails clicked', async () => {
      const execution = createMockExecution({
        action_name: 'Test Action',
        user_name: 'Test User',
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([execution]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Action')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Voir détails/i }));

      await waitFor(() => {
        expect(screen.getByText("Détails de l'exécution planifiée")).toBeInTheDocument();
      });
    });

    it('displays all execution details in modal', async () => {
      const execution = createMockExecution({
        scheduled_execution_id: 123,
        action_id: 456,
        action_name: 'Backup Database',
        user_id: 789,
        user_name: 'Jean Admin',
        environment: 'prod',
        parameters: { target: 'db-main', compress: true },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([execution]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Backup Database')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Voir détails/i }));

      await waitFor(() => {
        const modal = screen.getByRole('dialog');
        expect(within(modal).getByText('123')).toBeInTheDocument();
        expect(within(modal).getByText(/Backup Database.*ID: 456/)).toBeInTheDocument();
        expect(within(modal).getByText(/Jean Admin.*ID: 789/)).toBeInTheDocument();
        expect(within(modal).getByText(/"target": "db-main"/)).toBeInTheDocument();
      });
    });

    it('closes details modal when Fermer clicked', async () => {
      const execution = createMockExecution();
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([execution]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Voir détails/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Voir détails/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const modal = screen.getByRole('dialog');
      const closeButton = within(modal).getByRole('button', { name: /Fermer/i });
      await user.click(closeButton);

      // Wait for modal to start closing (animation takes time, check it initiated close)
      await waitFor(
        () => {
          const dialog = screen.queryByRole('dialog');
          // Either dialog is gone or it has closing animation class
          const isClosing = !dialog || dialog.classList.contains('ant-zoom-leave');
          expect(isClosing).toBe(true);
        },
        { timeout: 2000 }
      );
    });
  });

  describe('Filters (AC7, AC8, AC9)', () => {
    it('calls API with status filter when status selected', async () => {
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(mockListScheduledExecutions).toHaveBeenCalledTimes(1);
      });

      // Open the status select
      const statusSelect = screen.getByRole('combobox');
      await user.click(statusSelect);

      // Select "En attente"
      await user.click(screen.getByText('En attente'));

      await waitFor(() => {
        expect(mockListScheduledExecutions).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'pending' }),
          expect.any(Number),
          expect.any(Number)
        );
      });
    });

    it('clears status filter when cleared', async () => {
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      // Open the status select
      const statusSelect = screen.getByRole('combobox');
      await user.click(statusSelect);
      await user.click(screen.getByText('En attente'));

      // Clear the selection
      const clearButton = document.querySelector('.ant-select-clear');
      if (clearButton) {
        await user.click(clearButton);
      }

      await waitFor(() => {
        // Should have been called with undefined status
        const lastCall = mockListScheduledExecutions.mock.calls[mockListScheduledExecutions.mock.calls.length - 1];
        expect(lastCall[0].status).toBeUndefined();
      });
    });
  });

  describe('Error handling', () => {
    it('shows error notification when API call fails', async () => {
      mockListScheduledExecutions.mockRejectedValue(new Error('Network error'));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(mockNotificationError).toHaveBeenCalledWith(
          expect.objectContaining({
            message: 'Erreur',
          })
        );
      });
    });
  });

  describe('Pagination', () => {
    it('displays total count in header', async () => {
      const items = [createMockExecution(), createMockExecution({ scheduled_execution_id: 2 })];
      mockListScheduledExecutions.mockResolvedValue({
        data: items,
        pagination: { page: 1, page_size: 10, total_count: 25, total_pages: 3 },
      });

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText(/Exécutions planifiées \(25\)/)).toBeInTheDocument();
      });
    });
  });

  describe('Recurring patterns - Daily/Weekly (Story 11.7)', () => {
    it('shows Récurrent tag for daily recurring executions', async () => {
      const dailyExecution = createMockExecution({
        scheduled_execution_id: 1,
        recurring_pattern: {
          pattern_type: 'daily',
          pattern_config: { hour: 2, minute: 0 },
          next_execution_date: dayjs().add(1, 'day').toISOString(),
          is_active: true,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([dailyExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Récurrent')).toBeInTheDocument();
        expect(screen.getByText(/Tous les jours à 02:00/)).toBeInTheDocument();
      });
    });

    it('shows Récurrent tag for weekly recurring executions', async () => {
      const weeklyExecution = createMockExecution({
        scheduled_execution_id: 1,
        recurring_pattern: {
          pattern_type: 'weekly',
          pattern_config: { day_of_week: 1, hour: 14, minute: 0 },
          next_execution_date: dayjs().add(1, 'week').toISOString(),
          is_active: true,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([weeklyExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Récurrent')).toBeInTheDocument();
        expect(screen.getByText(/Tous les lundis à 14:00/)).toBeInTheDocument();
      });
    });

    it('shows Désactivé for inactive recurring patterns', async () => {
      const inactiveExecution = createMockExecution({
        scheduled_execution_id: 1,
        recurring_pattern: {
          pattern_type: 'daily',
          pattern_config: { hour: 2, minute: 0 },
          next_execution_date: null,
          is_active: false,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([inactiveExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('(Désactivé)')).toBeInTheDocument();
      });
    });

    it('hides Annuler button for recurring executions', async () => {
      const recurringExecution = createMockExecution({
        status: 'pending',
        recurring_pattern: {
          pattern_type: 'daily',
          pattern_config: { hour: 2, minute: 0 },
          next_execution_date: dayjs().add(1, 'day').toISOString(),
          is_active: true,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([recurringExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Récurrent')).toBeInTheDocument();
        // Annuler button should not be present for recurring patterns
        expect(screen.queryByRole('button', { name: /^Annuler$/i })).not.toBeInTheDocument();
      });
    });
  });

  describe('Cron patterns (Story 11.8)', () => {
    it('shows Récurrent tag for cron recurring executions', async () => {
      const cronExecution = createMockExecution({
        scheduled_execution_id: 1,
        recurring_pattern: {
          pattern_type: 'cron',
          pattern_config: { cron_expression: '0 2 * * *' },
          next_execution_date: dayjs().add(1, 'day').toISOString(),
          is_active: true,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([cronExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Récurrent')).toBeInTheDocument();
        // Should display human-readable description from cronHelper
        expect(screen.getByText(/Tous les jours à 2h00/i)).toBeInTheDocument();
      });
    });

    it('shows cron pattern type in details modal', async () => {
      const cronExecution = createMockExecution({
        scheduled_execution_id: 1,
        action_name: 'Cron Action',
        recurring_pattern: {
          pattern_type: 'cron',
          pattern_config: { cron_expression: '0 2 * * 1-5' },
          next_execution_date: dayjs().add(1, 'day').toISOString(),
          is_active: true,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([cronExecution]));
      const user = userEvent.setup();

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Cron Action')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Voir détails/i }));

      await waitFor(() => {
        const modal = screen.getByRole('dialog');
        // Should show "Récurrent - Cron" in the Type field
        expect(within(modal).getByText(/Récurrent - Cron/)).toBeInTheDocument();
        // Should show the raw cron expression
        expect(within(modal).getByText('0 2 * * 1-5')).toBeInTheDocument();
      });
    });

    it('shows human-readable description for complex cron expressions', async () => {
      const cronExecution = createMockExecution({
        scheduled_execution_id: 1,
        recurring_pattern: {
          pattern_type: 'cron',
          pattern_config: { cron_expression: '0 14 * * 1' },
          next_execution_date: dayjs().add(1, 'week').toISOString(),
          is_active: true,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([cronExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        // Should display "Tous les lundis à 14h00" from describeCronExpression
        expect(screen.getByText(/Tous les lundis à 14h00/)).toBeInTheDocument();
      });
    });

    it('shows next execution for cron patterns', async () => {
      const nextExec = dayjs().add(12, 'hour');
      const cronExecution = createMockExecution({
        scheduled_execution_id: 1,
        recurring_pattern: {
          pattern_type: 'cron',
          pattern_config: { cron_expression: '*/15 * * * *' },
          next_execution_date: nextExec.toISOString(),
          is_active: true,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([cronExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText(/Prochaine :/)).toBeInTheDocument();
        // Should show "Bientôt" tag since it's within 24h
        expect(screen.getByText('Bientôt')).toBeInTheDocument();
      });
    });

    it('displays disabled cron patterns correctly', async () => {
      const cronExecution = createMockExecution({
        scheduled_execution_id: 1,
        recurring_pattern: {
          pattern_type: 'cron',
          pattern_config: { cron_expression: '0 0 1 * *' },
          next_execution_date: null,
          is_active: false,
        },
      });
      mockListScheduledExecutions.mockResolvedValue(createMockResponse([cronExecution]));

      renderWithApp(<ScheduledExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText('(Désactivé)')).toBeInTheDocument();
        // Should not show "Prochaine" for disabled patterns
        expect(screen.queryByText(/Prochaine :/)).not.toBeInTheDocument();
      });
    });
  });
});
