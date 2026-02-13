/**
 * StepDetailDrawer tests (Story 19.3).
 * Covers AC1 (drawer opens), AC2 (timeline), AC3 (metadata header),
 * AC4 (real-time updates), AC5 (close), AC9 (error card), AC10 (pending step).
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { StepDetailDrawer } from './StepDetailDrawer';
import type { WorkflowStep, ExecutionStepResponse } from '../../types/api';

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

const mockWorkflowSteps: WorkflowStep[] = [
  {
    order: 1,
    name: 'Build',
    referenced_action_id: 10,
    action_name: 'Build Action',
    step_id: 'step-1',
    on_success_step_id: 'step-2',
    on_error_step_id: null,
    retry_enabled: false,
  },
  {
    order: 2,
    name: 'Deploy',
    referenced_action_id: 11,
    action_name: 'Deploy Action',
    step_id: 'step-2',
    on_success_step_id: null,
    on_error_step_id: null,
    retry_enabled: false,
  },
];

const mockExecutionSteps: ExecutionStepResponse[] = [
  {
    id: 1,
    execution_id: 1,
    step_order: 1,
    step_name: 'Build',
    step_type: 'platform',
    status: 'COMPLETED',
    started_at: '2026-02-08T10:00:00Z',
    completed_at: '2026-02-08T10:02:15Z',
    output: { result: 'Build successful' },
    platform_job_id: null,
    error_message: null,
  },
  {
    id: 2,
    execution_id: 1,
    step_order: 2,
    step_name: 'Deploy',
    step_type: 'platform',
    status: 'RUNNING',
    started_at: '2026-02-08T10:02:20Z',
    completed_at: null,
    output: null,
    platform_job_id: null,
    error_message: null,
  },
];

describe('StepDetailDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('AC1: renders drawer when open and stepId provided', () => {
    render(
      <StepDetailDrawer
        open
        stepId="step-1"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId('step-detail-drawer')).toBeInTheDocument();
  });

  it('AC1: does not render when open is false', () => {
    render(
      <StepDetailDrawer
        open={false}
        stepId="step-1"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByTestId('step-detail-drawer')).not.toBeInTheDocument();
  });

  it('AC3: displays step metadata in header', () => {
    render(
      <StepDetailDrawer
        open
        stepId="step-1"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    const header = screen.getByTestId('step-detail-header');
    expect(header).toBeInTheDocument();
    // Header contains step title, order, action name, status, and duration
    expect(header.textContent).toContain('Build');
    expect(header.textContent).toContain('#1');
    expect(header.textContent).toContain('Build Action');
    expect(header.textContent).toContain('Terminé');
    expect(header.textContent).toContain('2m 15s');
  });

  it('AC2: displays step detail content for selected step', () => {
    render(
      <StepDetailDrawer
        open
        stepId="step-1"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    // Step detail shows step info card with status
    const header = screen.getByTestId('step-detail-header');
    expect(header.textContent).toContain('Build');
    expect(header.textContent).toContain('Terminé');
  });

  it('AC5: calls onClose when close button clicked', async () => {
    const onClose = vi.fn();
    render(
      <StepDetailDrawer
        open
        stepId="step-1"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={onClose}
      />,
    );

    const closeButton = screen.getByTestId('step-detail-close');
    await userEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('AC4: updates step details when executionSteps prop changes', () => {
    const { rerender } = render(
      <StepDetailDrawer
        open
        stepId="step-2"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    // Initial: step RUNNING
    const header = screen.getByTestId('step-detail-header');
    expect(header.textContent).toContain('En cours');

    // Update: step COMPLETED
    const updatedSteps = mockExecutionSteps.map((s) =>
      s.step_order === 2
        ? { ...s, status: 'COMPLETED' as const, completed_at: '2026-02-08T10:05:00Z' }
        : s,
    );

    rerender(
      <StepDetailDrawer
        open
        stepId="step-2"
        executionId={1}
        executionSteps={updatedSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    expect(header.textContent).toContain('Terminé');
  });

  it('AC9: displays StructuredErrorCard for FAILED step', () => {
    const failedSteps: ExecutionStepResponse[] = [
      {
        ...mockExecutionSteps[0],
        status: 'FAILED',
        error_message: 'Build failed: syntax error in main.py',
      },
    ];

    render(
      <StepDetailDrawer
        open
        stepId="step-1"
        executionId={1}
        executionSteps={failedSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    const errorCard = screen.getByRole('alert');
    expect(errorCard).toBeInTheDocument();
    expect(within(errorCard).getByText(/Build failed: syntax error in main\.py/)).toBeInTheDocument();
  });

  it('AC10: displays alert when step not yet executed (no matching ExecutionStep)', () => {
    // Workflow has step-2 but no matching execution step
    render(
      <StepDetailDrawer
        open
        stepId="step-2"
        executionId={1}
        executionSteps={[mockExecutionSteps[0]]} // Only step 1 executed
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId('step-pending-alert')).toBeInTheDocument();
    expect(screen.getByText('Étape en attente')).toBeInTheDocument();
  });

  it('AC6: updates content when stepId changes (navigation between steps)', () => {
    const { rerender } = render(
      <StepDetailDrawer
        open
        stepId="step-1"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    // Initially shows Build step header
    const header = screen.getByTestId('step-detail-header');
    expect(header.textContent).toContain('Build');
    expect(header.textContent).toContain('#1');

    // Navigate to Deploy step
    rerender(
      <StepDetailDrawer
        open
        stepId="step-2"
        executionId={1}
        executionSteps={mockExecutionSteps}
        workflowSteps={mockWorkflowSteps}
        onClose={vi.fn()}
      />,
    );

    expect(header.textContent).toContain('Deploy');
    expect(header.textContent).toContain('#2');
  });
});
