/**
 * Tests for TimelineList component (Story 34.12 — SOLID-FE-1).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TimelineList } from './TimelineList';
import type { ExecutionResponse, ExecutionStepResponse } from '../../../types/api';

// Mock TimelineStepItem to avoid deep dependency tree, exposing callbacks
vi.mock('./TimelineStepItem', () => ({
  TimelineStepItem: ({ step, onToggleExpand, onOpenLogs }: { step: { id: number }; onToggleExpand: () => void; onOpenLogs: () => void }) => (
    <div data-testid={`step-${step.id}`}>
      Step {step.id}
      <button onClick={onToggleExpand} data-testid={`toggle-${step.id}`}>toggle</button>
      <button onClick={onOpenLogs} data-testid={`logs-${step.id}`}>logs</button>
    </div>
  ),
}));

// Mock formatDuration utility
vi.mock('./utils', () => ({
  formatDuration: (start: string, end: string) => `${start}->${end}`,
}));

const mockSteps: ExecutionStepResponse[] = [
  {
    id: 1,
    execution_id: 100,
    step_name: 'Step One',
    status: 'COMPLETED',
    started_at: '2026-01-01T10:00:00Z',
    completed_at: '2026-01-01T10:05:00Z',
    output: null,
    error: null,
    order: 1,
  } as unknown as ExecutionStepResponse,
  {
    id: 2,
    execution_id: 100,
    step_name: 'Step Two',
    status: 'FAILED',
    started_at: '2026-01-01T10:06:00Z',
    completed_at: '2026-01-01T10:07:00Z',
    output: null,
    error: 'Something failed',
    order: 2,
  } as unknown as ExecutionStepResponse,
];

const defaultProps = {
  steps: [],
  execution: null,
  embedInWorkflowStepDrawer: false,
  statusAnnouncement: '',
  expandedId: null,
  onToggleExpand: vi.fn(),
  onOpenLogs: vi.fn(),
};

describe('TimelineList', () => {
  it('renders the timeline list container with aria-label', () => {
    render(<TimelineList {...defaultProps} />);
    expect(screen.getByRole('list', { name: "Timeline d'exécution" })).toBeInTheDocument();
  });

  it('renders "Aucune étape à afficher" when steps is empty and execution is null', () => {
    render(<TimelineList {...defaultProps} steps={[]} execution={null} />);
    expect(screen.getByText('Aucune étape à afficher')).toBeInTheDocument();
  });

  it('renders "Aucune étape à afficher" for standalone execution with empty steps', () => {
    const standaloneExecution = {
      id: 100,
      status: 'COMPLETED',
      parent_item_type: null,
      parent_execution_id: null,
    } as unknown as ExecutionResponse;

    render(<TimelineList {...defaultProps} steps={[]} execution={standaloneExecution} />);
    expect(screen.getByText('Aucune étape à afficher')).toBeInTheDocument();
  });

  it('renders workflow parent card when steps empty, execution is a workflow action with parent', () => {
    const workflowStepExecution = {
      id: 200,
      status: 'COMPLETED',
      parent_item_type: 'workflow',
      parent_execution_id: 50,
      started_at: '2026-01-01T10:00:00Z',
      completed_at: '2026-01-01T10:30:00Z',
    } as unknown as ExecutionResponse;

    render(
      <TimelineList
        {...defaultProps}
        steps={[]}
        execution={workflowStepExecution}
        embedInWorkflowStepDrawer={false}
      />
    );

    expect(screen.getByText('Action du workflow')).toBeInTheDocument();
    expect(screen.getByText('Voir le workflow parent')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Voir le workflow parent/i })).toHaveAttribute(
      'href',
      '/executions/50'
    );
  });

  it('renders "Aucune étape à afficher" when embedInWorkflowStepDrawer=true even with workflow parent', () => {
    const workflowStepExecution = {
      id: 200,
      status: 'COMPLETED',
      parent_item_type: 'workflow',
      parent_execution_id: 50,
    } as unknown as ExecutionResponse;

    render(
      <TimelineList
        {...defaultProps}
        steps={[]}
        execution={workflowStepExecution}
        embedInWorkflowStepDrawer={true}
      />
    );

    // When embedded, shows "Aucune étape à afficher" instead of parent card
    expect(screen.getByText('Aucune étape à afficher')).toBeInTheDocument();
    expect(screen.queryByText('Action du workflow')).not.toBeInTheDocument();
  });

  it('renders step items when steps array is non-empty', () => {
    render(<TimelineList {...defaultProps} steps={mockSteps} />);

    expect(screen.getByTestId('step-1')).toBeInTheDocument();
    expect(screen.getByTestId('step-2')).toBeInTheDocument();
    expect(screen.queryByText('Aucune étape à afficher')).not.toBeInTheDocument();
  });

  it('renders aria-live status announcement region', () => {
    render(<TimelineList {...defaultProps} statusAnnouncement="Étape 2 terminée" />);

    // The aria-live region should contain the announcement (positioned off-screen)
    const liveRegion = document.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion?.textContent).toBe('Étape 2 terminée');
  });

  it('renders FAILED status tag in workflow parent card', () => {
    const failedWorkflowStepExecution = {
      id: 300,
      status: 'FAILED',
      parent_item_type: 'workflow',
      parent_execution_id: 75,
      started_at: null,
      completed_at: null,
    } as unknown as ExecutionResponse;

    render(
      <TimelineList
        {...defaultProps}
        steps={[]}
        execution={failedWorkflowStepExecution}
        embedInWorkflowStepDrawer={false}
      />
    );

    expect(screen.getByText('Action du workflow')).toBeInTheDocument();
    expect(screen.getByText('FAILED')).toBeInTheDocument();
  });
});

describe('TimelineList — callbacks coverage', () => {
  it('calls onToggleExpand and onOpenLogs callbacks via step item buttons', () => {
    const onToggleExpand = vi.fn();
    const onOpenLogs = vi.fn();

    render(
      <TimelineList
        {...defaultProps}
        steps={mockSteps}
        onToggleExpand={onToggleExpand}
        onOpenLogs={onOpenLogs}
      />
    );

    // Invoke the onToggleExpand wrapper (line 89)
    fireEvent.click(screen.getByTestId('toggle-1'));
    expect(onToggleExpand).toHaveBeenCalledWith(1);

    // Invoke the onOpenLogs wrapper (line 90)
    fireEvent.click(screen.getByTestId('logs-1'));
    expect(onOpenLogs).toHaveBeenCalledWith(1);
  });
});
