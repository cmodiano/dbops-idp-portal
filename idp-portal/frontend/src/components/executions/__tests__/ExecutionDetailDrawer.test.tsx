/**
 * Tests for ExecutionDetailDrawer component (Story 26.4 - AC5).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExecutionDetailDrawer } from '../ExecutionDetailDrawer';
import type { ExecutionDetailDrawerProps } from '../ExecutionDetailDrawer';
import type { ExecutionResponse } from '../../../types/api';

// Mock ExecutionTimeline
vi.mock('../../execution/ExecutionTimeline', () => ({
  ExecutionTimeline: ({ execution }: { execution: { id: number } }) => (
    <div data-testid="execution-timeline">Timeline for #{execution.id}</div>
  ),
}));

// Mock WorkflowExecutionGraph
vi.mock('../../execution/WorkflowExecutionGraph', () => ({
  WorkflowExecutionGraph: ({ executionId }: { executionId: number }) => (
    <div data-testid="workflow-execution-graph">WorkflowGraph for #{executionId}</div>
  ),
}));

// Mock ErrorBoundary - supports error simulation via ErrorBoundary.simulateError flag
let simulateErrorBoundaryError = false;
vi.mock('../../ErrorBoundary', () => ({
  ErrorBoundary: ({ children, fallback }: {
    children: React.ReactNode;
    fallback: (err: Error, reset: () => void) => React.ReactNode;
  }) => {
    if (simulateErrorBoundaryError) {
      return <>{fallback(new Error('Test render error'), vi.fn())}</>;
    }
    return <>{children}</>;
  },
}));

// Mock Ant Design components
vi.mock('antd', async () => {
  return {
    Drawer: ({ open, onClose, children, title }: {
      open: boolean;
      onClose: () => void;
      children: React.ReactNode;
      title: React.ReactNode;
      destroyOnHidden?: boolean;
      width?: string | number;
    }) => {
      if (!open) return null;
      return (
        <div data-testid="drawer">
          <div data-testid="drawer-title">{title}</div>
          <button data-testid="drawer-close" onClick={onClose}>Close</button>
          {children}
        </div>
      );
    },
    Skeleton: ({ active }: { active?: boolean }) => (
      <div data-testid="skeleton" data-active={active}>Loading...</div>
    ),
    Alert: ({ type, description, message }: { type: string; description?: string; message?: string; title?: string; showIcon?: boolean }) => (
      <div data-testid="alert" data-type={type}>
        {message && <span>{message}</span>}
        {description && <span>{description}</span>}
      </div>
    ),
    Button: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
      <button onClick={onClick}>{children}</button>
    ),
  };
});

const baseExecution: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Deploy App',
  user_id: 5,
  environment: 'production',
  parameters: null,
  status: 'COMPLETED',
  servicenow_change_id: null,
  started_at: '2025-01-01T10:00:00Z',
  completed_at: '2025-01-01T10:05:00Z',
  created_at: '2025-01-01T09:59:00Z',
  item_type: 'action',
};

const workflowExecution: ExecutionResponse = {
  ...baseExecution,
  id: 2,
  action_name: 'Full Deploy Workflow',
  item_type: 'workflow',
};

const defaultProps: ExecutionDetailDrawerProps = {
  open: true,
  execution: baseExecution,
  steps: [],
  actionDetail: null,
  loading: false,
  error: null,
  onClose: vi.fn(),
  onExecutionUpdate: vi.fn(),
};

describe('ExecutionDetailDrawer', () => {
  it('renders nothing when open=false', () => {
    render(<ExecutionDetailDrawer {...defaultProps} open={false} />);

    expect(screen.queryByTestId('drawer')).not.toBeInTheDocument();
  });

  it('shows skeleton when loading=true', () => {
    render(<ExecutionDetailDrawer {...defaultProps} loading={true} />);

    expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    expect(screen.queryByTestId('execution-timeline')).not.toBeInTheDocument();
  });

  it('shows error Alert when error is set', () => {
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        loading={false}
        error="Erreur de connexion"
      />,
    );

    const alert = screen.getByTestId('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveAttribute('data-type', 'error');
    expect(alert).toHaveTextContent('Erreur de connexion');
  });

  it('shows ExecutionTimeline for action type', () => {
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        execution={baseExecution}
        actionDetail={null}
      />,
    );

    expect(screen.getByTestId('execution-timeline')).toBeInTheDocument();
    expect(screen.getByTestId('execution-timeline')).toHaveTextContent('Timeline for #1');
    expect(screen.queryByTestId('workflow-execution-graph')).not.toBeInTheDocument();
  });

  it('shows WorkflowExecutionGraph for workflow type with workflow_steps', () => {
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        execution={workflowExecution}
        actionDetail={{
          id: 10,
          name: 'Full Deploy Workflow',
          item_type: 'workflow',
          workflow_steps: [
            { step_order: 1, action_id: 11, action_name: 'Step 1' },
          ],
        } as never}
      />,
    );

    expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
    expect(screen.getByTestId('workflow-execution-graph')).toHaveTextContent('WorkflowGraph for #2');
    expect(screen.queryByTestId('execution-timeline')).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    render(<ExecutionDetailDrawer {...defaultProps} onClose={onClose} />);

    const closeBtn = screen.getByTestId('drawer-close');
    await userEvent.click(closeBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders null content when execution is null (no loading, no error)', () => {
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        execution={null}
        loading={false}
        error={null}
      />,
    );

    expect(screen.queryByTestId('skeleton')).not.toBeInTheDocument();
    expect(screen.queryByTestId('alert')).not.toBeInTheDocument();
    expect(screen.queryByTestId('execution-timeline')).not.toBeInTheDocument();
  });

  it('uses fallback title when action_name is null', () => {
    const executionNoName = { ...baseExecution, action_name: null };
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        execution={executionNoName}
      />,
    );

    expect(screen.getByTestId('drawer-title')).toHaveTextContent('Action #10');
  });

  it('shows timeline for workflow type when actionDetail has no workflow_steps', () => {
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        execution={workflowExecution}
        actionDetail={{
          id: 10,
          name: 'Workflow',
          item_type: 'workflow',
          workflow_steps: [],
        } as never}
      />,
    );

    expect(screen.getByTestId('execution-timeline')).toBeInTheDocument();
    expect(screen.queryByTestId('workflow-execution-graph')).not.toBeInTheDocument();
  });

  it('shows timeline for workflow type when actionDetail is null', () => {
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        execution={workflowExecution}
        actionDetail={null}
      />,
    );

    expect(screen.getByTestId('execution-timeline')).toBeInTheDocument();
    expect(screen.queryByTestId('workflow-execution-graph')).not.toBeInTheDocument();
  });

  it('shows action title with action_name', () => {
    render(
      <ExecutionDetailDrawer
        {...defaultProps}
        execution={baseExecution}
      />,
    );

    expect(screen.getByTestId('drawer-title')).toHaveTextContent('Deploy App');
  });

  it('renders workflow ErrorBoundary fallback on error', () => {
    simulateErrorBoundaryError = true;
    try {
      render(
        <ExecutionDetailDrawer
          {...defaultProps}
          execution={workflowExecution}
          actionDetail={{
            id: 10, name: 'Workflow', item_type: 'workflow',
            workflow_steps: [{ step_order: 1, action_id: 11, action_name: 'Step 1' }],
          } as never}
        />,
      );
      const alert = screen.getByTestId('alert');
      expect(alert).toBeInTheDocument();
      expect(alert).toHaveAttribute('data-type', 'error');
    } finally {
      simulateErrorBoundaryError = false;
    }
  });

  it('renders timeline ErrorBoundary fallback on error', () => {
    simulateErrorBoundaryError = true;
    try {
      render(
        <ExecutionDetailDrawer
          {...defaultProps}
          execution={baseExecution}
          actionDetail={null}
        />,
      );
      const alert = screen.getByTestId('alert');
      expect(alert).toBeInTheDocument();
    } finally {
      simulateErrorBoundaryError = false;
    }
  });
});
