/**
 * Tests for ExecutionTimeline (Story 4.6, Task 5.2, 5.3).
 *
 * HIGH-2 FIX: Added integration tests for wizard→timeline flow.
 * MEDIUM-4 FIX: Added tests for useWebSocket hook behavior.
 * Story 9.1: Added tests for remediation suggestions integration (Task 17).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExecutionTimeline } from './ExecutionTimeline';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useExecutionPolling } from '../../hooks/useExecutionPolling';
import { useRemediationSuggestions } from '../../hooks/useRemediationSuggestions';

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({
    steps: [],
    execution: null,
    loading: false,
    error: null,
    lastMessage: null,
  })),
}));

vi.mock('../../hooks/useExecutionPolling', () => ({
  useExecutionPolling: vi.fn(() => ({
    execution: null,
    steps: [],
    isPolling: false,
    error: null,
  })),
}));

vi.mock('../../hooks/useRemediationSuggestions', () => ({
  useRemediationSuggestions: vi.fn(() => ({
    suggestions: null,
    loading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}));

const mockUseWebSocket = useWebSocket as ReturnType<typeof vi.fn>;
const mockUseExecutionPolling = useExecutionPolling as ReturnType<typeof vi.fn>;
const mockUseRemediationSuggestions = useRemediationSuggestions as ReturnType<typeof vi.fn>;

describe('ExecutionTimeline', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseExecutionPolling.mockReturnValue({
      execution: null,
      steps: [],
      isPolling: false,
      error: null,
    });
    mockUseRemediationSuggestions.mockReturnValue({
      suggestions: null,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
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

    it('falls back to polling when WebSocket has error (Story 19.0, AC8)', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: null,
        loading: false,
        error: 'Connexion WebSocket perdue',
        lastMessage: null,
      });

      // Polling fallback returns data
      mockUseExecutionPolling.mockReturnValue({
        execution: { id: 42, status: 'RUNNING' },
        steps: [
          {
            id: 1,
            execution_id: 42,
            step_order: 1,
            step_name: 'Préparation',
            step_type: 'prerequisite',
            status: 'RUNNING',
            started_at: '2026-02-08T10:00:00',
            completed_at: null,
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        isPolling: true,
        error: null,
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      // Polling mode indicator shown
      expect(screen.getByTestId('polling-mode-alert')).toBeInTheDocument();
      expect(screen.getByText('Mode polling activé (dev)')).toBeInTheDocument();
      // Steps from polling are rendered
      expect(screen.getByText('Préparation')).toBeInTheDocument();
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

  // Story 7.4: PENDING_APPROVAL and REJECTED status display
  describe('Story 7.4 approval workflow status', () => {
    it('shows pending approval banner when execution is PENDING_APPROVAL', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: {
          id: 1,
          status: 'PENDING_APPROVAL',
          environment: 'prod',
        } as unknown as import('../../types/api').ExecutionResponse,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      expect(screen.getByText("En attente d'approbation DBA")).toBeInTheDocument();
      expect(screen.getByText(/Cette exécution nécessite l'approbation/)).toBeInTheDocument();
    });

    it('shows rejected banner when execution is REJECTED', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: {
          id: 1,
          status: 'REJECTED',
          approval_comment: 'Policy violation',
          approved_at: '2026-02-01T10:00:00Z',
        } as unknown as import('../../types/api').ExecutionResponse,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      expect(screen.getByText('Exécution refusée')).toBeInTheDocument();
      expect(screen.getByText(/Cette exécution a été refusée/)).toBeInTheDocument();
      expect(screen.getByText(/Policy violation/)).toBeInTheDocument();
    });

    it('shows approved info in success banner when execution was approved', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 1,
            execution_id: 1,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'COMPLETED',
            started_at: '2026-02-01T10:00:00',
            completed_at: '2026-02-01T10:00:10',
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        execution: {
          id: 1,
          status: 'COMPLETED',
          started_at: '2026-02-01T10:00:00',
          completed_at: '2026-02-01T10:00:10',
          approved_by: 10,
          approved_at: '2026-02-01T09:55:00',
          approval_comment: 'Approved after review',
        } as unknown as import('../../types/api').ExecutionResponse,
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      expect(screen.getByText('Exécution terminée avec succès')).toBeInTheDocument();
      expect(screen.getByText(/Approuvé le/)).toBeInTheDocument();
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

  // Story 9.1: Remediation suggestions integration tests (Task 17)
  describe('Story 9.1 remediation suggestions', () => {
    const mockSuggestions = [
      {
        action_id: 42,
        action_name: 'Fix Database Issue',
        action_description: 'Restarts the database listener',
        matching_rule: {
          error_pattern: 'ORA-\\d+',
          target_action_id: 42,
          environments: ['prod'],
          auto_trigger: false,
          risk_level: 'medium' as const,
        },
      },
      {
        action_id: 10,
        action_name: 'Retry Connection',
        action_description: null,
        matching_rule: {
          error_pattern: 'timeout',
          target_action_id: 10,
          environments: ['dev', 'prod'],
          auto_trigger: true,
          risk_level: 'low' as const,
        },
      },
    ];

    it('calls useRemediationSuggestions with executionId and status', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'FAILED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:30',
            output: null,
            platform_job_id: null,
            error_message: 'ORA-12154: TNS:could not resolve service name',
          },
        ],
        execution: {
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      expect(mockUseRemediationSuggestions).toHaveBeenCalledWith(42, 'FAILED');
    });

    it('passes remediation suggestions to StructuredErrorCard when execution is FAILED', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'FAILED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:30',
            output: null,
            platform_job_id: null,
            error_message: 'ORA-12154: TNS:could not resolve service name',
          },
        ],
        execution: {
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: null,
      });

      mockUseRemediationSuggestions.mockReturnValue({
        suggestions: mockSuggestions,
        loading: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      // Verify remediation suggestions section is shown in StructuredErrorCard
      expect(screen.getByText('Actions correctives suggérées')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Fix Database Issue/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry Connection/i })).toBeInTheDocument();
    });

    it('passes suggestionsLoading to StructuredErrorCard', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
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
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: null,
      });

      mockUseRemediationSuggestions.mockReturnValue({
        suggestions: null,
        loading: true,
        error: null,
        refetch: vi.fn(),
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      // When loading, StructuredErrorCard should show the loading state
      expect(screen.getByText('Actions correctives suggérées')).toBeInTheDocument();
    });

    it('calls onSuggestionClick when a suggestion is clicked', async () => {
      const user = userEvent.setup();
      const onSuggestionClick = vi.fn();

      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
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
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: null,
      });

      mockUseRemediationSuggestions.mockReturnValue({
        suggestions: mockSuggestions,
        loading: false,
        error: null,
        refetch: vi.fn(),
      });

      render(
        <ExecutionTimeline
          executionId={42}
          mode="realtime"
          onSuggestionClick={onSuggestionClick}
        />
      );

      await user.click(screen.getByRole('button', { name: /Fix Database Issue/i }));

      expect(onSuggestionClick).toHaveBeenCalledTimes(1);
      expect(onSuggestionClick).toHaveBeenCalledWith(mockSuggestions[0]);
    });

    it('does not show remediation suggestions when execution is not FAILED', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'COMPLETED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:30',
            output: null,
            platform_job_id: null,
            error_message: null,
          },
        ],
        execution: {
          id: 42,
          status: 'COMPLETED',
          started_at: '2026-01-30T10:00:00',
          completed_at: '2026-01-30T10:00:30',
        },
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      expect(screen.queryByText('Actions correctives suggérées')).not.toBeInTheDocument();
    });

    it('does not show suggestions section when no suggestions and not loading', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
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
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: null,
      });

      mockUseRemediationSuggestions.mockReturnValue({
        suggestions: [],
        loading: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      // StructuredErrorCard should not show remediation section when no suggestions
      expect(screen.queryByText('Actions correctives suggérées')).not.toBeInTheDocument();
    });
  });

  // Story 9.3: Auto-remediation timeline features (Tasks 22-24)
  describe('Story 9.3 auto-remediation timeline', () => {
    it('shows auto-remediation progress card when WebSocket sends auto_remediation_started', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'FAILED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:30',
            output: null,
            platform_job_id: null,
            error_message: 'ORA-12154: TNS error',
          },
        ],
        execution: {
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: {
          type: 'auto_remediation_started',
          data: {
            child_execution_id: 100,
            corrective_action_name: 'Restart Database Listener',
          },
        },
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      expect(screen.getByText('Auto-remédiation en cours')).toBeInTheDocument();
      expect(screen.getByText(/Restart Database Listener/)).toBeInTheDocument();
    });

    it('shows fallback alert when WebSocket sends auto_remediation_failed', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [
          {
            id: 101,
            execution_id: 42,
            step_order: 1,
            step_name: 'Platform',
            step_type: 'platform',
            status: 'FAILED',
            started_at: '2026-01-30T10:00:00',
            completed_at: '2026-01-30T10:00:30',
            output: null,
            platform_job_id: null,
            error_message: 'ORA-12154: TNS error',
          },
        ],
        execution: {
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: {
          type: 'auto_remediation_failed',
          data: {
            child_execution_id: 100,
            message: 'Service unavailable',
          },
        },
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      expect(screen.getByText(/Tentative de correction automatique échouée/)).toBeInTheDocument();
      expect(screen.getByText(/évaluer manuellement/i)).toBeInTheDocument();
    });

    it('clears auto-remediation state when execution changes', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: {
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: {
          type: 'auto_remediation_started',
          data: {
            child_execution_id: 100,
            corrective_action_name: 'Fix Action',
          },
        },
      });

      const { rerender } = render(<ExecutionTimeline executionId={42} mode="realtime" />);

      expect(screen.getByText('Auto-remédiation en cours')).toBeInTheDocument();

      // Simulate switching to a different execution
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: {
          id: 99,
          status: 'RUNNING',
        },
        loading: false,
        error: null,
        lastMessage: null,
      });

      rerender(<ExecutionTimeline executionId={99} mode="realtime" />);

      expect(screen.queryByText('Auto-remédiation en cours')).not.toBeInTheDocument();
    });

    it('provides link to child execution in auto-remediation progress card', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: {
          id: 42,
          status: 'FAILED',
        },
        loading: false,
        error: null,
        lastMessage: {
          type: 'auto_remediation_started',
          data: {
            child_execution_id: 100,
            corrective_action_name: 'Fix Action',
          },
        },
      });

      render(<ExecutionTimeline executionId={42} mode="realtime" />);

      const link = screen.getByRole('link', { name: /Voir exécution corrective/i });
      expect(link).toHaveAttribute('href', '/executions/100');
    });
  });

  // Story 19.0: Polling fallback tests (AC8, AC10, AC12)
  describe('Story 19.0 polling fallback', () => {
    it('does not show polling indicator when WebSocket is connected', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: { id: 1, status: 'RUNNING' },
        loading: false,
        error: null,
        lastMessage: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      expect(screen.queryByTestId('polling-mode-alert')).not.toBeInTheDocument();
    });

    it('activates polling and shows indicator when WebSocket errors', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: null,
        loading: false,
        error: 'WebSocket error',
        lastMessage: null,
      });

      mockUseExecutionPolling.mockReturnValue({
        execution: { id: 1, status: 'RUNNING' },
        steps: [],
        isPolling: true,
        error: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      expect(screen.getByTestId('polling-mode-alert')).toBeInTheDocument();
      // useExecutionPolling was called with enabled=true
      expect(mockUseExecutionPolling).toHaveBeenCalledWith(
        expect.objectContaining({ executionId: 1, enabled: true }),
      );
    });

    it('uses polling data for steps and execution when polling is active', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: null,
        loading: false,
        error: 'WebSocket unavailable',
        lastMessage: null,
      });

      mockUseExecutionPolling.mockReturnValue({
        execution: { id: 1, status: 'COMPLETED', started_at: '2026-02-08T10:00:00Z', completed_at: '2026-02-08T10:01:00Z' },
        steps: [
          {
            id: 1, execution_id: 1, step_order: 1, step_name: 'Préparation',
            step_type: 'prerequisite', status: 'COMPLETED',
            started_at: '2026-02-08T10:00:00Z', completed_at: '2026-02-08T10:00:05Z',
            output: null, platform_job_id: null, error_message: null,
          },
          {
            id: 2, execution_id: 1, step_order: 2, step_name: 'Vault',
            step_type: 'vault', status: 'COMPLETED',
            started_at: '2026-02-08T10:00:05Z', completed_at: '2026-02-08T10:00:10Z',
            output: null, platform_job_id: null, error_message: null,
          },
        ],
        isPolling: true,
        error: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      // Both steps from polling are rendered
      expect(screen.getByText('Préparation')).toBeInTheDocument();
      expect(screen.getByText('Vault')).toBeInTheDocument();
      // Success banner from polling execution
      expect(screen.getByText('Exécution terminée avec succès')).toBeInTheDocument();
    });

    it('does not activate polling in historical mode', () => {
      render(
        <ExecutionTimeline
          mode="historical"
          execution={{ id: 1, status: 'COMPLETED' } as any}
          steps={[]}
        />
      );

      expect(mockUseExecutionPolling).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false }),
      );
    });

    it('does not show polling indicator when not actively polling', () => {
      mockUseWebSocket.mockReturnValue({
        steps: [],
        execution: { id: 1, status: 'RUNNING' },
        loading: false,
        error: null,
        lastMessage: null,
      });

      mockUseExecutionPolling.mockReturnValue({
        execution: null,
        steps: [],
        isPolling: false,
        error: null,
      });

      render(<ExecutionTimeline executionId={1} mode="realtime" />);

      expect(screen.queryByTestId('polling-mode-alert')).not.toBeInTheDocument();
    });
  });
});
