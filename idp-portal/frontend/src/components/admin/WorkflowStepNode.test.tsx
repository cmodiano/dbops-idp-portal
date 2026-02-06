/**
 * WorkflowStepNode tests (Story 16.6, Tasks 9.5-9.6, 9.9).
 *
 * Tests:
 * - Retry badge display
 * - Tooltip with retry details
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
});
