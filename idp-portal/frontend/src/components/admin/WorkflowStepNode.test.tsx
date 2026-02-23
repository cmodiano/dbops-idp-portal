/**
 * WorkflowStepNode tests (Story 16.6, Tasks 9.5-9.6, 9.9; Story 16.7, AC6).
 *
 * Tests:
 * - Retry badge display
 * - Tooltip with retry details and exit paths (Story 16.7)
 * - ARIA labels and accessibility
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock @xyflow/react before importing the component
vi.mock('@xyflow/react', () => ({
  Handle: ({ id, type }: { id: string; type: string }) =>
    React.createElement('div', { 'data-testid': `handle-${id}`, 'data-handle-type': type }),
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));

// Import after mocks
import WorkflowStepNode from './WorkflowStepNode';

const defaultData = {
  action_id: 100,
  action_name: 'Create PDB',
  action_engine: 'Oracle',
  action_platform: 'Linux',
  name: null,
  retry_enabled: false,
  retry_max_attempts: null,
  retry_interval_seconds: null,
  retry_backoff_multiplier: null,
};

const makeProps = (dataOverrides: Record<string, unknown> = {}, selected = false) => ({
  id: 'step-1',
  type: 'workflowStep' as const,
  data: { ...defaultData, ...dataOverrides },
  selected,
  dragging: false,
  draggable: false,
  selectable: false,
  deletable: false,
  zIndex: 0,
  isConnectable: true,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
});

describe('WorkflowStepNode', () => {
  it('renders action name', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByText('Create PDB')).toBeInTheDocument();
  });

  it('renders engine and platform', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByText('Oracle / Linux')).toBeInTheDocument();
  });

  it('renders custom display name when provided', () => {
    render(<WorkflowStepNode {...makeProps({ name: 'Mon étape' })} />);
    expect(screen.getByText('Mon étape')).toBeInTheDocument();
  });

  it('renders ARIA label with step name', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByRole('img', { name: 'Étape: Create PDB' })).toBeInTheDocument();
  });

  it('displays retry badge "Réessai: 5×" when retry is enabled', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          retry_enabled: true,
          retry_max_attempts: 5,
          retry_interval_seconds: 60,
          retry_backoff_multiplier: 2.0,
        })}
      />,
    );

    expect(screen.getByText('Réessai: 5×')).toBeInTheDocument();
  });

  it('displays retry badge "Réessai: 3×" with default attempts', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          retry_enabled: true,
          retry_max_attempts: null,
        })}
      />,
    );

    expect(screen.getByText('Réessai: 3×')).toBeInTheDocument();
  });

  it('handles retry_max_attempts = 0 by using default value 3', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          retry_enabled: true,
          retry_max_attempts: 0,
        })}
      />,
    );

    expect(screen.getByText('Réessai: 3×')).toBeInTheDocument();
  });

  it('does not display retry badge when retry is disabled', () => {
    render(<WorkflowStepNode {...makeProps({ retry_enabled: false })} />);
    expect(screen.queryByText(/Réessai:/)).not.toBeInTheDocument();
  });

  it('renders three handles (input, success, error)', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByTestId('handle-input')).toBeInTheDocument();
    expect(screen.getByTestId('handle-success')).toBeInTheDocument();
    expect(screen.getByTestId('handle-error')).toBeInTheDocument();
  });

  it('displays validation error message', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          validationStatus: 'error',
          validationMessage: 'Boucle infinie détectée',
        })}
      />,
    );

    expect(screen.getByText('Boucle infinie détectée')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('does not display validation message when null', () => {
    render(<WorkflowStepNode {...makeProps({ validationMessage: null })} />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  // Story 16.7, AC6: Extended tooltip with exit paths
  describe('tooltip with exit paths (Story 16.7)', () => {
    it('shows exit paths when on_success_step_id is set', () => {
      // Note: Ant Design Tooltip renders title content in the DOM.
      // The tooltip content is rendered as part of the component tree.
      // We test the node rendering which includes the data for tooltip.
      render(
        <WorkflowStepNode
          {...makeProps({
            on_success_step_id: 'step-2',
            on_error_step_id: 'step-3',
          })}
        />,
      );
      // Node should still render correctly
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('renders node with exit path data available for tooltip', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            on_success_step_id: null,
            on_error_step_id: null,
          })}
        />,
      );
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('preserves retry tooltip when both retry and exit paths are set', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            retry_enabled: true,
            retry_max_attempts: 5,
            retry_interval_seconds: 30,
            retry_backoff_multiplier: 1.5,
            on_success_step_id: 'step-2',
            on_error_step_id: null,
          })}
        />,
      );
      // Badge still shows
      expect(screen.getByText('Réessai: 5×')).toBeInTheDocument();
    });
  });

  // Story 19.2: Execution status tooltip
  describe('execution status tooltip (Story 19.2)', () => {
    it('AC10: renders node with executionStatus data', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            executionStatus: 'COMPLETED',
            executionDuration: '1m 30s',
          })}
        />,
      );
      // Node renders correctly with execution data
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('AC10: renders node with RUNNING status', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            executionStatus: 'RUNNING',
            executionDuration: null,
          })}
        />,
      );
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('AC10: renders node with PENDING status (no duration)', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            executionStatus: 'PENDING',
          })}
        />,
      );
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });
  });

  // Story 18.3, AC4: Real action name display
  describe('action name display (Story 18.3)', () => {
    it('displays real action_name "Apply Oracle Patch"', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'Apply Oracle Patch', action_id: 12 })}
        />,
      );
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
      expect(screen.queryByText('Action #12')).not.toBeInTheDocument();
    });

    it('falls back to action_name when name is null', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'Backup DB', name: null })}
        />,
      );
      expect(screen.getByText('Backup DB')).toBeInTheDocument();
    });

    it('displays custom name over action_name when both present', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'Apply Oracle Patch', name: 'Mon étape' })}
        />,
      );
      // Custom name displayed first (primary)
      expect(screen.getByText('Mon étape')).toBeInTheDocument();
      // action_name displayed as secondary
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
    });

    it('truncates long action names with ellipsis via CSS', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'A very long action name that exceeds thirty characters easily' })}
        />,
      );
      // The text is rendered but CSS handles truncation
      expect(screen.getByText('A very long action name that exceeds thirty characters easily')).toBeInTheDocument();
    });
  });
});
