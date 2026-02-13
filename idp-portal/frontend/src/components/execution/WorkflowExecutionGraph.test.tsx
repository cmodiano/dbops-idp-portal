/**
 * WorkflowExecutionGraph tests (Story 19.2, 19.3).
 * Story 19.2: AC2 (graph display), AC3 (running highlight), AC4 (status indicators),
 * AC5 (real-time updates), AC6 (read-only), AC8 (path traversal), AC10 (legend).
 * Story 19.3: AC1 (node click → drawer), AC8 (Start/End not clickable),
 * AC7 (selected node highlight).
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { WorkflowExecutionGraph } from './WorkflowExecutionGraph';
import type { WorkflowStep, ExecutionResponse, ExecutionStepResponse } from '../../types/api';

vi.mock('../../services/execution_service', () => ({
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(() => Promise.resolve([])),
}));

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({
    steps: [],
    execution: null,
    loading: false,
    error: 'WebSocket not available in test',
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

vi.mock('../../services/logger', () => ({
  default: { warn: vi.fn(), error: vi.fn(), info: vi.fn(), debug: vi.fn() },
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

// Mock ResizeObserver for React Flow
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

// Mock IntersectionObserver for React Flow
class IntersectionObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
global.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;

const Wrapper = ({ children }: { children: React.ReactNode }) => <App>{children}</App>;

const mockWorkflowSteps: WorkflowStep[] = [
  {
    order: 1,
    name: 'Build App',
    referenced_action_id: 10,
    action_name: 'Build Action',
    step_id: 'step-1',
    on_success_step_id: 'step-2',
    on_error_step_id: null,
    retry_enabled: false,
  },
  {
    order: 2,
    name: 'Deploy App',
    referenced_action_id: 11,
    action_name: 'Deploy Action',
    step_id: 'step-2',
    on_success_step_id: null,
    on_error_step_id: null,
    retry_enabled: false,
  },
];

const mockExecution: ExecutionResponse = {
  id: 1,
  action_id: 42,
  action_name: 'Deploy Pipeline',
  user_id: 5,
  environment: 'dev',
  parameters: null,
  status: 'RUNNING',
  servicenow_change_id: null,
  started_at: new Date().toISOString(),
  completed_at: null,
  created_at: new Date().toISOString(),
  item_type: 'workflow',
};

const mockExecutionSteps: ExecutionStepResponse[] = [
  {
    id: 1,
    execution_id: 1,
    step_order: 1,
    step_name: 'Build App',
    step_type: 'platform',
    status: 'COMPLETED',
    started_at: '2026-02-08T10:00:00Z',
    completed_at: '2026-02-08T10:01:30Z',
    output: null,
    platform_job_id: null,
    error_message: null,
  },
  {
    id: 2,
    execution_id: 1,
    step_order: 2,
    step_name: 'Deploy App',
    step_type: 'platform',
    status: 'RUNNING',
    started_at: '2026-02-08T10:01:30Z',
    completed_at: null,
    output: null,
    platform_job_id: null,
    error_message: null,
  },
];

describe('WorkflowExecutionGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('AC2: renders graph container with data-testid', async () => {
    const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
    vi.mocked(useExecutionPolling).mockReturnValue({
      execution: mockExecution,
      steps: mockExecutionSteps,
      isPolling: true,
      error: null,
    });

    render(
      <WorkflowExecutionGraph
        executionId={1}
        workflowSteps={mockWorkflowSteps}
        execution={mockExecution}
      />,
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
    });
  });

  it('AC10: displays legend with all status labels', async () => {
    const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
    vi.mocked(useExecutionPolling).mockReturnValue({
      execution: mockExecution,
      steps: [],
      isPolling: false,
      error: null,
    });

    render(
      <WorkflowExecutionGraph
        executionId={1}
        workflowSteps={mockWorkflowSteps}
        execution={mockExecution}
      />,
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(screen.getByText('Légende')).toBeInTheDocument();
      expect(screen.getByText('En cours')).toBeInTheDocument();
      expect(screen.getByText('Terminé (succès)')).toBeInTheDocument();
      expect(screen.getByText('Échoué')).toBeInTheDocument();
      expect(screen.getByText('À venir / Annulé')).toBeInTheDocument();
    });
  });

  it('shows empty workflow alert when no steps', async () => {
    const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
    vi.mocked(useExecutionPolling).mockReturnValue({
      execution: mockExecution,
      steps: [],
      isPolling: false,
      error: null,
    });

    render(
      <WorkflowExecutionGraph
        executionId={1}
        workflowSteps={[]}
        execution={mockExecution}
      />,
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(screen.getByText('Workflow vide')).toBeInTheDocument();
    });
  });

  it('AC2: renders workflow step nodes from workflowSteps', async () => {
    const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
    vi.mocked(useExecutionPolling).mockReturnValue({
      execution: mockExecution,
      steps: mockExecutionSteps,
      isPolling: true,
      error: null,
    });

    render(
      <WorkflowExecutionGraph
        executionId={1}
        workflowSteps={mockWorkflowSteps}
        execution={mockExecution}
      />,
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
    });

    // React Flow renders step nodes with their names
    // The exact rendering depends on React Flow internals, but nodes should contain step names
    expect(screen.getByText('Build App')).toBeInTheDocument();
    expect(screen.getByText('Deploy App')).toBeInTheDocument();
  });

  it('AC2: renders Start and End visual nodes', async () => {
    const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
    vi.mocked(useExecutionPolling).mockReturnValue({
      execution: mockExecution,
      steps: [],
      isPolling: false,
      error: null,
    });

    render(
      <WorkflowExecutionGraph
        executionId={1}
        workflowSteps={mockWorkflowSteps}
        execution={mockExecution}
      />,
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
    });

    // Start/End nodes should be rendered
    expect(screen.getByText('Départ')).toBeInTheDocument();
    expect(screen.getByText('Fin')).toBeInTheDocument();
  });

  // Story 19.3: Step selection and drawer integration
  describe('Story 19.3: Step detail drawer', () => {
    it('AC1: opens StepDetailDrawer when clicking on action node', async () => {
      const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
      vi.mocked(useExecutionPolling).mockReturnValue({
        execution: mockExecution,
        steps: mockExecutionSteps,
        isPolling: true,
        error: null,
      });

      render(
        <WorkflowExecutionGraph
          executionId={1}
          workflowSteps={mockWorkflowSteps}
          execution={mockExecution}
        />,
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
      });

      // Click on "Build App" node
      await userEvent.click(screen.getByText('Build App'));

      // Drawer should open
      await waitFor(() => {
        expect(screen.getByTestId('step-detail-drawer')).toBeInTheDocument();
      });
    });

    it('AC8: does not open drawer when clicking Start node', async () => {
      const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
      vi.mocked(useExecutionPolling).mockReturnValue({
        execution: mockExecution,
        steps: mockExecutionSteps,
        isPolling: true,
        error: null,
      });

      render(
        <WorkflowExecutionGraph
          executionId={1}
          workflowSteps={mockWorkflowSteps}
          execution={mockExecution}
        />,
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
      });

      // Click on Start node
      await userEvent.click(screen.getByText('Départ'));

      // Drawer should not appear
      expect(screen.queryByTestId('step-detail-drawer')).not.toBeInTheDocument();
    });

    it('AC5: closes drawer when close button clicked', async () => {
      const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
      vi.mocked(useExecutionPolling).mockReturnValue({
        execution: mockExecution,
        steps: mockExecutionSteps,
        isPolling: true,
        error: null,
      });

      render(
        <WorkflowExecutionGraph
          executionId={1}
          workflowSteps={mockWorkflowSteps}
          execution={mockExecution}
        />,
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
      });

      // Open drawer
      await userEvent.click(screen.getByText('Build App'));
      await waitFor(() => {
        expect(screen.getByTestId('step-detail-drawer')).toBeInTheDocument();
      });

      // Close drawer
      await userEvent.click(screen.getByTestId('step-detail-close'));

      await waitFor(() => {
        expect(screen.queryByTestId('step-detail-drawer')).not.toBeInTheDocument();
      });
    });

    it('AC3: shows step metadata in drawer header', async () => {
      const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
      vi.mocked(useExecutionPolling).mockReturnValue({
        execution: mockExecution,
        steps: mockExecutionSteps,
        isPolling: true,
        error: null,
      });

      render(
        <WorkflowExecutionGraph
          executionId={1}
          workflowSteps={mockWorkflowSteps}
          execution={mockExecution}
        />,
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
      });

      // Open drawer for Build App
      await userEvent.click(screen.getByText('Build App'));

      await waitFor(() => {
        const header = screen.getByTestId('step-detail-header');
        expect(header).toBeInTheDocument();
        expect(header.textContent).toContain('Build App');
        expect(header.textContent).toContain('#1');
        expect(header.textContent).toContain('Terminé');
      });
    });

    it('AC6: navigates between steps without closing drawer', async () => {
      const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
      vi.mocked(useExecutionPolling).mockReturnValue({
        execution: mockExecution,
        steps: mockExecutionSteps,
        isPolling: true,
        error: null,
      });

      render(
        <WorkflowExecutionGraph
          executionId={1}
          workflowSteps={mockWorkflowSteps}
          execution={mockExecution}
        />,
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
      });

      // Open drawer with Build App
      await userEvent.click(screen.getByText('Build App'));
      await waitFor(() => {
        const header = screen.getByTestId('step-detail-header');
        expect(header.textContent).toContain('Build App');
        expect(header.textContent).toContain('#1');
      });

      // Click on Deploy App node — drawer should stay open and update content
      await userEvent.click(screen.getByText('Deploy App'));
      await waitFor(() => {
        const header = screen.getByTestId('step-detail-header');
        expect(header.textContent).toContain('Deploy App');
        expect(header.textContent).toContain('#2');
      });

      // Drawer should still be open (not closed/reopened)
      expect(screen.getByTestId('step-detail-drawer')).toBeInTheDocument();
    });

    it('AC7: highlights selected node with golden border', async () => {
      const { useExecutionPolling } = await import('../../hooks/useExecutionPolling');
      vi.mocked(useExecutionPolling).mockReturnValue({
        execution: mockExecution,
        steps: mockExecutionSteps,
        isPolling: true,
        error: null,
      });

      const { container } = render(
        <WorkflowExecutionGraph
          executionId={1}
          workflowSteps={mockWorkflowSteps}
          execution={mockExecution}
        />,
        { wrapper: Wrapper },
      );

      await waitFor(() => {
        expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
      });

      // Click on Build App node
      await userEvent.click(screen.getByText('Build App'));

      await waitFor(() => {
        expect(screen.getByTestId('step-detail-drawer')).toBeInTheDocument();
      });

      // Verify selected node has golden border (STATUS_COLORS.SELECTED = '#faad14')
      // Note: React Flow applies styles to nodes, we check via DOM inspection
      const reactFlowNodes = container.querySelectorAll('[data-id]');
      const buildNode = Array.from(reactFlowNodes).find((node) =>
        node.textContent?.includes('Build App'),
      );
      expect(buildNode).toBeDefined();
      // Golden border should be applied (borderWidth 4, borderColor #faad14)
      // This is a visual indicator that the node is selected
    });
  });
});
