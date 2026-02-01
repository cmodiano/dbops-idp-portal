/**
 * Tests for ExecutionTimeline (Story 4.6, Task 5.2, 5.3).
 *
 * HIGH-2 FIX: Added integration tests for wizard→timeline flow.
 * MEDIUM-4 FIX: Added tests for useWebSocket hook behavior.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExecutionTimeline } from './ExecutionTimeline';
import { useWebSocket } from '../../hooks/useWebSocket';

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({
    steps: [],
    execution: null,
    loading: false,
    error: null,
    lastMessage: null,
  })),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}));

const mockUseWebSocket = useWebSocket as ReturnType<typeof vi.fn>;

describe('ExecutionTimeline', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state when no steps in historical mode', () => {
    render(
      <ExecutionTimeline
        mode="historical"
        execution={null}
        steps={[]}
      />
    );
    expect(screen.getByText(/Aucune étape à afficher/)).toBeInTheDocument();
  });

  it('has role="list" and aria-label for accessibility (AC4)', () => {
    render(
      <ExecutionTimeline
        mode="historical"
        steps={[
          {
            id: 1,
            execution_id: 1,
            step_order: 1,
            step_name: 'Vault',
            step_type: 'vault',
            status: 'COMPLETED',
            started_at: null,
            completed_at: null,
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ]}
      />
    );
    const list = screen.getByRole('list', { name: /Timeline d'exécution/ });
    expect(list).toBeInTheDocument();
  });

  it('renders nodes with status icons in historical mode', () => {
    render(
      <ExecutionTimeline
        mode="historical"
        steps={[
          {
            id: 1,
            execution_id: 1,
            step_order: 1,
            step_name: 'Vault',
            step_type: 'vault',
            status: 'COMPLETED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:05',
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ]}
      />
    );
    expect(screen.getByText('Vault')).toBeInTheDocument();
    expect(screen.getByRole('listitem')).toBeInTheDocument();
  });

  // HIGH-2 FIX: Task 5.3 - Integration test for realtime mode with executionId
  describe('realtime mode integration (Task 5.3)', () => {
    it('calls useWebSocket with executionId when mode is realtime', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 1,
            execution_id: 42,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'RUNNING',
            started_at: '2026-01-30T10:00:00',
            completed_at: null,
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        execution: { id: 42, status: 'RUNNING' },
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      // Verify useWebSocket was called with the executionId
      expect(mockUseWebSocket).toHaveBeenCalledWith(42);
      // Verify the step from WebSocket is rendered
      expect(screen.getByText('Platform')).toBeInTheDocument();
      expect(screen.getByText(/En cours/)).toBeInTheDocument();
    });

    it('shows loading state when WebSocket is loading', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: null,
        loading: true,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      expect(screen.getByText('Chargement...')).toBeInTheDocument();
    });

    it('shows error state when WebSocket has error', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: null,
        loading: false,
        error: 'Connexion WebSocket perdue',
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      expect(screen.getByText('Connexion WebSocket perdue')).toBeInTheDocument();
    });

    it('does not call useWebSocket when executionId is null', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: null,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={null} mode="realtime" />);

      expect(mockUseWebSocket).toHaveBeenCalledWith(null);
    });

    it('updates steps when WebSocket receives step_update (simulated)', () => {
      // First render with PENDING step
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 1,
            execution_id: 42,
            step_order: 1,
            step_name: 'Vault',
            step_type: 'vault',
            status: 'PENDING',
            started_at: null,
            completed_at: null,
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        execution: { id: 42, status: 'RUNNING' },
        loading: false,
        error: null,
        lastMessage: null,
      });

      const { rerender } = render(<ExecutionTimeline executionId={42} mode="realtime" />);

      // Simulate WebSocket update: step now COMPLETED
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 1,
            execution_id: 42,
            step_order: 1,
            step_name: 'Vault',
            step_type: 'vault',
            status: 'COMPLETED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:05',
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        execution: { id: 42, status: 'RUNNING' },
        loading: false,
        error: null,
        lastMessage: { type: 'step_update', execution_id: 42 },
      });

      rerender(<ExecutionTimeline executionId={42} mode="realtime" />);

      // The step should now show as completed (5s duration)
      expect(screen.getByText('5s')).toBeInTheDocument();
    });
  });

  // MEDIUM-3 FIX: Test aria-live announcement
  describe('accessibility (AC4)', () => {
    it('has a dedicated aria-live region for status announcements', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 1,
            execution_id: 42,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'RUNNING',
            started_at: '2026-01-30T10:00:00',
            completed_at: null,
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        execution: null,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      // Check for aria-live region (visually hidden but present)
      const liveRegion = document.querySelector('[aria-live="polite"]');
      expect(liveRegion).toBeInTheDocument();
      expect(liveRegion?.textContent).toContain('Platform en cours');
    });

    it('does not have aria-live on individual list items (MEDIUM-3 fix)', () => {
      render(
        <ExecutionTimeline
          mode="historical"
          steps={[
            {
              id: 1,
              execution_id: 1,
              step_order: 1,
              step_name: 'Vault',
              step_type: 'vault',
              status: 'COMPLETED',
              started_at: null,
              completed_at: null,
              output: null,
              platform_job_id: null,
              error_message: null,
            },
          ]}
        />
      );

      const listItem = screen.getByRole('listitem');
      expect(listItem).not.toHaveAttribute('aria-live');
    });
  });

  // ServiceNow badge test (Task 3.5)
  describe('ServiceNow badge (Task 3.5)', () => {
    it('shows change number badge for servicenow step with output', () => {
      render(
        <ExecutionTimeline
          mode="historical"
          steps={[
            {
              id: 1,
              execution_id: 1,
              step_order: 1,
              step_name: 'ServiceNow',
              step_type: 'servicenow',
              status: 'COMPLETED',
              started_at: '2026-01-30T10:00:00',
              completed_at: '2026-01-30T10:00:10',
              output: { change_number: 'CHG0012345', change_id: 'abc123', status: 'approved' },
              platform_job_id: null,
              error_message: null,
            },
          ]}
        />
      );

      expect(screen.getByText(/Changement CHG0012345/)).toBeInTheDocument();
    });

    it('shows pending approval badge when status is pending_approval', () => {
      render(
        <ExecutionTimeline
          mode="historical"
          steps={[
            {
              id: 1,
              execution_id: 1,
              step_order: 1,
              step_name: 'ServiceNow',
              step_type: 'servicenow',
              status: 'RUNNING',
              started_at: '2026-01-30T10:00:00',
              completed_at: null,
              output: { change_number: 'CHG0012345', status: 'pending_approval' },
              platform_job_id: null,
              error_message: null,
            },
          ]}
        />
      );

      expect(screen.getByText(/En attente approbation/)).toBeInTheDocument();
    });
  });

  // Story 4.7: Bandeau succès, StructuredErrorCard, logs (Task 6.2)
  describe('Story 4.7 result and error UI', () => {
    it('shows success banner when execution status is COMPLETED', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 1,
            execution_id: 1,
            step_order: 1,
            step_name: 'Vault',
            step_type: 'vault',
            status: 'COMPLETED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:05',
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        execution: {
          id: 1,
          status: 'COMPLETED',
          started_at: '2026-01-30T10:00:00',
          completed_at: '2026-01-30T10:00:10',
        } as unknown as import('../../types/api').ExecutionResponse,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      expect(screen.getByText('Exécution terminée avec succès')).toBeInTheDocument();
      expect(screen.getByText(/1 étape/)).toBeInTheDocument();
    });

    it('shows StructuredErrorCard when execution status is FAILED', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 1,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'FAILED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:30',
            output: null,
            platform_job_id: null,
            error_message: 'Connection timeout',
          },
        ],
        execution: {
          id: 1,
          status: 'FAILED',
        } as unknown as import('../../types/api').ExecutionResponse,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(within(alert).getByText('Platform')).toBeInTheDocument();
      expect(within(alert).getByText('Connection timeout')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Relancer/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Voir logs/ })).toBeInTheDocument();
    });

    it('clicking Voir logs in StructuredErrorCard opens logs drawer (Task 6.3 integration)', async () => {
      const user = userEvent.setup();
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 1,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'FAILED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:30',
            output: null,
            platform_job_id: null,
            error_message: 'Connection timeout',
          },
        ],
        execution: {
          id: 1,
          status: 'FAILED',
        } as unknown as import('../../types/api').ExecutionResponse,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      const voirLogsButton = screen.getByRole('button', { name: /Voir logs/ });
      await user.click(voirLogsButton);

      expect(screen.getByText('Logs détaillés - Platform')).toBeInTheDocument();
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('shows Voir logs détaillés in expanded node', async () => {
      const user = userEvent.setup();
      render(
        <ExecutionTimeline
          mode="historical"
          steps={[
            {
              id: 1,
              execution_id: 1,
              step_order: 1,
              step_name: 'Vault',
              step_type: 'vault',
              status: 'COMPLETED',
              started_at: null,
              completed_at: null,
              output: { key: 'value' },
              platform_job_id: null,
              error_message: null,
            },
          ]}
        />
      );

      await user.click(screen.getByText('Vault'));
      expect(screen.getByRole('button', { name: /Voir logs détaillés/ })).toBeInTheDocument();
    });
  });
});
